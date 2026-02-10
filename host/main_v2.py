import logging
import asyncio
import threading
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from core.agent import DashanAgent, ToolRegistry, AgentConfig, AgentMode
from core.rag import KnowledgeManager
from core.behavior_tree import (
    BehaviorTree, SequenceNode, SelectorNode,
    WakeUpBehavior, SleepBehavior, ListenBehavior,
    ThinkBehavior, RespondBehavior, IdleBehavior,
    CheckWakeWord, CheckProximity, UpdateInteractionTime,
    ExpressEmotion, TrackFaceBehavior
)
from core.multimodal import CLIPEncoder, MultimodalFusionEngine, VisionLanguageModel, EmotionRecognizer

from modules.voice.realtime_stt import RealtimeSTT
from modules.voice.streaming_tts import StreamingTTS, VoiceManager
from modules.vision.face_tracker import FaceTracker
from modules.dialogue.llm import LLMClient

from web import create_app, WebSocketManager, WebSocketBroadcaster

from modules.protocol.protocol_client import ProtocolClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class DaShanSystem:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        
        self.protocol_client = ProtocolClient(
            port=self.config.get("serial_port", "COM3"),
            baudrate=self.config.get("baudrate", 115200)
        )
        
        self.broadcaster = WebSocketBroadcaster()
        self.ws_manager = WebSocketManager(self.broadcaster)
        
        self._init_components()
        self._build_behavior_tree()
        
        self._running = False
        self._main_thread: Optional[threading.Thread] = None
        
        logger.info("DaShanSystem V2.0 initialized")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "serial_port": "COM3",
            "baudrate": 115200,
            "llm": {
                "model": "glm-4",
                "api_key": "",
                "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "voice": {
                "stt": {
                    "model_name": "base",
                    "sample_rate": 16000,
                    "language": "zh"
                },
                "tts": {
                    "engine": "edge",
                    "voice": "zh-CN-XiaoxiaoNeural",
                    "sample_rate": 24000
                }
            },
            "web": {
                "host": "0.0.0.0",
                "port": 8000
            },
            "rag": {
                "store_type": "chromadb",
                "persist_directory": "./data/knowledge_db",
                "embedding_model": "shibing624/text2vec-base-chinese"
            },
            "multimodal": {
                "clip_model": "openai/clip-vit-base-patch32",
                "device": "auto"
            }
        }
    
    def _init_components(self):
        llm_config = self.config.get("llm", {})
        
        self.agent_config = AgentConfig(
            llm_provider="glm",
            model=llm_config.get("model", "glm-4"),
            api_key=llm_config.get("api_key", ""),
            base_url=llm_config.get("base_url", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 2000),
            mode=AgentMode.CHAT
        )
        
        self.tool_registry = ToolRegistry()
        self._register_default_tools()
        
        self.agent = DashanAgent(self.agent_config, self.tool_registry)
        
        rag_config = self.config.get("rag", {})
        self.knowledge_manager = KnowledgeManager(
            store_type=rag_config.get("store_type", "chromadb"),
            persist_directory=rag_config.get("persist_directory", "./data/knowledge_db"),
            embedding_model=rag_config.get("embedding_model", "shibing624/text2vec-base-chinese")
        )
        
        voice_config = self.config.get("voice", {})
        stt_config = voice_config.get("stt", {})
        tts_config = voice_config.get("tts", {})
        
        self.stt = RealtimeSTT(**stt_config)
        self.tts = StreamingTTS(**tts_config)
        self.voice_manager = VoiceManager(stt_config, tts_config)
        
        self.face_tracker = FaceTracker()
        
        multimodal_config = self.config.get("multimodal", {})
        from core.multimodal import CLIPModelConfig
        
        self.clip_encoder = CLIPEncoder(
            CLIPModelConfig(
                model_name=multimodal_config.get("clip_model", "openai/clip-vit-base-patch32"),
                device=multimodal_config.get("device", "auto")
            )
        )
        
        self.multimodal_fusion = MultimodalFusionEngine(self.clip_encoder)
        self.vlm = VisionLanguageModel(self.clip_encoder, self.agent)
        
        self.emotion_recognizer = EmotionRecognizer()
        
        web_config = self.config.get("web", {})
        self.app = create_app(
            host=web_config.get("host", "0.0.0.0"),
            port=web_config.get("port", 8000)
        )
        
        self._setup_event_handlers()
        
        logger.info("All components initialized")
    
    def _register_default_tools(self):
        from core.agent.tool_registry import (
            SearchTool, CalculatorTool, TimeTool, WeatherTool
        )
        
        self.tool_registry.register(SearchTool())
        self.tool_registry.register(CalculatorTool())
        self.tool_registry.register(TimeTool())
        self.tool_registry.register(WeatherTool())
        
        logger.info("Default tools registered")
    
    def _setup_event_handlers(self):
        self.agent.on("input_received", self._on_agent_input)
        self.agent.on("processing_complete", self._on_agent_complete)
        self.agent.on("error", self._on_agent_error)
        
        self.stt.on("on_speech_start", self._on_speech_start)
        self.stt.on("on_speech_end", self._on_speech_end)
        self.stt.on("on_transcript", self._on_transcript)
        
        self.broadcaster.on("robot_command", self._on_robot_command)
        self.broadcaster.on("agent_query", self._on_agent_query)
        
        logger.info("Event handlers configured")
    
    def _build_behavior_tree(self):
        from core.behavior_tree import (
            SequenceNode, SelectorNode, ParallelNode,
            RepeatNode, CooldownNode, ConditionNode
        )
        
        root = SelectorNode(
            "RootSelector",
            children=[
                SequenceNode(
                    "EmergencySequence",
                    [
                        ConditionNode("CheckEmergency", lambda ctx: ctx.get("emergency", False)),
                        ActionNode("HandleEmergency", self._handle_emergency)
                    ],
                    priority=10
                ),
                SequenceNode(
                    "InteractionSequence",
                    [
                        CheckWakeWord("CheckWakeWord", wake_word_detector=self.stt),
                        UpdateInteractionTime("UpdateInteraction"),
                        WakeUpBehavior("WakeUp", protocol_client=self.protocol_client),
                        ListenBehavior("Listen", protocol_client=self.protocol_client, voice_manager=self.voice_manager),
                        ThinkBehavior("Think", protocol_client=self.protocol_client, agent=self.agent),
                        RespondBehavior("Respond", protocol_client=self.protocol_client, tts_engine=self.tts),
                        ExpressEmotion("ExpressEmotion", protocol_client=self.protocol_client)
                    ],
                    priority=5
                ),
                SequenceNode(
                    "TrackingSequence",
                    [
                        ConditionNode("ShouldTrack", lambda ctx: ctx.get("face_detected", False)),
                        TrackFaceBehavior("TrackFace", protocol_client=self.protocol_client, face_tracker=self.face_tracker),
                        IdleBehavior("IdleTrack", protocol_client=self.protocol_client)
                    ],
                    priority=3
                ),
                SequenceNode(
                    "IdleSequence",
                    [
                        CheckProximity("CheckProximity"),
                        IdleBehavior("Idle", protocol_client=self.protocol_client)
                    ],
                    priority=1
                ),
                SequenceNode(
                    "SleepSequence",
                    [
                        ConditionNode("CheckSleep", lambda ctx: ctx.get("idle_time", 0) > 300),
                        SleepBehavior("Sleep", protocol_client=self.protocol_client)
                    ],
                    priority=2
                )
            ],
            use_priority=True
        )
        
        self.behavior_tree = BehaviorTree(root, "DaShan_BT_V2")
        
        logger.info("Behavior tree built successfully")
    
    async def _on_agent_input(self, data: Dict[str, Any]):
        self.broadcaster.broadcast("agent_input", data)
        self.protocol_client.set_expression(3, brightness=200)
    
    async def _on_agent_complete(self, data: Dict[str, Any]):
        self.broadcaster.broadcast("agent_response", data)
        self.behavior_tree.set_variable("last_interaction_time", asyncio.get_event_loop().time())
    
    async def _on_agent_error(self, data: Dict[str, Any]):
        logger.error(f"Agent error: {data}")
        self.broadcaster.broadcast("agent_error", data)
    
    def _on_speech_start(self, data: Dict[str, Any]):
        self.broadcaster.broadcast("speech_start", data)
        self.behavior_tree.set_blackboard("speech_active", True)
    
    def _on_speech_end(self, data: Dict[str, Any]):
        self.broadcaster.broadcast("speech_end", data)
        self.behavior_tree.set_blackboard("speech_active", False)
    
    def _on_transcript(self, data: Dict[str, Any]):
        text = data.get("text", "")
        
        self.broadcaster.broadcast("transcript", data)
        self.behavior_tree.set_var("user_input", text)
        
        result = asyncio.run(self.agent.process(text))
        
        if result.get("success"):
            response = result.get("output", "")
            self.tts.speak_stream(response)
    
    def _on_robot_command(self, message):
        data = message.data
        cmd_type = data.get("type")
        params = data.get("params", {})
        
        logger.info(f"Robot command: {cmd_type}, params: {params}")
        
        if cmd_type == "set_expression":
            self.protocol_client.set_expression(
                params.get("id", 1),
                brightness=params.get("brightness", 255)
            )
        elif cmd_type == "set_servo":
            self.protocol_client.set_servo(
                params.get("channel", 1),
                params.get("angle", 90)
            )
        elif cmd_type == "play_animation":
            self.protocol_client.play_animation(params.get("name", "default"))
    
    def _on_agent_query(self, message):
        data = message.data
        question = data.get("question", "")
        
        result = asyncio.run(self.agent.process(question))
        
        self.broadcaster.broadcast("agent_result", result)
    
    def _handle_emergency(self, ctx):
        logger.warning("Emergency handling triggered")
        self.protocol_client.set_expression(0, brightness=50)
        self.broadcaster.broadcast("emergency", {"message": "Emergency triggered"})
    
    def start(self):
        if self._running:
            logger.warning("System already running")
            return
        
        self._running = True
        
        self.protocol_client.connect()
        
        self._main_thread = threading.Thread(
            target=self._run_behavior_tree,
            daemon=True
        )
        self._main_thread.start()
        
        self._run_web_server()
        
        logger.info("DaShanSystem started")
    
    def _run_behavior_tree(self):
        try:
            import time
            
            while self._running:
                try:
                    status = self.behavior_tree.tick()
                    
                    if status != 0:
                        logger.debug(f"BT tick status: {status}")
                    
                    time.sleep(0.016)
                
                except Exception as e:
                    logger.error(f"Behavior tree error: {e}")
                    time.sleep(1.0)
        
        except KeyboardInterrupt:
            logger.info("Behavior tree stopped by user")
        finally:
            self._running = False
    
    def _run_web_server(self):
        web_config = self.config.get("web", {})
        
        def run_web():
            import uvicorn
            uvicorn.run(
                self.app,
                host=web_config.get("host", "0.0.0.0"),
                port=web_config.get("port", 8000),
                log_level="info"
            )
        
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()
        
        logger.info(f"Web dashboard started on {web_config.get('host', '0.0.0.0')}:{web_config.get('port', 8000)}")
    
    def stop(self):
        if not self._running:
            return
        
        self._running = False
        
        self.behavior_tree.stop()
        
        if self.stt.is_listening():
            self.stt.stop_listening()
        
        self.tts.stop()
        
        self.protocol_client.disconnect()
        
        logger.info("DaShanSystem stopped")
    
    def get_system_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "behavior_tree": self.behavior_tree.get_stats(),
            "agent": self.agent.get_state(),
            "voice": self.voice_manager.get_stats(),
            "knowledge": self.knowledge_manager.get_stats(),
            "multimodal": {
                "clip": self.clip_encoder.get_model_info(),
                "emotion": self.emotion_recognizer.get_model_info()
            },
            "websocket": self.ws_manager.get_stats(),
            "protocol": self.protocol_client.get_stats() if hasattr(self.protocol_client, 'get_stats') else {}
        }
    
    def add_knowledge(self, filepath: str) -> bool:
        result = self.knowledge_manager.add_document(filepath)
        return result.get("success", False)
    
    def search_knowledge(self, query: str, top_k: int = 5):
        return self.knowledge_manager.search(query, top_k=top_k)
    
    def analyze_image(self, image: Any):
        from core.multimodal import MultimodalInput
        
        caption = self.vlm.generate_caption(image)
        emotions = self.emotion_recognizer.recognize(image)
        
        return {
            "caption": caption,
            "emotions": [e.to_dict() for e in emotions],
            "scene": self.vlm.describe_scene(image)
        }


def main():
    system = DaShanSystem("config/config.yaml")
    
    try:
        system.start()
        
        import time
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        system.stop()


if __name__ == "__main__":
    main()
