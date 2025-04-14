"""
Search module for the MCP server.

This package provides content indexing, text search,
and vector search capabilities for the MCP server.
"""

from .search import (
    ContentSearchService,
    ContentMetadata,
    SearchQuery,
    VectorQuery
)

__all__ = [
    "ContentSearchService",
    "ContentMetadata",
    "SearchQuery",
    "VectorQuery"
]