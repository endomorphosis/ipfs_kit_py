"""
Prometheus Integration for MCP Server

This module provides integration with Prometheus monitoring system:
- Prometheus metrics exposition format
- Push gateway support
- Custom metrics registration
- Helper functions for instrumentation

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import time
import logging
import requests
import threading
from typing import Dict, Any, List, Optional, Union, Callable
from urllib.parse import urlparse

from ipfs_kit_py.mcp.monitoring import MetricsRegistry, MetricType, MetricUnit, MetricTag

# Configure logging
logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Export MCP metrics to Prometheus.
    
    This class provides methods to expose metrics in Prometheus format
    and push metrics to a Prometheus Pushgateway.
    """
    
    def __init__(self, metrics_registry: MetricsRegistry, job_name: str = "mcp_server"):
        """
        Initialize the Prometheus exporter.
        
        Args:
            metrics_registry: MCP metrics registry
            job_name: Job name for Pushgateway
        """
        self.metrics = metrics_registry
        self.job_name = job_name
        self.instance_id = os.environ.get("HOSTNAME", "mcp-instance")
        self.push_interval = 60  # seconds
        self.push_gateway_url = os.environ.get("PROMETHEUS_PUSHGATEWAY", "")
        self.push_thread = None
        self.running = False
    
    def metrics_handler(self) -> str:
        """
        Generate metrics in Prometheus exposition format.
        
        Returns:
            Prometheus metrics text
        """
        return self.metrics.get_prometheus_metrics()
    
    def start_push_loop(self, push_gateway_url: str, interval: int = 60) -> None:
        """
        Start pushing metrics to Pushgateway in a background thread.
        
        Args:
            push_gateway_url: URL of the Prometheus Pushgateway
            interval: Push interval in seconds
        """
        if self.running:
            logger.warning("Push loop already running")
            return
        
        # Validate URL
        try:
            parsed = urlparse(push_gateway_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            logger.error(f"Invalid Pushgateway URL: {e}")
            return
        
        self.push_gateway_url = push_gateway_url
        self.push_interval = interval
        self.running = True
        
        # Start push thread
        self.push_thread = threading.Thread(
            target=self._push_loop,
            daemon=True
        )
        self.push_thread.start()
        
        logger.info(f"Started Prometheus push loop to {push_gateway_url} with interval {interval}s")
    
    def stop_push_loop(self) -> None:
        """Stop pushing metrics to Pushgateway."""
        self.running = False
        
        if self.push_thread:
            self.push_thread.join(timeout=5.0)
            logger.info("Stopped Prometheus push loop")
    
    def _push_loop(self) -> None:
        """Background thread to push metrics to Pushgateway."""
        while self.running:
            try:
                self.push_to_gateway()
            except Exception as e:
                logger.error(f"Error pushing to Prometheus Pushgateway: {e}")
            
            # Sleep until next push
            time.sleep(self.push_interval)
    
    def push_to_gateway(self) -> bool:
        """
        Push metrics to Prometheus Pushgateway.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.push_gateway_url:
            logger.warning("Pushgateway URL not set")
            return False
        
        # Get metrics in Prometheus format
        metrics_text = self.metrics_handler()
        
        # Build URL with job and instance labels
        url = f"{self.push_gateway_url.rstrip('/')}/metrics/job/{self.job_name}/instance/{self.instance_id}"
        
        try:
            # Send metrics to Pushgateway
            response = requests.post(
                url,
                data=metrics_text,
                headers={"Content-Type": "text/plain"}
            )
            
            # Check response
            if response.ok:
                logger.debug(f"Successfully pushed metrics to {url}")
                return True
            else:
                logger.warning(f"Failed to push metrics to {url}: {response.status_code} {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error pushing metrics to {url}: {e}")
            return False


class PrometheusMiddleware:
    """
    FastAPI middleware for Prometheus metrics.
    
    This middleware automatically records API metrics for all requests.
    """
    
    def __init__(self, app, metrics_registry: MetricsRegistry, exclude_paths: List[str] = None):
        """
        Initialize the Prometheus middleware.
        
        Args:
            app: FastAPI application
            metrics_registry: MCP metrics registry
            exclude_paths: List of paths to exclude from metrics
        """
        from starlette.middleware.base import BaseHTTPMiddleware
        
        self.app = app
        self.metrics = metrics_registry
        self.exclude_paths = exclude_paths or [
            "/metrics",
            "/health",
            "/api/v0/status"
        ]
        
        # Create middleware
        class MetricsMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                # Skip excluded paths
                path = request.url.path
                if any(path.startswith(excluded) for excluded in self.exclude_paths):
                    return await call_next(request)
                
                # Record start time
                start_time = time.time()
                
                # Process request
                response = await call_next(request)
                
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000
                
                # Normalize path for metrics
                # Replace path parameters with {param} to avoid high cardinality
                normalized_path = self._normalize_path(path)
                
                # Record metrics
                self.metrics.observe_histogram(
                    "api_request_duration",
                    duration_ms,
                    label_values={
                        "endpoint": normalized_path,
                        "method": request.method
                    }
                )
                
                self.metrics.increment_counter(
                    "api_requests_total",
                    label_values={
                        "endpoint": normalized_path,
                        "method": request.method,
                        "status": str(response.status_code)
                    }
                )
                
                return response
        
        # Add middleware to app
        app.add_middleware(MetricsMiddleware)
        logger.info("Added Prometheus metrics middleware")
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for metrics to avoid high cardinality.
        
        Args:
            path: Request path
            
        Returns:
            Normalized path
        """
        parts = path.split('/')
        normalized_parts = []
        
        for part in parts:
            # Check if this part is likely a parameter (UUID, hash, ID, etc.)
            if len(part) > 8 and not part.startswith('api') and not part.startswith('v0'):
                # Replace with {param}
                normalized_parts.append('{param}')
            else:
                normalized_parts.append(part)
        
        return '/'.join(normalized_parts)


def setup_prometheus(app, metrics_registry: MetricsRegistry) -> PrometheusExporter:
    """
    Set up Prometheus integration for MCP server.
    
    Args:
        app: FastAPI application
        metrics_registry: MCP metrics registry
        
    Returns:
        Prometheus exporter
    """
    # Create exporter
    exporter = PrometheusExporter(metrics_registry)
    
    # Add middleware
    PrometheusMiddleware(app, metrics_registry)
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(exporter.metrics_handler())
    
    # Start push gateway if configured
    push_gateway_url = os.environ.get("PROMETHEUS_PUSHGATEWAY", "")
    if push_gateway_url:
        push_interval = int(os.environ.get("PROMETHEUS_PUSH_INTERVAL", "60"))
        exporter.start_push_loop(push_gateway_url, push_interval)
    
    logger.info("Prometheus integration set up")
    return exporter