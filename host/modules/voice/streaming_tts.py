import logging
import numpy as np
import io
import queue
import threading
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    audio_data: np.ndarray
    sample_rate: int
    text: str
    duration: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_shape": self.audio_data.shape,
            "sample_rate": self.sample_rate,
            "text": self.text,
            "duration": self.duration,
            "metadata": self.metadata
        }


class BaseTTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> Optional[np.ndarray]:
        pass
    
    @abstractmethod
    def synthesize_stream(self, text: str):
        pass
    
    @abstractmethod
    def get_voices(self) -> List[Dict[str, str]]:
        pass
    
    @abstractmethod
    def set_voice(self, voice_id: str):
        pass
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        pass


class PiperTTSEngine(BaseTTSEngine):
    def __init__(
        self,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        sample_rate: int = 22050,
        voice_id: str = "default"
    ):
        self.model_path = model_path
        self.config_path = config_path
        self._sample_rate = sample_rate
        self.voice_id = voice_id
        self._model = None
        self._loaded = False
        
        self._load_model()
        
        logger.info(f"PiperTTS initialized (voice={voice_id}, sr={sample_rate})")
    
    def _load_model(self):
        try:
            from piper import PiperVoice
            
            if self.model_path and self.config_path:
                self._model = PiperVoice.load(self.model_path, self.config_path)
            else:
                logger.warning("No model path provided, using default")
            
            self._loaded = True
            logger.info("Piper model loaded")
        
        except ImportError:
            logger.error("piper-tts not installed")
        except Exception as e:
            logger.error(f"Failed to load Piper model: {e}")
    
    def synthesize(self, text: str) -> Optional[np.ndarray]:
        if not self._loaded or not self._model:
            logger.error("Model not loaded")
            return None
        
        try:
            import numpy as np
            
            text = self._preprocess_text(text)
            
            audio = self._model.synthesize(text)
            
            audio_np = np.array(audio, dtype=np.float32)
            
            return audio_np
        
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return None
    
    def synthesize_stream(self, text: str):
        if not self._loaded or not self._model:
            return
        
        text = self._preprocess_text(text)
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            audio = self._model.synthesize(sentence)
            yield audio
    
    def _preprocess_text(self, text: str) -> str:
        import re
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _split_sentences(self, text: str) -> List[str]:
        import re
        
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def get_voices(self) -> List[Dict[str, str]]:
        return [{"id": "default", "name": "Default Voice"}]
    
    def set_voice(self, voice_id: str):
        logger.info(f"Setting voice to: {voice_id}")
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate


class EdgeTTSEngine(BaseTTSEngine):
    def __init__(
        self,
        model_name: str = "edge-tts",
        voice: str = "zh-CN-XiaoxiaoNeural",
        sample_rate: int = 24000
    ):
        self.model_name = model_name
        self.voice = voice
        self._sample_rate = sample_rate
        self._loaded = False
        
        logger.info(f"EdgeTTS initialized (voice={voice})")
    
    def synthesize(self, text: str) -> Optional[np.ndarray]:
        try:
            import edge_tts
            
            communicate = edge_tts.Communicate(text, self.voice)
            
            audio_data = io.BytesIO()
            
            async def get_audio():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data.write(chunk["data"])
            
            import asyncio
            asyncio.run(get_audio())
            
            audio_data.seek(0)
            
            if SOUNDFILE_AVAILABLE:
                audio, sr = sf.read(audio_data)
                
                if len(audio.shape) > 1:
                    audio = audio[:, 0]
                
                return audio.astype(np.float32)
            else:
                logger.error("soundfile not available")
                return None
        
        except ImportError:
            logger.error("edge-tts not installed")
            return None
        except Exception as e:
            logger.error(f"EdgeTTS synthesis failed: {e}")
            return None
    
    def synthesize_stream(self, text: str):
        try:
            import edge_tts
            
            communicate = edge_tts.Communicate(text, self.voice)
            
            async def get_audio_stream():
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_bytes = chunk["data"]
                        
                        if SOUNDFILE_AVAILABLE:
                            audio_file = io.BytesIO(audio_bytes)
                            audio, sr = sf.read(audio_file)
                            
                            if len(audio.shape) > 1:
                                audio = audio[:, 0]
                            
                            yield audio.astype(np.float32)
            
            import asyncio
            
            async def generate():
                async for audio in get_audio_stream():
                    yield audio
            
            gen = generate()
            
            try:
                while True:
                    yield asyncio.run(gen.__anext__())
            except StopAsyncIteration:
                pass
        
        except ImportError:
            logger.error("edge-tts not installed")
        except Exception as e:
            logger.error(f"EdgeTTS stream failed: {e}")
    
    def get_voices(self) -> List[Dict[str, str]]:
        voices = [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓 (女声)"},
            {"id": "zh-CN-YunxiNeural", "name": "云希 (男声)"},
            {"id": "zh-CN-YunyangNeural", "name": "云扬 (男声)"},
            {"id": "zh-CN-XiaoyiNeural", "name": "晓伊 (女声)"},
            {"id": "en-US-AriaNeural", "name": "Aria (English)"},
            {"id": "en-US-GuyNeural", "name": "Guy (English)"}
        ]
        return voices
    
    def set_voice(self, voice_id: str):
        self.voice = voice_id
        logger.info(f"Voice set to: {voice_id}")
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate


