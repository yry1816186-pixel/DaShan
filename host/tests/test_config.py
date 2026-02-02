import pytest
import tempfile
import os
from pathlib import Path
from host.core.config import ConfigManager, Config, SerialConfig, LLMConfig


@pytest.fixture
def temp_config_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
serial:
  port: COM3
  baudrate: 115200
  timeout: 2.0

llm:
  api_key: test_key_123
  model: test-model
  temperature: 0.5
""")
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def config_manager(temp_config_file):
    return ConfigManager(temp_config_file)


def test_config_manager_init(config_manager):
    assert config_manager is not None
    assert config_manager.config_path == temp_config_file


def test_config_manager_load(config_manager):
    config = config_manager.load()
    
    assert isinstance(config, Config)
    assert config.serial.port == "COM3"
    assert config.serial.baudrate == 115200
    assert config.llm.api_key == "test_key_123"
    assert config.llm.model == "test-model"
    assert config.llm.temperature == 0.5


def test_config_manager_save(config_manager, temp_config_file):
    config = config_manager.load()
    config.serial.baudrate = 9600
    
    result = config_manager.save()
    assert result is True
    
    new_manager = ConfigManager(temp_config_file)
    new_config = new_manager.load()
    assert new_config.serial.baudrate == 9600


def test_config_manager_get(config_manager):
    config_manager.load()
    
    port = config_manager.get('serial.port')
    assert port == "COM3"
    
    baudrate = config_manager.get('serial.baudrate')
    assert baudrate == 115200


def test_config_manager_set(config_manager):
    config_manager.load()
    
    result = config_manager.set('serial.baudrate', 57600)
    assert result is True
    
    baudrate = config_manager.get('serial.baudrate')
    assert baudrate == 57600


def test_config_default_values():
    with tempfile.TemporaryDirectory() as temp_dir:
        non_existent_file = os.path.join(temp_dir, 'non_existent.yaml')
        manager = ConfigManager(non_existent_file)
        config = manager.load()
        
        assert isinstance(config, Config)
        assert config.llm.api_key == ""
        assert config.voice.wake_word == "瓦力"


def test_get_config_singleton():
    from host.core.config import get_config, reload_config
    
    config1 = get_config()
    config2 = get_config()
    
    assert config1 is config2
    
    reload_config()
    config3 = get_config()
    
    assert config1 is not config3
