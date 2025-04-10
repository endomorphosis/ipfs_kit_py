#!/usr/bin/env python3
"""
Run the MCP server directly with uvicorn on port 8001 for tests.
"""

import os
import logging
import uvicorn
import argparse
from fastapi import FastAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run custom MCP server with patched IPFS model')
parser.add_argument('--port', type=int, default=8002, help='Port to run the server on')
args = parser.parse_args()

# Create FastAPI app
app = FastAPI(
    title="IPFS MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="0.1.0"
)

# Create and register MCP server
try:
    from ipfs_kit_py.mcp.server import MCPServer
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    
    # Import ipfs_kit to properly initialize IPFS
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    
    # Create an ipfs_kit instance with leecher role to avoid cluster requirements
    logger.info("Creating ipfs_kit instance and ensuring daemon is running...")
    kit = ipfs_kit(auto_start_daemons=True)  # Use default leecher role
    
    # Initialize the IPFS daemon
    init_result = kit.initialize(start_daemons=True)
    logger.info(f"IPFS initialization result: {init_result}")
    
    # Create MCP server with debug and isolation modes
    mcp_server = MCPServer(
        debug_mode=True,
        isolation_mode=False,  # Set to False to use the existing IPFS installation
        persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_test"),
        ipfs_kit_instance=kit  # Pass the already initialized kit instance
    )
    
    # Force reload IPFS model with our updated implementation
    logger.info("Patching IPFSModel with updated implementation")
    
    # Create new IPFS model with our updated implementation
    new_ipfs_model = IPFSModel(
        ipfs_kit_instance=kit,
        cache_manager=mcp_server.cache_manager,
        credential_manager=mcp_server.credential_manager
    )
    
    # Replace the existing model with our new one
    mcp_server.models["ipfs"] = new_ipfs_model
    
    # Update controller to use the new model
    mcp_server.controllers["ipfs"] = mcp_server.controllers["ipfs"].__class__(new_ipfs_model)
    
    # Update storage manager to use the new model
    mcp_server.storage_manager.ipfs_model = new_ipfs_model
    
    # Verify our model has the required methods
    logger.info(f"IPFSModel has add_content: {hasattr(new_ipfs_model, 'add_content')}")
    logger.info(f"IPFSModel has get_content: {hasattr(new_ipfs_model, 'get_content')}")
    logger.info(f"IPFSModel has pin_content: {hasattr(new_ipfs_model, 'pin_content')}")
    
    # Register with app
    mcp_server.register_with_app(app, prefix="/api/v0/mcp")
    
    logger.info("MCP server initialized and registered with app")
except Exception as e:
    logger.error(f"Failed to create MCP server: {e}")
    
    @app.get("/")
    async def error():
        return {"error": f"Failed to initialize MCP server: {str(e)}"}

# Add simple root endpoint
@app.get("/")
async def root():
    return {
        "message": "MCP Server is running for tests", 
        "endpoints": {
            "health_check": "/api/v0/mcp/health"
        }
    }

if __name__ == "__main__":
    # Run the server
    logger.info(f"Starting MCP server on port {args.port} for tests")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")