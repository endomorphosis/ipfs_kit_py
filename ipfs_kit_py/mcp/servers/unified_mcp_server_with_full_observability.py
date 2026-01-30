#!/usr/bin/env python3
"""
Unified MCP Server with Full Observability
==========================================

This server integrates:
1. Enhanced MCP Server with daemon management
2. Integrated dashboard server with comprehensive monitoring  
3. Real-time observability into all program states
4. Full backend status tracking and alerting
5. Advanced debugging and introspection capabilities

Key features:
- Unified MCP JSON-RPC and WebSocket endpoints
- Real-time dashboard with comprehensive backend monitoring
- Deep introspection into IPFS Kit state and daemon management
- Enhanced error handling and fallback mechanisms
- Performance monitoring and alerting
- Debug endpoints for troubleshooting
"""

import sys
import os
import json
import anyio
import logging
import traceback
import time
import subprocess
import tempfile
import platform
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging for better observability
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('/tmp/unified_mcp_server.log', mode='a')
    ]
)
logger = logging.getLogger("unified-mcp-server")

# Add project root to Python path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Import components with detailed error tracking
COMPONENT_STATUS = {
    "mcp_server": False,
    "dashboard": False,
    "web_framework": False,
    "ipfs_kit": False,
    "comprehensive_monitor": False
}

try:
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt, handle_message
    COMPONENT_STATUS["mcp_server"] = True
    logger.info("✓ MCP server components imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import MCP server: {e}")

try:
    from dashboard.config import DashboardConfig
    from dashboard.web_dashboard import WebDashboard
    from dashboard.data_collector import DataCollector
    from dashboard.metrics_aggregator import MetricsAggregator
    from dashboard.comprehensive_backend_monitor import get_comprehensive_backend_status, get_backend_recommendations
    COMPONENT_STATUS["dashboard"] = True
    COMPONENT_STATUS["comprehensive_monitor"] = True
    logger.info("✓ Dashboard and monitoring components imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import dashboard: {e}")

try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    COMPONENT_STATUS["web_framework"] = True
    logger.info("✓ Web framework imports successful")
except ImportError as e:
    logger.error(f"❌ Failed to import web framework: {e}")


