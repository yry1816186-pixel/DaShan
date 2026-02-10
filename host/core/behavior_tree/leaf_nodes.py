import logging
import time
from typing import Any, Optional, List
from .behavior_tree import ActionNode, ConditionNode, NodeContext, NodeStatus

logger = logging.getLogger(__name__)


class WaitAction(ActionNode):
    def __init__(
        self,
        name: str = "Wait",
        duration: float = 1.0,
        variable_duration: str = None,
        **kwargs
    ):
        self.duration = duration
        self.variable_duration = variable_duration
        self._start_time: Optional[float] = None
        
        super().__init__(name, self._wait, **kwargs)
    
    def _wait(self, context: NodeContext) -> NodeStatus:
        duration = self.duration
        
        if self.variable_duration:
            var_duration = context.get(self.variable_duration)
            if var_duration is not None:
                try:
                    duration = float(var_duration)
                except (ValueError, TypeError):
                    pass
        
        if self._start_time is None:
            self._start_time = time.time()
        
        elapsed = time.time() - self._start_time
        
        if elapsed >= duration:
            self._start_time = None
            return NodeStatus.SUCCESS
        
        return NodeStatus.RUNNING
    
    def reset(self):
        super().reset()
        self._start_time = None


class LogAction(ActionNode):
    def __init__(
        self,
        name: str = "Log",
        message: str = "Node executed",
        level: str = "info",
        **kwargs
    ):
        self.message = message
        self.level = level
        
        def log_action(ctx: NodeContext) -> NodeStatus:
            formatted_msg = self._format_message(ctx)
            
            if self.level == "debug":
                logger.debug(formatted_msg)
            elif self.level == "info":
                logger.info(formatted_msg)
            elif self.level == "warning":
                logger.warning(formatted_msg)
            elif self.level == "error":
                logger.error(formatted_msg)
            else:
                logger.info(formatted_msg)
            
            return NodeStatus.SUCCESS
        
        super().__init__(name, log_action, **kwargs)
    
    def _format_message(self, context: NodeContext) -> str:
        try:
            return self.message.format(**context.variables, **context.blackboard)
        except (KeyError, AttributeError):
            return self.message


class SetVariableAction(ActionNode):
    def __init__(
        self,
        name: str = "SetVariable",
        key: str = "value",
        value: Any = None,
        variable_value: str = None,
        **kwargs
    ):
        self.key = key
        self.value = value
        self.variable_value = variable_value
        
        def set_var(ctx: NodeContext) -> NodeStatus:
            final_value = self.value
            
            if self.variable_value:
                final_value = ctx.get(self.variable_value, self.value)
            
            ctx.set_var(self.key, final_value)
            return NodeStatus.SUCCESS
        
        super().__init__(name, set_var, **kwargs)


class IncrementVariableAction(ActionNode):
    def __init__(
        self,
        name: str = "Increment",
        key: str = "counter",
        amount: float = 1.0,
        **kwargs
    ):
        self.key = key
        self.amount = amount
        
        def increment(ctx: NodeContext) -> NodeStatus:
            current = ctx.get(key, 0)
            try:
                new_value = current + self.amount
            except TypeError:
                logger.error(f"Cannot increment {key} with {amount}")
                return NodeStatus.FAILURE
            
            ctx.set_var(key, new_value)
            return NodeStatus.SUCCESS
        
        super().__init__(name, increment, **kwargs)


class CheckCondition(ConditionNode):
    def __init__(
        self,
        name: str = "CheckCondition",
        variable: str = None,
        expected_value: Any = None,
        operator: str = "==",
        blackboard_key: str = None,
        **kwargs
    ):
        self.variable = variable
        self.expected_value = expected_value
        self.operator = operator
        self.blackboard_key = blackboard_key
        
        def check(ctx: NodeContext) -> bool:
            if self.blackboard_key:
                actual_value = ctx.get(self.blackboard_key)
            elif self.variable:
                actual_value = ctx.get(self.variable)
            else:
                return False
            
            ops = {
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
                ">": lambda a, b: a > b,
                "<": lambda a, b: a < b,
                ">=": lambda a, b: a >= b,
                "<=": lambda a, b: a <= b,
                "in": lambda a, b: a in b,
                "not_in": lambda a, b: a not in b,
                "is": lambda a, b: a is b,
                "is_not": lambda a, b: a is not b,
                "contains": lambda a, b: b in a if hasattr(a, '__contains__') else False,
                "not_contains": lambda a, b: b not in a if hasattr(a, '__contains__') else True
            }
            
            op = ops.get(self.operator, ops["=="])
            return op(actual_value, self.expected_value)
        
        super().__init__(name, check, **kwargs)


