"""
OAuth Integration Module for MCP Server

This module initializes and connects the OAuth components with the main
authentication system and FastAPI application.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import os
from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware

from ipfs_kit_py.mcp.auth.oauth_manager import get_oauth_manager
from ipfs_kit_py.mcp.auth.oauth_persistence import extend_persistence_manager
from ipfs_kit_py.mcp.auth.oauth_router import router as oauth_router
from .security_enhancements import (
    TokenBlacklist, 
    SecureTokenProcessor,
    OAuthSecurityConfig
)

logger = logging.getLogger(__name__)

# Initialize global security components
token_blacklist = TokenBlacklist()
oauth_security_config = OAuthSecurityConfig()

# Get or generate secret key
SECRET_KEY = os.environ.get("MCP_OAUTH_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < oauth_security_config.minimum_key_length:
    logger.warning("OAuth secret key not found or too short, generating a secure random key")
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("Generated temporary OAuth secret key. This will be lost on restart. Set MCP_OAUTH_SECRET_KEY env var for persistence.")

# Initialize secure token processor
secure_token_processor = SecureTokenProcessor(SECRET_KEY, issuer="mcp-oauth")

# OAuth2 password bearer for FastAPI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def initialize_oauth_system():
    """
    Initialize the OAuth system components.
    
    This function:
    1. Extends the persistence manager with OAuth methods
    2. Initializes the OAuth manager
    3. Sets up token security enhancements
    """
    logger.info("Initializing OAuth system components")
    
    # Extend the persistence manager with OAuth methods
    extend_persistence_manager()
    
    # Initialize the OAuth manager
    oauth_manager = get_oauth_manager()
    
    # Register the token blacklist with the OAuth manager
    oauth_manager.register_token_blacklist(token_blacklist)
    
    # Register the secure token processor with the OAuth manager
    oauth_manager.register_token_processor(secure_token_processor)
    
    logger.info("OAuth system components initialized with enhanced security")


def register_oauth_routes(app: FastAPI):
    """
    Register OAuth API routes with a FastAPI application.
    
    Args:
        app: FastAPI application
    """
    logger.info("Registering OAuth API routes")
    
    # Include the OAuth router
    app.include_router(oauth_router)
    
    # Add secure CORS policy for OAuth endpoints
    if oauth_security_config.enforce_https:
        logger.info("Enforcing HTTPS for OAuth endpoints")
        origins = [
            origin for origin in oauth_security_config.allowed_callback_domains
            if origin.startswith("https://")
        ]
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["X-CSRF-Token"],
            max_age=600,
        )
    
    logger.info("OAuth API routes registered with security enhancements")


def setup_oauth(app: FastAPI):
    """
    Set up the complete OAuth system.
    
    This function:
    1. Initializes the OAuth system components
    2. Registers OAuth API routes
    
    Args:
        app: FastAPI application
    """
    logger.info("Setting up OAuth system")
    
    # Initialize the OAuth system
    initialize_oauth_system()
    
    # Register OAuth routes
    register_oauth_routes(app)
    
    logger.info("OAuth system setup complete")