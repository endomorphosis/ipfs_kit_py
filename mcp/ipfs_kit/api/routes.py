"""
API routes configuration for IPFS Kit MCP Server.
Clean version without duplication.
"""

import traceback
import asyncio
import os
import shutil
from fastapi import FastAPI, Request, HTTPException, WebSocket, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from .health_endpoints import HealthEndpoints
from .config_endpoints import ConfigEndpoints
from .vfs_endpoints import VFSEndpoints
from .file_endpoints import FileEndpoints
from .websocket_handler import WebSocketHandler
from .vector_kb_endpoints import VectorKBEndpoints
from .peer_endpoints import PeerEndpoints

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
        self.vector_kb_endpoints = VectorKBEndpoints(backend_monitor, vfs_observer)
        self.file_endpoints = FileEndpoints()
        self.websocket_handler = WebSocketHandler(websocket_manager)
        self.peer_endpoints = PeerEndpoints(backend_monitor)
        
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
        
        # Storage backends endpoint for dashboard compatibility
        @self.app.get("/api/v0/storage/backends")
        async def get_storage_backends():
            """Get storage backend configurations for dashboard."""
            return await self._safe_endpoint_call(
                self.backend_monitor.check_all_backends,
                "storage_backends"
            )
        
        @self.app.get("/api/v0/storage/backends/{backend_name}")
        async def get_storage_backend_detail(backend_name: str):
            """Get detailed configuration for a specific storage backend."""
            return await self._safe_endpoint_call(
                lambda: self.backend_monitor.check_backend_health(backend_name),
                f"storage_backend_{backend_name}"
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
        
        # Enhanced logging endpoints
        @self.app.get("/api/logs")
        async def get_logs():
            """Get logs from all backends (redirect to all logs)."""
            return await self._safe_endpoint_call(
                self._get_all_backend_logs,
                "all_logs"
            )
        
        @self.app.get("/api/logs/all")
        async def get_all_logs():
            """Get logs from all backends."""
            return await self._safe_endpoint_call(
                self._get_all_backend_logs,
                "all_logs"
            )
        
        @self.app.get("/api/logs/recent")
        async def get_recent_logs(minutes: int = 30):
            """Get recent logs from all backends."""
            return await self._safe_endpoint_call(
                lambda: self._get_recent_logs(minutes),
                "recent_logs"
            )
        
        @self.app.get("/api/logs/errors")
        async def get_error_logs():
            """Get error and warning logs from all backends."""
            return await self._safe_endpoint_call(
                self._get_error_logs,
                "error_logs"
            )
        
        @self.app.get("/api/logs/statistics")
        async def get_log_statistics():
            """Get logging statistics for dashboard."""
            return await self._safe_endpoint_call(
                self._get_log_statistics,
                "log_statistics"
            )
        
        @self.app.post("/api/logs/clear/{backend_name}")
        async def clear_backend_logs(backend_name: str):
            """Clear logs for a specific backend."""
            return await self._safe_endpoint_call(
                lambda: self._clear_backend_logs(backend_name),
                "clear_logs"
            )
        
        @self.app.post("/api/backends/{backend_name}/restart")
        async def restart_backend(backend_name: str):
            return await self._safe_endpoint_call(
                lambda: self._restart_backend(backend_name),
                "restart_backend"
            )
        
        @self.app.post("/api/backends/{backend_name}/start")
        async def start_backend(backend_name: str):
            return await self._safe_endpoint_call(
                lambda: self._start_backend(backend_name),
                "start_backend"
            )
        
        @self.app.post("/api/backends/{backend_name}/stop")
        async def stop_backend(backend_name: str):
            return await self._safe_endpoint_call(
                lambda: self._stop_backend(backend_name),
                "stop_backend"
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
            try:
                # Call synchronous method directly since it's not async
                result = self.config_endpoints.get_package_config()
                return {"success": True, "data": result}
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "type": type(e).__name__,
                    "endpoint": "package_config",
                    "timestamp": self._get_current_timestamp()
                }
        
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
        @self.app.get("/api/vfs/journal")
        async def get_vfs_journal(backend: Optional[str] = None, query: Optional[str] = None):
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_journal,
                "vfs_journal",
                backend_filter=backend,
                search_query=query
            )

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
                self.vector_kb_endpoints.get_enhanced_vector_index_status,
                "enhanced_vector_index"
            )
        
        @self.app.get("/api/vfs/knowledge-base")
        async def get_vfs_knowledge_base():
            return await self._safe_endpoint_call(
                self.vector_kb_endpoints.get_enhanced_knowledge_base_status,
                "enhanced_knowledge_base"
            )
        
        # Enhanced Vector & KB search endpoints
        @self.app.get("/api/vector/search")
        async def search_vector_database(query: str, limit: int = 10, min_similarity: float = 0.1):
            return await self._safe_endpoint_call(
                lambda: self.vector_kb_endpoints.search_vector_database(query, limit, min_similarity),
                "vector_search"
            )
        
        @self.app.get("/api/vector/collections")
        async def list_vector_collections():
            return await self._safe_endpoint_call(
                self.vector_kb_endpoints.list_vector_collections,
                "vector_collections"
            )
        
        @self.app.get("/api/kg/entity/{entity_id}")
        async def get_entity_details(entity_id: str):
            return await self._safe_endpoint_call(
                lambda: self.vector_kb_endpoints.get_entity_details(entity_id),
                "entity_details"
            )
        
        @self.app.get("/api/kg/search")
        async def search_knowledge_graph_by_entity(entity_id: str):
            return await self._safe_endpoint_call(
                lambda: self.vector_kb_endpoints.search_knowledge_graph_by_entity(entity_id),
                "kg_entity_search"
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

        # Peer Management API Routes
        @self.app.get("/api/peers/summary")
        async def get_peers_summary():
            """Get summary of all discovered peers."""
            return await self._safe_endpoint_call(
                self.peer_endpoints.get_peers_summary,
                "peers_summary"
            )
        
        @self.app.get("/api/peers/list")
        async def get_peers_list(
            limit: int = Query(50, ge=1, le=500),
            offset: int = Query(0, ge=0),
            filter_protocol: Optional[str] = Query(None),
            filter_connected: Optional[bool] = Query(None)
        ):
            """Get paginated list of discovered peers."""
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.get_peers_list(limit, offset, filter_protocol, filter_connected),
                "peers_list"
            )
        
        @self.app.get("/api/peers/{peer_id}")
        async def get_peer_details(peer_id: str):
            """Get detailed information about a specific peer."""
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.get_peer_details(peer_id),
                "peer_details"
            )
        
        @self.app.get("/api/peers/{peer_id}/content")
        async def get_peer_content(peer_id: str):
            """Get content shared by a specific peer."""
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.get_peer_content(peer_id),
                "peer_content"
            )
        
        @self.app.post("/api/peers/{peer_id}/connect")
        async def connect_to_peer(peer_id: str, request: Request):
            """Connect to a specific peer."""
            data = await request.json()
            multiaddr = data.get("multiaddr")
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.connect_to_peer(peer_id, multiaddr),
                "connect_peer"
            )
        
        @self.app.post("/api/peers/{peer_id}/disconnect")
        async def disconnect_from_peer(peer_id: str):
            """Disconnect from a specific peer."""
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.disconnect_from_peer(peer_id),
                "disconnect_peer"
            )
        
        @self.app.get("/api/peers/search")
        async def search_peers(query: str):
            """Search peers by various criteria."""
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.search_peers(query),
                "search_peers"
            )
        
        @self.app.get("/api/peers/discovery/status")
        async def get_peer_discovery_status():
            """Get the status of peer discovery."""
            return await self._safe_endpoint_call(
                self.peer_endpoints.get_peer_discovery_status,
                "discovery_status"
            )
        
        @self.app.post("/api/peers/discovery/start")
        async def start_peer_discovery():
            """Start peer discovery."""
            return await self._safe_endpoint_call(
                self.peer_endpoints.start_peer_discovery,
                "start_discovery"
            )
        
        @self.app.post("/api/peers/discovery/stop")
        async def stop_peer_discovery():
            """Stop peer discovery."""
            return await self._safe_endpoint_call(
                self.peer_endpoints.stop_peer_discovery,
                "stop_discovery"
            )
        
        @self.app.post("/api/peers/bootstrap/add")
        async def add_bootstrap_peer(request: Request):
            """Add a bootstrap peer."""
            data = await request.json()
            multiaddr = data.get("multiaddr")
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.add_bootstrap_peer(multiaddr),
                "add_bootstrap"
            )
        
        @self.app.post("/api/peers/bootstrap/remove")
        async def remove_bootstrap_peer(request: Request):
            """Remove a bootstrap peer."""
            data = await request.json()
            multiaddr = data.get("multiaddr")
            return await self._safe_endpoint_call(
                lambda: self.peer_endpoints.remove_bootstrap_peer(multiaddr),
                "remove_bootstrap"
            )
        
        @self.app.get("/api/peers/network/stats")
        async def get_peer_network_stats():
            """Get network statistics for the peer network."""
            return await self._safe_endpoint_call(
                self.peer_endpoints.get_peer_network_stats,
                "network_stats"
            )

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

    async def _start_backend(self, backend_name: str) -> Dict[str, Any]:
        """Start a specific backend."""
        try:
            logger.info(f"Start requested for backend: {backend_name}")
            
            # Check if backend is already running
            backend_health = await self.backend_monitor.check_backend(backend_name)
            if backend_health.get("status") == "healthy":
                return {
                    "success": True,
                    "message": f"{backend_name} is already running",
                    "backend": backend_name,
                    "status": "already_running",
                    "timestamp": self._get_current_timestamp()
                }
            
            # Start the backend using backend_monitor
            if hasattr(self.backend_monitor, 'start_backend'):
                result = await self.backend_monitor.start_backend(backend_name)
                return {
                    "success": True,
                    "message": f"Start initiated for {backend_name}",
                    "backend": backend_name,
                    "status": "starting",
                    "details": result,
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": True,
                    "message": f"Start simulated for {backend_name} (not yet implemented)",
                    "backend": backend_name,
                    "status": "simulated",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error starting {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }

    async def _stop_backend(self, backend_name: str) -> Dict[str, Any]:
        """Stop a specific backend."""
        try:
            logger.info(f"Stop requested for backend: {backend_name}")
            
            # Stop the backend using backend_monitor
            if hasattr(self.backend_monitor, 'stop_backend'):
                result = await self.backend_monitor.stop_backend(backend_name)
                return {
                    "success": True,
                    "message": f"Stop initiated for {backend_name}",
                    "backend": backend_name,
                    "status": "stopping",
                    "details": result,
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": True,
                    "message": f"Stop simulated for {backend_name} (not yet implemented)",
                    "backend": backend_name,
                    "status": "simulated",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error stopping {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }

    async def _get_backend_config(self, backend_name: str) -> Dict[str, Any]:
        """Get configuration for a specific backend."""
        try:
            logger.info(f"Config requested for backend: {backend_name}")
            
            # Get backend configuration from backend_monitor
            if hasattr(self.backend_monitor, 'get_backend_config'):
                result = await self.backend_monitor.get_backend_config(backend_name)
                
                # Handle different response formats
                if isinstance(result, dict):
                    if "error" in result:
                        return {
                            "success": False,
                            "error": result["error"],
                            "backend": backend_name,
                            "timestamp": self._get_current_timestamp()
                        }
                    elif "config" in result:
                        # If wrapped in config key, unwrap it
                        config = result["config"]
                    else:
                        # Direct config data
                        config = result
                else:
                    config = {"error": "Invalid config format returned"}
                    
            else:
                # Mock configuration for now
                config = {
                    "enabled": True,
                    "port": 5001 if backend_name == "ipfs" else 9042 if backend_name == "cassandra" else 8080,
                    "host": "localhost",
                    "max_connections": 100,
                    "timeout": 30,
                    "debug": False
                }
            
            return {
                "success": True,
                "backend": backend_name,
                "config": config,
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting config for {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }

    async def _set_backend_config(self, backend_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Set configuration for a specific backend."""
        try:
            logger.info(f"Config update requested for backend: {backend_name}")
            
            # Set backend configuration using backend_monitor
            if hasattr(self.backend_monitor, 'set_backend_config'):
                result = await self.backend_monitor.set_backend_config(backend_name, config_data)
                return {
                    "success": True,
                    "message": f"Configuration updated for {backend_name}",
                    "backend": backend_name,
                    "config": config_data,
                    "details": result,
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": True,
                    "message": f"Configuration simulated for {backend_name} (not yet implemented)",
                    "backend": backend_name,
                    "config": config_data,
                    "status": "simulated",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error setting config for {backend_name}: {e}")
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
    
    async def _get_all_backend_logs(self) -> Dict[str, Any]:
        """Get logs from all backends."""
        try:
            if hasattr(self.backend_monitor, 'log_manager'):
                all_logs = self.backend_monitor.log_manager.get_all_backend_logs(limit=50)
                return {
                    "success": True,
                    "logs": all_logs,
                    "total_backends": len(all_logs),
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "Log manager not available",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error getting all backend logs: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }
    
    async def _get_recent_logs(self, minutes: int = 30) -> Dict[str, Any]:
        """Get recent logs from all backends."""
        try:
            if hasattr(self.backend_monitor, 'log_manager'):
                recent_logs = self.backend_monitor.log_manager.get_recent_logs(minutes=minutes, limit=200)
                return {
                    "success": True,
                    "logs": recent_logs,
                    "minutes": minutes,
                    "count": len(recent_logs),
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "Log manager not available",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error getting recent logs: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }
    
    async def _get_error_logs(self) -> Dict[str, Any]:
        """Get error and warning logs from all backends."""
        try:
            if hasattr(self.backend_monitor, 'log_manager'):
                error_logs = self.backend_monitor.log_manager.get_error_logs(limit=100)
                return {
                    "success": True,
                    "error_logs": error_logs,
                    "count": len(error_logs),
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "Log manager not available",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error getting error logs: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }
    
    async def _get_log_statistics(self) -> Dict[str, Any]:
        """Get logging statistics for dashboard."""
        try:
            if hasattr(self.backend_monitor, 'log_manager'):
                stats = self.backend_monitor.log_manager.get_log_statistics()
                return {
                    "success": True,
                    "statistics": stats,
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "Log manager not available",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error getting log statistics: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
            }
    
    async def _clear_backend_logs(self, backend_name: str) -> Dict[str, Any]:
        """Clear logs for a specific backend."""
        try:
            if hasattr(self.backend_monitor, 'log_manager'):
                self.backend_monitor.log_manager.clear_backend_logs(backend_name)
                return {
                    "success": True,
                    "message": f"Logs cleared for {backend_name}",
                    "backend": backend_name,
                    "timestamp": self._get_current_timestamp()
                }
            else:
                return {
                    "success": False,
                    "error": "Log manager not available",
                    "timestamp": self._get_current_timestamp()
                }
        except Exception as e:
            logger.error(f"Error clearing logs for {backend_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": backend_name,
                "timestamp": self._get_current_timestamp()
            }
