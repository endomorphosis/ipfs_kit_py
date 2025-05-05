#!/usr/bin/env python3
"""
Comprehensive Final MCP Server Implementation

This server integrates all components of IPFS Kit Python:
- Complete IPFS toolkit functionality
- Virtual Filesystem with enhanced features
- Caching and performance optimizations
- JSON-RPC interface for tool invocation
- Fallback mechanisms for robust operation

This implementation resolves code debt by properly organizing and
integrating all previously developed modules.
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

# --- Early Setup: Logging and Path Configuration ---
# Configure robust logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("comprehensive_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("comprehensive-mcp")

# Define the version
__version__ = "1.1.0"

# Global state
PORT = 3000  # Default port
server_initialized = False
initialization_lock = asyncio.Lock()
initialization_event = asyncio.Event()
server_start_time = datetime.now()

# Tool registries
registered_tools = {}
tool_implementations = {}
available_extensions = {}

# Configure system paths for reliable module imports
def configure_paths():
    """Set up system paths to ensure all modules can be imported correctly."""
    logger.info("Configuring system paths...")
    
    paths_to_add = [
        os.getcwd(),  # Current working directory
        os.path.join(os.getcwd(), "ipfs_kit_py"),  # IPFS Kit directory
        os.path.abspath(os.path.join(os.getcwd(), "docs/mcp-python-sdk/src")),  # MCP SDK
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")
    
    logger.info("System paths configured successfully")
    return True

# Initialize paths early
configure_paths()

# Try to import required modules
try:
    import uvicorn
    from mcp.server.fastmcp import FastMCP, Context
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, StreamingResponse, Response
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from jsonrpc.dispatcher import Dispatcher
    from jsonrpc.exceptions import JSONRPCDispatchException
    
    logger.info("Successfully imported core modules")
    imports_succeeded = True
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error(traceback.format_exc())
    imports_succeeded = False
    sys.exit(1)

# Create the FastMCP server instance
server = FastMCP(
    name="comprehensive-ipfs-mcp-server",
    instructions="Comprehensive MCP server with complete IPFS toolkit and virtual filesystem support"
)

# --- Tool Registration Functions ---

def register_all_ipfs_tools() -> bool:
    """Register all IPFS tools with the server."""
    logger.info("Registering all IPFS tools...")
    
    try:
        # First try using unified_ipfs_tools
        import unified_ipfs_tools
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        if result:
            logger.info("Successfully registered IPFS tools via unified_ipfs_tools")
            return True
    except Exception as e:
        logger.warning(f"Failed to register tools via unified_ipfs_tools: {e}")
    
    # Fallback: Try direct import approach
    try:
        spec = importlib.util.find_spec("ipfs_mcp_tools_integration")
        if spec is not None and spec.loader is not None:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "register_ipfs_tools"):
                result = module.register_ipfs_tools(server)
                if result:
                    logger.info("Successfully registered IPFS tools via ipfs_mcp_tools_integration")
                    return True
    except Exception as e:
        logger.warning(f"Failed to register tools via ipfs_mcp_tools_integration: {e}")
    
    # Last resort: Register basic IPFS tools directly
    logger.warning("Falling back to direct tool registration")
    basic_tools_registered = register_basic_ipfs_tools()
    
    return basic_tools_registered

def register_basic_ipfs_tools() -> bool:
    """Register basic IPFS tools directly with the server."""
    logger.info("Registering basic IPFS tools directly...")
    
    try:
        # Add a mock IPFS add tool as fallback
        @server.tool("ipfs_add")
        async def ipfs_add(ctx, path: str):
            """Add a file or directory to IPFS"""
            await ctx.info(f"Adding {path} to IPFS (mock implementation)")
            
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path not found: {path}"
                }
            
            # Create a mock CID based on file path and time
            import hashlib
            from datetime import datetime
            
            hash_input = f"{path}:{datetime.now().isoformat()}".encode('utf-8')
            mock_cid = f"Qm{hashlib.sha256(hash_input).hexdigest()[:44]}"
            
            return {
                "success": True,
                "cid": mock_cid,
                "path": path,
                "implementation": "mock"
            }
        
        # Add a mock IPFS cat tool as fallback
        @server.tool("ipfs_cat")
        async def ipfs_cat(ctx, cid: str):
            """Retrieve content from IPFS by CID"""
            await ctx.info(f"Retrieving content for CID: {cid} (mock implementation)")
            
            # Return mock content
            mock_content = f"Mock content for CID: {cid}"
            
            return {
                "success": True,
                "content": mock_content,
                "cid": cid,
                "implementation": "mock"
            }
        
        logger.info("Registered basic IPFS tools as fallback")
        return True
    except Exception as e:
        logger.error(f"Failed to register basic IPFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_filesystem_tools() -> bool:
    """Register virtual filesystem tools with the server."""
    logger.info("Registering virtual filesystem tools...")
    
    try:
        # First try the enhanced VFS integration
        import enhance_vfs_mcp_integration
        result = enhance_vfs_mcp_integration.register_all_fs_tools(server)
        if result:
            logger.info("Successfully registered enhanced virtual filesystem tools")
            return True
    except Exception as e:
        logger.warning(f"Failed to register enhanced VFS tools: {e}")
        logger.warning(traceback.format_exc())
    
    # Fallback: Try the basic VFS integration
    try:
        import integrate_vfs_to_final_mcp
        result = integrate_vfs_to_final_mcp.register_vfs_tools(server)
        if result:
            logger.info("Successfully registered basic virtual filesystem tools")
            return True
    except Exception as e:
        logger.warning(f"Failed to register basic VFS tools: {e}")
    
    # Last resort: Register minimal VFS tools directly
    logger.warning("Falling back to direct VFS tool registration")
    minimal_tools_registered = register_minimal_vfs_tools()
    
    return minimal_tools_registered

def register_minimal_vfs_tools() -> bool:
    """Register minimal VFS tools directly with the server."""
    logger.info("Registering minimal VFS tools directly...")
    
    try:
        # Add a basic file read tool
        @server.tool("vfs_read_file_minimal")
        async def vfs_read_file_minimal(ctx, path: str):
            """Read a file from the filesystem (minimal implementation)"""
            await ctx.info(f"Reading file: {path} (minimal implementation)")
            
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            try:
                with open(path, 'r') as f:
                    content = f.read()
                
                return {
                    "success": True,
                    "path": path,
                    "content": content,
                    "size": len(content)
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Add a basic file write tool
        @server.tool("vfs_write_file_minimal")
        async def vfs_write_file_minimal(ctx, path: str, content: str):
            """Write content to a file (minimal implementation)"""
            await ctx.info(f"Writing to file: {path} (minimal implementation)")
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                
                with open(path, 'w') as f:
                    f.write(content)
                
                return {
                    "success": True,
                    "path": path,
                    "size": len(content),
                    "message": f"File written successfully: {path}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        logger.info("Registered minimal VFS tools as fallback")
        return True
    except Exception as e:
        logger.error(f"Failed to register minimal VFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_additional_tools() -> bool:
    """Register additional utility tools."""
    logger.info("Registering additional utility tools...")
    
    try:
        # Health check tool
        @server.tool("health_check")
        async def health_check(ctx):
            """Check the health of the MCP server and components"""
            await ctx.info("Performing health check...")
            
            # Get list of registered tools
            tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
            
            return {
                "server": {
                    "status": "healthy",
                    "version": __version__,
                    "uptime_seconds": (datetime.now() - server_start_time).total_seconds()
                },
                "tools": {
                    "count": len(tool_names),
                    "names": tool_names
                },
                "timestamp": datetime.now().isoformat()
            }
        
        # System info tool
        @server.tool("system_info")
        async def system_info(ctx):
            """Get information about the system"""
            await ctx.info("Retrieving system information...")
            
            import platform
            import psutil
            
            try:
                # Get CPU info
                cpu_info = {
                    "physical_cores": psutil.cpu_count(logical=False),
                    "logical_cores": psutil.cpu_count(logical=True),
                    "usage_percent": psutil.cpu_percent(interval=1)
                }
                
                # Get memory info
                memory = psutil.virtual_memory()
                memory_info = {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                }
                
                # Get disk info
                disk = psutil.disk_usage('/')
                disk_info = {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                }
                
                return {
                    "platform": {
                        "system": platform.system(),
                        "release": platform.release(),
                        "version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor()
                    },
                    "python": {
                        "version": platform.python_version(),
                        "implementation": platform.python_implementation()
                    },
                    "resources": {
                        "cpu": cpu_info,
                        "memory": memory_info,
                        "disk": disk_info
                    }
                }
            except Exception as e:
                # Fallback to basic info if psutil is not available
                return {
                    "platform": {
                        "system": platform.system(),
                        "release": platform.release(),
                        "version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor()
                    },
                    "python": {
                        "version": platform.python_version(),
                        "implementation": platform.python_implementation()
                    },
                    "note": "Detailed resource info not available. Error: " + str(e)
                }
        
        logger.info("Registered additional utility tools")
        return True
    except Exception as e:
        logger.error(f"Failed to register additional tools: {e}")
        logger.error(traceback.format_exc())
        return False

def register_all_tools() -> bool:
    """Register all available tools."""
    logger.info("Registering all available tools...")
    
    # Track registration success
    ipfs_success = register_all_ipfs_tools()
    filesystem_success = register_filesystem_tools()
    additional_success = register_additional_tools()
    
    # Log registration status
    if ipfs_success:
        logger.info("IPFS tools registered successfully")
    else:
        logger.warning("IPFS tool registration had issues")
    
    if filesystem_success:
        logger.info("Filesystem tools registered successfully")
    else:
        logger.warning("Filesystem tool registration had issues")
    
    if additional_success:
        logger.info("Additional tools registered successfully")
    else:
        logger.warning("Additional tool registration had issues")
    
    # Consider it a success if any category was registered
    return ipfs_success or filesystem_success or additional_success

# --- Server endpoints ---

async def homepage(request):
    """Handle the homepage request."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    # Group tools by category for better organization
    tool_categories = {
        "ipfs": [name for name in tool_names if name.startswith("ipfs_")],
        "vfs": [name for name in tool_names if name.startswith("vfs_")],
        "utility": [name for name in tool_names if not (name.startswith("ipfs_") or name.startswith("vfs_"))]
    }
    
    return JSONResponse({
        "server": "Comprehensive IPFS MCP Server",
        "version": __version__,
        "uptime": str(datetime.now() - server_start_time),
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "tools": {
            "total": len(tool_names),
            "categories": tool_categories
        },
        "endpoints": {
            "/": "Home page with server information",
            "/health": "Health check endpoint",
            "/initialize": "Client initialization endpoint",
            "/mcp": "MCP SSE connection endpoint",
            "/jsonrpc": "JSON-RPC API endpoint",
            "/test": "Test endpoint to verify all tools"
        }
    })

