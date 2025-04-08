#!/usr/bin/env python3
"""
Simple runner script that starts the MCP server with WebRTC forced available.
This script combines mcp_wrapper with the run_mcp_server script.
"""

import os
import sys
import time
import importlib
import logging

# Set environment variables for WebRTC support
os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
os.environ["FORCE_WEBRTC_TESTS"] = "1"
os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Force WebRTC modules to recognize their dependencies
def force_webrtc_availability():
    """Force WebRTC modules to recognize their dependencies."""
    logger.info("Forcing WebRTC dependencies to be available...")
    
    # Try to import and patch webrtc_streaming
    try:
        from ipfs_kit_py import webrtc_streaming
        
        # Force all dependency flags to True
        webrtc_streaming.HAVE_WEBRTC = True
        webrtc_streaming.HAVE_NUMPY = True
        webrtc_streaming.HAVE_CV2 = True
        webrtc_streaming.HAVE_AV = True
        webrtc_streaming.HAVE_AIORTC = True
        webrtc_streaming.HAVE_NOTIFICATIONS = True
        
        # Reload to ensure changes take effect
        importlib.reload(webrtc_streaming)
        
        logger.info("Patched webrtc_streaming module successfully")
    except Exception as e:
        logger.error(f"Failed to patch webrtc_streaming module: {e}")
    
    # Try to import and patch high_level_api
    try:
        from ipfs_kit_py import high_level_api
        
        # Force WebRTC flag if it exists
        if hasattr(high_level_api, 'HAVE_WEBRTC'):
            high_level_api.HAVE_WEBRTC = True
            
        # Reload to ensure changes take effect
        importlib.reload(high_level_api)
        
        logger.info("Patched high_level_api module successfully")
    except Exception as e:
        logger.error(f"Failed to patch high_level_api module: {e}")

# Force WebRTC availability
force_webrtc_availability()

# Now import the run_mcp_server module and get its app
try:
    import run_mcp_server
    app = run_mcp_server.app
    logger.info("Successfully imported run_mcp_server.app")
except Exception as e:
    logger.error(f"Failed to import run_mcp_server.app: {e}")
    sys.exit(1)

# If running directly, start the server with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    # Define a port argument
    port = 9999
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    
    logger.info(f"Starting MCP server with WebRTC on port {port}...")
    uvicorn.run("run_mcp_with_webrtc:app", host="127.0.0.1", port=port, log_level="info")