"""
WAL Telemetry integration for AI/ML operations in IPFS Kit with AnyIO support.

This module extends the WAL telemetry system to provide specialized monitoring
and tracing for AI/ML operations. It includes metrics for model loading times,
inference latency, training throughput, and distributed training coordination.
It has been updated to support AnyIO for async backend flexibility.

Key features:
1. WAL telemetry integration with AIMLMetrics for comprehensive monitoring
2. Specialized Prometheus metrics for AI/ML operations
3. Distributed tracing support for model training and inference
4. Integration with the high-level API for ease of use
5. Context propagation for tracking AI/ML operations across services
6. AnyIO support for backend-agnostic async operations
"""

import json
import logging
import time
import uuid
import warnings
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

import anyio
import sniffio

# Import the core telemetry modules - use try/except for graceful degradation
try:
    # Check for AnyIO-compatible version first
    try:
        from ipfs_kit_py.wal_telemetry_api_anyio import WAL_TELEMETRY_AVAILABLE
        from ipfs_kit_py.wal_telemetry_api_anyio import WALTelemetryAPIExtensionAnyIO
        ANYIO_AVAILABLE = True
    except ImportError:
        # Fall back to standard version
        from ipfs_kit_py.wal_telemetry_api import WAL_TELEMETRY_AVAILABLE
        from ipfs_kit_py.wal_telemetry_api import WALTelemetryAPIExtension
        ANYIO_AVAILABLE = False
except ImportError:
    WAL_TELEMETRY_AVAILABLE = False
    ANYIO_AVAILABLE = False

# Import AI/ML metrics - use try/except for graceful degradation
try:
    from ipfs_kit_py.ai_ml_metrics import AIMLMetrics
    AIML_METRICS_AVAILABLE = True
except ImportError:
    AIML_METRICS_AVAILABLE = False

# Set up logger
logger = logging.getLogger(__name__)


