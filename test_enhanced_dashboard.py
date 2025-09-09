#!/usr/bin/env python3
"""
Test Enhanced Dashboard - Serving the enhanced_dashboard.html template
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Mock MCP Server for testing
class MockMCPServer:
    def __init__(self):
        self.backends = [
            {
                "name": "local_storage",
                "type": "local_fs",
                "description": "Local filesystem storage",
                "status": "enabled",
                "health": "healthy",
                "last_check": "2025-01-31T21:30:08+00:00",
                "policies": {"cache": "none", "replication": 1, "retention": 30}
            },
            {
                "name": "s3_demo", 
                "type": "s3",
                "description": "Amazon S3 storage",
                "status": "enabled",
                "health": "error",
                "last_check": "2025-01-31T21:30:08+00:00",
                "policies": {"cache": "none", "replication": 1, "retention": 30}
            },
            {
                "name": "ipfs_local",
                "type": "ipfs",
                "description": "Local IPFS node",
                "status": "enabled", 
                "health": "healthy",
                "last_check": "2025-01-31T21:30:08+00:00",
                "policies": {"cache": "none", "replication": 1, "retention": 30}
            }
        ]
    
    async def handle_tool_call(self, tool_name: str, params: dict) -> dict:
        """Handle MCP tool calls"""
        if tool_name == "list_backends":
            return {"result": self.backends}
        elif tool_name == "get_system_status":
            return {"result": {"cpu_percent": 15.2, "memory_percent": 48.5, "disk_percent": 70.1, "status": "running"}}
        elif tool_name == "health_check":
            return {"result": {"status": "healthy", "timestamp": datetime.now().isoformat()}}
        elif tool_name in ["test_backend_config", "test_backend"]:
            backend_name = params.get("name", "unknown")
            if backend_name == "s3_demo":
                return {"result": {"reachable": False, "error": "Missing API credentials"}}
            else:
                return {"result": {"reachable": True, "status": "healthy"}}
        elif tool_name == "apply_backend_policy":
            return {"result": {"success": True, "message": "Policy applied successfully"}}
        elif tool_name == "update_backend_policy":
            return {"result": {"success": True, "message": "Backend configuration saved"}}
        else:
            return {"error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

class TestEnhancedDashboard:
    def __init__(self):
        self.app = FastAPI(title="Test Enhanced Dashboard")
        self.mock_mcp = MockMCPServer()
        self.setup_app()
    
    def setup_app(self):
        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files
        static_dir = Path(__file__).parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        
        # Setup templates
        templates_dir = Path(__file__).parent / "templates"
        if templates_dir.exists():
            templates = Jinja2Templates(directory=str(templates_dir))
        else:
            templates = None
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Serve the enhanced dashboard."""
            if templates:
                return templates.TemplateResponse(
                    "enhanced_dashboard.html", 
                    {"request": request, "title": "Enhanced Dashboard Test"}
                )
            else:
                return HTMLResponse("<h1>Templates not found</h1>")
        
        @self.app.post("/mcp/tools/call")
        async def mcp_tools_call(request: Request):
            """Handle MCP tool calls."""
            try:
                data = await request.json()
                tool_name = data.get("params", {}).get("name")
                arguments = data.get("params", {}).get("arguments", {})
                
                result = await self.mock_mcp.handle_tool_call(tool_name, arguments)
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    **result
                })
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": data.get("id") if 'data' in locals() else None,
                    "error": {"code": -32000, "message": str(e)}
                })
    
    def run(self, host="127.0.0.1", port=8005):
        """Run the test dashboard."""
        print(f"🚀 Starting Enhanced Dashboard Test")
        print(f"📍 URL: http://{host}:{port}")
        print("="*50)
        uvicorn.run(self.app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    dashboard = TestEnhancedDashboard()
    dashboard.run()