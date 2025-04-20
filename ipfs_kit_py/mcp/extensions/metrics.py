"""
Metrics extension for the MCP server.

This extension provides Prometheus metrics reporting for MCP.
"""

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Response  # Added Query import

# Configure logger
logger = logging.getLogger(__name__)

# Import Prometheus client if available
try:
    from prometheus_client import generate_latest

    PROMETHEUS_AVAILABLE = True
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain"

    def generate_latest(*args, **kwargs):
        """Stub for generate_latest when prometheus_client is not available."""
        return b"Prometheus metrics not available - client library not installed"


# Import our monitoring system
# Note: Duplicated logging setup removed here
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from mcp_monitoring import MonitoringSystem

    MONITORING_AVAILABLE = True
    logger.info("Monitoring system successfully imported")
except ImportError as e:
    MONITORING_AVAILABLE = False
    logger.error(f"Error importing Monitoring system: {e}")

# Initialize monitoring system
# Note: Redundant Prometheus check block removed here
monitoring_system = None
if MONITORING_AVAILABLE:
    try:
        # Load configuration
        config = {
            "metrics_enabled": True,
            "prometheus_enabled": PROMETHEUS_AVAILABLE,  # Changed from PROMETHEUS_CLIENT_AVAILABLE
            "prometheus_port": 9998,
            "collection_interval": 10,
            "disk_paths": ["/", os.path.expanduser("~")],
            "network_interfaces": ["eth0", "wlan0", "en0"],  # Common interface names
        }

        monitoring_system = MonitoringSystem(config)
        logger.info("Monitoring system initialized")
    except Exception as e:
        logger.error(f"Error initializing Monitoring system: {e}")


