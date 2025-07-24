"""
Replication Management API for IPFS Kit Dashboard
Enhanced API endpoints for managing pin replication across storage backends
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .replication_manager import ReplicationManager, BackendType, ReplicationPolicy

logger = logging.getLogger(__name__)


class ReplicationRequest(BaseModel):
    """Request model for replication operations."""
    action: str = Field(..., description="Action to perform")
    cid: Optional[str] = Field(None, description="Content ID for pin-specific operations")
    backend_name: Optional[str] = Field(None, description="Target backend name")
    settings: Optional[Dict[str, Any]] = Field(None, description="Settings to update")
    backend_config: Optional[Dict[str, Any]] = Field(None, description="Backend configuration")
    target_replicas: Optional[int] = Field(None, description="Target number of replicas")
    priority: Optional[int] = Field(1, description="Replication priority")
    export_format: Optional[str] = Field("json", description="Export format")
    import_file: Optional[str] = Field(None, description="Import file path")


class ReplicationSettingsResponse(BaseModel):
    """Response model for replication settings."""
    success: bool
    settings: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BackendResponse(BaseModel):
    """Response model for backend operations."""
    success: bool
    backends: Optional[List[Dict[str, Any]]] = None
    backend: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ReplicationStatusResponse(BaseModel):
    """Response model for replication status."""
    success: bool
    summary: Optional[Dict[str, Any]] = None
    storage_usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ReplicationAPI:
    """API for replication management operations."""
    
    def __init__(self, replication_manager: ReplicationManager):
        self.replication_manager = replication_manager
        self.router = APIRouter(prefix="/api/replication", tags=["replication"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes for replication operations."""
        
        @self.router.get("/status", response_model=ReplicationStatusResponse)
        async def get_replication_status():
            """Get overall replication status and statistics."""
            try:
                result = await self.replication_manager.get_replication_status()
                return ReplicationStatusResponse(**result)
            except Exception as e:
                logger.error(f"Error getting replication status: {e}")
                return ReplicationStatusResponse(success=False, error=str(e))
        
        @self.router.get("/settings", response_model=ReplicationSettingsResponse)
        async def get_replication_settings():
            """Get current replication settings."""
            try:
                result = await self.replication_manager.get_replication_settings()
                return ReplicationSettingsResponse(**result)
            except Exception as e:
                logger.error(f"Error getting replication settings: {e}")
                return ReplicationSettingsResponse(success=False, error=str(e))
        
        @self.router.post("/settings", response_model=ReplicationSettingsResponse)
        async def update_replication_settings(request: ReplicationRequest):
            """Update replication settings."""
            try:
                if not request.settings:
                    return ReplicationSettingsResponse(
                        success=False, 
                        error="Settings data is required"
                    )
                
                result = await self.replication_manager.update_replication_settings(request.settings)
                return ReplicationSettingsResponse(**result)
            except Exception as e:
                logger.error(f"Error updating replication settings: {e}")
                return ReplicationSettingsResponse(success=False, error=str(e))
        
        @self.router.get("/backends", response_model=BackendResponse)
        async def list_storage_backends():
            """List all configured storage backends."""
            try:
                result = await self.replication_manager.list_storage_backends()
                return BackendResponse(**result)
            except Exception as e:
                logger.error(f"Error listing storage backends: {e}")
                return BackendResponse(success=False, error=str(e))
        
        @self.router.post("/backends", response_model=BackendResponse)
        async def add_storage_backend(request: ReplicationRequest):
            """Add a new storage backend."""
            try:
                if not request.backend_config:
                    return BackendResponse(
                        success=False,
                        error="Backend configuration is required"
                    )
                
                result = await self.replication_manager.add_storage_backend(request.backend_config)
                return BackendResponse(**result)
            except Exception as e:
                logger.error(f"Error adding storage backend: {e}")
                return BackendResponse(success=False, error=str(e))
        
        @self.router.put("/backends/{backend_name}", response_model=BackendResponse)
        async def update_storage_backend(backend_name: str, request: ReplicationRequest):
            """Update an existing storage backend."""
            try:
                if not request.backend_config:
                    return BackendResponse(
                        success=False,
                        error="Backend configuration updates are required"
                    )
                
                result = await self.replication_manager.update_storage_backend(
                    backend_name, request.backend_config
                )
                return BackendResponse(**result)
            except Exception as e:
                logger.error(f"Error updating storage backend: {e}")
                return BackendResponse(success=False, error=str(e))
        
        @self.router.delete("/backends/{backend_name}", response_model=BackendResponse)
        async def remove_storage_backend(backend_name: str):
            """Remove a storage backend."""
            try:
                result = await self.replication_manager.remove_storage_backend(backend_name)
                return BackendResponse(**result)
            except Exception as e:
                logger.error(f"Error removing storage backend: {e}")
                return BackendResponse(success=False, error=str(e))
        
        @self.router.post("/pins/{cid}/register")
        async def register_pin_for_replication(cid: str, request: ReplicationRequest):
            """Register a pin for replication management."""
            try:
                result = await self.replication_manager.register_pin_for_replication(
                    cid=cid,
                    target_replicas=request.target_replicas,
                    priority=request.priority or 1
                )
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error registering pin for replication: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.get("/pins/{cid}/status")
        async def get_pin_replication_status(cid: str):
            """Get replication status for a specific pin."""
            try:
                result = await self.replication_manager.get_pin_replication_status(cid)
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error getting pin replication status: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.post("/pins/{cid}/replicate")
        async def replicate_pin_to_backend(cid: str, request: ReplicationRequest):
            """Replicate a specific pin to a target backend."""
            try:
                if not request.backend_name:
                    return JSONResponse(
                        content={"success": False, "error": "Backend name is required"},
                        status_code=400
                    )
                
                result = await self.replication_manager.replicate_pin_to_backend(
                    cid, request.backend_name
                )
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error replicating pin to backend: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.post("/operation")
        async def perform_replication_operation(request: ReplicationRequest):
            """Perform general replication operations."""
            try:
                if request.action == "start_monitoring":
                    result = await self.replication_manager.start_monitoring()
                elif request.action == "stop_monitoring":
                    result = await self.replication_manager.stop_monitoring()
                elif request.action == "get_status":
                    result = await self.replication_manager.get_replication_status()
                elif request.action == "get_settings":
                    result = await self.replication_manager.get_replication_settings()
                elif request.action == "update_settings" and request.settings:
                    result = await self.replication_manager.update_replication_settings(request.settings)
                else:
                    result = {"success": False, "error": f"Unknown action: {request.action}"}
                
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error in replication operation: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.post("/backends/{backend_name}/export")
        async def export_backend_pins(backend_name: str, request: ReplicationRequest):
            """Export pins from a specific backend."""
            try:
                export_format = request.export_format or "json"
                result = await self.replication_manager.export_backend_pins(
                    backend_name, export_format
                )
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error exporting backend pins: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.post("/backends/{backend_name}/import")
        async def import_backend_pins(backend_name: str, request: ReplicationRequest):
            """Import pins to a specific backend."""
            try:
                if not request.import_file:
                    return JSONResponse(
                        content={"success": False, "error": "Import file path is required"},
                        status_code=400
                    )
                
                result = await self.replication_manager.import_backend_pins(
                    backend_name, request.import_file
                )
                return JSONResponse(content=result)
            except Exception as e:
                logger.error(f"Error importing backend pins: {e}")
                return JSONResponse(
                    content={"success": False, "error": str(e)},
                    status_code=500
                )
        
        @self.router.get("/health")
        async def get_replication_health():
            """Get replication health status."""
            try:
                status = await self.replication_manager.get_replication_status()
                
                # Determine overall health
                if status["success"]:
                    summary = status["summary"]
                    total_pins = summary["total_pins"]
                    healthy_ratio = summary["replication_ratio"]
                    failed_pins = summary["failed_pins"]
                    
                    if total_pins == 0:
                        health_status = "no_data"
                    elif healthy_ratio >= 0.9 and failed_pins == 0:
                        health_status = "healthy"
                    elif healthy_ratio >= 0.7:
                        health_status = "warning"
                    else:
                        health_status = "critical"
                    
                    health_data = {
                        "success": True,
                        "health_status": health_status,
                        "replication_ratio": healthy_ratio,
                        "total_pins": total_pins,
                        "failed_pins": failed_pins,
                        "monitoring_active": summary["monitoring_active"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    health_data = {
                        "success": False,
                        "health_status": "error",
                        "error": status.get("error", "Unknown error")
                    }
                
                return JSONResponse(content=health_data)
            except Exception as e:
                logger.error(f"Error getting replication health: {e}")
                return JSONResponse(
                    content={
                        "success": False,
                        "health_status": "error",
                        "error": str(e)
                    },
                    status_code=500
                )


def create_replication_api(replication_manager: ReplicationManager) -> ReplicationAPI:
    """Create and configure the replication API."""
    return ReplicationAPI(replication_manager)
