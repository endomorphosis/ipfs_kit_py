#!/usr/bin/env python3
"""
Minimal MCP Server for Testing

This is a simplified MCP server implementation that provides the basic endpoints and
functionality needed for testing, without relying on complex IPFS dependencies.
"""

import os
import sys
import json
import uuid
import logging
import asyncio
import signal
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable, AsyncGenerator

# Import Starlette components
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("minimal_testing_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("minimal-mcp-test")

# Define the version
__version__ = "1.0.0"

# Global state
PORT = 9996  # Default to port 9996 for VSCode/Cline compatibility
server_initialized = False
server_start_time = datetime.now()
tools = {}  # Dictionary to store registered tools
active_connections = set()  # Track SSE connections

class Context:
    """Simplified Context class for tool implementations."""
    
    def __init__(self):
        """Initialize a new context."""
        self.data = {}
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the context."""
        self.data[key] = value
    
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get a value from the context."""
        return self.data.get(key, default)
    
    def has(self, key: str) -> bool:
        """Check if a key exists in the context."""
        return key in self.data

# Create a global context
global_context = Context()

# Virtual filesystem simulation
vfs = {
    "/": {"type": "dir", "children": {}}
}

def register_tool(name: str, handler: Callable, description: str, schema: Dict[str, Any]) -> None:
    """Register a tool with the MCP server."""
    tools[name] = {
        "name": name,
        "description": description,
        "schema": schema,
        "handler": handler
    }
    logger.info(f"Registered tool: {name}")

# Core tools
async def handle_ping(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Handle the ping tool request."""
    return {
        "status": "success",
        "message": "pong",
        "timestamp": datetime.now().isoformat(),
        "elapsed_ms": params.get("delay", 0),
        "server_uptime_seconds": (datetime.now() - server_start_time).total_seconds()
    }

async def handle_health(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Handle the health tool request."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "version": __version__,
        "tools_count": len(tools)
    }

async def handle_list_tools(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Handle the list_tools tool request."""
    tool_list = []
    for name, tool_info in tools.items():
        tool_list.append({
            "name": name,
            "description": tool_info.get("description", ""),
            "schema": tool_info.get("schema", {})
        })
    
    return {
        "tools": tool_list
    }

async def handle_server_info(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Handle the server_info tool request."""
    return {
        "version": __version__,
        "server_start_time": server_start_time.isoformat(),
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "tools_count": len(tools),
        "platform": sys.platform
    }

async def handle_initialize(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Handle the initialize tool request."""
    global server_initialized
    server_initialized = True
    
    # Return server information
    return {
        "initialized": True,
        "timestamp": datetime.now().isoformat(),
        "server_info": {
            "version": __version__,
            "start_time": server_start_time.isoformat()
        },
        "tools_count": len(tools)
    }

# Mock IPFS tools
async def handle_ipfs_version(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_version tool."""
    return {
        "version": "0.14.0-mock",
        "commit": "mock-hash",
        "repo": "12",
        "system": "mock-system"
    }

async def handle_ipfs_add(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_add tool."""
    content = params.get("content", "")
    mock_cid = f"QmMock{hash(content) % 1000000:06d}"
    
    return {
        "cid": mock_cid,
        "size": len(content)
    }

async def handle_ipfs_cat(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_cat tool."""
    cid = params.get("cid", "")
    # For testing, we'll respond with a mock content based on the CID
    return f"Mock content for CID: {cid}"

# Virtual filesystem tools
async def handle_vfs_ls(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """List directory contents in the virtual filesystem."""
    path = params.get("path", "/")
    
    # Navigate to the requested path
    current = vfs
    if path != "/":
        parts = path.strip("/").split("/")
        for part in parts:
            if part and current.get("type") == "dir" and part in current.get("children", {}):
                current = current["children"][part]
            else:
                return {"error": f"Path not found: {path}"}
    
    # List the contents
    entries = []
    if current.get("type") == "dir":
        for name, item in current.get("children", {}).items():
            entries.append({
                "name": name,
                "type": item.get("type", "unknown"),
                "size": item.get("size", 0) if item.get("type") == "file" else 0
            })
    
    return {
        "entries": entries
    }

async def handle_vfs_mkdir(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Create a directory in the virtual filesystem."""
    path = params.get("path", "")
    if not path or path == "/":
        return {"error": "Cannot create root directory"}
    
    # Navigate to the parent directory
    parts = path.strip("/").split("/")
    dirname = parts[-1]
    parent_path = "/" + "/".join(parts[:-1])
    
    parent = vfs
    if parent_path != "/":
        parent_parts = parent_path.strip("/").split("/")
        for part in parent_parts:
            if part and parent.get("type") == "dir" and part in parent.get("children", {}):
                parent = parent["children"][part]
            else:
                return {"error": f"Parent directory not found: {parent_path}"}
    
    # Create the directory
    if parent.get("type") == "dir":
        if dirname in parent.get("children", {}):
            return {"error": f"Path already exists: {path}"}
        
        if "children" not in parent:
            parent["children"] = {}
        
        parent["children"][dirname] = {"type": "dir", "children": {}}
        return {"success": True, "path": path}
    
    return {"error": "Parent is not a directory"}

async def handle_vfs_write(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Write content to a file in the virtual filesystem."""
    path = params.get("path", "")
    content = params.get("content", "")
    
    if not path or path == "/":
        return {"error": "Invalid file path"}
    
    # Navigate to the parent directory
    parts = path.strip("/").split("/")
    filename = parts[-1]
    parent_path = "/" + "/".join(parts[:-1])
    
    parent = vfs
    if parent_path != "/":
        parent_parts = parent_path.strip("/").split("/")
        for part in parent_parts:
            if part and parent.get("type") == "dir" and part in parent.get("children", {}):
                parent = parent["children"][part]
            else:
                return {"error": f"Parent directory not found: {parent_path}"}
    
    # Create/update the file
    if parent.get("type") == "dir":
        if "children" not in parent:
            parent["children"] = {}
        
        parent["children"][filename] = {
            "type": "file",
            "content": content,
            "size": len(content),
            "modified": datetime.now().isoformat()
        }
        
        return {"success": True, "path": path, "size": len(content)}
    
    return {"error": "Parent is not a directory"}

async def handle_vfs_read(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Read content from a file in the virtual filesystem."""
    path = params.get("path", "")
    
    if not path or path == "/":
        return {"error": "Invalid file path"}
    
    # Navigate to the file
    current = vfs
    parts = path.strip("/").split("/")
    
    for i, part in enumerate(parts):
        if i < len(parts) - 1:  # Navigating directories
            if part and current.get("type") == "dir" and part in current.get("children", {}):
                current = current["children"][part]
            else:
                return {"error": f"Path not found: {'/'.join(parts[:i+1])}"}
        else:  # Last part (filename)
            if part in current.get("children", {}):
                file_info = current["children"][part]
                if file_info.get("type") == "file":
                    return {
                        "content": file_info.get("content", ""),
                        "size": file_info.get("size", 0),
                        "modified": file_info.get("modified", "")
                    }
                else:
                    return {"error": f"Not a file: {path}"}
            else:
                return {"error": f"File not found: {path}"}
    
    return {"error": "Invalid path"}

async def handle_vfs_rm(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Remove a file from the virtual filesystem."""
    path = params.get("path", "")
    
    if not path or path == "/":
        return {"error": "Cannot remove root directory"}
    
    # Navigate to the parent directory
    parts = path.strip("/").split("/")
    filename = parts[-1]
    parent_path = "/" + "/".join(parts[:-1])
    
    parent = vfs
    if parent_path != "/":
        parent_parts = parent_path.strip("/").split("/")
        for part in parent_parts:
            if part and parent.get("type") == "dir" and part in parent.get("children", {}):
                parent = parent["children"][part]
            else:
                return {"error": f"Parent directory not found: {parent_path}"}
    
    # Remove the file
    if parent.get("type") == "dir" and "children" in parent and filename in parent["children"]:
        file_info = parent["children"][filename]
        if file_info.get("type") == "file":
            del parent["children"][filename]
            return {"success": True, "path": path}
        else:
            return {"error": f"Not a file: {path}"}
    
    return {"error": f"File not found: {path}"}

async def handle_vfs_rmdir(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Remove a directory from the virtual filesystem."""
    path = params.get("path", "")
    
    if not path or path == "/":
        return {"error": "Cannot remove root directory"}
    
    # Navigate to the parent directory
    parts = path.strip("/").split("/")
    dirname = parts[-1]
    parent_path = "/" + "/".join(parts[:-1])
    
    parent = vfs
    if parent_path != "/":
        parent_parts = parent_path.strip("/").split("/")
        for part in parent_parts:
            if part and parent.get("type") == "dir" and part in parent.get("children", {}):
                parent = parent["children"][part]
            else:
                return {"error": f"Parent directory not found: {parent_path}"}
    
    # Remove the directory
    if parent.get("type") == "dir" and "children" in parent and dirname in parent["children"]:
        dir_info = parent["children"][dirname]
        if dir_info.get("type") == "dir":
            if len(dir_info.get("children", {})) > 0:
                return {"error": f"Directory not empty: {path}"}
            
            del parent["children"][dirname]
            return {"success": True, "path": path}
        else:
            return {"error": f"Not a directory: {path}"}
    
    return {"error": f"Directory not found: {path}"}

# Mock IPFS files tools
async def handle_ipfs_files_mkdir(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_files_mkdir tool."""
    path = params.get("path", "")
    return {
        "success": True,
        "path": path
    }

async def handle_ipfs_files_write(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_files_write tool."""
    path = params.get("path", "")
    content = params.get("content", "")
    return {
        "success": True,
        "path": path,
        "size": len(content)
    }

async def handle_ipfs_files_read(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_files_read tool."""
    path = params.get("path", "")
    return {
        "content": f"Mock content for MFS path: {path}",
        "size": len(f"Mock content for MFS path: {path}")
    }

async def handle_ipfs_files_ls(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_files_ls tool."""
    path = params.get("path", "")
    return {
        "entries": [
            {"name": "test1.txt", "type": "file", "size": 1024},
            {"name": "test2.txt", "type": "file", "size": 2048},
            {"name": "testdir", "type": "dir", "size": 0}
        ]
    }

async def handle_ipfs_files_rm(params: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """Mock ipfs_files_rm tool."""
    path = params.get("path", "")
    return {
        "success": True,
        "path": path
    }

# Register all tools
def register_all_tools():
    # Core tools
    register_tool("ping", handle_ping, "Test the server's ping/pong functionality", {
        "type": "object",
        "properties": {
            "delay": {"type": "integer", "description": "Optional delay in milliseconds"}
        }
    })
    
    register_tool("health", handle_health, "Check the health of the server", {
        "type": "object",
        "properties": {}
    })
    
    register_tool("list_tools", handle_list_tools, "List all available tools", {
        "type": "object",
        "properties": {}
    })
    
    register_tool("server_info", handle_server_info, "Get server information", {
        "type": "object",
        "properties": {}
    })
    
    register_tool("initialize", handle_initialize, "Initialize the server", {
        "type": "object",
        "properties": {}
    })
    
    # Mock IPFS tools
    register_tool("ipfs_version", handle_ipfs_version, "Get IPFS version information", {
        "type": "object",
        "properties": {}
    })
    
    register_tool("ipfs_add", handle_ipfs_add, "Add content to IPFS", {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The content to add to IPFS"}
        },
        "required": ["content"]
    })
    
    register_tool("ipfs_cat", handle_ipfs_cat, "Get content from IPFS", {
        "type": "object",
        "properties": {
            "cid": {"type": "string", "description": "The CID of the content to get"}
        },
        "required": ["cid"]
    })
    
    # VFS tools
    register_tool("vfs_ls", handle_vfs_ls, "List directory contents in the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The path to list"}
        }
    })
    
    register_tool("vfs_mkdir", handle_vfs_mkdir, "Create a directory in the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The directory path to create"}
        },
        "required": ["path"]
    })
    
    register_tool("vfs_write", handle_vfs_write, "Write content to a file in the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to write to"},
            "content": {"type": "string", "description": "The content to write"}
        },
        "required": ["path", "content"]
    })
    
    register_tool("vfs_read", handle_vfs_read, "Read content from a file in the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to read from"}
        },
        "required": ["path"]
    })
    
    register_tool("vfs_rm", handle_vfs_rm, "Remove a file from the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to remove"}
        },
        "required": ["path"]
    })
    
    register_tool("vfs_rmdir", handle_vfs_rmdir, "Remove a directory from the virtual filesystem", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The directory path to remove"}
        },
        "required": ["path"]
    })
    
    # Mock IPFS files tools
    register_tool("ipfs_files_mkdir", handle_ipfs_files_mkdir, "Create a directory in the MFS", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The directory path to create in MFS"}
        },
        "required": ["path"]
    })
    
    register_tool("ipfs_files_write", handle_ipfs_files_write, "Write content to a file in the MFS", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to write to in MFS"},
            "content": {"type": "string", "description": "The content to write"}
        },
        "required": ["path", "content"]
    })
    
    register_tool("ipfs_files_read", handle_ipfs_files_read, "Read content from a file in the MFS", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to read from in MFS"}
        },
        "required": ["path"]
    })
    
    register_tool("ipfs_files_ls", handle_ipfs_files_ls, "List directory contents in the MFS", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The path to list in MFS"}
        }
    })
    
    register_tool("ipfs_files_rm", handle_ipfs_files_rm, "Remove a file or directory from the MFS", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The path to remove from MFS"}
        },
        "required": ["path"]
    })

