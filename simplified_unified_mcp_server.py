#!/usr/bin/env python3
"""
Simplified Unified MCP Server with Full Observability
====================================================

A streamlined version that avoids protobuf conflicts while providing
comprehensive observability and dashboard functionality.
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
import psutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging
log_dir = Path("/tmp/ipfs_kit_logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'simplified_unified_mcp.log', mode='a')
    ]
)
logger = logging.getLogger("simplified-unified-mcp")

# Add project root to Python path
current_dir = Path(__file__).parent
project_root = current_dir
sys.path.insert(0, str(project_root))

# Component status tracking
COMPONENTS = {
    "web_framework": False,
    "dashboard": False,
    "backend_monitor": False,
    "mcp_tools": True  # Always available as we implement them directly
}

# Import web framework
try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
    from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    COMPONENTS["web_framework"] = True
    logger.info("✓ Web framework imported")
except ImportError as e:
    logger.error(f"❌ Web framework import failed: {e}")

# Import dashboard components (optional)
try:
    from dashboard.comprehensive_backend_monitor import (
        get_comprehensive_backend_status as _get_backend_status_async,
        get_backend_recommendations as _get_backend_recommendations_async
    )
    # Temporarily disable backend monitor due to hanging issues
    COMPONENTS["backend_monitor"] = False
    logger.info("⚠️  Backend monitor temporarily disabled")
    
    # Fallback functions
    async def get_comprehensive_backend_status():
        return {"backends": {}, "summary": {"health_score": 75, "status": "simplified_mode"}}
    
    async def get_backend_recommendations():
        return [{"type": "info", "title": "Backend monitoring in simplified mode"}]
        
except ImportError as e:
    logger.warning(f"⚠️  Backend monitor import failed: {e}")
    COMPONENTS["backend_monitor"] = False
    
    # Fallback functions
    async def get_comprehensive_backend_status():
        return {"backends": {}, "summary": {"health_score": 0}}
    
    async def get_backend_recommendations():
        return [{"type": "info", "title": "Backend monitoring not available"}]

try:
    from dashboard.config import DashboardConfig
    COMPONENTS["dashboard"] = True
    logger.info("✓ Dashboard config imported")
except ImportError as e:
    logger.warning(f"⚠️  Dashboard config import failed: {e}")


class SimplifiedMCPTool:
    """Simplified MCP tool representation."""
    
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


class SimplifiedUnifiedMCPServer:
    """
    Simplified unified MCP server with full observability.
    Avoids problematic imports while providing comprehensive functionality.
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8766):
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Server state for observability
        self.server_state = {
            "initialization_time": datetime.now().isoformat(),
            "components": COMPONENTS.copy(),
            "connections": {
                "websocket_active": 0,  # Changed from set to count
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
        
        # Keep websocket connections separately
        self.websocket_connections = set()
        
        # MCP Tools
        self.mcp_tools = self._create_mcp_tools()
        
        # Background monitoring
        self.monitoring_active = False
        
        logger.info(f"🚀 Initializing Simplified Unified MCP Server on {host}:{port}")
        
        # Initialize web server
        if COMPONENTS["web_framework"]:
            self._setup_web_server()
        else:
            logger.error("❌ Cannot start server without web framework")
    
    def _create_mcp_tools(self) -> List[SimplifiedMCPTool]:
        """Create MCP tools."""
        
        return [
            SimplifiedMCPTool(
                name="system_health",
                description="Get comprehensive system health status including backend monitoring",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_status",
                description="Get comprehensive backend status and monitoring data",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            SimplifiedMCPTool(
                name="get_observability_data",
                description="Get full observability data including metrics, errors, and performance",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            SimplifiedMCPTool(
                name="ipfs_status_check",
                description="Check IPFS daemon and backend status",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            SimplifiedMCPTool(
                name="performance_metrics",
                description="Get detailed performance metrics and system information",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    def _setup_web_server(self):
        """Setup FastAPI web server."""
        
        self.app = FastAPI(
            title="Simplified Unified IPFS Kit MCP Server",
            description="MCP server with comprehensive monitoring and full observability",
            version="2.1.0",
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
                if total_requests > 0:
                    self.server_state["metrics"]["average_response_time"] = (
                        (current_avg * (total_requests - 1) + duration) / total_requests
                    )
        
        self._setup_routes()
        logger.info("✓ Web server configured")
    
    def _setup_routes(self):
        """Setup all web server routes."""
        
        # Root endpoint - comprehensive dashboard
        @self.app.get("/")
        async def root():
            self.server_state["metrics"]["dashboard_views"] += 1
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
            self.websocket_connections.add(websocket)
            self.server_state["connections"]["websocket_active"] = len(self.websocket_connections)
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
                self.websocket_connections.discard(websocket)
                self.server_state["connections"]["websocket_active"] = len(self.websocket_connections)
                self.server_state["connections"]["mcp_clients"] = max(0, 
                    self.server_state["connections"]["mcp_clients"] - 1)
        
        # Health endpoint
        @self.app.get("/health")
        async def health():
            return JSONResponse(await self._get_health_status())
        
        # Dashboard status API
        @self.app.get("/dashboard/api/status")
        async def dashboard_status():
            return JSONResponse(await self._get_comprehensive_status())
        
        # Backend status API
        @self.app.get("/dashboard/api/backends")
        async def backend_status():
            return JSONResponse(await self._get_backend_status())
        
        # Metrics endpoint
        @self.app.get("/metrics")
        async def metrics():
            return PlainTextResponse(self._get_prometheus_metrics())
        
        # Observability endpoint
        @self.app.get("/observability")
        async def observability():
            return JSONResponse(self._get_full_observability_data())
        
        # Debug endpoint
        @self.app.get("/debug")
        async def debug():
            return JSONResponse({
                "server_state": self.server_state,
                "components": COMPONENTS,
                "system_info": self._get_system_info(),
                "mcp_tools": [tool.to_dict() for tool in self.mcp_tools]
            })
    
    async def _handle_mcp_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP JSON-RPC requests."""
        
        try:
            method = data.get("method")
            params = data.get("params", {})
            
            if method == "tools/list":
                return {
                    "id": data.get("id"),
                    "result": {
                        "tools": [tool.to_dict() for tool in self.mcp_tools]
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await self._execute_mcp_tool(tool_name, arguments)
                return {
                    "id": data.get("id"),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }]
                    }
                }
            else:
                return {
                    "id": data.get("id"),
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
        
        except Exception as e:
            logger.error(f"MCP request handling failed: {e}")
            return {
                "id": data.get("id", None),
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
            }
    
    async def _execute_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool."""
        
        try:
            if tool_name == "system_health":
                return await self._get_health_status()
            elif tool_name == "get_backend_status":
                return await self._get_backend_status()
            elif tool_name == "get_observability_data":
                return self._get_full_observability_data()
            elif tool_name == "ipfs_status_check":
                return await self._check_ipfs_status()
            elif tool_name == "performance_metrics":
                return self._get_performance_metrics()
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            error_msg = f"Tool {tool_name} failed: {str(e)}"
            logger.error(error_msg)
            self.server_state["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "component": "mcp_tool",
                "tool": tool_name,
                "error": str(e),
                "arguments": arguments
            })
            return {"error": error_msg, "traceback": traceback.format_exc()}
    
    async def _get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        
        self._update_performance_metrics()
        health_score = self._calculate_health_score()
        
        return {
            "status": "healthy" if health_score > 70 else "degraded" if health_score > 40 else "unhealthy",
            "health_score": health_score,
            "uptime_seconds": time.time() - self.start_time,
            "components": COMPONENTS,
            "server_state": self.server_state,
            "system_info": self._get_system_info(),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _get_backend_status(self) -> Dict[str, Any]:
        """Get backend status using available monitoring."""
        
        if COMPONENTS["backend_monitor"]:
            try:
                status = await get_comprehensive_backend_status()
                recommendations = await get_backend_recommendations()
                self.server_state["metrics"]["backend_checks"] += 1
                return {
                    "success": True,
                    "comprehensive_status": status,
                    "recommendations": recommendations,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"Backend monitoring failed: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": False, 
                "error": "Backend monitoring not available",
                "basic_status": self._get_basic_system_status()
            }
    
    async def _check_ipfs_status(self) -> Dict[str, Any]:
        """Check IPFS daemon status."""
        
        try:
            # Check if IPFS daemon is running
            ipfs_running = False
            ipfs_api_available = False
            
            # Check for IPFS process
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'ipfs' in proc.info['name'].lower():
                        ipfs_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Try to connect to IPFS API
            try:
                import requests
                response = requests.get("http://127.0.0.1:5001/api/v0/version", timeout=5)
                if response.status_code == 200:
                    ipfs_api_available = True
                    ipfs_version = response.json().get("Version", "unknown")
                else:
                    ipfs_version = "unknown"
            except Exception:
                ipfs_version = "unknown"
            
            return {
                "daemon_running": ipfs_running,
                "api_available": ipfs_api_available,
                "version": ipfs_version,
                "status": "running" if ipfs_running and ipfs_api_available else "stopped",
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "error": f"IPFS status check failed: {e}",
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        
        self._update_performance_metrics()
        
        return {
            "system": self.server_state["performance"],
            "connections": self.server_state["connections"],
            "metrics": self.server_state["metrics"],
            "recent_errors": len([
                e for e in self.server_state["errors"]
                if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300
            ]),
            "health_score": self._calculate_health_score(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _update_performance_metrics(self):
        """Update performance metrics."""
        
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            self.server_state["performance"]["memory_usage_mb"] = memory.used / (1024 * 1024)
            
            # CPU usage
            self.server_state["performance"]["cpu_usage_percent"] = psutil.cpu_percent()
            
            # Uptime
            self.server_state["performance"]["uptime_seconds"] = time.time() - self.start_time
            
        except Exception as e:
            logger.warning(f"Failed to update performance metrics: {e}")
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
    
    def _get_basic_system_status(self) -> Dict[str, Any]:
        """Get basic system status as fallback."""
        
        try:
            return {
                "memory_usage_percent": psutil.virtual_memory().percent,
                "cpu_usage_percent": psutil.cpu_percent(),
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"System status failed: {e}"}
    
    async def _get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        
        backend_status = await self._get_backend_status()
        health_status = await self._get_health_status()
        
        return {
            "server_info": {
                "host": self.host,
                "port": self.port,
                "uptime_seconds": time.time() - self.start_time,
                "version": "2.1.0"
            },
            "health": health_status,
            "backends": backend_status,
            "observability": self._get_full_observability_data(),
            "timestamp": datetime.now().isoformat()
        }
    
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
            ],
            "mcp_tools_available": len(self.mcp_tools),
            "performance_snapshot": self._get_performance_metrics()
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture(),
            "hostname": platform.node(),
            "working_directory": os.getcwd(),
            "process_id": os.getpid(),
            "available_memory_gb": psutil.virtual_memory().total / (1024**3),
            "cpu_count": psutil.cpu_count()
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
        
        # Performance metrics
        self._update_performance_metrics()
        metrics.append(f"ipfs_kit_memory_usage_mb {self.server_state['performance']['memory_usage_mb']}")
        metrics.append(f"ipfs_kit_cpu_usage_percent {self.server_state['performance']['cpu_usage_percent']}")
        metrics.append(f"ipfs_kit_websocket_connections {len(self.websocket_connections)}")
        
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
    <title>🚀 Simplified Unified IPFS Kit MCP Server - Full Observability</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1600px; 
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
            font-size: 3.5rem; 
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
        .wide-card {{ grid-column: 1 / -1; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Simplified Unified IPFS Kit MCP Server</h1>
            <p>Full Observability Dashboard with Comprehensive Backend Monitoring</p>
            <p style="font-size: 0.9rem; color: #a0aec0;">Running on {self.host}:{self.port} | Version 2.1.0</p>
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
                    <span class="metric-value">{len(self.websocket_connections)}</span>
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
                    <span class="metric-label">MCP Tools Available:</span>
                    <span class="metric-value">{len(self.mcp_tools)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Tool Calls:</span>
                    <span class="metric-value">{self.server_state["metrics"]["mcp_tools_calls"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Active Clients:</span>
                    <span class="metric-value">{self.server_state["connections"]["mcp_clients"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Avg Response Time:</span>
                    <span class="metric-value">{self.server_state["metrics"]["average_response_time"]:.3f}s</span>
                </div>
            </div>
            
            <div class="card">
                <h2>💻 System Performance</h2>
                <div class="metric">
                    <span class="metric-label">Memory Usage:</span>
                    <span class="metric-value">{self.server_state["performance"]["memory_usage_mb"]:.0f} MB</span>
                </div>
                <div class="metric">
                    <span class="metric-label">CPU Usage:</span>
                    <span class="metric-value">{self.server_state["performance"]["cpu_usage_percent"]:.1f}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Dashboard Views:</span>
                    <span class="metric-value">{self.server_state["metrics"]["dashboard_views"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Backend Checks:</span>
                    <span class="metric-value">{self.server_state["metrics"]["backend_checks"]}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🗄️ Backend Status</h2>
                <div id="backend-status">Loading backend status...</div>
            </div>
            
            <div class="card">
                <h2>📈 IPFS Integration</h2>
                <div id="ipfs-status">Loading IPFS status...</div>
            </div>
            
            <div class="card wide-card">
                <h2>🔗 Quick Actions & API Endpoints</h2>
                <div class="quick-links">
                    <a href="/dashboard/api/status">📊 Full Status API</a>
                    <a href="/dashboard/api/backends">🗄️ Backend Status</a>
                    <a href="/observability">🔍 Full Observability</a>
                    <a href="/debug">🐛 Debug Info</a>
                    <a href="/metrics">📈 Prometheus Metrics</a>
                    <a href="/health">🏥 Health Check</a>
                    <a href="/docs">📚 API Documentation</a>
                    <a href="/mcp">📡 MCP Endpoint</a>
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
                if (data.success && data.comprehensive_status) {{
                    const backends = data.comprehensive_status.backends || {{}};
                    const running = Object.values(backends).filter(b => b.status === 'running').length;
                    const total = Object.keys(backends).length;
                    
                    document.getElementById('backend-status').innerHTML = 
                        `<div class="metric">
                            <span class="metric-label">Total Backends:</span>
                            <span class="metric-value">${{total}}</span>
                         </div>
                         <div class="metric">
                            <span class="metric-label">Running:</span>
                            <span class="metric-value status-${{running > 0 ? 'good' : 'error'}}">${{running}}</span>
                         </div>
                         <div class="metric">
                            <span class="metric-label">Health:</span>
                            <span class="metric-value">${{data.comprehensive_status.summary?.health_score || 0}}%</span>
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
        
        // Load IPFS status
        fetch('/mcp', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {{
                    "name": "ipfs_status_check",
                    "arguments": {{}}
                }}
            }})
        }})
        .then(r => r.json())
        .then(data => {{
            if (data.result && data.result.content) {{
                const ipfsStatus = JSON.parse(data.result.content[0].text);
                const status = ipfsStatus.status || 'unknown';
                const apiAvailable = ipfsStatus.api_available || false;
                
                document.getElementById('ipfs-status').innerHTML = 
                    `<div class="metric">
                        <span class="metric-label">Daemon Status:</span>
                        <span class="metric-value status-${{status === 'running' ? 'good' : 'error'}}">${{status}}</span>
                     </div>
                     <div class="metric">
                        <span class="metric-label">API Available:</span>
                        <span class="metric-value status-${{apiAvailable ? 'good' : 'error'}}">${{apiAvailable ? 'Yes' : 'No'}}</span>
                     </div>
                     <div class="metric">
                        <span class="metric-label">Version:</span>
                        <span class="metric-value">${{ipfsStatus.version || 'unknown'}}</span>
                     </div>`;
            }} else {{
                document.getElementById('ipfs-status').innerHTML = 
                    '<div class="metric"><span class="metric-label">Status:</span><span class="metric-value status-warning">Check Failed</span></div>';
            }}
        }})
        .catch(e => {{
            document.getElementById('ipfs-status').innerHTML = 
                '<div class="metric"><span class="metric-label">Status:</span><span class="metric-value status-error">Error Loading</span></div>';
        }});
    </script>
</body>
</html>"""
    
    async def start_background_monitoring(self):
        """Start background monitoring services."""
        
        self.monitoring_active = True
        
        # Start periodic health checks
        asyncio.create_task(self._periodic_health_check())
        
        logger.info("✓ Background monitoring started")
    
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
    
    async def stop_background_monitoring(self):
        """Stop background monitoring."""
        
        self.monitoring_active = False
        logger.info("✓ Background monitoring stopped")
    
    async def run(self):
        """Run the simplified unified server."""
        
        if not COMPONENTS["web_framework"]:
            logger.error("❌ Web framework not available - cannot start server")
            return
        
        try:
            # Start background services
            await self.start_background_monitoring()
            
            logger.info(f"🚀 Starting Simplified Unified MCP Server on {self.host}:{self.port}")
            logger.info(f"📊 Component Status: {COMPONENTS}")
            logger.info(f"🌐 Dashboard: http://{self.host}:{self.port}/")
            logger.info(f"📡 MCP Endpoint: http://{self.host}:{self.port}/mcp")
            logger.info(f"🔌 WebSocket: ws://{self.host}:{self.port}/mcp/ws")
            logger.info(f"🛠️  Available MCP Tools: {len(self.mcp_tools)}")
            
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
            await self.stop_background_monitoring()


async def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="Simplified Unified IPFS Kit MCP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8766, help="Server port")
    
    args = parser.parse_args()
    
    # Handle shutdown gracefully
    def signal_handler(signum, frame):
        logger.info("🛑 Shutdown signal received")
        raise KeyboardInterrupt
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Initializing Simplified Unified IPFS Kit MCP Server")
    logger.info(f"📊 Available Components: {[k for k, v in COMPONENTS.items() if v]}")
    logger.info(f"⚠️  Missing Components: {[k for k, v in COMPONENTS.items() if not v]}")
    
    # Create and run server
    server = SimplifiedUnifiedMCPServer(host=args.host, port=args.port)
    
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
