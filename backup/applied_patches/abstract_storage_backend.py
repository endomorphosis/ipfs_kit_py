#!/usr/bin/env python3
"""
Abstract Storage Backend Interface

This module defines the common interface that all storage backends must implement.
It provides a standardized way to interact with different storage systems,
including IPFS, Filecoin, S3, Storacha, HuggingFace, and Lassie.

This is part of the effort to modularize storage backends as outlined in
the MCP Server Development Roadmap (Q2 2025).
"""

import abc
from typing import Dict, Any, Optional, Union, BinaryIO, List, Tuple


class AbstractStorageBackend(abc.ABC):
    """
    Abstract base class for all storage backends.

    This class defines the common interface that all storage backends must implement.
    Concrete implementations should inherit from this class and implement all abstract methods.
    """

    @abc.abstractmethod
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the storage backend with the given configuration.

        Args:
            config: Configuration dictionary for the backend
        """
        self.config = config or {}
        self.name = "abstract"
        self.description = "Abstract Storage Backend"
        self.initialized = False
        self.performance_stats = {
            "store": {"count": 0, "total_time": 0, "avg_time": 0},
            "retrieve": {"count": 0, "total_time": 0, "avg_time": 0},
            "delete": {"count": 0, "total_time": 0, "avg_time": 0},
            "list": {"count": 0, "total_time": 0, "avg_time": 0},
        }

    @abc.abstractmethod
    def get_name(self) -> str:
        """
        Get the name of the storage backend.

        Returns:
            The backend name as a string
        """
        pass

    @abc.abstractmethod
    def get_description(self) -> str:
        """
        Get a description of the storage backend.

        Returns:
            The backend description as a string
        """
        pass

    @abc.abstractmethod
    def is_available(self) -> bool:
        """
        Check if the backend is available for use.

        Returns:
            True if the backend is available, False otherwise
        """
        pass

    @abc.abstractmethod
    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store data in the storage backend.

        Args:
            data: The data to store (bytes, file-like object, or string)
            container: Optional container/bucket name
            path: Optional path within the container
            options: Additional options for the storage operation

        Returns:
            Dict with operation results, including at minimum:
            {
                "success": bool,
                "identifier": str,  # Content ID or path
                "backend": str,     # Backend name
                "details": dict     # Backend-specific details
            }
        """
        pass

    @abc.abstractmethod
    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve data from the storage backend.

        Args:
            identifier: The content ID or path to retrieve
            container: Optional container/bucket name
            options: Additional options for the retrieval operation

        Returns:
            Dict with operation results, including at minimum:
            {
                "success": bool,
                "data": bytes,      # The retrieved data
                "backend": str,     # Backend name
                "identifier": str,  # Content ID or path
                "details": dict     # Backend-specific details
            }
        """
        pass

    @abc.abstractmethod
    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete data from the storage backend.

        Args:
            identifier: The content ID or path to delete
            container: Optional container/bucket name
            options: Additional options for the delete operation

        Returns:
            Dict with operation results, including at minimum:
            {
                "success": bool,
                "backend": str,     # Backend name
                "identifier": str,  # Content ID or path
                "details": dict     # Backend-specific details
            }
        """
        pass

    @abc.abstractmethod
    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List content in the storage backend.

        Args:
            container: Optional container/bucket name
            prefix: Optional prefix to filter results
            options: Additional options for the list operation

        Returns:
            Dict with operation results, including at minimum:
            {
                "success": bool,
                "items": list,      # List of content items
                "backend": str,     # Backend name
                "details": dict     # Backend-specific details
            }
        """
        pass

    @abc.abstractmethod
    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if content exists in the storage backend.

        Args:
            identifier: The content ID or path to check
            container: Optional container/bucket name
            options: Additional options for the check operation

        Returns:
            True if the content exists, False otherwise
        """
        pass

    @abc.abstractmethod
    def get_stats(
        self,
        identifier: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics for content or backend operations.

        Args:
            identifier: Optional content ID or path
            options: Additional options for the stats operation

        Returns:
            Dict with statistics information
        """
        pass

    def _update_perf_stats(self, operation: str, duration: float) -> None:
        """
        Update performance statistics for an operation.

        Args:
            operation: The name of the operation (store, retrieve, delete, list)
            duration: The duration of the operation in seconds
        """
        if operation in self.performance_stats:
            stats = self.performance_stats[operation]
            stats["count"] = int(stats.get("count", 0)) + 1
            stats["total_time"] = float(stats.get("total_time", 0)) + duration
            count = stats["count"]
            if count > 0:
                stats["avg_time"] = float(stats["total_time"]) / count

    def format_response(
        self,
        success: bool,
        data: Any = None,
        identifier: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format a standardized response for backend operations.

        Args:
            success: Whether the operation was successful
            data: Optional data returned by the operation
            identifier: Optional content ID or path
            details: Optional backend-specific details
            error: Optional error message

        Returns:
            Standardized response dictionary
        """
        response = {
            "success": success,
            "backend": self.get_name(),
        }

        if data is not None:
            response["data"] = data

        if identifier is not None:
            response["identifier"] = identifier

        if details is not None:
            response["details"] = details

        if error is not None:
            response["error"] = error

        return response
