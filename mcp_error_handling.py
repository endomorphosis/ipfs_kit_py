"""
MCP Standardized Error Handling

This module provides standardized error handling functionality for the MCP server,
ensuring consistent error responses across all endpoints.
"""

import time
import logging
import traceback
from typing import Dict, Any, Optional, Type, List, Union
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Error response models
class ErrorDetails(BaseModel):
    """Detailed error information for debugging."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestion: Optional[str] = Field(None, description="Suggested action to resolve the error")
    documentation_url: Optional[str] = Field(None, description="URL to documentation for this error")

class ErrorResponse(BaseModel):
    """Standardized error response structure."""
    success: bool = Field(False, description="Always false for error responses")
    error: ErrorDetails = Field(..., description="Error details")
    timestamp: float = Field(..., description="Unix timestamp when the error occurred")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    endpoint: Optional[str] = Field(None, description="Endpoint that generated the error")

# Error codes with descriptions and HTTP status codes
ERROR_CODES = {
    # 400-level errors (client errors)
    "INVALID_REQUEST": {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "message": "Invalid request parameters",
        "suggestion": "Check the request parameters and try again"
    },
    "MISSING_PARAMETER": {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "message": "Required parameter is missing",
        "suggestion": "Include all required parameters in the request"
    },
    "INVALID_CID": {
        "status_code": status.HTTP_400_BAD_REQUEST,
        "message": "Invalid content identifier (CID)",
        "suggestion": "Verify the CID format and try again"
    },
    "CONTENT_NOT_FOUND": {
        "status_code": status.HTTP_404_NOT_FOUND,
        "message": "Content not found",
        "suggestion": "Verify the content exists before requesting it"
    },
    "AUTHENTICATION_REQUIRED": {
        "status_code": status.HTTP_401_UNAUTHORIZED,
        "message": "Authentication required",
        "suggestion": "Provide valid authentication credentials"
    },
    "UNAUTHORIZED": {
        "status_code": status.HTTP_403_FORBIDDEN,
        "message": "Not authorized to perform this action",
        "suggestion": "Request access or use different credentials"
    },
    "RATE_LIMITED": {
        "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
        "message": "Too many requests",
        "suggestion": "Reduce request frequency or contact administrator for increased limits"
    },
    
    # 500-level errors (server errors)
    "INTERNAL_ERROR": {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "Internal server error",
        "suggestion": "Contact the administrator with the request ID"
    },
    "SERVICE_UNAVAILABLE": {
        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
        "message": "Service temporarily unavailable",
        "suggestion": "Try again later"
    },
    "UPSTREAM_ERROR": {
        "status_code": status.HTTP_502_BAD_GATEWAY,
        "message": "Error in upstream service",
        "suggestion": "Check service status and try again later"
    },
    "DAEMON_ERROR": {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "Error communicating with IPFS daemon",
        "suggestion": "Verify the IPFS daemon is running"
    },
    "TIMEOUT": {
        "status_code": status.HTTP_504_GATEWAY_TIMEOUT,
        "message": "Request timed out",
        "suggestion": "Try again with a simpler request or contact administrator"
    },
    
    # Validation errors
    "VALIDATION_ERROR": {
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "message": "Validation error",
        "suggestion": "Check input data format and constraints"
    },
    
    # Storage backend errors
    "STORAGE_ERROR": {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "Storage backend error",
        "suggestion": "Check storage backend status and try again"
    },
    "SIMULATION_MODE": {
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "message": "Operation not supported in simulation mode",
        "suggestion": "Configure real storage backend credentials"
    },
    "MOCK_MODE": {
        "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "message": "Operation limited in mock mode",
        "suggestion": "Configure real storage backend credentials"
    },
    
    # Extension-specific errors
    "EXTENSION_ERROR": {
        "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "message": "Error in extension",
        "suggestion": "Check extension configuration and try again"
    },
    "EXTENSION_NOT_AVAILABLE": {
        "status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
        "message": "Required extension not available",
        "suggestion": "Install or enable the required extension"
    }
}

# Documentation URLs for different error categories
DOCUMENTATION_URLS = {
    "api": "https://docs.ipfs-kit.com/api/errors",
    "ipfs": "https://docs.ipfs-kit.com/ipfs/troubleshooting",
    "storage": "https://docs.ipfs-kit.com/storage/troubleshooting",
    "auth": "https://docs.ipfs-kit.com/auth/troubleshooting",
    "extensions": "https://docs.ipfs-kit.com/extensions/troubleshooting"
}

def create_error_response(
    code: str,
    details: Optional[Dict[str, Any]] = None,
    message_override: Optional[str] = None,
    suggestion_override: Optional[str] = None,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    doc_category: Optional[str] = "api"
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        code: Error code from ERROR_CODES
        details: Additional error details
        message_override: Override default error message
        suggestion_override: Override default suggestion
        request_id: Request ID for tracing
        endpoint: Endpoint that generated the error
        doc_category: Documentation category for URL
        
    Returns:
        Standardized error response dictionary
    """
    # Get error info from code
    if code not in ERROR_CODES:
        logger.warning(f"Unknown error code: {code}, falling back to INTERNAL_ERROR")
        code = "INTERNAL_ERROR"
    
    error_info = ERROR_CODES[code]
    
    # Build documentation URL if category is valid
    doc_url = None
    if doc_category in DOCUMENTATION_URLS:
        doc_url = f"{DOCUMENTATION_URLS[doc_category]}#{code.lower()}"
    
    # Create error details
    error_details = ErrorDetails(
        code=code,
        message=message_override or error_info["message"],
        details=details,
        suggestion=suggestion_override or error_info.get("suggestion"),
        documentation_url=doc_url
    )
    
    # Create error response
    error_response = ErrorResponse(
        success=False,
        error=error_details,
        timestamp=time.time(),
        request_id=request_id,
        endpoint=endpoint
    )
    
    # Convert to dict for JSON serialization
    return error_response.dict(exclude_none=True)

