"""
Standardized error handling for MCP storage backends.

This module provides consistent error handling across all storage backends
to improve troubleshooting and user experience.
"""

import logging
import time
import sys
import traceback
from typing import Dict, Any, Optional, Type, List, Union, Callable
from functools import wraps

# Configure logger
logger = logging.getLogger(__name__)

# Define error categories for better organization
ERROR_CATEGORIES = {
    "CONNECTION": {
        "description": "Errors related to connecting to storage services",
        "common_causes": [
            "Network connectivity issues",
            "Service endpoint unavailable",
            "Incorrect endpoint configuration",
            "Firewall or proxy blocking connections"
        ],
        "troubleshooting": [
            "Check your network connection",
            "Verify the service endpoint is correct and accessible",
            "Check for any network issues between your machine and the service",
            "Verify firewall settings allow connection to the service"
        ]
    },
    "AUTHENTICATION": {
        "description": "Errors related to authentication with storage services",
        "common_causes": [
            "Invalid API keys or credentials",
            "Expired credentials",
            "Missing required permissions",
            "Account restrictions"
        ],
        "troubleshooting": [
            "Verify your API keys and credentials are correct",
            "Check if credentials have expired and need to be renewed",
            "Ensure your account has the necessary permissions",
            "Contact service provider if account restrictions may be in place"
        ]
    },
    "CONTENT": {
        "description": "Errors related to content operations",
        "common_causes": [
            "Invalid content ID",
            "Content not found",
            "Content format issues",
            "Content size limitations"
        ],
        "troubleshooting": [
            "Verify the content ID is correct",
            "Check if the content exists in the specified location",
            "Ensure content meets format requirements",
            "Check if content size is within service limits"
        ]
    },
    "RATE_LIMIT": {
        "description": "Errors related to rate limiting",
        "common_causes": [
            "Too many requests in a short time period",
            "Account-specific rate limits",
            "Service-wide throttling"
        ],
        "troubleshooting": [
            "Implement exponential backoff strategy",
            "Reduce frequency of requests",
            "Check service documentation for rate limit information",
            "Consider upgrading service tier if available"
        ]
    },
    "CONFIGURATION": {
        "description": "Errors related to service configuration",
        "common_causes": [
            "Missing required configuration parameters",
            "Incompatible configuration settings",
            "Services not properly initialized"
        ],
        "troubleshooting": [
            "Check your configuration against service requirements",
            "Verify all required parameters are provided",
            "Ensure services are initialized in the correct order"
        ]
    },
    "RESOURCES": {
        "description": "Errors related to resource limitations",
        "common_causes": [
            "Out of storage space",
            "Memory limitations",
            "CPU limitations",
            "Bandwidth limitations"
        ],
        "troubleshooting": [
            "Check available resources",
            "Free up space if necessary",
            "Consider upgrading resource limits",
            "Optimize operations to use fewer resources"
        ]
    },
    "COMPATIBILITY": {
        "description": "Errors related to compatibility issues",
        "common_causes": [
            "API version mismatches",
            "Unsupported features",
            "Deprecated functionality"
        ],
        "troubleshooting": [
            "Check service documentation for compatibility information",
            "Update client libraries to latest compatible versions",
            "Avoid using deprecated features",
            "Consider feature detection instead of version checking"
        ]
    },
    "INTERNAL": {
        "description": "Internal errors within the MCP server",
        "common_causes": [
            "Software bugs",
            "Unexpected edge cases",
            "Resource contention issues"
        ],
        "troubleshooting": [
            "Check server logs for detailed error information",
            "Report the issue with steps to reproduce",
            "Try restarting the service"
        ]
    }
}

