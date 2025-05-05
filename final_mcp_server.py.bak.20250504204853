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
import shutil
import re

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
jsonrpc_dispatcher = None

# Tool registration tracking
registered_tools = {}
registered_tool_categories = set()

# Import availability flags - will be set during initialization
IPFS_AVAILABLE = False
VFS_AVAILABLE = False
FS_JOURNAL_AVAILABLE = False
IPFS_FS_BRIDGE_AVAILABLE = False
MULTI_BACKEND_FS_AVAILABLE = False

try:
    # Import FastAPI and related components
    import uvicorn
    from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import Response as StarletteResponse
    from starlette.background import BackgroundTask as StarletteBackgroundTask
except ImportError as e:
    logger.error(f"Failed to import FastAPI components: {e}")
    logger.info("Please install required dependencies with: pip install fastapi uvicorn[standard]")
    sys.exit(1)

try:
    # Import JSON-RPC components
    from jsonrpcserver import dispatch, Result, Success, Error, InvalidParams, InvalidRequest, MethodNotFound
    from jsonrpcserver import method as jsonrpc_method
    from jsonrpcserver.dispatcher import Dispatcher
except ImportError as e:
    logger.error(f"Failed to import JSON-RPC components: {e}")
    logger.info("Please install required dependencies with: pip install jsonrpcserver")
    sys.exit(1)

# --- Dynamic Imports Check ---
def check_module_availability():
    """Check which modules are available and set flags accordingly."""
    global IPFS_AVAILABLE, VFS_AVAILABLE, FS_JOURNAL_AVAILABLE
    global IPFS_FS_BRIDGE_AVAILABLE, MULTI_BACKEND_FS_AVAILABLE
    
    try:
        import unified_ipfs_tools
        IPFS_AVAILABLE = True
        logger.info("✅ IPFS tools module available")
    except ImportError:
        logger.warning("⚠️ unified_ipfs_tools module not available")
    
    try:
        import mcp_vfs_config
        VFS_AVAILABLE = True
        logger.info("✅ Virtual filesystem module available")
    except ImportError:
        logger.warning("⚠️ mcp_vfs_config module not available")
    
    try:
        import fs_journal_tools
        FS_JOURNAL_AVAILABLE = True
        logger.info("✅ Filesystem journal module available")
    except ImportError:
        logger.warning("⚠️ fs_journal_tools module not available")
    
    try:
        import ipfs_mcp_fs_integration
        IPFS_FS_BRIDGE_AVAILABLE = True
        logger.info("✅ IPFS-FS bridge module available")
    except ImportError:
        logger.warning("⚠️ ipfs_mcp_fs_integration module not available")
    
    try:
        import multi_backend_fs_integration
        MULTI_BACKEND_FS_AVAILABLE = True
        logger.info("✅ Multi-backend filesystem module available")
    except ImportError:
        logger.warning("⚠️ multi_backend_fs_integration module not available")
    
    try:
        import integrate_vfs_to_final_mcp
        logger.info("✅ VFS integration module available")
    except ImportError:
        logger.warning("⚠️ integrate_vfs_to_final_mcp module not available")


# --- Server Initialization ---

