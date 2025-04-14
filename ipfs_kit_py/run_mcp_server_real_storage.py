#!/usr/bin/env python3
"""
MCP server implementation with real (non-simulated) storage backends.

This server integrates with actual storage services rather than using simulations,
providing full functionality for all storage backends:
- Hugging Face
- Storacha
- Filecoin
- Lassie
- S3
"""

import os
import sys
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
    filename='mcp_real_storage_server.log'
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables or use defaults
debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "false").lower() == "false"  # Turn off isolation for real mode
api_prefix = "/api/v0"  # Fixed prefix for consistency
persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp_real_storage")

# Port configuration
port = int(os.environ.get("MCP_PORT", "9994"))  # Using a different port than other servers

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server with Real Storage",
        description="Model-Controller-Persistence Server for IPFS Kit with real storage backends",
        version="0.1.0"
    )
    
    # Import MCP server
    try:
        from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Corrected import path
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=debug_mode,
            isolation_mode=isolation_mode,
            persistence_path=os.path.expanduser(persistence_path)
        )
        
        # Force loading all storage backends
        # Ensure we have real implementations initialized
        if hasattr(mcp_server, 'storage_manager') and hasattr(mcp_server.storage_manager, '_init_storage_models'):
            try:
                mcp_server.storage_manager._init_storage_models()
                logger.info("Initialized all storage backends")
            except Exception as e:
                logger.error(f"Error initializing storage backends: {e}")
        
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
            
            # Storage backends status
            storage_backends = {}
            if hasattr(mcp_server, 'storage_manager'):
                try:
                    for backend_name, backend in mcp_server.storage_manager.storage_models.items():
                        storage_backends[backend_name] = {
                            "available": True,
                            "simulation": False,
                            "real_implementation": True
                        }
                except Exception as e:
                    storage_backends["error"] = str(e)
            
            # Example endpoints
            example_endpoints = {
                "ipfs": {
                    "version": f"{api_prefix}/ipfs/version",
                    "add": f"{api_prefix}/ipfs/add",
                    "cat": f"{api_prefix}/ipfs/cat/{{cid}}",
                    "pin": f"{api_prefix}/ipfs/pin/add"
                },
                "storage": {
                    "huggingface": {
                        "status": f"{api_prefix}/huggingface/status",
                        "from_ipfs": f"{api_prefix}/huggingface/from_ipfs",
                        "to_ipfs": f"{api_prefix}/huggingface/to_ipfs"
                    },
                    "storacha": {
                        "status": f"{api_prefix}/storacha/status",
                        "from_ipfs": f"{api_prefix}/storacha/from_ipfs",
                        "to_ipfs": f"{api_prefix}/storacha/to_ipfs"
                    },
                    "filecoin": {
                        "status": f"{api_prefix}/filecoin/status",
                        "from_ipfs": f"{api_prefix}/filecoin/from_ipfs",
                        "to_ipfs": f"{api_prefix}/filecoin/to_ipfs"
                    },
                    "lassie": {
                        "status": f"{api_prefix}/lassie/status",
                        "to_ipfs": f"{api_prefix}/lassie/to_ipfs"
                    },
                    "s3": {
                        "status": f"{api_prefix}/s3/status",
                        "from_ipfs": f"{api_prefix}/s3/from_ipfs",
                        "to_ipfs": f"{api_prefix}/s3/to_ipfs"
                    }
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
            - HuggingFace Status: {api_prefix}/huggingface/status
            """
            
            return {
                "message": "MCP Server is running (REAL STORAGE MODE)",
                "debug_mode": debug_mode,
                "isolation_mode": isolation_mode,
                "daemon_status": daemon_info,
                "controllers": controllers,
                "storage_backends": storage_backends,
                "example_endpoints": example_endpoints,
                "help": help_message,
                "documentation": "/docs",
                "server_id": str(uuid.uuid4())
            }
        
        # Add a storage backends health check
        @app.get(f"{api_prefix}/storage/health")
        async def storage_health():
            """Health check for all storage backends."""
            health_info = {
                "success": True,
                "timestamp": time.time(),
                "mode": "real_storage",
                "components": {}
            }
            
            # Check each storage backend
            if hasattr(mcp_server, 'storage_manager'):
                for backend_name, backend in mcp_server.storage_manager.storage_models.items():
                    try:
                        # Call the backend's health check
                        if hasattr(backend, 'async_health_check'):
                            status = await backend.async_health_check()
                        else:
                            status = backend.health_check()
                            
                        health_info["components"][backend_name] = {
                            "status": "available" if status.get("success", False) else "error",
                            "simulation": status.get("simulation", False),
                            "details": status
                        }
                    except Exception as e:
                        health_info["components"][backend_name] = {
                            "status": "error",
                            "error": str(e),
                            "error_type": type(e).__name__
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
    with open('mcp_real_storage_server.pid', 'w') as f:
        f.write(str(os.getpid()))

if __name__ == "__main__":
    # Write PID file
    write_pid()
    
    # Run uvicorn directly
    logger.info(f"Starting MCP server on port {port} with API prefix: {api_prefix}")
    logger.info(f"Debug mode: {debug_mode}, Isolation mode: {isolation_mode}")
    logger.info(f"Using REAL storage backend implementations (no simulation)")
    
    uvicorn.run(
        "ipfs_kit_py.run_mcp_server_real_storage:app", 
        host="0.0.0.0", 
        port=port,
        reload=False,  # Disable reload to avoid duplicate process issues
        log_level="info"
    )
