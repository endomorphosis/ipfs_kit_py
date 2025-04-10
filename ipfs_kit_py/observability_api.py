"""
Observability API for IPFS Kit

This module provides a FastAPI router for accessing observability features
in IPFS Kit, including metrics, logging, and tracing.

Features:
- Metrics collection and retrieval
- Log level management and log searching
- Distributed tracing configuration
- Health checks and status monitoring
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union

import fastapi
from fastapi import Body, HTTPException, Query, Request, BackgroundTasks, Response
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
observability_router = fastapi.APIRouter(prefix="/api/v0/observability", tags=["observability"])

@observability_router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    metric_type: Optional[str] = Query(None, description="Filter metrics by type (system, ipfs, libp2p, storage)"),
    format: str = Query("json", description="Response format (json or prometheus)")
):
    """
    Get system and IPFS metrics.
    
    This endpoint returns metrics from the IPFS Kit instance, including system metrics,
    IPFS metrics, LibP2P metrics, and storage metrics.
    
    Parameters:
    - **metric_type**: Filter metrics by type (system, ipfs, libp2p, storage)
    - **format**: Response format (json or prometheus)
    
    Returns:
        Metrics data in the specified format
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Get metrics
        logger.info(f"Getting metrics (type: {metric_type or 'all'}, format: {format})")
        metrics = api.observability.get_metrics(metric_type=metric_type)
        
        # Return in requested format
        if format.lower() == "prometheus":
            # Convert to Prometheus format
            prometheus_lines = []
            
            for metric_name, metric_data in metrics.items():
                metric_type = metric_data.get("type", "gauge")
                help_text = metric_data.get("description", "")
                
                # Add metric type and help
                prometheus_lines.append(f"# TYPE {metric_name} {metric_type}")
                prometheus_lines.append(f"# HELP {metric_name} {help_text}")
                
                # Add metric values
                if isinstance(metric_data.get("value"), dict):
                    # Metric with labels
                    for label_values, value in metric_data["value"].items():
                        label_str = "{" + label_values + "}"
                        prometheus_lines.append(f"{metric_name}{label_str} {value}")
                else:
                    # Simple metric
                    prometheus_lines.append(f"{metric_name} {metric_data.get('value', 0)}")
            
            # Return Prometheus format
            return Response(
                content="\n".join(prometheus_lines),
                media_type="text/plain"
            )
        else:
            # Return JSON format
            return {
                "success": True,
                "operation": "get_metrics",
                "timestamp": time.time(),
                "metrics": metrics
            }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")
        
