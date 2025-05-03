"""
Storage types for the unified storage manager.

This module defines the core types used in the unified storage system,
including backend types and content references.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

# Configure logger
logger = logging.getLogger(__name__)


class StorageBackendType(Enum):
    """Enum for supported storage backend types."""
    IPFS = "ipfs"
    MOCK = "mock"
    FILECOIN = "filecoin"
    S3 = "s3"
    STORACHA = "storacha"
    HUGGINGFACE = "huggingface"
    LASSIE = "lassie"
    LOCAL = "local"
    OTHER = "other"


class ContentReference:
    """Reference to content across multiple storage backends."""
    def __init__(self, content_id: str, content_hash: str, metadata: Dict[str, Any]):
        self.content_id = content_id
        self.content_hash = content_hash
        self.metadata = metadata
        self._locations: Dict[StorageBackendType, Any] = {}

    def add_location(self, backend_type: StorageBackendType, identifier: Any) -> None:
        """Add a location for the content under a specific backend."""
        self._locations[backend_type] = identifier

    def has_location(self, backend_type: StorageBackendType) -> bool:
        """Check if a location exists for the given backend."""
        return backend_type in self._locations

    def get_location(self, backend_type: StorageBackendType) -> Optional[Any]:
        """Get the identifier for content stored in the given backend."""
        return self._locations.get(backend_type)