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
from pydantic import BaseModel, Field
import aiofiles
import anyio # Import anyio

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

# --- Database Helper Functions (for anyio.to_thread) ---

def _db_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def _db_execute(conn: sqlite3.Connection, sql: str, params: tuple = ()):
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return cursor

def _db_commit(conn: sqlite3.Connection):
    conn.commit()

def _db_close(conn: sqlite3.Connection):
    conn.close()

def _db_fetchone(cursor: sqlite3.Cursor):
    return cursor.fetchone()

def _db_fetchall(cursor: sqlite3.Cursor):
    return cursor.fetchall()

# --- FAISS Helper Functions (for anyio.to_thread) ---

def _faiss_read_index(index_file: str) -> Optional[Any]:
    if FAISS_AVAILABLE and os.path.exists(index_file):
        try:
            return faiss.read_index(index_file)
        except Exception as e:
            logger.error(f"Error loading FAISS index from {index_file}: {e}")
    return None

def _faiss_write_index(index: Any, index_file: str):
    if FAISS_AVAILABLE and index is not None:
        try:
            faiss.write_index(index, index_file)
        except Exception as e:
            logger.error(f"Error writing FAISS index to {index_file}: {e}")

def _faiss_add_vector(index: Any, vector: np.ndarray):
    if FAISS_AVAILABLE and index is not None:
        index.add(vector)

def _faiss_remove_ids(index: Any, ids: np.ndarray):
     if FAISS_AVAILABLE and index is not None:
        try:
            index.remove_ids(ids)
        except Exception as e:
            logger.error(f"Error removing IDs from FAISS index: {e}") # FAISS might error if ID not found

def _faiss_search(index: Any, query_vector: np.ndarray, k: int):
    if FAISS_AVAILABLE and index is not None:
        return index.search(query_vector, k=k)
    return (np.array([[]]), np.array([[]])) # Return empty arrays if FAISS unavailable

# --- ContentSearchService ---

