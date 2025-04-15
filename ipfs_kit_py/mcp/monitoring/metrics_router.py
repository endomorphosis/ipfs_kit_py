#!/usr/bin/env python3
"""
Metrics and Monitoring API Router

This module provides FastAPI routes for the enhanced monitoring system including:
- Prometheus metrics endpoint
- Health check endpoints
- Monitoring dashboard API

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import os
import time
import json
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Response, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

# Import the metrics system
from ipfs_kit_py.mcp.monitoring.metrics import get_instance as get_metrics

# Create API router
router = APIRouter(prefix="/api/v0/monitoring", tags=["monitoring"])

# --- Pydantic models for request/response validation ---

class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    last_check: float
    checks: Dict[str, bool]
    details: Dict[str, Dict[str, Any]]

class MetricDataPoint(BaseModel):
    """Model for a metric data point."""
    timestamp: float
    value: float

class MetricSeries(BaseModel):
    """Model for a time series of metric data points."""
    name: str
    labels: Dict[str, str]
    data_points: List[MetricDataPoint]

class BackendHealth(BaseModel):
    """Model for backend health status."""
    backend: str
    status: str
    latency: float
    last_check: float
    details: Optional[Dict[str, Any]] = None

# --- API Routes ---

@router.get("/health", response_model=HealthStatus, summary="Get system health status")
async def get_health():
    """
    Get the current health status of the MCP server and its components.
    
    Returns a comprehensive health report with status of all registered checks.
    Status will be "healthy" only if all checks pass.
    """
    metrics = get_metrics()
    return metrics.get_health_status()

@router.get("/health/{check_name}", summary="Get specific health check status")
async def get_specific_health_check(check_name: str = Path(..., description="Name of the health check")):
    """
    Get the status of a specific health check.
    
    Args:
        check_name: Name of the health check to query
        
    Returns:
        Detailed status of the specified health check
    """
    metrics = get_metrics()
    health_status = metrics.get_health_status()
    
    if check_name not in health_status["checks"]:
        raise HTTPException(status_code=404, detail=f"Health check '{check_name}' not found")
    
    return {
        "name": check_name,
        "healthy": health_status["checks"][check_name],
        "details": health_status["details"].get(check_name, {}),
        "last_check": health_status["last_check"]
    }

@router.get("/backends/health", summary="Get health status of all storage backends")
async def get_backend_health():
    """
    Get health status for all storage backends.
    
    Returns health information and latency measurements for each backend.
    """
    metrics = get_metrics()
    
    # Extract backend metrics from our metrics store
    backend_metrics = {}
    
    # Get operation counts
    for name, metric in metrics.get_all_metrics().items():
        if name == "mcp_backend_operations_total":
            for labels_key, value in metric["data"].items():
                try:
                    labels = json.loads(labels_key)
                    backend = labels.get("backend")
                    if backend:
                        if backend not in backend_metrics:
                            backend_metrics[backend] = {"operations": {}}
                        
                        op = labels.get("operation", "unknown")
                        status = labels.get("status", "unknown")
                        key = f"{op}_{status}"
                        backend_metrics[backend]["operations"][key] = value
                except:
                    pass
        
        elif name == "mcp_backend_operation_duration_seconds":
            for labels_key, data in metric["data"].items():
                try:
                    labels = json.loads(labels_key)
                    backend = labels.get("backend")
                    if backend:
                        if backend not in backend_metrics:
                            backend_metrics[backend] = {"operations": {}}
                        
                        # Get latest latency information
                        if "latency" not in backend_metrics[backend]:
                            backend_metrics[backend]["latency"] = {}
                        
                        op = labels.get("operation", "unknown")
                        mean = data.get("mean", 0)
                        backend_metrics[backend]["latency"][op] = mean
                except:
                    pass
    
    # Convert to health status response
    results = []
    last_check = time.time()
    
    for backend, data in backend_metrics.items():
        # Calculate overall latency (average of all operations)
        latencies = data.get("latency", {}).values()
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        # Calculate health based on error rates
        operations = data.get("operations", {})
        error_ops = sum(v for k, v in operations.items() if k.endswith("_error"))
        total_ops = sum(operations.values())
        error_rate = error_ops / total_ops if total_ops > 0 else 0
        
        # Determine status
        status = "healthy"
        if error_rate > 0.5:  # More than 50% errors
            status = "critical"
        elif error_rate > 0.1:  # More than 10% errors
            status = "warning"
        elif total_ops == 0:  # No operations recorded
            status = "unknown"
        
        results.append(BackendHealth(
            backend=backend,
            status=status,
            latency=avg_latency,
            last_check=last_check,
            details={
                "error_rate": error_rate,
                "total_operations": total_ops,
                "error_operations": error_ops,
                "operation_latencies": data.get("latency", {})
            }
        ))
    
    return results

@router.get("/metrics", response_class=PlainTextResponse, summary="Get Prometheus metrics")
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus exposition format.
    
    This endpoint is compatible with Prometheus scraping and follows the
    Prometheus exposition format specification.
    """
    metrics = get_metrics()
    return metrics.get_prometheus_metrics()

@router.get("/metrics/json", summary="Get all metrics in JSON format")
async def get_metrics_json():
    """
    Get all metrics in JSON format.
    
    Returns comprehensive metrics data including metadata and current values.
    """
    metrics = get_metrics()
    return metrics.get_all_metrics()

