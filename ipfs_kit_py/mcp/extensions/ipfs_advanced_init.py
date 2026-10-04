"""
Advanced IPFS Operations Integration for MCP Server.

This module initializes and integrates the enhanced IPFS operations
with the MCP server, providing connection pooling, DHT operations,
IPNS key management, and DAG operations.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI

# Import our advanced IPFS modules
from ipfs_kit_py.mcp.extensions.advanced_ipfs_operations import get_instance as get_advanced_ipfs
from ipfs_kit_py.mcp.extensions.advanced_ipfs_router import create_router

# Set up logging
logger = logging.getLogger("ipfs_advanced_init")

def init_advanced_ipfs(app: FastAPI, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize and integrate advanced IPFS operations with the MCP server.
    
    Args:
        app: FastAPI application instance
        config: Configuration options
        
    Returns:
        Dictionary with initialization results
    """
    logger.info("Initializing Advanced IPFS Operations")
    
    try:
        # Initialize the advanced IPFS operations
        advanced_ipfs = get_advanced_ipfs(config)
        
        # Create and include the router
        router = create_router(config)
        app.include_router(router)
        
        # Store the advanced IPFS instance in the app state for access from other components
        app.state.advanced_ipfs = advanced_ipfs
        
        logger.info("Advanced IPFS Operations initialized and integrated with MCP server")
        return {
            "success": True,
            "message": "Advanced IPFS Operations initialized successfully",
        }
    except Exception as e:
        logger.error(f"Error initializing Advanced IPFS Operations: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }

def shutdown_advanced_ipfs(app: FastAPI) -> Dict[str, Any]:
    """
    Shutdown advanced IPFS operations.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Dictionary with shutdown results
    """
    logger.info("Shutting down Advanced IPFS Operations")
    
    try:
        # Get the advanced IPFS instance from app state
        if hasattr(app.state, "advanced_ipfs"):
            advanced_ipfs = app.state.advanced_ipfs
            advanced_ipfs.shutdown()
            
        logger.info("Advanced IPFS Operations shut down successfully")
        return {
            "success": True,
            "message": "Advanced IPFS Operations shut down successfully",
        }
    except Exception as e:
        logger.error(f"Error shutting down Advanced IPFS Operations: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }