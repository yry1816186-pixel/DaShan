import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib
import re

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    content: str
    doc_id: str
    chunk_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    chunk_index: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def unique_id(self) -> str:
        content_hash = hashlib.md5(self.content.encode()).hexdigest()[:8]
        return f"{self.doc_id}_{self.chunk_id}_{content_hash}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "metadata": self.metadata,
            "source": self.source,
            "chunk_index": self.chunk_index,
            "timestamp": self.timestamp.isoformat(),
            "unique_id": self.unique_id
        }


class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self._supported_extensions = {'.txt', '.md', '.py', '.js', '.html', '.json', '.yaml', '.yml'}
        
        logger.info(f"DocumentProcessor initialized (chunk_size={chunk_size}, overlap={chunk_overlap})")
    
    def process_file(self, filepath: str, metadata: Dict[str, Any] = None) -> List[DocumentChunk]:
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if path.suffix.lower() not in self._supported_extensions:
            logger.warning(f"Unsupported file type: {path.suffix}")
            return []
        
        try:
            content = path.read_text(encoding='utf-8')
            return self.process_text(
                content,
                doc_id=self._generate_doc_id(filepath),
                source=str(filepath),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to process file {filepath}: {e}")
            return []
    
    def process_text(
        self,
        text: str,
        doc_id: str = None,
        source: str = "",
        metadata: Dict[str, Any] = None
    ) -> List[DocumentChunk]:
        doc_id = doc_id or self._generate_doc_id(text)
        metadata = metadata or {}
        
        text = self._clean_text(text)
        
        if not text or len(text) < self.min_chunk_size:
            return [DocumentChunk(
                content=text,
                doc_id=doc_id,
                chunk_id="0",
                metadata=metadata,
                source=source
            )]
        
        chunks = self._split_text(text)
        
        document_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata.update({
                "chunk_index": i,
                "total_chunks": len(chunks),
                "char_count": len(chunk_text)
            })
            
            document_chunks.append(DocumentChunk(
                content=chunk_text,
                doc_id=doc_id,
                chunk_id=str(i),
                metadata=chunk_metadata,
                source=source,
                chunk_index=i
            ))
        
        logger.info(f"Processed {len(document_chunks)} chunks from document {doc_id}")
        return document_chunks
    
    def process_directory(
        self,
        directory: str,
        recursive: bool = True,
        metadata: Dict[str, Any] = None
    ) -> List[DocumentChunk]:
        path = Path(directory)
        
        if not path.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        all_chunks = []
        
        pattern = "**/*" if recursive else "*"
        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix in self._supported_extensions:
                file_metadata = metadata.copy() if metadata else {}
                file_metadata["filename"] = file_path.name
                file_metadata["filepath"] = str(file_path)
                
                chunks = self.process_file(str(file_path), file_metadata)
                all_chunks.extend(chunks)
        
        logger.info(f"Processed {len(all_chunks)} chunks from {len(set(c.doc_id for c in all_chunks))} files")
        return all_chunks
    
    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        
        return text
    
    def _split_text(self, text: str) -> List[str]:
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            if end >= len(text):
                chunks.append(text[start:].strip())
                break
            
            if '\n' in text[start:end]:
                last_newline = text.rfind('\n', start, end)
                end = last_newline + 1
            elif '. ' in text[start:end]:
                last_period = text.rfind('. ', start, end)
                end = last_period + 2
            elif '，' in text[start:end]:
                last_comma = text.rfind('，', start, end)
                if last_comma > start + self.chunk_size // 2:
                    end = last_comma + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = max(start + 1, end - self.chunk_overlap)
        
        return chunks
    
    def _generate_doc_id(self, identifier: str) -> str:
        hash_obj = hashlib.md5(identifier.encode('utf-8'))
        return hash_obj.hexdigest()[:12]
    
    def extract_code_blocks(self, text: str) -> Dict[str, List[str]]:
        code_blocks = {
            "python": re.findall(r'```python\n(.*?)\n```', text, re.DOTALL),
            "javascript": re.findall(r'```javascript\n(.*?)\n```', text, re.DOTALL),
            "bash": re.findall(r'```bash\n(.*?)\n```', text, re.DOTALL),
            "generic": re.findall(r'```\n(.*?)\n```', text, re.DOTALL)
        }
        
        for lang in code_blocks:
            code_blocks[lang] = [code.strip() for code in code_blocks[lang] if code.strip()]
        
        return code_blocks
    
    def extract_headers(self, text: str) -> List[Dict[str, Any]]:
        headers = re.findall(r'^(#{1,6})\s+(.+)$', text, re.MULTILINE)
        
        return [
            {
                "level": len(h[0]),
                "text": h[1].strip(),
                "type": "markdown"
            }
            for h in headers
        ]
    
    def get_summary(self, chunks: List[DocumentChunk], max_length: int = 200) -> str:
        if not chunks:
            return ""
        
        total_content = " ".join([c.content[:100] for c in chunks[:5]])
        return total_content[:max_length] + "..." if len(total_content) > max_length else total_content