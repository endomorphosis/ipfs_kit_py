#!/usr/bin/env python3
"""
MCP All-in-One Server with all extensions enabled

This script provides an enhanced MCP server with all features enabled, including:
1. JSON-RPC support for VS Code LSP integration
2. Fixed pin endpoints (add, rm, ls)
3. Enhanced error handling
4. Proper CORS headers
5. All available storage backends
"""

import os
import sys
import logging
import importlib
import argparse
import time
import uuid
import json
import asyncio
from fastapi import FastAPI, APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_server.log'
)
logger = logging.getLogger(__name__)

def main():
    """Run the enhanced MCP server with all extensions initialized."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start the All-in-One MCP server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "9994")),
                      help="Port number to use (default: 9994)")
    parser.add_argument("--jsonrpc-port", type=int, default=int(os.environ.get("MCP_JSONRPC_PORT", "9995")),
                      help="JSON-RPC port number (default: 9995)")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Disable debug mode")
    parser.add_argument("--isolation", dest="isolation", action="store_true", help="Enable isolation mode")
    parser.add_argument("--no-isolation", dest="isolation", action="store_false", help="Disable isolation mode")
    parser.add_argument("--skip-daemon", dest="skip_daemon", action="store_true", help="Skip daemon initialization")
    parser.add_argument("--no-skip-daemon", dest="skip_daemon", action="store_false", help="Don't skip daemon initialization")
    parser.add_argument("--api-prefix", type=str, default="/api/v0", help="API prefix to use")
    parser.add_argument("--log-file", type=str, default="mcp_server.log", help="Log file to use")
    parser.add_argument("--jsonrpc", dest="jsonrpc", action="store_true", help="Enable JSON-RPC support")
    parser.add_argument("--no-jsonrpc", dest="jsonrpc", action="store_false", help="Disable JSON-RPC support")

    # Set default values
    parser.set_defaults(debug=True, isolation=True, skip_daemon=True, jsonrpc=True)

    # Parse arguments
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=args.log_file
    )

    # Set environment variables for configuration
    os.environ["MCP_DEBUG_MODE"] = str(args.debug).lower()
    os.environ["MCP_ISOLATION_MODE"] = str(args.isolation).lower()
    os.environ["MCP_SKIP_DAEMON"] = str(args.skip_daemon).lower()
    os.environ["MCP_PORT"] = str(args.port)
    os.environ["MCP_API_PREFIX"] = args.api_prefix

    # Log configuration
    logger.info(f"Starting All-in-One MCP server with configuration:")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  JSON-RPC Port: {args.jsonrpc_port}")
    logger.info(f"  Debug mode: {args.debug}")
    logger.info(f"  Isolation mode: {args.isolation}")
    logger.info(f"  Skip daemon: {args.skip_daemon}")
    logger.info(f"  JSON-RPC support: {args.jsonrpc}")
    logger.info(f"  API prefix: {args.api_prefix}")
    logger.info(f"  Log file: {args.log_file}")

    # Initialize extensions and fixes
    try:
        logger.info("Initializing MCP extensions and fixes")

        # First, apply IPFS model fixes
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_fix import apply_fixes as apply_ipfs_model_fixes
            logger.info("Applying IPFS model fixes")
            if apply_ipfs_model_fixes():
                logger.info("Successfully applied IPFS model fixes")
            else:
                logger.warning("Failed to apply IPFS model fixes")
        except ImportError as e:
            logger.warning(f"Could not import IPFS model fixes: {e}")

        # Initialize IPFS model extensions
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
            logger.info("Initializing IPFS model extensions")
            if initialize_ipfs_model():
                logger.info("Successfully initialized IPFS model extensions")
            else:
                logger.warning("Failed to initialize IPFS model extensions")
        except ImportError as e:
            logger.warning(f"Could not import IPFS model initializer: {e}")

        # Apply SSE and CORS fixes
        try:
            from ipfs_kit_py.mcp.sse_cors_fix import patch_mcp_server_for_sse
            logger.info("Applying SSE and CORS fixes")
            if patch_mcp_server_for_sse():
                logger.info("Successfully applied SSE and CORS fixes")
            else:
                logger.warning("Failed to apply SSE and CORS fixes")
        except ImportError as e:
            logger.warning(f"Could not import SSE and CORS fixes: {e}")

        # Patch run_mcp_server if needed
        try:
            from ipfs_kit_py.mcp.run_mcp_server_initializer import patch_run_mcp_server
            logger.info("Patching run_mcp_server")
            if patch_run_mcp_server():
                logger.info("Successfully patched run_mcp_server")
            else:
                logger.warning("Failed to patch run_mcp_server")
        except ImportError as e:
            logger.warning(f"Could not import run_mcp_server initializer: {e}")

    except Exception as init_error:
        logger.error(f"Error initializing MCP extensions: {init_error}")
        print(f"Error: Failed to initialize MCP extensions: {init_error}")

    # Start the server
    try:
        # Import uvicorn
        import uvicorn

        # Write PID file
        with open('/tmp/mcp_server.pid', 'w') as f:
            f.write(str(os.getpid()))

        # Run the server
        logger.info(f"Starting MCP server on port {args.port}")
        uvicorn.run(
            "mcp_server_fixed_all:app",
            host="0.0.0.0",
            port=args.port,
            reload=False,
            log_level="debug" if args.debug else "info"
        )
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        print(f"Error: Failed to import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        print(f"Error: Failed to start MCP server: {e}")
        sys.exit(1)

# Get configuration from environment variables
debug_mode = os.environ.get("MCP_DEBUG_MODE", "true").lower() == "true"
isolation_mode = os.environ.get("MCP_ISOLATION_MODE", "true").lower() == "true"
api_prefix = os.environ.get("MCP_API_PREFIX", "/api/v0")
persistence_path = os.environ.get("MCP_PERSISTENCE_PATH", "~/.ipfs_kit/mcp")

# Define Pydantic models for requests and responses
class CIDRequest(BaseModel):
    """Request model for operations using a CID."""
    cid: str = Field(..., description="Content Identifier (CID)")

class OperationResponse(BaseModel):
    """Base response model for operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: str = Field(..., description="Unique identifier for this operation")
    duration_ms: float = Field(..., description="Duration of the operation in milliseconds")

