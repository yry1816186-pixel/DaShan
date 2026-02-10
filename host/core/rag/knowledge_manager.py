import logging
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from datetime import datetime
import json

from .document_processor import DocumentProcessor, DocumentChunk
from .embedding_service import EmbeddingService
from .vector_store import VectorStore, SearchResult

logger = logging.getLogger(__name__)


class KnowledgeManager:
    def __init__(
        self,
        store_type: str = "chromadb",
        persist_directory: Optional[str] = None,
        embedding_model: str = "shibing624/text2vec-base-chinese",
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        self.persist_directory = persist_directory or "./data/knowledge_db"
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        
        self.embedding_service = EmbeddingService(model_name=embedding_model)
        
        self.vector_store = VectorStore(
            store_type=store_type,
            collection_name="dashan_knowledge",
            persist_directory=self.persist_directory,
            embedding_dim=self.embedding_service.embedding_dim
        )
        
        self.document_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        self._load_index()
        
        logger.info(f"KnowledgeManager initialized (store={store_type})")
    
    def add_document(
        self,
        filepath: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            chunks = self.document_processor.process_file(filepath, metadata)
            
            if not chunks:
                return {"success": False, "error": "No chunks generated"}
            
            embeddings = self.embedding_service.embed_batch(
                [c.content for c in chunks],
                show_progress=True
            )
            
            count = self.vector_store.add_documents(chunks, embeddings.tolist())
            
            self._save_index()
            
            logger.info(f"Added document {filepath}: {count} chunks")
            
            return {
                "success": True,
                "chunks_added": count,
                "doc_id": chunks[0].doc_id if chunks else None
            }
        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return {"success": False, "error": str(e)}
    
    def add_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        doc_id: str = None
    ) -> Dict[str, Any]:
        try:
            chunks = self.document_processor.process_text(text, doc_id=doc_id, metadata=metadata)
            
            if not chunks:
                return {"success": False, "error": "No chunks generated"}
            
            embeddings = self.embedding_service.embed_batch([c.content for c in chunks])
            
            count = self.vector_store.add_documents(chunks, embeddings.tolist())
            
            self._save_index()
            
            logger.info(f"Added text: {count} chunks")
            
            return {
                "success": True,
                "chunks_added": count,
                "doc_id": chunks[0].doc_id if chunks else None
            }
        except Exception as e:
            logger.error(f"Failed to add text: {e}")
            return {"success": False, "error": str(e)}
    
    def add_directory(
        self,
        directory: str,
        recursive: bool = True,
        file_patterns: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            chunks = self.document_processor.process_directory(
                directory,
                recursive=recursive,
                metadata=metadata
            )
            
            if not chunks:
                return {"success": False, "error": "No chunks generated"}
            
            embeddings = self.embedding_service.embed_batch(
                [c.content for c in chunks],
                show_progress=True
            )
            
            count = self.vector_store.add_documents(chunks, embeddings.tolist())
            
            self._save_index()
            
            logger.info(f"Added directory {directory}: {count} chunks")
            
            return {
                "success": True,
                "chunks_added": count,
                "doc_count": len(set(c.doc_id for c in chunks))
            }
        except Exception as e:
            logger.error(f"Failed to add directory: {e}")
            return {"success": False, "error": str(e)}
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.3,
        filter_metadata: Dict[str, Any] = None
    ) -> List[SearchResult]:
        try:
            query_embedding = self.embedding_service.embed_text(query)
            
            results = self.vector_store.search(
                query_embedding.tolist(),
                top_k=top_k,
                min_score=min_score,
                filter_metadata=filter_metadata
            )
            
            logger.info(f"Search '{query[:30]}...': {len(results)} results")
            
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_with_context(
        self,
        query: str,
        top_k: int = 3,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        results = self.search(query, top_k=top_k)
        
        if not results:
            return {
                "found": False,
                "message": "No relevant information found"
            }
        
        context_parts = []
        sources = []
        
        for result in results:
            context_parts.append(f"[{result.source or 'Unknown'}]\n{result.content}")
            sources.append({
                "doc_id": result.doc_id,
                "chunk_id": result.chunk_id,
                "score": result.score,
                "source": result.source
            })
        
        context = "\n\n".join(context_parts)
        
        return {
            "found": True,
            "context": context,
            "sources": sources,
            "count": len(results)
        }
    
    def delete_document(self, doc_id: str) -> bool:
        try:
            count = self.vector_store.delete_by_doc_id(doc_id)
            self._save_index()
            logger.info(f"Deleted document: {doc_id}")
            return count > 0
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def clear_all(self) -> bool:
        try:
            self.vector_store.clear()
            self._save_index()
            logger.info("Cleared all knowledge")
            return True
        except Exception as e:
            logger.error(f"Failed to clear: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.get_stats()
        
        doc_ids = self.vector_store.get_all_doc_ids()
        
        return {
            **stats,
            "unique_documents": len(doc_ids),
            "persist_directory": self.persist_directory,
            "last_updated": datetime.now().isoformat()
        }
    
    def export_knowledge(self, filepath: str) -> bool:
        try:
            self.vector_store.export_metadata(filepath)
            logger.info(f"Knowledge exported to: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export: {e}")
            return False
    
    def rebuild_index(self, batch_size: int = 100) -> Dict[str, Any]:
        try:
            self.vector_store.clear()
            
            all_chunks = self._get_all_chunks_from_disk()
            
            if not all_chunks:
                return {"success": True, "message": "No chunks to rebuild"}
            
            total = len(all_chunks)
            added = 0
            
            for i in range(0, total, batch_size):
                batch = all_chunks[i:i + batch_size]
                embeddings = self.embedding_service.embed_batch(
                    [c.content for c in batch]
                )
                
                count = self.vector_store.add_documents(batch, embeddings.tolist())
                added += count
                
                logger.info(f"Rebuilding index: {added}/{total}")
            
            self._save_index()
            
            return {
                "success": True,
                "total_chunks": total,
                "added": added
            }
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            return {"success": False, "error": str(e)}
    
    def get_document_content(self, doc_id: str) -> Optional[List[DocumentChunk]]:
        try:
            results = self.vector_store.search(
                self.embedding_service.embed_text("").tolist(),
                top_k=1000,
                min_score=0.0,
                filter_metadata={"doc_id": doc_id}
            )
            
            chunks = [
                DocumentChunk(
                    content=r.content,
                    doc_id=r.doc_id,
                    chunk_id=r.chunk_id,
                    metadata=r.metadata,
                    source=r.source
                )
                for r in results
                if r.doc_id == doc_id
            ]
            
            chunks.sort(key=lambda c: int(c.chunk_id))
            
            return chunks
        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return None
    
    def _load_index(self):
        index_file = Path(self.persist_directory) / "knowledge_index.json"
        
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded knowledge index from: {index_file}")
            except Exception as e:
                logger.warning(f"Failed to load index: {e}")
    
    def _save_index(self):
        index_file = Path(self.persist_directory) / "knowledge_index.json"
        
        try:
            data = {
                "stats": self.get_stats(),
                "last_updated": datetime.now().isoformat()
            }
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save index: {e}")
    
    def _get_all_chunks_from_disk(self) -> List[DocumentChunk]:
        return []
    
    def add_conversation_memory(
        self,
        user_input: str,
        assistant_response: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        combined = f"用户: {user_input}\n助手: {assistant_response}"
        
        metadata = metadata or {}
        metadata.update({
            "type": "conversation",
            "timestamp": datetime.now().isoformat()
        })
        
        result = self.add_text(combined, metadata=metadata)
        return result.get("success", False)
    
    def search_conversation_history(
        self,
        query: str,
        limit: int = 5
    ) -> List[SearchResult]:
        return self.search(
            query,
            top_k=limit,
            filter_metadata={"type": "conversation"}
        )
    
    def add_facts(self, facts: List[str], category: str = "general") -> Dict[str, Any]:
        total_added = 0
        errors = []
        
        for fact in facts:
            metadata = {
                "type": "fact",
                "category": category,
                "timestamp": datetime.now().isoformat()
            }
            
            result = self.add_text(fact, metadata=metadata)
            
            if result.get("success"):
                total_added += result.get("chunks_added", 0)
            else:
                errors.append(result.get("error", "Unknown error"))
        
        return {
            "success": total_added > 0,
            "facts_added": total_added,
            "errors": errors
        }
    
    def get_related_topics(self, query: str, top_k: int = 10) -> List[str]:
        results = self.search(query, top_k=top_k)
        
        topics = set()
        
        for result in results:
            if "category" in result.metadata:
                topics.add(result.metadata["category"])
            if "tags" in result.metadata:
                topics.update(result.metadata["tags"])
        
        return list(topics)
