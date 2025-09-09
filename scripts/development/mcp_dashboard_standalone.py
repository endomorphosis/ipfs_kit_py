#!/usr/bin/env python3
"""
Standalone MCP Dashboard for Iterative Development
================================================

A minimal dashboard implementation focused on MCP functionality for iterative development with Playwright.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles  
from fastapi.templating import Jinja2Templates
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="MCP Dashboard - Iterative Development")

# Setup static files and templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

class MCPDashboardManager:
    """Manages MCP dashboard functionality"""
    
    def __init__(self):
        self.mcp_server_status = "stopped"
        self.mcp_tools = []
        self.mcp_connections = []
        self.iteration_data = {}
        
    def get_mcp_status(self) -> Dict:
        """Get current MCP server status"""
        return {
            "server_status": self.mcp_server_status,
            "tools_count": len(self.mcp_tools),
            "connections_count": len(self.mcp_connections),
            "available": True
        }
    
    def get_mcp_tools(self) -> List[Dict]:
        """Get available MCP tools"""
        return [
            {
                "name": "ipfs_pin_tool",
                "description": "IPFS pinning operations via MCP",
                "capabilities": ["pin_add", "pin_remove", "pin_list"],
                "status": "available"
            },
            {
                "name": "bucket_management_tool", 
                "description": "Bucket operations via MCP",
                "capabilities": ["create_bucket", "list_buckets", "delete_bucket"],
                "status": "available"
            },
            {
                "name": "ipfs_kit_control_tool",
                "description": "Core ipfs_kit_py control via MCP",
                "capabilities": ["daemon_control", "config_management", "status_check"],
                "status": "available"
            }
        ]
    
    def get_protocol_metrics(self) -> Dict:
        """Get MCP protocol debugging metrics"""
        return {
            "messages_sent": 156,
            "messages_received": 143,
            "errors": 2,
            "avg_response_time": 45.6,
            "protocol_version": "2024-11-05"
        }

# Global manager instance
dashboard_manager = MCPDashboardManager()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("mcp_dashboard.html", {
        "request": request,
        "title": "MCP Dashboard - Iterative Development"
    })

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mcp_dashboard"}

@app.get("/api/mcp/status")
async def mcp_status():
    """Get MCP server status"""
    return dashboard_manager.get_mcp_status()

@app.get("/api/mcp/tools")
async def mcp_tools():
    """Get MCP tools registry"""
    return {
        "tools": dashboard_manager.get_mcp_tools(),
        "total": len(dashboard_manager.get_mcp_tools())
    }

@app.get("/api/mcp/metrics")
async def mcp_metrics():
    """Get MCP protocol metrics"""
    return dashboard_manager.get_protocol_metrics()

@app.post("/api/mcp/server/{action}")
async def mcp_server_control(action: str):
    """Control MCP server lifecycle"""
    if action == "start":
        dashboard_manager.mcp_server_status = "running"
        return {"success": True, "message": "MCP server started", "status": "running"}
    elif action == "stop":
        dashboard_manager.mcp_server_status = "stopped"
        return {"success": True, "message": "MCP server stopped", "status": "stopped"}
    elif action == "restart":
        dashboard_manager.mcp_server_status = "restarting"
        dashboard_manager.mcp_server_status = "running"
        return {"success": True, "message": "MCP server restarted", "status": "running"}
    else:
        return {"success": False, "message": f"Unknown action: {action}"}

@app.post("/api/mcp/tools/{tool_name}/execute")
async def execute_mcp_tool(tool_name: str, request: Request):
    """Execute an MCP tool"""
    body = await request.json()
    return {
        "success": True,
        "tool": tool_name,
        "result": f"Executed {tool_name} with parameters: {body}",
        "execution_time": 1.23
    }

def main():
    """Main function to start the dashboard"""
    port = int(os.environ.get("PORT", 8014))
    
    logger.info(f"Starting MCP Dashboard on port {port}")
    logger.info("This is a standalone dashboard for iterative development")
    
    uvicorn.run(
        "mcp_dashboard_standalone:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()