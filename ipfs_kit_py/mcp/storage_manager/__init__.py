"""
Unified Storage Manager for MCP.

This module provides a single unified interface for interacting with all supported
storage backends in the MCP system, implementing the "Unified Data Management" 
features from the roadmap, including:
- Single interface for all storage operations
- Content addressing across backends
- Metadata synchronization and consistency
"""

from .storage_types import StorageBackendType, ContentReference
from .manager import UnifiedStorageManager

__all__ = [
    'StorageBackendType',
    'ContentReference',
    'UnifiedStorageManager',
]