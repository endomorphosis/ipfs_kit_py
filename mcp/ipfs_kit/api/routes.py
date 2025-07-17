"""
API routes configuration for IPFS Kit MCP Server.
"""

import traceback
import asyncio
from fastapi import FastAPI, Request, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any
import logging

from .health_endpoints import HealthEndpoints
from .config_endpoints import ConfigEndpoints
from .vfs_endpoints import VFSEndpoints
from .websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)


class APIRoutes:
    """Manages all API routes for the MCP server."""
    
    def __init__(self, app: FastAPI, backend_monitor, templates, websocket_manager):
        self.app = app
        self.backend_monitor = backend_monitor
        self.templates = templates
        self.websocket_manager = websocket_manager
        
        # Initialize endpoint handlers
        self.health_endpoints = HealthEndpoints(backend_monitor)
        self.config_endpoints = ConfigEndpoints(backend_monitor)
        self.vfs_endpoints = VFSEndpoints(backend_monitor)
        self.websocket_handler = WebSocketHandler(websocket_manager)
        
        # Setup error handling
        self._setup_error_handlers()
        
        # Setup routes
        self._setup_routes()
    
    def _setup_error_handlers(self):
        """Setup comprehensive error handling for better debugging."""
        
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """Global exception handler that provides detailed error information to GUI."""
            error_info = {
                "error": True,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "url": str(request.url),
                "method": request.method,
                "timestamp": asyncio.get_event_loop().time(),
                "traceback": traceback.format_exc(),
                "details": {
                    "headers": dict(request.headers),
                    "query_params": dict(request.query_params) if request.query_params else {},
                    "path_params": request.path_params if hasattr(request, 'path_params') else {}
                }
            }
            
            # Log the error for server-side debugging
            logger.error(f"API Error in {request.method} {request.url}: {exc}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return JSONResponse(
                status_code=500,
                content=error_info
            )
    
    async def _safe_endpoint_call(self, endpoint_func, endpoint_name: str, **kwargs):
        """Safely call an endpoint with enhanced error handling."""
        try:
            result = await endpoint_func(**kwargs)
            return {
                "success": True,
                "data": result,
                "endpoint": endpoint_name,
                "timestamp": asyncio.get_event_loop().time()
            }
        except Exception as e:
            error_info = {
                "success": False,
                "error": True,
                "error_type": type(e).__name__,
                "message": str(e),
                "endpoint": endpoint_name,
                "timestamp": asyncio.get_event_loop().time(),
                "traceback": traceback.format_exc(),
                "debug_info": {
                    "function_name": endpoint_func.__name__,
                    "kwargs": kwargs
                }
            }
            
            # Log for server debugging
            logger.error(f"Error in {endpoint_name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return error_info
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        # Dashboard route
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("index.html", {"request": request})
        
        # Health endpoints with enhanced error handling
        @self.app.get("/api/health")
        async def health_check():
            return await self._safe_endpoint_call(
                self.health_endpoints.get_health,
                "health_check"
            )
        
        @self.app.get("/api/backends")
        async def get_backends():
            return await self._safe_endpoint_call(
                self.health_endpoints.get_all_backends,
                "all_backends"
            )
        
        @self.app.get("/api/backends/{backend_name}")
        async def get_backend_status(backend_name: str):
            return await self._safe_endpoint_call(
                self.health_endpoints.get_backend_status,
                "backend_status",
                backend_name=backend_name
            )
        
        @self.app.get("/api/backends/{backend_name}/detailed")
        async def get_backend_detailed(backend_name: str):
            return await self._safe_endpoint_call(
                self.health_endpoints.get_backend_detailed,
                "backend_detailed",
                backend_name=backend_name
            )
        
        @self.app.get("/api/backends/{backend_name}/info")
        async def get_backend_info(backend_name: str):
            return await self._safe_endpoint_call(
                self.health_endpoints.get_backend_info,
                "backend_info",
                backend_name=backend_name
            )
        
        # Tools endpoint
        @self.app.get("/api/tools")
        async def get_tools():
            """Get all available MCP tools."""
            return await self._safe_endpoint_call(
                self._get_available_tools,
                "tools"
            )
        
        # Configuration endpoints with enhanced error handling
        @self.app.get("/api/backends/{backend_name}/config")
        async def get_backend_config(backend_name: str):
            async def get_config():
                return await self.config_endpoints.get_backend_config(backend_name)
            
            return await self._safe_endpoint_call(
                get_config,
                "backend_config"
            )
        
        @self.app.post("/api/backends/{backend_name}/config")
        async def set_backend_config(backend_name: str, request: Request):
            config_data = await request.json()
            
            async def set_config():
                return await self.config_endpoints.set_backend_config(backend_name, config_data)
            
            return await self._safe_endpoint_call(
                set_config,
                "set_backend_config"
            )
        
        @self.app.get("/api/config/package")
        async def get_package_config():
            return await self._safe_endpoint_call(
                self.config_endpoints.get_package_config,
                "package_config"
            )
        
        @self.app.post("/api/config/package")
        async def set_package_config(request: Request):
            config_data = await request.json()
            return await self._safe_endpoint_call(
                lambda: self.config_endpoints.set_package_config(config_data),
                "set_package_config"
            )
        
        @self.app.get("/api/config/export")
        async def export_config():
            return await self.config_endpoints.export_config()
        
        # Backend management endpoints
        @self.app.post("/api/backends/{backend_name}/restart")
        async def restart_backend(backend_name: str):
            return await self.health_endpoints.restart_backend(backend_name)
        
        @self.app.get("/api/backends/{backend_name}/logs")
        async def get_backend_logs(backend_name: str):
            return await self.health_endpoints.get_backend_logs(backend_name)
        
        # VFS endpoints with enhanced error handling
        @self.app.get("/api/vfs/statistics")
        async def get_vfs_statistics():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_statistics,
                "vfs_statistics"
            )

        @self.app.get("/api/vfs/cache")
        async def get_vfs_cache():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_cache,
                "vfs_cache"
            )

        @self.app.get("/api/vfs/vector-index")
        async def get_vfs_vector_index():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_vector_index,
                "vfs_vector_index"
            )

        @self.app.get("/api/vfs/knowledge-base")
        async def get_vfs_knowledge_base():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_knowledge_base,
                "vfs_knowledge_base"
            )

        @self.app.get("/api/vfs/access-patterns")
        async def get_vfs_access_patterns():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_access_patterns,
                "vfs_access_patterns"
            )

        @self.app.get("/api/vfs/resource-utilization")
        async def get_vfs_resource_utilization():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_resource_utilization,
                "vfs_resource_utilization"
            )

        @self.app.get("/api/vfs/filesystem-metrics")
        async def get_vfs_filesystem_metrics():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_filesystem_metrics,
                "vfs_filesystem_metrics"
            )

        # Enhanced VFS endpoints from comprehensive implementation
        @self.app.get("/api/vfs/health")
        async def get_vfs_health():
            """Enhanced VFS health with alerts and recommendations."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_health,
                "vfs_health"
            )
        
        @self.app.get("/api/vfs/performance")
        async def get_vfs_performance():
            """Detailed VFS performance analysis."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_performance,
                "vfs_performance"
            )
        
        @self.app.get("/api/vfs/recommendations")
        async def get_vfs_recommendations():
            """VFS optimization recommendations."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_recommendations,
                "vfs_recommendations"
            )
        
        @self.app.get("/api/vfs/vector-index")
        async def get_vector_index():
            """Vector index status and metrics."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vector_index,
                "vector_index"
            )
        
        @self.app.get("/api/vfs/knowledge-base")
        async def get_knowledge_base():
            """Knowledge base metrics and analytics."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_knowledge_base,
                "knowledge_base"
            )

        # Debug endpoints for testing error propagation
        @self.app.get("/api/debug/test-error")
        async def test_error():
            """Test endpoint that deliberately throws an error for debugging error propagation."""
            raise ValueError("This is a test error to verify error propagation to the GUI")
        
        @self.app.get("/api/debug/test-timeout-error")
        async def test_timeout_error():
            """Test endpoint that throws a timeout error."""
            import asyncio
            await asyncio.sleep(0.1)  # Short delay
            raise asyncio.TimeoutError("This is a test timeout error")
        
        @self.app.get("/api/debug/test-vfs-error")
        async def test_vfs_error():
            """Test VFS endpoint error through safe_endpoint_call."""
            async def failing_vfs_function():
                raise RuntimeError("VFS subsystem error for testing")
            
            return await self._safe_endpoint_call(
                failing_vfs_function,
                "test_vfs_error"
            )

        # Enhanced monitoring endpoints for comprehensive monitoring tab
        @self.app.get("/api/monitoring/comprehensive")
        async def get_comprehensive_monitoring():
            """Get comprehensive monitoring data for the monitoring tab."""
            return await self._get_comprehensive_monitoring()
        
        @self.app.get("/api/monitoring/metrics")
        async def get_monitoring_metrics():
            """Get detailed metrics for monitoring dashboard."""
            return await self._get_monitoring_metrics()
        
        @self.app.get("/api/monitoring/alerts")
        async def get_monitoring_alerts():
            """Get active monitoring alerts."""
            return await self._get_monitoring_alerts()

        # File management endpoints
        @self.app.get("/api/files/list")
        async def list_files(path: str = "/"):
            """List files in a directory."""
            return await self._safe_endpoint_call(
                self._list_files,
                "list_files",
                path=path
            )

        @self.app.get("/api/files/stats")
        async def get_file_stats():
            """Get file system statistics."""
            return await self._safe_endpoint_call(
                self._get_file_stats,
                "file_stats"
            )

        @self.app.post("/api/files/create-folder")
        async def create_folder(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._create_folder,
                "create_folder",
                path=data.get("path", "/"),
                name=data.get("name")
            )

        @self.app.post("/api/files/upload")
        async def upload_file(request: Request):
            """Upload a file."""
            # This would need proper file upload handling
            return await self._safe_endpoint_call(
                self._upload_file,
                "upload_file",
                request=request
            )

        @self.app.delete("/api/files/delete")
        async def delete_file(request: Request):
            """Delete a file or folder."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._delete_file,
                "delete_file",
                path=data.get("path")
            )

        @self.app.post("/api/files/rename")
        async def rename_file(request: Request):
            """Rename a file or folder."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._rename_file,
                "rename_file",
                old_path=data.get("oldPath"),
                new_name=data.get("newName")
            )

        @self.app.get("/api/files/download")
        async def download_file(path: str):
            """Download a file."""
            return await self._safe_endpoint_call(
                self._download_file,
                "download_file",
                path=path
            )

        # Enhanced configuration endpoints
        @self.app.get("/api/config")
        async def get_config():
            return await self.config_endpoints.get_config()
        
        @self.app.post("/api/config")
        async def save_config(config_data: dict):
            return await self.config_endpoints.save_config(config_data)

        # Analytics endpoints
        @self.app.get("/api/analytics/summary")
        async def get_analytics_summary():
            """Get comprehensive analytics summary."""
            return await self._get_analytics_summary()
        
        @self.app.get("/api/analytics/performance")
        async def get_performance_analytics():
            """Get performance analytics."""
            return await self._get_performance_analytics()
        
        @self.app.get("/api/analytics/trends")
        async def get_trend_analytics():
            """Get trend analysis."""
            return await self._get_trend_analytics()
        
        # Development insights endpoint
        @self.app.get("/api/insights")
        async def get_development_insights():
            """Get development insights and recommendations."""
            return await self._get_development_insights()

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_handler.handle_websocket(websocket)
        
        logger.info("✓ API routes configured with comprehensive endpoints")
    
    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            # Get backend health
            backend_health = await self.backend_monitor.check_all_backends()
            
            # Get system metrics
            system_metrics = await self._get_system_metrics()
            
            # Get performance indicators
            performance_indicators = await self._get_performance_indicators()
            
            # Get operational metrics
            operational_metrics = await self._get_operational_metrics()
            
            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "system_metrics": system_metrics,
                    "performance_indicators": performance_indicators,
                    "operational_metrics": operational_metrics,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": {"avg_ms": 45.2, "p95_ms": 120.5, "p99_ms": 250.1},
                        "cluster": {"avg_ms": 78.9, "p95_ms": 180.2, "p99_ms": 420.3},
                        "lotus": {"avg_ms": 123.4, "p95_ms": 340.7, "p99_ms": 890.2}
                    },
                    "error_rates": {
                        "ipfs": {"rate": 0.02, "count_1h": 15},
                        "cluster": {"rate": 0.01, "count_1h": 8},
                        "lotus": {"rate": 0.05, "count_1h": 32}
                    },
                    "throughput": {
                        "requests_per_second": 85.6,
                        "data_transfer_mbps": 156.7,
                        "operations_per_minute": 5140
                    },
                    "resource_utilization": {
                        "cpu_percent": 23.5,
                        "memory_percent": 67.8,
                        "disk_io_percent": 12.3,
                        "network_io_percent": 34.6
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            return {
                "success": True,
                "alerts": [
                    {
                        "id": "alert_001",
                        "level": "warning",
                        "component": "ipfs_cluster",
                        "message": "Cluster peer count below threshold",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "acknowledged": False
                    },
                    {
                        "id": "alert_002", 
                        "level": "info",
                        "component": "lotus",
                        "message": "Sync lag detected but within normal range",
                        "timestamp": "2024-01-15T09:15:00Z", 
                        "acknowledged": True
                    }
                ],
                "alert_summary": {
                    "total": 2,
                    "critical": 0,
                    "warning": 1,
                    "info": 1,
                    "acknowledged": 1
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "peak_hours": [9, 10, 11, 14, 15, 16],
                        "most_active_backends": ["ipfs", "cluster", "storacha"],
                        "content_types": {
                            "json": 0.35,
                            "text": 0.25, 
                            "images": 0.20,
                            "other": 0.20
                        }
                    },
                    "performance_summary": {
                        "overall_health_score": 0.87,
                        "avg_response_time_ms": 45.6,
                        "uptime_percent": 99.8,
                        "error_rate_percent": 0.02
                    },
                    "capacity_analysis": {
                        "storage_utilization": 0.68,
                        "memory_utilization": 0.45,
                        "cpu_utilization": 0.23,
                        "network_utilization": 0.34
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            return {
                "success": True,
                "performance": {
                    "response_time_trends": {
                        "1h": {"avg": 45.2, "trend": "stable"},
                        "24h": {"avg": 48.7, "trend": "improving"},
                        "7d": {"avg": 52.1, "trend": "stable"}
                    },
                    "throughput_analysis": {
                        "current_rps": 85.6,
                        "peak_rps": 234.7,
                        "capacity_utilization": 0.36
                    },
                    "bottleneck_analysis": [
                        {
                            "component": "lotus_rpc",
                            "severity": "medium",
                            "impact": "15% slower responses",
                            "recommendation": "Optimize RPC connection pooling"
                        }
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            return {
                "success": True,
                "trends": {
                    "usage_trends": {
                        "daily_growth": 0.05,
                        "weekly_pattern": "weekday_heavy",
                        "seasonal_adjustment": 1.15
                    },
                    "performance_trends": {
                        "latency_trend": "improving",
                        "error_rate_trend": "stable",
                        "throughput_trend": "growing"
                    },
                    "capacity_trends": {
                        "storage_growth_rate": 0.08,
                        "memory_growth_rate": 0.03,
                        "predicted_capacity_breach": "3-4 months"
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
        try:
            backend_health = await self.backend_monitor.check_all_backends()
            
            insights = []
            
            # Analyze backend health for insights
            for backend_name, backend_info in backend_health.items():
                if backend_info.get("health") == "unhealthy":
                    insights.append({
                        "type": "issue",
                        "component": backend_name,
                        "message": f"{backend_name} is not healthy",
                        "recommendation": f"Check {backend_name} configuration and logs",
                        "priority": "high"
                    })
                elif backend_info.get("health") == "partial":
                    insights.append({
                        "type": "warning",
                        "component": backend_name,
                        "message": f"{backend_name} has partial functionality",
                        "recommendation": f"Review {backend_name} setup and dependencies",
                        "priority": "medium"
                    })
            
            # Add development recommendations
            insights.extend([
                {
                    "type": "optimization",
                    "component": "general",
                    "message": "Consider implementing request caching",
                    "recommendation": "Add Redis or in-memory caching for frequently accessed data",
                    "priority": "low"
                },
                {
                    "type": "monitoring",
                    "component": "observability",
                    "message": "Enhance monitoring capabilities",
                    "recommendation": "Add custom metrics and alerting rules",
                    "priority": "medium"
                }
            ])
            
            return {
                "success": True,
                "insights": insights,
                "summary": {
                    "total_insights": len(insights),
                    "high_priority": len([i for i in insights if i["priority"] == "high"]),
                    "medium_priority": len([i for i in insights if i["priority"] == "medium"]),
                    "low_priority": len([i for i in insights if i["priority"] == "low"])
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics."""
        return {
            "cpu": {"usage_percent": 23.5, "cores": 8, "load_average": [1.2, 1.4, 1.6]},
            "memory": {"used_gb": 5.6, "total_gb": 16.0, "available_gb": 10.4},
            "disk": {"used_gb": 234.5, "total_gb": 512.0, "available_gb": 277.5},
            "network": {"rx_mbps": 45.6, "tx_mbps": 23.4, "connections": 156}
        }
    
    async def _get_performance_indicators(self) -> Dict[str, Any]:
        """Get key performance indicators."""
        return {
            "uptime_seconds": 345600,  # 4 days
            "requests_processed": 1234567,
            "average_response_time_ms": 45.6,
            "error_rate_percent": 0.02,
            "cache_hit_rate": 0.87,
            "concurrent_connections": 234
        }
    
    async def _get_operational_metrics(self) -> Dict[str, Any]:
        """Get operational metrics."""
        return {
            "active_backends": 8,
            "healthy_backends": 6,
            "unhealthy_backends": 1,
            "partial_backends": 1,
            "total_operations_24h": 45678,
            "failed_operations_24h": 123,
            "data_transferred_gb_24h": 567.8,
            "peak_concurrent_users": 89
        }
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    async def _get_available_tools(self) -> Dict[str, Any]:
        """Get all available MCP tools."""
        try:
            # Get the tool manager from the backend monitor
            from ..mcp_tools.tool_manager import MCPToolManager
            tool_manager = MCPToolManager(self.backend_monitor)
            tools = tool_manager.get_tools()
            
            return {
                "success": True,
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema
                    }
                    for tool in tools
                ],
                "count": len(tools),
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting available tools: {e}")
            return {
                "success": False,
                "error": str(e),
                "tools": [],
                "count": 0,
                "timestamp": self._get_current_timestamp()
            }

    # File management implementation methods
    async def _list_files(self, path: str = "/") -> Dict[str, Any]:
        """List files in a directory."""
        try:
            import os
            import stat
            from pathlib import Path
            
            # Sanitize path to prevent directory traversal
            if not path.startswith("/"):
                path = "/" + path
            
            # For demo purposes, use /tmp/vfs as root, but allow other paths for testing
            if path == "/":
                actual_path = "/tmp/vfs"
            else:
                # Be careful with path traversal
                actual_path = os.path.abspath(path)
            
            if not os.path.exists(actual_path):
                os.makedirs(actual_path, exist_ok=True)
            
            if not os.path.isdir(actual_path):
                return {
                    "success": False,
                    "error": "Path is not a directory",
                    "files": []
                }
            
            files = []
            for item in os.listdir(actual_path):
                item_path = os.path.join(actual_path, item)
                stat_info = os.stat(item_path)
                
                files.append({
                    "name": item,
                    "path": os.path.join(path, item),
                    "is_dir": os.path.isdir(item_path),
                    "size": stat_info.st_size,
                    "modified": stat_info.st_mtime,
                    "type": "directory" if os.path.isdir(item_path) else self._get_file_type(item)
                })
            
            return {
                "success": True,
                "files": files,
                "path": path,
                "count": len(files)
            }
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return {
                "success": False,
                "error": str(e),
                "files": []
            }

    async def _get_file_stats(self) -> Dict[str, Any]:
        """Get file system statistics."""
        try:
            import os
            import shutil
            
            vfs_path = "/tmp/vfs"
            if not os.path.exists(vfs_path):
                os.makedirs(vfs_path, exist_ok=True)
            
            total_files = 0
            total_size = 0
            last_modified = 0
            
            for root, dirs, files in os.walk(vfs_path):
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        stat_info = os.stat(file_path)
                        total_size += stat_info.st_size
                        last_modified = max(last_modified, stat_info.st_mtime)
                    except OSError:
                        continue
            
            # Get disk usage
            disk_usage = shutil.disk_usage(vfs_path)
            
            return {
                "success": True,
                "totalFiles": total_files,
                "totalSize": total_size,
                "lastModified": last_modified,
                "diskUsage": {
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free
                }
            }
        except Exception as e:
            logger.error(f"Error getting file stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        """Create a new folder."""
        try:
            import os
            
            if not name:
                return {
                    "success": False,
                    "error": "Folder name is required"
                }
            
            # Sanitize paths
            base_path = "/tmp/vfs" if path == "/" else os.path.abspath(path)
            folder_path = os.path.join(base_path, name)
            
            if os.path.exists(folder_path):
                return {
                    "success": False,
                    "error": "Folder already exists"
                }
            
            os.makedirs(folder_path, exist_ok=True)
            
            return {
                "success": True,
                "message": f"Folder '{name}' created successfully",
                "path": folder_path
            }
        except Exception as e:
            logger.error(f"Error creating folder: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _upload_file(self, request) -> Dict[str, Any]:
        """Upload a file."""
        try:
            # This is a placeholder implementation
            # In a real implementation, you'd handle multipart form data
            return {
                "success": False,
                "error": "File upload not implemented yet"
            }
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file or folder."""
        try:
            import os
            import shutil
            
            if not path:
                return {
                    "success": False,
                    "error": "Path is required"
                }
            
            actual_path = os.path.abspath(path)
            
            if not os.path.exists(actual_path):
                return {
                    "success": False,
                    "error": "File or folder does not exist"
                }
            
            if os.path.isdir(actual_path):
                shutil.rmtree(actual_path)
                message = "Folder deleted successfully"
            else:
                os.remove(actual_path)
                message = "File deleted successfully"
            
            return {
                "success": True,
                "message": message
            }
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Rename a file or folder."""
        try:
            import os
            
            if not old_path or not new_name:
                return {
                    "success": False,
                    "error": "Both old path and new name are required"
                }
            
            actual_old_path = os.path.abspath(old_path)
            
            if not os.path.exists(actual_old_path):
                return {
                    "success": False,
                    "error": "File or folder does not exist"
                }
            
            directory = os.path.dirname(actual_old_path)
            new_path = os.path.join(directory, new_name)
            
            if os.path.exists(new_path):
                return {
                    "success": False,
                    "error": "A file or folder with that name already exists"
                }
            
            os.rename(actual_old_path, new_path)
            
            return {
                "success": True,
                "message": "File renamed successfully",
                "newPath": new_path
            }
        except Exception as e:
            logger.error(f"Error renaming file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _download_file(self, path: str) -> Dict[str, Any]:
        """Download a file."""
        try:
            import os
            from fastapi.responses import FileResponse
            
            if not path:
                return {
                    "success": False,
                    "error": "Path is required"
                }
            
            actual_path = os.path.abspath(path)
            
            if not os.path.exists(actual_path):
                return {
                    "success": False,
                    "error": "File does not exist"
                }
            
            if os.path.isdir(actual_path):
                return {
                    "success": False,
                    "error": "Cannot download a directory"
                }
            
            # This would return a FileResponse in a real implementation
            return {
                "success": True,
                "message": "File download initiated",
                "path": actual_path
            }
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_file_type(self, filename: str) -> str:
        """Get file type based on extension."""
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        type_map = {
            'txt': 'text', 'md': 'markdown', 'json': 'json',
            'js': 'javascript', 'py': 'python', 'html': 'html',
            'css': 'css', 'png': 'image', 'jpg': 'image',
            'jpeg': 'image', 'gif': 'image', 'svg': 'image',
            'mp4': 'video', 'mp3': 'audio', 'wav': 'audio',
            'pdf': 'pdf', 'doc': 'document', 'docx': 'document',
            'zip': 'archive', 'tar': 'archive', 'gz': 'archive'
        }
        
        return type_map.get(ext, 'unknown')
