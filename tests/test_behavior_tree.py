import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock

from host.core.behavior_tree.behavior_tree import (
    BehaviorTree, SequenceNode, SelectorNode, ParallelNode,
    DecoratorNode, RetryDecorator, TimeLimitDecorator,
    InverterDecorator, BaseNode, NodeStatus
)
from host.core.behavior_tree.nodes import (
    ActionNode, ConditionNode, WaitNode,
    RandomNode, CooldownNode, ThrottleNode
)


@pytest.mark.asyncio
async def test_action_node_success():
    async def success_action():
        return NodeStatus.SUCCESS
    
    node = ActionNode(name="test_action", action=success_action)
    status = await node.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_action_node_failure():
    async def failure_action():
        return NodeStatus.FAILURE
    
    node = ActionNode(name="test_action", action=failure_action)
    status = await node.tick()
    
    assert status == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_action_node_running():
    async def running_action():
        return NodeStatus.RUNNING
    
    node = ActionNode(name="test_action", action=running_action)
    status = await node.tick()
    
    assert status == NodeStatus.RUNNING


@pytest.mark.asyncio
async def test_condition_node_true():
    async def true_condition():
        return True
    
    node = ConditionNode(name="test_condition", condition=true_condition)
    status = await node.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_condition_node_false():
    async def false_condition():
        return False
    
    node = ConditionNode(name="test_condition", condition=false_condition)
    status = await node.tick()
    
    assert status == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_wait_node():
    node = WaitNode(name="wait", duration=0.1)
    
    start_time = asyncio.get_event_loop().time()
    status = await node.tick()
    elapsed = asyncio.get_event_loop().time() - start_time
    
    assert status == NodeStatus.SUCCESS
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_sequence_node_all_success():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    sequence = SequenceNode(name="sequence", children=[child1, child2])
    status = await sequence.tick()
    
    assert status == NodeStatus.SUCCESS
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 1


@pytest.mark.asyncio
async def test_sequence_node_first_failure():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.FAILURE)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    sequence = SequenceNode(name="sequence", children=[child1, child2])
    status = await sequence.tick()
    
    assert status == NodeStatus.FAILURE
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 0


@pytest.mark.asyncio
async def test_sequence_node_running():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.RUNNING)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    sequence = SequenceNode(name="sequence", children=[child1, child2])
    status = await sequence.tick()
    
    assert status == NodeStatus.RUNNING
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 0


@pytest.mark.asyncio
async def test_selector_node_first_success():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    selector = SelectorNode(name="selector", children=[child1, child2])
    status = await selector.tick()
    
    assert status == NodeStatus.SUCCESS
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 0


@pytest.mark.asyncio
async def test_selector_node_all_failure():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.FAILURE)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.FAILURE)
    
    selector = SelectorNode(name="selector", children=[child1, child2])
    status = await selector.tick()
    
    assert status == NodeStatus.FAILURE
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 1


@pytest.mark.asyncio
async def test_parallel_node_all_success():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    parallel = ParallelNode(name="parallel", children=[child1, child2])
    status = await parallel.tick()
    
    assert status == NodeStatus.SUCCESS
    assert child1.tick.call_count == 1
    assert child2.tick.call_count == 1


@pytest.mark.asyncio
async def test_parallel_node_one_failure():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.FAILURE)
    
    parallel = ParallelNode(name="parallel", children=[child1, child2])
    status = await parallel.tick()
    
    assert status == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_parallel_node_success_threshold():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.FAILURE)
    
    child3 = Mock(spec=BaseNode)
    child3.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    parallel = ParallelNode(name="parallel", children=[child1, child2, child3], success_threshold=2)
    status = await parallel.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_retry_decorator():
    attempts = [0]
    
    async def failing_action():
        attempts[0] += 1
        if attempts[0] < 3:
            return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    child = ActionNode(name="failing", action=failing_action)
    decorator = RetryDecorator(name="retry", child=child, max_attempts=3)
    
    status = await decorator.tick()
    
    assert status == NodeStatus.SUCCESS
    assert attempts[0] == 3