async def health_endpoint(request):
    """Health check endpoint for monitoring."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    categories = {
        "ipfs": len([name for name in tool_names if name.startswith("ipfs_")]),
        "vfs": len([name for name in tool_names if name.startswith("vfs_")]),
        "utility": len([name for name in tool_names if not (name.startswith("ipfs_") or name.startswith("vfs_"))])
    }
    
    return JSONResponse({
        "status": "healthy",
        "version": __version__,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "registered_tools": {
            "total": len(tool_names),
            "by_category": categories
        },
        "timestamp": datetime.now().isoformat()
    })

async def initialize_endpoint(request):
    """Initialize endpoint for clients."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    # Group tools by category
    tool_categories = {
        "ipfs": [name for name in tool_names if name.startswith("ipfs_")],
        "vfs": [name for name in tool_names if name.startswith("vfs_")],
        "utility": [name for name in tool_names if not (name.startswith("ipfs_") or name.startswith("vfs_"))]
    }
    
    return JSONResponse({
        "server_info": {
            "name": "Comprehensive IPFS MCP Server",
            "version": __version__,
            "status": "ready"
        },
        "capabilities": {
            "ipfs": len(tool_categories["ipfs"]) > 0,
            "vfs": len(tool_categories["vfs"]) > 0,
            "jsonrpc": True,
            "streaming": True
        },
        "tools": {
            "categories": tool_categories,
            "total": len(tool_names)
        }
    })

