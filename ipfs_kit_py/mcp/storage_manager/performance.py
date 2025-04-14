"""
Performance optimization module for the Unified Storage Manager.

This module provides advanced performance features such as:
- Load balancing across backends
- Adaptive caching strategies
- Connection pooling and request batching
"""

import logging
import time
import threading
import random
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from .storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Tracker for backend performance metrics."""
    def __init__(selfself):
        """Initialize performance metrics tracker."""
        self.metrics = {}
        self.lock = threading.RLock()

        # Initialize default metrics for each operation type
        self.operation_types = ["store", "retrieve", "list", "delete"]

    def record_operation(self
        self
        backend_type: Union[StorageBackendType, str]
        operation: str
        duration: float
        success: bool
        data_size: int = 0,
    ):
        """
        Record a backend operation and its performance.

        Args:
            backend_type: Backend type
            operation: Operation type (store, retrieve, etc.)
            duration: Operation duration in seconds
            success: Whether operation was successful
            data_size: Size of data in bytes (for store/retrieve)
        """
        # Convert backend_type to string if necessary
        if isinstance(backend_type, StorageBackendType):
            backend_key = backend_type.value
        else:
            backend_key = str(backend_type)

        with self.lock:
            # Initialize backend metrics if not exists
            if backend_key not in self.metrics:
                self.metrics[backend_key] = {
                    op: {
                        "count": 0,
                        "success_count": 0,
                        "total_duration": 0,
                        "total_size": 0,
                        "failures": 0,
                        "last_operation": 0,
                        "avg_duration": 0,
                        "success_rate": 1.0,  # Start optimistic
                    }
                    for op in self.operation_types
                }

            # Update metrics for this operation
            if operation in self.metrics[backend_key]:
                metrics = self.metrics[backend_key][operation]
                metrics["count"] += 1
                metrics["total_duration"] += duration
                metrics["last_operation"] = time.time()

                if success:
                    metrics["success_count"] += 1
                    if data_size > 0:
                        metrics["total_size"] += data_size
                else:
                    metrics["failures"] += 1

                # Update derived metrics
                metrics["avg_duration"] = metrics["total_duration"] / metrics["count"]
                metrics["success_rate"] = metrics["success_count"] / metrics["count"]

    def get_backend_metrics(selfself, backend_type: Union[StorageBackendType, str]) -> Dict[str, Any]:
        """
        Get metrics for a specific backend.

        Args:
            backend_type: Backend type

        Returns:
            Dictionary with backend metrics
        """
        # Convert backend_type to string if necessary
        if isinstance(backend_type, StorageBackendType):
            backend_key = backend_type.value
        else:
            backend_key = str(backend_type)

        with self.lock:
            return self.metrics.get(backend_key, {}).copy()

    def get_all_metrics(selfself) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all backends.

        Returns:
            Dictionary with all metrics
        """
        with self.lock:
            return self.metrics.copy()

    def get_best_backend_for_operation(self
        self
        available_backends: List[StorageBackendType]
        operation: str
        min_success_rate: float = 0.7,
    ) -> Optional[StorageBackendType]:
        """
        Get the best backend for a specific operation based on performance metrics.

        Args:
            available_backends: List of available backends
            operation: Operation type
            min_success_rate: Minimum acceptable success rate

        Returns:
            Best backend or None if no suitable backend
        """
        if not available_backends:
            return None

        with self.lock:
            candidates = []

            for backend in available_backends:
                backend_key = backend.value

                # Skip backends with insufficient data
                if backend_key not in self.metrics:
                    # New backends start with neutral score
                    candidates.append((backend, 0.5))
                    continue

                if operation not in self.metrics[backend_key]:
                    # New operation types start with neutral score
                    candidates.append((backend, 0.5))
                    continue

                metrics = self.metrics[backend_key][operation]

                # Skip backends with low success rates
                if metrics["success_rate"] < min_success_rate:
                    continue

                # Score based on success rate and speed
                if metrics["count"] > 0:
                    speed_factor = 1.0
                    if metrics["avg_duration"] > 0:
                        # Normalize speed - lower is better
                        speed_factor = min(1.0, 1.0 / metrics["avg_duration"])

                    # Combined score (70% success rate, 30% speed)
                    score = (metrics["success_rate"] * 0.7) + (speed_factor * 0.3)
                    candidates.append((backend, score))
                else:
                    # No data yet, neutral score
                    candidates.append((backend, 0.5))

            if not candidates:
                # If no suitable backends, return random one from available
                return random.choice(available_backends)

            # Sort by score (highest first) and return best backend
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]