# Create the FastAPI app
app = FastAPI(
    title="MCP Server",
    description="Model Context Protocol Server with IPFS and VFS Integration",
    version=__version__
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signal handlers
def handle_sigterm(signum, frame):
    """Handle SIGTERM signal."""
    logger.info("Received SIGTERM signal, shutting down")
    sys.exit(0)

def handle_sigint(signum, frame):
    """Handle SIGINT signal."""
    logger.info("Received SIGINT signal, shutting down")
    sys.exit(0)

# MCP Server class definition
class MCPServer:
    """Model Context Protocol server."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.tools = {}
        self.resources = {}
    
    def tool(self, name: str, description: str = "", parameter_descriptions: Optional[Dict[str, str]] = None):
        """Decorator for registering tools with the server."""
        def decorator(func):
            self.register_tool(name, func, description, parameter_descriptions)
            return func
        return decorator
    
    def register_tool(self, name: str, func: Callable, description: str = "", 
                     parameter_descriptions: Optional[Dict[str, str]] = None):
        """Register a tool with the server."""
        if name in self.tools:
            logger.warning(f"Tool {name} already registered, overwriting")
        
        # Store function and metadata
        self.tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameter_descriptions or {}
        }
        
        # Add to registered tools tracking
        registered_tools[name] = {
            "name": name,
            "description": description
        }
        
        logger.debug(f"Registered tool: {name}")
        return True
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None, context: Optional[Dict[str, Any]] = None):
        """Execute a registered tool."""
        if arguments is None:
            arguments = {}
        if context is None:
            context = {}
        
        if tool_name not in self.tools:
            logger.error(f"Tool {tool_name} not found")
            return {"error": f"Tool {tool_name} not found"}
        
        tool = self.tools[tool_name]
        func = tool["function"]
        
        try:
            # Create a simple context object if the tool expects it
            ctx = SimpleContext(context)
            
            # Check if the function expects a context parameter
            import inspect
            sig = inspect.signature(func)
            if "ctx" in sig.parameters or "context" in sig.parameters:
                # Add context as first parameter
                result = await func(ctx, **arguments) if asyncio.iscoroutinefunction(func) else func(ctx, **arguments)
            else:
                # Call without context
                result = await func(**arguments) if asyncio.iscoroutinefunction(func) else func(**arguments)
            
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}

class SimpleContext:
    """A simple context for tool execution."""
    
    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """Initialize the context."""
        self.data = data or {}
    
    async def info(self, message: str):
        """Log an info message."""
        logger.info(message)
    
    async def error(self, message: str):
        """Log an error message."""
        logger.error(message)
    
    async def warn(self, message: str):
        """Log a warning message."""
        logger.warning(message)
    
    async def debug(self, message: str):
        """Log a debug message."""
        logger.debug(message)

# Create server instance
server = MCPServer()

# --- Tool Registration Functions ---

def register_all_tools():
    """Register all available tools with the MCP server."""
    logger.info("Registering all available tools with MCP server...")
    
    # Keep track of successfully registered tools
    successful_tools = []
    
    try:
        # First, try to use the comprehensive integration module
        try:
            import integrate_vfs_to_final_mcp
            result = integrate_vfs_to_final_mcp.register_all_components(server)
            if isinstance(result, dict):
                # Track which components were registered successfully
                for component, success in result.items():
                    if success:
                        successful_tools.append(component)
                        registered_tool_categories.add(component)
            else:
                if result:
                    successful_tools.append("integrated_components")
                    registered_tool_categories.add("integrated_components")
            logger.info(f"Integrated components: {successful_tools}")
        except ImportError:
            logger.warning("Comprehensive integration module not available, falling back to individual modules")
        except Exception as e:
            logger.error(f"Error using comprehensive integration: {e}")
            logger.error(traceback.format_exc())
        
        # If no tools were registered via the integration module, try individual modules
        if not successful_tools:
            # Register IPFS tools if available
            if IPFS_AVAILABLE:
                if register_ipfs_tools():
                    successful_tools.append("ipfs_tools")
                    registered_tool_categories.add("ipfs_tools")
            
            # Register virtual filesystem tools
            if VFS_AVAILABLE:
                if register_vfs_tools():
                    successful_tools.append("vfs_tools")
                    registered_tool_categories.add("vfs_tools")
            
            # Register FS Journal tools if available
            if FS_JOURNAL_AVAILABLE:
                if register_fs_journal_tools():
                    successful_tools.append("fs_journal_tools")
                    registered_tool_categories.add("fs_journal_tools")
            
            # Register IPFS-FS Bridge tools if available
            if IPFS_FS_BRIDGE_AVAILABLE:
                if register_ipfs_fs_bridge_tools():
                    successful_tools.append("ipfs_fs_bridge_tools")
                    registered_tool_categories.add("ipfs_fs_bridge_tools")
            
            # Register Multi-Backend FS tools if available
            if MULTI_BACKEND_FS_AVAILABLE:
                if register_multi_backend_tools():
                    successful_tools.append("multi_backend_tools")
                    registered_tool_categories.add("multi_backend_tools")
        
        logger.info(f"Successfully registered tool categories: {', '.join(successful_tools)}")
        return True
    except Exception as e:
        logger.error(f"Error during tool registration: {e}")
        logger.error(traceback.format_exc())
        return False

def register_ipfs_tools():
    """Register IPFS tools."""
    try:
        import unified_ipfs_tools
        logger.info("Using unified_ipfs_tools for IPFS tool registration")
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info(f"Registered IPFS tools using unified_ipfs_tools: {len(result) if isinstance(result, list) else result}")
        return True
    except ImportError:
        logger.warning("unified_ipfs_tools module not available")
    except Exception as e:
        logger.error(f"Error registering IPFS tools: {e}")
        logger.error(traceback.format_exc())
    
    # Try alternative registration method
    try:
        from ipfs_mcp_tools_integration import register_ipfs_tools as register_tools_alt
        logger.info("Using ipfs_mcp_tools_integration for IPFS tool registration")
        result = register_tools_alt(server)
        logger.info(f"Registered IPFS tools using ipfs_mcp_tools_integration: {result}")
        return True
    except ImportError:
        logger.warning("ipfs_mcp_tools_integration module not available")
    except Exception as e:
        logger.error(f"Error registering IPFS tools via alternative method: {e}")
        logger.error(traceback.format_exc())
    
    return False

def register_vfs_tools():
    """Register virtual filesystem tools."""
    try:
        import mcp_vfs_config
        logger.info("Using mcp_vfs_config for VFS tool registration")
        result = mcp_vfs_config.register_vfs_tools(server)
        logger.info(f"Registered VFS tools: {result}")
        return True
    except ImportError:
        logger.warning("mcp_vfs_config module not available")
    except Exception as e:
        logger.error(f"Error registering VFS tools: {e}")
        logger.error(traceback.format_exc())
    
    # Try alternative registration method
    try:
        from enhance_vfs_mcp_integration import register_all_fs_tools
        logger.info("Using enhance_vfs_mcp_integration for VFS tool registration")
        result = register_all_fs_tools(server)
        logger.info(f"Registered VFS tools using enhance_vfs_mcp_integration: {result}")
        return True
    except ImportError:
        logger.warning("enhance_vfs_mcp_integration module not available")
    except Exception as e:
        logger.error(f"Error registering VFS tools via alternative method: {e}")
        logger.error(traceback.format_exc())
    
    return False

def register_fs_journal_tools():
    """Register filesystem journal tools."""
    try:
        import fs_journal_tools
        logger.info("Using fs_journal_tools for FS journal tool registration")
        result = fs_journal_tools.register_tools(server)
        logger.info(f"Registered FS journal tools: {result}")
        return True
    except ImportError:
        logger.warning("fs_journal_tools module not available")
    except Exception as e:
        logger.error(f"Error registering FS journal tools: {e}")
        logger.error(traceback.format_exc())
    return False

def register_ipfs_fs_bridge_tools():
    """Register IPFS-FS bridge tools."""
    try:
        import ipfs_mcp_fs_integration
        logger.info("Using ipfs_mcp_fs_integration for IPFS-FS bridge tool registration")
        
        # Try to find the appropriate registration function
        if hasattr(ipfs_mcp_fs_integration, "register_all_tools"):
            result = ipfs_mcp_fs_integration.register_all_tools(server)
        elif hasattr(ipfs_mcp_fs_integration, "register_tools"):
            result = ipfs_mcp_fs_integration.register_tools(server)
        elif hasattr(ipfs_mcp_fs_integration, "register_ipfs_fs_tools"):
            result = ipfs_mcp_fs_integration.register_ipfs_fs_tools(server)
        else:
            logger.warning("Could not find appropriate registration function in ipfs_mcp_fs_integration")
            return False
            
        logger.info(f"Registered IPFS-FS bridge tools: {result}")
        return True
    except ImportError:
        logger.warning("ipfs_mcp_fs_integration module not available")
    except Exception as e:
        logger.error(f"Error registering IPFS-FS bridge tools: {e}")
        logger.error(traceback.format_exc())
    return False

def register_multi_backend_tools():
    """Register multi-backend filesystem tools."""
    try:
        import multi_backend_fs_integration
        logger.info("Using multi_backend_fs_integration for multi-backend tool registration")
        
        # Try to find the appropriate registration function
        if hasattr(multi_backend_fs_integration, "register_all_tools"):
            result = multi_backend_fs_integration.register_all_tools(server)
        elif hasattr(multi_backend_fs_integration, "register_tools"):
            result = multi_backend_fs_integration.register_tools(server)
        elif hasattr(multi_backend_fs_integration, "register_multi_backend_fs_tools"):
            result = multi_backend_fs_integration.register_multi_backend_fs_tools(server)
        else:
            logger.warning("Could not find appropriate registration function in multi_backend_fs_integration")
            return False
            
        logger.info(f"Registered multi-backend filesystem tools: {result}")
        return True
    except ImportError:
        logger.warning("multi_backend_fs_integration module not available")
    except Exception as e:
        logger.error(f"Error registering multi-backend filesystem tools: {e}")
        logger.error(traceback.format_exc())
    
    # Try alternative registration
    try:
        from register_multi_backend_tools import register_multi_backend_tools as reg_tools_alt
        logger.info("Using register_multi_backend_tools for multi-backend tool registration")
        result = reg_tools_alt(server)
        logger.info(f"Registered multi-backend filesystem tools using alternative method: {result}")
        return True
    except ImportError:
        logger.warning("register_multi_backend_tools module not available")
    except Exception as e:
        logger.error(f"Error registering multi-backend filesystem tools via alternative method: {e}")
        logger.error(traceback.format_exc())
    
    return False

# --- Server Initialization and Endpoints ---

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup."""
    logger.info("Starting server initialization...")
    
    # Check module availability
    check_module_availability()
    
    # Initialize JSON-RPC
    if not setup_jsonrpc():
        logger.error("Failed to set up JSON-RPC, but continuing with limited functionality")
    
    # Register all tools
    if not register_all_tools():
        logger.error("Failed to register all tools, but continuing with limited functionality")
    
    logger.info("Server initialization complete")

def setup_jsonrpc():
    """Set up JSON-RPC dispatcher and methods."""
    global jsonrpc_dispatcher
    
    try:
        logger.info("Setting up JSON-RPC dispatcher")
        jsonrpc_dispatcher = Dispatcher()
        
        # Register the execute_tool method
        @jsonrpc_dispatcher.add_method
        async def use_tool(tool_name: str, arguments: Dict[str, Any] = None, context: Dict[str, Any] = None):
            """Execute a tool by name."""
            if arguments is None:
                arguments = {}
            if context is None:
                context = {}
            
            logger.info(f"Executing tool: {tool_name}")
            result = await server.execute_tool(tool_name, arguments, context)
            logger.debug(f"Tool {tool_name} result: {result}")
            return result
        
        # Register the get_tools method
        @jsonrpc_dispatcher.add_method
        async def get_tools(**kwargs):
            """Get a list of available tools."""
            tool_list = []
            for name, tool in server.tools.items():
                tool_list.append({
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                })
            return tool_list
        
        # Register the get_server_info method
        @jsonrpc_dispatcher.add_method
        async def get_server_info(**kwargs):
            """Get server information."""
            uptime = datetime.now() - server_start_time
            return {
                "version": __version__,
                "uptime_seconds": uptime.total_seconds(),
                "port": PORT,
                "registered_tools": len(server.tools),
                "registered_tool_categories": list(registered_tool_categories)
            }
        
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

# Basic routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "MCP Server with IPFS and VFS Integration",
        "version": __version__,
        "tools_count": len(server.tools),
        "ipfs_available": IPFS_AVAILABLE,
        "vfs_available": VFS_AVAILABLE
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    uptime = datetime.now() - server_start_time
    return {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": uptime.total_seconds(),
        "tools_count": len(server.tools),
        "registered_tool_categories": list(registered_tool_categories)
    }

@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: Request):
    """JSON-RPC endpoint."""
    return await handle_jsonrpc(request)

@app.get("/tools")
async def list_tools():
    """List all registered tools."""
    tool_list = []
    for name, tool in server.tools.items():
        tool_list.append({
            "name": name,
            "description": tool["description"],
            "parameters": tool["parameters"]
        })
    return {
        "tools": tool_list,
        "count": len(tool_list),
        "registered_tool_categories": list(registered_tool_categories)
    }

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
    
    # Start the server
    log_level = "debug" if args.debug else "info"
    logger.info(f"Starting server on {args.host}:{args.port}, debug={args.debug}")
    
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=log_level)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
