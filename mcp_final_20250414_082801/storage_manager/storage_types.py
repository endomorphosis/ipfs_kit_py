"""
Storage types for the unified storage manager.

This module defines the core types used in the unified storage system,
including backend types and content references.
"""

import logging
import time
from enum import Enum
from typing import Dict, Any, Optional, Union

# Configure logger
logger = logging.getLogger(__name__)


class StorageBackendType(Enum):
    """Enumeration of supported storage backend types."""
    IPFS = "ipfs"
    S3 = "s3"
    STORACHA = "storacha"  # Web3.Storage
    FILECOIN = "filecoin"
    HUGGINGFACE = "huggingface"
    LASSIE = "lassie"

    @classmethod
    def from_string(cls, backend_str: str) -> "StorageBackendType":
        """Convert string to backend type enum."""
        for backend in cls:
            if backend.value == backend_str.lower():
                return backend
        raise ValueError(f"Unsupported backend type: {backend_str}")


class ContentReference:
    """
    Reference to content stored in one or more backends.

    This class provides a unified way to reference content across different
    storage backends, enabling seamless access regardless of where the
    content is physically stored.
    """
    def __init__(
        self
        content_id: str
        content_hash: Optional[str] = None,
        backend_locations: Optional[Dict[StorageBackendType, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a content reference.

        Args:
            content_id: Global unique identifier for the content
            content_hash: Hash of the content (for integrity verification)
            backend_locations: Mapping of backend types to backend-specific identifiers
            metadata: Additional metadata about the content
        """
        self.content_id = content_id
        self.content_hash = content_hash
        self.backend_locations = backend_locations or {}
        self.metadata = metadata or {}
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.access_count = 0

    def add_location(self, backend_type: Union[StorageBackendType, str], location_id: str):
        """
        Add a backend location for this content.

        Args:
            backend_type: Backend type (enum or string)
            location_id: Backend-specific identifier for the content
        """
        if isinstance(backend_type, str):
            backend_type = StorageBackendType.from_string(backend_type)

        self.backend_locations[backend_type] = location_id

    def remove_location(self, backend_type: Union[StorageBackendType, str]) -> bool:
        """
        Remove a backend location for this content.

        Args:
            backend_type: Backend type to remove

        Returns:
            True if location was found and removed
        """
        if isinstance(backend_type, str):
            backend_type = StorageBackendType.from_string(backend_type)

        if backend_type in self.backend_locations:
            del self.backend_locations[backend_type]
            return True
        return False

    def has_location(self, backend_type: Union[StorageBackendType, str]) -> bool:
        """
        Check if content is available in a specific backend.

        Args:
            backend_type: Backend type to check

        Returns:
            True if content is available in the specified backend
        """
        if isinstance(backend_type, str):
            backend_type = StorageBackendType.from_string(backend_type)

        return backend_type in self.backend_locations

    def get_location(self, backend_type: Union[StorageBackendType, str]) -> Optional[str]:
        """
        Get location identifier for a specific backend.

        Args:
            backend_type: Backend type

        Returns:
            Backend-specific identifier or None if not available
        """
        if isinstance(backend_type, str):
            backend_type = StorageBackendType.from_string(backend_type)

        return self.backend_locations.get(backend_type)

    def record_access(self):
        """Record an access to this content."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content_id": self.content_id,
            "content_hash": self.content_hash,
            "backend_locations": {k.value: v for k, v in self.backend_locations.items()},
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentReference":
        """Create from dictionary representation."""
        backend_locations = {
            StorageBackendType.from_string(k): v
            for k, v in data.get("backend_locations", {}).items()
        }

        ref = cls(
            content_id=data["content_id"],
            content_hash=data.get("content_hash"),
            backend_locations=backend_locations,
            metadata=data.get("metadata", {}),
        )

        # Set timestamps and access count
        ref.created_at = data.get("created_at", time.time())
        ref.last_accessed = data.get("last_accessed", time.time())
        ref.access_count = data.get("access_count", 0)

        return ref
