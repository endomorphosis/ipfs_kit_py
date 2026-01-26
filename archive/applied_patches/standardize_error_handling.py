"""
Standardized Error Handling for MCP.

This module provides consistent error handling mechanisms across the MCP server,
addressing the "API Standardization" section from the mcp_roadmap.md.

Features:
- Standardized error codes and response formats
- Detailed error information with troubleshooting suggestions
- Legacy error conversion for backward compatibility
- Error classification and categorization
"""

import os
import sys
import time
import uuid
import logging
import traceback
import inspect
from enum import Enum
from typing import Dict, Any, Optional, Union, Tuple, List, Type
from http import HTTPStatus

# Configure logging
logger = logging.getLogger(__name__)

# Define standard error categories
class ErrorCategory(str, Enum):
    """Standard error categories for classification."""
    VALIDATION = "validation"  # Input validation errors
    AUTHENTICATION = "authentication"  # Auth-related errors
    AUTHORIZATION = "authorization"  # Permission-related errors
    NOT_FOUND = "not_found"  # Resource not found
    RESOURCE_CONFLICT = "resource_conflict"  # Resource already exists or conflict
    DEPENDENCY_ERROR = "dependency_error"  # External service/dependency error
    INTERNAL_ERROR = "internal_error"  # Internal system errors
    NETWORK_ERROR = "network_error"  # Network/connectivity issues
    TIMEOUT_ERROR = "timeout"  # Operation timeouts
    STORAGE_ERROR = "storage"  # Storage-related errors
    RATE_LIMIT = "rate_limit"  # Rate limiting
    FORMAT_ERROR = "format"  # Data format issues
    UNKNOWN = "unknown"  # Uncategorized errors


# Define standard error codes with categories, HTTP status codes, and messages
class ErrorCode(str, Enum):
    """Standard error codes with associated metadata."""
    # Validation errors (400)
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FORMAT = "invalid_format"
    VALUE_OUT_OF_RANGE = "value_out_of_range"
    INVALID_CID = "invalid_cid"
    
    # Authentication errors (401)
    UNAUTHORIZED = "unauthorized"
    INVALID_CREDENTIALS = "invalid_credentials"
    EXPIRED_TOKEN = "expired_token"
    
    # Authorization errors (403)
    FORBIDDEN = "forbidden"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    
    # Not found errors (404)
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONTENT_NOT_FOUND = "content_not_found"
    ENDPOINT_NOT_FOUND = "endpoint_not_found"
    
    # Resource conflict errors (409)
    RESOURCE_ALREADY_EXISTS = "resource_already_exists"
    RESOURCE_IN_USE = "resource_in_use"
    CONCURRENT_MODIFICATION = "concurrent_modification"
    
    # Dependency errors (502)
    UPSTREAM_SERVICE_ERROR = "upstream_service_error"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    GATEWAY_ERROR = "gateway_error"
    
    # Internal errors (500)
    INTERNAL_SERVER_ERROR = "internal_server_error"
    UNEXPECTED_ERROR = "unexpected_error"
    CONFIGURATION_ERROR = "configuration_error"
    
    # Network errors (various)
    CONNECTION_ERROR = "connection_error"
    DNS_ERROR = "dns_error"
    TLS_ERROR = "tls_error"
    
    # Timeout errors (408, 504)
    REQUEST_TIMEOUT = "request_timeout"
    OPERATION_TIMEOUT = "operation_timeout"
    GATEWAY_TIMEOUT = "gateway_timeout"
    
    # Storage errors (507)
    STORAGE_FULL = "storage_full"
    IO_ERROR = "io_error"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    
    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOO_MANY_REQUESTS = "too_many_requests"
    
    # Format errors (415)
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    CONTENT_TYPE_MISMATCH = "content_type_mismatch"
    SERIALIZATION_ERROR = "serialization_error"
    
    # Unknown errors
    UNKNOWN_ERROR = "unknown_error"


