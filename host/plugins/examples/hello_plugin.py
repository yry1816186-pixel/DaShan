from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..plugin_base import Plugin, PluginInfo, PluginContext, PluginResult, PluginType, CommandPlugin


@dataclass
class HelloConfig:
    greeting: str = "你好"
    include_emoji: bool = True
    greeting_language: str = "zh"


class HelloPlugin(CommandPlugin):
    
    def __init__(self, config: Optional[HelloConfig] = None):
        self._config = config or HelloConfig()
        self._context: Optional[PluginContext] = None
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="hello_plugin",
            name="Hello Plugin",
            version="1.0.0",
            type=PluginType.COMMAND,
            author="DaShan Team",
            description="A simple greeting plugin that demonstrates the plugin system",
            dependencies=[],
            permissions=["text_output"],
            config_schema={
                "greeting": {"type": "string", "default": "你好"},
                "include_emoji": {"type": "boolean", "default": True},
                "greeting_language": {"type": "string", "default": "zh"}
            }
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        self._context = context
        return PluginResult(success=True, message="Hello plugin initialized")
    
    async def shutdown(self) -> PluginResult:
        self._context = None
        return PluginResult(success=True, message="Hello plugin shutdown")
    
    async def execute(self, params: Dict[str, Any]) -> PluginResult:
        name = params.get("name", "世界")
        greeting = self._config.greeting
        
        if self._config.include_emoji:
            if self._config.greeting_language == "zh":
                greeting += " 👋"
            elif self._config.greeting_language == "en":
                greeting += " 🤖"
        
        message = f"{greeting}，{name}！"
        
        return PluginResult(
            success=True,
            message=message,
            data={
                "greeting": greeting,
                "name": name,
                "full_message": message
            }
        )
    
    async def on_event(self, event: str, data: Any) -> PluginResult:
        if event == "user_greeting":
            return await self.execute({"name": data.get("name", "用户")})
        return PluginResult(success=True, message=f"Event {event} received")
    
    def export_config(self) -> Dict[str, Any]:
        return {
            "greeting": self._config.greeting,
            "include_emoji": self._config.include_emoji,
            "greeting_language": self._config.greeting_language
        }
    
    async def import_config(self, config: Dict[str, Any]) -> PluginResult:
        try:
            if "greeting" in config:
                self._config.greeting = config["greeting"]
            if "include_emoji" in config:
                self._config.include_emoji = config["include_emoji"]
            if "greeting_language" in config:
                self._config.greeting_language = config["greeting_language"]
            return PluginResult(success=True, message="Configuration imported")
        except Exception as e:
            return PluginResult(success=False, message=f"Failed to import config: {str(e)}")
