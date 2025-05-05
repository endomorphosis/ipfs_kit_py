#!/usr/bin/env python3
"""
Minimal MCP Server Implementation

This is a simplified version of the MCP server that works without requiring the full FastMCP module.
It provides a basic JSON-RPC interface for tool registration and execution.
"""

import os
import sys
import json
import logging
import asyncio
import signal
import argparse
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import importlib.util

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/minimal_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("minimal-mcp")

# Define the version
__version__ = "1.0.0"

# Create necessary directories
os.makedirs("logs", exist_ok=True)

# Global state
PORT = 3000
server_start_time = datetime.now()

# Tool registries
registered_tools = {}


class MCPServer:
    """A minimal MCP server implementation."""

    def __init__(self, name="minimal-mcp", instructions="Minimal MCP server with IPFS tools"):
        self.name = name
        self.instructions = instructions
        self._tools = {}
        logger.info(f"Initialized {name} server")

    def tool(self, name=None, description=None):
        """Decorator for registering tools."""
        def decorator(func):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or ""
            
            self._tools[tool_name] = Tool(
                name=tool_name, 
                description=tool_desc,
                func=func
            )
            logger.info(f"Registered tool: {tool_name}")
            return func
        return decorator

    async def use_tool(self, tool_name, **kwargs):
        """Use a specific tool."""
        if tool_name not in self._tools:
            return {"error": f"Tool '{tool_name}' not found"}
        
        tool = self._tools[tool_name]
        logger.info(f"Using tool: {tool_name}")
        
        try:
            # Create a simple context for the tool
            context = SimpleContext(tool_name, kwargs)
            return await tool.run(context)
        except Exception as e:
            error_msg = f"Error using tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {"error": error_msg}
    
    def get_starlette_app(self):
        """Create a Starlette application for serving the MCP server."""
        try:
            from starlette.applications import Starlette
            from starlette.routing import Route
            from starlette.responses import JSONResponse
            from starlette.middleware.cors import CORSMiddleware
            
            # Create a JSON-RPC dispatcher
            dispatcher = JsonRpcDispatcher()
            
            # Add JSON-RPC methods
            @dispatcher.method
            async def ping(**kwargs):
                """Simple ping method to test JSON-RPC connection."""
                return {
                    "status": "ok",
                    "server": self.name,
                    "timestamp": datetime.now().isoformat()
                }
            
            @dispatcher.method
            async def get_tools(**kwargs):
                """Get all registered tools."""
                tools = []
                for name, tool in self._tools.items():
                    tools.append({
                        "name": name,
                        "description": tool.description,
                        "schema": {"type": "object"}  # Simplified schema
                    })
                return tools
            
            @dispatcher.method
            async def use_tool(tool_name, arguments=None, **kwargs):
                """Use a specific tool."""
                arguments = arguments or {}
                return await self.use_tool(tool_name, **arguments)
            
            # Define endpoint handlers
            async def homepage(request):
                """Handle the homepage request."""
                return JSONResponse({
                    "message": f"{self.name} is running",
                    "version": __version__,
                    "port": PORT,
                    "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
                    "registered_tools_count": len(self._tools),
                    "registered_tools": list(self._tools.keys()),
                    "endpoints": {
                        "/": "Home page with server information",
                        "/health": "Health check endpoint",
                        "/jsonrpc": "JSON-RPC endpoint"
                    }
                })
            
            async def health_endpoint(request):
                """Health check endpoint."""
                return JSONResponse({
                    "status": "healthy",
                    "version": __version__,
                    "uptime_seconds": (datetime.now() - server_start_time).total_seconds(),
                    "registered_tools_count": len(self._tools),
                    "timestamp": datetime.now().isoformat()
                })
            
            async def handle_jsonrpc(request):
                """Handle JSON-RPC requests."""
                try:
                    request_json = await request.json()
                    logger.debug(f"Received JSON-RPC request: {request_json}")
                    response = await dispatcher.dispatch(request_json)
                    return JSONResponse(response)
                except Exception as e:
                    logger.error(f"Error handling JSON-RPC request: {e}")
                    logger.error(traceback.format_exc())
                    return JSONResponse(
                        {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},
                        status_code=500
                    )
            
            # Create Starlette app
            app = Starlette(routes=[
                Route("/", endpoint=homepage),
                Route("/health", endpoint=health_endpoint),
                Route("/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]),
                Route("/api/v0/jsonrpc", endpoint=handle_jsonrpc, methods=["POST"]),
            ])
            
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
            logger.error(f"Failed to create Starlette app: {e}")
            return None


class Tool:
    """Represents an MCP tool."""

    def __init__(self, name, description, func):
        self.name = name
        self.description = description
        self.func = func
        self.schema = {"type": "object"}  # Simplified schema
    
    async def run(self, context):
        """Run the tool with the given context."""
        try:
            if asyncio.iscoroutinefunction(self.func):
                return await self.func(context, **context.params)
            else:
                return self.func(context, **context.params)
        except Exception as e:
            logger.error(f"Error running tool {self.name}: {e}")
            logger.error(traceback.format_exc())
            await context.error(f"Error: {str(e)}")
            return {"error": str(e)}


class SimpleContext:
    """A simple context for tool execution."""

    def __init__(self, tool_name, params):
        self.tool_name = tool_name
        self._params = params
    
    @property
    def params(self):
        return self._params
    
    async def info(self, message):
        logger.info(f"[{self.tool_name}] {message}")
    
    async def error(self, message):
        logger.error(f"[{self.tool_name}] {message}")
    
    async def warning(self, message):
        logger.warning(f"[{self.tool_name}] {message}")


class JsonRpcDispatcher:
    """Simple JSON-RPC dispatcher."""

    def __init__(self):
        self.methods = {}
    
    def method(self, func=None, name=None):
        """Decorator for registering methods."""
        if func is not None:
            self.methods[func.__name__] = func
            return func
        
        def wrapper(func):
            self.methods[name or func.__name__] = func
            return func
        return wrapper
    
    async def dispatch(self, request):
        """Dispatch a JSON-RPC request."""
        if isinstance(request, list):
            return [await self._dispatch_single(req) for req in request]
        else:
            return await self._dispatch_single(request)
    
    async def _dispatch_single(self, request):
        """Dispatch a single JSON-RPC request."""
        method_name = request.get('method')
        params = request.get('params', {})
        req_id = request.get('id')
        
        if method_name not in self.methods:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method {method_name} not found"},
                "id": req_id
            }
        
        try:
            result = await self.methods[method_name](**params)
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
        except Exception as e:
            logger.error(f"Error dispatching method {method_name}: {e}")
            logger.error(traceback.format_exc())
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": req_id
            }


