"""
MCP Server Integration Patch for Advanced Authentication

This patch updates the MCP server to fully integrate the advanced authentication
and authorization components, including OAuth, API key management, and enhanced audit logging.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import logging
from fastapi import FastAPI

from ipfs_kit_py.mcp.auth.integration_advanced import create_auth_integration
from ipfs_kit_py.mcp.auth.audit_extensions import get_audit_logger
from ipfs_kit_py.mcp.auth.oauth_integration_service import patch_authentication_service

# Configure logging
logger = logging.getLogger(__name__)


def patch_mcp_server(app: FastAPI):
    """
    Patch the MCP server with advanced authentication and authorization components.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Applying MCP server patch for advanced authentication...")
    
    # Create auth integration function
    auth_integration = create_auth_integration(app)
    
    # Register startup event to initialize advanced auth components
    @app.on_event("startup")
    async def startup_auth_components():
        logger.info("Initializing advanced authentication components...")
        
        # Initialize the auth integration
        await auth_integration()
        
        # Initialize audit logger
        audit_logger = get_audit_logger()
        await audit_logger.start()
        
        logger.info("Advanced authentication components initialized successfully")
    
    # Register shutdown event for audit logger
    @app.on_event("shutdown")
    async def shutdown_auth_components():
        logger.info("Shutting down advanced authentication components...")
        
        # Stop audit logger
        audit_logger = get_audit_logger()
        await audit_logger.stop()
        
        logger.info("Advanced authentication components shut down successfully")
    
    # Patch authentication service with OAuth integration
    patch_authentication_service()
    
    logger.info("MCP server patched with advanced authentication and authorization")


# Function to check if configuration is present
def check_auth_configuration():
    """
    Check if advanced authentication configuration is present.
    
    Returns:
        bool: True if configuration is present
    """
    # Check for OAuth provider configuration
    has_provider_config = any([
        os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"),
        os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"),
        os.environ.get("MICROSOFT_CLIENT_ID") and os.environ.get("MICROSOFT_CLIENT_SECRET"),
    ])
    
    # Check for JWT secret key
    has_jwt_secret = bool(os.environ.get("MCP_JWT_SECRET"))
    
    # If missing configuration, log warnings
    if not has_provider_config:
        logger.warning("No OAuth provider configuration found. OAuth login will be disabled.")
    
    if not has_jwt_secret:
        logger.warning("No JWT secret key found. A random secret will be generated.")
    
    return has_provider_config or has_jwt_secret