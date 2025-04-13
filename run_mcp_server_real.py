#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by run_mcp_server_unified.py

This file is kept for reference only. Please use the unified script instead,
which provides all functionality with more options:

    python run_mcp_server_unified.py --help

Backup of the original script is at: run_mcp_server_real.py.bak_20250412_202314
"""

# Original content follows:

#!/usr/bin/env python3
"""
MCP server implementation using actual API calls instead of simulation.
"""

import os
import logging
import time
import uuid
import asyncio
from fastapi import FastAPI, APIRouter

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_server_real.log'
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables or use defaults
debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "false").lower() == "true"  # Turn off isolation for real mode
api_prefix = "/api/v0"  # Fixed prefix for consistency
persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp")

# Port configuration
port = int(os.environ.get("MCP_PORT", "9992"))  # Using a different port than simulation

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Import MCP server
    try:
        from ipfs_kit_py.mcp.server import MCPServer
        
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
            
            return {
                "message": "MCP Server is running (REAL API MODE)",
                "debug_mode": debug_mode,
                "isolation_mode": isolation_mode,
                "daemon_status": daemon_info,
                "controllers": controllers,
                "example_endpoints": example_endpoints,
                "help": help_message,
                "documentation": "/docs",
                "server_id": str(uuid.uuid4())
            }
        
        # Add a health check that verifies IPFS daemon is actually running
        @app.get(f"{api_prefix}/real_health")
        async def real_health():
            """Health check that verifies actual daemon connectivity."""
            health_info = {
                "success": True,
                "timestamp": time.time(),
                "mode": "actual_api",
                "components": {}
            }
            
            # Check IPFS daemon
            try:
                ipfs_controller = mcp_server.controllers.get("ipfs")
                if ipfs_controller:
                    version = await ipfs_controller.version()
                    health_info["components"]["ipfs"] = {
                        "status": "connected",
                        "version": version.get("version", "unknown")
                    }
                else:
                    health_info["components"]["ipfs"] = {
                        "status": "error",
                        "message": "IPFS controller not found"
                    }
            except Exception as e:
                health_info["components"]["ipfs"] = {
                    "status": "error",
                    "message": str(e)
                }
                
            # Check storage backends
            for backend in ["storage_huggingface", "storage_storacha", "storage_filecoin", "storage_lassie", "s3"]:
                controller = mcp_server.controllers.get(backend)
                if controller:
                    try:
                        # Just check if the controller exists - we'll do deeper checks later
                        health_info["components"][backend] = {
                            "status": "available"
                        }
                    except Exception as e:
                        health_info["components"][backend] = {
                            "status": "error",
                            "message": str(e)
                        }
                else:
                    health_info["components"][backend] = {
                        "status": "not_available"
                    }
                    
            # Overall status
            errors = [c for c in health_info["components"].values() if c.get("status") == "error"]
            health_info["overall_status"] = "degraded" if errors else "healthy"
                
            return health_info
        
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
    with open('mcp_real_server.pid', 'w') as f:
        f.write(str(os.getpid()))

if __name__ == "__main__":
    # Write PID file
    write_pid()
    
    # Run uvicorn directly
    logger.info(f"Starting MCP server on port {port} with API prefix: {api_prefix}")
    logger.info(f"Debug mode: {debug_mode}, Isolation mode: {isolation_mode}")
    logger.info(f"Using REAL API implementations (no simulation)")
    
    uvicorn.run(
        "run_mcp_server_real:app", 
        host="0.0.0.0", 
        port=port,
        reload=False,  # Disable reload to avoid duplicate process issues
        log_level="info"
    )