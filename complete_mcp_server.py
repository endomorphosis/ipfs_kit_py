#!/usr/bin/env python3
"""
Complete standalone MCP server with VS Code compatibility
"""

import os
import sys
import json
import uuid
import logging
import asyncio
import argparse
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.routing import Route
    from starlette.responses import JSONResponse, Response, StreamingResponse
    from starlette.requests import Request
except ImportError:
    print("Error: Starlette is required. Please install with: pip install starlette")
    sys.exit(1)

try:
    import uvicorn
except ImportError:
    print("Error: Uvicorn is required. Please install with: pip install uvicorn")
    sys.exit(1)

# Configuration
LOG_FILE = "complete_mcp_server.log"
PORT = 9996  # Default port for VS Code compatibility
HOST = "0.0.0.0"  # Listen on all interfaces by default
DEBUG = False
VERSION = "1.0.0"  # Server version

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("complete-mcp")

# Global variables
server_start_time = datetime.now()
tools = {}  # Dictionary to store registered tools

# Context class for tools
class Context:
    """Context for tool execution."""
    
    def __init__(self, request_id: str):
        """Initialize context."""
        self.request_id = request_id
        self.logs = []
    
    async def info(self, message: str) -> bool:
        """Log an info message."""
        logger.info(f"[{self.request_id}] {message}")
        self.logs.append({"level": "info", "message": message})
        return True
    
    async def warning(self, message: str) -> bool:
        """Log a warning message."""
        logger.warning(f"[{self.request_id}] {message}")
        self.logs.append({"level": "warning", "message": message})
        return True
    
    async def error(self, message: str) -> bool:
        """Log an error message."""
        logger.error(f"[{self.request_id}] {message}")
        self.logs.append({"level": "error", "message": message})
        return True

# Tool registration
async def register_tool(name: str, func, description: str = "", schema: Optional[Dict] = None) -> bool:
    """Register a tool."""
    global tools
    tools[name] = {
        "func": func,
        "description": description,
        "schema": schema or {
            "input": {"type": "object", "properties": {}, "required": []},
            "output": {"type": "object", "properties": {}}
        }
    }
    logger.info(f"Registered tool: {name}")
    return True

# Tool execution
async def run_tool(name: str, request_id: str, **kwargs) -> Dict:
    """Run a registered tool."""
    if name not in tools:
        return {"error": f"Tool not found: {name}"}
    
    tool = tools[name]
    ctx = Context(request_id)
    
    try:
        result = await tool["func"](ctx, **kwargs)
        return {
            "result": result,
            "logs": ctx.logs
        }
    except Exception as e:
        logger.error(f"Error running tool {name}: {str(e)}")
        logger.error(traceback.format_exc())
        await ctx.error(f"Error: {str(e)}")
        return {
            "error": str(e),
            "logs": ctx.logs
        }

# Endpoint handlers
async def homepage(request: Request) -> JSONResponse:
    """Handle homepage request."""
    return JSONResponse({
        "message": "Complete MCP Server",
        "version": VERSION,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "tools": list(tools.keys())
    })

async def health_endpoint(request: Request) -> JSONResponse:
    """Handle health check request."""
    return JSONResponse({
        "status": "healthy",
        "version": VERSION,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "tool_count": len(tools),
        "timestamp": datetime.now().isoformat()
    })

async def initialize_endpoint(request: Request) -> JSONResponse:
    """Handle initialize request."""
    tools_list = [
        {
            "name": name,
            "description": tool["description"],
            "inputSchema": tool["schema"].get("input", {"type": "object", "properties": {}}),
            "outputSchema": tool["schema"].get("output", {"type": "object", "properties": {}})
        }
        for name, tool in tools.items()
    ]
    
    return JSONResponse({
        "server_info": {
            "name": "ipfs-kit-mcp",  # Use name expected by VS Code
            "version": VERSION,
            "status": "ready"
        },
        "capabilities": {
            "tools": list(tools.keys()),
            "streaming": True
        },
        "tools": tools_list,
        "resources": [
            {"uri": "ipfs://info", "description": "IPFS node information", "mediaType": "application/json"},
            {"uri": "storage://backends", "description": "Available storage backends", "mediaType": "application/json"}
        ]
    })

async def mcp_endpoint(request: Request) -> StreamingResponse:
    """Handle MCP SSE endpoint."""
    
    async def event_stream():
        """Generate SSE events."""
        client_id = str(uuid.uuid4())
        yield f"event: connection\ndata: {json.dumps({'client_id': client_id})}\n\n"
        
        while True:
            try:
                await asyncio.sleep(30)
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
            except asyncio.CancelledError:
                logger.info(f"Connection closed for client {client_id}")
                break
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