@observability_router.post("/metrics/export", response_model=Dict[str, Any])
async def export_metrics(
    export_target: str = Body(..., description="Export target (prometheus, influxdb, etc.)"),
    config: Dict[str, Any] = Body(..., description="Export configuration"),
    background_tasks: BackgroundTasks = None
):
    """
    Export metrics to an external system.
    
    This endpoint configures metric export to an external monitoring system.
    
    Parameters:
    - **export_target**: Export target (prometheus, influxdb, etc.)
    - **config**: Export configuration
    
    Returns:
        Export operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Export metrics
        logger.info(f"Exporting metrics to {export_target}")
        
        # Start export in background task
        background_tasks.add_task(
            api.observability.export_metrics,
            target=export_target,
            config=config
        )
        
        return {
            "success": True,
            "operation": "export_metrics",
            "timestamp": time.time(),
            "export_target": export_target,
            "status": "started"
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error exporting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error exporting metrics: {str(e)}")
        
@observability_router.get("/logs", response_model=Dict[str, Any])
async def get_logs(
    level: Optional[str] = Query(None, description="Filter logs by level (debug, info, warning, error)"),
    component: Optional[str] = Query(None, description="Filter logs by component"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    since: Optional[str] = Query(None, description="Get logs since timestamp (ISO format)"),
    query: Optional[str] = Query(None, description="Search query")
):
    """
    Get system logs.
    
    This endpoint returns logs from the IPFS Kit instance.
    
    Parameters:
    - **level**: Filter logs by level (debug, info, warning, error)
    - **component**: Filter logs by component
    - **limit**: Maximum number of logs to return
    - **since**: Get logs since timestamp (ISO format)
    - **query**: Search query
    
    Returns:
        Log entries matching the filters
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Get logs
        logger.info(f"Getting logs (level: {level or 'all'}, component: {component or 'all'}, limit: {limit})")
        logs = api.observability.get_logs(
            level=level,
            component=component,
            limit=limit,
            since=since,
            query=query
        )
        
        return {
            "success": True,
            "operation": "get_logs",
            "timestamp": time.time(),
            "logs": logs.get("entries", []),
            "count": logs.get("count", 0),
            "total": logs.get("total", 0)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting logs: {str(e)}")
        
@observability_router.post("/logs/level", response_model=Dict[str, Any])
async def set_log_level(
    component: str = Body(..., description="Component to set log level for"),
    level: str = Body(..., description="Log level to set (debug, info, warning, error)")
):
    """
    Set log level for a component.
    
    This endpoint sets the log level for a specific component.
    
    Parameters:
    - **component**: Component to set log level for
    - **level**: Log level to set (debug, info, warning, error)
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Validate log level
        valid_levels = ["debug", "info", "warning", "error"]
        if level.lower() not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid log level. Must be one of: {', '.join(valid_levels)}"
            )
            
        # Set log level
        logger.info(f"Setting log level for {component} to {level}")
        result = api.observability.set_log_level(component, level)
        
        return {
            "success": True,
            "operation": "set_log_level",
            "timestamp": time.time(),
            "component": component,
            "level": level,
            "previous_level": result.get("previous_level"),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error setting log level: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error setting log level: {str(e)}")
        
@observability_router.get("/tracing", response_model=Dict[str, Any])
async def get_tracing_config():
    """
    Get distributed tracing configuration.
    
    This endpoint returns the current distributed tracing configuration.
    
    Returns:
        Tracing configuration
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Get tracing config
        logger.info("Getting tracing configuration")
        config = api.observability.get_tracing_config()
        
        return {
            "success": True,
            "operation": "get_tracing_config",
            "timestamp": time.time(),
            "enabled": config.get("enabled", False),
            "provider": config.get("provider"),
            "sampling_rate": config.get("sampling_rate"),
            "endpoint": config.get("endpoint"),
            "propagation": config.get("propagation", [])
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting tracing configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting tracing configuration: {str(e)}")
        
@observability_router.post("/tracing", response_model=Dict[str, Any])
async def configure_tracing(
    enabled: bool = Body(..., description="Enable or disable tracing"),
    provider: str = Body(..., description="Tracing provider (jaeger, zipkin, otlp)"),
    endpoint: str = Body(..., description="Tracing endpoint"),
    sampling_rate: float = Body(1.0, description="Sampling rate (0.0-1.0)"),
    propagation: List[str] = Body(["w3c"], description="Context propagation formats")
):
    """
    Configure distributed tracing.
    
    This endpoint configures distributed tracing.
    
    Parameters:
    - **enabled**: Enable or disable tracing
    - **provider**: Tracing provider (jaeger, zipkin, otlp)
    - **endpoint**: Tracing endpoint
    - **sampling_rate**: Sampling rate (0.0-1.0)
    - **propagation**: Context propagation formats
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Validate provider
        valid_providers = ["jaeger", "zipkin", "otlp"]
        if provider.lower() not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tracing provider. Must be one of: {', '.join(valid_providers)}"
            )
            
        # Validate sampling rate
        if sampling_rate < 0.0 or sampling_rate > 1.0:
            raise HTTPException(
                status_code=400,
                detail="Sampling rate must be between 0.0 and 1.0"
            )
            
        # Configure tracing
        logger.info(f"Configuring tracing (enabled: {enabled}, provider: {provider})")
        result = api.observability.configure_tracing(
            enabled=enabled,
            provider=provider,
            endpoint=endpoint,
            sampling_rate=sampling_rate,
            propagation=propagation
        )
        
        return {
            "success": True,
            "operation": "configure_tracing",
            "timestamp": time.time(),
            "enabled": enabled,
            "provider": provider,
            "sampling_rate": sampling_rate,
            "endpoint": endpoint,
            "propagation": propagation,
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error configuring tracing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error configuring tracing: {str(e)}")
        
@observability_router.get("/health", response_model=Dict[str, Any])
async def health_check(
    comprehensive: bool = Query(False, description="Perform a comprehensive health check")
):
    """
    Perform a health check.
    
    This endpoint performs a health check on the IPFS Kit instance.
    
    Parameters:
    - **comprehensive**: Perform a comprehensive health check
    
    Returns:
        Health check results
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            # Fallback to basic health check
            return {
                "success": True,
                "operation": "health_check",
                "timestamp": time.time(),
                "status": "ok",
                "api_version": getattr(api, "version", "unknown"),
                "uptime": 0  # We don't know the uptime
            }
            
        # Perform health check
        logger.info(f"Performing health check (comprehensive: {comprehensive})")
        result = api.observability.health_check(comprehensive=comprehensive)
        
        return {
            "success": True,
            "operation": "health_check",
            "timestamp": time.time(),
            "status": result.get("status", "unknown"),
            "components": result.get("components", {}),
            "api_version": result.get("api_version"),
            "uptime": result.get("uptime", 0),
            "resources": result.get("resources", {})
        }
    except Exception as e:
        logger.exception(f"Error performing health check: {str(e)}")
        # Even if there's an error, return a health check result
        return {
            "success": False,
            "operation": "health_check",
            "timestamp": time.time(),
            "status": "error",
            "error": str(e)
        }
        
@observability_router.post("/alerts", response_model=Dict[str, Any])
async def configure_alerts(
    enabled: bool = Body(..., description="Enable or disable alerts"),
    endpoints: List[Dict[str, Any]] = Body(..., description="Alert endpoints"),
    rules: List[Dict[str, Any]] = Body(..., description="Alert rules")
):
    """
    Configure alerts.
    
    This endpoint configures alerts based on metrics and logs.
    
    Parameters:
    - **enabled**: Enable or disable alerts
    - **endpoints**: Alert endpoints (email, webhook, etc.)
    - **rules**: Alert rules
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Configure alerts
        logger.info(f"Configuring alerts (enabled: {enabled})")
        result = api.observability.configure_alerts(
            enabled=enabled,
            endpoints=endpoints,
            rules=rules
        )
        
        return {
            "success": True,
            "operation": "configure_alerts",
            "timestamp": time.time(),
            "enabled": enabled,
            "endpoint_count": len(endpoints),
            "rule_count": len(rules),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error configuring alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error configuring alerts: {str(e)}")
        
@observability_router.get("/alerts", response_model=Dict[str, Any])
async def get_alert_config():
    """
    Get alert configuration.
    
    This endpoint returns the current alert configuration.
    
    Returns:
        Alert configuration
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Get alert config
        logger.info("Getting alert configuration")
        config = api.observability.get_alert_config()
        
        return {
            "success": True,
            "operation": "get_alert_config",
            "timestamp": time.time(),
            "enabled": config.get("enabled", False),
            "endpoints": config.get("endpoints", []),
            "rules": config.get("rules", [])
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting alert configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting alert configuration: {str(e)}")
        
@observability_router.get("/alerts/history", response_model=Dict[str, Any])
async def get_alert_history(
    limit: int = Query(100, description="Maximum number of alerts to return"),
    since: Optional[str] = Query(None, description="Get alerts since timestamp (ISO format)"),
    rule_id: Optional[str] = Query(None, description="Filter alerts by rule ID"),
    severity: Optional[str] = Query(None, description="Filter alerts by severity")
):
    """
    Get alert history.
    
    This endpoint returns the alert history.
    
    Parameters:
    - **limit**: Maximum number of alerts to return
    - **since**: Get alerts since timestamp (ISO format)
    - **rule_id**: Filter alerts by rule ID
    - **severity**: Filter alerts by severity
    
    Returns:
        Alert history
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if observability module is available
        if not hasattr(api, "observability"):
            raise HTTPException(
                status_code=404,
                detail="Observability API is not available."
            )
            
        # Get alert history
        logger.info(f"Getting alert history (limit: {limit})")
        history = api.observability.get_alert_history(
            limit=limit,
            since=since,
            rule_id=rule_id,
            severity=severity
        )
        
        return {
            "success": True,
            "operation": "get_alert_history",
            "timestamp": time.time(),
            "alerts": history.get("alerts", []),
            "count": history.get("count", 0),
            "total": history.get("total", 0)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting alert history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting alert history: {str(e)}")
