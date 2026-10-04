"""
API routes configuration for IPFS Kit MCP Server.
"""

import traceback
import anyio
import os # Added for file operations
import shutil # Added for file operations
from fastapi import FastAPI, Request, HTTPException, WebSocket, UploadFile, File, Form
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
    
    def __init__(self, app: FastAPI, backend_monitor, vfs_observer, templates, websocket_manager):
        self.app = app
        self.backend_monitor = backend_monitor
        self.vfs_observer = vfs_observer # New: VFS observer
        self.templates = templates
        self.websocket_manager = websocket_manager
        
        # Initialize endpoint handlers
        self.health_endpoints = HealthEndpoints(backend_monitor)
        self.config_endpoints = ConfigEndpoints(backend_monitor)
        self.vfs_endpoints = VFSEndpoints(backend_monitor, vfs_observer) # Pass vfs_observer
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
                "timestamp": anyio.current_time(),
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
                "timestamp": anyio.current_time()
            }
        except Exception as e:
            error_info = {
                "success": False,
                "error": True,
                "error_type": type(e).__name__,
                "message": str(e),
                "endpoint": endpoint_name,
                "timestamp": anyio.current_time(),
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
            await anyio.sleep(0.1)  # Short delay
            raise TimeoutError("This is a test timeout error")
        
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
            return await self._list_files(path)

        @self.app.get("/api/files/stats")
        async def get_file_stats():
            """Get file system statistics."""
            return await self._get_file_stats()

        @self.app.post("/api/files/create-folder")
        async def create_folder(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/upload")
        async def upload_file(request: Request, file: UploadFile = File(...)):
            """Upload a file."""
            # This would need proper file upload handling
            return await self._upload_file(request)

        @self.app.post("/api/files/rename")
        async def rename_file(request: Request):
            """Rename a file or folder."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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

# Enhanced File Management Routes for Real Dashboard Integration
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._list_files(path)

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._delete_file(data.get("path"))

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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

# Enhanced File Management Routes for Real Dashboard Integration
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._list_files(path)

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._delete_file(data.get("path"))

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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

# Enhanced File Management Routes for Real Dashboard Integration
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._list_files(path)

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._delete_file(data.get("path"))

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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

# Enhanced File Management Routes for Real Dashboard Integration
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._list_files(path)

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._delete_file(data.get("path"))

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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

# Enhanced File Management Routes for Real Dashboard Integration
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._list_files(path)

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._create_folder(data.get("path", "/"), data.get("name"))

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._delete_file(data.get("path"))

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._rename_file(data.get("oldPath"), data.get("newName"))

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._move_item(data.get("sourcePath"), data.get("targetPath"))


        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
            """Upload a file to the specified path."""
            return await self.vfs_endpoints.upload_file(path, file)

        @self.app.get("/api/files/download", tags=["File Manager"])
        async def download_file_endpoint(path: str):
            """Download a file."""
            result = await self._download_file(path)
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
    
    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            results = {}
            async with anyio.create_task_group() as task_group:
                async def get_backend_health():
                    results["backend_health"] = await self.backend_monitor.check_all_backends()

                async def get_vfs_stats():
                    results["vfs_stats"] = await self.vfs_observer.get_vfs_statistics()

                task_group.start_soon(get_backend_health)
                task_group.start_soon(get_vfs_stats)

            backend_health = results.get("backend_health")
            vfs_stats = results.get("vfs_stats")

            return {
                "success": True,
                "monitoring_data": {
                    "backend_health": backend_health,
                    "vfs_stats": vfs_stats,
                    "last_updated": self._get_current_timestamp()
                }
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics for monitoring dashboard."""
        try:
            # Fetch real-time metrics from backend_monitor and vfs_observer
            system_metrics = await self.backend_monitor.get_system_metrics()
            vfs_performance = await self.vfs_observer.get_performance_metrics()
            
            # Aggregate and format data
            return {
                "success": True,
                "metrics": {
                    "response_times": {
                        "ipfs": await self.backend_monitor.get_response_time_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_response_time_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_response_time_metrics("lotus")
                    },
                    "error_rates": {
                        "ipfs": await self.backend_monitor.get_error_rate_metrics("ipfs"),
                        "cluster": await self.backend_monitor.get_error_rate_metrics("cluster"),
                        "lotus": await self.backend_monitor.get_error_rate_metrics("lotus")
                    },
                    "throughput": {
                        "requests_per_second": vfs_performance.get("requests_per_second", 0),
                        "data_transfer_mbps": vfs_performance.get("data_transfer_mbps", 0),
                        "operations_per_minute": vfs_performance.get("operations_per_minute", 0)
                    },
                    "resource_utilization": {
                        "cpu_percent": system_metrics.get("cpu", {}).get("usage_percent", 0),
                        "memory_percent": (system_metrics.get("memory", {}).get("used_gb", 0) / system_metrics.get("memory", {}).get("total_gb", 1)) * 100,
                        "disk_io_percent": vfs_performance.get("disk_io_percent", 0),
                        "network_io_percent": system_metrics.get("network", {}).get("tx_mbps", 0) + system_metrics.get("network", {}).get("rx_mbps", 0)
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get active monitoring alerts."""
        try:
            alerts = await self.backend_monitor.get_active_alerts()
            
            alert_summary = {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("level") == "critical"),
                "warning": sum(1 for a in alerts if a.get("level") == "warning"),
                "info": sum(1 for a in alerts if a.get("level") == "info"),
                "acknowledged": sum(1 for a in alerts if a.get("acknowledged"))
            }
            
            return {
                "success": True,
                "alerts": alerts,
                "alert_summary": alert_summary
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            backend_health = await self.backend_monitor.check_all_backends()

            healthy_backends = [b for b, h in backend_health.items() if h.get('health') == 'healthy']

            return {
                "success": True,
                "analytics": {
                    "usage_patterns": {
                        "most_active_backends": healthy_backends,
                        "access_patterns": vfs_stats.get("access_patterns", {})
                    },
                    "performance_summary": {
                        "cache_performance": vfs_stats.get("cache_performance", {}),
                        "vector_index_performance": vfs_stats.get("vector_index_status", {}).get("search_performance", {})
                    },
                    "capacity_analysis": {
                       "resource_utilization": vfs_stats.get("resource_utilization", {})
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting analytics summary: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_performance_analytics(self) -> Dict[str, Any]:
        """Get performance analytics."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "performance": {
                    "cache_performance": vfs_stats.get("cache_performance", {}),
                    "vector_index_performance": vfs_stats.get("vector_index_status", {}),
                    "filesystem_performance": vfs_stats.get("filesystem_metrics", {})
                }
            }
        except Exception as e:
            logger.error(f"Error getting performance analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_trend_analytics(self) -> Dict[str, Any]:
        """Get trend analysis."""
        try:
            vfs_stats = await self.vfs_observer.get_vfs_statistics()
            return {
                "success": True,
                "trends": {
                    "access_patterns": vfs_stats.get("access_patterns", {}),
                }
            }
        except Exception as e:
            logger.error(f"Error getting trend analytics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
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
                }
            }
        except Exception as e:
            logger.error(f"Error getting development insights: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
        return await self.vfs_endpoints.list_files(path)

    async def _get_file_stats(self) -> Dict[str, Any]:
        # This can be derived from list_files or a new endpoint in vfs_endpoints
        return await self.vfs_endpoints.get_vfs_statistics()


    async def _create_folder(self, path: str, name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.create_folder(path, name)

    async def _upload_file(self, request: Request) -> Dict[str, Any]:
        async with request.form() as form:
            path = form.get("path", "/")
            file = form["file"]
            return await self.vfs_endpoints.upload_file(path, file)

    async def _delete_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.delete_item(path)

    async def _rename_file(self, old_path: str, new_name: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.rename_item(old_path, new_name)

    async def _download_file(self, path: str) -> Dict[str, Any]:
        return await self.vfs_endpoints.download_file(path)

    async def _move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Helper to move a file or folder."""
        return await self.vfs_endpoints.move_item(source_path, target_path)

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
