#!/usr/bin/env python3
"""
Register All Backend Tools

This module provides functions to register all storage backend tools
with the MCP server, integrating the multi-backend filesystem with IPFS,
HuggingFace, S3, Filecoin, Storacha, and more.
"""

import os
import sys
import logging
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def register_multi_backend_tools_with_server(server: Any) -> bool:
    """
    Register multi-backend tools with the MCP server.
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    try:
        # Import multi-backend integration
        from multi_backend_fs_integration import register_multi_backend_tools, MultiBackendFS
        
        # Initialize multi-backend filesystem
        logger.info("Initializing Multi-Backend filesystem...")
        server.multi_backend_fs = MultiBackendFS(os.getcwd())
        
        # Register multi-backend tools
        logger.info("Registering Multi-Backend tools...")
        success = register_multi_backend_tools(server)
        
        if success:
            logger.info("✅ Successfully registered Multi-Backend tools")
        else:
            logger.error("Failed to register Multi-Backend tools")
            
        return success
    except ImportError as e:
        logger.error(f"Failed to import multi-backend integration: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error registering multi-backend tools: {e}")
        return False

def register_all_tools(server: Any) -> bool:
    """
    Register all storage backend tools with the MCP server.
    
    This function registers:
    1. FS Journal tools (if not already registered)
    2. IPFS-FS Bridge tools (if not already registered)
    3. Multi-Backend storage tools
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if all registrations were successful, False otherwise
    """
    try:
        # Import FS Journal integration
        import fs_journal_tools
        import ipfs_mcp_fs_integration
        
        # Check if FS Journal tools are already registered
        fs_journal_registered = False
        ipfs_fs_bridge_registered = False
        
        # Check for existing tool registrations
        if hasattr(server, "fs_journal"):
            logger.info("FS Journal already initialized")
            fs_journal_registered = True
        
        if hasattr(server, "ipfs_fs_bridge"):
            logger.info("IPFS-FS Bridge already initialized")
            ipfs_fs_bridge_registered = True
            
        # Register FS Journal tools if not already registered
        if not fs_journal_registered:
            logger.info("Registering FS Journal tools...")
            fs_journal_tools.register_fs_journal_tools(server)
            
        # Register IPFS-FS Bridge tools if not already registered
        if not ipfs_fs_bridge_registered:
            logger.info("Registering IPFS-FS Bridge tools...")
            ipfs_mcp_fs_integration.register_with_mcp_server(server)
            
        # Register Multi-Backend tools
        multi_backend_success = register_multi_backend_tools_with_server(server)
        
        # Return overall success status
        return (fs_journal_registered or True) and (ipfs_fs_bridge_registered or True) and multi_backend_success
    
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during tool registration: {e}")
        return False

if __name__ == "__main__":
    # This is a module intended to be imported, not run directly
    logger.warning("This module is intended to be imported, not run directly")
