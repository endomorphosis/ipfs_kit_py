# ipfs_kit_py/wal_telemetry_prometheus_anyio.py

"""
Prometheus integration for WAL telemetry with AnyIO support.

This module provides Prometheus integration for the WAL telemetry system with
AnyIO support, allowing WAL performance metrics to be exposed in Prometheus
format for monitoring with Prometheus, Grafana, and other observability tools
while working with any async backend.
"""

import time
import logging
import warnings
import threading
from typing import Dict, List, Any, Optional, Union, Set

import anyio
import sniffio

# Try to import the WAL telemetry module
try:
    from .wal_telemetry import (
        WALTelemetry,
        TelemetryMetricType,
        TelemetryAggregation
    )
    WAL_TELEMETRY_AVAILABLE = True
except ImportError:
    WAL_TELEMETRY_AVAILABLE = False
    
# Try to import Prometheus client
try:
    import prometheus_client
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, 
        CollectorRegistry, start_http_server
    )
    from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    
    # Create dummy classes for type checking
    class Counter:
        def inc(self, value=1):
            pass
        
    class Gauge:
        def set(self, value):
            pass
        
    class Histogram:
        def observe(self, value):
            pass
            
    class Summary:
        def observe(self, value):
            pass
    
    class CollectorRegistry:
        def __init__(self):
            pass
    
    class GaugeMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass
            
    class CounterMetricFamily:
        def __init__(self, *args, **kwargs):
            pass
        def add_metric(self, *args, **kwargs):
            pass

# Configure logging
logger = logging.getLogger(__name__)

