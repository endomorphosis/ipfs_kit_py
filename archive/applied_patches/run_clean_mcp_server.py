#!/usr/bin/env python3
"""
Clean MCP server implementation for testing and debugging.

This script starts a clean MCP server instance with both basic and storage functionality.
"""

import os
import sys
import logging
import uvicorn
from fastapi import FastAPI

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/mcp/mcp_clean_server.log'
)

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

# Get logger
logger = logging.getLogger(__name__)

# Configuration
DEBUG_MODE = True
ISOLATION_MODE = True
PORT = 9995  # Using a different port to avoid conflicts
HOST = "0.0.0.0"
API_PREFIX = "/api/v0"

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Import MCP server
    try:
        # Try the AnyIO version first (preferred)
        try:
            from ipfs_kit_py.mcp.server_anyio import MCPServer
            logger.info("Using AnyIO-compatible MCP server implementation")
            use_anyio = True
        except ImportError:
            from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
            logger.info("Using standard MCP server implementation")
            use_anyio = False
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=DEBUG_MODE,
            isolation_mode=ISOLATION_MODE,
            # Use a specific persistence path to avoid conflicts
            persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_clean")
        )
        
        # Register with app
        mcp_server.register_with_app(app, prefix=API_PREFIX)
        
        # Add root endpoint
        @app.get("/")
        async def root():
            """Root endpoint with API information."""
            version = "AnyIO" if use_anyio else "Standard"
            
            return {
                "message": f"MCP Server is running ({version} implementation)",
                "debug_mode": DEBUG_MODE,
                "isolation_mode": ISOLATION_MODE,
                "documentation": "/docs",
                "health_endpoint": f"{API_PREFIX}/health",
                "api_version": "v0"
            }
        
        return app, mcp_server
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP server: {e}")
        app = FastAPI()
        
        @app.get("/")
        async def error():
            return {"error": f"Failed to initialize MCP server: {str(e)}"}
            
        return app, None

# Create the app for uvicorn
app, mcp_server = create_app()

# Write PID file
def write_pid():
    """Write the current process ID to a file."""
    pid_dir = os.path.dirname('run/mcp/mcp_clean_server.pid')
    os.makedirs(pid_dir, exist_ok=True)
    with open('run/mcp/mcp_clean_server.pid', 'w') as f:
        f.write(str(os.getpid()))

if __name__ == "__main__":
    # Write PID file
    write_pid()
    
    # Ensure log directory exists
    os.makedirs('logs/mcp', exist_ok=True)
    
    # Run uvicorn directly
    logger.info(f"Starting clean MCP server on port {PORT} with API prefix: {API_PREFIX}")
    logger.info(f"Debug mode: {DEBUG_MODE}, Isolation mode: {ISOLATION_MODE}")
    
    uvicorn.run(
        "run_clean_mcp_server:app", 
        host=HOST, 
        port=PORT,
        reload=False,  # Disable reload to avoid duplicate process issues
        log_level="info" if not DEBUG_MODE else "debug"
    )