#!/usr/bin/env python3
"""
Unified MCP Server with Full Observability and Dashboard Integration
===================================================================

This server combines:
1. Enhanced MCP Server with daemon management capabilities
2. Full dashboard integration with real-time monitoring
3. Complete observability into program state and backend status
4. WebSocket and HTTP endpoints for comprehensive access
5. Real-time health monitoring and alerting

Features:
- MCP JSON-RPC protocol via HTTP and WebSocket
- Real-time dashboard with comprehensive backend monitoring
- IPFS Kit integration with automatic daemon management
- VFS operations and analytics
- Performance metrics and system health monitoring
- Error tracking and diagnostic capabilities
- Background services for continuous monitoring
"""

import sys
import json
import asyncio
import logging
import traceback
import os
import time
import subprocess
import tempfile
import platform
import argparse
import signal
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure comprehensive logging
log_dir = Path("/tmp/ipfs_kit_logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'unified_mcp_server.log', mode='a')
    ]
)
logger = logging.getLogger("unified-observability-mcp")

# Add project root to Python path
current_dir = Path(__file__).parent
project_root = current_dir
sys.path.insert(0, str(project_root))

# Component availability tracking
COMPONENTS = {
    "mcp_core": False,
    "dashboard": False,
    "web_framework": False,
    "ipfs_kit": False,
    "backend_monitor": False,
    "vfs_system": False
}

# Import MCP and dashboard components with error tracking
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
    COMPONENTS["mcp_core"] = True
    logger.info("✓ MCP core components imported")
except ImportError as e:
    logger.warning(f"⚠️  MCP core import failed: {e} - using simplified MCP handling")
    # Create simplified classes for compatibility
    class Tool:
        def __init__(self, name, description, inputSchema):
            self.name = name
            self.description = description
            self.inputSchema = inputSchema
        def dict(self):
            return {"name": self.name, "description": self.description, "inputSchema": self.inputSchema}
    
    class TextContent:
        def __init__(self, type, text):
            self.type = type
            self.text = text
        def dict(self):
            return {"type": self.type, "text": self.text}
    
    class Server:
        def __init__(self, name):
            self.name = name
            self._tools = []
        def list_tools(self):
            def decorator(func):
                return func
            return decorator
        def call_tool(self):
            def decorator(func):
                return func
            return decorator
    
    COMPONENTS["mcp_core"] = True  # Use simplified implementation

try:
    from dashboard.config import DashboardConfig
    from dashboard.web_dashboard import WebDashboard
    from dashboard.data_collector import DataCollector
    from dashboard.metrics_aggregator import MetricsAggregator
    from dashboard.comprehensive_backend_monitor import get_comprehensive_backend_status, get_backend_recommendations
    COMPONENTS["dashboard"] = True
    COMPONENTS["backend_monitor"] = True
    logger.info("✓ Dashboard components imported")
except ImportError as e:
    logger.error(f"❌ Dashboard import failed: {e}")

try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
    from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    COMPONENTS["web_framework"] = True
    logger.info("✓ Web framework imported")
except ImportError as e:
    logger.error(f"❌ Web framework import failed: {e}")

try:
    from ipfs_kit_py import IPFSKit
    COMPONENTS["ipfs_kit"] = True
    logger.info("✓ IPFS Kit imported")
except ImportError as e:
    logger.error(f"❌ IPFS Kit import failed: {e}")