class RandomChanceNode(ConditionNode):
    import random
    
    def __init__(
        self,
        name: str = "RandomChance",
        chance: float = 0.5,
        variable_chance: str = None,
        **kwargs
    ):
        self.chance = chance
        self.variable_chance = variable_chance
        
        def random_check(ctx: NodeContext) -> bool:
            chance = self.chance
            
            if self.variable_chance:
                var_chance = ctx.get(self.variable_chance)
                if var_chance is not None:
                    try:
                        chance = float(var_chance)
                    except (ValueError, TypeError):
                        pass
            
            return random.random() < chance
        
        super().__init__(name, random_check, **kwargs)


class ExpressionCheck(ConditionNode):
    def __init__(
        self,
        name: str = "ExpressionCheck",
        expression: str = "True",
        **kwargs
    ):
        self.expression = expression
        
        def eval_expr(ctx: NodeContext) -> bool:
            try:
                result = eval(expression, {}, ctx.variables)
                return bool(result)
            except Exception as e:
                logger.error(f"Expression evaluation failed: {e}")
                return False
        
        super().__init__(name, eval_expr, **kwargs)


class MemoryCheck(ConditionNode):
    def __init__(
        self,
        name: str = "MemoryCheck",
        key: str = None,
        exists: bool = True,
        **kwargs
    ):
        self.key = key
        self.exists = exists
        
        def check_memory(ctx: NodeContext) -> bool:
            if not self.key:
                return False
            
            memory = ctx.get(f"memory.{self.key}")
            
            if self.exists:
                return memory is not None
            else:
                return memory is None
        
        super().__init__(name, check_memory, **kwargs)


class TimerCheck(ConditionNode):
    def __init__(
        self,
        name: str = "TimerCheck",
        duration: float = 0.0,
        variable_duration: str = None,
        reset_on_success: bool = False,
        **kwargs
    ):
        self.duration = duration
        self.variable_duration = variable_duration
        self.reset_on_success = reset_on_success
        self._timer_key = f"timer_{name}"
        
        def check_timer(ctx: NodeContext) -> bool:
            duration = self.duration
            
            if self.variable_duration:
                var_duration = ctx.get(self.variable_duration)
                if var_duration is not None:
                    try:
                        duration = float(var_duration)
                    except (ValueError, TypeError):
                        pass
            
            start_time = ctx.get(self._timer_key)
            
            if start_time is None:
                ctx.set(self._timer_key, time.time())
                return False
            
            elapsed = time.time() - start_time
            
            if elapsed >= duration:
                if self.reset_on_success:
                    ctx.set(self._timer_key, time.time())
                return True
            
            return False
        
        super().__init__(name, check_timer, **kwargs)


class CounterCheck(ConditionNode):
    def __init__(
        self,
        name: str = "CounterCheck",
        key: str = "counter",
        target: int = 0,
        operator: str = ">=",
        **kwargs
    ):
        self.key = key
        self.target = target
        self.operator = operator
        
        def check_counter(ctx: NodeContext) -> bool:
            current = ctx.get(key, 0)
            
            ops = {
                "==": lambda c, t: c == t,
                "!=": lambda c, t: c != t,
                ">": lambda c, t: c > t,
                "<": lambda c, t: c < t,
                ">=": lambda c, t: c >= t,
                "<=": lambda c, t: c <= t
            }
            
            op = ops.get(self.operator, ops[">="])
            return op(current, self.target)
        
        super().__init__(name, check_counter, **kwargs)


