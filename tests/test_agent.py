import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from host.core.agent.agent_graph import DashanAgent
from host.core.agent.agent_state import AgentState, AgentMessage
from host.core.agent.tool_registry import ToolRegistry, SearchTool, CalculatorTool, TimeTool


@pytest.fixture
def agent_config():
    return {
        "llm": {
            "model": "glm-4",
            "api_key": "test_key",
            "api_base": "https://api.example.com/v4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "rag": {
            "enabled": True,
            "vector_db": "chromadb",
            "collection_name": "test_collection"
        },
        "tools": {
            "search": {"enabled": True, "api_key": "test_search_key"},
            "calculator": {"enabled": True},
            "time": {"enabled": True}
        }
    }


@pytest.fixture
def tool_registry():
    registry = ToolRegistry()
    registry.register_tool(SearchTool())
    registry.register_tool(CalculatorTool())
    registry.register_tool(TimeTool())
    return registry


@pytest.mark.asyncio
async def test_agent_state_creation():
    state = AgentState(
        messages=[AgentMessage(role="user", content="你好")],
        current_step="input_processing"
    )
    assert len(state.messages) == 1
    assert state.current_step == "input_processing"
    assert state.context == {}


@pytest.mark.asyncio
async def test_agent_state_update():
    state = AgentState(
        messages=[AgentMessage(role="user", content="你好")],
        current_step="input_processing"
    )
    
    state.add_message(AgentMessage(role="assistant", content="你好！"))
    state.update_context({"user_id": "123"})
    state.current_step = "response_generation"
    
    assert len(state.messages) == 2
    assert state.context["user_id"] == "123"
    assert state.current_step == "response_generation"


@pytest.mark.asyncio
async def test_tool_registry_registration(tool_registry):
    assert len(tool_registry.list_tools()) == 3
    assert "search" in tool_registry.list_tools()
    assert "calculator" in tool_registry.list_tools()


@pytest.mark.asyncio
async def test_tool_registry_get_tool(tool_registry):
    tool = tool_registry.get_tool("search")
    assert tool is not None
    assert tool.name == "search"


@pytest.mark.asyncio
async def test_tool_registry_get_nonexistent_tool(tool_registry):
    tool = tool_registry.get_tool("nonexistent")
    assert tool is None


@pytest.mark.asyncio
async def test_search_tool_execution():
    tool = SearchTool(api_key="test_key")
    result = await tool.execute(query="test")
    assert result is not None


@pytest.mark.asyncio
async def test_calculator_tool_execution():
    tool = CalculatorTool()
    result = await tool.execute(expression="2 + 2")
    assert result == 4


@pytest.mark.asyncio
async def test_calculator_tool_complex_expression():
    tool = CalculatorTool()
    result = await tool.execute(expression="(3 + 4) * 5")
    assert result == 35


@pytest.mark.asyncio
async def test_time_tool_execution():
    tool = TimeTool()
    result = await tool.execute()
    assert result is not None
    assert "current_time" in result


@pytest.mark.asyncio
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_agent_initialization(mock_chat, agent_config):
    mock_llm = MagicMock()
    mock_chat.return_value = mock_llm
    
    agent = DashanAgent(config=agent_config)
    
    assert agent.config == agent_config
    assert agent.graph is not None


@pytest.mark.asyncio
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_agent_process_simple_message(mock_chat, agent_config):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    agent = DashanAgent(config=agent_config)
    
    state = AgentState(
        messages=[AgentMessage(role="user", content="你好")],
        current_step="input_processing"
    )
    
    with patch.object(agent, '_execute_step') as mock_execute:
        mock_execute.return_value = state
        result = await agent.process("你好")
        
        assert result is not None


@pytest.mark.asyncio
async def test_agent_intent_classification():
    config = {
        "llm": {"model": "glm-4", "api_key": "test_key"},
        "rag": {"enabled": False},
        "tools": {}
    }
    
    agent = DashanAgent(config=config)
    
    state = AgentState(
        messages=[AgentMessage(role="user", content="今天天气怎么样？")],
        current_step="intent_classification"
    )
    
    result = await agent._classify_intent(state)
    
    assert result.current_step == "tool_selection"


@pytest.mark.asyncio
async def test_agent_tool_selection():
    config = {
        "llm": {"model": "glm-4", "api_key": "test_key"},
        "rag": {"enabled": False},
        "tools": {
            "search": {"enabled": True, "api_key": "test_key"}
        }
    }
    
    agent = DashanAgent(config=config)
    agent.tool_registry.register_tool(SearchTool(api_key="test_key"))
    
    state = AgentState(
        messages=[AgentMessage(role="user", content="搜索关于人工智能的信息")],
        current_step="tool_selection"
    )
    
    result = await agent._select_tools(state)
    
    assert result.current_step == "tool_execution"


@pytest.mark.asyncio
async def test_agent_tool_execution(tool_registry):
    config = {
        "llm": {"model": "glm-4", "api_key": "test_key"},
        "rag": {"enabled": False},
        "tools": {
            "calculator": {"enabled": True}
        }
    }
    
    agent = DashanAgent(config=config)
    agent.tool_registry = tool_registry
    
    state = AgentState(
        messages=[AgentMessage(role="user", content="计算 2 + 2")],
        current_step="tool_execution",
        selected_tools=["calculator"],
        tool_parameters={"expression": "2 + 2"}
    )
    
    result = await agent._execute_tools(state)
    
    assert result.current_step == "reasoning"
    assert "tool_results" in result.context
