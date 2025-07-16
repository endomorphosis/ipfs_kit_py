"""
GraphRAG Search Engine for IPFS Kit.

This module provides advanced search capabilities for VFS/MFS content
using GraphRAG, vector search, and SPARQL queries.
"""

import logging
import os
import sqlite3
from typing import Dict, Any, List, Optional

# Dependency checks
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import rdflib
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

logger = logging.getLogger(__name__)


class GraphRAGSearchEngine:
    """Advanced search engine with GraphRAG, vector search, and SPARQL."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.path.expanduser("~/.ipfs_mcp_search")
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        self.db_path = os.path.join(self.workspace_dir, "search_index.db")
        self._init_database()
        
        self.embeddings_model = self._init_vector_search()
        self.knowledge_graph = self._init_knowledge_graph()
        self.rdf_graph = self._init_rdf_graph()
        
        logger.info(f"GraphRAG search engine initialized at {self.workspace_dir}")

    def _init_database(self):
        """Initialize SQLite database for content indexing."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_index (
                    id INTEGER PRIMARY KEY, cid TEXT UNIQUE, path TEXT,
                    content_type TEXT, title TEXT, content TEXT, metadata TEXT,
                    embedding BLOB, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS content_relationships (
                    source_cid TEXT, target_cid TEXT, relationship_type TEXT,
                    FOREIGN KEY (source_cid) REFERENCES content_index (cid),
                    FOREIGN KEY (target_cid) REFERENCES content_index (cid)
                )
            ''')
            conn.commit()

    def _init_vector_search(self):
        """Initialize vector search capabilities."""
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                return SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer model: {e}")
        return None

    def _init_knowledge_graph(self):
        """Initialize knowledge graph for GraphRAG."""
        return nx.Graph() if HAS_NETWORKX else None

    def _init_rdf_graph(self):
        """Initialize RDF graph for SPARQL queries."""
        return rdflib.Graph() if HAS_RDFLIB else None

    async def index_content(self, cid: str, path: str, content: str, **kwargs) -> Dict[str, Any]:
        """Index content for search."""
        try:
            embedding = None
            if self.embeddings_model:
                embedding = self.embeddings_model.encode([content])[0]

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO content_index (cid, path, content, embedding) VALUES (?, ?, ?, ?)",
                    (cid, path, content, embedding.tobytes() if embedding is not None else None)
                )
                conn.commit()
            
            if self.knowledge_graph is not None:
                self.knowledge_graph.add_node(cid, path=path, type='content')

            return {"success": True, "cid": cid}
        except Exception as e:
            logger.error(f"Error indexing content {cid}: {e}")
            return {"success": False, "error": str(e)}

    async def search(self, query: str, search_type: str = "hybrid", **kwargs) -> Dict[str, Any]:
        """Perform a search operation."""
        if search_type == "vector" and self.embeddings_model:
            return await self.vector_search(query, **kwargs)
        if search_type == "graph" and self.knowledge_graph:
            return await self.graph_search(query, **kwargs)
        if search_type == "sparql" and self.rdf_graph:
            return await self.sparql_search(query, **kwargs)
        if search_type == "hybrid":
            return await self.hybrid_search(query, **kwargs)
        
        return {"success": False, "error": f"Search type '{search_type}' not supported or dependencies missing."}

    async def vector_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Perform vector similarity search."""
        if not self.embeddings_model or not HAS_NUMPY or not HAS_SKLEARN:
            return {"success": False, "error": "Vector search dependencies not available."}
        
        query_embedding = self.embeddings_model.encode([query])[0]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cid, path, embedding FROM content_index WHERE embedding IS NOT NULL")
            results = []
            for cid, path, embedding_bytes in cursor.fetchall():
                embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                similarity = cosine_similarity([query_embedding], [embedding])[0][0]
                results.append({"cid": cid, "path": path, "score": float(similarity)})
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return {"success": True, "results": results[:limit]}

    async def hybrid_search(self, query: str, **kwargs) -> Dict[str, Any]:
        # Basic hybrid search, can be expanded
        vector_results = await self.vector_search(query, **kwargs)
        # In a real scenario, you would combine with other search types
        return vector_results
    
    async def graph_search(self, query: str, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "Graph search not fully implemented."}

    async def sparql_search(self, query: str, **kwargs) -> Dict[str, Any]:
        return {"success": False, "error": "SPARQL search not fully implemented."}
