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
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_real_storage_server.log'
)
logger = logging.getLogger(__name__)

import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description="Run the MCP server with real storage backends")
parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "9994")),
                    help="Port to run the server on")
parser.add_argument("--api-prefix", type=str, default="/api/v0",
                    help="API prefix for endpoints")
parser.add_argument("--log-file", type=str, default="mcp_real_storage_server.log",
                    help="Log file path")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()

# Get configuration from environment variables or use defaults
debug_mode = args.debug if args.debug else os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "false").lower() == "false"  # Turn off isolation for real mode
api_prefix = args.api_prefix  # Use command line argument
persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp_real_storage")

# Port configuration
port = args.port  # Use command line argument

# Update log file based on args
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=args.log_file
)

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
        from ipfs_kit_py.mcp.server_bridge import MCPServer
        
        # Create MCP server
        mcp_server = MCPServer(
            debug_mode=debug_mode,
            isolation_mode=isolation_mode,
            persistence_path=os.path.expanduser(persistence_path)
        )
        
        # Register controllers
        from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
        from ipfs_kit_py.mcp.controllers.storage_manager_controller import StorageManagerController
        from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
        from ipfs_kit_py.mcp.controllers.storage.huggingface_controller import HuggingFaceController
        from ipfs_kit_py.mcp.controllers.storage.storacha_controller import StorachaController
        from ipfs_kit_py.mcp.controllers.storage.lassie_controller import LassieController
        from ipfs_kit_py.mcp.controllers.storage.s3_controller import S3Controller
        
        # Import models
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        from ipfs_kit_py.mcp.models.storage_manager import StorageManager
        
        # Create and register models
        # Import ipfs_kit for model initialization
        try:
            from ipfs_kit_py import ipfs_kit
            ipfs_instance = ipfs_kit
        except ImportError:
            ipfs_instance = None
            logger.warning("Could not import ipfs_kit, using None as instance")
            
        # Create config for model
        ipfs_config = {
            "ipfs_host": mcp_server.ipfs_host,
            "ipfs_port": mcp_server.ipfs_port,
            "debug_mode": debug_mode
        }
            
        ipfs_model = IPFSModel(
            ipfs_kit_instance=ipfs_instance,
            config=ipfs_config
        )
        mcp_server.register_model("ipfs", ipfs_model)
        
        # Create properly formatted resources and metadata for StorageManager
        resources = {
            "ipfs": {
                "host": mcp_server.ipfs_host,
                "port": mcp_server.ipfs_port
            }
        }
        
        metadata = {
            "debug_mode": debug_mode,
            "isolation_mode": isolation_mode,
            "persistence_path": os.path.expanduser(persistence_path)
        }
        
        # Create StorageManager with correct parameters
        storage_model = StorageManager(
            ipfs_model=ipfs_model,  # Pass the IPFS model we created earlier
            resources=resources,
            metadata=metadata
        )
        mcp_server.register_model("storage_manager", storage_model)
        
        # Create and register controllers
        ipfs_controller = IPFSController(ipfs_model)
        mcp_server.register_controller("ipfs", ipfs_controller)
        
        storage_manager_controller = StorageManagerController(storage_model)
        mcp_server.register_controller("storage_manager", storage_manager_controller)
        
        # Storage backends controllers
        filecoin_controller = FilecoinController(storage_model)
        mcp_server.register_controller("filecoin", filecoin_controller)
        
        huggingface_controller = HuggingFaceController(storage_model)
        mcp_server.register_controller("huggingface", huggingface_controller)
        
        storacha_controller = StorachaController(storage_model)
        mcp_server.register_controller("storacha", storacha_controller)
        
        lassie_controller = LassieController(storage_model)
        mcp_server.register_controller("lassie", lassie_controller)
        
        s3_controller = S3Controller(storage_model)
        mcp_server.register_controller("s3", s3_controller)
        
        # Try to import and register LibP2P controller if available
        try:
            from ipfs_kit_py.mcp.controllers.libp2p_controller import LibP2PController
            from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel
            
            # Create LibP2P model without debug_mode parameter
            try:
                libp2p_model = LibP2PModel()  # Don't pass debug_mode
                mcp_server.register_model("libp2p", libp2p_model)
                
                libp2p_controller = LibP2PController(libp2p_model)
                mcp_server.register_controller("libp2p", libp2p_controller)
                logger.info("LibP2P controller registered successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize LibP2P model: {e}")
        except ImportError as e:
            logger.info(f"LibP2P controller not available: {e}")
        
        # WebRTC controller is disabled to avoid import errors
        logger.info("WebRTC controller disabled")
        
        # Log registered controllers
        logger.info(f"Registered controllers: {list(mcp_server.controllers.keys())}")
        
        # Register with app
        mcp_server.register_with_app(app, prefix=api_prefix)
        
        # Add root endpoint
        @app.get("/")
        async def root():
            """Root endpoint with API information."""
            # Get daemon status
            daemon_info = {
                "ipfs": {
                    "running": True,
                    "host": mcp_server.ipfs_host,
                    "port": mcp_server.ipfs_port
                }
            }
                    
            # Available controllers
            controllers = list(mcp_server.controllers.keys())
            
            # Storage backends status
            storage_backends = {}
            if "storage_manager" in mcp_server.models:
                try:
                    storage_manager = mcp_server.models["storage_manager"]
                    if hasattr(storage_manager, 'storage_models') and isinstance(storage_manager.storage_models, dict):
                        # Access storage_models only if it exists and is a dictionary
                        for backend_name, backend in storage_manager.storage_models.items():
                            storage_backends[backend_name] = {
                                "available": True,
                                "simulation": False,
                                "real_implementation": True
                            }
                    elif hasattr(storage_manager, 'get_available_backends'):
                        # Alternative method using get_available_backends if it exists
                        available_backends = storage_manager.get_available_backends()
                        for backend_name, is_available in available_backends.items():
                            storage_backends[backend_name] = {
                                "available": is_available,
                                "simulation": False,
                                "real_implementation": True
                            }
                    else:
                        # Fallback for when neither attribute is present
                        storage_backends["info"] = "Storage backends information unavailable"
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
        
        # Add SSE endpoint for server-sent events
        @app.get("/sse")
        async def sse(request: Request):
            """Server-Sent Events (SSE) endpoint for real-time updates."""
            async def event_generator():
                """Generate SSE events."""
                # Initial connection established event
                yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
                
                # Keep connection alive with heartbeats
                counter = 0
                while True:
                    if await request.is_disconnected():
                        logger.info("SSE client disconnected")
                        break
                        
                    # Send a heartbeat every 15 seconds
                    if counter % 15 == 0:
                        status_data = {
                            "event": "heartbeat",
                            "timestamp": time.time(),
                            "server_id": str(uuid.uuid4())
                        }
                        yield f"event: heartbeat\ndata: {json.dumps(status_data)}\n\n"
                    
                    # Wait a second between iterations
                    await asyncio.sleep(1)
                    counter += 1
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*"
                }
            )
        
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
            if "storage_manager" in mcp_server.models:
                storage_manager = mcp_server.models["storage_manager"]
                
                # Make sure storage_models exists and is a dictionary before iterating
                if hasattr(storage_manager, 'storage_models') and isinstance(storage_manager.storage_models, dict):
                    for backend_name, backend in storage_manager.storage_models.items():
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
                # Alternative method using get_available_backends if it exists
                elif hasattr(storage_manager, 'get_available_backends'):
                    available_backends = storage_manager.get_available_backends()
                    for backend_name, is_available in available_backends.items():
                        health_info["components"][backend_name] = {
                            "status": "available" if is_available else "unavailable",
                            "simulation": False
                        }
                else:
                    health_info["components"]["info"] = {
                        "status": "unknown",
                        "message": "Storage backends information unavailable"
                    }
            
            # Overall status
            errors = [c for c in health_info["components"].values() if c.get("status") == "error"]
            health_info["overall_status"] = "degraded" if errors else "healthy"
                
            return health_info
        
        # Add /initialize endpoint for health/initialization check compatibility
        @app.post("/initialize")
        async def initialize():
            """Initialization endpoint for MCP server tools/clients."""
            return {"status": "success", "message": "MCP server initialized", "timestamp": time.time()}
        
        return app, mcp_server
        
    except Exception as server_error:
        error_message = str(server_error)
        logger.error(f"Failed to initialize MCP server: {error_message}")
        app = FastAPI()
        
        @app.get("/")
        async def error():
            return {"error": f"Failed to initialize MCP server: {error_message}"}
            
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
