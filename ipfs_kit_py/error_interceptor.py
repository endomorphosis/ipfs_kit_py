"""
Error Interceptor for Python Runtime.

This module provides functionality to intercept and report unhandled exceptions
and errors that occur during runtime, automatically creating GitHub issues for them.
"""

import sys
import logging
import threading
from typing import Optional, Callable, Any
from .error_reporter import get_error_reporter, initialize_error_reporter

logger = logging.getLogger(__name__)


class ErrorInterceptor:
    """
    Interceptor for Python runtime errors.
    
    This class hooks into Python's exception handling system to automatically
    report unhandled exceptions as GitHub issues.
    """
    
    def __init__(self, enabled: bool = True, context: str = "Python Runtime"):
        """
        Initialize the error interceptor.
        
        Args:
            enabled: Whether to enable error interception
            context: Context string to include in error reports
        """
        self.enabled = enabled
        self.context = context
        self.original_excepthook = sys.excepthook
        self.installed = False
    
    def install(self) -> None:
        """Install the error interceptor."""
        if self.installed:
            logger.warning("Error interceptor is already installed")
            return
        
        if not self.enabled:
            logger.info("Error interceptor is disabled")
            return
        
        # Replace the default exception hook
        sys.excepthook = self._exception_hook
        
        # Install threading exception hook for Python 3.8+
        if hasattr(threading, 'excepthook'):
            threading.excepthook = self._threading_exception_hook
        
        self.installed = True
        logger.info("Error interceptor installed successfully")
    
    def uninstall(self) -> None:
        """Uninstall the error interceptor."""
        if not self.installed:
            return
        
        # Restore original exception hook
        sys.excepthook = self.original_excepthook
        
        self.installed = False
        logger.info("Error interceptor uninstalled")
    
    def _exception_hook(self, exc_type, exc_value, exc_traceback):
        """
        Custom exception hook for unhandled exceptions.
        
        Args:
            exc_type: Exception type
            exc_value: Exception value
            exc_traceback: Exception traceback
        """
        # Call the original exception hook first
        self.original_excepthook(exc_type, exc_value, exc_traceback)
        
        # Don't report KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            return
        
        # Report the error
        try:
            reporter = get_error_reporter()
            if reporter:
                logger.info(f"Reporting unhandled exception: {exc_type.__name__}")
                reporter.report_error(
                    exc_value,
                    context=self.context,
                    additional_info={
                        "exception_type": exc_type.__name__,
                        "is_unhandled": True,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to report error: {e}")
    
    def _threading_exception_hook(self, args):
        """
        Custom exception hook for unhandled exceptions in threads.
        
        Args:
            args: Threading exception arguments
        """
        exc_type = args.exc_type
        exc_value = args.exc_value
        exc_traceback = args.exc_traceback
        thread = args.thread
        
        # Log the exception
        logger.error(
            f"Unhandled exception in thread {thread.name}",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Don't report KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            return
        
        # Report the error
        try:
            reporter = get_error_reporter()
            if reporter:
                logger.info(f"Reporting unhandled thread exception: {exc_type.__name__}")
                reporter.report_error(
                    exc_value,
                    context=f"{self.context} (Thread: {thread.name})",
                    additional_info={
                        "exception_type": exc_type.__name__,
                        "is_unhandled": True,
                        "thread_name": thread.name,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to report thread error: {e}")


# Global error interceptor instance
_global_interceptor: Optional[ErrorInterceptor] = None


def install_error_interceptor(
    enabled: bool = True,
    context: str = "Python Runtime",
    github_token: Optional[str] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
) -> ErrorInterceptor:
    """
    Install the global error interceptor.
    
    This function both initializes the error reporter and installs the
    error interceptor to catch unhandled exceptions.
    
    Args:
        enabled: Whether to enable error interception
        context: Context string to include in error reports
        github_token: GitHub personal access token
        repo_owner: Repository owner
        repo_name: Repository name
        
    Returns:
        The installed error interceptor instance
    """
    global _global_interceptor
    
    # Initialize error reporter if not already initialized
    reporter = get_error_reporter()
    if reporter is None:
        initialize_error_reporter(
            github_token=github_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
            enabled=enabled,
        )
    
    # Create and install interceptor
    _global_interceptor = ErrorInterceptor(enabled=enabled, context=context)
    _global_interceptor.install()
    
    return _global_interceptor


def get_error_interceptor() -> Optional[ErrorInterceptor]:
    """
    Get the global error interceptor instance.
    
    Returns:
        The global error interceptor instance, or None if not installed
    """
    return _global_interceptor


def uninstall_error_interceptor() -> None:
    """Uninstall the global error interceptor."""
    global _global_interceptor
    if _global_interceptor:
        _global_interceptor.uninstall()
        _global_interceptor = None
