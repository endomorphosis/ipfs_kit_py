#!/usr/bin/env python3
"""
Enhanced MCP Server implementation with Prometheus metrics integration and
WebRTC streaming capabilities.

This script provides:
1. A Model-Controller-Persistence (MCP) server for IPFS operations
2. Prometheus metrics export for monitoring
3. WebRTC streaming functionality for multimedia content
4. Configurable environment with both debug and production modes
"""

import os
import time
import logging
import argparse
import json
import signal
import sys
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_server.log")
    ]
)
logger = logging.getLogger(__name__)

# Import FastAPI components
try:
    from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware
except ImportError as e:
    logger.error(f"Failed to import FastAPI components: {e}")
    logger.error("Please install required packages: pip install fastapi uvicorn prometheus-client")
    sys.exit(1)

# Import Prometheus components
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, make_asgi_app, CollectorRegistry, multiprocess
except ImportError as e:
    logger.error(f"Failed to import Prometheus components: {e}")
    logger.error("Please install required packages: pip install prometheus-client")
    sys.exit(1)

# Import MCP server
try:
    from ipfs_kit_py.mcp.server import MCPServer
except ImportError as e:
    logger.error(f"Failed to import MCP server: {e}")
    logger.error("Make sure ipfs_kit_py is installed or in your PYTHONPATH")
    sys.exit(1)