class StreamingTTS:
    def __init__(
        self,
        engine: str = "edge",
        engine_config: Dict[str, Any] = None,
        buffer_size: int = 8192
    ):
        self.engine_name = engine
        self.buffer_size = buffer_size
        
        self._engine = self._create_engine(engine, engine_config or {})
        
        self._playback_queue = queue.Queue(maxsize=20)
        self._is_playing = False
        self._playback_thread: Optional[threading.Thread] = None
        
        self._callbacks: Dict[str, List[Callable]] = {
            "on_start": [],
            "on_complete": [],
            "on_chunk": [],
            "on_error": []
        }
        
        logger.info(f"StreamingTTS initialized (engine={engine})")
    
    def _create_engine(self, engine: str, config: Dict[str, Any]) -> BaseTTSEngine:
        if engine == "piper":
            return PiperTTSEngine(
                model_path=config.get("model_path"),
                config_path=config.get("config_path"),
                voice_id=config.get("voice_id", "default")
            )
        elif engine == "edge":
            return EdgeTTSEngine(
                voice=config.get("voice", "zh-CN-XiaoxiaoNeural"),
                sample_rate=config.get("sample_rate", 24000)
            )
        else:
            logger.warning(f"Unknown engine {engine}, using edge")
            return EdgeTTSEngine()
    
    def synthesize(self, text: str) -> Optional[TTSResult]:
        try:
            audio_data = self._engine.synthesize(text)
            
            if audio_data is None:
                return None
            
            duration = len(audio_data) / self._engine.sample_rate
            
            result = TTSResult(
                audio_data=audio_data,
                sample_rate=self._engine.sample_rate,
                text=text,
                duration=duration,
                metadata={"engine": self.engine_name}
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            self._emit("on_error", {"error": str(e)})
            return None
    
    def synthesize_stream(self, text: str):
        try:
            self._emit("on_start", {"text": text})
            
            for chunk_audio in self._engine.synthesize_stream(text):
                duration = len(chunk_audio) / self._engine.sample_rate
                
                result = TTSResult(
                    audio_data=chunk_audio,
                    sample_rate=self._engine.sample_rate,
                    text=text,
                    duration=duration,
                    metadata={"engine": self.engine_name}
                )
                
                self._emit("on_chunk", result)
                
                yield result
            
            self._emit("on_complete", {"text": text})
        
        except Exception as e:
            logger.error(f"Stream synthesis failed: {e}")
            self._emit("on_error", {"error": str(e)})
    
    def speak(self, text: str, blocking: bool = False):
        result = self.synthesize(text)
        
        if result:
            self.play_audio(result.audio_data, blocking)
    
    def speak_stream(self, text: str):
        if not SOUNDDEVICE_AVAILABLE:
            logger.error("sounddevice not available")
            return
        
        self._is_playing = True
        
        def playback_worker():
            try:
                for chunk in self._engine.synthesize_stream(text):
                    sd.play(chunk, self._engine.sample_rate)
                    sd.wait()
                
                self._is_playing = False
                self._emit("on_complete", {"text": text})
            
            except Exception as e:
                logger.error(f"Playback error: {e}")
                self._emit("on_error", {"error": str(e)})
                self._is_playing = False
        
        self._playback_thread = threading.Thread(
            target=playback_worker,
            daemon=True
        )
        self._playback_thread.start()
    
    def play_audio(self, audio_data: np.ndarray, blocking: bool = False):
        if not SOUNDDEVICE_AVAILABLE:
            logger.error("sounddevice not available")
            return
        
        try:
            if blocking:
                sd.play(audio_data, self._engine.sample_rate)
                sd.wait()
            else:
                sd.play(audio_data, self._engine.sample_rate)
        
        except Exception as e:
            logger.error(f"Playback failed: {e}")
    
    def stop(self):
        if SOUNDDEVICE_AVAILABLE:
            sd.stop()
        
        self._is_playing = False
        logger.info("Playback stopped")
    
    def is_playing(self) -> bool:
        if SOUNDDEVICE_AVAILABLE:
            return sd.get_stream().active if sd.get_stream() else False
        return self._is_playing
    
    def on(self, event: str, callback: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, data: Dict[str, Any]):
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def set_voice(self, voice_id: str):
        self._engine.set_voice(voice_id)
        logger.info(f"Voice changed to: {voice_id}")
    
    def get_voices(self) -> List[Dict[str, str]]:
        return self._engine.get_voices()
    
    def estimate_duration(self, text: str) -> float:
        avg_chars_per_second = 4.0
        return len(text) / avg_chars_per_second
    
    def save_to_file(self, text: str, filepath: str) -> bool:
        result = self.synthesize(text)
        
        if result and SOUNDFILE_AVAILABLE:
            try:
                sf.write(filepath, result.audio_data, result.sample_rate)
                logger.info(f"Audio saved to: {filepath}")
                return True
            except Exception as e:
                logger.error(f"Failed to save audio: {e}")
                return False
        
        return False
    
    @property
    def sample_rate(self) -> int:
        return self._engine.sample_rate
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine": self.engine_name,
            "voice": getattr(self._engine, 'voice', 'default'),
            "sample_rate": self._engine.sample_rate,
            "is_playing": self.is_playing(),
            "buffer_size": self.buffer_size
        }


