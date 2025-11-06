"""
Initialize error reporting for IPFS Kit.

This module should be imported at application startup to automatically
configure error reporting for Python runtime, MCP server, and API endpoints.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def setup_error_reporting(
    github_token: Optional[str] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    enabled: Optional[bool] = None,
    context: str = "IPFS Kit",
    install_interceptor: bool = True,
    install_mcp_handler: bool = True,
) -> bool:
    """
    Set up error reporting for the application.
    
    This function initializes the error reporter, installs the error interceptor
    for unhandled exceptions, and optionally installs the MCP error handler.
    
    Args:
        github_token: GitHub personal access token (or use GITHUB_TOKEN env var)
        repo_owner: Repository owner (or use GITHUB_REPO_OWNER env var)
        repo_name: Repository name (or use GITHUB_REPO_NAME env var)
        enabled: Whether to enable error reporting (or use ERROR_REPORTING_ENABLED env var)
        context: Context string for error reports
        install_interceptor: Whether to install the error interceptor
        install_mcp_handler: Whether to install the MCP error handler
        
    Returns:
        True if error reporting was successfully configured, False otherwise
    """
    try:
        # Get configuration from environment if not provided
        if github_token is None:
            github_token = os.environ.get("GITHUB_TOKEN")
        
        if repo_owner is None:
            repo_owner = os.environ.get("GITHUB_REPO_OWNER", "endomorphosis")
        
        if repo_name is None:
            repo_name = os.environ.get("GITHUB_REPO_NAME", "ipfs_kit_py")
        
        if enabled is None:
            enabled_env = os.environ.get("ERROR_REPORTING_ENABLED", "true")
            enabled = enabled_env.lower() in ("true", "1", "yes", "on")
        
        # Import error reporting modules
        from ipfs_kit_py.error_reporter import initialize_error_reporter
        from ipfs_kit_py.error_interceptor import install_error_interceptor
        
        # Initialize error reporter
        reporter = initialize_error_reporter(
            github_token=github_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
            enabled=enabled,
            max_reports_per_hour=int(os.environ.get("MAX_ERROR_REPORTS_PER_HOUR", "10")),
        )
        
        if not reporter.enabled:
            logger.info(
                "Error reporting is disabled. "
                "Set GITHUB_TOKEN environment variable to enable."
            )
            return False
        
        logger.info(
            f"Error reporting initialized for {repo_owner}/{repo_name}"
        )
        
        # Install error interceptor if requested
        if install_interceptor:
            install_error_interceptor(
                enabled=True,
                context=context,
            )
            logger.info("Error interceptor installed")
        
        # Install MCP error handler if requested
        if install_mcp_handler:
            try:
                from ipfs_kit_py.mcp_error_reporter import install_mcp_error_handler
                install_mcp_error_handler()
                logger.info("MCP error handler installed")
            except ImportError:
                logger.warning("MCP error handler not available")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to set up error reporting: {e}", exc_info=True)
        return False


def register_error_reporting_api(app):
    """
    Register error reporting API endpoints with a FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    try:
        from ipfs_kit_py.error_reporting_api import register_error_reporting_routes
        register_error_reporting_routes(app)
        logger.info("Error reporting API routes registered")
    except Exception as e:
        logger.error(f"Failed to register error reporting routes: {e}")


# Automatic initialization on import (can be disabled by setting env var)
if os.environ.get("AUTO_INIT_ERROR_REPORTING", "true").lower() in ("true", "1", "yes"):
    # Only auto-initialize if we're not in a test environment
    if "pytest" not in os.environ.get("_", ""):
        setup_error_reporting()