# JSONRPC handler
async def handle_jsonrpc(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        
        jsonrpc = data.get("jsonrpc")
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id")
        
        if jsonrpc != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": request_id
            })
        
        if not method:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Method not specified"},
                "id": request_id
            })
        
        if method not in tools:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            })
        
        # Create a new context for this request
        request_context = Context()
        request_context.set("request_id", request_id)
        request_context.set("timestamp", datetime.now().isoformat())
        
        # Handle the tool request
        try:
            result = await tools[method]["handler"](params, request_context)
            
            # Send SSE notification
            await send_tool_event(method, params, result)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            })
        except Exception as e:
            logger.exception(f"Error handling tool request: {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": request_id
            })
    
    except Exception as e:
        logger.exception("Error processing JSON-RPC request")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            "id": None
        })

# SSE handling
async def sse_endpoint(request: Request) -> StreamingResponse:
    async def event_generator():
        # Register this connection
        connection_id = str(uuid.uuid4())
        active_connections.add(connection_id)
        
        try:
            # Send initial server_info event
            tool_list = []
            for name, tool_info in tools.items():
                tool_list.append({
                    "name": name,
                    "description": tool_info.get("description", "")
                })
            
            yield f"event: server_info\n"
            yield f"data: {json.dumps({
                'type': 'server_info',
                'timestamp': datetime.now().isoformat(),
                'version': __version__,
                'tools': tool_list
            })}\n\n"
            
            # Keep the connection open
            while True:
                await asyncio.sleep(30)
                
                # Send a heartbeat event
                yield f"event: heartbeat\n"
                yield f"data: {json.dumps({
                    'type': 'heartbeat',
                    'timestamp': datetime.now().isoformat()
                })}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up on disconnect
            if connection_id in active_connections:
                active_connections.remove(connection_id)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Helper to send SSE events when tools are called
