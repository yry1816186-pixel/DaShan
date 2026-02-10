import logging
import time
from typing import Optional
from .behavior_tree import DecoratorNode, NodeStatus, NodeContext

logger = logging.getLogger(__name__)


class RepeatNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        count: int = -1,
        until_failure: bool = False,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.count = count
        self.until_failure = until_failure
        self._current_count = 0
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        while True:
            if self.count > 0 and self._current_count >= self.count:
                self._current_count = 0
                return NodeStatus.SUCCESS
            
            status = self._child.tick(context)
            self._current_count += 1
            
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif status == NodeStatus.FAILURE:
                if self.until_failure:
                    self._current_count = 0
                    return NodeStatus.SUCCESS
                return NodeStatus.FAILURE
            elif status == NodeStatus.SUCCESS:
                if not self.until_failure and self.count > 0:
                    if self._current_count >= self.count:
                        self._current_count = 0
                        return NodeStatus.SUCCESS
                continue
    
    def reset(self):
        super().reset()
        self._current_count = 0


class RetryNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        max_retries: int = 3,
        reset_child: bool = True,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.max_retries = max_retries
        self.reset_child = reset_child
        self._current_retry = 0
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        while self._current_retry <= self.max_retries:
            status = self._child.tick(context)
            
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            elif status == NodeStatus.SUCCESS:
                self._current_retry = 0
                return NodeStatus.SUCCESS
            elif status == NodeStatus.FAILURE:
                self._current_retry += 1
                
                if self.reset_child:
                    self._child.reset()
                
                if self._current_retry > self.max_retries:
                    self._current_retry = 0
                    return NodeStatus.FAILURE
                
                logger.info(f"Retry {self._current_retry}/{self.max_retries} for {self._child.name}")
                time.sleep(0.1)
        
        return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()
        self._current_retry = 0


class InverterNode(DecoratorNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        elif status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        else:
            return status
    
    def reset(self):
        super().reset()


class TimeoutNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        timeout: float = 5.0,
        on_timeout: str = "failure",
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.timeout = timeout
        self.on_timeout = on_timeout
        self._start_time: Optional[float] = None
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        if self._start_time is None:
            self._start_time = time.time()
        
        elapsed = time.time() - self._start_time
        
        if elapsed > self.timeout:
            logger.warning(f"Node {self._child.name} timed out after {elapsed:.2f}s")
            self._start_time = None
            
            if self.on_timeout == "success":
                return NodeStatus.SUCCESS
            elif self.on_timeout == "running":
                return NodeStatus.RUNNING
            else:
                return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status != NodeStatus.RUNNING:
            self._start_time = None
        
        return status
    
    def reset(self):
        super().reset()
        self._start_time = None


class CooldownNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        cooldown: float = 1.0,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.cooldown = cooldown
        self._last_execute: float = 0.0
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        elapsed = time.time() - self._last_execute
        
        if elapsed < self.cooldown:
            logger.debug(f"Node {self._child.name} on cooldown ({elapsed:.2f}/{self.cooldown}s)")
            return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status == NodeStatus.SUCCESS or status == NodeStatus.FAILURE:
            self._last_execute = time.time()
        
        return status
    
    def reset(self):
        super().reset()
        self._last_execute = 0.0


class AlwaysSuccessNode(DecoratorNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        if self._child:
            self._child.tick(context)
        return NodeStatus.SUCCESS
    
    def reset(self):
        super().reset()


class AlwaysFailureNode(DecoratorNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        if self._child:
            self._child.tick(context)
        return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()


class ForceSuccessNode(DecoratorNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.SUCCESS
        
        status = self._child.tick(context)
        
        if status == NodeStatus.RUNNING:
            return NodeStatus.RUNNING
        
        return NodeStatus.SUCCESS
    
    def reset(self):
        super().reset()


class ForceFailureNode(DecoratorNode):
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status == NodeStatus.RUNNING:
            return NodeStatus.RUNNING
        
        return NodeStatus.FAILURE
    
    def reset(self):
        super().reset()


class OnceNode(DecoratorNode):
    def __init__(self, name: str, child = None, reset_on_success: bool = False, **kwargs):
        super().__init__(name, child, **kwargs)
        self.reset_on_success = reset_on_success
        self._executed = False
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if self._executed:
            return NodeStatus.FAILURE
        
        if not self._child:
            return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status == NodeStatus.SUCCESS:
            self._executed = True
        
        return status
    
    def reset(self):
        super().reset()
        if self.reset_on_success:
            self._executed = False


class ConditionalNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        condition: str = None,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.condition = condition
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        if not self._evaluate_condition(context):
            return NodeStatus.FAILURE
        
        return self._child.tick(context)
    
    def _evaluate_condition(self, context: NodeContext) -> bool:
        if not self.condition:
            return True
        
        try:
            return eval(self.condition, {}, context.variables)
        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            return False
    
    def reset(self):
        super().reset()


class InterruptNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        interrupt_key: str = None,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.interrupt_key = interrupt_key
        self._was_interrupted = False
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        if self.interrupt_key and context.get(self.interrupt_key):
            logger.info(f"Node {self._child.name} interrupted by {self.interrupt_key}")
            self._was_interrupted = True
            return NodeStatus.FAILURE
        
        status = self._child.tick(context)
        
        if status != NodeStatus.RUNNING:
            self._was_interrupted = False
        
        return status
    
    def reset(self):
        super().reset()
        self._was_interrupted = False


class MonitorNode(DecoratorNode):
    def __init__(
        self,
        name: str,
        child = None,
        monitor_func = None,
        **kwargs
    ):
        super().__init__(name, child, **kwargs)
        self.monitor_func = monitor_func
    
    def execute(self, context: NodeContext) -> NodeStatus:
        if not self._child:
            return NodeStatus.FAILURE
        
        if self.monitor_func:
            self.monitor_func(self._child, context)
        
        return self._child.tick(context)
    
    def reset(self):
        super().reset()