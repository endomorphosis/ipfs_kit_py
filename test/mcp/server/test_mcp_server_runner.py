#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_server_for_tests.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

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
parser = argparse.ArgumentParser(description='Run MCP server for tests')
parser.add_argument('--port', type=int, default=8001, help='Port to run the server on')
# Only parse args when running the script directly, not when imported by pytest
if __name__ == "__main__":
    args = parser.parse_args()
else:
    # When run under pytest, use default values
    args = parser.parse_args([])

# Patch missing methods in ipfs_kit
try:
    import patch_missing_methods
    logger.info("Successfully patched missing methods to ipfs_kit")
except Exception as e:
    logger.error(f"Failed to patch missing methods: {e}")

# Create FastAPI app
app = FastAPI(
    title="IPFS MCP Server",
    description="Model-Controller-Persistence Server for IPFS Kit",
    version="0.1.0"
)

# Variable to track initialization status
init_success = False
init_error = None

# Create and register MCP server
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import

    # Import ipfs_kit to properly initialize IPFS
    from ipfs_kit_py.ipfs_kit import ipfs_kit

    # Create an ipfs_kit instance
    kit = ipfs_kit()

    # Create MCP server with debug and isolation modes
    mcp_server = MCPServer(
        debug_mode=True,
        isolation_mode=False,  # Set to False to use the existing IPFS installation
        persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_test"),
        ipfs_kit_instance=kit  # Pass the already initialized kit instance
    )

    # Register with app using the correct prefix for proper controller routes
    # Using /api/v0 instead of /api/v0/mcp fixes the 404 errors with advanced controllers
    mcp_server.register_with_app(app, prefix="/api/v0")

    init_success = True
    logger.info("MCP server initialized and registered with app")
except Exception as e:
    init_error = str(e)
    logger.error(f"Failed to create MCP server: {e}")

# Add root endpoint with initialization status
@app.get("/")
async def root():
    if init_success:
        return {
            "message": "MCP Server is running for tests",
            "status": "ready",
            "endpoints": {
                "health_check": "/api/v0/health"
            }
        }
    else:
        return {
            "message": "MCP Server initialization failed",
            "status": "error",
            "error": init_error
        }

if __name__ == "__main__":
    # Run the server
    logger.info(f"Starting MCP server on port {args.port} for tests")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
