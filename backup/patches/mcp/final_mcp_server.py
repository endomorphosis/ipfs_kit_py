<<<<<<< HEAD:final_mcp_server.py
=======
#!/usr/bin/env python3
"""
Final MCP Server Implementation

This server combines all the successful approaches from previous attempts
to create a unified MCP server with complete IPFS tool integration.

Key features:
- Comprehensive error handling and recovery
- Multiple tool registration methods
- Consistent port usage (3000)
- Path configuration to ensure proper module imports
- Fallback to mock implementations when needed
- Full JSON-RPC support
"""

import os
import sys
import json
import logging
import anyio
import signal
import argparse
import traceback
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("final_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("final-mcp")

# Define the version
__version__ = "1.0.0"

# Global state
PORT = 3000  # Default to port 3000 as recommended
server_initialized = False
initialization_lock = anyio.Lock()
initialization_event = anyio.Event()

# Tool registries - will be populated during startup
registered_tools = {}
tool_implementations = {}
available_extensions = {}

# Add necessary paths for module imports
def setup_python_paths():
    """Set up Python paths for proper module imports."""
    logger.info("Setting up Python paths for module imports...")

    # Current directory
    cwd = os.getcwd()

    # Add the MCP SDK path
    paths_to_add = [
        # Main directory
        cwd,
        # MCP SDK path
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
        # IPFS Kit path
        os.path.join(cwd, "ipfs_kit_py"),
    ]

    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")

    # Return True if successful
    return True

# Import required modules - this is done after setting up paths
def import_required_modules():
    """Import required modules after setting up paths."""
    global server, FastMCP, Context, JSONResponse, Starlette, CORSMiddleware

    try:
        # Try imports that require the MCP SDK
        import uvicorn
        from mcp.server.fastmcp import FastMCP, Context
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import JSONResponse, StreamingResponse, Response
        from starlette.middleware.cors import CORSMiddleware
        from starlette.requests import Request

        # JSON-RPC libraries
        from jsonrpc.dispatcher import Dispatcher
        from jsonrpc.exceptions import JSONRPCDispatchException

        # Create FastMCP server
        server = FastMCP(
            name=f"final-mcp-server",
            instructions="Unified MCP server with comprehensive IPFS tool coverage"
        )

        logger.info("Successfully imported required modules and created server instance")
        return True
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False

# Tool registration functions
def register_all_tools():
    """Register all available tools with the MCP server."""
    logger.info("Registering all available tools with MCP server...")

    # Keep track of successfully registered tools
    successful_tools = []

    try:
        # First, try to register tools from ipfs_mcp_tools_integration
        if register_ipfs_tools():
            successful_tools.append("ipfs_tools")

        # Then, try to register tools from ipfs_mcp_fs_integration
        if register_ipfs_fs_tools():
            successful_tools.append("ipfs_fs_tools")

        # Finally, register any additional tools
        if register_additional_tools():
            successful_tools.append("additional_tools")

        logger.info(f"Successfully registered tool categories: {', '.join(successful_tools)}")
        return True
    except Exception as e:
        logger.error(f"Error during tool registration: {e}")
        logger.error(traceback.format_exc())
        return False

def register_ipfs_tools():
    """Register IPFS tools using unified_ipfs_tools."""
    try:
        import unified_ipfs_tools
        logger.info("Using unified_ipfs_tools for IPFS tool registration")
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info(f"Registered IPFS tools using unified_ipfs_tools: {len(result) if isinstance(result, list) else result}")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS tools using unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())

        # Fall back to the original approach
        logger.warning("Falling back to original IPFS tool registration approach")
    """Register IPFS tools using unified_ipfs_tools."""
    try:
        import unified_ipfs_tools
        logger.info("Using unified_ipfs_tools for IPFS tool registration")
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info(f"Registered IPFS tools using unified_ipfs_tools: {len(result) if isinstance(result, list) else result}")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS tools using unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())

        # Fall back to the original approach
        logger.warning("Falling back to original IPFS tool registration approach")
    """Register IPFS tools using ipfs_mcp_tools_integration."""
    try:
        # Try to import the module
        spec = importlib.util.find_spec("ipfs_mcp_tools_integration")
        if spec is None:
            logger.warning("ipfs_mcp_tools_integration module not found")
            return False

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Register tools using the module's function
        if hasattr(module, "register_ipfs_tools"):
            result = module.register_ipfs_tools(server)
            logger.info(f"Registered IPFS tools from ipfs_mcp_tools_integration: {result}")
            return result
        else:
            logger.warning("register_ipfs_tools function not found in ipfs_mcp_tools_integration")
            return False
    except Exception as e:
        logger.error(f"Error registering IPFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_ipfs_fs_tools():
    """Register IPFS-FS bridge tools."""
    try:
        # Try to import the module
        spec = importlib.util.find_spec("ipfs_mcp_fs_integration")
        if spec is None:
            logger.warning("ipfs_mcp_fs_integration module not found")
            return False

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Register tools using the module's function
        if hasattr(module, "register_ipfs_fs_tools"):
            result = module.register_ipfs_fs_tools(server)
            logger.info(f"Registered IPFS-FS tools from ipfs_mcp_fs_integration: {result}")
            return result
        else:
            logger.warning("register_ipfs_fs_tools function not found in ipfs_mcp_fs_integration")
            return False
    except Exception as e:
        logger.error(f"Error registering IPFS-FS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_additional_tools():
    """Register any additional tools not covered by the specialized modules."""
    try:
        # This is where you would register any additional tools
        # For now, we'll just register a simple health check tool

        @server.tool(name="health_check", description="Check the health of the MCP server and IPFS components")
        async def health_check(ctx: Context):
            """Check the health of the MCP server and IPFS components."""
            await ctx.info("Checking server health...")

            health_status = {
                "server": {
                    "status": "healthy",
                    "version": __version__,
                    "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
                },
                "tools": {
                    "registered_count": len(server._tools),
                    "tool_names": list(server._tools.keys())
                },
                "timestamp": datetime.now().isoformat()
            }

            await ctx.info("Health check completed successfully")
            return health_status

        logger.info("Registered additional tools")
        return True
    except Exception as e:
        logger.error(f"Error registering additional tools: {e}")
        logger.error(traceback.format_exc())
        return False

# Server endpoint handlers
async def homepage(request):
    """Handle the homepage request."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []

    return JSONResponse({
        "message": "Final MCP Server is running",
        "version": __version__,
        "port": PORT,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "registered_tools_count": len(tool_names),
        "registered_tools": tool_names,
        "endpoints": {
            "/": "Home page with server information",
            "/health": "Health check endpoint",
            "/initialize": "Client initialization endpoint",
            "/mcp": "MCP SSE connection endpoint",
            "/jsonrpc": "JSON-RPC endpoint"
        }
    })

async def health_endpoint(request):
    """Health check endpoint for the MCP server"""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []

    return JSONResponse({
        "status": "healthy",
        "version": __version__,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "registered_tools_count": len(tool_names),
        "timestamp": datetime.now().isoformat()
    })

async def initialize_endpoint(request):
    """Initialize endpoint for clients."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []

    return JSONResponse({
        "server_info": {
            "name": "Final MCP Server",
            "version": __version__,
            "status": "ready"
        },
        "capabilities": {
            "tools": tool_names,
            "jsonrpc": True,
            "ipfs": True,
            "streaming": True
        }
    })

# JSON-RPC implementation
jsonrpc_dispatcher = None

def setup_jsonrpc():
    """Set up JSON-RPC dispatcher and handlers."""
    global jsonrpc_dispatcher

    try:
        from jsonrpc.dispatcher import Dispatcher

        jsonrpc_dispatcher = Dispatcher()

        @jsonrpc_dispatcher.add_method
        async def ping(**kwargs):
            """Simple ping method to test JSON-RPC connection."""
            return {
                "status": "ok",
                "server": "final-mcp",
                "timestamp": datetime.now().isoformat()
            }

        @jsonrpc_dispatcher.add_method
        async def initialize(client_info=None, **kwargs):
            """Initialize the connection with the client."""
            logger.info(f"Received initialize request from client: {client_info}")

            tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []

            return {
                "server": "final-mcp",
                "version": __version__,
                "capabilities": {
                    "streaming": True,
                    "jsonrpc": True,
                    "tooling": True,
                    "ipfs": True
                },
                "tools": tool_names
            }

        @jsonrpc_dispatcher.add_method
        async def shutdown(**kwargs):
            """Handle shutdown request from client."""
            logger.info("Received shutdown request from client")
            return {"status": "ok"}

        logger.info("JSON-RPC dispatcher initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error setting up JSON-RPC: {e}")
        logger.error(traceback.format_exc())
        return False

async def handle_jsonrpc(request):
    """Handle JSON-RPC requests."""
    if jsonrpc_dispatcher is None:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": "JSON-RPC not initialized"}, "id": None},
            status_code=500
        )

    try:
        request_json = await request.json()
        logger.debug(f"Received JSON-RPC request: {request_json}")

        # Process the request
        response = await jsonrpc_dispatcher.dispatch(request_json)

        return JSONResponse(response.to_dict())
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())

        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},
            status_code=500
        )

