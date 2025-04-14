"""
Storage Bridge Model for MCP Server.

This module provides a bridge for cross-backend storage operations, enabling
content transfer, replication, verification, and migration between different
storage backends.
"""

import logging
import time
import os
import tempfile
import uuid
from typing import Dict, List, Any, Optional

# Configure logger
logger = logging.getLogger(__name__)


class StorageBridgeModel:
    """
    Model for cross-backend storage operations.

    Provides functionality for transferring content between storage backends,
    replicating content across multiple backends, verifying content across backends,
    and finding the optimal source for content retrieval.
    """
    def __init__(self, ipfs_model = None, backends = None, cache_manager = None):
        """
        Initialize storage bridge model.

        Args:
            ipfs_model: IPFS model for core operations
            backends: Dictionary of backend models
            cache_manager: Cache manager for content caching
        """
        self.ipfs_model = ipfs_model
        self.backends = backends or {}  # Dictionary of backend models
        self.cache_manager = cache_manager
        self.correlation_id = str(uuid.uuid4())
        self.operation_stats = self._initialize_stats()

        logger.info(
            f"Storage Bridge Model initialized with backends: {', '.join(self.backends.keys())}"

    def _initialize_stats(self) -> Dict[str, Any]:
        """Initialize operation statistics tracking."""
        return {
            "transfer_count": 0,
            "migration_count": 0,
            "replication_count": 0,
            "verification_count": 0,
            "policy_application_count": 0,
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "bytes_transferred": 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get current operation statistics."""
        return {
            "operation_stats": self.operation_stats,
            "timestamp": time.time(),
            "backends": list(self.backends.keys()),
            "correlation_id": self.correlation_id,
        }

    def reset(self) -> Dict[str, Any]:
        """Reset model state for testing."""
        prev_stats = self.operation_stats.copy()
        self.operation_stats = self._initialize_stats()
        self.correlation_id = str(uuid.uuid4())
        logger.info(f"Reset StorageBridgeModel state, new ID: {self.correlation_id}")

        return {
            "success": True,
            "operation": "reset_stats",
            "previous_stats": prev_stats,
            "new_correlation_id": self.correlation_id,
            "timestamp": time.time(),
        }

    async def async_reset(self) -> Dict[str, Any]:
        """Asynchronously reset model state for testing."""
        # Reset is lightweight enough that we can just call the sync version
        result = self.reset()

        # Notify any listeners if we add them in the future
        # For now, just return the result
        return result

    def _create_result_dict(self, operation: str) -> Dict[str, Any]:
        """
        Create a standardized result dictionary.

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
        """
        Update operation statistics based on result.

        Args:
            result: Operation result dictionary
            bytes_count: Number of bytes processed (if applicable)
        """
        operation = result.get("operation", "unknown")

        # Update operation counts
        self.operation_stats["total_operations"] += 1

        if operation.startswith("transfer"):
            self.operation_stats["transfer_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_transferred"] += bytes_count
        elif operation.startswith("replicate"):
            self.operation_stats["replication_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_transferred"] += bytes_count
        elif operation.startswith("verify"):
            self.operation_stats["verification_count"] += 1
        elif operation.startswith("migrate"):
            self.operation_stats["migration_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_transferred"] += bytes_count
        elif operation.startswith("apply_replication_policy"):
            self.operation_stats["policy_application_count"] += 1
            if bytes_count and result.get("success", False):
                self.operation_stats["bytes_transferred"] += bytes_count

        # Update success/failure counts
        if result.get("success", False):
            self.operation_stats["success_count"] += 1
        else:
            self.operation_stats["failure_count"] += 1

    def _handle_error(
        self, result: Dict[str, Any], error: Exception, message: Optional[str] = None
        """
        Handle errors in a standardized way.

        Args:
            result: Result dictionary to update
            error: Exception that occurred
            message: Optional custom error message

        Returns:
            Updated result dictionary with error information
        """
        result["success"] = False
        result["error"] = message or str(error)
        result["error_type"] = type(error).__name__

        # Log the error
        logger.error(f"Error in {result['operation']}: {result['error']}")

        return result

    def transfer_content(
        self
        source_backend: str
        target_backend: str
        content_id: str
        source_options: Optional[Dict[str, Any]] = None,
        target_options: Optional[Dict[str, Any]] = None,
        """
        Transfer content between storage backends.

        Args:
            source_backend: Name of source backend
            target_backend: Name of target backend
            content_id: Content identifier (CID)
            source_options: Options for source backend
            target_options: Options for target backend

        Returns:
            Dictionary with transfer operation result
        """
        start_time = time.time()

        result = self._create_result_dict("transfer_content")
        result.update(
            {
                "source_backend": source_backend,
                "target_backend": target_backend,
                "content_id": content_id,
            }

        try:
            # Validate backends
            if source_backend not in self.backends:
                result["error"] = f"Source backend '{source_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            if target_backend not in self.backends:
                result["error"] = f"Target backend '{target_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            # Get source backend model
            source_model = self.backends[source_backend]

            # Get content from source backend
            if hasattr(source_model, "get_content"):
                source_result = source_model.get_content(content_id, source_options)
            else:
                # Try alternate methods based on backend type
                if source_backend == "ipfs" and hasattr(source_model, "cat"):
                    source_result = source_model.cat(content_id)
                elif hasattr(source_model, "download_file"):
                    # Create temporary file to store the content
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_path = temp_file.name

                    # Get key or path in source backend
                    key = content_id
                    bucket = None
                    if source_options:
                        key = source_options.get("key", key)
                        bucket = source_options.get("bucket")

                    # Download to temporary file
                    if bucket:
                        source_result = source_model.download_file(bucket, key, temp_path)
                    else:
                        source_result = source_model.download_file(key, temp_path)

                    # Read content from temporary file
                    if source_result.get("success", False):
                        with open(temp_path, "rb") as f:
                            content = f.read()
                        source_result["content"] = content

                        # Clean up temporary file
                        os.unlink(temp_path)
                else:
                    result["error"] = (
                        f"Source backend '{source_backend}' does not support content retrieval"
                    result["error_type"] = "UnsupportedOperationError"
                    return result

            # Check if source operation was successful
            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}"
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            # Extract content from source result
            content = source_result.get("content", None)
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Get target backend model
            target_model = self.backends[target_backend]

            # Store content in target backend
            if hasattr(target_model, "put_content"):
                target_result = target_model.put_content(content_id, content, target_options)
            else:
                # Try alternate methods based on backend type
                if target_backend == "ipfs" and hasattr(target_model, "add"):
                    target_result = target_model.add(content)
                elif hasattr(target_model, "upload_file"):
                    # Create temporary file to store the content
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_path = temp_file.name

                    # Get key or path in target backend
                    key = content_id
                    bucket = None
                    if target_options:
                        key = target_options.get("key", key)
                        bucket = target_options.get("bucket")

                    # Upload from temporary file
                    if bucket:
                        target_result = target_model.upload_file(temp_path, bucket, key)
                    else:
                        target_result = target_model.upload_file(temp_path, key)

                    # Clean up temporary file
                    os.unlink(temp_path)
                else:
                    result["error"] = (
                        f"Target backend '{target_backend}' does not support content storage"
                    result["error_type"] = "UnsupportedOperationError"
                    return result

            # Check if target operation was successful
            if not target_result.get("success", False):
                result["error"] = target_result.get(
                    "error", f"Failed to store content in {target_backend}"
                result["error_type"] = target_result.get("error_type", "ContentStorageError")
                return result

            # Transfer successful
            result["success"] = True
            result["source_location"] = source_result.get("location", None)
            result["target_location"] = target_result.get("location", None)
            result["bytes_transferred"] = (
                len(content) if isinstance(content, (bytes, bytearray)) else None

            # Update stats
            self._update_stats(result, result["bytes_transferred"])

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_transfer_content(
        self
        source_backend: str
        target_backend: str
        content_id: str
        source_options: Optional[Dict[str, Any]] = None,
        target_options: Optional[Dict[str, Any]] = None,
        """
        Transfer content between storage backends asynchronously.

        Args:
            source_backend: Name of source backend
            target_backend: Name of target backend
            content_id: Content identifier (CID)
            source_options: Options for source backend
            target_options: Options for target backend

        Returns:
            Dictionary with transfer operation result
        """
        start_time = time.time()

        result = self._create_result_dict("transfer_content")
        result.update(
            {
                "source_backend": source_backend,
                "target_backend": target_backend,
                "content_id": content_id,
            }

        try:
            # Validate backends
            if source_backend not in self.backends:
                result["error"] = f"Source backend '{source_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            if target_backend not in self.backends:
                result["error"] = f"Target backend '{target_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            # Get source backend model
            source_model = self.backends[source_backend]

            # Get content from source backend
            source_result = None

            # Try to use async methods first, then fall back to sync methods
            if hasattr(source_model, "async_get_content"):
                source_result = await source_model.async_get_content(content_id, source_options)
            elif hasattr(source_model, "get_content"):
                # Fallback to sync method
                source_result = source_model.get_content(content_id, source_options)
            else:
                # Try alternate methods based on backend type
                if source_backend == "ipfs": ,
                    if hasattr(source_model, "async_cat"):
                        source_result = await source_model.async_cat(content_id)
                    elif hasattr(source_model, "cat"):
                        source_result = source_model.cat(content_id)
                elif hasattr(source_model, "async_download_file"):
                    # Create temporary file to store the content
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_path = temp_file.name

                    # Get key or path in source backend
                    key = content_id
                    bucket = None
                    if source_options:
                        key = source_options.get("key", key)
                        bucket = source_options.get("bucket")

                    # Download to temporary file
                    if bucket:
                        source_result = await source_model.async_download_file(
                            bucket, key, temp_path
                    else:
                        source_result = await source_model.async_download_file(key, temp_path)

                    # Read content from temporary file
                    if source_result.get("success", False):
                        with open(temp_path, "rb") as f:
                            content = f.read()
                        source_result["content"] = content

                        # Clean up temporary file
                        os.unlink(temp_path)
                elif hasattr(source_model, "download_file"):
                    # Fallback to sync method
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_path = temp_file.name

                    # Get key or path in source backend
                    key = content_id
                    bucket = None
                    if source_options:
                        key = source_options.get("key", key)
                        bucket = source_options.get("bucket")

                    # Download to temporary file
                    if bucket:
                        source_result = source_model.download_file(bucket, key, temp_path)
                    else:
                        source_result = source_model.download_file(key, temp_path)

                    # Read content from temporary file
                    if source_result.get("success", False):
                        with open(temp_path, "rb") as f:
                            content = f.read()
                        source_result["content"] = content

                        # Clean up temporary file
                        os.unlink(temp_path)
                else:
                    result["error"] = (
                        f"Source backend '{source_backend}' does not support content retrieval"
                    result["error_type"] = "UnsupportedOperationError"
                    return result

            # Check if source operation was successful
            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}"
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            # Extract content from source result
            content = source_result.get("content", None)
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Get target backend model
            target_model = self.backends[target_backend]

            # Store content in target backend
            target_result = None

            # Try to use async methods first, then fall back to sync methods
            if hasattr(target_model, "async_add_content"):
                target_result = await target_model.async_add_content(content, target_options)
            elif hasattr(target_model, "add_content"):
                target_result = target_model.add_content(content, target_options)
            elif hasattr(target_model, "put_content"):
                target_result = target_model.put_content(content_id, content, target_options)
            else:
                # Try alternate methods based on backend type
                if target_backend == "ipfs": ,
                    if hasattr(target_model, "async_add"):
                        target_result = await target_model.async_add(content)
                    elif hasattr(target_model, "add"):
                        target_result = target_model.add(content)
                elif hasattr(target_model, "async_upload_file"):
                    # Create temporary file to store the content
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_path = temp_file.name

                    # Get key or path in target backend
                    key = content_id
                    bucket = None
                    if target_options:
                        key = target_options.get("key", key)
                        bucket = target_options.get("bucket")

                    # Upload from temporary file
                    if bucket:
                        target_result = await target_model.async_upload_file(temp_path, bucket, key)
                    else:
                        target_result = await target_model.async_upload_file(temp_path, key)

                    # Clean up temporary file
                    os.unlink(temp_path)
                elif hasattr(target_model, "upload_file"):
                    # Fallback to sync method
                    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                        temp_file.write(content)
                        temp_path = temp_file.name

                    # Get key or path in target backend
                    key = content_id
                    bucket = None
                    if target_options:
                        key = target_options.get("key", key)
                        bucket = target_options.get("bucket")

                    # Upload from temporary file
                    if bucket:
                        target_result = target_model.upload_file(temp_path, bucket, key)
                    else:
                        target_result = target_model.upload_file(temp_path, key)

                    # Clean up temporary file
                    os.unlink(temp_path)
                else:
                    result["error"] = (
                        f"Target backend '{target_backend}' does not support content storage"
                    result["error_type"] = "UnsupportedOperationError"
                    return result

            # Check if target operation was successful
            if not target_result.get("success", False):
                result["error"] = target_result.get(
                    "error", f"Failed to store content in {target_backend}"
                result["error_type"] = target_result.get("error_type", "ContentStorageError")
                return result

            # Transfer successful
            result["success"] = True
            result["source_location"] = source_result.get("location", None)
            result["target_location"] = target_result.get("location", None)
            result["bytes_transferred"] = (
                len(content) if isinstance(content, (bytes, bytearray)) else None

            # Update stats
            self._update_stats(result, result["bytes_transferred"])

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def replicate_content(
        self
        content_id: str
        target_backends: List[str]
        source_backend: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        """
        Replicate content across multiple storage backends.

        Args:
            content_id: Content identifier (CID)
            target_backends: List of target backend names
            source_backend: Source backend name (if None, use any backend that has the content)
            options: Backend-specific options

        Returns:
            Dictionary with replication operation result
        """
        start_time = time.time()

        result = self._create_result_dict("replicate_content")
        result.update(
            {
                "content_id": content_id,
                "target_backends": target_backends,
                "source_backend": source_backend,
                "replication_results": {},
            }

        try:
            # Find source backend if not specified
            if source_backend is None:
                source_backend = self._find_content_source(content_id)
                result["source_backend"] = source_backend

                if source_backend is None:
                    result["error"] = f"Content '{content_id}' not found in any available backend"
                    result["error_type"] = "ContentNotFoundError"
                    return result
            elif source_backend not in self.backends:
                result["error"] = f"Source backend '{source_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            # Get content from source backend (only once)
            source_result = self._get_content_from_backend(source_backend, content_id, options)

            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}"
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            content = source_result.get("content")
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Replicate to each target backend
            total_transferred = 0
            successful_backends = []

            for target in target_backends:
                if target == source_backend:
                    # Skip source backend
                    result["replication_results"][target] = {
                        "success": True,
                        "skipped": True,
                        "reason": "Source backend",
                    }
                    continue

                if target not in self.backends:
                    result["replication_results"][target] = {
                        "success": False,
                        "error": f"Target backend '{target}' not found",
                        "error_type": "BackendNotFoundError",
                    }
                    continue

                # Store in target backend
                backend_options = options.get(target, {}) if options else {}
                target_result = self._store_content_in_backend(
                    target, content_id, content, backend_options

                result["replication_results"][target] = target_result

                if target_result.get("success", False):
                    successful_backends.append(target)
                    if isinstance(content, (bytes, bytearray)):
                        total_transferred += len(content)

            # Update overall success
            result["success"] = len(successful_backends) > 0
            result["successful_backends"] = successful_backends
            result["failed_backends"] = [
                t for t in target_backends if t not in successful_backends and t != source_backend
            ]
            result["bytes_transferred"] = total_transferred

            # Update stats
            self._update_stats(result, total_transferred)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_replicate_content(
        self
        content_id: str
        target_backends: List[str]
        source_backend: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        """
        Asynchronously replicate content across multiple storage backends.

        Args:
            content_id: Content identifier (CID)
            target_backends: List of target backend names
            source_backend: Source backend name (if None, use any backend that has the content)
            options: Backend-specific options

        Returns:
            Dictionary with replication operation result
        """
        start_time = time.time()

        result = self._create_result_dict("replicate_content")
        result.update(
            {
                "content_id": content_id,
                "target_backends": target_backends,
                "source_backend": source_backend,
                "replication_results": {},
            }

        try:
            # Find source backend if not specified
            if source_backend is None:
                # Use async version if available
                if hasattr(self, "_async_find_content_source"):
                    source_backend = await self._async_find_content_source(content_id)
                else:
                    source_backend = self._find_content_source(content_id)

                result["source_backend"] = source_backend

                if source_backend is None:
                    result["error"] = f"Content '{content_id}' not found in any available backend"
                    result["error_type"] = "ContentNotFoundError"
                    return result
            elif source_backend not in self.backends:
                result["error"] = f"Source backend '{source_backend}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            # Get content from source backend (only once)
            # Try to use async methods first
            source_model = self.backends[source_backend]
            source_result = None

            # Try different async methods depending on the backend capabilities
            if hasattr(source_model, "async_get_content"):
                source_result = await source_model.async_get_content(content_id, options)
            elif hasattr(source_model, "get_content"):
                # Fallback to sync method
                source_result = source_model.get_content(content_id, options)
            elif source_backend == "ipfs": ,
                if hasattr(source_model, "async_cat"):
                    source_result = await source_model.async_cat(content_id)
                elif hasattr(source_model, "cat"):
                    source_result = source_model.cat(content_id)
            else:
                # Use the general content retrieval helper
                if hasattr(self, "_async_get_content_from_backend"):
                    source_result = await self._async_get_content_from_backend(
                        source_backend, content_id, options
                else:
                    source_result = self._get_content_from_backend(
                        source_backend, content_id, options

            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}"
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            content = source_result.get("content")
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Replicate to each target backend
            total_transferred = 0
            successful_backends = []

            for target in target_backends:
                if target == source_backend:
                    # Skip source backend
                    result["replication_results"][target] = {
                        "success": True,
                        "skipped": True,
                        "reason": "Source backend",
                    }
                    continue

                if target not in self.backends:
                    result["replication_results"][target] = {
                        "success": False,
                        "error": f"Target backend '{target}' not found",
                        "error_type": "BackendNotFoundError",
                    }
                    continue

                # Store in target backend
                backend_options = options.get(target, {}) if options else {}

                # Try to use async methods first
                target_model = self.backends[target]
                target_result = None

                # Use async methods if available, with fallback to sync methods
                if hasattr(target_model, "async_put_content"):
                    target_result = await target_model.async_put_content(
                        content_id, content, backend_options
                elif hasattr(target_model, "put_content"):
                    target_result = target_model.put_content(content_id, content, backend_options)
                elif hasattr(target_model, "async_add_content"):
                    target_result = await target_model.async_add_content(content, backend_options)
                elif hasattr(target_model, "add_content"):
                    target_result = target_model.add_content(content, backend_options)
                elif target == "ipfs": ,
                    if hasattr(target_model, "async_add"):
                        target_result = await target_model.async_add(content)
                    elif hasattr(target_model, "add"):
                        target_result = target_model.add(content)
                else:
                    # Use the general content storage helper
                    if hasattr(self, "_async_store_content_in_backend"):
                        target_result = await self._async_store_content_in_backend(
                            target, content_id, content, backend_options
                    else:
                        target_result = self._store_content_in_backend(
                            target, content_id, content, backend_options

                result["replication_results"][target] = target_result

                if target_result.get("success", False):
                    successful_backends.append(target)
                    if isinstance(content, (bytes, bytearray)):
                        total_transferred += len(content)

            # Update overall success
            result["success"] = len(successful_backends) > 0
            result["successful_backends"] = successful_backends
            result["failed_backends"] = [
                t for t in target_backends if t not in successful_backends and t != source_backend
            ]
            result["bytes_transferred"] = total_transferred

            # Update stats
            self._update_stats(result, total_transferred)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def verify_content(
        self
        content_id: str
        backends: Optional[List[str]] = None,
        reference_backend: Optional[str] = None,
        """
        Verify content availability and integrity across backends.

        Args:
            content_id: Content identifier (CID)
            backends: List of backend names to check (if None, check all)
            reference_backend: Backend to use as reference for integrity check

        Returns:
            Dictionary with verification results
        """
        start_time = time.time()

        result = self._create_result_dict("verify_content")
        result.update({"content_id": content_id, "verification_results": {}})

        try:
            # Use all backends if not specified
            if backends is None:
                backends = list(self.backends.keys())

            # Find reference backend if not specified
            if reference_backend is None:
                for backend_name in backends:
                    # First backend that has the content becomes the reference
                    backend_result = self._check_content_availability(backend_name, content_id)
                    if backend_result.get("success", False):
                        reference_backend = backend_name
                        break

            # Verify content in each backend
            available_backends = []
            content_hash = None
            reference_content = None

            # Get reference content if a reference backend was found
            if reference_backend:
                reference_result = self._get_content_from_backend(reference_backend, content_id)
                if reference_result.get("success", False):
                    reference_content = reference_result.get("content")
                    if reference_content:
                        import hashlib

                        content_hash = hashlib.sha256(reference_content).hexdigest()

                        # Add reference backend to results
                        result["verification_results"][reference_backend] = {
                            "success": True,
                            "available": True,
                            "integrity": "reference",
                            "hash": content_hash,
                        }
                        available_backends.append(reference_backend)

            # Check availability and integrity in each backend
            for backend_name in backends:
                if backend_name == reference_backend:
                    # Already handled
                    continue

                availability_result = self._check_content_availability(backend_name, content_id)

                if availability_result.get("success", False):
                    available_backends.append(backend_name)

                    # Check integrity if we have a reference hash
                    if content_hash and reference_content:
                        integrity_result = self._check_content_integrity(
                            backend_name, content_id, reference_content, content_hash
                        result["verification_results"][backend_name] = integrity_result
                    else:
                        result["verification_results"][backend_name] = {
                            "success": True,
                            "available": True,
                            "integrity": "unknown",
                        }
                else:
                    result["verification_results"][backend_name] = {
                        "success": False,
                        "available": False,
                        "error": availability_result.get("error"),
                        "error_type": availability_result.get("error_type"),
                    }

            # Update overall result
            result["success"] = len(available_backends) > 0
            result["available_backends"] = available_backends
            result["unavailable_backends"] = [b for b in backends if b not in available_backends]
            result["content_hash"] = content_hash
            result["reference_backend"] = reference_backend

            # Update stats
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_verify_content(
        self
        content_id: str
        backends: Optional[List[str]] = None,
        reference_backend: Optional[str] = None,
        """
        Asynchronously verify content availability and integrity across backends.

        Args:
            content_id: Content identifier (CID)
            backends: List of backend names to check (if None, check all)
            reference_backend: Backend to use as reference for integrity check

        Returns:
            Dictionary with verification results
        """
        start_time = time.time()

        result = self._create_result_dict("verify_content")
        result.update({"content_id": content_id, "verification_results": {}})

        try:
            # Use all backends if not specified
            if backends is None:
                backends = list(self.backends.keys())

            # Find reference backend if not specified
            if reference_backend is None:
                for backend_name in backends:
                    # First backend that has the content becomes the reference
                    if hasattr(self, "_async_check_content_availability"):
                        backend_result = await self._async_check_content_availability(
                            backend_name, content_id
                    else:
                        # Fallback to sync method
                        backend_result = self._check_content_availability(backend_name, content_id)

                    if backend_result.get("success", False):
                        reference_backend = backend_name
                        break

            # Verify content in each backend
            available_backends = []
            content_hash = None
            reference_content = None

            # Get reference content if a reference backend was found
            if reference_backend:
                # Try to use async methods first
                if hasattr(self, "_async_get_content_from_backend"):
                    reference_result = await self._async_get_content_from_backend(
                        reference_backend, content_id
                else:
                    # Fallback to sync method
                    reference_result = self._get_content_from_backend(reference_backend, content_id)

                if reference_result.get("success", False):
                    reference_content = reference_result.get("content")
                    if reference_content:
                        import hashlib

                        content_hash = hashlib.sha256(reference_content).hexdigest()

                        # Add reference backend to results
                        result["verification_results"][reference_backend] = {
                            "success": True,
                            "available": True,
                            "integrity": "reference",
                            "hash": content_hash,
                        }
                        available_backends.append(reference_backend)

            # Check availability and integrity in each backend
            for backend_name in backends:
                if backend_name == reference_backend:
                    # Already handled
                    continue

                # Try to use async methods first
                if hasattr(self, "_async_check_content_availability"):
                    availability_result = await self._async_check_content_availability(
                        backend_name, content_id
                else:
                    # Fallback to sync method
                    availability_result = self._check_content_availability(backend_name, content_id)

                if availability_result.get("success", False):
                    available_backends.append(backend_name)

                    # Check integrity if we have a reference hash
                    if content_hash and reference_content:
                        # Try to use async methods first
                        if hasattr(self, "_async_check_content_integrity"):
                            integrity_result = await self._async_check_content_integrity(
backend_name
content_id
reference_content
content_hash
                        else:
                            # Fallback to sync method
                            integrity_result = self._check_content_integrity(
backend_name
content_id
reference_content
content_hash

                        result["verification_results"][backend_name] = integrity_result
                    else:
                        result["verification_results"][backend_name] = {
                            "success": True,
                            "available": True,
                            "integrity": "unknown",
                        }
                else:
                    result["verification_results"][backend_name] = {
                        "success": False,
                        "available": False,
                        "error": availability_result.get("error"),
                        "error_type": availability_result.get("error_type"),
                    }

            # Update overall result
            result["success"] = len(available_backends) > 0
            result["available_backends"] = available_backends
            result["unavailable_backends"] = [b for b in backends if b not in available_backends]
            result["content_hash"] = content_hash
            result["reference_backend"] = reference_backend

            # Update stats
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def get_optimal_source(
        self, content_id: str, required_backends: Optional[List[str]] = None
        """
        Get the optimal source for content based on availability and performance.

        Args:
            content_id: Content identifier (CID)
            required_backends: List of backend names that must be checked

        Returns:
            Dictionary with optimal source information
        """
        start_time = time.time()

        result = self._create_result_dict("get_optimal_source")
        result.update({"content_id": content_id})

        try:
            # Determine which backends to check
            backends_to_check = required_backends or list(self.backends.keys())

            # Define backend priority (lower number = higher priority)
            backend_priorities = {
                "ipfs": 10,  # Local IPFS (fast)
                "s3": 20,  # S3 storage (often fast)
                "storacha": 30,  # Storacha (medium)
                "huggingface": 40,  # HuggingFace (medium)
                "lassie": 50,  # Lassie (varies)
                "filecoin": 60,  # Filecoin (slowest)
            }

            # Check availability in each backend
            available_backends = []

            for backend_name in backends_to_check:
                availability_result = self._check_content_availability(backend_name, content_id)

                if availability_result.get("success", False):
                    # Add to available backends with priority
                    priority = backend_priorities.get(backend_name, 100)
                    available_backends.append((backend_name, priority))

            if not available_backends:
                result["error"] = f"Content '{content_id}' not found in any backend"
                result["error_type"] = "ContentNotFoundError"
                return result

            # Sort backends by priority
            available_backends.sort(key=lambda x: x[1])

            # Select optimal source
            optimal_backend = available_backends[0][0]

            result["success"] = True
            result["optimal_backend"] = optimal_backend
            result["all_available_backends"] = [b[0] for b in available_backends]

            # Update stats
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_get_optimal_source(
        self, content_id: str, required_backends: Optional[List[str]] = None
        """
        Asynchronously get the optimal source for content based on availability and performance.

        Args:
            content_id: Content identifier (CID)
            required_backends: List of backend names that must be checked

        Returns:
            Dictionary with optimal source information
        """
        start_time = time.time()

        result = self._create_result_dict("get_optimal_source")
        result.update({"content_id": content_id})

        try:
            # Determine which backends to check
            backends_to_check = required_backends or list(self.backends.keys())

            # Define backend priority (lower number = higher priority)
            backend_priorities = {
                "ipfs": 10,  # Local IPFS (fast)
                "s3": 20,  # S3 storage (often fast)
                "storacha": 30,  # Storacha (medium)
                "huggingface": 40,  # HuggingFace (medium)
                "lassie": 50,  # Lassie (varies)
                "filecoin": 60,  # Filecoin (slowest)
            }

            # Check availability in each backend
            available_backends = []

            for backend_name in backends_to_check:
                # Try to use async method first
                if hasattr(self, "_async_check_content_availability"):
                    availability_result = await self._async_check_content_availability(
                        backend_name, content_id
                else:
                    # Fallback to sync method
                    availability_result = self._check_content_availability(backend_name, content_id)

                if availability_result.get("success", False):
                    # Add to available backends with priority
                    priority = backend_priorities.get(backend_name, 100)

                    # Adjust priority based on async capability (prefer async-capable backends)
                    backend_model = self.backends.get(backend_name)
                    if backend_model and (
                        hasattr(backend_model, "async_get_content")
                        or hasattr(backend_model, "async_cat")
                        or hasattr(backend_model, "async_download_file")
                        # Slightly boost priority for backends with async support
                        priority -= 2

                    available_backends.append((backend_name, priority))

            if not available_backends:
                result["error"] = f"Content '{content_id}' not found in any backend"
                result["error_type"] = "ContentNotFoundError"
                return result

            # Sort backends by priority
            available_backends.sort(key=lambda x: x[1])

            # Select optimal source
            optimal_backend = available_backends[0][0]

            result["success"] = True
            result["optimal_backend"] = optimal_backend
            result["all_available_backends"] = [b[0] for b in available_backends]

            # Update stats
            self._update_stats(result)

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def _find_content_source(self, content_id: str) -> Optional[str]:
        """
        Find a backend that has the specified content.

        Args:
            content_id: Content identifier (CID)

        Returns:
            Backend name or None if not found
        """
        for backend_name, backend_model in self.backends.items():
            availability_result = self._check_content_availability(backend_name, content_id)
            if availability_result.get("success", False):
                return backend_name

        return None

    def _check_content_availability(self, backend_name: str, content_id: str) -> Dict[str, Any]:
        """
        Check if content is available in a specific backend.

        Args:
            backend_name: Backend name
            content_id: Content identifier (CID)

        Returns:
            Dictionary with availability check result
        """
        result = {"success": False, "backend": backend_name, "content_id": content_id}

        try:
            if backend_name not in self.backends:
                result["error"] = f"Backend '{backend_name}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            backend_model = self.backends[backend_name]

            # Try backend-specific availability check
            if hasattr(backend_model, "check_content_availability"):
                check_result = backend_model.check_content_availability(content_id)
                return check_result

            # Fallback to various methods based on backend type
            if backend_name == "ipfs" and hasattr(backend_model, "ls"):
                # Use ls method if available
                ls_result = backend_model.ls(content_id)
                result["success"] = ls_result.get("success", False)
                if not result["success"]:
                    result["error"] = ls_result.get("error", "Content not found")
                    result["error_type"] = ls_result.get("error_type", "ContentNotFoundError")
            elif hasattr(backend_model, "has_object"):
                # Generic has_object method
                has_result = backend_model.has_object(content_id)
                result["success"] = has_result.get("success", False) and has_result.get(
                    "has", False
                if not result["success"]:
                    result["error"] = has_result.get("error", "Content not found")
                    result["error_type"] = has_result.get("error_type", "ContentNotFoundError")
            else:
                # Attempt to get metadata or head object
                if hasattr(backend_model, "head_object"):
                    head_result = backend_model.head_object(content_id)
                    result["success"] = head_result.get("success", False)
                    if not result["success"]:
                        result["error"] = head_result.get("error", "Content not found")
                        result["error_type"] = head_result.get("error_type", "ContentNotFoundError")
                elif hasattr(backend_model, "stat"):
                    # Try stat method (IPFS-like)
                    stat_result = backend_model.stat(content_id)
                    result["success"] = stat_result.get("success", False)
                    if not result["success"]:
                        result["error"] = stat_result.get("error", "Content not found")
                        result["error_type"] = stat_result.get("error_type", "ContentNotFoundError")
                else:
                    # Last resort: try to get content but don't download it fully
                    if hasattr(backend_model, "get_content"):
                        # Some backends might support head-like operations in get_content
                        # with a special option to only check existence
                        check_result = backend_model.get_content(content_id, {"check_only": True})
                        result["success"] = check_result.get("success", False)
                        if not result["success"]:
                            result["error"] = check_result.get("error", "Content not found")
                            result["error_type"] = check_result.get(
                                "error_type", "ContentNotFoundError"
                    else:
                        result["error"] = (
                            f"Backend '{backend_name}' does not support content availability check"
                        result["error_type"] = "UnsupportedOperationError"

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error checking content availability in {backend_name}: {e}")

        return result

    def _get_content_from_backend(
        self
        backend_name: str
        content_id: str
        options: Optional[Dict[str, Any]] = None,
        """
        Get content from a specific backend.

        Args:
            backend_name: Backend name
            content_id: Content identifier (CID)
            options: Backend-specific options

        Returns:
            Dictionary with content retrieval result
        """
        result = {"success": False, "backend": backend_name, "content_id": content_id}

        try:
            if backend_name not in self.backends:
                result["error"] = f"Backend '{backend_name}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            backend_model = self.backends[backend_name]

            # Try to get content using the most appropriate method
            if hasattr(backend_model, "get_content"):
                # Generic get_content method
                return backend_model.get_content(content_id, options)
            elif backend_name == "ipfs" and hasattr(backend_model, "cat"):
                # IPFS cat method
                # Check if head_only option is specified
                if options and options.get("head_only", False):
                    # Use stat instead of cat for head-only requests
                    if hasattr(backend_model, "stat"):
                        stat_result = backend_model.stat(content_id)
                        if stat_result.get("success", False):
                            result["success"] = True
                            result["size"] = stat_result.get(
                                "CumulativeSize", stat_result.get("Size", 0)
                            # Don't fetch actual content
                            result["content"] = None
                        else:
                            result["error"] = stat_result.get(
                                "error", "Failed to retrieve content metadata"
                            result["error_type"] = stat_result.get(
                                "error_type", "ContentRetrievalError"
                    else:
                        # Fallback to cat if stat is not available
                        cat_result = backend_model.cat(content_id)
                        if cat_result.get("success", False):
                            result["success"] = True
                            result["content"] = None  # Don't store actual content
                            result["size"] = len(cat_result.get("content", b""))
                        else:
                            result["error"] = cat_result.get("error", "Failed to retrieve content")
                            result["error_type"] = cat_result.get(
                                "error_type", "ContentRetrievalError"
                else:
                    # Normal content retrieval
                    cat_result = backend_model.cat(content_id)
                    if cat_result.get("success", False):
                        result["success"] = True
                        result["content"] = cat_result.get("content")
                        result["size"] = len(cat_result.get("content", b""))
                    else:
                        result["error"] = cat_result.get("error", "Failed to retrieve content")
                        result["error_type"] = cat_result.get("error_type", "ContentRetrievalError")
            elif hasattr(backend_model, "download_file"):
                # Create temporary file for download
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name

                # Download to temporary file
                download_options = {}
                if options:
                    download_options = options.copy()

                # Get bucket/key if provided
                bucket = download_options.pop("bucket", None)
                key = download_options.pop("key", content_id)

                if bucket:
                    download_result = backend_model.download_file(
                        bucket, key, temp_path, **download_options
                else:
                    download_result = backend_model.download_file(
                        key, temp_path, **download_options

                if download_result.get("success", False):
                    # Read content from temporary file
                    with open(temp_path, "rb") as f:
                        content = f.read()

                    # Update result
                    result["success"] = True
                    result["content"] = content
                    result["size"] = len(content)
                    result["location"] = download_result.get("location")
                else:
                    result["error"] = download_result.get("error", "Failed to download content")
                    result["error_type"] = download_result.get(
                        "error_type", "ContentRetrievalError"

                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            else:
                result["error"] = f"Backend '{backend_name}' does not support content retrieval"
                result["error_type"] = "UnsupportedOperationError"

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error getting content from {backend_name}: {e}")

        return result

    def _store_content_in_backend(
        self
        backend_name: str
        content_id: str
        content: bytes
        options: Optional[Dict[str, Any]] = None,
        """
        Store content in a specific backend.

        Args:
            backend_name: Backend name
            content_id: Content identifier (CID)
            content: Content data
            options: Backend-specific options

        Returns:
            Dictionary with content storage result
        """
        result = {"success": False, "backend": backend_name, "content_id": content_id}

        try:
            if backend_name not in self.backends:
                result["error"] = f"Backend '{backend_name}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            backend_model = self.backends[backend_name]

            # Try to store content using the most appropriate method
            if hasattr(backend_model, "put_content"):
                # Generic put_content method
                return backend_model.put_content(content_id, content, options)
            elif backend_name == "ipfs" and hasattr(backend_model, "add"):
                # IPFS add method
                add_result = backend_model.add(content)
                if add_result.get("success", False):
                    result["success"] = True
                    result["cid"] = add_result.get("cid") or content_id
                    result["size"] = len(content)

                    # Pin if requested
                    if options and options.get("pin", True):
                        backend_model.pin_add(result["cid"])
                else:
                    result["error"] = add_result.get("error", "Failed to add content")
                    result["error_type"] = add_result.get("error_type", "ContentStorageError")
            elif hasattr(backend_model, "upload_file"):
                # Create temporary file for upload
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                # Upload from temporary file
                upload_options = {}
                if options:
                    upload_options = options.copy()

                # Get bucket/key if provided
                bucket = upload_options.pop("bucket", None)
                key = upload_options.pop("key", content_id)

                if bucket:
                    upload_result = backend_model.upload_file(
                        temp_path, bucket, key, **upload_options
                else:
                    upload_result = backend_model.upload_file(temp_path, key, **upload_options)

                # Update result
                result["success"] = upload_result.get("success", False)
                if result["success"]:
                    result["location"] = upload_result.get("location")
                    result["size"] = len(content)
                else:
                    result["error"] = upload_result.get("error", "Failed to upload content")
                    result["error_type"] = upload_result.get("error_type", "ContentStorageError")

                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            else:
                result["error"] = f"Backend '{backend_name}' does not support content storage"
                result["error_type"] = "UnsupportedOperationError"

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error storing content in {backend_name}: {e}")

        return result

    def _check_content_integrity(
        self
        backend_name: str
        content_id: str
        reference_content: bytes
        reference_hash: str
        """
        Check content integrity by comparing with reference content.

        Args:
            backend_name: Backend name
            content_id: Content identifier (CID)
            reference_content: Reference content to compare against
            reference_hash: Hash of reference content

        Returns:
            Dictionary with integrity check result
        """
        result = {
            "success": False,
            "backend": backend_name,
            "content_id": content_id,
            "available": False,
            "integrity": "unknown",
        }

        try:
            # Get content from backend
            content_result = self._get_content_from_backend(backend_name, content_id)

            if not content_result.get("success", False):
                result["error"] = content_result.get("error", "Failed to retrieve content")
                result["error_type"] = content_result.get("error_type", "ContentRetrievalError")
                return result

            # Content is available
            result["available"] = True

            # Check content integrity
            content = content_result.get("content")
            if not content:
                result["integrity"] = "empty"
                result["success"] = False
                result["error"] = "Empty content returned"
                result["error_type"] = "ContentIntegrityError"
                return result

            # Compute hash of content
            import hashlib

            content_hash = hashlib.sha256(content).hexdigest()
            result["hash"] = content_hash

            # Compare hashes
            if content_hash == reference_hash:
                result["integrity"] = "valid"
                result["success"] = True
            else:
                result["integrity"] = "invalid"
                result["success"] = False
                result["error"] = "Content hash mismatch"
                result["error_type"] = "ContentIntegrityError"

                # Include size difference for debugging
                result["reference_size"] = len(reference_content)
                result["actual_size"] = len(content)
                result["size_difference"] = len(content) - len(reference_content)

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error checking content integrity in {backend_name}: {e}")

        return result

    def apply_replication_policy(self, content_id: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a replication policy to content across storage backends.

        The policy specifies how content should be distributed across backends
        based on various criteria like content type, size, and importance.

        Args:
            content_id: Content identifier (CID)
            policy: Policy configuration dictionary with these possible keys:
                - target_backends: List of backend names to consider
                - tier_requirements: Mapping of tier names to requirement sets
                - content_type: Type of content for policy decisions
                - importance: Importance level (high, medium, low)
                - size_threshold: Size threshold for backend selection
                - cleanup_source: Whether to remove from source after replication
                - verify: Whether to verify replication success

        Returns:
            Dictionary with replication policy application result
        """
        start_time = time.time()

        result = self._create_result_dict("apply_replication_policy")
        result.update(
            {
                "content_id": content_id,
                "policy_applied": False,
                "backends_selected": [],
                "replication_results": {},
            }

        try:
            # Get policy parameters
            target_backends = policy.get("target_backends", list(self.backends.keys()))
            tier_requirements = policy.get("tier_requirements", {})
            cleanup_source = policy.get("cleanup_source", False)
            verify = policy.get("verify", True)

            # Find current location of content
            source_backend = self._find_content_source(content_id)
            if not source_backend:
                result["error"] = f"Content '{content_id}' not found in any available backend"
                result["error_type"] = "ContentNotFoundError"
                return result

            result["source_backend"] = source_backend

            # Get content metadata
            metadata = self._get_content_metadata(source_backend, content_id)
            if not metadata.get("success", False):
                result["error"] = metadata.get("error", "Failed to get content metadata")
                result["error_type"] = metadata.get("error_type", "MetadataRetrievalError")
                return result

            # Select backends based on policy and content characteristics
            selected_backends = self._select_backends_by_policy(
                content_id, metadata, target_backends, tier_requirements

            if source_backend in selected_backends:
                # Remove source from target list if it's already there
                selected_backends.remove(source_backend)

            if not selected_backends:
                # No backends selected, just verify source
                if verify:
                    verify_result = self.verify_content(content_id, [source_backend])
                    result["verification_result"] = verify_result

                result["success"] = True
                result["policy_applied"] = True
                result["backends_selected"] = []
                result["message"] = "No additional backends selected by policy"
                return result

            # Replicate to selected backends
            replication_result = self.replicate_content(
content_id=content_id
target_backends=selected_backends
source_backend=source_backend
                options=policy.get("backend_options", {}),

            # Update result with replication details
            result["replication_results"] = replication_result.get("replication_results", {})
            result["successful_backends"] = replication_result.get("successful_backends", [])
            result["failed_backends"] = replication_result.get("failed_backends", [])
            result["backends_selected"] = selected_backends

            # Verify replication if requested
            if verify and result["successful_backends"]:
                verify_backends = [source_backend] + result["successful_backends"]
                verify_result = self.verify_content(
                    content_id, verify_backends, reference_backend=source_backend
                result["verification_result"] = verify_result

            # Clean up source if requested and replication was successful
            if cleanup_source and result["successful_backends"]:
                if hasattr(self.backends[source_backend], "delete_content"):
                    delete_result = self.backends[source_backend].delete_content(content_id)
                    result["source_cleanup_result"] = delete_result
                else:
                    result["source_cleanup_result"] = {
                        "success": False,
                        "error": f"Source backend '{source_backend}' does not support content deletion",
                        "error_type": "UnsupportedOperationError",
                    }

            # Set overall success based on selected backends
            result["success"] = len(result["successful_backends"]) == len(selected_backends)
            result["policy_applied"] = True

            # Update stats
            self._update_stats(result, replication_result.get("bytes_transferred", 0))

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_apply_replication_policy(
        self, content_id: str, policy: Dict[str, Any]
        """
        Asynchronously apply a replication policy to content across storage backends.

        The policy specifies how content should be distributed across backends
        based on various criteria like content type, size, and importance.

        Args:
            content_id: Content identifier (CID)
            policy: Policy configuration dictionary with these possible keys:
                - target_backends: List of backend names to consider
                - tier_requirements: Mapping of tier names to requirement sets
                - content_type: Type of content for policy decisions
                - importance: Importance level (high, medium, low)
                - size_threshold: Size threshold for backend selection
                - cleanup_source: Whether to remove from source after replication
                - verify: Whether to verify replication success

        Returns:
            Dictionary with replication policy application result
        """
        start_time = time.time()

        result = self._create_result_dict("apply_replication_policy")
        result.update(
            {
                "content_id": content_id,
                "policy_applied": False,
                "backends_selected": [],
                "replication_results": {},
            }

        try:
            # Get policy parameters
            target_backends = policy.get("target_backends", list(self.backends.keys()))
            tier_requirements = policy.get("tier_requirements", {})
            cleanup_source = policy.get("cleanup_source", False)
            verify = policy.get("verify", True)

            # Find current location of content
            if hasattr(self, "_async_find_content_source"):
                source_backend = await self._async_find_content_source(content_id)
            else:
                source_backend = self._find_content_source(content_id)

            if not source_backend:
                result["error"] = f"Content '{content_id}' not found in any available backend"
                result["error_type"] = "ContentNotFoundError"
                return result

            result["source_backend"] = source_backend

            # Get content metadata
            if hasattr(self, "_async_get_content_metadata"):
                metadata = await self._async_get_content_metadata(source_backend, content_id)
            else:
                metadata = self._get_content_metadata(source_backend, content_id)

            if not metadata.get("success", False):
                result["error"] = metadata.get("error", "Failed to get content metadata")
                result["error_type"] = metadata.get("error_type", "MetadataRetrievalError")
                return result

            # Select backends based on policy and content characteristics
            if hasattr(self, "_async_select_backends_by_policy"):
                selected_backends = await self._async_select_backends_by_policy(
                    content_id, metadata, target_backends, tier_requirements
            else:
                selected_backends = self._select_backends_by_policy(
                    content_id, metadata, target_backends, tier_requirements

            if source_backend in selected_backends:
                # Remove source from target list if it's already there
                selected_backends.remove(source_backend)

            if not selected_backends:
                # No backends selected, just verify source
                if verify:
                    if hasattr(self, "async_verify_content"):
                        verify_result = await self.async_verify_content(
                            content_id, [source_backend]
                    else:
                        verify_result = self.verify_content(content_id, [source_backend])

                    result["verification_result"] = verify_result

                result["success"] = True
                result["policy_applied"] = True
                result["backends_selected"] = []
                result["message"] = "No additional backends selected by policy"
                return result

            # Replicate to selected backends
            if hasattr(self, "async_replicate_content"):
                replication_result = await self.async_replicate_content(
content_id=content_id
target_backends=selected_backends
source_backend=source_backend
                    options=policy.get("backend_options", {}),
            else:
                replication_result = self.replicate_content(
content_id=content_id
target_backends=selected_backends
source_backend=source_backend
                    options=policy.get("backend_options", {}),

            # Update result with replication details
            result["replication_results"] = replication_result.get("replication_results", {})
            result["successful_backends"] = replication_result.get("successful_backends", [])
            result["failed_backends"] = replication_result.get("failed_backends", [])
            result["backends_selected"] = selected_backends

            # Verify replication if requested
            if verify and result["successful_backends"]:
                verify_backends = [source_backend] + result["successful_backends"]

                if hasattr(self, "async_verify_content"):
                    verify_result = await self.async_verify_content(
                        content_id, verify_backends, reference_backend=source_backend
                else:
                    verify_result = self.verify_content(
                        content_id, verify_backends, reference_backend=source_backend

                result["verification_result"] = verify_result

            # Clean up source if requested and replication was successful
            if cleanup_source and result["successful_backends"]:
                source_model = self.backends[source_backend]

                if hasattr(source_model, "async_delete_content"):
                    delete_result = await source_model.async_delete_content(content_id)
                    result["source_cleanup_result"] = delete_result
                elif hasattr(source_model, "delete_content"):
                    delete_result = source_model.delete_content(content_id)
                    result["source_cleanup_result"] = delete_result
                else:
                    result["source_cleanup_result"] = {
                        "success": False,
                        "error": f"Source backend '{source_backend}' does not support content deletion",
                        "error_type": "UnsupportedOperationError",
                    }

            # Set overall success based on selected backends
            result["success"] = len(result["successful_backends"]) == len(selected_backends)
            result["policy_applied"] = True

            # Update stats
            self._update_stats(result, replication_result.get("bytes_transferred", 0))

        except Exception as e:
            self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    def _get_content_metadata(self, backend_name: str, content_id: str) -> Dict[str, Any]:
        """
        Get metadata for content from a specific backend.

        Args:
            backend_name: Backend name
            content_id: Content identifier (CID)

        Returns:
            Dictionary with content metadata
        """
        result = {"success": False, "backend": backend_name, "content_id": content_id}

        try:
            if backend_name not in self.backends:
                result["error"] = f"Backend '{backend_name}' not found"
                result["error_type"] = "BackendNotFoundError"
                return result

            backend_model = self.backends[backend_name]

            # Try to get metadata using the most appropriate method
            if hasattr(backend_model, "get_content_metadata"):
                return backend_model.get_content_metadata(content_id)
            elif backend_name == "ipfs" and hasattr(backend_model, "stat"):
                # Try IPFS stat method
                stat_result = backend_model.stat(content_id)
                if stat_result.get("success", False):
                    result["success"] = True
                    result["size"] = stat_result.get("CumulativeSize", stat_result.get("Size", 0))
                    result["block_count"] = stat_result.get("NumLinks", 0)
                    result["content_type"] = stat_result.get("Type", "unknown")
                    result["hash"] = stat_result.get("Hash", content_id)
                else:
                    result["error"] = stat_result.get("error", "Failed to get content stats")
                    result["error_type"] = stat_result.get("error_type", "MetadataRetrievalError")
            elif hasattr(backend_model, "head_object"):
                # Try S3-like head_object method
                head_result = backend_model.head_object(content_id)
                if head_result.get("success", False):
                    result["success"] = True
                    result["size"] = head_result.get("ContentLength", 0)
                    result["content_type"] = head_result.get("ContentType", "unknown")
                    result["etag"] = head_result.get("ETag", "")
                    result["last_modified"] = head_result.get("LastModified", "")
                    result["metadata"] = head_result.get("Metadata", {})
                else:
                    result["error"] = head_result.get("error", "Failed to get content metadata")
                    result["error_type"] = head_result.get("error_type", "MetadataRetrievalError")
            else:
                # Fallback: get content but only check size
                content_result = self._get_content_from_backend(
                    backend_name, content_id, {"head_only": True}
                if content_result.get("success", False):
                    result["success"] = True
                    result["size"] = content_result.get("size", 0)
                    result["content_type"] = "unknown"
                else:
                    result["error"] = content_result.get("error", "Failed to get content metadata")
                    result["error_type"] = content_result.get(
                        "error_type", "MetadataRetrievalError"

        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error getting content metadata from {backend_name}: {e}")

        return result

    def _select_backends_by_policy(
        self
        content_id: str
        metadata: Dict[str, Any]
        target_backends: List[str]
        tier_requirements: Dict[str, Any]
        """
        Select appropriate backends based on content characteristics and policy.

        Args:
            content_id: Content identifier (CID)
            metadata: Content metadata dictionary
            target_backends: List of target backend names to consider
            tier_requirements: Mapping of tier names to requirement sets

        Returns:
            List of selected backend names
        """
        selected_backends = []

        # Get content size (default to 0 if not available)
        content_size = metadata.get("size", 0)
        content_type = metadata.get("content_type", "unknown")

        # Define backend tiers if not provided
        if not tier_requirements:
            tier_requirements = {
                "hot": {
                    "max_size": 10 * 1024 * 1024,  # 10MB
                    "backends": ["ipfs"],
                    "required": True,
}
                "warm": {
                    "max_size": 100 * 1024 * 1024,  # 100MB
                    "backends": ["s3", "storacha"],
                    "required": False,
}
                "cold": {
                    "min_size": 10 * 1024 * 1024,  # 10MB
                    "backends": ["filecoin"],
                    "required": False,
}
            }

        # Process each tier
        for tier_name, requirements in tier_requirements.items():
            # Skip tier if size requirements don't match
            if "min_size" in requirements and content_size < requirements["min_size"]:
                continue
            if "max_size" in requirements and content_size > requirements["max_size"]:
                continue

            # Skip tier if content type requirements don't match
            if (
                "content_types" in requirements
                and content_type not in requirements["content_types"]
                continue

            # Get backends for this tier
            tier_backends = requirements.get("backends", [])

            # Find intersection with target backends
            available_backends = [b for b in tier_backends if b in target_backends]

            # Add to selected backends
            selected_backends.extend(available_backends)

        # Remove duplicates while preserving order
        unique_backends = []
        for backend in selected_backends:
            if backend not in unique_backends:
                unique_backends.append(backend)

        return unique_backends