class RequestBatcher:
    """Batches similar requests for performance optimization."""
    def __init___v2(selfself, max_batch_size: int = 10, max_wait_time: float = 0.1):
        """
        Initialize request batcher.

        Args:
            max_batch_size: Maximum number of requests in a batch
            max_wait_time: Maximum time to wait for batch to fill (seconds)
        """
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.batches = {}
        self.lock = threading.RLock()

    def add_request(self
        self
        batch_key: str
        request_data: Any
        callback: Callable[[List[Any], Any], None],
    ) -> None:
        """
        Add a request to a batch.

        Args:
            batch_key: Key to identify the batch
            request_data: Request data
            callback: Function to call when batch is processed
        """
        with self.lock:
            # Initialize batch if not exists
            if batch_key not in self.batches:
                self.batches[batch_key] = {
                    "requests": [],
                    "callbacks": [],
                    "created_at": time.time(),
                    "timer": None,
                }

                # Set timer to process batch after max_wait_time
                timer = threading.Timer(self.max_wait_time, self._process_batch, args=[batch_key])
                timer.daemon = True
                timer.start()
                self.batches[batch_key]["timer"] = timer

            # Add request to batch
            self.batches[batch_key]["requests"].append(request_data)
            self.batches[batch_key]["callbacks"].append(callback)

            # Process batch if full
            if len(self.batches[batch_key]["requests"]) >= self.max_batch_size:
                # Cancel timer
                if self.batches[batch_key]["timer"]:
                    self.batches[batch_key]["timer"].cancel()

                # Process batch
                self._process_batch(batch_key)

    def _process_batch(selfself, batch_key: str) -> None:
        """
        Process a batch of requests.

        Args:
            batch_key: Key of the batch to process
        """
        with self.lock:
            if batch_key not in self.batches:
                return

            batch = self.batches.pop(batch_key)

        # Process batch outside of lock
        try:
            # Implement batch processing logic here
            # This is placeholder logic - actual implementation depends on the specific backend
            for i, request in enumerate(batch["requests"]):
                try:
                    # Call callback with batch and request index
                    batch["callbacks"][i](batch["requests"], i)
                except Exception as e:
                    logger.error(f"Error in batch callback: {e}")
        except Exception as e:
            logger.error(f"Error processing batch {batch_key}: {e}")


