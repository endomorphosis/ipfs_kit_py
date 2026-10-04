#!/usr/bin/env python3
"""
Enhanced Final MCP Server with Comprehensive IPFS Kit and VFS Integration

This server provides a comprehensive MCP (Model Context Protocol) implementation that:
1. Exposes all IPFS Kit functionality as MCP tools
2. Fully integrates the virtual filesystem (VFS) 
3. Provides comprehensive health monitoring and diagnostics
4. Includes robust error handling and logging
"""

import os
import sys
import json
import time
import anyio
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enhanced_mcp_server.log')
    ]
)
logger = logging.getLogger("enhanced-mcp-server")

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.background import BackgroundTask
    from pydantic import BaseModel, Field
except ImportError:
    logger.error("Required packages not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "starlette", "pydantic", "httpx"])
    import uvicorn
    from fastapi import FastAPI, Request, Response, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.background import BackgroundTask
    from pydantic import BaseModel, Field

# Try to import IPFS components, with fallbacks if they're not available
try:
    # Try to import the ipfs_kit_py module
    from ipfs_kit_py import ipfs_controller
    from ipfs_kit_py.mcp import server_bridge
    from ipfs_kit_py.mcp.tools_registry import register_all_tools
    from ipfs_kit_py.vfs import vfs_manager
    IPFS_KIT_AVAILABLE = True
    logger.info("Successfully imported ipfs_kit_py modules")
except ImportError:
    logger.warning("ipfs_kit_py modules not available, using mock implementations")
    IPFS_KIT_AVAILABLE = False

# JSON-RPC implementation
try:
    from jsonrpcserver import method, Success, Error, dispatch
    JSON_RPC_SERVER_AVAILABLE = True
except ImportError:
    logger.error("jsonrpcserver not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "jsonrpcserver"])
    from jsonrpcserver import method, Success, Error, dispatch
    JSON_RPC_SERVER_AVAILABLE = True

# Create FastAPI app
app = FastAPI(title="Enhanced MCP Server")

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage for registered tools and resources
registered_tools = {}
registered_resources = {}

# Mock IPFS controller for when ipfs_kit_py is not available
class MockIPFSController:
    """Mock implementation for IPFS controller when the real one is not available"""
    
    def __init__(self):
        self.version = "Mock IPFS Controller v0.1.0"
        logger.info(f"Initialized {self.version}")
    
    async def get_version(self):
        """Get the IPFS version"""
        return {"version": self.version}
    
    async def add_string(self, content, filename=None, pin=True):
        """Simulate adding string content to IPFS"""
        import hashlib
        # Generate a mock CID based on content
        mock_cid = hashlib.sha256(content.encode()).hexdigest()[:46]
        return {"cid": f"Qm{mock_cid}", "filename": filename or "unnamed", "size": len(content)}
    
    async def cat(self, cid):
        """Simulate retrieving content from IPFS"""
        if not cid or not cid.startswith("Qm"):
            return {"error": "Invalid CID format"}
        return {"content": f"Mock content for CID: {cid}", "size": len(f"Mock content for CID: {cid}")}
    
    # MFS operations
    async def files_mkdir(self, path, parents=False):
        """Simulate creating a directory in MFS"""
        return {"success": True, "path": path, "parents": parents}
    
    async def files_write(self, path, content, create=True, truncate=True, offset=0):
        """Simulate writing to a file in MFS"""
        return {"success": True, "path": path, "size": len(content)}
    
    async def files_ls(self, path="/"):
        """Simulate listing a directory in MFS"""
        return {"entries": [{"name": "mock_file.txt", "type": 0, "size": 100}]}
    
    async def files_read(self, path, offset=0, count=-1):
        """Simulate reading a file from MFS"""
        return {"content": f"Mock content from MFS file: {path}", "size": len(f"Mock content from MFS file: {path}")}
    
    async def files_rm(self, path, recursive=False):
        """Simulate removing a file or directory from MFS"""
        return {"success": True, "path": path, "recursive": recursive}

# Mock VFS Manager for when ipfs_kit_py is not available
class MockVFSManager:
    """Mock implementation for VFS Manager when the real one is not available"""
    
    def __init__(self):
        self.version = "Mock VFS Manager v0.1.0"
        self.storage = {}  # Simple in-memory storage
        logger.info(f"Initialized {self.version}")
    
    async def create_dir(self, path):
        """Simulate creating a directory in VFS"""
        self.storage[path] = {"type": "dir", "entries": {}}
        return {"success": True, "path": path}
    
    async def write(self, path, content):
        """Simulate writing to a file in VFS"""
        # Extract directory from path
        dir_path = os.path.dirname(path)
        if dir_path not in self.storage:
            await self.create_dir(dir_path)
        
        self.storage[path] = {"type": "file", "content": content, "size": len(content)}
        return {"success": True, "path": path, "size": len(content)}
    
    async def read(self, path):
        """Simulate reading a file from VFS"""
        if path not in self.storage:
            return {"error": f"File not found: {path}"}
        if self.storage[path]["type"] != "file":
            return {"error": f"Not a file: {path}"}
        
        return {"content": self.storage[path]["content"], "size": self.storage[path]["size"]}
    
    async def list(self, path):
        """Simulate listing a directory in VFS"""
        if path not in self.storage:
            return {"error": f"Directory not found: {path}"}
        if self.storage[path]["type"] != "dir":
            return {"error": f"Not a directory: {path}"}
        
        return {"entries": list(self.storage[path]["entries"].keys())}
    
    async def delete(self, path):
        """Simulate deleting a file or directory from VFS"""
        if path not in self.storage:
            return {"error": f"Path not found: {path}"}
        
        del self.storage[path]
        return {"success": True, "path": path}
    
    # Integration with IPFS
    async def import_ipfs(self, cid, destination):
        """Simulate importing content from IPFS to VFS"""
        content = f"Imported IPFS content from CID: {cid}"
        await self.write(destination, content)
        return {"success": True, "cid": cid, "destination": destination, "size": len(content)}
    
    async def export_to_ipfs(self, path):
        """Simulate exporting content from VFS to IPFS"""
        if path not in self.storage:
            return {"error": f"Path not found: {path}"}
        if self.storage[path]["type"] != "file":
            return {"error": f"Not a file: {path}"}
        
        import hashlib
        content = self.storage[path]["content"]
        mock_cid = hashlib.sha256(content.encode()).hexdigest()[:46]
        return {"success": True, "path": path, "cid": f"Qm{mock_cid}", "size": len(content)}

# Initialize controller based on availability
if IPFS_KIT_AVAILABLE:
    try:
        ipfs_ctrl = ipfs_controller.IPFSController()
        logger.info("Initialized real IPFSController")
        
        # Try to initialize VFS Manager
        try:
            vfs_mgr = vfs_manager.VFSManager()
            logger.info("Initialized real VFSManager")
        except Exception as e:
            logger.error(f"Failed to initialize VFSManager: {str(e)}")
            logger.info("Falling back to mock VFS implementation")
            vfs_mgr = MockVFSManager()
    except Exception as e:
        logger.error(f"Failed to initialize IPFSController: {str(e)}")
        logger.info("Falling back to mock implementations")
        ipfs_ctrl = MockIPFSController()
        vfs_mgr = MockVFSManager()
else:
    logger.info("Using mock implementations for IPFS and VFS")
    ipfs_ctrl = MockIPFSController()
    vfs_mgr = MockVFSManager()

# ------ Tool Registration Functions ------

def register_tool(name, description, function, params_schema=None):
    """Register a tool with the MCP server"""
    registered_tools[name] = {
        "name": name,
        "description": description,
        "function": function,
        "params_schema": params_schema or {}
    }
    logger.info(f"Registered tool: {name}")
    return True

def register_resource(uri, description, content_type, getter):
    """Register a resource with the MCP server"""
    registered_resources[uri] = {
        "uri": uri,
        "description": description,
        "content_type": content_type,
        "getter": getter
    }
    logger.info(f"Registered resource: {uri}")
    return True

# ------ Register IPFS Tools ------

# Basic IPFS operations
register_tool(
    "ipfs_version", 
    "Get the IPFS version",
    ipfs_ctrl.get_version,
    {}
)

register_tool(
    "ipfs_add", 
    "Add content to IPFS",
    ipfs_ctrl.add_string,
    {
        "content": {"type": "string", "description": "Content to add to IPFS"},
        "filename": {"type": "string", "description": "Optional filename", "optional": True},
        "pin": {"type": "boolean", "description": "Whether to pin the content", "optional": True}
    }
)

register_tool(
    "ipfs_cat", 
    "Retrieve content from IPFS by CID",
    ipfs_ctrl.cat,
    {
        "cid": {"type": "string", "description": "CID of the content to retrieve"}
    }
)

# MFS operations
register_tool(
    "ipfs_files_mkdir", 
    "Create a directory in MFS",
    ipfs_ctrl.files_mkdir,
    {
        "path": {"type": "string", "description": "Path of the directory to create"},
        "parents": {"type": "boolean", "description": "Create parent directories if they don't exist", "optional": True}
    }
)

register_tool(
    "ipfs_files_write", 
    "Write content to a file in MFS",
    ipfs_ctrl.files_write,
    {
        "path": {"type": "string", "description": "Path of the file to write to"},
        "content": {"type": "string", "description": "Content to write to the file"},
        "create": {"type": "boolean", "description": "Create the file if it doesn't exist", "optional": True},
        "truncate": {"type": "boolean", "description": "Truncate the file if it exists", "optional": True}
    }
)

register_tool(
    "ipfs_files_ls", 
    "List a directory in MFS",
    ipfs_ctrl.files_ls,
    {
        "path": {"type": "string", "description": "Path of the directory to list", "optional": True}
    }
)

register_tool(
    "ipfs_files_read", 
    "Read a file from MFS",
    ipfs_ctrl.files_read,
    {
        "path": {"type": "string", "description": "Path of the file to read"}
    }
)

register_tool(
    "ipfs_files_rm", 
    "Remove a file or directory from MFS",
    ipfs_ctrl.files_rm,
    {
        "path": {"type": "string", "description": "Path of the file or directory to remove"},
        "recursive": {"type": "boolean", "description": "Recursively remove directories", "optional": True}
    }
)

# ------ Register VFS Tools ------

register_tool(
    "vfs_create_dir", 
    "Create a directory in the virtual filesystem",
    vfs_mgr.create_dir,
    {
        "path": {"type": "string", "description": "Path of the directory to create"}
    }
)

register_tool(
    "vfs_write", 
    "Write content to a file in the virtual filesystem",
    vfs_mgr.write,
    {
        "path": {"type": "string", "description": "Path of the file to write to"},
        "content": {"type": "string", "description": "Content to write to the file"}
    }
)

register_tool(
    "vfs_read", 
    "Read a file from the virtual filesystem",
    vfs_mgr.read,
    {
        "path": {"type": "string", "description": "Path of the file to read"}
    }
)

register_tool(
    "vfs_list", 
    "List a directory in the virtual filesystem",
    vfs_mgr.list,
    {
        "path": {"type": "string", "description": "Path of the directory to list"}
    }
)

register_tool(
    "vfs_delete", 
    "Delete a file or directory from the virtual filesystem",
    vfs_mgr.delete,
    {
        "path": {"type": "string", "description": "Path of the file or directory to delete"}
    }
)

# ------ Register Integration Tools ------

register_tool(
    "vfs_import_ipfs", 
    "Import content from IPFS to the virtual filesystem",
    vfs_mgr.import_ipfs,
    {
        "cid": {"type": "string", "description": "CID of the content to import"},
        "destination": {"type": "string", "description": "Destination path in the virtual filesystem"}
    }
)

register_tool(
    "vfs_export_to_ipfs", 
    "Export content from the virtual filesystem to IPFS",
    vfs_mgr.export_to_ipfs,
    {
        "path": {"type": "string", "description": "Path of the file to export to IPFS"}
    }
)

# ------ Define API Routes ------

@app.get("/")
async def root():
    """Root endpoint that returns basic server information"""
    return {
        "server": "Enhanced MCP Server",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "initialize": "/initialize",
        "jsonrpc": "/jsonrpc"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    ipfs_status = "available" if IPFS_KIT_AVAILABLE else "mock"
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": "ok",
            "ipfs": ipfs_status,
            "jsonrpc": "ok" if JSON_RPC_SERVER_AVAILABLE else "error",
            "tools_count": len(registered_tools),
            "resources_count": len(registered_resources)
        }
    }

@app.post("/initialize")
async def initialize():
    """Initialize endpoint that returns available tools and resources"""
    return {
        "capabilities": {
            "tools": list(registered_tools.keys()),
            "resources": list(registered_resources.keys())
        },
        "server_info": {
            "name": "Enhanced MCP Server",
            "version": "1.0.0",
            "ipfs_available": IPFS_KIT_AVAILABLE,
            "vfs_available": True  # We always have at least the mock VFS
        }
    }

class JSONRPCRequest(BaseModel):
    """Model for JSON-RPC requests"""
    jsonrpc: str = Field("2.0", description="JSON-RPC version")
    method: str = Field(..., description="Method name")
    params: Dict[str, Any] = Field({}, description="Method parameters")
    id: Union[str, int] = Field(..., description="Request ID")

@app.post("/jsonrpc")
async def jsonrpc_endpoint(request: JSONRPCRequest):
    """JSON-RPC endpoint for executing tools"""
    try:
        if request.method == "ping":
            return {"jsonrpc": "2.0", "result": "pong", "id": request.id}
        
        # Handle MCP/execute method
        if request.method == "mcp/execute":
            if "name" not in request.params:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: missing 'name'"}, "id": request.id}
            
            tool_name = request.params["name"]
            if tool_name not in registered_tools:
                return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}, "id": request.id}
            
            tool = registered_tools[tool_name]
            tool_params = request.params.get("params", {})
            
            # Execute the tool function
            try:
                result = await tool["function"](**tool_params)
                if isinstance(result, dict) and "error" in result:
                    return {
                        "jsonrpc": "2.0", 
                        "error": {"code": -32603, "message": result["error"]}, 
                        "id": request.id
                    }
                return {"jsonrpc": "2.0", "result": {"success": True, **result}, "id": request.id}
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {str(e)}")
                return {
                    "jsonrpc": "2.0", 
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}, 
                    "id": request.id
                }
        
        # Handle MCP/getResource method
        if request.method == "mcp/getResource":
            if "uri" not in request.params:
                return {"jsonrpc": "2.0", "error": {"code": -32602, "message": "Invalid params: missing 'uri'"}, "id": request.id}
            
            uri = request.params["uri"]
            if uri not in registered_resources:
                return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Resource not found: {uri}"}, "id": request.id}
            
            resource = registered_resources[uri]
            
            # Get the resource
            try:
                content = await resource["getter"]()
                return {
                    "jsonrpc": "2.0", 
                    "result": {
                        "content": content,
                        "content_type": resource["content_type"]
                    }, 
                    "id": request.id
                }
            except Exception as e:
                logger.error(f"Error getting resource {uri}: {str(e)}")
                return {
                    "jsonrpc": "2.0", 
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}, 
                    "id": request.id
                }
        
        # Unknown method
        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {request.method}"}, "id": request.id}
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {str(e)}")
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {str(e)}"}, "id": request.id}