# Mapping of common error patterns to categories
ERROR_PATTERN_MAPPING = {
    # Connection errors
    "connection refused": "CONNECTION",
    "connect timeout": "CONNECTION",
    "connection error": "CONNECTION",
    "network unreachable": "CONNECTION",
    "dns resolution": "CONNECTION",
    "could not connect": "CONNECTION",
    "no such host": "CONNECTION",
    
    # Authentication errors
    "unauthorized": "AUTHENTICATION",
    "forbidden": "AUTHENTICATION",
    "access denied": "AUTHENTICATION",
    "invalid api key": "AUTHENTICATION",
    "invalid token": "AUTHENTICATION",
    "authentication failed": "AUTHENTICATION",
    "permission denied": "AUTHENTICATION",
    
    # Content errors
    "not found": "CONTENT",
    "invalid cid": "CONTENT",
    "content size exceeds": "CONTENT",
    "invalid content": "CONTENT",
    "hash mismatch": "CONTENT",
    "invalid format": "CONTENT",
    
    # Rate limit errors
    "rate limit": "RATE_LIMIT",
    "too many requests": "RATE_LIMIT",
    "throttled": "RATE_LIMIT",
    "quota exceeded": "RATE_LIMIT",
    
    # Configuration errors
    "missing configuration": "CONFIGURATION",
    "invalid configuration": "CONFIGURATION",
    "not initialized": "CONFIGURATION",
    "configuration error": "CONFIGURATION",
    
    # Resource errors
    "out of space": "RESOURCES",
    "insufficient storage": "RESOURCES",
    "memory error": "RESOURCES",
    "disk full": "RESOURCES",
    "bandwidth exceeded": "RESOURCES",
    
    # Compatibility errors
    "unsupported version": "COMPATIBILITY",
    "api version": "COMPATIBILITY",
    "deprecated": "COMPATIBILITY",
    "not supported": "COMPATIBILITY"
}

def get_error_category(error_msg: str) -> str:
    """
    Determine the error category based on error message patterns.
    
    Args:
        error_msg: Error message to categorize
        
    Returns:
        Error category
    """
    if not error_msg:
        return "INTERNAL"
        
    error_lower = error_msg.lower()
    
    for pattern, category in ERROR_PATTERN_MAPPING.items():
        if pattern in error_lower:
            return category
            
    return "INTERNAL"

