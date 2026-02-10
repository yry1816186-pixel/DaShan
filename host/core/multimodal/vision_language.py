import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import numpy as np

from .clip_encoder import CLIPEncoder

logger = logging.getLogger(__name__)


@dataclass
class VQARequest:
    image: Any
    question: str
    options: List[str] = field(default_factory=list)
    max_tokens: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "options": self.options,
            "max_tokens": self.max_tokens
        }


@dataclass
class VQAResponse:
    answer: str
    confidence: float
    reasoning: Optional[str] = None
    options_scores: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "options_scores": self.options_scores
        }


class BaseVLLM(ABC):
    @abstractmethod
    def answer_question(self, request: VQARequest) -> VQAResponse:
        pass
    
    @abstractmethod
    def generate_caption(self, image: Any, max_length: int = 50) -> str:
        pass
    
    @abstractmethod
    def detect_objects(self, image: Any) -> List[Dict[str, Any]]:
        pass


class CLIPBasedVLLM(BaseVLLM):
    def __init__(self, clip_encoder: CLIPEncoder):
        self.clip = clip_encoder
        self._answer_templates: List[str] = []
        self._object_classes: List[str] = []
        
        logger.info("CLIPBasedVLLM initialized")
    
    def set_answer_templates(self, templates: List[str]):
        self._answer_templates = templates
        logger.info(f"Set {len(templates)} answer templates")
    
    def set_object_classes(self, classes: List[str]):
        self._object_classes = classes
        logger.info(f"Set {len(classes)} object classes")
    
    def answer_question(self, request: VQARequest) -> VQAResponse:
        if request.options:
            return self._answer_with_options(request)
        else:
            return self._answer_with_templates(request)
    
    def _answer_with_options(self, request: VQARequest) -> VQAResponse:
        question = request.question
        options = request.options if request.options else self._answer_templates
        
        if not options:
            options = ["yes", "no", "maybe"]
        
        scores = {}
        image_emb = self.clip.encode_image(request.image)
        
        for option in options:
            prompt = f"{question} {option}"
            text_emb = self.clip.encode_text(prompt)
            
            score = float(np.dot(image_emb, text_emb))
            scores[option] = score
        
        best_option = max(scores, key=scores.get)
        best_score = scores[best_option]
        
        total_score = sum(np.exp(list(scores.values())))
        confidence = np.exp(best_score) / total_score if total_score > 0 else 0
        
        return VQAResponse(
            answer=best_option,
            confidence=float(confidence),
            options_scores=scores
        )
    
    def _answer_with_templates(self, request: VQARequest) -> VQAResponse:
        templates = self._answer_templates
        
        if not templates:
            templates = [
                "yes",
                "no",
                "a photo of",
                "a drawing of",
                "I see"
            ]
        
        return self._answer_with_options(request)
    
    def generate_caption(self, image: Any, max_length: int = 50) -> str:
        captions = [
            "a photo of a",
            "a drawing of a",
            "a picture of a",
            "an image of a"
        ]
        
        image_emb = self.clip.encode_image(image)
        
        scores = []
        for caption in captions:
            text_emb = self.clip.encode_text(caption)
            score = float(np.dot(image_emb, text_emb))
            scores.append((caption, score))
        
        best_caption = max(scores, key=lambda x: x[1])[0]
        
        return best_caption
    
    def detect_objects(self, image: Any) -> List[Dict[str, Any]]:
        if not self._object_classes:
            return []
        
        image_emb = self.clip.encode_image(image)
        
        detections = []
        for obj_class in self._object_classes:
            prompt = f"a photo of a {obj_class}"
            text_emb = self.clip.encode_text(prompt)
            
            score = float(np.dot(image_emb, text_emb))
            
            if score > 0.2:
                detections.append({
                    "class": obj_class,
                    "confidence": score,
                    "bbox": None
                })
        
        detections.sort(key=lambda x: x["confidence"], reverse=True)
        
        return detections


