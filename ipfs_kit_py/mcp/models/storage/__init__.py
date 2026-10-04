"""
Storage backend models for MCP server.

This package provides models for different storage backends:
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

These models implement the business logic for storage operations
and follow a common interface pattern.
"""

import logging
import time
import uuid
from typing import Dict, Optional, Any  # Removed unused List, Union

# Configure logger
logger = logging.getLogger(__name__)


class BaseStorageModel:
    """Base model for storage backend operations."""
    def __init__(self, kit_instance = None, cache_manager = None, credential_manager = None):
        """Initialize storage model with dependencies.

        Args:
            kit_instance: Backend-specific kit instance
            cache_manager: Cache manager for content caching
            credential_manager: Credential manager for authentication
        """
        self.kit = kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.correlation_id = str(uuid.uuid4())
        self.operation_stats = self._initialize_stats()
        logger.info(f"Initialized BaseStorageModel with ID: {self.correlation_id}")

    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize operation statistics tracking."""
        return {
            "upload_count": 0,
            "download_count": 0,
            "list_count": 0,
            "delete_count": 0,
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get current operation statistics."""
        return {"operation_stats": self.operation_stats, "timestamp": time.time()}

    def reset(self) -> None:
        """Reset model state for testing."""
        self.operation_stats = self._initialize_stats()
        self.correlation_id = str(uuid.uuid4())
        logger.info(f"Reset BaseStorageModel state, new ID: {self.correlation_id}")

    def _create_result_dict(self, operation: str) -> Dict[str, Any]:
        """Create a standardized result dictionary.

        Args:
            operation: Name of the operation being performed

        Returns:
            Result dictionary with standard fields
        """
        return {
            "success": False,
            "operation": operation,
            "timestamp": time.time(),
            "correlation_id": self.correlation_id,
            "duration_ms": 0,  # Will be set at the end of the operation
        }

    def _update_stats(self, result: Dict[str, Any], bytes_count: Optional[int] = None) -> None:
        """Update operation statistics based on result.

        Args:
            result: Operation result dictionary
            bytes_count: Number of bytes processed (if applicable)
        """
        # Update operation counts
        operation = result.get("operation", "unknown")
        self.operation_stats["total_operations"] += 1

        if operation.startswith("upload"):
            self.operation_stats["upload_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_uploaded"] += bytes_count
        elif operation.startswith("download"):
            self.operation_stats["download_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_downloaded"] += bytes_count
        elif operation.startswith("list"):
            self.operation_stats["list_count"] += 1
        elif operation.startswith("delete"):
            self.operation_stats["delete_count"] += 1

        # Update success/failure counts
        if result.get("success", False):
            self.operation_stats["success_count"] += 1
        else:
            self.operation_stats["failure_count"] += 1

    def _handle_error(
        self, result: Dict[str, Any], error: Exception, message: Optional[str] = None
    ) -> None:
        """Handle errors in a standardized way.

        Args:
            result: Result dictionary to update
            error: Exception that occurred
            message: Optional custom error message

        Returns:
            None
        """
        result["success"] = False
        result["error"] = message or str(error)
        result["error_type"] = type(error).__name__

        # Log the error
        logger.error(f"Error in {result['operation']}: {result['error']}")

        return result
