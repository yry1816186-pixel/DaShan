from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import IntEnum
from datetime import datetime
import json


class AgentStatus(IntEnum):
    IDLE = 0
    PROCESSING = 1
    THINKING = 2
    RESPONDING = 3
    ERROR = 4
    OFFLINE = 5


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {})
        )


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "duration": self.duration
        }


@dataclass
class MemoryItem:
    content: str
    importance: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    embeddings: Optional[List[float]] = None
    access_count: int = 0
    
    def decay(self, rate: float = 0.01):
        self.importance *= (1 - rate)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "access_count": self.access_count
        }


@dataclass
class AgentState:
    status: AgentStatus = AgentStatus.IDLE
    conversation: List[Message] = field(default_factory=list)
    current_input: Optional[str] = None
    current_output: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[ToolCall] = field(default_factory=list)
    short_term_memory: List[MemoryItem] = field(default_factory=list)
    long_term_memory: List[MemoryItem] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_start: Optional[datetime] = None
    processing_end: Optional[datetime] = None
    user_profile: Dict[str, Any] = field(default_factory=dict)
    mode: str = "chat"
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.conversation.append(msg)
        if len(self.conversation) > 50:
            self.conversation = self.conversation[-50:]
    
    def add_tool_call(self, name: str, arguments: Dict[str, Any]):
        self.tool_calls.append(ToolCall(name=name, arguments=arguments))
    
    def add_memory(self, content: str, importance: float = 1.0, tags: List[str] = None):
        item = MemoryItem(content=content, importance=importance, tags=tags or [])
        self.short_term_memory.append(item)
        if len(self.short_term_memory) > 50:
            self.short_term_memory = self.short_term_memory[-50:]
    
    def get_recent_conversation(self, n: int = 5) -> List[Message]:
        return self.conversation[-n:]
    
    def get_context_summary(self) -> str:
        if not self.conversation:
            return "无对话历史"
        
        recent = self.get_recent_conversation(3)
        summary = "最近对话:\n"
        for msg in recent:
            summary += f"{msg.role}: {msg.content[:50]}...\n"
        return summary
    
    def clear_conversation(self):
        self.conversation.clear()
        self.tool_calls.clear()
    
    def get_processing_duration(self) -> Optional[float]:
        if self.processing_start and self.processing_end:
            return (self.processing_end - self.processing_start).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.name,
            "conversation": [m.to_dict() for m in self.conversation[-10:]],
            "current_input": self.current_input,
            "current_output": self.current_output,
            "context": self.context,
            "tool_calls": [t.to_dict() for t in self.tool_calls[-5:]],
            "memory_count": len(self.short_term_memory),
            "error_message": self.error_message,
            "processing_duration": self.get_processing_duration(),
            "mode": self.mode
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)
