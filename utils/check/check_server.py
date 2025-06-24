#!/usr/bin/env python3
"""
Check the MCP server routes to debug URL routing issues.
"""

import os
import sys
import logging
import uvicorn
from fastapi import FastAPI
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for detailed output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_check")

def main():
    """Check the MCP server routes."""
    logger.info("Checking MCP server routes...")

    # Import MCP server
    from ipfs_kit_py.mcp.server_anyio import MCPServer

    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server Debug",
        description="Debugging MCP Server Routes",
        version="0.1.0"
    )

    # Create MCP server with debug mode
    mcp_server = MCPServer(
        debug_mode=True,
        isolation_mode=True,
        persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_debug")
    )

    # Explicitly register controllers in custom order
    router = mcp_server.register_controllers()

    # Log all registered routes
    logger.info("All registered routes:")
    for route in router.routes:
        if hasattr(route, 'methods'):
            logger.info(f"  {route.path} - {route.methods}")
        else:
            # Handle WebSocket routes or other route types that don't have methods
            route_type = route.__class__.__name__
            logger.info(f"  {route.path} - [{route_type}]")

    # Register MCP server with app at root prefix (no additional prefix)
    mcp_server.register_with_app(app, prefix="/api/v0")

    # Add a custom endpoint to check registered routes
    @app.get("/check-routes")
    async def check_routes():
        routes_info = []
        for route in app.routes:
            route_info = {
                "path": getattr(route, "path", "unknown"),
                "methods": getattr(route, "methods", []),
                "name": getattr(route, "name", ""),
                "endpoint": str(getattr(route, "endpoint", ""))
            }
            routes_info.append(route_info)
        return {
            "total_routes": len(routes_info),
            "routes": routes_info
        }

    # Print all routes in the FastAPI app
    logger.info("All FastAPI routes:")
    for route in app.routes:
        logger.info(f"  {getattr(route, 'methods', [])} {getattr(route, 'path', 'unknown')}")

    # Specifically check for storage status endpoint
    has_storage_endpoint = False
    for route in app.routes:
        if getattr(route, "path", "").endswith("/storage/status"):
            has_storage_endpoint = True
            logger.info(f"Found storage status endpoint: {route.path} with methods {route.methods}")
            logger.info(f"  Endpoint function: {route.endpoint}")

    if not has_storage_endpoint:
        logger.warning("Storage status endpoint not found in registered routes!")

    # Start the server
    return app

if __name__ == "__main__":
    app = main()

    # Print final status
    print("\nRoute verification complete. To start the server, run:")
    print("uvicorn check_server:app --reload --port 8000")

    # Check if we should run the server
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        print("Starting server...")
        uvicorn.run(app, host="127.0.0.1", port=8000)
