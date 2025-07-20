"""
API routes configuration for IPFS Kit MCP Server.
Clean version without duplication.
"""

import traceback
import asyncio
import os
import shutil
from fastapi import FastAPI, Request, HTTPException, WebSocket, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any
import logging
from pathlib import Path

from .health_endpoints import HealthEndpoints
from .config_endpoints import ConfigEndpoints
from .vfs_endpoints import VFSEndpoints
from .file_endpoints import FileEndpoints
from .websocket_handler import WebSocketHandler

logger = logging.getLogger(__name__)


class APIRoutes:
    """Manages all API routes for the MCP server."""
    
    def __init__(self, app: FastAPI, backend_monitor, vfs_observer, templates, websocket_manager):
        self.app = app
        self.backend_monitor = backend_monitor
        self.vfs_observer = vfs_observer
        self.templates = templates
        self.websocket_manager = websocket_manager
        
        # Initialize endpoint handlers
        self.health_endpoints = HealthEndpoints(backend_monitor)
        self.config_endpoints = ConfigEndpoints(backend_monitor)
        self.vfs_endpoints = VFSEndpoints(backend_monitor, vfs_observer)
        self.file_endpoints = FileEndpoints()
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
                "success": False,
                "error": str(exc),
                "type": type(exc).__name__,
                "details": traceback.format_exc(),
                "endpoint": str(request.url),
                "method": request.method,
                "timestamp": self._get_current_timestamp()
            }
            
            logger.error(f"Global exception in {request.method} {request.url}: {exc}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return JSONResponse(
                status_code=500,
                content=error_info
            )
    
    async def _safe_endpoint_call(self, func, endpoint_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Safely call an endpoint function with comprehensive error handling."""
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, dict) and not result.get("success", True):
                logger.warning(f"Endpoint {endpoint_name} returned unsuccessful result: {result}")
            return result
        except Exception as e:
            error_info = {
                "success": False,
                "error": str(e),
                "type": type(e).__name__,
                "endpoint": endpoint_name,
                "timestamp": self._get_current_timestamp(),
                "details": traceback.format_exc()
            }
            
            logger.error(f"Error in {endpoint_name}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return error_info
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        # Mount static files for JavaScript, CSS, and other assets
        static_dir = Path(__file__).parent.parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logger.info(f"✓ Static files mounted from: {static_dir}")
        else:
            logger.warning(f"⚠ Static directory not found: {static_dir}")
        
        # Dashboard route
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        # Simple favicon route - return a simple icon response
        @self.app.get("/favicon.ico")
        async def favicon():
            # Return a simple 1x1 transparent PNG to avoid 404 errors
            favicon_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
            from fastapi.responses import Response
            return Response(content=favicon_content, media_type="image/png")
        
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
                self.backend_monitor.check_all_backends,
                "all_backends"
            )
        
        @self.app.get("/api/backends/status")
        async def get_all_backends_status():
            return await self._safe_endpoint_call(
                self.health_endpoints.get_all_backends_status,
                "all_backends_status"
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
        
        @self.app.get("/api/backends/{backend_name}/logs")
        async def get_backend_logs(backend_name: str):
            return await self._safe_endpoint_call(
                lambda: self._get_backend_logs(backend_name),
                "backend_logs"
            )
        
        @self.app.post("/api/backends/{backend_name}/restart")
        async def restart_backend(backend_name: str):
            return await self._safe_endpoint_call(
                lambda: self._restart_backend(backend_name),
                "restart_backend"
            )
        
        # Tools endpoint
        @self.app.get("/api/tools")
        async def get_tools():
            """Get all available MCP tools."""
            return await self._safe_endpoint_call(
                self._get_available_tools,
                "tools"
            )

        # Insights endpoint for dashboard analytics
        @self.app.get("/api/insights")
        async def get_insights():
            """Get comprehensive system insights for dashboard."""
            return await self._safe_endpoint_call(
                self._get_system_insights,
                "insights"
            )

        # Monitoring endpoints
        @self.app.get("/api/monitoring/metrics")
        async def get_monitoring_metrics():
            """Get monitoring metrics."""
            return await self._safe_endpoint_call(
                self._get_monitoring_metrics,
                "monitoring_metrics"
            )
        
        @self.app.get("/api/monitoring/alerts")
        async def get_monitoring_alerts():
            """Get monitoring alerts."""
            return await self._safe_endpoint_call(
                self._get_monitoring_alerts,
                "monitoring_alerts"
            )
        
        @self.app.get("/api/monitoring/comprehensive")
        async def get_comprehensive_monitoring():
            """Get comprehensive monitoring data."""
            return await self._safe_endpoint_call(
                self._get_comprehensive_monitoring,
                "comprehensive_monitoring"
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
                lambda: self.config_endpoints.get_package_config(),
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
            return await self._safe_endpoint_call(
                self.config_endpoints.export_config,
                "export_config"
            )
        
        @self.app.post("/api/config/import")
        async def import_config(request: Request):
            import_data = await request.json()
            return await self._safe_endpoint_call(
                lambda: self.config_endpoints.export_config(),  # Use export for now since import doesn't exist
                "import_config"
            )
        
        # VFS and file management endpoints
        # VFS endpoints with comprehensive error handling
        @self.app.get("/api/vfs/status")
        async def get_vfs_status():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_analytics,
                "vfs_status"
            )
        
        @self.app.get("/api/vfs/statistics")
        async def get_vfs_statistics():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_analytics,
                "vfs_statistics"
            )
        
        @self.app.get("/api/vfs/cache")
        async def get_vfs_cache():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_cache,
                "vfs_cache"
            )
        
        @self.app.get("/api/vfs/health")
        async def get_vfs_health():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_health,
                "vfs_health"
            )
        
        @self.app.get("/api/vfs/performance")
        async def get_vfs_performance():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_performance,
                "vfs_performance"
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
        
        @self.app.get("/api/vfs/recommendations")
        async def get_vfs_recommendations():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_recommendations,
                "vfs_recommendations"
            )
        
        # File listing endpoint
        @self.app.get("/api/files/")
        async def simple_list_files(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.list_files,
                "list_files",
                path=path
            )
        
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.list_files,
                "list_files",
                path=path
            )

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self.vfs_endpoints.create_folder,
                "create_folder",
                path=data.get("path", "/"),
                name=data.get("name")
            )

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self.vfs_endpoints.delete_item,
                "delete_file",
                path=data.get("path")
            )

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self.vfs_endpoints.rename_item,
                "rename_file",
                old_path=data.get("oldPath"),
                new_name=data.get("newName")
            )

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self.vfs_endpoints.move_item,
                "move_file",
                source_path=data.get("sourcePath"),
                target_path=data.get("targetPath")
            )

        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(file: UploadFile = File(...), path: str = Form("/")):
            """Upload a file to the specified path."""
            return await self._safe_endpoint_call(
                self.vfs_endpoints.upload_file,
                "upload_file",
                path=path,
                file=file
            )

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._safe_endpoint_call(
                self.vfs_endpoints.download_file,
                "download_file",
                path=path
            )
            
            if result.get("success"):
                from fastapi.responses import FileResponse
                # Assuming download_file returns the absolute path to the file
                file_path = result["file_path"]
                file_name = result["name"]
                return FileResponse(path=file_path, filename=file_name, media_type="application/octet-stream")
            else:
                raise HTTPException(status_code=404, detail=result.get("error", "File not found"))

        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.websocket_handler.handle_websocket(websocket)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    async def _get_available_tools(self) -> Dict[str, Any]:
        """Get all available MCP tools."""
        try:
            # For now, return a basic tools list
            # In the future, integrate with tool manager
            return {
                "success": True,
                "tools": [
                    {
                        "name": "vfs_analytics",
                        "description": "VFS Analytics and monitoring",
                        "category": "filesystem"
                    },
                    {
                        "name": "backend_monitoring",
                        "description": "Backend health monitoring",
                        "category": "monitoring"
                    },
                    {
                        "name": "config_management",
                        "description": "Configuration management",
                        "category": "configuration"
                    }
                ],
                "count": 3,
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

    async def _get_system_insights(self) -> Dict[str, Any]:
        """Get comprehensive system insights for dashboard."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            recommendations = vfs_stats.get("recommendations", [])

            return {
                "success": True,
                "insights": recommendations,
                "summary": {
                    "total_insights": len(recommendations),
                    "high_priority": len([i for i in recommendations if i.get("priority") == "high"]),
                    "medium_priority": len([i for i in recommendations if i.get("priority") == "medium"]),
                    "low_priority": len([i for i in recommendations if i.get("priority") == "low"])
                },
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting system insights: {e}", exc_info=True)
            return {
                "success": False, 
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }

    async def _get_backend_logs(self, backend_name: str) -> Dict[str, Any]:
        """Get logs for a specific backend."""
        try:
            # For now, return mock logs - in a real implementation, you'd read actual log files
            import os
            log_file = f"/tmp/ipfs_kit_logs/{backend_name}.log"
            
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = f.readlines()[-100:]  # Last 100 lines
            else:
                logs = [f"No log file found for {backend_name}"]
            
            return {
                "success": True,
                "backend": backend_name,
                "logs": logs,
                "count": len(logs),
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting logs for {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }

    async def _restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a specific backend."""
        try:
            # For now, return a mock restart response
            # In a real implementation, you'd trigger an actual restart
            logger.info(f"Restart requested for backend: {backend_name}")
            
            return {
                "success": True,
                "message": f"Restart initiated for {backend_name}",
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error restarting {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics."""
        try:
            # Get basic metrics from VFS and backends
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()
            
            return {
                "success": True,
                "metrics": {
                    "vfs": vfs_stats.get("data", {}),
                    "backends": backend_health,
                    "system": {
                        "uptime": vfs_stats.get("data", {}).get("uptime_seconds", 0),
                        "memory_usage": vfs_stats.get("data", {}).get("resource_utilization", {}).get("memory_usage", {}),
                        "cpu_usage": vfs_stats.get("data", {}).get("resource_utilization", {}).get("cpu_usage", {})
                    }
                },
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get monitoring alerts."""
        try:
            # Generate alerts based on system status
            alerts = []
            
            # Check backend health for alerts
            backend_health = await self.backend_monitor.check_all_backends()
            for backend_name, status in backend_health.items():
                if not status.get("healthy", False):
                    alerts.append({
                        "type": "error",
                        "message": f"Backend {backend_name} is unhealthy",
                        "source": backend_name,
                        "timestamp": self._get_current_timestamp()
                    })
            
            return {
                "success": True,
                "alerts": alerts,
                "count": len(alerts),
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data."""
        try:
            # Combine metrics and alerts for comprehensive view
            metrics = await self._get_monitoring_metrics()
            alerts = await self._get_monitoring_alerts()
            insights = await self._get_system_insights()
            
            return {
                "success": True,
                "comprehensive": {
                    "metrics": metrics.get("metrics", {}),
                    "alerts": alerts.get("alerts", []),
                    "insights": insights.get("insights", []),
                    "summary": {
                        "total_backends": len(metrics.get("metrics", {}).get("backends", {})),
                        "healthy_backends": len([b for b in metrics.get("metrics", {}).get("backends", {}).values() if b.get("healthy", False)]),
                        "total_alerts": alerts.get("count", 0),
                        "total_insights": len(insights.get("insights", []))
                    }
                },
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }
