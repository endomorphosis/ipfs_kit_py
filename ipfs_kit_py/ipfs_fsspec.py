"""
FSSpec implementation for IPFS.

This module provides an FSSpec interface for IPFS, allowing interaction with
IPFS content as a filesystem. It integrates with the ipfs_kit_py library's
core IPFS client and tiered caching mechanisms.
"""

import os
import time
import logging
import io
import tempfile
from typing import Dict, List, Any, Optional, Union, Tuple, Callable, BinaryIO

# Import fsspec
import fsspec
from fsspec.spec import AbstractFileSystem
from fsspec.callbacks import DEFAULT_CALLBACK # Import DEFAULT_CALLBACK

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Track and report performance metrics for IPFS operations."""
    
    def __init__(self, enable_metrics=True):
        """
        Initialize metrics counters.
        
        Args:
            enable_metrics: Whether to enable metrics collection
        """
        self.enable_metrics = enable_metrics
        self.read_count = 0
        self.write_count = 0
        self.read_bytes = 0
        self.write_bytes = 0
        self.read_time = 0.0
        self.write_time = 0.0
        self.operation_times: Dict[str, float] = {}
        self.operation_counts: Dict[str, int] = {}
        
        # Cache metrics
        self.cache_stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0
        }
    
    def track_operation(self, operation_name: str) -> Callable:
        """
        Create a decorator to track operation timing.
        
        Args:
            operation_name: Name of the operation to track
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self.enable_metrics:
                    return func(*args, **kwargs)
                    
                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                if operation_name not in self.operation_times:
                    self.operation_times[operation_name] = 0.0
                    self.operation_counts[operation_name] = 0
                    
                self.operation_times[operation_name] += elapsed
                self.operation_counts[operation_name] += 1
                
                return result
            return wrapper
        return decorator
    
    def record_read(self, size: int, elapsed: float) -> None:
        """
        Record a read operation.
        
        Args:
            size: Number of bytes read
            elapsed: Time taken in seconds
        """
        if not self.enable_metrics:
            return
            
        self.read_count += 1
        self.read_bytes += size
        self.read_time += elapsed
    
    def record_write(self, size: int, elapsed: float) -> None:
        """
        Record a write operation.
        
        Args:
            size: Number of bytes written
            elapsed: Time taken in seconds
        """
        if not self.enable_metrics:
            return
            
        self.write_count += 1
        self.write_bytes += size
        self.write_time += elapsed
    
    def record_operation_time(self, operation_name: str, elapsed_time: float, size: int = 0) -> None:
        """
        Record time taken for a specific operation.
        
        Args:
            operation_name: Name of the operation
            elapsed_time: Time taken in seconds
            size: Size of data processed (optional)
        """
        if not self.enable_metrics:
            return
            
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = 0.0
            self.operation_counts[operation_name] = 0
            
        self.operation_times[operation_name] += elapsed_time
        self.operation_counts[operation_name] += 1
        
        # Also update read/write counters if applicable
        if operation_name == "read":
            self.record_read(size, elapsed_time)
        elif operation_name == "write":
            self.record_write(size, elapsed_time)
    
    def get_operation_stats(self, operation_name=None) -> Dict[str, Any]:
        """
        Get statistics for operations.
        
        Args:
            operation_name: Optional name of specific operation to get stats for
                            If None, returns stats for all operations
        
        Returns:
            Dictionary of operation statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        if operation_name is not None:
            if operation_name not in self.operation_counts:
                return {"count": 0, "total_time": 0.0, "mean": 0.0}
                
            count = self.operation_counts[operation_name]
            total_time = self.operation_times[operation_name]
            mean = total_time / count if count > 0 else 0.0
            
            return {
                "count": count,
                "total_time": total_time,
                "mean": mean
            }
        
        # Get stats for all operations
        result = {"total_operations": sum(self.operation_counts.values())}
        
        for op_name in self.operation_counts:
            count = self.operation_counts[op_name]
            total_time = self.operation_times[op_name]
            mean = total_time / count if count > 0 else 0.0
            
            result[op_name] = {
                "count": count,
                "total_time": total_time,
                "average_time": mean
            }
        
        return result
    
    # Cache-related methods
    
    def record_cache_access(self, access_type: str) -> None:
        """
        Record a cache access event.
        
        Args:
            access_type: Type of access ("memory_hit", "disk_hit", or "miss")
        """
        if not self.enable_metrics:
            return
            
        if access_type == "memory_hit":
            self.cache_stats["memory_hits"] += 1
        elif access_type == "disk_hit":
            self.cache_stats["disk_hits"] += 1
        elif access_type == "miss":
            self.cache_stats["misses"] += 1
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache access statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        if not self.enable_metrics:
            return {"metrics_disabled": True}
            
        memory_hits = self.cache_stats["memory_hits"]
        disk_hits = self.cache_stats["disk_hits"]
        misses = self.cache_stats["misses"]
        total = memory_hits + disk_hits + misses
        
        stats = {
            "memory_hits": memory_hits,
            "disk_hits": disk_hits,
            "misses": misses,
            "total": total
        }
        
        # Calculate rates if there are any accesses
        if total > 0:
            stats["memory_hit_rate"] = float(memory_hits) / total
            stats["disk_hit_rate"] = float(disk_hits) / total
            stats["overall_hit_rate"] = float(memory_hits + disk_hits) / total
            stats["miss_rate"] = float(misses) / total
        else:
            stats["memory_hit_rate"] = 0.0
            stats["disk_hit_rate"] = 0.0
            stats["overall_hit_rate"] = 0.0
            stats["miss_rate"] = 0.0
            
        return stats
    
    def reset(self) -> None:
        """Reset all metrics to zero."""
        self.read_count = 0
        self.write_count = 0
        self.read_bytes = 0
        self.write_bytes = 0
        self.read_time = 0.0
        self.write_time = 0.0
        self.operation_times = {}
        self.operation_counts = {}
        self.cache_stats = {
            "memory_hits": 0,
            "disk_hits": 0,
            "misses": 0
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.reset()  # Reuse existing reset method
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary of metrics
        """
        if not self.enable_metrics:
            return {"metrics_enabled": False}
            
        metrics = {
            "metrics_enabled": True,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "read_bytes": self.read_bytes,
            "write_bytes": self.write_bytes,
            "read_time": self.read_time,
            "write_time": self.write_time,
            "operations": {},
            "cache": self.get_cache_stats()
        }
        
        for op_name in self.operation_counts:
            count = self.operation_counts[op_name]
            total_time = self.operation_times[op_name]
            avg_time = total_time / count if count > 0 else 0.0
            
            metrics["operations"][op_name] = {
                "count": count,
                "total_time": total_time,
                "average_time": avg_time
            }
        
        return metrics

