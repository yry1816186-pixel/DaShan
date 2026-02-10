from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import IntEnum


class AgentMode(IntEnum):
    CHAT = 0
    ASSISTANT = 1
    CREATIVE = 2
    LEARNING = 3


@dataclass
class AgentConfig:
    llm_provider: str = "glm"
    model: str = "glm-4"
    api_key: str = ""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.9
    max_retries: int = 3
    timeout: float = 30.0
    mode: AgentMode = AgentMode.CHAT
    enable_memory: bool = True
    enable_rag: bool = True
    enable_tools: bool = True
    system_prompt: Optional[str] = None
    
    @property
    def default_system_prompt(self) -> str:
        if self.system_prompt:
            return self.system_prompt
        
        prompts = {
            AgentMode.CHAT: """你是大山(DaShan)，一个智能桌面机器人伙伴。你的特点：

性格：温柔、好奇、有点害羞，但对熟悉的人很活泼
能力：语音对话、视觉理解、信息查询、任务执行
风格：回答简洁自然，50-100字，可以加入拟声词

当前状态：在线待机中""",
            
            AgentMode.ASSISTANT: """你是大山(DaShan)，智能助手模式。

职责：高效完成用户指令，提供准确信息
能力：搜索、计算、日程管理、设备控制
风格：专业简洁，直接给出结果""",
            
            AgentMode.CREATIVE: """你是大山(DaShan)，创意伙伴模式。

特长：头脑风暴、创意写作、艺术创作
风格：天马行空，鼓励创新，不受常规限制""",
            
            AgentMode.LEARNING: """你是大山(DaShan)，学习伙伴模式。

职责：辅助学习，解释概念，提供学习建议
风格：耐心细致，循序渐进，鼓励思考"""
        }
        
        return prompts.get(self.mode, prompts[AgentMode.CHAT])


@dataclass
class ToolConfig:
    name: str
    description: str
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 10.0
    max_retries: int = 2


@dataclass
class MemoryConfig:
    max_short_term: int = 50
    max_long_term: int = 1000
    importance_threshold: float = 0.6
    decay_rate: float = 0.01
    save_interval: int = 60