class ConnectionPool:
    """
    Manages connections to backend services for reuse.

    This reduces the overhead of creating new connections for each request.
    """
    # DISABLED REDEFINITION
        """
        Initialize connection pool.

        Args:
            max_connections: Maximum number of connections per backend
            connection_ttl: Time-to-live for idle connections (seconds)
        """
        self.max_connections = max_connections
        self.connection_ttl = connection_ttl
        self.pools = {}
        self.lock = threading.RLock()

        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_connections)
        self.cleanup_thread.daemon = True
        self.cleanup_thread.start()

    def get_connection(self
        self
        backend_type: Union[StorageBackendType, str]
        conn_params: Dict[str, Any] = None,
    ) -> Any:
        """
        Get a connection from the pool or create a new one.

        Args:
            backend_type: Backend type
            conn_params: Connection parameters

        Returns:
            Connection object
        """
        # Convert backend_type to string if necessary
        if isinstance(backend_type, StorageBackendType):
            backend_key = backend_type.value
        else:
            backend_key = str(backend_type)

        conn_params = conn_params or {}

        with self.lock:
            # Initialize pool for this backend if not exists
            if backend_key not in self.pools:
                self.pools[backend_key] = {
                    "available": [],
                    "in_use": set(),
                    "params": conn_params,
                }

            pool = self.pools[backend_key]

            # Check if an available connection exists
            if pool["available"]:
                conn_info = pool["available"].pop()
                conn, last_used, _ = conn_info

                # Update last used time
                conn_info = (conn, time.time(), conn_params)
                pool["in_use"].add(conn_info)

                return conn

            # If pool is full, we cannot create new connections
            if len(pool["in_use"]) >= self.max_connections:
                raise Exception(f"Connection pool for {backend_key} is full")

            # Create new connection
            conn = self._create_connection(backend_type, conn_params)
            conn_info = (conn, time.time(), conn_params)
            pool["in_use"].add(conn_info)

            return conn

    def release_connection(selfself, backend_type: Union[StorageBackendType, str], conn: Any) -> None:
        """
        Release a connection back to the pool.

        Args:
            backend_type: Backend type
            conn: Connection object
        """
        # Convert backend_type to string if necessary
        if isinstance(backend_type, StorageBackendType):
            backend_key = backend_type.value
        else:
            backend_key = str(backend_type)

        with self.lock:
            if backend_key not in self.pools:
                return

            pool = self.pools[backend_key]

            # Find the connection in the in_use set
            conn_info = None
            for info in pool["in_use"]:
                if info[0] == conn:
                    conn_info = info
                    break

            if conn_info:
                pool["in_use"].remove(conn_info)

                # Update last used time and add to available pool
                new_conn_info = (conn, time.time(), conn_info[2])
                pool["available"].append(new_conn_info)

    def _create_connection(self
    def __init__(self, backend_type: Union[StorageBackendType, str], conn_params: Dict[str, Any]
    ) -> Any:
        """
        Create a new connection to a backend.

        Args:
            backend_type: Backend type
            conn_params: Connection parameters

        Returns:
            New connection object
        """
        # This is a placeholder for actual connection creation logic
        # The implementation depends on the specific backend

        if isinstance(backend_type, StorageBackendType):
            backend_str = backend_type.value
        else:
            backend_str = str(backend_type)

        logger.info(f"Creating new connection to {backend_str} backend")

        # Placeholder - return a dummy connection object
        return {"type": backend_str, "params": conn_params, "created_at": time.time()}

    def _cleanup_connections(selfself) -> None:
        """Periodically clean up idle connections."""
        while True:
            try:
                # Sleep first to allow initial connections to be established
                time.sleep(60)

                with self.lock:
                    now = time.time()

                    for backend_key, pool in list(self.pools.items()):
                        # Find expired connections
                        expired = []
                        for i, (conn, last_used, params) in enumerate(pool["available"]):
                            if now - last_used > self.connection_ttl:
                                expired.append(i)

                        # Remove expired connections (in reverse order)
                        for i in sorted(expired, reverse=True):
                            conn, _, _ = pool["available"].pop(i)
                            self._close_connection(conn)

                        logger.debug(
                            f"Cleaned up {len(expired)} idle connections for {backend_key}"
                        )

            except Exception as e:
                logger.error(f"Error in connection pool cleanup: {e}")

    def _close_connection(selfself, conn: Any) -> None:
        """
        Close a connection.

        Args:
            conn: Connection object
        """
        # This is a placeholder for actual connection closing logic
        # The implementation depends on the specific backend

        logger.debug(f"Closing connection: {conn}")

        # If connection has a close method, call it
        if hasattr(conn, "close") and callable(conn.close):
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")


class LoadBalancer:
    """
    Load balancer for distributing operations across backends.

    This helps optimize performance by selecting the best backend for each operation
    based on various factors like availability, performance, and cost.
    """
    # DISABLED REDEFINITION
        """
        Initialize load balancer.

        Args:
            performance_metrics: Performance metrics tracker
        """
        self.metrics = performance_metrics
        self.health_checks = {}
        self.lock = threading.RLock()

        # Weights for different factors in backend selection
        self.weights = {"performance": 0.4, "health": 0.3, "cost": 0.2, "load": 0.1}

    def select_backend(self
        self
        available_backends: List[StorageBackendType]
        operation: str
        content_metadata: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Optional[StorageBackendType]:
        """
        Select the best backend for an operation.

        Args:
            available_backends: List of available backends
            operation: Operation type (store, retrieve, etc.)
            content_metadata: Optional metadata about the content
            requirements: Optional specific requirements for the operation

        Returns:
            Selected backend or None if no suitable backend
        """
        if not available_backends:
            return None

        # If only one backend is available, use it
        if len(available_backends) == 1:
            return available_backends[0]

        # If specific requirements are provided, filter backends
        if requirements:
            filtered_backends = self._filter_backends_by_requirements(
                available_backends, requirements
            )
            if filtered_backends:
                available_backends = filtered_backends

        # Calculate scores for each backend
        scores = {}
        for backend in available_backends:
            scores[backend] = self._calculate_backend_score(backend, operation, content_metadata)

        if not scores:
            # If no scores, return a random backend
            return random.choice(available_backends)

        # Select backend with highest score
        return max(scores.items(), key=lambda x: x[1])[0]

    def _filter_backends_by_requirements(self
    def __init__(self, backends: List[StorageBackendType], requirements: Dict[str, Any]
    ) -> List[StorageBackendType]:
        """
        Filter backends based on specific requirements.

        Args:
            backends: List of backends to filter
            requirements: Requirements dictionary

        Returns:
            Filtered list of backends
        """
        filtered = []

        for backend in backends:
            # Check if this backend meets all requirements
            meets_requirements = True

            # Check for required backend type
            if "backend_type" in requirements:
                if isinstance(requirements["backend_type"], list):
                    if backend not in requirements["backend_type"]:
                        meets_requirements = False
                elif backend != requirements["backend_type"]:
                    meets_requirements = False

            # Check for minimum success rate
            if "min_success_rate" in requirements:
                metrics = self.metrics.get_backend_metrics(backend)
                for op, op_metrics in metrics.items():
                    if op_metrics["success_rate"] < requirements["min_success_rate"]:
                        meets_requirements = False
                        break

            # Check for maximum cost
            if "max_cost" in requirements and hasattr(backend, "get_cost_estimate"):
                # This would require backends to implement a cost estimation method
                cost = backend.get_cost_estimate(requirements.get("size", 0))
                if cost > requirements["max_cost"]:
                    meets_requirements = False

            # Add to filtered list if it meets all requirements
            if meets_requirements:
                filtered.append(backend)

        return filtered

    def _calculate_backend_score(self
        self
        backend: StorageBackendType
        operation: str
        content_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate a score for a backend for a specific operation.

        Args:
            backend: Backend to score
            operation: Operation type
            content_metadata: Optional content metadata

        Returns:
            Score between 0 and 1
        """
        # Get backend metrics
        metrics = self.metrics.get_backend_metrics(backend)

        # Calculate performance score
        performance_score = 0.5  # Default neutral score
        if operation in metrics:
            op_metrics = metrics[operation]
            if op_metrics["count"] > 0:
                # Consider both success rate and speed
                success_rate = op_metrics["success_rate"]

                # Calculate speed score - lower duration is better
                speed_score = 0.5
                if op_metrics["avg_duration"] > 0:
                    # Normalize speed (1/duration) to 0-1 range
                    speed_score = min(1.0, 1.0 / op_metrics["avg_duration"])

                # Combined performance score (70% success, 30% speed)
                performance_score = (success_rate * 0.7) + (speed_score * 0.3)

        # Calculate health score
        health_score = self._get_health_score(backend)

        # Calculate cost score (higher is better - lower cost)
        cost_score = self._get_cost_score(backend, operation, content_metadata)

        # Calculate load score (higher is better - lower load)
        load_score = self._get_load_score(backend)

        # Calculate final weighted score
        final_score = (
            (performance_score * self.weights["performance"])
            + (health_score * self.weights["health"])
            + (cost_score * self.weights["cost"])
            + (load_score * self.weights["load"])
        )

        return final_score

    def _get_health_score(selfself, backend: StorageBackendType) -> float:
        """
        Get health score for a backend.

        Args:
            backend: Backend to check

        Returns:
            Health score between 0 and 1
        """
        # Check if we have health check information
        with self.lock:
            if backend.value not in self.health_checks:
                # No health info, assume healthy
                return 0.9

            health_info = self.health_checks[backend.value]

            # Calculate health score based on success rate of health checks
            success_rate = health_info.get("success_rate", 0.9)
            last_check = health_info.get("last_check", 0)
            last_success = health_info.get("last_success", 0)

            # Reduce score if last health check failed
            if last_check > last_success:
                success_rate *= 0.8

            return success_rate

    def _get_cost_score(self
        self
        backend: StorageBackendType
        operation: str
        content_metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Get cost score for a backend operation.

        Args:
            backend: Backend to check
            operation: Operation type
            content_metadata: Optional content metadata

        Returns:
            Cost score between 0 and 1 (higher is better - lower cost)
        """
        # This is a simplified cost model
        # Real implementation would query backends for actual cost estimates

        # Default cost scores for different backends and operations
        cost_factors = {
            StorageBackendType.IPFS.value: {
                "store": 0.7,
                "retrieve": 0.9,
                "list": 0.95,
                "delete": 0.95,
            },
            StorageBackendType.S3.value: {
                "store": 0.6,
                "retrieve": 0.7,
                "list": 0.8,
                "delete": 0.9,
            },
            StorageBackendType.STORACHA.value: {
                "store": 0.8,
                "retrieve": 0.7,
                "list": 0.85,
                "delete": 0.9,
            },
            StorageBackendType.FILECOIN.value: {
                "store": 0.5,  # More expensive for initial storage
                "retrieve": 0.6,
                "list": 0.9,
                "delete": 0.95,
            },
        }

        # Get base cost factor for this backend and operation
        base_factor = cost_factors.get(backend.value, {}).get(operation, 0.7)

        # Adjust for content size if available
        if content_metadata and "size" in content_metadata:
            size = content_metadata["size"]

            # Adjust cost factor based on size
            if size > 100 * 1024 * 1024:  # >100MB
                # Large files may be cheaper on some backends
                if backend == StorageBackendType.S3:
                    base_factor *= 1.2  # Better for large files
                elif backend == StorageBackendType.IPFS:
                    base_factor *= 0.8  # Worse for large files
            elif size < 1024 * 1024:  # <1MB
                # Small files may be cheaper on some backends
                if backend == StorageBackendType.IPFS:
                    base_factor *= 1.2  # Better for small files
                elif backend == StorageBackendType.FILECOIN:
                    base_factor *= 0.8  # Worse for small files

        # Ensure score is in 0-1 range
        return max(0.1, min(1.0, base_factor))

    def _get_load_score(selfself, backend: StorageBackendType) -> float:
        """
        Get load score for a backend.

        Args:
            backend: Backend to check

        Returns:
            Load score between 0 and 1 (higher is better - lower load)
        """
        # This is a simplified load model
        # Real implementation would track actual load on backends

        # Get metrics for this backend
        metrics = self.metrics.get_backend_metrics(backend)

        # Default score if no metrics
        if not metrics:
            return 0.8

        # Calculate total operations in last minute
        now = time.time()
        recent_ops = 0

        for op_type, op_metrics in metrics.items():
            if op_metrics["last_operation"] > now - 60:
                recent_ops += op_metrics["count"]

        # Calculate load score - more operations means higher load
        if recent_ops == 0:
            return 1.0  # No recent operations
        elif recent_ops < 10:
            return 0.9  # Low load
        elif recent_ops < 50:
            return 0.7  # Medium load
        elif recent_ops < 100:
            return 0.5  # High load
        else:
            return 0.3  # Very high load

    def update_health_check(selfself, backend: Union[StorageBackendType, str], success: bool) -> None:
        """
        Update health check information for a backend.

        Args:
            backend: Backend type
            success: Whether health check was successful
        """
        # Convert backend to string if necessary
        if isinstance(backend, StorageBackendType):
            backend_key = backend.value
        else:
            backend_key = str(backend)

        with self.lock:
            # Initialize health check info if not exists
            if backend_key not in self.health_checks:
                self.health_checks[backend_key] = {
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 1.0,
                    "last_check": 0,
                    "last_success": 0,
                }

            health_info = self.health_checks[backend_key]

            # Update health check info
            now = time.time()
            health_info["last_check"] = now

            if success:
                health_info["success_count"] += 1
                health_info["last_success"] = now
            else:
                health_info["failure_count"] += 1

            # Update success rate
            total_checks = health_info["success_count"] + health_info["failure_count"]
            if total_checks > 0:
                health_info["success_rate"] = health_info["success_count"] / total_checks


class PerformanceOptimizer:
    """
    Main performance optimization manager for the Unified Storage Manager.

    This class coordinates the performance optimization features:
    - Load balancing
    - Request batching
    - Connection pooling
    - Performance monitoring
    """
    # DISABLED REDEFINITION
        """Initialize performance optimizer."""
        # Create performance metrics tracker
        self.metrics = PerformanceMetrics()

        # Create load balancer
        self.load_balancer = LoadBalancer(self.metrics)

        # Create request batcher
        self.request_batcher = RequestBatcher()

        # Create connection pool
        self.connection_pool = ConnectionPool()

        # Cache settings
        self.cache_enabled = True
        self.cache_ttl = 300  # seconds
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_lock = threading.RLock()

        # Start background health check thread
        self.health_check_thread = threading.Thread(target=self._background_health_checks)
        self.health_check_thread.daemon = True
        self.health_check_thread.start()

    def select_backend_for_operation(self
        self
        available_backends: List[StorageBackendType]
        operation: str
        content_metadata: Optional[Dict[str, Any]] = None,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Optional[StorageBackendType]:
        """
        Select the best backend for an operation.

        Args:
            available_backends: List of available backends
            operation: Operation type
            content_metadata: Optional content metadata
            requirements: Optional specific requirements

        Returns:
            Selected backend or None if no suitable backend
        """
        return self.load_balancer.select_backend(
            available_backends, operation, content_metadata, requirements
        )

    def record_operation_v2(self
        self
        backend: Union[StorageBackendType, str]
        operation: str
        duration: float
        success: bool
        data_size: int = 0,
    ) -> None:
        """
        Record a backend operation for performance tracking.

        Args:
            backend: Backend type
            operation: Operation type
            duration: Operation duration in seconds
            success: Whether operation was successful
            data_size: Size of data in bytes
        """
        self.metrics.record_operation(backend, operation, duration, success, data_size)

    def batch_request(self
        self
        batch_key: str
        request_data: Any
        callback: Callable[[List[Any], Any], None],
    ) -> None:
        """
        Add a request to be processed in a batch.

        Args:
            batch_key: Key to identify the batch
            request_data: Request data
            callback: Function to call when batch is processed
        """
        self.request_batcher.add_request(batch_key, request_data, callback)

    def get_connection_v2(self
        self
        backend: Union[StorageBackendType, str]
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Get a connection from the connection pool.

        Args:
            backend: Backend type
            params: Connection parameters

        Returns:
            Connection object
        """
        return self.connection_pool.get_connection(backend, params)

    def release_connection_v2(self
    def __init__(self, backend: Union[StorageBackendType, str], connection: Any
    ) -> None:
        """
        Release a connection back to the pool.

        Args:
            backend: Backend type
            connection: Connection object
        """
        self.connection_pool.release_connection(backend, connection)

    def cache_get(selfself, key: str) -> Optional[Tuple[Any, float]]:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Tuple of (value, timestamp) or None if not in cache
        """
        if not self.cache_enabled:
            return None

        with self.cache_lock:
            if key in self.cache:
                value, timestamp = self.cache[key]

                # Check if value is expired
                if time.time() - timestamp > self.cache_ttl:
                    del self.cache[key]
                    self.cache_misses += 1
                    return None

                self.cache_hits += 1
                return value, timestamp

            self.cache_misses += 1
            return None

    def cache_set(selfself, key: str, value: Any) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        if not self.cache_enabled:
            return

        with self.cache_lock:
            self.cache[key] = (value, time.time())

    def cache_invalidate(selfself, key: str) -> None:
        """
        Invalidate a cache entry.

        Args:
            key: Cache key to invalidate
        """
        with self.cache_lock:
            if key in self.cache:
                del self.cache[key]

    def cache_clear(selfself) -> None:
        """Clear the entire cache."""
        with self.cache_lock:
            self.cache.clear()

    def get_cache_stats(selfself) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self.cache_lock:
            return {
                "enabled": self.cache_enabled,
                "ttl": self.cache_ttl,
                "size": len(self.cache),
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_ratio": (,
                    self.cache_hits / (self.cache_hits + self.cache_misses)
                    if (self.cache_hits + self.cache_misses) > 0
                    else 0
                ),
            }

    def get_optimization_stats(selfself) -> Dict[str, Any]:
        """
        Get performance optimization statistics.

        Returns:
            Dictionary with optimization statistics
        """
        return {
            "backends": self.metrics.get_all_metrics(),
            "cache": self.get_cache_stats(),
            "connection_pool": {
                "max_connections": self.connection_pool.max_connections,
                "connection_ttl": self.connection_pool.connection_ttl,
            },
            "request_batcher": {
                "max_batch_size": self.request_batcher.max_batch_size,
                "max_wait_time": self.request_batcher.max_wait_time,
            },
        }

    def _background_health_checks(selfself) -> None:
        """Perform periodic health checks on backends."""
        # This is a placeholder for actual health check implementation
        # In a real system, this would ping backends to check their status

        # Sleep interval between health checks (seconds)
        health_check_interval = 60

        while True:
            # Sleep first to allow initialization
            time.sleep(health_check_interval)

            try:
                # This would be replaced with actual health checks
                # For now, just log that health checks are running
                logger.debug("Running background health checks")

                # In a real implementation, we would:
                # 1. Get all available backends
                # 2. Check each backend's health
                # 3. Update health status in load balancer
            except Exception as e:
                logger.error(f"Error in background health checks: {e}")
