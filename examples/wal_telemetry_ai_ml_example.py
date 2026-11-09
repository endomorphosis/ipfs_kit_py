"""
Example showing WAL telemetry integration with AI/ML operations in IPFS Kit.

This example demonstrates how to use the WAL telemetry system to monitor AI/ML 
operations in IPFS Kit. It covers model loading, inference, training, and
distributed training with full telemetry and observability.

Key features demonstrated:
1. Setting up WAL telemetry with AI/ML extensions
2. Tracking model loading and initialization
3. Monitoring inference operations with latency tracking
4. Collecting training metrics with epochs and loss values
5. Visualizing AI/ML telemetry with Prometheus integration
"""

import time
import random
import numpy as np
import logging
import argparse
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import high-level API with graceful degradation
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.wal_telemetry_api import extend_high_level_api, WAL_TELEMETRY_AVAILABLE
    from ipfs_kit_py.wal_telemetry_ai_ml import extend_high_level_api_with_aiml_telemetry

    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available. This example requires WAL telemetry.")
except ImportError as e:
    logger.error(f"Could not import required modules: {e}")
    raise

# Try to import FastAPI for setting up metrics server (optional)
try:
    import fastapi
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI not available. Metrics server will not be started.")
    FASTAPI_AVAILABLE = False


class WALTelemetryAIMLExample:
    """
    Example application demonstrating WAL telemetry integration with AI/ML operations.
    """
    
    def __init__(self):
        """Initialize the example application."""
        self.api = None
        self.app = None
        
    def setup(self):
        """Set up the high-level API with WAL telemetry and AI/ML extensions."""
        # Create high-level API instance
        self.api = IPFSSimpleAPI(role="master")
        
        # Extend with WAL telemetry capabilities
        self.api = extend_high_level_api(self.api)
        
        # Initialize WAL telemetry with metrics
        telemetry_result = self.api.wal_telemetry(
            enabled=True,
            aggregation_interval=5,  # Aggregate metrics every 5 seconds
            max_history_entries=100  # Keep the last 100 history entries
        )
        
        if not telemetry_result.get("success", False):
            logger.error(f"Failed to initialize WAL telemetry: {telemetry_result.get('error')}")
            return False
        
        # Initialize Prometheus integration
        prometheus_result = self.api.wal_prometheus(
            enabled=True,
            port=9090,  # Prometheus metrics port
            start_http_server=False  # We'll use FastAPI to serve metrics
        )
        
        if not prometheus_result.get("success", False):
            logger.warning(f"Failed to initialize Prometheus: {prometheus_result.get('error')}")
        
        # Initialize distributed tracing
        tracing_result = self.api.wal_tracing(
            enabled=True,
            service_name="ipfs-aiml-example"
        )
        
        if not tracing_result.get("success", False):
            logger.warning(f"Failed to initialize tracing: {tracing_result.get('error')}")
        
        # Extend with AI/ML telemetry capabilities
        self.api = extend_high_level_api_with_aiml_telemetry(self.api)
        
        # Initialize AI/ML telemetry
        aiml_result = self.api.wal_aiml_telemetry()
        
        if not aiml_result.get("success", False):
            logger.error(f"Failed to initialize AI/ML telemetry: {aiml_result.get('error')}")
            return False
        
        logger.info("WAL telemetry with AI/ML extensions initialized successfully")
        return True
    
    def setup_metrics_server(self):
        """Set up FastAPI server with metrics endpoints."""
        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not available. Metrics server not started.")
            return False
        
        # Create FastAPI app
        self.app = FastAPI(title="IPFS AI/ML Telemetry Example")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add Prometheus metrics endpoint
        metrics_result = self.api.wal_add_metrics_endpoint(self.app)
        
        if not metrics_result.get("success", False):
            logger.warning(f"Failed to add metrics endpoint: {metrics_result.get('error')}")
        
        # Add distributed tracing middleware
        @self.app.middleware("http")
        async def tracing_middleware(request: Request, call_next):
            # Extract tracing context from request headers
            parent_context = self.api.wal_extract_tracing_context(dict(request.headers))
            
            # Create a span for this request
            with self.api.wal_create_span(
                name="http_request",
                context=parent_context,
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.path": request.url.path
                }
            ):
                # Process the request
                response = await call_next(request)
                return response
        
        # Add endpoints
        @self.app.get("/")
        async def root():
            return {"message": "IPFS AI/ML Telemetry Example API"}
        
        @self.app.get("/aiml-report")
        async def aiml_report():
            # Generate AI/ML metrics report
            report_result = self.api.wal_generate_metrics_report(format="markdown")
            if report_result.get("success", False):
                return {"report": report_result.get("report", "")}
            else:
                return {"error": report_result.get("error", "Unknown error")}
        
        logger.info("Metrics server set up successfully")
        return True
    
    def run_metrics_server(self, host="0.0.0.0", port=8000):
        """Run the FastAPI metrics server."""
        if not FASTAPI_AVAILABLE or not self.app:
            logger.warning("FastAPI not available or app not set up. Metrics server not started.")
            return False
        
        # Run the server
        uvicorn.run(self.app, host=host, port=port)
        return True
    
    def simulate_model_operations(self, num_models=3):
        """Simulate AI model operations with telemetry."""
        logger.info(f"Simulating operations for {num_models} models")
        
        # Define model frameworks for simulation
        frameworks = ["pytorch", "tensorflow", "scikit-learn"]
        model_sizes = [10 * 1024 * 1024, 50 * 1024 * 1024, 100 * 1024 * 1024]  # 10MB, 50MB, 100MB
        
        # Simulate model loading
        for i in range(num_models):
            model_id = f"model_{i+1}"
            framework = frameworks[i % len(frameworks)]
            model_size = model_sizes[i % len(model_sizes)]
            
            logger.info(f"Loading model {model_id} ({framework})...")
            
            # Track model loading with WAL telemetry
            with self.api.wal_track_model_operation(
                operation_type="model_load",
                model_id=model_id,
                framework=framework,
                model_size=model_size
            ):
                # Simulate model loading time based on size
                load_time = model_size / (20 * 1024 * 1024)  # ~1s per 20MB
                time.sleep(load_time)
            
            logger.info(f"Initializing model {model_id} on device...")
            
            # Track model initialization with WAL telemetry
            with self.api.wal_track_model_operation(
                operation_type="model_init",
                model_id=model_id,
                device="cuda" if i % 2 == 0 else "cpu"
            ):
                # Simulate initialization time
                time.sleep(0.5)
        
        logger.info("Model operations completed")
        return True
    
    def simulate_inference(self, num_inferences=10):
        """Simulate model inference operations with telemetry."""
        logger.info(f"Simulating {num_inferences} inference operations")
        
        models = ["model_1", "model_2", "model_3"]
        batch_sizes = [1, 4, 8, 16]
        
        for i in range(num_inferences):
            model_id = models[i % len(models)]
            batch_size = batch_sizes[i % len(batch_sizes)]
            
            logger.info(f"Running inference with {model_id}, batch size {batch_size}...")
            
            # Track inference with WAL telemetry
            with self.api.wal_track_inference(
                model_id=model_id,
                batch_size=batch_size,
                input_type="image" if i % 2 == 0 else "text"
            ):
                # Simulate inference time based on model and batch size
                base_time = 0.1  # 100ms base latency
                model_factor = 1.0 + (int(model_id.split("_")[1]) * 0.2)  # More complex models are slower
                batch_factor = 0.8 + (batch_size * 0.05)  # Larger batches take longer but have better throughput
                
                inference_time = base_time * model_factor * batch_factor
                time.sleep(inference_time)
        
        logger.info("Inference operations completed")
        return True
    
    def simulate_training(self, num_epochs=5):
        """Simulate model training operations with telemetry."""
        logger.info(f"Simulating training for {num_epochs} epochs")
        
        model_id = "model_1"
        num_samples = 1000
        
        # Initial loss value
        loss = 2.5
        learning_rate = 0.01
        
        for epoch in range(num_epochs):
            logger.info(f"Training epoch {epoch+1}/{num_epochs}...")
            
            # Track training epoch with WAL telemetry
            with self.api.wal_track_training_epoch(
                model_id=model_id,
                epoch=epoch,
                num_samples=num_samples
            ):
                # Simulate epoch processing time
                time.sleep(2.0)
                
                # Compute new loss (decreasing over time)
                loss = max(0.1, loss * 0.8)
                
                # Compute gradient norm (decreasing over time)
                gradient_norm = max(0.01, 1.0 - (epoch / num_epochs))
                
                # Compute learning rate (decreasing over time)
                learning_rate = 0.01 * (0.9 ** epoch)
            
            # Record training statistics
            self.api.wal_record_training_stats(
                model_id=model_id,
                epoch=epoch,
                loss=loss,
                learning_rate=learning_rate,
                gradient_norm=gradient_norm
            )
            
            logger.info(f"Epoch {epoch+1} completed: loss={loss:.4f}, lr={learning_rate:.6f}")
        
        logger.info("Training completed")
        return True
    
    def simulate_dataset_operations(self, num_datasets=2):
        """Simulate dataset operations with telemetry."""
        logger.info(f"Simulating operations for {num_datasets} datasets")
        
        formats = ["csv", "parquet", "json", "tfrecord"]
        sizes = [100 * 1024 * 1024, 500 * 1024 * 1024, 1024 * 1024 * 1024]  # 100MB, 500MB, 1GB
        
        for i in range(num_datasets):
            dataset_id = f"dataset_{i+1}"
            format = formats[i % len(formats)]
            size = sizes[i % len(sizes)]
            
            logger.info(f"Loading dataset {dataset_id} ({format}, {size/(1024*1024):.0f}MB)...")
            
            # Track dataset loading with WAL telemetry
            with self.api.wal_track_dataset_operation(
                operation_type="dataset_load",
                dataset_id=dataset_id,
                format=format,
                dataset_size=size
            ):
                # Simulate dataset loading time based on size
                load_time = size / (200 * 1024 * 1024)  # ~1s per 200MB
                time.sleep(load_time)
            
            logger.info(f"Preprocessing dataset {dataset_id}...")
            
            # Track dataset preprocessing with WAL telemetry
            with self.api.wal_track_dataset_operation(
                operation_type="dataset_preprocess",
                dataset_id=dataset_id,
                operation="normalize"
            ):
                # Simulate preprocessing time
                time.sleep(1.0)
        
        logger.info("Dataset operations completed")
        return True
    
    def simulate_distributed_training(self, num_workers=3, num_tasks=2):
        """Simulate distributed training operations with telemetry."""
        logger.info(f"Simulating distributed training with {num_workers} workers, {num_tasks} tasks")
        
        for task_idx in range(num_tasks):
            task_id = f"training_task_{task_idx+1}"
            
            logger.info(f"Starting task {task_id} coordination...")
            
            # Track worker coordination with WAL telemetry
            with self.api.wal_track_distributed_operation(
                operation_type="worker_coordination",
                task_id=task_id,
                num_workers=num_workers
            ):
                # Simulate coordination overhead time
                time.sleep(1.0)
            
            logger.info(f"Distributing work for task {task_id}...")
            
            # Track task distribution with WAL telemetry
            with self.api.wal_track_distributed_operation(
                operation_type="task_distribution",
                task_id=task_id,
                num_workers=num_workers
            ):
                # Simulate task distribution time
                time.sleep(0.5)
            
            # Record worker utilization
            for worker_idx in range(num_workers):
                worker_id = f"worker_{worker_idx+1}"
                # Simulate varying worker utilizations
                utilization = 0.5 + (0.4 * random.random())
                
                self.api.wal_record_worker_utilization(
                    worker_id=worker_id,
                    utilization=utilization
                )
            
            logger.info(f"Aggregating results for task {task_id}...")
            
            # Track result aggregation with WAL telemetry
            with self.api.wal_track_distributed_operation(
                operation_type="result_aggregation",
                task_id=task_id,
                num_workers=num_workers
            ):
                # Simulate result aggregation time
                time.sleep(0.8)
        
        logger.info("Distributed training completed")
        return True
    
    def print_metrics_report(self):
        """Print the metrics report to the console."""
        logger.info("Generating AI/ML metrics report...")
        
        report_result = self.api.wal_generate_metrics_report(format="markdown")
        
        if report_result.get("success", False):
            print("\n" + "=" * 80)
            print("AI/ML METRICS REPORT")
            print("=" * 80)
            print(report_result.get("report", "No report available"))
            print("=" * 80 + "\n")
        else:
            logger.error(f"Failed to generate metrics report: {report_result.get('error')}")
        
        return True