# Main entry point
server_start_time = datetime.now()

def main():
    """Main entry point for the server."""
    global PORT, server_start_time

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Final MCP Server with integrated IPFS tools")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    PORT = args.port

    # Set up Python paths
    if not setup_python_paths():
        logger.error("Failed to set up Python paths")
        return 1

    # Import required modules
    if not import_required_modules():
        logger.error("Failed to import required modules")
        return 1

    # Set up JSON-RPC
    if not setup_jsonrpc():
        logger.warning("JSON-RPC setup failed, continuing without it")

    # Register all tools
    if not register_all_tools():
        logger.warning("Some tools could not be registered, continuing with partial functionality")

    # Get the Starlette app from the server
    app = server.sse_app()

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set up routes
    from starlette.routing import Route

    app.routes.extend([
        Route("/", endpoint=homepage),
        Route("/health", endpoint=health_endpoint),
        Route("/initialize", endpoint=initialize_endpoint),
        Route("/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]),
        Route("/api/v0/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]),
    ])

    # Register startup and shutdown handlers
    @app.on_event("startup")
    async def on_startup():
        """Handle server startup."""
        global server_initialized, server_start_time

        logger.info("Starting Final MCP Server...")
        server_start_time = datetime.now()
        server_initialized = True
        initialization_event.set()

        logger.info(f"Server started successfully on port {PORT}")

    @app.on_event("shutdown")
    async def on_shutdown():
        """Handle server shutdown."""
        logger.info("Shutting down Final MCP Server...")

    # Run the server
    import uvicorn

    logger.info(f"Starting Final MCP Server on {args.host}:{PORT}...")
    uvicorn.run(app, host=args.host, port=PORT, log_level="debug" if args.debug else "info")

    return 0

if __name__ == "__main__":
    sys.exit(main())
>>>>>>> 8a0fb83a3a6bbf5fa6d90dd457f2ae42f880c647:patches/mcp/final_mcp_server.py