async def test_endpoint(request):
    """Endpoint to verify all registered tools."""
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    # Group tools by category
    ipfs_tools = [name for name in tool_names if name.startswith("ipfs_")]
    vfs_tools = [name for name in tool_names if name.startswith("vfs_")]
    utility_tools = [name for name in tool_names if not (name.startswith("ipfs_") or name.startswith("vfs_"))]
    
    return JSONResponse({
        "test_info": {
            "timestamp": datetime.now().isoformat(),
            "server_version": __version__
        },
        "tools_summary": {
            "total": len(tool_names),
            "ipfs_count": len(ipfs_tools),
            "vfs_count": len(vfs_tools),
            "utility_count": len(utility_tools)
        },
        "tools_by_category": {
            "ipfs": ipfs_tools,
            "vfs": vfs_tools,
            "utility": utility_tools
        },
        "verification_instructions": {
            "message": "To verify tools, use the JSON-RPC endpoint with method 'test_tool'",
            "example": {
                "jsonrpc": "2.0",
                "method": "test_tool",
                "params": {"tool_name": "health_check"},
                "id": 1
            }
        }
    })

# --- JSON-RPC Implementation ---

# Initialize JSON-RPC dispatcher
jsonrpc_dispatcher = Dispatcher()

# JSON-RPC methods
@jsonrpc_dispatcher.add_method
async def ping(**kwargs):
    """Simple ping method for connection testing."""
    return {
        "status": "ok",
        "server": "comprehensive-ipfs-mcp",
        "version": __version__,
        "timestamp": datetime.now().isoformat()
    }