# Metadata for error codes
ERROR_METADATA = {
    # Validation errors
    ErrorCode.INVALID_INPUT: {
        "category": ErrorCategory.VALIDATION,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "The provided input is invalid.",
        "suggestion": "Please check the input data and try again."
    },
    ErrorCode.MISSING_REQUIRED_FIELD: {
        "category": ErrorCategory.VALIDATION,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "A required field is missing.",
        "suggestion": "Please ensure all required fields are provided."
    },
    ErrorCode.INVALID_FORMAT: {
        "category": ErrorCategory.VALIDATION,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "The format of the provided data is invalid.",
        "suggestion": "Please check the format of your input data."
    },
    ErrorCode.VALUE_OUT_OF_RANGE: {
        "category": ErrorCategory.VALIDATION,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "A value is outside the allowed range.",
        "suggestion": "Please ensure all values are within acceptable ranges."
    },
    ErrorCode.INVALID_CID: {
        "category": ErrorCategory.VALIDATION,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "The provided CID is invalid.",
        "suggestion": "Please provide a valid IPFS CID."
    },
    
    # Authentication errors
    ErrorCode.UNAUTHORIZED: {
        "category": ErrorCategory.AUTHENTICATION,
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "Authentication is required for this operation.",
        "suggestion": "Please provide valid authentication credentials."
    },
    ErrorCode.INVALID_CREDENTIALS: {
        "category": ErrorCategory.AUTHENTICATION,
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "The provided authentication credentials are invalid.",
        "suggestion": "Please check your credentials and try again."
    },
    ErrorCode.EXPIRED_TOKEN: {
        "category": ErrorCategory.AUTHENTICATION,
        "status_code": HTTPStatus.UNAUTHORIZED,
        "message": "The authentication token has expired.",
        "suggestion": "Please refresh your token or login again."
    },
    
    # Authorization errors
    ErrorCode.FORBIDDEN: {
        "category": ErrorCategory.AUTHORIZATION,
        "status_code": HTTPStatus.FORBIDDEN,
        "message": "You do not have permission to perform this operation.",
        "suggestion": "Please contact an administrator if you need access."
    },
    ErrorCode.INSUFFICIENT_PERMISSIONS: {
        "category": ErrorCategory.AUTHORIZATION,
        "status_code": HTTPStatus.FORBIDDEN,
        "message": "You do not have sufficient permissions for this operation.",
        "suggestion": "Please request additional permissions or contact an administrator."
    },
    
    # Not found errors
    ErrorCode.RESOURCE_NOT_FOUND: {
        "category": ErrorCategory.NOT_FOUND,
        "status_code": HTTPStatus.NOT_FOUND,
        "message": "The requested resource was not found.",
        "suggestion": "Please check that the resource identifier is correct."
    },
    ErrorCode.CONTENT_NOT_FOUND: {
        "category": ErrorCategory.NOT_FOUND,
        "status_code": HTTPStatus.NOT_FOUND,
        "message": "The requested content was not found.",
        "suggestion": "Please check that the content identifier is correct."
    },
    ErrorCode.ENDPOINT_NOT_FOUND: {
        "category": ErrorCategory.NOT_FOUND,
        "status_code": HTTPStatus.NOT_FOUND,
        "message": "The requested endpoint was not found.",
        "suggestion": "Please check the API documentation for available endpoints."
    },
    
    # Resource conflict errors
    ErrorCode.RESOURCE_ALREADY_EXISTS: {
        "category": ErrorCategory.RESOURCE_CONFLICT,
        "status_code": HTTPStatus.CONFLICT,
        "message": "The resource already exists.",
        "suggestion": "Please use a different identifier or update the existing resource."
    },
    ErrorCode.RESOURCE_IN_USE: {
        "category": ErrorCategory.RESOURCE_CONFLICT,
        "status_code": HTTPStatus.CONFLICT,
        "message": "The resource is currently in use and cannot be modified.",
        "suggestion": "Please try again later when the resource is not in use."
    },
    ErrorCode.CONCURRENT_MODIFICATION: {
        "category": ErrorCategory.RESOURCE_CONFLICT,
        "status_code": HTTPStatus.CONFLICT,
        "message": "The resource was modified concurrently.",
        "suggestion": "Please refresh and try again."
    },
    
    # Dependency errors
    ErrorCode.UPSTREAM_SERVICE_ERROR: {
        "category": ErrorCategory.DEPENDENCY_ERROR,
        "status_code": HTTPStatus.BAD_GATEWAY,
        "message": "An upstream service returned an error.",
        "suggestion": "Please try again later or contact support if the problem persists."
    },
    ErrorCode.DEPENDENCY_UNAVAILABLE: {
        "category": ErrorCategory.DEPENDENCY_ERROR,
        "status_code": HTTPStatus.SERVICE_UNAVAILABLE,
        "message": "A required dependency is unavailable.",
        "suggestion": "Please try again later or check system status."
    },
    ErrorCode.GATEWAY_ERROR: {
        "category": ErrorCategory.DEPENDENCY_ERROR,
        "status_code": HTTPStatus.BAD_GATEWAY,
        "message": "The gateway encountered an error.",
        "suggestion": "Please try again later or contact support if the problem persists."
    },
    
    # Internal errors
    ErrorCode.INTERNAL_SERVER_ERROR: {
        "category": ErrorCategory.INTERNAL_ERROR,
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "An internal server error occurred.",
        "suggestion": "Please try again later or contact support if the problem persists."
    },
    ErrorCode.UNEXPECTED_ERROR: {
        "category": ErrorCategory.INTERNAL_ERROR,
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "An unexpected error occurred.",
        "suggestion": "Please try again later or contact support if the problem persists."
    },
    ErrorCode.CONFIGURATION_ERROR: {
        "category": ErrorCategory.INTERNAL_ERROR,
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "A configuration error occurred.",
        "suggestion": "Please contact support to resolve this issue."
    },
    
    # Network errors
    ErrorCode.CONNECTION_ERROR: {
        "category": ErrorCategory.NETWORK_ERROR,
        "status_code": HTTPStatus.BAD_GATEWAY,
        "message": "A connection error occurred.",
        "suggestion": "Please check your network connection and try again."
    },
    ErrorCode.DNS_ERROR: {
        "category": ErrorCategory.NETWORK_ERROR,
        "status_code": HTTPStatus.BAD_GATEWAY,
        "message": "A DNS resolution error occurred.",
        "suggestion": "Please check your DNS configuration or try again later."
    },
    ErrorCode.TLS_ERROR: {
        "category": ErrorCategory.NETWORK_ERROR,
        "status_code": HTTPStatus.BAD_GATEWAY,
        "message": "A TLS/SSL error occurred.",
        "suggestion": "Please check your SSL/TLS configuration or certificates."
    },
    
    # Timeout errors
    ErrorCode.REQUEST_TIMEOUT: {
        "category": ErrorCategory.TIMEOUT_ERROR,
        "status_code": HTTPStatus.REQUEST_TIMEOUT,
        "message": "The request timed out.",
        "suggestion": "Please try again later or with a longer timeout."
    },
    ErrorCode.OPERATION_TIMEOUT: {
        "category": ErrorCategory.TIMEOUT_ERROR,
        "status_code": HTTPStatus.GATEWAY_TIMEOUT,
        "message": "The operation timed out.",
        "suggestion": "Please try again later or with a longer timeout."
    },
    ErrorCode.GATEWAY_TIMEOUT: {
        "category": ErrorCategory.TIMEOUT_ERROR,
        "status_code": HTTPStatus.GATEWAY_TIMEOUT,
        "message": "The gateway timed out.",
        "suggestion": "Please try again later or check system status."
    },
    
    # Storage errors
    ErrorCode.STORAGE_FULL: {
        "category": ErrorCategory.STORAGE_ERROR,
        "status_code": HTTPStatus.INSUFFICIENT_STORAGE,
        "message": "The storage is full.",
        "suggestion": "Please free up some space or contact an administrator."
    },
    ErrorCode.IO_ERROR: {
        "category": ErrorCategory.STORAGE_ERROR,
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "An I/O error occurred.",
        "suggestion": "Please try again later or contact support if the problem persists."
    },
    ErrorCode.STORAGE_UNAVAILABLE: {
        "category": ErrorCategory.STORAGE_ERROR,
        "status_code": HTTPStatus.SERVICE_UNAVAILABLE,
        "message": "The storage service is unavailable.",
        "suggestion": "Please try again later or check system status."
    },
    
    # Rate limiting
    ErrorCode.RATE_LIMIT_EXCEEDED: {
        "category": ErrorCategory.RATE_LIMIT,
        "status_code": HTTPStatus.TOO_MANY_REQUESTS,
        "message": "Rate limit exceeded.",
        "suggestion": "Please reduce your request rate or try again later."
    },
    ErrorCode.TOO_MANY_REQUESTS: {
        "category": ErrorCategory.RATE_LIMIT,
        "status_code": HTTPStatus.TOO_MANY_REQUESTS,
        "message": "Too many requests.",
        "suggestion": "Please reduce your request rate or try again later."
    },
    
    # Format errors
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: {
        "category": ErrorCategory.FORMAT_ERROR,
        "status_code": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        "message": "The media type is not supported.",
        "suggestion": "Please use a supported media type."
    },
    ErrorCode.CONTENT_TYPE_MISMATCH: {
        "category": ErrorCategory.FORMAT_ERROR,
        "status_code": HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        "message": "The content type does not match the expected format.",
        "suggestion": "Please use the correct content type for this operation."
    },
    ErrorCode.SERIALIZATION_ERROR: {
        "category": ErrorCategory.FORMAT_ERROR,
        "status_code": HTTPStatus.BAD_REQUEST,
        "message": "Failed to serialize or deserialize the data.",
        "suggestion": "Please check the format of your data."
    },
    
    # Unknown errors
    ErrorCode.UNKNOWN_ERROR: {
        "category": ErrorCategory.UNKNOWN,
        "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
        "message": "An unknown error occurred.",
        "suggestion": "Please try again later or contact support if the problem persists."
    }
}


