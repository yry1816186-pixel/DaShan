import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum
import numpy as np
from PIL import Image
import io

logger = logging.getLogger(__name__)


class EmotionType(IntEnum):
    NEUTRAL = 0
    HAPPY = 1
    SAD = 2
    ANGRY = 3
    SURPRISED = 4
    FEAR = 5
    DISGUST = 6
    CONTEMPT = 7


@dataclass
class EmotionResult:
    emotion: EmotionType
    emotion_name: str
    confidence: float
    all_scores: Dict[str, float]
    bounding_box: Optional[Tuple[int, int, int, int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "emotion": self.emotion_name,
            "confidence": self.confidence,
            "all_scores": self.all_scores,
            "bounding_box": self.bounding_box
        }


class EmotionRecognizer:
    def __init__(
        self,
        model_name: str = "deepface",
        backend: str = "opencv",
        device: str = "cpu"
    ):
        self.model_name = model_name
        self.backend = backend
        self.device = device
        self._model = None
        self._loaded = False
        
        self.emotion_map = {
            "neutral": EmotionType.NEUTRAL,
            "happy": EmotionType.HAPPY,
            "sad": EmotionType.SAD,
            "angry": EmotionType.ANGRY,
            "surprise": EmotionType.SURPRISED,
            "fear": EmotionType.FEAR,
            "disgust": EmotionType.DISGUST
        }
        
        self._load_model()
        
        logger.info(f"EmotionRecognizer initialized (model={model_name})")
    
    def _load_model(self):
        try:
            if self.model_name == "deepface":
                self._load_deepface()
            elif self.model_name == "face_recognition":
                self._load_face_recognition()
            else:
                logger.warning(f"Unknown model: {self.model_name}, using simple fallback")
                self._load_fallback()
        except Exception as e:
            logger.error(f"Failed to load emotion model: {e}")
            self._load_fallback()
    
    def _load_deepface(self):
        try:
            from deepface import DeepFace
            
            self._model = DeepFace
            self._loaded = True
            logger.info("DeepFace loaded successfully")
        except ImportError:
            logger.warning("deepface not installed, using fallback")
            self._load_fallback()
    
    def _load_face_recognition(self):
        try:
            import face_recognition
            
            self._model = face_recognition
            self._loaded = True
            logger.info("face_recognition loaded successfully")
        except ImportError:
            logger.warning("face_recognition not installed, using fallback")
            self._load_fallback()
    
    def _load_fallback(self):
        self._loaded = True
        logger.info("Using fallback emotion recognizer")
    
    def recognize(
        self,
        image: Any,
        detect_multiple: bool = False
    ) -> List[EmotionResult]:
        if not self._loaded:
            return []
        
        try:
            pil_image = self._prepare_image(image)
            
            if self.model_name == "deepface" and self._model:
                return self._recognize_deepface(pil_image, detect_multiple)
            elif self.model_name == "face_recognition" and self._model:
                return self._recognize_face_recognition(pil_image, detect_multiple)
            else:
                return self._recognize_fallback(pil_image)
        
        except Exception as e:
            logger.error(f"Emotion recognition failed: {e}")
            return []
    
    def _prepare_image(self, image: Any) -> Image.Image:
        if isinstance(image, str):
            return Image.open(image)
        elif isinstance(image, bytes):
            return Image.open(io.BytesIO(image))
        elif isinstance(image, np.ndarray):
            if image.dtype == np.uint8:
                return Image.fromarray(image)
            else:
                return Image.fromarray((image * 255).astype(np.uint8))
        elif isinstance(image, Image.Image):
            return image
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")
    
    def _recognize_deepface(
        self,
        image: Image.Image,
        detect_multiple: bool
    ) -> List[EmotionResult]:
        results = []
        
        try:
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                image.save(tmp, format="JPEG")
                tmp_path = tmp.name
            
            try:
                detections = self._model.analyze(
                    tmp_path,
                    actions=['emotion'],
                    enforce_detection=False,
                    detector_backend=self.backend
                )
                
                if not isinstance(detections, list):
                    detections = [detections]
                
                for det in detections:
                    emotion_scores = det.get('emotion', {})
                    dominant_emotion = max(emotion_scores, key=emotion_scores.get)
                    confidence = emotion_scores[dominant_emotion]
                    
                    region = det.get('region')
                    bbox = None
                    if region:
                        bbox = (
                            region.get('x', 0),
                            region.get('y', 0),
                            region.get('w', 0),
                            region.get('h', 0)
                        )
                    
                    emotion_type = self.emotion_map.get(dominant_emotion, EmotionType.NEUTRAL)
                    
                    results.append(EmotionResult(
                        emotion=emotion_type,
                        emotion_name=dominant_emotion,
                        confidence=confidence,
                        all_scores=emotion_scores,
                        bounding_box=bbox
                    ))
            
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        
        except Exception as e:
            logger.error(f"DeepFace recognition failed: {e}")
        
        return results[:1] if not detect_multiple else results
    
    def _recognize_face_recognition(
        self,
        image: Image.Image,
        detect_multiple: bool
    ) -> List[EmotionResult]:
        results = []
        
        try:
            img_array = np.array(image)
            
            face_locations = self._model.face_locations(img_array, number_of_times_to_upsample=0)
            
            for location in face_locations[:1] if not detect_multiple else face_locations:
                top, right, bottom, left = location
                face_image = img_array[top:bottom, left:right]
                
                emotions = self._analyze_face_features(face_image)
                
                dominant_emotion = max(emotions, key=emotions.get)
                confidence = emotions[dominant_emotion]
                
                emotion_type = self.emotion_map.get(dominant_emotion, EmotionType.NEUTRAL)
                
                results.append(EmotionResult(
                    emotion=emotion_type,
                    emotion_name=dominant_emotion,
                    confidence=confidence,
                    all_scores=emotions,
                    bounding_box=(left, top, right - left, bottom - top)
                ))
        
        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
        
        return results
    
    def _analyze_face_features(self, face_image: np.ndarray) -> Dict[str, float]:
        emotions = {
            "neutral": 0.6,
            "happy": 0.1,
            "sad": 0.1,
            "angry": 0.05,
            "surprise": 0.05,
            "fear": 0.05,
            "disgust": 0.05
        }
        
        try:
            gray = np.mean(face_image, axis=2) if len(face_image.shape) == 3 else face_image
            brightness = np.mean(gray)
            
            mouth_height = gray.shape[0] // 3
            mouth_region = gray[-mouth_height:]
            mouth_std = np.std(mouth_region)
            
            if mouth_std > 30:
                emotions["happy"] = 0.4
                emotions["neutral"] = 0.2
            elif brightness < 100:
                emotions["sad"] = 0.3
                emotions["neutral"] = 0.3
            
            variance = np.var(gray)
            if variance > 1000:
                emotions["surprise"] = 0.2
            
            total = sum(emotions.values())
            for k in emotions:
                emotions[k] /= total
        
        except Exception as e:
            logger.error(f"Feature analysis failed: {e}")
        
        return emotions
    
    def _recognize_fallback(self, image: Image.Image) -> List[EmotionResult]:
        emotions = {
            "neutral": 0.8,
            "happy": 0.1,
            "sad": 0.05,
            "angry": 0.05
        }
        
        dominant_emotion = "neutral"
        confidence = emotions["neutral"]
        
        return [EmotionResult(
            emotion=EmotionType.NEUTRAL,
            emotion_name=dominant_emotion,
            confidence=confidence,
            all_scores=emotions
        )]
    
    def recognize_batch(
        self,
        images: List[Any],
        detect_multiple: bool = False
    ) -> List[List[EmotionResult]]:
        results = []
        for image in images:
            result = self.recognize(image, detect_multiple)
            results.append(result)
        return results
    
    def get_emotion_from_expression_id(
        self,
        expression_id: int
    ) -> EmotionType:
        expression_map = {
            0: EmotionType.NEUTRAL,
            1: EmotionType.HAPPY,
            2: EmotionType.SAD,
            3: EmotionType.SURPRISED,
            4: EmotionType.ANGRY,
            5: EmotionType.FEAR,
            6: EmotionType.NEUTRAL
        }
        return expression_map.get(expression_id, EmotionType.NEUTRAL)
    
    def expression_id_to_emotion(self, expression_id: int) -> str:
        emotion_type = self.get_emotion_from_expression_id(expression_id)
        return emotion_type.name.lower()
    
    def emotion_to_expression_id(self, emotion: str) -> int:
        emotion_map = {
            "neutral": 0,
            "happy": 1,
            "sad": 2,
            "surprised": 3,
            "angry": 4,
            "fear": 5
        }
        return emotion_map.get(emotion.lower(), 0)
    
    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "backend": self.backend,
            "device": self.device,
            "loaded": self._loaded,
            "supported_emotions": list(self.emotion_map.keys())
        }