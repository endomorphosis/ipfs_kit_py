# FSSpec Integration for IPFS

## Overview

The FSSpec integration for IPFS provides a standard filesystem interface to content-addressed storage. This integration enables familiar file operations (`open`, `ls`, `cat`, etc.) on IPFS content, with the added benefits of content addressing, deduplication, and distributed storage.

## Key Features

- **Filesystem Interface**: Standard file operations on content-addressed storage
- **Tiered Caching**: Multi-level caching (memory, disk) with intelligent data movement using Adaptive Replacement Cache (ARC). ([See Docs](tiered_cache.md))
- **Memory-mapping**: Zero-copy access for large files via `mmap`.
- **Data Science Integration**: Works seamlessly with Pandas, PyArrow, Dask, and other tools that leverage `fsspec`.
- **Performance Metrics**: Built-in collection and analysis of latency, bandwidth, and cache performance.
- **Unix Socket Support**: Faster local daemon communication on Linux/macOS.
- **Gateway Fallback**: Optionally use public HTTP gateways if the local daemon is unavailable.

## Architecture

The FSSpec integration consists of several key components:

1. **IPFSFileSystem**: Main class implementing the Abstract Filesystem interface
2. **TieredCacheManager**: Manages content across memory and disk tiers
3. **ARCache**: Adaptive Replacement Cache for memory-tier optimization
4. **DiskCache**: Persistent storage with metadata

This architecture provides a bridge between the content-addressed model of IPFS and the path-based model of traditional filesystems.

## Usage

*Note: When using `fsspec` directly (e.g., `fsspec.filesystem("ipfs")` or `fsspec.open("ipfs://...")`), paths **must** be prefixed with `ipfs://`. When using the higher-level `IPFSSimpleAPI` methods like `api.open(cid)`, the prefix is often handled internally.*

### Basic Usage

```python
import fsspec

# Open the filesystem with default settings
# This registers the 'ipfs' protocol if ipfs_kit_py is installed
fs = fsspec.filesystem("ipfs")

# Open a file directly by CID (ensure prefix)
# Note: 'r' mode reads as text, 'rb' as bytes
try:
    with fs.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "rb") as f:
        content_bytes = f.read()
        print(f"Read {len(content_bytes)} bytes.")
except Exception as e:
    print(f"Error reading file: {e}")

# List directory contents (ensure prefix)
try:
    # Example directory CID (replace with a real one if needed)
    dir_cid = "ipfs://QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"
    files = fs.ls(dir_cid, detail=True) # Use detail=True for more info
    print(f"Contents of {dir_cid}:")
    for item in files:
        print(f"- {item['name']} (type: {item['type']}, size: {item.get('size', 'N/A')})")
except Exception as e:
    print(f"Error listing directory: {e}")


# Check if a path exists (ensure prefix)
try:
    file_cid_path = "ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"
    exists = fs.exists(file_cid_path)
    print(f"Path {file_cid_path} exists: {exists}")
except Exception as e:
    print(f"Error checking existence: {e}")
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
        'max_item_size': 100 * 1024 * 1024,  # Max size for memory cache items
        'promotion_threshold': 3, # Access count to promote from disk to memory
        'demotion_threshold': 30 # Days inactive to demote from memory to disk
    },
    use_mmap=True, # Use memory mapping for large files
    enable_metrics=True, # Enable performance metrics
    gateway_urls=["https://ipfs.io/ipfs/", "https://dweb.link/ipfs/"], # Fallback gateways
    use_gateway_fallback=True # Use gateways if local daemon fails
)

# Get file details (ensure prefix)
try:
    info = fs.info("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
    print(f"Info: {info}")
except Exception as e:
    print(f"Error getting info: {e}")


# Walk through a directory tree (ensure prefix)
try:
    dir_cid = "ipfs://QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn" # Example CID
    print(f"\nWalking directory: {dir_cid}")
    for root, dirs, files in fs.walk(dir_cid):
        print(f"Directory: {root}")
        print(f"  Subdirectories: {dirs}")
        print(f"  Files: {[f['name'] for f in files]}") # Extract names for clarity
except Exception as e:
    print(f"Error walking directory: {e}")

```

### Integration with Data Science Tools

```python
import pandas as pd
import pyarrow.parquet as pq
import fsspec

# Read a CSV file directly from IPFS (ensure prefix)
try:
    df = pd.read_csv("ipfs://QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV") # Example CID
    print("\nCSV Head:")
    print(df.head())
except Exception as e:
    print(f"Error reading CSV: {e}")


# Read a Parquet file (ensure prefix)
try:
    fs_pq = fsspec.filesystem("ipfs") # Get instance if needed
    # Example Parquet CID
    table = pq.read_table("ipfs://QmXH6qjnYXCSfc5Wn1jZyZV8AtrNKgWbXLLGJvXVYzk4wC", filesystem=fs_pq)
    df2 = table.to_pandas()
    print("\nParquet Head:")
    print(df2.head())
except ImportError:
    print("\nPyArrow needed for Parquet reading.")
except Exception as e:
    print(f"Error reading Parquet: {e}")

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
- `open(path, mode='rb', **kwargs)`: Open a file-like object for reading.
- `ls(path, detail=True, **kwargs)`: List directory contents.
- `info(path, **kwargs)`: Get file information (size, type, etc.).
- `cat(path, **kwargs)` / `cat_file(path, **kwargs)`: Read the entire file content as bytes.
- `put(local_path, target_path=None, **kwargs)`: Upload a local file to IPFS. Returns the CID.
- `exists(path)`: Check if a path (CID or ipfs:// path) exists.
- `pin(cid)`: Pin content to the local IPFS node.
- `unpin(cid)`: Unpin content from the local node.
- `get_pins()`: List CIDs pinned to the local node.
- `clear_cache()`: Clear all cache tiers (memory and disk).
- `get_metrics()` / `get_performance_metrics()`: Get collected performance metrics.
- `analyze_metrics()`: Analyze metrics and provide summary statistics.

## Using the High-Level API

The `IPFSSimpleAPI` class provides convenient high-level methods for working with the filesystem interface:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize the API
api = IPFSSimpleAPI()

# Open a file directly by CID (no need for ipfs:// prefix)
with api.open_file("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx") as f:
    content = f.read()
    print(f"Read {len(content)} bytes")

# Read entire file contents as bytes
data = api.read_file("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")

# Read entire file contents as text
text = api.read_text("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")

# List directory contents
dir_contents = api.list_directory("QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
for item in dir_contents:
    print(f"- {item['name']}")

# Get a configured filesystem instance with custom options
fs = api.get_filesystem(
    gateway_urls=["https://ipfs.io/ipfs/", "https://dweb.link/ipfs/"],
    use_gateway_fallback=True,
    enable_metrics=True
)
```

The high-level API provides a simpler interface that handles prefix management, error handling, and configuration automatically.

## Extension Points

The implementation is designed for extensibility:

- **Additional Cache Tiers**: Add new storage backends (S3, IPFS Cluster, etc.)
- **Custom Eviction Policies**: Implement specialized caching strategies
- **Content Transformation**: Add format conversion during transfers
- **Cross-node Synchronization**: Share cache state across cluster nodes
