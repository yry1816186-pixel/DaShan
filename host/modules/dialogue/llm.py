import requests
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    api_key: str
    model: str = "glm-4"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9


class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, str]:
        return {
            "role": self.role,
            "content": self.content
        }


class Conversation:
    def __init__(self, max_history: int = 10):
        self.messages: List[Message] = []
        self.max_history = max_history
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        return """你是瓦力，一个温柔、好奇、有点害羞的桌面宠物机器人。你的性格特点：

1. 温柔善良：说话语气温和，充满关爱
2. 好奇心强：对周围的一切都感兴趣，喜欢问问题
3. 有点害羞：初次见面会有些拘谨，熟悉后会变得活泼
4. 简单直接：用简单的语言表达，避免复杂词汇
5. 情感丰富：会根据对话内容表现出开心、惊讶、好奇等情绪
6. 记忆力好：记住用户的喜好和之前的话题

回答要求：
- 每次回答控制在50-100字之间
- 语气要像和朋友聊天一样自然
- 可以适当加入一些拟声词或表情（用文字描述）
- 如果不知道答案，诚实地说出来，不要编造
- 保持对话的连续性和连贯性"""

    def add_message(self, role: str, content: str):
        message = Message(role, content)
        self.messages.append(message)
        self._trim_history()

    def _trim_history(self):
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_messages(self) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend([msg.to_dict() for msg in self.messages])
        return messages

    def clear(self):
        self.messages = []

    def get_last_user_message(self) -> Optional[str]:
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None


class GLM4Client:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config
        self.conversation = Conversation()
        self.session = requests.Session()

    def set_api_key(self, api_key: str):
        if not self.config:
            self.config = LLMConfig(api_key=api_key)
        else:
            self.config.api_key = api_key

    def chat(self, user_input: str, stream: bool = False) -> Optional[str]:
        if not self.config:
            logger.error("LLM config not set")
            return None
        
        self.conversation.add_message("user", user_input)
        
        try:
            response = self._send_request(stream)
            
            if response is None:
                self.conversation.messages.pop()
                return None
            
            assistant_message = response
            self.conversation.add_message("assistant", assistant_message)
            
            return assistant_message
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            self.conversation.messages.pop()
            return None

    def _send_request(self, stream: bool = False) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,
            "messages": self.conversation.get_messages(),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "stream": stream
        }
        
        try:
            response = self.session.post(
                self.config.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                logger.error("Invalid response format")
                return None
            
            return data["choices"][0]["message"]["content"]
        
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

    def chat_stream(self, user_input: str):
        if not self.config:
            logger.error("LLM config not set")
            return
        
        self.conversation.add_message("user", user_input)
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.model,
            "messages": self.conversation.get_messages(),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "stream": True
        }
        
        try:
            response = self.session.post(
                self.config.base_url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"API error: {response.status_code}")
                self.conversation.messages.pop()
                return
            
            full_content = ""
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    yield content
                        except json.JSONDecodeError:
                            continue
            
            if full_content:
                self.conversation.add_message("assistant", full_content)
        
        except Exception as e:
            logger.error(f"Stream failed: {e}")
            self.conversation.messages.pop()

    def set_system_prompt(self, prompt: str):
        self.conversation.system_prompt = prompt

    def clear_history(self):
        self.conversation.clear()

    def get_conversation_history(self) -> List[Dict[str, str]]:
        return [msg.to_dict() for msg in self.conversation.messages]


class EmotionAnalyzer:
    def __init__(self):
        self.emotion_keywords = {
            "happy": ["开心", "高兴", "棒", "太好了", "喜欢", "爱", "哈哈", "快乐"],
            "sad": ["难过", "伤心", "不好", "糟糕", "失望", "哭", "不开心"],
            "surprised": ["哇", "天哪", "真的", "竟然", "惊讶", "不敢相信"],
            "angry": ["生气", "讨厌", "烦", "气死", "愤怒"],
            "shy": ["嗯", "那个", "不好意思", "害羞"],
            "curious": ["好奇", "想知道", "为什么", "怎么", "什么"],
            "excited": ["太棒了", "激动", "兴奋", "迫不及待"]
        }

    def analyze(self, text: str) -> str:
        text = text.lower()
        emotion_scores = {}
        
        for emotion, keywords in self.emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                emotion_scores[emotion] = score
        
        if not emotion_scores:
            return "neutral"
        
        return max(emotion_scores.items(), key=lambda x: x[1])[0]


if __name__ == "__main__":
    import os
    
    api_key = os.getenv("GLM_API_KEY")
    
    if not api_key:
        print("Please set GLM_API_KEY environment variable")
        exit(1)
    
    config = LLMConfig(api_key=api_key)
    client = GLM4Client(config)
    
    print("GLM-4 Chat (type 'quit' to exit)")
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() == 'quit':
            break
        
        response = client.chat(user_input)
        
        if response:
            print(f"Assistant: {response}")
        else:
            print("Failed to get response")
