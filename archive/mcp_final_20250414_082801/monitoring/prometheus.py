"""
Prometheus monitoring integration for MCP.
"""

import logging
import platform

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

# Configure logger
logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
except ImportError:
    logger.warning("Prometheus client library not available, metrics will be disabled")
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain"


# Metrics collection class
class PrometheusMetricsCollector:
    """Collect and expose Prometheus metrics for MCP."""

    def __init__(self, config=None):
        """Initialize metrics collector with configuration."""
        self.config = config or {}
        self.enabled = self.config.get("enabled", PROMETHEUS_AVAILABLE)
        self.port = self.config.get("port", 9090)
        self.endpoint = self.config.get("endpoint", "/metrics")
        self.collection_interval = self.config.get("collection_interval", 15)
        self.registry = REGISTRY
        self.server_started = False
        self.metrics = {}
        self.collection_thread = None
        self.running = False

        if self.enabled and PROMETHEUS_AVAILABLE:
            self._setup_metrics()
        else:
            logger.info("Prometheus metrics collection is disabled")

    def _setup_metrics(self):
        """Set up metrics collectors."""
        # System metrics
        self.metrics["system_info"] = Info("mcp_system_info", "System information")
        self.metrics["system_cpu_usage"] = Gauge("mcp_system_cpu_usage", "System CPU usage percent")
        self.metrics["system_memory_usage"] = Gauge(
            "mcp_system_memory_usage", "System memory usage in bytes"
        )
        self.metrics["system_memory_percent"] = Gauge(
            "mcp_system_memory_percent", "System memory usage percent"
        )
        self.metrics["system_disk_usage"] = Gauge(
            "mcp_system_disk_usage", "System disk usage in bytes"
        )
        self.metrics["system_disk_percent"] = Gauge(
            "mcp_system_disk_percent", "System disk usage percent"
        )

        # IPFS metrics
        self.metrics["ipfs_operations_total"] = Counter(
            "mcp_ipfs_operations_total", "Total IPFS operations", ["operation", "status"]
        )
        self.metrics["ipfs_operation_duration"] = Histogram(
            "mcp_ipfs_operation_duration", "IPFS operation duration in seconds", ["operation"]
        )
        self.metrics["ipfs_peers_connected"] = Gauge(
            "mcp_ipfs_peers_connected", "Number of connected IPFS peers"
        )
        self.metrics["ipfs_repo_size"] = Gauge(
            "mcp_ipfs_repo_size", "IPFS repository size in bytes"
        )
        self.metrics["ipfs_bandwidth_total"] = Counter(
            "mcp_ipfs_bandwidth_total", "Total IPFS bandwidth usage in bytes", ["direction"]
        )

        # Storage metrics
        self.metrics["storage_operations_total"] = Counter(
            "mcp_storage_operations_total",
            "Total storage operations",
            ["backend", "operation", "status"],
        )
        self.metrics["storage_operation_duration"] = Histogram(
            "mcp_storage_operation_duration",
            "Storage operation duration in seconds",
            ["backend", "operation"],
        )
        self.metrics["storage_size"] = Gauge(
            "mcp_storage_size", "Storage size in bytes", ["backend"]
        )
        self.metrics["storage_objects"] = Gauge(
            "mcp_storage_objects", "Number of objects in storage", ["backend"]
        )

        # API metrics
        self.metrics["api_requests_total"] = Counter(
            "mcp_api_requests_total", "Total API requests", ["method", "endpoint", "status_code"]
        )
        self.metrics["api_request_duration"] = Histogram(
            "mcp_api_request_duration", "API request duration in seconds", ["method", "endpoint"]
        )

        # System information
        self.metrics["system_info"].info(
            {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "processor": platform.processor(),
                "hostname": platform.node(),
            }
        )

        logger.info("Prometheus metrics collectors initialized")

    def get_metrics(self):
        """Get current metrics as text."""
        if not PROMETHEUS_AVAILABLE:
            return "Prometheus metrics not available", 503

        try:
            # Generate latest metrics
            prometheus_data = generate_latest()
            return prometheus_data, 200, {"Content-Type": CONTENT_TYPE_LATEST}
        except Exception as e:
            logger.error(f"Error generating Prometheus metrics: {e}")
            return f"Error generating metrics: {e}", 500


# Singleton instance
metrics_collector = None


def get_metrics_collector(config=None):
    """Get or create the metrics collector singleton."""
    global metrics_collector
    if metrics_collector is None:
        metrics_collector = PrometheusMetricsCollector(config)
    return metrics_collector
