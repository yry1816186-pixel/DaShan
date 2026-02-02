import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Memory:
    id: str
    content: str
    type: str
    timestamp: str
    importance: float = 1.0
    access_count: int = 0


@dataclass
class UserProfile:
    name: str = "User"
    preferences: Dict[str, Any] = None
    facts: List[str] = None
    interaction_count: int = 0
    first_met: str = None

    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}
        if self.facts is None:
            self.facts = []
        if self.first_met is None:
            self.first_met = datetime.now().isoformat()


class MemoryManager:
    def __init__(self, storage_path: str = "data/memory"):
        self.storage_path = storage_path
        self.memories: List[Memory] = []
        self.user_profile = UserProfile()
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self):
        os.makedirs(self.storage_path, exist_ok=True)

    def _load(self):
        try:
            profile_path = os.path.join(self.storage_path, "profile.json")
            if os.path.exists(profile_path):
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_profile = UserProfile(**data)
            
            memories_path = os.path.join(self.storage_path, "memories.json")
            if os.path.exists(memories_path):
                with open(memories_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories = [Memory(**m) for m in data]
            
            logger.info(f"Loaded {len(self.memories)} memories")
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")

    def _save(self):
        try:
            profile_path = os.path.join(self.storage_path, "profile.json")
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self.user_profile), f, ensure_ascii=False, indent=2)
            
            memories_path = os.path.join(self.storage_path, "memories.json")
            with open(memories_path, 'w', encoding='utf-8') as f:
                data = [asdict(m) for m in self.memories]
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug("Memories saved")
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    def add_memory(self, content: str, memory_type: str = "general", importance: float = 1.0):
        memory_id = f"mem_{len(self.memories)}_{datetime.now().timestamp()}"
        memory = Memory(
            id=memory_id,
            content=content,
            type=memory_type,
            timestamp=datetime.now().isoformat(),
            importance=importance
        )
        self.memories.append(memory)
        self._trim_memories()
        self._save()
        logger.debug(f"Added memory: {content[:50]}...")

    def _trim_memories(self, max_memories: int = 100):
        if len(self.memories) > max_memories:
            self.memories.sort(key=lambda m: m.importance * (m.access_count + 1))
            self.memories = self.memories[-max_memories:]

    def get_memories(self, memory_type: Optional[str] = None, limit: int = 10) -> List[Memory]:
        if memory_type:
            filtered = [m for m in self.memories if m.type == memory_type]
        else:
            filtered = self.memories
        
        filtered.sort(key=lambda m: (m.importance * (m.access_count + 1)), reverse=True)
        return filtered[:limit]

    def search_memories(self, query: str, limit: int = 5) -> List[Memory]:
        query_lower = query.lower()
        scored = []
        
        for memory in self.memories:
            score = 0
            content_lower = memory.content.lower()
            
            if query_lower in content_lower:
                score += 10
            
            for word in query_lower.split():
                if word in content_lower:
                    score += 1
            
            if score > 0:
                scored.append((memory, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in scored[:limit]]

    def update_preference(self, key: str, value: Any):
        self.user_profile.preferences[key] = value
        self._save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.user_profile.preferences.get(key, default)

    def add_fact(self, fact: str):
        if fact not in self.user_profile.facts:
            self.user_profile.facts.append(fact)
            self._save()

    def get_facts(self, limit: int = 10) -> List[str]:
        return self.user_profile.facts[-limit:]

    def increment_interaction(self):
        self.user_profile.interaction_count += 1
        self._save()

    def get_interaction_count(self) -> int:
        return self.user_profile.interaction_count

    def set_name(self, name: str):
        self.user_profile.name = name
        self.add_fact(f"用户的名字是{name}")
        self._save()

    def get_name(self) -> str:
        return self.user_profile.name

    def get_context_for_llm(self) -> str:
        context_parts = []
        
        context_parts.append(f"用户名字: {self.user_profile.name}")
        
        if self.user_profile.preferences:
            prefs_str = ", ".join([f"{k}={v}" for k, v in self.user_profile.preferences.items()])
            context_parts.append(f"用户偏好: {prefs_str}")
        
        if self.user_profile.facts:
            facts_str = "; ".join(self.user_profile.facts[-5:])
            context_parts.append(f"用户信息: {facts_str}")
        
        recent_memories = self.get_memories(limit=3)
        if recent_memories:
            mem_str = "; ".join([m.content for m in recent_memories])
            context_parts.append(f"最近记忆: {mem_str}")
        
        return "\n".join(context_parts)

    def clear(self):
        self.memories = []
        self.user_profile = UserProfile()
        self._save()

    def export(self, filepath: str):
        data = {
            "profile": asdict(self.user_profile),
            "memories": [asdict(m) for m in self.memories]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported memories to {filepath}")

    def import_(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.user_profile = UserProfile(**data["profile"])
            self.memories = [Memory(**m) for m in data["memories"]]
            self._save()
            logger.info(f"Imported memories from {filepath}")
        except Exception as e:
            logger.error(f"Failed to import memories: {e}")


if __name__ == "__main__":
    memory = MemoryManager()
    
    print("Memory Manager Test")
    
    memory.add_memory("用户喜欢吃苹果", "preference", importance=2.0)
    memory.add_memory("用户是程序员", "fact", importance=1.5)
    memory.add_memory("用户住在上海", "fact", importance=1.0)
    
    memory.set_name("张三")
    memory.update_preference("color", "blue")
    memory.increment_interaction()
    
    print(f"\nUser: {memory.get_name()}")
    print(f"Interactions: {memory.get_interaction_count()}")
    print(f"Color preference: {memory.get_preference('color')}")
    
    print("\nRecent memories:")
    for mem in memory.get_memories(limit=3):
        print(f"  - {mem.content}")
    
    print("\nSearch results for '苹果':")
    for mem in memory.search_memories("苹果"):
        print(f"  - {mem.content}")
    
    print("\nContext for LLM:")
    print(memory.get_context_for_llm())
