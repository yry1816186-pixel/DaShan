import os
import yaml
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SerialConfig:
    port: Optional[str] = None
    baudrate: int = 115200
    timeout: float = 2.0


@dataclass
class LLMConfig:
    api_key: str = ""
    model: str = "glm-4"
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9
    timeout: int = 30


@dataclass
class VoiceConfig:
    wake_word: str = "瓦力"
    wake_threshold: float = 0.5
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    language: str = "zh"
    stt_model: str = "base"
    tts_model: str = "zh_CN-xiaoyan-low"
    tts_sample_rate: int = 22050


@dataclass
class VisionConfig:
    enabled: bool = True
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15
    face_detection_model: str = "hog"
    min_face_size: int = 50
    gaze_tracking: bool = True


@dataclass
class BehaviorConfig:
    idle_timeout: float = 30.0
    random_behavior_interval: float = 15.0
    animation_duration: float = 0.5
    blink_interval_min: float = 2.0
    blink_interval_max: float = 5.0


@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "data/logs"
    max_size: int = 10485760
    backup_count: int = 5


@dataclass
class Config:
    serial: SerialConfig = field(default_factory=SerialConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    log: LogConfig = field(default_factory=LogConfig)
    
    def __post_init__(self):
        if not self.llm.api_key:
            self.llm.api_key = os.getenv("GLM_API_KEY", "")


class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self.config: Optional[Config] = None
        
    def _find_config_file(self) -> str:
        possible_paths = [
            "config/settings.yaml",
            "settings.yaml",
            "config.yaml",
            "../config/settings.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return "config/settings.yaml"
    
    def load(self) -> Config:
        if not os.path.exists(self.config_path):
            logger.info(f"Config file not found at {self.config_path}, creating default")
            self.config = Config()
            self._create_default_config()
            return self.config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            self.config = Config(
                serial=SerialConfig(**data.get('serial', {})),
                llm=LLMConfig(**data.get('llm', {})),
                voice=VoiceConfig(**data.get('voice', {})),
                vision=VisionConfig(**data.get('vision', {})),
                behavior=BehaviorConfig(**data.get('behavior', {})),
                log=LogConfig(**data.get('log', {}))
            )
            
            logger.info(f"Config loaded from {self.config_path}")
            return self.config
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            self.config = Config()
            return self.config
    
    def save(self) -> bool:
        if not self.config:
            return False
        
        try:
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump({
                    'serial': {
                        'port': self.config.serial.port,
                        'baudrate': self.config.serial.baudrate,
                        'timeout': self.config.serial.timeout
                    },
                    'llm': {
                        'api_key': self.config.llm.api_key,
                        'model': self.config.llm.model,
                        'base_url': self.config.llm.base_url,
                        'temperature': self.config.llm.temperature,
                        'max_tokens': self.config.llm.max_tokens,
                        'top_p': self.config.llm.top_p,
                        'timeout': self.config.llm.timeout
                    },
                    'voice': {
                        'wake_word': self.config.voice.wake_word,
                        'wake_threshold': self.config.voice.wake_threshold,
                        'sample_rate': self.config.voice.sample_rate,
                        'channels': self.config.voice.channels,
                        'chunk_size': self.config.voice.chunk_size,
                        'language': self.config.voice.language,
                        'stt_model': self.config.voice.stt_model,
                        'tts_model': self.config.voice.tts_model,
                        'tts_sample_rate': self.config.voice.tts_sample_rate
                    },
                    'vision': {
                        'enabled': self.config.vision.enabled,
                        'camera_index': self.config.vision.camera_index,
                        'width': self.config.vision.width,
                        'height': self.config.vision.height,
                        'fps': self.config.vision.fps,
                        'face_detection_model': self.config.vision.face_detection_model,
                        'min_face_size': self.config.vision.min_face_size,
                        'gaze_tracking': self.config.vision.gaze_tracking
                    },
                    'behavior': {
                        'idle_timeout': self.config.behavior.idle_timeout,
                        'random_behavior_interval': self.config.behavior.random_behavior_interval,
                        'animation_duration': self.config.behavior.animation_duration,
                        'blink_interval_min': self.config.behavior.blink_interval_min,
                        'blink_interval_max': self.config.behavior.blink_interval_max
                    },
                    'log': {
                        'level': self.config.log.level,
                        'format': self.config.log.format,
                        'log_dir': self.config.log.log_dir,
                        'max_size': self.config.log.max_size,
                        'backup_count': self.config.log.backup_count
                    }
                }, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            logger.info(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def _create_default_config(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self.save()
    
    def reload(self) -> Config:
        self.config = self.load()
        return self.config
    
    def get(self, key: str, default: Any = None) -> Any:
        if not self.config:
            self.load()
        
        if hasattr(self.config, key):
            return getattr(self.config, key)
        
        sub_keys = key.split('.')
        value = self.config
        for k in sub_keys:
            if hasattr(value, k):
                value = getattr(value, k)
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        if not self.config:
            self.load()
        
        sub_keys = key.split('.')
        obj = self.config
        for k in sub_keys[:-1]:
            if hasattr(obj, k):
                obj = getattr(obj, k)
            else:
                return False
        
        if hasattr(obj, sub_keys[-1]):
            setattr(obj, sub_keys[-1], value)
            return True
        
        return False


_global_config: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> Config:
    global _global_config
    if _global_config is None:
        _global_config = ConfigManager(config_path)
        _global_config.load()
    return _global_config.config


def reload_config():
    global _global_config
    if _global_config:
        _global_config.reload()