async def jsonrpc_endpoint(request: Request) -> JSONResponse:
    """Handle JSON-RPC requests."""
    request_id = None
    
    try:
        # Parse request
        request_data = await request.json()
        request_id = request_data.get("id")
        
        # Check JSON-RPC version
        if request_data.get("jsonrpc") != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: Not a valid JSON-RPC 2.0 request"},
                "id": request_id
            }, status_code=400)
        
        # Get method and parameters
        method = request_data.get("method")
        params = request_data.get("params", {})
        
        if not method:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: Method not specified"},
                "id": request_id
            }, status_code=400)
        
        # Check if method exists
        if method not in tools:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }, status_code=404)
        
        # Run the tool
        request_uuid = str(uuid.uuid4())
        result = await run_tool(method, request_uuid, **params)
        
        if "error" in result:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,
                    "message": result["error"],
                    "data": {"logs": result.get("logs", [])}
                },
                "id": request_id
            })
        
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": result["result"],
            "id": request_id
        })
    
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error: Invalid JSON"},
            "id": None
        }, status_code=400)
    
    except Exception as e:
        logger.error(f"Unexpected error in JSON-RPC endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            "id": request_id
        }, status_code=500)

# Register default tools
async def register_default_tools():
    """Register default tools for the server."""
    
    # Health check tool
    async def health_check(ctx, **kwargs):
        await ctx.info("Checking server health...")
        
        health_status = {
            "status": "healthy",
            "version": VERSION,
            "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
            "tool_count": len(tools),
            "timestamp": datetime.now().isoformat()
        }
        
        await ctx.info("Health check completed")
        return health_status
    
    # File system tools
    async def fs_list_directory(ctx, path="/", **kwargs):
        await ctx.info(f"Listing directory: {path}")
        
        try:
            entries = os.listdir(path)
            result = []
            
            for entry in entries:
                entry_path = os.path.join(path, entry)
                entry_type = "directory" if os.path.isdir(entry_path) else "file"
                entry_size = os.path.getsize(entry_path) if entry_type == "file" else 0
                
                result.append({
                    "name": entry,
                    "type": entry_type,
                    "size": entry_size,
                    "path": entry_path
                })
            
            await ctx.info(f"Found {len(result)} entries")
            return {"entries": result}
        except Exception as e:
            await ctx.error(f"Error listing directory: {str(e)}")
            return {"error": str(e)}
    
    async def fs_read_file(ctx, path, **kwargs):
        await ctx.info(f"Reading file: {path}")
        
        try:
            with open(path, "r") as f:
                content = f.read()
            
            await ctx.info(f"Read {len(content)} bytes from file")
            return {"content": content, "size": len(content)}
        except Exception as e:
            await ctx.error(f"Error reading file: {str(e)}")
            return {"error": str(e)}
    
    async def fs_write_file(ctx, path, content, **kwargs):
        await ctx.info(f"Writing to file: {path}")
        
        try:
            with open(path, "w") as f:
                f.write(content)
            
            await ctx.info(f"Wrote {len(content)} bytes to file")
            return {"success": True, "size": len(content)}
        except Exception as e:
            await ctx.error(f"Error writing file: {str(e)}")
            return {"error": str(e)}
    
    async def system_info(ctx, **kwargs):
        await ctx.info("Getting system information...")
        
        import platform
        try:
            import psutil
            memory_info = {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available
            }
            disk_info = {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free
            }
        except ImportError:
            memory_info = {"error": "psutil not available"}
            disk_info = {"error": "psutil not available"}
        
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "memory": memory_info,
            "disk": disk_info
        }
        
        await ctx.info("System information retrieved")
        return info
    
    # Register basic IPFS tool
    async def ipfs_basic_info(ctx, **kwargs):
        await ctx.info("Getting basic IPFS information...")
        
        try:
            # Try to check if IPFS is available
            import subprocess
            result = subprocess.run(["ipfs", "--version"], capture_output=True, text=True)
            ipfs_version = result.stdout.strip() if result.returncode == 0 else "IPFS not available"
            
            return {
                "ipfs_version": ipfs_version,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            await ctx.error(f"Error getting IPFS information: {e}")
            return {"error": str(e)}
    
    # Register tools
    await register_tool("health_check", health_check, "Check the health of the server")
    await register_tool("fs_list_directory", fs_list_directory, "List files and directories in a path")
    await register_tool("fs_read_file", fs_read_file, "Read a file's contents")
    await register_tool("fs_write_file", fs_write_file, "Write content to a file")
    await register_tool("system_info", system_info, "Get system information")
    await register_tool("ipfs_basic_info", ipfs_basic_info, "Get basic IPFS information")
    
    # Register mock IPFS tools for VS Code
    ipfs_tools = [
        "ipfs_files_ls", "ipfs_files_mkdir", "ipfs_files_write", "ipfs_files_read",
        "ipfs_files_rm", "ipfs_files_stat", "ipfs_files_cp", "ipfs_files_mv",
        "ipfs_name_publish", "ipfs_name_resolve", "ipfs_dag_put", "ipfs_dag_get",
        "fs_journal_get_history", "fs_journal_sync", "ipfs_fs_bridge_status", 
        "ipfs_fs_bridge_sync", "s3_store_file", "s3_retrieve_file",
        "filecoin_store_file", "filecoin_retrieve_deal", "huggingface_model_load",
        "huggingface_model_inference", "webrtc_peer_connect", "webrtc_send_data",
        "credential_store", "credential_retrieve", "ipfs_pubsub_publish", 
        "ipfs_pubsub_subscribe", "ipfs_dht_findpeer", "ipfs_dht_findprovs",
        "ipfs_cluster_pin", "ipfs_cluster_status", "ipfs_cluster_peers",
        "lassie_fetch", "lassie_fetch_with_providers", "ai_model_register",
        "ai_dataset_register", "search_content", "storacha_store",
        "storacha_retrieve", "multi_backend_add_backend", "multi_backend_list_backends",
        "streaming_create_stream", "streaming_publish", "monitoring_get_metrics",
        "monitoring_create_alert"
    ]
    
    # Define a factory for mock tools
    async def create_mock_tool(tool_name):
        async def mock_tool(ctx, **kwargs):
            await ctx.info(f"Called {tool_name} with params: {kwargs}")
            await ctx.info(f"This is a mock implementation for VS Code integration")
            return {
                "success": True,
                "warning": "Mock implementation",
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "params": kwargs
            }
        return mock_tool
    
    # Register all mock tools
    for tool_name in ipfs_tools:
        try:
            await register_tool(
                tool_name,
                await create_mock_tool(tool_name),
                f"IPFS tool: {tool_name}"
            )
        except Exception as e:
            logger.error(f"Failed to register mock tool {tool_name}: {str(e)}")
    
    logger.info(f"Registered {len(tools)} tools")

# Create the application with CORS middleware
app = Starlette(
    debug=DEBUG,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True
        )
    ]
)

