#!/usr/bin/env python3
"""
Integrated MCP Server with Web Dashboard
========================================

This server combines:
1. JSON-RPC MCP server functionality via HTTP/WebSocket
2. Web dashboard for monitoring and analytics
3. Real-time metrics and health endpoints
4. Enhanced IPFS Kit integration with daemon management

The server provides:
- HTTP JSON-RPC endpoint for MCP protocol communication
- WebSocket support for real-time MCP communication  
- Web dashboard interface for monitoring
- Metrics and health endpoints
- Static asset serving

All services run on the same port for unified access.
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
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("integrated-mcp-dashboard-server")

# Add current directory to Python path for imports
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Import MCP server functionality
try:
    from mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt, handle_message
    MCP_SERVER_AVAILABLE = True
    logger.info("✓ MCP server components imported successfully")
except ImportError as e:
    logger.error(f"Failed to import MCP server: {e}")
    MCP_SERVER_AVAILABLE = False

# Import dashboard components
try:
    from dashboard.config import DashboardConfig
    from dashboard.web_dashboard import WebDashboard
    from dashboard.data_collector import DataCollector
    from dashboard.metrics_aggregator import MetricsAggregator
    DASHBOARD_AVAILABLE = True
    logger.info("✓ Dashboard components imported successfully")
except ImportError as e:
    logger.error(f"Failed to import dashboard: {e}")
    DASHBOARD_AVAILABLE = False

# Web framework imports
try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    WEB_FRAMEWORK_AVAILABLE = True
    logger.info("✓ Web framework imports successful")
except ImportError as e:
    logger.error(f"Failed to import web framework: {e}")
    WEB_FRAMEWORK_AVAILABLE = False


class IntegratedMCPDashboardServer:
    """
    Integrated server combining MCP functionality with web dashboard.
    
    Provides unified access to:
    - MCP JSON-RPC API via HTTP POST and WebSocket
    - Web dashboard interface
    - Metrics and health endpoints
    - Real-time monitoring and analytics
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, dashboard_enabled: bool = True):
        """Initialize the integrated server."""
        self.host = host
        self.port = port
        self.dashboard_enabled = dashboard_enabled and DASHBOARD_AVAILABLE
        
        # Initialize FastAPI app
        self.app = FastAPI(
            title="IPFS Kit MCP Server with Dashboard",
            description="Integrated MCP server and monitoring dashboard",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Initialize MCP server
        self.mcp_server = None
        if MCP_SERVER_AVAILABLE:
            self.mcp_server = EnhancedMCPServerWithDaemonMgmt()
            logger.info("✓ MCP server initialized")
        
        # Initialize dashboard components (without FastAPI app)
        self.dashboard = None
        self.dashboard_config = None
        if self.dashboard_enabled:
            try:
                self.dashboard_config = DashboardConfig(
                    host=host,
                    port=port,
                    dashboard_path="/dashboard",
                    api_path="/dashboard/api",
                    static_path="/dashboard/static",
                    mcp_server_url=f"http://{host}:{port}",
                    ipfs_kit_url=f"http://{host}:{port}",  # Self-reference for metrics
                    debug=True
                )
                
                # Create dashboard components manually instead of WebDashboard
                from dashboard.data_collector import DataCollector
                from dashboard.metrics_aggregator import MetricsAggregator
                from dashboard.web_dashboard import WebSocketManager
                from fastapi.templating import Jinja2Templates
                
                self.dashboard_data_collector = DataCollector(self.dashboard_config)
                self.dashboard_metrics_aggregator = MetricsAggregator(self.dashboard_config, self.dashboard_data_collector)
                self.dashboard_websocket_manager = WebSocketManager()
                
                # Setup templates
                templates_dir = Path(__file__).parent.parent / "dashboard" / "templates"
                if templates_dir.exists():
                    self.dashboard_templates = Jinja2Templates(directory=str(templates_dir))
                else:
                    self.dashboard_templates = None
                    logger.warning("Dashboard templates directory not found")
                
                logger.info("✓ Dashboard components initialized")
            except Exception as e:
                logger.error(f"Failed to initialize dashboard: {e}")
                self.dashboard_enabled = False
        
        # Setup middleware and routes
        self._setup_middleware()
        self._setup_routes()
        
        # Server state
        self.websocket_connections = set()
        self.metrics_data = {
            "mcp_requests_total": 0,
            "mcp_requests_success": 0,
            "mcp_requests_error": 0,
            "server_start_time": time.time(),
            "last_request_time": None
        }
        
        logger.info(f"✓ Integrated server initialized on {host}:{port}")
    
    def _get_basic_filesystem_status(self):
        """Get basic filesystem status as fallback."""
        try:
            import os
            import psutil
            
            # Basic filesystem info
            statvfs = os.statvfs('/')
            total_space = statvfs.f_frsize * statvfs.f_blocks
            free_space = statvfs.f_frsize * statvfs.f_bavail
            used_space = total_space - free_space
            
            return {
                "filesystem": {
                    "total_space_gb": round(total_space / (1024**3), 2),
                    "free_space_gb": round(free_space / (1024**3), 2),
                    "used_space_gb": round(used_space / (1024**3), 2),
                    "usage_percent": round((used_space / total_space) * 100, 2) if total_space > 0 else 0
                },
                "performance": {
                    "cpu_usage_percent": psutil.cpu_percent(),
                    "memory_usage_percent": psutil.virtual_memory().percent
                },
                "note": "Basic fallback status - comprehensive monitoring unavailable"
            }
        except Exception as e:
            return {"error": f"Could not get basic filesystem status: {e}"}
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Setup all server routes."""
        
        # Root endpoint - redirect to dashboard or docs
        @self.app.get("/")
        async def root():
            if self.dashboard_enabled:
                return {"message": "IPFS Kit MCP Server with Dashboard", "dashboard": "/dashboard", "docs": "/docs"}
            else:
                return {"message": "IPFS Kit MCP Server", "docs": "/docs"}
        
        # MCP JSON-RPC endpoint
        @self.app.post("/mcp")
        async def mcp_jsonrpc(request: Request):
            """Handle MCP JSON-RPC requests via HTTP POST."""
            if not self.mcp_server:
                raise HTTPException(status_code=503, detail="MCP server not available")
            
            try:
                # Get JSON payload
                payload = await request.json()
                
                # Update metrics
                self.metrics_data["mcp_requests_total"] += 1
                self.metrics_data["last_request_time"] = time.time()
                
                # Handle MCP message
                response = await handle_message(self.mcp_server, payload)
                
                if response:
                    self.metrics_data["mcp_requests_success"] += 1
                    return JSONResponse(content=response)
                else:
                    self.metrics_data["mcp_requests_error"] += 1
                    raise HTTPException(status_code=500, detail="No response from MCP server")
                    
            except json.JSONDecodeError:
                self.metrics_data["mcp_requests_error"] += 1
                raise HTTPException(status_code=400, detail="Invalid JSON")
            except Exception as e:
                self.metrics_data["mcp_requests_error"] += 1
                logger.error(f"MCP request error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # MCP WebSocket endpoint
        @self.app.websocket("/mcp/ws")
        async def mcp_websocket(websocket: WebSocket):
            """Handle MCP communication via WebSocket."""
            if not self.mcp_server:
                await websocket.close(code=1011, reason="MCP server not available")
                return
            
            await websocket.accept()
            self.websocket_connections.add(websocket)
            
            try:
                while True:
                    # Receive message
                    data = await websocket.receive_text()
                    
                    try:
                        # Parse JSON-RPC message
                        message = json.loads(data)
                        
                        # Update metrics
                        self.metrics_data["mcp_requests_total"] += 1
                        self.metrics_data["last_request_time"] = time.time()
                        
                        # Handle MCP message
                        response = await handle_message(self.mcp_server, message)
                        
                        # Send response
                        if response:
                            await websocket.send_text(json.dumps(response))
                            self.metrics_data["mcp_requests_success"] += 1
                        else:
                            self.metrics_data["mcp_requests_error"] += 1
                            
                    except json.JSONDecodeError:
                        self.metrics_data["mcp_requests_error"] += 1
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"}
                        }
                        await websocket.send_text(json.dumps(error_response))
                    except Exception as e:
                        self.metrics_data["mcp_requests_error"] += 1
                        logger.error(f"WebSocket MCP error: {e}")
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32603, "message": "Internal error"}
                        }
                        await websocket.send_text(json.dumps(error_response))
                        
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_connections.discard(websocket)
        
        # Health endpoint
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            uptime = time.time() - self.metrics_data["server_start_time"]
            
            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "uptime_seconds": uptime,
                "services": {
                    "mcp_server": self.mcp_server is not None,
                    "dashboard": self.dashboard_enabled,
                    "websocket_connections": len(self.websocket_connections)
                },
                "version": "1.0.0"
            }
            
            return JSONResponse(content=health_data)
        
        # Metrics endpoint (Prometheus-style)
        @self.app.get("/metrics")
        async def metrics():
            """Metrics endpoint for monitoring."""
            uptime = time.time() - self.metrics_data["server_start_time"]
            success_rate = 0
            if self.metrics_data["mcp_requests_total"] > 0:
                success_rate = self.metrics_data["mcp_requests_success"] / self.metrics_data["mcp_requests_total"]
            
            metrics_text = f"""# HELP mcp_requests_total Total number of MCP requests
# TYPE mcp_requests_total counter
mcp_requests_total {self.metrics_data["mcp_requests_total"]}

# HELP mcp_requests_success Number of successful MCP requests
# TYPE mcp_requests_success counter
mcp_requests_success {self.metrics_data["mcp_requests_success"]}

# HELP mcp_requests_error Number of failed MCP requests
# TYPE mcp_requests_error counter
mcp_requests_error {self.metrics_data["mcp_requests_error"]}

# HELP mcp_success_rate Success rate of MCP requests
# TYPE mcp_success_rate gauge
mcp_success_rate {success_rate}

# HELP server_uptime_seconds Server uptime in seconds
# TYPE server_uptime_seconds gauge
server_uptime_seconds {uptime}

# HELP websocket_connections_active Number of active WebSocket connections
# TYPE websocket_connections_active gauge
websocket_connections_active {len(self.websocket_connections)}
"""
            
            return PlainTextResponse(content=metrics_text, media_type="text/plain")
        
        # MCP server status endpoint
        @self.app.get("/mcp/status")
        async def mcp_status():
            """Get MCP server status and capabilities."""
            if not self.mcp_server:
                raise HTTPException(status_code=503, detail="MCP server not available")
            
            # Get server info
            status_data = {
                "server_name": "IPFS Kit MCP Server",
                "version": "1.0.0",
                "available": True,
                "endpoints": {
                    "jsonrpc_http": "/mcp",
                    "websocket": "/mcp/ws",
                    "status": "/mcp/status"
                },
                "capabilities": [
                    "ipfs_operations",
                    "vfs_operations", 
                    "daemon_management",
                    "file_operations",
                    "cluster_operations"
                ],
                "metrics": self.metrics_data,
                "connections": {
                    "websocket_active": len(self.websocket_connections)
                }
            }
            
            return JSONResponse(content=status_data)
        
        # Dashboard integration (if enabled)
        if self.dashboard_enabled and self.dashboard_config:
            # Dashboard routes integration
            logger.info("Setting up dashboard routes...")
            
            try:
                # Dashboard pages
                @self.app.get(self.dashboard_config.dashboard_path, response_class=HTMLResponse)
                async def dashboard_index(request: Request):
                    # Use the new functional dashboard
                    dashboard_html_path = Path(__file__).parent.parent / "dashboard" / "templates" / "functional_dashboard.html"
                    if dashboard_html_path.exists():
                        with open(dashboard_html_path, 'r', encoding='utf-8') as f:
                            return HTMLResponse(content=f.read())
                    else:
                        return HTMLResponse(content=self._get_fallback_dashboard_html("Dashboard"))
                
                @self.app.get(f"{self.dashboard_config.dashboard_path}/metrics", response_class=HTMLResponse)
                async def dashboard_metrics_page(request: Request):
                    if self.dashboard_templates:
                        return self.dashboard_templates.TemplateResponse("metrics.html", {
                            "request": request,
                            "config": self.dashboard_config.to_dict()
                        })
                    else:
                        return HTMLResponse(content=self._get_fallback_dashboard_html("Metrics"))
                
                @self.app.get(f"{self.dashboard_config.dashboard_path}/health", response_class=HTMLResponse)
                async def dashboard_health_page(request: Request):
                    if self.dashboard_templates:
                        return self.dashboard_templates.TemplateResponse("health.html", {
                            "request": request,
                            "config": self.dashboard_config.to_dict()
                        })
                    else:
                        return HTMLResponse(content=self._get_fallback_dashboard_html("Health"))
                
                @self.app.get(f"{self.dashboard_config.dashboard_path}/vfs", response_class=HTMLResponse)
                async def dashboard_vfs_page(request: Request):
                    if self.dashboard_templates:
                        return self.dashboard_templates.TemplateResponse("vfs.html", {
                            "request": request,
                            "config": self.dashboard_config.to_dict()
                        })
                    else:
                        return HTMLResponse(content=self._get_vfs_analytics_html())
                
                # Dashboard API endpoints
                @self.app.get(f"{self.dashboard_config.api_path}/summary")
                async def dashboard_api_summary():
                    if self.dashboard_metrics_aggregator:
                        self.dashboard_metrics_aggregator.update_aggregations()
                        summary = self.dashboard_metrics_aggregator.get_dashboard_summary()
                        
                        # Add VFS deep insights if available
                        if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                            try:
                                vfs_insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                                summary['vfs_insights'] = vfs_insights
                            except Exception as e:
                                logger.error(f"Error getting VFS insights: {e}")
                                summary['vfs_insights'] = {'error': str(e)}
                        
                        return summary
                    else:
                        return {"error": "Dashboard not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/metrics")
                async def dashboard_api_metrics():
                    if self.dashboard_data_collector and self.dashboard_metrics_aggregator:
                        metrics = self.dashboard_data_collector.get_latest_values()
                        aggregated = {
                            name: metric.to_dict() 
                            for name, metric in self.dashboard_metrics_aggregator.get_aggregated_metrics().items()
                        }
                        return {
                            "latest_values": metrics,
                            "aggregated_metrics": aggregated,
                            "collection_summary": self.dashboard_data_collector.get_metric_summary(),
                            "mcp_metrics": self.metrics_data  # Include MCP-specific metrics
                        }
                    else:
                        return {"error": "Dashboard not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/health")
                async def dashboard_api_health():
                    if self.dashboard_metrics_aggregator:
                        self.dashboard_metrics_aggregator.update_aggregations()
                        health_status = self.dashboard_metrics_aggregator.get_health_status()
                        active_alerts, alert_history = self.dashboard_metrics_aggregator.get_alerts()
                        
                        return {
                            "health_status": health_status.to_dict(),
                            "active_alerts": [alert.to_dict() for alert in active_alerts],
                            "alert_history": [alert.to_dict() for alert in alert_history[-10:]]
                        }
                    else:
                        return {"error": "Dashboard not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/analytics")
                async def dashboard_api_analytics():
                    if self.dashboard_metrics_aggregator:
                        self.dashboard_metrics_aggregator.update_aggregations()
                        
                        # Get standard analytics
                        analytics = {
                            "performance_analytics": self.dashboard_metrics_aggregator.get_performance_analytics(),
                            "vfs_analytics": self.dashboard_metrics_aggregator.get_vfs_analytics(),
                            "mcp_analytics": self._get_mcp_analytics()
                        }
                        
                        # Add enhanced VFS analytics if available
                        if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                            try:
                                vfs_deep = await self.dashboard_data_collector.get_vfs_deep_insights()
                                analytics['vfs_deep_analytics'] = vfs_deep
                            except Exception as e:
                                logger.error(f"Error getting VFS deep analytics: {e}")
                                analytics['vfs_deep_analytics'] = {'error': str(e)}
                        
                        return analytics
                    else:
                        return {"error": "Dashboard not available"}
                
                # Enhanced VFS Analytics endpoints
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/health")
                async def dashboard_api_vfs_health():
                    """Get comprehensive VFS health status and alerts."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                return {
                                    "health_summary": insights.get('health_summary', {}),
                                    "alerts": insights.get('comprehensive_report', {}).get('alerts', []),
                                    "overall_health": insights.get('comprehensive_report', {}).get('overall_health', {}),
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS health: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS health analytics not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/performance")
                async def dashboard_api_vfs_performance():
                    """Get detailed VFS performance metrics and analysis."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                return {
                                    "realtime_metrics": insights.get('detailed_analyses', {}).get('realtime', {}),
                                    "bandwidth_analysis": insights.get('detailed_analyses', {}).get('bandwidth', {}),
                                    "operation_analysis": insights.get('detailed_analyses', {}).get('operations', {}),
                                    "trends": insights.get('trends', {}),
                                    "insights": insights.get('insights', []),
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS performance: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS performance analytics not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/recommendations")
                async def dashboard_api_vfs_recommendations():
                    """Get VFS optimization recommendations."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                return {
                                    "recommendations": insights.get('recommendations', []),
                                    "insights": insights.get('insights', []),
                                    "priority_actions": [
                                        rec for rec in insights.get('recommendations', [])
                                        if rec.get('priority') in ['critical', 'high']
                                    ],
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS recommendations: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS recommendations not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/backends")
                async def dashboard_api_vfs_backends():
                    """Get VFS backend health and performance details."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                backend_data = insights.get('detailed_analyses', {}).get('backends', {})
                                return {
                                    "backend_health": backend_data,
                                    "summary": backend_data.get('summary', {}),
                                    "individual_backends": backend_data.get('backends', {}),
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS backends: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS backend analytics not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/replication")
                async def dashboard_api_vfs_replication():
                    """Get VFS replication health and status."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                replication_data = insights.get('detailed_analyses', {}).get('replication', {})
                                return {
                                    "replication_health": replication_data,
                                    "current_status": replication_data.get('current_status', {}),
                                    "trends": replication_data.get('trends', {}),
                                    "alerts": replication_data.get('alerts', []),
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS replication: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS replication analytics not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/cache")
                async def dashboard_api_vfs_cache():
                    """Get VFS cache performance and efficiency metrics."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                cache_data = insights.get('detailed_analyses', {}).get('cache', {})
                                return {
                                    "cache_analysis": cache_data,
                                    "current_metrics": cache_data.get('current_metrics', {}),
                                    "historical_averages": cache_data.get('historical_averages', {}),
                                    "alerts": cache_data.get('alerts', []),
                                    "timestamp": time.time()
                                }
                        except Exception as e:
                            logger.error(f"Error getting VFS cache: {e}")
                            return {"error": str(e)}
                    
                    return {"available": False, "error": "VFS cache analytics not available"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/vfs/analytics")
                async def dashboard_api_vfs_analytics():
                    """Get comprehensive VFS analytics - the main endpoint for all VFS data."""
                    if hasattr(self.dashboard_data_collector, 'get_vfs_deep_insights'):
                        try:
                            insights = await self.dashboard_data_collector.get_vfs_deep_insights()
                            if insights.get('available'):
                                return {
                                    "available": True,
                                    "comprehensive_report": insights.get('comprehensive_report', {}),
                                    "detailed_analyses": insights.get('detailed_analyses', {}),
                                    "health_summary": insights.get('health_summary', {}),
                                    "trends": insights.get('trends', {}),
                                    "insights": insights.get('insights', []),
                                    "recommendations": insights.get('recommendations', []),
                                    "timestamp": time.time()
                                }
                            else:
                                return {"available": False, "message": "VFS analytics not available"}
                        except Exception as e:
                            logger.error(f"Error getting VFS analytics: {e}")
                            return {"available": False, "error": str(e)}
                    
                    return {"available": False, "error": "VFS analytics not available - data collector missing method"}
                
                @self.app.get(f"{self.dashboard_config.api_path}/filesystem/status")
                async def dashboard_api_filesystem_status_comprehensive():
                    """Get comprehensive filesystem and backend status."""
                    try:
                        # Import the comprehensive backend monitor
                        from dashboard.comprehensive_backend_monitor import get_comprehensive_backend_status, get_backend_recommendations
                        
                        # Get comprehensive status
                        status = await get_comprehensive_backend_status()
                        recommendations = await get_backend_recommendations()
                        
                        return {
                            "success": True,
                            "comprehensive_status": status,
                            "recommendations": recommendations,
                            "summary": {
                                "total_backends": len(status.get("backends", {})),
                                "running_backends": len([b for b in status.get("backends", {}).values() if b.get("status") == "running"]),
                                "total_daemons": len(status.get("daemons", {})),
                                "running_daemons": len([d for d in status.get("daemons", {}).values() if d.get("status") == "running"]),
                                "alerts_count": len(status.get("alerts", [])),
                                "critical_alerts": len([a for a in status.get("alerts", []) if a.get("level") == "critical"])
                            },
                            "timestamp": time.time()
                        }
                    except Exception as e:
                        logger.error(f"Error getting comprehensive filesystem status: {e}")
                        # Return fallback status  
                        fallback_status = self._get_basic_filesystem_status()
                        return {
                            "success": False,
                            "error": str(e),
                            "fallback_status": fallback_status,
                            "timestamp": time.time()
                        }
                
                @self.app.post(f"{self.dashboard_config.api_path}/alerts/{{alert_id}}/acknowledge")
                async def dashboard_api_acknowledge_alert(alert_id: str):
                    if self.dashboard_metrics_aggregator:
                        success = self.dashboard_metrics_aggregator.acknowledge_alert(alert_id)
                        if success:
                            return {"status": "acknowledged", "alert_id": alert_id}
                        else:
                            raise HTTPException(status_code=404, detail="Alert not found")
                    else:
                        raise HTTPException(status_code=503, detail="Dashboard not available")
                
                # Dashboard WebSocket
                @self.app.websocket(f"{self.dashboard_config.dashboard_path}/ws")
                async def dashboard_websocket(websocket: WebSocket):
                    if self.dashboard_websocket_manager:
                        await self.dashboard_websocket_manager.connect(websocket)
                        
                        try:
                            # Send initial data
                            await self._send_dashboard_websocket_update(websocket)
                            
                            # Keep connection alive
                            while True:
                                try:
                                    data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                                    
                                    # Handle client requests
                                    if data == "get_update":
                                        await self._send_dashboard_websocket_update(websocket)
                                    
                                except asyncio.TimeoutError:
                                    # Send periodic update
                                    await self._send_dashboard_websocket_update(websocket)
                            
                        except WebSocketDisconnect:
                            self.dashboard_websocket_manager.disconnect(websocket)
                        except Exception as e:
                            logger.error(f"Dashboard WebSocket error: {e}")
                            self.dashboard_websocket_manager.disconnect(websocket)
                    else:
                        await websocket.close(code=1011, reason="Dashboard not available")
                
                # Mount static files
                static_dir = Path(__file__).parent.parent / "dashboard" / "static"
                if static_dir.exists():
                    self.app.mount(
                        self.dashboard_config.static_path,
                        StaticFiles(directory=str(static_dir)),
                        name="dashboard_static"
                    )
                
                logger.info("✓ Dashboard routes integrated successfully")
                
            except Exception as e:
                logger.error(f"Failed to setup dashboard routes: {e}")
                self.dashboard_enabled = False
    
    async def start_background_services(self):
        """Start background services like dashboard data collection."""
        if self.dashboard_enabled and self.dashboard_data_collector:
            try:
                # Start dashboard background services
                await self.dashboard_data_collector.start()
                
                # Start metrics update task
                asyncio.create_task(self._metrics_update_loop())
                
                logger.info("✓ Background services started")
            except Exception as e:
                logger.error(f"Failed to start background services: {e}")
    
    async def stop_background_services(self):
        """Stop background services."""
        if self.dashboard_enabled and self.dashboard_data_collector:
            try:
                await self.dashboard_data_collector.stop()
                logger.info("✓ Background services stopped")
            except Exception as e:
                logger.error(f"Error stopping background services: {e}")
    
    def _get_fallback_dashboard_html(self, page_title: str) -> str:
        """Get fallback HTML when templates are not available."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Dashboard - {page_title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 2rem; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .card {{ background: #f5f5f5; padding: 1rem; margin: 1rem 0; border-radius: 8px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .metric {{ background: white; padding: 1rem; border-radius: 4px; text-align: center; }}
        .metric-value {{ font-size: 2rem; font-weight: bold; color: #2563eb; }}
        .metric-label {{ color: #6b7280; }}
        nav {{ margin-bottom: 2rem; }}
        nav a {{ margin-right: 1rem; padding: 0.5rem 1rem; background: #2563eb; color: white; text-decoration: none; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IPFS Kit Dashboard - {page_title}</h1>
        <nav>
            <a href="/dashboard">Overview</a>
            <a href="/dashboard/metrics">Metrics</a>
            <a href="/dashboard/health">Health</a>
            <a href="/dashboard/vfs">VFS Analytics</a>
            <a href="/docs">API Docs</a>
        </nav>
        
        <div class="card">
            <h2>Dashboard Information</h2>
            <p>The dashboard is running in fallback mode. Templates are not available.</p>
            <p>API endpoints are still functional:</p>
            <ul>
                <li><a href="/dashboard/api/summary">Summary Data</a></li>
                <li><a href="/dashboard/api/metrics">Metrics Data</a></li>
                <li><a href="/dashboard/api/health">Health Status</a></li>
                <li><a href="/health">Server Health</a></li>
                <li><a href="/metrics">Prometheus Metrics</a></li>
            </ul>
        </div>
        
        <div class="card">
            <h2>MCP Server Status</h2>
            <div class="metrics">
                <div class="metric">
                    <div class="metric-value" id="total-requests">--</div>
                    <div class="metric-label">Total Requests</div>
                </div>
                <div class="metric">
                    <div class="metric-value" id="success-rate">--%</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="metric">
                    <div class="metric-value" id="active-connections">--</div>
                    <div class="metric-label">Active Connections</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Quick Actions</h2>
            <p>
                <a href="/mcp/status">MCP Server Status</a> | 
                <a href="/health">Health Check</a> | 
                <a href="/metrics">Prometheus Metrics</a>
            </p>
        </div>
    </div>
    
    <script>
        // Simple metrics update
        async function updateMetrics() {{
            try {{
                const response = await fetch('/mcp/status');
                const data = await response.json();
                
                document.getElementById('total-requests').textContent = data.metrics.mcp_requests_total || 0;
                
                const successRate = data.metrics.mcp_requests_total > 0 
                    ? Math.round((data.metrics.mcp_requests_success / data.metrics.mcp_requests_total) * 100)
                    : 0;
                document.getElementById('success-rate').textContent = successRate + '%';
                
                document.getElementById('active-connections').textContent = data.connections.websocket_active || 0;
            }} catch (e) {{
                console.error('Failed to update metrics:', e);
            }}
        }}
        
        // Update metrics every 5 seconds
        updateMetrics();
        setInterval(updateMetrics, 5000);
    </script>
</body>
</html>"""
    
    def _get_vfs_analytics_html(self) -> str:
        """Get enhanced VFS analytics HTML page."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Dashboard - VFS Analytics</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; background: #f8fafc; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .header { background: white; padding: 1.5rem; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .nav { display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
        .nav a { padding: 0.5rem 1rem; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px; font-weight: 500; }
        .nav a:hover { background: #2563eb; }
        .nav a.active { background: #1d4ed8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .card h3 { margin: 0 0 1rem 0; color: #1f2937; font-size: 1.125rem; }
        .metric { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid #e5e7eb; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #6b7280; font-weight: 500; }
        .metric-value { font-weight: 600; color: #1f2937; }
        .status-healthy { color: #059669; }
        .status-warning { color: #d97706; }
        .status-critical { color: #dc2626; }
        .alert { padding: 1rem; border-radius: 8px; margin: 0.5rem 0; }
        .alert-info { background: #dbeafe; border-left: 4px solid #3b82f6; }
        .alert-warning { background: #fef3c7; border-left: 4px solid #f59e0b; }
        .alert-critical { background: #fee2e2; border-left: 4px solid #ef4444; }
        .loading { text-align: center; padding: 2rem; color: #6b7280; }
        .error { color: #dc2626; padding: 1rem; background: #fee2e2; border-radius: 8px; }
        .chart-placeholder { height: 200px; background: #f3f4f6; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #6b7280; }
        .recommendations { margin-top: 1rem; }
        .recommendation { background: #f8fafc; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #3b82f6; }
        .recommendation-title { font-weight: 600; color: #1f2937; margin-bottom: 0.5rem; }
        .recommendation-desc { color: #6b7280; font-size: 0.875rem; }
        .health-score { text-align: center; margin: 1rem 0; }
        .health-score-value { font-size: 3rem; font-weight: bold; margin: 0.5rem 0; }
        .health-grade { font-size: 1.5rem; font-weight: 600; }
        .tabs { display: flex; border-bottom: 2px solid #e5e7eb; margin-bottom: 1rem; }
        .tab { padding: 0.75rem 1.5rem; background: none; border: none; cursor: pointer; font-weight: 500; color: #6b7280; }
        .tab.active { color: #3b82f6; border-bottom: 2px solid #3b82f6; margin-bottom: -2px; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🗂️ Virtual Filesystem Analytics</h1>
            <div class="nav">
                <a href="/dashboard">Overview</a>
                <a href="/dashboard/metrics">Metrics</a>
                <a href="/dashboard/health">Health</a>
                <a href="/dashboard/vfs" class="active">VFS Analytics</a>
                <a href="/docs">API Docs</a>
            </div>
        </div>

        <div id="loading" class="loading">
            <div>🔄 Loading VFS analytics...</div>
        </div>

        <div id="error" class="error" style="display: none;"></div>

        <div id="content" style="display: none;">
            <!-- Health Score Section -->
            <div class="card">
                <h3>📊 Overall VFS Health</h3>
                <div class="health-score">
                    <div id="health-score" class="health-score-value status-healthy">--</div>
                    <div id="health-grade" class="health-grade">--</div>
                    <div id="health-status">--</div>
                </div>
            </div>

            <!-- Tabs for different analytics sections -->
            <div class="card">
                <div class="tabs">
                    <button class="tab active" onclick="showTab('overview')">Overview</button>
                    <button class="tab" onclick="showTab('performance')">Performance</button>
                    <button class="tab" onclick="showTab('replication')">Replication</button>
                    <button class="tab" onclick="showTab('cache')">Cache</button>
                    <button class="tab" onclick="showTab('backends')">Backends</button>
                    <button class="tab" onclick="showTab('recommendations')">Recommendations</button>
                </div>

                <!-- Overview Tab -->
                <div id="overview-tab" class="tab-content active">
                    <div class="grid">
                        <div>
                            <h4>Real-time Metrics</h4>
                            <div class="metric">
                                <span class="metric-label">Operations per Second</span>
                                <span id="ops-per-sec" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Error Rate</span>
                                <span id="error-rate" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Total Operations</span>
                                <span id="total-ops" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Bandwidth (MB/s)</span>
                                <span id="bandwidth" class="metric-value">--</span>
                            </div>
                        </div>
                        <div>
                            <h4>System Status</h4>
                            <div class="metric">
                                <span class="metric-label">Healthy Backends</span>
                                <span id="healthy-backends" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Cache Hit Rate</span>
                                <span id="cache-hit-rate" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Replication Health</span>
                                <span id="replication-health" class="metric-value">--</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">Active Alerts</span>
                                <span id="active-alerts" class="metric-value">--</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Performance Tab -->
                <div id="performance-tab" class="tab-content">
                    <div class="grid">
                        <div>
                            <h4>Bandwidth Analysis</h4>
                            <div id="bandwidth-chart" class="chart-placeholder">Bandwidth chart will appear here</div>
                        </div>
                        <div>
                            <h4>Operation Analysis</h4>
                            <div id="operations-chart" class="chart-placeholder">Operations chart will appear here</div>
                        </div>
                    </div>
                    <div id="performance-metrics"></div>
                </div>

                <!-- Replication Tab -->
                <div id="replication-tab" class="tab-content">
                    <div id="replication-metrics"></div>
                </div>

                <!-- Cache Tab -->
                <div id="cache-tab" class="tab-content">
                    <div id="cache-metrics"></div>
                </div>

                <!-- Backends Tab -->
                <div id="backends-tab" class="tab-content">
                    <div id="backend-status"></div>
                </div>

                <!-- Recommendations Tab -->
                <div id="recommendations-tab" class="tab-content">
                    <div id="recommendations-list"></div>
                </div>
            </div>

            <!-- Alerts Section -->
            <div class="card">
                <h3>🚨 Active Alerts</h3>
                <div id="alerts-list">No alerts</div>
            </div>
        </div>
    </div>

    <script>
        let currentData = null;

        function showTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }

        async function loadVFSAnalytics() {
            try {
                const response = await fetch('/dashboard/api/vfs/analytics');
                const data = await response.json();
                
                if (data.error) {
                    showError(data.error);
                    return;
                }
                
                if (!data.available) {
                    showError('VFS analytics not available');
                    return;
                }
                
                currentData = data;
                updateDisplay(data);
                
                document.getElementById('loading').style.display = 'none';
                document.getElementById('content').style.display = 'block';
                
            } catch (error) {
                showError('Failed to load VFS analytics: ' + error.message);
            }
        }

        function showError(message) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('error').style.display = 'block';
            document.getElementById('error').textContent = message;
        }

        function updateDisplay(data) {
            // Update health score
            const healthSummary = data.health_summary || {};
            const overallHealth = healthSummary.overall || {};
            
            const healthScore = overallHealth.score || 0;
            const healthGrade = overallHealth.grade || 'F';
            const healthStatus = overallHealth.status || 'unknown';
            
            document.getElementById('health-score').textContent = Math.round(healthScore);
            document.getElementById('health-grade').textContent = healthGrade;
            document.getElementById('health-status').textContent = healthStatus;
            
            // Set health score color
            const scoreElement = document.getElementById('health-score');
            scoreElement.className = 'health-score-value ' + getHealthClass(healthStatus);
            
            // Update overview metrics
            const realtime = data.detailed_analyses?.realtime || {};
            const backends = data.detailed_analyses?.backends || {};
            const cache = data.detailed_analyses?.cache || {};
            const replication = data.detailed_analyses?.replication || {};
            
            document.getElementById('ops-per-sec').textContent = (realtime.operations_per_second || 0).toFixed(1);
            document.getElementById('error-rate').textContent = ((realtime.error_rate || 0) * 100).toFixed(1) + '%';
            document.getElementById('total-ops').textContent = realtime.total_operations || 0;
            document.getElementById('bandwidth').textContent = ((realtime.bytes_per_second || 0) / (1024*1024)).toFixed(2);
            
            const backendSummary = backends.summary || {};
            document.getElementById('healthy-backends').textContent = 
                (backendSummary.healthy_backends || 0) + '/' + (backendSummary.total_backends || 0);
            
            const cacheMetrics = cache.current_metrics || {};
            document.getElementById('cache-hit-rate').textContent = ((cacheMetrics.hit_rate || 0) * 100).toFixed(1) + '%';
            
            const replicationStatus = replication.current_status || {};
            document.getElementById('replication-health').textContent = (replicationStatus.health_percentage || 0).toFixed(1) + '%';
            
            const alerts = data.comprehensive_report?.alerts || [];
            document.getElementById('active-alerts').textContent = alerts.length;
            
            // Update detailed sections
            updatePerformanceTab(data);
            updateReplicationTab(data);
            updateCacheTab(data);
            updateBackendsTab(data);
            updateRecommendationsTab(data);
            updateAlertsSection(data);
        }

        function getHealthClass(status) {
            switch (status) {
                case 'healthy': return 'status-healthy';
                case 'warning': return 'status-warning';
                case 'critical': return 'status-critical';
                default: return 'status-warning';
            }
        }

        function updatePerformanceTab(data) {
            const bandwidth = data.detailed_analyses?.bandwidth || {};
            const operations = data.detailed_analyses?.operations || {};
            
            let html = '<div class="grid">';
            
            // Bandwidth details
            if (bandwidth.interfaces) {
                html += '<div><h4>Bandwidth by Interface</h4>';
                for (const [interface, stats] of Object.entries(bandwidth.interfaces)) {
                    html += `<div class="metric">
                        <span class="metric-label">${interface}</span>
                        <span class="metric-value">${((stats.average_in_bps + stats.average_out_bps) / (1024*1024)).toFixed(2)} MB/s</span>
                    </div>`;
                }
                html += '</div>';
            }
            
            // Operation details
            if (operations.operations_by_type) {
                html += '<div><h4>Operations by Type</h4>';
                for (const [opType, stats] of Object.entries(operations.operations_by_type)) {
                    const [operation, backend] = opType.split(':');
                    html += `<div class="metric">
                        <span class="metric-label">${operation} (${backend})</span>
                        <span class="metric-value">${stats.total_operations} ops (${(stats.success_rate * 100).toFixed(1)}% success)</span>
                    </div>`;
                }
                html += '</div>';
            }
            
            html += '</div>';
            document.getElementById('performance-metrics').innerHTML = html;
        }

        function updateReplicationTab(data) {
            const replication = data.detailed_analyses?.replication || {};
            const status = replication.current_status || {};
            
            let html = '<div class="grid"><div><h4>Replication Status</h4>';
            html += `<div class="metric"><span class="metric-label">Total Replicas</span><span class="metric-value">${status.total_replicas || 0}</span></div>`;
            html += `<div class="metric"><span class="metric-label">Healthy Replicas</span><span class="metric-value">${status.healthy_replicas || 0}</span></div>`;
            html += `<div class="metric"><span class="metric-label">Health Percentage</span><span class="metric-value">${(status.health_percentage || 0).toFixed(1)}%</span></div>`;
            html += `<div class="metric"><span class="metric-label">Sync Lag</span><span class="metric-value">${(status.sync_lag_seconds || 0).toFixed(1)}s</span></div>`;
            html += `<div class="metric"><span class="metric-label">Pending Operations</span><span class="metric-value">${status.pending_operations || 0}</span></div>`;
            html += `<div class="metric"><span class="metric-label">Failed Operations</span><span class="metric-value">${status.failed_operations || 0}</span></div>`;
            html += '</div></div>';
            
            document.getElementById('replication-metrics').innerHTML = html;
        }

        function updateCacheTab(data) {
            const cache = data.detailed_analyses?.cache || {};
            const metrics = cache.current_metrics || {};
            const historical = cache.historical_averages || {};
            
            let html = '<div class="grid">';
            html += '<div><h4>Current Cache Metrics</h4>';
            html += `<div class="metric"><span class="metric-label">Hit Rate</span><span class="metric-value">${(metrics.hit_rate * 100 || 0).toFixed(1)}%</span></div>`;
            html += `<div class="metric"><span class="metric-label">Miss Rate</span><span class="metric-value">${(metrics.miss_rate * 100 || 0).toFixed(1)}%</span></div>`;
            html += `<div class="metric"><span class="metric-label">Utilization</span><span class="metric-value">${(metrics.utilization * 100 || 0).toFixed(1)}%</span></div>`;
            html += `<div class="metric"><span class="metric-label">Size</span><span class="metric-value">${formatBytes(metrics.size_bytes || 0)}</span></div>`;
            html += `<div class="metric"><span class="metric-label">Avg Lookup Time</span><span class="metric-value">${(metrics.avg_lookup_time_ms || 0).toFixed(1)}ms</span></div>`;
            html += '</div>';
            
            if (Object.keys(historical).length > 0) {
                html += '<div><h4>Historical Averages</h4>';
                html += `<div class="metric"><span class="metric-label">Avg Hit Rate</span><span class="metric-value">${(historical.avg_hit_rate * 100 || 0).toFixed(1)}%</span></div>`;
                html += `<div class="metric"><span class="metric-label">Avg Lookup Time</span><span class="metric-value">${(historical.avg_lookup_time_ms || 0).toFixed(1)}ms</span></div>`;
                html += '</div>';
            }
            
            html += '</div>';
            document.getElementById('cache-metrics').innerHTML = html;
        }

        function updateBackendsTab(data) {
            const backends = data.detailed_analyses?.backends || {};
            const backendList = backends.backends || {};
            
            let html = '<div class="grid">';
            
            for (const [backendName, status] of Object.entries(backendList)) {
                const healthClass = status.healthy ? 'status-healthy' : 'status-critical';
                html += `<div class="card">
                    <h4>${backendName} <span class="${healthClass}">${status.healthy ? '✅' : '❌'}</span></h4>
                    <div class="metric"><span class="metric-label">Status</span><span class="metric-value">${status.healthy ? 'Healthy' : 'Unhealthy'}</span></div>
                    <div class="metric"><span class="metric-label">Last Check</span><span class="metric-value">${(status.last_check_age_seconds || 0).toFixed(0)}s ago</span></div>`;
                
                if (status.average_latency_ms !== null) {
                    html += `<div class="metric"><span class="metric-label">Avg Latency</span><span class="metric-value">${status.average_latency_ms.toFixed(1)}ms</span></div>`;
                }
                if (status.p95_latency_ms !== null) {
                    html += `<div class="metric"><span class="metric-label">P95 Latency</span><span class="metric-value">${status.p95_latency_ms.toFixed(1)}ms</span></div>`;
                }
                
                html += `<div class="metric"><span class="metric-label">Samples</span><span class="metric-value">${status.latency_samples || 0}</span></div>`;
                html += '</div>';
            }
            
            html += '</div>';
            document.getElementById('backend-status').innerHTML = html;
        }

        function updateRecommendationsTab(data) {
            const recommendations = data.recommendations || [];
            
            let html = '';
            if (recommendations.length === 0) {
                html = '<div class="metric">No recommendations available</div>';
            } else {
                recommendations.forEach(rec => {
                    const priorityClass = rec.priority === 'critical' ? 'alert-critical' : 
                                        rec.priority === 'high' ? 'alert-warning' : 'alert-info';
                    
                    html += `<div class="recommendation ${priorityClass}">
                        <div class="recommendation-title">${rec.title} (${rec.priority})</div>
                        <div class="recommendation-desc">${rec.description}</div>
                        <div style="margin-top: 0.5rem; font-size: 0.875rem;">
                            <strong>Category:</strong> ${rec.category}<br>
                            <strong>Expected Impact:</strong> ${rec.expected_impact}
                        </div>
                    </div>`;
                });
            }
            
            document.getElementById('recommendations-list').innerHTML = html;
        }

        function updateAlertsSection(data) {
            const alerts = data.comprehensive_report?.alerts || [];
            
            let html = '';
            if (alerts.length === 0) {
                html = '<div class="metric">No active alerts</div>';
            } else {
                alerts.forEach(alert => {
                    const alertClass = `alert-${alert.severity}`;
                    html += `<div class="alert ${alertClass}">
                        <strong>${alert.type}:</strong> ${alert.message}
                    </div>`;
                });
            }
            
            document.getElementById('alerts-list').innerHTML = html;
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        // Load data on page load
        loadVFSAnalytics();
        
        // Refresh data every 10 seconds
        setInterval(loadVFSAnalytics, 10000);
    </script>
</body>
</html>"""
    
    def _get_mcp_analytics(self) -> Dict[str, Any]:
        """Get MCP-specific analytics."""
        uptime = time.time() - self.metrics_data["server_start_time"]
        total_requests = self.metrics_data["mcp_requests_total"]
        success_requests = self.metrics_data["mcp_requests_success"]
        error_requests = self.metrics_data["mcp_requests_error"]
        
        success_rate = 0
        if total_requests > 0:
            success_rate = success_requests / total_requests
        
        requests_per_second = 0
        if uptime > 0:
            requests_per_second = total_requests / uptime
        
        return {
            "total_operations": total_requests,
            "success_operations": success_requests,
            "error_operations": error_requests,
            "success_rate": success_rate,
            "requests_per_second": requests_per_second,
            "uptime_seconds": uptime,
            "active_websocket_connections": len(self.websocket_connections),
            "last_request_time": self.metrics_data["last_request_time"],
            "server_start_time": self.metrics_data["server_start_time"]
        }
    
    async def _send_dashboard_websocket_update(self, websocket: WebSocket):
        """Send update data to a dashboard WebSocket."""
        try:
            if self.dashboard:
                self.dashboard.metrics_aggregator.update_aggregations()
                data = {
                    "timestamp": time.time(),
                    "summary": self.dashboard.metrics_aggregator.get_dashboard_summary(),
                    "latest_metrics": self.dashboard.data_collector.get_latest_values(),
                    "mcp_metrics": self.metrics_data,
                    "mcp_analytics": self._get_mcp_analytics()
                }
                await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.debug(f"Failed to send dashboard WebSocket update: {e}")
    
    async def _metrics_update_loop(self):
        """Background task to update metrics and dashboard."""
        try:
            while True:
                # Update dashboard metrics if available
                if self.dashboard_enabled and self.dashboard_metrics_aggregator:
                    self.dashboard_metrics_aggregator.update_aggregations()
                    
                    # Broadcast updates to dashboard WebSocket clients
                    if self.dashboard_websocket_manager:
                        summary = self.dashboard_metrics_aggregator.get_dashboard_summary()
                        await self.dashboard_websocket_manager.broadcast({
                            "timestamp": time.time(),
                            "summary": summary,
                            "mcp_metrics": self.metrics_data,
                            "mcp_analytics": self._get_mcp_analytics()
                        })
                
                # Wait for next update
                await asyncio.sleep(5)  # Update every 5 seconds
                
        except asyncio.CancelledError:
            logger.info("Metrics update loop cancelled")
        except Exception as e:
            logger.error(f"Error in metrics update loop: {e}")
    
    async def run(self):
        """Run the integrated server."""
        logger.info(f"Starting integrated MCP server with dashboard on {self.host}:{self.port}")
        
        # Start background services
        await self.start_background_services()
        
        try:
            # Configure uvicorn
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            
            server = uvicorn.Server(config)
            
            logger.info("🚀 Server starting...")
            logger.info(f"📊 Dashboard: http://{self.host}:{self.port}/dashboard")
            logger.info(f"🔌 MCP HTTP: http://{self.host}:{self.port}/mcp")
            logger.info(f"🔌 MCP WebSocket: ws://{self.host}:{self.port}/mcp/ws")
            logger.info(f"📈 Metrics: http://{self.host}:{self.port}/metrics")
            logger.info(f"💚 Health: http://{self.host}:{self.port}/health")
            logger.info(f"📚 API Docs: http://{self.host}:{self.port}/docs")
            
            await server.serve()
            
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            await self.stop_background_services()


def create_integrated_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    dashboard_enabled: bool = True
) -> IntegratedMCPDashboardServer:
    """Create an integrated MCP server with dashboard."""
    return IntegratedMCPDashboardServer(
        host=host,
        port=port,
        dashboard_enabled=dashboard_enabled
    )


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated MCP Server with Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--no-dashboard", action="store_true", help="Disable dashboard")
    
    args = parser.parse_args()
    
    # Check dependencies
    if not WEB_FRAMEWORK_AVAILABLE:
        logger.error("FastAPI and uvicorn are required. Install with: pip install fastapi uvicorn")
        return 1
    
    if not MCP_SERVER_AVAILABLE:
        logger.error("MCP server components not available")
        return 1
    
    # Create and run server
    server = create_integrated_server(
        host=args.host,
        port=args.port,
        dashboard_enabled=not args.no_dashboard
    )
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Server failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
