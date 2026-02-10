import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def sample_config():
    return {
        "serial": {"port": "COM3", "baudrate": 115200},
        "llm": {"model": "glm-4", "api_key": "test_key"},
        "voice": {"stt_model": "base", "tts_engine": "edge-tts", "tts_voice": "zh-CN-XiaoxiaoNeural"},
        "web": {"host": "0.0.0.0", "port": 8000},
        "rag": {"vector_db": "chromadb", "embedding_model": "shibing624/text2vec-base-chinese"},
        "multimodal": {"clip_model": "openai/clip-vit-base-patch32", "fusion_weights": {"text": 0.6, "image": 0.4}}
    }
