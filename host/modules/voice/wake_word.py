import openwakeword
import numpy as np
import pyaudio
import queue
import threading
import logging
from typing import Optional, Callable
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WakeWordConfig:
    model_path: str = "models/wakeword"
    threshold: float = 0.5
    sample_rate: int = 16000
    chunk_size: int = 1280
    channels: int = 1


class WakeWordDetector:
    def __init__(self, config: Optional[WakeWordConfig] = None):
        self.config = config or WakeWordConfig()
        self.oww = None
        self.audio = None
        self.stream = None
        self.running = False
        self.detected_event = threading.Event()
        self.callback: Optional[Callable[[], None]] = None
        self._thread: Optional[threading.Thread] = None
        self.audio_queue = queue.Queue()

    def load_model(self, model_path: Optional[str] = None):
        try:
            path = model_path or self.config.model_path
            self.oww = openwakeword.Model(
                wakeword_models=[path],
                inference_framework='onnx'
            )
            logger.info(f"Wake word model loaded: {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load wake word model: {e}")
            return False

    def start(self):
        if self.oww is None:
            if not self.load_model():
                return False
        
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            self.running = True
            self.detected_event.clear()
            
            self._thread = threading.Thread(target=self._detect_loop, daemon=True)
            self._thread.start()
            
            logger.info("Wake word detector started")
            return True
        except Exception as e:
            logger.error(f"Failed to start wake word detector: {e}")
            return False

    def stop(self):
        self.running = False
        
        if self._thread:
            self._thread.join(timeout=1.0)
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.audio:
            self.audio.terminate()
        
        logger.info("Wake word detector stopped")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        self.audio_queue.put(audio_data)
        
        return (in_data, pyaudio.paContinue)

    def _detect_loop(self):
        audio_buffer = np.array([], dtype=np.int16)
        
        while self.running:
            try:
                while not self.audio_queue.empty():
                    chunk = self.audio_queue.get()
                    audio_buffer = np.concatenate([audio_buffer, chunk])
                    
                    if len(audio_buffer) >= 1280:
                        audio_float = audio_buffer[:1280].astype(np.float32) / 32768.0
                        prediction = self.oww.predict(audio_float)
                        
                        for key, score in prediction.items():
                            if score > self.config.threshold:
                                logger.info(f"Wake word detected: {key} (score: {score:.3f})")
                                if self.callback:
                                    self.callback()
                                self.detected_event.set()
                        
                        audio_buffer = audio_buffer[1280:]
                
                self.detected_event.wait(timeout=0.01)
                self.detected_event.clear()
                
            except Exception as e:
                logger.error(f"Detection error: {e}")

    def set_callback(self, callback: Callable[[], None]):
        self.callback = callback

    def wait_for_wake_word(self, timeout: Optional[float] = None) -> bool:
        return self.detected_event.wait(timeout=timeout)

    def reset(self):
        self.detected_event.clear()


if __name__ == "__main__":
    import time
    
    def on_wake_word():
        print("Wake word detected! Hello!")
    
    config = WakeWordConfig(
        model_path="models/wakeword",
        threshold=0.5
    )
    
    detector = WakeWordDetector(config)
    detector.set_callback(on_wake_word)
    
    if detector.start():
        print("Listening for wake word...")
        try:
            while True:
                if detector.wait_for_wake_word():
                    print("Wake word detected!")
                    time.sleep(1)
                    detector.reset()
        except KeyboardInterrupt:
            print("\nStopping...")
        
        detector.stop()
    else:
        print("Failed to start detector")
