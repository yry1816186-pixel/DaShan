import logging
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from abc import ABC, abstractmethod
import time

logger = logging.getLogger(__name__)


class NodeStatus(IntEnum):
    SUCCESS = 0
    FAILURE = 1
    RUNNING = 2
    INVALID = 3


@dataclass
class NodeContext:
    blackboard: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    elapsed_time: float = 0.0
    node_stack: List[str] = field(default_factory=list)
    
    def update_time(self):
        self.elapsed_time = time.time() - self.start_time
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.blackboard.get(key, self.variables.get(key, default))
    
    def set(self, key: str, value: Any):
        self.blackboard[key] = value
    
    def set_var(self, key: str, value: Any):
        self.variables[key] = value
    
    def reset(self):
        self.blackboard.clear()
        self.variables.clear()
        self.start_time = time.time()
        self.elapsed_time = 0.0
        self.node_stack.clear()


class BaseNode(ABC):
    def __init__(
        self,
        name: str,
        description: str = "",
        priority: int = 0
    ):
        self.name = name
        self.description = description
        self.priority = priority
        self._parent = None
        self._status = NodeStatus.INVALID
        self._execution_count = 0
        self._last_execution_time: float = 0.0
        self._total_execution_time: float = 0.0
        self._callbacks: Dict[str, List[Callable]] = {
            "on_start": [],
            "on_success": [],
            "on_failure": [],
            "on_running": []
        }
    
    @abstractmethod
    def execute(self, context: NodeContext) -> NodeStatus:
        pass
    
    @abstractmethod
    def reset(self):
        self._status = NodeStatus.INVALID
    
    @property
    def parent(self) -> Optional['BaseNode']:
        return self._parent
    
    @parent.setter
    def parent(self, node: Optional['BaseNode']):
        self._parent = node
    
    @property
    def status(self) -> NodeStatus:
        return self._status
    
    @property
    def depth(self) -> int:
        depth = 0
        parent = self._parent
        while parent:
            depth += 1
            parent = parent._parent
        return depth
    
    def tick(self, context: NodeContext) -> NodeStatus:
        context.node_stack.append(self.name)
        self._execution_count += 1
        
        start_time = time.time()
        
        self._emit("on_start", context)
        
        try:
            self._status = self.execute(context)
            
            if self._status == NodeStatus.SUCCESS:
                self._emit("on_success", context)
            elif self._status == NodeStatus.FAILURE:
                self._emit("on_failure", context)
            elif self._status == NodeStatus.RUNNING:
                self._emit("on_running", context)
            
            execution_time = time.time() - start_time
            self._last_execution_time = execution_time
            self._total_execution_time += execution_time
            
            context.update_time()
            
            logger.debug(f"Node {self.name} -> {self._status.name} ({execution_time:.3f}s)")
            
            return self._status
        except Exception as e:
            logger.error(f"Node {self.name} execution error: {e}")
            self._status = NodeStatus.FAILURE
            self._emit("on_failure", context)
            return self._status
    
    def on(self, event: str, callback: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, context: NodeContext):
        for callback in self._callbacks.get(event, []):
            try:
                callback(self, context)
            except Exception as e:
                logger.error(f"Callback error in {self.name}.{event}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self._status.name,
            "execution_count": self._execution_count,
            "last_execution_time": self._last_execution_time,
            "total_execution_time": self._total_execution_time,
            "avg_execution_time": (
                self._total_execution_time / self._execution_count
                if self._execution_count > 0 else 0
            ),
            "priority": self.priority,
            "depth": self.depth
        }
    
    def get_children(self) -> List['BaseNode']:
        return []
    
    def find_node(self, name: str) -> Optional['BaseNode']:
        if self.name == name:
            return self
        for child in self.get_children():
            found = child.find_node(name)
            if found:
                return found
        return None
    
    def to_dot(self, indent: int = 0) -> str:
        prefix = "  " * indent
        status_icon = {
            NodeStatus.SUCCESS: "✓",
            NodeStatus.FAILURE: "✗",
            NodeStatus.RUNNING: "⟳",
            NodeStatus.INVALID: "○"
        }
        icon = status_icon.get(self._status, "?")
        
        lines = [f"{prefix}{icon} {self.name} (priority={self.priority})"]
        
        for child in self.get_children():
            lines.append(child.to_dot(indent + 1))
        
        return "\n".join(lines)


