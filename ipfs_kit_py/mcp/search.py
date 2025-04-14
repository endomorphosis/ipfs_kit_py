"""
MCP Search Module for content indexing and retrieval.

This module provides comprehensive search capabilities for MCP content, including:
1. Content indexing with metadata extraction
2. Full-text search using SQLite FTS5
3. Vector search using FAISS
4. Hybrid search combining text and vector search results
"""

import os
import json
import sqlite3
import logging
import hashlib
import time
import uuid
import threading
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO
from enum import Enum
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)


class SearchIndexType(Enum):
    """Types of search indices."""
    TEXT = "text"
    VECTOR = "vector"
    HYBRID = "hybrid"


class ContentType(Enum):
    """Supported content types for indexing."""
    TEXT = "text"
    JSON = "json"
    BINARY = "binary"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    UNKNOWN = "unknown"


def detect_content_type(content: bytes, filename: Optional[str] = None, 
                       mime_type: Optional[str] = None) -> ContentType:
    """
    Detect the type of content for indexing.
    
    Args:
        content: The content bytes
        filename: Optional filename
        mime_type: Optional MIME type
        
    Returns:
        ContentType enum value
    """
    # Use MIME type if provided
    if mime_type:
        mime_lower = mime_type.lower()
        if 'text/' in mime_lower:
            return ContentType.TEXT
        elif 'application/json' in mime_lower:
            return ContentType.JSON
        elif 'image/' in mime_lower:
            return ContentType.IMAGE
        elif 'audio/' in mime_lower:
            return ContentType.AUDIO
        elif 'video/' in mime_lower:
            return ContentType.VIDEO
        elif 'application/pdf' in mime_lower:
            return ContentType.PDF
    
    # Use filename extension if provided
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in ['.txt', '.md', '.html', '.htm', '.css', '.js', '.py', '.c', '.cpp', '.java', '.sh']:
            return ContentType.TEXT
        elif ext == '.json':
            return ContentType.JSON
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
            return ContentType.IMAGE
        elif ext in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
            return ContentType.AUDIO
        elif ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            return ContentType.VIDEO
        elif ext == '.pdf':
            return ContentType.PDF
    
    # Try to detect based on content
    try:
        # Check if it's JSON
        try:
            json.loads(content)
            return ContentType.JSON
        except:
            pass
        
        # Check if it's text (take a sample to avoid large binary content)
        sample = content[:min(1024, len(content))]
        try:
            sample.decode('utf-8')
            return ContentType.TEXT
        except:
            pass
        
        # Check for common file signatures
        if content.startswith(b'\xff\xd8\xff'):  # JPEG
            return ContentType.IMAGE
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return ContentType.IMAGE
        elif content.startswith(b'GIF87a') or content.startswith(b'GIF89a'):  # GIF
            return ContentType.IMAGE
        elif content.startswith(b'%PDF'):  # PDF
            return ContentType.PDF
        
    except Exception as e:
        logger.warning(f"Error detecting content type: {e}")
    
    # Default to binary if we can't determine
    return ContentType.BINARY


def extract_text(content: bytes, content_type: ContentType) -> Optional[str]:
    """
    Extract searchable text from content.
    
    Args:
        content: Content bytes
        content_type: Type of content
        
    Returns:
        Extracted text or None if extraction failed
    """
    try:
        if content_type == ContentType.TEXT:
            # Simple UTF-8 decoding for text content
            return content.decode('utf-8', errors='replace')
        
        elif content_type == ContentType.JSON:
            # Parse JSON and extract text values
            data = json.loads(content.decode('utf-8', errors='replace'))
            
            # Extract all string values recursively
            def extract_strings(obj):
                if isinstance(obj, str):
                    return obj
                elif isinstance(obj, list):
                    return ' '.join(extract_strings(item) for item in obj if extract_strings(item))
                elif isinstance(obj, dict):
                    return ' '.join(extract_strings(value) for value in obj.values() if extract_strings(value))
                return ''
            
            return extract_strings(data)
        
        elif content_type == ContentType.PDF:
            # Use PyPDF2 if available
            try:
                from io import BytesIO
                import PyPDF2
                
                pdf_file = BytesIO(content)
                reader = PyPDF2.PdfReader(pdf_file)
                text = ' '.join(page.extract_text() for page in reader.pages)
                return text
            except ImportError:
                logger.warning("PyPDF2 not installed, PDF text extraction disabled")
                return None
        
        # For other content types, more specialized extraction would be needed
        # For example, using OCR for images, speech recognition for audio, etc.
        # This is beyond the scope of this implementation
        
    except Exception as e:
        logger.warning(f"Error extracting text: {e}")
    
    return None


