"""
Base class definition for storage backends.

This module defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod


class BackendStorage(ABC):
    """
    Abstract base class for storage backends.
    """
    def __init__(self, backend_type, resources: dict, metadata: dict):
        self.backend_type = backend_type
        self.resources = resources
        self.metadata = metadata

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the backend."""
        raise NotImplementedError

    @abstractmethod
    def add_content(self, content, metadata: dict = None) -> dict:
        """Store content and return operation result."""
        raise NotImplementedError

    @abstractmethod
    def get_content(self, identifier) -> dict:
        """Retrieve content by identifier."""
        raise NotImplementedError

    @abstractmethod
    def remove_content(self, identifier) -> dict:
        """Remove content by identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, identifier) -> dict:
        """Retrieve metadata for content identifier."""
        raise NotImplementedError
