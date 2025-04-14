"""
MCP Search module - Backward compatibility module.

This module provides backward compatibility for code using the old import path.
The actual implementation has been moved to ipfs_kit_py.mcp.search module.
"""

import logging
import warnings

# Issue a deprecation warning
warnings.warn(
    "Importing from ipfs_kit_py.mcp_search is deprecated. "
    "Please use ipfs_kit_py.mcp.search instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from the new module
from ipfs_kit_py.mcp.search import (
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