class CompositeNode(BaseNode):
    def __init__(self, name: str, children: List[BaseNode] = None, **kwargs):
        super().__init__(name, **kwargs)
        self._children = children or []
        
        for child in self._children:
            child.parent = self
    
    def add_child(self, child: BaseNode):
        self._children.append(child)
        child.parent = self
    
    def remove_child(self, child: BaseNode):
        if child in self._children:
            self._children.remove(child)
            child.parent = None
    
    def get_children(self) -> List[BaseNode]:
        return self._children.copy()
    
    def reset(self):
        super().reset()
        for child in self._children:
            child.reset()


class BehaviorTree:
    def __init__(self, root: BaseNode, name: str = "DaShan_BT"):
        self.root = root
        self.name = name
        self.context = NodeContext()
        self._running = False
        self._tick_interval = 0.016
        self._tick_count = 0
        self._last_tick_time: float = 0.0
        self._tick_stats = {
            "total_ticks": 0,
            "success_ticks": 0,
            "failure_ticks": 0,
            "running_ticks": 0
        }
    
    def tick(self) -> NodeStatus:
        self._tick_count += 1
        status = self.root.tick(self.context)
        
        self._tick_stats["total_ticks"] = self._tick_count
        
        if status == NodeStatus.SUCCESS:
            self._tick_stats["success_ticks"] += 1
        elif status == NodeStatus.FAILURE:
            self._tick_stats["failure_ticks"] += 1
        elif status == NodeStatus.RUNNING:
            self._tick_stats["running_ticks"] += 1
        
        return status
    
    def update(self, dt: float):
        self.context.update_time()
        self._last_tick_time = time.time()
        return self.tick()
    
    def run(self, max_ticks: Optional[int] = None):
        self._running = True
        ticks = 0
        
        try:
            while self._running and (max_ticks is None or ticks < max_ticks):
                status = self.tick()
                
                if status != NodeStatus.RUNNING:
                    self._running = False
                
                time.sleep(self._tick_interval)
                ticks += 1
                
                if self._tick_count % 100 == 0:
                    logger.info(f"BT: {self._tick_count} ticks, status={status.name}")
        
        except KeyboardInterrupt:
            logger.info("BehaviorTree stopped by user")
        finally:
            self._running = False
            logger.info(f"BehaviorTree stopped: {self._tick_count} ticks")
    
    def stop(self):
        self._running = False
        logger.info("BehaviorTree stop requested")
    
    def reset(self):
        self.context.reset()
        self.root.reset()
        self._tick_count = 0
        self._tick_stats = {
            "total_ticks": 0,
            "success_ticks": 0,
            "failure_ticks": 0,
            "running_ticks": 0
        }
        logger.info("BehaviorTree reset")
    
    def set_variable(self, key: str, value: Any):
        self.context.set_var(key, value)
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)
    
    def set_blackboard(self, key: str, value: Any):
        self.context.set(key, value)
    
    def get_blackboard(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)
    
    def find_node(self, name: str) -> Optional[BaseNode]:
        return self.root.find_node(name)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "running": self._running,
            "tick_count": self._tick_count,
            "tick_stats": self._tick_stats,
            "context_vars": self.context.variables.copy(),
            "blackboard_keys": list(self.context.blackboard.keys()),
            "root_stats": self.root.get_stats()
        }
    
    def visualize(self) -> str:
        return f"""
Behavior Tree: {self.name}
{'=' * 50}
{self.root.to_dot()}
{'=' * 50}
Stats: {self.get_stats()}
"""
    
    def export_to_dot(self) -> str:
        lines = [
            "digraph BehaviorTree {",
            "  node [shape=box];",
            f'  label="{self.name}";',
            ""
        ]
        
        lines.extend(self._node_to_dot(self.root))
        
        lines.append("}")
        return "\n".join(lines)
    
    def _node_to_dot(self, node: BaseNode, parent_id: str = None) -> List[str]:
        lines = []
        node_id = f'"{node.name}_{id(node)}"'
        
        colors = {
            NodeStatus.SUCCESS: "green",
            NodeStatus.FAILURE: "red",
            NodeStatus.RUNNING: "blue",
            NodeStatus.INVALID: "gray"
        }
        color = colors.get(node._status, "white")
        
        lines.append(f'  {node_id} [label="{node.name}", fillcolor={color}, style=filled];')
        
        if parent_id:
            lines.append(f'  {parent_id} -> {node_id};')
        
        for child in node.get_children():
            lines.extend(self._node_to_dot(child, node_id))
        
        return lines
    
    @property
    def tick_interval(self) -> float:
        return self._tick_interval
    
    @tick_interval.setter
    def tick_interval(self, value: float):
        self._tick_interval = max(0.001, value)
