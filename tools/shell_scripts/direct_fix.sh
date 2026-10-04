#!/bin/bash
# Direct approach to fix the MCP server

# Kill all existing Python servers
echo "Killing all Python servers..."
pkill -9 -f "python.*mcp.*server"
pkill -9 -f "python.*minimal_mcp_server"
pkill -9 -f "python.*simple_mcp_server"
pkill -9 -f "python.*final_mcp_server"
sleep 2

# Create a standalone server with all the tools
echo "Creating standalone server..."
cat > /home/barberb/ipfs_kit_py/standalone_mcp_server.py << EOF
#!/usr/bin/env python3
"""
Standalone MCP Server with all the necessary tools registered for VS Code
"""

import os
import sys
import json
import uuid
import logging
import asyncio
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("standalone_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("standalone-mcp")

# Define the version
__version__ = "1.0.0"

# Import Starlette components
try:
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, StreamingResponse, Response
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
except ImportError as e:
    logger.error(f"Failed to import Starlette components: {e}")
    logger.error("Please install Starlette with: pip install starlette uvicorn")
    sys.exit(1)

# Global state
PORT = 9996  # VSCode/Cline compatible port
server_start_time = datetime.now()
tools = {}  # Dictionary to store registered tools

class Context:
    """Context class for tool execution."""
    def __init__(self, request_id):
        self.request_id = request_id
        self.logs = []
    
    async def info(self, message):
        logger.info(f"[{self.request_id}] {message}")
        self.logs.append({"level": "info", "message": message})
        return True
    
    async def error(self, message):
        logger.error(f"[{self.request_id}] {message}")
        self.logs.append({"level": "error", "message": message})
        return True
    
    async def warning(self, message):
        logger.warning(f"[{self.request_id}] {message}")
        self.logs.append({"level": "warning", "message": message})
        return True

async def register_tool(name, func, description="", schema=None):
    """Register a tool with the server."""
    global tools
    tools[name] = {"func": func, "description": description, "schema": schema or {}}
    logger.info(f"Registered tool: {name}")
    return True

async def run_tool(name, request_id, **kwargs):
    """Run a registered tool."""
    if name not in tools:
        logger.error(f"Tool not found: {name}")
        return {"error": f"Tool not found: {name}"}
    
    logger.info(f"Running tool: {name}")
    tool = tools[name]
    ctx = Context(request_id)
    
    try:
        result = await tool["func"](ctx, **kwargs)
        return {
            "result": result,
            "logs": ctx.logs
        }
    except Exception as e:
        logger.error(f"Error running tool {name}: {e}")
        logger.error(traceback.format_exc())
        await ctx.error(f"Error: {e}")
        return {
            "error": str(e),
            "logs": ctx.logs
        }

# Define endpoints
async def homepage(request):
    """Handle homepage request."""
    return JSONResponse({
        "message": "Standalone MCP Server is running",
        "version": __version__,
        "tools": list(tools.keys())
    })

async def health_endpoint(request):
    """Handle health check request."""
    return JSONResponse({
        "status": "healthy",
        "version": __version__,
        "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
        "tool_count": len(tools),
        "timestamp": datetime.now().isoformat()
    })

async def initialize_endpoint(request):
    """Handle initialize request for VSCode/Cline compatibility."""
    tools_list = list(tools.keys())
    
    # Create tools with schema for VSCode/Cline
    tools_with_schema = []
    for name, tool in tools.items():
        tools_with_schema.append({
            "name": name,
            "description": tool.get("description", ""),
            "inputSchema": tool.get("schema", {}).get("input", {
                "type": "object",
                "properties": {},
                "required": []
            }),
            "outputSchema": tool.get("schema", {}).get("output", {
                "type": "object",
                "properties": {}
            })
        })
    
    # Format compatible with VSCode/Cline
    return JSONResponse({
        "server_info": {
            "name": "ipfs-kit-mcp",  # Use name expected by VSCode/Cline
            "version": __version__,
            "status": "ready"
        },
        "capabilities": {
            "tools": tools_list,
            "streaming": True
        },
        # Add these fields for VSCode/Cline compatibility
        "tools": tools_with_schema,
        "resources": [
            {
                "uri": "ipfs://info",
                "description": "IPFS node information",
                "mediaType": "application/json"
            },
            {
                "uri": "storage://backends",
                "description": "Available storage backends",
                "mediaType": "application/json"
            }
        ]
    })

async def mcp_endpoint(request):
    """Handle MCP SSE connection."""
    async def event_stream():
        client_id = str(uuid.uuid4())
        logger.info(f"New MCP client connected: {client_id}")
        
        yield f"event: connection\\ndata: {json.dumps({'client_id': client_id})}\\n\\n"
        
        while True:
            await asyncio.sleep(30)
            yield f"event: heartbeat\\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\\n\\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

async def jsonrpc_endpoint(request):
    """Handle JSON-RPC requests for tool invocation."""
    try:
        # Parse the JSON-RPC request
        request_data = await request.json()
        
        # Check if it's a valid JSON-RPC request
        if "jsonrpc" not in request_data or request_data.get("jsonrpc") != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": request_data.get("id", None)
            }, status_code=400)
        
        # Extract the request details
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        logger.info(f"Received JSON-RPC request: method={method}, id={request_id}")
        
        # Check if the method is a tool name
        if method not in tools:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }, status_code=404)
        
        # Run the tool
        result = await run_tool(method, str(uuid.uuid4()), **params)
        
        # Check for errors
        if "error" in result:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(result["error"]), "data": result.get("logs", [])},
                "id": request_id
            })
        
        # Return the successful result
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": result.get("result", {}),
            "id": request_id
        })
    
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            "id": request_data.get("id", None) if 'request_data' in locals() else None
        }, status_code=500)

