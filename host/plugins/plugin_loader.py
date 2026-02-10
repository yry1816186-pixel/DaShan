import asyncio
import logging
import importlib.util
import sys
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Set, Type
from dataclasses import dataclass, field
import importlib

from .plugin_base import Plugin, PluginInfo, PluginType

logger = logging.getLogger(__name__)


@dataclass
class PluginLoadResult:
    plugin_id: str
    plugin: Plugin
    success: bool = True
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    load_time: float = 0.0


@dataclass
class PluginDiscoveryResult:
    plugin_path: Path
    plugin_id: Optional[str] = None
    plugin_class: Optional[Type[Plugin]] = None
    info: Optional[PluginInfo] = None
    loadable: bool = False
    error: Optional[str] = None


class PluginLoader:
    def __init__(self, plugin_dirs: List[Path], recursive: bool = True):
        self.plugin_dirs = [Path(d) for d in plugin_dirs]
        self.recursive = recursive
        self._loaded_modules: Dict[str, importlib.types.ModuleType] = {}
        self._discovered_plugins: Dict[str, PluginDiscoveryResult] = {}

    async def discover_and_load(
        self,
        filter_types: Optional[List[PluginType]] = None
    ) -> Dict[str, PluginLoadResult]:
        await self.discover_plugins()
        
        results = {}
        for plugin_id, discovery in self._discovered_plugins.items():
            if not discovery.loadable:
                continue
            
            if filter_types and discovery.info and discovery.info.type not in filter_types:
                continue
            
            result = await self._load_plugin_from_discovery(discovery)
            results[plugin_id] = result
        
        return results

    async def discover_plugins(self) -> Dict[str, PluginDiscoveryResult]:
        self._discovered_plugins = {}
        
        discovery_tasks = []
        for plugin_dir in self.plugin_dirs:
            if plugin_dir.exists() and plugin_dir.is_dir():
                discovery_tasks.append(self._discover_in_directory(plugin_dir))
        
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                self._discovered_plugins.update(result)
        
        return self._discovered_plugins

    async def _discover_in_directory(self, directory: Path) -> Dict[str, PluginDiscoveryResult]:
        results = {}
        
        for item in directory.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                discovery = await self._discover_file(item)
                if discovery.plugin_id:
                    results[discovery.plugin_id] = discovery
            
            elif item.is_dir() and self.recursive:
                init_file = item / "__init__.py"
                if init_file.exists():
                    discovery = await self._discover_file(init_file)
                    if discovery.plugin_id:
                        results[discovery.plugin_id] = discovery
                
                for sub_item in item.iterdir():
                    if sub_item.is_file() and sub_item.suffix == ".py" and not sub_item.name.startswith("_"):
                        discovery = await self._discover_file(sub_item)
                        if discovery.plugin_id:
                            results[discovery.plugin_id] = discovery
        
        return results

    async def _discover_file(self, file_path: Path) -> PluginDiscoveryResult:
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{file_path.stem}",
                file_path
            )
            if spec is None or spec.loader is None:
                return PluginDiscoveryResult(
                    plugin_path=file_path,
                    loadable=False,
                    error="Could not create module spec"
                )
            
            module = importlib.util.module_from_spec(spec)
            
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                return PluginDiscoveryResult(
                    plugin_path=file_path,
                    loadable=False,
                    error=f"Failed to load module: {str(e)}"
                )
            
            plugin_classes = self._find_plugin_classes(module)
            
            if not plugin_classes:
                return PluginDiscoveryResult(
                    plugin_path=file_path,
                    loadable=False,
                    error="No plugin class found"
                )
            
            plugin_class = plugin_classes[0]
            plugin_instance = plugin_class()
            info = plugin_instance.info
            
            plugin_id = info.id or f"{info.name}_{info.version}".replace(" ", "_").lower()
            
            return PluginDiscoveryResult(
                plugin_path=file_path,
                plugin_id=plugin_id,
                plugin_class=plugin_class,
                info=info,
                loadable=True
            )
        
        except Exception as e:
            return PluginDiscoveryResult(
                plugin_path=file_path,
                loadable=False,
                error=f"Discovery error: {str(e)}"
            )

    def _find_plugin_classes(self, module) -> List[Type[Plugin]]:
        plugin_classes = []
        
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, Plugin) and obj != Plugin and obj.__module__ == module.__name__:
                plugin_classes.append(obj)
        
        return sorted(plugin_classes, key=lambda cls: cls.__name__)

    async def load_plugin(self, plugin_path: Path) -> PluginLoadResult:
        discovery = await self._discover_file(plugin_path)
        if not discovery.loadable:
            return PluginLoadResult(
                plugin_id=plugin_path.stem,
                plugin=None,
                success=False,
                error=discovery.error or "Plugin not loadable"
            )
        
        return await self._load_plugin_from_discovery(discovery)

    async def _load_plugin_from_discovery(
        self,
        discovery: PluginDiscoveryResult
    ) -> PluginLoadResult:
        start_time = asyncio.get_event_loop().time()
        
        try:
            plugin = discovery.plugin_class()
            info = plugin.info
            
            plugin_id = info.id or f"{info.name}_{info.version}".replace(" ", "_").lower()
            
            warnings = []
            
            if not info.name:
                warnings.append("Plugin name is empty")
            
            if not info.version:
                warnings.append("Plugin version is not specified")
            
            if not info.description:
                warnings.append("Plugin description is missing")
            
            for dep in info.dependencies:
                if dep not in sys.modules:
                    try:
                        importlib.import_module(dep)
                    except ImportError:
                        warnings.append(f"Dependency {dep} may not be installed")
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return PluginLoadResult(
                plugin_id=plugin_id,
                plugin=plugin,
                success=True,
                warnings=warnings,
                load_time=execution_time
            )
        
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"Failed to load plugin from {discovery.plugin_path}: {e}")
            return PluginLoadResult(
                plugin_id=discovery.plugin_path.stem,
                plugin=None,
                success=False,
                error=str(e),
                load_time=execution_time
            )

    async def load_plugin_by_id(self, plugin_id: str) -> Optional[PluginLoadResult]:
        if plugin_id not in self._discovered_plugins:
            await self.discover_plugins()
        
        discovery = self._discovered_plugins.get(plugin_id)
        if discovery and discovery.loadable:
            return await self._load_plugin_from_discovery(discovery)
        
        return None

    def get_discovered_plugins(self) -> Dict[str, PluginDiscoveryResult]:
        return self._discovered_plugins.copy()

    def get_discovered_plugin_ids(self) -> List[str]:
        return list(self._discovered_plugins.keys())

    def get_discovered_plugins_by_type(self, plugin_type: PluginType) -> Dict[str, PluginDiscoveryResult]:
        return {
            pid: discovery
            for pid, discovery in self._discovered_plugins.items()
            if discovery.info and discovery.info.type == plugin_type
        }

    async def validate_plugin(self, plugin_class: Type[Plugin]) -> List[str]:
        warnings = []
        
        try:
            plugin_instance = plugin_class()
            info = plugin_instance.info
        except Exception as e:
            return [f"Failed to instantiate plugin: {str(e)}"]
        
        if not isinstance(info, PluginInfo):
            warnings.append("info property must return a PluginInfo instance")
        
        if not info.name:
            warnings.append("Plugin name is required")
        
        if not info.version:
            warnings.append("Plugin version is required")
        
        if not info.author:
            warnings.append("Plugin author is recommended")
        
        if not info.description:
            warnings.append("Plugin description is recommended")
        
        required_methods = ["initialize", "shutdown"]
        for method in required_methods:
            if not hasattr(plugin_class, method):
                warnings.append(f"Missing required method: {method}")
        
        if info.type == PluginType.COMMAND and not hasattr(plugin_class, "execute"):
            warnings.append("Command plugins must implement execute method")
        
        if info.type == PluginType.FILTER and not hasattr(plugin_class, "filter"):
            warnings.append("Filter plugins must implement filter method")
        
        if info.type == PluginType.PROVIDER and not hasattr(plugin_class, "provide"):
            warnings.append("Provider plugins must implement provide method")
        
        return warnings

    async def check_plugin_compatibility(
        self,
        plugin: Plugin,
        required_version: Optional[str] = None
    ) -> bool:
        info = plugin.info
        
        if required_version and not self._check_version(info.version, required_version):
            return False
        
        return True

    def _check_version(self, plugin_version: str, required_version: str) -> bool:
        try:
            from packaging import version
            return version.parse(plugin_version) >= version.parse(required_version)
        except Exception:
            return True

    def get_plugin_manifest(self, plugin: Plugin) -> Dict[str, any]:
        info = plugin.info
        
        return {
            "id": info.id,
            "name": info.name,
            "version": info.version,
            "type": info.type.value,
            "author": info.author,
            "description": info.description,
            "dependencies": info.dependencies,
            "permissions": info.permissions,
            "config_schema": info.config_schema,
            "python_version": sys.version.split()[0]
        }

    def clear_cache(self):
        self._discovered_plugins.clear()
        self._loaded_modules.clear()

    def add_plugin_directory(self, directory: Path):
        dir_path = Path(directory)
        if dir_path not in self.plugin_dirs:
            self.plugin_dirs.append(dir_path)

    def remove_plugin_directory(self, directory: Path):
        dir_path = Path(directory)
        if dir_path in self.plugin_dirs:
            self.plugin_dirs.remove(dir_path)
