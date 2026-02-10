import logging
from typing import Optional, Callable, Dict, Any, List, TypedDict
from dataclasses import dataclass
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from .agent_state import AgentState, AgentStatus, Message
from .agent_config import AgentConfig
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentInput(TypedDict):
    user_input: str
    context: Optional[Dict[str, Any]]
    mode: Optional[str]


@dataclass
class AgentNodeResult:
    next_node: str
    state_update: Dict[str, Any]
    should_continue: bool = True


class DashanAgent:
    def __init__(self, config: AgentConfig, tool_registry: ToolRegistry):
        self.config = config
        self.tool_registry = tool_registry
        self.state = AgentState()
        self.graph = None
        self.llm = None
        self._event_callbacks: Dict[str, List[Callable]] = {}
        
        self._initialize_llm()
        self._build_graph()
        
        logger.info(f"DashanAgent initialized in {config.mode.name} mode")
    
    def _initialize_llm(self):
        from openai import OpenAI
        
        self.llm = ChatOpenAI(
            model=self.config.model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout
        )
        
        logger.info(f"LLM initialized: {self.config.model}")
    
    def _build_graph(self):
        graph = StateGraph(AgentState)
        
        graph.add_node("input_processing", self._process_input)
        graph.add_node("intent_classification", self._classify_intent)
        graph.add_node("tool_selection", self._select_tools)
        graph.add_node("tool_execution", self._execute_tools)
        graph.add_node("knowledge_retrieval", self._retrieve_knowledge)
        graph.add_node("reasoning", self._reason)
        graph.add_node("response_generation", self._generate_response)
        graph.add_node("output_formatting", self._format_output)
        
        graph.set_entry_point("input_processing")
        
        graph.add_edge("input_processing", "intent_classification")
        graph.add_edge("intent_classification", "tool_selection")
        graph.add_conditional_edges(
            "tool_selection",
            self._should_execute_tools,
            {
                "yes": "tool_execution",
                "no": "knowledge_retrieval"
            }
        )
        graph.add_edge("tool_execution", "reasoning")
        graph.add_conditional_edges(
            "knowledge_retrieval",
            self._has_retrieved_knowledge,
            {
                "yes": "reasoning",
                "no": "reasoning"
            }
        )
        graph.add_edge("reasoning", "response_generation")
        graph.add_edge("response_generation", "output_formatting")
        graph.add_edge("output_formatting", END)
        
        self.graph = graph.compile()
        logger.info("Agent graph built successfully")
    
    async def process(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        self.state.status = AgentStatus.PROCESSING
        self.state.current_input = user_input
        self.state.context = context or {}
        self.state.processing_start = datetime.now()
        self.state.add_message("user", user_input)
        
        self._emit_event("input_received", {"input": user_input})
        
        try:
            result = await self.graph.ainvoke(self.state)
            
            self.state.status = AgentStatus.IDLE
            self.state.processing_end = datetime.now()
            
            self._emit_event("processing_complete", self.state.to_dict())
            
            return {
                "success": True,
                "output": self.state.current_output,
                "state": self.state.to_dict(),
                "duration": self.state.get_processing_duration()
            }
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            self.state.status = AgentStatus.ERROR
            self.state.error_message = str(e)
            
            self._emit_event("error", {"error": str(e)})
            
            return {
                "success": False,
                "error": str(e),
                "state": self.state.to_dict()
            }
    
    async def _process_input(self, state: AgentState) -> AgentState:
        state.status = AgentStatus.PROCESSING
        logger.info(f"Processing input: {state.current_input[:50]}...")
        
        state.context["input_length"] = len(state.current_input)
        state.context["input_type"] = self._detect_input_type(state.current_input)
        
        return state
    
    async def _classify_intent(self, state: AgentState) -> AgentState:
        prompt = f"""分析以下用户输入的意图，从以下选项中选择最合适的：

选项：
- greeting: 问候、打招呼
- question: 提问、询问信息
- command: 命令、指令
- conversation: 普通对话
- request: 请求执行某个任务

用户输入：{state.current_input}

只返回一个选项名称。"""
        
        try:
            intent = self.llm.invoke(prompt).content.strip().lower()
            state.context["intent"] = intent
            logger.info(f"Intent classified: {intent}")
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}")
            state.context["intent"] = "conversation"
        
        return state
    
    async def _select_tools(self, state: AgentState) -> AgentState:
        if not self.config.enable_tools:
            state.context["selected_tools"] = []
            return state
        
        intent = state.context.get("intent", "conversation")
        
        if intent in ["greeting", "conversation"]:
            state.context["selected_tools"] = []
            return state
        
        tools_desc = self.tool_registry.get_tool_descriptions()
        
        prompt = f"""根据用户输入，判断是否需要使用工具。如果需要，选择最合适的工具。

可用工具：
{tools_desc}

用户输入：{state.current_input}
意图：{intent}

分析后，如果需要工具，返回工具名称。如果不需要，返回"none"。
只返回一个工具名称或"none"。"""
        
        try:
            tool_name = self.llm.invoke(prompt).content.strip().lower()
            
            if tool_name and tool_name != "none":
                state.context["selected_tools"] = [tool_name]
                logger.info(f"Tool selected: {tool_name}")
            else:
                state.context["selected_tools"] = []
        except Exception as e:
            logger.warning(f"Tool selection failed: {e}")
            state.context["selected_tools"] = []
        
        return state
    
    def _should_execute_tools(self, state: AgentState) -> str:
        return "yes" if state.context.get("selected_tools") else "no"
    
    async def _execute_tools(self, state: AgentState) -> AgentState:
        tool_names = state.context.get("selected_tools", [])
        state.tool_calls = []
        
        for tool_name in tool_names:
            result = await self.tool_registry.execute_tool(
                tool_name,
                query=state.current_input
            )
            
            from .agent_state import ToolCall
            state.tool_calls.append(ToolCall(
                name=tool_name,
                arguments={"query": state.current_input},
                result=result.get("result"),
                error=result.get("error"),
                duration=result.get("duration", 0)
            ))
        
        if state.tool_calls and state.tool_calls[0].result:
            state.context["tool_results"] = [tc.result for tc in state.tool_calls if tc.result]
        
        return state
    
    async def _retrieve_knowledge(self, state: AgentState) -> AgentState:
        if not self.config.enable_rag:
            state.context["retrieved_knowledge"] = None
            return state
        
        from ..rag.knowledge_manager import KnowledgeManager
        
        km = KnowledgeManager()
        results = km.search(state.current_input, top_k=3)
        
        if results:
            state.context["retrieved_knowledge"] = results
            logger.info(f"Retrieved {len(results)} knowledge items")
        else:
            state.context["retrieved_knowledge"] = None
        
        return state
    
    def _has_retrieved_knowledge(self, state: AgentState) -> str:
        return "yes" if state.context.get("retrieved_knowledge") else "no"
    
    async def _reason(self, state: AgentState) -> AgentState:
        state.status = AgentStatus.THINKING
        
        context_parts = []
        
        if state.context.get("tool_results"):
            context_parts.append(f"工具结果：{state.context['tool_results']}")
        
        if state.context.get("retrieved_knowledge"):
            knowledge = state.context['retrieved_knowledge']
            context_parts.append(f"知识库信息：{knowledge}")
        
        if state.conversation:
            recent = [f"{m.role}: {m.content}" for m in state.get_recent_conversation(3)]
            context_parts.append(f"对话历史：\n" + "\n".join(recent))
        
        context_str = "\n\n".join(context_parts) if context_parts else ""
        
        state.context["reasoning_context"] = context_str
        logger.info("Reasoning with context")
        
        return state
    
    async def _generate_response(self, state: AgentState) -> AgentState:
        state.status = AgentStatus.RESPONDING
        
        system_prompt = self.config.default_system_prompt
        
        messages = [{"role": "system", "content": system_prompt}]
        
        for msg in state.conversation:
            messages.append(msg.to_dict())
        
        if state.context.get("reasoning_context"):
            messages[-1]["content"] += f"\n\n参考信息：\n{state.context['reasoning_context']}"
        
        try:
            response = self.llm.invoke(messages)
            state.current_output = response.content.strip()
            
            logger.info(f"Response generated: {state.current_output[:50]}...")
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state.current_output = "抱歉，我遇到了一些问题，请再试一次。"
        
        return state
    
    async def _format_output(self, state: AgentState) -> AgentState:
        state.add_message("assistant", state.current_output)
        
        if self.config.enable_memory:
            self.state.add_memory(
                f"{state.current_input} -> {state.current_output}",
                importance=1.2,
                tags=["dialogue"]
            )
        
        return state
    
    def _detect_input_type(self, text: str) -> str:
        text = text.strip()
        
        if any(char in text for char in "？?"):
            return "question"
        if text.startswith(("帮我", "请", "搜索", "计算", "查")):
            return "request"
        if any(word in text for word in ["你好", "hi", "hello", "早上好"]):
            return "greeting"
        
        return "conversation"
    
    def on(self, event_name: str, callback: Callable):
        if event_name not in self._event_callbacks:
            self._event_callbacks[event_name] = []
        self._event_callbacks[event_name].append(callback)
    
    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        callbacks = self._event_callbacks.get(event_name, [])
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        return self.state.to_dict()
    
    def clear_conversation(self):
        self.state.clear_conversation()
        logger.info("Conversation cleared")
    
    def set_mode(self, mode: str):
        from .agent_config import AgentMode
        self.config.mode = AgentMode[mode.upper()]
        logger.info(f"Mode changed to: {mode}")
    
    def export_state(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"State exported to: {filepath}")
    
    def import_state(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.state = AgentState()
        self.state.__dict__.update(data)
        logger.info(f"State imported from: {filepath}")
