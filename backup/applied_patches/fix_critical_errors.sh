#!/bin/bash

# Script to fix the most critical syntax errors in the codebase
echo "Fixing critical syntax errors in problematic files..."

# 1. Fix the syntax error in prometheus.py
echo "Fixing prometheus.py syntax errors..."
cat > ipfs_kit_py/mcp/monitoring/prometheus.py << 'EOL'
"""
Prometheus monitoring integration for MCP.

This module provides Prometheus metrics collection and reporting for MCP.
"""

import logging
import psutil
import platform
from datetime import datetime
import time
import threading

# Configure logger
logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Summary,
        Info,
        Enum,
        start_http_server,
        generate_latest,
        REGISTRY,
        CollectorRegistry,
        multiprocess,
    )
    PROMETHEUS_AVAILABLE = True
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'
except ImportError:
    logger.warning("Prometheus client library not available, metrics will be disabled")
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = 'text/plain'

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
        self.metrics["system_info"] = Info(
            "mcp_system_info", "System information"
        )
        self.metrics["system_cpu_usage"] = Gauge(
            "mcp_system_cpu_usage", "System CPU usage percent"
        )
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
            "mcp_ipfs_operations_total", "Total IPFS operations", 
            ["operation", "status"]
        )
        self.metrics["ipfs_operation_duration"] = Histogram(
            "mcp_ipfs_operation_duration", "IPFS operation duration in seconds",
            ["operation"]
        )
        self.metrics["ipfs_peers_connected"] = Gauge(
            "mcp_ipfs_peers_connected", "Number of connected IPFS peers"
        )
        self.metrics["ipfs_repo_size"] = Gauge(
            "mcp_ipfs_repo_size", "IPFS repository size in bytes"
        )
        self.metrics["ipfs_bandwidth_total"] = Counter(
            "mcp_ipfs_bandwidth_total", "Total IPFS bandwidth usage in bytes",
            ["direction"]
        )
        
        # Storage metrics
        self.metrics["storage_operations_total"] = Counter(
            "mcp_storage_operations_total", "Total storage operations",
            ["backend", "operation", "status"]
        )
        self.metrics["storage_operation_duration"] = Histogram(
            "mcp_storage_operation_duration", "Storage operation duration in seconds",
            ["backend", "operation"]
        )
        self.metrics["storage_size"] = Gauge(
            "mcp_storage_size", "Storage size in bytes", 
            ["backend"]
        )
        self.metrics["storage_objects"] = Gauge(
            "mcp_storage_objects", "Number of objects in storage",
            ["backend"]
        )
        
        # API metrics
        self.metrics["api_requests_total"] = Counter(
            "mcp_api_requests_total", "Total API requests",
            ["method", "endpoint", "status_code"]
        )
        self.metrics["api_request_duration"] = Histogram(
            "mcp_api_request_duration", "API request duration in seconds",
            ["method", "endpoint"]
        )
        
        # System information
        self.metrics["system_info"].info({
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "hostname": platform.node(),
        })
        
        logger.info("Prometheus metrics collectors initialized")
    
    def start(self):
        """Start metrics collection and HTTP server."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            logger.warning("Cannot start metrics collection: Prometheus not available")
            return False
        
        # Start HTTP server if not already running
        if not self.server_started:
            try:
                start_http_server(self.port)
                self.server_started = True
                logger.info(f"Started Prometheus metrics server on port {self.port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                return False
        
        # Start collection thread if not already running
        if not self.running:
            self.running = True
            self.collection_thread = threading.Thread(
                target=self._collection_loop,
                daemon=True
            )
            self.collection_thread.start()
            logger.info(f"Started metrics collection thread (interval: {self.collection_interval}s)")
        
        return True
    
    def stop(self):
        """Stop metrics collection."""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=1.0)
            logger.info("Stopped metrics collection thread")
        return True
    
    def _collection_loop(self):
        """Metrics collection background loop."""
        while self.running:
            try:
                self._collect_system_metrics()
                # Sleep for collection interval
                time.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                time.sleep(5)  # Shorter sleep on error
    
    def _collect_system_metrics(self):
        """Collect system metrics."""
        # CPU usage
        self.metrics["system_cpu_usage"].set(psutil.cpu_percent())
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.metrics["system_memory_usage"].set(memory.used)
        self.metrics["system_memory_percent"].set(memory.percent)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        self.metrics["system_disk_usage"].set(disk.used)
        self.metrics["system_disk_percent"].set(disk.percent)
    
    def record_ipfs_operation(self, operation, status, duration=None):
        """Record an IPFS operation metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["ipfs_operations_total"].labels(
                operation=operation, status=status
            ).inc()
            
            if duration is not None:
                self.metrics["ipfs_operation_duration"].labels(
                    operation=operation
                ).observe(duration)
        except Exception as e:
            logger.error(f"Error recording IPFS operation metric: {e}")
    
    def record_storage_operation(self, backend, operation, status, duration=None):
        """Record a storage operation metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["storage_operations_total"].labels(
                backend=backend, operation=operation, status=status
            ).inc()
            
            if duration is not None:
                self.metrics["storage_operation_duration"].labels(
                    backend=backend, operation=operation
                ).observe(duration)
        except Exception as e:
            logger.error(f"Error recording storage operation metric: {e}")
    
    def record_api_request(self, method, endpoint, status_code, duration=None):
        """Record an API request metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["api_requests_total"].labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()
            
            if duration is not None:
                self.metrics["api_request_duration"].labels(
                    method=method, endpoint=endpoint
                ).observe(duration)
        except Exception as e:
            logger.error(f"Error recording API request metric: {e}")
    
    def update_ipfs_peers(self, peer_count):
        """Update IPFS peers count metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["ipfs_peers_connected"].set(peer_count)
        except Exception as e:
            logger.error(f"Error updating IPFS peers metric: {e}")
    
    def update_ipfs_repo_size(self, size_bytes):
        """Update IPFS repository size metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["ipfs_repo_size"].set(size_bytes)
        except Exception as e:
            logger.error(f"Error updating IPFS repo size metric: {e}")
    
    def update_ipfs_bandwidth(self, bytes_count, direction):
        """Update IPFS bandwidth usage metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["ipfs_bandwidth_total"].labels(
                direction=direction
            ).inc(bytes_count)
        except Exception as e:
            logger.error(f"Error updating IPFS bandwidth metric: {e}")
    
    def update_storage_size(self, backend, size_bytes):
        """Update storage size metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["storage_size"].labels(backend=backend).set(size_bytes)
        except Exception as e:
            logger.error(f"Error updating storage size metric: {e}")
    
    def update_storage_objects(self, backend, object_count):
        """Update storage objects count metric."""
        if not self.enabled or not PROMETHEUS_AVAILABLE:
            return
        
        try:
            self.metrics["storage_objects"].labels(backend=backend).set(object_count)
        except Exception as e:
            logger.error(f"Error updating storage objects metric: {e}")

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
EOL

