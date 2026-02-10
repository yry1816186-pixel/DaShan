import logging
from typing import List, Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
from PIL import Image
import io

logger = logging.getLogger(__name__)


@dataclass
class CLIPModelConfig:
    model_name: str = "openai/clip-vit-base-patch32"
    device: str = "auto"
    cache_dir: Optional[str] = None
    image_size: int = 224
    text_max_length: int = 77
    normalize: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CLIPModelConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class CLIPEncoder:
    def __init__(self, config: CLIPModelConfig = None):
        self.config = config or CLIPModelConfig()
        self._model = None
        self._processor = None
        self._embedding_dim = 512
        
        self._load_model()
        
        logger.info(f"CLIPEncoder initialized (model={self.config.model_name})")
    
    def _load_model(self):
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch
            
            device = self.config.device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            
            logger.info(f"Loading CLIP model on {device}...")
            
            self._model = CLIPModel.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.cache_dir
            ).to(device)
            
            self._processor = CLIPProcessor.from_pretrained(
                self.config.model_name,
                cache_dir=self.config.cache_dir
            )
            
            self._device = device
            self._model.eval()
            
            logger.info(f"CLIP model loaded successfully")
        
        except ImportError:
            logger.error("transformers not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise
    
    def encode_text(
        self,
        text: Union[str, List[str]],
        normalize: bool = None
    ) -> np.ndarray:
        if normalize is None:
            normalize = self.config.normalize
        
        texts = [text] if isinstance(text, str) else text
        
        try:
            inputs = self._processor(
                text=texts,
                padding=True,
                truncation=True,
                max_length=self.config.text_max_length,
                return_tensors="pt"
            ).to(self._device)
            
            with torch.no_grad():
                text_features = self._model.get_text_features(**inputs)
            
            if normalize:
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            embeddings = text_features.cpu().numpy()
            
            if isinstance(text, str):
                return embeddings[0]
            
            return embeddings
        
        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            raise
    
    def encode_image(
        self,
        image: Union[str, Path, Image.Image, bytes, np.ndarray],
        normalize: bool = None
    ) -> np.ndarray:
        if normalize is None:
            normalize = self.config.normalize
        
        try:
            if isinstance(image, (str, Path)):
                pil_image = Image.open(image)
            elif isinstance(image, bytes):
                pil_image = Image.open(io.BytesIO(image))
            elif isinstance(image, np.ndarray):
                if image.dtype == np.uint8:
                    pil_image = Image.fromarray(image)
                else:
                    image = (image * 255).astype(np.uint8)
                    pil_image = Image.fromarray(image)
            elif isinstance(image, Image.Image):
                pil_image = image
            else:
                raise TypeError(f"Unsupported image type: {type(image)}")
            
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            if pil_image.size[0] != self.config.image_size or pil_image.size[1] != self.config.image_size:
                pil_image = pil_image.resize((self.config.image_size, self.config.image_size))
            
            inputs = self._processor(
                images=pil_image,
                return_tensors="pt"
            ).to(self._device)
            
            with torch.no_grad():
                image_features = self._model.get_image_features(**inputs)
            
            if normalize:
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            embedding = image_features.cpu().numpy()[0]
            
            return embedding
        
        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            raise
    
    def encode_image_batch(
        self,
        images: List[Union[str, Path, Image.Image, bytes, np.ndarray]],
        normalize: bool = None
    ) -> np.ndarray:
        if normalize is None:
            normalize = self.config.normalize
        
        embeddings = []
        
        for image in images:
            emb = self.encode_image(image, normalize)
            embeddings.append(emb)
        
        return np.array(embeddings)
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        metric: str = "cosine"
    ) -> float:
        if metric == "cosine":
            return float(np.dot(embedding1, embedding2))
        elif metric == "euclidean":
            return float(-np.linalg.norm(embedding1 - embedding2))
        elif metric == "dot":
            return float(np.dot(embedding1, embedding2))
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def compute_text_image_similarity(
        self,
        text: str,
        image: Union[str, Path, Image.Image, bytes, np.ndarray]
    ) -> float:
        text_emb = self.encode_text(text)
        image_emb = self.encode_image(image)
        
        return self.compute_similarity(text_emb, image_emb)
    
    def rank_images_by_text(
        self,
        query_text: str,
        images: List[Union[str, Path, Image.Image, bytes, np.ndarray]],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        text_emb = self.encode_text(query_text)
        
        similarities = []
        
        for i, image in enumerate(images):
            image_emb = self.encode_image(image)
            sim = self.compute_similarity(text_emb, image_emb)
            similarities.append((i, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def rank_texts_by_image(
        self,
        query_image: Union[str, Path, Image.Image, bytes, np.ndarray],
        texts: List[str],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        image_emb = self.encode_image(query_image)
        
        similarities = []
        
        for i, text in enumerate(texts):
            text_emb = self.encode_text(text)
            sim = self.compute_similarity(image_emb, text_emb)
            similarities.append((i, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim
    
    def save_model(self, path: str):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            
            self._model.save_pretrained(path)
            self._processor.save_pretrained(path)
            
            logger.info(f"Model saved to: {path}")
        
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.config.model_name,
            "device": self._device,
            "embedding_dim": self._embedding_dim,
            "image_size": self.config.image_size,
            "text_max_length": self.config.text_max_length,
            "normalize": self.config.normalize
        }


class ZeroShotClassifier:
    def __init__(self, clip_encoder: CLIPEncoder):
        self.clip = clip_encoder
        self._labels: List[str] = []
        self._label_embeddings: np.ndarray = None
    
    def set_labels(self, labels: List[str]):
        self._labels = labels
        self._label_embeddings = self.clip.encode_text(labels)
        logger.info(f"Zero-shot classifier initialized with {len(labels)} labels")
    
    def classify(
        self,
        image: Union[str, Path, Image.Image, bytes, np.ndarray],
        top_k: int = 1
    ) -> List[Tuple[str, float]]:
        if self._label_embeddings is None:
            raise RuntimeError("Labels not set. Call set_labels() first.")
        
        image_emb = self.clip.encode_image(image)
        
        similarities = np.dot(self._label_embeddings, image_emb)
        
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = [
            (self._labels[i], float(similarities[i]))
            for i in top_indices
        ]
        
        return results
    
    def classify_batch(
        self,
        images: List[Union[str, Path, Image.Image, bytes, np.ndarray]],
        top_k: int = 1
    ) -> List[List[Tuple[str, float]]]:
        return [self.classify(img, top_k) for img in images]
