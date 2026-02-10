import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from abc import ABC, abstractmethod

from .clip_encoder import CLIPEncoder, CLIPModelConfig

logger = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    fusion_method: str = "concat"
    text_weight: float = 0.5
    image_weight: float = 0.3
    audio_weight: float = 0.2
    normalize: bool = True
    output_dim: Optional[int] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FusionConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class MultimodalInput:
    text: Optional[str] = None
    text_embedding: Optional[np.ndarray] = None
    image: Optional[Any] = None
    image_embedding: Optional[np.ndarray] = None
    audio: Optional[np.ndarray] = None
    audio_embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_text(self) -> bool:
        return self.text is not None or self.text_embedding is not None
    
    def has_image(self) -> bool:
        return self.image is not None or self.image_embedding is not None
    
    def has_audio(self) -> bool:
        return self.audio is not None or self.audio_embedding is not None
    
    def get_available_modalities(self) -> List[str]:
        modalities = []
        if self.has_text(): modalities.append("text")
        if self.has_image(): modalities.append("image")
        if self.has_audio(): modalities.append("audio")
        return modalities


class BaseFusionMethod(ABC):
    @abstractmethod
    def fuse(self, inputs: Dict[str, np.ndarray], config: FusionConfig) -> np.ndarray:
        pass
    
    @abstractmethod
    def get_output_dim(self, input_dims: Dict[str, int], config: FusionConfig) -> int:
        pass


class ConcatFusion(BaseFusionMethod):
    def fuse(self, inputs: Dict[str, np.ndarray], config: FusionConfig) -> np.ndarray:
        embeddings = []
        
        for modality, emb in inputs.items():
            if config.normalize:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
            embeddings.append(emb)
        
        fused = np.concatenate(embeddings)
        return fused
    
    def get_output_dim(self, input_dims: Dict[str, int], config: FusionConfig) -> int:
        return sum(input_dims.values())


class WeightedSumFusion(BaseFusionMethod):
    def fuse(self, inputs: Dict[str, np.ndarray], config: FusionConfig) -> np.ndarray:
        if len(inputs) == 1:
            emb = list(inputs.values())[0]
            return emb / np.linalg.norm(emb) if config.normalize else emb
        
        weights = {
            "text": config.text_weight,
            "image": config.image_weight,
            "audio": config.audio_weight
        }
        
        available_weights = [weights.get(m, 0.1) for m in inputs.keys()]
        total_weight = sum(available_weights)
        available_weights = [w / total_weight for w in available_weights]
        
        normalized_embs = []
        for emb in inputs.values():
            if config.normalize:
                norm = np.linalg.norm(emb)
                emb = emb / norm if norm > 0 else emb
            normalized_embs.append(emb)
        
        fused = sum(w * e for w, e in zip(available_weights, normalized_embs))
        
        if config.normalize:
            fused = fused / np.linalg.norm(fused)
        
        return fused
    
    def get_output_dim(self, input_dims: Dict[str, int], config: FusionConfig) -> int:
        return list(input_dims.values())[0] if input_dims else 0


class AttentionFusion(BaseFusionMethod):
    def __init__(self, hidden_dim: int = 256):
        self.hidden_dim = hidden_dim
        self._attention_weights: Optional[np.ndarray] = None
    
    def fuse(self, inputs: Dict[str, np.ndarray], config: FusionConfig) -> np.ndarray:
        modalities = list(inputs.values())
        
        if len(modalities) == 1:
            emb = modalities[0]
            return emb / np.linalg.norm(emb) if config.normalize else emb
        
        dims = [emb.shape[0] for emb in modalities]
        max_dim = max(dims)
        
        padded_embs = []
        for emb in modalities:
            if emb.shape[0] < max_dim:
                padded = np.pad(emb, (0, max_dim - emb.shape[0]), 'constant')
            else:
                padded = emb[:max_dim]
            padded_embs.append(padded)
        
        stacked = np.stack(padded_embs)
        
        attention_scores = np.mean(stacked, axis=1)
        attention_weights = np.exp(attention_scores) / np.sum(np.exp(attention_scores))
        
        self._attention_weights = attention_weights
        
        fused = np.sum(attention_weights[:, None] * stacked, axis=0)
        
        if config.normalize:
            fused = fused / np.linalg.norm(fused)
        
        return fused
    
    def get_attention_weights(self) -> Optional[np.ndarray]:
        return self._attention_weights
    
    def get_output_dim(self, input_dims: Dict[str, int], config: FusionConfig) -> int:
        return max(input_dims.values()) if input_dims else 0


class CrossModalAttentionFusion(BaseFusionMethod):
    def __init__(self, projection_dim: int = 256):
        self.projection_dim = projection_dim
        self._projection_matrices: Dict[str, np.ndarray] = {}
        self._attention_matrix: Optional[np.ndarray] = None
    
    def fuse(self, inputs: Dict[str, np.ndarray], config: FusionConfig) -> np.ndarray:
        if len(inputs) == 1:
            emb = list(inputs.values())[0]
            return emb / np.linalg.norm(emb) if config.normalize else emb
        
        projected = {}
        for modality, emb in inputs.items():
            if modality not in self._projection_matrices:
                input_dim = emb.shape[0]
                proj_matrix = np.random.randn(input_dim, self.projection_dim) * 0.1
                self._projection_matrices[modality] = proj_matrix
            
            proj_matrix = self._projection_matrices[modality]
            projected[modality] = np.dot(emb, proj_matrix)
        
        modalities = list(projected.keys())
        
        attention_scores = np.zeros((len(modalities), len(modalities)))
        for i, mod1 in enumerate(modalities):
            for j, mod2 in enumerate(modalities):
                if i != j:
                    sim = np.dot(projected[mod1], projected[mod2])
                    attention_scores[i, j] = sim
        
        self._attention_matrix = attention_scores
        
        fused = np.mean(list(projected.values()), axis=0)
        
        if config.normalize:
            fused = fused / np.linalg.norm(fused)
        
        return fused
    
    def get_output_dim(self, input_dims: Dict[str, int], config: FusionConfig) -> int:
        return self.projection_dim
    
    def get_cross_attention_matrix(self) -> Optional[np.ndarray]:
        return self._attention_matrix