@jsonrpc_dispatcher.add_method
async def initialize(client_info=None, **kwargs):
    """Initialize the connection with details about available tools."""
    logger.info(f"Client initialization request: {client_info}")
    
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    # Group tools by category for better organization
    tool_categories = {
        "ipfs": [name for name in tool_names if name.startswith("ipfs_")],
        "vfs": [name for name in tool_names if name.startswith("vfs_")],
        "utility": [name for name in tool_names if not (name.startswith("ipfs_") or name.startswith("vfs_"))]
    }
    
    return {
        "server": "comprehensive-ipfs-mcp",
        "version": __version__,
        "capabilities": {
            "streaming": True,
            "jsonrpc": True,
            "ipfs": len(tool_categories["ipfs"]) > 0,
            "vfs": len(tool_categories["vfs"]) > 0
        },
        "tools": {
            "categories": tool_categories,
            "total": len(tool_names)
        }
    }

@jsonrpc_dispatcher.add_method
async def test_tool(tool_name=None, **kwargs):
    """Test a specific tool to verify it's working."""
    logger.info(f"Testing tool: {tool_name}")
    
    if not tool_name:
        return {
            "status": "error",
            "message": "No tool name provided. Please specify a tool to test."
        }
    
    tool_names = list(server._tools.keys()) if hasattr(server, "_tools") else []
    
    if tool_name not in tool_names:
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' not found. Available tools: {', '.join(tool_names)}"
        }
    
    try:
        # Create a mock context for testing
        class MockContext:
            async def info(self, message):
                logger.info(f"Tool test info: {message}")
            
            async def error(self, message):
                logger.error(f"Tool test error: {message}")
        
        # Get the tool implementation
        tool_impl = server._tools[tool_name]
        
        # Call the tool with mock parameters (this is simple verification, not full testing)
        if tool_name == "health_check" or tool_name == "system_info":
            # These tools don't need parameters
            result = await tool_impl(MockContext())
        elif tool_name.startswith("ipfs_add"):
            # Test with a sample file
            sample_path = "comprehensive_mcp_server.log"
            if not os.path.exists(sample_path):
                with open(sample_path, "w") as f:
                    f.write("Test content for IPFS add")
            result = await tool_impl(MockContext(), path=sample_path)
        elif tool_name.startswith("ipfs_cat"):
            # Test with a mock CID
            result = await tool_impl(MockContext(), cid="QmTest1234")
        elif tool_name.startswith("vfs_read"):
            # Test with a sample file
            sample_path = "comprehensive_mcp_server.log"
            if not os.path.exists(sample_path):
                with open(sample_path, "w") as f:
                    f.write("Test content for VFS read")
            result = await tool_impl(MockContext(), path=sample_path)
        elif tool_name.startswith("vfs_write"):
            # Use a test file path
            test_path = "test_file_for_vfs_write.txt"
            result = await tool_impl(MockContext(), path=test_path, content="Test content for VFS write")
        else:
            return {
                "status": "skipped",
                "message": f"Test not implemented for tool '{tool_name}'",
                "tool": tool_name
            }
        
        return {
            "status": "success",
            "tool": tool_name,
            "result_summary": {
                "result_type": type(result).__name__,
                "result_keys": list(result.keys()) if isinstance(result, dict) else "N/A",
                "success": result.get("success", "N/A") if isinstance(result, dict) else "N/A"
            }
        }
    except Exception as e:
        logger.error(f"Error testing tool '{tool_name}': {e}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "error",
            "tool": tool_name,
            "error": str(e),
            "error_type": type(e).__name__,
            "message": f"Error testing tool '{tool_name}'"
        }

