#!/usr/bin/env python3
"""
Test script for MCP server with WebRTC capabilities.
This script initializes the MCP server and checks if WebRTC features are correctly enabled.
"""

import logging
import os
import sys
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test MCP server with WebRTC capabilities."""
    logger.info("Starting MCP WebRTC test")
    
    # Import the MCP server module
    try:
        from ipfs_kit_py.mcp.server import MCPServer
        logger.info("Successfully imported MCPServer")
    except ImportError as e:
        logger.error(f"Failed to import MCPServer: {e}")
        return
    
    # First, check WebRTC dependencies
    try:
        from ipfs_kit_py.webrtc_streaming import check_webrtc_dependencies
        
        # Get WebRTC status
        webrtc_status = check_webrtc_dependencies()
        logger.info(f"WebRTC dependencies status: {webrtc_status}")
        
        # Check high-level API WebRTC status
        from ipfs_kit_py.high_level_api import HAVE_WEBRTC as HL_HAVE_WEBRTC
        logger.info(f"High-level API WebRTC flag: {HL_HAVE_WEBRTC}")
        
    except ImportError as e:
        logger.error(f"Failed to import WebRTC dependencies: {e}")
    
    # Initialize the MCP server (don't start it)
    try:
        # Create MCP server with debug mode
        server = MCPServer(
            debug_mode=True,
            log_level="INFO",
            persistence_path=None,  # Use default
            isolation_mode=False
        )
        
        logger.info("Successfully created MCPServer instance")
        
        # Check if the server has access to WebRTC capabilities
        if hasattr(server, 'models') and 'ipfs' in server.models:
            ipfs_model = server.models['ipfs']
            
            # Check if the model has WebRTC methods or attributes
            webrtc_attrs = [attr for attr in dir(ipfs_model) if "webrtc" in attr.lower()]
            logger.info(f"IPFS model WebRTC attributes: {webrtc_attrs}")
            
            # Check if the model can access WebRTC dependencies
            if hasattr(ipfs_model, '_check_webrtc'):
                webrtc_available = ipfs_model._check_webrtc()
                logger.info(f"IPFS model WebRTC availability check: {webrtc_available}")
            else:
                logger.warning("IPFS model doesn't have _check_webrtc method")
                
                # Try accessing HAVE_WEBRTC directly from the model
                if hasattr(ipfs_model, 'HAVE_WEBRTC'):
                    logger.info(f"IPFS model HAVE_WEBRTC: {ipfs_model.HAVE_WEBRTC}")
                else:
                    logger.warning("IPFS model doesn't have HAVE_WEBRTC attribute")
                    
                    # Try importing from the module
                    try:
                        from ipfs_kit_py.mcp.models.ipfs_model import HAVE_WEBRTC as MODEL_HAVE_WEBRTC
                        logger.info(f"ipfs_model module HAVE_WEBRTC: {MODEL_HAVE_WEBRTC}")
                    except (ImportError, AttributeError) as e:
                        logger.warning(f"Failed to import HAVE_WEBRTC from ipfs_model module: {e}")
                        
        else:
            logger.warning("MCPServer doesn't have IPFS model")
            
    except Exception as e:
        logger.error(f"Error testing MCP server: {type(e).__name__}: {e}")
        
    logger.info("MCP WebRTC test completed")

if __name__ == "__main__":
    main()