"""
Mock implementation of the server module to resolve import errors.
"""

import logging
logger = logging.getLogger("ipfs-kit-mcp-server")

def init_server():
    """Initialize the IPFS MCP server."""
    logger.info("Mock IPFS MCP server initialized")
    return True
