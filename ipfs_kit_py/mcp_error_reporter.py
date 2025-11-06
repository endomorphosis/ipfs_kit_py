"""
MCP Error Handler with GitHub Issue Reporting.

This module extends the MCP error handling system to automatically report
errors as GitHub issues when they occur in the MCP server.
"""

import logging
from typing import Optional, Dict, Any
from .error_reporter import get_error_reporter

logger = logging.getLogger(__name__)

# Severity levels for automatic reporting
REPORTABLE_SEVERITY_LEVELS = ['error', 'critical']


def report_mcp_error(
    error_code: str,
    error_message: str,
    error_category: str = "unknown",
    error_severity: str = "error",
    traceback: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = None,
) -> Optional[str]:
    """
    Report an MCP error as a GitHub issue.
    
    Args:
        error_code: MCP error code
        error_message: Error message
        error_category: Error category
        error_severity: Error severity level
        traceback: Error traceback (if available)
        details: Additional error details
        suggestion: Suggested resolution
        
    Returns:
        URL of the created issue, or None if no issue was created
    """
    reporter = get_error_reporter()
    if not reporter:
        return None
    
    # Only report errors with reportable severity levels
    if error_severity not in REPORTABLE_SEVERITY_LEVELS:
        logger.debug(f"Skipping error report for severity: {error_severity}")
        return None
    
    # Create error info dictionary
    error_info = {
        "error_type": error_code,
        "error_message": error_message,
        "traceback": traceback or "",
        "environment": {
            "component": "MCP Server",
            "category": error_category,
            "severity": error_severity,
        },
        "details": details or {},
    }
    
    if suggestion:
        error_info["details"]["suggestion"] = suggestion
    
    # Report the error
    return reporter.report_error_dict(
        error_info=error_info,
        context="MCP Server"
    )


class MCPErrorReporter:
    """
    Error reporter that integrates with the MCP error handling system.
    
    This class can be used as a decorator or context manager to automatically
    report MCP errors as GitHub issues.
    """
    
    def __init__(
        self,
        context: str = "MCP Server",
        auto_report: bool = True,
        min_severity: str = "error",
    ):
        """
        Initialize the MCP error reporter.
        
        Args:
            context: Context string for error reports
            auto_report: Whether to automatically report errors
            min_severity: Minimum severity level to report
        """
        self.context = context
        self.auto_report = auto_report
        self.min_severity = min_severity
    
    def __call__(self, func):
        """
        Decorator to wrap a function with error reporting.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function
        """
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if self.auto_report:
                    self._report_exception(e, func.__name__)
                raise
        
        return wrapper
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Context manager exit with error reporting."""
        if exc_type is not None and self.auto_report:
            self._report_exception(exc_value, self.context)
        return False  # Don't suppress the exception
    
    def _report_exception(self, error: Exception, function_name: str) -> None:
        """
        Report an exception as a GitHub issue.
        
        Args:
            error: The exception to report
            function_name: Name of the function where error occurred
        """
        try:
            reporter = get_error_reporter()
            if reporter:
                logger.info(f"Reporting MCP error from {function_name}")
                reporter.report_error(
                    error,
                    context=f"{self.context} ({function_name})",
                    additional_info={
                        "function": function_name,
                        "component": "MCP Server",
                    }
                )
        except Exception as e:
            logger.error(f"Failed to report MCP error: {e}")


def install_mcp_error_handler():
    """
    Install MCP error handler hooks.
    
    This function patches the MCP error handling to automatically report
    errors as GitHub issues.
    """
    try:
        # Import MCP error handling module
        from ipfs_kit_py.mcp import mcp_error_handling
        
        # Store original MCPError init
        original_init = mcp_error_handling.MCPError.__init__
        
        def patched_init(self, *args, **kwargs):
            # Call original init
            original_init(self, *args, **kwargs)
            
            # Report error if severity is high enough
            if hasattr(self, 'severity') and self.severity.value in REPORTABLE_SEVERITY_LEVELS:
                try:
                    report_mcp_error(
                        error_code=getattr(self, 'error_code', 'UNKNOWN'),
                        error_message=getattr(self, 'message', str(self)),
                        error_category=getattr(self, 'category', 'unknown').value if hasattr(getattr(self, 'category', None), 'value') else 'unknown',
                        error_severity=self.severity.value,
                        details=getattr(self, 'details', None),
                        suggestion=getattr(self, 'suggestion', None),
                    )
                except Exception as e:
                    logger.error(f"Failed to auto-report MCP error: {e}")
        
        # Patch the MCPError class
        mcp_error_handling.MCPError.__init__ = patched_init
        
        logger.info("MCP error handler installed successfully")
        
    except ImportError as e:
        logger.warning(f"Could not install MCP error handler: {e}")
    except Exception as e:
        logger.error(f"Error installing MCP error handler: {e}")
