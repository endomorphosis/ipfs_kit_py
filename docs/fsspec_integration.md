# FSSpec Integration for IPFS

## Overview

The FSSpec integration for IPFS provides a standard filesystem interface to content-addressed storage. This integration enables familiar file operations (`open`, `ls`, `cat`, etc.) on IPFS content, with the added benefits of content addressing, deduplication, and distributed storage.

## Key Features

- **Filesystem Interface**: Standard file operations on content-addressed storage
- **Tiered Caching**: Multi-level caching with intelligent data movement
- **Adaptive Replacement**: Advanced caching algorithm balancing recency and frequency
- **Memory-mapping**: Zero-copy access for large files
- **Data Science Integration**: Works with Pandas, PyArrow, Dask, and other tools
- **Metrics Collection**: Performance monitoring and optimization
- **Distributed Access**: Access content from peers across the network

## Architecture

The FSSpec integration consists of several key components:

1. **IPFSFileSystem**: Main class implementing the Abstract Filesystem interface
2. **TieredCacheManager**: Manages content across memory and disk tiers
3. **ARCache**: Adaptive Replacement Cache for memory-tier optimization
4. **DiskCache**: Persistent storage with metadata

This architecture provides a bridge between the content-addressed model of IPFS and the path-based model of traditional filesystems.

## Usage

### Basic Usage

```python
import fsspec

# Open the filesystem with default settings
fs = fsspec.filesystem("ipfs")

# Open a file directly by CID
with fs.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "r") as f:
    content = f.read()
    print(content)

# List directory contents
files = fs.ls("ipfs://Qmf7dMkJqYJb4vtGBQrF1Ak3zCQAAHbhXTAcMeSKfUF9XF")
print(files)

# Check if a file exists
exists = fs.exists("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
print(f"File exists: {exists}")
```

### Advanced Configuration

```python
from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem

# Configure with custom options
fs = IPFSFileSystem(
    ipfs_path="~/.ipfs",
    socket_path="/var/run/ipfs/api.sock",  # Unix socket for better performance
    role="worker",
    cache_config={
        'memory_cache_size': 500 * 1024 * 1024,  # 500MB memory cache
        'local_cache_size': 5 * 1024 * 1024 * 1024,  # 5GB disk cache
        'local_cache_path': '/tmp/ipfs_cache',
        'max_item_size': 100 * 1024 * 1024,  # Items up to 100MB in memory
    },
    use_mmap=True  # Use memory mapping for large files
)

# Get file details
info = fs.info("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
print(info)

# Walk through a directory tree
for root, dirs, files in fs.walk("ipfs://QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"):
    print(f"Directory: {root}")
    print(f"  Subdirectories: {dirs}")
    print(f"  Files: {files}")
```

### Integration with Data Science Tools

```python
import pandas as pd
import pyarrow.parquet as pq
import fsspec

# Read a CSV file directly from IPFS
df = pd.read_csv("ipfs://QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV")
print(df.head())

# Read a Parquet file
fs = fsspec.filesystem("ipfs")
table = pq.read_table("ipfs://QmXH6qjnYXCSfc5Wn1jZyZV8AtrNKgWbXLLGJvXVYzk4wC", filesystem=fs)
df2 = table.to_pandas()
print(df2.head())
```

## Performance Characteristics

The tiered caching provides significant performance improvements:

| Access Pattern | Without Cache | With Cache | Improvement |
|----------------|--------------|------------|-------------|
| First access   | 100-1000ms   | 100-1000ms | - |
| Repeated small file access | 100-1000ms | 0.1-1ms | 1000x |
| Repeated large file access | 100-1000ms | 1-10ms | 100x |
| Memory-mapped large file | 100-1000ms | 0.5-5ms | 200x |

## Implementation Details

### Unix Socket Support

For optimal performance on Linux systems, the implementation can communicate with the IPFS daemon via Unix domain sockets rather than HTTP:

```python
socket_path = "/var/run/ipfs/api.sock"
fs = IPFSFileSystem(socket_path=socket_path)
```

This provides lower latency for local operations.

### Memory-Mapping

For large files, the implementation uses memory mapping to provide efficient zero-copy access:

```python
# Normal read loads the entire file into memory
content = fs.cat("large_file_cid")

# Memory-mapped access only loads the parts you access
with fs.open("large_file_cid", "rb", use_mmap=True) as f:
    header = f.read(1024)  # Only loads the first 1KB
    f.seek(1000000)
    middle = f.read(1024)  # Only loads 1KB at offset 1MB
```

### Cache Management

The system automatically manages content across tiers based on:

- **Content Size**: Smaller items stay in memory, larger ones in disk
- **Access Frequency**: Frequently accessed items stay in faster tiers
- **Access Recency**: Recently accessed items are prioritized
- **Usage Patterns**: Adaptive based on observed workloads

## API Reference

### IPFSFileSystem

Main class implementing the fsspec interface for IPFS.

```python
class IPFSFileSystem(AbstractFileSystem):
    """FSSpec-compatible filesystem interface with tiered caching."""
    
    def __init__(self, 
                 ipfs_path=None, 
                 socket_path=None, 
                 role="leecher", 
                 cache_config=None, 
                 use_mmap=True,
                 **kwargs)
```

**Parameters:**
- `ipfs_path`: Path to IPFS config directory
- `socket_path`: Path to Unix socket (for high-performance on Linux)
- `role`: Node role ("master", "worker", "leecher")
- `cache_config`: Configuration for the tiered cache system
- `use_mmap`: Whether to use memory-mapped files for large content

**Methods:**
- `open(path, mode='rb', **kwargs)`: Open a file-like object
- `ls(path, detail=True, **kwargs)`: List directory contents
- `info(path, **kwargs)`: Get file information
- `cp_file(path1, path2, **kwargs)`: Copy a file
- `cat(path, **kwargs)`: Read file contents
- `put(path, value, **kwargs)`: Write content
- `get(path, local_path, **kwargs)`: Download to local filesystem
- `exists(path)`: Check if path exists
- `isdir(path)`: Check if path is a directory
- `pin(path)`: Pin content to local node
- `unpin(path)`: Unpin content
- `publish_to_ipns(path, key=None)`: Publish content to IPNS
- `resolve_ipns(name)`: Resolve IPNS name to CID

## Extension Points

The implementation is designed for extensibility:

- **Additional Cache Tiers**: Add new storage backends (S3, IPFS Cluster, etc.)
- **Custom Eviction Policies**: Implement specialized caching strategies
- **Content Transformation**: Add format conversion during transfers
- **Cross-node Synchronization**: Share cache state across cluster nodes