# Create server instance
server = MCPServer()


# Register IPFS tools
def register_ipfs_tools():
    """Register basic IPFS tools."""
    logger.info("Registering basic IPFS tools...")
    
    # Try to import unified_ipfs_tools if available
    try:
        import unified_ipfs_tools
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info(f"Registered IPFS tools using unified_ipfs_tools: {result}")
        return True
    except Exception as e:
        logger.warning(f"Could not register IPFS tools from unified_ipfs_tools: {e}")
    
    # Register basic tools directly if unified_ipfs_tools is not available
    @server.tool(name="ipfs_add", description="Add content to IPFS")
    async def ipfs_add(ctx, content: str = "", file_path: str = "", name: str = "file"):
        """Add content to IPFS."""
        await ctx.info(f"Adding content to IPFS: {name}")
        
        try:
            # Simple mock implementation
            import hashlib
            import time
            
            if content:
                # Generate a deterministic hash for the content
                content_bytes = content.encode('utf-8') if isinstance(content, str) else content
                hash_value = hashlib.sha256(content_bytes).hexdigest()
                
                # Format hash as IPFS hash (not a real IPFS hash, just for mock purposes)
                ipfs_hash = f"Qm{hash_value[:44]}"
                
                await ctx.info(f"Added to IPFS with hash: {ipfs_hash} (mock)")
                return {
                    "Hash": ipfs_hash,
                    "Name": name,
                    "Size": len(content_bytes),
                    "timestamp": time.time(),
                    "mock": True
                }
            elif file_path:
                if not os.path.exists(file_path):
                    await ctx.error(f"File not found: {file_path}")
                    return {"error": f"File not found: {file_path}"}
                
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                
                # Generate a deterministic hash for the file content
                hash_value = hashlib.sha256(file_content).hexdigest()
                
                # Format hash as IPFS hash (not a real IPFS hash, just for mock purposes)
                ipfs_hash = f"Qm{hash_value[:44]}"
                
                await ctx.info(f"Added file to IPFS with hash: {ipfs_hash} (mock)")
                return {
                    "Hash": ipfs_hash,
                    "Name": os.path.basename(file_path),
                    "Size": len(file_content),
                    "timestamp": time.time(),
                    "mock": True
                }
            else:
                await ctx.error("Either content or file_path must be provided")
                return {"error": "Either content or file_path must be provided"}
        
        except Exception as e:
            error_msg = f"Error adding to IPFS: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    @server.tool(name="ipfs_cat", description="Get content from IPFS by its hash")
    async def ipfs_cat(ctx, hash: str):
        """Get content from IPFS by its hash."""
        await ctx.info(f"Getting content from IPFS: {hash}")
        
        try:
            # Mock implementation
            import time
            
            # Generate mock content based on the hash
            mock_content = f"Mock content for IPFS hash: {hash}\nGenerated at {time.time()}"
            
            await ctx.info(f"Retrieved mock content for hash: {hash}")
            return {
                "content": mock_content,
                "hash": hash,
                "size": len(mock_content),
                "is_text": True,
                "mock": True
            }
        
        except Exception as e:
            error_msg = f"Error getting content from IPFS: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    logger.info("Basic IPFS tools registered")
    return True


