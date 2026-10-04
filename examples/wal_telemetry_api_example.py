#!/usr/bin/env python3
# examples/wal_telemetry_api_example.py

"""
Example demonstrating the high-level API integration with WAL telemetry.

This example shows how to:
1. Initialize the high-level API with WAL telemetry capabilities
2. Add Prometheus metrics and distributed tracing
3. Generate test operations to collect metrics
4. Access telemetry metrics through the API
5. View traces and performance information
"""

import os
import time
import argparse
import anyio
import random
import json
import logging
from typing import Dict, Any, Optional, List

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wal_telemetry_api_example")

# Try to import FastAPI for the API server example
try:
    from fastapi import FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI not available, API server example will be skipped")
    FASTAPI_AVAILABLE = False

# Try to import the high-level API with WAL telemetry
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.wal_telemetry_api import extend_high_level_api
    from ipfs_kit_py.wal_telemetry_tracing import TracingExporterType
    HIGH_LEVEL_API_AVAILABLE = True
except ImportError:
    import sys
    import os
    # Add parent directory to path for development
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        from ipfs_kit_py.wal_telemetry_api import extend_high_level_api
        from ipfs_kit_py.wal_telemetry_tracing import TracingExporterType
        HIGH_LEVEL_API_AVAILABLE = True
    except ImportError:
        logger.error("High-level API or WAL telemetry modules not available")
        HIGH_LEVEL_API_AVAILABLE = False

