import asyncio
import logging
from typing import Dict, List, Optional, Type, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import orjson
from pathlib import Path
import importlib
import sys
from datetime import datetime

from .plugin_base import (
    Plugin, PluginInfo, PluginContext, PluginResult,
    PluginType, PluginStatus, CommandPlugin, FilterPlugin,
    ProviderPlugin, ExtensionPlugin
)
from .plugin_loader import PluginLoader, PluginLoadResult

logger = logging.getLogger(__name__)


@dataclass
class PluginInstance:
    plugin: Plugin
    status: PluginStatus = PluginStatus.LOADED
    enabled: bool = True
    load_time: datetime = field(default_factory=datetime.now)
    last_error: Optional[str] = None
    execution_stats: Dict[str, Any] = field(default_factory=dict)
    event_handlers: Dict[str, List[Callable]] = field(default_factory=dict)


@dataclass
class PluginExecutionRequest:
    plugin_id: str
    method: str
    kwargs: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0


@dataclass
class PluginExecutionResult:
    plugin_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class PluginManager:
    def __init__(
        self,
        plugin_dirs: List[Path],
        context: PluginContext,
        auto_load: bool = True
    ):
        self.plugin_dirs = [Path(d) for d in plugin_dirs]
        self.context = context
        self.loader = PluginLoader(plugin_dirs)
        self._plugins: Dict[str, PluginInstance] = {}
        self._plugin_map: Dict[PluginType, Dict[str, PluginInstance]] = {
            pt: {} for pt in PluginType
        }
        self._lock = asyncio.Lock()
        self._global_hooks: Dict[str, List[Callable]] = {}
        
        if auto_load:
            asyncio.create_task(self.load_all_plugins())

    async def load_all_plugins(self) -> Dict[str, PluginLoadResult]:
        async with self._lock:
            results = await self.loader.discover_and_load()
            for plugin_id, load_result in results.items():
                if load_result.success:
                    await self._initialize_plugin(load_result.plugin, plugin_id)
            return results

    async def _initialize_plugin(self, plugin: Plugin, plugin_id: str) -> PluginInstance:
        try:
            info = plugin.info
            instance = PluginInstance(plugin=plugin, status=PluginStatus.LOADED)
            
            await plugin.initialize(self.context)
            
            instance.status = PluginStatus.READY
            instance.enabled = True
            
            self._plugins[plugin_id] = instance
            self._plugin_map[info.type][plugin_id] = instance
            
            logger.info(f"Plugin {plugin_id} ({info.name}) initialized successfully")
            return instance
        except Exception as e:
            logger.error(f"Failed to initialize plugin {plugin_id}: {e}")
            instance = PluginInstance(plugin=plugin, status=PluginStatus.ERROR, last_error=str(e))
            self._plugins[plugin_id] = instance
            return instance

    async def load_plugin(self, plugin_path: Path) -> Optional[PluginInstance]:
        async with self._lock:
            result = await self.loader.load_plugin(plugin_path)
            if result.success:
                return await self._initialize_plugin(result.plugin, result.plugin_id)
            return None

    async def unload_plugin(self, plugin_id: str) -> bool:
        async with self._lock:
            if plugin_id not in self._plugins:
                return False
            
            instance = self._plugins[plugin_id]
            plugin = instance.plugin
            
            try:
                await plugin.shutdown()
                instance.status = PluginStatus.UNLOADED
                
                info = plugin.info
                if plugin_id in self._plugin_map[info.type]:
                    del self._plugin_map[info.type][plugin_id]
                
                del self._plugins[plugin_id]
                logger.info(f"Plugin {plugin_id} unloaded successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to unload plugin {plugin_id}: {e}")
                instance.last_error = str(e)
                return False

    async def enable_plugin(self, plugin_id: str) -> bool:
        async with self._lock:
            if plugin_id not in self._plugins:
                return False
            
            instance = self._plugins[plugin_id]
            instance.enabled = True
            logger.info(f"Plugin {plugin_id} enabled")
            return True

    async def disable_plugin(self, plugin_id: str) -> bool:
        async with self._lock:
            if plugin_id not in self._plugins:
                return False
            
            instance = self._plugins[plugin_id]
            instance.enabled = False
            logger.info(f"Plugin {plugin_id} disabled")
            return True

    async def reload_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        async with self._lock:
            if plugin_id not in self._plugins:
                return None
            
            instance = self._plugins[plugin_id]
            plugin_path = instance.plugin.__module__
            
            await self.unload_plugin(plugin_id)
            
            try:
                module = importlib.import_module(plugin_path)
                importlib.reload(module)
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                        plugin_instance = attr()
                        return await self._initialize_plugin(plugin_instance, plugin_id)
            except Exception as e:
                logger.error(f"Failed to reload plugin {plugin_id}: {e}")
                return None

    async def execute_plugin(
        self,
        request: PluginExecutionRequest
    ) -> PluginExecutionResult:
        start_time = asyncio.get_event_loop().time()
        
        if request.plugin_id not in self._plugins:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=False,
                error="Plugin not found"
            )
        
        instance = self._plugins[request.plugin_id]
        
        if not instance.enabled:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=False,
                error="Plugin is disabled"
            )
        
        if instance.status != PluginStatus.READY:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=False,
                error=f"Plugin status is {instance.status.value}"
            )
        
        try:
            result = await asyncio.wait_for(
                self._execute_plugin_method(instance, request),
                timeout=request.timeout
            )
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            stats_key = f"{request.method}_count"
            instance.execution_stats[stats_key] = instance.execution_stats.get(stats_key, 0) + 1
            instance.execution_stats[f"{request.method}_last_time"] = execution_time
            
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=result.success,
                result=result.data,
                error=result.message,
                execution_time=execution_time
            )
        except asyncio.TimeoutError:
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=False,
                error=f"Execution timeout after {request.timeout}s",
                execution_time=request.timeout
            )
        except Exception as e:
            logger.error(f"Error executing plugin {request.plugin_id}: {e}")
            return PluginExecutionResult(
                plugin_id=request.plugin_id,
                success=False,
                error=str(e),
                execution_time=asyncio.get_event_loop().time() - start_time
            )

    async def _execute_plugin_method(
        self,
        instance: PluginInstance,
        request: PluginExecutionRequest
    ) -> PluginResult:
        plugin = instance.plugin
        
        if request.method == "execute":
            if isinstance(plugin, CommandPlugin):
                return await plugin.execute(request.kwargs)
            else:
                return PluginResult(success=False, message="Plugin does not support execute method")
        elif request.method == "filter":
            if isinstance(plugin, FilterPlugin):
                return await plugin.filter(request.kwargs.get("data"), request.kwargs.get("context"))
            else:
                return PluginResult(success=False, message="Plugin does not support filter method")
        elif request.method == "provide":
            if isinstance(plugin, ProviderPlugin):
                return await plugin.provide(request.kwargs.get("request_data"), request.kwargs.get("context"))
            else:
                return PluginResult(success=False, message="Plugin does not support provide method")
        elif request.method == "on_event":
            event = request.kwargs.get("event")
            data = request.kwargs.get("data")
            return await plugin.on_event(event, data)
        else:
            return PluginResult(success=False, message=f"Unknown method: {request.method}")

    async def broadcast_event(self, event: str, data: Any = None) -> List[PluginResult]:
        tasks = []
        for plugin_id, instance in self._plugins.items():
            if instance.enabled and instance.status == PluginStatus.READY:
                task = self.execute_plugin(
                    PluginExecutionRequest(
                        plugin_id=plugin_id,
                        method="on_event",
                        kwargs={"event": event, "data": data}
                    )
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]

    def get_plugin(self, plugin_id: str) -> Optional[PluginInstance]:
        return self._plugins.get(plugin_id)

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[PluginInstance]:
        return list(self._plugin_map[plugin_type].values())

    def get_enabled_plugins(self) -> List[PluginInstance]:
        return [p for p in self._plugins.values() if p.enabled]

    def get_plugin_info(self, plugin_id: str) -> Optional[PluginInfo]:
        instance = self._plugins.get(plugin_id)
        if instance:
            return instance.plugin.info
        return None

    def get_all_plugin_infos(self) -> Dict[str, PluginInfo]:
        return {
            plugin_id: instance.plugin.info
            for plugin_id, instance in self._plugins.items()
        }

    def get_plugin_status(self, plugin_id: str) -> Optional[PluginStatus]:
        instance = self._plugins.get(plugin_id)
        return instance.status if instance else None

    def get_plugin_stats(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        instance = self._plugins.get(plugin_id)
        if instance:
            return {
                "status": instance.status.value,
                "enabled": instance.enabled,
                "load_time": instance.load_time.isoformat(),
                "last_error": instance.last_error,
                "execution_stats": instance.execution_stats
            }
        return None

    def register_hook(self, event: str, callback: Callable):
        if event not in self._global_hooks:
            self._global_hooks[event] = []
        self._global_hooks[event].append(callback)

    def unregister_hook(self, event: str, callback: Callable):
        if event in self._global_hooks:
            self._global_hooks[event].remove(callback)

    async def trigger_hook(self, event: str, *args, **kwargs):
        if event in self._global_hooks:
            for hook in self._global_hooks[event]:
                try:
                    if asyncio.iscoroutinefunction(hook):
                        await hook(*args, **kwargs)
                    else:
                        hook(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in hook {event}: {e}")

    async def shutdown_all(self):
        tasks = []
        for plugin_id in list(self._plugins.keys()):
            tasks.append(self.unload_plugin(plugin_id))
        await asyncio.gather(*tasks)

    def export_config(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        instance = self._plugins.get(plugin_id)
        if instance:
            return instance.plugin.export_config()
        return None

    async def import_config(self, plugin_id: str, config: Dict[str, Any]) -> bool:
        instance = self._plugins.get(plugin_id)
        if instance:
            try:
                await instance.plugin.import_config(config)
                return True
            except Exception as e:
                logger.error(f"Failed to import config for plugin {plugin_id}: {e}")
                return False
        return False

    def get_plugin_dependencies(self, plugin_id: str) -> List[str]:
        info = self.get_plugin_info(plugin_id)
        if info:
            return info.dependencies
        return []

    async def check_dependencies(self, plugin_id: str) -> Dict[str, bool]:
        dependencies = self.get_plugin_dependencies(plugin_id)
        result = {}
        for dep in dependencies:
            result[dep] = dep in self._plugins and self._plugins[dep].enabled
        return result

    async def validate_plugin_permissions(self, plugin_id: str) -> bool:
        info = self.get_plugin_info(plugin_id)
        if not info:
            return False
        
        for perm in info.permissions:
            if perm not in self.context.config.get("permissions", []):
                logger.warning(f"Plugin {plugin_id} requires permission {perm} which is not granted")
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugins": {
                plugin_id: {
                    "info": {
                        "name": instance.plugin.info.name,
                        "version": instance.plugin.info.version,
                        "type": instance.plugin.info.type.value,
                        "author": instance.plugin.info.author,
                        "description": instance.plugin.info.description
                    },
                    "status": instance.status.value,
                    "enabled": instance.enabled,
                    "load_time": instance.load_time.isoformat(),
                    "last_error": instance.last_error,
                    "execution_stats": instance.execution_stats
                }
                for plugin_id, instance in self._plugins.items()
            },
            "plugin_dirs": [str(d) for d in self.plugin_dirs],
            "total_plugins": len(self._plugins),
            "enabled_plugins": len([p for p in self._plugins.values() if p.enabled])
        }

    def save_state(self, file_path: Path) -> bool:
        try:
            state = {
                "plugins": {
                    plugin_id: {
                        "enabled": instance.enabled,
                        "config": instance.plugin.export_config()
                    }
                    for plugin_id, instance in self._plugins.items()
                },
                "timestamp": datetime.now().isoformat()
            }
            file_path.write_bytes(orjson.dumps(state))
            return True
        except Exception as e:
            logger.error(f"Failed to save plugin state: {e}")
            return False

    async def load_state(self, file_path: Path) -> bool:
        try:
            if not file_path.exists():
                return False
            
            state = orjson.loads(file_path.read_bytes())
            
            for plugin_id, plugin_state in state.get("plugins", {}).items():
                instance = self._plugins.get(plugin_id)
                if instance:
                    if plugin_state.get("enabled", True):
                        await self.enable_plugin(plugin_id)
                    else:
                        await self.disable_plugin(plugin_id)
                    
                    config = plugin_state.get("config")
                    if config:
                        await self.import_config(plugin_id, config)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin state: {e}")
            return False
