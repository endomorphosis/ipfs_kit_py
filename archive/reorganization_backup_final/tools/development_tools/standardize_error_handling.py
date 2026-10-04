"""
Standardized error handling for IPFS Kit.

This module provides a consistent error handling framework for the IPFS Kit
ecosystem, including error classification, structured error responses, and
integration with FastAPI for consistent API error responses.
"""

import sys
import uuid
import enum
import traceback
import inspect
import logging
from typing import Dict, Any, List, Optional, Callable, Tuple, TypeVar, Union, Type
from http import HTTPStatus

# Configure logging
logger = logging.getLogger("standardize_error_handling")

# Type variables for generic functions
T = TypeVar('T')
R = TypeVar('R')


class ErrorCategory(str, enum.Enum):
    """Categories of errors for better grouping and filtering."""
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMIT = "rate_limit"
    TIMEOUT_ERROR = "timeout"  # Named TIMEOUT_ERROR for API consistency
    DEPENDENCY_ERROR = "dependency_error"
    STORAGE_ERROR = "storage_error"
    NETWORK_ERROR = "network_error"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorCode(str, enum.Enum):
    """Standardized error codes for consistent error identification."""
    # Validation errors
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_FIELD_FORMAT = "invalid_field_format"
    
    # Not found errors
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONTENT_NOT_FOUND = "content_not_found"
    PROVIDER_NOT_FOUND = "provider_not_found"
    PEER_NOT_FOUND = "peer_not_found"
    ROUTE_NOT_FOUND = "route_not_found"
    
    # Authentication errors
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    TOKEN_EXPIRED = "token_expired"
    
    # Authorization errors
    PERMISSION_DENIED = "permission_denied"
    INSUFFICIENT_PRIVILEGES = "insufficient_privileges"
    
    # Rate limit errors
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    QUOTA_EXCEEDED = "quota_exceeded"
    
    # Timeout errors
    OPERATION_TIMEOUT = "operation_timeout"
    CONNECTION_TIMEOUT = "connection_timeout"
    
    # Dependency errors
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DEPENDENCY_CONFIGURATION_ERROR = "dependency_configuration_error"
    
    # Storage errors
    STORAGE_UNAVAILABLE = "storage_unavailable"
    STORAGE_QUOTA_EXCEEDED = "storage_quota_exceeded"
    CONTENT_ALREADY_EXISTS = "content_already_exists"
    
    # Network errors
    NETWORK_UNAVAILABLE = "network_unavailable"
    CONNECTION_RESET = "connection_reset"
    PEER_UNREACHABLE = "peer_unreachable"
    
    # Internal errors
    INTERNAL_SERVER_ERROR = "internal_server_error"
    CONFIGURATION_ERROR = "configuration_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # Unknown errors
    UNKNOWN_ERROR = "unknown_error"


# Map error codes to HTTP status codes
ERROR_CODE_TO_STATUS = {
    # Validation errors -> 400 Bad Request
    ErrorCode.INVALID_INPUT: HTTPStatus.BAD_REQUEST,
    ErrorCode.MISSING_REQUIRED_FIELD: HTTPStatus.BAD_REQUEST,
    ErrorCode.INVALID_FIELD_FORMAT: HTTPStatus.BAD_REQUEST,
    
    # Not found errors -> 404 Not Found
    ErrorCode.RESOURCE_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.CONTENT_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.PROVIDER_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.PEER_NOT_FOUND: HTTPStatus.NOT_FOUND,
    ErrorCode.ROUTE_NOT_FOUND: HTTPStatus.NOT_FOUND,
    
    # Authentication errors -> 401 Unauthorized
    ErrorCode.AUTHENTICATION_REQUIRED: HTTPStatus.UNAUTHORIZED,
    ErrorCode.INVALID_CREDENTIALS: HTTPStatus.UNAUTHORIZED,
    ErrorCode.TOKEN_EXPIRED: HTTPStatus.UNAUTHORIZED,
    
    # Authorization errors -> 403 Forbidden
    ErrorCode.PERMISSION_DENIED: HTTPStatus.FORBIDDEN,
    ErrorCode.INSUFFICIENT_PRIVILEGES: HTTPStatus.FORBIDDEN,
    
    # Rate limit errors -> 429 Too Many Requests
    ErrorCode.RATE_LIMIT_EXCEEDED: HTTPStatus.TOO_MANY_REQUESTS,
    ErrorCode.QUOTA_EXCEEDED: HTTPStatus.TOO_MANY_REQUESTS,
    
    # Timeout errors -> 504 Gateway Timeout
    ErrorCode.OPERATION_TIMEOUT: HTTPStatus.GATEWAY_TIMEOUT,
    ErrorCode.CONNECTION_TIMEOUT: HTTPStatus.GATEWAY_TIMEOUT,
    
    # Dependency errors -> 503 Service Unavailable
    ErrorCode.DEPENDENCY_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    ErrorCode.DEPENDENCY_CONFIGURATION_ERROR: HTTPStatus.SERVICE_UNAVAILABLE,
    
    # Storage errors -> 507 Insufficient Storage (or others)
    ErrorCode.STORAGE_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    ErrorCode.STORAGE_QUOTA_EXCEEDED: HTTPStatus.INSUFFICIENT_STORAGE,
    ErrorCode.CONTENT_ALREADY_EXISTS: HTTPStatus.CONFLICT,
    
    # Network errors -> 503 Service Unavailable (or others)
    ErrorCode.NETWORK_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    ErrorCode.CONNECTION_RESET: HTTPStatus.BAD_GATEWAY,
    ErrorCode.PEER_UNREACHABLE: HTTPStatus.BAD_GATEWAY,
    
    # Internal errors -> 500 Internal Server Error
    ErrorCode.INTERNAL_SERVER_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
    ErrorCode.CONFIGURATION_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE: HTTPStatus.SERVICE_UNAVAILABLE,
    
    # Unknown errors -> 500 Internal Server Error
    ErrorCode.UNKNOWN_ERROR: HTTPStatus.INTERNAL_SERVER_ERROR,
}

