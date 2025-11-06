"""
API Endpoint for Error Reporting.

This module provides a FastAPI endpoint to receive error reports from
JavaScript and other sources, and create GitHub issues for them.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from .error_reporter import get_error_reporter

logger = logging.getLogger(__name__)

# Create router for error reporting endpoints
error_reporting_router = APIRouter(prefix="/api", tags=["error-reporting"])


class ErrorReportRequest(BaseModel):
    """Request model for error reporting."""
    
    error_info: Dict[str, Any] = Field(
        ...,
        description="Dictionary containing error information"
    )
    context: Optional[str] = Field(
        None,
        description="Optional context about where the error occurred"
    )


class ErrorReportResponse(BaseModel):
    """Response model for error reporting."""
    
    success: bool = Field(..., description="Whether the error was reported successfully")
    issue_url: Optional[str] = Field(None, description="URL of the created GitHub issue")
    message: str = Field(..., description="Response message")


@error_reporting_router.post(
    "/report-error",
    response_model=ErrorReportResponse,
    summary="Report an error",
    description="Report an error to automatically create a GitHub issue"
)
async def report_error_endpoint(
    request: ErrorReportRequest = Body(...),
) -> ErrorReportResponse:
    """
    Report an error by creating a GitHub issue.
    
    This endpoint accepts error information from various sources (JavaScript,
    Python, etc.) and creates a GitHub issue for the error.
    
    Args:
        request: Error report request
        
    Returns:
        Error report response
        
    Raises:
        HTTPException: If error reporting fails
    """
    try:
        # Get error reporter
        reporter = get_error_reporter()
        if not reporter:
            logger.warning("Error reporter not initialized")
            return ErrorReportResponse(
                success=False,
                message="Error reporting is not configured"
            )
        
        if not reporter.enabled:
            logger.info("Error reporting is disabled")
            return ErrorReportResponse(
                success=False,
                message="Error reporting is disabled"
            )
        
        # Report the error
        issue_url = reporter.report_error_dict(
            error_info=request.error_info,
            context=request.context
        )
        
        if issue_url:
            return ErrorReportResponse(
                success=True,
                issue_url=issue_url,
                message="Error reported successfully"
            )
        else:
            return ErrorReportResponse(
                success=False,
                message="Error not reported (may be duplicate or rate limited)"
            )
    
    except Exception as e:
        logger.error(f"Failed to report error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to report error: {str(e)}"
        )


@error_reporting_router.get(
    "/error-reporting/status",
    summary="Get error reporting status",
    description="Get the status of the error reporting system"
)
async def get_error_reporting_status() -> Dict[str, Any]:
    """
    Get the status of the error reporting system.
    
    Returns:
        Status information
    """
    reporter = get_error_reporter()
    
    if not reporter:
        return {
            "enabled": False,
            "configured": False,
            "message": "Error reporter not initialized"
        }
    
    return {
        "enabled": reporter.enabled,
        "configured": True,
        "repo_owner": reporter.repo_owner,
        "repo_name": reporter.repo_name,
        "max_reports_per_hour": reporter.max_reports_per_hour,
        "message": "Error reporting is active" if reporter.enabled else "Error reporting is disabled"
    }


def register_error_reporting_routes(app):
    """
    Register error reporting routes with a FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    app.include_router(error_reporting_router)
    logger.info("Error reporting routes registered")