def get_context_from_exception(
    exception: Exception, 
    operation: Optional[str] = None, 
    backend_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract context information from an exception.
    
    Args:
        exception: Exception to analyze
        operation: Operation being performed when exception occurred
        backend_name: Name of the backend where exception occurred
        
    Returns:
        Dict with context information
    """
    context = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "timestamp": time.time()
    }
    
    if operation:
        context["operation"] = operation
        
    if backend_name:
        context["backend"] = backend_name
        
    # Extract status code if available
    if hasattr(exception, "response") and hasattr(exception.response, "status_code"):
        context["status_code"] = exception.response.status_code
        
    # Extract response details if available
    if hasattr(exception, "response") and hasattr(exception.response, "text"):
        try:
            import json
            response_json = json.loads(exception.response.text)
            context["response_details"] = response_json
        except (json.JSONDecodeError, Exception):
            context["response_text"] = exception.response.text
            
    # Check for timeout
    if "timeout" in str(exception).lower():
        context["is_timeout"] = True
        
    # Get the error category
    context["error_category"] = get_error_category(str(exception))
    
    # Add category description and troubleshooting
    category_info = ERROR_CATEGORIES.get(context["error_category"], {})
    context["category_description"] = category_info.get("description", "")
    context["troubleshooting"] = category_info.get("troubleshooting", [])
        
    return context

def create_enhanced_error_response(
    context: Dict[str, Any],
    success: bool = False,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """
    Create an enhanced error response with troubleshooting information.
    
    Args:
        context: Error context information
        success: Whether the operation was technically successful
        include_traceback: Whether to include traceback in the response
        
    Returns:
        Enhanced error response dict
    """
    response = {
        "success": success,
        "error": str(context.get("exception_message", "Unknown error")),
        "error_type": context.get("exception_type", "Exception"),
        "error_category": context.get("error_category", "INTERNAL"),
        "category_description": context.get("category_description", ""),
        "timestamp": context.get("timestamp", time.time()),
    }
    
    # Add operation and backend if available
    if "operation" in context:
        response["operation"] = context["operation"]
        
    if "backend" in context:
        response["backend"] = context["backend"]
        
    # Add troubleshooting suggestions
    if "troubleshooting" in context and context["troubleshooting"]:
        response["troubleshooting_suggestions"] = context["troubleshooting"]
        
    # Add specific details based on error category
    if context.get("error_category") == "CONNECTION":
        response["connection_details"] = {
            "check_endpoint": True,
            "check_network": True,
            "check_firewall": True
        }
    elif context.get("error_category") == "AUTHENTICATION":
        response["authentication_details"] = {
            "check_credentials": True,
            "check_permissions": True
        }
    elif context.get("error_category") == "RATE_LIMIT":
        response["rate_limit_details"] = {
            "implement_backoff": True,
            "reduce_frequency": True
        }
        
    # Add status code if available
    if "status_code" in context:
        response["status_code"] = context["status_code"]
        
    # Add response details if available
    if "response_details" in context:
        response["response_details"] = context["response_details"]
    elif "response_text" in context:
        response["response_text"] = context["response_text"]
        
    # Add traceback if requested
    if include_traceback:
        response["traceback"] = traceback.format_exc()
        
    return response

def handle_backend_errors(
    operation: str,
    backend_name: str,
    log_level: str = "error",
    include_traceback: bool = False
):
    """
    Decorator for handling backend operation errors consistently.
    
    Args:
        operation: Name of the operation being performed
        backend_name: Name of the backend
        log_level: Logging level for errors
        include_traceback: Whether to include traceback in responses
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get logger instance
                logger_instance = logger
                
                # Get context from exception
                context = get_context_from_exception(e, operation, backend_name)
                
                # Log the error
                log_msg = f"Error in {backend_name} {operation}: {e}"
                if log_level == "error":
                    logger_instance.error(log_msg)
                    if include_traceback:
                        logger_instance.error(traceback.format_exc())
                elif log_level == "warning":
                    logger_instance.warning(log_msg)
                elif log_level == "info":
                    logger_instance.info(log_msg)
                else:
                    logger_instance.error(log_msg)
                
                # Create enhanced error response
                error_response = create_enhanced_error_response(
                    context, 
                    success=False,
                    include_traceback=include_traceback
                )
                
                return error_response
                
        return wrapper
    return decorator

def handle_backend_errors_async(
    operation: str,
    backend_name: str,
    log_level: str = "error",
    include_traceback: bool = False
):
    """
    Decorator for handling async backend operation errors consistently.
    
    Args:
        operation: Name of the operation being performed
        backend_name: Name of the backend
        log_level: Logging level for errors
        include_traceback: Whether to include traceback in responses
        
    Returns:
        Async decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Get logger instance
                logger_instance = logger
                
                # Get context from exception
                context = get_context_from_exception(e, operation, backend_name)
                
                # Log the error
                log_msg = f"Error in {backend_name} {operation}: {e}"
                if log_level == "error":
                    logger_instance.error(log_msg)
                    if include_traceback:
                        logger_instance.error(traceback.format_exc())
                elif log_level == "warning":
                    logger_instance.warning(log_msg)
                elif log_level == "info":
                    logger_instance.info(log_msg)
                else:
                    logger_instance.error(log_msg)
                
                # Create enhanced error response
                error_response = create_enhanced_error_response(
                    context, 
                    success=False,
                    include_traceback=include_traceback
                )
                
                return error_response
                
        return wrapper
    return decorator

def graceful_degradation(
    fallback_function: Callable,
    error_types: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for implementing graceful degradation when services are unavailable.
    
    Args:
        fallback_function: Function to call as fallback if main function fails
        error_types: List of exception types to catch (defaults to all exceptions)
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Check if we should handle this exception type
                if error_types and not any(isinstance(e, t) for t in error_types):
                    raise
                    
                # Log the error
                logger.warning(f"Function {func.__name__} failed, using fallback: {e}")
                
                # Call fallback function with original arguments and the exception
                return fallback_function(*args, exception=e, **kwargs)
                
        return wrapper
    return decorator

def graceful_degradation_async(
    fallback_function: Callable,
    error_types: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for implementing graceful degradation for async functions when services are unavailable.
    
    Args:
        fallback_function: Async function to call as fallback if main function fails
        error_types: List of exception types to catch (defaults to all exceptions)
        
    Returns:
        Async decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Check if we should handle this exception type
                if error_types and not any(isinstance(e, t) for t in error_types):
                    raise
                    
                # Log the error
                logger.warning(f"Async function {func.__name__} failed, using fallback: {e}")
                
                # Call fallback function with original arguments and the exception
                return await fallback_function(*args, exception=e, **kwargs)
                
        return wrapper
    return decorator