class UnifiedMCPServerWithObservability:
    """
    Unified MCP server combining all functionality with full observability.
    
    Provides:
    - MCP JSON-RPC API via HTTP and WebSocket
    - Real-time dashboard with comprehensive monitoring
    - Deep program state introspection
    - Enhanced debugging and troubleshooting
    - Performance monitoring and alerting
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        """Initialize the unified server with full observability."""
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # Server state tracking for observability
        self.server_state = {
            "initialization_time": datetime.now().isoformat(),
            "component_status": COMPONENT_STATUS.copy(),
            "active_connections": {
                "websocket": set(),
                "http_sessions": 0
            },
            "metrics": {
                "requests_total": 0,
                "requests_success": 0,
                "requests_error": 0,
                "last_request_time": None,
                "average_response_time": 0.0,
                "backend_status_updates": 0,
                "alert_count": 0
            },
            "errors": [],
            "performance": {
                "memory_usage_mb": 0,
                "cpu_usage_percent": 0,
                "disk_io_read_mb": 0,
                "disk_io_write_mb": 0
            }
        }
        
        # Initialize FastAPI with enhanced error handling
        self.app = FastAPI(
            title="Unified IPFS Kit MCP Server with Full Observability",
            description="Complete MCP server with comprehensive monitoring and debugging",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            debug=True
        )
        
        # Initialize components with error tracking
        self.mcp_server = None
        self.dashboard_config = None
        self.dashboard_data_collector = None
        self.dashboard_metrics_aggregator = None
        
        self._initialize_components()
        self._setup_middleware()
        self._setup_routes()
        self._setup_observability_endpoints()
        
        logger.info(f"🚀 Unified server initialized on {host}:{port}")
        logger.info(f"📊 Component status: {COMPONENT_STATUS}")
    
    def _initialize_components(self):
        """Initialize all server components with detailed error tracking."""
        
        # Initialize MCP server
        if COMPONENT_STATUS["mcp_server"]:
            try:
                self.mcp_server = EnhancedMCPServerWithDaemonMgmt()
                logger.info("✓ MCP server component initialized")
                self.server_state["component_status"]["mcp_server"] = True
            except Exception as e:
                logger.error(f"❌ Failed to initialize MCP server: {e}")
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "mcp_server",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
        
        # Initialize dashboard components
        if COMPONENT_STATUS["dashboard"]:
            try:
                self.dashboard_config = DashboardConfig()
                self.dashboard_data_collector = DataCollector(
                    update_interval=5,
                    enable_vfs_analytics=True
                )
                self.dashboard_metrics_aggregator = MetricsAggregator()
                logger.info("✓ Dashboard components initialized")
                self.server_state["component_status"]["dashboard"] = True
            except Exception as e:
                logger.error(f"❌ Failed to initialize dashboard: {e}")
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "dashboard",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
    
    def _setup_middleware(self):
        """Setup FastAPI middleware with request tracking."""
        
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
            self.server_state["metrics"]["requests_total"] += 1
            self.server_state["active_connections"]["http_sessions"] += 1
            
            try:
                response = await call_next(request)
                self.server_state["metrics"]["requests_success"] += 1
                return response
            except Exception as e:
                self.server_state["metrics"]["requests_error"] += 1
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "http_request",
                    "error": str(e),
                    "path": str(request.url),
                    "method": request.method
                })
                raise
            finally:
                duration = time.time() - start_time
                self.server_state["metrics"]["last_request_time"] = datetime.now().isoformat()
                
                # Update average response time
                total_requests = self.server_state["metrics"]["requests_total"]
                current_avg = self.server_state["metrics"]["average_response_time"]
                new_avg = ((current_avg * (total_requests - 1)) + duration) / total_requests
                self.server_state["metrics"]["average_response_time"] = new_avg
                
                self.server_state["active_connections"]["http_sessions"] -= 1
    
    def _setup_routes(self):
        """Setup all server routes with enhanced observability."""
        
        # Root endpoint with server status
        @self.app.get("/")
        async def root():
            return {
                "service": "Unified IPFS Kit MCP Server with Full Observability",
                "version": "2.0.0",
                "status": "running",
                "uptime_seconds": time.time() - self.start_time,
                "component_status": self.server_state["component_status"],
                "endpoints": {
                    "dashboard": f"http://{self.host}:{self.port}/dashboard",
                    "mcp_http": f"http://{self.host}:{self.port}/mcp",
                    "mcp_websocket": f"ws://{self.host}:{self.port}/mcp/ws",
                    "observability": f"http://{self.host}:{self.port}/observability",
                    "health": f"http://{self.host}:{self.port}/health",
                    "metrics": f"http://{self.host}:{self.port}/metrics",
                    "debug": f"http://{self.host}:{self.port}/debug"
                }
            }
        
        # Enhanced MCP JSON-RPC endpoint
        @self.app.post("/mcp")
        async def mcp_jsonrpc(request: Request):
            """Enhanced MCP JSON-RPC endpoint with full observability."""
            try:
                body = await request.body()
                message = json.loads(body.decode('utf-8'))
                
                logger.info(f"📥 MCP Request: {message.get('method', 'unknown')} (ID: {message.get('id', 'none')})")
                
                if not self.mcp_server:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32000,
                            "message": "MCP server not available",
                            "data": {"component_status": self.server_state["component_status"]}
                        }
                    })
                
                # Handle MCP message with observability
                start_time = time.time()
                response = await handle_message(self.mcp_server, message)
                duration = time.time() - start_time
                
                logger.info(f"📤 MCP Response: {response.get('result', {}).get('success', 'unknown')} ({duration:.3f}s)")
                
                return JSONResponse(response)
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON decode error: {e}")
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }, status_code=400)
            except Exception as e:
                logger.error(f"❌ MCP request error: {e}")
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": message.get("id") if 'message' in locals() else None,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                }, status_code=500)
        
        # Enhanced MCP WebSocket endpoint
        @self.app.websocket("/mcp/ws")
        async def mcp_websocket(websocket: WebSocket):
            """Enhanced MCP WebSocket endpoint with connection tracking."""
            await websocket.accept()
            connection_id = id(websocket)
            self.server_state["active_connections"]["websocket"].add(connection_id)
            
            logger.info(f"🔌 WebSocket connected: {connection_id}")
            
            try:
                while True:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    logger.info(f"📥 WS MCP Request: {message.get('method', 'unknown')} (ID: {message.get('id', 'none')})")
                    
                    if self.mcp_server:
                        response = await handle_message(self.mcp_server, message)
                        await websocket.send_text(json.dumps(response))
                    else:
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "error": {"code": -32000, "message": "MCP server not available"}
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket disconnected: {connection_id}")
            except Exception as e:
                logger.error(f"❌ WebSocket error: {e}")
            finally:
                self.server_state["active_connections"]["websocket"].discard(connection_id)
        
        # Enhanced dashboard routes
        if COMPONENT_STATUS["dashboard"]:
            self._setup_dashboard_routes()
        
        # Health endpoint with comprehensive status
        @self.app.get("/health")
        async def health():
            """Comprehensive health check with component status."""
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime_seconds": time.time() - self.start_time,
                "components": {},
                "metrics": self.server_state["metrics"].copy(),
                "active_connections": {
                    "websocket": len(self.server_state["active_connections"]["websocket"]),
                    "http_sessions": self.server_state["active_connections"]["http_sessions"]
                }
            }
            
            # Check component health
            overall_healthy = True
            for component, status in self.server_state["component_status"].items():
                health_status["components"][component] = {
                    "status": "healthy" if status else "unhealthy",
                    "available": status
                }
                if not status and component in ["web_framework"]:  # Critical components
                    overall_healthy = False
            
            # Check for recent errors
            recent_errors = [e for e in self.server_state["errors"] 
                           if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300]
            if recent_errors:
                health_status["recent_errors"] = len(recent_errors)
                if len(recent_errors) > 5:
                    overall_healthy = False
            
            health_status["status"] = "healthy" if overall_healthy else "degraded"
            
            return health_status
        
        # Enhanced metrics endpoint
        @self.app.get("/metrics")
        async def metrics():
            """Prometheus-style metrics with enhanced observability."""
            metrics_text = []
            
            # Server metrics
            metrics_text.extend([
                f"# HELP mcp_server_uptime_seconds Server uptime in seconds",
                f"# TYPE mcp_server_uptime_seconds gauge",
                f"mcp_server_uptime_seconds {time.time() - self.start_time}",
                "",
                f"# HELP mcp_requests_total Total number of MCP requests",
                f"# TYPE mcp_requests_total counter",
                f"mcp_requests_total {self.server_state['metrics']['requests_total']}",
                "",
                f"# HELP mcp_requests_success_total Total number of successful MCP requests",
                f"# TYPE mcp_requests_success_total counter", 
                f"mcp_requests_success_total {self.server_state['metrics']['requests_success']}",
                "",
                f"# HELP mcp_requests_error_total Total number of failed MCP requests",
                f"# TYPE mcp_requests_error_total counter",
                f"mcp_requests_error_total {self.server_state['metrics']['requests_error']}",
                "",
                f"# HELP mcp_websocket_connections_active Active WebSocket connections",
                f"# TYPE mcp_websocket_connections_active gauge",
                f"mcp_websocket_connections_active {len(self.server_state['active_connections']['websocket'])}",
                ""
            ])
            
            # Component status metrics
            for component, status in self.server_state["component_status"].items():
                metrics_text.extend([
                    f"# HELP mcp_component_status Component availability status",
                    f"# TYPE mcp_component_status gauge",
                    f"mcp_component_status{{component=\"{component}\"}} {1 if status else 0}",
                    ""
                ])
            
            return PlainTextResponse("\n".join(metrics_text))
    
    def _setup_dashboard_routes(self):
        """Setup dashboard routes with enhanced monitoring."""
        
        # Serve dashboard static files
        try:
            dashboard_static_path = project_root / "dashboard" / "static"
            if dashboard_static_path.exists():
                self.app.mount("/dashboard/static", StaticFiles(directory=str(dashboard_static_path)), name="dashboard_static")
        except Exception as e:
            logger.warning(f"⚠️ Could not mount dashboard static files: {e}")
        
        # Serve dashboard templates
        try:
            dashboard_templates_path = project_root / "dashboard" / "templates"
            if dashboard_templates_path.exists():
                self.app.mount("/dashboard/templates", StaticFiles(directory=str(dashboard_templates_path)), name="dashboard_templates")
        except Exception as e:
            logger.warning(f"⚠️ Could not mount dashboard templates: {e}")
        
        # Main dashboard endpoint
        @self.app.get("/dashboard")
        async def dashboard():
            """Enhanced dashboard with full observability."""
            try:
                template_path = project_root / "dashboard" / "templates" / "functional_dashboard.html"
                if template_path.exists():
                    with open(template_path, 'r', encoding='utf-8') as f:
                        return HTMLResponse(f.read())
            except Exception as e:
                logger.warning(f"⚠️ Could not load dashboard template: {e}")
            
            # Fallback to enhanced inline dashboard
            return HTMLResponse(self._get_enhanced_fallback_dashboard())
        
        # Enhanced comprehensive backend status API
        @self.app.get("/dashboard/api/filesystem/status")
        async def dashboard_api_filesystem_status_unified():
            """Unified comprehensive filesystem and backend status with enhanced observability."""
            try:
                # Get comprehensive status
                if COMPONENT_STATUS["comprehensive_monitor"]:
                    status = await get_comprehensive_backend_status()
                    recommendations = await get_backend_recommendations()
                    
                    # Add observability data
                    enhanced_status = status.copy()
                    enhanced_status["server_observability"] = {
                        "component_status": self.server_state["component_status"],
                        "server_metrics": self.server_state["metrics"],
                        "active_connections": {
                            "websocket": len(self.server_state["active_connections"]["websocket"]),
                            "http_sessions": self.server_state["active_connections"]["http_sessions"]
                        },
                        "recent_errors": len([e for e in self.server_state["errors"] 
                                            if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300]),
                        "uptime_seconds": time.time() - self.start_time
                    }
                    
                    return {
                        "success": True,
                        "comprehensive_status": enhanced_status,
                        "recommendations": recommendations,
                        "summary": {
                            "total_backends": len(status.get("backends", {})),
                            "running_backends": len([b for b in status.get("backends", {}).values() if b.get("status") == "running"]),
                            "total_daemons": len(status.get("daemons", {})),
                            "running_daemons": len([d for d in status.get("daemons", {}).values() if d.get("status") == "running"]),
                            "alerts_count": len(status.get("alerts", [])),
                            "critical_alerts": len([a for a in status.get("alerts", []) if a.get("level") == "critical"])
                        },
                        "timestamp": time.time(),
                        "observability": enhanced_status["server_observability"]
                    }
                else:
                    # Basic fallback status
                    return {
                        "success": False,
                        "error": "Comprehensive monitoring not available",
                        "fallback_status": self._get_basic_system_status(),
                        "observability": {
                            "component_status": self.server_state["component_status"],
                            "server_metrics": self.server_state["metrics"],
                            "message": "Install comprehensive backend monitor for full features"
                        }
                    }
                    
            except Exception as e:
                logger.error(f"❌ Error getting comprehensive filesystem status: {e}")
                self.server_state["errors"].append({
                    "timestamp": datetime.now().isoformat(),
                    "component": "dashboard_api",
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                
                return {
                    "success": False,
                    "error": str(e),
                    "fallback_status": self._get_basic_system_status(),
                    "observability": {
                        "component_status": self.server_state["component_status"],
                        "error_details": str(e)
                    }
                }

        @self.app.get("/dashboard/api/configs")
        async def dashboard_api_configs():
            """Returns all aggregated configuration data."""
            if self.mcp_server:
                return self.mcp_server.get_all_configs()
            return JSONResponse({"error": "MCP server not initialized"}, status_code=500)

        @self.app.get("/dashboard/api/pins")
        async def dashboard_api_pins():
            """Returns pin metadata."""
            if self.mcp_server:
                return self.mcp_server.get_pin_metadata()
            return JSONResponse({"error": "MCP server not initialized"}, status_code=500)

        @self.app.get("/dashboard/api/program_state")
        async def dashboard_api_program_state():
            """Returns program state data."""
            if self.mcp_server:
                return self.mcp_server.get_program_state_data()
            return JSONResponse({"error": "MCP server not initialized"}, status_code=500)

        @self.app.get("/dashboard/api/buckets")
        async def dashboard_api_buckets():
            """Returns bucket registry data."""
            if self.mcp_server:
                return self.mcp_server.get_bucket_registry()
            return JSONResponse({"error": "MCP server not initialized"}, status_code=500)

        @self.app.get("/dashboard/api/backend_status")
        async def dashboard_api_backend_status():
            """Returns backend status data."""
            if self.mcp_server:
                return self.mcp_server.get_backend_status_data()
            return JSONResponse({"error": "MCP server not initialized"}, status_code=500)
    
    def _setup_observability_endpoints(self):
        """Setup enhanced observability and debugging endpoints."""
        
        @self.app.get("/observability")
        async def observability_overview():
            """Complete observability overview."""
            return {
                "server_info": {
                    "service": "Unified IPFS Kit MCP Server",
                    "version": "2.0.0",
                    "start_time": self.server_state["initialization_time"],
                    "uptime_seconds": time.time() - self.start_time,
                    "host": self.host,
                    "port": self.port
                },
                "component_status": self.server_state["component_status"],
                "metrics": self.server_state["metrics"],
                "active_connections": {
                    "websocket_count": len(self.server_state["active_connections"]["websocket"]),
                    "websocket_ids": list(self.server_state["active_connections"]["websocket"]),
                    "http_sessions": self.server_state["active_connections"]["http_sessions"]
                },
                "error_summary": {
                    "total_errors": len(self.server_state["errors"]),
                    "recent_errors": len([e for e in self.server_state["errors"] 
                                        if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300]),
                    "error_by_component": self._get_error_breakdown()
                },
                "performance": self.server_state["performance"]
            }
        
        @self.app.get("/debug")
        async def debug_info():
            """Detailed debug information."""
            return {
                "server_state": self.server_state,
                "environment": {
                    "python_version": sys.version,
                    "platform": platform.platform(),
                    "working_directory": os.getcwd(),
                    "python_path": sys.path[:5],  # First 5 entries
                    "environment_vars": {k: v for k, v in os.environ.items() 
                                       if k.startswith(('IPFS', 'MCP', 'DASHBOARD'))}
                },
                "component_details": {
                    "mcp_server": {
                        "available": COMPONENT_STATUS["mcp_server"],
                        "instance": self.mcp_server is not None,
                        "tools_count": len(self.mcp_server.tools) if self.mcp_server else 0
                    },
                    "dashboard": {
                        "available": COMPONENT_STATUS["dashboard"],
                        "config": self.dashboard_config is not None,
                        "data_collector": self.dashboard_data_collector is not None,
                        "metrics_aggregator": self.dashboard_metrics_aggregator is not None
                    }
                }
            }
        
        @self.app.get("/debug/errors")
        async def debug_errors():
            """Detailed error information."""
            return {
                "total_errors": len(self.server_state["errors"]),
                "errors": self.server_state["errors"][-20:],  # Last 20 errors
                "error_breakdown": self._get_error_breakdown()
            }
        
        @self.app.post("/debug/clear-errors")
        async def clear_errors():
            """Clear error log for debugging."""
            cleared_count = len(self.server_state["errors"])
            self.server_state["errors"] = []
            return {"message": f"Cleared {cleared_count} errors"}
    
    def _get_error_breakdown(self) -> Dict[str, int]:
        """Get error breakdown by component."""
        breakdown = {}
        for error in self.server_state["errors"]:
            component = error.get("component", "unknown")
            breakdown[component] = breakdown.get(component, 0) + 1
        return breakdown
    
    def _get_basic_system_status(self) -> Dict[str, Any]:
        """Get basic system status as fallback."""
        try:
            import psutil
            
            return {
                "filesystem": {
                    "total_space_gb": 0,
                    "used_space_gb": 0, 
                    "free_space_gb": 0,
                    "usage_percent": 0
                },
                "performance": {
                    "cpu_usage_percent": psutil.cpu_percent(),
                    "memory_usage_percent": psutil.virtual_memory().percent,
                    "uptime_seconds": time.time() - self.start_time
                },
                "server_info": {
                    "component_status": self.server_state["component_status"],
                    "active_connections": len(self.server_state["active_connections"]["websocket"]),
                    "total_requests": self.server_state["metrics"]["requests_total"],
                    "error_count": len(self.server_state["errors"])
                }
            }
        except Exception as e:
            logger.error(f"❌ Error getting basic system status: {e}")
            return {"error": str(e)}
    
    def _get_enhanced_fallback_dashboard(self) -> str:
        """Enhanced fallback dashboard with full observability."""
        component_status_html = "".join([
            f'<div class="component-status {component}-{"healthy" if status else "unhealthy"}">'
            f'<strong>{component.replace("_", " ").title()}:</strong> '
            f'<span class="status-indicator">{"✓" if status else "✗"}</span>'
            f'</div>'
            for component, status in self.server_state["component_status"].items()
        ])
        
        recent_errors = [e for e in self.server_state["errors"] 
                        if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300]
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified IPFS Kit MCP Server - Full Observability Dashboard</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #2d3748; margin-bottom: 10px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .card h2 {{ margin: 0 0 15px 0; color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
        .metric {{ display: flex; justify-content: space-between; margin: 10px 0; padding: 8px; background: #f8fafc; border-radius: 6px; }}
        .metric-label {{ font-weight: 600; }}
        .metric-value {{ font-family: 'Monaco', monospace; }}
        .status-indicator {{ margin-left: 8px; }}
        .component-status {{ margin: 8px 0; padding: 8px; border-radius: 6px; }}
        .component-status.healthy {{ background: #f0fff4; border-left: 4px solid #48bb78; }}
        .component-status.unhealthy {{ background: #fff5f5; border-left: 4px solid #f56565; }}
        .refresh-btn {{ position: fixed; bottom: 20px; right: 20px; background: #4299e1; color: white; border: none; padding: 12px 20px; border-radius: 25px; cursor: pointer; }}
        .error-count {{ background: #fed7d7; color: #c53030; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }}
        .observability-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Unified IPFS Kit MCP Server</h1>
            <p>Full Observability Dashboard - Real-time monitoring and debugging</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>🏥 Server Health</h2>
                <div class="metric">
                    <span class="metric-label">Status:</span>
                    <span class="metric-value">Running</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Uptime:</span>
                    <span class="metric-value" id="uptime">{time.time() - self.start_time:.1f}s</span>
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
                    <span class="metric-value">{len(self.server_state["active_connections"]["websocket"])}</span>
                </div>
                {f'<div class="metric"><span class="metric-label">Recent Errors:</span><span class="error-count">{len(recent_errors)}</span></div>' if recent_errors else ''}
            </div>
            
            <div class="card">
                <h2>🔧 Component Status</h2>
                {component_status_html}
            </div>
            
            <div class="card">
                <h2>📊 Performance Metrics</h2>
                <div class="metric">
                    <span class="metric-label">Avg Response Time:</span>
                    <span class="metric-value">{self.server_state["metrics"]["average_response_time"]:.3f}s</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Errors/Total:</span>
                    <span class="metric-value">{self.server_state["metrics"]["requests_error"]}/{self.server_state["metrics"]["requests_total"]}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Last Request:</span>
                    <span class="metric-value">{self.server_state["metrics"]["last_request_time"] or "None"}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>🔗 Quick Links</h2>
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <a href="/observability" style="padding: 8px; background: #e2e8f0; text-decoration: none; border-radius: 4px; text-align: center;">Full Observability</a>
                    <a href="/debug" style="padding: 8px; background: #e2e8f0; text-decoration: none; border-radius: 4px; text-align: center;">Debug Info</a>
                    <a href="/metrics" style="padding: 8px; background: #e2e8f0; text-decoration: none; border-radius: 4px; text-align: center;">Metrics</a>
                    <a href="/health" style="padding: 8px; background: #e2e8f0; text-decoration: none; border-radius: 4px; text-align: center;">Health Check</a>
                    <a href="/docs" style="padding: 8px; background: #4299e1; color: white; text-decoration: none; border-radius: 4px; text-align: center;">API Documentation</a>
                </div>
            </div>
        </div>
        
        <div class="observability-grid">
            <div class="card">
                <h2>🎯 MCP Server Status</h2>
                <div id="mcp-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>📈 Backend Monitor</h2>
                <div id="backend-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>⚙️ Configurations</h2>
                <div id="config-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>📌 Pin Metadata</h2>
                <div id="pin-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>💾 Program State</h2>
                <div id="program-state-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>🗄️ Bucket Registry</h2>
                <div id="bucket-registry-status">Loading...</div>
            </div>
            
            <div class="card">
                <h2>🌐 Backend Status (New)</h2>
                <div id="backend-status-new">Loading...</div>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="window.location.reload()">🔄 Refresh</button>
    
    <script>
        // Auto-refresh data every 30 seconds
        setInterval(() => {{
            fetch('/observability')
                .then(r => r.json())
                .then(data => {{
                    document.getElementById('uptime').textContent = data.server_info.uptime_seconds.toFixed(1) + 's';
                }})
                .catch(e => console.error('Update failed:', e));
        }}, 30000);
        
        // Load MCP status
        fetch('/mcp/status')
            .then(r => r.json())
            .then(data => {{
                document.getElementById('mcp-status').innerHTML = 
                    `<div class="metric"><span class="metric-label">Tools:</span><span class="metric-value">${{data.tools_count || 0}}</span></div>
                     <div class="metric"><span class="metric-label">IPFS Kit:</span><span class="metric-value">${{data.ipfs_integration ? 'Available' : 'Unavailable'}}</span></div>`;
            }})
            .catch(e => {{
                document.getElementById('mcp-status').innerHTML = '<div style="color: #f56565;">Error loading MCP status</div>';
            }});
        
        // Load backend status (old endpoint)
        fetch('/dashboard/api/filesystem/status')
            .then(r => r.json())
            .then(data => {{
                if (data.success && data.comprehensive_status) {{
                    const backends = data.comprehensive_status.backends || {{}};
                    const running = Object.values(backends).filter(b => b.status === 'running').length;
                    document.getElementById('backend-status').innerHTML = 
                        `<div class="metric"><span class="metric-label">Backends:</span><span class="metric-value">${{Object.keys(backends).length}}</span></div>
                         <div class="metric"><span class="metric-label">Running:</span><span class="metric-value">${{running}}</span></div>
                         <div class="metric"><span class="metric-label">Alerts:</span><span class="metric-value">${{data.summary.alerts_count || 0}}</span></div>`;
                }} else {{
                    document.getElementById('backend-status').innerHTML = 
                        '<div style="color: #f56565;">Comprehensive monitoring unavailable</div>';
                }}
            }})
            .catch(e => {{
                document.getElementById('backend-status').innerHTML = '<div style="color: #f56565;">Error loading backend status</div>';
            }});

        // Load Configurations
        fetch('/dashboard/api/configs')
            .then(r => r.json())
            .then(data => {
                let html = '';
                for (const key in data) {
                    html += `<div class="metric"><span class="metric-label">${{key}}:</span><span class="metric-value">${{JSON.stringify(data[key]).substring(0, 50)}}...</span></div>`;
                }
                document.getElementById('config-status').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('config-status').innerHTML = '<div style="color: #f56565;">Error loading configs</div>';
            });

        // Load Pin Metadata
        fetch('/dashboard/api/pins')
            .then(r => r.json())
            .then(data => {
                let html = '';
                if (data.length > 0) {
                    html += `<div class="metric"><span class="metric-label">Total Pins:</span><span class="metric-value">${{data.length}}</span></div>`;
                    html += `<div class="metric"><span class="metric-label">First Pin CID:</span><span class="metric-value">${{data[0].cid.substring(0, 20)}}...</span></div>`;
                } else {
                    html += `<div class="metric"><span class="metric-label">Total Pins:</span><span class="metric-value">0</span></div>`;
                }
                document.getElementById('pin-status').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('pin-status').innerHTML = '<div style="color: #f56565;">Error loading pins</div>';
            });

        // Load Program State
        fetch('/dashboard/api/program_state')
            .then(r => r.json())
            .then(data => {
                let html = '';
                for (const key in data) {
                    html += `<div class="metric"><span class="metric-label">${{key}}:</span><span class="metric-value">${{JSON.stringify(data[key]).substring(0, 50)}}...</span></div>`;
                }
                document.getElementById('program-state-status').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('program-state-status').innerHTML = '<div style="color: #f56565;">Error loading program state</div>';
            });

        // Load Bucket Registry
        fetch('/dashboard/api/buckets')
            .then(r => r.json())
            .then(data => {
                let html = '';
                if (data.length > 0) {
                    html += `<div class="metric"><span class="metric-label">Total Buckets:</span><span class="metric-value">${{data.length}}</span></div>`;
                    html += `<div class="metric"><span class="metric-label">First Bucket:</span><span class="metric-value">${{data[0].name}}</span></div>`;
                } else {
                    html += `<div class="metric"><span class="metric-label">Total Buckets:</span><span class="metric-value">0</span></div>`;
                }
                document.getElementById('bucket-registry-status').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('bucket-registry-status').innerHTML = '<div style="color: #f56565;">Error loading buckets</div>';
            });

        // Load Backend Status (new endpoint)
        fetch('/dashboard/api/backend_status')
            .then(r => r.json())
            .then(data => {
                let html = '';
                const configuredBackends = Object.keys(data).length;
                const activeBackends = Object.values(data).filter(b => b.status === 'active').length;
                html += `<div class="metric"><span class="metric-label">Configured:</span><span class="metric-value">${{configuredBackends}}</span></div>`;
                html += `<div class="metric"><span class="metric-label">Active:</span><span class="metric-value">${{activeBackends}}</span></div>`;
                document.getElementById('backend-status-new').innerHTML = html;
            })
            .catch(e => {
                document.getElementById('backend-status-new').innerHTML = '<div style="color: #f56565;">Error loading backend status</div>';
            });
    </script>
</body>
</html>"""
    
    async def start_background_services(self):
        """Start background services for monitoring."""
        if self.dashboard_data_collector:
            try:
                await self.dashboard_data_collector.start()
                logger.info("✓ Dashboard data collector started")
            except Exception as e:
                logger.error(f"❌ Failed to start data collector: {e}")
    
    async def stop_background_services(self):
        """Stop background services."""
        if self.dashboard_data_collector:
            try:
                await self.dashboard_data_collector.stop()
                logger.info("✓ Dashboard data collector stopped")
            except Exception as e:
                logger.error(f"❌ Error stopping data collector: {e}")
    
    async def run(self):
        """Run the unified server with full observability."""
        try:
            await self.start_background_services()
            
            logger.info("🚀 Starting unified server...")
            logger.info(f"📊 Dashboard: http://{self.host}:{self.port}/dashboard")
            logger.info(f"🔌 MCP HTTP: http://{self.host}:{self.port}/mcp")
            logger.info(f"🔌 MCP WebSocket: ws://{self.host}:{self.port}/mcp/ws")
            logger.info(f"🔍 Observability: http://{self.host}:{self.port}/observability")
            logger.info(f"🐛 Debug: http://{self.host}:{self.port}/debug")
            logger.info(f"📈 Metrics: http://{self.host}:{self.port}/metrics")
            logger.info(f"💚 Health: http://{self.host}:{self.port}/health")
            logger.info(f"📚 API Docs: http://{self.host}:{self.port}/docs")
            
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            server = uvicorn.Server(config)
            await server.serve()
            
        except Exception as e:
            logger.error(f"❌ Server error: {e}")
            raise
        finally:
            await self.stop_background_services()


async def main():
    """Main entry point with argument parsing and error handling."""
    parser = argparse.ArgumentParser(description="Unified IPFS Kit MCP Server with Full Observability")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    
    args = parser.parse_args()
    
    # Check critical dependencies
    if not COMPONENT_STATUS["web_framework"]:
        logger.error("❌ Web framework not available. Install with: pip install fastapi uvicorn")
        sys.exit(1)
    
    logger.info("🚀 Initializing Unified IPFS Kit MCP Server with Full Observability")
    logger.info(f"📊 Component Status: {COMPONENT_STATUS}")
    
    # Create and run server
    server = UnifiedMCPServerWithObservability(host=args.host, port=args.port)
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server failed: {e}")
        raise


if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        logger.info("🛑 Server interrupted")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
