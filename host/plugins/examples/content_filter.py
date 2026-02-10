import re
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass

from ..plugin_base import Plugin, PluginInfo, PluginContext, PluginResult, PluginType, FilterPlugin


@dataclass
class FilterConfig:
    blocked_words: Set[str] = None
    blocked_patterns: List[str] = None
    max_length: int = 1000
    min_length: int = 1
    mode: str = "block"
    
    def __post_init__(self):
        if self.blocked_words is None:
            self.blocked_words = {
                "脏话", "暴力", "非法", "黑客", "破解"
            }
        if self.blocked_patterns is None:
            self.blocked_patterns = [
                r'(?i).*\b(password|token|secret|key)\b.*',
                r'(?i).*\b(xxx|adult)\b.*'
            }


class ContentFilterPlugin(FilterPlugin):
    
    def __init__(self, config: Optional[FilterConfig] = None):
        self._config = config or FilterConfig()
        self._context: Optional[PluginContext] = None
        self._compiled_patterns: List[re.Pattern] = []
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="content_filter",
            name="Content Filter Plugin",
            version="1.0.0",
            type=PluginType.FILTER,
            author="DaShan Team",
            description="Content filtering plugin for blocking inappropriate content",
            dependencies=[],
            permissions=["text_filter"],
            config_schema={
                "blocked_words": {"type": "array", "items": {"type": "string"}},
                "blocked_patterns": {"type": "array", "items": {"type": "string"}},
                "max_length": {"type": "integer", "default": 1000},
                "min_length": {"type": "integer", "default": 1},
                "mode": {"type": "string", "enum": ["block", "replace", "flag"]}
            }
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        self._context = context
        self._compiled_patterns = [
            re.compile(pattern) for pattern in self._config.blocked_patterns
        ]
        return PluginResult(
            success=True,
            message=f"Content filter initialized with {len(self._config.blocked_words)} blocked words"
        )
    
    async def shutdown(self) -> PluginResult:
        self._compiled_patterns.clear()
        self._context = None
        return PluginResult(success=True, message="Content filter shutdown")
    
    async def filter(
        self,
        data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> PluginResult:
        if not isinstance(data, str):
            return PluginResult(
                success=True,
                message="Non-string data passed through",
                data={"filtered": False, "original": data}
            )
        
        text = data
        
        if len(text) < self._config.min_length:
            return PluginResult(
                success=False,
                message=f"Text too short (minimum {self._config.min_length} characters)",
                data={"filtered": True, "reason": "too_short", "original": text}
            )
        
        if len(text) > self._config.max_length:
            return PluginResult(
                success=False,
                message=f"Text too long (maximum {self._config.max_length} characters)",
                data={"filtered": True, "reason": "too_long", "original": text}
            )
        
        for word in self._config.blocked_words:
            if word.lower() in text.lower():
                if self._config.mode == "block":
                    return PluginResult(
                        success=False,
                        message=f"Blocked word found: {word}",
                        data={
                            "filtered": True,
                            "reason": "blocked_word",
                            "blocked_word": word,
                            "original": text
                        }
                    )
                elif self._config.mode == "replace":
                    text = re.sub(re.escape(word), "***", text, flags=re.IGNORECASE)
                elif self._config.mode == "flag":
                    return PluginResult(
                        success=True,
                        message=f"Flagged content: {word}",
                        data={
                            "filtered": False,
                            "flagged": True,
                            "reason": "blocked_word",
                            "blocked_word": word,
                            "original": text
                        }
                    )
        
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                if self._config.mode == "block":
                    return PluginResult(
                        success=False,
                        message=f"Blocked pattern matched",
                        data={
                            "filtered": True,
                            "reason": "blocked_pattern",
                            "pattern": pattern.pattern,
                            "original": text
                        }
                    )
                elif self._config.mode == "replace":
                    text = pattern.sub("***", text)
                elif self._config.mode == "flag":
                    return PluginResult(
                        success=True,
                        message=f"Flagged content: pattern matched",
                        data={
                            "filtered": False,
                            "flagged": True,
                            "reason": "blocked_pattern",
                            "pattern": pattern.pattern,
                            "original": text
                        }
                    )
        
        if self._config.mode == "replace" and text != data:
            return PluginResult(
                success=True,
                message="Content filtered and replaced",
                data={
                    "filtered": True,
                    "original": data,
                    "filtered_text": text
                }
            )
        
        return PluginResult(
            success=True,
            message="Content passed filter",
            data={"filtered": False, "original": text}
        )
    
    async def on_event(self, event: str, data: Any) -> PluginResult:
        if event == "config_update":
            await self._update_config(data)
        return PluginResult(success=True, message=f"Event {event} received")
    
    async def _update_config(self, new_config: Dict[str, Any]):
        if "blocked_words" in new_config:
            self._config.blocked_words = set(new_config["blocked_words"])
        if "blocked_patterns" in new_config:
            self._config.blocked_patterns = new_config["blocked_patterns"]
            self._compiled_patterns = [
                re.compile(pattern) for pattern in self._config.blocked_patterns
            ]
        if "max_length" in new_config:
            self._config.max_length = new_config["max_length"]
        if "min_length" in new_config:
            self._config.min_length = new_config["min_length"]
        if "mode" in new_config:
            self._config.mode = new_config["mode"]
    
    async def add_blocked_word(self, word: str) -> PluginResult:
        self._config.blocked_words.add(word)
        return PluginResult(success=True, message=f"Added blocked word: {word}")
    
    async def remove_blocked_word(self, word: str) -> PluginResult:
        if word in self._config.blocked_words:
            self._config.blocked_words.remove(word)
            return PluginResult(success=True, message=f"Removed blocked word: {word}")
        return PluginResult(success=False, message=f"Blocked word not found: {word}")
    
    async def get_blocked_words(self) -> List[str]:
        return list(self._config.blocked_words)
    
    def export_config(self) -> Dict[str, Any]:
        return {
            "blocked_words": list(self._config.blocked_words),
            "blocked_patterns": self._config.blocked_patterns,
            "max_length": self._config.max_length,
            "min_length": self._config.min_length,
            "mode": self._config.mode
        }
    
    async def import_config(self, config: Dict[str, Any]) -> PluginResult:
        try:
            if "blocked_words" in config:
                self._config.blocked_words = set(config["blocked_words"])
            if "blocked_patterns" in config:
                self._config.blocked_patterns = config["blocked_patterns"]
                self._compiled_patterns = [
                    re.compile(pattern) for pattern in self._config.blocked_patterns
                ]
            if "max_length" in config:
                self._config.max_length = config["max_length"]
            if "min_length" in config:
                self._config.min_length = config["min_length"]
            if "mode" in config:
                self._config.mode = config["mode"]
            return PluginResult(success=True, message="Configuration imported")
        except Exception as e:
            return PluginResult(success=False, message=f"Failed to import config: {str(e)}")
