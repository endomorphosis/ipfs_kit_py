"""
Unified Storage Manager for MCP.

This module provides a single unified interface for interacting with all supported
storage backends in the MCP system, implementing the "Unified Data Management"
features from the roadmap, including:
- Single interface for all storage operations
- Content addressing across backends
- Metadata synchronization and consistency
"""

from .manager import UnifiedStorageManager
from .storage_types import ContentReference, StorageBackendType
from .backend_base import BackendStorage

__all__ = [
    "StorageBackendType",
    "ContentReference",
    "UnifiedStorageManager",
    "BackendStorage",
]