@router.get("/metrics/{metric_name}", summary="Get a specific metric")
async def get_specific_metric(
    metric_name: str = Path(..., description="Name of the metric to retrieve")
):
    """
    Get data for a specific metric.
    
    Args:
        metric_name: Name of the metric to retrieve
        
    Returns:
        Detailed metric data including metadata and current values
    """
    metrics = get_metrics()
    result = metrics.get_metric(metric_name)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

@router.get("/metrics/{metric_name}/series", response_model=List[MetricSeries], summary="Get time series data for a metric")
async def get_metric_time_series(
    metric_name: str = Path(..., description="Name of the metric"),
    labels: Optional[str] = Query(None, description="JSON-encoded labels filter")
):
    """
    Get time series data for a specific metric.
    
    Args:
        metric_name: Name of the metric to retrieve time series for
        labels: Optional JSON-encoded labels to filter by
        
    Returns:
        List of time series with data points
    """
    metrics = get_metrics()
    
    # Verify metric exists
    metric_data = metrics.get_metric(metric_name)
    if "error" in metric_data:
        raise HTTPException(status_code=404, detail=metric_data["error"])
    
    # Get time series data
    time_series = metrics._instance.time_series.get(metric_name, {})
    
    # Filter by labels if provided
    labels_filter = None
    if labels:
        try:
            labels_filter = json.loads(labels)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid labels JSON")
    
    # Convert to response format
    results = []
    for labels_key, points in time_series.items():
        # Parse labels
        try:
            label_dict = json.loads(labels_key) if labels_key else {}
        except:
            label_dict = {}
        
        # Apply labels filter
        if labels_filter:
            matches = True
            for k, v in labels_filter.items():
                if k not in label_dict or label_dict[k] != v:
                    matches = False
                    break
            
            if not matches:
                continue
        
        # Format data points
        data_points = [
            MetricDataPoint(timestamp=ts, value=value)
            for ts, value in points
        ]
        
        results.append(MetricSeries(
            name=metric_name,
            labels=label_dict,
            data_points=data_points
        ))
    
    return results

@router.post("/system/collect", summary="Trigger immediate metrics collection")
async def trigger_metrics_collection(background_tasks: BackgroundTasks):
    """
    Trigger an immediate collection of system metrics.
    
    This will run metrics collection in the background. Useful for getting
    the most up-to-date metrics without waiting for the scheduled collection.
    """
    metrics = get_metrics()
    
    # Use background tasks to avoid blocking
    background_tasks.add_task(metrics.collect_system_metrics)
    
    return {"message": "Metrics collection triggered"}

# --- Register built-in health checks ---

def register_default_health_checks():
    """Register default health checks with the metrics system."""
    metrics = get_metrics()
    
    # Memory usage health check
    def check_memory_usage():
        try:
            import psutil
            import os
            
            # Get process memory usage
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_usage_mb = memory_info.rss / (1024 * 1024)
            
            # Set thresholds (configurable)
            warning_threshold_mb = 500  # 500 MB
            critical_threshold_mb = 1000  # 1 GB
            
            healthy = memory_usage_mb < critical_threshold_mb
            
            return {
                "healthy": healthy,
                "memory_usage_mb": memory_usage_mb,
                "status": "critical" if memory_usage_mb >= critical_threshold_mb else
                          "warning" if memory_usage_mb >= warning_threshold_mb else
                          "healthy"
            }
        except ImportError:
            return {
                "healthy": True,
                "status": "unknown",
                "message": "psutil not installed, can't monitor memory"
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    # CPU usage health check
    def check_cpu_usage():
        try:
            import psutil
            import os
            
            # Get process CPU usage
            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # Set thresholds (configurable)
            warning_threshold = 70  # 70%
            critical_threshold = 90  # 90%
            
            healthy = cpu_percent < critical_threshold
            
            return {
                "healthy": healthy,
                "cpu_percent": cpu_percent,
                "status": "critical" if cpu_percent >= critical_threshold else
                          "warning" if cpu_percent >= warning_threshold else
                          "healthy"
            }
        except ImportError:
            return {
                "healthy": True,
                "status": "unknown",
                "message": "psutil not installed, can't monitor CPU"
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    # Disk usage health check
    def check_disk_usage():
        try:
            import psutil
            
            # Get disk usage for the current directory
            disk_usage = psutil.disk_usage(os.getcwd())
            disk_percent = disk_usage.percent
            
            # Set thresholds (configurable)
            warning_threshold = 80  # 80%
            critical_threshold = 95  # 95%
            
            healthy = disk_percent < critical_threshold
            
            return {
                "healthy": healthy,
                "disk_percent": disk_percent,
                "free_gb": disk_usage.free / (1024 * 1024 * 1024),
                "total_gb": disk_usage.total / (1024 * 1024 * 1024),
                "status": "critical" if disk_percent >= critical_threshold else
                          "warning" if disk_percent >= warning_threshold else
                          "healthy"
            }
        except ImportError:
            return {
                "healthy": True,
                "status": "unknown",
                "message": "psutil not installed, can't monitor disk"
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    # Register the health checks
    metrics.register_health_check("memory_usage", check_memory_usage)
    metrics.register_health_check("cpu_usage", check_cpu_usage)
    metrics.register_health_check("disk_usage", check_disk_usage)

# Register default health checks when module is imported
register_default_health_checks()