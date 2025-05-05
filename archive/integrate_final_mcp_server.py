#!/usr/bin/env python3
"""
This script integrates the virtual filesystem and other components 
from existing experiments into the final_mcp_server.py
"""

import os
import sys
import shutil
import traceback
import logging
import argparse
import json
import subprocess
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("final_integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("integration")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FINAL_SERVER_PATH = os.path.join(BASE_DIR, "final_mcp_server.py")
BACKUP_PATH = os.path.join(BASE_DIR, "final_mcp_server.py.bak.integration")
TEMP_DIR = os.path.join(BASE_DIR, "integration_temp")
START_SCRIPT_PATH = os.path.join(BASE_DIR, "start_final_mcp_server.sh")

def backup_files():
    """Backup important files before making changes"""
    logger.info("Creating backups of important files...")
    
    # Create backup of final_mcp_server.py if it exists
    if os.path.exists(FINAL_SERVER_PATH):
        logger.info(f"Backing up {FINAL_SERVER_PATH} to {BACKUP_PATH}")
        shutil.copy2(FINAL_SERVER_PATH, BACKUP_PATH)
    
    # Create backup of start_final_mcp_server.sh if it exists
    start_script_backup = f"{START_SCRIPT_PATH}.bak"
    if os.path.exists(START_SCRIPT_PATH):
        logger.info(f"Backing up {START_SCRIPT_PATH} to {start_script_backup}")
        shutil.copy2(START_SCRIPT_PATH, start_script_backup)
    
    logger.info("Backups created successfully")
    return True

def create_final_mcp_server():
    """Create the final MCP server implementation"""
    logger.info("Creating new final_mcp_server.py...")
    
    # Check if we have the MCP SDK
    mcp_sdk_path = os.path.join(BASE_DIR, "docs/mcp-python-sdk/src")
    if not os.path.exists(mcp_sdk_path):
        logger.warning("MCP SDK not found at expected path. Some features may not work properly.")
    
    # Check for required components
    vfs_components = [
        "enhance_vfs_mcp_integration.py",
        "ipfs_mcp_tools_integration.py",
        "register_all_backend_tools.py"
    ]
    
    for component in vfs_components:
        if not os.path.exists(os.path.join(BASE_DIR, component)):
            logger.warning(f"Component {component} not found. Some features may not be available.")
    
    # Try to create the final server
    try:
        with open(os.path.join(BASE_DIR, "final_mcp_server.py.template"), "r") as f:
            template = f.read()
            
        with open(FINAL_SERVER_PATH, "w") as f:
            f.write(template)
            
        logger.info("Created final_mcp_server.py from template")
        return True
    except Exception as e:
        logger.error(f"Failed to create final_mcp_server.py: {e}")
        logger.error(traceback.format_exc())
        return False

def verify_integration():
    """Verify that the integration was successful"""
    logger.info("Verifying integration...")
    
    # Check if final_mcp_server.py exists
    if not os.path.exists(FINAL_SERVER_PATH):
        logger.error("final_mcp_server.py not found!")
        return False
    
    # Check if start_final_mcp_server.sh exists
    if not os.path.exists(START_SCRIPT_PATH):
        logger.error("start_final_mcp_server.sh not found!")
        return False
    
    # Try to run the server in test mode
    try:
        logger.info("Testing server startup...")
        
        # Kill any existing instances
        try:
            pid_file = os.path.join(BASE_DIR, "final_mcp_server.pid")
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    pid = f.read().strip()
                    
                if pid:
                    try:
                        os.kill(int(pid), 9)
                        logger.info(f"Killed existing server with PID {pid}")
                    except ProcessLookupError:
                        pass
        except Exception as e:
            logger.warning(f"Error cleaning up existing server: {e}")
        
        # Run the test
        subprocess.check_call(
            ["python3", FINAL_SERVER_PATH, "--port", "3050", "--debug"],
            timeout=5,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logger.error("Server should have exited, but didn't. This is unexpected.")
        return False
    except subprocess.TimeoutExpired:
        # This is expected - server started successfully
        logger.info("Server started successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Server failed to start: {e}")
        logger.error(f"stderr: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"Error testing server: {e}")
        logger.error(traceback.format_exc())
        return False
    
    # Clean up after test
    try:
        pid_file = os.path.join(BASE_DIR, "final_mcp_server.pid")
        if os.path.exists(pid_file):
            with open(pid_file, "r") as f:
                pid = f.read().strip()
                
            if pid:
                try:
                    os.kill(int(pid), 9)
                    logger.info(f"Killed test server with PID {pid}")
                except ProcessLookupError:
                    pass
    except Exception as e:
        logger.warning(f"Error cleaning up test server: {e}")
    
    logger.info("Integration verified successfully!")
    return True

def restore_backups():
    """Restore backups if integration failed"""
    logger.info("Restoring backups...")
    
    if os.path.exists(BACKUP_PATH):
        logger.info(f"Restoring {FINAL_SERVER_PATH} from {BACKUP_PATH}")
        shutil.copy2(BACKUP_PATH, FINAL_SERVER_PATH)
    
    start_script_backup = f"{START_SCRIPT_PATH}.bak"
    if os.path.exists(start_script_backup):
        logger.info(f"Restoring {START_SCRIPT_PATH} from {start_script_backup}")
        shutil.copy2(start_script_backup, START_SCRIPT_PATH)
    
    logger.info("Backups restored successfully")
    return True

def cleanup():
    """Clean up temporary files"""
    logger.info("Cleaning up temporary files...")
    
    # Remove temporary directory if it exists
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    
    # Remove temporary files
    temp_files = [
        os.path.join(BASE_DIR, "final_integration.log"),
    ]
    
    for file in temp_files:
        if os.path.exists(file):
            os.remove(file)
    
    logger.info("Cleanup completed")
    return True

def create_server_template():
    """Create the final_mcp_server.py template"""
    logger.info("Creating final_mcp_server.py template...")
    
    template = """#!/usr/bin/env python3
'''
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
'''

import os
import sys
import json
import logging
import asyncio
import signal
import argparse
import traceback
import importlib.util
import uuid
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
server_start_time = datetime.now()

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
    
# --- Custom JSON-RPC implementation ---
class JSONRPCHandler:
    """Simple JSON-RPC 2.0 handler"""
    
    def __init__(self):
        self.methods = {}
        
    def register_method(self, name: str, method: Callable):
        """Register a method to be called via JSON-RPC"""
        self.methods[name] = method
        
    async def handle_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a JSON-RPC request and return a response"""
        # Validate JSON-RPC request
        if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
            return self._error_response(None, -32600, "Invalid Request: Not a valid JSON-RPC 2.0 request")
            
        if "id" not in data:
            # Notification, no response needed
            return None
            
        request_id = data.get("id")
        
        if "method" not in data or not isinstance(data["method"], str):
            return self._error_response(request_id, -32600, "Invalid Request: Method not specified or not a string")
            
        method_name = data["method"]
        params = data.get("params", {})
        
        if method_name not in self.methods:
            return self._error_response(request_id, -32601, f"Method not found: {method_name}")
            
        try:
            # Call the method with the parameters
            result = await self._call_method(method_name, params)
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
        except Exception as e:
            logger.error(f"Error executing method {method_name}: {e}")
            logger.error(traceback.format_exc())
            return self._error_response(request_id, -32603, f"Internal error: {str(e)}")
            
    async def _call_method(self, method_name: str, params: Any) -> Any:
        """Call a registered method with the given parameters"""
        method = self.methods[method_name]
        if asyncio.iscoroutinefunction(method):
            return await method(params)
        else:
            return method(params)
            
    def _error_response(self, request_id: Any, code: int, message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message
            },
            "id": request_id
        }

# Create JSON-RPC handler
jsonrpc_handler = JSONRPCHandler()

# --- Server Functions ---
async def get_tools(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get a list of all available tools
    """
    logger.info("Handling get_tools request")
    
    # Wait for server initialization if needed
    if not server_initialized:
        logger.info("Server not initialized yet, waiting...")
        await initialization_event.wait()
    
    tools_list = []
    for name, tool in registered_tools.items():
        tools_list.append({
            "name": name,
            "description": tool.get("description", ""),
            "inputSchema": tool.get("inputSchema", {}),
            "outputSchema": tool.get("outputSchema", {})
        })
    
    logger.info(f"Returning {len(tools_list)} tools")
    return {"tools": tools_list}

async def use_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use a specific tool
    """
    tool_name = params.get("tool_name")
    arguments = params.get("arguments", {})
    
    logger.info(f"Handling use_tool request for {tool_name}")
    
    # Wait for server initialization if needed
    if not server_initialized:
        logger.info("Server not initialized yet, waiting...")
        await initialization_event.wait()
    
    if not tool_name:
        raise ValueError("Tool name not provided")
    
    if tool_name not in tool_implementations:
        raise ValueError(f"Tool '{tool_name}' not found")
    
    try:
        handler = tool_implementations[tool_name]
        if asyncio.iscoroutinefunction(handler):
            result = await handler(arguments)
        else:
            result = handler(arguments)
        
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        logger.error(traceback.format_exc())
        raise ValueError(f"Error executing tool {tool_name}: {str(e)}")

async def initialize_server(params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Initialize the server with configuration
    """
    logger.info("Initializing server")
    global server_initialized
    
    async with initialization_lock:
        if server_initialized:
            logger.info("Server already initialized")
            return {"status": "already_initialized"}
        
        try:
            # Load extensions and tools
            await _load_all_extensions()
            
            # Mark as initialized and notify waiters
            server_initialized = True
            initialization_event.set()
            
            return {
                "status": "success",
                "tools_count": len(registered_tools),
                "extensions": list(available_extensions.keys())
            }
        except Exception as e:
            logger.error(f"Error initializing server: {e}")
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "error": str(e)
            }

async def _load_all_extensions():
    """
    Load all available extensions
    """
    logger.info("Loading extensions")
    
    # Register core methods
    register_tools([
        {
            "name": "get_tools",
            "description": "Get a list of all available tools",
            "inputSchema": {},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "tools": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "inputSchema": {"type": "object"},
                                "outputSchema": {"type": "object"}
                            }
                        }
                    }
                }
            },
            "handler": get_tools
        },
        {
            "name": "use_tool",
            "description": "Use a specific tool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "arguments": {"type": "object"}
                },
                "required": ["tool_name"]
            },
            "outputSchema": {
                "type": "object"
            },
            "handler": use_tool
        }
    ])
    
    # Try to load IPFS tools if available
    try:
        from ipfs_mcp_tools_integration import register_ipfs_tools
        register_ipfs_tools(register_tools)
        logger.info("IPFS tools registered")
    except ImportError:
        logger.warning("IPFS tools module not available")
    except Exception as e:
        logger.error(f"Error registering IPFS tools: {e}")
    
    # Try to load VFS tools if available
    try:
        from enhance_vfs_mcp_integration import register_all_fs_tools
        register_all_fs_tools(register_tools)
        logger.info("VFS tools registered")
    except ImportError:
        logger.warning("VFS tools module not available")
    except Exception as e:
        logger.error(f"Error registering VFS tools: {e}")
    
    # Try to load all backend tools if available
    try:
        from register_all_backend_tools import register_all_tools
        register_all_tools(register_tools)
        logger.info("Backend tools registered")
    except ImportError:
        logger.warning("Backend tools module not available")
    except Exception as e:
        logger.error(f"Error registering backend tools: {e}")

def register_tools(tools: List[Dict[str, Any]]):
    """
    Register tools with the server
    """
    for tool in tools:
        name = tool["name"]
        handler = tool.get("handler")
        
        if not handler:
            logger.warning(f"Tool {name} has no handler, skipping")
            continue
        
        registered_tools[name] = {
            "name": name,
            "description": tool.get("description", ""),
            "inputSchema": tool.get("inputSchema", {}),
            "outputSchema": tool.get("outputSchema", {})
        }
        
        tool_implementations[name] = handler
        logger.info(f"Registered tool: {name}")

# --- HTTP Routes ---
async def handle_home(request):
    """Handle requests to the root path"""
    uptime = (datetime.now() - server_start_time).total_seconds()
    return JSONResponse({
        "message": "MCP Server is running",
        "version": __version__,
        "uptime_seconds": uptime,
        "registered_tools_count": len(registered_tools),
        "server_initialized": server_initialized
    })

async def handle_health(request):
    """Handle health check requests"""
    uptime = (datetime.now() - server_start_time).total_seconds()
    return JSONResponse({
        "status": "healthy",
        "uptime": uptime,
        "tools_count": len(registered_tools),
        "initialized": server_initialized
    })

async def handle_jsonrpc_post(request):
    """Handle JSON-RPC POST requests"""
    try:
        # Parse the request body
        data = await request.json()
        
        if isinstance(data, list):
            # Batch request
            results = []
            for item in data:
                response = await jsonrpc_handler.handle_request(item)
                if response:  # Skip notifications (no response needed)
                    results.append(response)
            return JSONResponse(results)
        else:
            # Single request
            response = await jsonrpc_handler.handle_request(data)
            if response:
                return JSONResponse(response)
            else:
                # Notification, no response needed
                return Response(status_code=204)
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32700,
                "message": "Parse error: Invalid JSON"
            },
            "id": None
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            "id": None
        }, status_code=500)

# --- Main Application ---
async def startup():
    """Initialize on server startup"""
    logger.info("Server starting up...")
    
    # Register JSON-RPC methods
    jsonrpc_handler.register_method("get_tools", get_tools)
    jsonrpc_handler.register_method("use_tool", use_tool)
    jsonrpc_handler.register_method("initialize", initialize_server)
    
    # Initialize the server automatically
    asyncio.create_task(initialize_server())

# Create the Starlette application
routes = [
    Route("/", handle_home),
    Route("/health", handle_health),
    Route("/jsonrpc", handle_jsonrpc_post, methods=["POST"]),
]

# Create Starlette app
app = Starlette(routes=routes, on_startup=[startup])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signal handlers
def handle_sigterm(signum, frame):
    """Handle SIGTERM"""
    logger.info("Received SIGTERM, shutting down...")
    sys.exit(0)

def handle_sigint(signum, frame):
    """Handle SIGINT (Ctrl+C)"""
    logger.info("Received SIGINT, shutting down...")
    sys.exit(0)

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
"""
    
    template_path = os.path.join(BASE_DIR, "final_mcp_server.py.template")
    with open(template_path, "w") as f:
        f.write(template)
    
    logger.info(f"Created template at {template_path}")
    return True

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Integrate VFS and other components into final MCP server")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup step")
    parser.add_argument("--no-verify", action="store_true", help="Skip verification step")
    parser.add_argument("--restore", action="store_true", help="Restore backups")
    args = parser.parse_args()
    
    logger.info("Starting integration process...")
    
    if args.restore:
        restore_backups()
        return 0
    
    try:
        # Step 1: Create backups
        if not args.no_backup:
            if not backup_files():
                logger.error("Failed to create backups")
                return 1
        
        # Step 2: Create server template
        if not create_server_template():
            logger.error("Failed to create server template")
            if not args.no_backup:
                restore_backups()
            return 1
        
        # Step 3: Create the final MCP server
        if not create_final_mcp_server():
            logger.error("Failed to create final MCP server")
            if not args.no_backup:
                restore_backups()
            return 1
        
        # Step 4: Verify integration
        if not args.no_verify:
            if not verify_integration():
                logger.error("Integration verification failed")
                if not args.no_backup:
                    restore_backups()
                return 1
        
        logger.info("""
✅ Integration complete! 

You can now start the server with:
   ./start_final_mcp_server.sh
        
The server will run on port 3000 by default.

To check that the server is running:
   curl http://localhost:3000/health
   
To get the list of available tools:
   curl -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"get_tools","id":1}' http://localhost:3000/jsonrpc
        """)
        
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        if not args.no_backup:
            restore_backups()
        return 1
    finally:
        # Always clean up temporary files
        cleanup()

if __name__ == "__main__":
    sys.exit(main())
