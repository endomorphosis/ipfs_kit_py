"""
MCP Server Initializer for run_mcp_server.

This module patches the run_mcp_server to initialize the IPFS model with extensions.
"""

import logging
import importlib
import sys
from types import ModuleType
from typing import Optional, Callable, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)

def patch_run_mcp_server():
    """
    Patch the run_mcp_server module to initialize IPFS model extensions.
    
    This function modifies the create_app function in run_mcp_server_real_storage 
    to ensure the IPFS model is properly initialized with all required extensions.
    
    Returns:
        bool: True if patching was successful, False otherwise
    """
    try:
        # Import the model initializer
        from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
        
        # Try to import the target module
        try:
            run_mcp_server_module = importlib.import_module("ipfs_kit_py.run_mcp_server_real_storage")
        except ImportError:
            try:
                run_mcp_server_module = importlib.import_module("ipfs_kit_py.mcp.run_mcp_server_real_storage")
            except ImportError:
                logger.error("Could not import run_mcp_server_real_storage module")
                return False
        
        # Get the original create_app function
        original_create_app = getattr(run_mcp_server_module, "create_app", None)
        
        if not original_create_app or not callable(original_create_app):
            logger.error("create_app function not found in run_mcp_server_real_storage module")
            return False
        
        # Create a wrapper for create_app that initializes the IPFS model
        def create_app_wrapper(*args, **kwargs):
            """Wrapper for create_app that initializes IPFS model extensions."""
            # Initialize the IPFS model
            initialize_ipfs_model()
            
            # Call the original create_app function
            return original_create_app(*args, **kwargs)
        
        # Replace the original create_app function with our wrapper
        setattr(run_mcp_server_module, "create_app", create_app_wrapper)
        
        logger.info("Successfully patched run_mcp_server_real_storage module")
        return True
    
    except Exception as e:
        logger.error(f"Error patching run_mcp_server_real_storage: {e}")
        return False

def initialize_mcp_server():
    """
    Initialize MCP server with all required extensions.
    
    This function should be called during MCP server startup to ensure
    all controllers and models are properly initialized.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    success = True
    
    # Initialize IPFS model
    try:
        from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
        if not initialize_ipfs_model():
            logger.warning("Failed to initialize IPFS model")
            success = False
    except ImportError:
        logger.warning("Could not import IPFS model initializer")
        success = False
    
    # Patch run_mcp_server
    if not patch_run_mcp_server():
        logger.warning("Failed to patch run_mcp_server")
        success = False
        
    # Apply SSE and CORS fixes
    try:
        from ipfs_kit_py.mcp.sse_cors_fix import patch_mcp_server_for_sse
        if not patch_mcp_server_for_sse():
            logger.warning("Failed to apply SSE and CORS fixes")
            success = False
        else:
            logger.info("Successfully applied SSE and CORS fixes")
    except ImportError:
        logger.warning("Could not import SSE and CORS fixes")
        success = False
    
    return success

# Auto-initialize when this module is imported
if __name__ != "__main__":
    initialize_mcp_server()
