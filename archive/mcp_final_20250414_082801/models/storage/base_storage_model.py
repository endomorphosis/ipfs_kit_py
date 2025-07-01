"""
BaseStorageModel module for MCP server.

This module provides the base class for all storage backend models in the MCP server.
It defines a standard interface and common functionality for all storage backends,
ensuring consistent behavior and error handling across different implementations.
"""

import time
import uuid
import logging
import os
import anyio
import inspect
from functools import wraps
from typing import Dict, Any, Optional, Union, Callable, TypeVar, Awaitable, Set

# Configure logger
logger = logging.getLogger(__name__)

# Define type for event listeners
T = TypeVar("T")
EventListener = Callable[[str, Dict[str, Any]], Awaitable[None]]
SyncEventListener = Callable[[str, Dict[str, Any]], None]


class BaseStorageModel:
    """
    Base model for storage backend operations.

    This class provides a foundation for all storage backend models, including
    common functionality like statistics tracking, error handling, and operation
    result formatting. All specific storage backend models should inherit from
    this class and implement their specific operations.

    It provides both synchronous and asynchronous interfaces for all operations,
    with standardized error handling, retry mechanisms, event notification,
    and comprehensive metrics collection.
    """

    def __init__(
        self,
        kit_instance: Any = None,
        cache_manager: Any = None,
        credential_manager: Any = None,
    ):
        """
        Initialize storage model with dependencies.

        Args:
            kit_instance: Storage backend kit instance (e.g., s3_kit, huggingface_kit)
            cache_manager: Cache manager for caching operations
            credential_manager: Credential manager for handling authentication
        """
        self.kit = kit_instance
        self.cache_manager = cache_manager
        self.credential_manager = credential_manager
        self.backend_name = self._get_backend_name()
        self.operation_stats = self._initialize_stats()
        self.configuration = {}

        # Event notification system
        self.listeners: Set[Union[EventListener, SyncEventListener]] = set()
        self.max_listeners = 10

        # Retry configuration
        self.default_retry_config = {
            "max_retries": 3,
            "retry_delay": 1.0,
            "backoff_factor": 2.0,
            "max_delay": 30.0,
            "retry_on_exceptions": ["ConnectionError", "Timeout", "RequestException"],
            "retry_on_status_codes": [429, 500, 502, 503, 504],
        }

        logger.info(f"{self.backend_name} Model initialized")

    def _get_backend_name(self) -> str:
        """
        Get the name of the storage backend.

        This method should be overridden by subclasses to return their specific backend name.

        Returns:
            str: Name of the storage backend
        """
        # Default implementation uses class name without "Model" suffix
        class_name = self.__class__.__name__
        if class_name.endswith("Model"):
            return class_name[:-5]
        return class_name

    def _initialize_stats(self) -> Dict[str, Any]:
        """
        Initialize operation statistics tracking.

        Returns:
            Dict: Dictionary with initial statistics values
        """
        return {
            "upload_count": 0,
            "download_count": 0,
            "list_count": 0,
            "delete_count": 0,
            "transfer_count": 0,
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
            "retry_count": 0,
            "bytes_uploaded": 0,
            "bytes_downloaded": 0,
            "latency": {
                "upload": {"min": None, "max": None, "avg": None, "count": 0, "sum": 0},
                "download": {
                    "min": None,
                    "max": None,
                    "avg": None,
                    "count": 0,
                    "sum": 0,
                },
                "list": {"min": None, "max": None, "avg": None, "count": 0, "sum": 0},
                "delete": {"min": None, "max": None, "avg": None, "count": 0, "sum": 0},
                "transfer": {
                    "min": None,
                    "max": None,
                    "avg": None,
                    "count": 0,
                    "sum": 0,
                },
            },
            "start_time": time.time(),
            "last_operation_time": None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current operation statistics.

        Returns:
            Dict: Dictionary with current statistics
        """
        return {
            "backend_name": self.backend_name,
            "operation_stats": self.operation_stats,
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.operation_stats["start_time"],
        }

    def reset(self) -> Dict[str, Any]:
        """
        Reset operation statistics.

        Returns:
            Dict: Result of the reset operation
        """
        prev_stats = self.operation_stats.copy()
        self.operation_stats = self._initialize_stats()

        logger.info(f"{self.backend_name} Model statistics reset")

        return {
            "success": True,
            "operation": "reset_stats",
            "backend_name": self.backend_name,
            "previous_stats": prev_stats,
            "timestamp": time.time(),
        }

    async def async_reset(self) -> Dict[str, Any]:
        """
        Asynchronously reset operation statistics.

        Returns:
            Dict: Result of the reset operation
        """
        # Reset is lightweight enough that we can just call the sync version
        result = self.reset()

        # Notify listeners
        await self._notify_listeners("reset", result)

        return result

    def _update_stats(
        self,
        operation: str,
        success: bool,
        duration_ms: float,
        bytes_count: Optional[int] = None,
    ):
        """
        Update operation statistics.

        Args:
            operation: Type of operation (upload, download, list, delete, transfer)
            success: Whether the operation was successful
            duration_ms: Duration of the operation in milliseconds
            bytes_count: Number of bytes uploaded or downloaded
        """
        self.operation_stats["total_operations"] += 1
        self.operation_stats["last_operation_time"] = time.time()

        if success:
            self.operation_stats["success_count"] += 1
        else:
            self.operation_stats["failure_count"] += 1

        # Update operation-specific stats
        if operation in ["upload", "download", "list", "delete", "transfer"]:
            self.operation_stats[f"{operation}_count"] += 1

            # Update latency statistics
            latency_stats = self.operation_stats["latency"][operation]
            latency_stats["count"] += 1
            latency_stats["sum"] += duration_ms
            latency_stats["avg"] = latency_stats["sum"] / latency_stats["count"]

            if latency_stats["min"] is None or duration_ms < latency_stats["min"]:
                latency_stats["min"] = duration_ms

            if latency_stats["max"] is None or duration_ms > latency_stats["max"]:
                latency_stats["max"] = duration_ms

            # Update byte counts for upload/download operations
            if operation == "upload" and bytes_count is not None:
                self.operation_stats["bytes_uploaded"] += bytes_count
            elif operation == "download" and bytes_count is not None:
                self.operation_stats["bytes_downloaded"] += bytes_count

    def _create_operation_id(self, operation: str) -> str:
        """
        Create a unique operation ID.

        Args:
            operation: Type of operation

        Returns:
            str: Unique operation ID
        """
        return f"{self.backend_name.lower()}_{operation}_{uuid.uuid4()}"

    def _create_result_template(self, operation: str) -> Dict[str, Any]:
        """
        Create a standard result template for operations.

        Args:
            operation: Type of operation

        Returns:
            Dict: Result template with common fields
        """
        operation_id = self._create_operation_id(operation)
        timestamp = time.time()

        return {
            "success": False,  # Default to False, will be set to True if operation succeeds
            "operation": operation,
            "operation_id": operation_id,
            "backend_name": self.backend_name,
            "timestamp": timestamp,
        }

    def _handle_operation_result(
        self,
        result: Dict[str, Any],
        operation: str,
        start_time: float,
        bytes_count: Optional[int] = None,
    ):
        """
        Process and finalize an operation result.

        Args:
            result: Operation result dictionary
            operation: Type of operation
            start_time: Start time of the operation
            bytes_count: Number of bytes processed

        Returns:
            Dict: Finalized operation result
        """
        # Calculate duration
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        result["duration_ms"] = duration_ms

        # Update statistics
        self._update_stats(operation, result.get("success", False), duration_ms, bytes_count)

        return result

    async def _handle_operation_result_async(
        self,
        result: Dict[str, Any],
        operation: str,
        start_time: float,
        bytes_count: Optional[int] = None,
    ):
        """
        Process and finalize an operation result asynchronously.

        Args:
            result: Operation result dictionary
            operation: Type of operation
            start_time: Start time of the operation
            bytes_count: Number of bytes processed

        Returns:
            Dict: Finalized operation result
        """
        # Get the basic result processing
        processed_result = self._handle_operation_result(result, operation, start_time, bytes_count)

        # Notify listeners about the operation result
        await self._notify_listeners(operation, processed_result)

        return processed_result

    def _handle_exception(self, e: Exception, result: Dict[str, Any], operation: str):
        """
        Handle an exception during an operation.

        Args:
            e: Exception that occurred
            result: Current operation result
            operation: Type of operation

        Returns:
            Dict: Updated operation result with error information
        """
        logger.error(f"Error in {self.backend_name} {operation}: {str(e)}")

        result["success"] = False
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

        # For specific error types, add more detailed information
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            result["status_code"] = e.response.status_code

        return result

    async def _handle_exception_async(self, e: Exception, result: Dict[str, Any], operation: str):
        """
        Handle an exception during an async operation.

        Args:
            e: Exception that occurred
            result: Current operation result
            operation: Type of operation

        Returns:
            Dict: Updated operation result with error information
        """
        # Process the exception
        processed_result = self._handle_exception(e, result, operation)

        # Notify listeners about the error
        await self._notify_listeners(
            "error",
            {
                **processed_result,
                "event": "error",
                "error_operation": operation,
            },
        )

        return processed_result

    def _get_credentials(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get credentials for a service.

        Args:
            service: Optional service name to get specific credentials

        Returns:
            Dict: Credentials for the service
        """
        if self.credential_manager is None:
            logger.warning(f"No credential manager available for {self.backend_name}")
            return {}

        service_name = service or self.backend_name.lower()
        return self.credential_manager.get_credentials(service_name) or {}

    async def _get_credentials_async(self, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Get credentials for a service asynchronously.

        Args:
            service: Optional service name to get specific credentials

        Returns:
            Dict: Credentials for the service
        """
        if self.credential_manager is None:
            logger.warning(f"No credential manager available for {self.backend_name}")
            return {}

        service_name = service or self.backend_name.lower()

        # Check if credential manager has an async method
        if hasattr(self.credential_manager, "get_credentials_async"):
            return await self.credential_manager.get_credentials_async(service_name) or {}
        else:
            # Fall back to synchronous method if async not available
            return self.credential_manager.get_credentials(service_name) or {}

    def _get_file_size(self, file_path: str) -> int:
        """
        Get the size of a file.

        Args:
            file_path: Path to the file

        Returns:
            int: Size of the file in bytes
        """
        try:
            return os.path.getsize(file_path)
        except (OSError, IOError) as e:
            logger.warning(f"Error getting file size for {file_path}: {str(e)}")
            return 0

    def _cache_get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.

        Args:
            key: Cache key

        Returns:
            Any: Cached item or None if not found
        """
        if self.cache_manager is None:
            return None

        cache_key = f"{self.backend_name.lower()}:{key}"
        return self.cache_manager.get(cache_key)

    async def _cache_get_async(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache asynchronously.

        Args:
            key: Cache key

        Returns:
            Any: Cached item or None if not found
        """
        if self.cache_manager is None:
            return None

        cache_key = f"{self.backend_name.lower()}:{key}"

        # Check if cache manager has an async method
        if hasattr(self.cache_manager, "get_async"):
            return await self.cache_manager.get_async(cache_key)
        else:
            # Fall back to synchronous method if async not available
            return self.cache_manager.get(cache_key)

    def _cache_put(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Put an item in the cache.

        Args:
            key: Cache key
            value: Value to cache
            metadata: Optional metadata for the cached item

        Returns:
            bool: Whether the operation was successful
        """
        if self.cache_manager is None:
            return False

        cache_key = f"{self.backend_name.lower()}:{key}"
        return self.cache_manager.put(cache_key, value, metadata)

    async def _cache_put_async(
        self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Put an item in the cache asynchronously.

        Args:
            key: Cache key
            value: Value to cache
            metadata: Optional metadata for the cached item

        Returns:
            bool: Whether the operation was successful
        """
        if self.cache_manager is None:
            return False

        cache_key = f"{self.backend_name.lower()}:{key}"

        # Check if cache manager has an async method
        if hasattr(self.cache_manager, "put_async"):
            return await self.cache_manager.put_async(cache_key, value, metadata)
        else:
            # Fall back to synchronous method if async not available
            return self.cache_manager.put(cache_key, value, metadata)

    def add_event_listener(self, listener: Union[EventListener, SyncEventListener]) -> bool:
        """
        Add an event listener for operation notifications.

        Args:
            listener: Function that will be called with (event_type, data)

        Returns:
            bool: Whether the listener was successfully added
        """
        if len(self.listeners) >= self.max_listeners:
            logger.warning(f"Maximum number of listeners ({self.max_listeners}) reached")
            return False

        self.listeners.add(listener)
        return True

    def remove_event_listener(self, listener: Union[EventListener, SyncEventListener]) -> bool:
        """
        Remove an event listener.

        Args:
            listener: The listener function to remove

        Returns:
            bool: Whether the listener was successfully removed
        """
        if listener in self.listeners:
            self.listeners.remove(listener)
            return True
        return False

    async def _notify_listeners(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Notify all registered listeners of an event.

        Args:
            event_type: Type of event (e.g., "upload", "download", "error")
            data: Event data dictionary
        """
        event_data = {**data, "event": event_type, "timestamp": time.time()}

        for listener in self.listeners:
            try:
                # Check if the listener is a coroutine function
                if inspect.iscoroutinefunction(listener):
                    await listener(event_type, event_data)
                else:
                    # Run synchronous listeners in the executor to avoid blocking
                    await anyio.get_event_loop().run_in_executor(
                        None, listener, event_type, event_data
                    )
            except Exception as e:
                logger.error(f"Error in event listener: {str(e)}")

    def _should_retry(self, error: Exception, retry_config: Dict[str, Any], attempt: int) -> bool:
        """
        Determine if an operation should be retried.

        Args:
            error: The exception that occurred
            retry_config: Retry configuration dictionary
            attempt: Current attempt number (1-based)

        Returns:
            bool: Whether the operation should be retried
        """
        # Check if we've reached max retries
        if attempt >= retry_config["max_retries"]:
            return False

        # Check exception type
        error_type = type(error).__name__
        if error_type in retry_config["retry_on_exceptions"]:
            return True

        # Check status code if available
        if hasattr(error, "response") and hasattr(error.response, "status_code"):
            if error.response.status_code in retry_config["retry_on_status_codes"]:
                return True

        return False

    def _get_retry_delay(self, retry_config: Dict[str, Any], attempt: int) -> float:
        """
        Calculate the delay before the next retry attempt.

        Args:
            retry_config: Retry configuration dictionary
            attempt: Current attempt number (1-based)

        Returns:
            float: Delay in seconds before the next attempt
        """
        base_delay = retry_config["retry_delay"]
        backoff_factor = retry_config["backoff_factor"]
        max_delay = retry_config["max_delay"]

        delay = base_delay * (backoff_factor ** (attempt - 1))
        return min(delay, max_delay)

    async def _with_retry_async(
        self,
        operation_func,
        operation_name: str,
        retry_config: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ):
        """
        Execute an async operation with retry logic.

        Args:
            operation_func: Async function to execute
            operation_name: Name of the operation (for logging)
            retry_config: Optional custom retry configuration
            *args, **kwargs: Arguments to pass to the operation function

        Returns:
            Dict: Operation result
        """
        config = retry_config or self.default_retry_config
        attempt = 1
        last_error = None

        while attempt <= config["max_retries"]:
            try:
                # Execute the operation
                if attempt > 1:
                    logger.info(f"Retry attempt {attempt} for {operation_name}")
                    self.operation_stats["retry_count"] += 1

                result = await operation_func(*args, **kwargs)

                # If successful, return the result
                if result.get("success", False):
                    if attempt > 1:
                        result["retry_count"] = attempt - 1
                    return result

                # If not successful but no exception was raised, should we retry?
                error_type = result.get("error_type")
                if error_type in config["retry_on_exceptions"]:
                    last_error = Exception(result.get("error", "Operation failed"))
                else:
                    # Not retriable error
                    return result

            except Exception as e:
                last_error = e
                result = self._create_result_template(operation_name)
                result = await self._handle_exception_async(e, result, operation_name)

                # If not a retriable error, return immediately
                if not self._should_retry(e, config, attempt):
                    return result

            # Calculate delay for next attempt
            delay = self._get_retry_delay(config, attempt)

            # Notify listeners of retry
            await self._notify_listeners(
                "retry",
                {
                    "operation": operation_name,
                    "attempt": attempt,
                    "delay": delay,
                    "error": str(last_error),
                    "error_type": type(last_error).__name__,
                },
            )

            # Wait before retry
            await anyio.sleep(delay)
            attempt += 1

        # If we get here, all retries failed
        logger.error(f"All {config['max_retries']} retry attempts failed for {operation_name}")

        # Create a final error result
        result = self._create_result_template(operation_name)
        result["success"] = False
        result["error"] = (
            f"Operation failed after {config['max_retries']} attempts: {str(last_error)}"
        )
        result["error_type"] = "MaxRetriesExceeded"
        result["retry_count"] = config["max_retries"]

        return result

    def _with_retry_sync(
        self,
        operation_func,
        operation_name: str,
        retry_config: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ):
        """
        Execute a synchronous operation with retry logic.

        Args:
            operation_func: Function to execute
            operation_name: Name of the operation (for logging)
            retry_config: Optional custom retry configuration
            *args, **kwargs: Arguments to pass to the operation function

        Returns:
            Dict: Operation result
        """
        config = retry_config or self.default_retry_config
        attempt = 1
        last_error = None

        while attempt <= config["max_retries"]:
            try:
                # Execute the operation
                if attempt > 1:
                    logger.info(f"Retry attempt {attempt} for {operation_name}")
                    self.operation_stats["retry_count"] += 1

                result = operation_func(*args, **kwargs)

                # If successful, return the result
                if result.get("success", False):
                    if attempt > 1:
                        result["retry_count"] = attempt - 1
                    return result

                # If not successful but no exception was raised, should we retry?
                error_type = result.get("error_type")
                if error_type in config["retry_on_exceptions"]:
                    last_error = Exception(result.get("error", "Operation failed"))
                else:
                    # Not retriable error
                    return result

            except Exception as e:
                last_error = e
                result = self._create_result_template(operation_name)
                result = self._handle_exception(e, result, operation_name)

                # If not a retriable error, return immediately
                if not self._should_retry(e, config, attempt):
                    return result

            # Calculate delay for next attempt
            delay = self._get_retry_delay(config, attempt)

            # Wait before retry
            time.sleep(delay)
            attempt += 1

        # If we get here, all retries failed
        logger.error(f"All {config['max_retries']} retry attempts failed for {operation_name}")

        # Create a final error result
        result = self._create_result_template(operation_name)
        result["success"] = False
        result["error"] = (
            f"Operation failed after {config['max_retries']} attempts: {str(last_error)}"
        )
        result["error_type"] = "MaxRetriesExceeded"
        result["retry_count"] = config["max_retries"]

        return result

    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure the storage model with custom settings.

        Args:
            config: Configuration dictionary

        Returns:
            Dict: Result of the configuration operation
        """
        result = self._create_result_template("configure")
        start_time = time.time()

        try:
            # Update configuration
            self.configuration.update(config)

            # Update retry configuration if provided
            if "retry" in config:
                self.default_retry_config.update(config["retry"])

            # Update max listeners if provided
            if "max_listeners" in config:
                self.max_listeners = config["max_listeners"]

            result["success"] = True
            result["configuration"] = self.configuration

            logger.info(f"{self.backend_name} Model configured with {len(config)} settings")

        except Exception as e:
            return self._handle_exception(e, result, "configure")

        return self._handle_operation_result(result, "configure", start_time)

    async def async_configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure the storage model asynchronously.

        Args:
            config: Configuration dictionary

        Returns:
            Dict: Result of the configuration operation
        """
        # Configuration is lightweight enough to just call the sync version
        result = self.configure(config)

        # Notify listeners
        await self._notify_listeners("configure", result)

        return result

    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the storage backend.

        This method should be overridden by subclasses to implement a specific
        health check for the backend.

        Returns:
            Dict: Health check result
        """
        result = self._create_result_template("health_check")
        start_time = time.time()

        try:
            # Default implementation just returns basic kit information
            result["success"] = self.kit is not None
            result["kit_available"] = self.kit is not None
            result["cache_available"] = self.cache_manager is not None
            result["credential_available"] = self.credential_manager is not None

            # Add backend-specific information if available
            if hasattr(self.kit, "get_version"):
                try:
                    result["version"] = self.kit.get_version()
                except Exception:
                    result["version"] = "unknown"

        except Exception as e:
            return self._handle_exception(e, result, "health_check")

        return self._handle_operation_result(result, "health_check", start_time)

    async def async_health_check(self) -> Dict[str, Any]:
        """
        Check the health of the storage backend asynchronously.

        This method can be overridden by subclasses to implement a specific
        async health check for the backend.

        Returns:
            Dict: Health check result
        """
        result = self._create_result_template("health_check")
        start_time = time.time()

        try:
            # Use the standard health check by default
            sync_result = self.health_check()
            # Copy all fields except those we'll recalculate
            for key, value in sync_result.items():
                if key not in ["duration_ms"]:
                    result[key] = value

            # Add backend-specific async information if available
            if hasattr(self.kit, "get_version_async"):
                try:
                    result["version"] = await self.kit.get_version_async()
                except Exception:
                    # Use the value from sync check if it exists
                    result["version"] = sync_result.get("version", "unknown")

        except Exception as e:
            return await self._handle_exception_async(e, result, "health_check")

        return await self._handle_operation_result_async(result, "health_check", start_time)

    # Standard storage operations that should be implemented by subclasses

    async def add_content(self, content: Union[bytes, str], **kwargs) -> Dict[str, Any]:
        """
        Add content to the storage backend.

        This is an abstract method that should be implemented by subclasses.

        Args:
            content: Content to add (bytes or string)
            **kwargs: Additional backend-specific parameters

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("add_content")
        result["error"] = "Method not implemented"
        result["error_type"] = "NotImplementedError"
        logger.error(f"{self.backend_name} Model does not implement add_content")

        return result

    async def get_content(self, content_id: str, **kwargs) -> Dict[str, Any]:
        """
        Retrieve content from the storage backend.

        This is an abstract method that should be implemented by subclasses.

        Args:
            content_id: Identifier for the content to retrieve
            **kwargs: Additional backend-specific parameters

        Returns:
            Dict: Result of the operation with retrieved content
        """
        result = self._create_result_template("get_content")
        result["error"] = "Method not implemented"
        result["error_type"] = "NotImplementedError"
        logger.error(f"{self.backend_name} Model does not implement get_content")

        return result

    async def delete_content(self, content_id: str, **kwargs) -> Dict[str, Any]:
        """
        Delete content from the storage backend.

        This is an abstract method that should be implemented by subclasses.

        Args:
            content_id: Identifier for the content to delete
            **kwargs: Additional backend-specific parameters

        Returns:
            Dict: Result of the operation
        """
        result = self._create_result_template("delete_content")
        result["error"] = "Method not implemented"
        result["error_type"] = "NotImplementedError"
        logger.error(f"{self.backend_name} Model does not implement delete_content")

        return result

    async def list_content(self, **kwargs) -> Dict[str, Any]:
        """
        List content in the storage backend.

        This is an abstract method that should be implemented by subclasses.

        Args:
            **kwargs: Backend-specific parameters for filtering the list

        Returns:
            Dict: Result of the operation with content list
        """
        result = self._create_result_template("list_content")
        result["error"] = "Method not implemented"
        result["error_type"] = "NotImplementedError"
        logger.error(f"{self.backend_name} Model does not implement list_content")

        return result

    # Helper method for creating synchronous versions of async methods
    def _create_sync_method(async_method):
        """
        Decorator to create a synchronous version of an async method.

        Args:
            async_method: The async method to create a sync version for

        Returns:
            A synchronous wrapper function
        """

        @wraps(async_method)
        def sync_wrapper(self, *args, **kwargs):
            # Get the current event loop
            try:
                loop = anyio.get_event_loop()
            except RuntimeError:
                # Create a new event loop if none exists
                loop = anyio.new_event_loop()
                anyio.set_event_loop(loop)

            # Run the async method in the event loop
            return loop.run_until_complete(async_method(self, *args, **kwargs))

        return sync_wrapper