class VoiceManager:
    def __init__(
        self,
        stt_config: Dict[str, Any] = None,
        tts_config: Dict[str, Any] = None
    ):
        self.stt = None
        self.tts = None
        
        if stt_config:
            from .realtime_stt import RealtimeSTT
            self.stt = RealtimeSTT(**stt_config)
        
        if tts_config:
            self.tts = StreamingTTS(**tts_config)
        
        self._is_listening = False
        self._current_transcript = ""
        
        logger.info("VoiceManager initialized")
    
    def start_listening(self):
        if self.stt:
            self.stt.start_listening()
            self._is_listening = True
    
    def stop_listening(self):
        if self.stt:
            self.stt.stop_listening()
            self._is_listening = False
    
    def get_recognized_text(self) -> Optional[str]:
        if self.stt:
            return self.stt.get_recognized_text()
        return None
    
    def speak(self, text: str, blocking: bool = False):
        if self.tts:
            self.tts.speak(text, blocking)
    
    def speak_stream(self, text: str):
        if self.tts:
            self.tts.speak_stream(text)
    
    def set_voice(self, voice_id: str):
        if self.tts:
            self.tts.set_voice(voice_id)
    
    def get_voices(self) -> List[Dict[str, str]]:
        if self.tts:
            return self.tts.get_voices()
        return []
    
    def is_listening(self) -> bool:
        return self._is_listening
    
    def is_speaking(self) -> bool:
        if self.tts:
            return self.tts.is_playing()
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "listening": self._is_listening,
            "speaking": self.is_speaking()
        }
        
        if self.stt:
            stats["stt"] = self.stt.get_stats()
        
        if self.tts:
            stats["tts"] = self.tts.get_stats()
        
        return stats
