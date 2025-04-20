"""
Standardized error handling module for MCP components.

This module provides a standard way to raise and handle errors in the MCP architecture.
"""

import logging
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException, status

# Configure logger
logger = logging.getLogger(__name__)

# Define standard error codes and their HTTP status codes
ERROR_CODES = {
    # Storage errors
    "STORAGE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "STORAGE_NOT_AVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "STORAGE_ACCESS_DENIED": status.HTTP_403_FORBIDDEN,
    "STORAGE_QUOTA_EXCEEDED": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    
    # Content errors
    "CONTENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "CONTENT_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
    "CONTENT_TOO_LARGE": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    "CONTENT_INVALID": status.HTTP_400_BAD_REQUEST,
    
    # Authentication/authorization errors
    "AUTH_REQUIRED": status.HTTP_401_UNAUTHORIZED,
    "PERMISSION_DENIED": status.HTTP_403_FORBIDDEN,
    "TOKEN_EXPIRED": status.HTTP_401_UNAUTHORIZED,
    "TOKEN_INVALID": status.HTTP_401_UNAUTHORIZED,
    
    # Resource errors
    "RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "RESOURCE_EXHAUSTED": status.HTTP_429_TOO_MANY_REQUESTS,
    "QUOTA_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
    
    # General errors
    "INVALID_REQUEST": status.HTTP_400_BAD_REQUEST,
    "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    "NOT_IMPLEMENTED": status.HTTP_501_NOT_IMPLEMENTED,
    "SERVICE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "EXTENSION_NOT_AVAILABLE": status.HTTP_501_NOT_IMPLEMENTED,
    "REQUEST_TIMEOUT": status.HTTP_408_REQUEST_TIMEOUT,
    
    # Default
    "UNKNOWN_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR
}

def get_error_status_code(error_code: str) -> int:
    """
    Get the HTTP status code for a given error code.
    
    Args:
        error_code: The error code to look up
        
    Returns:
        HTTP status code
    """
    return ERROR_CODES.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

def raise_http_exception(
    code: str,
    message_override: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    endpoint: Optional[str] = None,
    doc_category: Optional[str] = None,
    log_level: str = "error"
) -> None:
    """
    Raise a standardized HTTPException with the given error details.
    
    Args:
        code: The error code (must be one of the defined ERROR_CODES)
        message_override: Optional override for the default error message
        details: Optional dictionary with additional error details
        endpoint: Optional endpoint where the error occurred
        doc_category: Optional documentation category for the error
        log_level: Log level to use when logging this error
        
    Raises:
        HTTPException: The formatted HTTP exception
    """
    # Get the HTTP status code for the error
    status_code = get_error_status_code(code)
    
    # Default message based on error code
    default_message = code.replace("_", " ").title()
    message = message_override or default_message
    
    # Prepare error payload
    error_payload = {
        "code": code,
        "message": message,
    }
    
    # Add optional details
    if details:
        error_payload["details"] = details
    
    if endpoint:
        error_payload["endpoint"] = endpoint
        
    if doc_category:
        error_payload["doc_category"] = doc_category
    
    # Log the error
    log_message = f"Error {code}: {message}"
    if endpoint:
        log_message += f" (endpoint: {endpoint})"
    
    # Select the appropriate log method based on log_level
    log_method = getattr(logger, log_level.lower(), logger.error)
    log_method(log_message)
    
    if details:
        logger.debug(f"Error details: {details}")
    
    # Raise the HTTP exception
    raise HTTPException(
        status_code=status_code,
        detail=error_payload
    )

def format_error_response(
    code: str,
    message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    endpoint: Optional[str] = None,
    success: bool = False
) -> Dict[str, Any]:
    """
    Format a standardized error response without raising an exception.
    
    Args:
        code: The error code
        message: Optional error message
        details: Optional dictionary with additional error details
        endpoint: Optional endpoint where the error occurred
        success: Whether the operation should be marked as successful
        
    Returns:
        Formatted error response dictionary
    """
    # Default message based on error code
    default_message = code.replace("_", " ").title()
    
    # Prepare error response
    response = {
        "success": success,
        "error": {
            "code": code,
            "message": message or default_message
        }
    }
    
    # Add optional details
    if details:
        response["error"]["details"] = details
    
    if endpoint:
        response["error"]["endpoint"] = endpoint
        
    return response