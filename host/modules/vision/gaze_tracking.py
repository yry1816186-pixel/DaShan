import logging
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from .face_tracker import FaceData
from ..core.event_bus import EventBus, EventType, Event

logger = logging.getLogger(__name__)


@dataclass
class GazeData:
    x: float = 0.0
    y: float = 0.0
    confidence: float = 0.0
    timestamp: float = 0.0
    is_tracking: bool = False
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()


@dataclass
class GazeTrackerConfig:
    smoothing_factor: float = 0.3
    prediction_enabled: bool = True
    confidence_threshold: float = 0.3
    gaze_speed_limit: float = 100.0
    enable_blink_detection: bool = True
    blink_threshold: float = 0.5


class GazeTracker:
    def __init__(self, config: GazeTrackerConfig, event_bus: Optional[EventBus] = None):
        self.config = config
        self.event_bus = event_bus or EventBus.get_instance()
        self._current_gaze: Optional[GazeData] = None
        self._previous_gaze: Optional[GazeData] = None
        self._gaze_history = []
        self._max_history = 20
        self._blink_state = False
        self._last_blink_time = 0
        self._prediction: Optional[Tuple[float, float]] = None
        
        logger.info(f"GazeTracker initialized with config: {config}")
    
    def update_from_face(self, face: Optional[FaceData], frame_width: int, frame_height: int) -> Optional[GazeData]:
        if face is None or not face.is_tracking:
            self._current_gaze = None
            return None
        
        face_center_x = face.x + face.width / 2
        face_center_y = face.y + face.height / 2
        
        norm_x = (face_center_x - frame_width / 2) / (frame_width / 2)
        norm_y = (face_center_y - frame_height / 2) / (frame_height / 2)
        
        norm_x = max(-1.0, min(1.0, norm_x))
        norm_y = max(-1.0, min(1.0, norm_y))
        
        gaze = self._smooth_gaze(norm_x, norm_y, face.confidence)
        
        if gaze.confidence < self.config.confidence_threshold:
            logger.debug(f"Gaze confidence too low: {gaze.confidence:.2f}")
            return None
        
        self._current_gaze = gaze
        self._add_to_history(gaze)
        
        self._detect_blink(face)
        
        self.event_bus.publish(EventType.GAZE_UPDATED, {
            'x': gaze.x,
            'y': gaze.y,
            'confidence': gaze.confidence,
            'is_tracking': gaze.is_tracking
        }, source='GazeTracker')
        
        return gaze
    
    def _smooth_gaze(self, x: float, y: float, confidence: float) -> GazeData:
        import time
        
        if self._current_gaze is None:
            return GazeData(x=x, y=y, confidence=confidence, is_tracking=True)
        
        alpha = self.config.smoothing_factor * confidence
        
        if self.config.prediction_enabled and self._prediction is not None:
            pred_x, pred_y = self._prediction
            x = x * (1 - alpha * 0.5) + pred_x * alpha * 0.5
            y = y * (1 - alpha * 0.5) + pred_y * alpha * 0.5
        
        smoothed = GazeData(
            x=self._current_gaze.x * (1 - alpha) + x * alpha,
            y=self._current_gaze.y * (1 - alpha) + y * alpha,
            confidence=confidence,
            is_tracking=True
        )
        
        return smoothed
    
    def _add_to_history(self, gaze: GazeData):
        self._previous_gaze = self._current_gaze
        self._gaze_history.append(gaze)
        
        if len(self._gaze_history) > self._max_history:
            self._gaze_history.pop(0)
        
        if self.config.prediction_enabled and len(self._gaze_history) >= 3:
            self._update_prediction()
    
    def _update_prediction(self):
        recent = self._gaze_history[-3:]
        if len(recent) < 3:
            return
        
        dx1 = recent[1].x - recent[0].x
        dx2 = recent[2].x - recent[1].x
        dy1 = recent[1].y - recent[0].y
        dy2 = recent[2].y - recent[1].y
        
        pred_x = recent[2].x + dx2 + (dx2 - dx1)
        pred_y = recent[2].y + dy2 + (dy2 - dy1)
        
        pred_x = max(-1.0, min(1.0, pred_x))
        pred_y = max(-1.0, min(1.0, pred_y))
        
        self._prediction = (pred_x, pred_y)
    
    def _detect_blink(self, face: FaceData):
        if not self.config.enable_blink_detection:
            return
        
        import time
        now = time.time()
        
        if self._current_gaze is None or self._previous_gaze is None:
            return
        
        gaze_diff_x = abs(self._current_gaze.x - self._previous_gaze.x)
        gaze_diff_y = abs(self._current_gaze.y - self._previous_gaze.y)
        
        is_blink = (gaze_diff_x > self.config.blink_threshold or 
                    gaze_diff_y > self.config.blink_threshold)
        
        if is_blink and not self._blink_state:
            self._blink_state = True
            self._last_blink_time = now
            
            logger.debug("Blink detected")
        elif not is_blink and self._blink_state:
            self._blink_state = False
    
    def get_current_gaze(self) -> Optional[GazeData]:
        if self._current_gaze is None:
            return None
        
        return GazeData(
            x=self._current_gaze.x,
            y=self._current_gaze.y,
            confidence=self._current_gaze.confidence,
            is_tracking=True
        )
    
    def get_servo_angles(self, frame_width: int = 640, frame_height: int = 480) -> Optional[Tuple[int, int]]:
        gaze = self.get_current_gaze()
        if gaze is None:
            return None
        
        h_angle = int(90 + gaze.x * 45)
        v_angle = int(90 - gaze.y * 45)
        
        h_angle = max(30, min(150, h_angle))
        v_angle = max(30, min(150, v_angle))
        
        return (h_angle, v_angle)
    
    def is_tracking(self) -> bool:
        return self._current_gaze is not None and self._current_gaze.is_tracking
    
    def reset_tracking(self):
        self._current_gaze = None
        self._previous_gaze = None
        self._gaze_history.clear()
        self._prediction = None
        self._blink_state = False
        logger.info("Gaze tracking reset")
    
    def get_statistics(self) -> dict:
        if not self._gaze_history:
            return {
                'avg_x': 0,
                'avg_y': 0,
                'avg_confidence': 0,
                'tracking_stability': 0
            }
        
        x_values = [g.x for g in self._gaze_history]
        y_values = [g.y for g in self._gaze_history]
        conf_values = [g.confidence for g in self._gaze_history]
        
        std_x = np.std(x_values) if x_values else 0
        std_y = np.std(y_values) if y_values else 0
        
        stability = 1.0 - min(1.0, (std_x + std_y) / 2.0)
        
        return {
            'avg_x': np.mean(x_values) if x_values else 0,
            'avg_y': np.mean(y_values) if y_values else 0,
            'avg_confidence': np.mean(conf_values) if conf_values else 0,
            'std_x': std_x,
            'std_y': std_y,
            'tracking_stability': stability,
            'sample_count': len(self._gaze_history)
        }
    
    def set_config(self, config: GazeTrackerConfig):
        self.config = config
        logger.info(f"GazeTracker config updated")
    
    def get_prediction(self) -> Optional[Tuple[float, float]]:
        return self._prediction
    
    def get_last_blink_time(self) -> float:
        return self._last_blink_time
