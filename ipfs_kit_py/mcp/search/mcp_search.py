"""
Search module for MCP server.

This module implements the search functionality mentioned in the roadmap,
including content indexing, text search, and vector search capabilities.
"""

import os
import sys
import json
import time
import logging
import sqlite3
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
import anyio

# Optional dependencies for vector search
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# Configure logger
logger = logging.getLogger(__name__)

class SearchEngine:
    """
    Search engine for IPFS content.
    
    This class implements the search capabilities mentioned in the roadmap:
    - Content indexing
    - Full-text search with SQLite FTS5
    - Vector search with FAISS
    - Hybrid search combining text and vector search
    """
    
    def __init__(self, db_path=None, enable_vector_search=True, vector_model_name="all-MiniLM-L6-v2"):
        """
        Initialize the search engine.
        
        Args:
            db_path: Path to the SQLite database file
            enable_vector_search: Whether to enable vector search
            vector_model_name: Name of the sentence transformer model to use
        """
        self.db_path = db_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "search.db"
        )
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize SQLite database for text search and metadata
        self._init_db()
        
        # Vector search support
        self.enable_vector_search = enable_vector_search
        self.vector_model_name = vector_model_name
        self.vector_model = None
        self.vector_index = None
        self.vectors = {}  # CID -> vector mapping
        
        # Initialize vector search if enabled
        if self.enable_vector_search:
            self._init_vector_search()
    
    def _init_db(self):
        """Initialize the SQLite database."""
        try:
            # Connect to database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # Create content table with FTS5 virtual table
            self.conn.executescript("""
                -- Content metadata table
                CREATE TABLE IF NOT EXISTS content (
                    cid TEXT PRIMARY KEY,
                    title TEXT,
                    content_type TEXT,
                    size INTEGER,
                    created_at REAL,
                    updated_at REAL
                );
                
                -- Content tags
                CREATE TABLE IF NOT EXISTS tags (
                    cid TEXT,
                    tag TEXT,
                    PRIMARY KEY (cid, tag),
                    FOREIGN KEY (cid) REFERENCES content(cid) ON DELETE CASCADE
                );
                
                -- Custom metadata
                CREATE TABLE IF NOT EXISTS metadata (
                    cid TEXT,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (cid, key),
                    FOREIGN KEY (cid) REFERENCES content(cid) ON DELETE CASCADE
                );
                
                -- Full-text search index
                CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                    cid UNINDEXED,
                    title,
                    text,
                    tokenize='porter unicode61'
                );
            """)
            
            # Create indexes
            self.conn.executescript("""
                CREATE INDEX IF NOT EXISTS idx_content_type ON content(content_type);
                CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
                CREATE INDEX IF NOT EXISTS idx_metadata_key ON metadata(key);
                CREATE INDEX IF NOT EXISTS idx_metadata_value ON metadata(value);
            """)
            
            logger.info(f"Initialized search database at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error initializing search database: {e}")
            raise
    
    def _init_vector_search(self):
        """Initialize vector search capabilities."""
        # Check required dependencies
        if not NUMPY_AVAILABLE:
            logger.warning("NumPy not available, vector search will be disabled")
            self.enable_vector_search = False
            return
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not available, vector search will be disabled")
            self.enable_vector_search = False
            return
        
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available, vector search will be disabled")
            self.enable_vector_search = False
            return
        
        try:
            # Load vector model
            logger.info(f"Loading sentence transformer model: {self.vector_model_name}")
            self.vector_model = SentenceTransformer(self.vector_model_name)
            
            # Get vector dimension
            self.vector_dim = self.vector_model.get_sentence_embedding_dimension()
            logger.info(f"Vector dimension: {self.vector_dim}")
            
            # Initialize FAISS index
            self.vector_index = faiss.IndexFlatL2(self.vector_dim)
            
            # Load existing vectors from database
            self._load_vectors()
            
            logger.info(f"Vector search initialized with model {self.vector_model_name}")
        except Exception as e:
            logger.error(f"Error initializing vector search: {e}")
            self.enable_vector_search = False
    
    def _load_vectors(self):
        """Load existing vectors from the database."""
        try:
            # Create vectors table if it doesn't exist
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    cid TEXT PRIMARY KEY,
                    vector BLOB,
                    FOREIGN KEY (cid) REFERENCES content(cid) ON DELETE CASCADE
                )
            """)
            
            # Load vectors
            rows = self.conn.execute("SELECT cid, vector FROM vectors").fetchall()
            
            vectors = []
            for row in rows:
                cid = row["cid"]
                vector_blob = row["vector"]
                
                # Deserialize vector
                vector = np.frombuffer(vector_blob, dtype=np.float32)
                self.vectors[cid] = vector
                vectors.append(vector)
            
            # Add vectors to FAISS index
            if vectors:
                vectors_array = np.vstack(vectors)
                self.vector_index.add(vectors_array)
                
                logger.info(f"Loaded {len(vectors)} vectors from database")
        except Exception as e:
            logger.error(f"Error loading vectors: {e}")
    
    def close(self):
        """Close the database connection."""
        if hasattr(self, "conn"):
            self.conn.close()
    
    async def index_document(self, cid: str, text: str = None, title: str = None, 
                      content_type: str = None, metadata: Dict[str, Any] = None,
                      extract_text: bool = False, ipfs_client = None) -> bool:
        """
        Index a document for search.
        
        Args:
            cid: Content identifier
            text: Document text, optional if extract_text is True
            title: Document title
            content_type: Content type
            metadata: Additional metadata
            extract_text: Whether to extract text from IPFS content
            ipfs_client: IPFS client for extracting text
            
        Returns:
            True if document was indexed successfully
        """
        try:
            # Extract text if requested
            if extract_text and not text and ipfs_client:
                text = await self._extract_text(cid, ipfs_client)
            
            # Use anyio to handle the database operation
            return await anyio.to_thread.run_sync(
                self._index_document_sync, 
                cid, text, title, content_type, metadata
            )
        except Exception as e:
            logger.error(f"Error indexing document {cid}: {e}")
            return False
    
    def _index_document_sync(self, cid: str, text: str = None, title: str = None,
                           content_type: str = None, metadata: Dict[str, Any] = None) -> bool:
        """Synchronous version of index_document."""
        try:
            # Start a transaction
            with self.conn:
                # Insert into content table
                now = time.time()
                self.conn.execute(
                    "INSERT OR REPLACE INTO content (cid, title, content_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (cid, title, content_type, now, now)
                )
                
                # Index text content
                if text:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO content_fts (cid, title, text) VALUES (?, ?, ?)",
                        (cid, title or "", text)
                    )
                
                # Index metadata
                if metadata:
                    # Insert tags
                    tags = metadata.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            self.conn.execute(
                                "INSERT OR REPLACE INTO tags (cid, tag) VALUES (?, ?)",
                                (cid, str(tag))
                            )
                    
                    # Insert other metadata
                    for key, value in metadata.items():
                        if key != "tags" and value is not None:
                            self.conn.execute(
                                "INSERT OR REPLACE INTO metadata (cid, key, value) VALUES (?, ?, ?)",
                                (cid, key, str(value))
                            )
                
                # Generate vector embedding
                if self.enable_vector_search and text and self.vector_model:
                    # Generate embedding
                    vector = self.vector_model.encode(text[:10000], show_progress_bar=False)
                    vector = vector.astype(np.float32)
                    
                    # Store in database
                    self.conn.execute(
                        "INSERT OR REPLACE INTO vectors (cid, vector) VALUES (?, ?)",
                        (cid, vector.tobytes())
                    )
                    
                    # Update in-memory vector index
                    if cid in self.vectors:
                        # Remove old vector
                        old_vector = self.vectors[cid]
                        temp_index = faiss.IndexFlatL2(self.vector_dim)
                        temp_index.add(np.array([old_vector]))
                        self.vector_index.remove_ids(faiss.IDSelectorBatch([0]))
                    
                    # Add new vector
                    self.vector_index.add(np.array([vector]))
                    self.vectors[cid] = vector
            
            return True
        except Exception as e:
            logger.error(f"Error in _index_document_sync for {cid}: {e}")
            return False
    
    async def _extract_text(self, cid: str, ipfs_client) -> str:
        """
        Extract text from IPFS content.
        
        Args:
            cid: Content identifier
            ipfs_client: IPFS client for retrieving content
            
        Returns:
            Extracted text
        """
        try:
            # Get content from IPFS
            result = await anyio.to_thread.run_sync(
                lambda: ipfs_client.ipfs_cat(cid)
            )
            
            if not result.get("success"):
                logger.warning(f"Failed to get content for {cid}: {result.get('error')}")
                return ""
            
            data = result.get("data")
            if not data:
                return ""
            
            # Simple text extraction based on content type
            # In a real implementation, this would use libraries like
            # Tika, pdftotext, etc. for proper extraction
            
            # Convert bytes to string
            if isinstance(data, bytes):
                try:
                    # Try UTF-8 first
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    # Fall back to latin-1
                    text = data.decode("latin-1")
            else:
                text = str(data)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {cid}: {e}")
            return ""
    
    async def search_text(self, query: str, limit: int = 10, offset: int = 0,
                   metadata_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search for documents using text search.
        
        Args:
            query: Search query
            limit: Maximum number of results
            offset: Results offset
            metadata_filters: Metadata filters
            
        Returns:
            List of search results
        """
        try:
            return await anyio.to_thread.run_sync(
                self._search_text_sync, query, limit, offset, metadata_filters
            )
        except Exception as e:
            logger.error(f"Error in search_text: {e}")
            return []
    
    def _search_text_sync(self, query: str, limit: int = 10, offset: int = 0,
                        metadata_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Synchronous version of search_text."""
        try:
            # Build query
            sql_query = """
                SELECT c.cid, c.title, c.content_type, c.created_at, c.updated_at,
                       fts.text, fts.rank
                FROM content c
                JOIN content_fts fts ON c.cid = fts.cid
            """
            
            params = []
            where_clauses = []
            
            # Add FTS match clause if query is not empty
            if query:
                where_clauses.append("content_fts MATCH ?")
                params.append(query)
            
            # Add metadata filters
            if metadata_filters:
                for key, value in metadata_filters.items():
                    if key == "tags":
                        # Handle tag filters
                        if isinstance(value, list):
                            placeholders = ", ".join(["?"] * len(value))
                            sql_query += f" JOIN tags t ON c.cid = t.cid"
                            where_clauses.append(f"t.tag IN ({placeholders})")
                            params.extend(value)
                        else:
                            sql_query += f" JOIN tags t ON c.cid = t.cid"
                            where_clauses.append("t.tag = ?")
                            params.append(value)
                    elif key == "content_type":
                        # Handle content type filter
                        where_clauses.append("c.content_type = ?")
                        params.append(value)
                    else:
                        # Handle other metadata filters
                        sql_query += f" JOIN metadata m_{key} ON c.cid = m_{key}.cid"
                        where_clauses.append(f"m_{key}.key = ? AND m_{key}.value = ?")
                        params.append(key)
                        params.append(str(value))
            
            # Add WHERE clause if needed
            if where_clauses:
                sql_query += " WHERE " + " AND ".join(where_clauses)
            
            # Add ORDER BY, LIMIT, and OFFSET
            if query:
                sql_query += " ORDER BY fts.rank"
            else:
                sql_query += " ORDER BY c.updated_at DESC"
            
            sql_query += " LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            # Execute query
            cursor = self.conn.execute(sql_query, params)
            rows = cursor.fetchall()
            
            # Format results
            results = []
            for row in rows:
                result = dict(row)
                
                # Get tags
                tags_cursor = self.conn.execute(
                    "SELECT tag FROM tags WHERE cid = ?",
                    (row["cid"],)
                )
                tags = [tag[0] for tag in tags_cursor.fetchall()]
                result["tags"] = tags
                
                # Get metadata
                metadata_cursor = self.conn.execute(
                    "SELECT key, value FROM metadata WHERE cid = ?",
                    (row["cid"],)
                )
                metadata = {key: value for key, value in metadata_cursor.fetchall()}
                result["metadata"] = metadata
                
                results.append(result)
            
            return results
        except Exception as e:
            logger.error(f"Error in _search_text_sync: {e}")
            return []
    
    async def search_vector(self, text: str, limit: int = 10,
                     metadata_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Search for documents using vector similarity.
        
        Args:
            text: Query text to convert to vector
            limit: Maximum number of results
            metadata_filters: Metadata filters
            
        Returns:
            List of search results
        """
        if not self.enable_vector_search:
            logger.warning("Vector search is not enabled")
            return []
        
        try:
            # Generate query vector
            query_vector = await anyio.to_thread.run_sync(
                lambda: self.vector_model.encode(text, show_progress_bar=False)
            )
            query_vector = query_vector.astype(np.float32)
            
            # Search FAISS index
            return await anyio.to_thread.run_sync(
                self._search_vector_sync, query_vector, limit, metadata_filters
            )
        except Exception as e:
            logger.error(f"Error in search_vector: {e}")
            return []
    
    def _search_vector_sync(self, query_vector: np.ndarray, limit: int = 10,
                          metadata_filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Synchronous version of search_vector."""
        try:
            # Search FAISS index
            distances, indices = self.vector_index.search(
                np.array([query_vector]), k=limit * 10  # Get more results for filtering
            )
            
            # Map indices to CIDs
            cids = list(self.vectors.keys())
            results = []
            
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < 0 or idx >= len(cids):
                    continue
                
                cid = cids[idx]
                
                # Get document metadata
                cursor = self.conn.execute(
                    """
                    SELECT c.cid, c.title, c.content_type, c.created_at, c.updated_at,
                           fts.text
                    FROM content c
                    LEFT JOIN content_fts fts ON c.cid = fts.cid
                    WHERE c.cid = ?
                    """,
                    (cid,)
                )
                
                row = cursor.fetchone()
                if not row:
                    continue
                
                result = dict(row)
                result["score"] = float(1.0 / (1.0 + distance))  # Convert distance to score
                
                # Get tags
                tags_cursor = self.conn.execute(
                    "SELECT tag FROM tags WHERE cid = ?",
                    (cid,)
                )
                tags = [tag[0] for tag in tags_cursor.fetchall()]
                result["tags"] = tags
                
                # Get metadata
                metadata_cursor = self.conn.execute(
                    "SELECT key, value FROM metadata WHERE cid = ?",
                    (cid,)
                )
                metadata = {key: value for key, value in metadata_cursor.fetchall()}
                result["metadata"] = metadata
                
                # Apply metadata filters
                if metadata_filters:
                    skip = False
                    for key, value in metadata_filters.items():
                        if key == "tags":
                            if isinstance(value, list):
                                if not any(tag in value for tag in tags):
                                    skip = True
                                    break
                            elif value not in tags:
                                skip = True
                                break
                        elif key == "content_type":
                            if result["content_type"] != value:
                                skip = True
                                break
                        elif key not in metadata or metadata[key] != str(value):
                            skip = True
                            break
                    
                    if skip:
                        continue
                
                results.append(result)
                
                # Stop if we have enough results
                if len(results) >= limit:
                    break
            
            return results
        except Exception as e:
            logger.error(f"Error in _search_vector_sync: {e}")
            return []
    
    async def search_hybrid(self, query: str, limit: int = 10,
                     metadata_filters: Dict[str, Any] = None,
                     text_weight: float = 0.5) -> List[Dict[str, Any]]:
        """
        Search for documents using both text and vector search.
        
        Args:
            query: Search query
            limit: Maximum number of results
            metadata_filters: Metadata filters
            text_weight: Weight for text search (0.0 to 1.0)
            
        Returns:
            List of search results
        """
        try:
            # Perform text search
            text_results = await self.search_text(
                query, limit=limit * 2, metadata_filters=metadata_filters
            )
            
            # Perform vector search if enabled
            vector_results = []
            if self.enable_vector_search:
                vector_results = await self.search_vector(
                    query, limit=limit * 2, metadata_filters=metadata_filters
                )
            
            # Combine and normalize scores
            results_map = {}
            
            # Add text search results
            for result in text_results:
                cid = result["cid"]
                # Normalize text rank to a score between 0 and 1
                # Since SQLite FTS5 ranks with lower values being better matches
                rank = result.get("rank", 1000)  # Default high rank if not available
                text_score = 1.0 / (1.0 + rank)
                
                results_map[cid] = {
                    **result,
                    "text_score": text_score,
                    "vector_score": 0.0,
                    "score": text_score * text_weight
                }
            
            # Add vector search results
            for result in vector_results:
                cid = result["cid"]
                vector_score = result.get("score", 0.0)
                
                if cid in results_map:
                    # Document exists in text results, update score
                    results_map[cid]["vector_score"] = vector_score
                    results_map[cid]["score"] += vector_score * (1.0 - text_weight)
                else:
                    # Document only in vector results
                    results_map[cid] = {
                        **result,
                        "text_score": 0.0,
                        "vector_score": vector_score,
                        "score": vector_score * (1.0 - text_weight)
                    }
            
            # Sort by combined score and limit results
            combined_results = list(results_map.values())
            combined_results.sort(key=lambda x: x["score"], reverse=True)
            
            return combined_results[:limit]
        except Exception as e:
            logger.error(f"Error in search_hybrid: {e}")
            return []
    
    async def delete_document(self, cid: str) -> bool:
        """
        Delete a document from the search index.
        
        Args:
            cid: Content identifier
            
        Returns:
            True if document was deleted successfully
        """
        try:
            return await anyio.to_thread.run_sync(
                self._delete_document_sync, cid
            )
        except Exception as e:
            logger.error(f"Error deleting document {cid}: {e}")
            return False
    
    def _delete_document_sync(self, cid: str) -> bool:
        """Synchronous version of delete_document."""
        try:
            # Start a transaction
            with self.conn:
                # Delete from content table (cascades to tags and metadata)
                self.conn.execute("DELETE FROM content WHERE cid = ?", (cid,))
                
                # Delete from FTS index
                self.conn.execute("DELETE FROM content_fts WHERE cid = ?", (cid,))
                
                # Delete vector if exists
                if self.enable_vector_search and cid in self.vectors:
                    # Remove from FAISS index
                    old_vector = self.vectors[cid]
                    temp_index = faiss.IndexFlatL2(self.vector_dim)
                    temp_index.add(np.array([old_vector]))
                    self.vector_index.remove_ids(faiss.IDSelectorBatch([0]))
                    
                    # Remove from database
                    self.conn.execute("DELETE FROM vectors WHERE cid = ?", (cid,))
                    
                    # Remove from in-memory map
                    del self.vectors[cid]
            
            return True
        except Exception as e:
            logger.error(f"Error in _delete_document_sync for {cid}: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get search engine statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            return await anyio.to_thread.run_sync(self._get_stats_sync)
        except Exception as e:
            logger.error(f"Error getting search stats: {e}")
            return {}
    
    def _get_stats_sync(self) -> Dict[str, Any]:
        """Synchronous version of get_stats."""
        try:
            # Get document count
            content_count = self.conn.execute(
                "SELECT COUNT(*) FROM content"
            ).fetchone()[0]
            
            # Get indexed text content count
            text_count = self.conn.execute(
                "SELECT COUNT(*) FROM content_fts"
            ).fetchone()[0]
            
            # Get tags count
            tags_count = self.conn.execute(
                "SELECT COUNT(DISTINCT tag) FROM tags"
            ).fetchone()[0]
            
            # Get vector count
            vector_count = 0
            if self.enable_vector_search:
                vector_count = len(self.vectors)
            
            return {
                "document_count": content_count,
                "indexed_text_count": text_count,
                "tags_count": tags_count,
                "vector_count": vector_count,
                "vector_search_enabled": self.enable_vector_search,
                "vector_model": self.vector_model_name if self.enable_vector_search else None
            }
        except Exception as e:
            logger.error(f"Error in _get_stats_sync: {e}")
            return {}

# For convenient imports
search_text = SearchEngine.search_text
search_vector = SearchEngine.search_vector
search_hybrid = SearchEngine.search_hybrid
index_document = SearchEngine.index_document