class WALTelemetryAPIExample:
    """Example application for WAL telemetry API integration."""
    
    def __init__(self):
        """Initialize the example application."""
        self.api = None
        self.app = None
        
    def setup(self):
        """Set up the high-level API with WAL telemetry."""
        if not HIGH_LEVEL_API_AVAILABLE:
            logger.error("High-level API or WAL telemetry modules not available")
            return False
            
        # Create high-level API instance
        self.api = IPFSSimpleAPI(role="master")
        
        # Extend with WAL telemetry capabilities
        self.api = extend_high_level_api(self.api)
        
        # Initialize telemetry
        telemetry_result = self.api.wal_telemetry(
            enabled=True,
            aggregation_interval=30,  # Aggregate metrics every 30 seconds
            max_history_entries=100  # Keep the last 100 history entries
        )
        logger.info(f"Telemetry initialization: {telemetry_result['success']}")
        
        # Initialize Prometheus integration
        prometheus_result = self.api.wal_prometheus(
            enabled=True,
            prefix="wal"
        )
        logger.info(f"Prometheus initialization: {prometheus_result['success']}")
        
        # Initialize tracing
        tracing_result = self.api.wal_tracing(
            enabled=True,
            service_name="ipfs-kit-example",
            exporter_type=TracingExporterType.CONSOLE,  # Use console exporter for demo
            sampling_ratio=1.0,  # Sample all traces
            auto_instrument=True
        )
        logger.info(f"Tracing initialization: {tracing_result['success']}")
        
        return telemetry_result.get("success", False) and \
               prometheus_result.get("success", False) and \
               tracing_result.get("success", False)
               
    def create_fastapi_app(self):
        """Create a FastAPI application with WAL telemetry endpoints."""
        if not FASTAPI_AVAILABLE:
            logger.error("FastAPI not available, cannot create application")
            return None
            
        # Create FastAPI app
        app = FastAPI(
            title="IPFS Kit WAL Telemetry Example",
            description="Example API demonstrating WAL telemetry capabilities",
            version="0.1.0"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Store API instance in app state
        app.state.api = self.api
        
        # Add metrics endpoint
        if hasattr(self.api, "wal_add_metrics_endpoint"):
            result = self.api.wal_add_metrics_endpoint(
                app=app,
                endpoint="/metrics"
            )
            logger.info(f"Added metrics endpoint: {result['success']}")
        
        # Add tracing middleware
        @app.middleware("http")
        async def tracing_middleware(request: Request, call_next):
            # Extract context from headers if available
            try:
                carrier = dict(request.headers)
                context_result = self.api.wal_extract_tracing_context(carrier)
                
                if context_result["success"]:
                    parent_context = context_result["context"]
                else:
                    parent_context = None
                    
                # Create span for request
                span_result = self.api.wal_create_span(
                    operation_type="http_request",
                    backend="api",
                    parent_context=parent_context,
                    attributes={
                        "http.method": request.method,
                        "http.url": str(request.url),
                        "http.path": request.url.path,
                        "http.client_ip": request.client.host
                    }
                )
                
                # Process request
                start_time = time.time()
                response = await call_next(request)
                duration = time.time() - start_time
                
                # Update span with response info
                if span_result["success"] and hasattr(self.api, "_wal_telemetry_extension"):
                    context = span_result["span_context"]
                    
                    self.api._wal_telemetry_extension.tracer.update_span(
                        context,
                        success=response.status_code < 400,
                        attributes={
                            "http.status_code": response.status_code,
                            "http.duration_ms": duration * 1000
                        }
                    )
                    
                    # End span
                    self.api._wal_telemetry_extension.tracer.end_span(context)
                    
                return response
                
            except Exception as e:
                logger.error(f"Error in tracing middleware: {e}")
                return await call_next(request)
        
        # Add example endpoints
        @app.get("/")
        async def root():
            return {"message": "IPFS Kit WAL Telemetry API Example"}
        
        @app.get("/telemetry")
        async def get_telemetry(
            include_history: bool = False,
            operation_type: str = None,
            backend_type: str = None
        ):
            # Get telemetry metrics
            metrics = self.api.wal_get_metrics(
                include_history=include_history,
                operation_type=operation_type,
                backend_type=backend_type
            )
            return metrics
        
        @app.post("/simulate")
        async def simulate(count: int = 10, delay: float = 0.5):
            # Run simulation in background task
            anyio.create_task(
                self._run_simulation_async(count, delay)
            )
            return {
                "success": True,
                "message": f"Started simulation with {count} operations",
                "metrics_url": "/telemetry"
            }
        
        # Store app reference
        self.app = app
        return app
    
    async def _run_simulation_async(self, count, delay):
        """Run the simulation in an async context."""
        loop = anyio.get_event_loop()
        await loop.run_in_executor(None, self.simulate_operations, count, delay)
    
    def simulate_operations(self, count=10, delay=0.5):
        """Simulate WAL operations to generate telemetry data."""
        logger.info(f"Simulating {count} operations with {delay}s delay")
        
        operations = ["add", "get", "pin", "unpin", "cat"]
        backends = ["ipfs", "s3", "storacha"]
        
        for i in range(count):
            # Select operation and backend
            op_index = i % len(operations)
            backend_index = i % len(backends)
            
            operation = operations[op_index]
            backend = backends[backend_index]
            
            # Create a span for the operation
            span_result = self.api.wal_create_span(
                operation_type=operation,
                backend=backend,
                attributes={
                    "simulation": "true",
                    "iteration": i,
                    "complexity": "medium"
                }
            )
            
            # Simulate operation time
            op_time = delay * (1 + (i % 3) * 0.5)  # Vary operation time
            time.sleep(op_time)
            
            # Simulate success or failure (fail every 7th operation)
            success = (i % 7) != 0
            
            # Check if span was created successfully
            if span_result["success"] and hasattr(self.api, "_wal_telemetry_extension"):
                # Get span context
                context = span_result["span_context"]
                
                # Update span with result
                self.api._wal_telemetry_extension.tracer.update_span(
                    context, 
                    success=success,
                    attributes={
                        "duration_ms": op_time * 1000,
                        "success": success,
                        "error": None if success else "Simulated failure"
                    }
                )
                
                # End span
                self.api._wal_telemetry_extension.tracer.end_span(context)
                
        logger.info(f"Completed {count} simulated operations")
    
    def run_example(self, server_mode=False, host="127.0.0.1", port=8000, operations=20, delay=0.5):
        """Run the WAL telemetry API example."""
        # Set up the high-level API with WAL telemetry
        if not self.setup():
            logger.error("Failed to set up WAL telemetry, exiting")
            return False
        
        if server_mode:
            if not FASTAPI_AVAILABLE:
                logger.error("FastAPI not available, cannot start server")
                return False
                
            # Create FastAPI app
            app = self.create_fastapi_app()
            if not app:
                logger.error("Failed to create FastAPI app")
                return False
                
            # Start the server
            logger.info(f"Starting FastAPI server on http://{host}:{port}")
            uvicorn.run(app, host=host, port=port)
        else:
            # Just run the simulation
            self.simulate_operations(operations, delay)
            
            # Get and display metrics
            time.sleep(2)  # Wait for metrics to be processed
            metrics = self.api.wal_get_metrics(include_history=True)
            
            if metrics["success"]:
                logger.info("Real-time metrics:")
                for category, metrics_data in metrics["real_time_metrics"].items():
                    logger.info(f"  {category}:")
                    for key, value in metrics_data.items():
                        logger.info(f"    {key}: {value}")
        
        return True

def main():
    """Main function for the example."""
    parser = argparse.ArgumentParser(description="WAL Telemetry API Example")
    parser.add_argument("--server", action="store_true", help="Start FastAPI server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--operations", type=int, default=20, help="Number of operations to simulate")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between operations (seconds)")
    args = parser.parse_args()
    
    # Run the example
    example = WALTelemetryAPIExample()
    example.run_example(
        server_mode=args.server,
        host=args.host,
        port=args.port,
        operations=args.operations,
        delay=args.delay
    )

# Allow running as script
if __name__ == "__main__":
    main()
