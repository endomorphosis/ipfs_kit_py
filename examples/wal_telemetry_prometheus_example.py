#!/usr/bin/env python3
# examples/wal_telemetry_prometheus_example.py

"""
Example of integrating WAL telemetry with Prometheus.

This example demonstrates how to:
1. Set up a WAL telemetry system
2. Integrate it with Prometheus for metrics exporting
3. Expose metrics through a FastAPI server
4. Generate sample workload to produce metrics

Prerequisites:
- prometheus_client package installed (pip install prometheus_client)
- fastapi package installed (pip install fastapi uvicorn)
"""

import os
import time
import sys
import random
import logging
import asyncio
import threading
import argparse
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import WAL components
try:
    from ipfs_kit_py.storage_wal import (
        StorageWriteAheadLog,
        BackendHealthMonitor,
        OperationType
    )
    from ipfs_kit_py.wal_telemetry import WALTelemetry
    from ipfs_kit_py.wal_telemetry_prometheus import (
        WALTelemetryPrometheusExporter,
        add_wal_metrics_endpoint
    )
except ImportError as e:
    print(f"Required modules not available: {e}")
    print("Make sure ipfs_kit_py is installed or in your Python path")
    sys.exit(1)

# Try to import FastAPI
try:
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, RedirectResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    print("FastAPI not available. Install with 'pip install fastapi uvicorn'")
    FASTAPI_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Workload generation constants
OPERATION_TYPES = ["add", "get", "pin", "unpin", "list"]
BACKENDS = ["ipfs", "s3", "storacha"]
OPERATION_DELAY_RANGE = (0.1, 0.5)  # seconds
SUCCESS_RATE = 0.95  # 95% success rate

class WorkloadGenerator:
    """Generates sample workload for WAL telemetry demo."""
    
    def __init__(self, wal, operations_per_second=10):
        """
        Initialize workload generator.
        
        Args:
            wal: WAL instance to send operations to
            operations_per_second: Target number of operations per second
        """
        self.wal = wal
        self.operations_per_second = operations_per_second
        self.running = False
        self.thread = None
        self.operations_count = 0
        self.start_time = None
        
    def start(self):
        """Start generating workload."""
        if self.running:
            return
            
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(
            target=self._generation_loop,
            name="WorkloadGenerator",
            daemon=True
        )
        self.thread.start()
        logger.info(f"Started workload generator at {self.operations_per_second} ops/sec")
        
    def stop(self):
        """Stop generating workload."""
        if not self.running:
            return
            
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        duration = time.time() - self.start_time if self.start_time else 0
        if duration > 0:
            rate = self.operations_count / duration
            logger.info(f"Stopped workload generator. Generated {self.operations_count} "
                        f"operations at {rate:.2f} ops/sec")
        
    def _generation_loop(self):
        """Main generation loop."""
        while self.running:
            start_time = time.time()
            
            # Determine how many operations to generate in this iteration
            ops_to_generate = max(1, int(self.operations_per_second / 10))
            
            # Generate operations
            for _ in range(ops_to_generate):
                if not self.running:
                    break
                    
                try:
                    self._generate_operation()
                    self.operations_count += 1
                except Exception as e:
                    logger.error(f"Error generating operation: {e}")
                    
            # Calculate sleep time to maintain operations_per_second
            elapsed = time.time() - start_time
            target_time = 1.0 / 10  # 10 cycles per second
            sleep_time = max(0, target_time - elapsed)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def _generate_operation(self):
        """Generate a single operation."""
        # Select random operation parameters
        op_type = random.choice(OPERATION_TYPES)
        backend = random.choice(BACKENDS)
        
        # Create parameters based on operation type
        parameters = {
            "path": f"/tmp/test/file_{random.randint(1, 1000)}.txt",
            "timestamp": datetime.now().isoformat()
        }
        
        # Add operation to WAL
        result = self.wal.add_operation(
            operation_type=op_type,
            backend=backend,
            parameters=parameters
        )
        
        if result.get("success", False) and "operation_id" in result:
            operation_id = result["operation_id"]
            
            # Simulate processing delay
            delay = random.uniform(*OPERATION_DELAY_RANGE)
            time.sleep(delay)
            
            # Update to processing status
            self.wal.update_operation_status(
                operation_id, 
                "processing"
            )
            
            # Simulate more processing time
            delay = random.uniform(*OPERATION_DELAY_RANGE)
            time.sleep(delay)
            
            # Complete or fail based on success rate
            if random.random() < SUCCESS_RATE:
                # Success
                self.wal.update_operation_status(
                    operation_id, 
                    "completed",
                    updates={
                        "result": {
                            "cid": f"Qm{''.join(random.choices('abcdef0123456789', k=44))}",
                            "size": random.randint(100, 10000000)
                        }
                    }
                )
            else:
                # Failure
                self.wal.update_operation_status(
                    operation_id, 
                    "failed",
                    updates={
                        "error": "Simulated random failure",
                        "error_type": random.choice([
                            "connection_error", "timeout_error", 
                            "validation_error", "backend_error"
                        ]),
                        "retry_count": random.randint(0, 3)
                    }
                )

