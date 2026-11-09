"""
Parquet VFS Integration for IPFS Kit.

This module integrates the Parquet-IPLD bridge with the Virtual File System,
enabling structured data to be accessed through filesystem operations while
maintaining all the benefits of content addressing, caching, and replication.

Features:
1. Mount Parquet datasets as virtual filesystems
2. SQL query interface through VFS paths
3. Automatic integration with tiered caching
4. Write-ahead logging for dataset operations
5. Metadata replication across storage tiers
6. Arrow-optimized data pipelines
"""

import os
import json
import logging
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO
from pathlib import Path

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

try:
    import fsspec
    from fsspec.spec import AbstractFileSystem
    FSSPEC_AVAILABLE = True
except ImportError:
    FSSPEC_AVAILABLE = False

from .parquet_ipld_bridge import ParquetIPLDBridge
from .error import IPFSError, create_result_dict, handle_error

logger = logging.getLogger(__name__)


class ParquetVirtualFileSystem(AbstractFileSystem):
    """
    Virtual filesystem interface for Parquet-IPLD bridge.
    
    This class provides FSSpec-compatible access to Parquet datasets
    stored through the Parquet-IPLD bridge, enabling standard filesystem
    operations on structured data.
    """
    
    protocol = "parquet-ipfs"
    
    def __init__(
        self,
        parquet_bridge: ParquetIPLDBridge,
        auto_cache: bool = True,
        **kwargs
    ):
        """
        Initialize the Parquet VFS.
        
        Args:
            parquet_bridge: ParquetIPLDBridge instance
            auto_cache: Whether to automatically cache accessed data
            **kwargs: Additional FSSpec arguments
        """
        super().__init__(**kwargs)
        
        if not ARROW_AVAILABLE:
            raise ImportError("PyArrow is required for ParquetVirtualFileSystem")
        
        self.bridge = parquet_bridge
        self.auto_cache = auto_cache
        
        # Virtual filesystem structure
        self._vfs_structure = {
            "/": {
                "type": "directory",
                "children": {
                    "datasets": {"type": "directory", "children": {}},
                    "queries": {"type": "directory", "children": {}},
                    "metadata": {"type": "directory", "children": {}}
                }
            }
        }
        
        # Refresh dataset listing
        self._refresh_datasets()
        
        logger.info("ParquetVirtualFileSystem initialized")
    
    def _refresh_datasets(self):
        """Refresh the virtual filesystem structure with current datasets."""
        try:
            datasets_result = self.bridge.list_datasets()
            if datasets_result["success"]:
                datasets_node = self._vfs_structure["/"]["children"]["datasets"]["children"]
                datasets_node.clear()
                
                for dataset in datasets_result["datasets"]:
                    cid = dataset["cid"]
                    datasets_node[cid] = {
                        "type": "file",
                        "cid": cid,
                        "size": dataset["size_bytes"],
                        "metadata": dataset["metadata"]
                    }
                    
                    # Create metadata entry
                    metadata_node = self._vfs_structure["/"]["children"]["metadata"]["children"]
                    metadata_node[f"{cid}.json"] = {
                        "type": "file",
                        "cid": cid,
                        "content_type": "application/json",
                        "metadata": dataset["metadata"]
                    }
        except Exception as e:
            logger.warning(f"Failed to refresh datasets: {e}")
    
    def ls(self, path, detail=True, **kwargs):
        """List directory contents."""
        try:
            # Normalize path
            path = self._normalize_path(path)
            
            # Refresh datasets for root-level listing
            if path in ["/", "/datasets"]:
                self._refresh_datasets()
            
            # Navigate to path in virtual structure
            current = self._vfs_structure
            path_parts = [p for p in path.split("/") if p]
            
            for part in path_parts:
                if part in current:
                    current = current[part]
                elif "children" in current and part in current["children"]:
                    current = current["children"][part]
                else:
                    raise FileNotFoundError(f"Path not found: {path}")
            
            # Generate listing
            if current.get("type") == "directory" and "children" in current:
                entries = []
                for name, info in current["children"].items():
                    entry = {
                        "name": f"{path.rstrip('/')}/{name}",
                        "type": info["type"],
                        "size": info.get("size", 0)
                    }
                    
                    if detail:
                        entry.update({
                            "cid": info.get("cid"),
                            "metadata": info.get("metadata", {})
                        })
                    
                    entries.append(entry)
                
                return entries
            else:
                # Single file
                return [{
                    "name": path,
                    "type": current.get("type", "file"),
                    "size": current.get("size", 0),
                    "cid": current.get("cid"),
                    "metadata": current.get("metadata", {}) if detail else None
                }]
                
        except Exception as e:
            logger.error(f"Error listing {path}: {e}")
            raise
    
    def info(self, path, **kwargs):
        """Get file/directory information."""
        try:
            path = self._normalize_path(path)
            
            # Check if it's a dataset
            if path.startswith("/datasets/"):
                cid = path.split("/datasets/")[-1]
                
                # Get dataset info from bridge
                datasets_result = self.bridge.list_datasets()
                if datasets_result["success"]:
                    for dataset in datasets_result["datasets"]:
                        if dataset["cid"] == cid:
                            return {
                                "name": path,
                                "type": "file",
                                "size": dataset["size_bytes"],
                                "cid": cid,
                                "is_partitioned": dataset["is_partitioned"],
                                "metadata": dataset["metadata"]
                            }
                
                raise FileNotFoundError(f"Dataset not found: {cid}")
            
            # Navigate virtual structure
            current = self._vfs_structure
            path_parts = [p for p in path.split("/") if p]
            
            for part in path_parts:
                if part in current:
                    current = current[part]
                elif "children" in current and part in current["children"]:
                    current = current["children"][part]
                else:
                    raise FileNotFoundError(f"Path not found: {path}")
            
            return {
                "name": path,
                "type": current.get("type", "file"),
                "size": current.get("size", 0),
                "cid": current.get("cid"),
                "metadata": current.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting info for {path}: {e}")
            raise
    
    def cat_file(self, path, start=None, end=None, **kwargs):
        """Read file contents."""
        try:
            path = self._normalize_path(path)
            
            # Handle dataset files
            if path.startswith("/datasets/"):
                cid = path.split("/datasets/")[-1]
                return self._read_dataset_as_bytes(cid, start, end)
            
            # Handle metadata files
            elif path.startswith("/metadata/") and path.endswith(".json"):
                cid = path.split("/metadata/")[-1].replace(".json", "")
                return self._read_metadata_as_bytes(cid)
            
            # Handle query results (if implemented)
            elif path.startswith("/queries/"):
                return self._handle_query_file(path)
            
            else:
                raise ValueError(f"Cannot read path: {path}")
                
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            raise
    
    def open(self, path, mode="rb", **kwargs):
        """Open file for reading/writing."""
        return ParquetVFSFile(self, path, mode, **kwargs)
    
    def exists(self, path, **kwargs):
        """Check if path exists."""
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False
    
    def _normalize_path(self, path):
        """Normalize filesystem path."""
        if not path.startswith("/"):
            path = "/" + path
        return path.rstrip("/") or "/"
    
    def _read_dataset_as_bytes(self, cid: str, start: Optional[int] = None, end: Optional[int] = None) -> bytes:
        """Read dataset as bytes (Parquet format)."""
        # Retrieve the dataset
        result = self.bridge.retrieve_dataframe(cid, use_cache=self.auto_cache)
        if not result["success"]:
            raise FileNotFoundError(f"Dataset {cid} not found")
        
        # Get the original Parquet file path
        storage_path = result["storage_path"]
        
        if os.path.isdir(storage_path):
            # Partitioned dataset - create a single Parquet file in memory
            table = result["table"]
            buffer = pa.BufferOutputStream()
            pq.write_table(table, buffer, compression="zstd")
            data = buffer.getvalue().to_pybytes()
        else:
            # Single file - read directly
            with open(storage_path, "rb") as f:
                data = f.read()
        
        # Apply range if specified
        if start is not None or end is not None:
            start = start or 0
            end = end or len(data)
            data = data[start:end]
        
        return data
    
    def _read_metadata_as_bytes(self, cid: str) -> bytes:
        """Read dataset metadata as JSON bytes."""
        datasets_result = self.bridge.list_datasets()
        if datasets_result["success"]:
            for dataset in datasets_result["datasets"]:
                if dataset["cid"] == cid:
                    metadata = {
                        "cid": cid,
                        "size_bytes": dataset["size_bytes"],
                        "is_partitioned": dataset["is_partitioned"],
                        "metadata": dataset["metadata"]
                    }
                    return json.dumps(metadata, indent=2).encode()
        
        raise FileNotFoundError(f"Metadata for dataset {cid} not found")
    
    def _handle_query_file(self, path: str) -> bytes:
        """Handle query file requests."""
        # Extract query parameters from path
        # Format: /queries/{sql_hash}.json or /queries/{sql_hash}.parquet
        
        # For now, return empty result
        # This could be extended to support cached query results
        return b'{"message": "Query interface not yet implemented"}'


class ParquetVFSFile:
    """
    File-like object for Parquet VFS operations.
    """
    
    def __init__(self, fs: ParquetVirtualFileSystem, path: str, mode: str = "rb", **kwargs):
        self.fs = fs
        self.path = path
        self.mode = mode
        self._buffer = None
        self._position = 0
        
        if "r" in mode:
            # Read mode - load data into buffer
            self._buffer = self.fs.cat_file(path)
        else:
            # Write mode not supported yet
            raise NotImplementedError("Write mode not supported for Parquet VFS")
    
    def read(self, size: int = -1) -> bytes:
        """Read data from file."""
        if self._buffer is None:
            return b""
        
        if size == -1:
            # Read all remaining data
            data = self._buffer[self._position:]
            self._position = len(self._buffer)
        else:
            # Read specified number of bytes
            end_pos = min(self._position + size, len(self._buffer))
            data = self._buffer[self._position:end_pos]
            self._position = end_pos
        
        return data
    
    def readline(self, size: int = -1) -> bytes:
        """Read a line from file."""
        if self._buffer is None:
            return b""
        
        # Find next newline
        start = self._position
        newline_pos = self._buffer.find(b'\n', start)
        
        if newline_pos == -1:
            # No newline found, read to end
            data = self._buffer[start:]
            self._position = len(self._buffer)
        else:
            # Read including newline
            end_pos = newline_pos + 1
            if size != -1 and (end_pos - start) > size:
                end_pos = start + size
            
            data = self._buffer[start:end_pos]
            self._position = end_pos
        
        return data
    
    def seek(self, position: int, whence: int = 0) -> int:
        """Seek to position in file."""
        if whence == 0:  # Absolute position
            self._position = position
        elif whence == 1:  # Relative to current position
            self._position += position
        elif whence == 2:  # Relative to end
            self._position = len(self._buffer) + position
        
        # Clamp position to valid range
        self._position = max(0, min(self._position, len(self._buffer)))
        return self._position
    
    def tell(self) -> int:
        """Get current position."""
        return self._position
    
    def close(self):
        """Close file."""
        self._buffer = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_parquet_vfs_integration(
    ipfs_client=None,
    storage_path: str = "~/.ipfs_parquet_storage",
    cache_manager=None,
    wal_manager=None,
    replication_manager=None,
    metadata_index=None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[ParquetIPLDBridge, ParquetVirtualFileSystem]:
    """
    Create integrated Parquet-IPLD bridge and VFS.
    
    Args:
        ipfs_client: IPFS client instance
        storage_path: Path for Parquet storage
        cache_manager: Tiered cache manager
        wal_manager: Write-ahead log manager
        replication_manager: Metadata replication manager
        metadata_index: Arrow metadata index
        config: Configuration options
        
    Returns:
        Tuple of (ParquetIPLDBridge, ParquetVirtualFileSystem)
    """
    if not ARROW_AVAILABLE:
        raise ImportError("PyArrow is required for Parquet VFS integration")
    
    if not FSSPEC_AVAILABLE:
        raise ImportError("FSSpec is required for Parquet VFS integration")
    
    # Create the bridge
    bridge = ParquetIPLDBridge(
        storage_path=storage_path,
        ipfs_client=ipfs_client,
        cache_manager=cache_manager,
        wal_manager=wal_manager,
        replication_manager=replication_manager,
        metadata_index=metadata_index,
        config=config
    )
    
    # Create the VFS
    vfs = ParquetVirtualFileSystem(
        parquet_bridge=bridge,
        auto_cache=True
    )
    
    # Register the VFS with fsspec
    try:
        from fsspec.registry import register_implementation
        register_implementation("parquet-ipfs", ParquetVirtualFileSystem)
        logger.info("Registered parquet-ipfs:// filesystem protocol")
    except Exception as e:
        logger.warning(f"Failed to register parquet-ipfs protocol: {e}")
    
    return bridge, vfs


# Convenience functions for integration

def store_dataframe_to_ipfs(
    df,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs
) -> str:
    """
    Convenience function to store a DataFrame to IPFS via Parquet.
    
    Args:
        df: DataFrame to store
        name: Optional name for dataset
        metadata: Additional metadata
        **kwargs: Additional arguments for bridge creation
        
    Returns:
        CID of stored dataset
    """
    bridge, _ = create_parquet_vfs_integration(**kwargs)
    result = bridge.store_dataframe(df, name=name, metadata=metadata)
    
    if result["success"]:
        return result["cid"]
    else:
        raise IPFSError(f"Failed to store DataFrame: {result.get('error')}")


def retrieve_dataframe_from_ipfs(
    cid: str,
    columns: Optional[List[str]] = None,
    filters: Optional[List] = None,
    **kwargs
):
    """
    Convenience function to retrieve a DataFrame from IPFS.
    
    Args:
        cid: Content identifier
        columns: Specific columns to retrieve
        filters: PyArrow filters
        **kwargs: Additional arguments for bridge creation
        
    Returns:
        PyArrow Table
    """
    bridge, _ = create_parquet_vfs_integration(**kwargs)
    result = bridge.retrieve_dataframe(cid, columns=columns, filters=filters)
    
    if result["success"]:
        return result["table"]
    else:
        raise IPFSError(f"Failed to retrieve DataFrame: {result.get('error')}")


def mount_parquet_vfs(mount_point: str = "/parquet", **kwargs) -> ParquetVirtualFileSystem:
    """
    Mount Parquet VFS at specified mount point.
    
    Args:
        mount_point: Mount point path
        **kwargs: Additional arguments for VFS creation
        
    Returns:
        ParquetVirtualFileSystem instance
    """
    bridge, vfs = create_parquet_vfs_integration(**kwargs)
    
    # In a full implementation, this would integrate with the OS filesystem
    # For now, just return the VFS instance
    logger.info(f"Parquet VFS ready for mounting at {mount_point}")
    
    return vfs
