import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import asyncio
from pathlib import Path

from host.main_v2 import DaShanSystem
from host.core.agent.agent_state import AgentState, AgentMessage
from host.core.behavior_tree.behavior_tree import NodeStatus


@pytest.fixture
def mock_config():
    return {
        "serial": {
            "port": "COM3",
            "baudrate": 115200,
            "timeout": 1.0
        },
        "llm": {
            "model": "glm-4",
            "api_key": "test_key",
            "api_base": "https://api.example.com/v4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "voice": {
            "stt_model": "base",
            "tts_engine": "edge-tts",
            "tts_voice": "zh-CN-XiaoxiaoNeural",
            "sample_rate": 16000,
            "channels": 1
        },
        "web": {
            "host": "0.0.0.0",
            "port": 8000,
            "enable_dashboard": True
        },
        "rag": {
            "enabled": True,
            "vector_db": "chromadb",
            "collection_name": "dashan_knowledge",
            "embedding_model": "shibing624/text2vec-base-chinese",
            "chunk_size": 512,
            "chunk_overlap": 50
        },
        "multimodal": {
            "clip_model": "openai/clip-vit-base-patch32",
            "fusion_method": "weighted_sum",
            "fusion_weights": {
                "text": 0.6,
                "image": 0.4
            },
            "enable_emotion": True
        },
        "behavior_tree": {
            "tick_interval": 0.016,
            "enable_parallel": True
        },
        "plugins": {
            "enabled": True,
            "plugin_dirs": ["plugins"],
            "auto_load": True
        },
        "permissions": [
            "text_output",
            "file_read",
            "file_write",
            "camera_access",
            "audio_record"
        ]
    }


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_initialization(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    
    assert system.config == mock_config
    assert system.agent is not None


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_startup(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    
    await system.startup()
    
    assert system.running is True
    mock_protocol_instance.connect.assert_called_once()
    mock_stt_instance.start.assert_called_once()


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_shutdown(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    await system.shutdown()
    
    assert system.running is False
    mock_protocol_instance.disconnect.assert_called_once()
    mock_stt_instance.stop.assert_called_once()


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_process_text(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    result = await system.process_text("你好")
    
    assert result is not None


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_speak(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    await system.speak("你好")
    
    mock_tts_instance.speak.assert_called_once_with("你好")


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_set_expression(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol_instance.send_expression = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    await system.set_expression("happy")
    
    mock_protocol_instance.send_expression.assert_called_once_with("happy")


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_set_servo(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol_instance.send_servo = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    await system.set_servo(1, 90)
    
    mock_protocol_instance.send_servo.assert_called_once_with(1, 90)


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_behavior_tree_running(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    
    await system.startup()
    
    await asyncio.sleep(0.1)
    
    assert system.behavior_tree is not None
    assert system.behavior_tree.running
    
    await system.shutdown()


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_rag_query(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    with patch.object(system.knowledge_manager, 'query', new_callable=AsyncMock) as mock_query:
        mock_query.return_value = ["测试文档1", "测试文档2"]
        
        results = await system.query_knowledge("测试查询")
        
        assert results is not None
        mock_query.assert_called_once_with("测试查询")


@pytest.mark.asyncio
@patch('host.modules.serial.protocol_client.ProtocolClient')
@patch('host.modules.voice.realtime_stt.RealtimeSTT')
@patch('host.modules.voice.streaming_tts.StreamingTTS')
@patch('host.web.api.create_app')
@patch('host.core.multimodal.clip_encoder.CLIPEncoder')
@patch('host.core.agent.agent_graph.ChatOpenAI')
async def test_dashan_system_multimodal_encoding(
    mock_chat, mock_clip, mock_api, mock_tts, mock_stt, mock_protocol, mock_config
):
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="测试回复"))
    mock_chat.return_value = mock_llm
    
    mock_clip_instance = MagicMock()
    mock_clip_instance.encode_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_clip_instance.encode_image = AsyncMock(return_value=[0.4, 0.5, 0.6])
    mock_clip_instance.compute_similarity = AsyncMock(return_value=0.85)
    mock_clip.return_value = mock_clip_instance
    
    mock_protocol_instance = MagicMock()
    mock_protocol_instance.connect = AsyncMock()
    mock_protocol_instance.disconnect = AsyncMock()
    mock_protocol.return_value = mock_protocol_instance
    
    mock_stt_instance = MagicMock()
    mock_stt_instance.start = AsyncMock()
    mock_stt_instance.stop = AsyncMock()
    mock_stt.return_value = mock_stt_instance
    
    mock_tts_instance = MagicMock()
    mock_tts_instance.speak = AsyncMock()
    mock_tts_instance.stop = AsyncMock()
    mock_tts.return_value = mock_tts_instance
    
    mock_app = MagicMock()
    mock_api.return_value = mock_app
    
    system = DaShanSystem(config=mock_config)
    system.running = True
    
    text_embedding = await system.encode_text("测试文本")
    assert text_embedding is not None
    
    similarity = await system.compute_text_image_similarity("测试", Path("test.jpg"))
    assert similarity is not None
