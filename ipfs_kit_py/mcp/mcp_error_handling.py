"""
MCP Error Handling System.

This module provides standardized error handling functionality for the MCP server,
including consistent error responses, error codes, and error tracking.
"""

import logging
import traceback
import sys
import json
from enum import Enum
from typing import Dict, Any, Optional, Union, List, Tuple
from datetime import datetime

# Configure logger
logger = logging.getLogger("mcp.error")

class ErrorSeverity(str, Enum):
    """Severity levels for MCP errors."""
    
    CRITICAL = "critical"  # System cannot function, immediate attention required
    ERROR = "error"        # Operation failed, requires attention
    WARNING = "warning"    # Operation succeeded but with issues, attention recommended
    INFO = "info"          # Informational message about a potential issue


class ErrorCategory(str, Enum):
    """Categories of MCP errors."""
    
    AUTHENTICATION = "authentication"  # Authentication-related errors
    AUTHORIZATION = "authorization"    # Authorization-related errors
    VALIDATION = "validation"          # Input validation errors
    NETWORK = "network"                # Network connectivity errors
    STORAGE = "storage"                # Storage backend errors
    RESOURCE = "resource"              # Resource-related errors (not found, etc.)
    SYSTEM = "system"                  # Internal system errors
    SERVICE = "service"                # Service-related errors
    PROTOCOL = "protocol"              # Protocol-specific errors
    DATA = "data"                      # Data-related errors
    MIGRATION = "migration"            # Migration-related errors
    CONFIGURATION = "configuration"    # Configuration-related errors
    UNKNOWN = "unknown"                # Unknown or unclassified errors


class MCPError(Exception):
    """Base exception class for MCP server errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "MCP_UNKNOWN_ERROR",
        status_code: int = 500,
        category: Union[str, ErrorCategory] = ErrorCategory.UNKNOWN,
        severity: Union[str, ErrorSeverity] = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        error_id: Optional[str] = None,
        original_exception: Optional[Exception] = None
    ):
        """Initialize the MCP error.
        
        Args:
            message: Human-readable error message
            error_code: Unique error code identifier
            status_code: HTTP status code for this error
            category: Error category
            severity: Error severity level
            details: Additional details about the error
            suggestion: Suggested action to resolve the error
            error_id: Unique identifier for this error instance
            original_exception: Original exception that caused this error
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        
        # Convert string values to enums if needed
        if isinstance(category, str):
            try:
                self.category = ErrorCategory(category)
            except ValueError:
                self.category = ErrorCategory.UNKNOWN
        else:
            self.category = category
            
        if isinstance(severity, str):
            try:
                self.severity = ErrorSeverity(severity)
            except ValueError:
                self.severity = ErrorSeverity.ERROR
        else:
            self.severity = severity
            
        self.details = details or {}
        self.suggestion = suggestion
        self.error_id = error_id
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow().isoformat()
        
        # Call the base class constructor
        super().__init__(message)
        
        # Log the error
        self._log_error()
    
    def _log_error(self) -> None:
        """Log the error with appropriate severity."""
        log_message = f"{self.error_code}: {self.message}"
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=self.original_exception)
        elif self.severity == ErrorSeverity.ERROR:
            logger.error(log_message, exc_info=self.original_exception)
        elif self.severity == ErrorSeverity.WARNING:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation.
        
        Returns:
            Dictionary representation of the error
        """
        error_dict = {
            "error": True,
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp
        }
        
        if self.suggestion:
            error_dict["suggestion"] = self.suggestion
            
        if self.error_id:
            error_dict["error_id"] = self.error_id
            
        if self.details:
            error_dict["details"] = self.details
            
        return error_dict
    
    def to_json(self) -> str:
        """Convert error to JSON string.
        
        Returns:
            JSON string representation of the error
        """
        return json.dumps(self.to_dict())
    
    def to_response(self) -> Tuple[Dict[str, Any], int]:
        """Convert error to API response.
        
        Returns:
            Tuple of (response_dict, status_code)
        """
        return self.to_dict(), self.status_code


# Authentication errors
class AuthenticationError(MCPError):
    """Error raised when authentication fails."""
    
    def __init__(
        self, 
        message: str = "Authentication failed", 
        error_code: str = "MCP_AUTH_FAILED",
        status_code: int = 401,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.AUTHENTICATION,
            **kwargs
        )


class InvalidCredentialsError(AuthenticationError):
    """Error raised when credentials are invalid."""
    
    def __init__(
        self,
        message: str = "Invalid credentials provided",
        error_code: str = "MCP_INVALID_CREDENTIALS",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            suggestion="Please check your username and password",
            **kwargs
        )


class TokenExpiredError(AuthenticationError):
    """Error raised when an authentication token has expired."""
    
    def __init__(
        self,
        message: str = "Authentication token has expired",
        error_code: str = "MCP_TOKEN_EXPIRED",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            suggestion="Please obtain a new authentication token",
            **kwargs
        )


# Authorization errors
class AuthorizationError(MCPError):
    """Error raised when a user is not authorized to perform an action."""
    
    def __init__(
        self,
        message: str = "Not authorized to perform this action",
        error_code: str = "MCP_NOT_AUTHORIZED",
        status_code: int = 403,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.AUTHORIZATION,
            **kwargs
        )


class InsufficientPermissionsError(AuthorizationError):
    """Error raised when a user has insufficient permissions."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        error_code: str = "MCP_INSUFFICIENT_PERMISSIONS",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            **kwargs
        )


