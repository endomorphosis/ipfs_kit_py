#!/usr/bin/env python3
# examples/wal_telemetry_tracing_example.py

"""
Example demonstrating the WAL telemetry distributed tracing capabilities.

This example shows how to:
1. Set up distributed tracing for WAL operations
2. Visualize traces with different visualization backends (Jaeger, Zipkin)
3. Propagate trace context between different components
4. Use different instrumentation patterns (automatic, manual, decorators)
5. Create a simple FastAPI server with tracing middleware
6. Trace operations across service boundaries

The example creates a complete simulation of a distributed system with
multiple services interacting through the WAL and provides visualization
of the resulting traces.
"""

import os
import time
import random
import uuid
import logging
import anyio
import threading
import argparse
from typing import Dict, List, Any, Optional
from enum import Enum

try:
    import fastapi
    from fastapi import FastAPI, Request, Response, Depends, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# Add parent directory to path so we can import ipfs_kit_py
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the modules we need
try:
    from ipfs_kit_py.storage_wal import (
        StorageWriteAheadLog,
        BackendHealthMonitor,
        OperationType,
        OperationStatus,
        BackendType
    )
    from ipfs_kit_py.wal_telemetry import WALTelemetry
    from ipfs_kit_py.wal_telemetry_tracing import (
        WALTracing,
        TracingExporterType, 
        add_tracing_middleware,
        trace_aiohttp_request
    )
    WAL_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    WAL_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("wal_tracing_example")

# Simulation configuration
SIM_DURATION_SECONDS = 60
REQUEST_INTERVAL_SECONDS = 2.0
BACKEND_FAILURE_PROBABILITY = 0.05
OPERATION_TYPES = ["add", "get", "pin", "list"]
BACKENDS = ["ipfs", "s3", "storacha"]
OPERATION_ERROR_PROBABILITY = 0.1
WORKER_COUNT = 3

class SimulationService:
    """Base class for simulation services."""
    
    def __init__(
        self,
        service_name: str,
        port: int,
        exporter_type: str = "console",
        exporter_endpoint: Optional[str] = None,
        base_path: str = "~/.ipfs_kit/simulation",
    ):
        self.service_name = service_name
        self.port = port
        self.base_path = os.path.expanduser(base_path)
        self.exporter_type = exporter_type
        self.exporter_endpoint = exporter_endpoint
        
        # Create base path
        os.makedirs(self.base_path, exist_ok=True)
        
        # Create WAL, telemetry and tracing
        self.health_monitor = BackendHealthMonitor(
            check_interval=5,
            history_size=10,
            status_change_callback=self._on_backend_status_change
        )
        
        self.wal = StorageWriteAheadLog(
            base_path=os.path.join(self.base_path, f"{service_name}/wal"),
            partition_size=100,
            health_monitor=self.health_monitor
        )
        
        self.telemetry = WALTelemetry(
            wal=self.wal,
            metrics_path=os.path.join(self.base_path, f"{service_name}/telemetry"),
            sampling_interval=10,
            enable_detailed_timing=True,
            operation_hooks=True
        )
        
        self.tracer = WALTracing(
            service_name=service_name,
            telemetry=self.telemetry,
            exporter_type=exporter_type,
            exporter_endpoint=exporter_endpoint,
            resource_attributes={
                "deployment.environment": "simulation",
                "service.instance.id": str(uuid.uuid4())[:8]
            },
            auto_instrument=True
        )
        
        # Create FastAPI app if available
        self.app = None
        if FASTAPI_AVAILABLE:
            self.app = FastAPI(title=f"{service_name} API", version="1.0.0")
            
            # Add tracing middleware
            add_tracing_middleware(self.app, self.tracer, service_name)
            
            # Add CORS middleware
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )
            
            # Add health check endpoint
            @self.app.get("/health")
            async def health_check():
                return {"status": "ok", "service": self.service_name}
                
            # Add trace-id endpoint
            @self.app.get("/trace-id")
            async def get_trace_id():
                trace_id = self.tracer.get_trace_id() or "none"
                span_id = self.tracer.get_span_id() or "none"
                return {
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "service": self.service_name
                }
        
        logger.info(f"Initialized {service_name} service on port {port}")
        
    def _on_backend_status_change(self, backend, old_status, new_status):
        """Handle backend status changes."""
        logger.info(f"[{self.service_name}] Backend {backend} status changed: {old_status} -> {new_status}")
        
        # Add custom event to current span if available
        self.tracer.add_event(
            name="backend.status.change",
            attributes={
                "backend": backend,
                "old_status": old_status,
                "new_status": new_status
            }
        )
        
    async def start(self):
        """Start the service."""
        if self.app and FASTAPI_AVAILABLE:
            # Start the FastAPI app in a background thread
            def run_app():
                uvicorn.run(self.app, host="0.0.0.0", port=self.port)
                
            thread = threading.Thread(target=run_app, daemon=True)
            thread.start()
            logger.info(f"[{self.service_name}] API server started on port {self.port}")
            
            # Give it a moment to start
            await anyio.sleep(0.5)
            
    def close(self):
        """Clean up resources."""
        # Close resources
        if hasattr(self, 'tracer'):
            self.tracer.close()
        if hasattr(self, 'telemetry'):
            self.telemetry.close()
        if hasattr(self, 'wal'):
            self.wal.close()
        if hasattr(self, 'health_monitor'):
            self.health_monitor.close()
        
        logger.info(f"[{self.service_name}] Service shut down")