class MultimodalFusionEngine:
    def __init__(
        self,
        clip_encoder: CLIPEncoder,
        config: FusionConfig = None
    ):
        self.clip = clip_encoder
        self.config = config or FusionConfig()
        
        self._fusion_methods = {
            "concat": ConcatFusion(),
            "weighted_sum": WeightedSumFusion(),
            "attention": AttentionFusion(),
            "cross_attention": CrossModalAttentionFusion()
        }
        
        self._current_fusion = self._fusion_methods.get(
            self.config.fusion_method,
            WeightedSumFusion()
        )
        
        self._audio_encoder: Optional[Any] = None
        
        logger.info(f"MultimodalFusionEngine initialized (method={self.config.fusion_method})")
    
    def set_fusion_method(self, method: str):
        if method not in self._fusion_methods:
            raise ValueError(f"Unknown fusion method: {method}")
        
        self.config.fusion_method = method
        self._current_fusion = self._fusion_methods[method]
        logger.info(f"Fusion method changed to: {method}")
    
    def set_audio_encoder(self, encoder):
        self._audio_encoder = encoder
        logger.info("Audio encoder set")
    
    def encode_input(
        self,
        input_data: MultimodalInput
    ) -> Dict[str, np.ndarray]:
        embeddings = {}
        
        if input_data.has_text():
            if input_data.text_embedding is not None:
                embeddings["text"] = input_data.text_embedding
            elif input_data.text:
                embeddings["text"] = self.clip.encode_text(input_data.text)
        
        if input_data.has_image():
            if input_data.image_embedding is not None:
                embeddings["image"] = input_data.image_embedding
            elif input_data.image:
                embeddings["image"] = self.clip.encode_image(input_data.image)
        
        if input_data.has_audio():
            if input_data.audio_embedding is not None:
                embeddings["audio"] = input_data.audio_embedding
            elif input_data.audio is not None and self._audio_encoder:
                embeddings["audio"] = self._audio_encoder(input_data.audio)
        
        return embeddings
    
    def fuse(
        self,
        input_data: MultimodalInput,
        method: Optional[str] = None
    ) -> np.ndarray:
        embeddings = self.encode_input(input_data)
        
        if not embeddings:
            raise ValueError("No valid input data provided")
        
        if method:
            fusion = self._fusion_methods.get(method, self._current_fusion)
        else:
            fusion = self._current_fusion
        
        fused_embedding = fusion.fuse(embeddings, self.config)
        
        return fused_embedding
    
    def fuse_batch(
        self,
        input_batch: List[MultimodalInput],
        method: Optional[str] = None
    ) -> np.ndarray:
        fused_embeddings = []
        
        for input_data in input_batch:
            fused = self.fuse(input_data, method)
            fused_embeddings.append(fused)
        
        return np.array(fused_embeddings)
    
    def compute_cross_modal_similarity(
        self,
        input1: MultimodalInput,
        input2: MultimodalInput
    ) -> float:
        emb1 = self.fuse(input1)
        emb2 = self.fuse(input2)
        
        similarity = np.dot(emb1, emb2)
        
        return float(similarity)
    
    def retrieve_by_text(
        self,
        query_text: str,
        candidates: List[MultimodalInput],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        query_input = MultimodalInput(text=query_text)
        query_emb = self.fuse(query_input)
        
        similarities = []
        
        for i, candidate in enumerate(candidates):
            cand_emb = self.fuse(candidate)
            sim = np.dot(query_emb, cand_emb)
            similarities.append((i, float(sim)))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def retrieve_by_image(
        self,
        query_image: Any,
        candidates: List[MultimodalInput],
        top_k: int = 5
    ) -> List[Tuple[int, float]]:
        query_input = MultimodalInput(image=query_image)
        query_emb = self.fuse(query_input)
        
        similarities = []
        
        for i, candidate in enumerate(candidates):
            cand_emb = self.fuse(candidate)
            sim = np.dot(query_emb, cand_emb)
            similarities.append((i, float(sim)))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def get_fusion_info(self) -> Dict[str, Any]:
        return {
            "method": self.config.fusion_method,
            "available_methods": list(self._fusion_methods.keys()),
            "config": {
                "text_weight": self.config.text_weight,
                "image_weight": self.config.image_weight,
                "audio_weight": self.config.audio_weight,
                "normalize": self.config.normalize
            },
            "audio_encoder_available": self._audio_encoder is not None
        }
    
    def get_attention_weights(self) -> Optional[np.ndarray]:
        if hasattr(self._current_fusion, 'get_attention_weights'):
            return self._current_fusion.get_attention_weights()
        return None
    
    def get_cross_attention_matrix(self) -> Optional[np.ndarray]:
        if hasattr(self._current_fusion, 'get_cross_attention_matrix'):
            return self._current_fusion.get_cross_attention_matrix()
        return None