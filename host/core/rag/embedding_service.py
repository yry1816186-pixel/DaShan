import logging
from typing import List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(
        self,
        model_name: str = "shibing624/text2vec-base-chinese",
        device: Optional[str] = None,
        batch_size: int = 32,
        cache_dir: Optional[str] = None
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Loading embedding model: {model_name} on {device}")
        
        self.device = device
        self.model = SentenceTransformer(
            model_name,
            device=device,
            cache_folder=cache_dir
        )
        
        self._embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded (dim={self._embedding_dim})")
    
    def embed_text(
        self,
        text: Union[str, List[str]],
        normalize: bool = True
    ) -> Union[np.ndarray, List[np.ndarray]]:
        is_single = isinstance(text, str)
        
        if is_single:
            text = [text]
        
        embeddings = self.model.encode(
            text,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=normalize
        )
        
        if is_single:
            return embeddings[0]
        
        return embeddings
    
    def embed_batch(
        self,
        texts: List[str],
        batch_size: Optional[int] = None,
        show_progress: bool = False
    ) -> np.ndarray:
        batch_size = batch_size or self.batch_size
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        return embeddings
    
    def similarity(
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
            raise ValueError(f"Unknown similarity metric: {metric}")
    
    def compute_similarities(
        self,
        query_embedding: np.ndarray,
        document_embeddings: np.ndarray,
        metric: str = "cosine"
    ) -> np.ndarray:
        if metric == "cosine":
            similarities = np.dot(document_embeddings, query_embedding)
        elif metric == "euclidean":
            similarities = -np.linalg.norm(document_embeddings - query_embedding, axis=1)
        elif metric == "dot":
            similarities = np.dot(document_embeddings, query_embedding)
        else:
            raise ValueError(f"Unknown similarity metric: {metric}")
        
        return similarities
    
    def find_top_k(
        self,
        query_embedding: np.ndarray,
        document_embeddings: np.ndarray,
        k: int = 5,
        metric: str = "cosine"
    ) -> tuple[np.ndarray, np.ndarray]:
        similarities = self.compute_similarities(query_embedding, document_embeddings, metric)
        top_indices = np.argsort(similarities)[-k:][::-1]
        
        return top_indices, similarities[top_indices]
    
    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim
    
    def save_model(self, path: str):
        self.model.save(path)
        logger.info(f"Model saved to: {path}")
    
    def load_model(self, path: str):
        self.model = SentenceTransformer(path, device=self.device)
        self._embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded from: {path}")
    
    @staticmethod
    def normalize(embedding: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm


class MultimodalEmbeddingService:
    def __init__(
        self,
        text_model: str = "shibing624/text2vec-base-chinese",
        vision_model: str = "openai/clip-vit-base-patch32",
        device: Optional[str] = None
    ):
        from sentence_transformers import SentenceTransformer
        from transformers import CLIPModel, CLIPProcessor
        
        if device is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.device = device
        self.text_encoder = SentenceTransformer(text_model, device=device)
        self.vision_model = CLIPModel.from_pretrained(vision_model).to(device)
        self.processor = CLIPProcessor.from_pretrained(vision_model)
        
        logger.info("Multimodal embedding service initialized")
    
    def embed_text(self, text: str) -> np.ndarray:
        return self.text_encoder.encode(text, convert_to_numpy=True)
    
    def embed_image(self, image) -> np.ndarray:
        import torch
        from PIL import Image
        
        if isinstance(image, str):
            image = Image.open(image)
        
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            image_features = self.vision_model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features.cpu().numpy()[0]
    
    def compute_image_text_similarity(
        self,
        image_embedding: np.ndarray,
        text_embedding: np.ndarray
    ) -> float:
        image_embedding = torch.from_numpy(image_embedding).to(self.device)
        text_embedding = torch.from_numpy(text_embedding).to(self.device)
        
        return float(torch.dot(image_embedding, text_embedding).item())
    
    def find_matching_images(
        self,
        query_text: str,
        image_embeddings: List[np.ndarray],
        top_k: int = 3
    ) -> List[tuple[int, float]]:
        text_emb = self.embed_text(query_text)
        
        similarities = []
        for i, img_emb in enumerate(image_embeddings):
            sim = self.compute_image_text_similarity(img_emb, text_emb)
            similarities.append((i, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
