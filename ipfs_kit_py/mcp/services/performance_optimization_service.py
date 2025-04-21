"""
Performance Optimization Service for MCP server.

This module implements the Performance Optimization functionality
as specified in the MCP roadmap Q2 2025 priorities:
- Request load balancing across backends
- Adaptive caching strategies
- Connection pooling and request batching
"""

import logging
import time
import asyncio
import random
import io
import statistics
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class PerformanceOptimizationService:
    """
    Service providing performance optimization for storage operations.

    This service implements the Performance Optimization requirement
    from the MCP roadmap.
    """
    def __init__(
    self,
    backend_registry,
        unified_storage_service,
        cache_size: int = 100,
        performance_window: int = 100,
    ):
        """
        Initialize the performance optimization service.

        Args:
            backend_registry: Registry of storage backends
            unified_storage_service: Unified storage service instance
            cache_size: Size of the content cache
            performance_window: Number of operations to track for performance metrics
        """
        self.backend_registry = backend_registry
        self.storage_service = unified_storage_service
        self.cache_size = cache_size
        self.performance_window = performance_window

        # LRU content cache: CID -> content
        self.content_cache = {}
        self.cache_access_order = deque()

        # Connection pools: backend -> list of connections
        self.connection_pools = {}

        # Batched requests: backend -> list of pending requests
        self.batched_requests = defaultdict(list)
        self.batch_processors = {}

        # Performance metrics: backend -> metric -> list of values
        self.performance_metrics = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=performance_window))
        )

        # Backend health status: backend -> status
        self.backend_health = {}

        # Backend weights for load balancing: backend -> weight
        self.backend_weights = {}

        # Request queue for throttling
        self.request_queue = {}
        self.request_semaphores = {}

        # Cached backend capabilities
        self.backend_capabilities = {}

    async def start(self):
        """Start the performance optimization service."""
        logger.info("Starting performance optimization service")

        # Initialize connection pools
        await self.initialize_connection_pools()

        # Start background tasks
        asyncio.create_task(self._process_batched_requests())
        asyncio.create_task(self._update_performance_metrics())
        asyncio.create_task(self._update_backend_health())
        asyncio.create_task(self._update_backend_weights())

        logger.info("Performance optimization service started")

    async def initialize_connection_pools(self):
        """Initialize connection pools for all backends."""
        backends = self.backend_registry.get_available_backends()

        for backend in backends:
            # Initialize connection pool
            self.connection_pools[backend] = []

            # Initialize request semaphore (limit concurrent requests)
            # Default to 10 concurrent requests per backend
            self.request_semaphores[backend] = asyncio.Semaphore(10)

            # Initialize request queue
            self.request_queue[backend] = asyncio.Queue()

            # Start request processor for this backend
            asyncio.create_task(self._process_request_queue(backend))

            # Start batch processor for this backend
            self.batch_processors[backend] = asyncio.create_task(
                self._process_backend_batch_queue(backend)
            )

            # Initialize backend health
            self.backend_health[backend] = {
                "status": "healthy",
                "errors": 0,
                "latency": 0,
                "success_rate": 1.0,
                "last_check": time.time(),
            }

            # Initialize backend weights
            self.backend_weights[backend] = 1.0

            # Get backend capabilities
            self.backend_capabilities[backend] = await self._get_backend_capabilities(backend)

    async def _get_backend_capabilities(self, backend: str) -> Dict[str, Any]:
        """
        Get capabilities of a backend.

        Args:
            backend: Backend name

        Returns:
            Dictionary of backend capabilities
        """
        capabilities = {
            "supports_batching": False,
            "supports_connection_pooling": False,
            "max_concurrent_requests": 10,
            "batch_size_limit": 10,
            "supports_streaming": False,
            "supports_filters": False,
            "performance_tier": "standard",
        }

        # Check if backend module has capabilities attribute
        backend_module = self.backend_registry.get_backend(backend)
        if backend_module and hasattr(backend_module, "capabilities"):
            # Update capabilities from backend module
            backend_capabilities = backend_module.capabilities
            capabilities.update(backend_capabilities)

        # Special handling for known backend types
        if backend == "ipfs":
            capabilities.update(
                {
                    "supports_batching": False,
                    "supports_connection_pooling": True,
                    "max_concurrent_requests": 20,
                    "supports_streaming": True,
                    "performance_tier": "high",
                }
            )
        elif backend == "s3":
            capabilities.update(
                {
                    "supports_batching": True,
                    "batch_size_limit": 100,
                    "supports_filters": True,
                    "performance_tier": "high",
                }
            )
        elif backend == "filecoin":
            capabilities.update(
                {
                    "supports_batching": False,
                    "max_concurrent_requests": 5,
                    "performance_tier": "archive",
                }
            )

        return capabilities

    async def _process_request_queue(self, backend: str):
        """
        Process the request queue for a backend.

        Args:
            backend: Backend name
        """
        while True:
            try:
                # Get the next request from the queue
                request_info = await self.request_queue[backend].get()

                # Extract request details
                func, args, kwargs, future = request_info

                # Acquire semaphore to limit concurrent requests
                async with self.request_semaphores[backend]:
                    start_time = time.time()
                    try:
                        # Execute the request
                        result = await func(*args, **kwargs)

                        # Set the result in the future
                        if not future.done():
                            future.set_result(result)

                        # Record successful operation
                        self.performance_metrics[backend]["success"].append(1)
                    except Exception as e:
                        logger.error(f"Error processing request for {backend}: {e}")

                        # Set the exception in the future
                        if not future.done():
                            future.set_exception(e)

                        # Record failed operation
                        self.performance_metrics[backend]["success"].append(0)
                    finally:
                        # Record latency
                        latency = time.time() - start_time
                        self.performance_metrics[backend]["latency"].append(latency)

                        # Mark task as done
                        self.request_queue[backend].task_done()
            except Exception as e:
                logger.error(f"Error in request queue processor for {backend}: {e}")
                await asyncio.sleep(1)  # Prevent tight loop in case of repeated errors

    async def _process_batched_requests(self):
        """Process batched requests for all backends."""
        while True:
            try:
                # Sleep for a short time to allow batching
                await asyncio.sleep(0.1)

                # Process batches for each backend
                for backend in list(self.batched_requests.keys()):
                    if self.batched_requests[backend]:
                        # Get capabilities for this backend
                        capabilities = self.backend_capabilities.get(backend, {})

                        # Check if backend supports batching
                        if capabilities.get("supports_batching", False):
                            # Get batch size limit
                            batch_size = min(
                                len(self.batched_requests[backend]),
                                capabilities.get("batch_size_limit", 10),
                            )

                            # Process batch
                            batch = self.batched_requests[backend][:batch_size]
                            self.batched_requests[backend] = self.batched_requests[backend][
                                batch_size:
                            ]

                            # Schedule batch processing
                            asyncio.create_task(self._process_batch(backend, batch))
                        else:
                            # If batching not supported, process individually
                            for request in self.batched_requests[backend]:
                                # Schedule request
                                await self.schedule_request(
                                    backend,
                                    request["func"],
                                    *request["args"],
                                    **request["kwargs"],
                                    future=request["future"],
                                )

                            # Clear batch
                            self.batched_requests[backend] = []
            except Exception as e:
                logger.error(f"Error processing batched requests: {e}")
                await asyncio.sleep(1)  # Prevent tight loop in case of repeated errors

    async def _process_backend_batch_queue(self, backend: str):
        """
        Process the batch queue for a specific backend.

        Args:
            backend: Backend name
        """
        while True:
            try:
                # Check if there are enough requests to batch
                capabilities = self.backend_capabilities.get(backend, {})
                min_batch_size = capabilities.get("min_batch_size", 5)

                if len(self.batched_requests[backend]) >= min_batch_size:
                    # Get batch size limit
                    batch_size = min(
                        len(self.batched_requests[backend]),
                        capabilities.get("batch_size_limit", 10),
                    )

                    # Process batch
                    batch = self.batched_requests[backend][:batch_size]
                    self.batched_requests[backend] = self.batched_requests[backend][batch_size:]

                    # Process batch
                    await self._process_batch(backend, batch)

                # Sleep for a short time
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in batch processor for {backend}: {e}")
                await asyncio.sleep(1)  # Prevent tight loop in case of repeated errors

    async def _process_batch(self, backend: str, batch: List[Dict[str, Any]]):
        """
        Process a batch of requests for a backend.

        Args:
            backend: Backend name
            batch: List of request information
        """
        try:
            # Group by operation type
            operations_by_type = defaultdict(list)
            for request in batch:
                op_type = request.get("op_type", "unknown")
                operations_by_type[op_type].append(request)

            # Process each group of operations
            for op_type, requests in operations_by_type.items():
                if op_type == "get_content":
                    # Batch get_content operations
                    cids = [request["args"][0] for request in requests]

                    # Get backend module
                    backend_module = self.backend_registry.get_backend(backend)

                    # Check if backend supports batch get
                    if hasattr(backend_module, "batch_get_content"):
                        # Perform batch get
                        results = await backend_module.batch_get_content(cids)

                        # Set results in futures
                        for i, request in enumerate(requests):
                            cid = cids[i]
                            if cid in results:
                                request["future"].set_result(results[cid])
                            else:
                                request["future"].set_result(None)
                    else:
                        # If batch get not supported, process individually
                        for request in requests:
                            # Schedule request
                            await self.schedule_request(
                                backend,
                                request["func"],
                                *request["args"],
                                **request["kwargs"],
                                future=request["future"],
                            )
                else:
                    # For other operation types, process individually
                    for request in requests:
                        # Schedule request
                        await self.schedule_request(
                            backend,
                            request["func"],
                            *request["args"],
                            **request["kwargs"],
                            future=request["future"],
                        )
        except Exception as e:
            logger.error(f"Error processing batch for {backend}: {e}")

            # Set exception in all futures
            for request in batch:
                if not request["future"].done():
                    request["future"].set_exception(e)

    async def _update_performance_metrics(self):
        """Update performance metrics for all backends."""
        while True:
            try:
                for backend in self.backend_registry.get_available_backends():
                    # Calculate success rate
                    success_values = list(self.performance_metrics[backend]["success"])
                    if success_values:
                        success_rate = sum(success_values) / len(success_values)
                    else:
                        success_rate = 1.0

                    # Calculate average latency
                    latency_values = list(self.performance_metrics[backend]["latency"])
                    if latency_values:
                        avg_latency = statistics.mean(latency_values)
                    else:
                        avg_latency = 0

                    # Update backend health
                    self.backend_health[backend] = {
                        "status": "healthy" if success_rate > 0.9 else "degraded",
                        "errors": len(success_values) - sum(success_values),
                        "latency": avg_latency,
                        "success_rate": success_rate,
                        "last_check": time.time(),
                    }
            except Exception as e:
                logger.error(f"Error updating performance metrics: {e}")

            # Sleep for 10 seconds before updating again
            await asyncio.sleep(10)

    async def _update_backend_health(self):
        """Update health status for all backends."""
        while True:
            try:
                for backend in self.backend_registry.get_available_backends():
                    # Check if backend is available
                    available = self.backend_registry.is_available(backend)

                    # If backend is not available, mark as unhealthy
                    if not available:
                        self.backend_health[backend] = {
                            "status": "unhealthy",
                            "errors": self.performance_window,
                            "latency": float("inf"),
                            "success_rate": 0.0,
                            "last_check": time.time(),
                        }
                        continue

                    # Perform health check
                    try:
                        # Simple health check - list content with small limit
                        start_time = time.time()
                        await self.storage_service.list_content(backend, limit=1)
                        latency = time.time() - start_time

                        # Record successful health check
                        self.performance_metrics[backend]["health_check"].append(1)
                        self.performance_metrics[backend]["health_check_latency"].append(latency)
                    except Exception as e:
                        logger.warning(f"Health check failed for {backend}: {e}")

                        # Record failed health check
                        self.performance_metrics[backend]["health_check"].append(0)

                        # Update backend health
                        self.backend_health[backend] = {
                            "status": "degraded",
                            "errors": self.backend_health[backend].get("errors", 0) + 1,
                            "latency": self.backend_health[backend].get("latency", 0),
                            "success_rate": self.backend_health[backend].get("success_rate", 0)
                            * 0.9,
                            "last_check": time.time(),
                        }
            except Exception as e:
                logger.error(f"Error updating backend health: {e}")

            # Sleep for 30 seconds before updating again
            await asyncio.sleep(30)

    async def _update_backend_weights(self):
        """Update weights for load balancing."""
        while True:
            try:
                total_weight = 0

                for backend in self.backend_registry.get_available_backends():
                    # Skip unhealthy backends
                    if self.backend_health.get(backend, {}).get("status") == "unhealthy":
                        self.backend_weights[backend] = 0
                        continue

                    # Base weight
                    weight = 1.0

                    # Adjust weight based on health
                    health = self.backend_health.get(backend, {})
                    if health.get("status") == "degraded":
                        weight *= 0.5

                    # Adjust weight based on success rate
                    success_rate = health.get("success_rate", 1.0)
                    weight *= success_rate

                    # Adjust weight based on latency
                    latency = health.get("latency", 0)
                    if latency > 0:
                        # Inverse relationship with latency: faster backends get higher weight
                        weight *= 1.0 / (1.0 + latency)

                    # Adjust weight based on performance tier
                    perf_tier = self.backend_capabilities.get(backend, {}).get(
                        "performance_tier", "standard"
                    )
                    if perf_tier == "high":
                        weight *= 1.5
                    elif perf_tier == "archive":
                        weight *= 0.7

                    # Save weight
                    self.backend_weights[backend] = weight
                    total_weight += weight

                # Normalize weights to sum to 1.0
                if total_weight > 0:
                    for backend in self.backend_weights:
                        self.backend_weights[backend] /= total_weight
            except Exception as e:
                logger.error(f"Error updating backend weights: {e}")

            # Sleep for 60 seconds before updating again
            await asyncio.sleep(60)

    async def schedule_request(
    self,
    backend: str
        func: Callable
        *args,
        future: asyncio.Future = None,
        **kwargs,
    ):
        """
        Schedule a request for a backend with throttling.

        Args:
            backend: Backend name
            func: Function to call
            args: Function arguments
            future: Future to set the result in
            kwargs: Function keyword arguments

        Returns:
            Future for the request result
        """
        if future is None:
            future = asyncio.Future()

        # Create request info
        request_info = (func, args, kwargs, future)

        # Add to request queue
        await self.request_queue[backend].put(request_info)

        return future

    async def batch_request(
        self, backend: str, func: Callable, op_type: str, *args, **kwargs
    ) -> asyncio.Future:
        """
        Add a request to the batch queue.

        Args:
            backend: Backend name
            func: Function to call
            op_type: Operation type for grouping
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Future for the request result
        """
        future = asyncio.Future()

        # Add to batch queue
        self.batched_requests[backend].append(
            {
                "func": func,
                "args": args,
                "kwargs": kwargs,
                "future": future,
                "op_type": op_type,
                "timestamp": time.time(),
            }
        )

        return future

    def _add_to_cache(self, cid: str, content: bytes):
        """
        Add content to the cache.

        Args:
            cid: Content identifier
            content: Content data
        """
        # Check if already in cache
        if cid in self.content_cache:
            # Update access order
            self.cache_access_order.remove(cid)
            self.cache_access_order.append(cid)
            return

        # If cache is full, remove least recently used item
        if len(self.content_cache) >= self.cache_size:
            if self.cache_access_order:
                old_cid = self.cache_access_order.popleft()
                if old_cid in self.content_cache:
                    del self.content_cache[old_cid]

        # Add to cache
        self.content_cache[cid] = content
        self.cache_access_order.append(cid)

    def _get_from_cache(self, cid: str) -> Optional[bytes]:
        """
        Get content from the cache.

        Args:
            cid: Content identifier

        Returns:
            Content data or None if not in cache
        """
        if cid in self.content_cache:
            # Update access order
            self.cache_access_order.remove(cid)
            self.cache_access_order.append(cid)

            return self.content_cache[cid]

        return None

    async def get_content(
        self, cid: str, preferred_backend: Optional[str] = None
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get content from the optimal backend with caching.

        Args:
            cid: Content identifier
            preferred_backend: Optional preferred backend

        Returns:
            Tuple of (content, backend) or (None, None) if not found
        """
        # Check cache first
        cached_content = self._get_from_cache(cid)
        if cached_content is not None:
            return cached_content, "cache"

        # Get locations where content is available
        locations = await self.storage_service.list_locations(cid)
        available_backends = [
            loc["backend"]
            for loc in locations
            if self.backend_registry.is_available(loc["backend"])
        ]

        # If preferred backend is specified and available, use it
        if preferred_backend and preferred_backend in available_backends:
            content = await self.storage_service.get_content(preferred_backend, cid)
            if content:
                # Add to cache
                self._add_to_cache(cid, content)
                return content, preferred_backend

        # If content is not in any backend or no backends are available, return None
        if not available_backends:
            # Try to find content in any available backend as a fallback
            content, backend = await self.storage_service.get_content_from_any(cid)
            if content:
                # Add to cache
                self._add_to_cache(cid, content)
                return content, backend
            return None, None

        # Choose backend based on weights
        valid_backends = [b for b in available_backends if self.backend_weights.get(b, 0) > 0]
        if not valid_backends:
            # If all backends have zero weight, use any available backend
            valid_backends = available_backends

        # Get weights for valid backends
        weights = [self.backend_weights.get(b, 0.1) for b in valid_backends]

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            # If all weights are zero, use equal weights
            weights = [1.0 / len(valid_backends)] * len(valid_backends)
        else:
            weights = [w / total_weight for w in weights]

        # Choose backend based on weights
        backend = random.choices(valid_backends, weights=weights, k=1)[0]

        # Get content from chosen backend
        content = await self.storage_service.get_content(backend, cid)
        if content:
            # Add to cache
            self._add_to_cache(cid, content)
            return content, backend

        # If chosen backend failed, try other backends
        for b in valid_backends:
            if b != backend:
                content = await self.storage_service.get_content(b, cid)
                if content:
                    # Add to cache
                    self._add_to_cache(cid, content)
                    return content, b

        # If all backends failed, return None
        return None, None

    async def store_content(
    self,
    content: Union[bytes, io.BytesIO, str],
        backends: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Store content in optimal backend(s) with replication if specified.

        Args:
            content: Content to store
            backends: Optional list of backends to store in

        Returns:
            Dictionary with storage result
        """
        # If no backends specified, choose based on weights
        if backends is None:
            available_backends = self.backend_registry.get_available_backends()

            # Filter out unhealthy backends
            healthy_backends = [
                b
                for b in available_backends
                if self.backend_health.get(b, {}).get("status") != "unhealthy"
            ]

            if not healthy_backends:
                # If no healthy backends, use any available backend
                healthy_backends = available_backends

            # Get weights for healthy backends
            weights = [self.backend_weights.get(b, 0.1) for b in healthy_backends]

            # Normalize weights
            total_weight = sum(weights)
            if total_weight == 0:
                # If all weights are zero, use equal weights
                weights = [1.0 / len(healthy_backends)] * len(healthy_backends)
            else:
                weights = [w / total_weight for w in weights]

            # Choose top backend based on weights
            backend = random.choices(healthy_backends, weights=weights, k=1)[0]
            backends = [backend]

        # Store content in each backend
        results = {}
        primary_result = None

        for i, backend in enumerate(backends):
            try:
                # For first backend, store content directly
                if i == 0:
                    result = await self.storage_service.store_content(backend, content)
                    if result:
                        primary_result = result
                        results[backend] = result

                        # Get CID for storage in other backends
                        cid = result.get("cid")

                        # Add to cache if it's bytes
                        if isinstance(content, bytes):
                            self._add_to_cache(cid, content)
                else:
                    # For additional backends, replicate from primary
                    if primary_result and "cid" in primary_result:
                        source_backend = list(results.keys())[0]
                        cid = primary_result["cid"]

                        # Get content from cache if available
                        cached_content = self._get_from_cache(cid)
                        if cached_content:
                            # Store from cache
                            result = await self.storage_service.store_content(
                                backend, cached_content, cid
                            )
                        else:
                            # Replicate from source backend
                            success = await self.storage_service.replicate_content(
                                cid, source_backend, backend
                            )
                            if success:
                                result = await self.storage_service.get_content_info(backend, cid)
                            else:
                                result = None

                        if result:
                            results[backend] = result
            except Exception as e:
                logger.error(f"Error storing content in {backend}: {e}")
                results[backend] = {"error": str(e)}

        # Return results
        return {
            "success": len(results) > 0,
            "results": results,
            "primary": primary_result,
            "replicated": [b for b in backends if b in results and b != backends[0]],
            "failed": [b for b in backends if b not in results],
        }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "backends": {
                backend: {
                    "health": self.backend_health.get(backend, {}),
                    "weight": self.backend_weights.get(backend, 0),
                    "capabilities": self.backend_capabilities.get(backend, {}),
                    "metrics": {
                        "latency": list(self.performance_metrics[backend]["latency"]),
                        "success_rate": sum(self.performance_metrics[backend]["success"]),
                        / max(len(self.performance_metrics[backend]["success"]), 1),
                    },
                }
                for backend in self.backend_registry.get_available_backends()
            },
            "cache": {
                "size": len(self.content_cache),
                "capacity": self.cache_size,
                "hit_ratio": (,
                    sum(self.performance_metrics["cache"]["hit"])
                    / max(len(self.performance_metrics["cache"]["hit"]), 1)
                    if "cache" in self.performance_metrics
                    else 0
                ),
            },
            "batching": {
                "pending_requests": {
                    backend: len(self.batched_requests[backend])
                    for backend in self.batched_requests
                }
            },
            "request_queue": {
                backend: self.request_queue[backend].qsize() for backend in self.request_queue
            },
        }

        return stats