class RangeCheck(ConditionNode):
    def __init__(
        self,
        name: str = "RangeCheck",
        key: str = "value",
        min_value: float = float('-inf'),
        max_value: float = float('inf'),
        **kwargs
    ):
        self.key = key
        self.min_value = min_value
        self.max_value = max_value
        
        def check_range(ctx: NodeContext) -> bool:
            value = ctx.get(self.key)
            
            try:
                value = float(value)
            except (ValueError, TypeError):
                return False
            
            return self.min_value <= value <= self.max_value
        
        super().__init__(name, check_range, **kwargs)


class ListNotEmptyCheck(ConditionNode):
    def __init__(
        self,
        name: str = "ListNotEmpty",
        key: str = "items",
        **kwargs
    ):
        self.key = key
        
        def check_list(ctx: NodeContext) -> bool:
            items = ctx.get(self.key, [])
            return bool(items)
        
        super().__init__(name, check_list, **kwargs)


class ListEmptyCheck(ConditionNode):
    def __init__(
        self,
        name: str = "ListEmpty",
        key: str = "items",
        **kwargs
    ):
        self.key = key
        
        def check_empty(ctx: NodeContext) -> bool:
            items = ctx.get(self.key, [])
            return not bool(items)
        
        super().__init__(name, check_empty, **kwargs)


class CallFunctionAction(ActionNode):
    def __init__(
        self,
        name: str = "CallFunction",
        func: callable = None,
        func_name: str = None,
        **kwargs
    ):
        self.func = func
        self.func_name = func_name
        
        def call_func(ctx: NodeContext) -> NodeStatus:
            function = self.func
            
            if not function and self.func_name:
                function = ctx.get(self.func_name)
            
            if not function:
                logger.error(f"Function not found: {self.func_name}")
                return NodeStatus.FAILURE
            
            try:
                result = function(ctx)
                
                if isinstance(result, NodeStatus):
                    return result
                elif result is True or result is None:
                    return NodeStatus.SUCCESS
                elif result is False:
                    return NodeStatus.FAILURE
                else:
                    return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Function call failed: {e}")
                return NodeStatus.FAILURE
        
        super().__init__(name, call_func, **kwargs)


class PrintAction(ActionNode):
    def __init__(
        self,
        name: str = "Print",
        message: str = "Hello",
        **kwargs
    ):
        self.message = message
        
        def print_msg(ctx: NodeContext) -> NodeStatus:
            try:
                formatted = self.message.format(**ctx.variables, **ctx.blackboard)
                print(formatted_msg)
                return NodeStatus.SUCCESS
            except Exception as e:
                print(self.message)
                return NodeStatus.SUCCESS
        
        super().__init__(name, print_msg, **kwargs)


class SaveToBlackboardAction(ActionNode):
    def __init__(
        self,
        name: str = "SaveToBlackboard",
        variable_key: str = None,
        blackboard_key: str = None,
        **kwargs
    ):
        self.variable_key = variable_key
        self.blackboard_key = blackboard_key
        
        def save(ctx: NodeContext) -> NodeStatus:
            if not self.variable_key or not self.blackboard_key:
                return NodeStatus.FAILURE
            
            value = ctx.get(self.variable_key)
            ctx.set(self.blackboard_key, value)
            return NodeStatus.SUCCESS
        
        super().__init__(name, save, **kwargs)


class LoadFromBlackboardAction(ActionNode):
    def __init__(
        self,
        name: str = "LoadFromBlackboard",
        blackboard_key: str = None,
        variable_key: str = None,
        **kwargs
    ):
        self.blackboard_key = blackboard_key
        self.variable_key = variable_key
        
        def load(ctx: NodeContext) -> NodeStatus:
            if not self.blackboard_key or not self.variable_key:
                return NodeStatus.FAILURE
            
            value = ctx.get(self.blackboard_key)
            ctx.set_var(self.variable_key, value)
            return NodeStatus.SUCCESS
        
        super().__init__(name, load, **kwargs)