def main():
    """Main function to run the example."""
    parser = argparse.ArgumentParser(description="WAL Telemetry AI/ML Example")
    parser.add_argument("--server", action="store_true", help="Run the metrics server")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--models", type=int, default=3, help="Number of models to simulate")
    parser.add_argument("--inferences", type=int, default=10, help="Number of inferences to simulate")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs to simulate")
    parser.add_argument("--datasets", type=int, default=2, help="Number of datasets to simulate")
    parser.add_argument("--workers", type=int, default=3, help="Number of workers for distributed training")
    
    args = parser.parse_args()
    
    # Create and set up the example
    example = WALTelemetryAIMLExample()
    if not example.setup():
        logger.error("Failed to set up the example")
        return 1
    
    # Set up metrics server if requested
    if args.server and FASTAPI_AVAILABLE:
        if not example.setup_metrics_server():
            logger.error("Failed to set up metrics server")
            return 1
        
        logger.info(f"Starting metrics server on port {args.port}. Press Ctrl+C to stop.")
        try:
            example.run_metrics_server(port=args.port)
        except KeyboardInterrupt:
            logger.info("Metrics server stopped")
            return 0
    else:
        # Run the simulation
        example.simulate_model_operations(num_models=args.models)
        example.simulate_inference(num_inferences=args.inferences)
        example.simulate_training(num_epochs=args.epochs)
        example.simulate_dataset_operations(num_datasets=args.datasets)
        example.simulate_distributed_training(num_workers=args.workers)
        
        # Print metrics report
        example.print_metrics_report()
    
    return 0


if __name__ == "__main__":
    exit(main())