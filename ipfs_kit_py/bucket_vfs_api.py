"""
Enhanced Dashboard API with Multi-Bucket VFS Support

This module extends the existing dashboard API to include comprehensive
bucket virtual filesystem management with S3-like semantics, IPLD
compatibility, and cross-platform data export capabilities.
"""

import anyio
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

try:
    from fastapi import APIRouter, HTTPException, Query, Body
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
from .error import create_result_dict, handle_error

logger = logging.getLogger(__name__)


# Pydantic models for API requests
if FASTAPI_AVAILABLE:
    class CreateBucketRequest(BaseModel):
        """Request model for creating a bucket."""
        name: str
        bucket_type: str = "general"
        vfs_structure: str = "hybrid"
        metadata: Optional[Dict[str, Any]] = None
    
    class AddFileRequest(BaseModel):
        """Request model for adding a file to a bucket."""
        bucket_name: str
        file_path: str
        content: str
        metadata: Optional[Dict[str, Any]] = None
    
    class CrossBucketQueryRequest(BaseModel):
        """Request model for cross-bucket SQL queries."""
        sql_query: str
        bucket_filter: Optional[List[str]] = None


class BucketVFSEndpoints:
    """API endpoints for bucket virtual filesystem management."""
    
    def __init__(self):
        """Initialize bucket VFS endpoints."""
        self.bucket_manager = None
        
        if FASTAPI_AVAILABLE:
            self.router = APIRouter(prefix="/api/bucket-vfs", tags=["bucket-vfs"])
            self._setup_routes()
        
        # Initialize bucket manager lazily
        self._initialize_bucket_manager()
    
    def _initialize_bucket_manager(self):
        """Initialize bucket VFS manager."""
        try:
            self.bucket_manager = get_global_bucket_manager(
                storage_path="/tmp/ipfs_kit_buckets",
                enable_parquet_export=True,
                enable_duckdb_integration=True
            )
            logger.info("✅ Bucket VFS Manager initialized for API endpoints")
        except Exception as e:
            logger.error(f"Failed to initialize bucket VFS manager: {e}")
            self.bucket_manager = None
    
    def _setup_routes(self):
        """Setup FastAPI routes for bucket VFS operations."""
        if not FASTAPI_AVAILABLE:
            return
        
        @self.router.get("/buckets")
        async def list_buckets():
            """List all available buckets."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                result = await self.bucket_manager.list_buckets()
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=500, detail=result.get("error"))
                    
            except Exception as e:
                logger.error(f"Error listing buckets: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/buckets")
        async def create_bucket(request: CreateBucketRequest):
            """Create a new bucket."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                # Validate enum values
                try:
                    bucket_type_enum = BucketType(request.bucket_type)
                    vfs_structure_enum = VFSStructureType(request.vfs_structure)
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")
                
                result = await self.bucket_manager.create_bucket(
                    bucket_name=request.name,
                    bucket_type=bucket_type_enum,
                    vfs_structure=vfs_structure_enum,
                    metadata=request.metadata
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=400, detail=result.get("error"))
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error creating bucket: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.delete("/buckets/{bucket_name}")
        async def delete_bucket(bucket_name: str, force: bool = Query(False)):
            """Delete a bucket."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                result = await self.bucket_manager.delete_bucket(bucket_name, force=force)
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=400, detail=result.get("error"))
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error deleting bucket: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/buckets/{bucket_name}")
        async def get_bucket_info(bucket_name: str):
            """Get detailed information about a bucket."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                bucket = await self.bucket_manager.get_bucket(bucket_name)
                if not bucket:
                    raise HTTPException(status_code=404, detail=f"Bucket '{bucket_name}' not found")
                
                # Collect bucket information
                bucket_info = {
                    "name": bucket.name,
                    "type": bucket.bucket_type.value,
                    "vfs_structure": bucket.vfs_structure.value,
                    "created_at": bucket.created_at,
                    "root_cid": bucket.root_cid,
                    "metadata": bucket.metadata,
                    "file_count": await bucket.get_file_count(),
                    "total_size": await bucket.get_total_size(),
                    "last_modified": await bucket.get_last_modified(),
                    "components": {
                        "knowledge_graph": bucket.knowledge_graph is not None,
                        "vector_index": bucket.vector_index is not None,
                        "parquet_bridge": bucket.parquet_bridge is not None,
                        "car_bridge": bucket.car_bridge is not None
                    },
                    "directory_structure": {
                        name: str(path) for name, path in bucket.dirs.items()
                    }
                }
                
                return {
                    "success": True,
                    "data": bucket_info,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting bucket info: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/buckets/{bucket_name}/files")
        async def add_file_to_bucket(bucket_name: str, request: AddFileRequest):
            """Add a file to a bucket."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                bucket = await self.bucket_manager.get_bucket(bucket_name)
                if not bucket:
                    raise HTTPException(status_code=404, detail=f"Bucket '{bucket_name}' not found")
                
                result = await bucket.add_file(
                    file_path=request.file_path,
                    content=request.content,
                    metadata=request.metadata
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=400, detail=result.get("error"))
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error adding file to bucket: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/buckets/{bucket_name}/export-car")
        async def export_bucket_to_car(bucket_name: str, include_indexes: bool = Query(True)):
            """Export bucket to CAR archive."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                result = await self.bucket_manager.export_bucket_to_car(
                    bucket_name=bucket_name,
                    include_indexes=include_indexes
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=400, detail=result.get("error"))
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error exporting bucket to CAR: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/query/cross-bucket")
        async def cross_bucket_query(request: CrossBucketQueryRequest):
            """Execute SQL query across multiple buckets."""
            try:
                if not self.bucket_manager:
                    raise HTTPException(status_code=503, detail="Bucket manager not available")
                
                if not self.bucket_manager.enable_duckdb_integration:
                    raise HTTPException(status_code=503, detail="DuckDB integration not available")
                
                result = await self.bucket_manager.cross_bucket_query(
                    sql_query=request.sql_query,
                    bucket_filter=request.bucket_filter
                )
                
                if result["success"]:
                    return {
                        "success": True,
                        "data": result["data"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                else:
                    raise HTTPException(status_code=400, detail=result.get("error"))
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error executing cross-bucket query: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/status")
        async def get_bucket_vfs_status():
            """Get overall bucket VFS system status."""
            try:
                if not self.bucket_manager:
                    return {
                        "success": False,
                        "error": "Bucket manager not available",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                
                # Get list of buckets
                buckets_result = await self.bucket_manager.list_buckets()
                
                status = {
                    "bucket_manager_available": True,
                    "duckdb_integration": self.bucket_manager.enable_duckdb_integration,
                    "parquet_export": self.bucket_manager.enable_parquet_export,
                    "storage_path": str(self.bucket_manager.storage_path),
                    "bucket_count": 0,
                    "total_files": 0,
                    "total_size": 0,
                    "bucket_types": {},
                    "vfs_structures": {}
                }
                
                if buckets_result["success"]:
                    buckets = buckets_result["data"]["buckets"]
                    status["bucket_count"] = len(buckets)
                    
                    for bucket in buckets:
                        # Aggregate statistics
                        status["total_files"] += bucket["file_count"]
                        status["total_size"] += bucket["size_bytes"]
                        
                        # Count bucket types
                        bucket_type = bucket["type"]
                        status["bucket_types"][bucket_type] = status["bucket_types"].get(bucket_type, 0) + 1
                        
                        # Count VFS structures
                        vfs_structure = bucket["vfs_structure"]
                        status["vfs_structures"][vfs_structure] = status["vfs_structures"].get(vfs_structure, 0) + 1
                
                return {
                    "success": True,
                    "data": status,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting bucket VFS status: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        @self.router.get("/bucket-types")
        async def get_bucket_types():
            """Get available bucket types and VFS structures."""
            try:
                return {
                    "success": True,
                    "data": {
                        "bucket_types": [
                            {"value": bt.value, "name": bt.name, "description": f"{bt.value.title()} bucket type"}
                            for bt in BucketType
                        ],
                        "vfs_structures": [
                            {"value": vs.value, "name": vs.name, "description": f"{vs.value.title()} filesystem structure"}
                            for vs in VFSStructureType
                        ]
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting bucket types: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    # Non-FastAPI methods for direct usage
    
    async def list_buckets_direct(self) -> Dict[str, Any]:
        """List buckets (direct method for non-FastAPI usage)."""
        try:
            if not self.bucket_manager:
                return create_result_dict("list_buckets", success=False, error="Bucket manager not available")
            
            return await self.bucket_manager.list_buckets()
            
        except Exception as e:
            result = create_result_dict("list_buckets", success=False)
            return handle_error(result, e, "list_buckets")
    
    async def create_bucket_direct(
        self,
        name: str,
        bucket_type: str = "general",
        vfs_structure: str = "hybrid",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create bucket (direct method for non-FastAPI usage)."""
        try:
            if not self.bucket_manager:
                return create_result_dict("create_bucket", success=False, error="Bucket manager not available")
            
            # Convert string enums
            try:
                bucket_type_enum = BucketType(bucket_type)
                vfs_structure_enum = VFSStructureType(vfs_structure)
            except ValueError as e:
                return create_result_dict("create_bucket", success=False, error=f"Invalid enum value: {e}")
            
            return await self.bucket_manager.create_bucket(
                bucket_name=name,
                bucket_type=bucket_type_enum,
                vfs_structure=vfs_structure_enum,
                metadata=metadata
            )
            
        except Exception as e:
            result = create_result_dict("create_bucket", success=False)
            return handle_error(result, e, "create_bucket")
    
    async def get_bucket_status_direct(self) -> Dict[str, Any]:
        """Get bucket VFS status (direct method for non-FastAPI usage)."""
        try:
            if not self.bucket_manager:
                return create_result_dict("bucket_status", success=False, error="Bucket manager not available")
            
            # Get basic statistics
            buckets_result = await self.bucket_manager.list_buckets()
            
            if not buckets_result["success"]:
                return buckets_result
            
            buckets = buckets_result["data"]["buckets"]
            
            status = {
                "available": True,
                "bucket_count": len(buckets),
                "total_files": sum(bucket["file_count"] for bucket in buckets),
                "total_size": sum(bucket["size_bytes"] for bucket in buckets),
                "duckdb_integration": self.bucket_manager.enable_duckdb_integration,
                "parquet_export": self.bucket_manager.enable_parquet_export,
                "storage_path": str(self.bucket_manager.storage_path)
            }
            
            return create_result_dict("bucket_status", success=True, data=status)
            
        except Exception as e:
            result = create_result_dict("bucket_status", success=False)
            return handle_error(result, e, "bucket_status")


# Global instance
_bucket_vfs_endpoints: Optional[BucketVFSEndpoints] = None


def get_bucket_vfs_endpoints() -> BucketVFSEndpoints:
    """Get or create global bucket VFS endpoints instance."""
    global _bucket_vfs_endpoints
    if _bucket_vfs_endpoints is None:
        _bucket_vfs_endpoints = BucketVFSEndpoints()
    return _bucket_vfs_endpoints


def get_bucket_vfs_router():
    """Get FastAPI router for bucket VFS endpoints."""
    endpoints = get_bucket_vfs_endpoints()
    return endpoints.router if FASTAPI_AVAILABLE else None