async def handle_jsonrpc(request):
    """Handle JSON-RPC requests."""
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

# --- Signal handlers ---

def handle_sigterm(sig, frame):
    """Handle SIGTERM signal."""
    logger.info("Received SIGTERM signal, shutting down gracefully...")
    sys.exit(0)

def handle_sigint(sig, frame):
    """Handle SIGINT signal (Ctrl+C)."""
    logger.info("Received SIGINT signal, shutting down gracefully...")
    sys.exit(0)

# --- Application setup ---

def create_app():
    """Create and configure the Starlette application."""
    try:
        # Define routes
        routes = [
            Route("/", homepage),
            Route("/health", health_endpoint),
            Route("/initialize", initialize_endpoint),
            Route("/test", test_endpoint),
            Route("/jsonrpc", handle_jsonrpc, methods=["POST"])
        ]
        
        # Create the application
        app = Starlette(routes=routes)
        
        # Add CORS middleware for cross-origin requests
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Attach the MCP SSE endpoint
        server.attach_to_starlette(app, path="/mcp")
        logger.info("Attached MCP SSE endpoint to Starlette application")
        
        return app
    except Exception as e:
        logger.error(f"Error creating Starlette application: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

# --- Main entry point ---

if __name__ == "__main__":
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Comprehensive IPFS MCP Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to listen on (default: 3000)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Store PID for easier management
    with open("comprehensive_mcp_server.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Set global port
    PORT = args.port
    
    # Register all tools
    if not register_all_tools():
        logger.warning("Some tools may not be available")
    
    # Create the application
    app = create_app()
    
    # Log server information
    logger.info(f"Starting Comprehensive IPFS MCP Server on {args.host}:{args.port}")
    logger.info(f"Server version: {__version__}")
    logger.info(f"Debug mode: {args.debug}")
    
    # Start the server
    log_level = "debug" if args.debug else "info"
    
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level=log_level)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
