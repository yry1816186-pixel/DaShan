import whisper
import torch
import numpy as np
import pyaudio
import queue
import threading
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WhisperModelSize(IntEnum):
    TINY = 1
    BASE = 2
    SMALL = 3
    MEDIUM = 4
    LARGE = 5


@dataclass
class STTConfig:
    model_size: WhisperModelSize = WhisperModelSize.BASE
    device: str = "auto"
    language: str = "zh"
    sample_rate: int = 16000
    chunk_size: int = 1024
    vad_threshold: float = 0.5
    silence_duration: float = 1.0


class SpeechToText:
    def __init__(self, config: Optional[STTConfig] = None):
        self.config = config or STTConfig()
        self.model = None
        self.audio = None
        self.stream = None
        self.running = False
        self.recording = False
        self.audio_queue = queue.Queue()
        self.audio_buffer = []
        self._thread: Optional[threading.Thread] = None

    def load_model(self, model_size: Optional[WhisperModelSize] = None):
        try:
            size = model_size or self.config.model_size
            model_name = self._get_model_name(size)
            
            device = self.config.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            logger.info(f"Loading Whisper model: {model_name} on {device}")
            self.model = whisper.load_model(model_name, device=device)
            logger.info("Whisper model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    def _get_model_name(self, size: WhisperModelSize) -> str:
        return {
            WhisperModelSize.TINY: "tiny",
            WhisperModelSize.BASE: "base",
            WhisperModelSize.SMALL: "small",
            WhisperModelSize.MEDIUM: "medium",
            WhisperModelSize.LARGE: "large"
        }.get(size, "base")

    def start_listening(self):
        if self.model is None:
            if not self.load_model():
                return False
        
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.running = True
            self.recording = False
            self.audio_buffer = []
            
            logger.info("STT started listening")
            return True
        except Exception as e:
            logger.error(f"Failed to start STT: {e}")
            return False

    def stop_listening(self):
        self.running = False
        
        if self._thread:
            self._thread.join(timeout=1.0)
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.audio:
            self.audio.terminate()
        
        logger.info("STT stopped listening")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if self.recording:
            self.audio_buffer.append(in_data)
        
        return (in_data, pyaudio.paContinue)

    def start_recording(self):
        self.recording = True
        self.audio_buffer = []
        logger.info("Recording started")

    def stop_recording(self) -> Optional[str]:
        self.recording = False
        
        if not self.audio_buffer:
            logger.warning("No audio data recorded")
            return None
        
        audio_data = b''.join(self.audio_buffer)
        audio_float = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        logger.info(f"Processing audio: {len(audio_float)} samples")
        
        try:
            result = self.model.transcribe(
                audio_float,
                language=self.config.language,
                fp16=False
            )
            text = result["text"].strip()
            logger.info(f"Transcribed text: {text}")
            return text
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None

    def record_and_transcribe(self, timeout: float = 10.0) -> Optional[str]:
        if not self.running:
            if not self.start_listening():
                return None
        
        self.start_recording()
        
        try:
            import time
            time.sleep(timeout)
        except KeyboardInterrupt:
            pass
        
        return self.stop_recording()

    def transcribe_file(self, audio_path: str) -> Optional[str]:
        if self.model is None:
            if not self.load_model():
                return None
        
        try:
            result = self.model.transcribe(
                audio_path,
                language=self.config.language,
                fp16=False
            )
            text = result["text"].strip()
            logger.info(f"Transcribed file: {text}")
            return text
        except Exception as e:
            logger.error(f"Failed to transcribe file: {e}")
            return None

    def is_recording(self) -> bool:
        return self.recording


class VAD:
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.silence_duration = 0
        self.last_speech_time = 0

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        energy = np.mean(audio_chunk ** 2)
        is_speech = energy > self.threshold
        
        if is_speech:
            self.last_speech_time = self.silence_duration
            self.silence_duration = 0
        else:
            self.silence_duration += len(audio_chunk) / self.sample_rate
        
        return is_speech

    def get_silence_duration(self) -> float:
        return self.silence_duration

    def reset(self):
        self.silence_duration = 0
        self.last_speech_time = 0


if __name__ == "__main__":
    import time
    
    config = STTConfig(
        model_size=WhisperModelSize.BASE,
        language="zh"
    )
    
    stt = SpeechToText(config)
    
    if stt.start_listening():
        print("Listening...")
        print("Press Enter to start recording, then press Enter again to stop")
        
        try:
            while True:
                input()
                stt.start_recording()
                print("Recording... Press Enter to stop")
                input()
                text = stt.stop_recording()
                if text:
                    print(f"Transcribed: {text}")
                else:
                    print("Failed to transcribe")
        except KeyboardInterrupt:
            print("\nStopping...")
        
        stt.stop_listening()
    else:
        print("Failed to start STT")