# Create an alias for backward compatibility
performance_metrics = PerformanceMetrics

def _strip_protocol(path: str) -> str:
    """Remove the 'ipfs://' protocol prefix if present."""
    if path.startswith("ipfs://"):
        return path[len("ipfs://"):]
    return path

def _full_path(path: str) -> str:
    """Ensure the path has the 'ipfs://' protocol prefix."""
    if not path.startswith("ipfs://"):
        return f"ipfs://{path}"
    return path

class IPFSFSSpecFileSystem(AbstractFileSystem):
    """
    FSSpec-compatible filesystem for IPFS.
    
    This implementation integrates with the ipfs_kit_py library's core IPFS client
    and tiered caching mechanisms to provide a unified interface to IPFS content.
    """
    
    protocol = "ipfs"
    
    def __init__(
        self, 
        ipfs_client: Any, # This will be an instance of ipfs_kit.ipfs_py or similar
        tiered_cache_manager: Any, # This will be an instance of TieredCacheManager
        api_addr: str = "/ip4/127.0.0.1/tcp/5001",
        role: str = "leecher",
        gateway_urls: Optional[List[str]] = None,
        gateway_only: bool = False,
        use_gateway_fallback: bool = True,
        cache_options: Optional[Dict[str, Any]] = None, # Renamed to cache_options
        enable_metrics: bool = False,
        **kwargs
    ):
        """
        Initialize the IPFS filesystem.
        
        Args:
            ipfs_client: An initialized instance of the IPFS client from ipfs_kit_py.
            tiered_cache_manager: An initialized instance of TieredCacheManager.
            api_addr: IPFS API address
            role: Node role (leecher, seeder, or full)
            gateway_urls: List of gateway URLs to use for fallback
            gateway_only: Whether to use only gateways (no local node)
            use_gateway_fallback: Whether to use gateways as fallback
            cache_options: Cache configuration options (renamed from cache_config)
            enable_metrics: Whether to enable performance metrics
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.ipfs_client = ipfs_client
        self.tiered_cache_manager = tiered_cache_manager
        self.api_addr = api_addr
        self.role = role
        self.gateway_urls = gateway_urls or ["https://ipfs.io", "https://cloudflare-ipfs.com"]
        self.gateway_only = gateway_only
        self.use_gateway_fallback = use_gateway_fallback
        self.cache_options = cache_options or {} # Renamed to cache_options
        self.enable_metrics = enable_metrics
        
        # Initialize performance metrics
        self.metrics = PerformanceMetrics(enable_metrics=enable_metrics)
        
        # Track open files
        self.open_files = {}
        
        logger.info(f"Initialized IPFS FSSpec filesystem with role: {role}")
    
    def _get_cid_from_path(self, path: str) -> str:
        """Extract CID from an IPFS path."""
        stripped_path = _strip_protocol(path)
        # Assuming path format like /ipfs/CID or CID/filename
        parts = stripped_path.split('/')
        if parts[0] == "ipfs":
            return parts[1]
        return parts[0] # Assume it's just a CID if no /ipfs/ prefix

    def ls(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """
        List directory contents.
        
        Args:
            path: IPFS path to list (can be a CID or a path like /ipfs/CID/dir)
            detail: Whether to return detailed information
            
        Returns:
            List of dictionaries with file info if detail=True,
            otherwise list of path strings
        """
        full_path = _strip_protocol(path)
        
        start_time = time.time()
        
        # Use ipfs_client.ipfs_ls_path
        ls_result = self.ipfs_client.ipfs_ls_path(full_path)
        
        if not ls_result.get("success", False):
            logger.error(f"Failed to list path {path}: {ls_result.get('error', 'Unknown error')}")
            return [] # Return empty list on failure
        
        items = []
        for item in ls_result.get("items", []):
            name = item.get("name")
            cid = item.get("hash")
            size = item.get("size")
            type_str = "directory" if item.get("type") == 1 else "file" # 0 for file, 1 for directory
            
            # Construct full path for the item
            item_path = os.path.join(path, name)
            
            if detail:
                items.append({
                    "name": _full_path(item_path),
                    "size": size,
                    "type": type_str,
                    "cid": cid
                })
            else:
                items.append(_full_path(item_path))
        
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("ls", elapsed)
        
        return items
    
    def info(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        Get info about a file/directory.
        
        Args:
            path: IPFS path
            
        Returns:
            Dictionary with file/directory info
        """
        stripped_path = _strip_protocol(path)
        
        start_time = time.time()
        
        # Use ipfs_client.files_stat for MFS paths or ipfs_client.ipfs_ls_path for DAG paths
        # For simplicity, let's assume it's a CID or a path under a CID for now,
        # and use ipfs_ls_path to get info about the specific item.
        # A more robust solution would differentiate between MFS and DAG paths.
        
        # Try to get info using ipfs_ls_path on the parent directory if it's a file within a CID
        parent_path = os.path.dirname(stripped_path)
        if not parent_path or parent_path == ".": # If it's just a CID or a file at root
            cid = self._get_cid_from_path(stripped_path)
            ls_result = self.ipfs_client.ipfs_ls_path(cid) # List the CID itself
            if ls_result.get("success", False) and ls_result.get("items"):
                # If it's a directory, the info should be about the directory itself
                # If it's a file, ipfs_ls_path on the CID will return the file's info
                item = ls_result["items"][0] # Assuming the first item is the one we want info for
                name = item.get("name")
                cid = item.get("hash")
                size = item.get("size")
                type_str = "directory" if item.get("type") == 1 else "file"
                
                result = {
                    "name": _full_path(stripped_path),
                    "size": size,
                    "type": type_str,
                    "cid": cid
                }
            else:
                # Fallback for direct CID info if ls_path doesn't work as expected for single files
                # This might require a different IPFS command like `ipfs object stat` or `ipfs dag stat`
                # For now, return a basic file info
                result = {
                    "name": _full_path(stripped_path),
                    "size": 0, # Unknown size
                    "type": "file",
                    "cid": self._get_cid_from_path(stripped_path)
                }
        else:
            # If it's a path like /ipfs/CID/dir/file.txt, we need to list the parent and find the item
            ls_result = self.ipfs_client.ipfs_ls_path(parent_path)
            found_item = None
            target_name = os.path.basename(stripped_path)
            for item in ls_result.get("items", []):
                if item.get("name") == target_name:
                    found_item = item
                    break
            
            if found_item:
                name = found_item.get("name")
                cid = found_item.get("hash")
                size = found_item.get("size")
                type_str = "directory" if found_item.get("type") == 1 else "file"
                
                result = {
                    "name": _full_path(stripped_path),
                    "size": size,
                    "type": type_str,
                    "cid": cid
                }
            else:
                logger.warning(f"Could not find info for path: {path}")
                raise FileNotFoundError(f"Path not found: {path}")
        
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("info", elapsed)
        
        return result
    
    def open(
        self, 
        path: str, 
        mode: str = "rb", 
        block_size: Optional[int] = None, 
        cache_options: Optional[Dict[str, Any]] = None, # Added cache_options
        compression: Optional[str] = None, # Added compression parameter
        **kwargs # Simplified signature to match fsspec.AbstractFileSystem.open
    ) -> "IPFSFSSpecFile":
        """
        Open a file.
        
        Args:
            path: IPFS path
            mode: File mode (rb, wb, etc.)
            block_size: Block size for reading
            cache_options: Options for caching
            compression: Compression type (e.g., 'gzip', 'lz4')
            **kwargs: Additional arguments passed to the file-like object
            
        Returns:
            File-like object
        """
        stripped_path = _strip_protocol(path)
        
        start_time = time.time()
        # Pass all relevant kwargs to the file-like object
        file = IPFSFSSpecFile(self, stripped_path, mode, block_size, compression=compression, cache_options=cache_options, **kwargs) # Pass compression, autocommit, cache_options
        self.open_files[id(file)] = file
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("open", elapsed)
        
        return file
    
    def cat(self, path: str, recursive: bool = False, on_error: str = "raise", **kwargs) -> bytes: # Added on_error parameter
        """
        Get file contents.
        
        Args:
            path: IPFS path (can be a CID or a path like /ipfs/CID/file.txt)
            recursive: Whether to retrieve directory contents recursively (ignored for files)
            on_error: How to handle errors ('raise', 'omit', 'return')
            
        Returns:
            File contents as bytes
        """
        stripped_path = _strip_protocol(path)
        cid = self._get_cid_from_path(stripped_path)
        
        # Try to get from cache first
        cached_content = self.tiered_cache_manager.get(cid)
        if cached_content:
            self.metrics.record_cache_access("memory_hit") # Assuming tiered_cache_manager handles memory/disk distinction
            return cached_content
        
        # Not in cache, fetch from IPFS
        self.metrics.record_cache_access("miss")
        start_time = time.time()
        
        # Use ipfs_client.ipfs_cat
        cat_result = self.ipfs_client.ipfs_cat(cid)
        
        if not cat_result.get("success", False):
            logger.error(f"Failed to cat content for {cid}: {cat_result.get('error', 'Unknown error')}")
            if on_error == "raise":
                raise FileNotFoundError(f"Content not found for CID: {cid}")
            elif on_error == "return":
                return cat_result.get("error", b"") # Return error message as bytes
            else: # omit
                return b"" # Return empty bytes
        
        content = cat_result.get("data", b"") # Assuming data is returned as bytes
        
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("read", elapsed, len(content))
        
        # Cache the content
        self.tiered_cache_manager.put(cid, content)
        
        return content
    
    def put(self, lpath: str, rpath: str, recursive: bool = False, callback: Optional[Any] = DEFAULT_CALLBACK, maxdepth: Optional[int] = None, **kwargs) -> None: # Added maxdepth parameter
        """
        Upload a local file to IPFS.
        
        Args:
            lpath: Local filename to upload
            rpath: Remote IPFS path to create (can be a target CID or a path like /ipfs/CID/new_file.txt)
            recursive: Whether to upload directory contents recursively
            callback: Callback for progress reporting
            maxdepth: Maximum depth for recursion (ignored for now)
            
        Returns:
            None
        """
        stripped_rpath = _strip_protocol(rpath)
        
        start_time = time.time()
        
        # Use ipfs_client.ipfs_add_path
        add_result = self.ipfs_client.ipfs_add_path(lpath, recursive=recursive) # Pass recursive
        
        if not add_result.get("success", False):
            logger.error(f"Failed to add file {lpath} to IPFS: {add_result.get('error', 'Unknown error')}")
            raise IOError(f"Failed to upload file to IPFS: {lpath}")
        
        # The CID of the added file/directory is in add_result["cid"] or add_result["files"][0].get("hash")
        # For simplicity, assume it's a single file and get the CID
        uploaded_cid = add_result.get("cid")
        if not uploaded_cid and add_result.get("files"):
            uploaded_cid = add_result["files"][0].get("hash")
            
        if not uploaded_cid:
            logger.error(f"Failed to get CID after adding file {lpath} to IPFS.")
            raise IOError(f"Failed to get CID for uploaded file: {lpath}")
            
        # If the path specified was a target path within an existing CID,
        # this would involve `ipfs files cp` or similar MFS operations.
        # For now, we assume `rpath` is just a placeholder or the target CID.
        
        # Record metrics for the operation
        size = os.path.getsize(lpath) if os.path.exists(lpath) else 0
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("write", elapsed, size)
        
        # Cache the content if it was a file
        try:
            with open(lpath, "rb") as f:
                content = f.read()
            self.tiered_cache_manager.put(uploaded_cid, content)
        except Exception as e:
            logger.warning(f"Failed to cache uploaded file {lpath} with CID {uploaded_cid}: {e}")
            
        # fsspec.put returns None
        return None
    
    def rm(self, path: str, recursive: bool = False, maxdepth: Optional[int] = None) -> None: # Added maxdepth parameter
        """
        Remove a file/directory from IPFS.
        
        Args:
            path: IPFS path to remove (can be a CID or a path like /ipfs/CID/dir)
            recursive: Whether to remove recursively
            maxdepth: Maximum depth for recursion (ignored for now)
        """
        stripped_path = _strip_protocol(path)
        cid_or_path = stripped_path # Can be a CID or an MFS path
        
        start_time = time.time()
        
        # Use ipfs_client.ipfs_remove_path or ipfs_client.ipfs_pin_rm
        # If it's a CID, we assume it means unpinning.
        # If it's an MFS path, we use ipfs_remove_path.
        
        # Simple heuristic: if it looks like a CID, try unpinning. Otherwise, try removing path.
        # A more robust solution would check if it's an MFS path vs a DAG path.
        if cid_or_path.startswith("Qm") or cid_or_path.startswith("ba"): # Basic CID check
            rm_result = self.ipfs_client.ipfs_pin_rm(cid_or_path, recursive=recursive)
        else:
            rm_result = self.ipfs_client.ipfs_remove_path(cid_or_path)
            
        if not rm_result.get("success", False):
            logger.error(f"Failed to remove {path} from IPFS: {rm_result.get('error', 'Unknown error')}")
            raise IOError(f"Failed to remove {path} from IPFS.")
            
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("remove", elapsed)
        
        # Invalidate cache for the removed item
        self.tiered_cache_manager.delete(self._get_cid_from_path(path))
    
    def close(self) -> None:
        """Close the filesystem and release resources."""
        for file_id, file in list(self.open_files.items()):
            file.close()
            del self.open_files[id(file)]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for this filesystem.
        
        Returns:
            Dictionary of performance metrics
        """
        return self.metrics.get_metrics() if self.enable_metrics else {"metrics_enabled": False}

class IPFSFSSpecFile(fsspec.spec.AbstractBufferedFile):
    """FSSpec-compatible file-like object for IPFS content."""
    
    def __init__(
        self, 
        fs: IPFSFSSpecFileSystem, 
        path: str, 
        mode: str = "rb", 
        block_size: Union[int, str] = "default", # Changed type hint to Union[int, str]
        **kwargs # Simplified signature to match fsspec.spec.AbstractBufferedFile
    ):
        """
        Initialize the file.
        
        Args:
            fs: Parent filesystem
            path: IPFS path (stripped of protocol)
            mode: File mode
            block_size: Block size for reading/writing ('default' or int)
            **kwargs: Additional arguments passed to the superclass
        """
        # Handle block_size being None
        if block_size is None:
            block_size = "default"
            
        super().__init__(fs, path, mode, block_size, **kwargs) # type: ignore # Pass block_size directly
        self.cid = self.fs._get_cid_from_path(path)
        self._content_buffer = io.BytesIO() # Buffer for read/write operations
        self._current_pos = 0 # Current position in the logical file
        
        if "r" in mode:
            # For read mode, fetch content and load into buffer
            try:
                content = self.fs.cat(self.path)
                self._content_buffer.write(content)
                self._content_buffer.seek(0) # Reset to beginning for reading
            except FileNotFoundError:
                logger.error(f"File not found for reading: {self.path}")
                raise
        elif "w" in mode or "a" in mode:
            # For write/append mode, buffer writes locally
            pass # Buffer is empty initially
        
        logger.debug(f"Opened IPFSFSSpecFile: {self.path} in mode {self.mode}")

    def _fetch_range(self, start: int, end: int) -> bytes:
        """
        Fetch a specific byte range from the IPFS content.
        This is a simplified implementation for demonstration.
        A real implementation might use `ipfs get --offset --length` or similar.
        """
        # For now, we'll just cat the whole file and slice it.
        # This is inefficient for large files but works for demonstration.
        full_content = self.fs.cat(self.path)
        return full_content[start:end]

    def _read_chunk(self, offset: int) -> bytes:
        """
        Read a chunk of data from the file, starting at offset.
        This method is called by fsspec's AbstractBufferedFile.
        """
        # Determine the size of the chunk to read
        chunk_size = int(self.blocksize) # Access block_size from superclass and cast to int
        
        # Fetch the content from IPFS (or cache)
        # For simplicity, we'll re-cat the whole file and slice.
        # In a real scenario, for large files, you'd want to implement
        # range requests if the IPFS client supports it efficiently.
        try:
            full_content = self.fs.cat(self.path)
            data = full_content[offset : offset + chunk_size]
            logger.debug(f"Read chunk from {self.path}: offset={offset}, size={len(data)}")
            return data
        except Exception as e:
            logger.error(f"Error reading chunk from {self.path} at offset {offset}: {e}")
            raise IOError(f"Error reading data from IPFS: {e}")

    def _upload_chunk(self, final: bool = False) -> None: # Corrected signature to match fsspec.AbstractBufferedFile
        """
        Upload a chunk of data to the file.
        This method is called by fsspec's AbstractBufferedFile when writing.
        """
        if not self.buffer.tell():
            return # Nothing to write
            
        self.buffer.seek(0)
        data_to_write = self.buffer.read()
        self.buffer.seek(0) # Reset buffer for next write
        self.buffer.truncate(0)
        
        # In a real IPFS write, you'd typically add the whole file at once
        # or use MFS operations to append/modify.
        # For simplicity, this mock assumes we're writing the whole file on final commit.
        # For chunked writes, a more complex MFS or DAG-building strategy would be needed.
        
        # For now, we'll just store the data in the _content_buffer
        # and only commit to IPFS on close/flush.
        self._content_buffer.write(data_to_write) # Write the data from self.buffer
        logger.debug(f"Buffered {len(data_to_write)} bytes for {self.path}. Final: {final}")
        
        if final:
            self.flush() # Force flush on final chunk

    def flush(self, force: bool = False) -> None:
        """
        Flush the buffer to the underlying storage.
        For write mode, this means adding the content to IPFS.
        """
        if self.closed:
            raise ValueError("Stream is closed")
        if "w" not in self.mode and "a" not in self.mode:
            return # Not in write mode
            
        if not force and not self.autocommit:
            return # Only flush on explicit force or autocommit
            
        self._content_buffer.seek(0)
        content_to_upload = self._content_buffer.read()
        
        if not content_to_upload:
            logger.debug(f"No content to flush for {self.path}")
            return
            
        logger.debug(f"Flushing {len(content_to_upload)} bytes to IPFS for {self.path}")
        
        # Create a temporary file to pass to ipfs_add_path
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(content_to_upload)
            tmp_file_path = tmp_file.name
        
        try:
            # Use ipfs_client.ipfs_add_path to add the content
            # This will return a new CID for the content
            add_result = self.fs.ipfs_client.ipfs_add_path(tmp_file_path)
            
            if not add_result.get("success", False):
                logger.error(f"Failed to flush content for {self.path}: {add_result.get('error', 'Unknown error')}")
                raise IOError(f"Failed to write data to IPFS: {self.path}")
            
            new_cid = add_result.get("cid")
            if not new_cid and add_result.get("files"):
                new_cid = add_result["files"][0].get("hash")
            
            if not new_cid:
                logger.error(f"Failed to get CID after flushing content for {self.path}.")
                raise IOError(f"Failed to get CID for flushed content: {self.path}")
            
            logger.info(f"Flushed {self.path} to IPFS with new CID: {new_cid}")
            self.cid = new_cid # Update CID if content changed
            
            # Update cache
            self.fs.tiered_cache_manager.put(new_cid, content_to_upload)
            
        finally:
            os.unlink(tmp_file_path) # Clean up temporary file
            
        # Reset buffer after flush
        self._content_buffer = io.BytesIO()
        self._current_pos = 0

    def close(self) -> None:
        """Close the file."""
        if self.closed:
            return
            
        if "w" in self.mode or "a" in self.mode:
            self.flush(force=True) # Ensure all buffered data is written
            
        super().close()
        logger.debug(f"Closed IPFSFSSpecFile: {self.path}")
        
        if id(self) in self.fs.open_files:
            del self.fs.open_files[id(self)]

    def seek(self, loc: int, whence: int = 0) -> int:
        """
        Seek to a file location.
        
        Args:
            loc: Target location
            whence: Seek reference (0: start, 1: current, 2: end)
            
        Returns:
            New file position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file.")
            
        # For read mode, seek within the buffered content
        if "r" in self.mode:
            self._current_pos = self._content_buffer.seek(loc, whence)
            return self._current_pos
        
        # For write mode, seeking might imply modifying parts of the file,
        # which is complex for IPFS. For simplicity, we'll just update
        # the internal position, assuming writes are mostly sequential or
        # overwrite the whole file on flush.
        if whence == 0:
            self._current_pos = loc
        elif whence == 1:
            self._current_pos += loc
        elif whence == 2:
            # This would require knowing the total size of the file being written,
            # which is not trivial until it's added to IPFS.
            # For now, assume it's relative to current buffered content size.
            self._current_pos = len(self._content_buffer.getvalue()) + loc
        else:
            raise ValueError("Invalid whence value")
            
        return self._current_pos
    
    def tell(self) -> int:
        """
        Get current file position.
        
        Returns:
            Current position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file.")
            
        if "r" in self.mode:
            return self._content_buffer.tell()
        
        return self._current_pos
