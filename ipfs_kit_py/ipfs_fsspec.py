"""
Mock FSSpec implementation for IPFS.

This module provides a lightweight mock implementation of the FSSpec interface
for IPFS, allowing the tests to run even when fsspec is not installed.
"""

import os
import time
import logging
import io
from typing import Dict, List, Any, Optional, Union, Tuple, Callable, BinaryIO

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
        self.operation_times = {}
        self.operation_counts = {}
        
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
                "mean": mean
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
            stats["memory_hit_rate"] = memory_hits / total
            stats["disk_hit_rate"] = disk_hits / total
            stats["overall_hit_rate"] = (memory_hits + disk_hits) / total
            stats["miss_rate"] = misses / total
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
            avg_time = total_time / count if count > 0 else 0
            
            metrics["operations"][op_name] = {
                "count": count,
                "total_time": total_time,
                "average_time": avg_time
            }
        
        return metrics

# Create an alias for backward compatibility
performance_metrics = PerformanceMetrics

class IPFSFileSystem:
    """
    Mock FSSpec-compatible filesystem for IPFS.
    
    This is a simplified mock version that provides the minimal functionality needed
    for test compatibility. In a real implementation, this would integrate with the
    fsspec package.
    """
    
    protocol = "ipfs"
    
    def __init__(
        self, 
        api_addr: str = "/ip4/127.0.0.1/tcp/5001",
        role: str = "leecher",
        gateway_urls: Optional[List[str]] = None,
        gateway_only: bool = False,
        use_gateway_fallback: bool = True,
        cache_config: Optional[Dict[str, Any]] = None,
        enable_metrics: bool = False,
        **kwargs
    ):
        """
        Initialize the IPFS filesystem.
        
        Args:
            api_addr: IPFS API address
            role: Node role (leecher, seeder, or full)
            gateway_urls: List of gateway URLs to use for fallback
            gateway_only: Whether to use only gateways (no local node)
            use_gateway_fallback: Whether to use gateways as fallback
            cache_config: Cache configuration options
            enable_metrics: Whether to enable performance metrics
            **kwargs: Additional arguments
        """
        self.api_addr = api_addr
        self.role = role
        self.gateway_urls = gateway_urls or ["https://ipfs.io", "https://cloudflare-ipfs.com"]
        self.gateway_only = gateway_only
        self.use_gateway_fallback = use_gateway_fallback
        self.cache_config = cache_config or {}
        self.enable_metrics = enable_metrics
        
        # Initialize performance metrics
        self.metrics = PerformanceMetrics(enable_metrics=enable_metrics)
        
        # Simple content cache
        self.content_cache = {}
        
        # Track open files
        self.open_files = {}
        
        logger.info(f"Initialized mock IPFS filesystem with role: {role}")
    
    def ls(self, path: str, detail: bool = True, **kwargs) -> Union[List[Dict[str, Any]], List[str]]:
        """
        List directory contents.
        
        Args:
            path: IPFS path to list
            detail: Whether to return detailed information
            
        Returns:
            List of dictionaries with file info if detail=True,
            otherwise list of path strings
        """
        if not path.startswith("/ipfs/") and not path.startswith("ipfs://"):
            path = f"/ipfs/{path}"
        
        start_time = time.time()
        mock_result = [
            {"name": f"{path}/file1.txt", "size": 1024, "type": "file"},
            {"name": f"{path}/file2.txt", "size": 2048, "type": "file"},
            {"name": f"{path}/dir1", "size": 0, "type": "directory"}
        ]
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("ls", elapsed)
        
        if not detail:
            return [item["name"] for item in mock_result]
        return mock_result
    
    def info(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        Get info about a file/directory.
        
        Args:
            path: IPFS path
            
        Returns:
            Dictionary with file/directory info
        """
        if not path.startswith("/ipfs/") and not path.startswith("ipfs://"):
            path = f"/ipfs/{path}"
        
        start_time = time.time()
        result = {
            "name": path,
            "size": 1024,
            "type": "file" if not path.endswith("/") else "directory",
            "cid": path.split("/")[-1] if path.split("/")[-1] else path.split("/")[-2]
        }
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("info", elapsed)
        
        return result
    
    def open(
        self, 
        path: str, 
        mode: str = "rb", 
        block_size: int = None, 
        **kwargs
    ) -> "IPFSFile":
        """
        Open a file.
        
        Args:
            path: IPFS path
            mode: File mode (rb, wb, etc.)
            block_size: Block size for reading
            
        Returns:
            File-like object
        """
        if not path.startswith("/ipfs/") and not path.startswith("ipfs://"):
            path = f"/ipfs/{path}"
        
        start_time = time.time()
        file = IPFSFile(self, path, mode, block_size, **kwargs)
        self.open_files[id(file)] = file
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("open", elapsed)
        
        return file
    
    def cat(self, path: str, **kwargs) -> bytes:
        """
        Get file contents.
        
        Args:
            path: IPFS path
            
        Returns:
            File contents as bytes
        """
        if not path.startswith("/ipfs/") and not path.startswith("ipfs://"):
            path = f"/ipfs/{path}"
        
        # Check cache first
        if path in self.content_cache:
            self.metrics.record_cache_access("memory_hit")
            return self.content_cache[path]
        
        # Not in cache, fetch from IPFS
        self.metrics.record_cache_access("miss")
        start_time = time.time()
        content = self._fetch_from_ipfs(path)
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("read", elapsed, len(content))
        
        # Cache the content
        self.content_cache[path] = content
        
        return content
    
    def _fetch_from_ipfs(self, path: str) -> bytes:
        """
        Fetch content from IPFS.
        
        Args:
            path: IPFS path
            
        Returns:
            Content as bytes
        """
        # This is a mock implementation
        return b"Mock file content for " + path.encode()
    
    def put(self, filename: str, path: str, **kwargs) -> str:
        """
        Upload a file.
        
        Args:
            filename: Local filename to upload
            path: IPFS path to create
            
        Returns:
            IPFS CID of the uploaded file
        """
        start_time = time.time()
        mock_cid = "QmMockCID" + os.path.basename(filename).replace(".", "")
        
        # Record metrics for the operation
        if os.path.exists(filename):
            size = os.path.getsize(filename)
        else:
            size = 0
            
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("write", elapsed, size)
        
        return mock_cid
    
    def rm(self, path: str, recursive: bool = False, **kwargs) -> None:
        """
        Remove a file/directory.
        
        Args:
            path: IPFS path to remove
            recursive: Whether to remove recursively
        """
        # This is a mock, so we don't actually remove anything
        # Just record the operation
        start_time = time.time()
        elapsed = time.time() - start_time
        self.metrics.record_operation_time("remove", elapsed)
    
    def close(self) -> None:
        """Close the filesystem and release resources."""
        for file_id, file in list(self.open_files.items()):
            file.close()
            del self.open_files[file_id]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for this filesystem.
        
        Returns:
            Dictionary of performance metrics
        """
        return self.metrics.get_metrics() if self.enable_metrics else {"metrics_enabled": False}

class IPFSMemoryFile(io.BytesIO):
    """In-memory file-like object for IPFS content."""
    
    def __init__(
        self, 
        fs: IPFSFileSystem, 
        path: str, 
        mode: str = "rb", 
        block_size: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the memory file.
        
        Args:
            fs: Parent filesystem
            path: IPFS path
            mode: File mode
            block_size: Block size for reading
        """
        super().__init__()
        self.fs = fs
        self.path = path
        self.mode = mode
        self.block_size = block_size or 8192
        self._closed = False
        
        # For write mode, initialize empty
        # For read mode, populate with content from fs
        if "r" in mode:
            # Mock content based on path
            content = b"Mock file content for " + path.encode()
            super().write(content)
            self.seek(0)
    
    def close(self) -> None:
        """Close the file and write to fs if in write mode."""
        if not self._closed:
            if "w" in self.mode or "a" in self.mode:
                # In a real implementation, this would write to IPFS
                pass
            super().close()
            self._closed = True
            if hasattr(self.fs, 'open_files') and id(self) in self.fs.open_files:
                del self.fs.open_files[id(self)]


class IPFSFile:
    """Mock file-like object for IPFS content."""
    
    def __init__(
        self, 
        fs: IPFSFileSystem, 
        path: str, 
        mode: str = "rb", 
        block_size: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the file.
        
        Args:
            fs: Parent filesystem
            path: IPFS path
            mode: File mode
            block_size: Block size for reading
        """
        self.fs = fs
        self.path = path
        self.mode = mode
        self.block_size = block_size or 8192
        
        # Mock content based on path
        self._content = b"Mock file content for " + path.encode()
        self._size = len(self._content)
        self._loc = 0
        self._closed = False
    
    def read(self, size: int = -1) -> bytes:
        """
        Read file content.
        
        Args:
            size: Number of bytes to read, -1 for all
            
        Returns:
            Bytes read
        """
        if self._closed:
            raise ValueError("I/O operation on closed file.")
        
        start_time = time.time()    
        if size < 0:
            data = self._content[self._loc:]
            self._loc = self._size
        else:
            data = self._content[self._loc:self._loc + size]
            self._loc += min(size, self._size - self._loc)
        
        elapsed = time.time() - start_time
        if hasattr(self.fs, 'metrics'):
            self.fs.metrics.record_read(len(data), elapsed)
            
        return data
    
    def write(self, data: bytes) -> int:
        """
        Write data to file.
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
        """
        if self._closed:
            raise ValueError("I/O operation on closed file.")
            
        if "w" not in self.mode and "a" not in self.mode:
            raise IOError("File not open for writing")
        
        start_time = time.time()
        # Mock write operation    
        data_len = len(data)
        elapsed = time.time() - start_time
        
        if hasattr(self.fs, 'metrics'):
            self.fs.metrics.record_write(data_len, elapsed)
            
        return data_len
    
    def close(self) -> None:
        """Close the file."""
        if not self._closed:
            self._closed = True
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
        if self._closed:
            raise ValueError("I/O operation on closed file.")
            
        if whence == 0:
            self._loc = min(max(0, loc), self._size)
        elif whence == 1:
            self._loc = min(max(0, self._loc + loc), self._size)
        elif whence == 2:
            self._loc = min(max(0, self._size + loc), self._size)
        else:
            raise ValueError("Invalid whence value")
            
        return self._loc
    
    def tell(self) -> int:
        """
        Get current file position.
        
        Returns:
            Current position
        """
        if self._closed:
            raise ValueError("I/O operation on closed file.")
            
        return self._loc
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __iter__(self):
        """Iterate over lines in the file."""
        return self
    
    def __next__(self):
        """Get next line."""
        line = b""
        while True:
            if self._loc >= self._size:
                if not line:
                    raise StopIteration
                return line
                
            char = self.read(1)
            line += char
            
            if char == b"\n":
                return line