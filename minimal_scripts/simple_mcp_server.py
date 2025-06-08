#!/usr/bin/env python3
"""
Simple MCP Server

This is a very simplified MCP server that doesn't rely on any external
dependencies except for Starlette and Uvicorn.
"""

import os
import sys
import json
import uuid
import logging
import asyncio
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("simple-mcp")

# Define the version
__version__ = "1.0.0"

# Global state
PORT = 3000  # Default to port 3000
server_start_time = datetime.now()

# Import Starlette components
try:
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import JSONResponse, StreamingResponse
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
except ImportError as e:
    logger.error(f"Failed to import Starlette components: {e}")
    logger.error("Please install Starlette with: pip install starlette uvicorn")
    sys.exit(1)

class Context:
    """Simple context for tool execution."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.logs = []
    
    async def info(self, message: str):
        logger.info(f"[{self.request_id}] {message}")
        self.logs.append({"level": "info", "message": message})
        return True
    
    async def error(self, message: str):
        logger.error(f"[{self.request_id}] {message}")
        self.logs.append({"level": "error", "message": message})
        return True

# Define tools registry
tools = {}

async def register_tool(name, func, description=""):
    """Register a tool with the server."""
    global tools
    tools[name] = {"func": func, "description": description}
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
        import traceback
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
        "message": "Simple MCP Server is running",
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
    """Handle initialize request."""
    return JSONResponse({
        "server_info": {
            "name": "simple-mcp-server",
            "version": __version__,
            "status": "ready"
        },
        "capabilities": {
            "tools": list(tools.keys()),
            "streaming": True
        }
    })

async def mcp_endpoint(request):
    """Handle MCP SSE connection."""
    async def event_stream():
        client_id = str(uuid.uuid4())
        logger.info(f"New MCP client connected: {client_id}")
        
        yield f"event: connection\ndata: {json.dumps({'client_id': client_id})}\n\n"
        
        while True:
            await asyncio.sleep(30)
            yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

async def tool_endpoint(request):
    """Handle tool execution request."""
    try:
        data = await request.json()
        tool_name = data.get("tool")
        params = data.get("params", {})
        request_id = data.get("request_id", str(uuid.uuid4()))
        
        if not tool_name:
            return JSONResponse({"error": "Missing tool name"}, status_code=400)
        
        result = await run_tool(tool_name, request_id, **params)
        return JSONResponse(result)
    except Exception as e:
        import traceback
        logger.error(f"Error handling tool request: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse({"error": str(e)}, status_code=500)

# Define the app
app = Starlette()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define routes
app.routes = [
    Route("/", endpoint=homepage),
    Route("/health", endpoint=health_endpoint),
    Route("/initialize", endpoint=initialize_endpoint, methods=["POST"]),
    Route("/tool", endpoint=tool_endpoint, methods=["POST"]),
    Route("/mcp", endpoint=mcp_endpoint)
]

# Register default tools
async def register_default_tools():
    """Register default tools."""
    
    async def health_check(ctx, **kwargs):
        """Check server health."""
        await ctx.info("Checking server health...")
        
        health_status = {
            "status": "healthy",
            "version": __version__,
            "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
            "timestamp": datetime.now().isoformat()
        }
        
        await ctx.info("Health check completed")
        return health_status
    
    await register_tool("health_check", health_check, "Check server health")
    
    async def list_tools(ctx, **kwargs):
        """List all available tools."""
        await ctx.info("Listing available tools...")
        
        tool_list = []
        for name, tool in tools.items():
            tool_list.append({
                "name": name,
                "description": tool.get("description", "")
            })
        
        await ctx.info(f"Found {len(tool_list)} tools")
        return tool_list
    
    await register_tool("list_tools", list_tools, "List all available tools")

# Main entry point
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple MCP Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    args = parser.parse_args()
    
    global PORT
    PORT = args.port
    
    # Register default tools
    asyncio.run(register_default_tools())
    
    # Run the server
    import uvicorn
    logger.info(f"Starting Simple MCP Server on {args.host}:{PORT}")
    uvicorn.run(app, host=args.host, port=PORT)
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        import traceback
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
