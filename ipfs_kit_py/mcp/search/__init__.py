"""
Search module for MCP server.

This module implements the search capabilities mentioned in the roadmap:
- Content indexing with automated metadata extraction
- Full-text search with SQLite FTS5
- Vector search with FAISS 
- Hybrid search combining text and vector search
"""

from .mcp_search import (
    SearchEngine,
    search_text,
    search_vector,
    search_hybrid,
    index_document
)

__all__ = [
    'SearchEngine',
    'search_text',
    'search_vector',
    'search_hybrid',
    'index_document'
]