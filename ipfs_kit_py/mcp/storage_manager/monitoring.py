"""
Monitoring system for storage backends.

This module implements the monitoring system for tracking health,
performance, and reliability of storage backends.
"""

import logging
import time
import threading
import json
import os
import statistics
from typing import Dict, Any, Optional, Union
from enum import Enum
from .storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class BackendStatus(Enum):
    """Status of a storage backend."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class OperationType(Enum):
    """Types of operations for performance tracking."""
    STORE = "store"
    RETRIEVE = "retrieve"
    DELETE = "delete"
    LIST = "list"
    METADATA = "metadata"


class MonitoringSystem:
    """
    Monitoring system for storage backends.

    Tracks health, performance, and reliability metrics for
    all storage backends in the unified storage system.
    """
    def __init__(self, storage_manager, options: Optional[Dict[str, Any]] = None):
        """
        Initialize the monitoring system.

        Args:
            storage_manager: UnifiedStorageManager instance
            options: Configuration options
        """
        self.storage_manager = storage_manager
        self.options = options or {}

        # Health status for each backend
        self.backend_status = {}

        # Performance metrics
        self.operation_times = {}
        self.error_counts = {}
        self.success_rates = {}

        # Capacity metrics
        self.capacity_metrics = {}

        # Last check timestamps
        self.last_health_check = {}
        self.last_metrics_update = 0

        # Monitoring thread
        self.monitor_thread = None
        self.running = False
        self.monitor_lock = threading.Lock()

        # Performance measurements history (for trends)
        self.performance_history = {}

        # Configuration
        self.health_check_interval = self.options.get("health_check_interval", 300)  # seconds
        self.metrics_update_interval = self.options.get("metrics_update_interval", 3600)  # seconds
        self.history_retention_days = self.options.get("history_retention_days", 30)

        # Test data settings
        self.test_data_size = self.options.get("test_data_size", 10 * 1024)  # 10KB
        self.test_data = b"0" * self.test_data_size
        self.test_path = "monitoring/test_data"

        # Initialize monitoring data
        self._initialize_metrics()

        # Load state from disk if available
        self._load_state()

    def _initialize_metrics(self):
        """Initialize metrics for all backends."""
        # Get all backends from storage manager
        for backend_type, backend in self.storage_manager.backends.items():
            # Initialize health status
            self.backend_status[backend_type.value] = BackendStatus.UNKNOWN.value

            # Initialize operation times
            self.operation_times[backend_type.value] = {
                op_type.value: {
                    "count": 0,
                    "total_time": 0,
                    "min_time": 0,
                    "max_time": 0,
                    "avg_time": 0,
                    "last_time": 0,
                }
                for op_type in OperationType
            }

            # Initialize error counts
            self.error_counts[backend_type.value] = {op_type.value: 0 for op_type in OperationType}

            # Initialize success rates
            self.success_rates[backend_type.value] = {
                op_type.value: 1.0 for op_type in OperationType  # Start optimistic
            }

            # Initialize capacity metrics
            self.capacity_metrics[backend_type.value] = {
                "total": 0,
                "used": 0,
                "available": 0,
                "usage_percent": 0,
            }

            # Initialize performance history
            self.performance_history[backend_type.value] = {
                op_type.value: [] for op_type in OperationType
            }

            # Initialize last check timestamps
            self.last_health_check[backend_type.value] = 0

    def _load_state(self):
        """Load monitoring state from disk."""
        state_path = self.options.get("state_path")

        if state_path and os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)

                # Load metrics if available
                if "backend_status" in state:
                    self.backend_status = state["backend_status"]

                if "operation_times" in state:
                    self.operation_times = state["operation_times"]

                if "error_counts" in state:
                    self.error_counts = state["error_counts"]

                if "success_rates" in state:
                    self.success_rates = state["success_rates"]

                if "capacity_metrics" in state:
                    self.capacity_metrics = state["capacity_metrics"]

                if "performance_history" in state:
                    self.performance_history = state["performance_history"]

                # Load timestamps
                if "last_health_check" in state:
                    self.last_health_check = state["last_health_check"]

                if "last_metrics_update" in state:
                    self.last_metrics_update = state["last_metrics_update"]

                logger.info("Loaded monitoring state")
            except Exception as e:
                logger.error(f"Failed to load monitoring state: {e}")

    def _save_state(self):
        """Save monitoring state to disk."""
        state_path = self.options.get("state_path")

        if state_path:
            try:
                state = {
                    "backend_status": self.backend_status,
                    "operation_times": self.operation_times,
                    "error_counts": self.error_counts,
                    "success_rates": self.success_rates,
                    "capacity_metrics": self.capacity_metrics,
                    "performance_history": self.performance_history,
                    "last_health_check": self.last_health_check,
                    "last_metrics_update": self.last_metrics_update,
                    "updated_at": time.time(),
                }

                with open(state_path, "w") as f:
                    json.dump(state, f, indent=2)

                logger.info("Saved monitoring state")
            except Exception as e:
                logger.error(f"Failed to save monitoring state: {e}")

    def record_operation(
        self,
        backend_type: Union[StorageBackendType, str],
        operation: Union[OperationType, str],
        duration: float,
        success: bool,
        data_size: Optional[int] = None,
    ):
        """
        Record an operation for metrics tracking.

        Args:
            backend_type: Backend type
            operation: Operation type
            duration: Duration in seconds
            success: Whether operation was successful
            data_size: Size of data in bytes (optional)
        """
        # Convert to string for dictionary keys
        if isinstance(backend_type, StorageBackendType):
            backend_type = backend_type.value

        if isinstance(operation, OperationType):
            operation = operation.value

        # Ensure backend and operation exist in metrics
        if backend_type not in self.operation_times:
            self._initialize_backend_metrics(backend_type)

        if operation not in self.operation_times[backend_type]:
            self._initialize_operation_metrics(backend_type, operation)

        # Update operation times
        op_times = self.operation_times[backend_type][operation]
        op_times["count"] += 1
        op_times["total_time"] += duration
        op_times["last_time"] = duration

        if op_times["count"] == 1 or duration < op_times["min_time"]:
            op_times["min_time"] = duration

        if duration > op_times["max_time"]:
            op_times["max_time"] = duration

        op_times["avg_time"] = op_times["total_time"] / op_times["count"]

        # Update error counts
        if not success:
            self.error_counts[backend_type][operation] += 1

        # Update success rates
        total_ops = op_times["count"]
        errors = self.error_counts[backend_type][operation]
        self.success_rates[backend_type][operation] = (
            (total_ops - errors) / total_ops if total_ops > 0 else 1.0
        )

        # Add to performance history
        timestamp = time.time()
        self.performance_history[backend_type][operation].append(
            {
                "timestamp": timestamp,
                "duration": duration,
                "success": success,
                "size": data_size,
            }
        )

        # Prune old history entries
        self._prune_history(backend_type, operation)

    def _initialize_backend_metrics(self, backend_type: str):
        """Initialize metrics for a new backend."""
        self.backend_status[backend_type] = BackendStatus.UNKNOWN.value

        self.operation_times[backend_type] = {}
        self.error_counts[backend_type] = {}
        self.success_rates[backend_type] = {}
        self.performance_history[backend_type] = {}
        self.capacity_metrics[backend_type] = {
            "total": 0,
            "used": 0,
            "available": 0,
            "usage_percent": 0,
        }

        self.last_health_check[backend_type] = 0

        for op_type in OperationType:
            self._initialize_operation_metrics(backend_type, op_type.value)

    def _initialize_operation_metrics(self, backend_type: str, operation: str):
        """Initialize metrics for a new operation type."""
        self.operation_times[backend_type][operation] = {
            "count": 0,
            "total_time": 0,
            "min_time": 0,
            "max_time": 0,
            "avg_time": 0,
            "last_time": 0,
        }

        self.error_counts[backend_type][operation] = 0
        self.success_rates[backend_type][operation] = 1.0
        self.performance_history[backend_type][operation] = []

    def _prune_history(self, backend_type: str, operation: str):
        """Prune old history entries."""
        if self.history_retention_days <= 0:
            return

        # Calculate cutoff timestamp
        cutoff = time.time() - (self.history_retention_days * 24 * 60 * 60)

        # Filter out old entries
        self.performance_history[backend_type][operation] = [
            entry
            for entry in self.performance_history[backend_type][operation]
            if entry["timestamp"] > cutoff
        ]

    def check_backend_health(self, backend_type: Union[StorageBackendType, str]) -> Dict[str, Any]:
        """
        Check health of a specific backend.

        Args:
            backend_type: Backend to check

        Returns:
            Dictionary with health status and metrics
        """
        # Convert to enum if needed
        if isinstance(backend_type, str):
            try:
                backend_type = StorageBackendType.from_string(backend_type)
            except ValueError:
                return {
                    "status": BackendStatus.UNKNOWN.value,
                    "error": f"Invalid backend type: {backend_type}",
                }

        # Get backend instance
        if backend_type not in self.storage_manager.backends:
            return {
                "status": BackendStatus.UNKNOWN.value,
                "error": f"Backend not available: {backend_type.value}",
            }

        backend = self.storage_manager.backends[backend_type]

        # Record start time
        start_time = time.time()

        # Test store operation
        store_success = False
        retrieve_success = False
        delete_success = False
        stored_id = None

        try:
            # Generate test identifier
            test_id = f"test_{int(time.time())}"
            test_container = None

            # Test based on backend type
            if backend_type == StorageBackendType.IPFS:
                # IPFS - store a small test file
                store_result = backend.store(
                    data=self.test_data, path=f"{self.test_path}/{test_id}"
                )

                store_success = store_result.get("success", False)
                stored_id = store_result.get("identifier") if store_success else None

                # Test retrieve if store succeeded
                if store_success and stored_id:
                    retrieve_result = backend.retrieve(stored_id)
                    retrieve_success = retrieve_result.get("success", False)

                    # Test delete
                    delete_result = backend.delete(stored_id)
                    delete_success = delete_result.get("success", False)

            elif backend_type == StorageBackendType.S3:
                # S3 - use default bucket
                if hasattr(backend, "default_bucket"):
                    test_container = backend.default_bucket

                store_result = backend.store(
                    data=self.test_data,
                    container=test_container,
                    path=f"{self.test_path}/{test_id}",
                )

                store_success = store_result.get("success", False)
                stored_id = store_result.get("identifier") if store_success else None

                # Test retrieve if store succeeded
                if store_success and stored_id:
                    retrieve_result = backend.retrieve(
                        identifier=stored_id, container=test_container
                    )
                    retrieve_success = retrieve_result.get("success", False)

                    # Test delete
                    delete_result = backend.delete(identifier=stored_id, container=test_container)
                    delete_success = delete_result.get("success", False)

            else:
                # Generic health check for other backends
                # Try a store operation
                store_result = backend.store(
                    data=self.test_data,
                    container=test_container,
                    path=f"{self.test_path}/{test_id}",
                )

                store_success = store_result.get("success", False)
                stored_id = store_result.get("identifier") if store_success else None

                # Test retrieve if store succeeded
                if store_success and stored_id:
                    retrieve_result = backend.retrieve(
                        identifier=stored_id, container=test_container
                    )
                    retrieve_success = retrieve_result.get("success", False)

                    # Test delete
                    delete_result = backend.delete(identifier=stored_id, container=test_container)
                    delete_success = delete_result.get("success", False)

        except Exception as e:
            logger.error(f"Error during health check for {backend_type.value}: {e}")
            return {
                "status": BackendStatus.UNHEALTHY.value,
                "error": str(e),
                "duration": time.time() - start_time,
            }

        # Calculate total duration
        duration = time.time() - start_time

        # Determine health status
        if store_success and retrieve_success and delete_success:
            status = BackendStatus.HEALTHY.value
        elif store_success or retrieve_success:
            status = BackendStatus.DEGRADED.value
        else:
            status = BackendStatus.UNHEALTHY.value

        # Update status in tracking
        self.backend_status[backend_type.value] = status
        self.last_health_check[backend_type.value] = time.time()

        # Record operations in metrics
        if store_success or not store_success:  # Always record
            self.record_operation(
                backend_type=backend_type,
                operation=OperationType.STORE,
                duration=duration / 3,  # Approximate time for store
                success=store_success,
                data_size=self.test_data_size,
            )

        if retrieve_success or (store_success and not retrieve_success):
            self.record_operation(
                backend_type=backend_type,
                operation=OperationType.RETRIEVE,
                duration=duration / 3,  # Approximate time for retrieve
                success=retrieve_success,
                data_size=self.test_data_size,
            )

        if delete_success or (retrieve_success and not delete_success):
            self.record_operation(
                backend_type=backend_type,
                operation=OperationType.DELETE,
                duration=duration / 3,  # Approximate time for delete
                success=delete_success,
            )

        # Save updated state
        self._save_state()

        return {
            "status": status,
            "backend": backend_type.value,
            "store_success": store_success,
            "retrieve_success": retrieve_success,
            "delete_success": delete_success,
            "duration": duration,
            "timestamp": time.time(),
        }

    def check_all_backends_health(self) -> Dict[str, Any]:
        """
        Check health of all backends.

        Returns:
            Dictionary with health status for all backends
        """
        results = {}
        overall_status = BackendStatus.HEALTHY.value

        for backend_type in self.storage_manager.backends:
            result = self.check_backend_health(backend_type)
            results[backend_type.value] = result

            # Update overall status
            if result["status"] == BackendStatus.UNHEALTHY.value:
                overall_status = BackendStatus.UNHEALTHY.value
            elif (
                result["status"] == BackendStatus.DEGRADED.value
                and overall_status != BackendStatus.UNHEALTHY.value
            ):
                overall_status = BackendStatus.DEGRADED.value

        return {
            "overall_status": overall_status,
            "backends": results,
            "timestamp": time.time(),
        }

    def update_capacity_metrics(self) -> Dict[str, Any]:
        """
        Update capacity metrics for all backends.

        Returns:
            Dictionary with capacity metrics for all backends
        """
        results = {}

        for backend_type, backend in self.storage_manager.backends.items():
            # Only update for backends that support capacity metrics
            if hasattr(backend, "get_capacity_metrics") and callable(
                getattr(backend, "get_capacity_metrics", None)
            ):
                try:
                    metrics = backend.get_capacity_metrics()
                    self.capacity_metrics[backend_type.value] = metrics
                    results[backend_type.value] = metrics
                except Exception as e:
                    logger.error(f"Error getting capacity metrics for {backend_type.value}: {e}")
                    results[backend_type.value] = {
                        "error": str(e),
                        "timestamp": time.time(),
                    }
            else:
                # For backends without native capacity support, estimate based on content size
                total_size = 0
                content_count = 0

                for (
                    content_id,
                    content_ref,
                ) in self.storage_manager.content_registry.items():
                    if content_ref.has_location(backend_type):
                        size = content_ref.metadata.get("size", 0)
                        total_size += size
                        content_count += 1

                metrics = {
                    "used": total_size,
                    "content_count": content_count,
                    "avg_content_size": total_size / content_count if content_count > 0 else 0,
                    "estimated": True,
                }

                self.capacity_metrics[backend_type.value] = metrics
                results[backend_type.value] = metrics

        # Update last metrics update timestamp
        self.last_metrics_update = time.time()

        # Save updated state
        self._save_state()

        return {"capacity_metrics": results, "timestamp": time.time()}

    def get_performance_metrics(
        self,
        backend_type: Optional[Union[StorageBackendType, str]] = None,
        operation: Optional[Union[OperationType, str]] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for backends.

        Args:
            backend_type: Optional backend to get metrics for (if None, get all)
            operation: Optional operation to get metrics for (if None, get all)

        Returns:
            Dictionary with performance metrics
        """
        results = {}

        # Convert to string if needed
        if isinstance(backend_type, StorageBackendType):
            backend_type = backend_type.value

        if isinstance(operation, OperationType):
            operation = operation.value

        # Filter by backend type if specified
        backend_types = [backend_type] if backend_type else list(self.operation_times.keys())

        for b_type in backend_types:
            # Skip if backend doesn't exist in metrics
            if b_type not in self.operation_times:
                continue

            # Filter by operation if specified
            op_types = [operation] if operation else list(self.operation_times[b_type].keys())
            backend_results = {}

            for op_type in op_types:
                # Skip if operation doesn't exist for this backend
                if op_type not in self.operation_times[b_type]:
                    continue

                # Get operation times
                op_times = self.operation_times[b_type][op_type]

                # Calculate standard deviation from history if available
                std_dev = 0
                last_day_avg = 0

                if (
                    b_type in self.performance_history
                    and op_type in self.performance_history[b_type]
                ):
                    history = self.performance_history[b_type][op_type]

                    if history:
                        # Calculate standard deviation
                        if len(history) > 1:
                            durations = [entry["duration"] for entry in history]
                            std_dev = statistics.stdev(durations) if len(durations) > 1 else 0

                        # Calculate average for last day
                        day_ago = time.time() - (24 * 60 * 60)
                        recent_entries = [
                            entry for entry in history if entry["timestamp"] > day_ago
                        ]

                        if recent_entries:
                            recent_durations = [entry["duration"] for entry in recent_entries]
                            last_day_avg = sum(recent_durations) / len(recent_durations)

                # Add metrics for this operation
                success_rate = self.success_rates.get(b_type, {}).get(op_type, 1.0)
                error_count = self.error_counts.get(b_type, {}).get(op_type, 0)

                backend_results[op_type] = {
                    "count": op_times["count"],
                    "avg_time": op_times["avg_time"],
                    "min_time": op_times["min_time"],
                    "max_time": op_times["max_time"],
                    "last_time": op_times["last_time"],
                    "std_dev": std_dev,
                    "last_day_avg": last_day_avg,
                    "success_rate": success_rate,
                    "error_count": error_count,
                }

            # Add results for this backend
            results[b_type] = backend_results

        return {"performance_metrics": results, "timestamp": time.time()}

    def get_backend_status(
        self, backend_type: Optional[Union[StorageBackendType, str]] = None
    ) -> Dict[str, Any]:
        """
        Get status of backends.

        Args:
            backend_type: Optional backend to get status for (if None, get all)

        Returns:
            Dictionary with backend status
        """
        # Convert to string if needed
        if isinstance(backend_type, StorageBackendType):
            backend_type = backend_type.value

        # Get status for specific backend
        if backend_type:
            if backend_type not in self.backend_status:
                return {
                    "status": BackendStatus.UNKNOWN.value,
                    "backend": backend_type,
                    "timestamp": time.time(),
                }

            return {
                "status": self.backend_status[backend_type],
                "backend": backend_type,
                "last_check": self.last_health_check.get(backend_type, 0),
                "timestamp": time.time(),
            }

        # Get status for all backends
        results = {}
        overall_status = BackendStatus.HEALTHY.value

        for b_type, status in self.backend_status.items():
            results[b_type] = {
                "status": status,
                "last_check": self.last_health_check.get(b_type, 0),
            }

            # Update overall status
            if status == BackendStatus.UNHEALTHY.value:
                overall_status = BackendStatus.UNHEALTHY.value
            elif (
                status == BackendStatus.DEGRADED.value
                and overall_status != BackendStatus.UNHEALTHY.value
            ):
                overall_status = BackendStatus.DEGRADED.value
            elif (
                status == BackendStatus.UNKNOWN.value
                and overall_status == BackendStatus.HEALTHY.value
            ):
                overall_status = BackendStatus.UNKNOWN.value

        return {
            "overall_status": overall_status,
            "backends": results,
            "timestamp": time.time(),
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all monitoring metrics.

        Returns:
            Dictionary with all metrics
        """
        return {
            "backend_status": self.get_backend_status(),
            "performance_metrics": self.get_performance_metrics(),
            "capacity_metrics": {
                "backends": self.capacity_metrics,
                "last_update": self.last_metrics_update,
            },
            "timestamp": time.time(),
        }

    def start_monitoring(self) -> bool:
        """
        Start the background monitoring thread.

        Returns:
            True if monitoring was started
        """
        with self.monitor_lock:
            if self.running:
                return False

            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, name="BackendMonitor", daemon=True
            )
            self.monitor_thread.start()
            logger.info("Started monitoring thread")

            return True

    def stop_monitoring(self, wait: bool = True) -> bool:
        """
        Stop the background monitoring thread.

        Args:
            wait: Whether to wait for thread to stop

        Returns:
            True if monitoring was stopped
        """
        with self.monitor_lock:
            if not self.running:
                return False

            self.running = False

            if wait and self.monitor_thread:
                self.monitor_thread.join(timeout=5)

            logger.info("Stopped monitoring thread")
            return True

    def _monitor_loop(self):
        """Main monitoring loop for checking backend health."""
        logger.info("Monitoring thread started")

        try:
            while self.running:
                try:
                    # Check backend health
                    current_time = time.time()

                    for backend_type in list(self.storage_manager.backends.keys()):
                        b_type = backend_type.value
                        last_check = self.last_health_check.get(b_type, 0)

                        # Check if it's time for a health check
                        if current_time - last_check >= self.health_check_interval:
                            try:
                                self.check_backend_health(backend_type)
                            except Exception as e:
                                logger.error(f"Error checking health for {b_type}: {e}")

                    # Update capacity metrics
                    if current_time - self.last_metrics_update >= self.metrics_update_interval:
                        try:
                            self.update_capacity_metrics()
                        except Exception as e:
                            logger.error(f"Error updating capacity metrics: {e}")

                    # Sleep for a bit
                    time.sleep(10)

                except Exception as loop_error:
                    logger.error(f"Error in monitoring loop: {loop_error}")
                    time.sleep(30)  # Sleep longer on error

        except Exception as e:
            logger.exception(f"Fatal error in monitoring thread: {e}")
        finally:
            logger.info("Monitoring thread stopped")

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive monitoring report.

        Returns:
            Dictionary with full monitoring report
        """
        # Get all metrics
        metrics = self.get_all_metrics()

        # Add additional analysis and recommendations
        recommendations = []
        warnings = []

        # Analyze backend status
        for backend, status in metrics["backend_status"]["backends"].items():
            if status["status"] == BackendStatus.UNHEALTHY.value:
                warnings.append(f"Backend {backend} is unhealthy and may be unavailable")
                recommendations.append(
                    f"Check connectivity to {backend} backend and verify credentials"
                )
            elif status["status"] == BackendStatus.DEGRADED.value:
                warnings.append(f"Backend {backend} is in a degraded state")
                recommendations.append(f"Monitor {backend} backend performance closely")

        # Analyze performance metrics
        for backend, ops in metrics["performance_metrics"]["performance_metrics"].items():
            for op_type, metrics in ops.items():
                # Check for low success rates
                if metrics["success_rate"] < 0.95:
                    warnings.append(
                        f"Backend {backend} has low success rate ({metrics['success_rate']:.2%}) for {op_type} operations"
                    )
                    recommendations.append(
                        f"Investigate failures for {op_type} operations on {backend} backend"
                    )

                # Check for unusually high latency
                avg_time = metrics["avg_time"]
                if avg_time > 5.0:  # More than 5 seconds
                    warnings.append(
                        f"Backend {backend} has high latency ({avg_time:.2f}s) for {op_type} operations"
                    )
                    recommendations.append(
                        f"Consider optimizing {op_type} operations on {backend} backend"
                    )

        # Analyze capacity metrics
        for backend, capacity in metrics["capacity_metrics"]["backends"].items():
            if "usage_percent" in capacity and capacity["usage_percent"] > 80:
                warnings.append(
                    f"Backend {backend} is nearing capacity ({capacity['usage_percent']}% used)"
                )
                recommendations.append(
                    f"Consider adding more storage to {backend} backend or migrating content"
                )

        # Generate overall assessment
        overall_status = metrics["backend_status"]["overall_status"]
        assessment = "Healthy"

        if overall_status == BackendStatus.DEGRADED.value:
            assessment = "Degraded"
        elif overall_status == BackendStatus.UNHEALTHY.value:
            assessment = "Unhealthy"
        elif overall_status == BackendStatus.UNKNOWN.value:
            assessment = "Unknown"

        # Add recommendations based on assessment
        if assessment != "Healthy":
            recommendations.append(
                f"Perform a full system check to identify issues causing {assessment.lower()} status"
            )

        # Add report metadata
        report = {
            "metrics": metrics,
            "assessment": assessment,
            "warnings": warnings,
            "recommendations": recommendations,
            "generated_at": time.time(),
        }

        return report
