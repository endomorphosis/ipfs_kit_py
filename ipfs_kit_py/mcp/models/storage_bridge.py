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
from typing import Dict, List, Any, Optional, Tuple

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
            f"Storage Bridge Model initialized with backends: {', '.join(self.backends.keys())}")

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
        self, result: Dict[str, Any], error: Exception, message: Optional[str] = None) -> Dict[str, Any]:
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

    def _find_content_source(self, content_id: str) -> Optional[str]:
        """
        Find a backend that has the specified content.

        Args:
            content_id: Content identifier (CID)

        Returns:
            Name of backend that has the content, or None if not found
        """
        for backend_name, backend_model in self.backends.items():
            has_content = False
            
            # Check if the backend has the content
            if hasattr(backend_model, "has_content"):
                try:
                    result = backend_model.has_content(content_id)
                    has_content = result.get("success", False) and result.get("has_content", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif hasattr(backend_model, "exists") and callable(getattr(backend_model, "exists")):
                try:
                    result = backend_model.exists(content_id)
                    has_content = result if isinstance(result, bool) else result.get("success", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif backend_name == "ipfs" and hasattr(backend_model, "cat"):
                try:
                    # Try to get the content directly
                    result = backend_model.cat(content_id)
                    has_content = result.get("success", False)
                except Exception as e:
                    # If we get an error, the content is not available
                    logger.debug(f"Error checking if IPFS has content {content_id}: {str(e)}")
                    continue
            
            if has_content:
                return backend_name
        
        return None

    async def _async_find_content_source(self, content_id: str) -> Optional[str]:
        """
        Asynchronously find a backend that has the specified content.

        Args:
            content_id: Content identifier (CID)

        Returns:
            Name of backend that has the content, or None if not found
        """
        for backend_name, backend_model in self.backends.items():
            has_content = False
            
            # Check if the backend has the content using async methods if available
            if hasattr(backend_model, "async_has_content"):
                try:
                    result = await backend_model.async_has_content(content_id)
                    has_content = result.get("success", False) and result.get("has_content", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif hasattr(backend_model, "has_content"):
                try:
                    result = backend_model.has_content(content_id)
                    has_content = result.get("success", False) and result.get("has_content", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif hasattr(backend_model, "async_exists") and callable(getattr(backend_model, "async_exists")):
                try:
                    result = await backend_model.async_exists(content_id)
                    has_content = result if isinstance(result, bool) else result.get("success", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif hasattr(backend_model, "exists") and callable(getattr(backend_model, "exists")):
                try:
                    result = backend_model.exists(content_id)
                    has_content = result if isinstance(result, bool) else result.get("success", False)
                except Exception as e:
                    logger.warning(f"Error checking if {backend_name} has content {content_id}: {str(e)}")
                    continue
            elif backend_name == "ipfs":
                if hasattr(backend_model, "async_cat"):
                    try:
                        # Try to get the content directly
                        result = await backend_model.async_cat(content_id)
                        has_content = result.get("success", False)
                    except Exception as e:
                        # If we get an error, the content is not available
                        logger.debug(f"Error checking if IPFS has content {content_id}: {str(e)}")
                        continue
                elif hasattr(backend_model, "cat"):
                    try:
                        # Try to get the content directly
                        result = backend_model.cat(content_id)
                        has_content = result.get("success", False)
                    except Exception as e:
                        # If we get an error, the content is not available
                        logger.debug(f"Error checking if IPFS has content {content_id}: {str(e)}")
                        continue
            
            if has_content:
                return backend_name
        
        return None

    def _get_content_from_backend(
        self, backend_name: str, content_id: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get content from a specific backend.

        Args:
            backend_name: Name of backend to get content from
            content_id: Content identifier (CID)
            options: Backend-specific options

        Returns:
            Dictionary with content retrieval result
        """
        # Default result for error cases
        result = {
            "success": False,
            "operation": "get_content",
            "backend": backend_name,
            "content_id": content_id,
        }

        if backend_name not in self.backends:
            result["error"] = f"Backend '{backend_name}' not found"
            result["error_type"] = "BackendNotFoundError"
            return result

        backend_model = self.backends[backend_name]
        source_options = options or {}

        try:
            # Try different methods to get content based on the backend type
            if hasattr(backend_model, "get_content"):
                return backend_model.get_content(content_id, source_options)
            elif backend_name == "ipfs" and hasattr(backend_model, "cat"):
                cat_result = backend_model.cat(content_id)
                if cat_result and cat_result.get("success", False):
                    return {
                        "success": True,
                        "operation": "get_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "content": cat_result.get("content"),
                        "location": f"ipfs://{content_id}",
                    }
                return cat_result
            elif hasattr(backend_model, "download_file"):
                # Create temporary file to store the content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name

                # Get key or path in source backend
                key = content_id
                bucket = None
                if source_options:
                    key = source_options.get("key", key)
                    bucket = source_options.get("bucket", None)

                # Download to temporary file
                dl_result = None
                if bucket:
                    dl_result = backend_model.download_file(bucket, key, temp_path)
                else:
                    dl_result = backend_model.download_file(key, temp_path)

                # Check if download was successful
                if dl_result and dl_result.get("success", False):
                    # Read content from temporary file
                    with open(temp_path, "rb") as f:
                        content = f.read()

                    # Clean up temporary file
                    os.unlink(temp_path)

                    return {
                        "success": True,
                        "operation": "get_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "content": content,
                        "location": dl_result.get("location"),
                    }
                else:
                    # Clean up temporary file if it exists
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    
                    # Return the download result
                    return dl_result or {
                        "success": False,
                        "operation": "get_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "error": "Failed to download file",
                        "error_type": "DownloadError",
                    }
            else:
                result["error"] = f"Backend '{backend_name}' does not support content retrieval"
                result["error_type"] = "UnsupportedOperationError"
                return result
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error getting content from {backend_name}: {str(e)}")
            return result

    async def _async_get_content_from_backend(
        self, backend_name: str, content_id: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously get content from a specific backend.

        Args:
            backend_name: Name of backend to get content from
            content_id: Content identifier (CID)
            options: Backend-specific options

        Returns:
            Dictionary with content retrieval result
        """
        # Default result for error cases
        result = {
            "success": False,
            "operation": "get_content",
            "backend": backend_name,
            "content_id": content_id,
        }

        if backend_name not in self.backends:
            result["error"] = f"Backend '{backend_name}' not found"
            result["error_type"] = "BackendNotFoundError"
            return result

        backend_model = self.backends[backend_name]
        source_options = options or {}

        try:
            # Try different async methods to get content based on the backend type
            if hasattr(backend_model, "async_get_content"):
                return await backend_model.async_get_content(content_id, source_options)
            elif hasattr(backend_model, "get_content"):
                return backend_model.get_content(content_id, source_options)
            elif backend_name == "ipfs":
                if hasattr(backend_model, "async_cat"):
                    cat_result = await backend_model.async_cat(content_id)
                    if cat_result and cat_result.get("success", False):
                        return {
                            "success": True,
                            "operation": "get_content",
                            "backend": backend_name,
                            "content_id": content_id,
                            "content": cat_result.get("content"),
                            "location": f"ipfs://{content_id}",
                        }
                    return cat_result
                elif hasattr(backend_model, "cat"):
                    cat_result = backend_model.cat(content_id)
                    if cat_result and cat_result.get("success", False):
                        return {
                            "success": True,
                            "operation": "get_content",
                            "backend": backend_name,
                            "content_id": content_id,
                            "content": cat_result.get("content"),
                            "location": f"ipfs://{content_id}",
                        }
                    return cat_result
            elif hasattr(backend_model, "async_download_file"):
                # Create temporary file to store the content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_path = temp_file.name

                # Get key or path in source backend
                key = content_id
                bucket = None
                if source_options:
                    key = source_options.get("key", key)
                    bucket = source_options.get("bucket", None)

                # Download to temporary file
                dl_result = None
                if bucket:
                    dl_result = await backend_model.async_download_file(bucket, key, temp_path)
                else:
                    dl_result = await backend_model.async_download_file(key, temp_path)

                # Check if download was successful
                if dl_result and dl_result.get("success", False):
                    # Read content from temporary file
                    with open(temp_path, "rb") as f:
                        content = f.read()

                    # Clean up temporary file
                    os.unlink(temp_path)

                    return {
                        "success": True,
                        "operation": "get_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "content": content,
                        "location": dl_result.get("location"),
                    }
                else:
                    # Clean up temporary file if it exists
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                    
                    # Return the download result
                    return dl_result or {
                        "success": False,
                        "operation": "get_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "error": "Failed to download file",
                        "error_type": "DownloadError",
                    }
            elif hasattr(backend_model, "download_file"):
                # Fallback to synchronous method
                return self._get_content_from_backend(backend_name, content_id, options)
            else:
                result["error"] = f"Backend '{backend_name}' does not support content retrieval"
                result["error_type"] = "UnsupportedOperationError"
                return result
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error getting content from {backend_name}: {str(e)}")
            return result

    def _store_content_in_backend(
        self, backend_name: str, content_id: str, content: bytes, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store content in a specific backend.

        Args:
            backend_name: Name of backend to store content in
            content_id: Content identifier (CID)
            content: Content to store
            options: Backend-specific options

        Returns:
            Dictionary with content storage result
        """
        # Default result for error cases
        result = {
            "success": False,
            "operation": "store_content",
            "backend": backend_name,
            "content_id": content_id,
        }

        if backend_name not in self.backends:
            result["error"] = f"Backend '{backend_name}' not found"
            result["error_type"] = "BackendNotFoundError"
            return result

        backend_model = self.backends[backend_name]
        target_options = options or {}

        try:
            # Try different methods to store content based on the backend type
            if hasattr(backend_model, "put_content"):
                return backend_model.put_content(content_id, content, target_options)
            elif hasattr(backend_model, "add_content"):
                return backend_model.add_content(content, target_options)
            elif backend_name == "ipfs" and hasattr(backend_model, "add"):
                add_result = backend_model.add(content)
                if add_result and add_result.get("success", False):
                    # Map the result to standard format
                    return {
                        "success": True,
                        "operation": "store_content",
                        "backend": backend_name,
                        "content_id": content_id,
                        "location": f"ipfs://{add_result.get('cid', content_id)}",
                    }
                return add_result
            elif hasattr(backend_model, "upload_file"):
                # Create temporary file to store the content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                # Get key or path in target backend
                key = content_id
                bucket = None
                if target_options:
                    key = target_options.get("key", key)
                    bucket = target_options.get("bucket", None)

                # Upload from temporary file
                up_result = None
                if bucket:
                    up_result = backend_model.upload_file(temp_path, bucket, key)
                else:
                    up_result = backend_model.upload_file(temp_path, key)

                # Clean up temporary file
                os.unlink(temp_path)

                # Return the upload result
                return up_result or {
                    "success": False,
                    "operation": "store_content",
                    "backend": backend_name,
                    "content_id": content_id,
                    "error": "Failed to upload file",
                    "error_type": "UploadError",
                }
            else:
                result["error"] = f"Backend '{backend_name}' does not support content storage"
                result["error_type"] = "UnsupportedOperationError"
                return result
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error storing content in {backend_name}: {str(e)}")
            return result

    async def _async_store_content_in_backend(
        self, backend_name: str, content_id: str, content: bytes, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously store content in a specific backend.

        Args:
            backend_name: Name of backend to store content in
            content_id: Content identifier (CID)
            content: Content to store
            options: Backend-specific options

        Returns:
            Dictionary with content storage result
        """
        # Default result for error cases
        result = {
            "success": False,
            "operation": "store_content",
            "backend": backend_name,
            "content_id": content_id,
        }

        if backend_name not in self.backends:
            result["error"] = f"Backend '{backend_name}' not found"
            result["error_type"] = "BackendNotFoundError"
            return result

        backend_model = self.backends[backend_name]
        target_options = options or {}

        try:
            # Try different async methods to store content based on the backend type
            if hasattr(backend_model, "async_put_content"):
                return await backend_model.async_put_content(content_id, content, target_options)
            elif hasattr(backend_model, "put_content"):
                return backend_model.put_content(content_id, content, target_options)
            elif hasattr(backend_model, "async_add_content"):
                return await backend_model.async_add_content(content, target_options)
            elif hasattr(backend_model, "add_content"):
                return backend_model.add_content(content, target_options)
            elif backend_name == "ipfs":
                if hasattr(backend_model, "async_add"):
                    add_result = await backend_model.async_add(content)
                    if add_result and add_result.get("success", False):
                        # Map the result to standard format
                        return {
                            "success": True,
                            "operation": "store_content",
                            "backend": backend_name,
                            "content_id": content_id,
                            "location": f"ipfs://{add_result.get('cid', content_id)}",
                        }
                    return add_result
                elif hasattr(backend_model, "add"):
                    add_result = backend_model.add(content)
                    if add_result and add_result.get("success", False):
                        # Map the result to standard format
                        return {
                            "success": True,
                            "operation": "store_content",
                            "backend": backend_name,
                            "content_id": content_id,
                            "location": f"ipfs://{add_result.get('cid', content_id)}",
                        }
                    return add_result
            elif hasattr(backend_model, "async_upload_file"):
                # Create temporary file to store the content
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                # Get key or path in target backend
                key = content_id
                bucket = None
                if target_options:
                    key = target_options.get("key", key)
                    bucket = target_options.get("bucket", None)

                # Upload from temporary file
                up_result = None
                if bucket:
                    up_result = await backend_model.async_upload_file(temp_path, bucket, key)
                else:
                    up_result = await backend_model.async_upload_file(temp_path, key)

                # Clean up temporary file
                os.unlink(temp_path)

                # Return the upload result
                return up_result or {
                    "success": False,
                    "operation": "store_content",
                    "backend": backend_name,
                    "content_id": content_id,
                    "error": "Failed to upload file",
                    "error_type": "UploadError",
                }
            elif hasattr(backend_model, "upload_file"):
                # Fallback to synchronous method
                return self._store_content_in_backend(backend_name, content_id, content, options)
            else:
                result["error"] = f"Backend '{backend_name}' does not support content storage"
                result["error_type"] = "UnsupportedOperationError"
                return result
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            logger.error(f"Error storing content in {backend_name}: {str(e)}")
            return result

    def transfer_content(
        self,
        source_backend: str,
        target_backend: str,
        content_id: str,
        source_options: Optional[Dict[str, Any]] = None,
        target_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        result.update({
            "source_backend": source_backend,
            "target_backend": target_backend,
            "content_id": content_id,
        })

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

            # Get content from source backend
            source_result = self._get_content_from_backend(source_backend, content_id, source_options)

            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}")
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            # Extract content from source result
            content = source_result.get("content", None)
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Store content in target backend
            target_result = self._store_content_in_backend(
                target_backend, content_id, content, target_options)

            if not target_result.get("success", False):
                result["error"] = target_result.get(
                    "error", f"Failed to store content in {target_backend}")
                result["error_type"] = target_result.get("error_type", "ContentStorageError")
                return result

            # Transfer successful
            result["success"] = True
            result["source_location"] = source_result.get("location", None)
            result["target_location"] = target_result.get("location", None)
            result["bytes_transferred"] = (
                len(content) if isinstance(content, (bytes, bytearray)) else None)

            # Update stats
            self._update_stats(result, result["bytes_transferred"])

        except Exception as e:
            result = self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result

    async def async_transfer_content(
        self,
        source_backend: str,
        target_backend: str,
        content_id: str,
        source_options: Optional[Dict[str, Any]] = None,
        target_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Asynchronously transfer content between storage backends.

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
        result.update({
            "source_backend": source_backend,
            "target_backend": target_backend,
            "content_id": content_id,
        })

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

            # Get content from source backend
            source_result = await self._async_get_content_from_backend(source_backend, content_id, source_options)

            if not source_result.get("success", False):
                result["error"] = source_result.get(
                    "error", f"Failed to retrieve content from {source_backend}")
                result["error_type"] = source_result.get("error_type", "ContentRetrievalError")
                return result

            # Extract content from source result
            content = source_result.get("content", None)
            if not content:
                result["error"] = f"No content returned from source backend '{source_backend}'"
                result["error_type"] = "ContentRetrievalError"
                return result

            # Store content in target backend
            target_result = await self._async_store_content_in_backend(
                target_backend, content_id, content, target_options)

            if not target_result.get("success", False):
                result["error"] = target_result.get(
                    "error", f"Failed to store content in {target_backend}")
                result["error_type"] = target_result.get("error_type", "ContentStorageError")
                return result

            # Transfer successful
            result["success"] = True
            result["source_location"] = source_result.get("location", None)
            result["target_location"] = target_result.get("location", None)
            result["bytes_transferred"] = (
                len(content) if isinstance(content, (bytes, bytearray)) else None)

            # Update stats
            self._update_stats(result, result["bytes_transferred"])

        except Exception as e:
            result = self._handle_error(result, e)

        # Add duration
        result["duration_ms"] = (time.time() - start_time) * 1000

        return result