class ContentSearchService:
    """
    Service for content indexing and search.

    This class provides functionality for indexing IPFS content metadata,
    extracting text for search, and performing hybrid search operations.
    Uses AnyIO for database operations.
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        vector_index_path: str = DEFAULT_INDEX_PATH,
        embedding_model_name: str = DEFAULT_MODEL_NAME,
        vector_dimension: int = 384  # Default for all-MiniLM-L6-v2
    ):
        self.db_path = db_path
        self.vector_index_path = vector_index_path
        self.embedding_model_name = embedding_model_name
        self.vector_dimension = vector_dimension
        self.db_lock = anyio.Lock() # Lock for database operations

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(vector_index_path, exist_ok=True)

        self.embedding_model = None
        self.vector_index = None
        # Initialization moved to async method

    async def initialize(self):
        """Asynchronously initialize database and vector index."""
        await self._init_database()

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Loading model can be blocking, run in thread
                self.embedding_model = await anyio.to_thread.run_sync(SentenceTransformer, self.embedding_model_name)
                logger.info(f"Loaded embedding model: {self.embedding_model_name}")
            except Exception as e:
                logger.error(f"Error loading embedding model: {e}")

        if FAISS_AVAILABLE:
            await self._init_vector_index()

    async def _init_database(self):
        """Initialize the SQLite database asynchronously."""
        try:
            async with self.db_lock:
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                try:
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        CREATE TABLE IF NOT EXISTS content_metadata (
                            cid TEXT PRIMARY KEY, name TEXT, description TEXT, tags TEXT,
                            content_type TEXT, size INTEGER, created REAL, author TEXT,
                            license TEXT, extra TEXT, indexed_at REAL,
                            text_extracted BOOLEAN DEFAULT 0, vector_embedded BOOLEAN DEFAULT 0
                        )
                        '''
                    )
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        CREATE TABLE IF NOT EXISTS content_text (
                            cid TEXT PRIMARY KEY, text TEXT, text_hash TEXT, extracted_at REAL,
                            FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
                        )
                        '''
                    )
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        CREATE TABLE IF NOT EXISTS vector_mapping (
                            cid TEXT PRIMARY KEY, vector_id INTEGER, embedded_at REAL,
                            FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
                        )
                        '''
                    )
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        CREATE TABLE IF NOT EXISTS content_tags (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, cid TEXT, tag TEXT,
                            FOREIGN KEY (cid) REFERENCES content_metadata (cid) ON DELETE CASCADE
                        )
                        '''
                    )
                    await anyio.to_thread.run_sync(_db_execute, conn, 'CREATE INDEX IF NOT EXISTS idx_content_tags_tag ON content_tags (tag)')
                    await anyio.to_thread.run_sync(_db_execute, conn, 'CREATE INDEX IF NOT EXISTS idx_content_tags_cid ON content_tags (cid)')
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                            cid UNINDEXED, name, description, tags, text,
                            content='content_text', content_rowid='rowid'
                        )
                        '''
                    )
                    await anyio.to_thread.run_sync(_db_commit, conn)
                finally:
                    await anyio.to_thread.run_sync(_db_close, conn)
            logger.info(f"Initialized search database at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    async def _init_vector_index(self):
        """Initialize the FAISS vector index asynchronously."""
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available, vector search disabled")
            return

        try:
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            # Reading index can be blocking
            self.vector_index = await anyio.to_thread.run_sync(_faiss_read_index, index_file)

            if self.vector_index:
                logger.info(f"Loaded vector index from {index_file} with {self.vector_index.ntotal} vectors")
            else:
                # Create new index (CPU intensive part is minor here)
                self.vector_index = faiss.IndexFlatIP(self.vector_dimension)
                logger.info(f"Created new vector index with dimension {self.vector_dimension}")
                # Saving index can be blocking
                await anyio.to_thread.run_sync(_faiss_write_index, self.vector_index, index_file)
        except Exception as e:
            logger.error(f"Error initializing vector index: {e}")

    async def _save_vector_index(self):
        """Save the vector index to disk asynchronously."""
        if not FAISS_AVAILABLE or self.vector_index is None:
            return
        try:
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            # Writing index can be blocking
            await anyio.to_thread.run_sync(_faiss_write_index, self.vector_index, index_file)
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
        """Index content metadata and optionally extract text/embedding."""
        conn = None
        try:
            async with self.db_lock:
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                cursor = await anyio.to_thread.run_sync(conn.cursor) # Get cursor in thread

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT cid FROM content_metadata WHERE cid = ?', (cid,))
                existing = await anyio.to_thread.run_sync(_db_fetchone, cursor)

                indexed_at = time.time()
                tags_json = json.dumps(metadata.tags) if metadata.tags else None
                extra_json = json.dumps(metadata.extra) if metadata.extra else None

                if existing:
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        UPDATE content_metadata SET name = ?, description = ?, tags = ?, content_type = ?, size = ?,
                        created = ?, author = ?, license = ?, extra = ?, indexed_at = ? WHERE cid = ?
                        ''',
                        (metadata.name, metadata.description, tags_json, metadata.content_type, metadata.size,
                         metadata.created or indexed_at, metadata.author, metadata.license, extra_json, indexed_at, cid)
                    )
                    await anyio.to_thread.run_sync(_db_execute, conn, 'DELETE FROM content_tags WHERE cid = ?', (cid,))
                else:
                    await anyio.to_thread.run_sync(
                        _db_execute, conn,
                        '''
                        INSERT INTO content_metadata (cid, name, description, tags, content_type, size, created, author, license, extra, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (cid, metadata.name, metadata.description, tags_json, metadata.content_type, metadata.size,
                         metadata.created or indexed_at, metadata.author, metadata.license, extra_json, indexed_at)
                    )

                if metadata.tags:
                    tag_data = [(cid, tag) for tag in metadata.tags]
                    await anyio.to_thread.run_sync(conn.executemany, 'INSERT INTO content_tags (cid, tag) VALUES (?, ?)', tag_data)

                await anyio.to_thread.run_sync(_db_commit, conn)

                # --- Text Extraction & Embedding (Potentially move to background tasks) ---
                text_extracted = False
                extracted_text = None
                if extract_text:
                    extracted_text, text_extracted = await self._extract_text(cid, conn, content_data=content_data) # Pass conn

                vector_embedded = False
                if create_embedding and text_extracted and extracted_text and SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE and self.embedding_model:
                     vector_embedded = await self._create_embedding(cid, extracted_text, conn) # Pass conn

                # Update status in DB
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'UPDATE content_metadata SET text_extracted = ?, vector_embedded = ? WHERE cid = ?',
                    (text_extracted, vector_embedded, cid)
                )
                await anyio.to_thread.run_sync(_db_commit, conn)
                # --- End Background Task Section ---

            return { "success": True, "cid": cid, "indexed": True, "text_extracted": text_extracted, "vector_embedded": vector_embedded, "indexed_at": indexed_at }

        except Exception as e:
            logger.error(f"Error indexing content {cid}: {e}", exc_info=True)
            return { "success": False, "cid": cid, "error": str(e) }
        finally:
            if conn:
                await anyio.to_thread.run_sync(_db_close, conn)

    async def _extract_text(
        self,
        cid: str,
        conn: sqlite3.Connection, # Pass connection instead of cursor
        content_data: Optional[bytes] = None
    ) -> Tuple[Optional[str], bool]:
        """Extract text from content for search indexing (using AnyIO)."""
        try:
            cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT content_type, size FROM content_metadata WHERE cid = ?', (cid,))
            metadata = await anyio.to_thread.run_sync(_db_fetchone, cursor)

            if not metadata or not metadata['content_type']:
                logger.warning(f"Unknown content type for CID {cid}")
                return None, False

            content_type = metadata['content_type'].lower()
            size = metadata['size'] or 0
            max_size = 10 * 1024 * 1024
            if size > max_size:
                logger.warning(f"Content too large for text extraction: {size} bytes (CID: {cid})")
                return None, False
            if not any(ct in content_type for ct in TEXT_CONTENT_TYPES):
                logger.debug(f"Skipping text extraction for non-text content: {content_type} (CID: {cid})")
                return None, False

            text = None
            if content_data:
                # Decode and potentially parse JSON in thread
                def decode_data():
                    decoded_text = content_data.decode('utf-8', errors='replace')
                    if content_type in JSON_CONTENT_TYPES:
                        try:
                            json_data = json.loads(decoded_text)
                            return self._extract_text_from_json(json_data)
                        except: return decoded_text # Fallback
                    return decoded_text
                text = await anyio.to_thread.run_sync(decode_data)
            else:
                # Using ipfs_py client to fetch content instead of subprocess
                try:
                    # Import the ipfs_py client
                    from ipfs_kit_py.ipfs import ipfs_py
                    ipfs_client = ipfs_py()
                    
                    # Use the ipfs_cat method to retrieve content - run in thread to avoid blocking
                    def fetch_ipfs_content():
                        result = ipfs_client.ipfs_cat(cid)
                        if not result.get("success", False):
                            logger.warning(f"Error fetching content for CID {cid}: {result.get('error', 'Unknown error')}")
                            return None
                        return result.get("data", None)
                    
                    content_data = await anyio.to_thread.run_sync(fetch_ipfs_content)
                    
                    if not content_data:
                        logger.warning(f"No content retrieved for CID {cid}")
                        return None, False
                        
                    # Process the retrieved data
                    def decode_data_fetched():
                        # Handle bytes or string content
                        if isinstance(content_data, bytes):
                            decoded_text = content_data.decode('utf-8', errors='replace')
                        else:
                            decoded_text = str(content_data)
                            
                        if content_type in JSON_CONTENT_TYPES:
                            try:
                                json_data = json.loads(decoded_text)
                                return self._extract_text_from_json(json_data)
                            except:
                                return decoded_text  # Fallback
                        return decoded_text
                    
                    text = await anyio.to_thread.run_sync(decode_data_fetched)
                    
                except ImportError as e:
                    logger.warning(f"Could not import ipfs_py, falling back to subprocess: {e}")
                    # Fallback to subprocess if ipfs_py import fails
                    import subprocess
                    process = await anyio.run_process(["ipfs", "cat", cid], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout = process.stdout
                    stderr = process.stderr
                    if process.returncode != 0:
                        logger.warning(f"Error fetching content for CID {cid}: {stderr.decode()}")
                        return None, False

                    def decode_data_fallback():
                        decoded_text = stdout.decode('utf-8', errors='replace')
                        if content_type in JSON_CONTENT_TYPES:
                            try:
                                json_data = json.loads(decoded_text)
                                return self._extract_text_from_json(json_data)
                            except: return decoded_text # Fallback
                        return decoded_text
                    text = await anyio.to_thread.run_sync(decode_data_fallback)


            if not text:
                logger.warning(f"No text extracted for CID {cid}")
                return None, False

            max_text_length = 32768
            if len(text) > max_text_length: text = text[:max_text_length]

            text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()

            cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT name, description, tags FROM content_metadata WHERE cid = ?', (cid,))
            meta = await anyio.to_thread.run_sync(_db_fetchone, cursor)
            name = meta['name'] or ""
            description = meta['description'] or ""
            tags_json = meta['tags'] or "[]"
            tags = json.loads(tags_json) if tags_json else []
            tags_str = " ".join(tags) if tags else ""

            cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT text_hash FROM content_text WHERE cid = ?', (cid,))
            existing = await anyio.to_thread.run_sync(_db_fetchone, cursor)

            extracted_at = time.time()

            if existing:
                if existing['text_hash'] == text_hash:
                    logger.debug(f"Text unchanged for CID {cid}")
                    return text, True # Return existing text
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'UPDATE content_text SET text = ?, text_hash = ?, extracted_at = ? WHERE cid = ?',
                    (text, text_hash, extracted_at, cid)
                )
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'UPDATE content_fts SET name = ?, description = ?, tags = ?, text = ? WHERE cid = ?',
                    (name, description, tags_str, text, cid)
                )
            else:
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'INSERT INTO content_text (cid, text, text_hash, extracted_at) VALUES (?, ?, ?, ?)',
                    (cid, text, text_hash, extracted_at)
                )
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'INSERT INTO content_fts (cid, name, description, tags, text) VALUES (?, ?, ?, ?, ?)',
                    (cid, name, description, tags_str, text)
                )

            return text, True

        except Exception as e:
            logger.error(f"Error extracting text for CID {cid}: {e}", exc_info=True)
            return None, False

    def _extract_text_from_json(self, json_data: Any, max_depth: int = 3) -> str:
        """Extract text from JSON data (remains synchronous helper)."""
        if max_depth <= 0: return ""
        result = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                result.append(str(key))
                if isinstance(value, (dict, list)): result.append(self._extract_text_from_json(value, max_depth - 1))
                elif isinstance(value, (str, int, float, bool)): result.append(str(value))
        elif isinstance(json_data, list):
            for item in json_data:
                if isinstance(item, (dict, list)): result.append(self._extract_text_from_json(item, max_depth - 1))
                elif isinstance(item, (str, int, float, bool)): result.append(str(item))
        elif isinstance(json_data, (str, int, float, bool)): result.append(str(json_data))
        return " ".join(result)


    async def _create_embedding(
        self,
        cid: str,
        text: str,
        conn: sqlite3.Connection # Pass connection
    ) -> bool:
        """Create a vector embedding for text (using AnyIO)."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE or not self.embedding_model or not self.vector_index:
            return False

        try:
            # Embedding creation can be CPU bound, run in thread
            def encode_text():
                embedding = self.embedding_model.encode(text, show_progress_bar=False)
                faiss.normalize_L2(np.expand_dims(embedding, axis=0))
                return embedding
            embedding = await anyio.to_thread.run_sync(encode_text)

            # Note: We don't acquire the lock here because the caller (index_content) 
            # already holds it. This prevents the "Attempted to acquire an already held Lock" error
            
            cursor = await anyio.to_thread.run_sync(conn.cursor)
            cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT vector_id FROM vector_mapping WHERE cid = ?', (cid,))
            existing = await anyio.to_thread.run_sync(_db_fetchone, cursor)

            embedded_at = time.time()
            vector_id_to_use = -1

            if existing:
                vector_id = existing['vector_id']
                # Removing from FAISS can be blocking
                await anyio.to_thread.run_sync(_faiss_remove_ids, self.vector_index, np.array([vector_id], dtype=np.int64))
                vector_id_to_use = vector_id # Reuse ID if possible, though FAISS might reassign
            else:
                vector_id_to_use = self.vector_index.ntotal # Use next available ID

            # Adding to FAISS can be blocking
            await anyio.to_thread.run_sync(_faiss_add_vector, self.vector_index, np.expand_dims(embedding, axis=0))
            # Get the actual ID assigned by FAISS (might differ from ntotal if removals happened)
            actual_vector_id = self.vector_index.ntotal - 1

            if existing:
                 await anyio.to_thread.run_sync(
                     _db_execute, conn,
                     'UPDATE vector_mapping SET vector_id = ?, embedded_at = ? WHERE cid = ?',
                     (actual_vector_id, embedded_at, cid)
                 )
            else:
                await anyio.to_thread.run_sync(
                    _db_execute, conn,
                    'INSERT INTO vector_mapping (cid, vector_id, embedded_at) VALUES (?, ?, ?)',
                    (cid, actual_vector_id, embedded_at)
                )

            await anyio.to_thread.run_sync(_db_commit, conn)
            await self._save_vector_index() # Saving index is now async

            return True

        except Exception as e:
            logger.error(f"Error creating embedding for CID {cid}: {e}", exc_info=True)
            return False

    async def remove_content(self, cid: str) -> Dict[str, Any]:
        """Remove content from the search index (using AnyIO)."""
        conn = None
        try:
            async with self.db_lock:
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                cursor = await anyio.to_thread.run_sync(conn.cursor)

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT cid FROM content_metadata WHERE cid = ?', (cid,))
                existing = await anyio.to_thread.run_sync(_db_fetchone, cursor)

                if not existing:
                    return { "success": False, "cid": cid, "error": "Content not found in index" }

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT vector_id FROM vector_mapping WHERE cid = ?', (cid,))
                vector_mapping = await anyio.to_thread.run_sync(_db_fetchone, cursor)

                if vector_mapping and self.vector_index:
                    vector_id = vector_mapping['vector_id']
                    await anyio.to_thread.run_sync(_faiss_remove_ids, self.vector_index, np.array([vector_id], dtype=np.int64))
                    await self._save_vector_index()

                await anyio.to_thread.run_sync(_db_execute, conn, 'DELETE FROM content_metadata WHERE cid = ?', (cid,))
                # Cascading delete should handle content_text, vector_mapping, content_tags

                await anyio.to_thread.run_sync(_db_commit, conn)

            return { "success": True, "cid": cid, "removed": True }

        except Exception as e:
            logger.error(f"Error removing content {cid}: {e}", exc_info=True)
            return { "success": False, "cid": cid, "error": str(e) }
        finally:
             if conn: await anyio.to_thread.run_sync(_db_close, conn)

    async def search(self, query: SearchQuery) -> Dict[str, Any]:
        """Search indexed content (using AnyIO)."""
        conn = None
        try:
            async with self.db_lock: # Use lock for read operations too for simplicity
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                cursor = await anyio.to_thread.run_sync(conn.cursor)

                has_text_query = query.query_text and len(query.query_text.strip()) > 0
                do_vector_search = query.vector_search and has_text_query and self.embedding_model and self.vector_index
                do_text_search = has_text_query

                scores = {}
                vector_results_meta = []
                text_results_meta = []

                if do_vector_search:
                    vector_results_meta = await self._vector_search(query.query_text, conn, query.max_results) # Pass conn
                    for result in vector_results_meta: scores[result["cid"]] = result["score"]

                if do_text_search:
                    text_results_meta = await self._text_search(query.query_text, conn, query.max_results) # Pass conn
                    for result in text_results_meta:
                        cid = result["cid"]
                        score = result["score"]
                        scores[cid] = (scores.get(cid, 0) + score) / (2 if cid in scores else 1) # Average if hybrid

                # Combine results based on search type
                combined_results_meta = []
                if query.hybrid_search:
                    all_cids = set(scores.keys())
                    # Fetch metadata for all relevant CIDs
                    if all_cids:
                         placeholders = ','.join('?' * len(all_cids))
                         sql = f'''SELECT cid, name, description, tags, content_type, size, created, author, license, extra, indexed_at
                                   FROM content_metadata WHERE cid IN ({placeholders})'''
                         cursor = await anyio.to_thread.run_sync(_db_execute, conn, sql, tuple(all_cids))
                         rows = await anyio.to_thread.run_sync(_db_fetchall, cursor)
                         for row in rows:
                             meta = dict(row)
                             meta["score"] = scores.get(meta["cid"], 0.0) # Add score
                             combined_results_meta.append(meta)
                    combined_results_meta.sort(key=lambda x: x["score"], reverse=True)

                elif do_vector_search:
                    combined_results_meta = vector_results_meta
                elif do_text_search:
                    combined_results_meta = text_results_meta

                # Apply filters
                filtered_results = await self._apply_filters(
                    combined_results_meta, query.metadata_filters, query.content_types, query.tags, conn # Pass conn
                )

                # Apply min score and limit
                final_results = [r for r in filtered_results if r.get("score", 0.0) >= query.min_score][:query.max_results]

                # Parse JSON fields in final results
                for r in final_results:
                    r["tags"] = json.loads(r["tags"]) if r.get("tags") else []
                    r["extra"] = json.loads(r["extra"]) if r.get("extra") else {}

            search_type = "hybrid" if query.hybrid_search else ("vector" if do_vector_search else ("text" if do_text_search else "none"))
            return { "success": True, "query": query.query_text, "count": len(final_results), "search_type": search_type, "results": final_results }

        except Exception as e:
            logger.error(f"Error searching content: {e}", exc_info=True)
            return { "success": False, "error": str(e) }
        finally:
            if conn: await anyio.to_thread.run_sync(_db_close, conn)

    async def _text_search(
        self, query_text: str, conn: sqlite3.Connection, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform text search (using AnyIO)."""
        clean_query = self._clean_fts_query(query_text)
        
        # Fix SQL error: use the table name in the WHERE clause correctly for FTS5
        sql = f'''
            SELECT 
                m.cid, m.name, m.description, m.tags, m.content_type, 
                m.size, m.created, m.author, m.license, m.extra, 
                m.indexed_at, fts.rank
            FROM 
                content_fts AS fts 
            JOIN 
                content_metadata AS m ON fts.cid = m.cid
            WHERE 
                content_fts MATCH ? 
            ORDER BY 
                rank 
            LIMIT ?
        '''
        
        cursor = await anyio.to_thread.run_sync(_db_execute, conn, sql, (clean_query, max_results))
        rows = await anyio.to_thread.run_sync(_db_fetchall, cursor)

        results = []
        for row in rows:
            result = dict(row)
            rank = result.pop("rank", 0)
            result["score"] = 1.0 / (1.0 + rank) if rank is not None else 0.0
            # JSON parsing will happen in the main search function
            results.append(result)
        return results

    def _clean_fts_query(self, query: str) -> str:
        """Clean query for FTS search (remains synchronous helper)."""
        terms = query.strip().split()
        cleaned_terms = []
        for term in terms:
            if len(term) < 2 or term.lower() in ("and", "or", "not"):
                cleaned_terms.append(term)
                continue
            if not term.endswith("*"): term = term + "*"
            cleaned_terms.append(term)
        return " ".join(cleaned_terms)


    async def _vector_search(
        self, query_text: str, conn: sqlite3.Connection, max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Perform vector search (using AnyIO)."""
        if not self.embedding_model or not self.vector_index: return []

        # Embedding can be CPU bound
        def encode_query():
            query_embedding = self.embedding_model.encode(query_text, show_progress_bar=False)
            faiss.normalize_L2(np.expand_dims(query_embedding, axis=0))
            return query_embedding
        query_embedding = await anyio.to_thread.run_sync(encode_query)

        # Searching index can be CPU bound
        scores, vector_ids = await anyio.to_thread.run_sync(
            _faiss_search, self.vector_index, np.expand_dims(query_embedding, axis=0), max_results
        )
        scores = scores[0]
        vector_ids = vector_ids[0]

        results = []
        if len(vector_ids) == 0 or vector_ids[0] == -1: return results # Handle empty results early

        # Fetch CIDs for vector IDs (can involve DB I/O)
        valid_ids = [int(vid) for vid in vector_ids if vid != -1]
        if not valid_ids: return results

        placeholders = ','.join('?' * len(valid_ids))
        sql = f'SELECT cid, vector_id FROM vector_mapping WHERE vector_id IN ({placeholders})'
        cursor = await anyio.to_thread.run_sync(_db_execute, conn, sql, tuple(valid_ids))
        mappings = await anyio.to_thread.run_sync(_db_fetchall, cursor)
        cid_map = {row['vector_id']: row['cid'] for row in mappings}

        # Fetch metadata for found CIDs
        found_cids = list(cid_map.values())
        if not found_cids: return results

        placeholders_cid = ','.join('?' * len(found_cids))
        sql_meta = f'''SELECT cid, name, description, tags, content_type, size, created, author, license, extra, indexed_at
                       FROM content_metadata WHERE cid IN ({placeholders_cid})'''
        cursor_meta = await anyio.to_thread.run_sync(_db_execute, conn, sql_meta, tuple(found_cids))
        meta_rows = await anyio.to_thread.run_sync(_db_fetchall, cursor_meta)
        metadata_map = {row['cid']: dict(row) for row in meta_rows}

        # Combine results
        for i, vector_id in enumerate(vector_ids):
             if vector_id == -1: continue
             cid = cid_map.get(int(vector_id))
             if cid and cid in metadata_map:
                 result = metadata_map[cid]
                 score = float(scores[i])
                 result["score"] = max(0.0, min(1.0, (score + 1.0) / 2.0)) # Normalize cosine sim
                 # JSON parsing will happen in the main search function
                 results.append(result)

        return results

    async def _apply_filters(
        self, results: List[Dict[str, Any]], metadata_filters: Optional[Dict[str, Any]],
        content_types: Optional[List[str]], tags: Optional[List[str]], conn: sqlite3.Connection
    ) -> List[Dict[str, Any]]:
        """Apply filters to search results (using AnyIO for tag query)."""
        filtered_results = results

        if content_types:
            filtered_results = [r for r in filtered_results if r.get("content_type") in content_types]

        if tags:
            tag_filtered_cids = set()
            first_tag = True
            for tag in tags:
                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT cid FROM content_tags WHERE tag = ?', (tag,))
                rows = await anyio.to_thread.run_sync(_db_fetchall, cursor)
                tag_cids = {row['cid'] for row in rows}
                if first_tag:
                    tag_filtered_cids = tag_cids
                    first_tag = False
                else:
                    tag_filtered_cids &= tag_cids
            filtered_results = [r for r in filtered_results if r["cid"] in tag_filtered_cids]

        if metadata_filters:
            # Metadata filtering is synchronous as it operates on already fetched data
            for key, value in metadata_filters.items():
                if key == "size_min": filtered_results = [r for r in filtered_results if r.get("size") is None or r.get("size", 0) >= value]
                elif key == "size_max": filtered_results = [r for r in filtered_results if r.get("size") is None or r.get("size", 0) <= value]
                elif key == "created_after": filtered_results = [r for r in filtered_results if r.get("created") is None or r.get("created", 0) >= value]
                elif key == "created_before": filtered_results = [r for r in filtered_results if r.get("created") is None or r.get("created", 0) <= value]
                elif key == "author": filtered_results = [r for r in filtered_results if r.get("author") == value]
                elif key == "license": filtered_results = [r for r in filtered_results if r.get("license") == value]
                elif key.startswith("extra.") and len(key) > 6:
                    extra_key = key[6:]
                    filtered_results = [r for r in filtered_results if r.get("extra") and extra_key in r["extra"] and r["extra"][extra_key] == value]

        return filtered_results

    async def get_content_metadata(self, cid: str) -> Dict[str, Any]:
        """Get metadata for indexed content (using AnyIO)."""
        conn = None
        try:
            async with self.db_lock:
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                cursor = await anyio.to_thread.run_sync(conn.cursor)
                cursor = await anyio.to_thread.run_sync(_db_execute, conn, '''
                    SELECT cid, name, description, tags, content_type, size, created, author, license, extra, indexed_at, text_extracted, vector_embedded
                    FROM content_metadata WHERE cid = ?
                ''', (cid,))
                row = await anyio.to_thread.run_sync(_db_fetchone, cursor)

            if not row:
                return { "success": False, "cid": cid, "error": "Content not found in index" }

            metadata = dict(row)
            metadata["tags"] = json.loads(metadata["tags"]) if metadata.get("tags") else []
            metadata["extra"] = json.loads(metadata["extra"]) if metadata.get("extra") else {}

            return { "success": True, "cid": cid, "metadata": metadata }

        except Exception as e:
            logger.error(f"Error getting metadata for CID {cid}: {e}", exc_info=True)
            return { "success": False, "cid": cid, "error": str(e) }
        finally:
            if conn: await anyio.to_thread.run_sync(_db_close, conn)

    async def get_stats(self) -> Dict[str, Any]:
        """Get search service statistics (using AnyIO)."""
        conn = None
        try:
            async with self.db_lock:
                conn = await anyio.to_thread.run_sync(_db_connect, self.db_path)
                cursor = await anyio.to_thread.run_sync(conn.cursor)

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT COUNT(*) FROM content_metadata')
                total_content = (await anyio.to_thread.run_sync(_db_fetchone, cursor))[0]

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT COUNT(*) FROM content_metadata WHERE text_extracted = 1')
                text_extracted = (await anyio.to_thread.run_sync(_db_fetchone, cursor))[0]

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT COUNT(*) FROM content_metadata WHERE vector_embedded = 1')
                vector_embedded = (await anyio.to_thread.run_sync(_db_fetchone, cursor))[0]

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT content_type, COUNT(*) as count FROM content_metadata GROUP BY content_type')
                rows_ct = await anyio.to_thread.run_sync(_db_fetchall, cursor)
                content_types = {row['content_type']: row['count'] for row in rows_ct if row['content_type']}

                cursor = await anyio.to_thread.run_sync(_db_execute, conn, 'SELECT tag, COUNT(*) as count FROM content_tags GROUP BY tag ORDER BY count DESC LIMIT 50')
                rows_tags = await anyio.to_thread.run_sync(_db_fetchall, cursor)
                tags = {row['tag']: row['count'] for row in rows_tags}

            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            index_file = os.path.join(self.vector_index_path, "index.faiss")
            vector_index_size = os.path.getsize(index_file) if os.path.exists(index_file) else 0
            vector_count = self.vector_index.ntotal if self.vector_index else 0

            return {
                "success": True,
                "stats": {
                    "total_content": total_content, "text_extracted": text_extracted, "vector_embedded": vector_embedded,
                    "content_types": content_types, "tags": tags, "database_size": db_size,
                    "vector_index_size": vector_index_size, "vector_count": vector_count,
                    "vector_dimension": self.vector_dimension,
                    "embedding_model": self.embedding_model_name if self.embedding_model else None,
                    "vector_search_available": FAISS_AVAILABLE and self.vector_index is not None
                }
            }

        except Exception as e:
            logger.error(f"Error getting search service statistics: {e}", exc_info=True)
            return { "success": False, "error": str(e) }
        finally:
            if conn: await anyio.to_thread.run_sync(_db_close, conn)

# --- FastAPI Router Setup ---

def create_search_router(api_prefix: str) -> APIRouter:
    """Create a FastAPI router with search endpoints."""
    router = APIRouter(prefix=f"{api_prefix}/search")
    search_service = ContentSearchService()

    @router.on_event("startup")
    async def startup_event():
        await search_service.initialize() # Initialize async components

    @router.get("/status")
    async def search_status():
        """Get search service status."""
        stats = await search_service.get_stats()
        features = {
            "text_search": True,
            "vector_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "hybrid_search": SENTENCE_TRANSFORMERS_AVAILABLE and FAISS_AVAILABLE,
            "content_extraction": True,
            "metadata_filtering": True
        }
        if stats["success"]:
            return { "success": True, "status": "available", "features": features, "stats": stats["stats"] }
        else:
            return { "success": False, "status": "error", "features": features, "error": stats.get("error", "Unknown error") }

    @router.post("/index")
    async def index_content_endpoint( # Renamed to avoid conflict
        background_tasks: BackgroundTasks, # Add BackgroundTasks dependency
        cid: str = Form(...),
        name: Optional[str] = Form(None), description: Optional[str] = Form(None),
        tags: Optional[str] = Form(None), content_type: Optional[str] = Form(None),
        size: Optional[int] = Form(None), created: Optional[float] = Form(None),
        author: Optional[str] = Form(None), license: Optional[str] = Form(None),
        extra: Optional[str] = Form(None),
        extract_text: bool = Form(True), create_embedding: bool = Form(True)
    ):
        """Index content metadata. Text extraction/embedding runs in background."""
        parsed_tags = None
        if tags:
            try: parsed_tags = json.loads(tags)
            except: parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        parsed_extra = None
        if extra:
            try: parsed_extra = json.loads(extra)
            except: parsed_extra = {"text": extra}

        metadata = ContentMetadata(
            name=name, description=description, tags=parsed_tags, content_type=content_type, size=size,
            created=created, author=author, license=license, extra=parsed_extra
        )

        # Schedule indexing in background
        background_tasks.add_task(
            search_service.index_content,
            cid, metadata, extract_text=extract_text, create_embedding=create_embedding
        )

        return {"success": True, "cid": cid, "message": "Indexing task scheduled"}

    @router.post("/query")
    async def search_content(query: SearchQuery):
        """Search indexed content."""
        result = await search_service.search(query)
        return result

    @router.get("/metadata/{cid}")
    async def get_metadata(cid: str):
        """Get metadata for indexed content."""
        result = await search_service.get_content_metadata(cid)
        return result

    @router.delete("/remove/{cid}")
    async def remove_content(cid: str):
        """Remove content from the search index."""
        result = await search_service.remove_content(cid)
        return result

    @router.post("/vector")
    async def vector_search(query: VectorQuery):
        """Perform vector search."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
            raise HTTPException(status_code=501, detail="Vector search not available")

        search_query = SearchQuery(
            query_text=query.text, metadata_filters=query.metadata_filters,
            vector_search=True, hybrid_search=False,
            min_score=query.min_score, max_results=query.max_results
        )
        result = await search_service.search(search_query)
        return result

    @router.post("/hybrid")
    async def hybrid_search(query: SearchQuery):
        """Perform hybrid search (text + vector)."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not FAISS_AVAILABLE:
             raise HTTPException(status_code=501, detail="Hybrid search not available")

        query.hybrid_search = True
        query.vector_search = True
        result = await search_service.search(query)
        return result

    return router