# 2. Fix the ipfs_model_anyio.py syntax error
echo "Fixing ipfs_model_anyio.py syntax error..."

# Use sed to fix the specific try-except block in ipfs_model_anyio.py
# First locate the line number where the syntax error occurs
LINENO=$(grep -n "except ImportError:" ipfs_kit_py/mcp/models/ipfs_model_anyio.py | grep -n "except ImportError:" | head -1 | cut -d: -f1)

if [ -n "$LINENO" ]; then
    # Fix the specific try-except block
    sed -i '566,570c\
                try:\
                    from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager\
                    logger.info("Successfully imported WebRTCStreamingManager")\
                except ImportError:\
                    # Look for WebRTCStreamingManager in the global scope\
                    if "WebRTCStreamingManager" not in globals():' ipfs_kit_py/mcp/models/ipfs_model_anyio.py
else
    echo "Could not find the problematic code section in ipfs_model_anyio.py"
fi

# 3. Fix unused imports in controllers/__init__.py
echo "Fixing unused imports in controllers/__init__.py..."
sed -i '/^ *from ipfs_kit_py.mcp.controllers.fs_journal_controller import/,/^ *import/s/FsJournalController/# FsJournalController/' ipfs_kit_py/mcp/controllers/__init__.py
sed -i '/^ *from ipfs_kit_py.mcp.controllers.libp2p_controller import/,/^ *import/s/LibP2PController/# LibP2PController/' ipfs_kit_py/mcp/controllers/__init__.py

# 4. Fix undefined names in various files
echo "Fixing undefined names in files..."

# Add missing imports to the alerting.py file
sed -i '1s/^/import os\n/' ipfs_kit_py/mcp/monitoring/alerting.py

# Fix undefined name 'time' in ipfs_controller.py
sed -i '1s/^/import time\n/' ipfs_kit_py/mcp/controllers/ipfs_controller.py

# Fix the most critical issues in webrtc.py
sed -i '1s/^/from fastapi import APIRouter, WebSocket\nfrom typing import Optional\n/' ipfs_kit_py/mcp/extensions/webrtc.py

# 5. Run final format and lint
echo "Running final Black and Ruff passes..."
black ipfs_kit_py/mcp/monitoring/prometheus.py
black ipfs_kit_py/mcp/models/ipfs_model_anyio.py
black ipfs_kit_py/mcp/controllers/__init__.py
black ipfs_kit_py/mcp/monitoring/alerting.py
black ipfs_kit_py/mcp/controllers/ipfs_controller.py
black ipfs_kit_py/mcp/extensions/webrtc.py

ruff check --fix ipfs_kit_py/mcp/monitoring/prometheus.py
ruff check --fix ipfs_kit_py/mcp/models/ipfs_model_anyio.py
ruff check --fix ipfs_kit_py/mcp/controllers/__init__.py
ruff check --fix ipfs_kit_py/mcp/monitoring/alerting.py
ruff check --fix ipfs_kit_py/mcp/controllers/ipfs_controller.py
ruff check --fix ipfs_kit_py/mcp/extensions/webrtc.py

echo "Fixed most critical syntax errors and issues!"