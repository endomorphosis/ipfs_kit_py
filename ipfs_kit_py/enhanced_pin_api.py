"""
Enhanced Pin Metadata API for IPFS Kit

This module provides FastAPI endpoints for the enhanced pin metadata index
that integrates with ipfs_kit_py's virtual filesystem and storage management.

Endpoints:
- GET /api/v0/enhanced-pins/status - Get index status and capabilities
- GET /api/v0/enhanced-pins/metrics - Get comprehensive metrics  
- GET /api/v0/enhanced-pins/vfs - Get VFS analytics
- GET /api/v0/enhanced-pins/pins - List pins with details
- GET /api/v0/enhanced-pins/track/{cid} - Track specific pin
- GET /api/v0/enhanced-pins/analytics - Get storage analytics
- POST /api/v0/enhanced-pins/record - Record pin access
"""

import logging
import time
from typing import Any, Dict, List, Optional

import fastapi
from fastapi import HTTPException, Path, Query
from pydantic import BaseModel

# Import enhanced pin index
try:
    from ipfs_kit_py.enhanced_pin_index import (
        get_global_enhanced_pin_index, 
        get_cli_pin_metrics,
        EnhancedPinMetadataIndex
    )
    ENHANCED_PIN_INDEX_AVAILABLE = True
except ImportError:
    ENHANCED_PIN_INDEX_AVAILABLE = False

logger = logging.getLogger(__name__)

# Create router
enhanced_pin_router = fastapi.APIRouter(prefix="/api/v0/enhanced-pins", tags=["enhanced_pins"])

# Pydantic models for request/response
class PinAccessRequest(BaseModel):
    cid: str
    access_pattern: Optional[str] = "unknown"
    vfs_path: Optional[str] = None
    tier: Optional[str] = "ipfs"
    size_bytes: Optional[int] = None
    mount_point: Optional[str] = None
    pin_type: Optional[str] = "file"
    pin_name: Optional[str] = None
    storage_tiers: Optional[List[str]] = None
    replication_factor: Optional[int] = 1

class PinDetailsResponse(BaseModel):
    cid: str
    size_bytes: int
    type: str
    name: Optional[str]
    vfs_path: Optional[str]
    mount_point: Optional[str]
    is_directory: bool
    primary_tier: str
    storage_tiers: List[str]
    replication_factor: int
    access_count: int
    last_accessed: Optional[float]
    hotness_score: float
    access_pattern: str
    integrity_status: str
    predicted_access_time: Optional[float]

# Global index instance
_enhanced_pin_index = None

def get_enhanced_pin_index():
    """Get or create the global enhanced pin index."""
    global _enhanced_pin_index
    
    if not ENHANCED_PIN_INDEX_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Enhanced pin index not available. Install with: pip install duckdb pandas pyarrow"
        )
    
    if _enhanced_pin_index is None:
        try:
            _enhanced_pin_index = get_global_enhanced_pin_index(
                enable_analytics=True,
                enable_predictions=True
            )
        except Exception as e:
            logger.error(f"Failed to initialize enhanced pin index: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize enhanced pin index: {e}"
            )
    
    return _enhanced_pin_index

