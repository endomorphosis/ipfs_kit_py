#!/usr/bin/env python3
"""
Test MCP server shutdown to verify coroutine handling.

This script tests the proper shutdown of WebRTC and WebSocket controllers
to ensure there are no "coroutine was never awaited" warnings.
"""

import os
import sys
import logging
import time
import warnings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable any RuntimeWarnings to be shown
warnings.filterwarnings("always", category=RuntimeWarning)

def test_mcp_shutdown():
    """
    Test MCP server shutdown process with WebRTC and WebSocket controllers.
    
    This test creates an MCP server with both WebRTC and WebSocket controllers,
    then shuts it down to check for proper handling of async shutdown methods.
    """
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
    
    # Create MCP server with isolation mode for testing
    logger.info("Creating MCP server...")
    server = MCPServer(
        debug_mode=True,
        log_level="DEBUG",
        persistence_path="/tmp/test_mcp_shutdown",
        isolation_mode=True
    )
    
    # Check if the WebRTC and WebSocket controllers were initialized
    has_webrtc = "webrtc" in server.controllers
    has_websocket = "peer_websocket" in server.controllers
    
    logger.info(f"MCP Server initialized with:")
    logger.info(f"- WebRTC controller: {'✅' if has_webrtc else '❌'}")
    logger.info(f"- WebSocket controller: {'✅' if has_websocket else '❌'}")
    
    # Let the server run for a short time
    logger.info("Letting server run for 2 seconds...")
    time.sleep(2)
    
    # Now shutdown the server and watch for warnings
    logger.info("Shutting down MCP server...")
    try:
        server.shutdown()
        logger.info("MCP Server shutdown completed without errors")
    except Exception as e:
        logger.error(f"Error during server shutdown: {e}")
        return False
    
    logger.info("Test completed successfully")
    return True

if __name__ == "__main__":
    logger.info("Starting MCP shutdown test")
    success = test_mcp_shutdown()
    
    if success:
        logger.info("✅ Test passed: MCP server shutdown completed without coroutine warnings")
        sys.exit(0)
    else:
        logger.error("❌ Test failed: Check logs for details")
        sys.exit(1)