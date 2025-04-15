"""
Router API Module

This module provides the FastAPI routes for the Optimized Data Routing system,
allowing administrators to configure and interact with the routing system.

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import json
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, HTTPException, Depends, Header, File, UploadFile, Form, Body, Query, Path

from .data_router import DataRouter, RoutingStrategy, RoutingPriority, RoutingRule, ContentCategory
from .optimized_router import OptimizedDataRouter
from ..auth.models import User

# Configure logging
logger = logging.getLogger(__name__)

def create_routing_router(app, backend_manager, data_router):
    """
    Create and return the routing API router.
    
    Args:
        app: FastAPI application
        backend_manager: Backend manager
        data_router: Data router instance
        
    Returns:
        FastAPI router
    """
    router = APIRouter(prefix="/api/v0/routing", tags=["Routing"])
    
    # --- Status Endpoints ---
    
    @router.get("/status")
    async def get_router_status(current_user: User = Depends()):
        """
        Get the current status of the routing system.
        
        Returns information about the current configuration, registered backends,
        and metrics collection status.
        """
        try:
            # Get available backends
            available_backends = backend_manager.list_backends() if backend_manager else []
            
            # Get backend metrics
            backend_metrics = data_router.get_all_backend_metrics()
            metrics_status = {
                name: {
                    "last_updated": metrics.last_updated.isoformat(),
                    "avg_latency_ms": metrics.avg_latency_ms,
                    "throughput_mbps": metrics.throughput_mbps,
                    "success_rate": metrics.success_rate,
                    "region": metrics.region,
                    "multi_region": metrics.multi_region
                }
                for name, metrics in backend_metrics.items()
            }
            
            # Get routing rules
            rules = data_router.list_routing_rules()
            rule_summary = [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "content_categories": [cat.value for cat in rule.content_categories],
                    "active": rule.active
                }
                for rule in rules
            ]
            
            return {
                "status": "operational",
                "available_backends": available_backends,
                "registered_metrics": list(backend_metrics.keys()),
                "metrics_status": metrics_status,
                "routing_rules_count": len(rules),
                "routing_rules": rule_summary
            }
        except Exception as e:
            logger.error(f"Error getting router status: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting router status: {str(e)}")
    
    # --- Backend Metrics Endpoints ---
    
    @router.get("/metrics")
    async def get_all_backend_metrics(current_user: User = Depends()):
        """
        Get performance metrics for all storage backends.
        
        Returns detailed metrics about each backend's performance, cost,
        and reliability.
        """
        try:
            metrics = data_router.get_all_backend_metrics()
            return {
                "success": True,
                "metrics": {
                    name: metric.to_dict() for name, metric in metrics.items()
                }
            }
        except Exception as e:
            logger.error(f"Error getting backend metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting backend metrics: {str(e)}")
    
    @router.get("/metrics/{backend_name}")
    async def get_backend_metrics(backend_name: str, current_user: User = Depends()):
        """
        Get performance metrics for a specific storage backend.
        
        Args:
            backend_name: Name of the backend to get metrics for
            
        Returns:
            Detailed metrics about the backend's performance, cost, and reliability
        """
        try:
            metrics = data_router.get_backend_metrics(backend_name)
            if not metrics:
                raise HTTPException(status_code=404, detail=f"Metrics for backend '{backend_name}' not found")
            
            return {
                "success": True,
                "metrics": metrics.to_dict()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting metrics for backend '{backend_name}': {e}")
            raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")
    
    @router.post("/metrics/collect")
    async def collect_backend_metrics(current_user: User = Depends()):
        """
        Initiate collection of metrics for all available backends.
        
        This endpoint triggers immediate collection of performance metrics
        for all registered storage backends.
        """
        try:
            await data_router.collect_backend_metrics()
            return {
                "success": True,
                "message": "Backend metrics collection initiated"
            }
        except Exception as e:
            logger.error(f"Error collecting backend metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Error collecting metrics: {str(e)}")
    
    # --- Routing Rules Endpoints ---
    
    @router.get("/rules")
    async def list_routing_rules(current_user: User = Depends()):
        """
        List all routing rules.
        
        Returns a list of all routing rules configured in the system.
        """
        try:
            rules = data_router.list_routing_rules()
            return {
                "success": True,
                "rules": [rule.to_dict() for rule in rules]
            }
        except Exception as e:
            logger.error(f"Error listing routing rules: {e}")
            raise HTTPException(status_code=500, detail=f"Error listing routing rules: {str(e)}")
    
    @router.get("/rules/{rule_id}")
    async def get_routing_rule(rule_id: str, current_user: User = Depends()):
        """
        Get a specific routing rule by ID.
        
        Args:
            rule_id: ID of the routing rule to get
            
        Returns:
            Detailed information about the routing rule
        """
        try:
            rule = data_router.get_routing_rule(rule_id)
            if not rule:
                raise HTTPException(status_code=404, detail=f"Routing rule '{rule_id}' not found")
            
            return {
                "success": True,
                "rule": rule.to_dict()
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting routing rule '{rule_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Error getting routing rule: {str(e)}")
    
    @router.post("/rules")
    async def create_routing_rule(
        rule_data: Dict[str, Any] = Body(...),
        current_user: User = Depends()
    ):
        """
        Create a new routing rule.
        
        Args:
            rule_data: Routing rule configuration
            
        Returns:
            Created routing rule ID
        """
        try:
            # Validate rule data
            from .data_router import validate_routing_rule
            is_valid, error_message = validate_routing_rule(rule_data)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_message)
            
            # Create rule
            rule = RoutingRule.from_dict(rule_data)
            rule_id = data_router.add_routing_rule(rule)
            
            return {
                "success": True,
                "rule_id": rule_id,
                "message": "Routing rule created successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating routing rule: {e}")
            raise HTTPException(status_code=500, detail=f"Error creating routing rule: {str(e)}")
    
    @router.put("/rules/{rule_id}")
    async def update_routing_rule(
        rule_id: str,
        rule_data: Dict[str, Any] = Body(...),
        current_user: User = Depends()
    ):
        """
        Update an existing routing rule.
        
        Args:
            rule_id: ID of the routing rule to update
            rule_data: Updated routing rule configuration
            
        Returns:
            Success message
        """
        try:
            # Check if rule exists
            existing_rule = data_router.get_routing_rule(rule_id)
            if not existing_rule:
                raise HTTPException(status_code=404, detail=f"Routing rule '{rule_id}' not found")
            
            # Validate rule data
            from .data_router import validate_routing_rule
            is_valid, error_message = validate_routing_rule(rule_data)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_message)
            
            # Update rule
            rule = RoutingRule.from_dict(rule_data)
            success = data_router.update_routing_rule(rule_id, rule)
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update routing rule")
            
            return {
                "success": True,
                "message": f"Routing rule '{rule_id}' updated successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating routing rule '{rule_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Error updating routing rule: {str(e)}")
    
    @router.delete("/rules/{rule_id}")
    async def delete_routing_rule(
        rule_id: str,
        current_user: User = Depends()
    ):
        """
        Delete a routing rule.
        
        Args:
            rule_id: ID of the routing rule to delete
            
        Returns:
            Success message
        """
        try:
            # Check if rule exists
            existing_rule = data_router.get_routing_rule(rule_id)
            if not existing_rule:
                raise HTTPException(status_code=404, detail=f"Routing rule '{rule_id}' not found")
            
            # Delete rule
            success = data_router.delete_routing_rule(rule_id)
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to delete routing rule")
            
            return {
                "success": True,
                "message": f"Routing rule '{rule_id}' deleted successfully"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting routing rule '{rule_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting routing rule: {str(e)}")
    
    # --- Routing Operations Endpoints ---
    
    @router.post("/route")
    async def route_content(
        file: UploadFile = File(...),
        metadata: Optional[str] = Form("{}"),
        strategy: Optional[str] = Form(None),
        priority: Optional[str] = Form(None),
        client_latitude: Optional[float] = Form(None),
        client_longitude: Optional[float] = Form(None),
        current_user: User = Depends()
    ):
        """
        Route content to the optimal backend.
        
        This endpoint analyzes the uploaded content and routes it to the
        optimal storage backend based on the specified strategy and priority.
        
        Args:
            file: File to route
            metadata: Optional JSON metadata about the content
            strategy: Optional routing strategy
            priority: Optional routing priority
            client_latitude: Optional client latitude
            client_longitude: Optional client longitude
            
        Returns:
            Routing result with the selected backend and content information
        """
        try:
            # Read file content
            content = await file.read()
            
            # Parse metadata
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                metadata_dict = {}
            
            # Add filename to metadata
            metadata_dict["filename"] = file.filename
            
            # Parse strategy
            routing_strategy = None
            if strategy:
                try:
                    routing_strategy = RoutingStrategy(strategy)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid routing strategy: {strategy}")
            
            # Parse priority
            routing_priority = None
            if priority:
                try:
                    routing_priority = RoutingPriority(priority)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid routing priority: {priority}")
            
            # Set client location if provided
            client_location = None
            if client_latitude is not None and client_longitude is not None:
                client_location = {
                    "lat": client_latitude,
                    "lon": client_longitude
                }
            
            # Route content
            result = await data_router.route_content(
                content,
                metadata_dict,
                routing_strategy,
                routing_priority,
                client_location
            )
            
            return result
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error routing content: {e}")
            raise HTTPException(status_code=500, detail=f"Error routing content: {str(e)}")
    
    @router.post("/analyze")
    async def analyze_routing(
        file: UploadFile = File(...),
        metadata: Optional[str] = Form("{}"),
        client_latitude: Optional[float] = Form(None),
        client_longitude: Optional[float] = Form(None),
        current_user: User = Depends()
    ):
        """
        Analyze how content would be routed.
        
        This endpoint analyzes the uploaded content and provides information about
        how it would be routed using different strategies and priorities.
        
        Args:
            file: File to analyze
            metadata: Optional JSON metadata about the content
            client_latitude: Optional client latitude
            client_longitude: Optional client longitude
            
        Returns:
            Routing analysis with details about different routing options
        """
        try:
            # Read file content
            content = await file.read()
            
            # Parse metadata
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError:
                metadata_dict = {}
            
            # Add filename to metadata
            metadata_dict["filename"] = file.filename
            
            # Set client location if provided
            client_location = None
            if client_latitude is not None and client_longitude is not None:
                client_location = {
                    "lat": client_latitude,
                    "lon": client_longitude
                }
            
            # Analyze routing
            result = data_router.get_routing_analysis(
                content,
                metadata_dict,
                client_location
            )
            
            return result
        except Exception as e:
            logger.error(f"Error analyzing routing: {e}")
            raise HTTPException(status_code=500, detail=f"Error analyzing routing: {str(e)}")
    
    @router.post("/select-backend")
    async def select_backend(
        content_info: Dict[str, Any] = Body(...),
        strategy: Optional[str] = Form(None),
        priority: Optional[str] = Form(None),
        client_latitude: Optional[float] = Form(None),
        client_longitude: Optional[float] = Form(None),
        current_user: User = Depends()
    ):
        """
        Select the optimal backend for content based on its characteristics.
        
        This endpoint determines the optimal backend for content based on the
        provided content information and routing preferences.
        
        Args:
            content_info: Information about the content (size, type, etc.)
            strategy: Optional routing strategy
            priority: Optional routing priority
            client_latitude: Optional client latitude
            client_longitude: Optional client longitude
            
        Returns:
            Selected backend name
        """
        try:
            # Parse strategy
            routing_strategy = None
            if strategy:
                try:
                    routing_strategy = RoutingStrategy(strategy)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid routing strategy: {strategy}")
            
            # Parse priority
            routing_priority = None
            if priority:
                try:
                    routing_priority = RoutingPriority(priority)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid routing priority: {priority}")
            
            # Get available backends
            available_backends = backend_manager.list_backends() if backend_manager else []
            
            # Set client location if provided
            client_location = None
            if client_latitude is not None and client_longitude is not None:
                client_location = {
                    "lat": client_latitude,
                    "lon": client_longitude
                }
            
            # Select backend
            backend = data_router.select_backend(
                b"",  # Dummy content (we're using content_info instead)
                content_info,
                available_backends,
                routing_strategy,
                routing_priority,
                client_location
            )
            
            return {
                "success": True,
                "selected_backend": backend,
                "content_info": content_info,
                "strategy": strategy,
                "priority": priority
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error selecting backend: {e}")
            raise HTTPException(status_code=500, detail=f"Error selecting backend: {str(e)}")
    
    # --- Geographic Router Endpoints ---
    
    @router.post("/geo/set-location")
    async def set_client_location(
        latitude: float = Form(...),
        longitude: float = Form(...),
        current_user: User = Depends()
    ):
        """
        Set the client's geographic location for routing decisions.
        
        This endpoint updates the client's geographic location used for
        location-aware routing decisions.
        
        Args:
            latitude: Client latitude
            longitude: Client longitude
            
        Returns:
            Success message
        """
        try:
            # Set location in geographic router
            data_router.geographic_router.set_client_location(latitude, longitude)
            
            # Get nearest region
            nearest_region = data_router.geographic_router.get_nearest_region()
            
            return {
                "success": True,
                "message": "Client location set successfully",
                "location": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "nearest_region": nearest_region
            }
        except Exception as e:
            logger.error(f"Error setting client location: {e}")
            raise HTTPException(status_code=500, detail=f"Error setting client location: {str(e)}")
    
    @router.get("/geo/regions")
    async def list_geographic_regions(current_user: User = Depends()):
        """
        List available geographic regions for routing.
        
        Returns information about available geographic regions that can be
        used for location-aware routing decisions.
        """
        try:
            # Get available regions
            regions = data_router.geographic_router.regions
            
            return {
                "success": True,
                "regions": regions
            }
        except Exception as e:
            logger.error(f"Error listing geographic regions: {e}")
            raise HTTPException(status_code=500, detail=f"Error listing geographic regions: {str(e)}")
    
    return router