class MCPError(Exception):
    """
    Base exception class for MCP errors.
    
    This class provides a standardized way to create and handle errors
    across the MCP system with consistent formats and behavior.
    """
    
    def __init__(
        self,
        code: Union[ErrorCode, str],
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        correlation_id: Optional[str] = None,
        status_code: Optional[int] = None,
        suggestion: Optional[str] = None,
        operation: Optional[str] = None,
    ):
        """
        Initialize an MCP error.
        
        Args:
            code: Error code (either an ErrorCode enum or string)
            message: Custom error message (uses default for the code if not provided)
            details: Additional error details
            original_error: Original exception that caused this error
            correlation_id: Unique ID for correlating related errors
            status_code: HTTP status code (uses default for the code if not provided)
            suggestion: Suggestion for resolving the error (uses default if not provided)
            operation: Operation that generated the error
        """
        # Convert string code to enum if needed
        if isinstance(code, str):
            try:
                self.code = ErrorCode(code)
            except ValueError:
                self.code = ErrorCode.UNKNOWN_ERROR
                details = details or {}
                details["original_code"] = code
        else:
            self.code = code
        
        # Get metadata for the error code
        metadata = ERROR_METADATA.get(self.code, ERROR_METADATA[ErrorCode.UNKNOWN_ERROR])
        
        # Use provided message or default
        self.message = message or metadata["message"]
        
        # Set attributes
        self.details = details or {}
        self.original_error = original_error
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.status_code = status_code or metadata["status_code"]
        self.suggestion = suggestion or metadata.get("suggestion")
        self.category = metadata["category"]
        self.operation = operation
        self.timestamp = time.time()
        
        # Add original error details if available
        if original_error:
            self.details["original_error"] = str(original_error)
            self.details["original_error_type"] = type(original_error).__name__
        
        # Set exception message
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the error to a dictionary representation.
        
        Returns:
            Dictionary representing the error
        """
        error_dict = {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "category": self.category,
                "correlation_id": self.correlation_id,
                "timestamp": self.timestamp
            }
        }
        
        # Add optional fields if available
        if self.suggestion:
            error_dict["error"]["suggestion"] = self.suggestion
        
        if self.operation:
            error_dict["error"]["operation"] = self.operation
        
        if self.details:
            error_dict["error"]["details"] = self.details
        
        return error_dict
    
    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Convert the error to a legacy dictionary format for compatibility.
        
        Returns:
            Dictionary representing the error in legacy format
        """
        return {
            "success": False,
            "error": self.message,
            "error_code": self.code.value,
            "correlation_id": self.correlation_id,
            "details": self.details
        }


