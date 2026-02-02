import cv2
import numpy as np
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
from ..core.event_bus import EventBus, EventType, Event

logger = logging.getLogger(__name__)


@dataclass
class FaceData:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    confidence: float = 0.0
    timestamp: float = 0.0
    face_id: Optional[int] = None
    is_tracking: bool = False
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()


@dataclass
class FaceTrackerConfig:
    model_type: str = "hog"
    scale_factor: float = 1.1
    min_neighbors: int = 5
    min_size: Tuple[int, int] = (50, 50)
    max_size: Optional[Tuple[int, int]] = None
    confidence_threshold: float = 0.5
    smoothing_factor: float = 0.3
    tracking_timeout: float = 2.0
    enable_landmarks: bool = True


class FaceTracker:
    def __init__(self, config: FaceTrackerConfig, event_bus: Optional[EventBus] = None):
        self.config = config
        self.event_bus = event_bus or EventBus.get_instance()
        self._face_cascade = None
        self._current_face: Optional[FaceData] = None
        self._face_history: List[FaceData] = []
        self._max_history = 10
        self._is_initialized = False
        
        logger.info(f"FaceTracker initialized with config: {config}")
    
    def initialize(self) -> bool:
        try:
            if self.config.model_type == "hog":
                self._face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                logger.info("HOG face detector loaded")
            elif self.config.model_type == "lbp":
                self._face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_alt.xml'
                )
                logger.info("LBP face detector loaded")
            else:
                logger.error(f"Unknown model type: {self.config.model_type}")
                return False
            
            self._is_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            return False
    
    def detect_faces(self, frame: np.ndarray) -> List[FaceData]:
        if not self._is_initialized or self._face_cascade is None:
            logger.warning("Face tracker not initialized")
            return []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        
        faces = self._face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.config.scale_factor,
            minNeighbors=self.config.min_neighbors,
            minSize=self.config.min_size,
            maxSize=self.config.max_size
        )
        
        face_data_list = []
        
        for (x, y, w, h) in faces:
            face = FaceData(
                x=float(x),
                y=float(y),
                width=float(w),
                height=float(h),
                confidence=1.0,
                is_tracking=True
            )
            face_data_list.append(face)
        
        if face_data_list:
            best_face = self._select_best_face(face_data_list)
            smoothed_face = self._smooth_face(best_face)
            
            self._current_face = smoothed_face
            self._add_to_history(smoothed_face)
            
            self.event_bus.publish(EventType.FACE_DETECTED, {
                'face_count': len(face_data_list),
                'primary_face': smoothed_face,
                'faces': [self._face_to_dict(f) for f in face_data_list]
            }, source='FaceTracker')
        
        return face_data_list
    
    def _select_best_face(self, faces: List[FaceData]) -> FaceData:
        if not faces:
            return None
        
        if len(faces) == 1:
            return faces[0]
        
        if self._current_face is not None:
            import time
            now = time.time()
            
            valid_faces = [f for f in faces if self._is_near_current_face(f)]
            
            if valid_faces:
                closest = min(valid_faces, key=lambda f: self._distance_to_current_face(f))
                return closest
        
        return max(faces, key=lambda f: f.width * f.height)
    
    def _is_near_current_face(self, face: FaceData) -> bool:
        if self._current_face is None:
            return True
        
        dx = face.x - self._current_face.x
        dy = face.y - self._current_face.y
        
        threshold = max(face.width, face.height) * 0.5
        
        return abs(dx) < threshold and abs(dy) < threshold
    
    def _distance_to_current_face(self, face: FaceData) -> float:
        if self._current_face is None:
            return float('inf')
        
        dx = face.x - self._current_face.x
        dy = face.y - self._current_face.y
        return (dx ** 2 + dy ** 2) ** 0.5
    
    def _smooth_face(self, new_face: FaceData) -> FaceData:
        if self._current_face is None:
            return new_face
        
        alpha = self.config.smoothing_factor
        
        smoothed = FaceData(
            x=self._current_face.x * (1 - alpha) + new_face.x * alpha,
            y=self._current_face.y * (1 - alpha) + new_face.y * alpha,
            width=self._current_face.width * (1 - alpha) + new_face.width * alpha,
            height=self._current_face.height * (1 - alpha) + new_face.height * alpha,
            confidence=new_face.confidence,
            is_tracking=True
        )
        
        return smoothed
    
    def _add_to_history(self, face: FaceData):
        self._face_history.append(face)
        if len(self._face_history) > self._max_history:
            self._face_history.pop(0)
    
    def get_current_face(self) -> Optional[FaceData]:
        if self._is_tracking_expired():
            self._current_face = None
            self._face_history.clear()
        
        return self._current_face
    
    def _is_tracking_expired(self) -> bool:
        if self._current_face is None:
            return False
        
        import time
        return time.time() - self._current_face.timestamp > self.config.tracking_timeout
    
    def get_face_center(self) -> Optional[Tuple[float, float]]:
        face = self.get_current_face()
        if face is None:
            return None
        
        return (face.x + face.width / 2, face.y + face.height / 2)
    
    def get_normalized_gaze(self, frame_width: int, frame_height: int) -> Optional[Tuple[float, float]]:
        center = self.get_face_center()
        if center is None:
            return None
        
        x_norm = (center[0] - frame_width / 2) / (frame_width / 2)
        y_norm = (center[1] - frame_height / 2) / (frame_height / 2)
        
        x_norm = max(-1.0, min(1.0, x_norm))
        y_norm = max(-1.0, min(1.0, y_norm))
        
        return (x_norm, y_norm)
    
    def reset_tracking(self):
        self._current_face = None
        self._face_history.clear()
        logger.info("Face tracking reset")
    
    def is_tracking(self) -> bool:
        return self._current_face is not None and not self._is_tracking_expired()
    
    def draw_faces(self, frame: np.ndarray, faces: List[FaceData]) -> np.ndarray:
        output = frame.copy()
        
        for i, face in enumerate(faces):
            color = (0, 255, 0) if i == 0 else (0, 0, 255)
            thickness = 3 if i == 0 else 1
            
            cv2.rectangle(
                output,
                (int(face.x), int(face.y)),
                (int(face.x + face.width), int(face.y + face.height)),
                color,
                thickness
            )
            
            center_x = int(face.x + face.width / 2)
            center_y = int(face.y + face.height / 2)
            cv2.circle(output, (center_x, center_y), 3, (255, 255, 255), -1)
            
            if self.config.enable_landmarks:
                self._draw_landmarks(output, face)
        
        return output
    
    def _draw_landmarks(self, frame: np.ndarray, face: FaceData):
        eye_y = int(face.y + face.height * 0.4)
        eye_width = int(face.width * 0.3)
        
        left_eye_x = int(face.x + face.width * 0.3)
        right_eye_x = int(face.x + face.width * 0.7)
        
        cv2.circle(frame, (left_eye_x, eye_y), int(eye_width / 4), (255, 0, 0), 2)
        cv2.circle(frame, (right_eye_x, eye_y), int(eye_width / 4), (255, 0, 0), 2)
    
    @staticmethod
    def _face_to_dict(face: FaceData) -> dict:
        return {
            'x': face.x,
            'y': face.y,
            'width': face.width,
            'height': face.height,
            'confidence': face.confidence,
            'timestamp': face.timestamp
        }
    
    def get_statistics(self) -> dict:
        if not self._face_history:
            return {
                'avg_width': 0,
                'avg_height': 0,
                'detection_rate': 0,
                'total_detections': 0
            }
        
        widths = [f.width for f in self._face_history]
        heights = [f.height for f in self._face_history]
        
        return {
            'avg_width': np.mean(widths),
            'avg_height': np.mean(heights),
            'std_width': np.std(widths),
            'std_height': np.std(heights),
            'detection_count': len(self._face_history),
            'tracking_duration': self._current_face.timestamp - self._face_history[0].timestamp if self._face_history else 0
        }
    
    def set_config(self, config: FaceTrackerConfig):
        self.config = config
        logger.info(f"FaceTracker config updated")
    
    def __del__(self):
        self.reset_tracking()
