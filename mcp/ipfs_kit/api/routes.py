"""
API routes configuration for IPFS Kit MCP Server.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
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
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup all API routes."""
        
        # Dashboard route
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("index.html", {"request": request})
        
        # Health endpoints
        @self.app.get("/api/health")
        async def health_check():
            return await self.health_endpoints.get_health()
        
        @self.app.get("/api/backends")
        async def get_backends():
            return await self.health_endpoints.get_all_backends()
        
        @self.app.get("/api/backends/{backend_name}")
        async def get_backend_status(backend_name: str):
            return await self.health_endpoints.get_backend_status(backend_name)
        
        @self.app.get("/api/backends/{backend_name}/detailed")
        async def get_backend_detailed(backend_name: str):
            return await self.health_endpoints.get_backend_detailed(backend_name)
        
        @self.app.get("/api/backends/{backend_name}/info")
        async def get_backend_info(backend_name: str):
            return await self.health_endpoints.get_backend_info(backend_name)
        
        # Configuration endpoints
        @self.app.get("/api/backends/{backend_name}/config")
        async def get_backend_config(backend_name: str):
            return await self.config_endpoints.get_backend_config(backend_name)
        
        @self.app.post("/api/backends/{backend_name}/config")
        async def set_backend_config(backend_name: str, config: Dict[str, Any]):
            return await self.config_endpoints.set_backend_config(backend_name, config)
        
        @self.app.get("/api/config/package")
        async def get_package_config():
            return await self.config_endpoints.get_package_config()
        
        @self.app.post("/api/config/package")
        async def set_package_config(config: Dict[str, Any]):
            return await self.config_endpoints.set_package_config(config)
        
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
        
        # VFS endpoints
        @self.app.get("/api/vfs/statistics")
        async def get_vfs_statistics():
            return await self.vfs_endpoints.get_vfs_statistics()
        
        @self.app.get("/api/vfs/cache")
        async def get_vfs_cache():
            return await self.vfs_endpoints.get_vfs_cache()
        
        @self.app.get("/api/vfs/vector-index")
        async def get_vfs_vector_index():
            return await self.vfs_endpoints.get_vfs_vector_index()
        
        @self.app.get("/api/vfs/knowledge-base")
        async def get_vfs_knowledge_base():
            return await self.vfs_endpoints.get_vfs_knowledge_base()
        
        @self.app.get("/api/vfs/filesystem-metrics")
        async def get_vfs_filesystem_metrics():
            return await self.vfs_endpoints.get_vfs_filesystem_metrics()
        
        @self.app.get("/api/vfs/access-patterns")
        async def get_vfs_access_patterns():
            return await self.vfs_endpoints.get_vfs_access_patterns()
        
        @self.app.get("/api/vfs/resource-utilization")
        async def get_vfs_resource_utilization():
            return await self.vfs_endpoints.get_vfs_resource_utilization()
        
        # System endpoints
        @self.app.get("/api/metrics/{backend_name}")
        async def get_backend_metrics(backend_name: str):
            return await self.health_endpoints.get_backend_metrics(backend_name)
        
        @self.app.get("/api/insights")
        async def get_insights():
            return await self.health_endpoints.get_insights()
        
        @self.app.get("/api/logs")
        async def get_system_logs():
            return await self.health_endpoints.get_system_logs()
        
        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket):
            await self.websocket_handler.handle_websocket(websocket)
        
        logger.info("✓ API routes configured")
