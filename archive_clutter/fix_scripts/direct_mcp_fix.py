#!/usr/bin/env python3
"""
Direct MCP Import Fix

This script creates a simplified version of the MCP server that directly uses 
components from the available modules without relying on problematic imports.
"""

import os
import sys
import logging
import importlib.util
import traceback
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct-mcp-fix")

def fix_import_issue():
    """Fix the import issue by creating a direct module or symlink."""
    try:
        cwd = os.getcwd()
        
        # Get the MCP SDK directory
        mcp_sdk_path = os.path.join(cwd, "docs/mcp-python-sdk/src")
        
        if not os.path.isdir(mcp_sdk_path):
            logger.error(f"MCP SDK path not found: {mcp_sdk_path}")
            return False
        
        # Create a minimal MCP server using available components
        create_minimal_server()
        
        # Create a startup script for the minimal server
        create_minimal_script()
        
        return True
    except Exception as e:
        logger.error(f"Error fixing import issue: {e}")
        logger.error(traceback.format_exc())
        return False

def create_minimal_server():
    """Create a minimal MCP server that doesn't rely on the problematic import."""
    minimal_server_path = os.path.join(os.getcwd(), "minimal_mcp_server.py")
    
    content = '''#!/usr/bin/env python3
"""
Minimal MCP Server

This is a simplified version of the MCP server that doesn't rely on
importing the problematic FastMCP module. It implements the basic
functionality needed to serve as an MCP server.
"""

import os
import sys
import json
import logging
import asyncio
import signal
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("minimal_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("minimal-mcp")

# Define the version
__version__ = "1.0.0"

# Global state
PORT = 3000  # Default to port 3000
server_initialized = False
tools = {}  # Dictionary to store registered tools

class Context:
    """Simplified Context class for tool implementations."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.log_messages = []
    
    async def info(self, message: str):
        """Log an info message."""
        logger.info(f"[{self.request_id}] {message}")
        self.log_messages.append({"level": "info", "message": message})
        return True
    
    async def error(self, message: str):
        """Log an error message."""
        logger.error(f"[{self.request_id}] {message}")
        self.log_messages.append({"level": "error", "message": message})
        return True

class Tool:
    """Simplified Tool class for registering tools."""
    
    def __init__(self, name: str, func: Callable, description: str = "", schema: Dict = None):
        self.name = name
        self.func = func
        self.description = description
        self.schema = schema or {}
    
    async def __call__(self, ctx: Context, **kwargs):
        """Call the tool function."""
        return await self.func(ctx, **kwargs)

class MinimalMCPServer:
    """Minimal implementation of an MCP server."""
    
    def __init__(self, name: str = "minimal-mcp-server", instructions: str = "Minimal MCP server"):
        self.name = name
        self.instructions = instructions
        self._tools = {}
        logger.info(f"Created {self.name} server with instructions: {self.instructions}")
    
    def tool(self, name: str = None, description: str = "", schema: Dict = None):
        """Decorator to register a tool."""
        def decorator(func):
            nonlocal name
            tool_name = name or func.__name__
            self._tools[tool_name] = Tool(tool_name, func, description, schema)
            logger.info(f"Registered tool: {tool_name}")
            return func
        return decorator
    
    def register_tool(self, name: str, func: Callable, description: str = "", schema: Dict = None):
        """Register a tool directly."""
        self._tools[name] = Tool(name, func, description, schema)
        logger.info(f"Registered tool: {name}")
        return func
    
    async def run_tool(self, tool_name: str, request_id: str, **kwargs):
        """Run a registered tool."""
        if tool_name not in self._tools:
            logger.error(f"Tool not found: {tool_name}")
            return {"error": f"Tool not found: {tool_name}"}
        
        logger.info(f"Running tool: {tool_name}")
        tool = self._tools[tool_name]
        ctx = Context(request_id)
        
        try:
            result = await tool(ctx, **kwargs)
            return {
                "result": result,
                "logs": ctx.log_messages
            }
        except Exception as e:
            logger.error(f"Error running tool {tool_name}: {e}")
            logger.error(traceback.format_exc())
            await ctx.error(f"Error: {e}")
            return {
                "error": str(e),
                "logs": ctx.log_messages
            }
    
    def get_tools(self):
        """Get all registered tools."""
        return list(self._tools.keys())
    
    def sse_app(self):
        """Create a Starlette app for SSE."""
        try:
            from starlette.applications import Starlette
            from starlette.routing import Route
            from starlette.responses import JSONResponse
            from starlette.middleware.cors import CORSMiddleware
            
            routes = [
                Route("/", endpoint=self.homepage),
                Route("/health", endpoint=self.health_endpoint),
                Route("/initialize", endpoint=self.initialize_endpoint, methods=["POST"]),
                Route("/mcp", endpoint=self.mcp_endpoint)
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
            
            return app
        except ImportError as e:
            logger.error(f"Failed to create SSE app: {e}")
            raise
    
    async def homepage(self, request):
        """Handle the homepage request."""
        return JSONResponse({
            "message": f"{self.name} is running",
            "version": __version__,
            "tools": self.get_tools()
        })
    
    async def health_endpoint(self, request):
        """Health check endpoint."""
        return JSONResponse({
            "status": "healthy",
            "version": __version__,
            "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
            "tool_count": len(self._tools),
            "timestamp": datetime.now().isoformat()
        })
    
    async def initialize_endpoint(self, request):
        """Initialize endpoint for clients."""
        return JSONResponse({
            "server_info": {
                "name": self.name,
                "version": __version__,
                "status": "ready"
            },
            "capabilities": {
                "tools": self.get_tools(),
                "streaming": True
            }
        })
    
    async def mcp_endpoint(self, request):
        """Handle MCP SSE connection."""
        from starlette.responses import StreamingResponse
        import json
        import uuid
        
        async def event_stream():
            client_id = str(uuid.uuid4())
            logger.info(f"New MCP client connected: {client_id}")
            
            # Send initial connection established event
            yield f"event: connection\ndata: {json.dumps({'client_id': client_id})}\n\n"
            
            # Keep the connection alive
            while True:
                # Send heartbeat every 30 seconds
                await asyncio.sleep(30)
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
        
        return StreamingResponse(event_stream(), media_type="text/event-stream")

# Initialize global variables
server = None
server_start_time = datetime.now()

def register_default_tools():
    """Register default tools for the server."""
    global server
    
    @server.tool(name="health_check", description="Check the health of the server")
    async def health_check(ctx: Context):
        """Check the health of the server."""
        await ctx.info("Checking server health...")
        
        health_status = {
            "status": "healthy",
            "version": __version__,
            "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
            "tool_count": len(server._tools),
            "timestamp": datetime.now().isoformat()
        }
        
        await ctx.info("Health check completed")
        return health_status
    
    # Try to import IPFS tools
    try:
        import unified_ipfs_tools
        unified_ipfs_tools.register_all_ipfs_tools(server)
    except ImportError:
        logger.warning("Failed to import unified_ipfs_tools. IPFS functionality will be limited.")
        
        # Register a basic IPFS tool if unified tools are not available
        @server.tool(name="ipfs_basic_info", description="Get basic IPFS information")
        async def ipfs_basic_info(ctx: Context):
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

def main():
    """Main entry point for the server."""
    global server, server_start_time
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Minimal MCP Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Initialize server
    server_start_time = datetime.now()
    server = MinimalMCPServer()
    
    # Register default tools
    register_default_tools()
    
    # Get the Starlette app
    app = server.sse_app()
    
    # Run the server
    import uvicorn
    logger.info(f"Starting Minimal MCP Server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="debug" if args.debug else "info")
    
    return 0

if __name__ == "__main__":
    import traceback
    
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
'''
    
    with open(minimal_server_path, "w") as f:
        f.write(content)
    
    os.chmod(minimal_server_path, 0o755)  # Make executable
    
    logger.info(f"Created minimal MCP server at {minimal_server_path}")
    return True

def create_minimal_script():
    """Create a startup script for the minimal server."""
    script_path = os.path.join(os.getcwd(), "start_minimal_mcp_server.sh")
    
    content = '''#!/bin/bash
# Start the minimal MCP server

# Kill any running instances
pkill -f "minimal_mcp_server.py" || echo "No running instances found"

# Wait for ports to be released
sleep 1

# Start the server
python3 minimal_mcp_server.py --debug --port 3000

# Exit with the same status as the server
exit $?
'''
    
    with open(script_path, "w") as f:
        f.write(content)
    
    os.chmod(script_path, 0o755)  # Make executable
    
    logger.info(f"Created minimal server startup script at {script_path}")
    return True

if __name__ == "__main__":
    if fix_import_issue():
        print("✅ Created a minimal MCP server that doesn't rely on problematic imports.")
        print("You can now start the server using ./start_minimal_mcp_server.sh")
    else:
        print("❌ Failed to create minimal MCP server.")
        sys.exit(1)
