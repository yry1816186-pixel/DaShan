import cv2
import numpy as np
import threading
import logging
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from .event_bus import EventBus, EventType, Event

logger = logging.getLogger(__name__)


@dataclass
class CameraConfig:
    camera_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15
    backend: int = cv2.CAP_ANY
    api_preference: int = cv2.CAP_ANY
    buffer_size: int = 3


class Camera:
    def __init__(self, config: CameraConfig, event_bus: Optional[EventBus] = None):
        self.config = config
        self.event_bus = event_bus or EventBus.get_instance()
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_buffer = []
        self._lock = threading.Lock()
        self._current_frame: Optional[np.ndarray] = None
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_update = 0
        
        logger.info(f"Camera initialized with config: {config}")
    
    def connect(self) -> bool:
        if self._cap is not None and self._cap.isOpened():
            logger.warning("Camera already connected")
            return True
        
        try:
            self._cap = cv2.VideoCapture(self.config.camera_index, self.config.backend)
            
            if not self._cap.isOpened():
                logger.error(f"Failed to open camera {self.config.camera_index}")
                return False
            
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Camera connected: {actual_width}x{actual_height} @ {actual_fps:.1f}fps")
            
            self.event_bus.publish(EventType.CAMERA_CONNECTED, {
                'width': actual_width,
                'height': actual_height,
                'fps': actual_fps
            }, source='Camera')
            
            return True
        except Exception as e:
            logger.error(f"Camera connection failed: {e}")
            return False
    
    def disconnect(self):
        self.stop()
        
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera disconnected")
    
    def start(self) -> bool:
        if self._running:
            logger.warning("Camera already running")
            return True
        
        if self._cap is None or not self._cap.isOpened():
            if not self.connect():
                return False
        
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="Camera-Capture")
        self._thread.start()
        
        logger.info("Camera capture started")
        return True
    
    def stop(self):
        if not self._running:
            return
        
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        with self._lock:
            self._frame_buffer.clear()
        
        logger.info("Camera capture stopped")
    
    def _capture_loop(self):
        last_time = 0
        frame_count = 0
        
        while self._running:
            try:
                ret, frame = self._cap.read()
                
                if not ret or frame is None:
                    logger.warning("Failed to read frame from camera")
                    continue
                
                self._frame_count += 1
                frame_count += 1
                
                with self._lock:
                    self._current_frame = frame.copy()
                    
                    if len(self._frame_buffer) >= self.config.buffer_size:
                        self._frame_buffer.pop(0)
                    self._frame_buffer.append(frame.copy())
                
                current_time = cv2.getTickCount() / cv2.getTickFrequency()
                
                if current_time - last_time >= 1.0:
                    self._fps = frame_count / (current_time - last_time)
                    frame_count = 0
                    last_time = current_time
                    
                    if current_time - self._last_fps_update >= 5.0:
                        logger.debug(f"Camera FPS: {self._fps:.1f}")
                        self._last_fps_update = current_time
                
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
            
            cv2.waitKey(int(1000 / self.config.fps))
    
    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    def get_latest_frames(self, count: int = 1) -> list[np.ndarray]:
        with self._lock:
            if count >= len(self._frame_buffer):
                return self._frame_buffer.copy()
            return self._frame_buffer[-count:].copy()
    
    def get_fps(self) -> float:
        return self._fps
    
    def get_frame_count(self) -> int:
        return self._frame_count
    
    def is_running(self) -> bool:
        return self._running
    
    def is_connected(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
    
    def set_property(self, prop_id: int, value: float) -> bool:
        if self._cap is None:
            return False
        
        result = self._cap.set(prop_id, value)
        actual_value = self._cap.get(prop_id)
        
        if abs(actual_value - value) > 1.0:
            logger.warning(f"Failed to set property {prop_id} to {value}, got {actual_value}")
            return False
        
        return True
    
    def get_property(self, prop_id: int) -> float:
        if self._cap is None:
            return 0.0
        return self._cap.get(prop_id)
    
    def save_frame(self, filename: str) -> bool:
        frame = self.get_frame()
        if frame is None:
            return False
        
        try:
            cv2.imwrite(filename, frame)
            logger.info(f"Frame saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save frame: {e}")
            return False
    
    def get_available_cameras(self) -> list[Tuple[int, str]]:
        cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                cameras.append((i, f"Camera {i}"))
                cap.release()
        return cameras
    
    def get_resolution(self) -> Tuple[int, int]:
        if self._cap is None:
            return (0, 0)
        return (
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        )
    
    def set_resolution(self, width: int, height: int) -> bool:
        if self._cap is None:
            return False
        
        success = (
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width) and
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        )
        
        if success:
            self.config.width = width
            self.config.height = height
            logger.info(f"Resolution set to {width}x{height}")
        
        return success
    
    def __del__(self):
        self.disconnect()
