"""
Search infrastructure for MCP server.

This module implements content indexing, metadata search, and vector search
capabilities for the MCP server, enabling efficient discovery of IPFS content.
"""

import os
import time
import json
import logging
import asyncio
import tempfile
import hashlib
import sqlite3
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple, Set
from fastapi import FastAPI, APIRouter, HTTPException, Form, Query, Body, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiofiles

# Configure logging
logger = logging.getLogger(__name__)

# Optional dependencies for enhanced search features
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    logger.info("Sentence Transformers available for vector embeddings")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("Sentence Transformers not available. Install with: pip install sentence-transformers")

try:
    import faiss
    FAISS_AVAILABLE = True
    logger.info("FAISS available for vector search")
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available. Install with: pip install faiss-cpu")

# Default paths
DEFAULT_DB_PATH = os.path.expanduser("~/.ipfs_kit/search/mcp_search.db")
DEFAULT_INDEX_PATH = os.path.expanduser("~/.ipfs_kit/search/vector_index")
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"  # Small but effective model for embeddings

# Content types for extraction
TEXT_CONTENT_TYPES = [
    "text/plain", "text/markdown", "text/csv", "text/html",
    "application/json", "application/xml", "application/javascript",
    "application/x-python", "application/x-typescript"
]

JSON_CONTENT_TYPES = [
    "application/json"
]

# Models for schema validation
class ContentMetadata(BaseModel):
    """Metadata for indexed content."""
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    created: Optional[float] = None
    author: Optional[str] = None
    license: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

class SearchQuery(BaseModel):
    """Search query parameters."""
    query_text: Optional[str] = None
    metadata_filters: Optional[Dict[str, Any]] = None
    content_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    vector_search: bool = False
    hybrid_search: bool = False
    min_score: float = 0.0
    max_results: int = 100

class VectorQuery(BaseModel):
    """Vector search query."""
    text: Optional[str] = None
    vector: Optional[List[float]] = None
    metadata_filters: Optional[Dict[str, Any]] = None
    min_score: float = 0.0
    max_results: int = 100

