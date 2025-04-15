"""
Authentication & Authorization Integration Module

This module provides a centralized integration point for all advanced authentication
and authorization components described in the MCP roadmap.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
from fastapi import FastAPI

from ipfs_kit_py.mcp.auth.oauth_integration import setup_oauth
from ipfs_kit_py.mcp.auth.oauth_integration_service import patch_authentication_service
from ipfs_kit_py.mcp.auth.audit_extensions import extend_audit_logger
from ipfs_kit_py.mcp.auth.audit import get_instance as get_audit_logger
from ipfs_kit_py.mcp.auth.apikey_router import router as apikey_router
from ipfs_kit_py.mcp.auth.rbac_router import router as rbac_router
from ipfs_kit_py.mcp.auth.router import router as auth_router

# Configure logging
logger = logging.getLogger(__name__)


async def initialize_auth_system():
    """
    Initialize all authentication and authorization components.
    
    This function:
    1. Initializes the audit logger
    2. Extends the audit logger with additional methods
    3. Patches the authentication service with OAuth integration
    """
    logger.info("Initializing advanced authentication system")
    
    # Initialize and extend the audit logger
    audit_logger = get_audit_logger()
    extend_audit_logger()
    await audit_logger.start()
    
    # Patch the authentication service with OAuth integration
    patch_authentication_service()
    
    logger.info("Advanced authentication system initialized")


def setup_auth_routes(app: FastAPI):
    """
    Set up all authentication and authorization routes.
    
    Args:
        app: FastAPI application
    """
    logger.info("Setting up authentication and authorization routes")
    
    # Include core authentication router
    app.include_router(auth_router)
    
    # Include API key management router
    app.include_router(apikey_router)
    
    # Include RBAC router
    app.include_router(rbac_router)
    
    logger.info("Authentication and authorization routes set up")


async def setup_advanced_auth(app: FastAPI):
    """
    Set up the complete advanced authentication and authorization system.
    
    This function:
    1. Initializes all components
    2. Sets up OAuth system
    3. Registers all routes
    
    Args:
        app: FastAPI application
    """
    logger.info("Setting up advanced authentication and authorization system")
    
    # Initialize auth system
    await initialize_auth_system()
    
    # Set up OAuth system
    setup_oauth(app)
    
    # Set up auth routes
    setup_auth_routes(app)
    
    logger.info("Advanced authentication and authorization system set up")


def create_auth_integration(app: FastAPI):
    """
    Create and return an integration function for the MCP server.
    
    This function creates an integration function that can be called
    during MCP server startup to set up all authentication and
    authorization components.
    
    Args:
        app: FastAPI application
        
    Returns:
        Async function to call during server startup
    """
    async def _integrate():
        # Set up advanced auth system
        await setup_advanced_auth(app)
        
        logger.info("Advanced authentication and authorization integrated with MCP server")
    
    return _integrate