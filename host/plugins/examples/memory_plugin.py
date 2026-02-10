from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from ..plugin_base import Plugin, PluginInfo, PluginContext, PluginResult, PluginType, ProviderPlugin


@dataclass
class MemoryEntry:
    key: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


@dataclass
class MemoryConfig:
    max_entries: int = 1000
    persist_to_disk: bool = True
    storage_path: str = "data/plugin_memory.json"
    auto_save: bool = True


class MemoryPlugin(ProviderPlugin):
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        self._config = config or MemoryConfig()
        self._context: Optional[PluginContext] = None
        self._memories: Dict[str, MemoryEntry] = {}
        self._tags_index: Dict[str, set] = {}
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            id="memory_plugin",
            name="Memory Plugin",
            version="1.0.0",
            type=PluginType.PROVIDER,
            author="DaShan Team",
            description="Persistent memory storage plugin for storing and retrieving data",
            dependencies=[],
            permissions=["file_read", "file_write"],
            config_schema={
                "max_entries": {"type": "integer", "default": 1000},
                "persist_to_disk": {"type": "boolean", "default": True},
                "storage_path": {"type": "string", "default": "data/plugin_memory.json"},
                "auto_save": {"type": "boolean", "default": True}
            }
        )
    
    async def initialize(self, context: PluginContext) -> PluginResult:
        self._context = context
        
        if self._config.persist_to_disk:
            await self._load_from_disk()
        
        return PluginResult(success=True, message=f"Memory plugin initialized with {len(self._memories)} entries")
    
    async def shutdown(self) -> PluginResult:
        if self._config.persist_to_disk and self._config.auto_save:
            await self._save_to_disk()
        self._context = None
        return PluginResult(success=True, message="Memory plugin shutdown")
    
    async def provide(self, request: Dict[str, Any], context: Optional[Dict] = None) -> PluginResult:
        action = request.get("action", "get")
        
        if action == "get":
            return await self._get_memory(request.get("key"), request.get("default"))
        elif action == "set":
            return await self._set_memory(
                request.get("key"),
                request.get("value"),
                request.get("tags", [])
            )
        elif action == "delete":
            return await self._delete_memory(request.get("key"))
        elif action == "list":
            return await self._list_memories(request.get("tags", []))
        elif action == "search":
            return await self._search_memories(request.get("query", ""))
        elif action == "clear":
            return await self._clear_all()
        else:
            return PluginResult(success=False, message=f"Unknown action: {action}")
    
    async def _get_memory(self, key: str, default: Any = None) -> PluginResult:
        if key in self._memories:
            entry = self._memories[key]
            return PluginResult(
                success=True,
                message=f"Retrieved memory: {key}",
                data={
                    "key": entry.key,
                    "value": entry.value,
                    "timestamp": entry.timestamp.isoformat(),
                    "tags": entry.tags
                }
            )
        else:
            return PluginResult(
                success=False,
                message=f"Memory not found: {key}",
                data={"key": key, "default": default}
            )
    
    async def _set_memory(self, key: str, value: Any, tags: List[str] = None) -> PluginResult:
        if len(self._memories) >= self._config.max_entries:
            oldest_key = min(self._memories.keys(), key=lambda k: self._memories[k].timestamp)
            await self._delete_memory(oldest_key)
        
        entry = MemoryEntry(
            key=key,
            value=value,
            timestamp=datetime.now(),
            tags=tags or []
        )
        
        if key in self._memories:
            old_entry = self._memories[key]
            for tag in old_entry.tags:
                if tag in self._tags_index:
                    self._tags_index[tag].discard(key)
        
        self._memories[key] = entry
        
        for tag in entry.tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(key)
        
        if self._config.persist_to_disk and self._config.auto_save:
            await self._save_to_disk()
        
        return PluginResult(
            success=True,
            message=f"Memory set: {key}",
            data={"key": key, "value": value, "tags": entry.tags}
        )
    
    async def _delete_memory(self, key: str) -> PluginResult:
        if key in self._memories:
            entry = self._memories[key]
            for tag in entry.tags:
                if tag in self._tags_index:
                    self._tags_index[tag].discard(key)
            
            del self._memories[key]
            
            if self._config.persist_to_disk and self._config.auto_save:
                await self._save_to_disk()
            
            return PluginResult(success=True, message=f"Memory deleted: {key}")
        else:
            return PluginResult(success=False, message=f"Memory not found: {key}")
    
    async def _list_memories(self, tags: List[str] = None) -> PluginResult:
        if tags:
            matching_keys = set()
            for tag in tags:
                if tag in self._tags_index:
                    matching_keys.update(self._tags_index[tag])
            memories = {k: self._memories[k] for k in matching_keys if k in self._memories}
        else:
            memories = self._memories
        
        return PluginResult(
            success=True,
            message=f"Found {len(memories)} memories",
            data={
                "count": len(memories),
                "memories": [
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "timestamp": entry.timestamp.isoformat(),
                        "tags": entry.tags
                    }
                    for entry in memories.values()
                ]
            }
        )
    
    async def _search_memories(self, query: str) -> PluginResult:
        query_lower = query.lower()
        results = []
        
        for entry in self._memories.values():
            if (query_lower in entry.key.lower() or 
                query_lower in str(entry.value).lower() or
                any(query_lower in tag.lower() for tag in entry.tags)):
                results.append(entry)
        
        return PluginResult(
            success=True,
            message=f"Found {len(results)} matching memories",
            data={
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "timestamp": entry.timestamp.isoformat(),
                        "tags": entry.tags
                    }
                    for entry in results
                ]
            }
        )
    
    async def _clear_all(self) -> PluginResult:
        count = len(self._memories)
        self._memories.clear()
        self._tags_index.clear()
        
        if self._config.persist_to_disk and self._config.auto_save:
            await self._save_to_disk()
        
        return PluginResult(success=True, message=f"Cleared {count} memories")
    
    async def _save_to_disk(self) -> bool:
        try:
            storage_path = Path(self._config.storage_path)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "memories": [
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "timestamp": entry.timestamp.isoformat(),
                        "tags": entry.tags
                    }
                    for entry in self._memories.values()
                ]
            }
            
            storage_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            return True
        except Exception as e:
            return False
    
    async def _load_from_disk(self) -> bool:
        try:
            storage_path = Path(self._config.storage_path)
            if not storage_path.exists():
                return True
            
            data = json.loads(storage_path.read_text())
            
            for mem_data in data.get("memories", []):
                entry = MemoryEntry(
                    key=mem_data["key"],
                    value=mem_data["value"],
                    timestamp=datetime.fromisoformat(mem_data["timestamp"]),
                    tags=mem_data.get("tags", [])
                )
                self._memories[entry.key] = entry
                
                for tag in entry.tags:
                    if tag not in self._tags_index:
                        self._tags_index[tag] = set()
                    self._tags_index[tag].add(entry.key)
            
            return True
        except Exception as e:
            return False
    
    def export_config(self) -> Dict[str, Any]:
        return {
            "max_entries": self._config.max_entries,
            "persist_to_disk": self._config.persist_to_disk,
            "storage_path": self._config.storage_path,
            "auto_save": self._config.auto_save
        }
    
    async def import_config(self, config: Dict[str, Any]) -> PluginResult:
        try:
            if "max_entries" in config:
                self._config.max_entries = config["max_entries"]
            if "persist_to_disk" in config:
                self._config.persist_to_disk = config["persist_to_disk"]
            if "storage_path" in config:
                self._config.storage_path = config["storage_path"]
            if "auto_save" in config:
                self._config.auto_save = config["auto_save"]
            return PluginResult(success=True, message="Configuration imported")
        except Exception as e:
            return PluginResult(success=False, message=f"Failed to import config: {str(e)}")
