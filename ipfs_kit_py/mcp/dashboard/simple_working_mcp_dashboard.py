#!/usr/bin/env python3
"""
Simple Working MCP Dashboard with Bucket VFS Operations
=======================================================

A minimal working MCP server with bucket virtual filesystem operations
that can be used with `ipfs-kit mcp start` command.
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Web framework imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConsolidatedMCPDashboard:
    """Simple working MCP Dashboard with bucket VFS operations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = {}
            
        self.config = config
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 8004)
        self.data_dir = Path(config.get('data_dir', '~/.ipfs_kit')).expanduser()
        self.debug = config.get('debug', False)
        
        # Ensure data directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vfs_root = self.data_dir / "vfs"
        self.vfs_root.mkdir(exist_ok=True)
        
        # Initialize demo buckets if they don't exist
        self._init_demo_buckets()
        
        # Initialize FastAPI app
        self.app = FastAPI(title="Simple MCP Dashboard")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Mount static files from the parent directory
        try:
            static_path = Path(__file__).parent.parent.parent.parent / "static"
            if static_path.exists():
                self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
                logger.info(f"Mounted static files from: {static_path}")
        except Exception as e:
            logger.warning(f"Could not mount static files: {e}")
    
    def _init_demo_buckets(self):
        """Initialize demo buckets and files for testing."""
        buckets = ["archive", "uploads", "documents"]
        
        for bucket_name in buckets:
            bucket_path = self.vfs_root / bucket_name
            bucket_path.mkdir(exist_ok=True)
            
            # Create some demo files
            if bucket_name == "archive":
                (bucket_path / "document1.pdf").write_text("Demo PDF content")
                (bucket_path / "config.json").write_text('{"config": "demo"}')
                images_dir = bucket_path / "images"
                images_dir.mkdir(exist_ok=True)
                (images_dir / "photo1.jpg").write_text("Demo image content")
                
            elif bucket_name == "uploads":
                (bucket_path / "temp_file.txt").write_text("Temporary file content")
                (bucket_path / "upload.log").write_text("Upload log content")
                
            elif bucket_name == "documents":  
                (bucket_path / "readme.md").write_text("# Demo README")
                (bucket_path / "notes.txt").write_text("Demo notes")
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint - serve the dashboard."""
            # Try to serve the bucket dashboard
            dashboard_path = Path(__file__).parent.parent.parent.parent / "static" / "bucket_dashboard.html"
            if dashboard_path.exists():
                return FileResponse(str(dashboard_path))
            else:
                return HTMLResponse("""
                <html>
                    <head><title>Simple MCP Dashboard</title></head>
                    <body>
                        <h1>Simple MCP Dashboard</h1>
                        <p>Server is running on port {}</p>
                        <p>Available MCP tools:</p>
                        <ul>
                            <li><a href="/mcp/tools/list">GET /mcp/tools/list</a> - List available tools</li>
                            <li>POST /mcp/tools/call - Call MCP tools</li>
                        </ul>
                        <p>Dashboard file not found at: {}</p>
                    </body>
                </html>
                """.format(self.port, dashboard_path))
        
        @self.app.get("/mcp/tools/list")
        async def list_tools():
            """List available MCP tools."""
            tools = [
                {
                    "name": "list_buckets",
                    "description": "List all available buckets",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "include_metadata": {
                                "type": "boolean",
                                "description": "Include detailed metadata",
                                "default": True
                            }
                        }
                    }
                },
                {
                    "name": "bucket_list_files", 
                    "description": "List files in a specific bucket with metadata priority",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "bucket": {
                                "type": "string", 
                                "description": "Bucket name",
                                "required": True
                            },
                            "path": {
                                "type": "string",
                                "description": "Path within bucket",
                                "default": "."
                            },
                            "show_metadata": {
                                "type": "boolean",
                                "description": "Show file metadata",
                                "default": True
                            }
                        },
                        "required": ["bucket"]
                    }
                },
                {
                    "name": "health_check",
                    "description": "Check server health",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]
            return {"result": {"tools": tools}}
        
        @self.app.post("/mcp/tools/call")
        async def call_tool(request: Request):
            """Execute MCP tool."""
            try:
                data = await request.json()
                logger.info(f"Received MCP tool call: {data}")
                
                # Handle both direct calls and JSON-RPC format
                if "params" in data:
                    # JSON-RPC format
                    tool_name = data["params"].get("name")
                    arguments = data["params"].get("arguments", {})
                    request_id = data.get("id")
                else:
                    # Direct format
                    tool_name = data.get("name") or data.get("method")
                    arguments = data.get("arguments", {})
                    request_id = data.get("id")
                
                # Route to appropriate handler
                if tool_name == "list_buckets":
                    result = await self._list_buckets(arguments)
                elif tool_name == "bucket_list_files":
                    result = await self._bucket_list_files(arguments)
                elif tool_name == "health_check":
                    result = await self._health_check()
                else:
                    error_msg = f"Unknown tool: {tool_name}"
                    logger.error(error_msg)
                    if request_id:
                        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": error_msg}, "id": request_id}
                    else:
                        raise HTTPException(status_code=404, detail=error_msg)
                
                # Return appropriate format
                if request_id:
                    # JSON-RPC format
                    return {"jsonrpc": "2.0", "result": result, "id": request_id}
                else:
                    # Direct format
                    return result
                    
            except Exception as e:
                logger.error(f"Error handling MCP tool call: {e}")
                error_msg = str(e)
                if "request_id" in locals() and request_id:
                    return {"jsonrpc": "2.0", "error": {"code": -32603, "message": error_msg}, "id": request_id}
                else:
                    return JSONResponse(
                        status_code=500,
                        content={"error": error_msg}
                    )
    
    async def _list_buckets(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all available buckets from VFS."""
        logger.info(f"Listing buckets from VFS: {self.vfs_root}")
        
        buckets = []
        if self.vfs_root.exists():
            for bucket_dir in self.vfs_root.iterdir():
                if bucket_dir.is_dir():
                    # Calculate bucket stats
                    total_size = 0
                    file_count = 0
                    
                    for file_path in bucket_dir.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            file_count += 1
                    
                    bucket_info = {
                        "name": bucket_dir.name,
                        "type": "vfs",
                        "backend": "local_vfs",  
                        "size": total_size,
                        "file_count": file_count,
                        "created": datetime.fromtimestamp(bucket_dir.stat().st_ctime).isoformat(),
                        "last_modified": datetime.fromtimestamp(bucket_dir.stat().st_mtime).isoformat(),
                        "status": "active",
                        "metadata": {
                            "backend": "local_vfs",
                            "status": "active",
                            "permissions": ["read", "write"],
                            "replicas": 1,
                            "path": str(bucket_dir)
                        }
                    }
                    buckets.append(bucket_info)
        
        return {
            "items": buckets,
            "total": len(buckets)
        }
    
    async def _bucket_list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files in a specific bucket."""
        bucket_name = args.get("bucket")
        path = args.get("path", ".")
        show_metadata = args.get("show_metadata", True)
        
        logger.info(f"Listing files in bucket '{bucket_name}', path '{path}'")
        
        if not bucket_name:
            raise ValueError("Bucket name is required")
        
        bucket_path = self.vfs_root / bucket_name
        if not bucket_path.exists():
            return {
                "items": [],
                "bucket": bucket_name,
                "path": path,
                "error": f"Bucket '{bucket_name}' not found"
            }
        
        # Handle path within bucket
        if path and path != ".":
            full_path = bucket_path / path.lstrip('/')
        else:
            full_path = bucket_path
        
        if not full_path.exists():
            return {
                "items": [],
                "bucket": bucket_name, 
                "path": path,
                "total": 0
            }
        
        files = []
        for item in full_path.iterdir():
            stat_info = item.stat()
            file_info = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": stat_info.st_size if item.is_file() else 0,
                "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                "path": str(item.relative_to(bucket_path))
            }
            
            if show_metadata:
                file_info["metadata"] = {
                    "permissions": oct(stat_info.st_mode)[-3:],
                    "owner": stat_info.st_uid,
                    "group": stat_info.st_gid,
                    "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                    "absolute_path": str(item)
                }
            
            files.append(file_info)
        
        # Sort files: directories first, then by name
        files.sort(key=lambda x: (x["type"] != "directory", x["name"]))
        
        return {
            "items": files,
            "bucket": bucket_name,
            "path": path,
            "total": len(files)
        }
    
    async def _health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "vfs_root": str(self.vfs_root),
            "buckets_available": len([d for d in self.vfs_root.iterdir() if d.is_dir()]) if self.vfs_root.exists() else 0,
            "version": "1.0.0"
        }
    
    def run(self):
        """Run the server."""
        logger.info(f"Starting Simple MCP Dashboard on {self.host}:{self.port}")
        logger.info(f"VFS root: {self.vfs_root}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


# For compatibility with CLI
def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple MCP Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind to")
    parser.add_argument("--data-dir", default="~/.ipfs_kit", help="Data directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    config = {
        "host": args.host,
        "port": args.port, 
        "data_dir": args.data_dir,
        "debug": args.debug
    }
    
    dashboard = ConsolidatedMCPDashboard(config)
    dashboard.run()


if __name__ == "__main__":
    main()