#!/usr/bin/env python3
"""
Unified MCP Dashboard - Fixed Version

A comprehensive FastAPI-based dashboard that combines MCP server functionality
with a modern web interface for managing IPFS Kit components.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import fallbacks for dependencies that might not be available
try:
    from .high_level_api import IPFSSimpleAPI
except ImportError:
    class IPFSSimpleAPI:
        def __init__(self, **kwargs): pass

try:
    from .bucket_manager import get_global_bucket_manager
except ImportError:
    def get_global_bucket_manager(**kwargs): return None

class McpRequest(BaseModel):
    """MCP request model."""
    method: str
    params: Optional[Dict[str, Any]] = None

class McpResponse(BaseModel):
    """MCP response model."""
    result: Optional[Any] = None
    error: Optional[str] = None

class UnifiedMCPDashboard:
    """
    Unified MCP Server and Dashboard
    
    Combines Model Context Protocol server functionality with a modern web dashboard
    for comprehensive IPFS Kit management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the unified MCP server and dashboard."""
        self.config = config or {}
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 8004)
        self.debug = self.config.get('debug', False)
        self.data_dir = Path(self.config.get('data_dir', '.'))
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="IPFS Kit Unified MCP Dashboard",
            description="Combined MCP server and management dashboard",
            version="1.0.0"
        )
        
        # Initialize components
        self.ipfs_api = None
        self.bucket_manager = None
        self.start_time = datetime.now()
        
        # Setup the server
        self._setup_middleware()
        self._setup_static_files()
        self._register_mcp_tools()
        self._setup_routes()
        
        # Initialize IPFS connection
        self._init_ipfs()
        
        logging.info(f"Unified MCP Dashboard initialized on {self.host}:{self.port}")

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_static_files(self):
        """Setup static file serving."""
        # Mount static files directory
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logging.info(f"Static files mounted from {static_dir}")
        else:
            logging.warning(f"Static directory not found: {static_dir}")
    

    def _register_mcp_tools(self):
        """Register MCP tools for VS Code integration."""
        self.mcp_tools = {
            "list_files": {
                "name": "list_files",
                "description": "List files in a directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"}
                    },
                    "required": ["path"]
                }
            },
            "read_file": {
                "name": "read_file", 
                "description": "Read contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"}
                    },
                    "required": ["path"]
                }
            },
            "write_file": {
                "name": "write_file",
                "description": "Write content to a file", 
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            }
        }

    def _init_ipfs(self):
        """Initialize IPFS API connection."""
        try:
            self.ipfs_api = IPFSSimpleAPI(role="leecher")
            self.bucket_manager = get_global_bucket_manager()
            logging.info("IPFS API and bucket manager initialized")
        except Exception as e:
            logging.warning(f"Could not initialize IPFS components: {e}")

    def _setup_routes(self):
        """Setup all API routes for both MCP and dashboard."""
        
        # MCP Protocol Routes
        @self.app.post("/mcp/initialize")
        async def mcp_initialize():
            """MCP initialization endpoint."""
            return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}

        @self.app.get("/mcp/tools")
        async def list_mcp_tools():
            """List available MCP tools."""
            return {"tools": list(self.mcp_tools.values())}

        @self.app.post("/mcp/tools/call")
        async def call_mcp_tool(request: McpRequest):
            """Execute MCP tool."""
            tool_name = request.method
            params = request.params or {}
            
            try:
                if tool_name == "list_files":
                    result = await self._list_files(params.get("path", "."))
                elif tool_name == "read_file":
                    result = await self._read_file(params.get("path"))
                elif tool_name == "write_file":
                    result = await self._write_file(params.get("path"), params.get("content"))
                else:
                    raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
                
                return McpResponse(result=result)
            except Exception as e:
                return McpResponse(error=str(e))

        # Dashboard Routes
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard():
            """Serve the main dashboard."""
            return self._get_dashboard_html()

        @self.app.get("/api/system/overview")
        async def get_system_overview():
            """Get system overview data."""
            try:
                # Get basic system information
                services_count = len(await self._get_services_status())
                backends_count = len(await self._get_backends_status()) 
                buckets_count = len(await self._get_buckets())
                pins_count = len(await self._get_all_pins())
                
                uptime_seconds = (datetime.now() - self.start_time).total_seconds()
                uptime_str = f"{int(uptime_seconds // 3600):02d}:{int((uptime_seconds % 3600) // 60):02d}:{int(uptime_seconds % 60):02d}"
                
                return {
                    "services": services_count,
                    "backends": backends_count, 
                    "buckets": buckets_count,
                    "pins": pins_count,
                    "uptime": uptime_str,
                    "status": "running",
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logging.error(f"Error getting system overview: {e}")
                return {
                    "services": 0,
                    "backends": 0,
                    "buckets": 0, 
                    "pins": 0,
                    "uptime": "00:00:00",
                    "status": "error",
                    "error": str(e)
                }

        @self.app.get("/api/services")
        async def get_services():
            """Get services status."""
            return await self._get_services_status()

        @self.app.get("/api/backends")
        async def get_backends():
            """Get storage backends status."""
            return await self._get_backends_status()

        @self.app.get("/api/buckets")
        async def get_buckets():
            """Get buckets list."""
            return await self._get_buckets()

        @self.app.get("/api/pins")
        async def get_pins():
            """Get pins list."""
            pins_list = await self._get_all_pins()
            
            # Return in the structure expected by the frontend JavaScript
            return {
                "total": len(pins_list),
                "active": len([p for p in pins_list if p.get("status") == "pinned"]),
                "pending": len([p for p in pins_list if p.get("status") == "pending"]),
                "total_size": "N/A",  # TODO: Calculate actual total size
                "pins": pins_list
            }

        @self.app.get("/api/config")
        async def get_config():
            """Get configuration."""
            return {
                "content": json.dumps(self.config, indent=2),
                "editable": True
            }

        @self.app.get("/api/metrics")
        async def get_metrics():
            """Get system metrics."""
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "network_io": {"in": 0, "out": 0},
                "timestamp": datetime.now().isoformat()
            }

    # MCP Tool Implementations
    async def _list_files(self, path: str) -> List[str]:
        """List files in directory."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"Path {path} does not exist")
            
            if path_obj.is_file():
                return [str(path_obj)]
            
            files = []
            for item in path_obj.iterdir():
                files.append(str(item))
            
            return files
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _read_file(self, path: str) -> str:
        """Read file content."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                raise FileNotFoundError(f"File {path} does not exist")
            
            return path_obj.read_text(encoding='utf-8')
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def _write_file(self, path: str, content: str) -> str:
        """Write file content."""
        try:
            path_obj = Path(path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding='utf-8')
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Dashboard Data Methods
    async def _get_services_status(self) -> List[Dict[str, Any]]:
        """Get status of all services."""
        services = []
        
        # Add IPFS service status
        ipfs_status = "running" if self.ipfs_api else "stopped"
        services.append({
            "name": "IPFS Node",
            "type": "ipfs",
            "status": ipfs_status,
            "description": "IPFS node connection"
        })
        
        # Add MCP server status
        services.append({
            "name": "MCP Server", 
            "type": "mcp",
            "status": "running",
            "description": "Model Context Protocol server"
        })
        
        # Add dashboard status
        services.append({
            "name": "Web Dashboard",
            "type": "web",
            "status": "running", 
            "description": "Web-based management interface"
        })
        
        return services

    async def _get_backends_status(self) -> List[Dict[str, Any]]:
        """Get status of storage backends."""
        backends = []
        
        # Add default IPFS backend
        backends.append({
            "name": "IPFS Local",
            "type": "ipfs", 
            "status": "running" if self.ipfs_api else "stopped",
            "url": "http://127.0.0.1:5001",
            "description": "Local IPFS node"
        })
        
        # Add other backend types as available
        backends.append({
            "name": "File System",
            "type": "filesystem",
            "status": "available",
            "description": "Local file system storage"
        })
        
        return backends

    async def _get_buckets(self) -> List[Dict[str, Any]]:
        """Get list of buckets."""
        buckets = []
        
        if self.bucket_manager:
            try:
                # Get buckets from bucket manager
                bucket_list = self.bucket_manager.list_buckets()
                for bucket_name in bucket_list:
                    bucket_info = self.bucket_manager.get_bucket_info(bucket_name)
                    buckets.append({
                        "name": bucket_name,
                        "description": bucket_info.get("description", ""),
                        "file_count": bucket_info.get("file_count", 0),
                        "total_size": bucket_info.get("total_size", "0 B"),
                        "created": bucket_info.get("created", ""),
                        "status": "active"
                    })
            except Exception as e:
                logging.error(f"Error getting buckets: {e}")
        
        # Add default bucket if none found
        if not buckets:
            buckets.append({
                "name": "default",
                "description": "Default storage bucket",
                "file_count": 0,
                "total_size": "0 B", 
                "status": "active"
            })
        
        return buckets

    async def _get_all_pins(self) -> List[Dict[str, Any]]:
        """Get list of all pins."""
        pins = []
        
        if self.ipfs_api:
            try:
                # Get pins from IPFS
                pin_response = self.ipfs_api.pin_ls()
                for cid, pin_info in pin_response.items():
                    pins.append({
                        "cid": cid,
                        "name": pin_info.get("name", ""),
                        "type": pin_info.get("type", "recursive"),
                        "status": "pinned",
                        "size": pin_info.get("size", "unknown"),
                        "pinned_at": pin_info.get("pinned_at", "")
                    })
            except Exception as e:
                logging.error(f"Error getting pins: {e}")
        
        # Add sample pin if none found  
        if not pins:
            pins.append({
                "cid": "QmSampleCidForDemonstration",
                "name": "Sample Pin",
                "type": "recursive", 
                "status": "pinned",
                "size": "1.2 MB"
            })
        
        return pins

    async def list_backend_buckets(self, backend_name: str) -> List[str]:
        """List buckets for a specific backend."""
        try:
            if self.bucket_manager:
                return self.bucket_manager.list_buckets(backend=backend_name)
            return []
        except Exception as e:
            logging.error(f"Error listing backend buckets: {e}")
            return []

    def _get_dashboard_html(self):
        """Generate the dashboard HTML with modern aesthetic design."""
        # Use the enhanced template file
        template_path = Path(__file__).parent / 'templates' / 'enhanced_dashboard.html'
        if template_path.exists():
            return template_path.read_text()
        
        # Fallback to basic template if enhanced template not found
        return self._get_basic_dashboard_html()
    
    def _get_basic_dashboard_html(self):
        """Basic fallback dashboard template."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit - MCP Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="min-h-screen flex">
        <div class="flex-1 p-6">
            <h1 class="text-2xl font-bold mb-6">IPFS Kit MCP Dashboard</h1>
            <div class="bg-white rounded-lg shadow p-6">
                <p>Dashboard is loading...</p>
                <p>If this message persists, please check the enhanced template file.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

    def run(self):
        """Run the unified server."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info" if not self.debug else "debug"
        )

def main():
    """Main entry point for the unified MCP dashboard."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    dashboard = UnifiedMCPDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
