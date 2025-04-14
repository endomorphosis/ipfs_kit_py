"""
Bridge module for storage manager base classes.

This module provides direct access to storage base classes without circular imports.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, BinaryIO
from .storage_types import StorageBackendType


class BackendStorage(ABC):
    """Abstract base class for all storage backends."""

    def __init__(self, backend_type: StorageBackendType, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """
        Initialize the backend.
        
        Args:
            backend_type: Type of the storage backend
            resources: Resources needed by the backend (e.g., API URL, credentials)
            metadata: Additional metadata for the backend
        """
        self.backend_type = backend_type
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.name = self.backend_type.value

    def get_type(self) -> StorageBackendType:
        """Get the type of the backend."""
        return self.backend_type

    def get_name(self) -> str:
        """Get the name of the backend."""
        return self.name

    @abstractmethod
    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data in the backend.
        
        Args:
            data: Data to store (bytes, file-like object, or string)
            container: Optional container/bucket name
            path: Optional path/key within the container
            options: Backend-specific options
            
        Returns:
            Dictionary with operation result
        """
        pass

    @abstractmethod
    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from the backend.
        
        Args:
            identifier: Content identifier
            container: Optional container/bucket name
            options: Backend-specific options
            
        Returns:
            Dictionary with operation result and data
        """
        pass

    @abstractmethod
    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete data from the backend.
        
        Args:
            identifier: Content identifier
            container: Optional container/bucket name
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
        List items in the backend.
        
        Args:
            container: Optional container/bucket name
            prefix: Optional prefix to filter items
            options: Backend-specific options
            
        Returns:
            Dictionary with operation result and items
        """
        pass

    @abstractmethod
    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if content exists in the backend.
        
        Args:
            identifier: Content identifier
            container: Optional container/bucket name
            options: Backend-specific options
            
        Returns:
            True if content exists, False otherwise
        """
        pass

    @abstractmethod
    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get metadata for content.
        
        Args:
            identifier: Content identifier
            container: Optional container/bucket name
            options: Backend-specific options
            
        Returns:
            Dictionary with operation result and metadata
        """
        pass

    @abstractmethod
    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for content.
        
        Args:
            identifier: Content identifier
            metadata: Metadata to update
            container: Optional container/bucket name
            options: Backend-specific options
            
        Returns:
            Dictionary with operation result
        """
        pass