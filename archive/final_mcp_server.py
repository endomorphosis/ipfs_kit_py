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
- Complete integration of IPFS Kit, Virtual Filesystem, and related components
"""

import os
import sys
import json
import logging
import asyncio
import signal
import argparse
import traceback
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable

# --- Early Setup: Logging and Path ---
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
initialization_lock = asyncio.Lock()
initialization_event = asyncio.Event()

# Tool registries - will be populated during startup
registered_tools = {}
tool_implementations = {}
available_extensions = {}

# Add MCP SDK path before imports
cwd = os.getcwd()
sdk_path = os.path.abspath(os.path.join(cwd, "docs/mcp-python-sdk/src"))
sdk_added_to_path = False
if os.path.isdir(sdk_path):
    if sdk_path not in sys.path:
        sys.path.insert(0, sdk_path)
        logger.info(f"Added SDK path: {sdk_path}")
        sdk_added_to_path = True
    else:
        logger.info(f"SDK path already in sys.path: {sdk_path}")
        sdk_added_to_path = True
else:
    logger.warning(f"MCP SDK path not found: {sdk_path}. MCP features might fail.")

# Add any additional directories to the path
paths_to_add = [
    os.getcwd(),
    os.path.join(os.getcwd(), "ipfs_kit_py"),
]

for path in paths_to_add:
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)
        logger.info(f"Added path to sys.path: {path}")

# Try to import MCP after setting paths
try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP, Context
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, StreamingResponse, Response
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from mcp import types as mcp_types
    logger.info("Successfully imported MCP and Starlette modules.")
    imports_succeeded = True
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Failed to import required modules")
    imports_succeeded = False
    sys.exit(1)

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
        
        # Register virtual filesystem tools
        try:
            # Try to import our enhanced VFS integration module
            import enhance_vfs_mcp_integration
            enhance_vfs_mcp_integration.register_all_fs_tools(server)
            logger.info('Virtual filesystem tools registered via enhanced integration')
        except Exception as e:
            logger.error(f"Error registering virtual filesystem tools: {e}")
            logger.error(traceback.format_exc())
        
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
        # First, try to register tools from unified_ipfs_tools
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
        
        # Try the original approach using ipfs_mcp_tools_integration
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
        response = await jsonrpc_dispatcher.call(request_json)
        
        return JSONResponse(response.to_dict())
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())
        
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},
            status_code=500
        )

# Signal handlers
def handle_sigterm(sig, frame):
    """Handle SIGTERM signal."""
    logger.info("Received SIGTERM signal, shutting down...")
    sys.exit(0)

def handle_sigint(sig, frame):
    """Handle SIGINT signal (Ctrl+C)."""
    logger.info("Received SIGINT signal, shutting down...")
    sys.exit(0)

# Setup application
def create_app():
    """Create the Starlette application with routes and middleware."""
    try:
        # Create the Starlette application
        routes = [
            Route("/", homepage),
            Route("/health", health_endpoint),
            Route("/initialize", initialize_endpoint),
            Route("/jsonrpc", handle_jsonrpc, methods=["POST"])
        ]
        
        app = Starlette(routes=routes)
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup up MCP SSE endpoint
        if server:
            server.attach_to_starlette(app, path="/mcp")
            logger.info("Attached MCP SSE endpoint to Starlette application")
        
        # Set up JSON-RPC
        setup_jsonrpc()
        
        return app
    except Exception as e:
        logger.error(f"Error creating Starlette application: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

# Main entry point
server_start_time = datetime.now()

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Final MCP Server Implementation")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on (default: 3000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Write pid to file
    with open("final_mcp_server.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Set the global port
    PORT = args.port
    
    # Import required modules and create server instance
    if not import_required_modules():
        logger.error("Failed to import required modules or create server instance")
        sys.exit(1)
    
    # Register all tools
    if not register_all_tools():
        logger.warning("Some tools may not be available")
    
    # Create application
    app = create_app()
    
    # Start the server
    log_level = "debug" if args.debug else "info"
    logger.info(f"Starting server on {args.host}:{args.port}, debug={args.debug}")
    
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=log_level)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
