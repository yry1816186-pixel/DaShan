import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import pickle
import json

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from .document_processor import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    content: str
    doc_id: str
    chunk_id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "metadata": self.metadata,
            "source": self.source
        }


class VectorStore:
    def __init__(
        self,
        store_type: str = "chromadb",
        collection_name: str = "dashan_knowledge",
        persist_directory: Optional[str] = None,
        embedding_dim: int = 768
    ):
        self.store_type = store_type
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self._store = None
        self._collection = None
        self._faiss_index = None
        self._faiss_docs = []
        
        if store_type == "chromadb" and CHROMADB_AVAILABLE:
            self._init_chromadb(persist_directory)
        elif store_type == "faiss" and FAISS_AVAILABLE:
            self._init_faiss()
        else:
            logger.warning(f"Using in-memory store (requested: {store_type})")
            self._init_in_memory()
        
        logger.info(f"VectorStore initialized: {store_type}")
    
    def _init_chromadb(self, persist_directory: Optional[str] = None):
        settings = Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        if persist_directory:
            client = chromadb.PersistentClient(path=persist_directory, settings=settings)
        else:
            client = chromadb.Client(settings=settings)
        
        self._store = client
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "DaShan knowledge base"}
        )
    
    def _init_faiss(self):
        self._faiss_index = faiss.IndexFlatL2(self.embedding_dim)
        self._faiss_docs = []
    
    def _init_in_memory(self):
        self._in_memory_data = []
    
    def add_documents(
        self,
        chunks: List[DocumentChunk],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        if not chunks:
            logger.warning("No chunks to add")
            return 0
        
        if self.store_type == "chromadb" and self._collection:
            return self._add_to_chromadb(chunks, embeddings)
        elif self.store_type == "faiss" and self._faiss_index is not None:
            return self._add_to_faiss(chunks, embeddings)
        else:
            return self._add_to_memory(chunks, embeddings)
    
    def _add_to_chromadb(
        self,
        chunks: List[DocumentChunk],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        ids = [c.unique_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                **c.metadata,
                "doc_id": c.doc_id,
                "chunk_id": c.chunk_id,
                "source": c.source,
                "timestamp": c.timestamp.isoformat()
            }
            for c in chunks
        ]
        
        try:
            if embeddings:
                self._collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings
                )
            else:
                self._collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
            
            logger.info(f"Added {len(chunks)} chunks to ChromaDB")
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to add to ChromaDB: {e}")
            return 0
    
    def _add_to_faiss(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]]
    ) -> int:
        import numpy as np
        
        if not embeddings:
            raise ValueError("Embeddings required for FAISS store")
        
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        self._faiss_index.add(embeddings_array)
        self._faiss_docs.extend(chunks)
        
        logger.info(f"Added {len(chunks)} chunks to FAISS (total: {len(self._faiss_docs)})")
        return len(chunks)
    
    def _add_to_memory(
        self,
        chunks: List[DocumentChunk],
        embeddings: Optional[List[List[float]]] = None
    ) -> int:
        for i, chunk in enumerate(chunks):
            self._in_memory_data.append({
                "chunk": chunk,
                "embedding": embeddings[i] if embeddings else None
            })
        
        logger.info(f"Added {len(chunks)} chunks to memory store")
        return len(chunks)
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        if self.store_type == "chromadb" and self._collection:
            return self._search_chromadb(query_embedding, top_k, min_score, filter_metadata)
        elif self.store_type == "faiss" and self._faiss_index is not None:
            return self._search_faiss(query_embedding, top_k, min_score)
        else:
            return self._search_memory(query_embedding, top_k, min_score)
    
    def _search_chromadb(
        self,
        query_embedding: List[float],
        top_k: int,
        min_score: float,
        filter_metadata: Optional[Dict[str, Any]]
    ) -> List[SearchResult]:
        import numpy as np
        
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata
        )
        
        search_results = []
        
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                score = results['distances'][0][i] if results.get('distances') else 1.0
                metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                
                if score >= min_score:
                    search_results.append(SearchResult(
                        content=doc,
                        doc_id=metadata.get('doc_id', ''),
                        chunk_id=metadata.get('chunk_id', ''),
                        score=float(score),
                        metadata=metadata,
                        source=metadata.get('source', '')
                    ))
        
        return search_results
    
    def _search_faiss(
        self,
        query_embedding: List[float],
        top_k: int,
        min_score: float
    ) -> List[SearchResult]:
        import numpy as np
        
        query_array = np.array([query_embedding], dtype=np.float32)
        
        distances, indices = self._faiss_index.search(query_array, top_k)
        
        search_results = []
        
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx >= 0 and idx < len(self._faiss_docs):
                chunk = self._faiss_docs[idx]
                score = 1.0 / (1.0 + float(dist))
                
                if score >= min_score:
                    search_results.append(SearchResult(
                        content=chunk.content,
                        doc_id=chunk.doc_id,
                        chunk_id=chunk.chunk_id,
                        score=score,
                        metadata=chunk.metadata,
                        source=chunk.source
                    ))
        
        return search_results
    
    def _search_memory(
        self,
        query_embedding: List[float],
        top_k: int,
        min_score: float
    ) -> List[SearchResult]:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        
        results = []
        
        for item in self._in_memory_data:
            if item['embedding'] is None:
                continue
            
            emb = np.array(item['embedding']).reshape(1, -1)
            query = np.array(query_embedding).reshape(1, -1)
            
            score = float(cosine_similarity(emb, query)[0][0])
            
            if score >= min_score:
                chunk = item['chunk']
                results.append(SearchResult(
                    content=chunk.content,
                    doc_id=chunk.doc_id,
                    chunk_id=chunk.chunk_id,
                    score=score,
                    metadata=chunk.metadata,
                    source=chunk.source
                ))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def delete_by_doc_id(self, doc_id: str) -> int:
        if self.store_type == "chromadb" and self._collection:
            self._collection.delete(where={"doc_id": doc_id})
            logger.info(f"Deleted document {doc_id} from ChromaDB")
            return 1
        elif self.store_type == "faiss":
            self._faiss_docs = [d for d in self._faiss_docs if d.doc_id != doc_id]
            self._rebuild_faiss_index()
            logger.info(f"Deleted document {doc_id} from FAISS")
            return 1
        else:
            before = len(self._in_memory_data)
            self._in_memory_data = [
                item for item in self._in_memory_data
                if item['chunk'].doc_id != doc_id
            ]
            return before - len(self._in_memory_data)
    
    def _rebuild_faiss_index(self):
        import numpy as np
        from .embedding_service import EmbeddingService
        
        self._faiss_index = faiss.IndexFlatL2(self.embedding_dim)
        
        if self._faiss_docs:
            embeddings = np.array([doc.get('embedding', np.zeros(self.embedding_dim)) for doc in self._faiss_docs])
            self._faiss_index.add(embeddings)
    
    def clear(self):
        if self.store_type == "chromadb" and self._collection:
            self._store.delete_collection(self.collection_name)
            self._collection = self._store.get_or_create_collection(name=self.collection_name)
        elif self.store_type == "faiss":
            self._faiss_index = faiss.IndexFlatL2(self.embedding_dim)
            self._faiss_docs.clear()
        else:
            self._in_memory_data.clear()
        
        logger.info("Vector store cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        if self.store_type == "chromadb" and self._collection:
            count = self._collection.count()
        elif self.store_type == "faiss":
            count = len(self._faiss_docs)
        else:
            count = len(self._in_memory_data)
        
        return {
            "store_type": self.store_type,
            "document_count": count,
            "collection_name": self.collection_name,
            "embedding_dim": self.embedding_dim
        }
    
    def save_faiss_index(self, filepath: str):
        if self.store_type == "faiss" and self._faiss_index:
            import numpy as np
            
            with open(filepath.replace('.index', '_docs.pkl'), 'wb') as f:
                pickle.dump(self._faiss_docs, f)
            
            faiss.write_index(self._faiss_index, filepath)
            logger.info(f"FAISS index saved to: {filepath}")
    
    def load_faiss_index(self, filepath: str):
        if self.store_type == "faiss":
            self._faiss_index = faiss.read_index(filepath)
            
            docs_file = filepath.replace('.index', '_docs.pkl')
            with open(docs_file, 'rb') as f:
                self._faiss_docs = pickle.load(f)
            
            logger.info(f"FAISS index loaded from: {filepath} ({len(self._faiss_docs)} docs)")
    
    def export_metadata(self, filepath: str):
        data = {
            "stats": self.get_stats(),
            "docs": [chunk.to_dict() for chunk in self._get_all_chunks()]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"Metadata exported to: {filepath}")
    
    def _get_all_chunks(self) -> List[DocumentChunk]:
        if self.store_type == "faiss":
            return self._faiss_docs
        elif hasattr(self, '_in_memory_data'):
            return [item['chunk'] for item in self._in_memory_data]
        else:
            return []
    
    def get_all_doc_ids(self) -> List[str]:
        if self.store_type == "faiss":
            return list(set(chunk.doc_id for chunk in self._faiss_docs))
        elif hasattr(self, '_in_memory_data'):
            return list(set(item['chunk'].doc_id for item in self._in_memory_data))
        elif self.store_type == "chromadb" and self._collection:
            result = self._collection.get(include=["metadatas"])
            return list(set(m['doc_id'] for m in result['metadatas']))
        return []