class MCPMetrics:
    """Metrics collection for MCP server."""
    
    def __init__(self):
        """Initialize Prometheus metrics."""
        # Request metrics
        self.request_count = Counter(
            'mcp_request_count', 
            'Count of API requests',
            ['endpoint', 'method', 'status']
        )
        
        self.request_latency = Histogram(
            'mcp_request_latency_seconds', 
            'Request latency in seconds',
            ['endpoint', 'method'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
        )
        
        # IPFS operation metrics
        self.ipfs_operation_count = Counter(
            'mcp_ipfs_operation_count', 
            'Count of IPFS operations',
            ['operation', 'success']
        )
        
        self.ipfs_operation_latency = Histogram(
            'mcp_ipfs_operation_latency_seconds', 
            'IPFS operation latency in seconds',
            ['operation'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
        )
        
        self.ipfs_bytes_transferred = Counter(
            'mcp_ipfs_bytes_transferred', 
            'Bytes transferred through IPFS operations',
            ['operation', 'direction']  # direction: 'in' or 'out'
        )
        
        # Cache metrics
        self.cache_hit_count = Counter(
            'mcp_cache_hit_count', 
            'Cache hit count',
            ['cache_type']  # memory, disk, parquet
        )
        
        self.cache_miss_count = Counter(
            'mcp_cache_miss_count', 
            'Cache miss count',
            ['cache_type']  # memory, disk, parquet
        )
        
        self.cache_size = Gauge(
            'mcp_cache_size_bytes', 
            'Current size of cache in bytes',
            ['cache_type']
        )
        
        self.cache_item_count = Gauge(
            'mcp_cache_item_count', 
            'Number of items in cache',
            ['cache_type']
        )
        
        # ParquetCIDCache specific metrics
        self.parquet_partition_count = Gauge(
            'mcp_parquet_partition_count', 
            'Number of partitions in ParquetCIDCache'
        )
        
        self.parquet_schema_version = Gauge(
            'mcp_parquet_schema_version', 
            'Current schema version in ParquetCIDCache'
        )
        
        # System metrics
        self.uptime = Gauge(
            'mcp_uptime_seconds', 
            'Server uptime in seconds'
        )
        
        self.active_sessions = Gauge(
            'mcp_active_sessions', 
            'Number of active sessions',
            ['controller']  # ipfs, webrtc, etc.
        )
        
        # WebRTC metrics
        self.webrtc_streams_count = Gauge(
            'mcp_webrtc_streams_count',
            'Number of active WebRTC streams'
        )
        
        self.webrtc_peer_connections = Gauge(
            'mcp_webrtc_peer_connections',
            'Number of active WebRTC peer connections'
        )
        
        self.webrtc_bytes_sent = Counter(
            'mcp_webrtc_bytes_sent',
            'Bytes sent over WebRTC'
        )
        
        self.webrtc_bytes_received = Counter(
            'mcp_webrtc_bytes_received',
            'Bytes received over WebRTC'
        )
        
        # Server info
        self.server_info = Info(
            'mcp_server_info', 
            'MCP server information'
        )
        
        # Start time for uptime tracking
        self.start_time = time.time()

    def update_uptime(self):
        """Update server uptime metric."""
        self.uptime.set(time.time() - self.start_time)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting request metrics."""
    
    def __init__(self, app, metrics: MCPMetrics):
        super().__init__(app)
        self.metrics = metrics
    
    async def dispatch(self, request, call_next):
        """Process request and collect metrics."""
        # Record start time
        start_time = time.time()
        
        # Process request
        try:
            response = await call_next(request)
            
            # Record metrics after successful processing
            endpoint = request.url.path
            method = request.method
            status = response.status_code
            
            # Update request metrics
            self.metrics.request_count.labels(
                endpoint=endpoint, 
                method=method, 
                status=status
            ).inc()
            
            self.metrics.request_latency.labels(
                endpoint=endpoint, 
                method=method
            ).observe(time.time() - start_time)
            
            # Update uptime gauge
            self.metrics.update_uptime()
            
            return response
            
        except Exception as e:
            # Record metrics for failed requests
            endpoint = request.url.path
            method = request.method
            status = 500  # Internal server error
            
            self.metrics.request_count.labels(
                endpoint=endpoint, 
                method=method, 
                status=status
            ).inc()
            
            # Re-raise the exception
            raise e

class EnhancedMCPServer:
    """Enhanced MCP Server with metrics integration."""
    
    def __init__(self, 
                 debug_mode: bool = False, 
                 isolation_mode: bool = False,
                 persistence_path: str = None,
                 enable_metrics: bool = True,
                 metrics_path: str = "/metrics",
                 parquet_cache_path: str = None,
                 cache_config: Dict[str, Any] = None,
                 register_signal_handlers: bool = True):
        """
        Initialize the Enhanced MCP Server.
        
        Args:
            debug_mode: Enable debug mode (more logging and debug endpoints)
            isolation_mode: Use isolated storage for IPFS operations
            persistence_path: Path for persistence files
            enable_metrics: Enable Prometheus metrics export
            metrics_path: Path for Prometheus metrics endpoint
            parquet_cache_path: Path for ParquetCIDCache storage
            cache_config: Custom cache configuration
            register_signal_handlers: Register signal handlers for graceful shutdown
        """
        self.debug_mode = debug_mode
        self.isolation_mode = isolation_mode
        self.persistence_path = persistence_path or os.path.expanduser("~/.ipfs_kit/mcp")
        self.enable_metrics = enable_metrics
        self.metrics_path = metrics_path
        
        # Setup cache configuration
        self.cache_config = cache_config or {}
        if parquet_cache_path:
            self.cache_config["parquet_cache_path"] = parquet_cache_path
            self.cache_config["enable_parquet_cache"] = True
        
        # Initialize metrics
        if enable_metrics:
            self.metrics = MCPMetrics()
        else:
            self.metrics = None
        
        # Create FastAPI app
        self.app = FastAPI(
            title="Enhanced IPFS MCP Server",
            description="Model-Controller-Persistence Server for IPFS Kit with Prometheus metrics integration",
            version="0.2.0"
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, restrict this to specific domains
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add metrics middleware if enabled
        if enable_metrics:
            self.app.add_middleware(
                MetricsMiddleware,
                metrics=self.metrics
            )
        
        # Create and configure MCP server
        try:
            self.mcp_server = MCPServer(
                debug_mode=debug_mode,
                isolation_mode=isolation_mode,
                persistence_path=self.persistence_path,
                config={"cache": self.cache_config}
            )
            
            # Register MCP server with the app
            self.mcp_server.register_with_app(self.app, prefix="/api/v0/mcp")
            
            # Add metrics endpoint if enabled
            if enable_metrics:
                # Mount Prometheus ASGI app at metrics path
                metrics_app = make_asgi_app()
                self.app.mount(self.metrics_path, metrics_app)
                logger.info(f"Metrics endpoint registered at {self.metrics_path}")
                
                # Set server info for metrics
                self.metrics.server_info.info({
                    "debug_mode": str(debug_mode),
                    "isolation_mode": str(isolation_mode),
                    "persistence_path": self.persistence_path,
                    "start_timestamp": str(time.time())
                })
            
            # Add root endpoint for server information
            self.register_info_endpoints()
            
            # Add shutdown event handler
            @self.app.on_event("shutdown")
            async def shutdown_event():
                logger.info("FastAPI shutdown event received, cleaning up resources")
                if hasattr(self, 'mcp_server'):
                    self.mcp_server.shutdown()
                logger.info("Resources cleaned up")
            
            # Register signal handlers if requested
            if register_signal_handlers:
                self.register_signal_handlers()
                
            logger.info("Enhanced MCP Server initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced MCP Server: {e}")
            raise
    
    def register_info_endpoints(self):
        """Register information endpoints."""
        @self.app.get("/")
        async def root():
            """Root endpoint with server information."""
            # Get daemon status information if available
            daemon_info = {}
            if hasattr(self.mcp_server.ipfs_kit, 'check_daemon_status'):
                try:
                    daemon_status = self.mcp_server.ipfs_kit.check_daemon_status()
                    daemons = daemon_status.get("daemons", {})
                    
                    # Add daemon status for all detected daemons
                    for daemon_type, status in daemons.items():
                        running = status.get("running", False)
                        daemon_info[f"{daemon_type}_running"] = running
                        
                        # Update metrics if enabled
                        if self.enable_metrics and hasattr(self, 'metrics'):
                            daemon_gauge_name = f"mcp_{daemon_type}_running"
                            if not hasattr(self.metrics, daemon_gauge_name):
                                setattr(self.metrics, daemon_gauge_name, 
                                        Gauge(daemon_gauge_name, f"{daemon_type} daemon running status"))
                            
                            getattr(self.metrics, daemon_gauge_name).set(1 if running else 0)
                            
                except Exception as e:
                    daemon_info["error"] = f"Error checking daemon status: {str(e)}"
            
            # Get WebRTC status if available
            webrtc_info = {}
            if 'webrtc' in self.mcp_server.controllers:
                try:
                    webrtc_controller = self.mcp_server.controllers['webrtc']
                    
                    # Get number of active streams if available
                    if hasattr(webrtc_controller, 'get_active_streams_count'):
                        webrtc_info["active_streams"] = webrtc_controller.get_active_streams_count()
                        
                        # Update metrics if enabled
                        if self.enable_metrics and hasattr(self, 'metrics'):
                            self.metrics.webrtc_streams_count.set(webrtc_info["active_streams"])
                    
                    # Get WebRTC capabilities
                    if hasattr(webrtc_controller, 'get_capabilities'):
                        webrtc_info["capabilities"] = webrtc_controller.get_capabilities()
                        
                except Exception as e:
                    webrtc_info["error"] = f"Error getting WebRTC status: {str(e)}"
            
            # Get cache status if available
            cache_info = {}
            if hasattr(self.mcp_server, 'cache_manager'):
                try:
                    cache_info = self.mcp_server.cache_manager.get_cache_info()
                    
                    # Update metrics if enabled
                    if self.enable_metrics and hasattr(self, 'metrics'):
                        # Memory cache metrics
                        if "memory" in cache_info:
                            self.metrics.cache_size.labels(cache_type="memory").set(
                                cache_info["memory"].get("size_bytes", 0))
                            self.metrics.cache_item_count.labels(cache_type="memory").set(
                                cache_info["memory"].get("item_count", 0))
                        
                        # Disk cache metrics
                        if "disk" in cache_info:
                            self.metrics.cache_size.labels(cache_type="disk").set(
                                cache_info["disk"].get("size_bytes", 0))
                            self.metrics.cache_item_count.labels(cache_type="disk").set(
                                cache_info["disk"].get("item_count", 0))
                        
                        # Parquet cache metrics
                        if "parquet" in cache_info:
                            self.metrics.cache_size.labels(cache_type="parquet").set(
                                cache_info["parquet"].get("size_bytes", 0))
                            self.metrics.cache_item_count.labels(cache_type="parquet").set(
                                cache_info["parquet"].get("item_count", 0))
                            self.metrics.parquet_partition_count.set(
                                cache_info["parquet"].get("partition_count", 0))
                            
                except Exception as e:
                    cache_info["error"] = f"Error getting cache info: {str(e)}"
            
            # Build response with all server information
            response = {
                "message": "Enhanced MCP Server is running",
                "debug_mode": self.debug_mode,
                "isolation_mode": self.isolation_mode,
                "metrics_enabled": self.enable_metrics,
                "controllers": list(self.mcp_server.controllers.keys()),
                "daemon_status": daemon_info,
                "webrtc": webrtc_info,
                "cache": cache_info,
                "uptime_seconds": time.time() - (self.metrics.start_time if self.enable_metrics else time.time()),
                "endpoints": {
                    "api_base": "/api/v0/mcp",
                    "metrics": self.metrics_path if self.enable_metrics else "Disabled",
                    "health": "/api/v0/mcp/health",
                    "documentation": "/docs"
                }
            }
            
            return response
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            # Basic health check
            health_status = {"status": "ok", "timestamp": time.time()}
            
            # Check if MCP server is healthy
            if hasattr(self, 'mcp_server'):
                try:
                    # Use existing MCP health check
                    mcp_health = await self.mcp_server.health_check()
                    health_status["mcp_status"] = mcp_health.get("status", "unknown")
                    health_status["daemon_status"] = {}
                    
                    # Check IPFS daemon
                    if "ipfs_daemon_running" in mcp_health:
                        health_status["daemon_status"]["ipfs"] = mcp_health["ipfs_daemon_running"]
                    
                    # Check cluster daemon
                    if "ipfs_cluster_daemon_running" in mcp_health:
                        health_status["daemon_status"]["ipfs_cluster"] = mcp_health["ipfs_cluster_daemon_running"]
                    
                except Exception as e:
                    health_status["error"] = f"Error checking MCP health: {str(e)}"
                    health_status["status"] = "degraded"
            else:
                health_status["status"] = "degraded"
                health_status["error"] = "MCP server not initialized"
            
            # Check metrics system if enabled
            if self.enable_metrics:
                health_status["metrics_status"] = "ok"
                
                # Update uptime metric
                if hasattr(self, 'metrics'):
                    self.metrics.update_uptime()
            
            # Return appropriate status code
            status_code = 200 if health_status["status"] == "ok" else 503
            return JSONResponse(content=health_status, status_code=status_code)
    
    def register_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            """Handle termination signals."""
            logger.info(f"Received signal {sig}, shutting down...")
            if hasattr(self, 'mcp_server'):
                self.mcp_server.shutdown()
            # Let the process terminate naturally
            sys.exit(0)
        
        # Register handlers for SIGINT (Ctrl+C) and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers registered for graceful shutdown")
    
    def run_server(self, host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
        """
        Run the server using uvicorn.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            reload: Enable auto-reload for development
        """
        try:
            import uvicorn
            logger.info(f"Starting Enhanced MCP Server on {host}:{port}")
            logger.info(f"Debug mode: {self.debug_mode}, Isolation mode: {self.isolation_mode}")
            logger.info(f"Metrics enabled: {self.enable_metrics}")
            
            # Print URL for convenience
            print(f"\nServer starting at: http://{host}:{port}")
            print(f"API Docs available at: http://{host}:{port}/docs")
            if self.enable_metrics:
                print(f"Metrics available at: http://{host}:{port}{self.metrics_path}")
            print("\nPress Ctrl+C to stop the server\n")
            
            # Start the server
            uvicorn.run(self.app, host=host, port=port, reload=reload)
            
        except ImportError:
            logger.error("Failed to import uvicorn. Please install it: pip install uvicorn")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error running server: {e}")
            sys.exit(1)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server")
    
    # Basic server configuration
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    
    # MCP server configuration
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Use isolated storage for IPFS operations")
    parser.add_argument("--persistence-path", help="Path for persistence files")
    
    # Metrics configuration
    parser.add_argument("--disable-metrics", action="store_true", help="Disable Prometheus metrics export")
    parser.add_argument("--metrics-path", default="/metrics", help="Path for Prometheus metrics endpoint")
    
    # Cache configuration
    parser.add_argument("--parquet-cache-path", help="Path for ParquetCIDCache storage")
    parser.add_argument("--memory-cache-size", type=int, help="Memory cache size in bytes")
    parser.add_argument("--disk-cache-size", type=int, help="Disk cache size in bytes")
    
    return parser.parse_args()

def main():
    """Main function to run the Enhanced MCP Server."""
    # Parse command line arguments
    args = parse_args()
    
    # Build cache configuration
    cache_config = {}
    if args.memory_cache_size:
        cache_config["memory_cache_size"] = args.memory_cache_size
    if args.disk_cache_size:
        cache_config["disk_cache_size"] = args.disk_cache_size
    
    # Create and run server
    try:
        server = EnhancedMCPServer(
            debug_mode=args.debug,
            isolation_mode=args.isolation,
            persistence_path=args.persistence_path,
            enable_metrics=not args.disable_metrics,
            metrics_path=args.metrics_path,
            parquet_cache_path=args.parquet_cache_path,
            cache_config=cache_config
        )
        
        server.run_server(
            host=args.host,
            port=args.port,
            reload=args.reload
        )
        
    except Exception as e:
        logger.error(f"Failed to start Enhanced MCP Server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()