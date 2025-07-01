#!/usr/bin/env python3
"""
Fixed Clean MCP server implementation with proper parameter handling.

This script starts a clean MCP server instance with both basic and storage functionality.
Command-line arguments are properly respected.
"""

import os
import sys
import logging
import uvicorn
import argparse
import time
from fastapi import FastAPI

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run a clean MCP server")
parser.add_argument("--port", type=int, default=9995, help="Port to run the server on")
parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
parser.add_argument("--api-prefix", default="/api/v0", help="API prefix")
args = parser.parse_args()

# Configure logging to file
os.makedirs('logs/mcp', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/mcp/mcp_fixed_server.log'
)

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

# Get logger
logger = logging.getLogger(__name__)

# Configuration from command-line arguments
DEBUG_MODE = args.debug
ISOLATION_MODE = args.isolation
PORT = args.port
HOST = args.host
API_PREFIX = args.api_prefix

# Ensure import paths are set up correctly
def fix_import_paths():
    """Ensure all necessary import paths are set up correctly."""
    try:
        # Create necessary directories if they don't exist
        os.makedirs("ipfs_kit_py/mcp/models", exist_ok=True)
        
        # Create symbolic links for necessary modules if they don't exist
        symlinks = [
            ("ipfs_kit_py/mcp_server/server_bridge.py", "ipfs_kit_py/mcp/server_bridge.py"),
            ("ipfs_kit_py/mcp_server/models/ipfs_model.py", "ipfs_kit_py/mcp/models/ipfs_model.py"),
            ("ipfs_kit_py/mcp_server/models/ipfs_model_anyio.py", "ipfs_kit_py/mcp/models/ipfs_model_anyio.py"),
            ("ipfs_kit_py/mcp_server/server.py", "ipfs_kit_py/mcp/server.py"),
            ("ipfs_kit_py/mcp_server/server_anyio.py", "ipfs_kit_py/mcp/server_anyio.py")
        ]
        
        for src, dst in symlinks:
            # Only create the symlink if the source file exists and the destination doesn't
            if os.path.exists(src) and not os.path.exists(dst):
                os.symlink(os.path.abspath(src), os.path.abspath(dst))
                logger.info(f"Created symlink: {src} -> {dst}")
                
        logger.info("Import paths fixed successfully")
    except Exception as e:
        logger.error(f"Failed to fix import paths: {e}")

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Fix import paths first
    fix_import_paths()
    
    # Import MCP server
    try:
        # Try the AnyIO version first (preferred)
        try:
            # Import directly from mcp_server
            from ipfs_kit_py.mcp_server.server_anyio import MCPServer
            logger.info("Using AnyIO-compatible MCP server implementation (direct import)")
            use_anyio = True
        except ImportError:
            # Import directly from mcp_server
            from ipfs_kit_py.mcp_server.server_bridge import MCPServer
            logger.info("Using standard MCP server implementation (direct import)")
            use_anyio = False
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=DEBUG_MODE,
            isolation_mode=ISOLATION_MODE,
            # Use a specific persistence path to avoid conflicts
            persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_fixed")
        )
        
        # Register with app
        if hasattr(mcp_server, 'register_with_app'):
            mcp_server.register_with_app(app, prefix=API_PREFIX)
        else:
            logger.warning("MCP server doesn't have 'register_with_app' method, using stub implementation")
        
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
                "api_version": "v0",
                "listening_on": f"{HOST}:{PORT}"
            }
        
        # Add a custom health endpoint if not already registered
        health_path = f"{API_PREFIX}/health"
        if not any(route.path == health_path for route in app.routes):
            @app.get(health_path)
            async def health_check():
                """Health check endpoint."""
                status = "healthy"
                
                # If server has health check method, use it
                if hasattr(mcp_server, 'health_check'):
                    try:
                        health_data = await mcp_server.health_check()
                        if isinstance(health_data, dict):
                            return health_data
                    except Exception as e:
                        logger.error(f"Error in health check: {e}")
                        status = "unhealthy"
                
                # Basic response if no health check available
                return {
                    "status": status,
                    "timestamp": time.time(),
                    "version": "1.0",
                    "server_type": "fixed_mcp"
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
    pid_dir = os.path.dirname('run/mcp/mcp_fixed_server.pid')
    os.makedirs(pid_dir, exist_ok=True)
    with open('run/mcp/mcp_fixed_server.pid', 'w') as f:
        f.write(str(os.getpid()))

if __name__ == "__main__":
    # Write PID file
    write_pid()
    
    # Run uvicorn directly
    logger.info(f"Starting fixed MCP server on port {PORT} with API prefix: {API_PREFIX}")
    logger.info(f"Debug mode: {DEBUG_MODE}, Isolation mode: {ISOLATION_MODE}")
    
    uvicorn.run(
        "run_fixed_mcp_server:app", 
        host=HOST, 
        port=PORT,
        reload=False,  # Disable reload to avoid duplicate process issues
        log_level="info" if not DEBUG_MODE else "debug"
    )
