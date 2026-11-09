"""
Standard error handling for MCP controllers.

This module provides standardized error handling for MCP controllers.
"""

import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Standard error codes
ERROR_CODES = {
    "INTERNAL_ERROR": {"status_code": 500, "detail": "Internal server error"},
    "MISSING_PARAMETER": {"status_code": 400, "detail": "Missing required parameter"},
    "INVALID_REQUEST": {"status_code": 400, "detail": "Invalid request"},
    "CONTENT_NOT_FOUND": {"status_code": 404, "detail": "Content not found"},
    "UNAUTHORIZED": {"status_code": 401, "detail": "Unauthorized access"},
    "FORBIDDEN": {"status_code": 403, "detail": "Forbidden"},
    "NOT_FOUND": {"status_code": 404, "detail": "Resource not found"},
    "METHOD_NOT_ALLOWED": {"status_code": 405, "detail": "Method not allowed"},
    "CONFLICT": {"status_code": 409, "detail": "Conflict"},
    "UNPROCESSABLE_ENTITY": {"status_code": 422, "detail": "Unprocessable entity"}
}

def raise_http_exception(code, message_override=None, endpoint=None, doc_category=None):
    """
    Raise a standardized HTTP exception.
    
    Args:
        code: Standard error code (see ERROR_CODES)
        message_override: Optional custom message
        endpoint: The endpoint where the error occurred
        doc_category: Documentation category
        
    Raises:
        HTTPException: Standardized HTTP exception
    """
    if code not in ERROR_CODES:
        logger.warning(f"Unknown error code: {code}, using INTERNAL_ERROR")
        code = "INTERNAL_ERROR"
        
    error_info = ERROR_CODES[code]
    status_code = error_info["status_code"]
    detail = message_override if message_override else error_info["detail"]
    
    # Add endpoint and category if provided
    error_detail = {
        "code": code,
        "message": detail
    }
    
    if endpoint:
        error_detail["endpoint"] = endpoint
    
    if doc_category:
        error_detail["category"] = doc_category
    
    logger.error(f"HTTP Exception: {code} - {detail}")
    
    raise HTTPException(
        status_code=status_code,
        detail=error_detail
    )