# ------ Alternative API Routes for Compatibility ------

@app.get("/api/v0/health")
async def health_v0():
    """Health check endpoint (compatibility version)"""
    return await health()

@app.post("/api/v0/initialize")
async def initialize_v0():
    """Initialize endpoint (compatibility version)"""
    return await initialize()

@app.post("/api/v0/jsonrpc")
async def jsonrpc_v0(request: JSONRPCRequest):
    """JSON-RPC endpoint (compatibility version)"""
    return await jsonrpc_endpoint(request)

# ------ Main Function ------

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to listen on")
    parser.add_argument("--port", type=int, default=9996, help="Port to listen on")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-level", type=str, default="info", choices=["debug", "info", "warning", "error"], help="Log level")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    # Configure logging based on arguments
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.log_level == "debug":
        logger.setLevel(logging.DEBUG)
    elif args.log_level == "info":
        logger.setLevel(logging.INFO)
    elif args.log_level == "warning":
        logger.setLevel(logging.WARNING)
    elif args.log_level == "error":
        logger.setLevel(logging.ERROR)
    
    logger.info(f"Starting Enhanced MCP Server on {args.host}:{args.port}")
    logger.info(f"Registered {len(registered_tools)} tools and {len(registered_resources)} resources")
    
    if IPFS_KIT_AVAILABLE:
        logger.info("Using real IPFS implementation")
    else:
        logger.info("Using mock IPFS implementation")
    
    # Run the server
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