@enhanced_pin_router.get("/status", response_model=Dict[str, Any])
async def get_enhanced_pin_status():
    """
    Get the status and capabilities of the enhanced pin metadata index.
    
    Returns:
        Dictionary containing status information, capabilities, and configuration
    """
    if not ENHANCED_PIN_INDEX_AVAILABLE:
        return {
            "success": False,
            "available": False,
            "error": "Enhanced pin index not available",
            "install_command": "pip install duckdb pandas pyarrow"
        }
    
    try:
        index = get_enhanced_pin_index()
        performance = index.get_performance_metrics()
        
        return {
            "success": True,
            "available": True,
            "data_directory": index.data_dir,
            "total_pins": len(index.pin_metadata),
            "capabilities": performance.get("capabilities", {}),
            "background_services": performance.get("background_services", {}),
            "storage_info": performance.get("storage_info", {}),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting enhanced pin status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/metrics", response_model=Dict[str, Any])
async def get_enhanced_pin_metrics():
    """
    Get comprehensive metrics from the enhanced pin metadata index.
    
    Returns:
        Comprehensive metrics including traffic, VFS, and performance data
    """
    try:
        if not ENHANCED_PIN_INDEX_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Enhanced pin index not available"
            )
        
        metrics = get_cli_pin_metrics()
        return {
            "success": True,
            "metrics": metrics,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting enhanced pin metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/vfs", response_model=Dict[str, Any])
async def get_vfs_analytics():
    """
    Get VFS-specific analytics from the enhanced pin metadata index.
    
    Returns:
        VFS analytics including mount points, operations, and path-based metrics
    """
    try:
        index = get_enhanced_pin_index()
        
        if not hasattr(index, 'get_vfs_analytics'):
            raise HTTPException(
                status_code=503,
                detail="VFS analytics not available in this index implementation"
            )
        
        vfs_analytics = index.get_vfs_analytics()
        return {
            "success": True,
            "vfs_analytics": vfs_analytics,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting VFS analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/pins", response_model=Dict[str, Any])
async def list_enhanced_pins(
    limit: int = Query(20, ge=1, le=1000, description="Maximum number of pins to return"),
    offset: int = Query(0, ge=0, description="Number of pins to skip"),
    tier: Optional[str] = Query(None, description="Filter by storage tier"),
    pattern: Optional[str] = Query(None, description="Filter by access pattern"),
    mount: Optional[str] = Query(None, description="Filter by mount point")
):
    """
    List pins with detailed information from the enhanced metadata index.
    
    Args:
        limit: Maximum number of pins to return (1-1000)
        offset: Number of pins to skip for pagination
        tier: Filter by storage tier (e.g., 'ssd', 'hdd', 'ipfs')
        pattern: Filter by access pattern (e.g., 'sequential', 'random')
        mount: Filter by mount point (e.g., '/documents', '/media')
    
    Returns:
        List of pins with comprehensive metadata
    """
    try:
        index = get_enhanced_pin_index()
        
        # Get all pins
        all_pins = list(index.pin_metadata.values())
        
        # Apply filters
        filtered_pins = all_pins
        
        if tier:
            filtered_pins = [pin for pin in filtered_pins if pin.primary_tier == tier]
        
        if pattern:
            filtered_pins = [pin for pin in filtered_pins if pin.access_pattern == pattern]
        
        if mount:
            filtered_pins = [pin for pin in filtered_pins if pin.mount_point == mount]
        
        # Sort by hotness score (descending)
        filtered_pins.sort(key=lambda x: x.hotness_score, reverse=True)
        
        # Apply pagination
        paginated_pins = filtered_pins[offset:offset + limit]
        
        # Convert to response format
        pins_data = []
        for pin in paginated_pins:
            pins_data.append({
                "cid": pin.cid,
                "size_bytes": pin.size_bytes,
                "type": pin.type,
                "name": pin.name,
                "vfs_path": pin.vfs_path,
                "mount_point": pin.mount_point,
                "is_directory": pin.is_directory,
                "primary_tier": pin.primary_tier,
                "storage_tiers": pin.storage_tiers,
                "replication_factor": pin.replication_factor,
                "access_count": pin.access_count,
                "last_accessed": pin.last_accessed,
                "hotness_score": pin.hotness_score,
                "access_pattern": pin.access_pattern,
                "integrity_status": pin.integrity_status,
                "predicted_access_time": pin.predicted_access_time
            })
        
        return {
            "success": True,
            "pins": pins_data,
            "pagination": {
                "total": len(filtered_pins),
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < len(filtered_pins)
            },
            "filters": {
                "tier": tier,
                "pattern": pattern,
                "mount": mount
            },
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error listing enhanced pins: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/track/{cid}", response_model=Dict[str, Any])
async def track_pin(cid: str = Path(..., description="Content ID to track")):
    """
    Track a specific pin and return detailed information.
    
    This endpoint also records the tracking access for analytics.
    
    Args:
        cid: Content ID of the pin to track
    
    Returns:
        Detailed pin information and tracking status
    """
    try:
        index = get_enhanced_pin_index()
        
        # Get pin details
        pin_details = index.get_pin_details(cid)
        
        if not pin_details:
            raise HTTPException(
                status_code=404,
                detail=f"Pin {cid} not found in index"
            )
        
        # Record this access for tracking
        index.record_enhanced_access(cid, access_pattern="api_track")
        
        return {
            "success": True,
            "pin_details": {
                "cid": pin_details.cid,
                "size_bytes": pin_details.size_bytes,
                "type": pin_details.type,
                "name": pin_details.name,
                "vfs_path": pin_details.vfs_path,
                "mount_point": pin_details.mount_point,
                "is_directory": pin_details.is_directory,
                "primary_tier": pin_details.primary_tier,
                "storage_tiers": pin_details.storage_tiers,
                "replication_factor": pin_details.replication_factor,
                "access_count": pin_details.access_count,
                "last_accessed": pin_details.last_accessed,
                "hotness_score": pin_details.hotness_score,
                "access_pattern": pin_details.access_pattern,
                "integrity_status": pin_details.integrity_status,
                "predicted_access_time": pin_details.predicted_access_time
            },
            "tracking_recorded": True,
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking pin {cid}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/analytics", response_model=Dict[str, Any])
async def get_storage_analytics():
    """
    Get comprehensive storage analytics and recommendations.
    
    Returns:
        Storage analytics including tier distribution, hot pins, recommendations
    """
    try:
        index = get_enhanced_pin_index()
        
        if not hasattr(index, 'get_comprehensive_metrics'):
            raise HTTPException(
                status_code=503,
                detail="Comprehensive analytics not available in this index implementation"
            )
        
        metrics = index.get_comprehensive_metrics()
        
        return {
            "success": True,
            "analytics": {
                "hot_pins": metrics.hot_pins[:10],  # Top 10
                "largest_pins": metrics.largest_pins[:10],  # Top 10
                "storage_recommendations": metrics.storage_recommendations,
                "tier_distribution": metrics.tier_distribution,
                "access_patterns": metrics.access_patterns,
                "integrity_summary": metrics.integrity_summary
            },
            "timestamp": time.time()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting storage analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.post("/record", response_model=Dict[str, Any])
async def record_pin_access(request: PinAccessRequest):
    """
    Record a pin access event for analytics and tracking.
    
    This endpoint allows external systems to record pin access events
    for comprehensive analytics and predictive modeling.
    
    Args:
        request: Pin access information to record
    
    Returns:
        Success status and updated pin information
    """
    try:
        index = get_enhanced_pin_index()
        
        # Record the access
        index.record_enhanced_access(
            cid=request.cid,
            access_pattern=request.access_pattern,
            vfs_path=request.vfs_path,
            tier=request.tier,
            size_bytes=request.size_bytes,
            mount_point=request.mount_point,
            pin_type=request.pin_type,
            pin_name=request.pin_name,
            storage_tiers=request.storage_tiers,
            replication_factor=request.replication_factor
        )
        
        # Get updated pin details
        pin_details = index.get_pin_details(request.cid)
        
        return {
            "success": True,
            "message": f"Recorded access for pin {request.cid}",
            "pin_details": {
                "cid": pin_details.cid,
                "access_count": pin_details.access_count,
                "hotness_score": pin_details.hotness_score,
                "last_accessed": pin_details.last_accessed
            } if pin_details else None,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error recording pin access: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@enhanced_pin_router.get("/health", response_model=Dict[str, Any])
async def enhanced_pin_health():
    """
    Health check endpoint for the enhanced pin metadata system.
    
    Returns:
        Health status and basic system information
    """
    try:
        if not ENHANCED_PIN_INDEX_AVAILABLE:
            return {
                "success": False,
                "healthy": False,
                "error": "Enhanced pin index not available",
                "timestamp": time.time()
            }
        
        index = get_enhanced_pin_index()
        total_pins = len(index.pin_metadata)
        
        return {
            "success": True,
            "healthy": True,
            "total_pins": total_pins,
            "data_directory": index.data_dir,
            "capabilities": {
                "analytics": index.enable_analytics,
                "predictions": index.enable_predictions,
                "vfs_integration": hasattr(index, 'ipfs_filesystem') and index.ipfs_filesystem is not None,
                "journal_sync": hasattr(index, 'journal') and index.journal is not None
            },
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Enhanced pin health check failed: {e}")
        return {
            "success": False,
            "healthy": False,
            "error": str(e),
            "timestamp": time.time()
        }