# Define routes
app.routes = [
    Route("/", endpoint=homepage),
    Route("/health", endpoint=health_endpoint),
    Route("/initialize", endpoint=initialize_endpoint, methods=["GET", "POST"]),
    Route("/mcp", endpoint=mcp_endpoint),
    Route("/jsonrpc", endpoint=jsonrpc_endpoint, methods=["POST"]),
    # VS Code compatible endpoint paths
    Route("/api/v0/initialize", endpoint=initialize_endpoint, methods=["GET", "POST"]),
    Route("/api/v0/health", endpoint=health_endpoint),
    Route("/api/v0/sse", endpoint=mcp_endpoint),
    Route("/api/v0/jsonrpc", endpoint=jsonrpc_endpoint, methods=["POST"])
]

@app.on_event("startup")
async def startup_event():
    """Run when the server starts."""
    global server_start_time
    server_start_time = datetime.now()
    
    logger.info(f"Starting Complete MCP Server v{VERSION}")
    await register_default_tools()
    
    # Create a marker file for VS Code to find
    with open("complete_mcp_server_active.txt", "w") as f:
        f.write(f"Complete MCP server is running on port {PORT}")
    
    logger.info(f"Server ready on port {PORT}")
    logger.info(f"Registered {len(tools)} tools")

# Main function
def main():
    """Run the server."""
    global PORT, HOST, DEBUG
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Complete MCP Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to run the server on (default: {PORT})")
    parser.add_argument("--host", type=str, default=HOST, help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-file", type=str, default=LOG_FILE, help=f"Log file (default: {LOG_FILE})")
    args = parser.parse_args()
    
    # Update global variables
    PORT = args.port
    HOST = args.host
    DEBUG = args.debug
    
    # Write PID file
    with open("complete_mcp_server.pid", "w") as f:
        f.write(str(os.getpid()))
    
    # Kill other MCP servers
    try:
        import signal
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['pid'] == os.getpid():
                continue
            
            cmdline = " ".join(proc.info['cmdline'] or [])
            if ("mcp_server" in cmdline or "mcp" in cmdline and "server" in cmdline) and "python" in cmdline:
                logger.info(f"Killing other MCP server: {proc.info['pid']}")
                try:
                    os.kill(proc.info['pid'], signal.SIGKILL)
                except:
                    pass
    except Exception as e:
        logger.warning(f"Failed to kill other MCP servers: {str(e)}")
    
    # Run the server
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="debug" if DEBUG else "info")

if __name__ == "__main__":
    main()