class SearchIndex:
    """Base class for search indices."""
    
    def __init__(self, index_path: str, index_name: str):
        """
        Initialize the search index.
        
        Args:
            index_path: Path to index storage location
            index_name: Name of the index
        """
        self.index_path = index_path
        self.index_name = index_name
        self.lock = threading.RLock()
    
    def add_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Add a document to the index.
        
        Args:
            id: Document identifier
            text: Document text content
            metadata: Document metadata
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement add_document")
    
    def search(self, query: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the index.
        
        Args:
            query: Search query
            limit: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        raise NotImplementedError("Subclasses must implement search")
    
    def delete_document(self, id: str) -> bool:
        """
        Delete a document from the index.
        
        Args:
            id: Document identifier
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement delete_document")
    
    def update_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a document in the index.
        
        Args:
            id: Document identifier
            text: New document text content
            metadata: New document metadata
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement update_document")
    
    def commit(self) -> bool:
        """
        Commit changes to the index.
        
        Returns:
            True if successful, False otherwise
        """
        return True
    
    def close(self) -> None:
        """Close the index and free resources."""
        pass


class TextSearchIndex(SearchIndex):
    """Text-based search index using SQLite FTS5."""
    
    def __init__(self, index_path: str, index_name: str = "text_index"):
        """
        Initialize the text search index.
        
        Args:
            index_path: Path to index storage location
            index_name: Name of the index
        """
        super().__init__(index_path, index_name)
        
        # Create the database file path
        os.makedirs(index_path, exist_ok=True)
        self.db_path = os.path.join(index_path, f"{index_name}.db")
        
        # Initialize the database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database with FTS5 table."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create documents table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                metadata TEXT,
                backend TEXT,
                content_type TEXT,
                indexed_at TEXT,
                updated_at TEXT
            )
            ''')
            
            # Create FTS5 virtual table
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
                id, 
                text, 
                content='documents', 
                content_rowid='rowid'
            )
            ''')
            
            # Create trigger to keep FTS index in sync with documents
            cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO fts_index(rowid, id, text) VALUES (new.rowid, new.id, '');
            END
            ''')
            
            cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO fts_index(fts_index, rowid, id, text) VALUES('delete', old.rowid, old.id, '');
            END
            ''')
            
            conn.commit()
            conn.close()
    
    def add_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Add a document to the index.
        
        Args:
            id: Document identifier
            text: Document text content
            metadata: Document metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Convert metadata to JSON
                metadata_json = json.dumps(metadata)
                
                # Get backend and content type from metadata
                backend = metadata.get("backend", "unknown")
                content_type = metadata.get("content_type", "unknown")
                
                # Get current time
                current_time = datetime.now().isoformat()
                
                # Insert or replace document
                cursor.execute('''
                INSERT OR REPLACE INTO documents (id, metadata, backend, content_type, indexed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (id, metadata_json, backend, content_type, current_time, current_time))
                
                # Get the rowid
                cursor.execute('SELECT rowid FROM documents WHERE id = ?', (id,))
                rowid = cursor.fetchone()[0]
                
                # Update FTS index
                cursor.execute('''
                INSERT OR REPLACE INTO fts_index(rowid, id, text) VALUES (?, ?, ?)
                ''', (rowid, id, text))
                
                conn.commit()
                conn.close()
                
                return True
                
        except Exception as e:
            logger.error(f"Error adding document to text index: {e}")
            return False
    
    def search(self, query: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the index.
        
        Args:
            query: Search query
            limit: Maximum number of results
            **kwargs: Additional search parameters (backend, content_type, etc.)
            
        Returns:
            List of search results
        """
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Prepare filter conditions
                filter_conditions = []
                filter_params = []
                
                if "backend" in kwargs:
                    filter_conditions.append("d.backend = ?")
                    filter_params.append(kwargs["backend"])
                
                if "content_type" in kwargs:
                    filter_conditions.append("d.content_type = ?")
                    filter_params.append(kwargs["content_type"])
                
                # Build the filter clause
                filter_clause = ""
                if filter_conditions:
                    filter_clause = "AND " + " AND ".join(filter_conditions)
                
                # Build the query
                if query:
                    # Use FTS5 to search
                    sql = f'''
                    SELECT d.id, d.metadata, d.backend, d.content_type, d.indexed_at, d.updated_at,
                          fts_index.text, fts.rank
                    FROM fts_index as fts
                    JOIN documents as d ON fts.rowid = d.rowid
                    WHERE fts.text MATCH ? {filter_clause}
                    ORDER BY fts.rank
                    LIMIT ?
                    '''
                    params = [query, *filter_params, limit]
                else:
                    # No query, just filter
                    sql = f'''
                    SELECT d.id, d.metadata, d.backend, d.content_type, d.indexed_at, d.updated_at,
                          NULL AS text, 0 AS rank
                    FROM documents as d
                    WHERE 1=1 {filter_clause}
                    LIMIT ?
                    '''
                    params = [*filter_params, limit]
                
                cursor.execute(sql, params)
                
                # Process results
                results = []
                for row in cursor.fetchall():
                    doc_id, metadata_json, backend, content_type, indexed_at, updated_at, text, rank = row
                    
                    # Parse metadata JSON
                    try:
                        metadata = json.loads(metadata_json)
                    except:
                        metadata = {}
                    
                    results.append({
                        "id": doc_id,
                        "metadata": metadata,
                        "backend": backend,
                        "content_type": content_type,
                        "indexed_at": indexed_at,
                        "updated_at": updated_at,
                        "score": 1.0 - rank / 1000,  # Normalize rank to score (0-1)
                        "match_type": "text"
                    })
                
                conn.close()
                
                return results
                
        except Exception as e:
            logger.error(f"Error searching text index: {e}")
            return []
    
    def delete_document(self, id: str) -> bool:
        """
        Delete a document from the index.
        
        Args:
            id: Document identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Delete from documents table (trigger will handle FTS)
                cursor.execute('DELETE FROM documents WHERE id = ?', (id,))
                
                conn.commit()
                conn.close()
                
                return True
                
        except Exception as e:
            logger.error(f"Error deleting document from text index: {e}")
            return False
    
    def update_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a document in the index.
        
        Args:
            id: Document identifier
            text: New document text content
            metadata: New document metadata
            
        Returns:
            True if successful, False otherwise
        """
        # For SQLite, add_document with the same ID will replace
        return self.add_document(id, text, metadata)
    
    def close(self) -> None:
        """Close the index and free resources."""
        # SQLite connections are closed after each operation
        pass


class VectorSearchIndex(SearchIndex):
    """Vector-based search index using FAISS."""
    
    def __init__(self, index_path: str, index_name: str = "vector_index", 
                 vector_dimension: int = 768, use_gpu: bool = False):
        """
        Initialize the vector search index.
        
        Args:
            index_path: Path to index storage location
            index_name: Name of the index
            vector_dimension: Dimension of the vectors
            use_gpu: Whether to use GPU acceleration if available
        """
        super().__init__(index_path, index_name)
        self.vector_dimension = vector_dimension
        self.use_gpu = use_gpu
        
        # Create the storage directory
        os.makedirs(index_path, exist_ok=True)
        
        # Paths for index files
        self.index_file = os.path.join(index_path, f"{index_name}.faiss")
        self.metadata_file = os.path.join(index_path, f"{index_name}_metadata.json")
        
        # Initialize the index
        self._init_index()
    
    def _init_index(self) -> None:
        """Initialize the FAISS index."""
        try:
            import faiss
            import numpy as np
        except ImportError:
            logger.error("FAISS not installed, vector search disabled")
            self.faiss_available = False
            return
        
        self.faiss_available = True
        
        with self.lock:
            # Initialize metadata storage
            self.metadata_store = {}
            self.id_to_index = {}
            
            # Load existing metadata if available
            if os.path.exists(self.metadata_file):
                try:
                    with open(self.metadata_file, 'r') as f:
                        metadata_data = json.load(f)
                        self.metadata_store = metadata_data.get("metadata", {})
                        self.id_to_index = metadata_data.get("id_to_index", {})
                except Exception as e:
                    logger.error(f"Error loading vector index metadata: {e}")
                    self.metadata_store = {}
                    self.id_to_index = {}
            
            # Initialize or load the FAISS index
            if os.path.exists(self.index_file):
                try:
                    self.index = faiss.read_index(self.index_file)
                    logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors")
                except Exception as e:
                    logger.error(f"Error loading FAISS index: {e}")
                    self._create_new_index()
            else:
                self._create_new_index()
            
            # Move to GPU if requested and available
            if self.use_gpu:
                try:
                    res = faiss.StandardGpuResources()
                    self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                    logger.info("Moved FAISS index to GPU")
                except Exception as e:
                    logger.warning(f"Failed to move FAISS index to GPU: {e}")
    
    def _create_new_index(self) -> None:
        """Create a new FAISS index."""
        try:
            import faiss
            # Create a new index
            self.index = faiss.IndexFlatL2(self.vector_dimension)
            logger.info(f"Created new FAISS index with dimension {self.vector_dimension}")
        except ImportError:
            logger.error("FAISS not installed, vector search disabled")
            self.faiss_available = False
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Get vector embedding for text using a language model.
        
        Args:
            text: Text to embed
            
        Returns:
            Vector embedding
        """
        try:
            from sentence_transformers import SentenceTransformer
            # Load the model if not already loaded
            if not hasattr(self, "embedding_model"):
                # Use a smaller model by default
                model_name = "all-MiniLM-L6-v2"
                self.embedding_model = SentenceTransformer(model_name)
                logger.info(f"Loaded embedding model: {model_name}")
            
            # Generate embedding
            embedding = self.embedding_model.encode(text, show_progress_bar=False)
            return embedding.tolist()
            
        except ImportError:
            logger.warning("sentence-transformers not installed, using random embeddings")
            # Generate a random embedding for testing
            import numpy as np
            random_vector = np.random.rand(self.vector_dimension).astype(np.float32)
            # Normalize to unit length
            random_vector = random_vector / np.linalg.norm(random_vector)
            return random_vector.tolist()
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * self.vector_dimension
    
    def add_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Add a document to the index.
        
        Args:
            id: Document identifier
            text: Document text content
            metadata: Document metadata
            
        Returns:
            True if successful, False otherwise
        """
        if not self.faiss_available:
            logger.error("FAISS not available, cannot add document to vector index")
            return False
        
        try:
            import faiss
            import numpy as np
            
            with self.lock:
                # Generate embedding
                embedding = self._get_embedding(text)
                
                # Convert to numpy array
                vector = np.array([embedding], dtype=np.float32)
                
                # Add to FAISS index
                index_id = self.index.ntotal
                self.index.add(vector)
                
                # Store mapping and metadata
                str_id = str(id)
                self.id_to_index[str_id] = index_id
                
                # Add timestamp to metadata
                enriched_metadata = metadata.copy()
                enriched_metadata["indexed_at"] = datetime.now().isoformat()
                enriched_metadata["updated_at"] = datetime.now().isoformat()
                
                self.metadata_store[str_id] = {
                    "metadata": enriched_metadata,
                    "index_id": index_id,
                    "embedding": embedding  # Store for potential reindexing
                }
                
                # Save metadata to disk
                self._save_metadata()
                
                # Save index to disk
                self._save_index()
                
                return True
                
        except Exception as e:
            logger.error(f"Error adding document to vector index: {e}")
            return False
    
    def search(self, query: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search the index.
        
        Args:
            query: Search query
            limit: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        if not self.faiss_available:
            logger.error("FAISS not available, cannot search vector index")
            return []
        
        try:
            import faiss
            import numpy as np
            
            with self.lock:
                # If query is already an embedding, use it directly
                if isinstance(query, list) and len(query) == self.vector_dimension:
                    query_vector = np.array([query], dtype=np.float32)
                else:
                    # Generate embedding
                    embedding = self._get_embedding(query)
                    query_vector = np.array([embedding], dtype=np.float32)
                
                # Search the index
                k = min(limit, self.index.ntotal)
                if k == 0:
                    return []
                
                distances, indices = self.index.search(query_vector, k)
                
                # Process results
                results = []
                for i, (distance, index_id) in enumerate(zip(distances[0], indices[0])):
                    # Find the document ID for this index
                    doc_id = None
                    for id_str, idx in self.id_to_index.items():
                        if idx == index_id:
                            doc_id = id_str
                            break
                    
                    if doc_id and doc_id in self.metadata_store:
                        metadata_entry = self.metadata_store[doc_id]
                        metadata = metadata_entry.get("metadata", {})
                        
                        # Apply filters
                        if "backend" in kwargs and metadata.get("backend") != kwargs["backend"]:
                            continue
                        
                        if "content_type" in kwargs and metadata.get("content_type") != kwargs["content_type"]:
                            continue
                        
                        # Calculate score (convert distance to similarity score)
                        score = 1.0 / (1.0 + distance)
                        
                        results.append({
                            "id": doc_id,
                            "metadata": metadata,
                            "backend": metadata.get("backend", "unknown"),
                            "content_type": metadata.get("content_type", "unknown"),
                            "indexed_at": metadata.get("indexed_at", ""),
                            "updated_at": metadata.get("updated_at", ""),
                            "score": score,
                            "match_type": "vector",
                            "distance": float(distance)
                        })
                
                return results
                
        except Exception as e:
            logger.error(f"Error searching vector index: {e}")
            return []
    
    def delete_document(self, id: str) -> bool:
        """
        Delete a document from the index.
        
        Args:
            id: Document identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self.faiss_available:
            logger.error("FAISS not available, cannot delete document from vector index")
            return False
        
        try:
            import faiss
            import numpy as np
            
            with self.lock:
                str_id = str(id)
                
                # Check if ID exists
                if str_id not in self.id_to_index:
                    return False
                
                # FAISS doesn't support direct deletion, so we need to rebuild the index
                # excluding the document we want to delete
                
                # Get all document embeddings except the one to delete
                vectors = []
                new_id_to_index = {}
                new_metadata_store = {}
                new_index = 0
                
                for doc_id, metadata_entry in self.metadata_store.items():
                    if doc_id != str_id:
                        embedding = metadata_entry.get("embedding", [])
                        if embedding:
                            vectors.append(embedding)
                            new_id_to_index[doc_id] = new_index
                            new_metadata_store[doc_id] = metadata_entry
                            new_index += 1
                
                # Rebuild the index
                if vectors:
                    vectors_array = np.array(vectors, dtype=np.float32)
                    new_index = faiss.IndexFlatL2(self.vector_dimension)
                    new_index.add(vectors_array)
                    self.index = new_index
                else:
                    # If no vectors left, create an empty index
                    self.index = faiss.IndexFlatL2(self.vector_dimension)
                
                # Update metadata and mappings
                self.id_to_index = new_id_to_index
                self.metadata_store = new_metadata_store
                
                # Save metadata and index
                self._save_metadata()
                self._save_index()
                
                return True
                
        except Exception as e:
            logger.error(f"Error deleting document from vector index: {e}")
            return False
    
    def update_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a document in the index.
        
        Args:
            id: Document identifier
            text: New document text content
            metadata: New document metadata
            
        Returns:
            True if successful, False otherwise
        """
        # For FAISS, we need to delete and re-add
        if self.delete_document(id):
            return self.add_document(id, text, metadata)
        else:
            # If delete failed, just try to add
            return self.add_document(id, text, metadata)
    
    def _save_metadata(self) -> None:
        """Save metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump({
                    "metadata": self.metadata_store,
                    "id_to_index": self.id_to_index
                }, f)
        except Exception as e:
            logger.error(f"Error saving vector index metadata: {e}")
    
    def _save_index(self) -> None:
        """Save FAISS index to disk."""
        try:
            import faiss
            
            # If index is on GPU, move back to CPU for saving
            if self.use_gpu:
                try:
                    self.index = faiss.index_gpu_to_cpu(self.index)
                except:
                    pass
            
            faiss.write_index(self.index, self.index_file)
            
            # Move back to GPU if needed
            if self.use_gpu:
                try:
                    res = faiss.StandardGpuResources()
                    self.index = faiss.index_cpu_to_gpu(res, 0, self.index)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error saving FAISS index: {e}")
    
    def close(self) -> None:
        """Close the index and free resources."""
        with self.lock:
            # Save metadata and index
            self._save_metadata()
            self._save_index()


class HybridSearchIndex(SearchIndex):
    """Hybrid search combining text and vector search."""
    
    def __init__(self, index_path: str, index_name: str = "hybrid_index",
                vector_dimension: int = 768, use_gpu: bool = False):
        """
        Initialize the hybrid search index.
        
        Args:
            index_path: Path to index storage location
            index_name: Name of the index
            vector_dimension: Dimension of the vectors
            use_gpu: Whether to use GPU acceleration if available
        """
        super().__init__(index_path, index_name)
        
        # Create the storage directory
        os.makedirs(index_path, exist_ok=True)
        
        # Create sub-directories for the indices
        text_index_path = os.path.join(index_path, "text")
        vector_index_path = os.path.join(index_path, "vector")
        
        os.makedirs(text_index_path, exist_ok=True)
        os.makedirs(vector_index_path, exist_ok=True)
        
        # Initialize the text and vector indices
        self.text_index = TextSearchIndex(text_index_path, f"{index_name}_text")
        self.vector_index = VectorSearchIndex(vector_index_path, f"{index_name}_vector", 
                                             vector_dimension, use_gpu)
        
        # Flag to check if vector search is available
        self.vector_search_available = self.vector_index.faiss_available
    
    def add_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Add a document to both text and vector indices.
        
        Args:
            id: Document identifier
            text: Document text content
            metadata: Document metadata
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Add to text index
            text_success = self.text_index.add_document(id, text, metadata)
            
            # Add to vector index if available
            vector_success = True
            if self.vector_search_available:
                vector_success = self.vector_index.add_document(id, text, metadata)
            
            return text_success and vector_success
    
    def search(self, query: str, limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search both text and vector indices and combine results.
        
        Args:
            query: Search query
            limit: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            List of search results
        """
        with self.lock:
            # Get search mode
            search_mode = kwargs.get("search_mode", "auto")
            
            # For text-specific search
            if search_mode == "text":
                return self.text_index.search(query, limit, **kwargs)
            
            # For vector-specific search
            if search_mode == "vector" and self.vector_search_available:
                return self.vector_index.search(query, limit, **kwargs)
            
            # For hybrid search (default)
            text_results = self.text_index.search(query, limit * 2, **kwargs)
            vector_results = []
            
            if self.vector_search_available and search_mode != "text":
                vector_results = self.vector_index.search(query, limit * 2, **kwargs)
            
            # Combine and deduplicate results
            combined_results = {}
            
            # Process text results
            for result in text_results:
                doc_id = result["id"]
                combined_results[doc_id] = result
            
            # Process vector results
            for result in vector_results:
                doc_id = result["id"]
                if doc_id in combined_results:
                    # Calculate combined score (average of text and vector scores)
                    text_score = combined_results[doc_id]["score"]
                    vector_score = result["score"]
                    combined_score = (text_score + vector_score) / 2
                    
                    # Update with combined information
                    combined_results[doc_id]["score"] = combined_score
                    combined_results[doc_id]["match_type"] = "hybrid"
                    combined_results[doc_id]["text_score"] = text_score
                    combined_results[doc_id]["vector_score"] = vector_score
                else:
                    combined_results[doc_id] = result
            
            # Sort by score and limit results
            sorted_results = sorted(combined_results.values(), key=lambda x: x["score"], reverse=True)
            return sorted_results[:limit]
    
    def delete_document(self, id: str) -> bool:
        """
        Delete a document from both indices.
        
        Args:
            id: Document identifier
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Delete from text index
            text_success = self.text_index.delete_document(id)
            
            # Delete from vector index if available
            vector_success = True
            if self.vector_search_available:
                vector_success = self.vector_index.delete_document(id)
            
            return text_success and vector_success
    
    def update_document(self, id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """
        Update a document in both indices.
        
        Args:
            id: Document identifier
            text: New document text content
            metadata: New document metadata
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            # Update text index
            text_success = self.text_index.update_document(id, text, metadata)
            
            # Update vector index if available
            vector_success = True
            if self.vector_search_available:
                vector_success = self.vector_index.update_document(id, text, metadata)
            
            return text_success and vector_success
    
    def close(self) -> None:
        """Close both indices and free resources."""
        with self.lock:
            self.text_index.close()
            if self.vector_search_available:
                self.vector_index.close()


class MCP_Search:
    """MCP Search Manager for content indexing and retrieval."""
    
    def __init__(self, index_path: Optional[str] = None, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the search manager.
        
        Args:
            index_path: Path to store indices
            backend_registry: Dictionary mapping backend names to instances
        """
        # Set index path
        if index_path:
            self.index_path = index_path
        else:
            self.index_path = os.path.join(tempfile.gettempdir(), "mcp_search")
        
        os.makedirs(self.index_path, exist_ok=True)
        logger.info(f"Using search index path: {self.index_path}")
        
        # Store backend registry
        self.backend_registry = backend_registry or {}
        
        # Create indices
        self.text_index = TextSearchIndex(os.path.join(self.index_path, "text"), "text_index")
        
        # Try to create vector index
        try:
            import faiss
            import numpy as np
            self.vector_index = VectorSearchIndex(os.path.join(self.index_path, "vector"), "vector_index")
            self.hybrid_index = HybridSearchIndex(os.path.join(self.index_path, "hybrid"), "hybrid_index")
            self.vector_search_available = True
        except ImportError:
            logger.warning("FAISS not installed, vector search disabled")
            self.vector_search_available = False
            self.vector_index = None
            self.hybrid_index = None
        
        # Default index to use
        self.default_index = self.hybrid_index if self.vector_search_available else self.text_index
        
        # Create lock
        self.lock = threading.RLock()
    
    def index_content(self, content_id: str, content: Union[str, bytes], 
                     metadata: Dict[str, Any], 
                     backend_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Index content for search.
        
        Args:
            content_id: Content identifier
            content: Content as string or bytes
            metadata: Content metadata
            backend_name: Optional backend name
            
        Returns:
            Dict with operation result
        """
        try:
            # Add backend name to metadata if provided
            if backend_name:
                metadata["backend"] = backend_name
            
            # Convert string content to bytes if needed
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
                content_type = ContentType.TEXT
            else:
                content_bytes = content
                
                # Detect content type
                filename = metadata.get("filename")
                mime_type = metadata.get("content_type") or metadata.get("mime_type")
                content_type = detect_content_type(content_bytes, filename, mime_type)
            
            # Add content type to metadata
            metadata["content_type"] = content_type.value
            
            # Extract text for indexing
            text = extract_text(content_bytes, content_type)
            
            if not text:
                logger.warning(f"No text could be extracted from content ID {content_id}")
                text = metadata.get("title", "") + " " + metadata.get("description", "")
            
            # Add to indices
            with self.lock:
                self.text_index.add_document(content_id, text, metadata)
                
                if self.vector_search_available:
                    self.vector_index.add_document(content_id, text, metadata)
                    self.hybrid_index.add_document(content_id, text, metadata)
            
            return {
                "success": True,
                "content_id": content_id,
                "content_type": content_type.value,
                "text_length": len(text) if text else 0,
                "backend": backend_name,
                "vector_indexed": self.vector_search_available
            }
            
        except Exception as e:
            logger.error(f"Error indexing content: {e}")
            return {
                "success": False,
                "content_id": content_id,
                "error": str(e),
                "backend": backend_name
            }
    
    def search(self, query: str, index_type: Optional[SearchIndexType] = None, 
              limit: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Search for content.
        
        Args:
            query: Search query
            index_type: Type of index to use (text, vector, hybrid)
            limit: Maximum number of results
            **kwargs: Additional search parameters
            
        Returns:
            Dict with search results
        """
        try:
            # Determine which index to use
            if not index_type:
                index = self.default_index
            elif index_type == SearchIndexType.TEXT:
                index = self.text_index
            elif index_type == SearchIndexType.VECTOR:
                if not self.vector_search_available:
                    return {
                        "success": False,
                        "error": "Vector search not available",
                        "query": query
                    }
                index = self.vector_index
            elif index_type == SearchIndexType.HYBRID:
                if not self.vector_search_available:
                    return {
                        "success": False,
                        "error": "Hybrid search not available",
                        "query": query
                    }
                index = self.hybrid_index
            else:
                index = self.default_index
            
            # Perform the search
            results = index.search(query, limit, **kwargs)
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results),
                "index_type": index_type.value if index_type else (
                    SearchIndexType.HYBRID.value if self.vector_search_available else SearchIndexType.TEXT.value
                )
            }
            
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    def delete_content(self, content_id: str) -> Dict[str, Any]:
        """
        Delete content from indices.
        
        Args:
            content_id: Content identifier
            
        Returns:
            Dict with operation result
        """
        try:
            with self.lock:
                text_success = self.text_index.delete_document(content_id)
                
                vector_success = True
                hybrid_success = True
                
                if self.vector_search_available:
                    vector_success = self.vector_index.delete_document(content_id)
                    hybrid_success = self.hybrid_index.delete_document(content_id)
                
                return {
                    "success": text_success and vector_success and hybrid_success,
                    "content_id": content_id,
                    "text_success": text_success,
                    "vector_success": vector_success,
                    "hybrid_success": hybrid_success
                }
                
        except Exception as e:
            logger.error(f"Error deleting content: {e}")
            return {
                "success": False,
                "content_id": content_id,
                "error": str(e)
            }
    
    def update_content(self, content_id: str, content: Union[str, bytes], 
                      metadata: Dict[str, Any], 
                      backend_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Update indexed content.
        
        Args:
            content_id: Content identifier
            content: Updated content as string or bytes
            metadata: Updated metadata
            backend_name: Optional backend name
            
        Returns:
            Dict with operation result
        """
        # For updates, we delete and re-index
        self.delete_content(content_id)
        return self.index_content(content_id, content, metadata, backend_name)
    
    def index_backend_content(self, backend_name: str, content_id: str) -> Dict[str, Any]:
        """
        Index content directly from a backend.
        
        Args:
            backend_name: Name of the backend
            content_id: Content identifier in the backend
            
        Returns:
            Dict with operation result
        """
        try:
            # Check if backend exists
            backend = self.backend_registry.get(backend_name)
            if not backend:
                return {
                    "success": False,
                    "content_id": content_id,
                    "backend": backend_name,
                    "error": f"Backend '{backend_name}' not found"
                }
            
            # Get content from backend
            content_result = backend.get_content(content_id)
            if not content_result.get("success", False):
                return {
                    "success": False,
                    "content_id": content_id,
                    "backend": backend_name,
                    "error": f"Failed to retrieve content: {content_result.get('error', 'Unknown error')}"
                }
            
            # Get metadata from backend
            metadata_result = backend.get_metadata(content_id)
            metadata = metadata_result.get("metadata", {}) if metadata_result.get("success", False) else {}
            
            # Add backend info to metadata
            metadata["backend"] = backend_name
            metadata["content_id"] = content_id
            
            # Index the content
            return self.index_content(content_id, content_result.get("data"), metadata, backend_name)
            
        except Exception as e:
            logger.error(f"Error indexing backend content: {e}")
            return {
                "success": False,
                "content_id": content_id,
                "backend": backend_name,
                "error": str(e)
            }
    
    def close(self) -> None:
        """Close indices and free resources."""
        with self.lock:
            self.text_index.close()
            
            if self.vector_search_available:
                self.vector_index.close()
                self.hybrid_index.close()
            
            logger.info("Search manager closed")