class VisionLanguageModel:
    def __init__(
        self,
        clip_encoder: CLIPEncoder,
        llm_client: Any = None
    ):
        self.clip = clip_encoder
        self.vllm = CLIPBasedVLLM(clip_encoder)
        self.llm_client = llm_client
        self._caption_history: List[str] = []
        
        logger.info("VisionLanguageModel initialized")
    
    def answer_question(
        self,
        image: Any,
        question: str,
        options: List[str] = None
    ) -> VQAResponse:
        request = VQARequest(
            image=image,
            question=question,
            options=options or []
        )
        
        response = self.vllm.answer_question(request)
        
        if self.llm_client and response.confidence < 0.7:
            response = self._answer_with_llm(request, response)
        
        return response
    
    def _answer_with_llm(
        self,
        request: VQARequest,
        initial_response: VQAResponse
    ) -> VQAResponse:
        try:
            caption = self.generate_caption(request.image)
            
            prompt = f"""Based on the image caption: "{caption}"
Question: {request.question}
Initial answer: {initial_response.answer} (confidence: {initial_response.confidence:.2f})

Please provide a better answer if needed. Otherwise, confirm the initial answer."""
            
            llm_response = self.llm_client.generate(prompt)
            
            return VQAResponse(
                answer=llm_response.strip(),
                confidence=0.8,
                reasoning=f"LLM refined from: {initial_response.answer}"
            )
        
        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")
            return initial_response
    
    def generate_caption(
        self,
        image: Any,
        max_length: int = 50,
        use_llm: bool = False
    ) -> str:
        clip_caption = self.vllm.generate_caption(image, max_length)
        
        if use_llm and self.llm_client:
            try:
                prompt = f"Improve this image caption: {clip_caption}"
                llm_caption = self.llm_client.generate(prompt)
                return llm_caption.strip()
            except Exception as e:
                logger.error(f"LLM caption enhancement failed: {e}")
        
        return clip_caption
    
    def describe_scene(
        self,
        image: Any,
        detail_level: str = "medium"
    ) -> Dict[str, Any]:
        caption = self.generate_caption(image)
        
        objects = self.vllm.detect_objects(image)
        
        if detail_level == "high" and self.llm_client:
            try:
                prompt = f"Describe this scene in detail. Caption: {caption}. Objects detected: {[o['class'] for o in objects]}"
                detailed_description = self.llm_client.generate(prompt)
                
                return {
                    "caption": caption,
                    "detailed_description": detailed_description,
                    "objects": objects,
                    "detail_level": detail_level
                }
            except Exception as e:
                logger.error(f"Detailed description failed: {e}")
        
        return {
            "caption": caption,
            "objects": objects,
            "detail_level": detail_level
        }
    
    def compare_images(
        self,
        image1: Any,
        image2: Any
    ) -> Dict[str, Any]:
        emb1 = self.clip.encode_image(image1)
        emb2 = self.clip.encode_image(image2)
        
        similarity = float(np.dot(emb1, emb2))
        
        comparison = {
            "similarity": similarity,
            "distance": float(np.linalg.norm(emb1 - emb2))
        }
        
        if similarity > 0.9:
            comparison["relation"] = "very similar"
        elif similarity > 0.7:
            comparison["relation"] = "similar"
        elif similarity > 0.5:
            comparison["relation"] = "somewhat similar"
        elif similarity > 0.3:
            comparison["relation"] = "somewhat different"
        else:
            comparison["relation"] = "very different"
        
        return comparison
    
    def search_similar_images(
        self,
        query_image: Any,
        image_database: List[Any],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        return self.clip.rank_images_by_text(
            "similar image",
            [query_image] + image_database[1:],
            top_k=top_k
        )
    
    def set_answer_templates(self, templates: List[str]):
        self.vllm.set_answer_templates(templates)
    
    def set_object_classes(self, classes: List[str]):
        self.vllm.set_object_classes(classes)
    
    def set_llm_client(self, llm_client: Any):
        self.llm_client = llm_client
        logger.info("LLM client set for VisionLanguageModel")
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "clip_model": self.clip.config.model_name,
            "llm_available": self.llm_client is not None,
            "answer_templates": len(self.vllm._answer_templates),
            "object_classes": len(self.vllm._object_classes)
        }