class ContentSearchService:
    """
    Service for content indexing and search.
    
    This class provides functionality for indexing IPFS content metadata,
    extracting text for search, and performing hybrid search operations.
    """
    
    def __init__(
        self, 
        db_path: str = DEFAULT_DB_PATH,
        vector_index_path: str = DEFAULT_INDEX_PATH,
        embedding_model_name: str = DEFAULT_MODEL_NAME,
        vector_dimension: int = 384  # Default for all-MiniLM-L6-v2
    ):
        """
        Initialize the content search service.
        
        Args:
            db_path: Path to the SQLite database
            vector_index_path: Path to store the vector index
            embedding_model_name: Name of the embedding model
            vector_dimension: Dimension of the embedding vectors
        """
        self.db_path = db_path
        self.vector_index_path = vector_index_path
        self.embedding_model_name = embedding_model_name
        self.vector_dimension = vector_dimension
        
        # Create necessary directories
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(vector_index_path, exist_ok=True)
        
        # Initialize the database
        self._init_database()
        
        # Initialize embedding model if available
        self.embedding_model = None
        self.vector_index = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(embedding_model_name)
                logger.info(f"Loaded embedding model: {embedding_model_name}")
            except Exception as e:
                logger.error(f"Error loading embedding model: {e}")
        
        # Initialize vector index if available
        if FAISS_AVAILABLE:
            self._init_vector_index()
    
    def _init_database(self):
        """Initialize the SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create content metadata table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_metadata (
                cid TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                tags TEXT,
                content_type TEXT,
                size INTEGER,
                created REAL,
                author TEXT,
                license TEXT,
                extra TEXT,
                indexed_at REAL,
                text_extracted BOOLEAN DEFAULT 0,
                vector_embedded BOOLEAN DEFAULT 0
            )
            ''')
            
            # Create content text table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_text (
                cid TEXT PRIMARY KEY,
                text TEXT,
                text_hash TEXT,
                extracted_at REAL,
                FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
            )
            ''')
            
            # Create vector mapping table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS vector_mapping (
                cid TEXT PRIMARY KEY,
                vector_id INTEGER,
                embedded_at REAL,
                FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
            )
            ''')
            
            # Create tags table for efficient filtering
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS content_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cid TEXT,
                tag TEXT,
                FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_tags_tag ON content_tags (tag)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_tags_cid ON content_tags (cid)')
            
            # Create full-text search index
            cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                cid UNINDEXED,
                name,
                description,
                tags,
                text,
                content='content_text',
                content_rowid='rowid'
            )
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Initialized search database at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def _init_vector_index(self):
        """Initialize the FAISS vector index."""
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available, vector search disabled")
            return
        
        try:
            # Check if index exists
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            if os.path.exists(index_file):
                # Load existing index
                self.vector_index = faiss.read_index(index_file)
                logger.info(f"Loaded vector index from {index_file} with {self.vector_index.ntotal} vectors")
            else:
                # Create new index
                self.vector_index = faiss.IndexFlatIP(self.vector_dimension)  # Inner product for cosine similarity with normalized vectors
                logger.info(f"Created new vector index with dimension {self.vector_dimension}")
                
                # Save empty index
                faiss.write_index(self.vector_index, index_file)
        except Exception as e:
            logger.error(f"Error initializing vector index: {e}")
    
    def _save_vector_index(self):
        """Save the vector index to disk."""
        if not FAISS_AVAILABLE or self.vector_index is None:
            return
        
        try:
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            faiss.write_index(self.vector_index, index_file)
            logger.info(f"Saved vector index to {index_file} with {self.vector_index.ntotal} vectors")
        except Exception as e:
            logger.error(f"Error saving vector index: {e}")
    
    async def index_content(
        self, 
        cid: str, 
        metadata: ContentMetadata,
        extract_text: bool = True,
        create_embedding: bool = True,
        content_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Index content metadata and optionally extract text for search.
        
        Args:
            cid: Content ID
            metadata: Content metadata
            extract_text: Whether to extract text for search
            create_embedding: Whether to create a vector embedding
            content_data: Optional content data (to avoid fetching from IPFS)
            
        Returns:
            Dict with indexing status
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if content already indexed
            cursor.execute('SELECT cid FROM content_metadata WHERE cid = ?', (cid,))
            existing = cursor.fetchone()
            
            # Prepare metadata
            indexed_at = time.time()
            
            # Convert tags list to JSON string
            tags_json = json.dumps(metadata.tags) if metadata.tags else None
            
            # Convert extra dict to JSON string
            extra_json = json.dumps(metadata.extra) if metadata.extra else None
            
            if existing:
                # Update existing metadata
                cursor.execute('''
                UPDATE content_metadata SET
                    name = ?,
                    description = ?,
                    tags = ?,
                    content_type = ?,
                    size = ?,
                    created = ?,
                    author = ?,
                    license = ?,
                    extra = ?,
                    indexed_at = ?
                WHERE cid = ?
                ''', (
                    metadata.name,
                    metadata.description,
                    tags_json,
                    metadata.content_type,
                    metadata.size,
                    metadata.created or indexed_at,
                    metadata.author,
                    metadata.license,
                    extra_json,
                    indexed_at,
                    cid
                ))
                
                # Delete existing tags
                cursor.execute('DELETE FROM content_tags WHERE cid = ?', (cid,))
            else:
                # Insert new metadata
                cursor.execute('''
                INSERT INTO content_metadata (
                    cid, name, description, tags, content_type, size,
                    created, author, license, extra, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    cid,
                    metadata.name,
                    metadata.description,
                    tags_json,
                    metadata.content_type,
                    metadata.size,
                    metadata.created or indexed_at,
                    metadata.author,
                    metadata.license,
                    extra_json,
                    indexed_at
                ))
            
            # Insert tags
            if metadata.tags:
                for tag in metadata.tags:
                    cursor.execute('INSERT INTO content_tags (cid, tag) VALUES (?, ?)', (cid, tag))
            
            # Commit metadata changes
            conn.commit()
            
            # Extract text if requested
            text_extracted = False
            if extract_text:
                text_extracted = await self._extract_text(cid, cursor, content_data=content_data)
            
            # Create embedding if requested
            vector_embedded = False
            if create_embedding and SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE and self.embedding_model:
                # Get text for embedding
                cursor.execute('SELECT text FROM content_text WHERE cid = ?', (cid,))
                text_row = cursor.fetchone()
                
                if text_row and text_row['text']:
                    vector_embedded = await self._create_embedding(cid, text_row['text'], cursor)
            
            # Update extraction status
            cursor.execute('''
            UPDATE content_metadata SET
                text_extracted = ?,
                vector_embedded = ?
            WHERE cid = ?
            ''', (
                text_extracted,
                vector_embedded,
                cid
            ))
            
            # Commit final changes
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "cid": cid,
                "indexed": True,
                "text_extracted": text_extracted,
                "vector_embedded": vector_embedded,
                "indexed_at": indexed_at
            }
            
        except Exception as e:
            logger.error(f"Error indexing content {cid}: {e}")
            # Ensure connection is closed
            try:
                conn.close()
            except:
                pass
            
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }
    
    async def _extract_text(
        self,
        cid: str,
        cursor: sqlite3.Cursor,
        content_data: Optional[bytes] = None
    ) -> bool:
        """
        Extract text from content for search indexing.
        
        Args:
            cid: Content ID
            cursor: Database cursor
            content_data: Optional content data (to avoid fetching from IPFS)
            
        Returns:
            bool: True if text was extracted, False otherwise
        """
        try:
            # Get content type
            cursor.execute('SELECT content_type, size FROM content_metadata WHERE cid = ?', (cid,))
            metadata = cursor.fetchone()
            
            if not metadata or not metadata['content_type']:
                logger.warning(f"Unknown content type for CID {cid}")
                return False
            
            content_type = metadata['content_type'].lower()
            size = metadata['size'] or 0
            
            # Skip large files
            max_size = 10 * 1024 * 1024  # 10MB
            if size > max_size:
                logger.warning(f"Content too large for text extraction: {size} bytes (CID: {cid})")
                return False
            
            # Skip non-text content
            if not any(ct in content_type for ct in TEXT_CONTENT_TYPES):
                logger.debug(f"Skipping text extraction for non-text content: {content_type} (CID: {cid})")
                return False
            
            # Get content data
            text = None
            if content_data:
                # Use provided content data
                if content_type in JSON_CONTENT_TYPES:
                    # Parse JSON and extract text
                    try:
                        json_data = json.loads(content_data.decode('utf-8', errors='replace'))
                        text = self._extract_text_from_json(json_data)
                    except:
                        # Fall back to raw text
                        text = content_data.decode('utf-8', errors='replace')
                else:
                    # Use raw text
                    text = content_data.decode('utf-8', errors='replace')
            else:
                # Fetch from IPFS
                process = await asyncio.create_subprocess_exec(
                    "ipfs", "cat", cid,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.warning(f"Error fetching content for CID {cid}: {stderr.decode()}")
                    return False
                
                if content_type in JSON_CONTENT_TYPES:
                    # Parse JSON and extract text
                    try:
                        json_data = json.loads(stdout.decode('utf-8', errors='replace'))
                        text = self._extract_text_from_json(json_data)
                    except:
                        # Fall back to raw text
                        text = stdout.decode('utf-8', errors='replace')
                else:
                    # Use raw text
                    text = stdout.decode('utf-8', errors='replace')
            
            if not text:
                logger.warning(f"No text extracted for CID {cid}")
                return False
            
            # Limit text length
            max_text_length = 32768  # 32KB
            if len(text) > max_text_length:
                text = text[:max_text_length]
            
            # Calculate text hash for change detection
            text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
            
            # Get name and description for FTS
            cursor.execute('SELECT name, description, tags FROM content_metadata WHERE cid = ?', (cid,))
            meta = cursor.fetchone()
            
            name = meta['name'] or ""
            description = meta['description'] or ""
            tags_json = meta['tags'] or "[]"
            tags = json.loads(tags_json) if tags_json else []
            tags_str = " ".join(tags) if tags else ""
            
            # Check if text already exists
            cursor.execute('SELECT text_hash FROM content_text WHERE cid = ?', (cid,))
            existing = cursor.fetchone()
            
            extracted_at = time.time()
            
            if existing:
                # Skip if hash matches
                if existing['text_hash'] == text_hash:
                    logger.debug(f"Text unchanged for CID {cid}")
                    return True
                
                # Update text
                cursor.execute('''
                UPDATE content_text SET
                    text = ?,
                    text_hash = ?,
                    extracted_at = ?
                WHERE cid = ?
                ''', (
                    text,
                    text_hash,
                    extracted_at,
                    cid
                ))
                
                # Update FTS index
                cursor.execute('''
                UPDATE content_fts SET
                    name = ?,
                    description = ?,
                    tags = ?,
                    text = ?
                WHERE cid = ?
                ''', (
                    name,
                    description,
                    tags_str,
                    text,
                    cid
                ))
            else:
                # Insert text
                cursor.execute('''
                INSERT INTO content_text (
                    cid, text, text_hash, extracted_at
                ) VALUES (?, ?, ?, ?)
                ''', (
                    cid,
                    text,
                    text_hash,
                    extracted_at
                ))
                
                # Insert into FTS index
                cursor.execute('''
                INSERT INTO content_fts (
                    cid, name, description, tags, text
                ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    cid,
                    name,
                    description,
                    tags_str,
                    text
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Error extracting text for CID {cid}: {e}")
            return False
    
    def _extract_text_from_json(self, json_data: Any, max_depth: int = 3) -> str:
        """
        Extract text from JSON data.
        
        Args:
            json_data: JSON data
            max_depth: Maximum recursion depth
            
        Returns:
            Extracted text
        """
        if max_depth <= 0:
            return ""
        
        result = []
        
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                result.append(str(key))
                if isinstance(value, (dict, list)):
                    result.append(self._extract_text_from_json(value, max_depth - 1))
                elif isinstance(value, (str, int, float, bool)):
                    result.append(str(value))
        elif isinstance(json_data, list):
            for item in json_data:
                if isinstance(item, (dict, list)):
                    result.append(self._extract_text_from_json(item, max_depth - 1))
                elif isinstance(item, (str, int, float, bool)):
                    result.append(str(item))
        elif isinstance(json_data, (str, int, float, bool)):
            result.append(str(json_data))
        
        return " ".join(result)
    
    async def _create_embedding(
        self,
        cid: str,
        text: str,
        cursor: sqlite3.Cursor
    ) -> bool:
        """
        Create a vector embedding for text.
        
        Args:
            cid: Content ID
            text: Text to embed
            cursor: Database cursor
            
        Returns:
            bool: True if embedding was created, False otherwise
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
            return False
        
        if not self.embedding_model or not self.vector_index:
            return False
        
        try:
            # Create embedding
            embedding = self.embedding_model.encode(text, show_progress_bar=False)
            
            # Normalize for cosine similarity
            faiss.normalize_L2(np.expand_dims(embedding, axis=0))
            
            # Check if vector already exists
            cursor.execute('SELECT vector_id FROM vector_mapping WHERE cid = ?', (cid,))
            existing = cursor.fetchone()
            
            embedded_at = time.time()
            
            if existing:
                # Replace existing vector
                vector_id = existing['vector_id']
                self.vector_index.remove_ids(np.array([vector_id], dtype=np.int64))
            else:
                # Generate new ID (use the current index size)
                vector_id = self.vector_index.ntotal
            
            # Add vector to index
            self.vector_index.add(np.expand_dims(embedding, axis=0))
            
            # Update database mapping
            if existing:
                cursor.execute('''
                UPDATE vector_mapping SET
                    embedded_at = ?
                WHERE cid = ?
                ''', (
                    embedded_at,
                    cid
                ))
            else:
                cursor.execute('''
                INSERT INTO vector_mapping (
                    cid, vector_id, embedded_at
                ) VALUES (?, ?, ?)
                ''', (
                    cid,
                    vector_id,
                    embedded_at
                ))
            
            # Save index
            self._save_vector_index()
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating embedding for CID {cid}: {e}")
            return False
    
    async def remove_content(self, cid: str) -> Dict[str, Any]:
        """
        Remove content from the search index.
        
        Args:
            cid: Content ID
            
        Returns:
            Dict with removal status
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if content is indexed
            cursor.execute('SELECT cid FROM content_metadata WHERE cid = ?', (cid,))
            existing = cursor.fetchone()
            
            if not existing:
                conn.close()
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not found in index"
                }
            
            # Check if content has a vector embedding
            cursor.execute('SELECT vector_id FROM vector_mapping WHERE cid = ?', (cid,))
            vector_mapping = cursor.fetchone()
            
            if vector_mapping and self.vector_index:
                # Remove vector from index
                vector_id = vector_mapping['vector_id']
                try:
                    self.vector_index.remove_ids(np.array([vector_id], dtype=np.int64))
                    self._save_vector_index()
                except Exception as e:
                    logger.error(f"Error removing vector for CID {cid}: {e}")
            
            # Delete from database
            cursor.execute('DELETE FROM content_metadata WHERE cid = ?', (cid,))
            
            # Commit changes
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "cid": cid,
                "removed": True
            }
            
        except Exception as e:
            logger.error(f"Error removing content {cid}: {e}")
            # Ensure connection is closed
            try:
                conn.close()
            except:
                pass
            
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }
    
    async def search(self, query: SearchQuery) -> Dict[str, Any]:
        """
        Search indexed content.
        
        Args:
            query: Search query parameters
            
        Returns:
            Dict with search results
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Determine search type
            has_text_query = query.query_text and len(query.query_text.strip()) > 0
            do_vector_search = query.vector_search and has_text_query and self.embedding_model and self.vector_index
            do_text_search = has_text_query
            
            # Start with an empty result set
            results = []
            
            # Track scores for hybrid search
            scores = {}
            
            # Vector search
            if do_vector_search:
                vector_results = await self._vector_search(query.query_text, cursor, query.max_results)
                
                # Add scores for hybrid search
                for result in vector_results:
                    cid = result["cid"]
                    score = result["score"]
                    scores[cid] = score
                
                # If not doing hybrid search, return vector results directly
                if not query.hybrid_search and not do_text_search:
                    # Apply filters
                    filtered_results = await self._apply_filters(
                        vector_results, 
                        query.metadata_filters,
                        query.content_types,
                        query.tags,
                        cursor
                    )
                    
                    # Close connection
                    conn.close()
                    
                    return {
                        "success": True,
                        "query": query.query_text,
                        "count": len(filtered_results),
                        "search_type": "vector",
                        "results": filtered_results
                    }
            
            # Text search
            if do_text_search:
                text_results = await self._text_search(query.query_text, cursor, query.max_results)
                
                # Add scores for hybrid search
                for result in text_results:
                    cid = result["cid"]
                    score = result["score"]
                    if cid in scores:
                        # Average scores for hybrid search
                        scores[cid] = (scores[cid] + score) / 2
                    else:
                        scores[cid] = score
                
                # If not doing hybrid search or vector search, return text results directly
                if not query.hybrid_search and not do_vector_search:
                    # Apply filters
                    filtered_results = await self._apply_filters(
                        text_results, 
                        query.metadata_filters,
                        query.content_types,
                        query.tags,
                        cursor
                    )
                    
                    # Close connection
                    conn.close()
                    
                    return {
                        "success": True,
                        "query": query.query_text,
                        "count": len(filtered_results),
                        "search_type": "text",
                        "results": filtered_results
                    }
            
            # Hybrid search - combine results
            if query.hybrid_search and scores:
                # Get all CIDs with scores
                all_cids = list(scores.keys())
                
                # Get metadata for all CIDs
                hybrid_results = []
                for cid in all_cids:
                    cursor.execute('''
                    SELECT 
                        cid, name, description, tags, content_type, size,
                        created, author, license, extra, indexed_at
                    FROM content_metadata
                    WHERE cid = ?
                    ''', (cid,))
                    
                    row = cursor.fetchone()
                    if row:
                        # Convert to dict
                        metadata = dict(row)
                        
                        # Parse JSON fields
                        if metadata["tags"]:
                            metadata["tags"] = json.loads(metadata["tags"])
                        else:
                            metadata["tags"] = []
                        
                        if metadata["extra"]:
                            metadata["extra"] = json.loads(metadata["extra"])
                        else:
                            metadata["extra"] = {}
                        
                        # Add score
                        metadata["score"] = scores[cid]
                        
                        # Add to results
                        hybrid_results.append(metadata)
                
                # Sort by score
                hybrid_results.sort(key=lambda x: x["score"], reverse=True)
                
                # Apply min score filter
                if query.min_score > 0:
                    hybrid_results = [r for r in hybrid_results if r["score"] >= query.min_score]
                
                # Apply other filters
                filtered_results = await self._apply_filters(
                    hybrid_results, 
                    query.metadata_filters,
                    query.content_types,
                    query.tags,
                    cursor
                )
                
                # Close connection
                conn.close()
                
                return {
                    "success": True,
                    "query": query.query_text,
                    "count": len(filtered_results),
                    "search_type": "hybrid",
                    "results": filtered_results
                }
            
            # If no search was performed, return empty results
            conn.close()
            
            return {
                "success": True,
                "query": query.query_text,
                "count": 0,
                "search_type": "none",
                "results": []
            }
            
        except Exception as e:
            logger.error(f"Error searching content: {e}")
            # Ensure connection is closed
            try:
                conn.close()
            except:
                pass
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _text_search(
        self,
        query_text: str,
        cursor: sqlite3.Cursor,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Perform text search.
        
        Args:
            query_text: Query text
            cursor: Database cursor
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        # Clean query for FTS
        clean_query = self._clean_fts_query(query_text)
        
        # Execute FTS query
        cursor.execute(f'''
        SELECT
            content_metadata.cid,
            content_metadata.name,
            content_metadata.description,
            content_metadata.tags,
            content_metadata.content_type,
            content_metadata.size,
            content_metadata.created,
            content_metadata.author,
            content_metadata.license,
            content_metadata.extra,
            content_metadata.indexed_at,
            content_fts.rank
        FROM
            content_fts
        JOIN
            content_metadata ON content_fts.cid = content_metadata.cid
        WHERE
            content_fts MATCH ?
        ORDER BY
            content_fts.rank
        LIMIT ?
        ''', (clean_query, max_results))
        
        # Process results
        results = []
        rows = cursor.fetchall()
        
        for row in rows:
            # Convert to dict
            result = dict(row)
            
            # Parse JSON fields
            if result["tags"]:
                result["tags"] = json.loads(result["tags"])
            else:
                result["tags"] = []
            
            if result["extra"]:
                result["extra"] = json.loads(result["extra"])
            else:
                result["extra"] = {}
            
            # Calculate score (normalize rank)
            rank = result.pop("rank", 0)
            result["score"] = 1.0 / (1.0 + rank) if rank is not None else 0.0
            
            results.append(result)
        
        return results
    
    def _clean_fts_query(self, query: str) -> str:
        """
        Clean query for FTS search.
        
        Args:
            query: Raw query string
            
        Returns:
            Cleaned query for FTS
        """
        # Split into terms and add wildcards for prefix matching
        terms = query.strip().split()
        cleaned_terms = []
        
        for term in terms:
            # Skip short terms and operators
            if len(term) < 2 or term.lower() in ("and", "or", "not"):
                cleaned_terms.append(term)
                continue
            
            # Add wildcard for prefix matching
            if not term.endswith("*"):
                term = term + "*"
            
            cleaned_terms.append(term)
        
        return " ".join(cleaned_terms)
    
    async def _vector_search(
        self,
        query_text: str,
        cursor: sqlite3.Cursor,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Perform vector search.
        
        Args:
            query_text: Query text
            cursor: Database cursor
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        if not self.embedding_model or not self.vector_index:
            return []
        
        # Create query embedding
        query_embedding = self.embedding_model.encode(query_text, show_progress_bar=False)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(np.expand_dims(query_embedding, axis=0))
        
        # Search vector index
        scores, vector_ids = self.vector_index.search(np.expand_dims(query_embedding, axis=0), k=max_results)
        
        # Flatten results
        scores = scores[0]
        vector_ids = vector_ids[0]
        
        # Get CIDs for vector IDs
        results = []
        for i, vector_id in enumerate(vector_ids):
            if vector_id == -1:  # -1 indicates no match
                continue
            
            # Get CID for vector ID
            cursor.execute('SELECT cid FROM vector_mapping WHERE vector_id = ?', (int(vector_id),))
            mapping = cursor.fetchone()
            
            if not mapping:
                continue
            
            cid = mapping['cid']
            
            # Get metadata for CID
            cursor.execute('''
            SELECT 
                cid, name, description, tags, content_type, size,
                created, author, license, extra, indexed_at
            FROM content_metadata
            WHERE cid = ?
            ''', (cid,))
            
            row = cursor.fetchone()
            if not row:
                continue
            
            # Convert to dict
            result = dict(row)
            
            # Parse JSON fields
            if result["tags"]:
                result["tags"] = json.loads(result["tags"])
            else:
                result["tags"] = []
            
            if result["extra"]:
                result["extra"] = json.loads(result["extra"])
            else:
                result["extra"] = {}
            
            # Add score (normalize to 0-1 range)
            score = float(scores[i])
            result["score"] = max(0.0, min(1.0, (score + 1.0) / 2.0))
            
            results.append(result)
        
        return results
    
    async def _apply_filters(
        self,
        results: List[Dict[str, Any]],
        metadata_filters: Optional[Dict[str, Any]],
        content_types: Optional[List[str]],
        tags: Optional[List[str]],
        cursor: sqlite3.Cursor
    ) -> List[Dict[str, Any]]:
        """
        Apply filters to search results.
        
        Args:
            results: Search results
            metadata_filters: Metadata filters
            content_types: Content type filters
            tags: Tag filters
            cursor: Database cursor
            
        Returns:
            Filtered search results
        """
        filtered_results = results.copy()
        
        # Apply content type filter
        if content_types:
            filtered_results = [r for r in filtered_results if r["content_type"] in content_types]
        
        # Apply tag filters
        if tags:
            # Get CIDs with all required tags
            tag_filtered_cids = set()
            for tag in tags:
                cursor.execute('SELECT cid FROM content_tags WHERE tag = ?', (tag,))
                rows = cursor.fetchall()
                tag_cids = {row['cid'] for row in rows}
                
                if not tag_filtered_cids:
                    tag_filtered_cids = tag_cids
                else:
                    tag_filtered_cids &= tag_cids
            
            # Filter results
            filtered_results = [r for r in filtered_results if r["cid"] in tag_filtered_cids]
        
        # Apply metadata filters
        if metadata_filters:
            for key, value in metadata_filters.items():
                if key == "size_min":
                    filtered_results = [r for r in filtered_results if r["size"] is None or r["size"] >= value]
                elif key == "size_max":
                    filtered_results = [r for r in filtered_results if r["size"] is None or r["size"] <= value]
                elif key == "created_after":
                    filtered_results = [r for r in filtered_results if r["created"] is None or r["created"] >= value]
                elif key == "created_before":
                    filtered_results = [r for r in filtered_results if r["created"] is None or r["created"] <= value]
                elif key == "author":
                    filtered_results = [r for r in filtered_results if r["author"] == value]
                elif key == "license":
                    filtered_results = [r for r in filtered_results if r["license"] == value]
                elif key.startswith("extra.") and len(key) > 6:
                    # Filter on extra fields
                    extra_key = key[6:]
                    filtered_results = [
                        r for r in filtered_results
                        if r["extra"] and extra_key in r["extra"] and r["extra"][extra_key] == value
                    ]
        
        return filtered_results
    
    async def get_content_metadata(self, cid: str) -> Dict[str, Any]:
        """
        Get metadata for indexed content.
        
        Args:
            cid: Content ID
            
        Returns:
            Dict with content metadata
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get metadata
            cursor.execute('''
            SELECT 
                cid, name, description, tags, content_type, size,
                created, author, license, extra, indexed_at,
                text_extracted, vector_embedded
            FROM content_metadata
            WHERE cid = ?
            ''', (cid,))
            
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return {
                    "success": False,
                    "cid": cid,
                    "error": "Content not found in index"
                }
            
            # Convert to dict
            metadata = dict(row)
            
            # Parse JSON fields
            if metadata["tags"]:
                metadata["tags"] = json.loads(metadata["tags"])
            else:
                metadata["tags"] = []
            
            if metadata["extra"]:
                metadata["extra"] = json.loads(metadata["extra"])
            else:
                metadata["extra"] = {}
            
            # Close connection
            conn.close()
            
            return {
                "success": True,
                "cid": cid,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata for CID {cid}: {e}")
            # Ensure connection is closed
            try:
                conn.close()
            except:
                pass
            
            return {
                "success": False,
                "cid": cid,
                "error": str(e)
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get search service statistics.
        
        Returns:
            Dict with search service statistics
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total content count
            cursor.execute('SELECT COUNT(*) FROM content_metadata')
            total_content = cursor.fetchone()[0]
            
            # Get text extraction count
            cursor.execute('SELECT COUNT(*) FROM content_metadata WHERE text_extracted = 1')
            text_extracted = cursor.fetchone()[0]
            
            # Get vector embedding count
            cursor.execute('SELECT COUNT(*) FROM content_metadata WHERE vector_embedded = 1')
            vector_embedded = cursor.fetchone()[0]
            
            # Get content by type counts
            cursor.execute('''
            SELECT content_type, COUNT(*) as count
            FROM content_metadata
            GROUP BY content_type
            ''')
            
            content_types = {}
            for row in cursor.fetchall():
                content_type, count = row
                if content_type:
                    content_types[content_type] = count
            
            # Get tag counts
            cursor.execute('''
            SELECT tag, COUNT(*) as count
            FROM content_tags
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 50
            ''')
            
            tags = {}
            for row in cursor.fetchall():
                tag, count = row
                tags[tag] = count
            
            # Get database size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            # Get vector index size
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            vector_index_size = os.path.getsize(index_file) if os.path.exists(index_file) else 0
            
            # Get vector index count
            vector_count = self.vector_index.ntotal if self.vector_index else 0
            
            # Close connection
            conn.close()
            
            return {
                "success": True,
                "stats": {
                    "total_content": total_content,
                    "text_extracted": text_extracted,
                    "vector_embedded": vector_embedded,
                    "content_types": content_types,
                    "tags": tags,
                    "database_size": db_size,
                    "vector_index_size": vector_index_size,
                    "vector_count": vector_count,
                    "vector_dimension": self.vector_dimension,
                    "embedding_model": self.embedding_model_name if self.embedding_model else None,
                    "vector_search_available": FAISS_AVAILABLE and self.vector_index is not None
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting search service statistics: {e}")
            # Ensure connection is closed
            try:
                conn.close()
            except:
                pass
            
            return {
                "success": False,
                "error": str(e)
            }

# Create FastAPI router for search endpoints

def create_search_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with search endpoints.
    
    Args:
        api_prefix: The API prefix for the endpoints
        
    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/search")
    search_service = ContentSearchService()
    
    @router.get("/status")
    async def search_status():
        """Get search service status."""
        stats = await search_service.get_stats()
        
        # Add feature availability
        features = {
            "text_search": True,
            "vector_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "hybrid_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "content_extraction": True,
            "metadata_filtering": True
        }
        
        if stats["success"]:
            return {
                "success": True,
                "status": "available",
                "features": features,
                "stats": stats["stats"]
            }
        else:
            return {
                "success": False,
                "status": "error",
                "features": features,
                "error": stats.get("error", "Unknown error")
            }
    
    @router.post("/index")
    async def index_content(
        cid: str = Form(...),
        name: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None),
        content_type: Optional[str] = Form(None),
        size: Optional[int] = Form(None),
        created: Optional[float] = Form(None),
        author: Optional[str] = Form(None),
        license: Optional[str] = Form(None),
        extra: Optional[str] = Form(None),
        extract_text: bool = Form(True),
        create_embedding: bool = Form(True)
    ):
        """
        Index content metadata for search.
        
        Args:
            cid: Content ID
            name: Content name
            description: Content description
            tags: JSON array of tags
            content_type: Content MIME type
            size: Content size in bytes
            created: Content creation timestamp
            author: Content author
            license: Content license
            extra: JSON object with additional metadata
            extract_text: Whether to extract text for search
            create_embedding: Whether to create a vector embedding
        """
        # Parse tags
        parsed_tags = None
        if tags:
            try:
                parsed_tags = json.loads(tags)
                if not isinstance(parsed_tags, list):
                    parsed_tags = [str(parsed_tags)]
            except:
                parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Parse extra
        parsed_extra = None
        if extra:
            try:
                parsed_extra = json.loads(extra)
                if not isinstance(parsed_extra, dict):
                    parsed_extra = {"value": parsed_extra}
            except:
                parsed_extra = {"text": extra}
        
        # Create metadata object
        metadata = ContentMetadata(
            name=name,
            description=description,
            tags=parsed_tags,
            content_type=content_type,
            size=size,
            created=created,
            author=author,
            license=license,
            extra=parsed_extra
        )
        
        # Index content
        result = await search_service.index_content(
            cid,
            metadata,
            extract_text=extract_text,
            create_embedding=create_embedding
        )
        
        return result
    
    @router.post("/query")
    async def search_content(query: SearchQuery):
        """
        Search indexed content.
        
        Args:
            query: Search query parameters
        """
        result = await search_service.search(query)
        return result
    
    @router.get("/metadata/{cid}")
    async def get_metadata(cid: str):
        """
        Get metadata for indexed content.
        
        Args:
            cid: Content ID
        """
        result = await search_service.get_content_metadata(cid)
        return result
    
    @router.delete("/remove/{cid}")
    async def remove_content(cid: str):
        """
        Remove content from the search index.
        
        Args:
            cid: Content ID
        """
        result = await search_service.remove_content(cid)
        return result
    
    @router.post("/vector")
    async def vector_search(query: VectorQuery):
        """
        Perform vector search.
        
        Args:
            query: Vector search query
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
            return {
                "success": False,
                "error": "Vector search is not available. Install required dependencies."
            }
        
        # Create SearchQuery
        search_query = SearchQuery(
            query_text=query.text,
            metadata_filters=query.metadata_filters,
            vector_search=True,
            hybrid_search=False,
            min_score=query.min_score,
            max_results=query.max_results
        )
        
        result = await search_service.search(search_query)
        return result
    
    @router.post("/hybrid")
    async def hybrid_search(query: SearchQuery):
        """
        Perform hybrid search (text + vector).
        
        Args:
            query: Search query parameters
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
            return {
                "success": False,
                "error": "Hybrid search is not available. Install required dependencies."
            }
        
        # Force hybrid search
        query.hybrid_search = True
        query.vector_search = True
        
        result = await search_service.search(query)
        return result
    
    return router