class WALTelemetryAIMLExtensionAnyIO:
    """
    WAL Telemetry extension for AI/ML operations in IPFS Kit with AnyIO support.
    
    This class extends the WAL telemetry system with specialized metrics and
    tracing for AI/ML operations. It integrates with AIMLMetrics to provide
    a comprehensive monitoring solution for AI/ML workloads.
    """
    
    def __init__(self, base_extension):
        """
        Initialize the AI/ML telemetry extension.
        
        Args:
            base_extension: The base WALTelemetryAPIExtension instance
        """
        self.base_extension = base_extension
        self.api = base_extension.api if base_extension else None
        
        # Initialize AIMLMetrics if available
        self.ai_ml_metrics = None
        if AIML_METRICS_AVAILABLE:
            self.ai_ml_metrics = AIMLMetrics()
        
        # Store metrics registration info
        self.metrics_registered = False
        self.registry = {}
        
        # Mapping of AI/ML operations to telemetry categories
        self.operation_categories = {
            # Model operations
            "model_load": "model_operations",
            "model_init": "model_operations",
            "model_save": "model_operations",
            
            # Inference operations
            "inference": "inference",
            "batch_inference": "inference",
            "embeddings_generation": "inference",
            
            # Training operations
            "training_epoch": "training",
            "optimizer_step": "training",
            "gradient_update": "training",
            
            # Dataset operations
            "dataset_load": "data_operations",
            "dataset_preprocess": "data_operations",
            "dataset_transform": "data_operations",
            
            # Distributed operations
            "worker_coordination": "distributed",
            "result_aggregation": "distributed",
            "task_distribution": "distributed"
        }
    
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
    
    def initialize(self, metrics_instance=None):
        """
        Initialize the AI/ML telemetry with optional metrics instance.
        
        Args:
            metrics_instance: Optional AIMLMetrics instance to use
            
        Returns:
            Result dictionary with initialization status
        """
        # Warn if called from async context
        self._warn_if_async_context("initialize")
        
        result = {
            "success": False,
            "operation": "initialize_aiml_telemetry",
            "timestamp": time.time()
        }
        
        try:
            # Make sure base extension is initialized
            if not self.base_extension or not hasattr(self.base_extension, "telemetry"):
                result["error"] = "Base WAL telemetry extension not initialized"
                result["error_type"] = "configuration_error"
                return result
            
            # Use provided metrics instance or existing one
            if metrics_instance and AIML_METRICS_AVAILABLE:
                self.ai_ml_metrics = metrics_instance
            elif not self.ai_ml_metrics and AIML_METRICS_AVAILABLE:
                self.ai_ml_metrics = AIMLMetrics()
            
            # Register AI/ML metrics with Prometheus (if exporter exists)
            if hasattr(self.base_extension, "prometheus_exporter") and self.base_extension.prometheus_exporter:
                self._register_prometheus_metrics()
            
            result["success"] = True
            result["message"] = "AI/ML telemetry initialized successfully"
            
            if not AIML_METRICS_AVAILABLE:
                result["warning"] = "AIMLMetrics module not available, limited functionality"
            
        except Exception as e:
            result["error"] = f"Failed to initialize AI/ML telemetry: {str(e)}"
            result["error_type"] = "initialization_error"
            logger.exception("Error initializing AI/ML telemetry")
        
        return result
    
    async def initialize_async(self, metrics_instance=None):
        """
        Initialize the AI/ML telemetry with optional metrics instance asynchronously.
        
        Args:
            metrics_instance: Optional AIMLMetrics instance to use
            
        Returns:
            Result dictionary with initialization status
        """
        result = {
            "success": False,
            "operation": "initialize_aiml_telemetry",
            "timestamp": time.time()
        }
        
        try:
            # Make sure base extension is initialized
            if not self.base_extension or not hasattr(self.base_extension, "telemetry"):
                result["error"] = "Base WAL telemetry extension not initialized"
                result["error_type"] = "configuration_error"
                return result
            
            # Use provided metrics instance or existing one
            if metrics_instance and AIML_METRICS_AVAILABLE:
                self.ai_ml_metrics = metrics_instance
            elif not self.ai_ml_metrics and AIML_METRICS_AVAILABLE:
                # Create metrics instance in a thread to avoid blocking
                self.ai_ml_metrics = await anyio.to_thread.run_sync(AIMLMetrics)
            
            # Register AI/ML metrics with Prometheus (if exporter exists)
            if hasattr(self.base_extension, "prometheus_exporter") and self.base_extension.prometheus_exporter:
                # Run in a thread to avoid blocking
                await anyio.to_thread.run_sync(self._register_prometheus_metrics)
            
            result["success"] = True
            result["message"] = "AI/ML telemetry initialized successfully"
            
            if not AIML_METRICS_AVAILABLE:
                result["warning"] = "AIMLMetrics module not available, limited functionality"
            
        except Exception as e:
            result["error"] = f"Failed to initialize AI/ML telemetry: {str(e)}"
            result["error_type"] = "initialization_error"
            logger.exception("Error initializing AI/ML telemetry")
        
        return result
    
    def _register_prometheus_metrics(self):
        """
        Register AI/ML specific metrics with the Prometheus exporter.
        """
        if self.metrics_registered or not hasattr(self.base_extension, "prometheus_exporter"):
            return
        
        try:
            # Get Prometheus registry from base extension
            exporter = self.base_extension.prometheus_exporter
            
            # Import prometheus_client if available
            try:
                import prometheus_client as prom
                from prometheus_client import Counter, Gauge, Histogram, Summary
                
                # Model metrics
                self.registry["model_load_time"] = Histogram(
                    "ipfs_aiml_model_load_seconds",
                    "Time taken to load models (seconds)",
                    ["model_id", "framework"]
                )
                
                self.registry["model_size"] = Gauge(
                    "ipfs_aiml_model_size_bytes",
                    "Size of models in bytes",
                    ["model_id", "framework"]
                )
                
                # Inference metrics
                self.registry["inference_latency"] = Histogram(
                    "ipfs_aiml_inference_seconds",
                    "Inference latency in seconds",
                    ["model_id", "batch_size"]
                )
                
                self.registry["inference_throughput"] = Gauge(
                    "ipfs_aiml_inference_throughput",
                    "Inference throughput (items/second)",
                    ["model_id"]
                )
                
                self.registry["inference_memory"] = Gauge(
                    "ipfs_aiml_inference_memory_bytes",
                    "Memory usage during inference in bytes",
                    ["model_id"]
                )
                
                # Training metrics
                self.registry["training_epoch_time"] = Histogram(
                    "ipfs_aiml_training_epoch_seconds",
                    "Training epoch time in seconds",
                    ["model_id"]
                )
                
                self.registry["training_samples_per_second"] = Gauge(
                    "ipfs_aiml_training_samples_per_second",
                    "Training throughput (samples/second)",
                    ["model_id"]
                )
                
                self.registry["training_loss"] = Gauge(
                    "ipfs_aiml_training_loss",
                    "Training loss value",
                    ["model_id", "epoch"]
                )
                
                # Dataset metrics
                self.registry["dataset_load_time"] = Histogram(
                    "ipfs_aiml_dataset_load_seconds",
                    "Dataset loading time in seconds",
                    ["dataset_id", "format"]
                )
                
                self.registry["dataset_size"] = Gauge(
                    "ipfs_aiml_dataset_size_bytes",
                    "Dataset size in bytes",
                    ["dataset_id"]
                )
                
                # Distributed training metrics
                self.registry["coordination_overhead"] = Histogram(
                    "ipfs_aiml_coordination_overhead_seconds",
                    "Coordination overhead in distributed training",
                    ["operation"]
                )
                
                self.registry["worker_utilization"] = Gauge(
                    "ipfs_aiml_worker_utilization_ratio",
                    "Worker utilization ratio (0.0-1.0)",
                    ["worker_id"]
                )
                
                # General operation counters
                self.registry["ai_operations_total"] = Counter(
                    "ipfs_aiml_operations_total",
                    "Total number of AI/ML operations",
                    ["operation_type", "status"]
                )
                
                # Register with the WAL Prometheus exporter
                for metric in self.registry.values():
                    exporter.registry.register(metric)
                
                self.metrics_registered = True
                
            except ImportError:
                logger.warning("prometheus_client not available, skipping metrics registration")
                
        except Exception as e:
            logger.error(f"Error registering AI/ML Prometheus metrics: {e}")
    
    def update_prometheus_metrics(self, metrics_data):
        """
        Update Prometheus metrics with the latest data from AIMLMetrics.
        
        Args:
            metrics_data: Dictionary with metrics data to update
            
        Returns:
            Result dictionary with update status
        """
        # Warn if called from async context
        self._warn_if_async_context("update_prometheus_metrics")
        
        result = {
            "success": False,
            "operation": "update_prometheus_metrics",
            "timestamp": time.time(),
            "metrics_updated": 0
        }
        
        if not self.metrics_registered:
            result["error"] = "Prometheus metrics not registered"
            return result
        
        try:
            updated_count = 0
            
            # Update model metrics
            if "models" in metrics_data and isinstance(metrics_data["models"], dict):
                for model_id, model_data in metrics_data["models"].get("models", {}).items():
                    # Update model size
                    if "size_bytes" in model_data and model_data["size_bytes"] is not None:
                        self.registry["model_size"].labels(
                            model_id=model_id,
                            framework=model_data.get("framework", "unknown")
                        ).set(model_data["size_bytes"])
                        updated_count += 1
                    
                    # Update load time histograms if there's new data
                    load_stats = model_data.get("load_time_stats", {})
                    if load_stats.get("count", 0) > 0 and hasattr(load_stats, "get"):
                        # We can only update the Histogram with actual observations,
                        # not with pre-computed statistics, so this is just a placeholder
                        # In a real implementation, this would be updated directly when
                        # observations occur
                        updated_count += 1
            
            # Update inference metrics
            if "inference" in metrics_data and isinstance(metrics_data["inference"], dict):
                for model_id, model_data in metrics_data["inference"].get("models", {}).items():
                    # Update throughput
                    throughput = model_data.get("throughput_stats", {}).get("mean")
                    if throughput is not None:
                        self.registry["inference_throughput"].labels(model_id=model_id).set(throughput)
                        updated_count += 1
            
            # Update training metrics
            if "training" in metrics_data and isinstance(metrics_data["training"], dict):
                for model_id, model_data in metrics_data["training"].get("models", {}).items():
                    # Update samples per second
                    samples_per_second = model_data.get("samples_per_second_stats", {}).get("mean")
                    if samples_per_second is not None:
                        self.registry["training_samples_per_second"].labels(
                            model_id=model_id
                        ).set(samples_per_second)
                        updated_count += 1
                    
                    # Update training loss
                    loss_progress = model_data.get("loss_progress", {})
                    if "final" in loss_progress and loss_progress["final"] is not None:
                        self.registry["training_loss"].labels(
                            model_id=model_id,
                            epoch=str(model_data.get("num_epochs", "latest"))
                        ).set(loss_progress["final"])
                        updated_count += 1
            
            # Update distributed metrics
            if "distributed" in metrics_data and isinstance(metrics_data["distributed"], dict):
                worker_utilization = metrics_data["distributed"].get("average_worker_utilization", {})
                for worker_id, utilization in worker_utilization.items():
                    self.registry["worker_utilization"].labels(worker_id=worker_id).set(utilization)
                    updated_count += 1
            
            result["success"] = True
            result["metrics_updated"] = updated_count
            
        except Exception as e:
            result["error"] = f"Failed to update Prometheus metrics: {str(e)}"
            result["error_type"] = "update_error"
            logger.error(f"Error updating AI/ML Prometheus metrics: {e}")
        
        return result
    
    async def update_prometheus_metrics_async(self, metrics_data):
        """
        Update Prometheus metrics with the latest data from AIMLMetrics asynchronously.
        
        Args:
            metrics_data: Dictionary with metrics data to update
            
        Returns:
            Result dictionary with update status
        """
        # Use anyio.to_thread.run_sync to run the synchronous function in a separate thread
        return await anyio.to_thread.run_sync(
            self.update_prometheus_metrics,
            metrics_data
        )
    
    @contextmanager
    def track_model_operation(self, operation_type, model_id, **kwargs):
        """
        Track a model-related operation with telemetry.
        
        Args:
            operation_type: Type of operation (load, init, save)
            model_id: Identifier for the model
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Warn if called from async context
        self._warn_if_async_context("track_model_operation")
        
        # Get operation category
        category = self.operation_categories.get(operation_type, "model_operations")
        
        # Start span in the base telemetry
        with self.base_extension.create_span(
            name=f"aiml.{operation_type}",
            attributes={
                "model.id": model_id,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                if operation_type == "model_load":
                    # Start AIMLMetrics tracking for model load
                    metrics_context = self.ai_ml_metrics.track_model_load(
                        model_id=model_id,
                        framework=kwargs.get("framework", "unknown"),
                        model_size=kwargs.get("model_size")
                    )
                elif operation_type == "model_init":
                    # Start AIMLMetrics tracking for model initialization
                    metrics_context = self.ai_ml_metrics.track_model_initialization(
                        model_id=model_id,
                        device=kwargs.get("device", "cpu")
                    )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "model_id": model_id
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="success"
                    ).inc()
                
            except Exception as e:
                # Record error in span
                span.record_exception(e)
                span.set_attribute("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="error"
                    ).inc()
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered and operation_type == "model_load":
                    duration = time.time() - tracking["start_time"]
                    self.registry["model_load_time"].labels(
                        model_id=model_id,
                        framework=kwargs.get("framework", "unknown")
                    ).observe(duration)
    
    async def track_model_operation_async(self, operation_type, model_id, **kwargs):
        """
        Track a model-related operation with telemetry asynchronously.
        
        This is an async context manager that provides the same functionality as 
        track_model_operation but with async support.
        
        Args:
            operation_type: Type of operation (load, init, save)
            model_id: Identifier for the model
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Get operation category
        category = self.operation_categories.get(operation_type, "model_operations")
        
        # Start span in the base telemetry
        async with self.base_extension.create_span_async(
            name=f"aiml.{operation_type}",
            attributes={
                "model.id": model_id,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                if operation_type == "model_load":
                    # Start AIMLMetrics tracking for model load asynchronously
                    metrics_context = await anyio.to_thread.run_sync(
                        lambda: self.ai_ml_metrics.track_model_load(
                            model_id=model_id,
                            framework=kwargs.get("framework", "unknown"),
                            model_size=kwargs.get("model_size")
                        )
                    )
                elif operation_type == "model_init":
                    # Start AIMLMetrics tracking for model initialization asynchronously
                    metrics_context = await anyio.to_thread.run_sync(
                        lambda: self.ai_ml_metrics.track_model_initialization(
                            model_id=model_id,
                            device=kwargs.get("device", "cpu")
                        )
                    )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "model_id": model_id
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    # Run in thread to avoid blocking
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="success"
                        ).inc()
                    )
                
            except Exception as e:
                # Record error in span
                await span.record_exception_async(e)
                await span.set_attribute_async("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    # Run in thread to avoid blocking
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="error"
                        ).inc()
                    )
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered and operation_type == "model_load":
                    duration = time.time() - tracking["start_time"]
                    # Run in thread to avoid blocking
                    await anyio.to_thread.run_sync(
                        lambda d=duration: self.registry["model_load_time"].labels(
                            model_id=model_id,
                            framework=kwargs.get("framework", "unknown")
                        ).observe(d)
                    )
    
    @contextmanager
    def track_inference(self, model_id, batch_size=1, **kwargs):
        """
        Track an inference operation with telemetry.
        
        Args:
            model_id: Identifier for the model
            batch_size: Size of the inference batch
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Warn if called from async context
        self._warn_if_async_context("track_inference")
        
        # Start span in the base telemetry
        with self.base_extension.create_span(
            name="aiml.inference",
            attributes={
                "model.id": model_id,
                "batch.size": batch_size,
                "operation.type": "inference",
                "operation.category": "inference",
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                # Start AIMLMetrics tracking for inference
                metrics_context = self.ai_ml_metrics.track_inference(
                    model_id=model_id,
                    batch_size=batch_size,
                    track_memory=kwargs.get("track_memory", True)
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "model_id": model_id,
                "batch_size": batch_size
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type="inference",
                        status="success"
                    ).inc()
                
            except Exception as e:
                # Record error in span
                span.record_exception(e)
                span.set_attribute("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type="inference",
                        status="error"
                    ).inc()
                
                # Re-raise the exception
                raise
            finally:
                # Record inference latency in histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    self.registry["inference_latency"].labels(
                        model_id=model_id,
                        batch_size=str(batch_size)
                    ).observe(duration)
                    
                    # Calculate and update throughput
                    if duration > 0:
                        throughput = batch_size / duration
                        self.registry["inference_throughput"].labels(
                            model_id=model_id
                        ).set(throughput)

    async def track_inference_async(self, model_id, batch_size=1, **kwargs):
        """
        Track an inference operation with telemetry asynchronously.
        
        Args:
            model_id: Identifier for the model
            batch_size: Size of the inference batch
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Start span in the base telemetry
        async with self.base_extension.create_span_async(
            name="aiml.inference",
            attributes={
                "model.id": model_id,
                "batch.size": batch_size,
                "operation.type": "inference",
                "operation.category": "inference",
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                # Start AIMLMetrics tracking for inference asynchronously
                metrics_context = await anyio.to_thread.run_sync(
                    lambda: self.ai_ml_metrics.track_inference(
                        model_id=model_id,
                        batch_size=batch_size,
                        track_memory=kwargs.get("track_memory", True)
                    )
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "model_id": model_id,
                "batch_size": batch_size
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type="inference",
                            status="success"
                        ).inc()
                    )
                
            except Exception as e:
                # Record error in span
                await span.record_exception_async(e)
                await span.set_attribute_async("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type="inference",
                            status="error"
                        ).inc()
                    )
                
                # Re-raise the exception
                raise
            finally:
                # Record inference latency in histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    
                    # Run in thread to avoid blocking
                    await anyio.to_thread.run_sync(
                        lambda d=duration: self.registry["inference_latency"].labels(
                            model_id=model_id,
                            batch_size=str(batch_size)
                        ).observe(d)
                    )
                    
                    # Calculate and update throughput
                    if duration > 0:
                        throughput = batch_size / duration
                        await anyio.to_thread.run_sync(
                            lambda t=throughput: self.registry["inference_throughput"].labels(
                                model_id=model_id
                            ).set(t)
                        )
    
    @contextmanager
    def track_training_epoch(self, model_id, epoch, num_samples, **kwargs):
        """
        Track a training epoch with telemetry.
        
        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            num_samples: Number of samples in the epoch
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Warn if called from async context
        self._warn_if_async_context("track_training_epoch")
        
        # Start span in the base telemetry
        with self.base_extension.create_span(
            name="aiml.training_epoch",
            attributes={
                "model.id": model_id,
                "epoch": epoch,
                "num_samples": num_samples,
                "operation.type": "training_epoch",
                "operation.category": "training",
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                # Start AIMLMetrics tracking for training epoch
                metrics_context = self.ai_ml_metrics.track_training_epoch(
                    model_id=model_id,
                    epoch=epoch,
                    num_samples=num_samples
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "model_id": model_id,
                "epoch": epoch,
                "num_samples": num_samples
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type="training_epoch",
                        status="success"
                    ).inc()
                
            except Exception as e:
                # Record error in span
                span.record_exception(e)
                span.set_attribute("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type="training_epoch",
                        status="error"
                    ).inc()
                
                # Re-raise the exception
                raise
            finally:
                # Record epoch time in histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    self.registry["training_epoch_time"].labels(
                        model_id=model_id
                    ).observe(duration)
                    
                    # Calculate and update samples per second
                    if duration > 0:
                        samples_per_second = num_samples / duration
                        self.registry["training_samples_per_second"].labels(
                            model_id=model_id
                        ).set(samples_per_second)
    
    async def track_training_epoch_async(self, model_id, epoch, num_samples, **kwargs):
        """
        Track a training epoch with telemetry asynchronously.
        
        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            num_samples: Number of samples in the epoch
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Start span in the base telemetry
        async with self.base_extension.create_span_async(
            name="aiml.training_epoch",
            attributes={
                "model.id": model_id,
                "epoch": epoch,
                "num_samples": num_samples,
                "operation.type": "training_epoch",
                "operation.category": "training",
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                # Start AIMLMetrics tracking for training epoch asynchronously
                metrics_context = await anyio.to_thread.run_sync(
                    lambda: self.ai_ml_metrics.track_training_epoch(
                        model_id=model_id,
                        epoch=epoch,
                        num_samples=num_samples
                    )
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "model_id": model_id,
                "epoch": epoch,
                "num_samples": num_samples
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type="training_epoch",
                            status="success"
                        ).inc()
                    )
                
            except Exception as e:
                # Record error in span
                await span.record_exception_async(e)
                await span.set_attribute_async("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type="training_epoch",
                            status="error"
                        ).inc()
                    )
                
                # Re-raise the exception
                raise
            finally:
                # Record epoch time in histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    
                    # Run in thread to avoid blocking
                    await anyio.to_thread.run_sync(
                        lambda d=duration: self.registry["training_epoch_time"].labels(
                            model_id=model_id
                        ).observe(d)
                    )
                    
                    # Calculate and update samples per second
                    if duration > 0:
                        samples_per_second = num_samples / duration
                        await anyio.to_thread.run_sync(
                            lambda s=samples_per_second: self.registry["training_samples_per_second"].labels(
                                model_id=model_id
                            ).set(s)
                        )
    
    def record_training_stats(self, model_id, epoch, loss, learning_rate=None, gradient_norm=None):
        """
        Record training statistics with telemetry.
        
        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            loss: The loss value for this epoch
            learning_rate: Optional learning rate
            gradient_norm: Optional gradient norm value
            
        Returns:
            Result dictionary with recording status
        """
        # Warn if called from async context
        self._warn_if_async_context("record_training_stats")
        
        result = {
            "success": False,
            "operation": "record_training_stats",
            "timestamp": time.time()
        }
        
        try:
            # Record in AIMLMetrics if available
            if self.ai_ml_metrics:
                self.ai_ml_metrics.record_training_stats(
                    model_id=model_id,
                    epoch=epoch,
                    loss=loss,
                    learning_rate=learning_rate,
                    gradient_norm=gradient_norm
                )
            
            # Record in Prometheus metrics
            if self.metrics_registered:
                self.registry["training_loss"].labels(
                    model_id=model_id,
                    epoch=str(epoch)
                ).set(loss)
            
            # Create a span for this event
            with self.base_extension.create_span(
                name="aiml.training_stats",
                attributes={
                    "model.id": model_id,
                    "epoch": epoch,
                    "loss": loss,
                    "learning_rate": learning_rate,
                    "gradient_norm": gradient_norm,
                    "operation.type": "training_stats",
                    "operation.category": "training"
                }
            ):
                # The span is automatically closed when exiting the context
                pass
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Failed to record training stats: {str(e)}"
            result["error_type"] = "recording_error"
            logger.error(f"Error recording training stats: {e}")
        
        return result
    
    async def record_training_stats_async(self, model_id, epoch, loss, learning_rate=None, gradient_norm=None):
        """
        Record training statistics with telemetry asynchronously.
        
        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            loss: The loss value for this epoch
            learning_rate: Optional learning rate
            gradient_norm: Optional gradient norm value
            
        Returns:
            Result dictionary with recording status
        """
        result = {
            "success": False,
            "operation": "record_training_stats",
            "timestamp": time.time()
        }
        
        try:
            # Record in AIMLMetrics if available
            if self.ai_ml_metrics:
                await anyio.to_thread.run_sync(
                    lambda: self.ai_ml_metrics.record_training_stats(
                        model_id=model_id,
                        epoch=epoch,
                        loss=loss,
                        learning_rate=learning_rate,
                        gradient_norm=gradient_norm
                    )
                )
            
            # Record in Prometheus metrics
            if self.metrics_registered:
                await anyio.to_thread.run_sync(
                    lambda: self.registry["training_loss"].labels(
                        model_id=model_id,
                        epoch=str(epoch)
                    ).set(loss)
                )
            
            # Create a span for this event
            async with self.base_extension.create_span_async(
                name="aiml.training_stats",
                attributes={
                    "model.id": model_id,
                    "epoch": epoch,
                    "loss": loss,
                    "learning_rate": learning_rate,
                    "gradient_norm": gradient_norm,
                    "operation.type": "training_stats",
                    "operation.category": "training"
                }
            ):
                # The span is automatically closed when exiting the context
                pass
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Failed to record training stats: {str(e)}"
            result["error_type"] = "recording_error"
            logger.error(f"Error recording training stats: {e}")
        
        return result
    
    @contextmanager
    def track_dataset_operation(self, operation_type, dataset_id, **kwargs):
        """
        Track a dataset-related operation with telemetry.
        
        Args:
            operation_type: Type of operation (load, preprocess, transform)
            dataset_id: Identifier for the dataset
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Warn if called from async context
        self._warn_if_async_context("track_dataset_operation")
        
        # Get operation category
        category = self.operation_categories.get(operation_type, "data_operations")
        
        # Start span in the base telemetry
        with self.base_extension.create_span(
            name=f"aiml.{operation_type}",
            attributes={
                "dataset.id": dataset_id,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                if operation_type == "dataset_load":
                    # Start AIMLMetrics tracking for dataset load
                    metrics_context = self.ai_ml_metrics.track_dataset_load(
                        dataset_id=dataset_id,
                        format=kwargs.get("format", "unknown"),
                        dataset_size=kwargs.get("dataset_size")
                    )
                elif operation_type == "dataset_preprocess":
                    # Start AIMLMetrics tracking for dataset preprocessing
                    metrics_context = self.ai_ml_metrics.track_dataset_preprocessing(
                        dataset_id=dataset_id,
                        operation=kwargs.get("operation", "preprocess")
                    )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "dataset_id": dataset_id
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="success"
                    ).inc()
                
            except Exception as e:
                # Record error in span
                span.record_exception(e)
                span.set_attribute("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="error"
                    ).inc()
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered and operation_type == "dataset_load":
                    duration = time.time() - tracking["start_time"]
                    self.registry["dataset_load_time"].labels(
                        dataset_id=dataset_id,
                        format=kwargs.get("format", "unknown")
                    ).observe(duration)
                
                # Record dataset size if provided
                if self.metrics_registered and operation_type == "dataset_load" and "dataset_size" in kwargs:
                    self.registry["dataset_size"].labels(
                        dataset_id=dataset_id
                    ).set(kwargs["dataset_size"])
    
    async def track_dataset_operation_async(self, operation_type, dataset_id, **kwargs):
        """
        Track a dataset-related operation with telemetry asynchronously.
        
        Args:
            operation_type: Type of operation (load, preprocess, transform)
            dataset_id: Identifier for the dataset
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Get operation category
        category = self.operation_categories.get(operation_type, "data_operations")
        
        # Start span in the base telemetry
        async with self.base_extension.create_span_async(
            name=f"aiml.{operation_type}",
            attributes={
                "dataset.id": dataset_id,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics:
                if operation_type == "dataset_load":
                    # Start AIMLMetrics tracking for dataset load asynchronously
                    metrics_context = await anyio.to_thread.run_sync(
                        lambda: self.ai_ml_metrics.track_dataset_load(
                            dataset_id=dataset_id,
                            format=kwargs.get("format", "unknown"),
                            dataset_size=kwargs.get("dataset_size")
                        )
                    )
                elif operation_type == "dataset_preprocess":
                    # Start AIMLMetrics tracking for dataset preprocessing asynchronously
                    metrics_context = await anyio.to_thread.run_sync(
                        lambda: self.ai_ml_metrics.track_dataset_preprocessing(
                            dataset_id=dataset_id,
                            operation=kwargs.get("operation", "preprocess")
                        )
                    )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "dataset_id": dataset_id
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="success"
                        ).inc()
                    )
                
            except Exception as e:
                # Record error in span
                await span.record_exception_async(e)
                await span.set_attribute_async("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="error"
                        ).inc()
                    )
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered and operation_type == "dataset_load":
                    duration = time.time() - tracking["start_time"]
                    await anyio.to_thread.run_sync(
                        lambda d=duration: self.registry["dataset_load_time"].labels(
                            dataset_id=dataset_id,
                            format=kwargs.get("format", "unknown")
                        ).observe(d)
                    )
                
                # Record dataset size if provided
                if self.metrics_registered and operation_type == "dataset_load" and "dataset_size" in kwargs:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["dataset_size"].labels(
                            dataset_id=dataset_id
                        ).set(kwargs["dataset_size"])
                    )
    
    @contextmanager
    def track_distributed_operation(self, operation_type, task_id=None, num_workers=None, **kwargs):
        """
        Track a distributed training operation with telemetry.
        
        Args:
            operation_type: Type of operation (worker_coordination, result_aggregation, task_distribution)
            task_id: Optional identifier for the training task
            num_workers: Optional number of workers participating
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Warn if called from async context
        self._warn_if_async_context("track_distributed_operation")
        
        # Generate task_id if not provided
        task_id = task_id or f"task-{uuid.uuid4()}"
        
        # Get operation category
        category = self.operation_categories.get(operation_type, "distributed")
        
        # Start span in the base telemetry
        with self.base_extension.create_span(
            name=f"aiml.{operation_type}",
            attributes={
                "task.id": task_id,
                "num_workers": num_workers,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics and operation_type == "worker_coordination" and num_workers:
                # Start AIMLMetrics tracking for distributed training task
                metrics_context = self.ai_ml_metrics.track_distributed_training_task(
                    task_id=task_id,
                    num_workers=num_workers
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "task_id": task_id,
                "num_workers": num_workers
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="success"
                    ).inc()
                
            except Exception as e:
                # Record error in span
                span.record_exception(e)
                span.set_attribute("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    self.registry["ai_operations_total"].labels(
                        operation_type=operation_type,
                        status="error"
                    ).inc()
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    self.registry["coordination_overhead"].labels(
                        operation=operation_type
                    ).observe(duration)
    
    async def track_distributed_operation_async(self, operation_type, task_id=None, num_workers=None, **kwargs):
        """
        Track a distributed training operation with telemetry asynchronously.
        
        Args:
            operation_type: Type of operation (worker_coordination, result_aggregation, task_distribution)
            task_id: Optional identifier for the training task
            num_workers: Optional number of workers participating
            **kwargs: Additional parameters for the operation
            
        Yields:
            Tracking context with metadata
        """
        # Generate task_id if not provided
        task_id = task_id or f"task-{uuid.uuid4()}"
        
        # Get operation category
        category = self.operation_categories.get(operation_type, "distributed")
        
        # Start span in the base telemetry
        async with self.base_extension.create_span_async(
            name=f"aiml.{operation_type}",
            attributes={
                "task.id": task_id,
                "num_workers": num_workers,
                "operation.type": operation_type,
                "operation.category": category,
                **kwargs
            }
        ) as span:
            
            # Track in AIMLMetrics if available
            metrics_context = None
            
            if self.ai_ml_metrics and operation_type == "worker_coordination" and num_workers:
                # Start AIMLMetrics tracking for distributed training task asynchronously
                metrics_context = await anyio.to_thread.run_sync(
                    lambda: self.ai_ml_metrics.track_distributed_training_task(
                        task_id=task_id,
                        num_workers=num_workers
                    )
                )
            
            # Create tracking context
            tracking = {
                "span": span,
                "metrics_context": metrics_context,
                "start_time": time.time(),
                "operation_type": operation_type,
                "task_id": task_id,
                "num_workers": num_workers
            }
            
            try:
                # Yield the tracking context to the caller
                yield tracking
                
                # Mark operation as successful in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="success"
                        ).inc()
                    )
                
            except Exception as e:
                # Record error in span
                await span.record_exception_async(e)
                await span.set_attribute_async("error", str(e))
                
                # Mark operation as failed in metrics
                if self.metrics_registered:
                    await anyio.to_thread.run_sync(
                        lambda: self.registry["ai_operations_total"].labels(
                            operation_type=operation_type,
                            status="error"
                        ).inc()
                    )
                
                # Re-raise the exception
                raise
            finally:
                # Record duration in appropriate histogram
                if self.metrics_registered:
                    duration = time.time() - tracking["start_time"]
                    await anyio.to_thread.run_sync(
                        lambda d=duration: self.registry["coordination_overhead"].labels(
                            operation=operation_type
                        ).observe(d)
                    )
    
    def record_worker_utilization(self, worker_id, utilization):
        """
        Record worker utilization with telemetry.
        
        Args:
            worker_id: Identifier for the worker
            utilization: Utilization ratio (0.0-1.0)
            
        Returns:
            Result dictionary with recording status
        """
        # Warn if called from async context
        self._warn_if_async_context("record_worker_utilization")
        
        result = {
            "success": False,
            "operation": "record_worker_utilization",
            "timestamp": time.time()
        }
        
        try:
            # Record in AIMLMetrics if available
            if self.ai_ml_metrics:
                self.ai_ml_metrics.record_worker_utilization(
                    worker_id=worker_id,
                    utilization=utilization
                )
            
            # Record in Prometheus metrics
            if self.metrics_registered:
                self.registry["worker_utilization"].labels(
                    worker_id=worker_id
                ).set(utilization)
            
            # Create a span for this event
            with self.base_extension.create_span(
                name="aiml.worker_utilization",
                attributes={
                    "worker.id": worker_id,
                    "utilization": utilization,
                    "operation.type": "worker_utilization",
                    "operation.category": "distributed"
                }
            ):
                # The span is automatically closed when exiting the context
                pass
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Failed to record worker utilization: {str(e)}"
            result["error_type"] = "recording_error"
            logger.error(f"Error recording worker utilization: {e}")
        
        return result
    
    async def record_worker_utilization_async(self, worker_id, utilization):
        """
        Record worker utilization with telemetry asynchronously.
        
        Args:
            worker_id: Identifier for the worker
            utilization: Utilization ratio (0.0-1.0)
            
        Returns:
            Result dictionary with recording status
        """
        result = {
            "success": False,
            "operation": "record_worker_utilization",
            "timestamp": time.time()
        }
        
        try:
            # Record in AIMLMetrics if available
            if self.ai_ml_metrics:
                await anyio.to_thread.run_sync(
                    lambda: self.ai_ml_metrics.record_worker_utilization(
                        worker_id=worker_id,
                        utilization=utilization
                    )
                )
            
            # Record in Prometheus metrics
            if self.metrics_registered:
                await anyio.to_thread.run_sync(
                    lambda: self.registry["worker_utilization"].labels(
                        worker_id=worker_id
                    ).set(utilization)
                )
            
            # Create a span for this event
            async with self.base_extension.create_span_async(
                name="aiml.worker_utilization",
                attributes={
                    "worker.id": worker_id,
                    "utilization": utilization,
                    "operation.type": "worker_utilization",
                    "operation.category": "distributed"
                }
            ):
                # The span is automatically closed when exiting the context
                pass
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = f"Failed to record worker utilization: {str(e)}"
            result["error_type"] = "recording_error"
            logger.error(f"Error recording worker utilization: {e}")
        
        return result
    
    def get_ai_ml_metrics(self):
        """
        Get the current AI/ML metrics data.
        
        Returns:
            Dictionary with AI/ML metrics data
        """
        # Warn if called from async context
        self._warn_if_async_context("get_ai_ml_metrics")
        
        result = {
            "success": False,
            "operation": "get_ai_ml_metrics",
            "timestamp": time.time()
        }
        
        try:
            if not self.ai_ml_metrics:
                result["error"] = "AI/ML metrics not available"
                result["error_type"] = "configuration_error"
                return result
            
            # Get comprehensive report from AIMLMetrics
            metrics_report = self.ai_ml_metrics.get_comprehensive_report()
            
            result["success"] = True
            result["metrics"] = metrics_report
            
        except Exception as e:
            result["error"] = f"Failed to get AI/ML metrics: {str(e)}"
            result["error_type"] = "retrieval_error"
            logger.error(f"Error getting AI/ML metrics: {e}")
        
        return result
    
    async def get_ai_ml_metrics_async(self):
        """
        Get the current AI/ML metrics data asynchronously.
        
        Returns:
            Dictionary with AI/ML metrics data
        """
        result = {
            "success": False,
            "operation": "get_ai_ml_metrics",
            "timestamp": time.time()
        }
        
        try:
            if not self.ai_ml_metrics:
                result["error"] = "AI/ML metrics not available"
                result["error_type"] = "configuration_error"
                return result
            
            # Get comprehensive report from AIMLMetrics asynchronously
            metrics_report = await anyio.to_thread.run_sync(
                lambda: self.ai_ml_metrics.get_comprehensive_report()
            )
            
            result["success"] = True
            result["metrics"] = metrics_report
            
        except Exception as e:
            result["error"] = f"Failed to get AI/ML metrics: {str(e)}"
            result["error_type"] = "retrieval_error"
            logger.error(f"Error getting AI/ML metrics: {e}")
        
        return result
    
    def generate_metrics_report(self, format="markdown"):
        """
        Generate a formatted report of AI/ML metrics.
        
        Args:
            format: Output format ('markdown' or 'text')
            
        Returns:
            Formatted report as a string
        """
        # Warn if called from async context
        self._warn_if_async_context("generate_metrics_report")
        
        result = {
            "success": False,
            "operation": "generate_metrics_report",
            "timestamp": time.time()
        }
        
        try:
            if not self.ai_ml_metrics:
                result["error"] = "AI/ML metrics not available"
                result["error_type"] = "configuration_error"
                return result
            
            # Generate formatted report
            report = self.ai_ml_metrics.generate_formatted_report(format=format)
            
            result["success"] = True
            result["report"] = report
            
        except Exception as e:
            result["error"] = f"Failed to generate metrics report: {str(e)}"
            result["error_type"] = "report_generation_error"
            logger.error(f"Error generating AI/ML metrics report: {e}")
        
        return result
    
    async def generate_metrics_report_async(self, format="markdown"):
        """
        Generate a formatted report of AI/ML metrics asynchronously.
        
        Args:
            format: Output format ('markdown' or 'text')
            
        Returns:
            Formatted report as a string
        """
        result = {
            "success": False,
            "operation": "generate_metrics_report",
            "timestamp": time.time()
        }
        
        try:
            if not self.ai_ml_metrics:
                result["error"] = "AI/ML metrics not available"
                result["error_type"] = "configuration_error"
                return result
            
            # Generate formatted report asynchronously
            report = await anyio.to_thread.run_sync(
                lambda f=format: self.ai_ml_metrics.generate_formatted_report(format=f)
            )
            
            result["success"] = True
            result["report"] = report
            
        except Exception as e:
            result["error"] = f"Failed to generate metrics report: {str(e)}"
            result["error_type"] = "report_generation_error"
            logger.error(f"Error generating AI/ML metrics report: {e}")
        
        return result


def extend_wal_telemetry(base_extension, use_anyio=None):
    """
    Extend WAL telemetry with AI/ML capabilities, selecting the appropriate
    extension class based on context.
    
    Args:
        base_extension: The base WALTelemetryAPIExtension instance
        use_anyio: Whether to use AnyIO version (None for auto-detect)
        
    Returns:
        WALTelemetryAIMLExtension or WALTelemetryAIMLExtensionAnyIO instance
    """
    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available, AI/ML extension not created")
        return None
    
    # If use_anyio is not specified, detect if in async context
    if use_anyio is None:
        try:
            sniffio.current_async_library()
            use_anyio = True
        except sniffio.AsyncLibraryNotFoundError:
            use_anyio = False
    
    # Return appropriate extension based on context and availability
    if use_anyio and ANYIO_AVAILABLE:
        return WALTelemetryAIMLExtensionAnyIO(base_extension)
    else:
        # Import original extension
        from ipfs_kit_py.wal_telemetry_ai_ml import WALTelemetryAIMLExtension
        return WALTelemetryAIMLExtension(base_extension)


def extend_high_level_api_with_aiml_telemetry(api, use_anyio=None):
    """
    Extend the high-level API with AI/ML telemetry capabilities,
    selecting the appropriate extension based on context.
    
    This function adds AI/ML telemetry methods to an existing IPFSSimpleAPI
    instance that already has the base WAL telemetry extension.
    
    Args:
        api: The IPFSSimpleAPI instance to extend
        use_anyio: Whether to use AnyIO version (None for auto-detect)
        
    Returns:
        Extended IPFSSimpleAPI instance
    """
    # Check if we're in an async context if use_anyio is not specified
    if use_anyio is None:
        try:
            sniffio.current_async_library()
            use_anyio = True
        except sniffio.AsyncLibraryNotFoundError:
            use_anyio = False
    
    # Check if WAL telemetry is available
    if not WAL_TELEMETRY_AVAILABLE:
        logger.warning("WAL telemetry not available, skipping AI/ML extension")
        return api
    
    # Check for telemetry extension on the API
    extension_attr = '_wal_telemetry_extension'
    if not hasattr(api, extension_attr):
        # Try AnyIO-specific attribute
        extension_attr = '_wal_telemetry_extension_anyio'
        if not hasattr(api, extension_attr) or getattr(api, extension_attr) is None:
            logger.warning("WAL telemetry extension not initialized, skipping AI/ML extension")
            return api
    
    # Create the AI/ML extension using the helper function
    aiml_extension = extend_wal_telemetry(
        getattr(api, extension_attr),
        use_anyio=use_anyio
    )
    
    if not aiml_extension:
        return api
    
    # Add methods to the API based on whether we're using AnyIO version
    if use_anyio and isinstance(aiml_extension, WALTelemetryAIMLExtensionAnyIO):
        # Add both synchronous and asynchronous methods
        api.wal_aiml_telemetry = aiml_extension.initialize
        api.wal_aiml_telemetry_async = aiml_extension.initialize_async
        
        api.wal_track_model_operation = aiml_extension.track_model_operation
        api.wal_track_model_operation_async = aiml_extension.track_model_operation_async
        
        api.wal_track_inference = aiml_extension.track_inference
        api.wal_track_inference_async = aiml_extension.track_inference_async
        
        api.wal_track_training_epoch = aiml_extension.track_training_epoch
        api.wal_track_training_epoch_async = aiml_extension.track_training_epoch_async
        
        api.wal_record_training_stats = aiml_extension.record_training_stats
        api.wal_record_training_stats_async = aiml_extension.record_training_stats_async
        
        api.wal_track_dataset_operation = aiml_extension.track_dataset_operation
        api.wal_track_dataset_operation_async = aiml_extension.track_dataset_operation_async
        
        api.wal_track_distributed_operation = aiml_extension.track_distributed_operation
        api.wal_track_distributed_operation_async = aiml_extension.track_distributed_operation_async
        
        api.wal_record_worker_utilization = aiml_extension.record_worker_utilization
        api.wal_record_worker_utilization_async = aiml_extension.record_worker_utilization_async
        
        api.wal_get_ai_ml_metrics = aiml_extension.get_ai_ml_metrics
        api.wal_get_ai_ml_metrics_async = aiml_extension.get_ai_ml_metrics_async
        
        api.wal_generate_metrics_report = aiml_extension.generate_metrics_report
        api.wal_generate_metrics_report_async = aiml_extension.generate_metrics_report_async
        
        # Store extension reference
        api._wal_aiml_telemetry_extension_anyio = aiml_extension
    else:
        # Use original implementation
        from ipfs_kit_py.wal_telemetry_ai_ml import extend_high_level_api_with_aiml_telemetry as original_extend
        return original_extend(api)
    
    return api