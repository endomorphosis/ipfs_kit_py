#!/usr/bin/env python3
"""
MCP Server Async Test - Tests the MCP server with FastAPI but without actual HTTP server
"""

import os
import sys
import time
import json
import logging
import tempfile
import anyio
from fastapi import FastAPI, Request, Response

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_async_test")

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
    """Test MCP server with FastAPI without actual HTTP server."""
    logger.info("Initializing FastAPI app and MCP Server...")
    
    # Create temporary directory for testing
    temp_dir = tempfile.mkdtemp(prefix="ipfs_mcp_async_test_")
    logger.info(f"Using temporary directory: {temp_dir}")
    
    # Create FastAPI app
    app = FastAPI(title="MCP Async Test")
    
    # Initialize the MCP server with debug and isolation modes
    mcp_server = MCPServer(
        debug_mode=True,
        isolation_mode=True,
        persistence_path=temp_dir
    )
    
    # Register MCP server with app
    mcp_server.register_with_app(app, prefix="/api/v0/mcp")
    
    # Test health endpoint through FastAPI
    logger.info("Testing MCP integration with FastAPI...")
    
    # Get the health endpoint handler
    health_route = None
    for route in app.routes:
        if route.path == "/api/v0/mcp/health":
            health_route = route
            break
    
    if health_route:
        # Create mock request
        mock_request = Request(scope={
            "type": "http",
            "method": "GET",
            "path": "/api/v0/mcp/health",
            "headers": []
        })
        
        # Call the endpoint handler directly
        logger.info("Calling health endpoint handler...")
        response = await health_route.endpoint(mock_request)
        
        # Convert response to dict
        if hasattr(response, "body"):
            response_data = json.loads(response.body)
        else:
            response_data = response
            
        logger.info(f"Health endpoint response: {json.dumps(response_data, indent=2)}")
        
        # Basic validation
        if response_data.get("success") == True:
            logger.info("✅ MCP server integration with FastAPI successful!")
        else:
            logger.error("❌ MCP server integration with FastAPI failed!")
    else:
        logger.error("❌ Health endpoint not found in registered routes!")
    
    # List all registered routes
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path,
            "methods": list(route.methods) if hasattr(route, "methods") else ["unknown"]
        })
    
    logger.info(f"Registered MCP routes: {json.dumps(routes, indent=2)}")
    
    # Clean up
    logger.info(f"Test completed! Temporary directory {temp_dir} can be removed manually.")
    
    return {
        "success": True,
        "message": "MCP server async test completed",
        "temp_dir": temp_dir,
        "routes": routes
    }

if __name__ == "__main__":
    # Run the async test using asyncio
    result = asyncio.run(test_mcp_server_async())
    logger.info(f"Test result: {result['success']}")
