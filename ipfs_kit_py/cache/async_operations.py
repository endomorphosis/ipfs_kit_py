"""
Asynchronous operations for ParquetCIDCache.

This module provides asynchronous versions of ParquetCIDCache operations for improved
concurrency and responsiveness. It implements non-blocking I/O for Parquet operations
and maintains compatibility with asyncio-based applications.
"""

import anyio
import functools
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union, cast

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow.dataset import Dataset

# Type variables for generic function signatures
T = TypeVar('T')
R = TypeVar('R')

logger = logging.getLogger(__name__)

class AsyncOperationManager:
    """Manager for asynchronous operations in ParquetCIDCache.
    
    This class provides asynchronous versions of ParquetCIDCache operations,
    implementing non-blocking I/O for improved concurrency and responsiveness.
    It maintains compatibility with asyncio-based applications and ensures
    thread safety for concurrent operations.
    """
    
    def __init__(self, 
                 max_workers: int = 8,
                 io_workers: int = 4,
                 compute_workers: int = 4,
                 task_timeout: float = 30.0,
                 enable_priority: bool = True,
                 enable_batching: bool = True,
                 enable_stats: bool = True):
        """Initialize the asynchronous operation manager.
        
        Args:
            max_workers: Maximum number of worker threads for general operations
            io_workers: Number of worker threads dedicated to I/O operations
            compute_workers: Number of worker threads for compute-intensive operations
            task_timeout: Default timeout for async tasks in seconds
            enable_priority: Whether to use priority queues for operations
            enable_batching: Whether to automatically batch compatible operations
            enable_stats: Whether to collect performance statistics
        """
        self.max_workers = max_workers
        self.io_workers = io_workers
        self.compute_workers = compute_workers
        self.task_timeout = task_timeout
        self.enable_priority = enable_priority
        self.enable_batching = enable_batching
        self.enable_stats = enable_stats
        
        # Initialize thread pools for different operation types
        self.io_pool = ThreadPoolExecutor(
            max_workers=io_workers, 
            thread_name_prefix="async-io-worker"
        )
        self.compute_pool = ThreadPoolExecutor(
            max_workers=compute_workers, 
            thread_name_prefix="async-compute-worker"
        )
        self.general_pool = ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="async-general-worker"
        )
        
        # Operation statistics
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "operation_times": {},
            "operation_counts": {},
            "in_flight": 0,
            "queued": 0,
            "batched_operations": 0,
            "batch_sizes": []
        }
        
        # Semaphore to limit concurrent operations
        self.semaphore = anyio.Semaphore(max_workers + io_workers + compute_workers)
        
        # Task registry for cleanup and tracking
        self.tasks: Dict[str, anyio.Task] = {}
        
        # Flag to track if the manager is being shut down
        self.shutting_down = False
        
        logger.info(
            f"AsyncOperationManager initialized with {max_workers} general workers, "
            f"{io_workers} I/O workers, and {compute_workers} compute workers"
        )
    
    async def run_in_executor(self, 
                             func: Callable[..., T], 
                             *args: Any, 
                             executor_type: str = "general", 
                             **kwargs: Any) -> T:
        """Run a function in the appropriate thread pool executor.
        
        Args:
            func: The function to execute
            *args: Arguments to pass to the function
            executor_type: Type of executor to use ("io", "compute", or "general")
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            The result of the function execution
        """
        # Select the appropriate executor
        if executor_type == "io":
            executor = self.io_pool
        elif executor_type == "compute":
            executor = self.compute_pool
        else:
            executor = self.general_pool
        
        # Update statistics
        if self.enable_stats:
            self.stats["in_flight"] += 1
            operation_name = func.__name__
            if operation_name not in self.stats["operation_counts"]:
                self.stats["operation_counts"][operation_name] = 0
                self.stats["operation_times"][operation_name] = []
            self.stats["operation_counts"][operation_name] += 1
            start_time = time.time()
        
        # Execute the function in the thread pool
        try:
            loop = anyio.get_event_loop()
            async with self.semaphore:
                result = await loop.run_in_executor(
                    executor, 
                    functools.partial(func, *args, **kwargs)
                )
            
            # Update success statistics
            if self.enable_stats:
                self.stats["successful_operations"] += 1
                self.stats["total_operations"] += 1
                
            return result
            
        except Exception as e:
            # Update failure statistics
            if self.enable_stats:
                self.stats["failed_operations"] += 1
                self.stats["total_operations"] += 1
                
            logger.exception(f"Error in async operation {func.__name__}: {str(e)}")
            raise
            
        finally:
            # Update completion statistics
            if self.enable_stats:
                end_time = time.time()
                operation_time = end_time - start_time
                self.stats["operation_times"][operation_name].append(operation_time)
                self.stats["in_flight"] -= 1
    
    async def async_get(self, 
                      cache_instance: Any, 
                      cid: str, 
                      columns: Optional[List[str]] = None, 
                      filters: Optional[List[Tuple]] = None) -> Optional[pa.Table]:
        """Asynchronous version of the get operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to retrieve
            columns: Optional list of columns to retrieve
            filters: Optional list of filters to apply
            
        Returns:
            Arrow Table with the retrieved data or None if not found
        """
        async def _get_operation():
            # Check memory cache first with direct access (thread-safe)
            if hasattr(cache_instance, 'memory_cache') and cid in cache_instance.memory_cache:
                if self.enable_stats:
                    self.stats.setdefault("memory_hits", 0)
                    self.stats["memory_hits"] += 1
                return cache_instance.memory_cache[cid]
            
            # Run the disk operation in the I/O thread pool
            return await self.run_in_executor(
                cache_instance._get_from_disk,
                cid,
                columns,
                filters,
                executor_type="io"
            )
        
        try:
            return await _get_operation()
        except Exception as e:
            logger.error(f"Error in async_get for CID {cid}: {str(e)}")
            return None
    
    async def async_put(self, 
                      cache_instance: Any, 
                      cid: str, 
                      table: pa.Table, 
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Asynchronous version of the put operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to store
            table: Arrow Table with the data to store
            metadata: Optional metadata to store with the data
            
        Returns:
            Boolean indicating success
        """
        async def _put_operation():
            # Update memory cache directly (thread-safe operation)
            if hasattr(cache_instance, 'memory_cache'):
                cache_instance.memory_cache[cid] = table
            
            # Run the disk operation in the I/O thread pool
            return await self.run_in_executor(
                cache_instance._put_to_disk,
                cid,
                table,
                metadata,
                executor_type="io"
            )
        
        try:
            return await _put_operation()
        except Exception as e:
            logger.error(f"Error in async_put for CID {cid}: {str(e)}")
            return False
    
    async def async_delete(self, cache_instance: Any, cid: str) -> bool:
        """Asynchronous version of the delete operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to delete
            
        Returns:
            Boolean indicating success
        """
        async def _delete_operation():
            # Remove from memory cache directly (thread-safe operation)
            if hasattr(cache_instance, 'memory_cache') and cid in cache_instance.memory_cache:
                del cache_instance.memory_cache[cid]
            
            # Run the disk operation in the I/O thread pool
            return await self.run_in_executor(
                cache_instance._delete_from_disk,
                cid,
                executor_type="io"
            )
        
        try:
            return await _delete_operation()
        except Exception as e:
            logger.error(f"Error in async_delete for CID {cid}: {str(e)}")
            return False
    
    async def async_query(self, 
                        cache_instance: Any, 
                        filters: List[Tuple], 
                        columns: Optional[List[str]] = None,
                        limit: Optional[int] = None) -> pa.Table:
        """Asynchronous version of the query operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            filters: List of filter conditions to apply
            columns: Optional list of columns to retrieve
            limit: Optional maximum number of results to return
            
        Returns:
            Arrow Table with the query results
        """
        return await self.run_in_executor(
            cache_instance._query,
            filters,
            columns,
            limit,
            executor_type="compute"
        )
    
    async def async_contains(self, cache_instance: Any, cid: str) -> bool:
        """Asynchronous version of the contains operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to check
            
        Returns:
            Boolean indicating if the CID is in the cache
        """
        # Check memory cache first (thread-safe)
        if hasattr(cache_instance, 'memory_cache') and cid in cache_instance.memory_cache:
            return True
        
        # Run the disk check in the I/O thread pool
        return await self.run_in_executor(
            cache_instance._contains_in_disk,
            cid,
            executor_type="io"
        )
    
    async def async_get_metadata(self, cache_instance: Any, cid: str) -> Optional[Dict[str, Any]]:
        """Asynchronous version of the get_metadata operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to get metadata for
            
        Returns:
            Dictionary with metadata or None if not found
        """
        return await self.run_in_executor(
            cache_instance._get_metadata,
            cid,
            executor_type="io"
        )
    
    async def async_update_metadata(self, 
                                  cache_instance: Any, 
                                  cid: str, 
                                  metadata: Dict[str, Any], 
                                  merge: bool = True) -> bool:
        """Asynchronous version of the update_metadata operation for ParquetCIDCache.
        
        Args:
            cache_instance: The ParquetCIDCache instance
            cid: The content identifier to update metadata for
            metadata: New metadata to store
            merge: Whether to merge with existing metadata or replace
            
        Returns:
            Boolean indicating success
        """
        return await self.run_in_executor(
            cache_instance._update_metadata,
            cid,
            metadata,
            merge,
            executor_type="io"
        )
    
    async def async_get_stats(self) -> Dict[str, Any]:
        """Get statistics about async operations.
        
        Returns:
            Dictionary with operation statistics
        """
        if not self.enable_stats:
            return {"stats_disabled": True}
        
        # Calculate average operation times
        avg_times = {}
        for op_name, times in self.stats["operation_times"].items():
            if times:
                avg_times[op_name] = sum(times) / len(times)
            else:
                avg_times[op_name] = 0
        
        # Create a copy of stats with calculated averages
        result = {**self.stats, "average_times": avg_times}
        
        # Add additional metrics
        result["io_pool_size"] = self.io_workers
        result["compute_pool_size"] = self.compute_workers
        result["general_pool_size"] = self.max_workers
        
        return result
    
    async def async_batch(self, 
                        operation: str, 
                        items: List[Dict[str, Any]], 
                        cache_instance: Any) -> List[Any]:
        """Execute a batch of operations asynchronously.
        
        Args:
            operation: The operation name to perform ("get", "put", etc.)
            items: List of operation parameters
            cache_instance: The ParquetCIDCache instance
            
        Returns:
            List of operation results in the same order as the input items
        """
        # Select the appropriate operation method
        op_methods = {
            "get": self.async_get,
            "put": self.async_put,
            "delete": self.async_delete,
            "contains": self.async_contains,
            "get_metadata": self.async_get_metadata,
            "update_metadata": self.async_update_metadata
        }
        
        if operation not in op_methods:
            raise ValueError(f"Unsupported batch operation: {operation}")
        
        op_method = op_methods[operation]
        
        # Create a task for each operation
        tasks = []
        for item in items:
            if operation == "get":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"],
                    item.get("columns"),
                    item.get("filters")
                ))
            elif operation == "put":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"],
                    item["table"],
                    item.get("metadata")
                ))
            elif operation == "delete":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"]
                ))
            elif operation == "contains":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"]
                ))
            elif operation == "get_metadata":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"]
                ))
            elif operation == "update_metadata":
                task = anyio.create_task(op_method(
                    cache_instance,
                    item["cid"],
                    item["metadata"],
                    item.get("merge", True)
                ))
            tasks.append(task)
        
        # Update batch statistics
        if self.enable_stats:
            self.stats["batched_operations"] += len(items)
            self.stats["batch_sizes"].append(len(items))
        
        # Wait for all tasks to complete
        results = await anyio.gather(*tasks, return_exceptions=True)
        
        # Process results to reraise exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch operation {operation}: {str(result)}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def shutdown(self, wait: bool = True) -> None:
        """Shutdown the async operation manager.
        
        Args:
            wait: Whether to wait for ongoing tasks to complete
        """
        logger.info("Shutting down AsyncOperationManager")
        self.shutting_down = True
        
        # Cancel all running tasks if not waiting
        if not wait:
            for task_id, task in self.tasks.items():
                if not task.done():
                    logger.warning(f"Cancelling task {task_id}")
                    task.cancel()
        
        # Wait for tasks to complete if requested
        if wait and self.tasks:
            pending_tasks = [task for task in self.tasks.values() if not task.done()]
            if pending_tasks:
                logger.info(f"Waiting for {len(pending_tasks)} tasks to complete")
                await anyio.gather(*pending_tasks, return_exceptions=True)
        
        # Shutdown thread pools
        self.io_pool.shutdown(wait=wait)
        self.compute_pool.shutdown(wait=wait)
        self.general_pool.shutdown(wait=wait)
        
        logger.info("AsyncOperationManager shutdown complete")


class AsyncParquetCIDCache:
    """Async-compatible wrapper for ParquetCIDCache.
    
    This class provides an async-compatible interface to the ParquetCIDCache,
    allowing it to be used with asyncio-based applications. It wraps a standard
    ParquetCIDCache instance and provides async versions of all operations.
    """
    
    def __init__(self, cache_instance: Any, async_manager: Optional[AsyncOperationManager] = None):
        """Initialize the async cache wrapper.
        
        Args:
            cache_instance: The ParquetCIDCache instance to wrap
            async_manager: Optional async operation manager to use
        """
        self.cache = cache_instance
        self.async_manager = async_manager or AsyncOperationManager()
        
        logger.info(f"AsyncParquetCIDCache initialized with {type(cache_instance).__name__}")
    
    async def get(self, 
                cid: str, 
                columns: Optional[List[str]] = None, 
                filters: Optional[List[Tuple]] = None) -> Optional[pa.Table]:
        """Asynchronously get data for a CID from the cache.
        
        Args:
            cid: The content identifier to retrieve
            columns: Optional list of columns to retrieve
            filters: Optional list of filters to apply
            
        Returns:
            Arrow Table with the retrieved data or None if not found
        """
        return await self.async_manager.async_get(self.cache, cid, columns, filters)
    
    async def put(self, 
                cid: str, 
                table: pa.Table, 
                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Asynchronously store data for a CID in the cache.
        
        Args:
            cid: The content identifier to store
            table: Arrow Table with the data to store
            metadata: Optional metadata to store with the data
            
        Returns:
            Boolean indicating success
        """
        return await self.async_manager.async_put(self.cache, cid, table, metadata)
    
    async def delete(self, cid: str) -> bool:
        """Asynchronously delete a CID from the cache.
        
        Args:
            cid: The content identifier to delete
            
        Returns:
            Boolean indicating success
        """
        return await self.async_manager.async_delete(self.cache, cid)
    
    async def query(self, 
                   filters: List[Tuple], 
                   columns: Optional[List[str]] = None,
                   limit: Optional[int] = None) -> pa.Table:
        """Asynchronously query the cache.
        
        Args:
            filters: List of filter conditions to apply
            columns: Optional list of columns to retrieve
            limit: Optional maximum number of results to return
            
        Returns:
            Arrow Table with the query results
        """
        return await self.async_manager.async_query(self.cache, filters, columns, limit)
    
    async def contains(self, cid: str) -> bool:
        """Asynchronously check if a CID is in the cache.
        
        Args:
            cid: The content identifier to check
            
        Returns:
            Boolean indicating if the CID is in the cache
        """
        return await self.async_manager.async_contains(self.cache, cid)
    
    async def get_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Asynchronously get metadata for a CID.
        
        Args:
            cid: The content identifier to get metadata for
            
        Returns:
            Dictionary with metadata or None if not found
        """
        return await self.async_manager.async_get_metadata(self.cache, cid)
    
    async def update_metadata(self, 
                            cid: str, 
                            metadata: Dict[str, Any], 
                            merge: bool = True) -> bool:
        """Asynchronously update metadata for a CID.
        
        Args:
            cid: The content identifier to update metadata for
            metadata: New metadata to store
            merge: Whether to merge with existing metadata or replace
            
        Returns:
            Boolean indicating success
        """
        return await self.async_manager.async_update_metadata(self.cache, cid, metadata, merge)
    
    async def batch_get(self, items: List[Dict[str, str]]) -> List[Optional[pa.Table]]:
        """Asynchronously get multiple items from the cache.
        
        Args:
            items: List of dictionaries with "cid" and optionally "columns" and "filters"
            
        Returns:
            List of Arrow Tables or None values in the same order as the input
        """
        return await self.async_manager.async_batch("get", items, self.cache)
    
    async def batch_put(self, items: List[Dict[str, Any]]) -> List[bool]:
        """Asynchronously store multiple items in the cache.
        
        Args:
            items: List of dictionaries with "cid", "table", and optionally "metadata"
            
        Returns:
            List of success booleans in the same order as the input
        """
        return await self.async_manager.async_batch("put", items, self.cache)
    
    async def batch_delete(self, cids: List[str]) -> List[bool]:
        """Asynchronously delete multiple CIDs from the cache.
        
        Args:
            cids: List of content identifiers to delete
            
        Returns:
            List of success booleans in the same order as the input
        """
        items = [{"cid": cid} for cid in cids]
        return await self.async_manager.async_batch("delete", items, self.cache)
    
    async def stats(self) -> Dict[str, Any]:
        """Get statistics about the async cache operations.
        
        Returns:
            Dictionary with operation statistics
        """
        return await self.async_manager.async_get_stats()
    
    async def close(self) -> None:
        """Close the async cache and clean up resources."""
        await self.async_manager.shutdown(wait=True)
        
        # Call sync close method if it exists
        if hasattr(self.cache, 'close') and callable(self.cache.close):
            # Run in executor to avoid blocking
            await anyio.get_event_loop().run_in_executor(None, self.cache.close)
    
    # Context manager support
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Utility functions for working with async caches
async def async_cache_get_or_create(
    cache: AsyncParquetCIDCache,
    cid: str,
    creator_func: Callable[[], Tuple[pa.Table, Dict[str, Any]]],
    max_age_seconds: Optional[float] = None
) -> pa.Table:
    """Get a value from the cache or create it if not present or too old.
    
    Args:
        cache: The async cache instance
        cid: The content identifier to retrieve
        creator_func: Function to call to create the value if not in cache
        max_age_seconds: Maximum age of cached value before recreation
        
    Returns:
        The cached or newly created value
    """
    # Try to get from cache first
    metadata = await cache.get_metadata(cid)
    
    # Check if we need to recreate
    need_create = False
    if metadata is None:
        need_create = True
    elif max_age_seconds is not None:
        created_time = metadata.get("created_at", 0)
        age = time.time() - created_time
        if age > max_age_seconds:
            need_create = True
    
    if need_create:
        # Run creator function in a thread to avoid blocking
        loop = anyio.get_event_loop()
        table, meta = await loop.run_in_executor(None, creator_func)
        
        # Add creation timestamp if not present
        if "created_at" not in meta:
            meta["created_at"] = time.time()
        
        # Store in cache
        await cache.put(cid, table, meta)
        return table
    
    # Get from cache
    return await cache.get(cid)