def raise_http_exception(
    code: str,
    details: Optional[Dict[str, Any]] = None,
    message_override: Optional[str] = None,
    suggestion_override: Optional[str] = None,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    doc_category: Optional[str] = "api"
) -> None:
    """
    Create and raise an HTTPException with standardized error response.
    
    Args:
        code: Error code from ERROR_CODES
        details: Additional error details
        message_override: Override default error message
        suggestion_override: Override default suggestion
        request_id: Request ID for tracing
        endpoint: Endpoint that generated the error
        doc_category: Documentation category for URL
        
    Raises:
        HTTPException with standardized error response
    """
    # Get error info for status code
    if code not in ERROR_CODES:
        logger.warning(f"Unknown error code: {code}, falling back to INTERNAL_ERROR")
        code = "INTERNAL_ERROR"
    
    error_info = ERROR_CODES[code]
    status_code = error_info["status_code"]
    
    # Create error response
    error_response = create_error_response(
        code=code,
        details=details,
        message_override=message_override,
        suggestion_override=suggestion_override,
        request_id=request_id,
        endpoint=endpoint,
        doc_category=doc_category
    )
    
    # Log the error
    logger.error(f"HTTP Exception ({status_code}): {error_response['error']['message']}")
    if details:
        logger.debug(f"Error details: {details}")
    
    # Raise HTTPException
    raise HTTPException(
        status_code=status_code,
        detail=error_response
    )

def handle_exception(
    exception: Exception,
    code: str = "INTERNAL_ERROR",
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    doc_category: Optional[str] = "api",
    log_traceback: bool = True
) -> Dict[str, Any]:
    """
    Handle exceptions and return standardized error response.
    
    Args:
        exception: The exception to handle
        code: Error code from ERROR_CODES
        request_id: Request ID for tracing
        endpoint: Endpoint that generated the error
        doc_category: Documentation category for URL
        log_traceback: Whether to log the full traceback
        
    Returns:
        Standardized error response dictionary
    """
    # Log the exception
    if log_traceback:
        logger.error(f"Exception in endpoint {endpoint}: {str(exception)}")
        logger.debug(traceback.format_exc())
    else:
        logger.error(f"Exception in endpoint {endpoint}: {str(exception)}")
    
    # Get exception details
    details = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception)
    }
    
    # Create error response
    return create_error_response(
        code=code,
        details=details,
        request_id=request_id,
        endpoint=endpoint,
        doc_category=doc_category
    )

# Exception handlers for common errors
def handle_validation_error(exception, request_id=None, endpoint=None):
    """Handle pydantic validation errors."""
    # Extract validation error details
    details = {"validation_errors": []}
    if hasattr(exception, "errors"):
        for error in exception.errors():
            details["validation_errors"].append({
                "loc": " -> ".join(str(loc) for loc in error["loc"]),
                "msg": error["msg"],
                "type": error["type"]
            })
    
    return create_error_response(
        code="VALIDATION_ERROR",
        details=details,
        request_id=request_id,
        endpoint=endpoint,
        doc_category="api"
    )

def handle_backend_error(exception, backend_name, request_id=None, endpoint=None):
    """Handle storage backend errors."""
    # Extract backend error details
    details = {
        "backend": backend_name,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception)
    }
    
    return create_error_response(
        code="STORAGE_ERROR",
        details=details,
        message_override=f"Error in {backend_name} backend: {str(exception)}",
        request_id=request_id,
        endpoint=endpoint,
        doc_category="storage"
    )

def handle_daemon_error(exception, request_id=None, endpoint=None):
    """Handle IPFS daemon errors."""
    # Extract daemon error details
    details = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception)
    }
    
    return create_error_response(
        code="DAEMON_ERROR",
        details=details,
        request_id=request_id,
        endpoint=endpoint,
        doc_category="ipfs"
    )

# Function to convert legacy error responses to standardized format
def standardize_legacy_error(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a legacy error response to the standardized format.
    
    Args:
        response: Legacy error response
        
    Returns:
        Standardized error response
    """
    # Check if this is already a standardized error
    if "error" in response and isinstance(response["error"], dict) and "code" in response["error"]:
        return response
    
    # Extract error information
    error_message = response.get("error", "Unknown error")
    
    # Choose an appropriate error code based on message content
    code = "INTERNAL_ERROR"  # Default
    
    if "not found" in error_message.lower():
        code = "CONTENT_NOT_FOUND"
    elif "invalid" in error_message.lower():
        code = "INVALID_REQUEST"
    elif "required" in error_message.lower():
        code = "MISSING_PARAMETER"
    elif "daemon" in error_message.lower():
        code = "DAEMON_ERROR"
    elif "timeout" in error_message.lower():
        code = "TIMEOUT"
    elif "simulation" in error_message.lower():
        code = "SIMULATION_MODE"
    elif "mock" in error_message.lower():
        code = "MOCK_MODE"
    
    # Create standardized error response
    return create_error_response(
        code=code,
        message_override=error_message,
        details={"original_response": response}
    )