class MasterService(SimulationService):
    """Master service that orchestrates operations."""
    
    def __init__(
        self,
        port: int = 8000,
        exporter_type: str = "console",
        exporter_endpoint: Optional[str] = None,
        worker_ports: List[int] = None,
    ):
        super().__init__(
            service_name="master",
            port=port,
            exporter_type=exporter_type,
            exporter_endpoint=exporter_endpoint
        )
        
        self.worker_ports = worker_ports or []
        self.worker_urls = [f"http://localhost:{port}" for port in self.worker_ports]
        
        # Set up worker health checks
        self.worker_health = {url: True for url in self.worker_urls}
        
        # Add master-specific API endpoints
        if self.app:
            @self.app.post("/api/operation")
            async def add_operation(
                request: Request,
                background_tasks: BackgroundTasks,
                operation_type: str = None,
                backend: str = None,
                param: str = None
            ):
                # Extract trace context from request headers
                trace_context = self.tracer.extract_context(dict(request.headers))
                
                # Create span for this request
                with self.tracer.start_span(
                    name="master.add_operation",
                    context=trace_context,
                    attributes={
                        "operation.type": operation_type,
                        "backend": backend,
                        "param": param
                    }
                ) as span:
                    # Add the operation to WAL
                    result = self.wal.add_operation(
                        operation_type=operation_type,
                        backend=backend,
                        parameters={"path": param} if param else {}
                    )
                    
                    if result.get("success"):
                        operation_id = result["operation_id"]
                        
                        # Process in background
                        background_tasks.add_task(
                            self.process_operation, 
                            operation_id, 
                            operation_type, 
                            backend
                        )
                        
                        return {
                            "success": True,
                            "operation_id": operation_id,
                            "message": f"Operation added: {operation_type} on {backend}",
                            "trace_id": self.tracer.get_trace_id()
                        }
                    else:
                        span.set_status(StatusCode.ERROR)
                        span.set_attribute("error.message", result.get("error", "Unknown error"))
                        
                        return {
                            "success": False,
                            "error": result.get("error", "Failed to add operation"),
                            "trace_id": self.tracer.get_trace_id()
                        }
                        
            @self.app.get("/api/status/{operation_id}")
            async def get_operation_status(operation_id: str, request: Request):
                # Extract trace context from request headers
                trace_context = self.tracer.extract_context(dict(request.headers))
                
                # Create span for this request
                with self.tracer.start_span(
                    name="master.get_operation_status",
                    context=trace_context,
                    attributes={
                        "operation.id": operation_id
                    }
                ) as span:
                    # Get operation from WAL
                    operation = self.wal.get_operation(operation_id)
                    
                    if operation:
                        return {
                            "success": True,
                            "operation": operation,
                            "trace_id": self.tracer.get_trace_id()
                        }
                    else:
                        span.set_status(StatusCode.ERROR)
                        span.set_attribute("error.message", f"Operation {operation_id} not found")
                        
                        return {
                            "success": False,
                            "error": f"Operation {operation_id} not found",
                            "trace_id": self.tracer.get_trace_id()
                        }
                        
            @self.app.get("/api/simulate")
            async def simulate_operation():
                """Simulate a random operation."""
                operation_type = random.choice(OPERATION_TYPES)
                backend = random.choice(BACKENDS)
                param = f"/tmp/file-{uuid.uuid4()}.txt"
                
                return await add_operation(
                    Request(scope={"type": "http"}),
                    BackgroundTasks(),
                    operation_type=operation_type,
                    backend=backend,
                    param=param
                )
                
    async def process_operation(self, operation_id: str, operation_type: str, backend: str):
        """Process an operation, potentially delegating to a worker."""
        # Update status to processing
        self.wal.update_operation_status(operation_id, OperationStatus.PROCESSING)
        
        # Determine if we should delegate to a worker
        should_delegate = random.random() < 0.7  # 70% chance of delegation
        
        if should_delegate and self.worker_urls:
            # Choose an available worker
            available_workers = [url for url, healthy in self.worker_health.items() if healthy]
            
            if available_workers:
                worker_url = random.choice(available_workers)
                
                try:
                    # Create a span for the worker request
                    with self.tracer.create_span_context(
                        operation_type=operation_type,
                        backend=backend,
                        operation_id=operation_id,
                        attributes={"delegation.target": worker_url}
                    ) as span:
                        # Prepare headers with trace context
                        headers = {}
                        self.tracer.inject_context(None, headers)
                        
                        # Delegate to worker
                        if AIOHTTP_AVAILABLE:
                            async with aiohttp.ClientSession() as session:
                                # Trace the request
                                carrier, request_span = trace_aiohttp_request(
                                    self.tracer, 
                                    "POST", 
                                    f"{worker_url}/api/process"
                                )
                                
                                # Add trace context to headers
                                headers.update(carrier)
                                
                                async with session.post(
                                    f"{worker_url}/api/process",
                                    json={
                                        "operation_id": operation_id,
                                        "operation_type": operation_type,
                                        "backend": backend
                                    },
                                    headers=headers
                                ) as response:
                                    data = await response.json()
                                    
                                    # Record the result
                                    span.set_attribute("worker.response.success", data.get("success", False))
                                    if not data.get("success", False):
                                        span.set_attribute("worker.response.error", data.get("error", "Unknown error"))
                                        span.set_status(StatusCode.ERROR)
                                        
                                        # Mark worker as unhealthy if it consistently fails
                                        self.worker_health[worker_url] = False
                                    
                                    # End the request span
                                    request_span.end()
                                    
                                    return
                        else:
                            # Simulate a worker response without aiohttp
                            await anyio.sleep(0.5)  # Simulate network delay
                            
                            # Randomly succeed or fail
                            success = random.random() > OPERATION_ERROR_PROBABILITY
                            
                            if success:
                                span.set_attribute("worker.response.success", True)
                                span.set_attribute("worker.response.simulated", True)
                            else:
                                span.set_attribute("worker.response.success", False)
                                span.set_attribute("worker.response.error", "Simulated error")
                                span.set_status(StatusCode.ERROR)
                                return
                                
                except Exception as e:
                    # Handle request failure
                    logger.error(f"[master] Failed to delegate to worker {worker_url}: {e}")
                    
                    # Mark worker as unhealthy
                    self.worker_health[worker_url] = False
                    
                    # Process locally as fallback
                    await self._local_processing(operation_id, operation_type, backend)
            else:
                # No healthy workers, process locally
                await self._local_processing(operation_id, operation_type, backend)
        else:
            # Process locally
            await self._local_processing(operation_id, operation_type, backend)
            
    async def _local_processing(self, operation_id: str, operation_type: str, backend: str):
        """Process an operation locally."""
        try:
            # Simulate processing time
            await anyio.sleep(random.uniform(0.1, 1.0))
            
            # Simulate random errors
            if random.random() < OPERATION_ERROR_PROBABILITY:
                self.wal.update_operation_status(
                    operation_id, 
                    OperationStatus.FAILED,
                    updates={
                        "error": f"Simulated error in {operation_type}",
                        "error_type": "simulation_error"
                    }
                )
                return
                
            # Mark operation as complete
            self.wal.update_operation_status(
                operation_id, 
                OperationStatus.COMPLETED,
                updates={
                    "result": f"Completed {operation_type} on {backend}"
                }
            )
            
        except Exception as e:
            logger.error(f"[master] Error processing operation {operation_id}: {e}")
            
            # Mark operation as failed
            self.wal.update_operation_status(
                operation_id, 
                OperationStatus.FAILED,
                updates={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
    async def simulate_backend_health(self):
        """Simulate backend health status changes."""
        while True:
            # Occasionally change backend health status
            if random.random() < BACKEND_FAILURE_PROBABILITY:
                backend = random.choice(BACKENDS)
                current_status = self.health_monitor.get_status().get(backend, {}).get("status", "unknown")
                
                if current_status == "online":
                    # Simulate degradation or failure
                    new_status = random.choice(["degraded", "offline"])
                    self.health_monitor.update_backend_status(backend, new_status)
                elif current_status in ("degraded", "offline"):
                    # Simulate recovery
                    self.health_monitor.update_backend_status(backend, "online")
                    
            # Wait before next health check
            await anyio.sleep(10)
            
    async def check_worker_health(self):
        """Check the health of worker services."""
        while True:
            for worker_url in self.worker_urls:
                try:
                    if AIOHTTP_AVAILABLE:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(f"{worker_url}/health") as response:
                                if response.status == 200:
                                    self.worker_health[worker_url] = True
                                else:
                                    self.worker_health[worker_url] = False
                    else:
                        # Just assume workers are healthy if we can't check
                        pass
                except Exception:
                    self.worker_health[worker_url] = False
                    
            # Wait before next check
            await anyio.sleep(10)


class WorkerService(SimulationService):
    """Worker service that processes delegated operations."""
    
    def __init__(
        self,
        port: int,
        exporter_type: str = "console",
        exporter_endpoint: Optional[str] = None,
        worker_id: int = 1,
        master_url: str = "http://localhost:8000"
    ):
        super().__init__(
            service_name=f"worker-{worker_id}",
            port=port,
            exporter_type=exporter_type,
            exporter_endpoint=exporter_endpoint
        )
        
        self.worker_id = worker_id
        self.master_url = master_url
        
        # Add worker-specific API endpoints
        if self.app:
            @self.app.post("/api/process")
            async def process_operation(request: Request):
                # Extract trace context from request headers
                trace_context = self.tracer.extract_context(dict(request.headers))
                
                # Get request body
                try:
                    data = await request.json()
                except ValueError:
                    return {"success": False, "error": "Invalid JSON"}
                
                operation_id = data.get("operation_id")
                operation_type = data.get("operation_type")
                backend = data.get("backend")
                
                if not all([operation_id, operation_type, backend]):
                    return {
                        "success": False, 
                        "error": "Missing required fields",
                        "trace_id": self.tracer.get_trace_id()
                    }
                
                # Create span for processing
                with self.tracer.start_span(
                    name=f"worker.process.{operation_type}",
                    context=trace_context,
                    attributes={
                        "operation.id": operation_id,
                        "operation.type": operation_type,
                        "backend": backend,
                        "worker.id": self.worker_id
                    }
                ) as span:
                    try:
                        # Simulate processing time
                        processing_time = random.uniform(0.2, 2.0)
                        await anyio.sleep(processing_time)
                        
                        # Record processing time
                        span.set_attribute("processing.time_seconds", processing_time)
                        
                        # Simulate random errors
                        if random.random() < OPERATION_ERROR_PROBABILITY:
                            span.set_status(StatusCode.ERROR)
                            span.set_attribute("error.message", f"Simulated worker error in {operation_type}")
                            
                            return {
                                "success": False,
                                "error": f"Simulated worker error in {operation_type}",
                                "trace_id": self.tracer.get_trace_id()
                            }
                            
                        # Record a successful event
                        span.add_event(
                            name="operation.processed",
                            attributes={
                                "worker.id": self.worker_id,
                                "processing.time_seconds": processing_time
                            }
                        )
                        
                        return {
                            "success": True,
                            "message": f"Operation {operation_id} processed successfully",
                            "processing_time": processing_time,
                            "worker_id": self.worker_id,
                            "trace_id": self.tracer.get_trace_id()
                        }
                        
                    except Exception as e:
                        # Handle processing error
                        span.record_exception(e)
                        span.set_status(StatusCode.ERROR)
                        
                        return {
                            "success": False,
                            "error": str(e),
                            "worker_id": self.worker_id,
                            "trace_id": self.tracer.get_trace_id()
                        }


async def run_simulation(args):
    """Run the complete simulation."""
    logger.info("Starting WAL tracing simulation")
    
    # Determine exporter based on arguments
    if args.exporter == "jaeger":
        exporter_type = TracingExporterType.JAEGER
        exporter_endpoint = args.endpoint or "http://localhost:14268/api/traces"
    elif args.exporter == "zipkin":
        exporter_type = TracingExporterType.ZIPKIN
        exporter_endpoint = args.endpoint or "http://localhost:9411/api/v2/spans"
    elif args.exporter == "otlp":
        exporter_type = TracingExporterType.OTLP
        exporter_endpoint = args.endpoint or "http://localhost:4317"
    else:
        exporter_type = TracingExporterType.CONSOLE
        exporter_endpoint = None
    
    # Create master service
    master_port = args.master_port
    worker_ports = [args.worker_port + i for i in range(args.workers)]
    
    master = MasterService(
        port=master_port,
        exporter_type=exporter_type,
        exporter_endpoint=exporter_endpoint,
        worker_ports=worker_ports
    )
    
    # Create worker services
    workers = []
    for i in range(args.workers):
        worker = WorkerService(
            port=worker_ports[i],
            exporter_type=exporter_type,
            exporter_endpoint=exporter_endpoint,
            worker_id=i+1,
            master_url=f"http://localhost:{master_port}"
        )
        workers.append(worker)
    
    # Start services
    logger.info("Starting master and worker services")
    await master.start()
    for worker in workers:
        await worker.start()
        
    # Run background health simulation
    anyio.create_task(master.simulate_backend_health())
    anyio.create_task(master.check_worker_health())
    
    # Run simulation for specified duration
    end_time = time.time() + args.duration
    
    logger.info(f"Starting operation simulation for {args.duration} seconds")
    operations_sent = 0
    
    try:
        while time.time() < end_time:
            # Generate random operations
            if AIOHTTP_AVAILABLE:
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"http://localhost:{master_port}/api/simulate") as response:
                            if response.status == 200:
                                data = await response.json()
                                operations_sent += 1
                                
                                if operations_sent % 10 == 0:
                                    logger.info(f"Sent {operations_sent} operations")
                    except Exception as e:
                        logger.error(f"Error in simulation request: {e}")
            else:
                # Just simulate the increment
                operations_sent += 1
                if operations_sent % 10 == 0:
                    logger.info(f"Simulated {operations_sent} operations")
            
            # Wait for next operation
            await anyio.sleep(args.interval)
            
        logger.info(f"Simulation completed with {operations_sent} operations")
        
        # Wait a bit for processing to complete
        logger.info("Allowing time for final processing...")
        await anyio.sleep(5)
        
    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user")
    finally:
        # Clean up
        logger.info("Shutting down services")
        for worker in workers:
            worker.close()
        master.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WAL Telemetry Tracing Simulation")
    parser.add_argument("--exporter", choices=["console", "jaeger", "zipkin", "otlp"], 
                        default="console", help="Tracing exporter type")
    parser.add_argument("--endpoint", help="Exporter endpoint URL")
    parser.add_argument("--master-port", type=int, default=8000, help="Master service port")
    parser.add_argument("--worker-port", type=int, default=8100, help="Base port for worker services")
    parser.add_argument("--workers", type=int, default=WORKER_COUNT, help="Number of worker services")
    parser.add_argument("--duration", type=int, default=SIM_DURATION_SECONDS, 
                        help="Simulation duration in seconds")
    parser.add_argument("--interval", type=float, default=REQUEST_INTERVAL_SECONDS, 
                        help="Interval between operations in seconds")
    
    args = parser.parse_args()
    
    if not WAL_AVAILABLE:
        print("WAL components not available. Cannot run simulation.")
        sys.exit(1)
        
    if not FASTAPI_AVAILABLE:
        print("WARNING: FastAPI not available. Simulation will run in limited mode.")
        
    if not AIOHTTP_AVAILABLE:
        print("WARNING: aiohttp not available. HTTP requests will be simulated.")
    
    # Print simulation info
    print(f"Starting WAL telemetry tracing simulation:")
    print(f"- Exporter: {args.exporter}" + (f" ({args.endpoint})" if args.endpoint else ""))
    print(f"- Master port: {args.master_port}")
    print(f"- Worker ports: {args.worker_port}-{args.worker_port + args.workers - 1}")
    print(f"- Duration: {args.duration} seconds")
    print(f"- Operation interval: {args.interval} seconds")
    print()
    
    if args.exporter != "console":
        print(f"NOTE: Traces will be sent to {args.exporter}. Make sure it's running at the specified endpoint.")
        if args.exporter == "jaeger" and not args.endpoint:
            print("Jaeger UI should be available at: http://localhost:16686")
        elif args.exporter == "zipkin" and not args.endpoint:
            print("Zipkin UI should be available at: http://localhost:9411")
        print()
    
    # Run simulation
    try:
        anyio.run(run_simulation(args))
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")


if __name__ == "__main__":
    main()