class UnifiedObservabilityMCPServer:
    """
    Unified MCP server with full observability and dashboard integration.
    
    This server provides:
    - Complete MCP protocol support (HTTP + WebSocket)
    - Real-time dashboard with backend monitoring
    - IPFS Kit integration with daemon management
    - Full program state observability
    - Performance monitoring and alerting
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Server state for full observability
        self.server_state = {
            "initialization_time": datetime.now().isoformat(),
            "components": COMPONENTS.copy(),
            "connections": {
                "websocket_active": set(),
                "http_sessions": 0,
                "mcp_clients": 0
            },
            "metrics": {
                "requests_total": 0,
                "requests_success": 0,
                "requests_error": 0,
                "mcp_tools_calls": 0,
                "dashboard_views": 0,
                "last_request_time": None,
                "average_response_time": 0.0,
                "backend_checks": 0,
                "alerts_generated": 0
            },
            "errors": [],
            "alerts": [],
            "performance": {
                "memory_usage_mb": 0,
                "cpu_usage_percent": 0,
                "uptime_seconds": 0
            },
            "ipfs_integration": {
                "daemon_status": "unknown",
                "last_check": None,
                "operations_count": 0,
                "errors_count": 0
            }
        }
        
        # Initialize components
        self.app = None
        self.mcp_server = None
        self.ipfs_kit = None
        self.dashboard_config = None
        self.dashboard = None
        self.data_collector = None
        self.metrics_aggregator = None
        
        # Background tasks
        self.background_tasks = []
        self.monitoring_active = False
        
        logger.info(f"🚀 Initializing Unified Observability MCP Server on {host}:{port}")
        
        self._initialize_components()
        self._setup_web_server()
        self._setup_mcp_server()
        
    def _initialize_components(self):
        """Initialize all server components with comprehensive error handling."""
        
        # Initialize IPFS Kit integration
        if COMPONENTS["ipfs_kit"]:
            try:
                self.ipfs_kit = IPFSKit()
                self.server_state["ipfs_integration"]["daemon_status"] = "initialized"
                logger.info("✓ IPFS Kit initialized")
            except Exception as e:
                logger.error(f"❌ IPFS Kit initialization failed: {e}")
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "ipfs_kit",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
        
        # Initialize dashboard components
        if COMPONENTS["dashboard"]:
            try:
                self.dashboard_config = DashboardConfig()
                self.data_collector = DataCollector(self.dashboard_config)
                self.metrics_aggregator = MetricsAggregator(self.dashboard_config, self.data_collector)
                logger.info("✓ Dashboard components initialized")
            except Exception as e:
                logger.error(f"❌ Dashboard initialization failed: {e}")
                # Continue without dashboard components
                self.dashboard_config = None
                self.data_collector = None
                self.metrics_aggregator = None
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "dashboard",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
    
    def _setup_web_server(self):
        """Setup FastAPI web server with comprehensive endpoints."""
        
        if not COMPONENTS["web_framework"]:
            logger.warning("Web framework not available - HTTP/WebSocket endpoints disabled")
            return
        
        self.app = FastAPI(
            title="Unified IPFS Kit MCP Server with Full Observability",
            description="Complete MCP server with dashboard integration and comprehensive monitoring",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Request tracking middleware
        @self.app.middleware("http")
        async def track_requests(request: Request, call_next):
            start_time = time.time()
            self.server_state["connections"]["http_sessions"] += 1
            
            try:
                response = await call_next(request)
                self.server_state["metrics"]["requests_success"] += 1
                return response
            except Exception as e:
                self.server_state["metrics"]["requests_error"] += 1
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "web_server",
                    "error": str(e),
                    "path": str(request.url)
                })
                raise
            finally:
                duration = time.time() - start_time
                self.server_state["metrics"]["requests_total"] += 1
                self.server_state["metrics"]["last_request_time"] = datetime.now().isoformat()
                
                # Update average response time
                current_avg = self.server_state["metrics"]["average_response_time"]
                total_requests = self.server_state["metrics"]["requests_total"]
                self.server_state["metrics"]["average_response_time"] = (
                    (current_avg * (total_requests - 1) + duration) / total_requests
                )
        
        self._setup_routes()
        logger.info("✓ Web server configured")
    
    def _setup_routes(self):
        """Setup all web server routes."""
        
        # Root endpoint - comprehensive server status
        @self.app.get("/")
        async def root():
            return HTMLResponse(self._get_comprehensive_dashboard_html())
        
        # MCP JSON-RPC endpoint
        @self.app.post("/mcp")
        async def mcp_endpoint(request: Request):
            try:
                data = await request.json()
                response = await self._handle_mcp_request(data)
                self.server_state["metrics"]["mcp_tools_calls"] += 1
                return JSONResponse(response)
            except Exception as e:
                logger.error(f"MCP request failed: {e}")
                return JSONResponse({"error": str(e)}, status_code=500)
        
        # MCP WebSocket endpoint
        @self.app.websocket("/mcp/ws")
        async def mcp_websocket(websocket: WebSocket):
            await websocket.accept()
            self.server_state["connections"]["websocket_active"].add(websocket)
            self.server_state["connections"]["mcp_clients"] += 1
            
            try:
                while True:
                    data = await websocket.receive_json()
                    response = await self._handle_mcp_request(data)
                    await websocket.send_json(response)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.server_state["connections"]["websocket_active"].discard(websocket)
                self.server_state["connections"]["mcp_clients"] = max(0, 
                    self.server_state["connections"]["mcp_clients"] - 1)
        
        # Dashboard endpoints
        @self.app.get("/dashboard")
        async def dashboard():
            self.server_state["metrics"]["dashboard_views"] += 1
            return HTMLResponse(self._get_comprehensive_dashboard_html())
        
        @self.app.get("/dashboard/api/status")
        async def dashboard_status():
            return JSONResponse(await self._get_comprehensive_status())
        
        @self.app.get("/dashboard/api/backends")
        async def backend_status():
            if COMPONENTS["backend_monitor"]:
                try:
                    status = get_comprehensive_backend_status()
                    recommendations = get_backend_recommendations(status)
                    return JSONResponse({
                        "success": True,
                        "status": status,
                        "recommendations": recommendations
                    })
                except Exception as e:
                    return JSONResponse({"success": False, "error": str(e)})
            else:
                return JSONResponse({"success": False, "error": "Backend monitoring not available"})
        
        # Health and metrics endpoints
        @self.app.get("/health")
        async def health():
            return JSONResponse(await self._get_health_status())
        
        @self.app.get("/metrics")
        async def metrics():
            return PlainTextResponse(self._get_prometheus_metrics())
        
        # Observability endpoints
        @self.app.get("/observability")
        async def observability():
            return JSONResponse(self._get_full_observability_data())
        
        @self.app.get("/debug")
        async def debug():
            return JSONResponse({
                "server_state": self.server_state,
                "components": COMPONENTS,
                "system_info": self._get_system_info()
            })
    
    def _setup_mcp_server(self):
        """Setup MCP server with all tools."""
        
        if not COMPONENTS["mcp_core"]:
            logger.warning("MCP core not available - MCP functionality disabled")
            return
        
        self.mcp_server = Server("unified-ipfs-kit-mcp")
        
        # Register MCP tools
        self._register_mcp_tools()
        logger.info("✓ MCP server configured")
    
    def _register_mcp_tools(self):
        """Register all MCP tools."""
        
        # System health tool
        @self.mcp_server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="system_health",
                    description="Get comprehensive system health status including IPFS daemon status",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                ),
                Tool(
                    name="ipfs_add",
                    description="Add content to IPFS and return the CID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Content to add to IPFS"},
                            "file_path": {"type": "string", "description": "Path to file to add to IPFS"}
                        }
                    }
                ),
                Tool(
                    name="ipfs_cat",
                    description="Retrieve and display content from IPFS",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {"type": "string", "description": "IPFS CID to retrieve content from"}
                        },
                        "required": ["cid"]
                    }
                ),
                Tool(
                    name="ipfs_pin_add",
                    description="Pin content in IPFS to prevent garbage collection",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cid": {"type": "string", "description": "IPFS CID to pin"},
                            "recursive": {"type": "boolean", "description": "Pin recursively", "default": True}
                        },
                        "required": ["cid"]
                    }
                ),
                Tool(
                    name="get_backend_status",
                    description="Get comprehensive backend status and monitoring data",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_observability_data",
                    description="Get full observability data including metrics, errors, and performance",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        @self.mcp_server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name == "system_health":
                    result = await self._get_health_status()
                elif name == "ipfs_add":
                    result = await self._ipfs_add(arguments)
                elif name == "ipfs_cat":
                    result = await self._ipfs_cat(arguments)
                elif name == "ipfs_pin_add":
                    result = await self._ipfs_pin_add(arguments)
                elif name == "get_backend_status":
                    result = await self._get_backend_status()
                elif name == "get_observability_data":
                    result = self._get_full_observability_data()
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
            except Exception as e:
                error_msg = f"Tool {name} failed: {str(e)}"
                logger.error(error_msg)
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "mcp_tool",
                    "tool": name,
                    "error": str(e),
                    "arguments": arguments
                })
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
    
    async def _handle_mcp_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC requests."""
        
        if not self.mcp_server:
            return {"error": "MCP server not available"}
        
        try:
            # This is a simplified MCP request handler
            # In a real implementation, you'd use the MCP library's request handling
            method = data.get("method")
            params = data.get("params", {})
            
            if method == "tools/list":
                tools = await self.mcp_server.list_tools()
                return {
                    "id": data.get("id"),
                    "result": {
                        "tools": [tool.dict() for tool in tools]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self.mcp_server.call_tool(tool_name, arguments)
                return {
                    "id": data.get("id"),
                    "result": {
                        "content": [content.dict() for content in result]
                    }
                }
            else:
                return {
                    "id": data.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
        
        except Exception as e:
            return {
                "id": data.get("id", None),
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }
    
    async def _ipfs_add(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add content to IPFS."""
        
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available", "mock": True}
        
        try:
            content = arguments.get("content")
            file_path = arguments.get("file_path")
            
            if content:
                # Add content directly
                result = await self.ipfs_kit.add_content(content)
            elif file_path:
                # Add file
                result = await self.ipfs_kit.add_file(file_path)
            else:
                return {"error": "Either content or file_path must be provided"}
            
            self.server_state["ipfs_integration"]["operations_count"] += 1
            return {"success": True, "cid": result.get("Hash"), "result": result}
        
        except Exception as e:
            self.server_state["ipfs_integration"]["errors_count"] += 1
            return {"error": f"IPFS add failed: {str(e)}", "mock": True}
    
    async def _ipfs_cat(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve content from IPFS."""
        
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available", "mock": True}
        
        try:
            cid = arguments.get("cid")
            if not cid:
                return {"error": "CID is required"}
            
            content = await self.ipfs_kit.cat(cid)
            self.server_state["ipfs_integration"]["operations_count"] += 1
            return {"success": True, "content": content}
        
        except Exception as e:
            self.server_state["ipfs_integration"]["errors_count"] += 1
            return {"error": f"IPFS cat failed: {str(e)}", "mock": True}
    
    async def _ipfs_pin_add(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Pin content in IPFS."""
        
        if not self.ipfs_kit:
            return {"error": "IPFS Kit not available", "mock": True}
        
        try:
            cid = arguments.get("cid")
            recursive = arguments.get("recursive", True)
            
            if not cid:
                return {"error": "CID is required"}
            
            result = await self.ipfs_kit.pin_add(cid, recursive=recursive)
            self.server_state["ipfs_integration"]["operations_count"] += 1
            return {"success": True, "result": result}
        
        except Exception as e:
            self.server_state["ipfs_integration"]["errors_count"] += 1
            return {"error": f"IPFS pin failed: {str(e)}", "mock": True}
    
    async def _get_backend_status(self) -> Dict[str, Any]:
        """Get comprehensive backend status."""
        
        if COMPONENTS["backend_monitor"]:
            try:
                status = get_comprehensive_backend_status()
                recommendations = get_backend_recommendations(status)
                self.server_state["metrics"]["backend_checks"] += 1
                return {
                    "success": True,
                    "comprehensive_status": status,
                    "recommendations": recommendations,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": "Backend monitoring not available"}
    
    async def _get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        
        # Update performance metrics
        self._update_performance_metrics()
        
        health_score = self._calculate_health_score()
        
        return {
            "status": "healthy" if health_score > 70 else "degraded" if health_score > 40 else "unhealthy",
            "health_score": health_score,
            "uptime_seconds": time.time() - self.start_time,
            "components": COMPONENTS,
            "server_state": self.server_state,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        
        backend_status = await self._get_backend_status()
        health_status = await self._get_health_status()
        
        return {
            "server_info": {
                "host": self.host,
                "port": self.port,
                "uptime_seconds": time.time() - self.start_time,
                "version": "2.0.0"
            },
            "health": health_status,
            "backends": backend_status,
            "observability": self._get_full_observability_data(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _update_performance_metrics(self):
        """Update performance metrics."""
        
        try:
            import psutil
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.server_state["performance"]["memory_usage_mb"] = memory.used / (1024 * 1024)
            
            # CPU usage
            self.server_state["performance"]["cpu_usage_percent"] = psutil.cpu_percent()
            
            # Uptime
            self.server_state["performance"]["uptime_seconds"] = time.time() - self.start_time
            
        except ImportError:
            # Fallback without psutil
            self.server_state["performance"]["uptime_seconds"] = time.time() - self.start_time
    
    def _calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        
        score = 100.0
        
        # Component availability
        available_components = sum(1 for available in COMPONENTS.values() if available)
        total_components = len(COMPONENTS)
        component_score = (available_components / total_components) * 50
        
        # Error rate
        total_requests = self.server_state["metrics"]["requests_total"]
        if total_requests > 0:
            error_rate = self.server_state["metrics"]["requests_error"] / total_requests
            error_score = max(0, 30 - (error_rate * 100))
        else:
            error_score = 30
        
        # Recent errors (last 5 minutes)
        recent_errors = [
            e for e in self.server_state["errors"]
            if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300
        ]
        recent_error_penalty = min(20, len(recent_errors) * 2)
        
        return max(0, component_score + error_score - recent_error_penalty)
    
    def _get_full_observability_data(self) -> Dict[str, Any]:
        """Get complete observability data."""
        
        return {
            "server_state": self.server_state,
            "components": COMPONENTS,
            "health_score": self._calculate_health_score(),
            "system_info": self._get_system_info(),
            "recent_errors": [
                e for e in self.server_state["errors"]
                if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 3600
            ]
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture(),
            "hostname": platform.node(),
            "working_directory": os.getcwd(),
            "process_id": os.getpid()
        }
    
    def _get_prometheus_metrics(self) -> str:
        """Generate Prometheus-style metrics."""
        
        metrics = []
        
        # Server metrics
        metrics.append(f"ipfs_kit_mcp_requests_total {self.server_state['metrics']['requests_total']}")
        metrics.append(f"ipfs_kit_mcp_requests_success {self.server_state['metrics']['requests_success']}")
        metrics.append(f"ipfs_kit_mcp_requests_error {self.server_state['metrics']['requests_error']}")
        metrics.append(f"ipfs_kit_mcp_tools_calls {self.server_state['metrics']['mcp_tools_calls']}")
        metrics.append(f"ipfs_kit_mcp_websocket_connections {len(self.server_state['connections']['websocket_active'])}")
        metrics.append(f"ipfs_kit_mcp_uptime_seconds {time.time() - self.start_time}")
        
        # Component status
        for component, available in COMPONENTS.items():
            metrics.append(f"ipfs_kit_component_available{{component=\"{component}\"}} {1 if available else 0}")
        
        # Health score
        metrics.append(f"ipfs_kit_health_score {self._calculate_health_score()}")
        
        return "\n".join(metrics)
    
    def _get_comprehensive_dashboard_html(self) -> str:
        """Generate comprehensive dashboard HTML."""
        
        health_score = self._calculate_health_score()
        uptime = time.time() - self.start_time
        
        # Component status indicators
        component_indicators = ""
        for component, available in COMPONENTS.items():
            status_class = "healthy" if available else "unhealthy"
            indicator = "✓" if available else "✗"
            component_indicators += f"""
            <div class="component-status {status_class}">
                <strong>{component.replace('_', ' ').title()}:</strong>
                <span class="status-indicator">{indicator}</span>
            </div>
            """
        
        # Recent errors
        recent_errors = [
            e for e in self.server_state["errors"]
            if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300
        ]
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Unified IPFS Kit MCP Server - Full Observability Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1400px; 
            margin: 0 auto; 
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        .header {{ 
            text-align: center; 
            margin-bottom: 40px; 
            padding-bottom: 20px;
            border-bottom: 3px solid #e2e8f0;
        }}
        .header h1 {{ 
            color: #2d3748; 
            margin-bottom: 10px; 
            font-size: 2.5rem;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header p {{ color: #718096; font-size: 1.1rem; }}
        .grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); 
            gap: 25px; 
            margin-bottom: 30px;
        }}
        .card {{ 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            border: 1px solid #e2e8f0;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.15);
        }}
        .card h2 {{ 
            margin: 0 0 20px 0; 
            color: #2d3748; 
            border-bottom: 2px solid #e2e8f0; 
            padding-bottom: 10px;
            font-size: 1.3rem;
        }}
        .metric {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            margin: 12px 0; 
            padding: 10px; 
            background: #f8fafc; 
            border-radius: 8px;
            border-left: 4px solid #4299e1;
        }}
        .metric-label {{ font-weight: 600; color: #4a5568; }}
        .metric-value {{ 
            font-family: 'Monaco', 'Menlo', monospace; 
            font-weight: bold;
            color: #2d3748;
        }}
        .health-score {{ 
            text-align: center; 
            font-size: 3rem; 
            font-weight: bold; 
            margin: 20px 0;
            color: {('#48bb78' if health_score > 70 else '#ed8936' if health_score > 40 else '#f56565')};
        }}
        .component-status {{ 
            margin: 10px 0; 
            padding: 12px; 
            border-radius: 8px; 
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .component-status.healthy {{ 
            background: #f0fff4; 
            border-left: 4px solid #48bb78; 
            color: #22543d;
        }}
        .component-status.unhealthy {{ 
            background: #fff5f5; 
            border-left: 4px solid #f56565; 
            color: #742a2a;
        }}
        .status-indicator {{ 
            font-size: 1.2rem; 
            font-weight: bold;
        }}
        .error-count {{ 
            background: #fed7d7; 
            color: #c53030; 
            padding: 6px 12px; 
            border-radius: 6px; 
            font-size: 0.9rem;
            font-weight: bold;
        }}
        .quick-links {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
        }}
        .quick-links a {{ 
            padding: 12px; 
            background: linear-gradient(45deg, #4299e1, #3182ce); 
            color: white; 
            text-decoration: none; 
            border-radius: 8px; 
            text-align: center;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
        .quick-links a:hover {{ 
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .refresh-btn {{ 
            position: fixed; 
            bottom: 30px; 
            right: 30px; 
            background: linear-gradient(45deg, #48bb78, #38a169); 
            color: white; 
            border: none; 
            padding: 15px 25px; 
            border-radius: 30px; 
            cursor: pointer; 
            font-size: 1rem;
            font-weight: bold;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transition: all 0.2s ease;
        }}
        .refresh-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.3);
        }}
        .status-good {{ color: #48bb78; }}
        .status-warning {{ color: #ed8936; }}
        .status-error {{ color: #f56565; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Unified IPFS Kit MCP Server</h1>
            <p>Full Observability Dashboard with Real-time Backend Monitoring</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>🏥 System Health</h2>
                <div class="health-score">{health_score:.1f}%</div>
                <div class="metric">
                    <span class="metric-label">Overall Health Score</span>
                    <span class="metric-value {('status-good' if health_score > 70 else 'status-warning' if health_score > 40 else 'status-error')}">{health_score:.1f}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value">{uptime/3600:.1f}h {(uptime%3600)/60:.0f}m</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Total Requests:</span>
                    <span class="metric-value">{self.server_state["metrics"]["requests_total"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Success Rate:</span>
                    <span class="metric-value">{(self.server_state["metrics"]["requests_success"] / max(self.server_state["metrics"]["requests_total"], 1) * 100):.1f}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active WebSocket:</span>
                    <span class="metric-value">{len(self.server_state["connections"]["websocket_active"])}</span>
                </div>
                {f'<div class="metric"><span class="metric-label">Recent Errors:</span><span class="error-count">{len(recent_errors)}</span></div>' if recent_errors else ''}
            </div>
            
            <div class="card">
                <h2>🔧 Component Status</h2>
                {component_indicators}
            </div>
            
            <div class="card">
                <h2>📊 MCP Performance</h2>
                <div class="metric">
                    <span class="metric-label">MCP Tool Calls:</span>
                    <span class="metric-value">{self.server_state["metrics"]["mcp_tools_calls"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active MCP Clients:</span>
                    <span class="metric-value">{self.server_state["connections"]["mcp_clients"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">IPFS Operations:</span>
                    <span class="metric-value">{self.server_state["ipfs_integration"]["operations_count"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Avg Response Time:</span>
                    <span class="metric-value">{self.server_state["metrics"]["average_response_time"]:.3f}s</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🗄️ IPFS Integration</h2>
                <div class="metric">
                    <span class="metric-label">Daemon Status:</span>
                    <span class="metric-value">{self.server_state["ipfs_integration"]["daemon_status"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Operations Count:</span>
                    <span class="metric-value">{self.server_state["ipfs_integration"]["operations_count"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Error Count:</span>
                    <span class="metric-value">{self.server_state["ipfs_integration"]["errors_count"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">IPFS Kit Available:</span>
                    <span class="metric-value status-{'good' if COMPONENTS['ipfs_kit'] else 'error'}">{'Yes' if COMPONENTS['ipfs_kit'] else 'No'}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>📈 Backend Monitor</h2>
                <div id="backend-status">Loading backend status...</div>
            </div>
            
            <div class="card">
                <h2>🔗 Quick Actions</h2>
                <div class="quick-links">
                    <a href="/dashboard/api/status">Full Status API</a>
                    <a href="/dashboard/api/backends">Backend Status</a>
                    <a href="/observability">Full Observability</a>
                    <a href="/debug">Debug Info</a>
                    <a href="/metrics">Prometheus Metrics</a>
                    <a href="/health">Health Check</a>
                    <a href="/docs">API Documentation</a>
                </div>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="window.location.reload()">🔄 Refresh</button>
    
    <script>
        // Auto-refresh every 30 seconds
        setInterval(() => {{
            window.location.reload();
        }}, 30000);
        
        // Load backend status
        fetch('/dashboard/api/backends')
            .then(r => r.json())
            .then(data => {{
                if (data.success && data.status) {{
                    const backends = data.status.backends || {{}};
                    const running = Object.values(backends).filter(b => b.status === 'running').length;
                    const total = Object.keys(backends).length;
                    
                    document.getElementById('backend-status').innerHTML = 
                        `<div class="metric">
                            <span class="metric-label">Total Backends:</span>
                            <span class="metric-value">${{total}}</span>
                         </div>
                         <div class="metric">
                            <span class="metric-label">Running Backends:</span>
                            <span class="metric-value status-${{running > 0 ? 'good' : 'error'}}">${{running}}</span>
                         </div>
                         <div class="metric">
                            <span class="metric-label">Health Score:</span>
                            <span class="metric-value">${{data.status.summary?.health_score || 0}}%</span>
                         </div>`;
                }} else {{
                    document.getElementById('backend-status').innerHTML = 
                        '<div class="metric"><span class="metric-label">Status:</span><span class="metric-value status-warning">Monitoring Unavailable</span></div>';
                }}
            }})
            .catch(e => {{
                document.getElementById('backend-status').innerHTML = 
                    '<div class="metric"><span class="metric-label">Status:</span><span class="metric-value status-error">Error Loading</span></div>';
            }});
    </script>
</body>
</html>"""
    
    async def start_background_services(self):
        """Start background monitoring services."""
        
        self.monitoring_active = True
        
        # Start dashboard data collection if available
        if self.data_collector and hasattr(self.data_collector, 'start_collection'):
            try:
                await self.data_collector.start_collection()
                logger.info("✓ Dashboard data collection started")
            except Exception as e:
                logger.error(f"Failed to start data collection: {e}")
        elif self.data_collector:
            logger.info("✓ Dashboard data collector ready (no start_collection method)")
        
        # Start periodic health checks
        asyncio.create_task(self._periodic_health_check())
        
        # Start IPFS daemon monitoring
        if self.ipfs_kit:
            asyncio.create_task(self._monitor_ipfs_daemon())
        
        logger.info("✓ Background services started")
    
    async def _periodic_health_check(self):
        """Periodic health monitoring."""
        
        while self.monitoring_active:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Update performance metrics
                self._update_performance_metrics()
                
                # Check for alerts
                health_score = self._calculate_health_score()
                if health_score < 50:
                    self.server_state["alerts"].append({
                        "timestamp": datetime.now().isoformat(),
                        "severity": "warning" if health_score > 30 else "critical",
                        "message": f"Low health score: {health_score:.1f}%",
                        "component": "health_monitor"
                    })
                    self.server_state["metrics"]["alerts_generated"] += 1
                
                # Limit stored errors and alerts to last 100 entries
                self.server_state["errors"] = self.server_state["errors"][-100:]
                self.server_state["alerts"] = self.server_state["alerts"][-100:]
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
    
    async def _monitor_ipfs_daemon(self):
        """Monitor IPFS daemon status."""
        
        while self.monitoring_active:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check daemon status
                try:
                    status = await self.ipfs_kit.daemon_status()
                    self.server_state["ipfs_integration"]["daemon_status"] = "running" if status else "stopped"
                    self.server_state["ipfs_integration"]["last_check"] = datetime.now().isoformat()
                except Exception as e:
                    self.server_state["ipfs_integration"]["daemon_status"] = "error"
                    logger.warning(f"IPFS daemon check failed: {e}")
                
            except Exception as e:
                logger.error(f"IPFS monitoring failed: {e}")
    
    async def stop_background_services(self):
        """Stop background services."""
        
        self.monitoring_active = False
        
        if self.data_collector and hasattr(self.data_collector, 'stop_collection'):
            try:
                await self.data_collector.stop_collection()
                logger.info("✓ Dashboard data collection stopped")
            except Exception as e:
                logger.error(f"Failed to stop data collection: {e}")
        elif self.data_collector:
            logger.info("✓ Dashboard data collector cleaned up")
        
        logger.info("✓ Background services stopped")
    
    async def run(self):
        """Run the unified server."""
        
        if not COMPONENTS["web_framework"]:
            logger.error("❌ Web framework not available - cannot start server")
            return
        
        try:
            # Start background services
            await self.start_background_services()
            
            logger.info(f"🚀 Starting Unified Observability MCP Server on {self.host}:{self.port}")
            logger.info(f"📊 Component Status: {COMPONENTS}")
            logger.info(f"🌐 Dashboard: http://{self.host}:{self.port}/")
            logger.info(f"📡 MCP Endpoint: http://{self.host}:{self.port}/mcp")
            logger.info(f"🔌 WebSocket: ws://{self.host}:{self.port}/mcp/ws")
            
            # Run the server
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"❌ Server failed to start: {e}")
            raise
        finally:
            await self.stop_background_services()


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="Unified IPFS Kit MCP Server with Full Observability")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    
    args = parser.parse_args()
    
    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        logger.info("🛑 Shutdown signal received")
        raise KeyboardInterrupt
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Initializing Unified IPFS Kit MCP Server with Full Observability")
    logger.info(f"📊 Available Components: {[k for k, v in COMPONENTS.items() if v]}")
    logger.info(f"⚠️  Missing Components: {[k for k, v in COMPONENTS.items() if not v]}")
    
    # Create and run server
    server = UnifiedObservabilityMCPServer(host=args.host, port=args.port)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("👋 Server shutdown requested")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
