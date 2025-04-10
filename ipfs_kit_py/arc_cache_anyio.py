# This file contains AnyIO-compatible async methods for the ARCache
# It's meant to be imported and used alongside the main arc_cache.py implementation

import logging
import time
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple, Callable, TypeVar, Union

try:
    import anyio
    has_async = True
except ImportError:
    has_async = False

try:
    import pyarrow as pa
    import pyarrow.compute as pc
    has_pyarrow = True
except ImportError:
    has_pyarrow = False

logger = logging.getLogger(__name__)

# Type variable for return values
T = TypeVar('T')

class ARCacheAnyIO:
    """AnyIO-compatible extension for ARCache.
    
    This class provides AnyIO-based async alternatives to the asyncio methods in ARCache.
    It's designed to be used as a mixin or by copying these methods into ARCache.
    """

    async def _run_in_thread_pool(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run a function in the thread pool using AnyIO.
        
        Args:
            func: Function to run
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the function
        """
        # Use anyio's to_thread.run_sync for thread pool execution
        return await anyio.to_thread.run_sync(
            lambda: func(*args, **kwargs)
        )

    async def async_contains(self, cid: str) -> bool:
        """Async version of contains using AnyIO.
        
        Args:
            cid: CID to check
            
        Returns:
            True if CID is in cache, False otherwise
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.contains, cid)
                return future.result()
            else:
                return self.contains(cid)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(self.contains, cid)

    async def async_get_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Async version of get_metadata using AnyIO.
        
        Args:
            cid: CID to get metadata for
            
        Returns:
            Dictionary with metadata for the CID or None if not found
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.get_metadata, cid)
                return future.result()
            else:
                return self.get_metadata(cid)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(self.get_metadata, cid)

    async def async_put_metadata(self, cid: str, metadata: Dict[str, Any]) -> bool:
        """Async version of put_metadata using AnyIO.
        
        Args:
            cid: CID to store metadata for
            metadata: Metadata to store
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.put_metadata, cid, metadata)
                return future.result()
            else:
                return self.put_metadata(cid, metadata)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(
            lambda: self.put_metadata(cid, metadata)
        )

    async def async_batch_put_metadata(self, cid_metadata_map: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Async version of batch_put_metadata using AnyIO.
        
        This method provides a non-blocking way to store metadata for multiple CIDs
        in a single batch operation, ideal for high-throughput asynchronous workflows.
        
        Args:
            cid_metadata_map: Dictionary mapping CIDs to metadata
            
        Returns:
            Dictionary mapping CIDs to success status (True if stored successfully)
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.batch_put_metadata, cid_metadata_map)
                return future.result()
            else:
                return self.batch_put_metadata(cid_metadata_map)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(
            lambda: self.batch_put_metadata(cid_metadata_map)
        )

    async def async_batch_get_metadata(self, cids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Async version of batch_get_metadata using AnyIO.
        
        This method provides a non-blocking way to retrieve metadata for multiple CIDs
        in a single batch operation, ideal for high-throughput asynchronous workflows.
        
        Args:
            cids: List of CIDs to get metadata for
            
        Returns:
            Dictionary mapping CIDs to their metadata (None for CIDs not found)
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.batch_get_metadata, cids)
                return future.result()
            else:
                return self.batch_get_metadata(cids)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(
            lambda: self.batch_get_metadata(cids)
        )

    async def async_disk_operations(self, needs_rotation: bool) -> None:
        """Perform asynchronous disk operations.
        
        Args:
            needs_rotation: Whether to rotate partition files
        """
        try:
            # Perform operations in thread pool
            if needs_rotation:
                # Rotate and persist
                await anyio.to_thread.run_sync(self._rotate_and_persist_partition)
                # Update last sync time
                self.last_sync_time = time.time()
            elif hasattr(self, 'auto_sync') and self.auto_sync:
                # Just sync
                await anyio.to_thread.run_sync(self.sync)
        except Exception as e:
            logger.error(f"Error in async disk operations: {e}")

    async def async_sync(self) -> bool:
        """Async version of sync using AnyIO.
        
        Asynchronously persist the current state to disk.
        
        Returns:
            True if sync was successful, False otherwise
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.sync)
                return future.result()
            else:
                return self.sync()
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(self.sync)

    async def async_query(self, filters: List[Tuple[str, str, Any]] = None, 
                         columns: List[str] = None,
                         sort_by: str = None,
                         limit: int = None,
                         parallel: bool = False,
                         max_workers: int = None) -> Dict[str, Any]:
        """Async version of query using AnyIO.
        
        Args:
            filters: List of filter tuples in format (field, op, value)
            columns: List of columns to return
            sort_by: Column to sort by
            limit: Maximum number of results to return
            parallel: Whether to use parallel execution for query
            max_workers: Number of workers for parallel execution
            
        Returns:
            Dictionary with query results
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(
                    self.query, filters, columns, sort_by, limit, parallel, max_workers
                )
                return future.result()
            else:
                return self.query(filters, columns, sort_by, limit, parallel, max_workers)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(
            lambda: self.query(filters, columns, sort_by, limit, parallel, max_workers)
        )

    async def async_parallel_query(self, filters: List[Tuple[str, str, Any]] = None,
                                  columns: List[str] = None,
                                  sort_by: str = None,
                                  limit: int = None,
                                  max_workers: int = None) -> Dict[str, Any]:
        """Async version of parallel_query using AnyIO.
        
        Args:
            filters: List of filter tuples in format (field, op, value)
            columns: List of columns to return
            sort_by: Column to sort by
            limit: Maximum number of results to return
            max_workers: Number of workers for parallel execution
            
        Returns:
            Dictionary with query results
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(
                    self.parallel_query, filters, columns, sort_by, limit, max_workers
                )
                return future.result()
            else:
                return self.parallel_query(filters, columns, sort_by, limit, max_workers)
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(
            lambda: self.parallel_query(filters, columns, sort_by, limit, max_workers)
        )

    async def async_batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_prefetch using AnyIO.
        
        Args:
            cids: List of CIDs to prefetch
            metadata: Optional metadata for the CIDs
            
        Returns:
            Dictionary mapping CIDs to their prefetch results
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.batch_prefetch, cids, metadata)
                return future.result()
            else:
                return self.batch_prefetch(cids, metadata)
        
        # Initialize results
        results = {
            "success": True,
            "operation": "async_batch_prefetch",
            "timestamp": time.time(),
            "total": len(cids),
            "prefetched": 0,
            "skipped": 0,
            "failed": 0,
            "results": {},
            "content_types": {}
        }
        
        # Group by content type if possible
        content_type_batches = {}
        
        if metadata and hasattr(self, 'detect_content_type'):
            # Detect content type for each CID
            for cid in cids:
                cid_metadata = metadata.get(cid, {})
                content_type = self.detect_content_type(cid, cid_metadata)
                
                if content_type not in content_type_batches:
                    content_type_batches[content_type] = []
                    
                content_type_batches[content_type].append(cid)
                
            # Update stats
            results["content_types"] = {
                content_type: {"count": len(batch)}
                for content_type, batch in content_type_batches.items()
            }
        else:
            # Single batch with default content type
            content_type_batches["default"] = cids
            results["content_types"] = {"default": {"count": len(cids)}}
            
        # Process each content type in parallel
        processed_results = {}
        
        # Use a task group to process all content types concurrently
        async with anyio.create_task_group() as tg:
            # For each content type
            for content_type, type_cids in content_type_batches.items():
                if not type_cids:
                    continue
                    
                if content_type == "parquet":
                    # Create task for Parquet batch processing
                    tg.start_soon(
                        self._async_prefetch_content_type, 
                        "parquet",
                        type_cids,
                        metadata,
                        processed_results
                    )
                elif content_type == "arrow":
                    # Create task for Arrow batch processing
                    tg.start_soon(
                        self._async_prefetch_content_type,
                        "arrow",
                        type_cids,
                        metadata,
                        processed_results
                    )
                else:
                    # Process each CID individually
                    for cid in type_cids:
                        cid_metadata = metadata.get(cid) if metadata else None
                        tg.start_soon(
                            self._async_prefetch_single_cid,
                            cid,
                            cid_metadata,
                            processed_results
                        )
        
        # Process results
        for cid, result in processed_results.items():
            results["results"][cid] = result
            
            if isinstance(result, Exception):
                results["failed"] += 1
                results["results"][cid] = {
                    "success": False,
                    "error": str(result),
                    "error_type": type(result).__name__
                }
            elif result.get("status") == "skipped":
                results["skipped"] += 1
            elif result.get("success", False):
                results["prefetched"] += 1
            else:
                results["failed"] += 1
                
        return results
    
    async def _async_prefetch_content_type(self, content_type, cids, metadata, results_dict):
        """Process a batch of CIDs of the same content type."""
        try:
            if content_type == "parquet":
                batch_results = await self._async_batch_prefetch_parquet(cids, metadata)
            elif content_type == "arrow":
                batch_results = await self._async_batch_prefetch_arrow(cids, metadata)
            else:
                batch_results = {}
                
            # Add results to the shared results dictionary
            for cid, result in batch_results.items():
                results_dict[cid] = result
        except Exception as e:
            # Mark all as failed
            for cid in cids:
                results_dict[cid] = e
    
    async def _async_prefetch_single_cid(self, cid, metadata, results_dict):
        """Process a single CID for prefetching."""
        try:
            result = await self._async_prefetch_content(cid, metadata)
            results_dict[cid] = result
        except Exception as e:
            results_dict[cid] = e

    async def _async_prefetch_content(self, cid: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Async implementation of prefetch_content."""
        try:
            # If already in cache, skip
            if hasattr(self, 'contains') and self.contains(cid):
                return {"status": "skipped", "reason": "already_in_cache"}
                
            # Add to in-progress set
            if hasattr(self, 'prefetch_in_progress'):
                self.prefetch_in_progress.add(cid)
                
            # Run actual prefetch in thread pool
            return await anyio.to_thread.run_sync(
                lambda: self.prefetch_content(cid, metadata)
            )
        finally:
            # Remove from in-progress set
            if hasattr(self, 'prefetch_in_progress'):
                self.prefetch_in_progress.discard(cid)

    async def _async_batch_prefetch_parquet(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async implementation of batch prefetch for Parquet files."""
        try:
            # For now, delegate to thread pool
            # In a future implementation, this could be fully async with native async Parquet support
            return await anyio.to_thread.run_sync(
                lambda: self._batch_prefetch_parquet(cids, metadata) if hasattr(self, '_batch_prefetch_parquet') else {}
            )
        finally:
            # Clean up in-progress set
            if hasattr(self, 'prefetch_in_progress'):
                for cid in cids:
                    self.prefetch_in_progress.discard(cid)

    async def _async_batch_prefetch_arrow(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async implementation of batch prefetch for Arrow files."""
        try:
            # For now, delegate to thread pool
            # In a future implementation, this could be fully async with native async Arrow support
            return await anyio.to_thread.run_sync(
                lambda: self._batch_prefetch_arrow(cids, metadata) if hasattr(self, '_batch_prefetch_arrow') else {}
            )
        finally:
            # Clean up in-progress set
            if hasattr(self, 'prefetch_in_progress'):
                for cid in cids:
                    self.prefetch_in_progress.discard(cid)

    async def async_get_prefetch_stats(self) -> Dict[str, Any]:
        """Async version of get_prefetch_stats using AnyIO.
        
        Returns:
            Dictionary with prefetch statistics
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.get_prefetch_stats)
                return future.result()
            else:
                return self.get_prefetch_stats()
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(self.get_prefetch_stats)

    async def async_delete(self, cid: str) -> bool:
        """Async version of delete using AnyIO.
        
        Args:
            cid: CID to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.delete, cid)
                return future.result()
            else:
                return self.delete(cid)
        
        try:
            in_memory_matches = 0
            match_found = False
            
            if hasattr(self, 'in_memory_batch') and has_pyarrow and self.in_memory_batch is not None:
                # Create a table from the in-memory batch
                table = pa.Table.from_batches([self.in_memory_batch])
                
                # Find matching records
                mask = pc.equal(pc.field('cid'), pa.scalar(cid))
                matching = table.filter(mask)
                in_memory_matches = matching.num_rows
                
                if in_memory_matches > 0:
                    # Filter out the matching records
                    inverse_mask = pc.invert(mask)
                    filtered_table = table.filter(inverse_mask)
                    
                    # Update in-memory batch
                    if filtered_table.num_rows > 0:
                        self.in_memory_batch = filtered_table.to_batches()[0]
                    else:
                        self.in_memory_batch = None
                        
                    # Mark that we have changes that need to be synced
                    if hasattr(self, 'modified_since_sync'):
                        self.modified_since_sync = True
                    
                    match_found = True
            
            # Also look in the metadata index
            if hasattr(self, '_metadata_index') and cid in self._metadata_index:
                # Remove from metadata index
                del self._metadata_index[cid]
                match_found = True
                
            # If we made changes, persist them in the background
            if match_found and hasattr(self, 'modified_since_sync') and self.modified_since_sync:
                # Schedule background tasks for sync and C Data Interface
                if hasattr(self, 'sync'):
                    anyio.create_task(anyio.to_thread.run_sync(self.sync))
                
                # Update C Data Interface if enabled
                if hasattr(self, 'enable_c_data_interface') and self.enable_c_data_interface and hasattr(self, '_export_to_c_data_interface'):
                    anyio.create_task(anyio.to_thread.run_sync(self._export_to_c_data_interface))
            
            return in_memory_matches > 0 or match_found
            
        except Exception as e:
            logger.error(f"Error in async_delete for CID {cid}: {e}")
            return False

    async def async_get_all_cids(self) -> List[str]:
        """Async version of get_all_cids using AnyIO.
        
        Returns:
            List of all CIDs in the cache
        """
        if not has_async:
            # Fallback to thread pool if anyio not available
            if hasattr(self, 'thread_pool'):
                future = self.thread_pool.submit(self.get_all_cids)
                return future.result()
            else:
                return self.get_all_cids()
            
        # Use anyio to run in thread pool
        return await anyio.to_thread.run_sync(self.get_all_cids)