# Define specific error classes for common error types
class ValidationError(MCPError):
    """Error for input validation failures."""
    def __init__(self, message: Optional[str] = None, **kwargs):
        super().__init__(ErrorCode.INVALID_INPUT, message, **kwargs)


class MissingRequiredFieldError(ValidationError):
    """Error for missing required fields."""
    def __init__(self, field_name: str, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details["field_name"] = field_name
        message = message or f"Missing required field: {field_name}"
        super().__init__(
            code=ErrorCode.MISSING_REQUIRED_FIELD,
            message=message,
            details=details,
            **kwargs
        )


class ResourceNotFoundError(MCPError):
    """Error for resource not found."""
    def __init__(self, resource_type: str, resource_id: str, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details.update({
            "resource_type": resource_type,
            "resource_id": resource_id
        })
        message = message or f"{resource_type} not found: {resource_id}"
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            details=details,
            **kwargs
        )


class ContentNotFoundError(ResourceNotFoundError):
    """Error for content not found."""
    def __init__(self, content_id: str, message: Optional[str] = None, **kwargs):
        message = message or f"Content not found: {content_id}"
        super().__init__(
            resource_type="Content",
            resource_id=content_id,
            code=ErrorCode.CONTENT_NOT_FOUND,
            message=message,
            **kwargs
        )


class DependencyError(MCPError):
    """Error for dependency failures."""
    def __init__(self, dependency_name: str, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details["dependency_name"] = dependency_name
        message = message or f"Dependency error: {dependency_name}"
        super().__init__(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message=message,
            details=details,
            **kwargs
        )


class StorageError(MCPError):
    """Error for storage-related issues."""
    def __init__(self, storage_type: str, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details["storage_type"] = storage_type
        message = message or f"Storage error with {storage_type}"
        super().__init__(
            code=ErrorCode.STORAGE_UNAVAILABLE,
            message=message,
            details=details,
            **kwargs
        )


class TimeoutError(MCPError):
    """Error for operation timeouts."""
    def __init__(self, operation: str, timeout_seconds: float, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details.update({
            "operation": operation,
            "timeout_seconds": timeout_seconds
        })
        message = message or f"Operation timed out after {timeout_seconds} seconds: {operation}"
        super().__init__(
            code=ErrorCode.OPERATION_TIMEOUT,
            message=message,
            details=details,
            operation=operation,
            **kwargs
        )


class RateLimitError(MCPError):
    """Error for rate limiting."""
    def __init__(self, limit: int, reset_after: float, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        details.update({
            "limit": limit,
            "reset_after": reset_after
        })
        message = message or f"Rate limit exceeded. Try again after {reset_after} seconds."
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            details=details,
            **kwargs
        )


class ConfigurationError(MCPError):
    """Error for configuration issues."""
    def __init__(self, config_key: Optional[str] = None, message: Optional[str] = None, **kwargs):
        details = kwargs.get("details", {})
        if config_key:
            details["config_key"] = config_key
            message = message or f"Configuration error with key: {config_key}"
        else:
            message = message or "Configuration error"
        
        super().__init__(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=message,
            details=details,
            **kwargs
        )


# Utility functions for error handling

def error_from_exception(
    exception: Exception,
    default_code: ErrorCode = ErrorCode.UNEXPECTED_ERROR,
    include_traceback: bool = False,
    correlation_id: Optional[str] = None,
    operation: Optional[str] = None
) -> MCPError:
    """
    Convert a regular exception to an MCPError.
    
    Args:
        exception: The exception to convert
        default_code: Default error code if the exception type can't be mapped
        include_traceback: Whether to include traceback in the error details
        correlation_id: Optional correlation ID
        operation: Optional operation name
        
    Returns:
        An MCPError instance
    """
    # If it's already an MCPError, just return it
    if isinstance(exception, MCPError):
        # Update correlation_id and operation if provided
        if correlation_id and not exception.correlation_id:
            exception.correlation_id = correlation_id
        if operation and not exception.operation:
            exception.operation = operation
        return exception
    
    # Map common exception types to appropriate error codes
    error_code = default_code
    if isinstance(exception, ValueError):
        error_code = ErrorCode.INVALID_INPUT
    elif isinstance(exception, TypeError):
        error_code = ErrorCode.INVALID_INPUT
    elif isinstance(exception, KeyError):
        error_code = ErrorCode.MISSING_REQUIRED_FIELD
    elif isinstance(exception, FileNotFoundError):
        error_code = ErrorCode.RESOURCE_NOT_FOUND
    elif isinstance(exception, PermissionError):
        error_code = ErrorCode.FORBIDDEN
    elif isinstance(exception, ConnectionError):
        error_code = ErrorCode.CONNECTION_ERROR
    elif isinstance(exception, TimeoutError):
        error_code = ErrorCode.OPERATION_TIMEOUT
    elif isinstance(exception, IOError):
        error_code = ErrorCode.IO_ERROR
    elif isinstance(exception, NotImplementedError):
        error_code = ErrorCode.INTERNAL_SERVER_ERROR
    
    # Create details dict
    details = {}
    if include_traceback:
        details["traceback"] = traceback.format_exc()
    
    # Create MCPError from the exception
    return MCPError(
        code=error_code,
        message=str(exception),
        details=details,
        original_error=exception,
        correlation_id=correlation_id,
        operation=operation
    )


def classify_error_code(status_code: int) -> ErrorCode:
    """
    Map an HTTP status code to an appropriate ErrorCode.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        Mapped ErrorCode
    """
    # Map common HTTP status codes to error codes
    mapping = {
        HTTPStatus.BAD_REQUEST: ErrorCode.INVALID_INPUT,
        HTTPStatus.UNAUTHORIZED: ErrorCode.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN: ErrorCode.FORBIDDEN,
        HTTPStatus.NOT_FOUND: ErrorCode.RESOURCE_NOT_FOUND,
        HTTPStatus.METHOD_NOT_ALLOWED: ErrorCode.INVALID_INPUT,
        HTTPStatus.CONFLICT: ErrorCode.RESOURCE_ALREADY_EXISTS,
        HTTPStatus.UNSUPPORTED_MEDIA_TYPE: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE: ErrorCode.VALUE_OUT_OF_RANGE,
        HTTPStatus.REQUEST_TIMEOUT: ErrorCode.REQUEST_TIMEOUT,
        HTTPStatus.TOO_MANY_REQUESTS: ErrorCode.RATE_LIMIT_EXCEEDED,
        HTTPStatus.INTERNAL_SERVER_ERROR: ErrorCode.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY: ErrorCode.UPSTREAM_SERVICE_ERROR,
        HTTPStatus.SERVICE_UNAVAILABLE: ErrorCode.DEPENDENCY_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT: ErrorCode.GATEWAY_TIMEOUT,
        HTTPStatus.INSUFFICIENT_STORAGE: ErrorCode.STORAGE_FULL
    }
    
    # Return mapped error code or default to unknown error
    return mapping.get(status_code, ErrorCode.UNKNOWN_ERROR)


def handle_error_response(
    response_dict: Dict[str, Any],
    correlation_id: Optional[str] = None
) -> MCPError:
    """
    Convert an error response dictionary to an MCPError.
    
    This is useful for handling errors from API responses.
    
    Args:
        response_dict: The error response dictionary
        correlation_id: Optional correlation ID
        
    Returns:
        An MCPError instance
    """
    # Check if it's already in the new error format
    if "error" in response_dict and isinstance(response_dict["error"], dict):
        error_info = response_dict["error"]
        
        # Extract error details
        code = error_info.get("code", ErrorCode.UNKNOWN_ERROR)
        message = error_info.get("message", "Unknown error")
        details = error_info.get("details")
        suggestion = error_info.get("suggestion")
        operation = error_info.get("operation")
        response_correlation_id = error_info.get("correlation_id")
        
        # Create MCPError
        return MCPError(
            code=code,
            message=message,
            details=details,
            correlation_id=correlation_id or response_correlation_id,
            suggestion=suggestion,
            operation=operation
        )
    
    # Handle legacy error format
    elif "error" in response_dict and isinstance(response_dict["error"], str):
        message = response_dict["error"]
        code = response_dict.get("error_code", ErrorCode.UNKNOWN_ERROR)
        details = response_dict.get("details")
        response_correlation_id = response_dict.get("correlation_id")
        
        # Create MCPError
        return MCPError(
            code=code,
            message=message,
            details=details,
            correlation_id=correlation_id or response_correlation_id
        )
    
    # Handle unknown error format
    else:
        return MCPError(
            code=ErrorCode.UNKNOWN_ERROR,
            message="Unknown error occurred",
            details={"raw_response": response_dict},
            correlation_id=correlation_id
        )


def safe_execute(
    func,
    *args,
    default_value: Any = None,
    error_handler: Optional[callable] = None,
    log_errors: bool = True,
    correlation_id: Optional[str] = None,
    operation: Optional[str] = None,
    **kwargs
) -> Tuple[bool, Any, Optional[MCPError]]:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        default_value: Default value to return on error
        error_handler: Custom error handler function
        log_errors: Whether to log errors
        correlation_id: Optional correlation ID
        operation: Optional operation name
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Tuple of (success, result, error)
            - success: Boolean indicating if the function executed successfully
            - result: Result of the function or default_value on error
            - error: MCPError instance on error, None on success
    """
    try:
        # Execute the function
        result = func(*args, **kwargs)
        return True, result, None
    
    except Exception as e:
        # Convert to MCPError
        error = error_from_exception(
            e,
            correlation_id=correlation_id,
            operation=operation
        )
        
        # Log the error if requested
        if log_errors:
            logger.error(
                f"Error in operation '{operation or func.__name__}': {error.message}",
                extra={
                    "correlation_id": error.correlation_id,
                    "error_code": error.code.value,
                    "error_category": error.category,
                    "error_details": error.details
                }
            )
        
        # Call custom error handler if provided
        if error_handler:
            try:
                error_handler(error)
            except Exception as handler_error:
                logger.error(f"Error in error handler: {handler_error}")
        
        # Return the error result
        return False, default_value, error


async def async_safe_execute(
    func,
    *args,
    default_value: Any = None,
    error_handler: Optional[callable] = None,
    log_errors: bool = True,
    correlation_id: Optional[str] = None,
    operation: Optional[str] = None,
    **kwargs
) -> Tuple[bool, Any, Optional[MCPError]]:
    """
    Safely execute an async function with error handling.
    
    Args:
        func: Async function to execute
        *args: Arguments to pass to the function
        default_value: Default value to return on error
        error_handler: Custom error handler function
        log_errors: Whether to log errors
        correlation_id: Optional correlation ID
        operation: Optional operation name
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Tuple of (success, result, error)
            - success: Boolean indicating if the function executed successfully
            - result: Result of the function or default_value on error
            - error: MCPError instance on error, None on success
    """
    try:
        # Execute the async function
        result = await func(*args, **kwargs)
        return True, result, None
    
    except Exception as e:
        # Convert to MCPError
        error = error_from_exception(
            e,
            correlation_id=correlation_id,
            operation=operation
        )
        
        # Log the error if requested
        if log_errors:
            logger.error(
                f"Error in async operation '{operation or func.__name__}': {error.message}",
                extra={
                    "correlation_id": error.correlation_id,
                    "error_code": error.code.value,
                    "error_category": error.category,
                    "error_details": error.details
                }
            )
        
        # Call custom error handler if provided
        if error_handler:
            try:
                if inspect.iscoroutinefunction(error_handler):
                    await error_handler(error)
                else:
                    error_handler(error)
            except Exception as handler_error:
                logger.error(f"Error in async error handler: {handler_error}")
        
        # Return the error result
        return False, default_value, error


# FastAPI integration utilities
try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    
    FASTAPI_AVAILABLE = True
    
    def add_error_handlers(app: FastAPI) -> None:
        """
        Add error handlers to a FastAPI application.
        
        Args:
            app: FastAPI application instance
        """
        # Handle validation errors
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            errors = exc.errors()
            details = {"validation_errors": errors}
            
            # Extract field names and create a user-friendly message
            fields = []
            for error in errors:
                loc = error.get("loc", [])
                if len(loc) > 1 and loc[0] == "body":
                    fields.append(loc[1])
                elif len(loc) > 0:
                    fields.append(loc[0])
            
            field_str = ", ".join(fields) if fields else "input data"
            message = f"Validation error with {field_str}"
            
            # Create MCPError
            error = MCPError(
                code=ErrorCode.INVALID_INPUT,
                message=message,
                details=details,
                original_error=exc
            )
            
            # Log the error
            logger.warning(
                f"Validation error: {message}",
                extra={
                    "correlation_id": error.correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                    "validation_errors": errors
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=error.status_code,
                content=error.to_dict()
            )
        
        # Handle Pydantic validation errors
        @app.exception_handler(ValidationError)
        async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
            errors = exc.errors()
            details = {"validation_errors": errors}
            
            # Extract field names and create a user-friendly message
            fields = []
            for error in errors:
                loc = error.get("loc", [])
                if loc:
                    fields.append(".".join(str(item) for item in loc))
            
            field_str = ", ".join(fields) if fields else "input data"
            message = f"Validation error with {field_str}"
            
            # Create MCPError
            error = MCPError(
                code=ErrorCode.INVALID_INPUT,
                message=message,
                details=details,
                original_error=exc
            )
            
            # Log the error
            logger.warning(
                f"Pydantic validation error: {message}",
                extra={
                    "correlation_id": error.correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                    "validation_errors": errors
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=error.status_code,
                content=error.to_dict()
            )
        
        # Handle MCPError exceptions
        @app.exception_handler(MCPError)
        async def mcp_error_exception_handler(request: Request, exc: MCPError):
            # Log the error
            level = logging.ERROR
            if exc.category in [ErrorCategory.VALIDATION, ErrorCategory.NOT_FOUND]:
                level = logging.WARNING
            
            logger.log(
                level,
                f"MCPError: {exc.message}",
                extra={
                    "correlation_id": exc.correlation_id,
                    "error_code": exc.code.value,
                    "error_category": exc.category,
                    "path": request.url.path,
                    "method": request.method,
                    "details": exc.details
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )
        
        # Handle generic exceptions
        @app.exception_handler(Exception)
        async def generic_exception_handler(request: Request, exc: Exception):
            # Convert to MCPError
            error = error_from_exception(
                exc,
                include_traceback=True
            )
            
            # Log the error
            logger.error(
                f"Unhandled exception: {error.message}",
                extra={
                    "correlation_id": error.correlation_id,
                    "error_code": error.code.value,
                    "error_category": error.category,
                    "path": request.url.path,
                    "method": request.method,
                    "details": error.details
                }
            )
            
            # Return error response
            return JSONResponse(
                status_code=error.status_code,
                content=error.to_dict()
            )
        
        # Add middleware to ensure correlation IDs and handle exceptions
        @app.middleware("http")
        async def error_handling_middleware(request: Request, call_next):
            # Generate or extract correlation ID
            correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
            
            try:
                # Call the next middleware or endpoint
                response = await call_next(request)
                
                # Add correlation ID to response headers
                response.headers["X-Correlation-ID"] = correlation_id
                
                return response
                
            except Exception as exc:
                # This should only catch exceptions not handled by the exception handlers
                # Convert to MCPError
                error = error_from_exception(
                    exc,
                    correlation_id=correlation_id,
                    include_traceback=True
                )
                
                # Log the error
                logger.error(
                    f"Unhandled middleware exception: {error.message}",
                    extra={
                        "correlation_id": error.correlation_id,
                        "error_code": error.code.value,
                        "error_category": error.category,
                        "path": request.url.path,
                        "method": request.method,
                        "details": error.details
                    }
                )
                
                # Return error response
                return JSONResponse(
                    status_code=error.status_code,
                    headers={"X-Correlation-ID": correlation_id},
                    content=error.to_dict()
                )
        
        # Log successful FastAPI setup
        logger.info("Added standardized error handlers to FastAPI application")

except ImportError:
    # FastAPI is not available
    FASTAPI_AVAILABLE = False
    logger.debug("FastAPI is not available. FastAPI integration features disabled.")


# Example usage
if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(level=logging.INFO)
    
    # Example 1: Basic error creation
    try:
        # Simulate an error
        raise ValueError("Invalid user input")
    except Exception as e:
        # Convert to MCPError
        error = error_from_exception(e)
        print("Example 1 - Basic error:")
        print(json.dumps(error.to_dict(), indent=2))
        print()
    
    # Example 2: Custom error with details
    custom_error = MCPError(
        code=ErrorCode.RESOURCE_NOT_FOUND,
        message="User profile not found",
        details={"user_id": "12345"},
        operation="get_user_profile"
    )
    print("Example 2 - Custom error with details:")
    print(json.dumps(custom_error.to_dict(), indent=2))
    print()
    
    # Example 3: Using safe_execute
    def example_function(x, y):
        return x / y
    
    print("Example 3 - Safe execute success:")
    success, result, error = safe_execute(example_function, 10, 2)
    print(f"Success: {success}, Result: {result}")
    print()
    
    print("Example 4 - Safe execute failure:")
    success, result, error = safe_execute(example_function, 10, 0, default_value="Error occurred")
    print(f"Success: {success}, Result: {result}")
    print(json.dumps(error.to_dict(), indent=2))
    print()
    
    # Example 5: Using specialized error classes
    validation_error = ValidationError("The email format is invalid")
    resource_not_found = ResourceNotFoundError("User", "12345")
    
    print("Example 5 - Specialized error classes:")
    print(json.dumps(validation_error.to_dict(), indent=2))
    print(json.dumps(resource_not_found.to_dict(), indent=2))