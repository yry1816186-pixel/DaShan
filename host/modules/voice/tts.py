import piper
import wave
import numpy as np
import io
import logging
import threading
from typing import Optional, Callable
from dataclasses import dataclass
from enum import IntEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VoiceType(IntEnum):
    MALE = 0
    FEMALE = 1
    CHILD = 2


@dataclass
class TTSConfig:
    model_path: str = "models/tts/zh_CN-xiaoyan-low"
    config_path: str = "models/tts/zh_CN-xiaoyan-low.onnx.json"
    sample_rate: int = 22050
    speaker_id: int = 0
    noise_scale: float = 0.667
    length_scale: float = 1.0
    noise_w: float = 0.8


class TextToSpeech:
    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.model = None
        self.synthesizer = None
        self.playing = False
        self._audio_callback: Optional[Callable[[bytes], None]] = None

    def load_model(self, model_path: Optional[str] = None, config_path: Optional[str] = None):
        try:
            model = model_path or self.config.model_path
            config = config_path or self.config.config_path
            
            logger.info(f"Loading TTS model: {model}")
            self.model = piper.PiperModel.load(model)
            logger.info("TTS model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load TTS model: {e}")
            return False

    def synthesize(self, text: str, output_file: Optional[str] = None) -> Optional[bytes]:
        if self.model is None:
            if not self.load_model():
                return None
        
        try:
            logger.info(f"Synthesizing text: {text[:50]}...")
            
            audio_stream = self.model.synthesize_stream(
                text,
                speaker_id=self.config.speaker_id,
                length_scale=self.config.length_scale,
                noise_scale=self.config.noise_scale,
                noise_w=self.config.noise_w
            )
            
            audio_data = bytearray()
            for chunk in audio_stream:
                audio_data.extend(chunk.tobytes())
            
            audio_bytes = bytes(audio_data)
            
            if output_file:
                self._save_wav(audio_bytes, output_file)
                logger.info(f"Saved audio to: {output_file}")
            
            return audio_bytes
        except Exception as e:
            logger.error(f"Failed to synthesize text: {e}")
            return None

    def synthesize_stream(self, text: str, chunk_size: int = 1024):
        if self.model is None:
            if not self.load_model():
                return
        
        try:
            logger.info(f"Synthesizing text (stream): {text[:50]}...")
            
            audio_stream = self.model.synthesize_stream(
                text,
                speaker_id=self.config.speaker_id,
                length_scale=self.config.length_scale,
                noise_scale=self.config.noise_scale,
                noise_w=self.config.noise_w
            )
            
            for chunk in audio_stream:
                audio_chunk = chunk.tobytes()
                for i in range(0, len(audio_chunk), chunk_size):
                    yield audio_chunk[i:i + chunk_size]
                    
                    if self._audio_callback:
                        self._audio_callback(audio_chunk[i:i + chunk_size])
        except Exception as e:
            logger.error(f"Failed to synthesize stream: {e}")

    def _save_wav(self, audio_data: bytes, filename: str):
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.config.sample_rate)
            wav_file.writeframes(audio_data)

    def set_audio_callback(self, callback: Callable[[bytes], None]):
        self._audio_callback = callback

    def estimate_duration(self, text: str) -> float:
        ch_per_sec = 4.0
        return len(text) / ch_per_sec

    def set_speed(self, speed: float):
        if speed > 0:
            self.config.length_scale = 1.0 / speed

    def set_pitch(self, pitch: float):
        self.config.noise_scale = max(0.1, min(2.0, pitch))


class EmotionTTS(TextToSpeech):
    def __init__(self, config: Optional[TTSConfig] = None):
        super().__init__(config)
        self.emotion_tags = {
            "happy": ["哈哈", "太好了", "棒", "开心", "高兴"],
            "sad": ["难过", "伤心", "不好", "糟糕"],
            "surprised": ["哇", "天哪", "真的", "竟然"],
            "angry": ["生气", "讨厌", "烦", "气死"],
            "shy": ["嗯", "那个", "不好意思"],
        }

    def synthesize_with_emotion(self, text: str, emotion: str = "neutral") -> Optional[bytes]:
        modified_text = self._apply_emotion(text, emotion)
        return self.synthesize(modified_text)

    def _apply_emotion(self, text: str, emotion: str) -> str:
        if emotion == "neutral":
            return text
        
        tags = self.emotion_tags.get(emotion, [])
        if not tags:
            return text
        
        import random
        tag = random.choice(tags)
        return f"{tag}，{text}"

    def detect_emotion(self, text: str) -> str:
        for emotion, keywords in self.emotion_tags.items():
            if any(keyword in text for keyword in keywords):
                return emotion
        return "neutral"


if __name__ == "__main__":
    config = TTSConfig(
        model_path="models/tts/zh_CN-xiaoyan-low",
        sample_rate=22050
    )
    
    tts = TextToSpeech(config)
    
    text = "你好，我是瓦力，很高兴见到你！"
    
    audio_data = tts.synthesize(text, output_file="output.wav")
    
    if audio_data:
        print(f"Synthesized {len(audio_data)} bytes")
    else:
        print("Failed to synthesize")