class WALTelemetryCollector:
    """
    Prometheus collector for WAL telemetry metrics.
    
    This collector integrates with the WAL telemetry system to expose
    performance metrics in a format that can be scraped by Prometheus.
    """
    
    def __init__(self, telemetry: Any, prefix: str = "wal"):
        """
        Initialize the WAL telemetry collector.
        
        Args:
            telemetry: WALTelemetry instance to collect metrics from
            prefix: Prefix for metric names (default: "wal")
        """
        if not WAL_TELEMETRY_AVAILABLE:
            raise ImportError("WAL telemetry module not available")
            
        self.telemetry = telemetry
        self.prefix = prefix
        self.last_update = 0
        self.update_interval = 5  # seconds
        self.known_operation_types = set()
        self.known_backends = set()
        self.rt_metrics = {}
        
    def collect(self):
        """
        Collect WAL telemetry metrics for Prometheus.
        
        This method is called by Prometheus client during scraping.
        It returns a list of metrics in Prometheus format.
        """
        # Update metrics at most once per update_interval
        current_time = time.time()
        if current_time - self.last_update > self.update_interval:
            # Get real-time metrics
            self.rt_metrics = self.telemetry.get_real_time_metrics()
            self.last_update = current_time
            
            # Update operation types and backends for dimension tracking
            for key in self.rt_metrics.get("latency", {}):
                if ":" in key:
                    op_type, backend = key.split(":", 1)
                    self.known_operation_types.add(op_type)
                    self.known_backends.add(backend)
        
        # Define and yield metrics
        metrics = []
        
        # 1. Operation latency metrics
        for metric_name, stat_name in [
            ("latency_seconds", "mean"),
            ("latency_seconds_median", "median"),
            ("latency_seconds_max", "max"),
            ("latency_seconds_min", "min"),
            ("latency_seconds_p95", "percentile_95")
        ]:
            metric = GaugeMetricFamily(
                f"{self.prefix}_operation_{metric_name}",
                f"Operation {stat_name.replace('_', ' ')} latency in seconds",
                labels=["operation_type", "backend"]
            )
            
            for key, stats in self.rt_metrics.get("latency", {}).items():
                if ":" in key:
                    op_type, backend = key.split(":", 1)
                    metric.add_metric([op_type, backend], stats.get(stat_name, 0))
                    
            yield metric
        
        # 2. Success rate metrics
        success_rate = GaugeMetricFamily(
            f"{self.prefix}_operation_success_rate",
            "Operation success rate (0-1)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("success_rate", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                success_rate.add_metric([op_type, backend], rate)
                
        yield success_rate
        
        # 3. Error rate metrics
        error_rate = GaugeMetricFamily(
            f"{self.prefix}_operation_error_rate",
            "Operation error rate (0-1)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("error_rate", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                error_rate.add_metric([op_type, backend], rate)
                
        yield error_rate
        
        # 4. Throughput metrics
        throughput = GaugeMetricFamily(
            f"{self.prefix}_operations_per_minute",
            "Operation throughput (operations per minute)",
            labels=["operation_type", "backend"]
        )
        
        for key, rate in self.rt_metrics.get("throughput", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                throughput.add_metric([op_type, backend], rate)
                
        yield throughput
        
        # 5. Operation status counts
        status_counts = GaugeMetricFamily(
            f"{self.prefix}_operations_by_status",
            "Number of operations by status",
            labels=["operation_type", "backend", "status"]
        )
        
        for key, counts in self.rt_metrics.get("status_distribution", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                for status, count in counts.items():
                    status_counts.add_metric([op_type, backend, status], count)
                    
        yield status_counts
        
        # If we have access to the WAL instance via telemetry, get more metrics
        if hasattr(self.telemetry, "wal") and self.telemetry.wal:
            wal = self.telemetry.wal
            
            # 6. Queue metrics
            queue_size = GaugeMetricFamily(
                f"{self.prefix}_queue_size",
                "Number of operations in queue",
                labels=["status"]
            )
            
            try:
                stats = wal.get_statistics()
                for status, count in stats.items():
                    if status in ["pending", "processing", "total_operations"]:
                        queue_size.add_metric([status], count)
            except Exception as e:
                logger.warning(f"Error getting WAL statistics: {e}")
                
            yield queue_size
            
            # 7. Backend health metrics
            if hasattr(wal, "health_monitor") and wal.health_monitor:
                backend_health = GaugeMetricFamily(
                    f"{self.prefix}_backend_health",
                    "Backend health status (1=online, 0.5=degraded, 0=offline)",
                    labels=["backend"]
                )
                
                try:
                    statuses = wal.health_monitor.get_status()
                    for backend, status_info in statuses.items():
                        # Convert status to numeric value
                        status_value = 1.0 if status_info.get("status") == "online" else \
                                       0.5 if status_info.get("status") == "degraded" else 0.0
                        backend_health.add_metric([backend], status_value)
                except Exception as e:
                    logger.warning(f"Error getting backend health: {e}")
                    
                yield backend_health
                
                # 8. Backend response time
                backend_latency = GaugeMetricFamily(
                    f"{self.prefix}_backend_response_time_seconds",
                    "Backend response time in seconds",
                    labels=["backend"]
                )
                
                try:
                    for backend, status_info in statuses.items():
                        latency = status_info.get("last_response_time", 0)
                        backend_latency.add_metric([backend], latency)
                except Exception as e:
                    logger.warning(f"Error getting backend latency: {e}")
                    
                yield backend_latency

class WALTelemetryPrometheusExporterAnyIO:
    """
    Prometheus exporter for WAL telemetry with AnyIO support.
    
    This class provides a Prometheus exporter for WAL telemetry metrics,
    making them available for scraping by Prometheus monitoring systems.
    It supports both synchronous and asynchronous usage with AnyIO.
    """
    
    def __init__(self, 
                 telemetry: Any, 
                 prefix: str = "wal",
                 registry: Optional[CollectorRegistry] = None):
        """
        Initialize the WAL telemetry Prometheus exporter with AnyIO support.
        
        Args:
            telemetry: WALTelemetry instance to expose metrics from
            prefix: Prefix for metric names (default: "wal")
            registry: Custom Prometheus registry (default: create new)
        """
        if not WAL_TELEMETRY_AVAILABLE:
            raise ImportError("WAL telemetry module not available")
            
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("Prometheus client not available")
            
        self.telemetry = telemetry
        self.prefix = prefix
        self.registry = registry or CollectorRegistry()
        
        # Create and register collector
        self.collector = WALTelemetryCollector(telemetry, prefix)
        self.registry.register(self.collector)
        
        # Create thread-safe lock for server management
        self._lock = threading.RLock()
        self._server = None
        self._server_port = None

    @staticmethod
    def get_backend() -> Optional[str]:
        """
        Get the current async backend being used.
        
        Returns:
            String identifying the async library or None if not in async context
        """
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name: str) -> None:
        """
        Warn if a synchronous method is called from an async context.
        
        Args:
            method_name: Name of the method being called
        """
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    def start_server(self, port: int = 9100, addr: str = "") -> bool:
        """
        Start a metrics server for Prometheus scraping.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
            
        Returns:
            True if server started successfully, False otherwise
        """
        # Warn if called from async context
        self._warn_if_async_context("start_server")
        
        with self._lock:
            if self._server is not None:
                logger.warning(f"Prometheus server already running on port {self._server_port}")
                return False
                
            try:
                # Check that port is available
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex((addr or "localhost", port))
                sock.close()
                
                if result == 0:
                    logger.error(f"Port {port} is already in use")
                    return False
                
                # Start HTTP server for metrics
                prometheus_client.start_http_server(port, addr, self.registry)
                self._server_port = port
                logger.info(f"Started Prometheus metrics server on {addr or '0.0.0.0'}:{port}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                return False
    
    async def start_server_async(self, port: int = 9100, addr: str = "") -> bool:
        """
        Start a metrics server for Prometheus scraping asynchronously.
        
        Args:
            port: Port to listen on
            addr: Address to bind to
            
        Returns:
            True if server started successfully, False otherwise
        """
        # Use anyio.to_thread.run_sync to run the synchronous logic
        # in a separate thread to avoid blocking
        return await anyio.to_thread.run_sync(
            self.start_server,
            port=port,
            addr=addr
        )
    
    def stop_server(self) -> bool:
        """
        Stop the metrics server.
        
        Returns:
            True if server stopped successfully, False otherwise
        """
        # Warn if called from async context
        self._warn_if_async_context("stop_server")
        
        with self._lock:
            if self._server is None:
                logger.warning("Prometheus server not running")
                return False
                
            try:
                # Unfortunately, prometheus_client doesn't provide a clean way to stop the server
                # We'll need to implement this manually if needed
                logger.warning("Stopping Prometheus server not implemented")
                return False
                
            except Exception as e:
                logger.error(f"Failed to stop Prometheus metrics server: {e}")
                return False
    
    async def stop_server_async(self) -> bool:
        """
        Stop the metrics server asynchronously.
        
        Returns:
            True if server stopped successfully, False otherwise
        """
        return await anyio.to_thread.run_sync(self.stop_server)
    
    def generate_latest(self) -> bytes:
        """
        Generate Prometheus metrics output in text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        # Warn if called from async context
        self._warn_if_async_context("generate_latest")
        
        if not PROMETHEUS_AVAILABLE:
            return b""
            
        return prometheus_client.generate_latest(self.registry)
    
    async def generate_latest_async(self) -> bytes:
        """
        Generate Prometheus metrics output in text format asynchronously.
        
        Returns:
            Metrics in Prometheus text format
        """
        if not PROMETHEUS_AVAILABLE:
            return b""
        
        # Use anyio.to_thread.run_sync to run the synchronous logic
        # in a separate thread to avoid blocking
        return await anyio.to_thread.run_sync(
            lambda: prometheus_client.generate_latest(self.registry)
        )

async def add_wal_metrics_endpoint_async(app, telemetry, path: str = "/metrics/wal"):
    """
    Add a WAL telemetry metrics endpoint to a FastAPI application with AnyIO support.
    
    Args:
        app: FastAPI application instance
        telemetry: WALTelemetry instance
        path: Endpoint path for metrics
        
    Returns:
        True if successful, False otherwise
    """
    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available, skipping metrics endpoint")
        return False
        
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, skipping metrics endpoint")
        return False
        
    try:
        from fastapi import Request
        from fastapi.responses import Response
        
        # Create exporter
        exporter = WALTelemetryPrometheusExporterAnyIO(telemetry, prefix="wal")
        
        # Add endpoint
        @app.get(path)
        async def wal_metrics(request: Request):
            content = await exporter.generate_latest_async()
            return Response(
                content=content,
                media_type="text/plain"
            )
            
        logger.info(f"Added WAL metrics endpoint at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add WAL metrics endpoint: {e}")
        return False

def add_wal_metrics_endpoint(app, telemetry, path: str = "/metrics/wal", use_anyio: bool = False):
    """
    Add a WAL telemetry metrics endpoint to a FastAPI application.
    
    Args:
        app: FastAPI application instance
        telemetry: WALTelemetry instance
        path: Endpoint path for metrics
        use_anyio: Whether to use AnyIO implementation
        
    Returns:
        True if successful, False otherwise
    """
    # Check if we're in an async context
    in_async_context = False
    try:
        sniffio.current_async_library()
        in_async_context = True
    except sniffio.AsyncLibraryNotFoundError:
        pass
    
    # Prefer AnyIO implementation if specified or if in async context
    if use_anyio or in_async_context:
        # Run the async version of the function
        import anyio
        try:
            loop = anyio.get_event_loop()
        except RuntimeError:
            # No event loop in this thread, create one
            loop = anyio.new_event_loop()
            anyio.set_event_loop(loop)
        
        return loop.run_until_complete(add_wal_metrics_endpoint_async(app, telemetry, path))
    
    # Fall back to original implementation
    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available, skipping metrics endpoint")
        return False
        
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, skipping metrics endpoint")
        return False
        
    try:
        from fastapi import Request
        from fastapi.responses import Response
        
        # Import original exporter
        from .wal_telemetry_prometheus import WALTelemetryPrometheusExporter
        
        # Create exporter
        exporter = WALTelemetryPrometheusExporter(telemetry, prefix="wal")
        
        # Add endpoint
        @app.get(path)
        async def wal_metrics(request: Request):
            return Response(
                content=exporter.generate_latest(),
                media_type="text/plain"
            )
            
        logger.info(f"Added WAL metrics endpoint at {path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add WAL metrics endpoint: {e}")
        return False

# Function to get the appropriate exporter based on context
def get_prometheus_exporter(telemetry, prefix: str = "wal", 
                          registry: Optional[CollectorRegistry] = None,
                          use_anyio: Optional[bool] = None):
    """
    Get the appropriate Prometheus exporter based on context.
    
    Args:
        telemetry: WALTelemetry instance
        prefix: Prefix for metric names
        registry: Custom Prometheus registry
        use_anyio: Whether to use AnyIO implementation (auto-detect if None)
        
    Returns:
        Appropriate WALTelemetryPrometheusExporter instance
    """
    if not WAL_TELEMETRY_AVAILABLE:
        raise ImportError("WAL telemetry module not available")
        
    if not PROMETHEUS_AVAILABLE:
        raise ImportError("Prometheus client not available")
    
    # Auto-detect if not specified
    if use_anyio is None:
        try:
            sniffio.current_async_library()
            use_anyio = True
        except sniffio.AsyncLibraryNotFoundError:
            use_anyio = False
    
    if use_anyio:
        return WALTelemetryPrometheusExporterAnyIO(
            telemetry=telemetry, 
            prefix=prefix,
            registry=registry
        )
    else:
        from .wal_telemetry_prometheus import WALTelemetryPrometheusExporter
        return WALTelemetryPrometheusExporter(
            telemetry=telemetry, 
            prefix=prefix,
            registry=registry
        )

# Example usage
if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    
    if not WAL_TELEMETRY_AVAILABLE:
        print("WAL telemetry module not available")
        exit(1)
        
    if not PROMETHEUS_AVAILABLE:
        print("Prometheus client not available. Install with 'pip install prometheus-client'")
        exit(1)
    
    # Synchronous usage example
    def sync_example():
        try:
            from ipfs_kit_py.wal_telemetry import WALTelemetry
            from ipfs_kit_py.storage_wal import (
                StorageWriteAheadLog, 
                BackendHealthMonitor
            )
            
            # Create WAL components
            health_monitor = BackendHealthMonitor(
                check_interval=5,
                history_size=10
            )
            
            wal = StorageWriteAheadLog(
                base_path="~/.ipfs_kit/wal",
                partition_size=100,
                health_monitor=health_monitor
            )
            
            # Create telemetry instance
            telemetry = WALTelemetry(
                wal=wal,
                metrics_path="~/.ipfs_kit/telemetry",
                sampling_interval=10,
                enable_detailed_timing=True,
                operation_hooks=True
            )
            
            # Create Prometheus exporter
            exporter = WALTelemetryPrometheusExporterAnyIO(telemetry)
            
            # Start metrics server
            exporter.start_server(port=9101)
            
            print("Prometheus metrics server running on port 9101")
            print("Press Ctrl+C to exit")
            
            # Add some operations to generate telemetry data
            for i in range(5):
                result = wal.add_operation(
                    operation_type="add",
                    backend="ipfs",
                    parameters={"path": f"/tmp/file{i}.txt"}
                )
                print(f"Added operation: {result['operation_id']}")
                
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Exiting...")
            finally:
                # Clean up
                telemetry.close()
                wal.close()
                health_monitor.close()
                
        except ImportError as e:
            print(f"Error importing required modules: {e}")
            exit(1)
    
    # Async usage example
    async def async_example():
        try:
            from ipfs_kit_py.wal_telemetry import WALTelemetry
            from ipfs_kit_py.storage_wal import (
                StorageWriteAheadLog, 
                BackendHealthMonitor
            )
            
            # Create WAL components
            health_monitor = BackendHealthMonitor(
                check_interval=5,
                history_size=10
            )
            
            # Create components synchronously (they don't have async APIs)
            # but run in a separate thread to avoid blocking
            wal = await anyio.to_thread.run_sync(
                lambda: StorageWriteAheadLog(
                    base_path="~/.ipfs_kit/wal",
                    partition_size=100,
                    health_monitor=health_monitor
                )
            )
            
            # Create telemetry instance
            telemetry = await anyio.to_thread.run_sync(
                lambda: WALTelemetry(
                    wal=wal,
                    metrics_path="~/.ipfs_kit/telemetry",
                    sampling_interval=10,
                    enable_detailed_timing=True,
                    operation_hooks=True
                )
            )
            
            # Create Prometheus exporter
            exporter = WALTelemetryPrometheusExporterAnyIO(telemetry)
            
            # Start metrics server asynchronously
            success = await exporter.start_server_async(port=9101)
            
            if success:
                print("Prometheus metrics server running on port 9101")
                print("Press Ctrl+C to exit")
                
                # Add some operations to generate telemetry data
                for i in range(5):
                    # Use anyio.to_thread.run_sync to run synchronous operations
                    # in a separate thread
                    result = await anyio.to_thread.run_sync(
                        lambda idx=i: wal.add_operation(
                            operation_type="add",
                            backend="ipfs",
                            parameters={"path": f"/tmp/file{idx}.txt"}
                        )
                    )
                    print(f"Added operation: {result['operation_id']}")
                    
                # Keep running until interrupted
                try:
                    # Sleep asynchronously to avoid blocking the event loop
                    while True:
                        await anyio.sleep(1)
                except KeyboardInterrupt:
                    print("Exiting...")
                finally:
                    # Clean up - run synchronous methods in separate thread
                    await anyio.to_thread.run_sync(telemetry.close)
                    await anyio.to_thread.run_sync(wal.close)
                    await anyio.to_thread.run_sync(health_monitor.close)
            else:
                print("Failed to start metrics server")
                
        except ImportError as e:
            print(f"Error importing required modules: {e}")
            exit(1)
    
    # Uncomment to run sync example
    # sync_example()
    
    # Uncomment to run async example with asyncio
    # import anyio
    # anyio.run(async_example())
    
    # Uncomment to run async example with trio
    # import trio
    # trio.run(async_example)