# Map error codes to categories
ERROR_CODE_TO_CATEGORY = {
    # Validation errors
    ErrorCode.INVALID_INPUT: ErrorCategory.VALIDATION,
    ErrorCode.MISSING_REQUIRED_FIELD: ErrorCategory.VALIDATION,
    ErrorCode.INVALID_FIELD_FORMAT: ErrorCategory.VALIDATION,
    
    # Not found errors
    ErrorCode.RESOURCE_NOT_FOUND: ErrorCategory.NOT_FOUND,
    ErrorCode.CONTENT_NOT_FOUND: ErrorCategory.NOT_FOUND,
    ErrorCode.PROVIDER_NOT_FOUND: ErrorCategory.NOT_FOUND,
    ErrorCode.PEER_NOT_FOUND: ErrorCategory.NOT_FOUND,
    ErrorCode.ROUTE_NOT_FOUND: ErrorCategory.NOT_FOUND,
    
    # Authentication errors
    ErrorCode.AUTHENTICATION_REQUIRED: ErrorCategory.AUTHENTICATION,
    ErrorCode.INVALID_CREDENTIALS: ErrorCategory.AUTHENTICATION,
    ErrorCode.TOKEN_EXPIRED: ErrorCategory.AUTHENTICATION,
    
    # Authorization errors
    ErrorCode.PERMISSION_DENIED: ErrorCategory.AUTHORIZATION,
    ErrorCode.INSUFFICIENT_PRIVILEGES: ErrorCategory.AUTHORIZATION,
    
    # Rate limit errors
    ErrorCode.RATE_LIMIT_EXCEEDED: ErrorCategory.RATE_LIMIT,
    ErrorCode.QUOTA_EXCEEDED: ErrorCategory.RATE_LIMIT,
    
    # Timeout errors
    ErrorCode.OPERATION_TIMEOUT: ErrorCategory.TIMEOUT_ERROR,
    ErrorCode.CONNECTION_TIMEOUT: ErrorCategory.TIMEOUT_ERROR,
    
    # Dependency errors
    ErrorCode.DEPENDENCY_UNAVAILABLE: ErrorCategory.DEPENDENCY_ERROR,
    ErrorCode.DEPENDENCY_CONFIGURATION_ERROR: ErrorCategory.DEPENDENCY_ERROR,
    
    # Storage errors
    ErrorCode.STORAGE_UNAVAILABLE: ErrorCategory.STORAGE_ERROR,
    ErrorCode.STORAGE_QUOTA_EXCEEDED: ErrorCategory.STORAGE_ERROR,
    ErrorCode.CONTENT_ALREADY_EXISTS: ErrorCategory.STORAGE_ERROR,
    
    # Network errors
    ErrorCode.NETWORK_UNAVAILABLE: ErrorCategory.NETWORK_ERROR,
    ErrorCode.CONNECTION_RESET: ErrorCategory.NETWORK_ERROR,
    ErrorCode.PEER_UNREACHABLE: ErrorCategory.NETWORK_ERROR,
    
    # Internal errors
    ErrorCode.INTERNAL_SERVER_ERROR: ErrorCategory.INTERNAL_ERROR,
    ErrorCode.CONFIGURATION_ERROR: ErrorCategory.INTERNAL_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE: ErrorCategory.INTERNAL_ERROR,
    
    # Unknown errors
    ErrorCode.UNKNOWN_ERROR: ErrorCategory.UNKNOWN_ERROR,
}


