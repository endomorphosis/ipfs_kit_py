#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_server_real_apis.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_server_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by run_mcp_server_unified.py

This file is kept for reference only. Please use the unified script instead,
which provides all functionality with more options:

    python run_mcp_server_unified.py --help

Backup of the original script is at: run_mcp_server_real_apis.py.bak_20250412_202314
"""

# Original content follows:

#!/usr/bin/env python3
"""
MCP server with real API implementations for storage backends.
"""

import os
import sys
import logging
import time
import json
from pathlib import Path
import importlib.util
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

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

# Configuration paths
CONFIG_DIR = Path.home() / ".ipfs_kit"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

def load_credentials():
    """Load credentials from file."""
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
    return {}

# Load the credentials
credentials = load_credentials()

# Backend implementations
backend_implementations = {}

# Try loading HuggingFace implementation
try:
    spec = importlib.util.spec_from_file_location("huggingface_real_api", "huggingface_real_api.py")
    huggingface_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(huggingface_module)
    logger.info("Loaded HuggingFace real API implementation")
    
    # Get token from credentials
    hf_token = credentials.get("huggingface", {}).get("token")
    
    # Create implementation
    huggingface_api = huggingface_module.HuggingFaceRealAPI(
        token=hf_token,
        simulation_mode=os.environ.get("HUGGINGFACE_SIMULATION", "1") == "1"
    )
    
    backend_implementations["huggingface"] = huggingface_api
    logger.info(f"HuggingFace API initialized (simulation: {huggingface_api.simulation_mode})")
except Exception as e:
    logger.error(f"Error loading HuggingFace implementation: {e}")

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit",
        version="0.1.0"
    )
    
    # Add backend-specific endpoints
    add_backend_endpoints(app)
    
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
            for backend, impl in backend_implementations.items():
                status_info = impl.status()
                backend_status[backend] = {
                    "available": status_info.get("is_available", False),
                    "simulation": status_info.get("simulation", True),
                    "capabilities": status_info.get("capabilities", [])
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

def add_backend_endpoints(app):
    """Add backend-specific endpoints to the app."""
    # HuggingFace endpoints
    if "huggingface" in backend_implementations:
        hf_api = backend_implementations["huggingface"]
        
        @app.get(f"{api_prefix}/huggingface/status")
        async def huggingface_status():
            """Get HuggingFace backend status."""
            return hf_api.status()
        
        @app.post(f"{api_prefix}/huggingface/from_ipfs")
        async def huggingface_from_ipfs(request: Request):
            """Transfer content from IPFS to HuggingFace."""
            data = await request.json()
            cid = data.get("cid")
            repo_id = data.get("repo_id")
            path_in_repo = data.get("path_in_repo")
            
            if not cid:
                return JSONResponse(
                    status_code=422,
                    content={"success": False, "error": "CID is required"}
                )
                
            if not repo_id:
                return JSONResponse(
                    status_code=422,
                    content={"success": False, "error": "Repository ID is required"}
                )
            
            return hf_api.from_ipfs(cid=cid, repo_id=repo_id, path_in_repo=path_in_repo)
        
        @app.post(f"{api_prefix}/huggingface/to_ipfs")
        async def huggingface_to_ipfs(request: Request):
            """Transfer content from HuggingFace to IPFS."""
            data = await request.json()
            repo_id = data.get("repo_id")
            path_in_repo = data.get("path_in_repo")
            
            if not repo_id:
                return JSONResponse(
                    status_code=422,
                    content={"success": False, "error": "Repository ID is required"}
                )
                
            if not path_in_repo:
                return JSONResponse(
                    status_code=422,
                    content={"success": False, "error": "Path in repository is required"}
                )
            
            return hf_api.to_ipfs(repo_id=repo_id, path_in_repo=path_in_repo)

# Create the app for uvicorn
app, mcp_server = create_app()

if __name__ == "__main__":
    # Run uvicorn directly
    logger.info(f"Starting MCP server with real APIs on port 9992")
    logger.info(f"Debug mode: {debug_mode}, Isolation mode: {isolation_mode}")
    
    # Log backend status
    for backend, impl in backend_implementations.items():
        status = impl.status()
        mode = "SIMULATION" if status.get("simulation", True) else "REAL"
        logger.info(f"Backend {backend}: {mode} mode, Available: {status.get('is_available', False)}")
    
    uvicorn.run(
        "run_mcp_server_real_apis:app", 
        host="0.0.0.0", 
        port=9992,
        reload=False,
        log_level="info"
    )
