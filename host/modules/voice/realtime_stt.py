import logging
import numpy as np
import queue
import threading
from typing import Optional, Callable, List, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime
import time
from abc import ABC, abstractmethod

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import webrtcvad
    WEBRTC_VAD_AVAILABLE = True
except ImportError:
    WEBRTC_VAD_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    audio_data: np.ndarray
    sample_rate: int
    start_time: float
    end_time: float
    is_speech: bool = True
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class VADDetector:
    def __init__(
        self,
        aggressiveness: int = 2,
        frame_duration_ms: int = 30,
        sample_rate: int = 16000
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        if not WEBRTC_VAD_AVAILABLE:
            logger.warning("webrtcvad not available, using energy-based VAD")
            self._use_webrtc_vad = False
        else:
            self.vad = webrtcvad.Vad(aggressiveness)
            self._use_webrtc_vad = True
        
        self._energy_threshold = 0.02
        self._speech_frames = 0
        self._silence_frames = 0
        self._min_speech_frames = 10
        self._min_silence_frames = 20
        
        logger.info(f"VAD initialized (webrtc={self._use_webrtc_vad}, aggressiveness={aggressiveness})")
    
    def is_speech(self, frame: np.ndarray) -> bool:
        if len(frame) != self.frame_size:
            frame = np.resize(frame, self.frame_size)
        
        if self._use_webrtc_vad:
            frame_bytes = (frame * 32767).astype(np.int16).tobytes()
            return bool(self.vad.is_speech(frame_bytes, self.sample_rate))
        else:
            energy = np.mean(np.abs(frame))
            return energy > self._energy_threshold
    
    def detect_segment(
        self,
        frames: List[np.ndarray],
        return_segments: bool = False
    ) -> Dict[str, Any]:
        speech_detected = False
        speech_start = 0
        speech_end = 0
        segments = []
        
        for i, frame in enumerate(frames):
            is_speech_frame = self.is_speech(frame)
            
            if is_speech_frame:
                self._speech_frames += 1
                self._silence_frames = 0
                
                if not speech_detected:
                    speech_detected = True
                    speech_start = i
            else:
                self._silence_frames += 1
                
                if speech_detected:
                    if self._silence_frames >= self._min_silence_frames:
                        speech_detected = False
                        speech_end = i
                        segments.append((speech_start, speech_end))
        
        if speech_detected:
            segments.append((speech_start, len(frames)))
        
        self._speech_frames = 0
        self._silence_frames = 0
        
        if return_segments:
            return {
                "has_speech": len(segments) > 0,
                "segments": segments,
                "total_segments": len(segments)
            }
        
        return {
            "has_speech": len(segments) > 0,
            "total_segments": len(segments)
        }
    
    def set_energy_threshold(self, threshold: float):
        self._energy_threshold = threshold
    
    def reset(self):
        self._speech_frames = 0
        self._silence_frames = 0


class RealtimeSTT:
    def __init__(
        self,
        model_name: str = "base",
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        vad_aggressiveness: int = 2,
        language: str = "zh"
    ):
        self.model_name = model_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.language = language
        
        self.vad = VADDetector(
            aggressiveness=vad_aggressiveness,
            sample_rate=sample_rate
        )
        
        self._audio_queue = queue.Queue(maxsize=100)
        self._text_queue = queue.Queue(maxsize=10)
        self._is_recording = False
        self._is_processing = False
        
        self._callbacks: Dict[str, List[Callable]] = {
            "on_speech_start": [],
            "on_speech_end": [],
            "on_transcript": [],
            "on_error": []
        }
        
        self._model = None
        self._current_buffer = []
        self._recording_thread: Optional[threading.Thread] = None
        self._processing_thread: Optional[threading.Thread] = None
        
        self._load_model()
        
        logger.info(f"RealtimeSTT initialized (model={model_name}, lang={language})")
    
    def _load_model(self):
        try:
            import whisper
            self._model = whisper.load_model(self.model_name)
            logger.info(f"Whisper model loaded: {self.model_name}")
        except ImportError:
            logger.error("whisper not installed. Please install: pip install whisper-openai")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
    
    def start_listening(self):
        if self._is_recording:
            logger.warning("Already recording")
            return
        
        if not PYAUDIO_AVAILABLE:
            logger.error("pyaudio not available")
            return
        
        self._is_recording = True
        self._current_buffer = []
        
        self._recording_thread = threading.Thread(
            target=self._recording_loop,
            daemon=True
        )
        self._processing_thread = threading.Thread(
            target=self._processing_loop,
            daemon=True
        )
        
        self._recording_thread.start()
        self._processing_thread.start()
        
        logger.info("Started listening")
    
    def stop_listening(self):
        if not self._is_recording:
            return
        
        self._is_recording = False
        self._is_processing = False
        
        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)
        if self._processing_thread:
            self._processing_thread.join(timeout=2.0)
        
        logger.info("Stopped listening")
    
    def _recording_loop(self):
        try:
            p = pyaudio.PyAudio()
            
            stream = p.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            stream.start_stream()
            
            while self._is_recording:
                time.sleep(0.1)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
            self._emit("on_error", {"error": str(e)})
    
    def _audio_callback(
        self,
        in_data,
        frame_count,
        time_info,
        status
    ):
        try:
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            self._audio_queue.put(audio_data, block=False)
        except queue.Full:
            pass
        
        return (None, pyaudio.paContinue)
    
    def _processing_loop(self):
        self._is_processing = True
        
        buffer = []
        in_speech = False
        silence_frames = 0
        speech_frames = 0
        
        while self._is_processing or not self._audio_queue.empty():
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                buffer.append(chunk)
                
                if len(buffer) > 0:
                    frame = np.concatenate(buffer)
                    is_speech = self.vad.is_speech(frame)
                    
                    if is_speech:
                        speech_frames += 1
                        silence_frames = 0
                        
                        if not in_speech:
                            in_speech = True
                            self._current_buffer = []
                            self._emit("on_speech_start", {})
                        
                        self._current_buffer.extend(frame)
                    else:
                        silence_frames += 1
                        
                        if in_speech and silence_frames > 30:
                            in_speech = False
                            
                            if len(self._current_buffer) > 0:
                                self._transcribe_current_buffer()
                            
                            self._emit("on_speech_end", {})
                    
                    buffer = []
            
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Processing loop error: {e}")
                self._emit("on_error", {"error": str(e)})
    
    def _transcribe_current_buffer(self):
        if not self._current_buffer or not self._model:
            return
        
        audio = np.array(self._current_buffer)
        
        if len(audio) < self.sample_rate * 0.5:
            return
        
        audio_int16 = (audio * 32767).astype(np.int16)
        
        try:
            result = self._model.transcribe(
                audio_int16,
                language=self.language,
                fp16=False
            )
            
            text = result["text"].strip()
            
            if text:
                self._emit("on_transcript", {"text": text, "segments": result.get("segments", [])})
            
            self._current_buffer = []
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
    
    def on(self, event: str, callback: Callable):
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit(self, event: str, data: Dict[str, Any]):
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def get_recognized_text(self) -> Optional[str]:
        try:
            return self._text_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def transcribe_file(self, filepath: str) -> str:
        if not self._model:
            raise RuntimeError("Model not loaded")
        
        try:
            result = self._model.transcribe(filepath, language=self.language)
            return result["text"].strip()
        except Exception as e:
            logger.error(f"File transcription error: {e}")
            return ""
    
    def set_language(self, language: str):
        self.language = language
        logger.info(f"Language changed to: {language}")
    
    def is_listening(self) -> bool:
        return self._is_recording
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "is_listening": self._is_recording,
            "buffer_size": len(self._current_buffer),
            "vad_enabled": self.vad._use_webrtc_vad
        }


class StreamingSTT(RealtimeSTT):
    def __init__(self, *args, stream_transcript: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_transcript = stream_transcript
        self._partial_transcripts = []
        self._last_transcript = ""
    
    def _transcribe_current_buffer(self):
        if not self._current_buffer or not self._model:
            return
        
        audio = np.array(self._current_buffer)
        
        if len(audio) < self.sample_rate * 0.5:
            return
        
        audio_int16 = (audio * 32767).astype(np.int16)
        
        try:
            result = self._model.transcribe(
                audio_int16,
                language=self.language,
                fp16=False,
                verbose=False
            )
            
            text = result["text"].strip()
            
            if text and text != self._last_transcript:
                self._emit("on_transcript", {
                    "text": text,
                    "partial": True,
                    "segments": result.get("segments", [])
                })
                
                self._last_transcript = text
                self._partial_transcripts.append(text)
            
            self._current_buffer = []
            
        except Exception as e:
            logger.error(f"Streaming transcription error: {e}")
    
    def get_full_transcript(self) -> str:
        return " ".join(self._partial_transcripts)
    
    def clear_transcripts(self):
        self._partial_transcripts.clear()
        self._last_transcript = ""
