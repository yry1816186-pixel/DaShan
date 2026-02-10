import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import IntEnum
from datetime import datetime

logger = logging.getLogger(__name__)


class PluginType(IntEnum):
    COMMAND = 0
    FILTER = 1
    PROVIDER = 2
    EXTENSION = 3


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    min_dashan_version: str = "2.0.0"
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    icon: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "plugin_type": self.plugin_type.name,
            "min_dashan_version": self.min_dashan_version,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "config_schema": self.config_schema,
            "icon": self.icon
        }


@dataclass
class PluginContext:
    system: Any
    agent: Any
    voice_manager: Any
    face_tracker: Any
    protocol_client: Any
    config: Dict[str, Any] = field(default_factory=dict)
    
    def get_system(self):
        return self.system
    
    def get_agent(self):
        return self.agent
    
    def get_voice_manager(self):
        return self.voice_manager
    
    def get_protocol_client(self):
        return self.protocol_client
    
    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        self.config[key] = value


@dataclass
class PluginResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }


class Plugin(ABC):
    def __init__(self, context: PluginContext):
        self.context = context
        self._enabled = True
        self._initialized = False
        self._event_handlers: Dict[str, List[Callable]] = {}
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        pass
    
    @abstractmethod
    async def initialize(self) -> PluginResult:
        pass
    
    @abstractmethod
    async def shutdown(self) -> PluginResult:
        pass
    
    async def execute(self, command: str, params: Dict[str, Any] = None) -> PluginResult:
        return PluginResult(
            success=False,
            error=f"Command not implemented: {command}"
        )
    
    async def on_event(self, event_name: str, event_data: Dict[str, Any]) -> PluginResult:
        return PluginResult(success=True)
    
    def is_enabled(self) -> bool:
        return self._enabled
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    def enable(self):
        self._enabled = True
        logger.info(f"Plugin {self.info.name} enabled")
    
    def disable(self):
        self._enabled = False
        logger.info(f"Plugin {self.info.name} disabled")
    
    def register_event_handler(self, event_name: str, handler: Callable):
        if event_name not in self._event_handlers:
            self._event_handlers[event_name] = []
        self._event_handlers[event_name].append(handler)
        logger.debug(f"Registered event handler: {event_name}")
    
    def unregister_event_handler(self, event_name: str, handler: Callable):
        if event_name in self._event_handlers and handler in self._event_handlers[event_name]:
            self._event_handlers[event_name].remove(handler)
            logger.debug(f"Unregistered event handler: {event_name}")
    
    async def emit_event(self, event_name: str, event_data: Dict[str, Any]):
        handlers = self._event_handlers.get(event_name, [])
        for handler in handlers:
            try:
                result = handler(event_name, event_data)
                if isinstance(result, PluginResult):
                    logger.debug(f"Event handler result: {result.success}")
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.info.name,
            "version": self.info.version,
            "enabled": self._enabled,
            "initialized": self._initialized,
            "event_handlers": len(self._event_handlers)
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        schema = self.info.config_schema
        if not schema:
            return True
        
        for key, spec in schema.items():
            if key not in config:
                if spec.get("required", False):
                    logger.error(f"Missing required config: {key}")
                    return False
            else:
                value = config[key]
                expected_type = spec.get("type")
                
                if expected_type and not isinstance(value, expected_type):
                    logger.error(f"Invalid type for {key}: expected {expected_type}")
                    return False
                
                min_val = spec.get("min")
                max_val = spec.get("max")
                
                if min_val is not None and value < min_val:
                    logger.error(f"Value {value} below minimum {min_val} for {key}")
                    return False
                
                if max_val is not None and value > max_val:
                    logger.error(f"Value {value} above maximum {max_val} for {key}")
                    return False
        
        return True
    
    def save_config(self, config_path: str) -> bool:
        import yaml
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.context.config, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"Config saved to: {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def load_config(self, config_path: str) -> bool:
        import yaml
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.context.config = yaml.safe_load(f) or {}
            logger.info(f"Config loaded from: {config_path}")
            return True
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False


class CommandPlugin(Plugin):
    @abstractmethod
    async def execute_command(self, command: str, params: Dict[str, Any] = None) -> PluginResult:
        pass
    
    async def execute(self, command: str, params: Dict[str, Any] = None) -> PluginResult:
        return await self.execute_command(command, params)
    
    @abstractmethod
    def get_commands(self) -> List[Dict[str, Any]]:
        pass


class FilterPlugin(Plugin):
    @abstractmethod
    async def filter_input(self, input_text: str, metadata: Dict[str, Any] = None) -> PluginResult:
        pass
    
    @abstractmethod
    async def filter_output(self, output_text: str, metadata: Dict[str, Any] = None) -> PluginResult:
        pass


class ProviderPlugin(Plugin):
    @abstractmethod
    async def provide(self, request_type: str, data: Dict[str, Any] = None) -> PluginResult:
        pass
    
    @abstractmethod
    def get_provided_services(self) -> List[str]:
        pass


class ExtensionPlugin(Plugin):
    @abstractmethod
    def get_ui_components(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def get_api_routes(self) -> List[Dict[str, Any]]:
        pass
