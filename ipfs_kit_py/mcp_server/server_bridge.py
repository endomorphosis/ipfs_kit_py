"""
MCP Server Bridge module.

This module provides compatibility with the old MCP server structure by bridging
to the new consolidated structure in ipfs_kit_py.mcp.
"""

import logging
import sys

# Set up logging
logger = logging.getLogger(__name__)

try:
    # Import from the new location directly
    from ipfs_kit_py.mcp.server_bridge import MCPServer, MCPCacheManager, AsyncMCPServer
    
    logger.info("Successfully imported MCPServer from ipfs_kit_py.mcp.server_bridge")
    
    # Re-export all the names
    __all__ = ['MCPServer', 'MCPCacheManager', 'AsyncMCPServer']
    
except ImportError as e:
    logger.error(f"Failed to import from ipfs_kit_py.mcp.server_bridge: {e}")
    # Raise to make the error visible
    raise
