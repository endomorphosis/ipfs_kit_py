"""
Enhanced Router API Module for MCP

This module provides enhanced API endpoints for the optimized data routing system.
It integrates the adaptive optimizer to provide intelligent routing decisions based on:
- Network conditions (bandwidth, latency, reliability)
- Content characteristics (size, type, access patterns)
- Cost considerations (storage, retrieval, bandwidth)
- Geographic awareness (client location, region optimization)

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Body, Query
from pydantic import BaseModel, Field

from .data_router import DataRouter, ContentCategory, RoutingStrategy, RoutingPriority, BackendMetrics
from .adaptive_optimizer import AdaptiveOptimizer, RouteOptimizationResult, create_adaptive_optimizer

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/routing",
    tags=["routing"],
    responses={404: {"description": "Not found"}},
)

# Create adaptive optimizer
adaptive_optimizer = create_adaptive_optimizer()


# Models for API
class ClientInfo(BaseModel):
    """Client information for routing decisions."""
    
    client_id: Optional[str] = Field(None, description="Client identifier")
    location: Optional[Dict[str, float]] = Field(
        None, 
        description="Geographic location (lat/lon)"
    )
    region: Optional[str] = Field(None, description="Client region")
    network_info: Optional[Dict[str, Any]] = Field(
        None, 
        description="Client network information"
    )


class RoutingRequest(BaseModel):
    """Request for routing optimization."""
    
    content_hash: Optional[str] = Field(None, description="Content hash if available")
    content_type: Optional[str] = Field(None, description="Content MIME type")
    content_size_bytes: int = Field(0, description="Content size in bytes")
    category: Optional[str] = Field(None, description="Content category")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Content metadata")
    available_backends: Optional[List[str]] = Field(None, description="Available backends")
    priority: Optional[str] = Field(None, description="Routing priority")
    client_info: Optional[ClientInfo] = Field(None, description="Client information")


class RoutingResponse(BaseModel):
    """Response for routing optimization."""
    
    backend_id: str = Field(..., description="Selected backend identifier")
    overall_score: float = Field(..., description="Overall score of the selection")
    factor_scores: Dict[str, float] = Field(..., description="Scores for each factor")
    alternatives: List[Dict[str, Any]] = Field(..., description="Alternative backends")
    content_analysis: Dict[str, Any] = Field(..., description="Content analysis results")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


class MetricsUpdateRequest(BaseModel):
    """Request to update backend metrics."""
    
    metrics: Dict[str, Any] = Field(..., description="Backend metrics")


class NetworkMetricsResponse(BaseModel):
    """Response with network metrics."""
    
    backend_id: str = Field(..., description="Backend identifier")
    region: Optional[str] = Field(None, description="Backend region")
    metrics: Dict[str, Any] = Field(..., description="Network metrics")
    overall_quality: str = Field(..., description="Overall network quality")
    performance_score: float = Field(..., description="Performance score")


class InsightsResponse(BaseModel):
    """Response with routing insights."""
    
    optimal_backends_by_content: Dict[str, List[str]] = Field(
        ..., 
        description="Optimal backends by content type"
    )
    network_quality_ranking: Dict[str, Dict[str, Any]] = Field(
        ..., 
        description="Backends ranked by network quality"
    )
    load_distribution: Dict[str, float] = Field(
        ..., 
        description="Load distribution across backends"
    )
    optimization_weights: Dict[str, float] = Field(
        ..., 
        description="Current optimization weights"
    )


# Routes
@router.post("/optimize", response_model=RoutingResponse)
async def optimize_route(request: RoutingRequest = Body(...)):
    """
    Optimize routing for content.
    
    Returns the optimal backend for storing the content based on various factors.
    """
    try:
        # Extract client location if provided
        client_location = None
        if request.client_info and request.client_info.location:
            client_location = request.client_info.location
        
        # Convert priority if provided
        priority = None
        if request.priority:
            try:
                priority = RoutingPriority(request.priority)
            except ValueError:
                priority = RoutingPriority.BALANCED
        
        # Extract content category if provided
        content_category = None
        if request.category:
            try:
                content_category = ContentCategory(request.category)
            except ValueError:
                pass
        
        # Create metadata
        metadata = request.metadata or {}
        if request.content_type:
            metadata["content_type"] = request.content_type
        if content_category:
            metadata["category"] = content_category.value
        
        # Create dummy content for optimization
        # In a real scenario, we might have the actual content or a sample
        content = b"0" * min(1024, request.content_size_bytes)  # Use at most 1KB for the sample
        
        # Get routing decision
        result = adaptive_optimizer.optimize_route(
            content=content,
            metadata=metadata,
            available_backends=request.available_backends,
            priority=priority,
            client_location=client_location
        )
        
        # Convert result to response
        response = RoutingResponse(
            backend_id=result.backend_id,
            overall_score=result.overall_score,
            factor_scores={factor.value: score for factor, score in result.factor_scores.items()},
            alternatives=[{"backend_id": bid, "score": score} for bid, score in result.alternatives],
            content_analysis=result.content_analysis,
            execution_time_ms=result.execution_time_ms
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error optimizing route: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-outcome")
async def record_routing_outcome(
    backend_id: str = Query(..., description="Backend identifier"),
    success: bool = Query(..., description="Whether the routing was successful"),
    request: RoutingRequest = Body(..., description="Original routing request")
):
    """
    Record the outcome of a routing decision.
    
    This helps the system learn from past decisions and improve future routing.
    """
    try:
        # Extract content information
        content_category = None
        if request.category:
            try:
                content_category = ContentCategory(request.category)
            except ValueError:
                content_category = ContentCategory.OTHER
        
        # Create dummy result for recording
        result = RouteOptimizationResult(backend_id)
        result.content_analysis = {
            "category": content_category.value if content_category else ContentCategory.OTHER.value,
            "size_bytes": request.content_size_bytes
        }
        
        # Record outcome
        adaptive_optimizer.record_outcome(result, success)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error recording outcome: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/network-metrics/{backend_id}", response_model=NetworkMetricsResponse)
async def get_network_metrics(backend_id: str, region: Optional[str] = None):
    """
    Get network metrics for a backend.
    
    Returns detailed network quality metrics for a specific backend.
    """
    try:
        # Get metrics from network analyzer
        metrics = adaptive_optimizer.network_analyzer.get_metrics(backend_id, region or "")
        
        # Convert to response
        response = NetworkMetricsResponse(
            backend_id=backend_id,
            region=region,
            metrics={
                metric_type.value: metric.to_dict()
                for metric_type, metric in metrics.metrics.items()
                if len(metric.samples) > 0
            },
            overall_quality=metrics.get_overall_quality().value,
            performance_score=metrics.get_performance_score()
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting network metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights", response_model=InsightsResponse)
async def get_routing_insights():
    """
    Get insights from the routing system.
    
    Returns information about the current state of the routing system,
    including optimal backends for different content types and performance rankings.
    """
    try:
        # Generate insights
        insights = adaptive_optimizer.generate_insights()
        
        # Convert to response
        response = InsightsResponse(
            optimal_backends_by_content=insights["optimal_backends_by_content"],
            network_quality_ranking=insights["network_quality_ranking"],
            load_distribution=insights.get("load_distribution", {}),
            optimization_weights=insights["optimization_weights"]
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect-metrics")
async def collect_all_metrics(backend_ids: List[str] = Body(...)):
    """
    Trigger collection of metrics for backends.
    
    This endpoint triggers the collection of network metrics and other
    performance data for the specified backends.
    """
    try:
        # Collect metrics asynchronously
        asyncio.create_task(adaptive_optimizer.collect_all_metrics(backend_ids))
        
        return {"status": "metrics collection started"}
        
    except Exception as e:
        logger.error(f"Error starting metrics collection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-backend-metrics/{backend_id}")
async def update_backend_metrics(
    backend_id: str,
    request: MetricsUpdateRequest = Body(...)
):
    """
    Update metrics for a backend.
    
    This endpoint allows updating performance and cost metrics for a backend.
    """
    try:
        # Convert to BackendMetrics
        metrics = BackendMetrics(
            avg_latency_ms=request.metrics.get("avg_latency_ms", 0.0),
            success_rate=request.metrics.get("success_rate", 1.0),
            throughput_mbps=request.metrics.get("throughput_mbps", 0.0),
            storage_cost_per_gb=request.metrics.get("storage_cost_per_gb", 0.0),
            retrieval_cost_per_gb=request.metrics.get("retrieval_cost_per_gb", 0.0),
            bandwidth_cost_per_gb=request.metrics.get("bandwidth_cost_per_gb", 0.0),
            total_stored_bytes=request.metrics.get("total_stored_bytes", 0.0),
            total_retrieved_bytes=request.metrics.get("total_retrieved_bytes", 0.0),
            region=request.metrics.get("region", "unknown"),
            multi_region=request.metrics.get("multi_region", False),
            uptime_percentage=request.metrics.get("uptime_percentage", 99.9)
        )
        
        # Update metrics
        adaptive_optimizer.update_backend_metrics(backend_id, metrics)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error updating backend metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic-data/enable")
async def enable_synthetic_data(
    backend_ids: List[str] = Body(...),
    update_interval_seconds: float = Body(30.0)
):
    """
    Enable synthetic data generation for testing.
    
    This endpoint enables the generation of synthetic network metrics
    for testing purposes.
    """
    try:
        adaptive_optimizer.network_analyzer.enable_synthetic_data(
            backend_ids=backend_ids,
            update_interval_seconds=update_interval_seconds
        )
        
        return {"status": "synthetic data generation enabled"}
        
    except Exception as e:
        logger.error(f"Error enabling synthetic data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthetic-data/disable")
async def disable_synthetic_data():
    """
    Disable synthetic data generation.
    
    This endpoint disables the generation of synthetic network metrics.
    """
    try:
        adaptive_optimizer.network_analyzer.disable_synthetic_data()
        
        return {"status": "synthetic data generation disabled"}
        
    except Exception as e:
        logger.error(f"Error disabling synthetic data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))