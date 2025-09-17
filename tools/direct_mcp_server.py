
#!/usr/bin/env python3
"""
Direct MCP Server with Bucket Management Tools
==============================================

A minimal MCP server implementation that provides the bucket management tools
needed by the dashboard JavaScript SDK.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
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

class DirectMCPServer:
    """Direct MCP Server with essential bucket management tools."""
    
    def __init__(self, host="127.0.0.1", port=8004):
        self.host = host
        self.port = port
        self.app = FastAPI(title="Direct MCP Server")
        self.start_time = datetime.now()
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mock bucket data for testing
        self.buckets = [
            {
                "name": "archive",
                "type": "standard",
                "size": 1024 * 1024 * 100,  # 100MB
                "file_count": 42,
                "created": "2024-01-15T10:30:00Z",
                "last_modified": "2024-01-20T14:45:00Z"
            },
            {
                "name": "uploads",
                "type": "standard", 
                "size": 1024 * 1024 * 50,   # 50MB
                "file_count": 23,
                "created": "2024-01-10T09:15:00Z",
                "last_modified": "2024-01-22T11:20:00Z"
            }
        ]
        
        # Mock files data for buckets
        self.bucket_files = {
            "archive": [
                {
                    "name": "document1.pdf",
                    "size": 1024 * 1024 * 2,  # 2MB
                    "type": "file",
                    "modified": "2024-01-20T14:45:00Z",
                    "cid": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"
                },
                {
                    "name": "images/",
                    "size": 0,
                    "type": "directory",
                    "modified": "2024-01-18T10:30:00Z",
                    "cid": None
                },
                {
                    "name": "config.json",
                    "size": 1024,  # 1KB
                    "type": "file", 
                    "modified": "2024-01-19T16:20:00Z",
                    "cid": "QmV7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPZ"
                }
            ],
            "uploads": [
                {
                    "name": "temp_file.txt",
                    "size": 1024 * 5,  # 5KB
                    "type": "file",
                    "modified": "2024-01-22T11:20:00Z",
                    "cid": "QmZ8Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPA"
                }
            ]
        }
        
        self._setup_routes()
        
        # Mount static files
        static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
        if os.path.exists(static_path):
            self.app.mount("/static", StaticFiles(directory=static_path), name="static")
            logger.info(f"Mounted static files from: {static_path}")
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        @self.app.get("/")
        async def root():
            """Root endpoint."""
            return HTMLResponse("""
            <html>
                <head><title>Direct MCP Server</title></head>
                <body>
                    <h1>Direct MCP Server</h1>
                    <p>Server is running on port {}</p>
                    <p>Available endpoints:</p>
                    <ul>
                        <li><a href="/mcp/tools/list">GET /mcp/tools/list</a> - List available tools</li>
                        <li>POST /mcp/tools/call - Call MCP tools</li>
                    </ul>
                </body>
            </html>
            """.format(self.port))
        
        @self.app.get("/dashboard")
        async def dashboard():
            """Dashboard endpoint."""
            dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "bucket_dashboard.html")
            if os.path.exists(dashboard_path):
                return FileResponse(dashboard_path)
            else:
                return HTMLResponse("""
                <html>
                    <head><title>MCP Dashboard</title></head>
                    <body>
                        <h1>MCP Dashboard</h1>
                        <p>Dashboard not found. Expected location: {}</p>
                        <p><a href="/mcp/tools/list">View available tools</a></p>
                    </body>
                </html>
                """.format(dashboard_path))
        
        @self.app.get("/mcp/tools/list")
        async def list_tools():
            """List available MCP tools."""
            tools = [
                {
                    "name": "list_buckets",
                    "description": "List all available buckets",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "include_metadata": {
                                "type": "boolean",
                                "description": "Include detailed metadata",
                                "default": True
                            },
                            "metadata_first": {
                                "type": "boolean", 
                                "description": "Return metadata first",
                                "default": True
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Pagination offset",
                                "default": 0
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Pagination limit", 
                                "default": 20
                            }
                        }
                    }
                },
                {
                    "name": "list_bucket_files",
                    "description": "List files in a specific bucket",
                    "schema": {
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
                                "default": ""
                            },
                            "metadata_first": {
                                "type": "boolean",
                                "description": "Return metadata first",
                                "default": True
                            }
                        },
                        "required": ["bucket"]
                    }
                },
                {
                    "name": "health_check",
                    "description": "Check server health",
                    "schema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]
            return {"tools": tools}
        
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
                elif tool_name == "list_bucket_files":
                    result = await self._list_bucket_files(arguments)
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
        """List all available buckets."""
        logger.info(f"Listing buckets with args: {args}")
        
        include_metadata = args.get("include_metadata", True)
        offset = args.get("offset", 0)
        limit = args.get("limit", 20)
        
        # Apply pagination
        paginated_buckets = self.buckets[offset:offset + limit]
        
        # Add metadata if requested
        if include_metadata:
            result_buckets = []
            for bucket in paginated_buckets:
                bucket_with_meta = bucket.copy()
                bucket_with_meta["metadata"] = {
                    "backend": "mock",
                    "status": "active",
                    "permissions": ["read", "write"],
                    "replicas": 1
                }
                result_buckets.append(bucket_with_meta)
        else:
            result_buckets = paginated_buckets
        
        return {
            "items": result_buckets,
            "total": len(self.buckets),
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < len(self.buckets)
        }
    
    async def _list_bucket_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files in a specific bucket."""
        bucket_name = args.get("bucket")
        path = args.get("path", "")
        
        logger.info(f"Listing files in bucket '{bucket_name}', path '{path}'")
        
        if not bucket_name:
            raise ValueError("Bucket name is required")
        
        if bucket_name not in self.bucket_files:
            return {
                "items": [],
                "bucket": bucket_name,
                "path": path,
                "error": f"Bucket '{bucket_name}' not found"
            }
        
        # Get files for the bucket
        files = self.bucket_files[bucket_name]
        
        # Filter by path if specified
        if path:
            # Simple path filtering - in a real implementation this would be more sophisticated
            filtered_files = [f for f in files if f["name"].startswith(path)]
        else:
            filtered_files = files
        
        return {
            "items": filtered_files,
            "bucket": bucket_name,
            "path": path,
            "total": len(filtered_files)
        }
    
    async def _health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int((datetime.now() - self.start_time).total_seconds()),
            "version": "1.0.0"
        }
    
    def run(self):
        """Run the server."""
        logger.info(f"Starting Direct MCP Server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Direct MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind to")
    
    args = parser.parse_args()
    
    server = DirectMCPServer(host=args.host, port=args.port)
    server.run()


if __name__ == "__main__":
    main()