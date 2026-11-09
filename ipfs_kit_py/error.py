"""
Error handling for IPFS Kit.

This module defines the error hierarchy for IPFS Kit operations
and provides utility functions for error handling.
"""

import logging
import subprocess
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

# Create a generic type variable for the return type
T = TypeVar("T")

# Configure logger
logger = logging.getLogger(__name__)


class IPFSError(Exception):
    """Base class for all IPFS-related exceptions."""

    pass


class IPFSConnectionError(IPFSError):
    """Error when connecting to IPFS daemon."""

    pass


class IPFSTimeoutError(IPFSError):
    """Timeout when communicating with IPFS daemon."""

    pass


class IPFSContentNotFoundError(IPFSError):
    """Content with specified CID not found."""

    pass


class IPFSValidationError(IPFSError):
    """Input validation failed."""

    pass


class IPFSConfigurationError(IPFSError):
    """IPFS configuration is invalid or missing."""

    pass


class IPFSPinningError(IPFSError):
    """Error during content pinning/unpinning."""

    pass


def create_result_dict(operation: str, success: bool = False, **kwargs) -> Dict[str, Any]:
    """
    Create a standardized result dictionary.

    Args:
        operation: Name of the operation
        success: Whether the operation was successful
        **kwargs: Additional key-value pairs to include in the result

    Returns:
        Standardized result dictionary with common fields
    """
    # Extract correlation_id without removing it from kwargs
    correlation_id = kwargs.get("correlation_id", None)

    result = {
        "success": success,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }

    # Add additional fields
    result.update(kwargs)

    return result


def handle_error(
    result: Dict[str, Any], e: Exception, error_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle exceptions and update result dictionary.

    Args:
        result: Result dictionary to update
        e: Exception that occurred
        error_type: Optional error type classification

    Returns:
        Updated result dictionary with error information
    """
    # Set success to False
    result["success"] = False

    # Add error message
    result["error"] = str(e)

    # Classify error type
    if isinstance(e, IPFSConnectionError):
        classified_type = "connection_error"
    elif isinstance(e, IPFSTimeoutError):
        classified_type = "timeout_error"
    elif isinstance(e, IPFSContentNotFoundError):
        classified_type = "content_not_found"
    elif isinstance(e, IPFSValidationError):
        classified_type = "validation_error"
    elif isinstance(e, IPFSConfigurationError):
        classified_type = "configuration_error"
    elif isinstance(e, IPFSPinningError):
        classified_type = "pinning_error"
    elif isinstance(e, IPFSError):
        classified_type = "ipfs_error"  # Generic IPFS error
    elif isinstance(e, FileNotFoundError) or "No such file or directory" in str(e):
        classified_type = "file_error"
    elif isinstance(e, ConnectionError) or "connection" in str(e).lower():
        classified_type = "connection_error"
    elif isinstance(e, subprocess.TimeoutExpired) or "timeout" in str(e).lower():
        classified_type = "timeout_error"
    else:
        classified_type = "unknown_error"  # Use a more reliable default

    result["error_type"] = error_type or classified_type

    # Add stack trace in debug mode
    if result.get("debug", False):
        result["stack_trace"] = traceback.format_exc()

    # Add error-specific information
    if isinstance(e, IPFSConnectionError) or classified_type == "connection_error":
        result["recoverable"] = True
    elif isinstance(e, IPFSTimeoutError) or classified_type == "timeout_error":
        result["recoverable"] = True
        result["timeout"] = True
    elif isinstance(e, IPFSContentNotFoundError) or classified_type == "content_not_found":
        result["recoverable"] = False
        result["not_found"] = True
    elif isinstance(e, FileNotFoundError) or classified_type == "file_error":
        result["recoverable"] = False
    else:
        result["recoverable"] = False  # Default to non-recoverable for safety

    return result


def perform_with_retry(
    operation_func: Callable[..., T],
    *args,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retry_exceptions: Tuple[Exception, ...] = (IPFSConnectionError, IPFSTimeoutError),
    **kwargs,
) -> T:
    """
    Perform operation with exponential backoff retry.

    Args:
        operation_func: Function to retry
        *args: Positional arguments for function
        max_retries: Maximum number of retry attempts
        backoff_factor: Base for exponential backoff
        retry_exceptions: Exception types to retry on
        **kwargs: Keyword arguments for function

    Returns:
        Result of the operation_func

    Raises:
        Exception: Last exception if all retries failed
    """
    attempt = 0
    last_exception = None

    while attempt < max_retries:
        try:
            return operation_func(*args, **kwargs)

        except retry_exceptions as e:
            attempt += 1
            last_exception = e

            if attempt < max_retries:
                # Calculate sleep time with exponential backoff
                sleep_time = backoff_factor**attempt
                logger.warning(
                    f"Retry attempt {attempt} after error: {str(e)}. "
                    f"Waiting {sleep_time}s before retry."
                )
                time.sleep(sleep_time)
            else:
                logger.error(
                    f"All {max_retries} retry attempts failed for operation. "
                    f"Last error: {str(e)}"
                )

    # If we get here, all retries failed
    if last_exception:
        raise last_exception

    # This should never happen, but just in case
    raise RuntimeError("Retry loop exited without success or exception")
