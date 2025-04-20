"""
Routing Performance Optimization

This module provides performance optimizations for the routing system, including:
- Decision caching
- Content signature calculation
- Batch processing
- Memory optimization
- Connection pooling
"""

import time
import hashlib
import logging
import functools
import asyncio
from typing import Dict, Any, List, Tuple, Optional, Union, Callable
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field

# Configure logging
logger = logging.getLogger(__name__)


class RoutingDecisionCache:
    """
    Cache for routing decisions to avoid recomputation for similar content.
    
    This class implements an LRU (Least Recently Used) cache with time-based expiration
    for efficient storage and retrieval of routing decisions based on content characteristics.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,  # 1 hour default TTL
        similarity_threshold: float = 0.9  # Threshold for considering content similar
    ):
        """
        Initialize the routing decision cache.
        
        Args:
            max_size: Maximum number of entries in the cache
            ttl_seconds: Time-to-live for cache entries in seconds
            similarity_threshold: Threshold for considering content similar (0.0-1.0)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        
        # Main cache storage - OrderedDict to maintain insertion order for LRU
        self._cache: OrderedDict[str, Tuple[Dict[str, Any], float]] = OrderedDict()
        
        # Similarity mapping - maps content signatures to decision keys
        self._signature_mapping: Dict[str, List[str]] = defaultdict(list)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"Initialized routing decision cache with max_size={max_size}, ttl={ttl_seconds}s")
    
    async def get(self, content_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get a cached routing decision for content.
        
        Args:
            content_info: Content information dictionary
            
        Returns:
            Cached routing decision or None if not found
        """
        # Calculate cache key and content signature
        key = self._calculate_cache_key(content_info)
        signature = self._calculate_content_signature(content_info)
        
        async with self._lock:
            # Check for exact match first
            if key in self._cache:
                decision, timestamp = self._cache[key]
                
                # Check if entry has expired
                if time.time() - timestamp > self.ttl_seconds:
                    # Remove expired entry
                    del self._cache[key]
                    # Remove from signature mapping
                    if signature in self._signature_mapping and key in self._signature_mapping[signature]:
                        self._signature_mapping[signature].remove(key)
                    return None
                
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                
                logger.debug(f"Cache hit for routing decision (exact match): {key}")
                return decision
            
            # No exact match, try similarity matching
            if signature in self._signature_mapping:
                for similar_key in self._signature_mapping[signature]:
                    if similar_key in self._cache:
                        similar_decision, timestamp = self._cache[similar_key]
                        
                        # Check if entry has expired
                        if time.time() - timestamp > self.ttl_seconds:
                            continue
                        
                        # Check similarity
                        if self._is_similar(content_info, similar_key):
                            # Move to end (most recently used)
                            self._cache.move_to_end(similar_key)
                            
                            logger.debug(f"Cache hit for routing decision (similarity match): {similar_key}")
                            return similar_decision
        
        # No match found
        return None
    
    async def put(self, content_info: Dict[str, Any], decision: Dict[str, Any]) -> None:
        """
        Store a routing decision in the cache.
        
        Args:
            content_info: Content information dictionary
            decision: Routing decision to cache
        """
        # Calculate cache key and content signature
        key = self._calculate_cache_key(content_info)
        signature = self._calculate_content_signature(content_info)
        
        async with self._lock:
            # Add to cache with current timestamp
            self._cache[key] = (decision, time.time())
            
            # Add to signature mapping
            if key not in self._signature_mapping[signature]:
                self._signature_mapping[signature].append(key)
            
            # Check if we need to remove oldest entries
            if len(self._cache) > self.max_size:
                # Remove oldest entry (first in OrderedDict)
                oldest_key, _ = self._cache.popitem(last=False)
                
                # Remove from signature mapping
                for sig, keys in self._signature_mapping.items():
                    if oldest_key in keys:
                        keys.remove(oldest_key)
                        # Remove empty signature entries
                        if not keys:
                            del self._signature_mapping[sig]
                        break
            
            logger.debug(f"Cached routing decision: {key}")
    
    async def invalidate(self, backend_id: Optional[str] = None) -> int:
        """
        Invalidate cache entries, optionally for a specific backend.
        
        Args:
            backend_id: Optional backend ID to invalidate entries for
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        async with self._lock:
            if backend_id is None:
                # Invalidate all entries
                count = len(self._cache)
                self._cache.clear()
                self._signature_mapping.clear()
                logger.info(f"Invalidated all cache entries ({count} entries)")
            else:
                # Invalidate entries for a specific backend
                keys_to_remove = []
                
                for key, (decision, _) in self._cache.items():
                    if decision.get("backend_id") == backend_id:
                        keys_to_remove.append(key)
                
                # Remove identified entries
                for key in keys_to_remove:
                    del self._cache[key]
                    count += 1
                    
                    # Remove from signature mapping
                    for sig, keys in list(self._signature_mapping.items()):
                        if key in keys:
                            keys.remove(key)
                            # Remove empty signature entries
                            if not keys:
                                del self._signature_mapping[sig]
                            break
                
                logger.info(f"Invalidated {count} cache entries for backend: {backend_id}")
        
        return count
    
    async def cleanup(self) -> int:
        """
        Remove expired entries from the cache.
        
        Returns:
            Number of entries removed
        """
        count = 0
        now = time.time()
        
        async with self._lock:
            keys_to_remove = []
            
            # Identify expired entries
            for key, (_, timestamp) in self._cache.items():
                if now - timestamp > self.ttl_seconds:
                    keys_to_remove.append(key)
            
            # Remove expired entries
            for key in keys_to_remove:
                del self._cache[key]
                count += 1
                
                # Remove from signature mapping
                for sig, keys in list(self._signature_mapping.items()):
                    if key in keys:
                        keys.remove(key)
                        # Remove empty signature entries
                        if not keys:
                            del self._signature_mapping[sig]
                        break
        
        if count > 0:
            logger.info(f"Removed {count} expired cache entries")
        
        return count
    
    def _calculate_cache_key(self, content_info: Dict[str, Any]) -> str:
        """
        Calculate a unique cache key for content info.
        
        Args:
            content_info: Content information dictionary
            
        Returns:
            Cache key string
        """
        # Extract key elements for the cache key
        key_elements = {
            "content_type": content_info.get("content_type", ""),
            "content_category": content_info.get("content_category", ""),
            "size_bytes": content_info.get("size_bytes", 0),
            "filename": content_info.get("filename", "")
        }
        
        # Create a deterministic string representation
        key_str = ";".join(f"{k}={v}" for k, v in sorted(key_elements.items()))
        
        # For additional uniqueness, add a hash of any content hash
        if "content_hash" in content_info:
            key_str += f";hash={content_info['content_hash']}"
        
        return key_str
    
    def _calculate_content_signature(self, content_info: Dict[str, Any]) -> str:
        """
        Calculate a signature for content similarity matching.
        
        The signature is used to find potentially similar content.
        
        Args:
            content_info: Content information dictionary
            
        Returns:
            Content signature string
        """
        # Create a simplified signature for similarity matching
        content_type = content_info.get("content_type", "")
        category = content_info.get("content_category", "")
        size_bytes = content_info.get("size_bytes", 0)
        
        # Size bucket (grouped into 10% ranges)
        if size_bytes > 0:
            size_magnitude = 10 ** (len(str(size_bytes)) - 1)
            size_bucket = size_bytes // (size_magnitude / 10) * (size_magnitude / 10)
        else:
            size_bucket = 0
        
        # Create signature
        if content_type:
            # Use main content type (before slash)
            main_type = content_type.split("/")[0]
            return f"{main_type}:{category}:{size_bucket}"
        elif category:
            return f"unknown:{category}:{size_bucket}"
        else:
            return f"unknown:unknown:{size_bucket}"
    
    def _is_similar(self, content_info: Dict[str, Any], cached_key: str) -> bool:
        """
        Check if content is similar to a cached entry.
        
        Args:
            content_info: Content information dictionary
            cached_key: Cache key to compare with
            
        Returns:
            True if content is similar, False otherwise
        """
        # Simple similarity check based on key comparison
        # In a real implementation, this would use more sophisticated similarity metrics
        
        # Calculate similarity score (0.0-1.0)
        new_key = self._calculate_cache_key(content_info)
        
        # Compare key elements
        new_elements = dict(item.split("=") for item in new_key.split(";"))
        cached_elements = dict(item.split("=") for item in cached_key.split(";"))
        
        # Count matching elements
        matches = 0
        total = len(new_elements)
        
        for key, value in new_elements.items():
            if key in cached_elements and cached_elements[key] == value:
                matches += 1
        
        similarity = matches / total if total > 0 else 0
        
        return similarity >= self.similarity_threshold


class ContentSignatureCalculator:
    """
    Efficient content signature calculator with caching.
    
    This class calculates and caches content signatures for routing decisions,
    improving performance for repeated operations on similar content.
    """
    
    def __init__(self, cache_size: int = 1000):
        """
        Initialize the signature calculator.
        
        Args:
            cache_size: Maximum number of signatures to cache
        """
        self.cache_size = cache_size
        self._cache: OrderedDict[int, str] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def calculate_signature(self, content: Union[bytes, str], algorithm: str = "xxh64") -> str:
        """
        Calculate a signature for content.
        
        Args:
            content: Content to calculate signature for
            algorithm: Hash algorithm to use
            
        Returns:
            Content signature string
        """
        # Use content identity hash as cache key (fast)
        cache_key = id(content)
        
        # Check cache first
        async with self._lock:
            if cache_key in self._cache:
                # Move to end (most recently used)
                signature = self._cache[cache_key]
                self._cache.move_to_end(cache_key)
                return signature
        
        # Convert string to bytes if needed
        content_bytes = content if isinstance(content, bytes) else content.encode('utf-8')
        
        # Calculate signature based on algorithm
        if algorithm == "xxh64":
            try:
                # Try to use xxhash (much faster)
                import xxhash
                signature = xxhash.xxh64(content_bytes).hexdigest()
            except ImportError:
                # Fall back to md5 if xxhash is not available
                signature = hashlib.md5(content_bytes).hexdigest()
        elif algorithm == "md5":
            signature = hashlib.md5(content_bytes).hexdigest()
        elif algorithm == "sha1":
            signature = hashlib.sha1(content_bytes).hexdigest()
        elif algorithm == "sha256":
            signature = hashlib.sha256(content_bytes).hexdigest()
        else:
            # Default to md5
            signature = hashlib.md5(content_bytes).hexdigest()
        
        # Store in cache
        async with self._lock:
            self._cache[cache_key] = signature
            
            # Remove oldest entry if cache is full
            if len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        
        return signature


class BatchProcessor:
    """
    Batch processor for routing operations.
    
    This class enables efficient batch processing of routing decisions and metrics updates,
    reducing overhead for high-volume operations.
    """
    
    def __init__(
        self,
        max_batch_size: int = 50,
        max_wait_time: float = 0.1,  # 100ms
        processor_func: Optional[Callable] = None
    ):
        """
        Initialize the batch processor.
        
        Args:
            max_batch_size: Maximum number of items in a batch
            max_wait_time: Maximum time to wait for a batch to fill in seconds
            processor_func: Function to process batches
        """
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.processor_func = processor_func
        
        self._batch: List[Any] = []
        self._batch_lock = asyncio.Lock()
        self._processing_task = None
        self._batch_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start the batch processor."""
        if self._processing_task is None:
            self._processing_task = asyncio.create_task(self._batch_processing_loop())
            logger.info("Started batch processor")
    
    async def stop(self) -> None:
        """Stop the batch processor."""
        if self._processing_task is not None:
            self._shutdown_event.set()
            await self._processing_task
            self._processing_task = None
            logger.info("Stopped batch processor")
    
    async def add_item(self, item: Any) -> None:
        """
        Add an item to the batch.
        
        Args:
            item: Item to add to the batch
        """
        async with self._batch_lock:
            self._batch.append(item)
            
            # Signal that a new item has been added
            self._batch_event.set()
            
            # If batch is full, process immediately
            if len(self._batch) >= self.max_batch_size:
                # Clear the event because we're processing the batch
                self._batch_event.clear()
                await self._process_batch()
    
    async def _batch_processing_loop(self) -> None:
        """Background loop for batch processing."""
        try:
            while not self._shutdown_event.is_set():
                # Wait for items or timeout
                try:
                    # Wait for either an item to be added or the timeout
                    await asyncio.wait_for(self._batch_event.wait(), timeout=self.max_wait_time)
                except asyncio.TimeoutError:
                    # If we timed out and have items, process them
                    async with self._batch_lock:
                        if self._batch:
                            await self._process_batch()
                            self._batch_event.clear()
                        continue
                
                # If we have items, process them
                async with self._batch_lock:
                    if self._batch:
                        await self._process_batch()
                        self._batch_event.clear()
        except asyncio.CancelledError:
            logger.info("Batch processing task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in batch processing loop: {e}")
    
    async def _process_batch(self) -> None:
        """Process the current batch."""
        if not self._batch:
            return
        
        # Get the current batch and clear it
        current_batch = self._batch.copy()
        self._batch.clear()
        
        # Process the batch if processor_func is set
        if self.processor_func:
            try:
                await self.processor_func(current_batch)
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
        else:
            logger.warning("No processor function set for batch processor")


class ConnectionPool:
    """
    Connection pool for backend connections.
    
    This class manages connections to backends, reusing existing connections
    to reduce overhead and improve performance.
    """
    
    def __init__(
        self,
        max_connections: int = 10,
        connection_ttl: int = 300,  # 5 minutes
        connection_factory: Optional[Callable] = None
    ):
        """
        Initialize the connection pool.
        
        Args:
            max_connections: Maximum number of connections per backend
            connection_ttl: Time-to-live for connections in seconds
            connection_factory: Function to create new connections
        """
        self.max_connections = max_connections
        self.connection_ttl = connection_ttl
        self.connection_factory = connection_factory
        
        # Connections by backend ID
        self._connections: Dict[str, List[Tuple[Any, float]]] = defaultdict(list)
        self._in_use: Dict[str, Set[Any]] = defaultdict(set)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Background task for cleanup
        self._cleanup_task = None
        self._shutdown_event = asyncio.Event()
        
        logger.info(f"Initialized connection pool with max_connections={max_connections}")
    
    async def start(self) -> None:
        """Start the connection pool cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started connection pool cleanup task")
    
    async def stop(self) -> None:
        """Stop the connection pool and close all connections."""
        if self._cleanup_task is not None:
            self._shutdown_event.set()
            await self._cleanup_task
            self._cleanup_task = None
        
        # Close all connections
        async with self._lock:
            for backend_id, connections in self._connections.items():
                for conn, _ in connections:
                    await self._close_connection(conn)
                self._connections[backend_id] = []
                self._in_use[backend_id] = set()
        
        logger.info("Stopped connection pool and closed all connections")
    
    async def get_connection(self, backend_id: str) -> Any:
        """
        Get a connection for a backend.
        
        Args:
            backend_id: Backend ID
            
        Returns:
            Connection object
        """
        async with self._lock:
            # Check if we have available connections
            if backend_id in self._connections and self._connections[backend_id]:
                # Get the first available connection
                for i, (conn, timestamp) in enumerate(self._connections[backend_id]):
                    # Check if connection has expired
                    if time.time() - timestamp > self.connection_ttl:
                        # Remove from connections list
                        self._connections[backend_id].pop(i)
                        # Close the connection
                        await self._close_connection(conn)
                        continue
                    
                    # Connection is valid, remove from available list
                    self._connections[backend_id].pop(i)
                    # Add to in-use set
                    self._in_use[backend_id].add(conn)
                    
                    logger.debug(f"Reusing connection for backend: {backend_id}")
                    return conn
            
            # No available connections, create a new one
            if self.connection_factory:
                try:
                    conn = await self.connection_factory(backend_id)
                    # Add to in-use set
                    self._in_use[backend_id].add(conn)
                    
                    logger.debug(f"Created new connection for backend: {backend_id}")
                    return conn
                except Exception as e:
                    logger.error(f"Error creating connection for backend {backend_id}: {e}")
                    raise
            else:
                raise ValueError("No connection factory provided")
    
    async def release_connection(self, backend_id: str, conn: Any) -> None:
        """
        Release a connection back to the pool.
        
        Args:
            backend_id: Backend ID
            conn: Connection object
        """
        async with self._lock:
            # Remove from in-use set
            if conn in self._in_use[backend_id]:
                self._in_use[backend_id].remove(conn)
            
            # Check if we can add it back to the available list
            if len(self._connections[backend_id]) < self.max_connections:
                # Add to available list with current timestamp
                self._connections[backend_id].append((conn, time.time()))
                logger.debug(f"Released connection back to pool for backend: {backend_id}")
            else:
                # Too many connections, close this one
                await self._close_connection(conn)
                logger.debug(f"Closed excess connection for backend: {backend_id}")
    
    async def _close_connection(self, conn: Any) -> None:
        """
        Close a connection.
        
        Args:
            conn: Connection object
        """
        try:
            # If connection has a close method, call it
            if hasattr(conn, "close"):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    conn.close()
            elif hasattr(conn, "disconnect"):
                if asyncio.iscoroutinefunction(conn.disconnect):
                    await conn.disconnect()
                else:
                    conn.disconnect()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up expired connections."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Sleep for a while
                    await asyncio.sleep(60)  # Check every minute
                    
                    # Clean up expired connections
                    await self._cleanup_expired_connections()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error in connection pool cleanup loop: {e}")
        except asyncio.CancelledError:
            logger.info("Connection pool cleanup task cancelled")
            raise
    
    async def _cleanup_expired_connections(self) -> None:
        """Clean up expired connections."""
        now = time.time()
        count = 0
        
        async with self._lock:
            for backend_id, connections in list(self._connections.items()):
                # Identify expired connections
                expired = []
                for i, (conn, timestamp) in enumerate(connections):
                    if now - timestamp > self.connection_ttl:
                        expired.append((i, conn))
                
                # Remove expired connections (in reverse order to avoid index issues)
                for i, conn in sorted(expired, reverse=True):
                    connections.pop(i)
                    await self._close_connection(conn)
                    count += 1
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired connections")


def optimize_routing_function(func: Callable) -> Callable:
    """
    Decorator to optimize a routing function with caching.
    
    Args:
        func: Function to optimize
        
    Returns:
        Optimized function
    """
    # Create a cache for this function
    cache = {}
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Create a cache key from arguments
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        cache_key = ":".join(key_parts)
        
        # Check cache
        if cache_key in cache:
            result, timestamp = cache[cache_key]
            # Check if entry has expired (1 minute TTL)
            if time.time() - timestamp < 60:
                return result
        
        # Call the original function
        result = await func(*args, **kwargs)
        
        # Cache the result
        cache[cache_key] = (result, time.time())
        
        # Limit cache size
        if len(cache) > 100:
            # Remove oldest entries
            oldest_keys = sorted(cache.keys(), key=lambda k: cache[k][1])[:10]
            for key in oldest_keys:
                del cache[key]
        
        return result
    
    return wrapper


@dataclass
class RoutingPerformanceMetrics:
    """Performance metrics for the routing system."""
    
    # Request counts
    requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    
    # Timing metrics (in milliseconds)
    avg_request_time: float = 0.0
    min_request_time: float = float('inf')
    max_request_time: float = 0.0
    total_request_time: float = 0.0
    
    # Recent request times
    recent_request_times: List[float] = field(default_factory=list)
    max_recent_times: int = 100
    
    # Resource usage
    memory_usage_bytes: int = 0
    
    def record_request(self, request_time: float, cached: bool = False, error: bool = False) -> None:
        """
        Record a routing request.
        
        Args:
            request_time: Request time in milliseconds
            cached: Whether the request was served from cache
            error: Whether the request resulted in an error
        """
        self.requests += 1
        
        if error:
            self.errors += 1
        elif cached:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        # Update timing metrics
        self.total_request_time += request_time
        self.avg_request_time = self.total_request_time / self.requests
        self.min_request_time = min(self.min_request_time, request_time)
        self.max_request_time = max(self.max_request_time, request_time)
        
        # Add to recent times
        self.recent_request_times.append(request_time)
        if len(self.recent_request_times) > self.max_recent_times:
            self.recent_request_times.pop(0)
    
    def get_cache_hit_ratio(self) -> float:
        """
        Get the cache hit ratio.
        
        Returns:
            Cache hit ratio (0.0-1.0)
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total
    
    def get_recent_avg_request_time(self) -> float:
        """
        Get the average request time for recent requests.
        
        Returns:
            Average request time in milliseconds
        """
        if not self.recent_request_times:
            return 0.0
        return sum(self.recent_request_times) / len(self.recent_request_times)
    
    def get_error_rate(self) -> float:
        """
        Get the error rate.
        
        Returns:
            Error rate (0.0-1.0)
        """
        if self.requests == 0:
            return 0.0
        return self.errors / self.requests
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to dictionary.
        
        Returns:
            Dictionary with metrics
        """
        return {
            "requests": self.requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "errors": self.errors,
            "avg_request_time_ms": self.avg_request_time,
            "min_request_time_ms": self.min_request_time if self.min_request_time != float('inf') else 0.0,
            "max_request_time_ms": self.max_request_time,
            "recent_avg_request_time_ms": self.get_recent_avg_request_time(),
            "cache_hit_ratio": self.get_cache_hit_ratio(),
            "error_rate": self.get_error_rate(),
            "memory_usage_bytes": self.memory_usage_bytes
        }


# Initialize default instances
routing_decision_cache = RoutingDecisionCache()
content_signature_calculator = ContentSignatureCalculator()
connection_pool = ConnectionPool()
performance_metrics = RoutingPerformanceMetrics()


async def initialize_performance_optimizations() -> None:
    """Initialize all performance optimizations."""
    # Start connection pool
    await connection_pool.start()
    
    logger.info("Initialized performance optimizations")


async def shutdown_performance_optimizations() -> None:
    """Shutdown all performance optimizations."""
    # Stop connection pool
    await connection_pool.stop()
    
    logger.info("Shutdown performance optimizations")


def measure_routing_performance(func: Callable) -> Callable:
    """
    Decorator to measure routing performance.
    
    Args:
        func: Function to measure
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        cached = False
        error = False
        
        try:
            # Try to get from cache if first argument is a dict (content_info)
            if args and isinstance(args[0], dict):
                content_info = args[0]
                cached_result = await routing_decision_cache.get(content_info)
                if cached_result:
                    cached = True
                    return cached_result
            
            # Call the original function
            result = await func(*args, **kwargs)
            
            # Cache the result if it's a routing decision
            if args and isinstance(args[0], dict) and isinstance(result, dict) and "backend_id" in result:
                await routing_decision_cache.put(args[0], result)
            
            return result
            
        except Exception as e:
            error = True
            raise
        finally:
            # Calculate request time
            request_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Record metrics
            performance_metrics.record_request(request_time, cached, error)
    
    return wrapper