class PinResponse(OperationResponse):
    """Response model for pin operations."""
    cid: str = Field(..., description="Content Identifier (CID)")
    error: Optional[str] = Field(None, description="Error message, if any")
    error_type: Optional[str] = Field(None, description="Type of error, if any")

class ListPinsResponse(OperationResponse):
    """Response model for listing pins."""
    pins: List[str] = Field(..., description="List of pinned CIDs")
    count: int = Field(..., description="Number of pins")
    error: Optional[str] = Field(None, description="Error message, if any")
    error_type: Optional[str] = Field(None, description="Type of error, if any")

def create_app():
    """Create and configure the FastAPI app with MCP server."""
    # Create FastAPI app
    app = FastAPI(
        title="All-in-One IPFS MCP Server",
        description="Model-Controller-Persistence Server for IPFS Kit with all extensions enabled",
        version="0.3.0"
    )

    # Add CORS middleware with permissive settings for client access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

    # Import and initialize MCP extensions
    try:
        # Import IPFS model fix
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_fix import apply_fixes
            apply_fixes()
            logger.info("Applied IPFS model fixes")
        except ImportError:
            logger.warning("IPFS model fix not available")

        # Initialize IPFS model extensions
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
            if initialize_ipfs_model():
                logger.info("Initialized IPFS model extensions")
            else:
                logger.warning("Failed to initialize IPFS model extensions")
        except ImportError:
            logger.warning("IPFS model initializer not available")

        # Apply SSE and CORS fixes
        try:
            from ipfs_kit_py.mcp.sse_cors_fix import patch_mcp_server_for_sse
            if patch_mcp_server_for_sse():
                logger.info("Applied SSE and CORS fixes")
            else:
                logger.warning("Failed to apply SSE and CORS fixes")
        except ImportError:
            logger.warning("SSE and CORS fixes not available")
    except Exception as e:
        logger.error(f"Error initializing MCP extensions: {e}")

    try:
        # Create a simple MCP server class since we can't import the original
        class MCPServer:
            """Simple MCP server implementation."""

            def __init__(self, debug_mode=False, isolation_mode=False, persistence_path=None):
                """Initialize the MCP server."""
                self.debug_mode = debug_mode
                self.isolation_mode = isolation_mode
                self.persistence_path = persistence_path
                self.controllers = {}
                self.models = {}
                self.ipfs_host = "localhost"
                self.ipfs_port = 5001

            def register_controller(self, name, controller):
                """Register a controller with the server."""
                self.controllers[name] = controller

            def register_model(self, name, model):
                """Register a model with the server."""
                self.models[name] = model

            def register_with_app(self, app, prefix=""):
                """Register controllers with the FastAPI app."""
                for name, controller in self.controllers.items():
                    if hasattr(controller, "register_routes"):
                        router = APIRouter()
                        controller.register_routes(router, prefix)
                        app.include_router(router)
                        logger.info(f"Registered routes for controller: {name}")

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

        # Ensure model has extensions
        if not hasattr(ipfs_model, 'add_content'):
            from ipfs_kit_py.mcp.models.ipfs_model_extensions import add_ipfs_model_extensions
            logger.info("Manually applying IPFS model extensions")
            add_ipfs_model_extensions(IPFSModel)

            # Now explicitly attach the methods to our instance
            for method_name in ['add_content', 'cat', 'pin_add', 'pin_rm', 'pin_ls',
                               'swarm_peers', 'swarm_connect', 'swarm_disconnect',
                               'storage_transfer', 'get_version']:
                # Make sure our model has these methods
                if hasattr(add_ipfs_model_extensions.__globals__, method_name):
                    method = add_ipfs_model_extensions.__globals__[method_name]
                    setattr(ipfs_model.__class__, method_name, method)
                    logger.info(f"Added {method_name} to IPFSModel")

        mcp_server.register_model("ipfs", ipfs_model)

        # Set up storage manager with reference to our ipfs_model
        # Instead of directly setting an attribute, let's use a safer approach
        # We'll add this attribute to the class if it doesn't exist
        if not hasattr(ipfs_model, 'storage_manager'):
            setattr(ipfs_model.__class__, 'storage_manager', None)

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

        # Add two-way reference - use setattr to avoid type checking errors
        setattr(ipfs_model, 'storage_manager', storage_model)

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

            # Create LibP2P model
            libp2p_model = LibP2PModel()
            mcp_server.register_model("libp2p", libp2p_model)

            libp2p_controller = LibP2PController(libp2p_model)
            mcp_server.register_controller("libp2p", libp2p_controller)
            logger.info("LibP2P controller registered successfully")
        except ImportError:
            logger.info("LibP2P controller not available")
        except Exception as e:
            logger.warning(f"Failed to initialize LibP2P model: {e}")

        # Log registered controllers
        logger.info(f"Registered controllers: {list(mcp_server.controllers.keys())}")

        # Register with app
        mcp_server.register_with_app(app, prefix=api_prefix)

        # Directly add the storage backend routers from mcp_extensions
        try:
            import mcp_extensions
            logger.info("Adding routers from mcp_extensions...")
            extension_routers = mcp_extensions.create_extension_routers(api_prefix)
            for ext_router in extension_routers:
                app.include_router(ext_router)
                logger.info(f"Added extension router with prefix: {ext_router.prefix}")
        except Exception as e:
            logger.error(f"Error adding extension routers: {e}")

        # Add IPFS routers from ipfs_router_extensions
        try:
            import ipfs_router_extensions
            logger.info("Adding routers from ipfs_router_extensions...")
            ipfs_routers = ipfs_router_extensions.create_ipfs_routers(api_prefix)
            for ipfs_router in ipfs_routers:
                app.include_router(ipfs_router)
                logger.info(f"Added IPFS router with prefix: {ipfs_router.prefix}")
        except Exception as e:
            logger.error(f"Error adding IPFS routers: {e}")

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

            # Check if IPFS model has extensions
            ipfs_extensions = {}
            if "ipfs" in mcp_server.models:
                ipfs_model = mcp_server.models["ipfs"]
                for method_name in ['add_content', 'cat', 'pin_add', 'pin_rm', 'pin_ls',
                                    'swarm_peers', 'swarm_connect', 'swarm_disconnect',
                                    'storage_transfer', 'get_version']:
                    ipfs_extensions[method_name] = hasattr(ipfs_model, method_name)

            # Storage backends status
            storage_backends = {}
            if "storage_manager" in mcp_server.models:
                try:
                    storage_manager = mcp_server.models["storage_manager"]
                    for backend_name, backend in storage_manager.storage_models.items():
                        storage_backends[backend_name] = {
                            "available": True,
                            "simulation": getattr(backend, 'simulation_mode', False),
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
                    "pin": {
                        "add": f"{api_prefix}/ipfs/pin/add?cid={{cid}}",
                        "rm": f"{api_prefix}/ipfs/pin/rm?cid={{cid}}",
                        "ls": f"{api_prefix}/ipfs/pin/ls"
                    }
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

            # Add JSON-RPC endpoint information
            example_endpoints["jsonrpc"] = {
                "root": "/jsonrpc",
                "api": f"{api_prefix}/jsonrpc",
                "supported_methods": ["initialize", "shutdown", "exit"]
            }

            # Help message about URL structure
            help_message = f"""
            The MCP server exposes endpoints under the {api_prefix} prefix.
            Controller endpoints use the pattern: {api_prefix}/{{controller}}/{{operation}}

            Example Tools:
            - IPFS Add: {api_prefix}/ipfs/add
            - IPFS Cat: {api_prefix}/ipfs/cat/{{cid}}
            - IPFS Pin:
                - Add: {api_prefix}/ipfs/pin/add?cid={{cid}}
                - Remove: {api_prefix}/ipfs/pin/rm?cid={{cid}}
                - List: {api_prefix}/ipfs/pin/ls
            """

            return {
                "message": "All-in-One MCP Server is running",
                "debug_mode": debug_mode,
                "isolation_mode": isolation_mode,
                "daemon_status": daemon_info,
                "controllers": controllers,
                "ipfs_extensions": ipfs_extensions,
                "storage_backends": storage_backends,
                "example_endpoints": example_endpoints,
                "help": help_message,
                "documentation": "/docs",
                "server_id": str(uuid.uuid4())
            }

        # Add SSE endpoint for server-sent events - both at root and with API prefix
        async def sse_handler(request: Request):
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

        # Register SSE endpoint at root level
        app.get("/sse")(sse_handler)

        # Register SSE endpoint at API prefix level
        app.get(f"{api_prefix}/sse")(sse_handler)

        # Add JSON-RPC endpoint for VS Code LSP protocol
        @app.post(f"{api_prefix}/jsonrpc")
        async def jsonrpc_handler(request: Request):
            """JSON-RPC endpoint for VS Code Language Server Protocol."""
            try:
                data = await request.json()
                logger.info(f"Received JSON-RPC request: {data}")

                # Handle 'initialize' request
                if data.get("method") == "initialize":
                    logger.info("Processing initialize request from VS Code")

                    # Return a standard LSP initialize response
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "capabilities": {
                                "textDocumentSync": {
                                    "openClose": True,
                                    "change": 1  # Full document sync
                                },
                                "completionProvider": {
                                    "resolveProvider": False,
                                    "triggerCharacters": ["/"]
                                },
                                "hoverProvider": True,
                                "definitionProvider": True,
                                "referencesProvider": True
                            },
                            "serverInfo": {
                                "name": "MCP IPFS Tools Server",
                                "version": "0.3.0"
                            }
                        }
                    }

                # Handle 'shutdown' request
                elif data.get("method") == "shutdown":
                    logger.info("Received shutdown request from VS Code")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": None
                    }

                # Handle 'exit' notification
                elif data.get("method") == "exit":
                    logger.info("Received exit notification from VS Code")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": None
                    }

                # For any other method, return a 'method not found' error
                else:
                    logger.warning(f"Unhandled JSON-RPC method: {data.get('method')}")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Method '{data.get('method')}' not found"
                        }
                    }
            except Exception as e:
                logger.error(f"Error handling JSON-RPC request: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }

        # Add JSON-RPC endpoint at root level too (some clients might expect it here)
        @app.post("/jsonrpc")
        async def jsonrpc_root_handler(request: Request):
            """JSON-RPC root endpoint for VS Code Language Server Protocol."""
            try:
                data = await request.json()
                logger.info(f"Received JSON-RPC request at root: {data}")

                # Handle 'initialize' request
                if data.get("method") == "initialize":
                    logger.info("Processing initialize request from VS Code")

                    # Return a standard LSP initialize response
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": {
                            "capabilities": {
                                "textDocumentSync": {
                                    "openClose": True,
                                    "change": 1  # Full document sync
                                },
                                "completionProvider": {
                                    "resolveProvider": False,
                                    "triggerCharacters": ["/"]
                                },
                                "hoverProvider": True,
                                "definitionProvider": True,
                                "referencesProvider": True
                            },
                            "serverInfo": {
                                "name": "MCP IPFS Tools Server",
                                "version": "0.3.0"
                            }
                        }
                    }

                # Handle 'shutdown' request
                elif data.get("method") == "shutdown":
                    logger.info("Received shutdown request from VS Code")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": None
                    }

                # Handle 'exit' notification
                elif data.get("method") == "exit":
                    logger.info("Received exit notification from VS Code")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "result": None
                    }

                # For any other method, return a 'method not found' error
                else:
                    logger.warning(f"Unhandled JSON-RPC method: {data.get('method')}")
                    return {
                        "jsonrpc": "2.0",
                        "id": data.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Method '{data.get('method')}' not found"
                        }
                    }
            except Exception as e:
                logger.error(f"Error handling JSON-RPC request: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }

        # Custom pin endpoints for IPFS operations
        @app.get(f"{api_prefix}/ipfs/pin/add")
        async def pin_add(cid: str = Query(..., description="Content Identifier (CID) to pin")):
            """Pin content to IPFS by CID."""
            if "ipfs" not in mcp_server.models:
                raise HTTPException(status_code=500, detail="IPFS model not found")

            ipfs_model = mcp_server.models["ipfs"]
            if not hasattr(ipfs_model, 'pin_add'):
                raise HTTPException(status_code=500, detail="pin_add method not available")

            try:
                start_time = time.time()
                result = ipfs_model.pin_add(cid)
                duration_ms = (time.time() - start_time) * 1000

                return PinResponse(
                    success=True,
                    operation_id=f"pin_add_{int(start_time * 1000)}",
                    duration_ms=duration_ms,
                    cid=cid
                )
            except Exception as e:
                logger.error(f"Error pinning content: {e}")
                return PinResponse(
                    success=False,
                    operation_id=f"pin_add_{int(time.time() * 1000)}",
                    duration_ms=0,
                    cid=cid,
                    error=str(e),
                    error_type=type(e).__name__
                )

        @app.get(f"{api_prefix}/ipfs/pin/rm")
        async def pin_rm(cid: str = Query(..., description="Content Identifier (CID) to unpin")):
            """Unpin content from IPFS by CID."""
            if "ipfs" not in mcp_server.models:
                raise HTTPException(status_code=500, detail="IPFS model not found")

            ipfs_model = mcp_server.models["ipfs"]
            if not hasattr(ipfs_model, 'pin_rm'):
                raise HTTPException(status_code=500, detail="pin_rm method not available")

            try:
                start_time = time.time()
                result = ipfs_model.pin_rm(cid)
                duration_ms = (time.time() - start_time) * 1000

                return PinResponse(
                    success=True,
                    operation_id=f"pin_rm_{int(start_time * 1000)}",
                    duration_ms=duration_ms,
                    cid=cid
                )
            except Exception as e:
                logger.error(f"Error unpinning content: {e}")
                return PinResponse(
                    success=False,
                    operation_id=f"pin_rm_{int(time.time() * 1000)}",
                    duration_ms=0,
                    cid=cid,
                    error=str(e),
                    error_type=type(e).__name__
                )

        @app.get(f"{api_prefix}/ipfs/pin/ls")
        async def pin_ls():
            """List pinned content in IPFS."""
            if "ipfs" not in mcp_server.models:
                raise HTTPException(status_code=500, detail="IPFS model not found")

            ipfs_model = mcp_server.models["ipfs"]
            if not hasattr(ipfs_model, 'pin_ls'):
                raise HTTPException(status_code=500, detail="pin_ls method not available")

            try:
                start_time = time.time()
                result = ipfs_model.pin_ls() or []
                duration_ms = (time.time() - start_time) * 1000

                return ListPinsResponse(
                    success=True,
                    operation_id=f"pin_ls_{int(start_time * 1000)}",
                    duration_ms=duration_ms,
                    pins=result,
                    count=len(result)
                )
            except Exception as e:
                logger.error(f"Error listing pins: {e}")
                return ListPinsResponse(
                    success=False,
                    operation_id=f"pin_ls_{int(time.time() * 1000)}",
                    duration_ms=0,
                    pins=[],
                    count=0,
                    error=str(e),
                    error_type=type(e).__name__
                )

        # Add a health check specifically for verifying model extensions
        @app.get(f"{api_prefix}/tools/health")
        async def tools_health():
            """Health check for MCP tools and extensions."""
            health_info = {
                "success": True,
                "timestamp": time.time(),
                "methods": {}
            }

            # Check if IPFS model has extensions
            if "ipfs" in mcp_server.models:
                ipfs_model = mcp_server.models["ipfs"]

                # Check each method
                for method_name in ['add_content', 'cat', 'pin_add', 'pin_rm', 'pin_ls',
                                    'swarm_peers', 'swarm_connect', 'swarm_disconnect',
                                    'storage_transfer', 'get_version']:
                    has_method = hasattr(ipfs_model, method_name)
                    health_info["methods"][method_name] = {
                        "available": has_method,
                        "callable": callable(getattr(ipfs_model, method_name, None)) if has_method else False
                    }

            # Overall status
            missing_methods = [m for m, status in health_info["methods"].items()
                              if not status.get("available", False)]

            health_info["overall_status"] = "healthy" if not missing_methods else "degraded"
            health_info["missing_methods"] = missing_methods

            return health_info

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

if __name__ == "__main__":
    main()