# Register basic tools
async def register_default_tools():
    """Register default tools."""
    
    # Health check tool
    @register_tool("health_check", description="Check the health of the server")
    async def health_check(ctx, **kwargs):
        """Check the health of the server."""
        await ctx.info("Checking server health...")
        
        health_status = {
            "status": "healthy",
            "version": __version__,
            "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
            "tool_count": len(tools),
            "timestamp": datetime.now().isoformat()
        }
        
        await ctx.info("Health check completed")
        return health_status
    
    # File system tools
    @register_tool("fs_list_directory", description="List files and directories in a path")
    async def fs_list_directory(ctx, path="/", **kwargs):
        """List files and directories in the specified path."""
        await ctx.info(f"Listing directory contents at: {path}")
        
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
    
    @register_tool("fs_read_file", description="Read a file's contents")
    async def fs_read_file(ctx, path, **kwargs):
        """Read the contents of a file."""
        await ctx.info(f"Reading file: {path}")
        
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            await ctx.info("File read successfully")
            return {
                "content": content,
                "path": path,
                "size": len(content)
            }
        except Exception as e:
            await ctx.error(f"Error reading file: {str(e)}")
            return {"error": str(e)}
    
    @register_tool("fs_write_file", description="Write content to a file")
    async def fs_write_file(ctx, path, content, **kwargs):
        """Write content to a file."""
        await ctx.info(f"Writing to file: {path}")
        
        try:
            with open(path, 'w') as f:
                f.write(content)
            
            await ctx.info("File written successfully")
            return {
                "success": True,
                "path": path,
                "size": len(content)
            }
        except Exception as e:
            await ctx.error(f"Error writing file: {str(e)}")
            return {"error": str(e)}
    
    @register_tool("system_info", description="Get system information")
    async def system_info(ctx, **kwargs):
        """Get system information."""
        await ctx.info("Getting system information...")
        
        import platform
        import psutil
        
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count(),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free
            }
        }
        
        await ctx.info("System information retrieved")
        return info
    
    # Register basic IPFS tool
    @register_tool("ipfs_basic_info", description="Get basic IPFS information")
    async def ipfs_basic_info(ctx, **kwargs):
        """Get basic IPFS information."""
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
    
    # Register IPFS mock tools for VS Code integration
    for tool_name in [
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
    ]:
        # Create a closure to capture the tool name
        async def mock_tool_factory(tool_name):
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
        
        # Register the mock tool
        await register_tool(
            name=tool_name,
            func=await mock_tool_factory(tool_name),
            description=f"IPFS tool: {tool_name}",
            schema={
                "input": {"type": "object", "properties": {}, "required": []},
                "output": {"type": "object", "properties": {}}
            }
        )

# Create the application
app = Starlette()

# Add routes
app.routes = [
    Route("/", endpoint=homepage),
    Route("/health", endpoint=health_endpoint),
    Route("/initialize", endpoint=initialize_endpoint, methods=["POST", "GET"]),
    Route("/mcp", endpoint=mcp_endpoint),
    # Add jsonrpc route at both root and api paths
    Route("/jsonrpc", endpoint=jsonrpc_endpoint, methods=["POST"]),
    # VSCode/Cline compatible endpoints
    Route("/api/v0/initialize", endpoint=initialize_endpoint, methods=["POST", "GET"]),
    Route("/api/v0/health", endpoint=health_endpoint),
    Route("/api/v0/sse", endpoint=mcp_endpoint),
    Route("/api/v0/jsonrpc", endpoint=jsonrpc_endpoint, methods=["POST"])
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main function
async def setup():
    """Set up the server."""
    await register_default_tools()
    logger.info("Server setup complete")

@app.on_event("startup")
async def startup_event():
    """Run when the server starts."""
    global server_start_time
    server_start_time = datetime.now()
    logger.info("Server starting...")
    await setup()
    logger.info(f"Server started on port {PORT}")

if __name__ == "__main__":
    import uvicorn
    
    parser = argparse.ArgumentParser(description="Standalone MCP Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to run the server on (default: {PORT})")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    PORT = args.port
    
    logger.info(f"Starting Standalone MCP Server on {args.host}:{PORT}")
    uvicorn.run(app, host=args.host, port=PORT, log_level="debug" if args.debug else "info")
EOF

# Make the server executable
chmod +x /home/barberb/ipfs_kit_py/standalone_mcp_server.py

# Start the server
echo "Starting the standalone server..."
cd /home/barberb/ipfs_kit_py
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Activated virtual environment"
fi

# Install psutil if not already installed
pip install psutil uvicorn starlette

# Run the server
nohup python3 standalone_mcp_server.py --port 9996 > standalone_mcp_server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 5

# Check if server is running
if ps -p $SERVER_PID > /dev/null; then
    echo "Server is running with PID: $SERVER_PID"
    echo "Testing health endpoint..."
    curl -s http://localhost:9996/health
    
    echo -e "\nTesting initialize endpoint..."
    curl -s -X POST http://localhost:9996/initialize | grep -o '"tools":\[[^]]*\]' | wc -l
    
    echo -e "\nAll done! VS Code should now be able to discover the MCP tools."
    echo "You may need to restart VS Code to see the changes."
else
    echo "Server failed to start. Check the log file: standalone_mcp_server.log"
    cat standalone_mcp_server.log
fi