async def send_tool_event(method: str, params: Dict[str, Any], result: Any):
    # Don't attempt to send events if there are no active connections
    if not active_connections:
        return
    
    # Create event data
    event_data = {
        "type": "tool_call",
        "timestamp": datetime.now().isoformat(),
        "method": method,
        "params": params,
        "result": result
    }
    
    # We would broadcast this to all connections if this was a real implementation
    # For this mock server, we just log it
    logger.debug(f"Would send SSE event: {json.dumps(event_data)}")

# Health check endpoint
async def health_endpoint(request: Request) -> JSONResponse:
    uptime = (datetime.now() - server_start_time).total_seconds()
    return JSONResponse({
        "status": "healthy",
        "uptime": uptime,
        "version": __version__,
        "tools_count": len(tools)
    })

# Create routes
routes = [
    Route("/jsonrpc", handle_jsonrpc, methods=["POST"]),
    Route("/sse", sse_endpoint, methods=["GET"]),
    Route("/health", health_endpoint, methods=["GET"])
]

# Create the application
app = Starlette(
    debug=True,
    routes=routes,
    on_startup=[register_all_tools]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)

# Main entry point
if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Minimal MCP Test Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=PORT, help="Port to run the server on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Update the global port
    PORT = args.port
    
    # Register the signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the server
    logger.info(f"Starting Minimal MCP Test Server v{__version__}")
    logger.info(f"Listening on {args.host}:{args.port}")
    
    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
