#!/usr/bin/env python3
"""
Minimal MCP Server

This is a simplified version of the MCP server that doesn't rely on
importing the problematic FastMCP module. It implements the basic
functionality needed to serve as an MCP server.
"""

import os
import sys
import json
import uuid
import logging
import anyio
import signal
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable

# Import Starlette components at the module level
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware

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
PORT = 9996  # Default to port 9996 for VSCode/Cline compatibility
server_initialized = False
server_start_time = datetime.now()
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
                Route("/mcp", endpoint=self.mcp_endpoint),
                # Add direct jsonrpc endpoint for VS Code
                Route("/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=["POST"]),
                # VSCode/Cline compatible endpoints
                Route("/api/v0/initialize", endpoint=self.initialize_endpoint, methods=["POST"]),
                Route("/api/v0/health", endpoint=self.health_endpoint),
                Route("/api/v0/sse", endpoint=self.mcp_endpoint),
                Route("/api/v0/jsonrpc", endpoint=self.jsonrpc_endpoint, methods=["POST"])
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
        tools_list = self.get_tools()
        
        # Create detailed tool info with schemas for VSCode/Cline
        tools_with_schema = []
        for tool_name in tools_list:
            tool = self._tools.get(tool_name)
            if tool:
                tools_with_schema.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.schema.get("input", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }),
                    "outputSchema": tool.schema.get("output", {
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
                await anyio.sleep(30)
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
        
        return StreamingResponse(event_stream(), media_type="text/event-stream")
    
    async def jsonrpc_endpoint(self, request):
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
            
            # Special handling for mcp/execute method
            if method == "mcp/execute":
                # Extract the tool name and parameters
                tool_name = params.get("name")
                tool_params = params.get("params", {})
                
                if not tool_name:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "error": {"code": -32602, "message": "Invalid params: missing tool name"},
                        "id": request_id
                    }, status_code=400)
                
                # Check if the tool exists
                if tool_name not in self._tools:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                        "id": request_id
                    }, status_code=404)
                
                logger.info(f"Executing tool via mcp/execute: {tool_name}")
                # Run the tool with the provided parameters
                result = await self.run_tool(tool_name, str(uuid.uuid4()), **(tool_params or {}))
                
                # Wrap the result for mcp/execute
                result = {"success": True, "result": result.get("result", {})}
            else:
                # Check if the method is a direct tool name
                if method not in self._tools:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                        "id": request_id
                    }, status_code=404)
                
                # Run the tool directly
                result = await self.run_tool(method, str(uuid.uuid4()), **params)
            
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
        
    @server.tool(name="ping", description="JSON-RPC ping method")
    async def ping(ctx: Context):
        """Respond to ping requests for JSON-RPC compatibility."""
        await ctx.info("Responding to ping request")
        return "pong"
        
    # Add some basic file system tools that don't rely on external dependencies
    @server.tool(name="fs_list_directory", description="List files and directories in a path")
    async def fs_list_directory(ctx: Context, path: str = "/"):
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
    
    @server.tool(name="fs_read_file", description="Read a file's contents")
    async def fs_read_file(ctx: Context, path: str):
        """Read the contents of a file."""
        await ctx.info(f"Reading file: {path}")
        
        try:
            with open(path, 'r') as f:
                content = f.read()
            
            await ctx.info(f"Successfully read {len(content)} bytes")
            return {"content": content}
        except Exception as e:
            await ctx.error(f"Error reading file: {str(e)}")
            return {"error": str(e)}
    
    @server.tool(name="fs_write_file", description="Write content to a file")
    async def fs_write_file(ctx: Context, path: str, content: str):
        """Write content to a file."""
        await ctx.info(f"Writing to file: {path}")
        
        try:
            with open(path, 'w') as f:
                f.write(content)
            
            await ctx.info(f"Successfully wrote {len(content)} bytes")
            return {"success": True, "bytes_written": len(content)}
        except Exception as e:
            await ctx.error(f"Error writing file: {str(e)}")
            return {"error": str(e)}
    
    @server.tool(name="system_info", description="Get system information")
    async def system_info(ctx: Context):
        """Get basic system information."""
        await ctx.info("Retrieving system information...")
        
        import platform
        
        info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "processor": platform.processor(),
            "machine": platform.machine()
        }
        
        await ctx.info("System information retrieved")
        return info
    
    # Try to import IPFS tools but with fallback for each component
    # First, register the IPFS basic info tool as a fallback
    @server.tool(name="ipfs_basic_info", description="Get basic IPFS information")
    async def ipfs_basic_info(ctx: Context):
        """Get basic IPFS information."""
        await ctx.info("Getting basic IPFS information...")
        
        try:
            # Try to check if IPFS is available
            import subprocess
            result = subprocess.run(["ipfs", "--version"], capture_output=True, text=True)
            ipfs_version = result.stdout.strip() if result.returncode == 0 else "IPFS not available"
            
            # Try to get IPFS ID
            try:
                id_result = subprocess.run(["ipfs", "id", "-f=<id>"], capture_output=True, text=True)
                ipfs_id = id_result.stdout.strip() if id_result.returncode == 0 else "Unknown"
            except Exception:
                ipfs_id = "Unknown"
            
            return {
                "ipfs_version": ipfs_version,
                "ipfs_id": ipfs_id,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            await ctx.error(f"Error getting IPFS information: {e}")
            return {"error": str(e)}
    
    # Register IPFS version tool
    @server.tool(name="ipfs_version", description="Get the IPFS version information")
    async def ipfs_version(ctx: Context):
        """Get IPFS version information."""
        await ctx.info("Getting IPFS version...")
        
        try:
            import subprocess
            result = subprocess.run(["ipfs", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                await ctx.info(f"IPFS version: {version}")
                return {
                    "success": True,
                    "version": version,
                    "versionInfo": {
                        "Version": version.replace("ipfs version ", "")
                    }
                }
            else:
                await ctx.error("Failed to get IPFS version")
                return {"success": False, "error": "IPFS command failed"}
        except Exception as e:
            await ctx.error(f"Error getting IPFS version: {e}")
            return {"success": False, "error": str(e)}
    
    # Register ipfs_add and ipfs_cat tools
    @server.tool(name="ipfs_add", description="Add content to IPFS")
    async def ipfs_add(ctx: Context, content=None, encoding="utf-8", path=None, filename=None, pin=False):
        """Add content to IPFS."""
        await ctx.info("Adding content to IPFS...")
        
        try:
            import base64
            import tempfile
            import subprocess
            import os
            
            if not content and not path:
                await ctx.error("Either content or path must be provided")
                return {"success": False, "error": "Either content or path must be provided"}
                
            # Build the IPFS add command
            cmd = ["ipfs", "add", "-Q"]
            
            # Add pin option if requested
            if pin:
                await ctx.info("Content will be pinned")
            else:
                cmd.append("--pin=false")
                
            # Handle file path or content
            if path:
                # Add file at path
                await ctx.info(f"Adding file from path: {path}")
                cmd.append(path)
                actual_path = path
            else:
                # Add content from parameter
                await ctx.info("Adding content from parameter")
                
                # Decode content if needed
                if encoding == "base64":
                    try:
                        decoded_content = base64.b64decode(content)
                    except Exception:
                        await ctx.error("Failed to decode base64 content")
                        return {"success": False, "error": "Failed to decode base64 content"}
                else:
                    # Treat as utf-8 string
                    decoded_content = content.encode("utf-8")
                
                # Write to temporary file with filename if provided
                temp_dir = tempfile.mkdtemp()
                if filename:
                    file_path = os.path.join(temp_dir, filename)
                    await ctx.info(f"Using filename: {filename}")
                else:
                    file_path = os.path.join(temp_dir, "tmp_content")
                    
                with open(file_path, "wb") as f:
                    f.write(decoded_content)
                
                cmd.append(file_path)
                actual_path = file_path
            
            # Execute IPFS add command
            await ctx.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                cid = result.stdout.strip()
                await ctx.info(f"Content added with CID: {cid}")
                
                # Get file size
                if content:
                    size = len(content)
                else:
                    try:
                        size = os.path.getsize(actual_path)
                    except:
                        size = 0
                        
                return {
                    "success": True,
                    "cid": cid,
                    "size": size,
                    "path": filename or actual_path,
                    "hash": cid,  # For backward compatibility
                    "Hash": cid   # For backward compatibility
                }
            else:
                await ctx.error(f"IPFS add failed: {result.stderr}")
                return {"success": False, "error": f"IPFS add failed: {result.stderr}"}
                
        except Exception as e:
            await ctx.error(f"Error adding to IPFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="ipfs_cat", description="Get content from IPFS")
    async def ipfs_cat(ctx: Context, path=None, cid=None):
        """Get content from IPFS."""
        ipfs_path = path or cid
        if not ipfs_path:
            await ctx.error("Path or CID must be provided")
            return {"error": "Path or CID must be provided"}
            
        await ctx.info(f"Getting content from IPFS: {ipfs_path}")
        
        try:
            import subprocess
            import base64
            
            result = subprocess.run(["ipfs", "cat", ipfs_path], capture_output=True)
            
            if result.returncode == 0:
                # Return content (try to decode as UTF-8 first, fallback to base64)
                try:
                    content = result.stdout.decode("utf-8")
                    encoding = "utf-8"
                except UnicodeDecodeError:
                    # Return as base64 if not valid UTF-8
                    content = base64.b64encode(result.stdout).decode("utf-8")
                    encoding = "base64"
                    
                await ctx.info(f"Successfully retrieved content from IPFS")
                return {
                    "success": True,
                    "content": content,
                    "encoding": encoding,
                    "size": len(result.stdout),
                    "cid": ipfs_path
                }
            else:
                await ctx.error(f"IPFS cat failed: {result.stderr.decode()}")
                return {"error": f"IPFS cat failed: {result.stderr.decode()}"}
                
        except Exception as e:
            await ctx.error(f"Error getting content from IPFS: {e}")
            return {"error": str(e)}
    
    # Register Mutable File System (MFS) tools
    @server.tool(name="ipfs_files_mkdir", description="Make directory in IPFS MFS")
    async def ipfs_files_mkdir(ctx: Context, path=None, parents=True):
        """Make directory in IPFS MFS."""
        if not path:
            await ctx.error("Path must be provided")
            return {"error": "Path must be provided"}
            
        await ctx.info(f"Creating directory in MFS: {path}")
        
        try:
            import subprocess
            cmd = ["ipfs", "files", "mkdir"]
            
            if parents:
                cmd.append("--parents")
                
            cmd.append(path)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                await ctx.info(f"Directory created: {path}")
                return {"success": True, "path": path}
            else:
                await ctx.error(f"Failed to create directory: {result.stderr}")
                return {"error": f"Failed to create directory: {result.stderr}"}
                
        except Exception as e:
            await ctx.error(f"Error creating directory in MFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="ipfs_files_write", description="Write to a file in IPFS MFS")
    async def ipfs_files_write(ctx: Context, path=None, content=None, encoding="utf-8", create=True, truncate=True):
        """Write to a file in IPFS MFS."""
        if not path or content is None:
            await ctx.error("Path and content must be provided")
            return {"error": "Path and content must be provided"}
            
        await ctx.info(f"Writing to file in MFS: {path}")
        
        try:
            import base64
            import tempfile
            import subprocess
            
            # Decode content if needed
            if encoding == "base64":
                try:
                    decoded_content = base64.b64decode(content)
                except Exception:
                    await ctx.error("Failed to decode base64 content")
                    return {"error": "Failed to decode base64 content"}
            else:
                # Treat as utf-8 string
                decoded_content = content.encode("utf-8")
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(decoded_content)
                tmp_path = tmp.name
            
            # Build command
            cmd = ["ipfs", "files", "write"]
            
            if create:
                cmd.append("--create")
                
            if truncate:
                cmd.append("--truncate")
                
            cmd.extend([path, tmp_path])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                await ctx.info(f"File written: {path}")
                return {"success": True, "path": path, "size": len(decoded_content)}
            else:
                await ctx.error(f"Failed to write file: {result.stderr}")
                return {"error": f"Failed to write file: {result.stderr}"}
                
        except Exception as e:
            await ctx.error(f"Error writing to file in MFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="ipfs_files_read", description="Read a file from IPFS MFS")
    async def ipfs_files_read(ctx: Context, path=None, offset=0, count=-1):
        """Read a file from IPFS MFS."""
        if not path:
            await ctx.error("Path must be provided")
            return {"error": "Path must be provided"}
            
        await ctx.info(f"Reading file from MFS: {path}")
        
        try:
            import subprocess
            import base64
            
            cmd = ["ipfs", "files", "read"]
            
            if offset > 0:
                cmd.extend(["--offset", str(offset)])
                
            if count >= 0:
                cmd.extend(["--count", str(count)])
                
            cmd.append(path)
            
            result = subprocess.run(cmd, capture_output=True)
            
            if result.returncode == 0:
                # Return as base64 to handle binary data
                encoded = base64.b64encode(result.stdout).decode("utf-8")
                await ctx.info(f"Successfully read file: {path}, {len(result.stdout)} bytes")
                return {
                    "data": encoded, 
                    "encoding": "base64",
                    "size": len(result.stdout)
                }
            else:
                await ctx.error(f"Failed to read file: {result.stderr.decode()}")
                return {"error": f"Failed to read file: {result.stderr.decode()}"}
                
        except Exception as e:
            await ctx.error(f"Error reading file from MFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="ipfs_files_ls", description="List directory contents in IPFS MFS")
    async def ipfs_files_ls(ctx: Context, path="/", long=False):
        """List directory contents in IPFS MFS."""
        await ctx.info(f"Listing directory in MFS: {path}")
        
        try:
            import subprocess
            import json
            
            cmd = ["ipfs", "files", "ls"]
            
            if long:
                cmd.append("--long")
                
            cmd.append(path)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse the plain text output format
                entries = []
                lines = result.stdout.strip()
                if lines:
                    entries = lines.split('\n')
                
                # Format in a structure similar to what the tests expect
                parsed_entries = []
                for entry in entries:
                    if long:
                        # Parse long format if used
                        parts = entry.split()
                        if len(parts) >= 3:
                            size = parts[0]
                            name = parts[-1]
                            parsed_entries.append({"Name": name, "Size": size, "Type": "file"})
                    else:
                        # Simple format just has the name
                        parsed_entries.append({"Name": entry, "Type": "unknown"})
                        
                await ctx.info(f"Successfully listed directory: {path}, {len(parsed_entries)} entries")
                return {"Entries": parsed_entries, "success": True}
            else:
                await ctx.error(f"Failed to list directory: {result.stderr}")
                return {"error": f"Failed to list directory: {result.stderr}", "success": False}
                
        except Exception as e:
            await ctx.error(f"Error listing directory in MFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="ipfs_files_rm", description="Remove files from IPFS MFS")
    async def ipfs_files_rm(ctx: Context, path=None, recursive=False):
        """Remove files from IPFS MFS."""
        if not path:
            await ctx.error("Path must be provided")
            return {"error": "Path must be provided"}
            
        await ctx.info(f"Removing from MFS: {path}")
        
        try:
            import subprocess
            
            cmd = ["ipfs", "files", "rm"]
            
            if recursive:
                cmd.append("-r")
                
            cmd.append(path)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                await ctx.info(f"Successfully removed: {path}")
                return {"success": True, "path": path}
            else:
                await ctx.error(f"Failed to remove: {result.stderr}")
                return {"error": f"Failed to remove: {result.stderr}"}
                
        except Exception as e:
            await ctx.error(f"Error removing from MFS: {e}")
            return {"error": str(e)}
            
    # Register virtual filesystem (VFS) tools
    @server.tool(name="vfs_mount", description="Mount a CID to the virtual filesystem")
    async def vfs_mount(ctx: Context, cid=None, path=None):
        """Mount a CID to the virtual filesystem."""
        if not cid or not path:
            await ctx.error("CID and path must be provided")
            return {"error": "CID and path must be provided"}
            
        await ctx.info(f"Mounting CID {cid} to virtual filesystem at {path}")
        
        try:
            # This is just a mock implementation that simulates mounting
            # In a real implementation, this would interact with the virtual filesystem
            await ctx.info(f"Virtual mount of {cid} at {path} (mock implementation)")
            return {
                "success": True,
                "cid": cid,
                "path": path,
                "note": "This is a mock implementation"
            }
        except Exception as e:
            await ctx.error(f"Error mounting to VFS: {e}")
            return {"error": str(e)}
    
    @server.tool(name="vfs_status", description="Check status of virtual filesystem")
    async def vfs_status(ctx: Context):
        """Check status of virtual filesystem."""
        await ctx.info("Checking virtual filesystem status")
        
        try:
            # This is just a mock implementation
            return {
                "status": "active",
                "mounts": [
                    {"cid": "QmExample1", "path": "/vfs/example1"},
                    {"cid": "QmExample2", "path": "/vfs/example2"}
                ],
                "note": "This is a mock implementation"
            }
        except Exception as e:
            await ctx.error(f"Error checking VFS status: {e}")
            return {"error": str(e)}
    
    @server.tool(name="vfs_delete", description="Delete a file or directory from the virtual filesystem")
    async def vfs_delete(ctx: Context, path=None):
        """Delete a file or directory from the virtual filesystem."""
        if not path:
            await ctx.error("Path must be provided")
            return {"error": "Path must be provided", "success": False}
            
        await ctx.info(f"Deleting {path} from virtual filesystem")
        
        try:
            # This is just a mock implementation that simulates deletion
            # In a real implementation, this would interact with the virtual filesystem
            await ctx.info(f"Virtual delete of {path} (mock implementation)")
            return {
                "success": True,
                "path": path,
                "note": "This is a mock implementation"
            }
        except Exception as e:
            await ctx.error(f"Error deleting from VFS: {e}")
            return {"error": str(e), "success": False}
    
    @server.tool(name="vfs_write", description="Write content to a file in the virtual filesystem")
    async def vfs_write(ctx: Context, path=None, content=None, encoding="utf-8"):
        """Write content to a file in the virtual filesystem."""
        if not path or content is None:
            await ctx.error("Path and content must be provided")
            return {"error": "Path and content must be provided", "success": False}
            
        await ctx.info(f"Writing to {path} in virtual filesystem")
        
        try:
            # This is just a mock implementation that simulates writing
            # In a real implementation, this would interact with the virtual filesystem
            await ctx.info(f"Virtual write to {path} (mock implementation)")
            
            # If encoding is base64, we would decode it here
            if encoding == "base64":
                await ctx.info("Decoding base64 content")
                # In a real implementation: content = base64.b64decode(content).decode('utf-8')
            
            return {
                "success": True,
                "path": path,
                "size": len(content),
                "note": "This is a mock implementation"
            }
        except Exception as e:
            await ctx.error(f"Error writing to VFS: {e}")
            return {"error": str(e), "success": False}
    
    @server.tool(name="vfs_read", description="Read content from a file in the virtual filesystem")
    async def vfs_read(ctx: Context, path=None, encoding="utf-8"):
        """Read content from a file in the virtual filesystem."""
        if not path:
            await ctx.error("Path must be provided")
            return {"error": "Path must be provided", "success": False}
            
        await ctx.info(f"Reading from {path} in virtual filesystem")
        
        try:
            # This is just a mock implementation that simulates reading
            # In a real implementation, this would interact with the virtual filesystem
            await ctx.info(f"Virtual read from {path} (mock implementation)")
            
            # Mock content - in a real implementation we would read from the actual file
            content = f"Mock content for {path} generated at {datetime.now().isoformat()}"
            
            # If encoding is base64, we would encode it here
            if encoding == "base64":
                await ctx.info("Encoding content as base64")
                import base64
                # In a real implementation: content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            
            return {
                "success": True,
                "path": path,
                "content": content,
                "encoding": encoding,
                "size": len(content),
                "note": "This is a mock implementation"
            }
        except Exception as e:
            await ctx.error(f"Error reading from VFS: {e}")
            return {"error": str(e), "success": False}
    
    # Try to import actual tools but don't fail if there's an error
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import unified_ipfs_tools
        unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info("Successfully registered real IPFS tools")
    except Exception as e:
        logger.warning(f"Failed to import or register real IPFS tools: {e}. Using mock implementations.")
        logger.debug(f"IPFS tools import traceback: {traceback.format_exc()}")
        
        # Already registered mock tools above
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
    global server, server_start_time, PORT
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Minimal MCP Server")
    parser.add_argument("--port", type=int, default=PORT, help="Port to run the server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    # Update PORT with command line argument if provided
    PORT = args.port
    
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
