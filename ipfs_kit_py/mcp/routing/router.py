"""
Optimized Data Routing API Router

This module provides API endpoints for the optimized data routing system:
- Content-aware backend selection for routing operations
- Cost-based routing options
- Geographic optimization
- Routing rules management
- Backend metrics management

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ipfs_kit_py.mcp.auth.models import User
from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
from ipfs_kit_py.mcp.rbac import require_permission, Permission
from ipfs_kit_py.mcp.routing.data_router import (
    DataRouter, RoutingRule, RoutingStrategy, RoutingPriority, 
    ContentCategory, BackendMetrics, validate_routing_rule
)

# Configure logging
logger = logging.getLogger(__name__)


# --- Pydantic Models for Request/Response ---

class BackendMetricsModel(BaseModel):
    """Model for backend metrics."""
    avg_latency_ms: float = Field(0.0, description="Average latency in milliseconds")
    success_rate: float = Field(1.0, description="Success rate (0.0-1.0)")
    throughput_mbps: float = Field(0.0, description="Throughput in Mbps")
    storage_cost_per_gb: float = Field(0.0, description="Storage cost per GB per month")
    retrieval_cost_per_gb: float = Field(0.0, description="Retrieval cost per GB")
    bandwidth_cost_per_gb: float = Field(0.0, description="Bandwidth cost per GB")
    total_stored_bytes: float = Field(0.0, description="Total bytes stored")
    total_retrieved_bytes: float = Field(0.0, description="Total bytes retrieved")
    region: str = Field("unknown", description="Geographic region")
    multi_region: bool = Field(False, description="Whether the backend spans multiple regions")
    uptime_percentage: float = Field(99.9, description="Uptime percentage")


class RoutingRuleModel(BaseModel):
    """Model for routing rule."""
    id: str = Field(..., description="Rule ID")
    name: str = Field(..., description="Rule name")
    content_categories: List[str] = Field(..., description="Content categories this rule applies to")
    content_patterns: List[str] = Field([], description="Content patterns to match")
    min_size_bytes: Optional[int] = Field(None, description="Minimum size in bytes")
    max_size_bytes: Optional[int] = Field(None, description="Maximum size in bytes")
    preferred_backends: List[str] = Field([], description="Preferred backends")
    excluded_backends: List[str] = Field([], description="Excluded backends")
    priority: str = Field("balanced", description="Routing priority")
    strategy: str = Field("balanced", description="Routing strategy")
    custom_factors: Dict[str, float] = Field({}, description="Custom factors for routing")
    active: bool = Field(True, description="Whether the rule is active")


class ClientLocationModel(BaseModel):
    """Model for client location."""
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")


class RoutingAnalysisRequest(BaseModel):
    """Request for routing analysis."""
    content_size: int = Field(..., description="Content size in bytes")
    content_type: str = Field("application/octet-stream", description="Content type")
    filename: Optional[str] = Field(None, description="Filename")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")
    client_location: Optional[ClientLocationModel] = Field(None, description="Client location")


class RouteContentRequest(BaseModel):
    """Request for routing content."""
    backend: Optional[str] = Field(None, description="Specific backend to use (bypasses routing)")
    strategy: Optional[str] = Field(None, description="Routing strategy")
    priority: Optional[str] = Field(None, description="Routing priority")
    client_location: Optional[ClientLocationModel] = Field(None, description="Client location")


# --- Router Creation ---

def create_routing_router(app, backend_manager, data_router: Optional[DataRouter] = None):
    """
    Create and configure the routing API router.
    
    Args:
        app: FastAPI application
        backend_manager: Storage backend manager
        data_router: Optional data router instance
    """
    # Create router if not provided
    if data_router is None:
        data_router = DataRouter(backend_manager)
    
    # Create router
    router = APIRouter(prefix="/api/v0/routing", tags=["routing"])
    
    # --- Add router endpoints ---
    
    @router.get("/status")
    async def get_routing_status(current_user: User = Depends(get_current_user)):
        """
        Get routing system status.
        
        Returns information about the routing system's configuration and status.
        """
        try:
            # Get metrics
            backend_metrics = data_router.get_all_backend_metrics()
            
            # Get rules
            routing_rules = data_router.list_routing_rules()
            
            return {
                "success": True,
                "status": "operational",
                "metrics_count": len(backend_metrics),
                "rules_count": len(routing_rules),
                "backends": list(backend_metrics.keys()),
                "strategies": [strategy.value for strategy in RoutingStrategy],
                "priorities": [priority.value for priority in RoutingPriority],
                "content_categories": [category.value for category in ContentCategory]
            }
        except Exception as e:
            logger.error(f"Error getting routing status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/analyze", summary="Analyze content routing")
    async def analyze_routing(
        request: RoutingAnalysisRequest,
        current_user: User = Depends(get_current_user)
    ):
        """
        Analyze how content would be routed.
        
        Provides an analysis of which backend would be selected for the content
        based on its characteristics and the current routing rules.
        """
        try:
            # Create dummy content of the right size
            content = b"x" * min(request.content_size, 1024)  # Use a small sample for analysis
            
            # Create metadata
            metadata = {
                "content_type": request.content_type,
                "size": request.content_size,  # Add real size to metadata
                "filename": request.filename,
                **request.metadata
            }
            
            # Convert client location if provided
            client_location = None
            if request.client_location:
                client_location = {
                    "lat": request.client_location.lat,
                    "lon": request.client_location.lon
                }
            
            # Get routing analysis
            analysis = data_router.get_routing_analysis(content, metadata, client_location)
            
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing routing: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/upload", summary="Upload with optimized routing")
    async def route_upload(
        file: UploadFile = File(...),
        metadata: str = Form("{}"),
        routing: str = Form("{}"),
        current_user: User = Depends(get_current_user)
    ):
        """
        Upload content with optimized routing.
        
        Routes the uploaded file to the optimal backend based on its characteristics.
        """
        try:
            # Parse metadata and routing options
            metadata_dict = json.loads(metadata)
            routing_dict = json.loads(routing)
            
            # Add filename to metadata
            metadata_dict["filename"] = file.filename
            metadata_dict["content_type"] = file.content_type or "application/octet-stream"
            
            # Get routing options
            backend = routing_dict.get("backend")
            
            # Convert strategy and priority
            strategy = None
            if "strategy" in routing_dict:
                try:
                    strategy = RoutingStrategy(routing_dict["strategy"])
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid routing strategy: {routing_dict['strategy']}"
                    )
            
            priority = None
            if "priority" in routing_dict:
                try:
                    priority = RoutingPriority(routing_dict["priority"])
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid routing priority: {routing_dict['priority']}"
                    )
            
            # Convert client location if provided
            client_location = None
            if "client_location" in routing_dict:
                loc = routing_dict["client_location"]
                if isinstance(loc, dict) and "lat" in loc and "lon" in loc:
                    client_location = {
                        "lat": float(loc["lat"]),
                        "lon": float(loc["lon"])
                    }
            
            # Read file content
            content = await file.read()
            
            # If specific backend is requested, bypass routing
            if backend:
                # Validate backend exists
                if backend_manager and not backend_manager.get_backend(backend):
                    raise HTTPException(status_code=404, detail=f"Backend '{backend}' not found")
                
                # Store directly to specified backend
                if backend_manager:
                    backend_instance = backend_manager.get_backend(backend)
                    result = await backend_instance.add_content(content, metadata_dict)
                    
                    # Add routing info
                    result["router_info"] = {
                        "selected_backend": backend,
                        "routing_strategy": "manual",
                        "content_analysis": data_router.content_analyzer.analyze(content, metadata_dict)
                    }
                    
                    return result
                else:
                    raise HTTPException(status_code=500, detail="Backend manager not available")
            else:
                # Use the router
                result = await data_router.route_content(
                    content, metadata_dict, strategy, priority, client_location
                )
                
                if not result.get("success", False):
                    raise HTTPException(
                        status_code=500,
                        detail=result.get("error", "Failed to route content")
                    )
                
                return result
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in metadata or routing options")
        except Exception as e:
            logger.error(f"Error routing upload: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Rule Management ---
    
    @router.get("/rules", summary="List routing rules")
    async def list_routing_rules(current_user: User = Depends(get_current_user)):
        """
        List all routing rules.
        """
        try:
            rules = data_router.list_routing_rules()
            return {
                "success": True,
                "rules": [rule.to_dict() for rule in rules]
            }
        except Exception as e:
            logger.error(f"Error listing routing rules: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/rules/{rule_id}", summary="Get routing rule")
    async def get_routing_rule(
        rule_id: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Get a routing rule by ID.
        """
        try:
            rule = data_router.get_routing_rule(rule_id)
            if not rule:
                raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
            
            return {
                "success": True,
                "rule": rule.to_dict()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting routing rule: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/rules", summary="Create routing rule")
    async def create_routing_rule(
        rule: RoutingRuleModel,
        current_user: User = Depends(get_admin_user)
    ):
        """
        Create a new routing rule.
        
        Requires admin privileges.
        """
        try:
            # Validate rule
            rule_dict = rule.dict()
            valid, error = validate_routing_rule(rule_dict)
            if not valid:
                raise HTTPException(status_code=400, detail=error)
            
            # Create rule object
            routing_rule = RoutingRule.from_dict(rule_dict)
            
            # Add rule
            rule_id = data_router.add_routing_rule(routing_rule)
            
            return {
                "success": True,
                "rule_id": rule_id,
                "message": f"Rule '{rule.name}' created successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating routing rule: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/rules/{rule_id}", summary="Update routing rule")
    async def update_routing_rule(
        rule_id: str,
        rule: RoutingRuleModel,
        current_user: User = Depends(get_admin_user)
    ):
        """
        Update an existing routing rule.
        
        Requires admin privileges.
        """
        try:
            # Check if rule exists
            existing_rule = data_router.get_routing_rule(rule_id)
            if not existing_rule:
                raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
            
            # Validate rule
            rule_dict = rule.dict()
            valid, error = validate_routing_rule(rule_dict)
            if not valid:
                raise HTTPException(status_code=400, detail=error)
            
            # Create rule object
            routing_rule = RoutingRule.from_dict(rule_dict)
            
            # Update rule
            success = data_router.update_routing_rule(rule_id, routing_rule)
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to update rule '{rule_id}'")
            
            return {
                "success": True,
                "message": f"Rule '{rule.name}' updated successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating routing rule: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/rules/{rule_id}", summary="Delete routing rule")
    async def delete_routing_rule(
        rule_id: str,
        current_user: User = Depends(get_admin_user)
    ):
        """
        Delete a routing rule.
        
        Requires admin privileges.
        """
        try:
            # Check if rule exists
            existing_rule = data_router.get_routing_rule(rule_id)
            if not existing_rule:
                raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
            
            # Delete rule
            success = data_router.delete_routing_rule(rule_id)
            if not success:
                raise HTTPException(status_code=500, detail=f"Failed to delete rule '{rule_id}'")
            
            return {
                "success": True,
                "message": f"Rule '{rule_id}' deleted successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting routing rule: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Backend Metrics Management ---
    
    @router.get("/metrics", summary="Get backend metrics")
    async def get_backend_metrics(current_user: User = Depends(get_current_user)):
        """
        Get metrics for all backends.
        """
        try:
            metrics = data_router.get_all_backend_metrics()
            return {
                "success": True,
                "metrics": {name: metrics.to_dict() for name, metrics in metrics.items()}
            }
        except Exception as e:
            logger.error(f"Error getting backend metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/metrics/{backend_name}", summary="Get backend metrics")
    async def get_backend_metrics_by_name(
        backend_name: str,
        current_user: User = Depends(get_current_user)
    ):
        """
        Get metrics for a specific backend.
        """
        try:
            metrics = data_router.get_backend_metrics(backend_name)
            if not metrics:
                raise HTTPException(status_code=404, detail=f"No metrics found for backend '{backend_name}'")
            
            return {
                "success": True,
                "metrics": metrics.to_dict()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting backend metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/metrics/{backend_name}", summary="Update backend metrics")
    async def update_backend_metrics(
        backend_name: str,
        metrics: BackendMetricsModel,
        current_user: User = Depends(get_admin_user)
    ):
        """
        Update metrics for a backend.
        
        Requires admin privileges.
        """
        try:
            # Check if backend exists if backend manager is available
            if backend_manager and not backend_manager.get_backend(backend_name):
                raise HTTPException(status_code=404, detail=f"Backend '{backend_name}' not found")
            
            # Convert to BackendMetrics object
            backend_metrics = BackendMetrics(
                avg_latency_ms=metrics.avg_latency_ms,
                success_rate=metrics.success_rate,
                throughput_mbps=metrics.throughput_mbps,
                storage_cost_per_gb=metrics.storage_cost_per_gb,
                retrieval_cost_per_gb=metrics.retrieval_cost_per_gb,
                bandwidth_cost_per_gb=metrics.bandwidth_cost_per_gb,
                total_stored_bytes=metrics.total_stored_bytes,
                total_retrieved_bytes=metrics.total_retrieved_bytes,
                region=metrics.region,
                multi_region=metrics.multi_region,
                uptime_percentage=metrics.uptime_percentage
            )
            
            # Update metrics
            data_router.update_backend_metrics(backend_name, backend_metrics)
            
            return {
                "success": True,
                "message": f"Metrics for backend '{backend_name}' updated successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating backend metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/metrics/collect", summary="Collect backend metrics")
    async def collect_backend_metrics(current_user: User = Depends(get_admin_user)):
        """
        Collect metrics from all available backends.
        
        This endpoint triggers automatic collection of metrics from all backends.
        Requires admin privileges.
        """
        try:
            # Collect metrics
            await data_router.collect_backend_metrics()
            
            return {
                "success": True,
                "message": "Backend metrics collected successfully"
            }
        except Exception as e:
            logger.error(f"Error collecting backend metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # --- Category Info ---
    
    @router.get("/categories", summary="List content categories")
    async def list_content_categories(current_user: User = Depends(get_current_user)):
        """
        List all available content categories.
        """
        try:
            return {
                "success": True,
                "categories": [
                    {
                        "id": category.value,
                        "name": category.name
                    }
                    for category in ContentCategory
                ]
            }
        except Exception as e:
            logger.error(f"Error listing content categories: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/strategies", summary="List routing strategies")
    async def list_routing_strategies(current_user: User = Depends(get_current_user)):
        """
        List all available routing strategies.
        """
        try:
            return {
                "success": True,
                "strategies": [
                    {
                        "id": strategy.value,
                        "name": strategy.name
                    }
                    for strategy in RoutingStrategy
                ]
            }
        except Exception as e:
            logger.error(f"Error listing routing strategies: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/priorities", summary="List routing priorities")
    async def list_routing_priorities(current_user: User = Depends(get_current_user)):
        """
        List all available routing priorities.
        """
        try:
            return {
                "success": True,
                "priorities": [
                    {
                        "id": priority.value,
                        "name": priority.name
                    }
                    for priority in RoutingPriority
                ]
            }
        except Exception as e:
            logger.error(f"Error listing routing priorities: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Register router with app
    app.include_router(router)
    logger.info("Registered routing API router")
    
    return data_router