@pytest.mark.asyncio
async def test_retry_decorator_exhausted():
    async def always_failing():
        return NodeStatus.FAILURE
    
    child = ActionNode(name="failing", action=always_failing)
    decorator = RetryDecorator(name="retry", child=child, max_attempts=2)
    
    status = await decorator.tick()
    
    assert status == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_time_limit_decorator_success():
    async def quick_action():
        return NodeStatus.SUCCESS
    
    child = ActionNode(name="quick", action=quick_action)
    decorator = TimeLimitDecorator(name="timeout", child=child, timeout=1.0)
    
    status = await decorator.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_time_limit_decorator_timeout():
    async def slow_action():
        await asyncio.sleep(2)
        return NodeStatus.SUCCESS
    
    child = ActionNode(name="slow", action=slow_action)
    decorator = TimeLimitDecorator(name="timeout", child=child, timeout=0.1)
    
    status = await decorator.tick()
    
    assert status == NodeStatus.FAILURE


@pytest.mark.asyncio
async def test_inverter_decorator():
    async def failure_action():
        return NodeStatus.FAILURE
    
    child = ActionNode(name="failing", action=failure_action)
    decorator = InverterDecorator(name="inverter", child=child)
    
    status = await decorator.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_random_node():
    child1 = Mock(spec=BaseNode)
    child1.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    child2 = Mock(spec=BaseNode)
    child2.tick = AsyncMock(return_value=NodeStatus.SUCCESS)
    
    random_node = RandomNode(name="random", children=[child1, child2])
    status = await random_node.tick()
    
    assert status == NodeStatus.SUCCESS


@pytest.mark.asyncio
async def test_cooldown_node():
    call_count = [0]
    
    async def counting_action():
        call_count[0] += 1
        return NodeStatus.SUCCESS
    
    child = ActionNode(name="counting", action=counting_action)
    cooldown = CooldownNode(name="cooldown", child=child, cooldown_time=0.2)
    
    await cooldown.tick()
    assert call_count[0] == 1
    
    await cooldown.tick()
    assert call_count[0] == 1
    
    await asyncio.sleep(0.25)
    await cooldown.tick()
    assert call_count[0] == 2


@pytest.mark.asyncio
async def test_throttle_node():
    call_count = [0]
    
    async def counting_action():
        call_count[0] += 1
        return NodeStatus.SUCCESS
    
    child = ActionNode(name="counting", action=counting_action)
    throttle = ThrottleNode(name="throttle", child=child, min_interval=0.1)
    
    await throttle.tick()
    await throttle.tick()
    await throttle.tick()
    
    assert call_count[0] == 1


@pytest.mark.asyncio
async def test_behavior_tree_initialization():
    root = Mock(spec=BaseNode)
    tree = BehaviorTree(root=root, tick_interval=0.016)
    
    assert tree.root == root
    assert tree.tick_interval == 0.016


@pytest.mark.asyncio
async def test_behavior_tree_start_stop():
    call_count = [0]
    
    async def counting_action():
        call_count[0] += 1
        return NodeStatus.SUCCESS
    
    root = ActionNode(name="counting", action=counting_action)
    tree = BehaviorTree(root=root, tick_interval=0.1)
    
    await tree.start()
    await asyncio.sleep(0.3)
    await tree.stop()
    
    assert call_count[0] > 0


@pytest.mark.asyncio
async def test_behavior_tree_get_status():
    root = Mock(spec=BaseNode)
    tree = BehaviorTree(root=root)
    
    status = tree.get_status()
    assert "running" in status
    assert "tick_count" in status


@pytest.mark.asyncio
async def test_behavior_tree_reset():
    reset_called = [False]
    
    class TestNode(BaseNode):
        async def reset(self):
            reset_called[0] = True
        
        async def tick(self):
            return NodeStatus.SUCCESS
    
    root = TestNode(name="test")
    tree = BehaviorTree(root=root)
    
    await tree.reset()
    
    assert reset_called[0]
