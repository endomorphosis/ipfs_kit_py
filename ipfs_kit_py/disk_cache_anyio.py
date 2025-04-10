import os
import time
import json
import logging
import hashlib
import math
import threading
import shutil
import uuid
import functools
from typing import Dict, Any, Optional, Tuple, List, Union, Callable, TypeVar

try:
    import anyio
    has_async = True
except ImportError:
    has_async = False

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    has_pyarrow = True
except ImportError:
    has_pyarrow = False

from concurrent.futures import ThreadPoolExecutor

from .api_stability import experimental_api, beta_api, stable_api

logger = logging.getLogger(__name__)

# Type variable for return values
T = TypeVar('T')

class DiskCacheAnyIO:
    """Disk-based persistent cache for IPFS content with AnyIO support.

    This cache stores content on disk with proper indexing and size management.
    It uses a simple directory structure with content-addressed files.
    """

    def __init__(self, directory: str = "~/.ipfs_cache", size_limit: int = 1 * 1024 * 1024 * 1024):
        """Initialize the disk cache.

        Args:
            directory: Directory to store cached files
            size_limit: Maximum size of the cache in bytes (default: 1GB)
        """
        self.directory = os.path.expanduser(directory)
        self.size_limit = size_limit
        self.index_file = os.path.join(self.directory, "cache_index.json")
        self.metadata_dir = os.path.join(self.directory, "metadata")
        self.index = {}
        self.current_size = 0
        self._metadata = {}  # Internal metadata storage

        # Create cache directories if they don't exist
        os.makedirs(self.directory, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)

        # Load existing index
        self._load_index()

        # Verify cache integrity
        self._verify_cache()

        # Initialize thread pool for concurrent operations
        self.thread_pool = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
        
        # Check for AnyIO support
        self.has_async = has_async
        self.anyio = anyio if has_async else None
    
    @property
    def metadata(self):
        """Access to the metadata dictionary.
        
        Returns:
            Dict containing metadata for all cache entries
        """
        return self._metadata
        
    @property
    def index_path(self):
        """Path to the index file.
        
        Returns:
            String path to the index file
        """
        return self.index_file

    def _load_index(self) -> None:
        """Load the cache index from disk."""
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    # Validate index data to ensure it's a dict of dict entries
                    if isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
                        self.index = data
                        logger.debug(f"Loaded cache index with {len(self.index)} entries")
                    else:
                        logger.warning(f"Invalid cache index format - creating new index")
                        self.index = {}
            else:
                self.index = {}
                logger.debug("No existing cache index found, creating new one")
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
            self.index = {}

    def _save_index(self) -> None:
        """Save the cache index to disk."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(self.index, f)
        except Exception as e:
            logger.error(f"Error saving cache index: {e}")

    def _ensure_async_environment(self) -> bool:
        """Checks if we're in an environment where async operations can be performed.
        
        Returns:
            bool: True if async operations are supported, False otherwise
        """
        if not self.has_async:
            return False  # AnyIO not available
            
        # In anyio, there's no need to explicitly create or manage event loops
        # as it handles that automatically based on the backend being used
        return True

    @experimental_api(since="0.19.0")
    def async_batch_get_metadata(self, cids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_get_metadata.
        
        Asynchronously retrieve metadata for multiple CIDs in a batch operation for improved efficiency.
        This method builds on the batch_get_metadata functionality but is non-blocking.
        
        Args:
            cids: List of CIDs to retrieve metadata for
            
        Returns:
            Dictionary mapping CIDs to their metadata
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.batch_get_metadata, cids)
            return future.result()
            
        async def _async_impl():
            # This implementation delegates to the batch version but in a non-blocking way
            # AnyIO automatically handles running in a thread
            return await anyio.to_thread.run_sync(self.batch_get_metadata, cids)
            
        # We always return an awaitable with anyio
        return anyio.create_task(_async_impl())
        
    @experimental_api(since="0.19.0")
    def async_batch_put_metadata(self, metadata_dict: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Async version of batch_put_metadata.
        
        Asynchronously store metadata for multiple CIDs in a batch operation for improved efficiency.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
            
        Returns:
            Dictionary mapping CIDs to success status
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.batch_put_metadata, metadata_dict)
            return future.result()
            
        async def _async_impl():
            # Run in a thread to avoid blocking
            return await anyio.to_thread.run_sync(self.batch_put_metadata, metadata_dict)
            
        # We always return an awaitable with anyio
        return anyio.create_task(_async_impl())
    
    @experimental_api(since="0.19.0")
    async def async_optimize_compression_settings(self, adaptive: bool = True) -> Dict[str, Any]:
        """Async version of optimize_compression_settings.
        
        Args:
            adaptive: If True, uses system resource information to adapt settings
            
        Returns:
            Dictionary with optimization results
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.optimize_compression_settings, adaptive)
            return future.result()
            
        # If anyio is available, run in thread to avoid blocking
        return await anyio.to_thread.run_sync(
            self.optimize_compression_settings, 
            adaptive
        )
    
    @experimental_api(since="0.19.0")
    async def async_optimize_batch_operations(self, content_type_aware: bool = True) -> Dict[str, Any]:
        """Async version of optimize_batch_operations.
        
        Args:
            content_type_aware: Whether to enable content type-specific optimizations
            
        Returns:
            Dictionary with optimization results
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.optimize_batch_operations, content_type_aware)
            return future.result()
            
        # If anyio is available, run in thread to avoid blocking
        return await anyio.to_thread.run_sync(
            self.optimize_batch_operations, 
            content_type_aware
        )
    
    @experimental_api(since="0.19.0")
    async def async_batch_prefetch(self, cids: List[str], metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """Async version of batch_prefetch.
        
        Asynchronously prefetch multiple CIDs with content-type optimizations and parallel processing.
        
        Args:
            cids: List of CIDs to prefetch
            metadata: Optional metadata for each CID to optimize prefetching strategy
            
        Returns:
            Dictionary with prefetch operation results
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.batch_prefetch, cids, metadata)
            return future.result()
            
        # If anyio is available, use parallel processing
        try:
            # Determine if we have content type awareness
            has_content_types = (hasattr(self, "content_type_registry") and 
                               self.content_type_registry and 
                               hasattr(self, "detect_content_type") and
                               hasattr(self, "optimize_batch"))
                               
            # Initialize result structure
            result = {
                "success": True,
                "operation": "async_batch_prefetch",
                "timestamp": time.time(),
                "total_cids": len(cids),
                "prefetched": 0,
                "skipped": 0,
                "failed": 0,
                "content_types": {},
                "results": {}
            }
            
            # Get or create metadata dict
            if metadata is None and hasattr(self, 'in_memory_batch') and self.in_memory_batch is not None and has_pyarrow:
                try:
                    metadata = {}
                    table = pa.Table.from_batches([self.in_memory_batch])
                    for row in table.to_pylist():
                        cid = row.get('cid')
                        if cid and cid in cids:
                            metadata[cid] = row
                except Exception as e:
                    logger.warning(f"Failed to extract metadata from in-memory batch: {e}")
                    metadata = {}
            
            # Group by content type if possible
            if has_content_types and metadata:
                # Use optimize_batch to group by content type
                batches = self.optimize_batch(cids, metadata)
            else:
                # Use a single default batch if no content type awareness
                batches = {"default": cids}
                
            # Process each content type in parallel
            async def process_content_type(content_type, batch_cids):
                if not batch_cids:
                    return content_type, {}
                    
                # Get optimization settings for this content type
                batch_settings = (self.batch_optimizations.get(content_type, {}) 
                               if hasattr(self, "batch_optimizations") else {})
                               
                # Default settings if not found
                prefetch_strategy = batch_settings.get("prefetch_strategy", "content_first")
                max_concurrent = batch_settings.get("batch_size", 20)
                
                # Stats for this type
                type_stats = {
                    "count": len(batch_cids),
                    "prefetched": 0,
                    "skipped": 0,
                    "failed": 0,
                    "strategy": prefetch_strategy
                }
                
                # Create a semaphore to limit concurrency
                semaphore = anyio.Semaphore(max_concurrent)
                
                # Create a function to process each CID
                async def process_cid(cid):
                    async with semaphore:
                        # Run prefetch in thread pool to avoid blocking
                        return await anyio.to_thread.run_sync(
                            self.prefetch,
                            cid
                        )
                
                # Process all CIDs concurrently with controlled parallelism
                tasks = []
                results = []
                
                # Use task group for parallel processing
                async with anyio.create_task_group() as tg:
                    for cid in batch_cids:
                        if hasattr(self, 'memory_cache') and self.memory_cache.contains(cid):
                            # Skip if already in memory
                            type_stats["skipped"] += 1
                            result["results"][cid] = {"status": "skipped", "reason": "already_in_memory"}
                        else:
                            # Start task for this CID
                            tasks.append(cid)
                            tg.start_soon(lambda c=cid: results.append((c, process_cid(c))))
                
                # Process results
                if tasks:
                    # Ensure all results are ready
                    processed_results = []
                    for cid, task_result in results:
                        try:
                            prefetch_result = await task_result
                            processed_results.append((cid, prefetch_result))
                        except Exception as e:
                            processed_results.append((cid, e))
                    
                    # Process results
                    for cid, prefetch_result in processed_results:
                        # Skip if we already marked it as skipped
                        if cid in result["results"] and result["results"][cid].get("status") == "skipped":
                            continue
                            
                        if isinstance(prefetch_result, Exception):
                            # Handle exception
                            type_stats["failed"] += 1
                            result["results"][cid] = {
                                "status": "error",
                                "error": str(prefetch_result),
                                "error_type": type(prefetch_result).__name__
                            }
                        else:
                            # Store result
                            result["results"][cid] = prefetch_result
                            
                            if prefetch_result.get("success", False):
                                type_stats["prefetched"] += 1
                            else:
                                type_stats["failed"] += 1
                
                return content_type, type_stats
            
            # Process all content types in parallel
            content_type_results = []
            
            async with anyio.create_task_group() as tg:
                # Start processing each content type
                for content_type, batch_cids in batches.items():
                    tg.start_soon(
                        lambda ct=content_type, bc=batch_cids: 
                            content_type_results.append(process_content_type(ct, bc))
                    )
            
            # Wait for all task results
            resolved_results = []
            for task_result in content_type_results:
                resolved_results.append(await task_result)
            
            # Process results
            for content_type, type_stats in resolved_results:
                if type_stats:  # Skip empty results
                    result["content_types"][content_type] = type_stats
                    
                    # Update totals
                    result["prefetched"] += type_stats["prefetched"]
                    result["skipped"] += type_stats["skipped"]
                    result["failed"] += type_stats["failed"]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in async batch prefetch: {e}")
            return {
                "success": False,
                "operation": "async_batch_prefetch",
                "timestamp": time.time(),
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    @experimental_api(since="0.19.0")
    async def async_batch_get_metadata_zero_copy(self, cids: List[str]) -> Dict[str, Any]:
        """Async version of batch_get_metadata_zero_copy.
        
        Args:
            cids: List of CIDs to retrieve metadata for
            
        Returns:
            Dictionary with results and metadata
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.batch_get_metadata_zero_copy, cids)
            return future.result()
            
        # If anyio is available, run in thread to avoid blocking
        return await anyio.to_thread.run_sync(
            self.batch_get_metadata_zero_copy,
            cids
        )
        
    @experimental_api(since="0.19.0")
    async def async_batch_put_metadata_zero_copy(self, metadata_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Async version of batch_put_metadata_zero_copy.
        
        This method provides a non-blocking way to update metadata for multiple CIDs using
        shared memory and the Arrow C Data Interface, ideal for high-throughput asynchronous
        workflows.
        
        Args:
            metadata_dict: Dictionary mapping CIDs to their metadata
            
        Returns:
            Dictionary with operation results
        """
        if not self.has_async:
            # Fallback to synchronous version through thread pool if anyio not available
            future = self.thread_pool.submit(self.batch_put_metadata_zero_copy, metadata_dict)
            return future.result()
            
        # If anyio is available, run in thread to avoid blocking
        return await anyio.to_thread.run_sync(
            self.batch_put_metadata_zero_copy,
            metadata_dict
        )