# Validation errors
class ValidationError(MCPError):
    """Error raised when input validation fails."""
    
    def __init__(
        self,
        message: str = "Input validation failed",
        error_code: str = "MCP_VALIDATION_FAILED",
        status_code: int = 400,
        field_errors: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if field_errors:
            details["field_errors"] = field_errors
            kwargs["details"] = details
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.VALIDATION,
            **kwargs
        )


class MissingParameterError(ValidationError):
    """Error raised when a required parameter is missing."""
    
    def __init__(
        self,
        parameter: str,
        message: Optional[str] = None,
        error_code: str = "MCP_MISSING_PARAMETER",
        **kwargs
    ):
        if message is None:
            message = f"Required parameter '{parameter}' is missing"
            
        super().__init__(
            message=message,
            error_code=error_code,
            suggestion=f"Please provide the '{parameter}' parameter",
            details={"parameter": parameter, **kwargs.get("details", {})},
            **kwargs
        )


class InvalidParameterError(ValidationError):
    """Error raised when a parameter is invalid."""
    
    def __init__(
        self,
        parameter: str,
        reason: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_INVALID_PARAMETER",
        **kwargs
    ):
        if message is None:
            message = f"Parameter '{parameter}' is invalid"
            if reason:
                message += f": {reason}"
                
        details = {"parameter": parameter}
        if reason:
            details["reason"] = reason
            
        details = {**details, **kwargs.get("details", {})}
        
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            **kwargs
        )


# Resource errors
class ResourceError(MCPError):
    """Error raised when a resource operation fails."""
    
    def __init__(
        self,
        message: str = "Resource operation failed",
        error_code: str = "MCP_RESOURCE_ERROR",
        status_code: int = 500,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.RESOURCE,
            **kwargs
        )


class ResourceNotFoundError(ResourceError):
    """Error raised when a resource is not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_RESOURCE_NOT_FOUND",
        status_code: int = 404,
        **kwargs
    ):
        if message is None:
            message = f"{resource_type} not found"
            if resource_id:
                message += f": {resource_id}"
                
        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id
            
        details = {**details, **kwargs.get("details", {})}
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            **kwargs
        )


class ResourceAlreadyExistsError(ResourceError):
    """Error raised when a resource already exists."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_RESOURCE_ALREADY_EXISTS",
        status_code: int = 409,
        **kwargs
    ):
        if message is None:
            message = f"{resource_type} already exists"
            if resource_id:
                message += f": {resource_id}"
                
        details = {"resource_type": resource_type}
        if resource_id:
            details["resource_id"] = resource_id
            
        details = {**details, **kwargs.get("details", {})}
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            **kwargs
        )


# Storage errors
class StorageError(MCPError):
    """Error raised when a storage operation fails."""
    
    def __init__(
        self,
        message: str = "Storage operation failed",
        error_code: str = "MCP_STORAGE_ERROR",
        status_code: int = 500,
        backend: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if backend:
            details["backend"] = backend
            kwargs["details"] = details
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.STORAGE,
            **kwargs
        )


class StorageBackendUnavailableError(StorageError):
    """Error raised when a storage backend is unavailable."""
    
    def __init__(
        self,
        backend: str,
        message: Optional[str] = None,
        error_code: str = "MCP_STORAGE_BACKEND_UNAVAILABLE",
        **kwargs
    ):
        if message is None:
            message = f"Storage backend '{backend}' is unavailable"
            
        super().__init__(
            message=message,
            error_code=error_code,
            backend=backend,
            **kwargs
        )


class ContentNotFoundError(StorageError):
    """Error raised when content is not found in storage."""
    
    def __init__(
        self,
        content_id: str,
        backend: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_CONTENT_NOT_FOUND",
        status_code: int = 404,
        **kwargs
    ):
        if message is None:
            message = f"Content not found: {content_id}"
            if backend:
                message += f" (backend: {backend})"
                
        details = {"content_id": content_id}
        if backend:
            details["backend"] = backend
            
        details = {**details, **kwargs.get("details", {})}
        
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            details=details,
            **kwargs
        )