# Register VFS tools
def register_vfs_tools():
    """Register basic VFS tools."""
    logger.info("Registering basic VFS tools...")
    
    # Try to use mcp_vfs_config if available
    try:
        import mcp_vfs_config
        result = mcp_vfs_config.register_vfs_tools(server)
        logger.info(f"Registered VFS tools using mcp_vfs_config: {result}")
        return True
    except Exception as e:
        logger.warning(f"Could not register VFS tools from mcp_vfs_config: {e}")
    
    # Register basic VFS tool directly
    @server.tool(name="vfs_list_files", description="List files and directories")
    async def vfs_list_files(ctx, directory: str = ".", recursive: bool = False):
        """List files and directories."""
        await ctx.info(f"Listing files in {directory}")
        
        try:
            import os
            
            base_dir = os.path.abspath(os.path.join(os.getcwd(), directory))
            
            if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
                await ctx.error(f"Directory not found: {directory}")
                return {"error": f"Directory not found: {directory}"}
            
            result = {"files": [], "directories": []}
            
            if recursive:
                for root, dirs, files in os.walk(base_dir):
                    rel_path = os.path.relpath(root, os.getcwd())
                    for d in dirs:
                        result["directories"].append(os.path.join(rel_path, d))
                    for f in files:
                        result["files"].append(os.path.join(rel_path, f))
            else:
                for entry in os.listdir(base_dir):
                    path = os.path.join(base_dir, entry)
                    if os.path.isdir(path):
                        result["directories"].append(os.path.join(directory, entry))
                    else:
                        result["files"].append(os.path.join(directory, entry))
            
            result["count"] = len(result["files"]) + len(result["directories"])
            await ctx.info(f"Found {result['count']} entries")
            return result
        
        except Exception as e:
            error_msg = f"Error listing files: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            await ctx.error(error_msg)
            return {"error": error_msg}
    
    logger.info("Basic VFS tools registered")
    return True


def register_all_tools():
    """Register all tools."""
    register_ipfs_tools()
    register_vfs_tools()


def main():
    """Main entry point."""
    global PORT
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Minimal MCP Server")
    parser.add_argument("--port", type=int, default=3000, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    PORT = args.port
    
    # Register all tools
    register_all_tools()
    
    # Create Starlette app
    app = server.get_starlette_app()
    
    if app is None:
        logger.error("Failed to create Starlette app")
        return 1
    
    # Run the server
    import uvicorn
    
    logger.info(f"Starting Minimal MCP Server on {args.host}:{PORT}...")
    uvicorn.run(app, host=args.host, port=PORT, log_level="debug" if args.debug else "info")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
