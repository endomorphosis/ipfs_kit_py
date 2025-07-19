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
        self.vfs_observer = vfs_observer
        self.templates = templates
        self.websocket_manager = websocket_manager
        
        # Initialize endpoint handlers
        self.health_endpoints = HealthEndpoints(backend_monitor)
        self.config_endpoints = ConfigEndpoints(backend_monitor)
        self.vfs_endpoints = VFSEndpoints(backend_monitor, vfs_observer)
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
            return await self._safe_endpoint_call(
                self.config_endpoints.export_config,
                "export_config"
            )
        
        @self.app.post("/api/config/import")
        async def import_config(request: Request):
            import_data = await request.json()
            return await self._safe_endpoint_call(
                lambda: self.config_endpoints.import_config(import_data),
                "import_config"
            )
        
        # VFS and file management endpoints
        @self.app.get("/api/vfs/status")
        async def get_vfs_status():
            return await self._safe_endpoint_call(
                self.vfs_endpoints.get_vfs_status,
                "vfs_status"
            )
        
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
        
        # File Management Routes
        @self.app.get("/api/files/list", tags=["File Manager"])
        async def list_files_endpoint(path: str = "/"):
            """List files and directories in the specified path."""
            return await self._safe_endpoint_call(
                self._list_files,
                "list_files",
                path=path
            )

        @self.app.post("/api/files/create-folder", tags=["File Manager"])
        async def create_folder_endpoint(request: Request):
            """Create a new folder."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._create_folder,
                "create_folder",
                path=data.get("path", "/"),
                name=data.get("name")
            )

        @self.app.post("/api/files/delete", tags=["File Manager"])
        async def delete_file_endpoint(request: Request):
            """Delete a file or directory."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._delete_file,
                "delete_file",
                path=data.get("path")
            )

        @self.app.post("/api/files/rename", tags=["File Manager"])
        async def rename_file_endpoint(request: Request):
            """Rename a file or directory."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._rename_file,
                "rename_file",
                old_path=data.get("oldPath"),
                new_name=data.get("newName")
            )

        @self.app.post("/api/files/move", tags=["File Manager"])
        async def move_file_endpoint(request: Request):
            """Move a file or directory to a new location."""
            data = await request.json()
            return await self._safe_endpoint_call(
                self._move_item,
                "move_file",
                source_path=data.get("sourcePath"),
                target_path=data.get("targetPath")
            )

        @self.app.post("/api/files/upload", tags=["File Manager"])
        async def upload_file_endpoint(path: str = Form("/"), file: UploadFile = File(...)):
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
                self._download_file,
                "download_file",
                path=path
            )
            
            if result.get("success"):
                from fastapi.responses import Response
                return Response(
                    content=result["content"],
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={result['name']}"}
                )
            else:
                return JSONResponse(status_code=404, content=result)
        
        # Analytics and monitoring endpoints
        @self.app.get("/api/analytics/comprehensive")
        async def get_comprehensive_analytics():
            return await self._safe_endpoint_call(
                self._get_comprehensive_monitoring,
                "comprehensive_analytics"
            )
        
        @self.app.get("/api/analytics/files")
        async def get_file_analytics():
            return await self._safe_endpoint_call(
                self._get_file_stats,
                "file_analytics"
            )
        
        # WebSocket endpoint
        @self.app.websocket("/ws/{client_id}")
        async def websocket_endpoint(websocket: WebSocket, client_id: str):
            await self.websocket_handler.handle_connection(websocket, client_id)
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def _get_available_tools(self) -> Dict[str, Any]:
        """Get all available MCP tools with enhanced error handling."""
        try:
            tools = []
            if hasattr(self.backend_monitor, '_tools') and self.backend_monitor._tools:
                tools = self.backend_monitor._tools
            
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

    async def _get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data for the monitoring tab."""
        try:
            backend_health_task = self.backend_monitor.check_all_backends()
            vfs_stats_task = self.vfs_endpoints.get_vfs_statistics()
            file_stats_task = self._get_file_stats()
            
            backend_health, vfs_stats, file_stats = await asyncio.gather(
                backend_health_task,
                vfs_stats_task,
                file_stats_task,
                return_exceptions=True
            )
            
            return {
                "success": True,
                "backend_health": backend_health if not isinstance(backend_health, Exception) else {"error": str(backend_health)},
                "vfs_statistics": vfs_stats if not isinstance(vfs_stats, Exception) else {"error": str(vfs_stats)},
                "file_statistics": file_stats if not isinstance(file_stats, Exception) else {"error": str(file_stats)},
                "timestamp": self._get_current_timestamp()
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._get_current_timestamp()
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
