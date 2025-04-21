"""
Base class definition for storage backends.

This module defines the abstract interface that all storage backends must implement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, BinaryIO

from .storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class BackendStorage(ABC):
    """Abstract base class for storage backends."""
    
    def __init__(self, backend_type: StorageBackendType, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize storage backend.
        
        Args:
            backend_type: Type of the backend
            resources: Resources needed by the backend
            metadata: Metadata for the backend
        """
        self.backend_type = backend_type
        self.resources = resources
        self.metadata = metadata
        
    @abstractmethod
    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content to the storage backend.
        
        Args:
            content: Content to store (can be a path, bytes, or file-like object)
            metadata: Optional metadata for the content
            
        Returns:
            Dict with operation result including content ID
        """
        pass
        
    @abstractmethod
    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from the storage backend.
        
        Args:
            content_id: ID of the content to retrieve
            
        Returns:
            Dict with operation result including content data
        """
        pass
        
    @abstractmethod
    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from the storage backend.
        
        Args:
            content_id: ID of the content to remove
            
        Returns:
            Dict with operation result
        """
        pass
        
    @abstractmethod
    def get_metadata(self, content_id: str) -> Dict[str, Any]:
        """Get metadata for content in the storage backend.
        
        Args:
            content_id: ID of the content
            
        Returns:
            Dict with operation result including metadata
        """
        pass
        
    # Method aliases for backward compatibility with test code
    def store(self, content, key=None, **kwargs):
        """Alias for add_content method."""
        metadata = kwargs.get('metadata', {})
        return self.add_content(content, metadata)
        
    def retrieve(self, key, **kwargs):
        """Alias for get_content method."""
        return self.get_content(key)
        
    def delete(self, key, **kwargs):
        """Alias for remove_content method."""
        return self.remove_content(key)
        
    def list_keys(self, **kwargs):
        """List all content keys in the storage backend.
        
        This is a basic implementation that should be overridden by subclasses.
        
        Returns:
            Dict with operation result including a list of keys
        """
        # Default implementation returns empty list
        # Subclasses should override this with actual implementation
        return {
            "success": True,
            "keys": [],
            "message": "Default implementation. Subclasses should override."
        }
