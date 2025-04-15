#!/usr/bin/env python3
"""
Optimized Monitoring Example for MCP Server.

This script demonstrates how to use the optimized metrics collector to address
memory usage issues when tracking many metrics. It shows the memory efficiency
features and adaptive collection capabilities.
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
logger = logging.getLogger("optimized-monitoring-example")

# Add parent directory to path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
    logger.info(f"Added parent directory to path: {parent_dir}")

try:
    # Import FastAPI
    from fastapi import FastAPI, APIRouter, Query, BackgroundTasks

    # Import MCP monitoring modules
    from ipfs_kit_py.mcp.monitoring.prometheus_exporter import get_exporter
    from ipfs_kit_py.mcp.monitoring.health_checker import get_health_checker, HealthStatus, register_component
    from ipfs_kit_py.mcp.monitoring.optimized_metrics import (
        get_optimized_metrics_collector,
        replace_default_collector_with_optimized,
        OptimizedMetricsCollector
    )

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
    optimize_metrics: bool = True,
    # Optimized metrics parameters
    retention_minutes: int = 60,
    max_entries_per_collector: int = 100,
    memory_pressure_threshold: float = 85.0,
    enable_memory_adaptive_collection: bool = True,
):
    """Set up a FastAPI application with optimized monitoring functionality."""
    app = FastAPI(
        title="MCP Optimized Monitoring Demo",
        description="Demonstration of MCP optimized monitoring capabilities",
        version="1.0.0",
    )

    # Create a router for the monitoring endpoints
    monitoring_router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

    # Setup Prometheus exporter if enabled
    exporter = None
    if enable_prometheus:
        logger.info("Setting up Prometheus exporter")
        exporter = get_exporter(
            prefix="mcp_demo",
            enable_default_metrics=True,
            auto_start_server=False,
        )
        exporter.register_with_fastapi(app)

    # Setup health checks if enabled
    health_checker = None
    if enable_health_checks:
        logger.info("Setting up health checks")
        health_checker = get_health_checker(check_interval=30)
        health_checker.register_with_fastapi(app)

        # Register some example components
        register_components_for_health_checks(health_checker)

        # Start automatic health checking
        health_checker.start_auto_checking()

    # Setup metrics collection if enabled
    metrics_collector = None
    if enable_metrics_collection:
        if optimize_metrics:
            logger.info("Setting up optimized metrics collection")
            metrics_collector = get_optimized_metrics_collector(
                prometheus_exporter=exporter if enable_prometheus else None,
                enable_default_collectors=True,
                collection_interval=30,
                retention_minutes=retention_minutes,
                max_entries_per_collector=max_entries_per_collector,
                memory_pressure_threshold=memory_pressure_threshold,
                enable_memory_adaptive_collection=enable_memory_adaptive_collection,
            )
            
            # Replace the default collector with the optimized one
            replace_default_collector_with_optimized()
        else:
            # Use standard metrics collector for comparison
            logger.info("Setting up standard metrics collection")
            from ipfs_kit_py.mcp.monitoring.metrics_collector import get_metrics_collector
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
            "message": "MCP Optimized Monitoring Demo",
            "endpoints": {
                "/docs": "API documentation",
                "/health": "Health check endpoints",
                "/metrics": "Prometheus metrics endpoint",
                "/monitoring/metrics/collect": "Metrics collection endpoints",
                "/monitoring/metrics/history": "Metrics history endpoints (optimized collector only)",
                "/monitoring/metrics/settings": "Metrics settings (optimized collector only)",
                "/monitoring/simulate-memory-pressure": "Simulate memory pressure",
                "/monitoring/simulate-many-collectors": "Simulate many metrics collectors",
            }
        }

    # Add a route to trigger custom metrics collection
    @monitoring_router.get("/trigger-custom-metrics")
    async def trigger_custom_metrics():
        """Trigger collection of custom metrics."""
        if metrics_collector:
            metrics = metrics_collector.collect_metrics("custom")
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
    
    # Add routes specific to the optimized metrics collector
    if enable_metrics_collection and optimize_metrics and isinstance(metrics_collector, OptimizedMetricsCollector):
        @monitoring_router.get("/register-critical-collector")
        async def register_critical_collector(collector: str):
            """Register a collector as critical, ensuring it runs even under memory pressure."""
            metrics_collector.register_critical_collector(collector)
            return {"message": f"Registered {collector} as a critical collector"}
        
        @monitoring_router.get("/unregister-critical-collector")
        async def unregister_critical_collector(collector: str):
            """Unregister a collector as critical."""
            metrics_collector.unregister_critical_collector(collector)
            return {"message": f"Unregistered {collector} as a critical collector"}
        
        @monitoring_router.get("/cleanup-metrics")
        async def cleanup_metrics():
            """Force cleanup of old metrics."""
            metrics_collector._cleanup_old_metrics(force=True)
            return {"message": "Forced cleanup of old metrics"}
        
        @monitoring_router.get("/check-memory-pressure")
        async def check_memory_pressure():
            """Check if the system is under memory pressure."""
            under_pressure = metrics_collector._check_memory_pressure()
            memory = psutil.virtual_memory()
            return {
                "under_memory_pressure": under_pressure,
                "memory_usage_percent": memory.percent,
                "memory_pressure_threshold": metrics_collector.memory_pressure_threshold,
                "adaptive_collection_enabled": metrics_collector.enable_memory_adaptive_collection,
            }
    
    # Add a route to simulate memory pressure
    @monitoring_router.get("/simulate-memory-pressure")
    async def simulate_memory_pressure(background_tasks: BackgroundTasks):
        """
        Simulate memory pressure by creating large objects in memory.
        
        This is useful for testing the memory adaptive collection feature.
        """
        # Define a background task to allocate and then release memory
        def allocate_memory():
            logger.info("Starting memory pressure simulation")
            
            # Store references to prevent garbage collection
            data_chunks = []
            
            try:
                # Create memory pressure by allocating chunks of memory
                for i in range(10):
                    # Allocate a 100MB chunk
                    chunk = bytearray(100 * 1024 * 1024)
                    data_chunks.append(chunk)
                    
                    # Check memory usage
                    memory = psutil.virtual_memory()
                    logger.info(f"Memory usage after chunk {i+1}: {memory.percent:.1f}%")
                    
                    # Give some time for metrics collection to observe the pressure
                    time.sleep(5)
                
                logger.info("Memory pressure simulation complete, holding for 10 seconds")
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in memory simulation: {str(e)}")
                
            finally:
                # Clear references to allow garbage collection
                data_chunks.clear()
                logger.info("Memory pressure released")
        
        # Add the task to run in the background
        background_tasks.add_task(allocate_memory)
        
        return {
            "message": "Started memory pressure simulation in the background",
            "info": "Check logs and metrics to observe the system's response"
        }
    
    # Add a route to simulate many metrics collectors
    @monitoring_router.get("/simulate-many-collectors")
    async def simulate_many_collectors(
        count: int = 100,
        metrics_per_collector: int = 10,
    ):
        """
        Simulate registering many metrics collectors.
        
        This is useful for testing the memory efficiency of the optimized collector.
        """
        if not metrics_collector:
            return {"message": "Metrics collection is disabled"}
        
        # Start registration counter at 0 for this run
        simulate_many_collectors.counter = getattr(simulate_many_collectors, "counter", 0)
        
        for i in range(count):
            collector_id = simulate_many_collectors.counter + i
            collector_name = f"simulated_collector_{collector_id}"
            
            # Create a collector function that generates random metrics
            def create_collector_func(collector_id):
                def collector_func():
                    return {
                        f"metric_{j}": random.uniform(0, 100)
                        for j in range(metrics_per_collector)
                    }
                return collector_func
            
            # Register the collector
            metrics_collector.register_collector(
                collector_name,
                create_collector_func(collector_id)
            )
        
        # Update the counter for the next run
        simulate_many_collectors.counter += count
        
        return {
            "message": f"Registered {count} simulated metrics collectors",
            "total_collectors": simulate_many_collectors.counter,
            "metrics_per_collector": metrics_per_collector,
            "total_metrics": simulate_many_collectors.counter * metrics_per_collector,
        }

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
    
    # Register collectors for different simulated subsystems
    metrics_collector.register_collector("network_traffic", collect_network_traffic_metrics)
    metrics_collector.register_collector("database_queries", collect_database_metrics)
    metrics_collector.register_collector("user_activity", collect_user_activity_metrics)
    metrics_collector.register_collector("content_storage", collect_content_storage_metrics)
    
    # Mark some collectors as critical if using the optimized collector
    if hasattr(metrics_collector, "register_critical_collector"):
        metrics_collector.register_critical_collector("network_traffic")
        metrics_collector.register_critical_collector("database_queries")
    
    logger.info("Registered custom metrics collectors")

def collect_custom_metrics():
    """Example custom metrics collector function."""
    # Simulate collecting some custom metrics
    return {
        "example_counter": random.randint(1, 100),
        "example_gauge": random.uniform(0, 100),
        "example_response_time": random.uniform(0.1, 2.0),
        "example_success_rate": random.uniform(90, 100),
    }

def collect_network_traffic_metrics():
    """Simulated network traffic metrics collector."""
    return {
        "bytes_sent": random.randint(1000, 10000000),
        "bytes_received": random.randint(1000, 10000000),
        "active_connections": random.randint(1, 100),
        "connection_errors": random.randint(0, 10),
        "average_latency_ms": random.uniform(1, 100),
        "packets_dropped": random.randint(0, 100),
    }

def collect_database_metrics():
    """Simulated database performance metrics collector."""
    return {
        "query_count": random.randint(100, 1000),
        "average_query_time_ms": random.uniform(1, 50),
        "active_connections": random.randint(1, 20),
        "connection_pool_usage": random.uniform(0, 100),
        "cache_hit_ratio": random.uniform(0, 100),
        "slow_queries": random.randint(0, 10),
    }

def collect_user_activity_metrics():
    """Simulated user activity metrics collector."""
    return {
        "active_users": random.randint(1, 1000),
        "new_users": random.randint(0, 100),
        "api_requests": random.randint(100, 10000),
        "content_uploads": random.randint(0, 500),
        "content_downloads": random.randint(0, 2000),
        "search_queries": random.randint(0, 1000),
    }

def collect_content_storage_metrics():
    """Simulated content storage metrics collector."""
    return {
        "total_content_count": random.randint(1000, 1000000),
        "total_size_bytes": random.randint(1024*1024, 1024*1024*1024*10),
        "average_content_size_bytes": random.randint(1024, 1024*1024),
        "pinned_content_count": random.randint(100, 10000),
        "content_by_type": {
            "images": random.randint(100, 10000),
            "videos": random.randint(10, 1000),
            "documents": random.randint(100, 5000),
            "other": random.randint(100, 5000),
        },
    }

async def main():
    """Run the optimized monitoring example."""
    parser = argparse.ArgumentParser(description="MCP Optimized Monitoring Example")
    parser.add_argument("--port", type=int, default=8000, help="Port for the API server")
    parser.add_argument("--no-prometheus", action="store_true", help="Disable Prometheus metrics")
    parser.add_argument("--no-health", action="store_true", help="Disable health checks")
    parser.add_argument("--no-metrics", action="store_true", help="Disable metrics collection")
    parser.add_argument("--no-optimize", action="store_true", help="Use standard metrics collector instead of optimized")
    parser.add_argument("--retention", type=int, default=60, help="Retention time in minutes for metrics history")
    parser.add_argument("--max-entries", type=int, default=100, help="Maximum entries per metrics collector")
    parser.add_argument("--memory-threshold", type=float, default=85.0, help="Memory pressure threshold percentage")
    parser.add_argument("--no-adaptive", action="store_true", help="Disable memory-adaptive collection")
    
    args = parser.parse_args()

    if not imports_succeeded:
        logger.error("Required modules could not be imported. Exiting...")
        sys.exit(1)

    # Setup FastAPI app with monitoring
    app = setup_api(
        enable_prometheus=not args.no_prometheus,
        enable_health_checks=not args.no_health,
        enable_metrics_collection=not args.no_metrics,
        optimize_metrics=not args.no_optimize,
        retention_minutes=args.retention,
        max_entries_per_collector=args.max_entries,
        memory_pressure_threshold=args.memory_threshold,
        enable_memory_adaptive_collection=not args.no_adaptive,
    )

    # Start uvicorn server
    import uvicorn
    logger.info(f"Starting server on port {args.port}")
    logger.info(f"Metrics optimization: {'ENABLED' if not args.no_optimize else 'DISABLED'}")
    logger.info(f"Memory-adaptive collection: {'ENABLED' if not args.no_adaptive else 'DISABLED'}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
