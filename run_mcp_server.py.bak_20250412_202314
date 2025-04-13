#!/usr/bin/env python3
"""
Simple script to run the MCP server.
"""

import os
import time
import logging
import fastapi
from fastapi import FastAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the MCP server."""
    logger.info("Starting MCP server")

    try:
        # Import MCP server
        from ipfs_kit_py.mcp.server import MCPServer
    except ImportError as e:
        logger.error(f"Failed to import MCP server: {e}")
        return 1

    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )

    # Create MCP server with debug and isolation modes
    try:
        mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=True,
            persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_debug")
        )
    except Exception as e:
        logger.error(f"Failed to create MCP server: {e}")
        return 1

    # Register MCP server with app
    try:
        # For the API routes to be properly accessible, we need to register with /api/v0 prefix
        mcp_server.register_with_app(app, prefix="/api/v0")
    except Exception as e:
        logger.error(f"Failed to register MCP server with app: {e}")
        return 1

    # Start the server using uvicorn
    import uvicorn
    logger.info("MCP server configured successfully, ready to start uvicorn")
    
    # Print success message and instructions
    print("Successfully initialized MCP server!")
    print("To run the server, use:")
    print("  uvicorn run_mcp_server:app --reload --port 8000")
    
    return 0

# Global variables for cleanup
mcp_server = None

# Create a global app instance for uvicorn
try:
    # Get configuration from environment variables or use defaults
    debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
    isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "true").lower() == "true"
    api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0/mcp")
    persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp_debug")
    
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Create and register MCP server
    from ipfs_kit_py.mcp.server import MCPServer
    mcp_server = MCPServer(
        debug_mode=debug_mode,
        isolation_mode=isolation_mode,
        persistence_path=os.path.expanduser(persistence_path)
    )
    # For the API routes to be properly accessible, we need to register with
    # the correct prefix that's compatible with the controller route paths.
    # We should use /api/v0 instead of /api/v0/mcp to fix the 404 errors
    mcp_server.register_with_app(app, prefix="/api/v0")
    
    # Add a simple root endpoint
    @app.get("/")
    async def root():
        # Get daemon status information if available
        daemon_info = {}
        if hasattr(mcp_server.ipfs_kit, 'check_daemon_status'):
            try:
                daemon_info["ipfs_daemon_running"] = mcp_server.ipfs_kit.check_daemon_status('ipfs').get("running", False)
            except Exception:
                daemon_info["ipfs_daemon_running"] = False
                
        if hasattr(mcp_server.ipfs_kit, 'auto_start_daemons'):
            daemon_info["auto_start_daemons"] = mcp_server.ipfs_kit.auto_start_daemons
            
        if hasattr(mcp_server.ipfs_kit, 'is_daemon_health_monitor_running'):
            daemon_info["daemon_monitor_running"] = mcp_server.ipfs_kit.is_daemon_health_monitor_running()
        
        # List available endpoints including daemon management endpoints
        endpoints = {
            "health_check": f"{api_prefix}/health",
            "debug_state": f"{api_prefix}/debug" if debug_mode else "Disabled (debug mode required)",
            "daemon_management": {
                "daemon_status": f"{api_prefix}/daemon/status",
                "start_daemon": f"{api_prefix}/daemon/start/{{daemon_type}}",
                "stop_daemon": f"{api_prefix}/daemon/stop/{{daemon_type}}",
                "start_monitor": f"{api_prefix}/daemon/monitor/start",
                "stop_monitor": f"{api_prefix}/daemon/monitor/stop"
            }
        }
        
        return {
            "message": "MCP Server is running", 
            "debug_mode": debug_mode,
            "isolation_mode": isolation_mode,
            "controllers": list(mcp_server.controllers.keys()),
            "daemon_status": daemon_info,
            "endpoints": endpoints,
            "documentation": "/docs"
        }
    
    # Add shutdown event handler
    @app.on_event("shutdown")
    async def shutdown_event():
        global mcp_server
        if mcp_server:
            logger.info("FastAPI shutdown event received, cleaning up MCP server")
            mcp_server.shutdown()
            logger.info("MCP server resources cleaned up")
        
    # Register signal handlers for graceful shutdown
    import signal
    
    def signal_handler(sig, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {sig}, shutting down...")
        if mcp_server:
            mcp_server.shutdown()
        # Let the process terminate naturally
        exit(0)
        
    # Register handlers for SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
        
except Exception as e:
    print(f"Error initializing app: {e}")
    app = FastAPI()
    
    @app.get("/")
    async def error():
        return {"error": f"Failed to initialize MCP server: {str(e)}"}

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)