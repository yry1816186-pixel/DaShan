from abc import ABC, abstractmethod
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import inspect
import time

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "enum": self.enum
        }


class BaseTool(ABC):
    def __init__(self):
        self._description: str = ""
        self._parameters: List[ToolParameter] = []
        self._enabled: bool = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    def description(self) -> str:
        return self._description or self.__class__.__doc__ or "No description"
    
    @property
    def parameters(self) -> List[ToolParameter]:
        if not self._parameters:
            self._parameters = self._get_parameters_from_signature()
        return self._parameters
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass
    
    def _get_parameters_from_signature(self) -> List[ToolParameter]:
        sig = inspect.signature(self.execute)
        params = []
        
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            
            required = param.default == inspect.Parameter.empty
            default = param.default if not required else None
            
            params.append(ToolParameter(
                name=name,
                type=param_type,
                description=f"Parameter {name}",
                required=required,
                default=default
            ))
        
        return params
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "enabled": self._enabled
        }
    
    def enable(self):
        self._enabled = True
    
    def disable(self):
        self._enabled = False


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_aliases: Dict[str, str] = {}
    
    def register(self, tool: BaseTool, aliases: List[str] = None):
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must be instance of BaseTool, got {type(tool)}")
        
        self._tools[tool.name] = tool
        
        if aliases:
            for alias in aliases:
                self._tool_aliases[alias] = tool.name
        
        logger.info(f"Registered tool: {tool.name} (aliases: {aliases})")
    
    def unregister(self, tool_name: str):
        if tool_name in self._tools:
            del self._tools[tool_name]
            self._tool_aliases = {k: v for k, v in self._tool_aliases.items() if v != tool_name}
            logger.info(f"Unregistered tool: {tool_name}")
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        resolved_name = self._tool_aliases.get(tool_name, tool_name)
        return self._tools.get(resolved_name)
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        if not tool._enabled:
            raise RuntimeError(f"Tool is disabled: {tool_name}")
        
        logger.info(f"Executing tool: {tool_name} with args: {kwargs}")
        
        start_time = time.time()
        try:
            result = await tool.execute(**kwargs)
            duration = time.time() - start_time
            logger.info(f"Tool {tool_name} completed in {duration:.2f}s")
            return {"success": True, "result": result, "duration": duration}
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"success": False, "error": str(e), "duration": duration}
    
    def list_tools(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        tools = self._tools.values()
        if enabled_only:
            tools = [t for t in tools if t._enabled]
        return [t.to_dict() for t in tools]
    
    def get_tool_descriptions(self) -> str:
        descriptions = []
        for tool in self._tools.values():
            if tool._enabled:
                params_desc = ", ".join([f"{p.name}({p.type})" for p in tool.parameters])
                descriptions.append(f"- {tool.name}: {tool.description} [{params_desc}]")
        return "\n".join(descriptions) if descriptions else "No tools available"


class SearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "search"
    
    @property
    def _description(self) -> str:
        return "Search the internet for information"
    
    async def execute(self, query: str, max_results: int = 5) -> str:
        import httpx
        
        search_url = f"https://duckduckgo.com/html/?q={query}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(search_url)
            
            if response.status_code == 200:
                import re
                results = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', response.text, re.DOTALL)
                results = [r.replace('<b>', '').replace('</b>', '') for r in results[:max_results]]
                return "\n".join(results) if results else "No results found"
            
            return "Search failed"


class CalculatorTool(BaseTool):
    @property
    def name(self) -> str:
        return "calculate"
    
    @property
    def _description(self) -> str:
        return "Perform mathematical calculations"
    
    async def execute(self, expression: str) -> str:
        try:
            allowed = set('0123456789+-*/(). ')
            if not all(c in allowed for c in expression):
                return "Invalid characters in expression"
            
            result = eval(expression)
            return f"{expression} = {result}"
        except Exception as e:
            return f"Calculation error: {e}"


class TimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_time"
    
    @property
    def _description(self) -> str:
        return "Get current time and date"
    
    async def execute(self) -> str:
        from datetime import datetime
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S %A")


class WeatherTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_weather"
    
    @property
    def _description(self) -> str:
        return "Get weather information for a location"
    
    async def execute(self, location: str) -> str:
        import httpx
        
        url = f"https://wttr.in/{location}?format=j1"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                return f"Temperature: {data.get('current_temperature', 'N/A')}°C, Condition: {data.get('weather', 'N/A')}"
            return "Weather information unavailable"


class MemoryTool(BaseTool):
    def __init__(self, memory_manager=None):
        super().__init__()
        self.memory_manager = memory_manager
    
    @property
    def name(self) -> str:
        return "remember"
    
    @property
    def _description(self) -> str:
        return "Store information in memory"
    
    async def execute(self, content: str, importance: float = 1.0, tags: str = None) -> str:
        if self.memory_manager:
            tag_list = tags.split(',') if tags else []
            self.memory_manager.add_memory(content, importance, tag_list)
            return f"Remembered: {content[:50]}..."
        return "Memory not available"
