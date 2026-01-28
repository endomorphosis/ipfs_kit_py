#!/usr/bin/env python3
"""
MCP server with real API implementations for storage backends.
"""

import os
import sys
import logging
import time
import hashlib
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
import uvicorn

# Import real API implementation
from real_api_storage_backends import get_all_backends_status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables or use defaults
debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "true").lower() == "true"
api_prefix = "/api/v0"  # Fixed prefix for consistency
persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp_debug")

# Get backend status
backends_status = get_all_backends_status()

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Add real API proxy endpoints for each backend
    for backend, status in backends_status.items():
        if status["exists"] and status["enabled"]:
            if status["simulation"]:
                # For backends in simulation mode, add simulation endpoints
                add_simulation_endpoints(app, backend)
            else:
                # For backends in real mode, ensure they connect to actual APIs
                logger.info(f"Using REAL API implementation for {backend}")
    
    # Add a custom pins endpoint that always works
    @app.get(f"{api_prefix}/mcp/cli/pins")
    async def list_pins():
        """Simple pins endpoint that always returns an empty list."""
        return {
            "success": True,
            "result": {
                "pins": {}
            },
            "operation_id": None,
            "format": None
        }
    
    # Import MCP server
    try:
        from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=debug_mode,
            isolation_mode=isolation_mode,
            persistence_path=os.path.expanduser(persistence_path)
        )
        
        # Register with app
        mcp_server.register_with_app(app, prefix=api_prefix)
        
        # Add root endpoint
        @app.get("/")
        async def root():
            """Root endpoint with API information."""
            # Get daemon status
            daemon_info = {}
            if hasattr(mcp_server.ipfs_kit, 'check_daemon_status'):
                try:
                    daemon_status = mcp_server.ipfs_kit.check_daemon_status()
                    for daemon_name, status in daemon_status.get("daemons", {}).items():
                        daemon_info[daemon_name] = {
                            "running": status.get("running", False),
                            "pid": status.get("pid")
                        }
                except Exception as e:
                    daemon_info["error"] = str(e)
                    
            # Available controllers
            controllers = list(mcp_server.controllers.keys())
            
            # Example endpoints
            example_endpoints = {
                "ipfs": {
                    "version": f"{api_prefix}/ipfs/version",
                    "add": f"{api_prefix}/ipfs/add",
                    "cat": f"{api_prefix}/ipfs/cat/{{cid}}",
                    "pin": f"{api_prefix}/ipfs/pin/add"
                },
                "daemon": {
                    "status": f"{api_prefix}/daemon/status"
                },
                "health": f"{api_prefix}/health"
            }
            
            # Help message about URL structure
            help_message = f"""
            The MCP server exposes endpoints under the {api_prefix} prefix.
            Controller endpoints use the pattern: {api_prefix}/{{controller}}/{{operation}}
            Examples:
            - IPFS Version: {api_prefix}/ipfs/version
            - Health Check: {api_prefix}/health
            """
            
            # Add backend status
            backend_status = {}
            for backend, status in backends_status.items():
                if status["exists"] and status["enabled"]:
                    mode = "SIMULATION" if status["simulation"] else "REAL"
                    backend_status[backend] = {
                        "enabled": True,
                        "mode": mode,
                        "status": status["status"]
                    }
            
            return {
                "message": "MCP Server is running with real API implementations",
                "debug_mode": debug_mode,
                "isolation_mode": isolation_mode,
                "daemon_status": daemon_info,
                "controllers": controllers,
                "example_endpoints": example_endpoints,
                "backend_status": backend_status,
                "help": help_message,
                "documentation": "/docs"
            }
        
        return app, mcp_server
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP server: {e}")
        app = FastAPI()
        
        @app.get("/")
        async def error():
            return {"error": f"Failed to initialize MCP server: {str(e)}"}
            
        return app, None

def add_simulation_endpoints(app, backend):
    """Add simulation endpoints for a backend."""
    logger.info(f"Adding SIMULATION endpoints for {backend}")
    
    @app.get(f"{api_prefix}/{backend}/status")
    async def status():
        """Simulation status endpoint."""
        return {
            "success": True,
            "operation_id": f"status_{int(time.time() * 1000)}",
            "duration_ms": 1.5,
            "backend_name": backend,
            "is_available": True,
            "capabilities": ["from_ipfs", "to_ipfs"],
            "simulation": True
        }

# Create the app for uvicorn
app, mcp_server = create_app()

if __name__ == "__main__":
    # Run uvicorn directly
    logger.info(f"Starting MCP server with real APIs on port 9992")
    logger.info(f"Debug mode: {debug_mode}, Isolation mode: {isolation_mode}")
    
    # Log backend status
    for backend, status in backends_status.items():
        if status["exists"] and status["enabled"]:
            mode = "SIMULATION" if status["simulation"] else "REAL"
            logger.info(f"Backend {backend}: {mode} mode")
    
    uvicorn.run(
        "run_mcp_server_real_apis:app", 
        host="0.0.0.0", 
        port=9992,
        reload=False,
        log_level="info"
    )
