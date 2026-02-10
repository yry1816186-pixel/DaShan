import logging
from typing import List, Optional, Callable
from .behavior_tree import BaseNode, CompositeNode, NodeStatus, NodeContext

logger = logging.getLogger(__name__)


class SequenceNode(CompositeNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        for child in self._children:
            status = child.tick(context)
            
            if status != NodeStatus.SUCCESS:
                return status
        
        return NodeStatus.SUCCESS
    
    def reset(self):
        super().reset()


class SelectorNode(CompositeNode):
    def __init__(self, name: str, children: List[BaseNode] = None, use_priority: bool = False, **kwargs):
        super().__init__(name, children, **kwargs)
        self.use_priority = use_priority
    
    def execute(self, context: NodeContext) -> NodeStatus:
        children = sorted(self._children, key=lambda c: c.priority, reverse=True) if self.use_priority else self._children
        
        for child in children:
            status = child.tick(context)
            
            if status != NodeStatus.FAILURE:
                return status
        
        return NodeStatus.FAILURE


class ParallelNode(CompositeNode):
    def __init__(
        self,
        name: str,
        children: List[BaseNode] = None,
        policy: str = "all",
        **kwargs
    ):
        super().__init__(name, children, **kwargs)
        self.policy = policy
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._children:
            return NodeStatus.FAILURE
        
        results = [child.tick(context) for child in self._children]
        
        if self.policy == "all":
            if all(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            elif any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            else:
                return NodeStatus.FAILURE
        
        elif self.policy == "any":
            if any(r == NodeStatus.SUCCESS for r in results):
                return NodeStatus.SUCCESS
            elif any(r == NodeStatus.RUNNING for r in results):
                return NodeStatus.RUNNING
            elif all(r == NodeStatus.FAILURE for r in results):
                return NodeStatus.FAILURE
            else:
                return NodeStatus.RUNNING
        
        elif self.policy == "one":
            for status in results:
                if status != NodeStatus.FAILURE:
                    return status
            return NodeStatus.FAILURE
        
        else:
            logger.warning(f"Unknown parallel policy: {self.policy}")
            return NodeStatus.FAILURE


class DecoratorNode(BaseNode):
    def __init__(self, name: str, child: BaseNode = None, **kwargs):
        super().__init__(name, **kwargs)
        self._child = child
        
        if child:
            child.parent = self
    
    @property
    def child(self) -> Optional[BaseNode]:
        return self._child
    
    @child.setter
    def child(self, node: BaseNode):
        self._child = node
        if node:
            node.parent = self
    
    def reset(self):
        super().reset()
        if self._child:
            self._child.reset()
    
    def get_children(self) -> List[BaseNode]:
        return [self._child] if self._child else []


class ActionNode(BaseNode):
    def __init__(
        self,
        name: str,
        action: Callable[[NodeContext], NodeStatus],
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self._action = action
    
    def execute(self, context: NodeContext) -> NodeStatus:
        try:
            return self._action(context)
        except Exception as e:
            logger.error(f"Action {self.name} failed: {e}")
            return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()


class ConditionNode(BaseNode):
    def __init__(
        self,
        name: str,
        condition: Callable[[NodeContext], bool],
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self._condition = condition
    
    def execute(self, context: NodeContext) -> NodeStatus:
        try:
            result = self._condition(context)
            return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception as e:
            logger.error(f"Condition {self.name} failed: {e}")
            return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()


class ReactiveSelector(SelectorNode):
    def __init__(self, name: str, children: List[BaseNode] = None, **kwargs):
        super().__init__(name, children, use_priority=True, **kwargs)
        self._running_child: Optional[BaseNode] = None
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if self._running_child and self._running_child.status == NodeStatus.RUNNING:
            status = self._running_child.tick(context)
            
            if status != NodeStatus.RUNNING:
                self._running_child = None
            
            return status
        
        children = sorted(self._children, key=lambda c: c.priority, reverse=True)
        
        for child in children:
            if child.status == NodeStatus.RUNNING:
                continue
            
            status = child.tick(context)
            
            if status == NodeStatus.RUNNING:
                self._running_child = child
                return status
            elif status == NodeStatus.SUCCESS:
                return status
        
        return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()
        self._running_child = None


class RandomSelector(SelectorNode):
    import random
    
    def execute(self, context: NodeContext) -> NodeStatus:
        import random
        
        available = [
            child for child in self._children
            if child.status != NodeStatus.RUNNING
        ]
        
        if not available:
            return NodeStatus.FAILURE
        
        random.shuffle(available)
        
        for child in available:
            status = child.tick(context)
            
            if status != NodeStatus.FAILURE:
                return status
        
        return NodeStatus.FAILURE


class WeightedSelector(SelectorNode):
    def __init__(
        self,
        name: str,
        children: List[BaseNode] = None,
        weights: List[float] = None,
        **kwargs
    ):
        super().__init__(name, children, **kwargs)
        self.weights = weights or [1.0] * len(self._children) if children else []
    
    def execute(self, context: NodeContext) -> NodeStatus:
        import random
        
        available_indices = [
            i for i, child in enumerate(self._children)
            if child.status != NodeStatus.RUNNING
        ]
        
        if not available_indices:
            return NodeStatus.FAILURE
        
        available_weights = [self.weights[i] for i in available_indices]
        total_weight = sum(available_weights)
        
        if total_weight == 0:
            return super().execute(context)
        
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        
        for i, weight in zip(available_indices, available_weights):
            cumulative += weight
            if r <= cumulative:
                return self._children[i].tick(context)
        
        return self._children[available_indices[-1]].tick(context)


class DynamicSequence(SequenceNode):
    def __init__(
        self,
        name: str,
        children_factory: Callable[[], List[BaseNode]],
        **kwargs
    ):
        super().__init__(name, [], **kwargs)
        self._children_factory = children_factory
        self._refresh_needed = True
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if self._refresh_needed:
            new_children = self._children_factory()
            
            old_children = {c.name: c for c in self._children}
            
            self._children.clear()
            
            for new_child in new_children:
                if new_child.name in old_children:
                    child = old_children[new_child.name]
                    if child not in self._children:
                        self._children.append(child)
                else:
                    self._children.append(new_child)
                    new_child.parent = self
            
            for child in self._children:
                if child.parent != self:
                    child.parent = self
            
            self._refresh_needed = False
        
        return super().execute(context)
    
    def request_refresh(self):
        self._refresh_needed = True
    
    def reset(self):
        self._refresh_needed = True
        super().reset()


class SubtreeNode(DecoratorNode):
    def __init__(self, name: str, subtree: BaseNode = None, **kwargs):
        super().__init__(name, subtree, **kwargs)
        self._subtree = subtree
    
    @property
    def subtree(self) -> Optional[BaseNode]:
        return self._subtree
    
    @subtree.setter
    def subtree(self, node: BaseNode):
        self._subtree = node
        self._child = node
        if node:
            node.parent = self
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._subtree:
            return NodeStatus.FAILURE
        
        return self._subtree.tick(context)


class BlackboardQueryNode(ConditionNode):
    def __init__(
        self,
        name: str,
        key: str,
        expected_value: Any = None,
        operator: str = "==",
        **kwargs
    ):
        def condition(ctx: NodeContext) -> bool:
            value = ctx.get(key)
            
            if expected_value is None:
                return value is not None
            
            ops = {
                "==": lambda v, e: v == e,
                "!=": lambda v, e: v != e,
                ">": lambda v, e: v > e,
                "<": lambda v, e: v < e,
                ">=": lambda v, e: v >= e,
                "<=": lambda v, e: v <= e,
                "in": lambda v, e: v in e,
                "not_in": lambda v, e: v not in e
            }
            
            op = ops.get(operator, ops["=="])
            return op(value, expected_value)
        
        super().__init__(name, condition, **kwargs)
        self.key = key
        self.expected_value = expected_value
        self.operator = operator


class BlackboardSetNode(ActionNode):
    def __init__(
        self,
        name: str,
        key: str,
        value: Any,
        **kwargs
    ):
        def action(ctx: NodeContext) -> NodeStatus:
            ctx.set(key, value)
            return NodeStatus.SUCCESS
        
        super().__init__(name, action, **kwargs)
        self.key = key
        self.value = value