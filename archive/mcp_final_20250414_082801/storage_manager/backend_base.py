"""
Base class for all storage backend implementations.

This module defines the abstract BackendStorage class that all
specific backend implementations must inherit from.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, BinaryIO
from .storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class BackendStorage(ABC):
    """Base class for all backend storage implementations."""
    def __init__(
    self,
    backend_type: StorageBackendType
        resources: Dict[str, Any]
        metadata: Dict[str, Any]
    ):
        """
        Initialize backend storage.

        Args:
            backend_type: Type of this backend
            resources: Dictionary of available resources
            metadata: Additional configuration metadata
        """
        self.backend_type = backend_type
        self.resources = resources or {}
        self.metadata = metadata or {}

    def get_name(self) -> str:
        """Get the name of this backend."""
        return self.backend_type.value

    @abstractmethod
    def store(
    self,
    data: Union[bytes, BinaryIO, str]
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data in this backend.

        Args:
            data: Data to store (bytes, file-like object, or string)
            container: Container to store in (e.g., bucket for S3)
            path: Path within container
            options: Backend-specific options

        Returns:
            Dictionary with operation result
        """
        pass

    @abstractmethod
    def retrieve(
    self,
    identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from this backend.

        Args:
            identifier: Backend-specific identifier
            container: Container to retrieve from
            options: Backend-specific options

        Returns:
            Dictionary with operation result and data
        """
        pass

    @abstractmethod
    def delete(
    self,
    identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete data from this backend.

        Args:
            identifier: Backend-specific identifier
            container: Container to delete from
            options: Backend-specific options

        Returns:
            Dictionary with operation result
        """
        pass

    @abstractmethod
    def list(
    self,
    container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List items in this backend.

        Args:
            container: Container to list
            prefix: Filter by prefix
            options: Backend-specific options

        Returns:
            Dictionary with operation result and items
        """
        pass

    @abstractmethod
    def exists(
    self,
    identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if item exists in this backend.

        Args:
            identifier: Backend-specific identifier
            container: Container to check
            options: Backend-specific options

        Returns:
            True if item exists
        """
        pass

    @abstractmethod
    def get_metadata(
    self,
    identifier: str
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get metadata for an item.

        Args:
            identifier: Backend-specific identifier
            container: Container to check
            options: Backend-specific options

        Returns:
            Dictionary with metadata
        """
        pass

    @abstractmethod
    def update_metadata(
    self,
    identifier: str
        metadata: Dict[str, Any]
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for an item.

        Args:
            identifier: Backend-specific identifier
            metadata: New metadata to set
            container: Container to update
            options: Backend-specific options

        Returns:
            Dictionary with operation result
        """
        pass