def setup_fastapi_app(telemetry):
    """Set up a FastAPI application with metrics endpoint and dashboard."""
    if not FASTAPI_AVAILABLE:
        return None
        
    app = FastAPI(title="WAL Telemetry Demo")
    
    # Add Prometheus metrics endpoint
    add_wal_metrics_endpoint(app, telemetry)
    
    # Add a simple dashboard
    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        # Get real-time metrics
        metrics = telemetry.get_real_time_metrics()
        
        # Format dashboard HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>WAL Telemetry Dashboard</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #333; }}
                .card {{ border: 1px solid #ddd; border-radius: 5px; 
                         padding: 15px; margin: 10px 0; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); 
                         gap: 15px; }}
                .good {{ color: green; }}
                .warn {{ color: orange; }}
                .error {{ color: red; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ text-align: left; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .links {{ margin: 20px 0; }}
                .links a {{ margin-right: 15px; }}
            </style>
        </head>
        <body>
            <h1>WAL Telemetry Dashboard</h1>
            <p>Real-time monitoring as of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="links">
                <a href="/metrics/wal" target="_blank">Prometheus Metrics</a>
                <a href="http://localhost:9090" target="_blank">Prometheus UI</a>
                <a href="http://localhost:3000" target="_blank">Grafana</a>
            </div>
            
            <h2>Operation Latency</h2>
            <div class="grid">
        """
        
        # Add latency cards
        for key, stats in metrics.get("latency", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                
                # Determine color based on latency
                mean_latency = stats.get("mean", 0)
                color_class = "good" if mean_latency < 0.2 else \
                             "warn" if mean_latency < 0.5 else "error"
                
                html += f"""
                <div class="card">
                    <h3>{op_type} on {backend}</h3>
                    <p class="{color_class}">Mean: {mean_latency:.3f}s</p>
                    <p>Median: {stats.get("median", 0):.3f}s</p>
                    <p>95%: {stats.get("percentile_95", 0):.3f}s</p>
                    <p>Count: {stats.get("count", 0)}</p>
                </div>
                """
        
        html += """
            </div>
            
            <h2>Success Rates</h2>
            <div class="grid">
        """
        
        # Add success rate cards
        for key, rate in metrics.get("success_rate", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                
                # Determine color based on success rate
                color_class = "good" if rate > 0.95 else \
                             "warn" if rate > 0.8 else "error"
                
                html += f"""
                <div class="card">
                    <h3>{op_type} on {backend}</h3>
                    <p class="{color_class}">Success Rate: {rate*100:.1f}%</p>
                </div>
                """
        
        html += """
            </div>
            
            <h2>Throughput</h2>
            <div class="grid">
        """
        
        # Add throughput cards
        for key, rate in metrics.get("throughput", {}).items():
            if ":" in key:
                op_type, backend = key.split(":", 1)
                
                html += f"""
                <div class="card">
                    <h3>{op_type} on {backend}</h3>
                    <p>Operations/min: {rate:.2f}</p>
                </div>
                """
        
        html += """
            </div>
            
            <script>
                // Auto-reload page every 5 seconds
                setTimeout(function() {
                    location.reload();
                }, 5000);
            </script>
        </body>
        </html>
        """
        
        return html
    
    @app.get("/favicon.ico")
    async def favicon():
        return RedirectResponse(url="/static/favicon.ico")
    
    return app

def run_fastapi_app(app, host="127.0.0.1", port=8000):
    """Run the FastAPI application."""
    uvicorn.run(app, host=host, port=port)

def simulate_backend_health(health_monitor):
    """Simulate backend health changes."""
    if not health_monitor:
        return
        
    # Set initial statuses
    health_monitor.set_backend_status("ipfs", "online")
    health_monitor.set_backend_status("s3", "online")
    health_monitor.set_backend_status("storacha", "online")
    
    # Start a thread to randomly change statuses
    def health_simulation():
        while True:
            # Sleep for a random interval
            time.sleep(random.uniform(30, 60))
            
            # Pick a random backend
            backend = random.choice(BACKENDS)
            
            # Get current status
            current_status = health_monitor.get_backend_status(backend)
            
            # Determine new status based on probabilities
            if current_status == "online":
                # 10% chance to degrade, 5% chance to go offline
                r = random.random()
                if r < 0.10:
                    health_monitor.set_backend_status(backend, "degraded")
                    logger.info(f"Backend {backend} degraded")
                elif r < 0.15:
                    health_monitor.set_backend_status(backend, "offline")
                    logger.info(f"Backend {backend} offline")
            elif current_status == "degraded":
                # 60% chance to recover, 20% chance to go offline
                r = random.random()
                if r < 0.60:
                    health_monitor.set_backend_status(backend, "online")
                    logger.info(f"Backend {backend} recovered")
                elif r < 0.80:
                    health_monitor.set_backend_status(backend, "offline")
                    logger.info(f"Backend {backend} offline")
            else:  # offline
                # 70% chance to come back online in degraded state
                r = random.random()
                if r < 0.70:
                    health_monitor.set_backend_status(backend, "degraded")
                    logger.info(f"Backend {backend} back online (degraded)")
    
    # Start health simulation thread
    health_thread = threading.Thread(
        target=health_simulation,
        name="HealthSimulation",
        daemon=True
    )
    health_thread.start()

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="WAL Telemetry Prometheus Example")
    parser.add_argument("--metrics-port", type=int, default=9101,
                       help="Port for Prometheus metrics server")
    parser.add_argument("--api-port", type=int, default=8000,
                       help="Port for FastAPI server")
    parser.add_argument("--ops-per-second", type=int, default=10,
                       help="Operations per second for workload generator")
    args = parser.parse_args()
    
    # Create temporary directory
    base_path = os.path.expanduser("~/.ipfs_kit/wal_prometheus_example")
    os.makedirs(base_path, exist_ok=True)
    
    # Create health monitor
    health_monitor = BackendHealthMonitor(
        check_interval=5,
        history_size=10
    )
    
    # Create WAL instance
    wal = StorageWriteAheadLog(
        base_path=os.path.join(base_path, "wal"),
        partition_size=1000,
        health_monitor=health_monitor
    )
    
    # Create telemetry instance
    telemetry = WALTelemetry(
        wal=wal,
        metrics_path=os.path.join(base_path, "telemetry"),
        sampling_interval=5,
        enable_detailed_timing=True,
        operation_hooks=True
    )
    
    # Create Prometheus exporter
    exporter = WALTelemetryPrometheusExporter(telemetry)
    
    # Start Prometheus metrics server
    exporter.start_server(port=args.metrics_port)
    logger.info(f"Prometheus metrics server running on port {args.metrics_port}")
    
    # Create workload generator
    workload = WorkloadGenerator(
        wal=wal,
        operations_per_second=args.ops_per_second
    )
    
    # Create FastAPI app if available
    app = None
    if FASTAPI_AVAILABLE:
        app = setup_fastapi_app(telemetry)
        
        # Start FastAPI in a separate thread
        api_thread = threading.Thread(
            target=run_fastapi_app,
            args=(app, "0.0.0.0", args.api_port),
            name="FastAPIThread",
            daemon=True
        )
        api_thread.start()
        logger.info(f"FastAPI server running on port {args.api_port}")
        logger.info(f"Dashboard available at http://localhost:{args.api_port}/")
    else:
        logger.warning("FastAPI not available. Install with 'pip install fastapi uvicorn'")
    
    # Simulate backend health changes
    simulate_backend_health(health_monitor)
    
    # Start workload generation
    workload.start()
    
    # Instructions for Prometheus setup
    print("\nPrometheus Configuration:")
    print("========================")
    print("To configure Prometheus to scrape these metrics, add this to your prometheus.yml:")
    print("""
  - job_name: 'wal_telemetry'
    scrape_interval: 5s
    static_configs:
      - targets: ['localhost:9101']
    """)
    
    # Run until interrupted
    try:
        print("\nPress Ctrl+C to exit")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Stop workload generator
        workload.stop()
        
        # Close telemetry
        telemetry.close()
        
        # Close WAL
        wal.close()
        
        # Close health monitor
        health_monitor.close()
        
        print("Cleanup complete")

if __name__ == "__main__":
    main()