def classify_error_code(code: ErrorCode) -> ErrorCategory:
    """Classify an error code into its category."""
    return ERROR_CODE_TO_CATEGORY.get(code, ErrorCategory.UNKNOWN_ERROR)


class MCPError(Exception):
    """Base class for all MCP-specific errors."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a new MCP error.
        
        Args:
            code: The error code from ErrorCode enum
            message: Human-readable error message
            details: Additional error details as a dictionary
            operation: Operation that failed (for context)
            correlation_id: Unique identifier to track the error across systems
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.operation = operation
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.category = classify_error_code(code)
        self.status_code = ERROR_CODE_TO_STATUS.get(code, HTTPStatus.INTERNAL_SERVER_ERROR)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for API responses."""
        return {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "category": self.category.value,
                "correlation_id": self.correlation_id,
                "details": self.details,
                "operation": self.operation
            }
        }


class ValidationError(MCPError):
    """Error raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a validation error.
        
        Args:
            message: Human-readable error message
            field: Name of the field that failed validation
            value: The invalid value
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        if field:
            err_details["field"] = field
        if value is not None:
            err_details["invalid_value"] = str(value)
        
        super().__init__(
            code=ErrorCode.INVALID_INPUT,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class ResourceNotFoundError(MCPError):
    """Error raised when a requested resource is not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a resource not found error.
        
        Args:
            resource_type: Type of resource (e.g., "User", "File")
            resource_id: ID of the resource that wasn't found
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["resource_type"] = resource_type
        err_details["resource_id"] = resource_id
        
        if not message:
            message = f"{resource_type} with ID '{resource_id}' not found"
        
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class ContentNotFoundError(ResourceNotFoundError):
    """Error raised when IPFS content is not found."""
    
    def __init__(
        self,
        cid: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a content not found error.
        
        Args:
            cid: Content ID that wasn't found
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        if not message:
            message = f"Content with CID '{cid}' not found"
        
        super().__init__(
            resource_type="Content",
            resource_id=cid,
            message=message,
            details=details,
            operation=operation,
            correlation_id=correlation_id,
        )
        self.code = ErrorCode.CONTENT_NOT_FOUND


class DependencyError(MCPError):
    """Error raised when a dependency is unavailable."""
    
    def __init__(
        self,
        dependency_name: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a dependency error.
        
        Args:
            dependency_name: Name of the unavailable dependency
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["dependency_name"] = dependency_name
        
        if not message:
            message = f"Dependency '{dependency_name}' is unavailable"
        
        super().__init__(
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class StorageError(MCPError):
    """Error raised when a storage system is unavailable."""
    
    def __init__(
        self,
        storage_type: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a storage error.
        
        Args:
            storage_type: Type of storage (e.g., "IPFS", "S3")
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["storage_type"] = storage_type
        
        if not message:
            message = f"Storage system '{storage_type}' is unavailable"
        
        super().__init__(
            code=ErrorCode.STORAGE_UNAVAILABLE,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class TimeoutError(MCPError):
    """Error raised when an operation times out."""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a timeout error.
        
        Args:
            operation: Name of the operation that timed out
            timeout_seconds: Timeout in seconds
            message: Human-readable error message
            details: Additional error details
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["operation"] = operation
        err_details["timeout_seconds"] = timeout_seconds
        
        if not message:
            message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        
        super().__init__(
            code=ErrorCode.OPERATION_TIMEOUT,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class RateLimitError(MCPError):
    """Error raised when rate limits are exceeded."""
    
    def __init__(
        self,
        limit: int,
        reset_after: int,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a rate limit error.
        
        Args:
            limit: Rate limit that was exceeded
            reset_after: Seconds until the rate limit resets
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["limit"] = limit
        err_details["reset_after"] = reset_after
        
        if not message:
            message = f"Rate limit exceeded. Try again in {reset_after} seconds"
        
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


class ConfigurationError(MCPError):
    """Error raised when there's a configuration issue."""
    
    def __init__(
        self,
        config_key: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        operation: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Initialize a configuration error.
        
        Args:
            config_key: The configuration key that has an issue
            message: Human-readable error message
            details: Additional error details
            operation: Operation that failed
            correlation_id: Unique identifier to track the error
        """
        err_details = details or {}
        err_details["config_key"] = config_key
        
        if not message:
            message = f"Configuration error for '{config_key}'"
        
        super().__init__(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=message,
            details=err_details,
            operation=operation,
            correlation_id=correlation_id,
        )


# Error mapping for converting standard Python exceptions to MCP errors
EXCEPTION_TO_ERROR_CODE = {
    ValueError: ErrorCode.INVALID_INPUT,
    TypeError: ErrorCode.INVALID_INPUT,
    KeyError: ErrorCode.MISSING_REQUIRED_FIELD,
    IndexError: ErrorCode.RESOURCE_NOT_FOUND,
    FileNotFoundError: ErrorCode.RESOURCE_NOT_FOUND,
    PermissionError: ErrorCode.PERMISSION_DENIED,
    ConnectionError: ErrorCode.NETWORK_UNAVAILABLE,
    ConnectionRefusedError: ErrorCode.DEPENDENCY_UNAVAILABLE,
    ConnectionResetError: ErrorCode.CONNECTION_RESET,
    BrokenPipeError: ErrorCode.CONNECTION_RESET,
    TimeoutError: ErrorCode.OPERATION_TIMEOUT,
    ModuleNotFoundError: ErrorCode.DEPENDENCY_UNAVAILABLE,
    ImportError: ErrorCode.DEPENDENCY_UNAVAILABLE,
    NotImplementedError: ErrorCode.INTERNAL_SERVER_ERROR,
    ZeroDivisionError: ErrorCode.INVALID_INPUT,  # Often due to invalid input
}


def error_from_exception(
    exception: Exception, 
    default_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
    include_traceback: bool = False
) -> MCPError:
    """Convert a standard Python exception to an MCP error.
    
    Args:
        exception: The exception to convert
        default_code: The error code to use if the exception type isn't mapped
        include_traceback: Whether to include the traceback in the error details
        
    Returns:
        MCPError: The converted error
    """
    # Get error code based on exception type
    for exc_type, code in EXCEPTION_TO_ERROR_CODE.items():
        if isinstance(exception, exc_type):
            error_code = code
            break
    else:
        error_code = default_code
    
    # Extract message
    if hasattr(exception, "args") and len(exception.args) > 0:
        message = str(exception.args[0])
    else:
        message = str(exception)
    
    # Create details
    details = {
        "original_error_type": exception.__class__.__name__
    }
    
    # Add traceback if requested
    if include_traceback:
        details["traceback"] = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
    
    # Create and return MCP error
    return MCPError(
        code=error_code,
        message=message,
        details=details,
        operation=None  # operation context not available from exception
    )


def safe_execute(
    func: Callable[..., T],
    *args,
    default_value: Optional[R] = None,
    error_handler: Optional[Callable[[MCPError], None]] = None,
    **kwargs
) -> Tuple[bool, Union[T, R], Optional[MCPError]]:
    """Safely execute a function and handle exceptions.
    
    Args:
        func: The function to execute
        *args: Positional arguments to pass to the function
        default_value: Value to return if the function fails
        error_handler: Optional function to call with the error
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Tuple containing:
        - success: boolean indicating if the function executed successfully
        - result: the function result or default_value if failed
        - error: MCPError if an error occurred, otherwise None
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        # Convert to MCP error
        if isinstance(e, MCPError):
            error = e
        else:
            error = error_from_exception(e)
        
        # Log the error
        logger.error(f"Error executing {func.__name__}: {error.message}")
        
        # Call error handler if provided
        if error_handler:
            error_handler(error)
        
        return False, default_value, error


async def async_safe_execute(
    func: Callable[..., T],
    *args,
    default_value: Optional[R] = None,
    error_handler: Optional[Union[Callable[[MCPError], None], Callable[[MCPError], Any]]] = None,
    **kwargs
) -> Tuple[bool, Union[T, R], Optional[MCPError]]:
    """Safely execute an async function and handle exceptions.
    
    Args:
        func: The async function to execute
        *args: Positional arguments to pass to the function
        default_value: Value to return if the function fails
        error_handler: Optional function to call with the error (can be async or sync)
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Tuple containing:
        - success: boolean indicating if the function executed successfully
        - result: the function result or default_value if failed
        - error: MCPError if an error occurred, otherwise None
    """
    try:
        result = await func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        # Convert to MCP error
        if isinstance(e, MCPError):
            error = e
        else:
            error = error_from_exception(e)
        
        # Log the error
        logger.error(f"Error executing async {func.__name__}: {error.message}")
        
        # Call error handler if provided
        if error_handler:
            try:
                # Check if error handler is a coroutine function
                if inspect.iscoroutinefunction(error_handler):
                    await error_handler(error)
                else:
                    error_handler(error)
            except Exception as handler_error:
                logger.error(f"Error in error handler: {handler_error}")
        
        return False, default_value, error


def handle_error_response(response_data: Dict[str, Any]) -> MCPError:
    """Parse an error response and convert it to an MCPError.
    
    Handles both the new standardized error format and legacy formats.
    
    Args:
        response_data: The error response data
        
    Returns:
        MCPError: The parsed error
    """
    # Check if it's the new standardized format
    if isinstance(response_data.get("success"), bool) and response_data.get("success") is False:
        error_data = response_data.get("error", {})
        
        if isinstance(error_data, dict):
            # New format with detailed error object
            code_str = error_data.get("code", "unknown_error")
            try:
                code = ErrorCode(code_str)
            except ValueError:
                code = ErrorCode.UNKNOWN_ERROR
            
            message = error_data.get("message", "Unknown error")
            correlation_id = error_data.get("correlation_id")
            details = error_data.get("details", {})
            operation = error_data.get("operation")
            
            return MCPError(
                code=code,
                message=message,
                details=details,
                operation=operation,
                correlation_id=correlation_id
            )
        else:
            # Legacy format with simple error string
            message = str(error_data or "Unknown error")
            code_str = response_data.get("error_code", "unknown_error")
            try:
                code = ErrorCode(code_str)
            except ValueError:
                code = ErrorCode.UNKNOWN_ERROR
            
            details = response_data.get("details", {})
            
            return MCPError(
                code=code,
                message=message,
                details=details
            )
    
    # Unknown format, return generic error with the raw response
    return MCPError(
        code=ErrorCode.UNKNOWN_ERROR,
        message="Unknown error format in response",
        details={"raw_response": response_data}
    )


# FastAPI integration if available
try:
    from fastapi import FastAPI, Request, Response, HTTPException
    from fastapi.responses import JSONResponse
    
    def add_error_handlers(app: FastAPI) -> None:
        """Add standardized error handlers to a FastAPI application.
        
        Args:
            app: The FastAPI application to add handlers to
        """
        # Handler for MCPError exceptions
        @app.exception_handler(MCPError)
        async def mcp_error_handler(request: Request, error: MCPError) -> JSONResponse:
            # Extract or generate correlation ID
            correlation_id = error.correlation_id or request.headers.get("X-Correlation-ID")
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            # Update error with correlation ID
            error.correlation_id = correlation_id
            
            # Log the error
            logger.error(
                f"API Error {error.code.value} [{correlation_id}]: {error.message}", 
                extra={"correlation_id": correlation_id}
            )
            
            # Create response
            response = JSONResponse(
                status_code=error.status_code,
                content=error.to_dict()
            )
            
            # Add correlation ID header
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
        
        # Handler for FastAPI HTTPException
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
            # Map status code to error code
            error_code = ErrorCode.UNKNOWN_ERROR
            for code, status in ERROR_CODE_TO_STATUS.items():
                if status == exc.status_code:
                    error_code = code
                    break
            
            # Create MCP error
            error = MCPError(
                code=error_code,
                message=exc.detail,
                details={"headers": dict(exc.headers or {})}
            )
            
            # Use the MCP error handler
            return await mcp_error_handler(request, error)
        
        # Handler for generic exceptions
        @app.exception_handler(Exception)
        async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
            # Convert to MCP error
            error = error_from_exception(exc, include_traceback=True)
            
            # Extract or generate correlation ID
            correlation_id = request.headers.get("X-Correlation-ID")
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            # Update error with correlation ID
            error.correlation_id = correlation_id
            
            # Log the error
            logger.error(
                f"API Error {error.code.value} [{correlation_id}]: {error.message}", 
                extra={"correlation_id": correlation_id}
            )
            
            # Create response
            response = JSONResponse(
                status_code=error.status_code,
                content=error.to_dict()
            )
            
            # Add correlation ID header
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
        
        # Add middleware for correlation ID propagation
        @app.middleware("http")
        async def correlation_id_middleware(request: Request, call_next):
            # Extract or generate correlation ID
            correlation_id = request.headers.get("X-Correlation-ID")
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
            
            # Add to request state
            request.state.correlation_id = correlation_id
            
            # Process request
            response = await call_next(request)
            
            # Add correlation ID header to response
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
except ImportError:
    # FastAPI not available, provide dummy function
    def add_error_handlers(app: Any) -> None:
        """Dummy function when FastAPI is not available."""
        logger.warning("FastAPI not available. Error handlers not added.")