# Network errors
class NetworkError(MCPError):
    """Error raised when a network operation fails."""
    
    def __init__(
        self,
        message: str = "Network operation failed",
        error_code: str = "MCP_NETWORK_ERROR",
        status_code: int = 503,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.NETWORK,
            **kwargs
        )


class ConnectionError(NetworkError):
    """Error raised when a connection fails."""
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_CONNECTION_ERROR",
        **kwargs
    ):
        if message is None:
            message = "Connection failed"
            if endpoint:
                message += f": {endpoint}"
                
        details = kwargs.get("details", {})
        if endpoint:
            details["endpoint"] = endpoint
            kwargs["details"] = details
            
        super().__init__(
            message=message,
            error_code=error_code,
            **kwargs
        )


class TimeoutError(NetworkError):
    """Error raised when a network operation times out."""
    
    def __init__(
        self,
        operation: Optional[str] = None,
        message: Optional[str] = None,
        error_code: str = "MCP_TIMEOUT_ERROR",
        **kwargs
    ):
        if message is None:
            message = "Operation timed out"
            if operation:
                message += f": {operation}"
                
        details = kwargs.get("details", {})
        if operation:
            details["operation"] = operation
            kwargs["details"] = details
            
        super().__init__(
            message=message,
            error_code=error_code,
            **kwargs
        )


# Migration errors
class MigrationError(MCPError):
    """Error raised when a migration operation fails."""
    
    def __init__(
        self,
        message: str = "Migration operation failed",
        error_code: str = "MCP_MIGRATION_ERROR",
        status_code: int = 500,
        migration_id: Optional[str] = None,
        source_backend: Optional[str] = None,
        target_backend: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.get("details", {})
        if migration_id:
            details["migration_id"] = migration_id
        if source_backend:
            details["source_backend"] = source_backend
        if target_backend:
            details["target_backend"] = target_backend
            
        kwargs["details"] = details
            
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.MIGRATION,
            **kwargs
        )


# System errors
class SystemError(MCPError):
    """Error raised when a system operation fails."""
    
    def __init__(
        self,
        message: str = "System error occurred",
        error_code: str = "MCP_SYSTEM_ERROR",
        status_code: int = 500,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.ERROR,
            **kwargs
        )


class ConfigurationError(SystemError):
    """Error raised when there is a configuration issue."""
    
    def __init__(
        self,
        message: str = "Configuration error",
        error_code: str = "MCP_CONFIGURATION_ERROR",
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.CONFIGURATION,
            **kwargs
        )


# Helper functions
def handle_exception(
    exception: Exception,
    default_message: str = "An unexpected error occurred",
    default_status_code: int = 500,
    include_traceback: bool = False
) -> Tuple[Dict[str, Any], int]:
    """Convert an exception to a standardized error response.
    
    Args:
        exception: The exception to handle
        default_message: Default message to use if the exception is not an MCPError
        default_status_code: Default HTTP status code to use
        include_traceback: Whether to include the traceback in the response
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    if isinstance(exception, MCPError):
        response_dict, status_code = exception.to_response()
    else:
        # Create a generic MCPError from the exception
        error = MCPError(
            message=str(exception) or default_message,
            error_code="MCP_UNEXPECTED_ERROR",
            status_code=default_status_code,
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.ERROR,
            original_exception=exception
        )
        response_dict, status_code = error.to_response()
    
    # Add traceback if requested
    if include_traceback:
        tb = traceback.format_exception(type(exception), exception, exception.__traceback__)
        response_dict["traceback"] = tb
    
    return response_dict, status_code


def convert_legacy_error(
    error_dict: Dict[str, Any],
    default_code: str = "MCP_LEGACY_ERROR"
) -> Dict[str, Any]:
    """Convert a legacy error format to the standardized format.
    
    Args:
        error_dict: Legacy error dictionary
        default_code: Default error code to use
        
    Returns:
        Standardized error dictionary
    """
    # Extract information from legacy format
    message = error_dict.get("message") or error_dict.get("error") or "Unknown error"
    error_code = error_dict.get("code") or default_code
    status_code = error_dict.get("status") or 500
    details = {k: v for k, v in error_dict.items() if k not in ["message", "code", "status", "error"]}
    
    # Create standardized error
    error = MCPError(
        message=message,
        error_code=error_code,
        status_code=status_code,
        details=details if details else None
    )
    
    return error.to_dict()