def create_metrics_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with metrics and monitoring endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/metrics")

    @router.get("/status")
    async def metrics_status():
        """Get the status of the metrics and monitoring system."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {
                "success": False,
                "status": "unavailable",
                "error": "Monitoring system is not available",
            }

        system_info = monitoring_system.get_system_info()
        return {
            "success": True,
            "status": "available",
            "system_info": system_info,
            "prometheus_enabled": PROMETHEUS_AVAILABLE and monitoring_system.config["prometheus_enabled"],
            "prometheus_port": (
                monitoring_system.config["prometheus_port"]
                if PROMETHEUS_AVAILABLE and monitoring_system.config["prometheus_enabled"]
                else None
            ),
            "collection_interval": monitoring_system.config["collection_interval"],
            "collection_running": monitoring_system.running,
        }

    @router.get("/dashboard")
    async def metrics_dashboard():
        """Get aggregated metrics for dashboard display."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        dashboard_data = monitoring_system.get_dashboard_data()
        return {"success": True, "data": dashboard_data}

    @router.get("/prometheus", response_class=Response)
    async def metrics_prometheus():
        """Export metrics in Prometheus format."""
        if not PROMETHEUS_AVAILABLE:  # Use the flag from the first import block
            return Response(
                content="Prometheus client not available",
                status_code=501,
                media_type="text/plain",
            )

        try:
            # Generate latest metrics
            prometheus_data = generate_latest()
            return Response(content=prometheus_data, media_type=CONTENT_TYPE_LATEST)
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return Response(
                content=f"Error generating metrics: {str(e)}",
                status_code=500,
                media_type="text/plain",
            )

    @router.get("/system")
    async def system_metrics():
        """Get system-level metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        system_metrics = {}

        for name, metric in monitoring_system.registry.metrics.items():
            if name.startswith("system."):
                system_metrics[name] = {
                    "type": metric["type"],
                    "description": metric["description"],
                    "values": metric["values"],
                    "timestamp": time.time(),
                }

        return {
            "success": True,
            "metrics": system_metrics,
            "system_info": monitoring_system.get_system_info(),
        }

    @router.get("/process")
    async def process_metrics():
        """Get process-level metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        process_metrics = {}

        for name, metric in monitoring_system.registry.metrics.items():
            if name.startswith("process."):
                process_metrics[name] = {
                    "type": metric["type"],
                    "description": metric["description"],
                    "values": metric["values"],
                    "timestamp": time.time(),
                }

        return {"success": True, "metrics": process_metrics}

    @router.get("/api")
    async def api_metrics():
        """Get API-level metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        api_metrics = {}

        for name, metric in monitoring_system.registry.metrics.items():
            if name.startswith("api."):
                api_metrics[name] = {
                    "type": metric["type"],
                    "description": metric["description"],
                    "values": metric["values"],
                    "timestamp": time.time(),
                }

        return {"success": True, "metrics": api_metrics}

    @router.get("/storage")
    async def storage_metrics():
        """Get storage-level metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        storage_metrics = {}

        for name, metric in monitoring_system.registry.metrics.items():
            if name.startswith("storage."):
                storage_metrics[name] = {
                    "type": metric["type"],
                    "description": metric["description"],
                    "values": metric["values"],
                    "timestamp": time.time(),
                }

        return {
            "success": True,
            "metrics": storage_metrics,
            "storage_backends": monitoring_system.storage_backends,
        }

    @router.get("/ipfs")
    async def ipfs_metrics():
        """Get IPFS-specific metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        ipfs_metrics = {}

        for name, metric in monitoring_system.registry.metrics.items():
            if name.startswith("ipfs."):
                ipfs_metrics[name] = {
                    "type": metric["type"],
                    "description": metric["description"],
                    "values": metric["values"],
                    "timestamp": time.time(),
                }

        return {"success": True, "metrics": ipfs_metrics}

    @router.get("/history/{metric_name}")
    async def metric_history(
        metric_name: str,
        labels: Optional[str] = Query(
            None, description="Comma-separated list of label=value pairs"
        ),
    ):
        """
        Get historical values for a specific metric.

        Args:
            metric_name: Name of the metric
            labels: Optional comma-separated list of label=value pairs
        """
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        # Parse labels
        label_dict = {}
        if labels:
            try:
                for label_pair in labels.split(","):
                    key, value = label_pair.split("=", 1)
                    label_dict[key.strip()] = value.strip()
            except Exception:
                return {
                    "success": False,
                    "error": "Invalid label format. Use 'key1=value1,key2=value2'",
                }

        # Get metric history
        history = monitoring_system.registry.get_history(metric_name, label_dict)

        if not history:
            return {
                "success": False,
                "error": f"No history available for metric {metric_name}",
                "metric": metric_name,
                "labels": label_dict,
            }

        # Format history as timestamps and values
        formatted_history = []
        for timestamp, value in history:
            formatted_history.append({"timestamp": timestamp, "value": value})

        return {
            "success": True,
            "metric": metric_name,
            "labels": label_dict,
            "history": formatted_history,
        }

    @router.get("/all")
    async def all_metrics():
        """Get all available metrics."""
        if not MONITORING_AVAILABLE or monitoring_system is None:
            return {"success": False, "error": "Monitoring system is not available"}

        metrics_data = monitoring_system.get_metrics_data()
        return {"success": True, "data": metrics_data}

    return router


# Health check router with detailed system health information
def create_health_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with enhanced health check endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/health")

    @router.get("")
    async def health_check():
        """Basic health check endpoint."""
        # Check IPFS daemon
        ipfs_running = False
        try:
            import subprocess

            result = subprocess.run(["ipfs", "version"], capture_output=True, timeout=2)
            ipfs_running = result.returncode == 0
        except Exception:
            pass

        # Get system info if monitoring available
        system_info = None
        if MONITORING_AVAILABLE and monitoring_system is not None:
            system_info = monitoring_system.get_system_info()

        # Basic health status
        health_status = "healthy" if ipfs_running else "degraded"

        return {
            "success": True,
            "status": health_status,
            "timestamp": time.time(),
            "ipfs_daemon_running": ipfs_running,
            "monitoring_available": MONITORING_AVAILABLE and monitoring_system is not None,
            "system_info": system_info,
        }

    @router.get("/detailed")
    async def detailed_health():
        """Detailed health check with system and component status."""
        # Basic system check
        import subprocess

        # Check disk space
        disk_health = True
        disk_status = {}
        try:
            import psutil

            for path in ["/", os.path.expanduser("~")]:
                try:
                    usage = psutil.disk_usage(path)
                    # Consider unhealthy if less than 10% free space
                    status = usage.percent < 90
                    disk_health = disk_health and status
                    disk_status[path] = {
                        "healthy": status,
                        "usage_percent": usage.percent,
                        "free_bytes": usage.free,
                        "total_bytes": usage.total,
                    }
                except Exception as e:
                    disk_status[path] = {"healthy": False, "error": str(e)}
                    disk_health = False
        except Exception as e:
            disk_health = False
            disk_status = {"error": str(e)}

        # Check memory
        memory_health = True
        memory_status = {}
        try:
            import psutil

            memory = psutil.virtual_memory()
            # Consider unhealthy if less than 10% free memory
            memory_health = memory.percent < 90
            memory_status = {
                "healthy": memory_health,
                "usage_percent": memory.percent,
                "available_bytes": memory.available,
                "total_bytes": memory.total,
            }
        except Exception as e:
            memory_health = False
            memory_status = {"error": str(e)}

        # Check IPFS daemon
        ipfs_health = False
        ipfs_status = {}
        try:
            result = subprocess.run(["ipfs", "version"], capture_output=True, text=True, timeout=2)
            ipfs_health = result.returncode == 0
            if ipfs_health:
                ipfs_status = {"healthy": True, "version": result.stdout.strip()}

                # Check IPFS peer count
                try:
                    result = subprocess.run(
                        ["ipfs", "swarm", "peers", "--count"],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if result.returncode == 0:
                        peer_count = int(result.stdout.strip())
                        # Consider unhealthy if no peers
                        peer_health = peer_count > 0
                        ipfs_status["peers"] = {
                            "healthy": peer_health,
                            "count": peer_count,
                        }
                except Exception:
                    pass
            else:
                ipfs_status = {"healthy": False, "error": result.stderr.strip()}
        except Exception as e:
            ipfs_status = {"healthy": False, "error": str(e)}

        # Get storage backends status
        storage_backends = {}

        # Overall health
        overall_health = ipfs_health and disk_health and memory_health
        overall_status = "healthy" if overall_health else "degraded"

        return {
            "success": True,
            "status": overall_status,
            "healthy": overall_health,
            "timestamp": time.time(),
            "components": {
                "ipfs": {"healthy": ipfs_health, "status": ipfs_status},
                "disk": {"healthy": disk_health, "status": disk_status},
                "memory": {"healthy": memory_health, "status": memory_status},
                "storage_backends": storage_backends,
            },
            "monitoring_available": MONITORING_AVAILABLE and monitoring_system is not None,
        }

    return router


def update_metrics_status(storage_backends: Dict[str, Any]) -> None:
    """
    Update storage_backends with monitoring system status.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    # Update monitoring system with storage backends
    if MONITORING_AVAILABLE and monitoring_system is not None:
        try:
            monitoring_system.update_storage_backend_status(storage_backends)
        except Exception as e:
            logger.error(f"Error updating storage backend status: {e}")

    # Add monitoring as a component
    storage_backends["monitoring"] = {
        "available": MONITORING_AVAILABLE and monitoring_system is not None,
        "simulation": False,
        "prometheus_available": PROMETHEUS_AVAILABLE,  # Use the flag from the first import block
        "features": (
            {
                "system_metrics": True,
                "process_metrics": True,
                "api_metrics": True,
                "storage_metrics": True,
                "prometheus_export": PROMETHEUS_AVAILABLE,  # Use the flag from the first import block
            }
            if MONITORING_AVAILABLE and monitoring_system is not None
            else {}
        ),
    }

    logger.debug("Updated monitoring status in storage backends")
