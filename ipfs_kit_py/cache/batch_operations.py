"""
Batch operations for ParquetCIDCache in tiered storage system.

This module provides efficient batch processing capability for the ParquetCIDCache,
implementing the first phase of performance optimizations from the performance
optimization roadmap.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple, Set, Union
import concurrent.futures
import queue

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyarrow import compute as pc
    from pyarrow.dataset import dataset
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

# Initialize logger
logger = logging.getLogger(__name__)

class BatchOperationManager:
    """Manager for batch operations in ParquetCIDCache.
    
    This class provides efficient batch processing capability for ParquetCIDCache
    by optimizing common operations for multiple CIDs at once, reducing overhead
    and improving throughput for bulk operations.
    
    Features:
    - Batched metadata retrieval and storage
    - Prioritized batch processing
    - Operation coalescing for efficiency
    - Background batch execution
    - Request deduplication
    - Result caching
    """
    
    def __init__(self, 
                max_batch_size: int = 1000,
                max_concurrent_batches: int = 4,
                batch_timeout_ms: int = 100,
                enable_operation_coalescing: bool = True,
                enable_request_deduplication: bool = True,
                enable_result_caching: bool = True,
                worker_count: int = 4):
        """Initialize the batch operation manager.
        
        Args:
            max_batch_size: Maximum number of items in a single batch
            max_concurrent_batches: Maximum number of batches to process concurrently
            batch_timeout_ms: Maximum time to wait for batch to fill in milliseconds
            enable_operation_coalescing: Whether to coalesce similar operations
            enable_request_deduplication: Whether to deduplicate identical requests
            enable_result_caching: Whether to cache operation results
            worker_count: Number of worker threads for batch processing
        """
        if not HAS_PYARROW:
            raise ImportError("PyArrow is required for BatchOperationManager")
        
        self.max_batch_size = max_batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.batch_timeout_ms = batch_timeout_ms
        self.enable_operation_coalescing = enable_operation_coalescing
        self.enable_request_deduplication = enable_request_deduplication
        self.enable_result_caching = enable_result_caching
        
        # Create worker pool for batch processing
        self.worker_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=worker_count, 
            thread_name_prefix="BatchOpWorker"
        )
        
        # Batching queues for different operation types
        self.get_queue = queue.Queue()
        self.put_queue = queue.Queue()
        self.query_queue = queue.Queue()
        
        # Pending batches tracking
        self.pending_gets = set()
        self.pending_puts = set()
        self.pending_queries = set()
        
        # Result caching if enabled
        self.result_cache = {} if enable_result_caching else None
        self.result_cache_max_size = 10000
        self.result_cache_ttl_ms = 5000  # Results valid for 5 seconds
        
        # In-flight request tracking for deduplication
        self.in_flight_requests = set() if enable_request_deduplication else None
        
        # Operation coalescing tracking
        self.coalescing_window = {} if enable_operation_coalescing else None
        self.coalescing_window_size_ms = 50  # 50ms window for coalescing
        
        # Performance metrics
        self.metrics = {
            "batches_processed": 0,
            "total_operations": 0,
            "batch_sizes": [],
            "coalesced_operations": 0,
            "deduplicated_requests": 0,
            "cache_hits": 0,
            "latencies_ms": []
        }
        
        # Start batch processing workers
        self._start_batch_processors()
    
    def _start_batch_processors(self):
        """Start background threads for batch processing."""
        # Submit batch processing tasks to the thread pool
        for _ in range(self.max_concurrent_batches):
            self.worker_pool.submit(self._process_get_batches)
            self.worker_pool.submit(self._process_put_batches)
            self.worker_pool.submit(self._process_query_batches)
    
    def _process_get_batches(self):
        """Process batches of get operations."""
        while True:
            try:
                # Collect operations until batch is full or timeout occurs
                batch = []
                start_time = time.time()
                timeout_time = start_time + (self.batch_timeout_ms / 1000.0)
                
                # Keep collecting until batch is full or timeout
                while len(batch) < self.max_batch_size and time.time() < timeout_time:
                    try:
                        # Try to get an operation with timeout
                        remaining_time = max(0, timeout_time - time.time())
                        operation = self.get_queue.get(timeout=remaining_time)
                        
                        # Add to batch
                        batch.append(operation)
                        
                    except queue.Empty:
                        # Timeout waiting for next operation
                        break
                
                # If we have operations to process
                if batch:
                    # Process the batch
                    self._execute_get_batch(batch)
                    
                    # Update metrics
                    self.metrics["batches_processed"] += 1
                    self.metrics["total_operations"] += len(batch)
                    self.metrics["batch_sizes"].append(len(batch))
                    
                    # Limit metrics collection to avoid memory growth
                    if len(self.metrics["batch_sizes"]) > 1000:
                        self.metrics["batch_sizes"] = self.metrics["batch_sizes"][-1000:]
                    if len(self.metrics["latencies_ms"]) > 1000:
                        self.metrics["latencies_ms"] = self.metrics["latencies_ms"][-1000:]
                
            except Exception as e:
                logger.error(f"Error processing get batch: {e}")
    
    def _process_put_batches(self):
        """Process batches of put operations."""
        while True:
            try:
                # Similar implementation as _process_get_batches
                batch = []
                start_time = time.time()
                timeout_time = start_time + (self.batch_timeout_ms / 1000.0)
                
                while len(batch) < self.max_batch_size and time.time() < timeout_time:
                    try:
                        remaining_time = max(0, timeout_time - time.time())
                        operation = self.put_queue.get(timeout=remaining_time)
                        batch.append(operation)
                    except queue.Empty:
                        break
                
                if batch:
                    self._execute_put_batch(batch)
                    
                    # Update metrics
                    self.metrics["batches_processed"] += 1
                    self.metrics["total_operations"] += len(batch)
                    self.metrics["batch_sizes"].append(len(batch))
            
            except Exception as e:
                logger.error(f"Error processing put batch: {e}")
    
    def _process_query_batches(self):
        """Process batches of query operations."""
        while True:
            try:
                # Similar implementation as other batch processors
                batch = []
                start_time = time.time()
                timeout_time = start_time + (self.batch_timeout_ms / 1000.0)
                
                while len(batch) < self.max_batch_size and time.time() < timeout_time:
                    try:
                        remaining_time = max(0, timeout_time - time.time())
                        operation = self.query_queue.get(timeout=remaining_time)
                        batch.append(operation)
                    except queue.Empty:
                        break
                
                if batch:
                    self._execute_query_batch(batch)
                    
                    # Update metrics
                    self.metrics["batches_processed"] += 1
                    self.metrics["total_operations"] += len(batch)
                    self.metrics["batch_sizes"].append(len(batch))
            
            except Exception as e:
                logger.error(f"Error processing query batch: {e}")
    
    def _execute_get_batch(self, batch):
        """Execute a batch of get operations.
        
        Args:
            batch: List of (cid, future, callback) tuples for get operations
        """
        # Extract CIDs from batch
        cids = [op[0] for op in batch]
        futures = [op[1] for op in batch]
        callbacks = [op[2] for op in batch]
        
        # Group by cache instance
        cache_groups = {}
        for i, op in enumerate(batch):
            cid, future, callback = op
            cache_instance = getattr(callback, '__self__', None)
            
            if cache_instance:
                if cache_instance not in cache_groups:
                    cache_groups[cache_instance] = []
                cache_groups[cache_instance].append((i, cid))
        
        # Process each cache group
        all_results = {}
        for cache_instance, items in cache_groups.items():
            # Extract CIDs for this cache
            group_indices = [item[0] for item in items]
            group_cids = [item[1] for item in items]
            
            # Call batch_get_metadata on the cache instance
            if hasattr(cache_instance, 'batch_get_metadata'):
                group_results = cache_instance.batch_get_metadata(group_cids)
                
                # Map results back to the original batch
                for i, cid in enumerate(group_cids):
                    batch_idx = group_indices[i]
                    all_results[batch_idx] = group_results.get(cid)
            else:
                # Fallback to individual gets if batch method not available
                for i, cid in enumerate(group_cids):
                    batch_idx = group_indices[i]
                    result = cache_instance.get_metadata(cid)
                    all_results[batch_idx] = result
        
        # Set results in futures
        for i, future in enumerate(futures):
            if i in all_results:
                future.set_result(all_results[i])
            else:
                future.set_result(None)
    
    def _execute_put_batch(self, batch):
        """Execute a batch of put operations.
        
        Args:
            batch: List of (cid, metadata, future, callback) tuples for put operations
        """
        # Group by cache instance
        cache_groups = {}
        for i, op in enumerate(batch):
            cid, metadata, future, callback = op
            cache_instance = getattr(callback, '__self__', None)
            
            if cache_instance:
                if cache_instance not in cache_groups:
                    cache_groups[cache_instance] = {}
                cache_groups[cache_instance][cid] = (i, metadata)
        
        # Process each cache group
        all_results = {}
        for cache_instance, cid_map in cache_groups.items():
            # Extract CIDs and metadata for this cache
            group_cids = {}
            indices = {}
            
            for cid, (idx, metadata) in cid_map.items():
                group_cids[cid] = metadata
                indices[cid] = idx
            
            # Call batch_put_metadata on the cache instance
            if hasattr(cache_instance, 'batch_put_metadata'):
                group_results = cache_instance.batch_put_metadata(group_cids)
                
                # Map results back to the original batch
                for cid, success in group_results.items():
                    batch_idx = indices[cid]
                    all_results[batch_idx] = success
            else:
                # Fallback to individual puts if batch method not available
                for cid, metadata in group_cids.items():
                    batch_idx = indices[cid]
                    result = cache_instance.put_metadata(cid, metadata)
                    all_results[batch_idx] = result
        
        # Set results in futures
        for i, op in enumerate(batch):
            _, _, future, _ = op
            if i in all_results:
                future.set_result(all_results[i])
            else:
                future.set_result(False)
    
    def _execute_query_batch(self, batch):
        """Execute a batch of query operations.
        
        Args:
            batch: List of (filters, future, callback) tuples for query operations
        """
        # This is more complex as queries are not easily batchable
        # For now, execute them individually
        for filters, future, callback in batch:
            cache_instance = getattr(callback, '__self__', None)
            if cache_instance and hasattr(cache_instance, 'query'):
                try:
                    result = cache_instance.query(filters)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
            else:
                future.set_exception(ValueError("Invalid cache instance or missing query method"))
    
    def batch_get_metadata(self, cid: str, callback):
        """Submit a get metadata operation to be processed in a batch.
        
        Args:
            cid: Content identifier to get
            callback: Method to call to execute the operation
            
        Returns:
            Future object for tracking the operation
        """
        # Create future for tracking the result
        future = concurrent.futures.Future()
        
        # Check result cache if enabled
        if self.enable_result_caching and cid in self.result_cache:
            cache_entry = self.result_cache[cid]
            if (time.time() * 1000) - cache_entry['timestamp'] < self.result_cache_ttl_ms:
                # Cache hit
                self.metrics["cache_hits"] += 1
                future.set_result(cache_entry['result'])
                return future
        
        # Check for in-flight requests if deduplication is enabled
        if self.enable_request_deduplication and cid in self.in_flight_requests:
            self.metrics["deduplicated_requests"] += 1
            # Return the same future as the existing request
            return self.pending_gets.get(cid, future)
        
        # Track in-flight request
        if self.enable_request_deduplication:
            self.in_flight_requests.add(cid)
            self.pending_gets[cid] = future
        
        # Submit to batch queue
        self.get_queue.put((cid, future, callback))
        
        return future
    
    def batch_put_metadata(self, cid: str, metadata: Dict[str, Any], callback):
        """Submit a put metadata operation to be processed in a batch.
        
        Args:
            cid: Content identifier to update
            metadata: Metadata to store
            callback: Method to call to execute the operation
            
        Returns:
            Future object for tracking the operation
        """
        # Create future for tracking the result
        future = concurrent.futures.Future()
        
        # Check for coalescing opportunity
        if self.enable_operation_coalescing and cid in self.coalescing_window:
            # Get existing operation
            existing_op = self.coalescing_window[cid]
            existing_timestamp = existing_op.get('timestamp', 0)
            
            # Check if within coalescing window
            if (time.time() * 1000) - existing_timestamp < self.coalescing_window_size_ms:
                # Coalesce by updating the metadata and reusing the future
                self.metrics["coalesced_operations"] += 1
                existing_op['metadata'].update(metadata)
                return existing_op['future']
        
        # Track for potential coalescing
        if self.enable_operation_coalescing:
            self.coalescing_window[cid] = {
                'timestamp': time.time() * 1000,
                'metadata': metadata.copy(),
                'future': future
            }
        
        # Submit to batch queue
        self.put_queue.put((cid, metadata, future, callback))
        
        return future
    
    def batch_query(self, filters: List[tuple], callback):
        """Submit a query operation to be processed in a batch.
        
        Args:
            filters: Query filters
            callback: Method to call to execute the operation
            
        Returns:
            Future object for tracking the operation
        """
        # Create future for tracking the result
        future = concurrent.futures.Future()
        
        # Submit to batch queue
        self.query_queue.put((filters, future, callback))
        
        return future
    
    def get_metrics(self):
        """Get performance metrics for batch operations.
        
        Returns:
            Dictionary with performance metrics
        """
        metrics = self.metrics.copy()
        
        # Calculate derived metrics
        total_batches = metrics["batches_processed"]
        if total_batches > 0:
            metrics["avg_batch_size"] = sum(metrics["batch_sizes"]) / len(metrics["batch_sizes"]) if metrics["batch_sizes"] else 0
            metrics["avg_latency_ms"] = sum(metrics["latencies_ms"]) / len(metrics["latencies_ms"]) if metrics["latencies_ms"] else 0
        
        # Queue metrics
        metrics["queued_operations"] = {
            "get": self.get_queue.qsize(),
            "put": self.put_queue.qsize(),
            "query": self.query_queue.qsize()
        }
        
        # Efficiency metrics
        if metrics["total_operations"] > 0:
            metrics["coalescing_rate"] = metrics["coalesced_operations"] / metrics["total_operations"]
            metrics["deduplication_rate"] = metrics["deduplicated_requests"] / metrics["total_operations"]
            metrics["cache_hit_rate"] = metrics["cache_hits"] / metrics["total_operations"]
        
        return metrics
    
    def shutdown(self):
        """Shutdown the batch operation manager."""
        # Clear queues
        while not self.get_queue.empty():
            try:
                self.get_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.put_queue.empty():
            try:
                self.put_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.query_queue.empty():
            try:
                self.query_queue.get_nowait()
            except queue.Empty:
                break
        
        # Shutdown worker pool
        self.worker_pool.shutdown(wait=False)