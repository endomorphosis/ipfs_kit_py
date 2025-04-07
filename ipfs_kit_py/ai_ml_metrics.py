"""
Performance metrics for AI/ML operations with IPFS.

This module extends the core performance metrics system with AI/ML specific metrics tracking
capabilities, focusing on model loading times, inference latency, training throughput,
dataset loading performance, and distributed training coordination overhead.

Key features:
1. Model metrics: loading time, size, initialization overhead
2. Inference metrics: latency, throughput, memory usage
3. Training metrics: epochs, samples/second, convergence rate
4. Dataset metrics: loading time, preprocessing overhead
5. Distributed metrics: coordination overhead, worker utilization

These metrics help optimize AI/ML workloads on IPFS by identifying bottlenecks
and providing insights for tuning the system.
"""

import json
import logging
import os
import statistics
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

from ipfs_kit_py.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class AIMLMetrics:
    """
    Extended metrics tracking for AI/ML operations with IPFS.

    This class provides specialized metrics collection and analysis for AI/ML
    workloads, extending the core performance metrics with ML-specific measures.
    """

    def __init__(
        self,
        base_metrics: Optional[PerformanceMetrics] = None,
        max_history: int = 1000,
        metrics_dir: Optional[str] = None,
        enable_logging: bool = True,
    ):
        """
        Initialize AI/ML metrics tracker.

        Args:
            base_metrics: Optional base PerformanceMetrics instance to extend
            max_history: Maximum number of data points to keep per metric
            metrics_dir: Directory to store metrics logs
            enable_logging: Whether to enable metrics logging
        """
        # Initialize or use provided base metrics
        self.base_metrics = base_metrics or PerformanceMetrics(
            max_history=max_history, metrics_dir=metrics_dir, enable_logging=enable_logging
        )

        self.max_history = max_history

        # Model metrics
        self.model_metrics = {
            "load_times": defaultdict(lambda: deque(maxlen=self.max_history)),
            "sizes": {},  # model_id -> size in bytes
            "frameworks": {},  # model_id -> framework name
            "initialization_times": defaultdict(lambda: deque(maxlen=self.max_history)),
        }

        # Inference metrics
        self.inference_metrics = {
            "latency": defaultdict(lambda: deque(maxlen=self.max_history)),
            "batch_sizes": defaultdict(list),
            "memory_usage": defaultdict(lambda: deque(maxlen=self.max_history)),
            "throughput": defaultdict(lambda: deque(maxlen=self.max_history)),
        }

        # Training metrics
        self.training_metrics = {
            "epoch_times": defaultdict(list),
            "samples_per_second": defaultdict(lambda: deque(maxlen=self.max_history)),
            "loss_values": defaultdict(list),
            "learning_rates": defaultdict(list),
            "gradient_norms": defaultdict(list),
        }

        # Dataset metrics
        self.dataset_metrics = {
            "load_times": defaultdict(lambda: deque(maxlen=self.max_history)),
            "preprocessing_times": defaultdict(lambda: deque(maxlen=self.max_history)),
            "sizes": {},  # dataset_id -> size in bytes
            "formats": {},  # dataset_id -> format name
        }

        # Distributed training metrics
        self.distributed_metrics = {
            "coordination_overhead": deque(maxlen=self.max_history),
            "worker_utilization": defaultdict(lambda: deque(maxlen=self.max_history)),
            "communication_times": deque(maxlen=self.max_history),
            "worker_counts": deque(maxlen=self.max_history),
            "task_distribution_times": deque(maxlen=self.max_history),
            "result_aggregation_times": deque(maxlen=self.max_history),
        }

    @contextmanager
    def track_model_load(
        self, model_id: str, framework: str = "unknown", model_size: Optional[int] = None
    ):
        """
        Track model loading performance.

        Args:
            model_id: Identifier for the model
            framework: ML framework being used
            model_size: Optional size of the model in bytes

        Yields:
            A tracking context for the model loading operation
        """
        start_time = time.time()

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"model_load_{framework}", correlation_id=model_id
        ) as tracking:
            try:
                yield tracking
            finally:
                # Calculate load time and record metrics
                end_time = time.time()
                load_time = end_time - start_time

                # Record in specialized metrics
                self.model_metrics["load_times"][model_id].append(load_time)
                self.model_metrics["frameworks"][model_id] = framework

                if model_size is not None:
                    self.model_metrics["sizes"][model_id] = model_size

                # Log slow model loads
                if load_time > 5.0:
                    logger.info(f"Slow model load: {model_id} ({framework}) took {load_time:.2f}s")

    @contextmanager
    def track_model_initialization(self, model_id: str, device: str = "cpu"):
        """
        Track model initialization performance.

        Args:
            model_id: Identifier for the model
            device: Device being used (cpu, gpu, etc.)

        Yields:
            A tracking context for the model initialization
        """
        start_time = time.time()

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"model_init_{device}", correlation_id=model_id
        ) as tracking:
            try:
                yield tracking
            finally:
                # Calculate initialization time
                end_time = time.time()
                init_time = end_time - start_time

                # Record in specialized metrics
                self.model_metrics["initialization_times"][model_id].append(init_time)

    @contextmanager
    def track_inference(self, model_id: str, batch_size: int = 1, track_memory: bool = True):
        """
        Track model inference performance.

        Args:
            model_id: Identifier for the model
            batch_size: Size of the inference batch
            track_memory: Whether to track memory usage

        Yields:
            A tracking context for the inference operation
        """
        start_time = time.time()

        # Track memory before inference if enabled
        pre_memory = None
        if track_memory:
            try:
                import psutil

                pre_memory = psutil.Process().memory_info().rss
            except (ImportError, AttributeError):
                pass

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"model_inference", correlation_id=model_id
        ) as tracking:
            try:
                yield tracking
            finally:
                # Calculate inference time and metrics
                end_time = time.time()
                inference_time = end_time - start_time

                # Record batch size
                self.inference_metrics["batch_sizes"][model_id].append(batch_size)

                # Record inference latency
                self.inference_metrics["latency"][model_id].append(inference_time)

                # Calculate items per second (throughput)
                throughput = batch_size / inference_time if inference_time > 0 else 0
                self.inference_metrics["throughput"][model_id].append(throughput)

                # Track memory usage if enabled
                if track_memory and pre_memory is not None:
                    try:
                        import psutil

                        post_memory = psutil.Process().memory_info().rss
                        memory_delta = post_memory - pre_memory
                        self.inference_metrics["memory_usage"][model_id].append(memory_delta)
                    except (ImportError, AttributeError):
                        pass

    @contextmanager
    def track_training_epoch(self, model_id: str, epoch: int, num_samples: int):
        """
        Track training epoch performance.

        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            num_samples: Number of samples in the epoch

        Yields:
            A tracking context for the training epoch
        """
        start_time = time.time()

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"training_epoch", correlation_id=model_id
        ) as tracking:
            tracking["epoch"] = epoch
            tracking["num_samples"] = num_samples

            try:
                yield tracking
            finally:
                # Calculate epoch time and metrics
                end_time = time.time()
                epoch_time = end_time - start_time

                # Record epoch time
                while len(self.training_metrics["epoch_times"][model_id]) <= epoch:
                    self.training_metrics["epoch_times"][model_id].append(None)
                self.training_metrics["epoch_times"][model_id][epoch] = epoch_time

                # Calculate and record samples per second
                samples_per_second = num_samples / epoch_time if epoch_time > 0 else 0
                self.training_metrics["samples_per_second"][model_id].append(samples_per_second)

    def record_training_stats(
        self,
        model_id: str,
        epoch: int,
        loss: float,
        learning_rate: Optional[float] = None,
        gradient_norm: Optional[float] = None,
    ):
        """
        Record training statistics.

        Args:
            model_id: Identifier for the model
            epoch: The current epoch number
            loss: The loss value for this epoch
            learning_rate: Optional learning rate
            gradient_norm: Optional gradient norm value
        """
        # Record loss value
        while len(self.training_metrics["loss_values"][model_id]) <= epoch:
            self.training_metrics["loss_values"][model_id].append(None)
        self.training_metrics["loss_values"][model_id][epoch] = loss

        # Record learning rate if provided
        if learning_rate is not None:
            while len(self.training_metrics["learning_rates"][model_id]) <= epoch:
                self.training_metrics["learning_rates"][model_id].append(None)
            self.training_metrics["learning_rates"][model_id][epoch] = learning_rate

        # Record gradient norm if provided
        if gradient_norm is not None:
            while len(self.training_metrics["gradient_norms"][model_id]) <= epoch:
                self.training_metrics["gradient_norms"][model_id].append(None)
            self.training_metrics["gradient_norms"][model_id][epoch] = gradient_norm

    @contextmanager
    def track_dataset_load(
        self, dataset_id: str, format: str = "unknown", dataset_size: Optional[int] = None
    ):
        """
        Track dataset loading performance.

        Args:
            dataset_id: Identifier for the dataset
            format: Format of the dataset
            dataset_size: Optional size of the dataset in bytes

        Yields:
            A tracking context for the dataset loading operation
        """
        start_time = time.time()

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"dataset_load_{format}", correlation_id=dataset_id
        ) as tracking:
            try:
                yield tracking
            finally:
                # Calculate load time and record metrics
                end_time = time.time()
                load_time = end_time - start_time

                # Record in specialized metrics
                self.dataset_metrics["load_times"][dataset_id].append(load_time)
                self.dataset_metrics["formats"][dataset_id] = format

                if dataset_size is not None:
                    self.dataset_metrics["sizes"][dataset_id] = dataset_size

                # Log slow dataset loads
                if load_time > 10.0:
                    logger.info(f"Slow dataset load: {dataset_id} ({format}) took {load_time:.2f}s")

    @contextmanager
    def track_dataset_preprocessing(self, dataset_id: str, operation: str = "preprocess"):
        """
        Track dataset preprocessing performance.

        Args:
            dataset_id: Identifier for the dataset
            operation: The preprocessing operation being performed

        Yields:
            A tracking context for the preprocessing operation
        """
        start_time = time.time()

        # Track in base metrics system
        with self.base_metrics.track_operation(
            f"dataset_{operation}", correlation_id=dataset_id
        ) as tracking:
            try:
                yield tracking
            finally:
                # Calculate preprocessing time
                end_time = time.time()
                preprocess_time = end_time - start_time

                # Record in specialized metrics
                self.dataset_metrics["preprocessing_times"][dataset_id].append(preprocess_time)

    @contextmanager
    def track_distributed_training_task(self, task_id: str, num_workers: int):
        """
        Track distributed training task performance.

        Args:
            task_id: Identifier for the training task
            num_workers: Number of workers participating

        Yields:
            A tracking context for the distributed training task
        """
        start_time = time.time()
        coordination_start = time.time()

        # Track worker count
        self.distributed_metrics["worker_counts"].append(num_workers)

        # Track in base metrics system
        with self.base_metrics.track_operation(
            "distributed_training", correlation_id=task_id
        ) as tracking:
            tracking["num_workers"] = num_workers

            try:
                # End of coordination phase
                coordination_end = time.time()
                coordination_time = coordination_end - coordination_start
                self.distributed_metrics["coordination_overhead"].append(coordination_time)

                # Record task distribution time
                tracking["distribution_start"] = time.time()

                yield tracking

                # Record task distribution time
                if "distribution_start" in tracking:
                    distribution_time = time.time() - tracking["distribution_start"]
                    self.distributed_metrics["task_distribution_times"].append(distribution_time)
            finally:
                # Record aggregation time if provided
                if "aggregation_start" in tracking:
                    aggregation_time = time.time() - tracking["aggregation_start"]
                    self.distributed_metrics["result_aggregation_times"].append(aggregation_time)

    def record_worker_utilization(self, worker_id: str, utilization: float):
        """
        Record worker utilization.

        Args:
            worker_id: Identifier for the worker
            utilization: Utilization ratio (0.0-1.0)
        """
        self.distributed_metrics["worker_utilization"][worker_id].append(utilization)

    def record_communication_time(self, duration: float):
        """
        Record inter-worker communication time.

        Args:
            duration: Communication duration in seconds
        """
        self.distributed_metrics["communication_times"].append(duration)

    def get_model_metrics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for a specific model or all models.

        Args:
            model_id: Optional model identifier to get metrics for

        Returns:
            Dictionary with model metrics
        """
        if model_id is not None:
            # Get metrics for specific model
            load_times = list(self.model_metrics["load_times"].get(model_id, []))

            return {
                "model_id": model_id,
                "framework": self.model_metrics["frameworks"].get(model_id, "unknown"),
                "size_bytes": self.model_metrics["sizes"].get(model_id),
                "load_time_stats": {
                    "count": len(load_times),
                    "mean": statistics.mean(load_times) if load_times else None,
                    "min": min(load_times) if load_times else None,
                    "max": max(load_times) if load_times else None,
                    "median": statistics.median(load_times) if load_times else None,
                },
                "initialization_time_stats": {
                    "count": len(self.model_metrics["initialization_times"].get(model_id, [])),
                    "mean": (
                        statistics.mean(
                            self.model_metrics["initialization_times"].get(model_id, [])
                        )
                        if self.model_metrics["initialization_times"].get(model_id, [])
                        else None
                    ),
                },
            }
        else:
            # Get metrics for all models
            result = {"models": {}}

            for model_id in set(self.model_metrics["load_times"].keys()):
                result["models"][model_id] = self.get_model_metrics(model_id)

            return result

    def get_inference_metrics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get inference metrics for a specific model or all models.

        Args:
            model_id: Optional model identifier to get metrics for

        Returns:
            Dictionary with inference metrics
        """
        if model_id is not None:
            # Get metrics for specific model
            latencies = list(self.inference_metrics["latency"].get(model_id, []))
            throughputs = list(self.inference_metrics["throughput"].get(model_id, []))

            return {
                "model_id": model_id,
                "latency_stats": {
                    "count": len(latencies),
                    "mean": statistics.mean(latencies) if latencies else None,
                    "min": min(latencies) if latencies else None,
                    "max": max(latencies) if latencies else None,
                    "median": statistics.median(latencies) if latencies else None,
                    "p95": self._percentile(latencies, 95) if latencies else None,
                },
                "throughput_stats": {
                    "count": len(throughputs),
                    "mean": statistics.mean(throughputs) if throughputs else None,
                    "max": max(throughputs) if throughputs else None,
                },
                "batch_sizes": self.inference_metrics["batch_sizes"].get(model_id, []),
                "memory_usage": list(self.inference_metrics["memory_usage"].get(model_id, [])),
            }
        else:
            # Get metrics for all models
            result = {"models": {}}

            for model_id in set(self.inference_metrics["latency"].keys()):
                result["models"][model_id] = self.get_inference_metrics(model_id)

            return result

    def get_training_metrics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get training metrics for a specific model or all models.

        Args:
            model_id: Optional model identifier to get metrics for

        Returns:
            Dictionary with training metrics
        """
        if model_id is not None:
            # Get metrics for specific model
            samples_per_second = list(self.training_metrics["samples_per_second"].get(model_id, []))
            epoch_times = [
                t for t in self.training_metrics["epoch_times"].get(model_id, []) if t is not None
            ]
            loss_values = [
                l for l in self.training_metrics["loss_values"].get(model_id, []) if l is not None
            ]
            
            # Initialize an empty accuracy_values list since we don't track it directly
            # This is needed for the visualization function
            accuracy_values = []
            
            # Calculate convergence rate if possible
            convergence_rate = None
            if len(loss_values) >= 2:
                # Simple convergence rate as slope of loss
                convergence_rate = (loss_values[0] - loss_values[-1]) / len(loss_values)

            return {
                "model_id": model_id,
                "num_epochs": len(epoch_times),
                "epoch_time_stats": {
                    "mean": statistics.mean(epoch_times) if epoch_times else None,
                    "min": min(epoch_times) if epoch_times else None,
                    "max": max(epoch_times) if epoch_times else None,
                },
                "samples_per_second_stats": {
                    "mean": statistics.mean(samples_per_second) if samples_per_second else None,
                    "min": min(samples_per_second) if samples_per_second else None,
                    "max": max(samples_per_second) if samples_per_second else None,
                },
                "loss_progress": {
                    "initial": loss_values[0] if loss_values else None,
                    "final": loss_values[-1] if loss_values else None,
                    "convergence_rate": convergence_rate,
                    "loss_curve": loss_values,  # Add the full loss curve
                    "accuracy_curve": accuracy_values, # Always initialize as empty list for now
                },
                "learning_rates": self.training_metrics["learning_rates"].get(model_id, []),
                "gradient_norms": self.training_metrics["gradient_norms"].get(model_id, []),
            }
        else:
            # Get metrics for all models
            result = {"models": {}}

            for model_id in set(self.training_metrics["epoch_times"].keys()):
                result["models"][model_id] = self.get_training_metrics(model_id)

            return result

    def get_dataset_metrics(self, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for a specific dataset or all datasets.

        Args:
            dataset_id: Optional dataset identifier to get metrics for

        Returns:
            Dictionary with dataset metrics
        """
        if dataset_id is not None:
            # Get metrics for specific dataset
            load_times = list(self.dataset_metrics["load_times"].get(dataset_id, []))
            preprocess_times = list(self.dataset_metrics["preprocessing_times"].get(dataset_id, []))

            return {
                "dataset_id": dataset_id,
                "format": self.dataset_metrics["formats"].get(dataset_id, "unknown"),
                "size_bytes": self.dataset_metrics["sizes"].get(dataset_id),
                "load_time_stats": {
                    "count": len(load_times),
                    "mean": statistics.mean(load_times) if load_times else None,
                    "min": min(load_times) if load_times else None,
                    "max": max(load_times) if load_times else None,
                    "median": statistics.median(load_times) if load_times else None,
                },
                "preprocessing_time_stats": {
                    "count": len(preprocess_times),
                    "mean": statistics.mean(preprocess_times) if preprocess_times else None,
                    "total": sum(preprocess_times) if preprocess_times else None,
                },
            }
        else:
            # Get metrics for all datasets
            result = {"datasets": {}}

            for dataset_id in set(self.dataset_metrics["load_times"].keys()):
                result["datasets"][dataset_id] = self.get_dataset_metrics(dataset_id)

            return result

    def get_distributed_metrics(self) -> Dict[str, Any]:
        """
        Get distributed training metrics.

        Returns:
            Dictionary with distributed training metrics
        """
        coordination_times = list(self.distributed_metrics["coordination_overhead"])
        communication_times = list(self.distributed_metrics["communication_times"])
        worker_counts = list(self.distributed_metrics["worker_counts"])

        # Calculate average worker utilization
        avg_worker_utilization = {}
        for worker_id, utils in self.distributed_metrics["worker_utilization"].items():
            if utils:
                avg_worker_utilization[worker_id] = sum(utils) / len(utils)

        return {
            "coordination_overhead_stats": {
                "count": len(coordination_times),
                "mean": statistics.mean(coordination_times) if coordination_times else None,
                "total": sum(coordination_times) if coordination_times else None,
            },
            "communication_time_stats": {
                "count": len(communication_times),
                "mean": statistics.mean(communication_times) if communication_times else None,
                "total": sum(communication_times) if communication_times else None,
            },
            "worker_counts": {
                "min": min(worker_counts) if worker_counts else None,
                "max": max(worker_counts) if worker_counts else None,
                "mean": statistics.mean(worker_counts) if worker_counts else None,
            },
            "average_worker_utilization": avg_worker_utilization,
            "task_distribution_times": {
                "mean": (
                    statistics.mean(self.distributed_metrics["task_distribution_times"])
                    if self.distributed_metrics["task_distribution_times"]
                    else None
                ),
            },
            "result_aggregation_times": {
                "mean": (
                    statistics.mean(self.distributed_metrics["result_aggregation_times"])
                    if self.distributed_metrics["result_aggregation_times"]
                    else None
                ),
            },
        }

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive AI/ML metrics report.

        Returns:
            Dictionary with all AI/ML metrics and analysis
        """
        report = {
            "timestamp": time.time(),
            "models": self.get_model_metrics(),
            "inference": self.get_inference_metrics(),
            "training": self.get_training_metrics(),
            "datasets": self.get_dataset_metrics(),
            "distributed": self.get_distributed_metrics(),
            "analysis": self._generate_analysis(),
            "recommendations": self._generate_recommendations(),
        }

        return report

    def _generate_analysis(self) -> Dict[str, Any]:
        """
        Generate analysis based on collected metrics.

        Returns:
            Dictionary with analysis data
        """
        analysis = {
            "performance_bottlenecks": [],
            "training_efficiency": {},
            "data_pipeline_analysis": {},
        }

        # Identify model loading bottlenecks
        for model_id, load_times in self.model_metrics["load_times"].items():
            if load_times and statistics.mean(load_times) > 5.0:
                analysis["performance_bottlenecks"].append(
                    {
                        "type": "model_loading",
                        "model_id": model_id,
                        "framework": self.model_metrics["frameworks"].get(model_id, "unknown"),
                        "avg_load_time": statistics.mean(load_times),
                        "severity": "high" if statistics.mean(load_times) > 10.0 else "medium",
                    }
                )

        # Analyze inference performance
        for model_id, latencies in self.inference_metrics["latency"].items():
            if latencies:
                # Check if inference is a bottleneck
                if statistics.mean(latencies) > 0.1:  # More than 100ms average latency
                    analysis["performance_bottlenecks"].append(
                        {
                            "type": "inference_latency",
                            "model_id": model_id,
                            "avg_latency": statistics.mean(latencies),
                            "severity": "high" if statistics.mean(latencies) > 0.5 else "medium",
                        }
                    )

        # Analyze training efficiency
        for model_id, samples_per_second in self.training_metrics["samples_per_second"].items():
            if samples_per_second:
                analysis["training_efficiency"][model_id] = {
                    "samples_per_second": statistics.mean(samples_per_second),
                    "efficiency_rating": (
                        "high"
                        if statistics.mean(samples_per_second) > 1000
                        else "medium" if statistics.mean(samples_per_second) > 100 else "low"
                    ),
                }

        # Analyze data pipeline efficiency
        dataset_load_times = {}
        for dataset_id, load_times in self.dataset_metrics["load_times"].items():
            if load_times:
                dataset_load_times[dataset_id] = statistics.mean(load_times)

                # Check if dataset loading is a bottleneck
                if statistics.mean(load_times) > 10.0:
                    analysis["performance_bottlenecks"].append(
                        {
                            "type": "dataset_loading",
                            "dataset_id": dataset_id,
                            "format": self.dataset_metrics["formats"].get(dataset_id, "unknown"),
                            "avg_load_time": statistics.mean(load_times),
                            "severity": "high" if statistics.mean(load_times) > 30.0 else "medium",
                        }
                    )

        # Analyze preprocessing overhead
        dataset_preprocess_times = {}
        for dataset_id, preprocess_times in self.dataset_metrics["preprocessing_times"].items():
            if preprocess_times:
                dataset_preprocess_times[dataset_id] = statistics.mean(preprocess_times)

        analysis["data_pipeline_analysis"] = {
            "loading_times": dataset_load_times,
            "preprocessing_overhead": dataset_preprocess_times,
        }

        # Analyze distributed training efficiency
        if self.distributed_metrics["coordination_overhead"]:
            avg_coordination = statistics.mean(self.distributed_metrics["coordination_overhead"])
            if avg_coordination > 5.0:
                analysis["performance_bottlenecks"].append(
                    {
                        "type": "coordination_overhead",
                        "avg_overhead": avg_coordination,
                        "severity": "high" if avg_coordination > 10.0 else "medium",
                    }
                )

        return analysis

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate recommendations based on metrics analysis.

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []
        analysis = self._generate_analysis()

        # Add recommendations based on bottlenecks
        for bottleneck in analysis["performance_bottlenecks"]:
            if bottleneck["type"] == "model_loading":
                recommendations.append(
                    {
                        "type": "performance",
                        "target": "model_loading",
                        "model_id": bottleneck["model_id"],
                        "severity": bottleneck["severity"],
                        "message": f"Optimize model loading for {bottleneck['model_id']} ({bottleneck['framework']})",
                        "details": f"Average load time of {bottleneck['avg_load_time']:.2f}s is high. Consider model compression, quantization, or caching.",
                    }
                )
            elif bottleneck["type"] == "inference_latency":
                recommendations.append(
                    {
                        "type": "performance",
                        "target": "inference",
                        "model_id": bottleneck["model_id"],
                        "severity": bottleneck["severity"],
                        "message": f"Reduce inference latency for {bottleneck['model_id']}",
                        "details": f"Average inference latency of {bottleneck['avg_latency'] * 1000:.2f}ms is high. Consider batch processing, model optimization, or hardware acceleration.",
                    }
                )
            elif bottleneck["type"] == "dataset_loading":
                recommendations.append(
                    {
                        "type": "performance",
                        "target": "data_pipeline",
                        "dataset_id": bottleneck["dataset_id"],
                        "severity": bottleneck["severity"],
                        "message": f"Optimize dataset loading for {bottleneck['dataset_id']} ({bottleneck['format']})",
                        "details": f"Average load time of {bottleneck['avg_load_time']:.2f}s is high. Consider data caching, preprocessing optimization, or format conversion.",
                    }
                )
            elif bottleneck["type"] == "coordination_overhead":
                recommendations.append(
                    {
                        "type": "performance",
                        "target": "distributed_training",
                        "severity": bottleneck["severity"],
                        "message": "Reduce coordination overhead in distributed training",
                        "details": f"Average coordination overhead of {bottleneck['avg_overhead']:.2f}s is high. Consider optimizing worker communication or task distribution strategy.",
                    }
                )

        # Add recommendations for training efficiency
        for model_id, efficiency in analysis.get("training_efficiency", {}).items():
            if efficiency["efficiency_rating"] == "low":
                recommendations.append(
                    {
                        "type": "efficiency",
                        "target": "training",
                        "model_id": model_id,
                        "severity": "medium",
                        "message": f"Improve training throughput for {model_id}",
                        "details": f"Low processing rate of {efficiency['samples_per_second']:.2f} samples/second. Consider increasing batch size, optimizing data pipeline, or using hardware acceleration.",
                    }
                )

        # Add recommendations for worker utilization
        worker_utils = self.distributed_metrics["worker_utilization"]
        low_utilization_workers = [
            worker_id
            for worker_id, utils in worker_utils.items()
            if utils and sum(utils) / len(utils) < 0.5  # Less than 50% average utilization
        ]

        if low_utilization_workers:
            recommendations.append(
                {
                    "type": "efficiency",
                    "target": "distributed_training",
                    "severity": "medium",
                    "message": "Improve worker utilization in distributed training",
                    "details": f"{len(low_utilization_workers)} workers have low utilization (<50%). Consider task rebalancing or reducing worker count.",
                    "affected_workers": low_utilization_workers,
                }
            )

        return recommendations

    def generate_formatted_report(self, format="markdown"):
        """
        Generate a formatted report of AI/ML metrics.

        Args:
            format: Output format ('markdown' or 'text')

        Returns:
            Formatted report as a string
        """
        report_data = self.get_comprehensive_report()

        if format == "markdown":
            return self._format_markdown_report(report_data)
        else:
            return self._format_text_report(report_data)

    def _format_markdown_report(self, report_data):
        """Format the report data as Markdown."""
        lines = [
            "# AI/ML Performance Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Model Performance",
            "",
        ]

        # Add model loading information
        lines.append("### Model Loading Statistics")
        lines.append("")
        lines.append("| Model | Framework | Size | Avg Load Time (s) | Min | Max |")
        lines.append("|-------|-----------|------|-------------------|-----|-----|")

        for model_id, model_data in report_data["models"].get("models", {}).items():
            load_stats = model_data.get("load_time_stats", {})
            size_str = (
                self._format_size(model_data.get("size_bytes"))
                if model_data.get("size_bytes")
                else "N/A"
            )

            lines.append(
                f"| {model_id} | {model_data.get('framework', 'unknown')} | {size_str} | "
                f"{load_stats.get('mean', 'N/A'):.3f} | {load_stats.get('min', 'N/A'):.3f} | "
                f"{load_stats.get('max', 'N/A'):.3f} |"
            )

        # Add inference information
        lines.append("")
        lines.append("### Inference Performance")
        lines.append("")
        lines.append("| Model | Avg Latency (ms) | P95 Latency (ms) | Throughput (items/sec) |")
        lines.append("|-------|------------------|------------------|------------------------|")

        for model_id, model_data in report_data["inference"].get("models", {}).items():
            latency_stats = model_data.get("latency_stats", {})
            throughput_stats = model_data.get("throughput_stats", {})

            avg_latency_ms = (
                latency_stats.get("mean", 0) * 1000 if latency_stats.get("mean") else "N/A"
            )
            p95_latency_ms = (
                latency_stats.get("p95", 0) * 1000 if latency_stats.get("p95") else "N/A"
            )

            if isinstance(avg_latency_ms, str):
                avg_latency_str = avg_latency_ms
            else:
                avg_latency_str = f"{avg_latency_ms:.2f}"

            if isinstance(p95_latency_ms, str):
                p95_latency_str = p95_latency_ms
            else:
                p95_latency_str = f"{p95_latency_ms:.2f}"

            lines.append(
                f"| {model_id} | {avg_latency_str} | {p95_latency_str} | "
                f"{throughput_stats.get('mean', 'N/A'):.2f} |"
            )

        # Add training information if available
        if report_data["training"].get("models"):
            lines.append("")
            lines.append("### Training Performance")
            lines.append("")
            lines.append("| Model | Epochs | Avg Epoch Time (s) | Samples/sec | Loss Reduction |")
            lines.append("|-------|--------|---------------------|-------------|----------------|")

            for model_id, model_data in report_data["training"].get("models", {}).items():
                epoch_stats = model_data.get("epoch_time_stats", {})
                samples_stats = model_data.get("samples_per_second_stats", {})
                loss_progress = model_data.get("loss_progress", {})

                loss_reduction = "N/A"
                if (
                    loss_progress.get("initial") is not None
                    and loss_progress.get("final") is not None
                ):
                    reduction = loss_progress["initial"] - loss_progress["final"]
                    loss_reduction = f"{reduction:.4f}"

                lines.append(
                    f"| {model_id} | {model_data.get('num_epochs', 'N/A')} | "
                    f"{epoch_stats.get('mean', 'N/A'):.2f} | {samples_stats.get('mean', 'N/A'):.2f} | "
                    f"{loss_reduction} |"
                )

        # Add dataset information
        lines.append("")
        lines.append("## Dataset Performance")
        lines.append("")
        lines.append("| Dataset | Format | Size | Avg Load Time (s) | Avg Preprocess Time (s) |")
        lines.append("|---------|--------|------|-------------------|--------------------------|")

        for dataset_id, dataset_data in report_data["datasets"].get("datasets", {}).items():
            load_stats = dataset_data.get("load_time_stats", {})
            preprocess_stats = dataset_data.get("preprocessing_time_stats", {})
            size_str = (
                self._format_size(dataset_data.get("size_bytes"))
                if dataset_data.get("size_bytes")
                else "N/A"
            )

            lines.append(
                f"| {dataset_id} | {dataset_data.get('format', 'unknown')} | {size_str} | "
                f"{load_stats.get('mean', 'N/A'):.3f} | {preprocess_stats.get('mean', 'N/A'):.3f} |"
            )

        # Add distributed training information if available
        dist_metrics = report_data["distributed"]
        if dist_metrics.get("coordination_overhead_stats", {}).get("count", 0) > 0:
            lines.append("")
            lines.append("## Distributed Training Performance")
            lines.append("")
            lines.append("### Overhead Metrics")
            lines.append("")
            lines.append("| Metric | Average (s) | Total (s) |")
            lines.append("|--------|-------------|-----------|")

            coord_stats = dist_metrics.get("coordination_overhead_stats", {})
            comm_stats = dist_metrics.get("communication_time_stats", {})

            lines.append(
                f"| Coordination Overhead | {coord_stats.get('mean', 'N/A'):.3f} | "
                f"{coord_stats.get('total', 'N/A'):.3f} |"
            )
            lines.append(
                f"| Communication Time | {comm_stats.get('mean', 'N/A'):.3f} | "
                f"{comm_stats.get('total', 'N/A'):.3f} |"
            )

            # Add worker utilization if available
            if dist_metrics.get("average_worker_utilization"):
                lines.append("")
                lines.append("### Worker Utilization")
                lines.append("")
                lines.append("| Worker | Utilization (%) |")
                lines.append("|--------|----------------|")

                for worker_id, util in dist_metrics.get("average_worker_utilization", {}).items():
                    lines.append(f"| {worker_id} | {util * 100:.2f}% |")

        # Add recommendations
        if report_data["recommendations"]:
            lines.append("")
            lines.append("## Recommendations")
            lines.append("")

            for i, rec in enumerate(report_data["recommendations"], 1):
                severity = rec.get("severity", "").upper()
                lines.append(f"### {i}. {rec.get('message')} [{severity}]")
                lines.append("")
                lines.append(rec.get("details", ""))
                lines.append("")

        return "\n".join(lines)

    def _format_text_report(self, report_data):
        """Format the report data as plain text."""
        lines = [
            "AI/ML PERFORMANCE REPORT",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "MODEL PERFORMANCE:",
            "-----------------",
            "",
            "Model Loading Statistics:",
        ]

        # Add model loading information
        model_format = "{:<20} {:<15} {:<12} {:<15} {:<10} {:<10}"
        lines.append(
            model_format.format("Model", "Framework", "Size", "Avg Load (s)", "Min", "Max")
        )
        lines.append("-" * 80)

        for model_id, model_data in report_data["models"].get("models", {}).items():
            load_stats = model_data.get("load_time_stats", {})
            size_str = (
                self._format_size(model_data.get("size_bytes"))
                if model_data.get("size_bytes")
                else "N/A"
            )

            avg_load = load_stats.get("mean", "N/A")
            min_load = load_stats.get("min", "N/A")
            max_load = load_stats.get("max", "N/A")

            # Format as string if not a number
            avg_str = f"{avg_load:.3f}" if isinstance(avg_load, (int, float)) else avg_load
            min_str = f"{min_load:.3f}" if isinstance(min_load, (int, float)) else min_load
            max_str = f"{max_load:.3f}" if isinstance(max_load, (int, float)) else max_load

            lines.append(
                model_format.format(
                    model_id[:20],
                    model_data.get("framework", "unknown")[:15],
                    size_str[:12],
                    avg_str[:15],
                    min_str[:10],
                    max_str[:10],
                )
            )

        # Add inference information
        lines.append("")
        lines.append("Inference Performance:")

        inf_format = "{:<20} {:<18} {:<18} {:<20}"
        lines.append(
            inf_format.format(
                "Model", "Avg Latency (ms)", "P95 Latency (ms)", "Throughput (items/s)"
            )
        )
        lines.append("-" * 80)

        for model_id, model_data in report_data["inference"].get("models", {}).items():
            latency_stats = model_data.get("latency_stats", {})
            throughput_stats = model_data.get("throughput_stats", {})

            avg_latency_ms = (
                latency_stats.get("mean", 0) * 1000 if latency_stats.get("mean") else "N/A"
            )
            p95_latency_ms = (
                latency_stats.get("p95", 0) * 1000 if latency_stats.get("p95") else "N/A"
            )

            if isinstance(avg_latency_ms, str):
                avg_latency_str = avg_latency_ms
            else:
                avg_latency_str = f"{avg_latency_ms:.2f}"

            if isinstance(p95_latency_ms, str):
                p95_latency_str = p95_latency_ms
            else:
                p95_latency_str = f"{p95_latency_ms:.2f}"

            throughput = throughput_stats.get("mean", "N/A")
            throughput_str = (
                f"{throughput:.2f}" if isinstance(throughput, (int, float)) else throughput
            )

            lines.append(
                inf_format.format(
                    model_id[:20], avg_latency_str[:18], p95_latency_str[:18], throughput_str[:20]
                )
            )

        # Add dataset information
        lines.append("")
        lines.append("DATASET PERFORMANCE:")
        lines.append("-------------------")
        lines.append("")

        ds_format = "{:<20} {:<10} {:<12} {:<18} {:<20}"
        lines.append(
            ds_format.format("Dataset", "Format", "Size", "Avg Load (s)", "Avg Preprocess (s)")
        )
        lines.append("-" * 80)

        for dataset_id, dataset_data in report_data["datasets"].get("datasets", {}).items():
            load_stats = dataset_data.get("load_time_stats", {})
            preprocess_stats = dataset_data.get("preprocessing_time_stats", {})
            size_str = (
                self._format_size(dataset_data.get("size_bytes"))
                if dataset_data.get("size_bytes")
                else "N/A"
            )

            avg_load = load_stats.get("mean", "N/A")
            avg_preprocess = preprocess_stats.get("mean", "N/A")

            avg_load_str = f"{avg_load:.3f}" if isinstance(avg_load, (int, float)) else avg_load
            avg_preprocess_str = (
                f"{avg_preprocess:.3f}"
                if isinstance(avg_preprocess, (int, float))
                else avg_preprocess
            )

            lines.append(
                ds_format.format(
                    dataset_id[:20],
                    dataset_data.get("format", "unknown")[:10],
                    size_str[:12],
                    avg_load_str[:18],
                    avg_preprocess_str[:20],
                )
            )

        # Add recommendations
        if report_data["recommendations"]:
            lines.append("")
            lines.append("RECOMMENDATIONS:")
            lines.append("----------------")
            lines.append("")

            for i, rec in enumerate(report_data["recommendations"], 1):
                severity = rec.get("severity", "").upper()
                lines.append(f"{i}. {rec.get('message')} [{severity}]")
                lines.append(f"   {rec.get('details', '')}")
                lines.append("")

        return "\n".join(lines)

    def _percentile(self, data, percentile):
        """Calculate the given percentile of the data."""
        if not data:
            return None

        sorted_data = sorted(data)
        n = len(sorted_data)
        index = (n - 1) * percentile / 100

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            i = int(index)
            fraction = index - i
            return sorted_data[i] * (1 - fraction) + sorted_data[i + 1] * fraction

    def _format_size(self, size_bytes):
        """Format a byte size value to a human-readable string."""
        if size_bytes is None:
            return "N/A"

        size_bytes = float(size_bytes)

        if size_bytes < 1024:
            return f"{size_bytes:.2f} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        elif size_bytes < 1024 * 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.2f} TB"


class AIMLMetricsCollector:
    """
    Collects and analyzes metrics for AI/ML workloads using IPFS.
    
    This class tracks various performance metrics specific to AI/ML workloads,
    such as data loading times, checkpoint storage efficiency, and distributed
    training coordination overhead.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metrics collector.
        
        Args:
            config: Optional configuration dictionary
        """
        self.metrics = {
            "data_loading": {
                "total_bytes": 0,
                "total_time_ms": 0,
                "operations": 0,
                "avg_throughput_mbps": 0.0,
                "histogram": {},
            },
            "training": {
                "checkpoint_save_count": 0,
                "checkpoint_load_count": 0,
                "checkpoint_save_time_ms": 0,
                "checkpoint_load_time_ms": 0,
                "avg_checkpoint_size_mb": 0.0,
            },
            "distribution": {
                "sync_operations": 0,
                "sync_time_ms": 0,
                "network_overhead_bytes": 0,
            }
        }
        
        # Default configuration
        self.config = {
            "histogram_buckets": [1, 10, 100, 1000, 10000],  # ms
            "storage_efficiency_baseline": 0.5,  # 50% compression as baseline
            "enable_tracing": False,
            "metrics_export_path": None,
        }
        
        # Update with provided config
        if config:
            self.config.update(config)
            
        # Initialize histogram buckets
        for bucket in self.config["histogram_buckets"]:
            self.metrics["data_loading"]["histogram"][str(bucket)] = 0
            
        # Start time for the session
        self.start_time = time.time()
        
        logger.info("AIMLMetricsCollector initialized")
    
    def record_data_loading(self, bytes_loaded: int, time_ms: float, 
                           data_type: str = "generic") -> None:
        """
        Record metrics for data loading operation.
        
        Args:
            bytes_loaded: Number of bytes loaded
            time_ms: Time taken in milliseconds
            data_type: Type of data loaded (e.g., "image", "text", "model")
        """
        self.metrics["data_loading"]["total_bytes"] += bytes_loaded
        self.metrics["data_loading"]["total_time_ms"] += time_ms
        self.metrics["data_loading"]["operations"] += 1
        
        # Update throughput calculation
        total_time_sec = self.metrics["data_loading"]["total_time_ms"] / 1000.0
        if total_time_sec > 0:
            throughput = (self.metrics["data_loading"]["total_bytes"] / 
                         total_time_sec / (1024 * 1024))
            self.metrics["data_loading"]["avg_throughput_mbps"] = throughput
        
        # Update histogram
        for bucket in sorted(map(int, self.metrics["data_loading"]["histogram"].keys())):
            if time_ms <= bucket:
                self.metrics["data_loading"]["histogram"][str(bucket)] += 1
                break
    
    def record_checkpoint(self, operation: str, size_bytes: int, 
                         time_ms: float) -> None:
        """
        Record metrics for model checkpoint operations.
        
        Args:
            operation: Either "save" or "load"
            size_bytes: Size of the checkpoint in bytes
            time_ms: Time taken in milliseconds
        """
        if operation == "save":
            self.metrics["training"]["checkpoint_save_count"] += 1
            self.metrics["training"]["checkpoint_save_time_ms"] += time_ms
        elif operation == "load":
            self.metrics["training"]["checkpoint_load_count"] += 1
            self.metrics["training"]["checkpoint_load_time_ms"] += time_ms
        
        # Update average checkpoint size
        total_ops = (self.metrics["training"]["checkpoint_save_count"] + 
                    self.metrics["training"]["checkpoint_load_count"])
        
        if total_ops > 0:
            current_total = (self.metrics["training"]["avg_checkpoint_size_mb"] * 
                           (total_ops - 1))
            new_total = current_total + (size_bytes / (1024 * 1024))
            self.metrics["training"]["avg_checkpoint_size_mb"] = new_total / total_ops
    
    def record_sync_operation(self, bytes_transferred: int, time_ms: float) -> None:
        """
        Record metrics for distributed training synchronization.
        
        Args:
            bytes_transferred: Number of bytes transferred
            time_ms: Time taken in milliseconds
        """
        self.metrics["distribution"]["sync_operations"] += 1
        self.metrics["distribution"]["sync_time_ms"] += time_ms
        self.metrics["distribution"]["network_overhead_bytes"] += bytes_transferred
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get the current metrics.
        
        Returns:
            Dictionary of collected metrics
        """
        # Calculate derived metrics
        metrics = self.metrics.copy()
        
        # Add session duration
        metrics["session_duration_sec"] = time.time() - self.start_time
        
        # Calculate efficiency metrics
        if metrics["data_loading"]["operations"] > 0:
            metrics["data_loading"]["avg_time_per_op_ms"] = (
                metrics["data_loading"]["total_time_ms"] / 
                metrics["data_loading"]["operations"]
            )
        
        if metrics["training"]["checkpoint_save_count"] > 0:
            metrics["training"]["avg_save_time_ms"] = (
                metrics["training"]["checkpoint_save_time_ms"] / 
                metrics["training"]["checkpoint_save_count"]
            )
            
        if metrics["training"]["checkpoint_load_count"] > 0:
            metrics["training"]["avg_load_time_ms"] = (
                metrics["training"]["checkpoint_load_time_ms"] / 
                metrics["training"]["checkpoint_load_count"]
            )
            
        if metrics["distribution"]["sync_operations"] > 0:
            metrics["distribution"]["avg_sync_time_ms"] = (
                metrics["distribution"]["sync_time_ms"] / 
                metrics["distribution"]["sync_operations"]
            )
        
        return metrics
    
    def export_metrics(self, file_path: Optional[str] = None) -> str:
        """
        Export metrics to a JSON file.
        
        Args:
            file_path: Path to save the metrics, defaults to config path
            
        Returns:
            Path to the saved file
        """
        if file_path is None:
            file_path = self.config.get("metrics_export_path")
            
        if file_path is None:
            file_path = f"ipfs_aiml_metrics_{int(time.time())}.json"
            
        metrics = self.get_metrics()
        
        with open(file_path, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        logger.info(f"Exported AI/ML metrics to {file_path}")
        return file_path
    
    def reset_metrics(self) -> None:
        """Reset all metrics to their initial state."""
        # Keep configuration but reset all metrics
        self.__init__(self.config)
        
    def generate_report(self) -> str:
        """
        Generate a human-readable report of the metrics.
        
        Returns:
            String containing the report
        """
        metrics = self.get_metrics()
        
        report = []
        report.append("=" * 60)
        report.append("IPFS AI/ML Metrics Report")
        report.append("=" * 60)
        report.append(f"Session Duration: {metrics['session_duration_sec']:.2f} seconds")
        report.append("")
        
        report.append("Data Loading Metrics:")
        report.append(f"- Total Data Loaded: {metrics['data_loading']['total_bytes']/1024/1024:.2f} MB")
        report.append(f"- Total Loading Time: {metrics['data_loading']['total_time_ms']/1000:.2f} seconds")
        report.append(f"- Number of Operations: {metrics['data_loading']['operations']}")
        report.append(f"- Average Throughput: {metrics['data_loading']['avg_throughput_mbps']:.2f} MB/s")
        if 'avg_time_per_op_ms' in metrics['data_loading']:
            report.append(f"- Average Time per Operation: {metrics['data_loading']['avg_time_per_op_ms']:.2f} ms")
        report.append("")
        
        report.append("Training Metrics:")
        report.append(f"- Checkpoint Save Count: {metrics['training']['checkpoint_save_count']}")
        report.append(f"- Checkpoint Load Count: {metrics['training']['checkpoint_load_count']}")
        report.append(f"- Average Checkpoint Size: {metrics['training']['avg_checkpoint_size_mb']:.2f} MB")
        if 'avg_save_time_ms' in metrics['training']:
            report.append(f"- Average Save Time: {metrics['training']['avg_save_time_ms']:.2f} ms")
        if 'avg_load_time_ms' in metrics['training']:
            report.append(f"- Average Load Time: {metrics['training']['avg_load_time_ms']:.2f} ms")
        report.append("")
        
        report.append("Distribution Metrics:")
        report.append(f"- Sync Operations: {metrics['distribution']['sync_operations']}")
        report.append(f"- Total Sync Time: {metrics['distribution']['sync_time_ms']/1000:.2f} seconds")
        report.append(f"- Network Overhead: {metrics['distribution']['network_overhead_bytes']/1024/1024:.2f} MB")
        if 'avg_sync_time_ms' in metrics['distribution']:
            report.append(f"- Average Sync Time: {metrics['distribution']['avg_sync_time_ms']:.2f} ms")
            
        return "\n".join(report)
