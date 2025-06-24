#!/usr/bin/env python3
"""
MCP Server Simple Test - Tests the MCP server functionality without requiring network
"""

import os
import sys
import time
import json
import logging
import tempfile
import anyio

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_simple_test")

# Import ipfs_kit_py components
try:
    from ipfs_kit_py.mcp import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
    from ipfs_kit_py.mcp.persistence.cache_manager import MCPCacheManager
    from ipfs_kit_py.ipfs_kit import ipfs_kit
except ImportError as e:
    logger.error(f"Failed to import ipfs_kit_py components: {e}")
    sys.exit(1)

async def test_mcp_server_async():
    """Test basic MCP server functionality without networking."""
    logger.info("Initializing MCP Server...")

    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_test_")
    logger.info(f"Using temporary directory: {temp_dir}")

    # Initialize the MCP server with debug and isolation modes
    mcp_server = MCPServer(
        debug_mode=True,
        isolation_mode=False,  # Disable isolation to avoid ipfs_path issues
        persistence_path=temp_dir
    )

    # Test health check
    logger.info("Testing health check...")
    health = await mcp_server.health_check()
    logger.info(f"Health check success: {health['success']}")

    # Test IPFS model directly
    logger.info("Testing IPFS model...")
    ipfs_model = mcp_server.models["ipfs"]

    # Add some test content
    test_content = b"Hello, IPFS MCP!"
    logger.info("Adding test content...")
    add_result = ipfs_model.add_content(test_content)

    if add_result.get("success"):
        cid = add_result.get("cid")
        logger.info(f"Content added with CID: {cid}")

        # Try to get the content back
        logger.info("Retrieving content...")
        get_result = ipfs_model.get_content(cid)

        if get_result.get("success"):
            content = get_result.get("content")
            if content:
                logger.info(f"Retrieved content: {content[:20]}...")

                # Check if the content matches
                if content == test_content:
                    logger.info("✅ Content verification successful!")
                else:
                    logger.error("❌ Content verification failed!")
            else:
                logger.info("Note: Content is simulated and not actually returned in debug mode.")
        else:
            logger.error(f"Failed to get content: {get_result.get('error')}")
    else:
        logger.error(f"Failed to add content: {add_result.get('error')}")

    # Test debug state
    logger.info("Testing debug state...")
    debug_state = await mcp_server.get_debug_state()
    logger.info(f"Debug state available: {debug_state['success']}")

    # Test operation log
    logger.info("Testing operation log...")
    operation_log = await mcp_server.get_operation_log()
    logger.info(f"Operation log contains {operation_log['count']} entries")

    # Test cache
    logger.info("Testing cache...")
    cache_info = mcp_server.persistence.get_cache_info()
    logger.info(f"Cache info: {json.dumps(cache_info, indent=2)}")

    # Clean up
    logger.info(f"Test completed! Temporary directory {temp_dir} can be removed manually.")

    return {
        "success": True,
        "message": "MCP server test completed",
        "temp_dir": temp_dir
    }

def test_mcp_server():
    """Run the async test function using anyio."""
    return anyio.run(test_mcp_server_async())

if __name__ == "__main__":
    result = test_mcp_server()
    logger.info(f"Test result: {result['success']}")
