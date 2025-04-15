#!/usr/bin/env python3
"""
Monitoring Example for MCP Server.

This script demonstrates how to use the MCP monitoring functionality,
including Prometheus metrics export, health checks, and metrics collection.
"""

import os
import sys
import time
import asyncio
import logging
import argparse
import random
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("monitoring-example")

# Add parent directory to path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
    logger.info(f"Added parent directory to path: {parent_dir}")

try:
    # Import FastAPI
    from fastapi import FastAPI, APIRouter

    # Import MCP monitoring modules
    from ipfs_kit_py.mcp.monitoring.prometheus_exporter import get_exporter, PrometheusExporter
    from ipfs_kit_py.mcp.monitoring.health_checker import get_health_checker, HealthStatus, register_component
    from ipfs_kit_py.mcp.monitoring.metrics_collector import get_metrics_collector

    # Import psutil for system metrics
    import psutil

    imports_succeeded = True
    logger.info("Successfully imported required modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    imports_succeeded = False

def setup_api(
    enable_prometheus: bool = True,
    enable_health_checks: bool = True,
    enable_metrics_collection: bool = True,
):
    """Set up a FastAPI application with monitoring functionality."""
    app = FastAPI(
        title="MCP Monitoring Demo",
        description="Demonstration of MCP monitoring capabilities",
        version="1.0.0",
    )

    # Create a router for the monitoring endpoints
    monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

    # Setup Prometheus exporter if enabled
    if enable_prometheus:
        logger.info("Setting up Prometheus exporter")
        exporter = get_exporter(
            prefix="mcp_demo",
            enable_default_metrics=True,
            auto_start_server=False,
        )
        exporter.register_with_fastapi(app)

    # Setup health checks if enabled
    if enable_health_checks:
        logger.info("Setting up health checks")
        health_checker = get_health_checker(check_interval=30)
        health_checker.register_with_fastapi(app)

        # Register some example components
        register_components_for_health_checks(health_checker)

        # Start automatic health checking
        health_checker.start_auto_checking()

    # Setup metrics collection if enabled
    if enable_metrics_collection:
        logger.info("Setting up metrics collection")
        metrics_collector = get_metrics_collector(
            prometheus_exporter=exporter if enable_prometheus else None,
            enable_default_collectors=True,
            collection_interval=30,
        )
        metrics_collector.register_with_fastapi(app)

        # Register some example custom metrics collectors
        register_custom_metrics_collectors(metrics_collector)

        # Start automatic metrics collection
        metrics_collector.start_auto_collection()

    # Add a simple home route to the main app
    @app.get("/")
    async def home():
        return {
            "message": "MCP Monitoring Demo",
            "endpoints": {
                "/docs": "API documentation",
                "/health": "Health check endpoints",
                "/metrics": "Prometheus metrics endpoint",
                "/monitoring/metrics/collect": "Metrics collection endpoints",
            }
        }

    # Add a route to trigger custom metrics collection
    @monitoring_router.get("/trigger-custom-metrics")
    async def trigger_custom_metrics():
        """Trigger collection of custom metrics."""
        if enable_metrics_collection:
            metrics = get_metrics_collector().collect_metrics("custom")
            return {"message": "Custom metrics collected", "metrics": metrics}
        else:
            return {"message": "Metrics collection is disabled"}

    # Add a route to simulate component health status changes
    @monitoring_router.get("/simulate-health-change")
    async def simulate_health_change(component: str = "api", status: str = "ok"):
        """Simulate a health status change for a component."""
        if enable_health_checks:
            try:
                health_status = HealthStatus(status)
                get_health_checker().update_component_health(
                    component=component,
                    status=health_status,
                    details=f"Simulated status change to {status}",
                )
                return {"message": f"Health status of {component} changed to {status}"}
            except ValueError:
                return {"error": f"Invalid status '{status}'. Valid values are: {[s.value for s in HealthStatus]}"}
        else:
            return {"message": "Health checks are disabled"}

    # Add a route to track example operations with Prometheus
    @monitoring_router.get("/track-example-operation")
    async def track_example_operation(operation: str = "read", succeed: bool = True):
        """Track an example operation with Prometheus metrics."""
        if enable_prometheus:
            # Simulate a random operation duration between 0.1 and 2 seconds
            duration = random.uniform(0.1, 2.0)
            time.sleep(duration)

            exporter = get_exporter()
            exporter.track_api_request(
                endpoint="/api/example",
                method="GET",
                status_code=200 if succeed else 500,
                duration_seconds=duration,
            )

            # Track a simulated storage operation
            exporter.track_storage_operation(
                operation=operation,
                backend="example",
                success=succeed,
                size_bytes=random.randint(1024, 1024 * 1024),  # 1KB to 1MB
            )

            return {
                "message": f"Tracked example {operation} operation",
                "success": succeed,
                "duration": duration,
            }
        else:
            return {"message": "Prometheus metrics are disabled"}

    # Register the monitoring router with the app
    app.include_router(monitoring_router)

    return app

def register_components_for_health_checks(health_checker):
    """Register example components for health checking."""
    # Register the API component
    health_checker.register_component(
        component="api",
        check_function=check_api_health,
        initial_status=HealthStatus.OK,
        initial_details="API is operational",
    )

    # Register the database component
    health_checker.register_component(
        component="database",
        check_function=check_database_health,
        initial_status=HealthStatus.OK,
        initial_details="Database is operational",
    )

    # Register the storage component
    health_checker.register_component(
        component="storage",
        check_function=check_storage_health,
        initial_status=HealthStatus.OK,
        initial_details="Storage is operational",
    )

    # Register the IPFS component
    health_checker.register_component(
        component="ipfs",
        check_function=check_ipfs_health,
        initial_status=HealthStatus.OK,
        initial_details="IPFS is operational",
    )

    logger.info("Registered example components for health checking")

def check_api_health():
    """Example health check function for the API component."""
    # Simulate API health check (always healthy in this example)
    return HealthStatus.OK, "API is responding normally"

def check_database_health():
    """Example health check function for the database component."""
    # Simulate database health check with random failures
    if random.random() < 0.05:  # 5% chance of degraded status
        return HealthStatus.DEGRADED, "Database performance is degraded"
    elif random.random() < 0.01:  # 1% chance of failure
        return HealthStatus.FAILING, "Database connection failed"
    else:
        return HealthStatus.OK, "Database is operational"

def check_storage_health():
    """Example health check function for the storage component."""
    # Simulate storage health check based on actual disk usage
    try:
        disk_usage = psutil.disk_usage(os.getcwd())
        if disk_usage.percent > 90:
            return HealthStatus.DEGRADED, f"Storage is almost full: {disk_usage.percent}% used"
        elif disk_usage.percent > 95:
            return HealthStatus.FAILING, f"Storage is critically full: {disk_usage.percent}% used"
        else:
            return HealthStatus.OK, f"Storage is operational: {disk_usage.percent}% used"
    except Exception as e:
        return HealthStatus.UNKNOWN, f"Error checking storage health: {str(e)}"

def check_ipfs_health():
    """Example health check function for the IPFS component."""
    # Simulate IPFS health check with occasional random failures
    if random.random() < 0.02:  # 2% chance of connection issues
        return HealthStatus.DEGRADED, "IPFS connection is unstable"
    else:
        return HealthStatus.OK, "IPFS is connected and operational"

def register_custom_metrics_collectors(metrics_collector):
    """Register custom metrics collectors."""
    # Register a custom metrics collector
    metrics_collector.register_collector("custom", collect_custom_metrics)
    logger.info("Registered custom metrics collector")

def collect_custom_metrics():
    """Example custom metrics collector function."""
    # Simulate collecting some custom metrics
    return {
        "example_counter": random.randint(1, 100),
        "example_gauge": random.uniform(0, 100),
        "example_response_time": random.uniform(0.1, 2.0),
        "example_success_rate": random.uniform(90, 100),
    }

async def main():
    """Run the monitoring example."""
    parser = argparse.ArgumentParser(description="MCP Monitoring Example")
    parser.add_argument("--port", type=int, default=8000, help="Port for the API server")
    parser.add_argument("--no-prometheus", action="store_true", help="Disable Prometheus metrics")
    parser.add_argument("--no-health", action="store_true", help="Disable health checks")
    parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
    args = parser.parse_args()

    if not imports_succeeded:
        logger.error("Required modules could not be imported. Exiting...")
        sys.exit(1)

    # Setup FastAPI app with monitoring
    app = setup_api(
        enable_prometheus=not args.no_prometheus,
        enable_health_checks=not args.no_health,
        enable_metrics_collection=not args.no_metrics,
    )

    # Start uvicorn server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
