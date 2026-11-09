# Tiered Caching System

## Overview

The ipfs_kit_py implements a high-performance multi-tier caching system for IPFS content using an Adaptive Replacement Cache (ARC) algorithm. This system provides efficient content access with automatic migration between tiers based on access patterns.

## Key Features

- **Multi-tier Architecture**: Hierarchical caching with memory, disk, and memory-mapped tiers
- **Adaptive Cache Policies**: ARC algorithm balances between recency and frequency for optimal hit rates
- **Intelligent Content Placement**: Automatic promotion/demotion based on content size and access patterns
- **Zero-copy Access**: Memory-mapped file support for large content without duplicating data
- **Heat Scoring**: Advanced content temperature calculation for optimal eviction decisions
- **Rich Metrics**: Comprehensive statistics for monitoring and debugging cache performance
- **Content-aware Tiering**: Metadata-based content type tracking and tier selection

## Core Components

### ARCache (Adaptive Replacement Cache)

The in-memory cache tier uses a modified ARC algorithm that considers:

- Recency of access (for capturing temporal locality)
- Frequency of access (for capturing popularity)
- Content size (for efficient memory utilization)

The ARC algorithm maintains four internal structures:
- **T1**: Recently accessed items in cache
- **T2**: Frequently accessed items in cache
- **B1**: Ghost entries for recently evicted items
- **B2**: Ghost entries for frequently evicted items

The algorithm dynamically adjusts the allocation between recent and frequent content based on observed workload patterns.

### DiskCache

The persistent disk cache tier provides:

- Content-addressed storage with metadata
- Resilience across program restarts
- JSON-based index for fast lookup
- Size-aware cache management
- Cache integrity verification
- Heat-based eviction policy

### TieredCacheManager

The coordinator that manages caching across tiers:

- **Unified Interface**: Single get/put API for accessing all cache tiers
- **Automatic Migration**: Content promotion/demotion between tiers
- **Optimization Heuristics**: Size and access-pattern based tier selection
- **Memory Mapping**: Zero-copy access for large files
- **Statistics Collection**: Comprehensive metrics for all tiers
- **Configurable Policies**: Tunable parameters for different workloads

## Usage Examples

### Basic Usage

```python
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Create a cache manager with default settings
cache = TieredCacheManager()

# Store content in the cache
cache.put("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", some_binary_content)

# Retrieve content (automatically uses fastest available tier)
content = cache.get("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
```

### Custom Configuration

```python
# Configure cache tiers with custom sizes and paths
config = {
    'memory_cache_size': 500 * 1024 * 1024,  # 500MB memory cache
    'local_cache_size': 10 * 1024 * 1024 * 1024,  # 10GB disk cache
    'local_cache_path': '/data/ipfs_cache',
    'max_item_size': 100 * 1024 * 1024,  # Items up to 100MB go to memory
    'min_access_count': 3,  # Items need 3+ accesses to stay in memory
    'enable_memory_mapping': True
}

cache = TieredCacheManager(config=config)
```

### Accessing Large Files with Zero-Copy

```python
# Store a large file (e.g., video content)
cache.put("QmLargeVideoFile", video_binary_data, {"mimetype": "video/mp4"})

# Get memory-mapped access (zero-copy)
mmap_obj = cache.get_mmap("QmLargeVideoFile")

# Use the memory-mapped object directly
# This avoids copying the entire file into memory
chunk = mmap_obj[1024:2048]  # Read a 1KB chunk at offset 1KB
```

### Tier Management

```python
# Clear specific tiers
cache.clear(tiers=['memory'])  # Clear only memory tier
cache.clear()  # Clear all tiers

# Get statistics about the cache
stats = cache.get_stats()
print(f"Memory utilization: {stats['memory_cache']['utilization']:.1%}")
print(f"Disk utilization: {stats['disk_cache']['utilization']:.1%}")
print(f"Overall hit rate: {stats['hit_rate']:.1%}")
```

## Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `memory_cache_size` | Maximum size of memory cache in bytes | 100MB |
| `local_cache_size` | Maximum size of disk cache in bytes | 1GB |
| `local_cache_path` | Directory to store disk cache | ~/.ipfs_cache |
| `max_item_size` | Maximum size of items to store in memory | 50MB |
| `min_access_count` | Minimum accesses before promoting to memory | 2 |
| `enable_memory_mapping` | Enable memory-mapped file access | True |

## Performance Characteristics

The tiered caching system provides significant performance improvements:

| Access Pattern | Without Cache | With Cache | Improvement |
|----------------|--------------|------------|-------------|
| First access   | 100-1000ms   | 100-1000ms | - |
| Repeated small file access | 100-1000ms | 0.1-1ms | 1000x |
| Repeated large file access | 100-1000ms | 1-10ms | 100x |
| Memory-mapped large file | 100-1000ms | 0.5-5ms | 200x |
| Multiple access to streaming file | 100-1000ms per access | One-time overhead | >10x |

## Integration with FSSpec

The tiered cache system integrates with the FSSpec implementation to provide:

```python
import fsspec

# Open the FSSpec filesystem with caching enabled
fs = fsspec.filesystem("ipfs", cache_type="tiered", 
                      cache_options={"memory_cache_size": "500MB"})

# Files are now automatically cached with tiered approach
with fs.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "rb") as f:
    content = f.read()
    # Second read will be from cache
    f.seek(0)
    content_again = f.read()  # Much faster!
```

## Heat Scoring Algorithm

The cache uses a sophisticated heat scoring algorithm to determine which items to evict:

```
heat_score = frequency_factor * recency_factor * age_boost

Where:
- frequency_factor = access_count / age
- recency_factor = 1.0 / (1.0 + (current_time - last_access) / 3600)
- age_boost = 1 + log(1 + age_in_days)
```

This combines:
- **Frequency**: Items accessed more often have higher heat
- **Recency**: Recently accessed items have higher heat
- **Maturity**: Long-lived items with consistent access get a slight boost

## Implementation Details

### Memory-tier Implementation

The ARCache uses an optimized data structure to minimize overhead:

```python
# ARC algorithm uses four lists:
# T1: Recently accessed items that are in cache
# B1: Recently accessed items that have been evicted from cache
# T2: Frequently accessed items that are in cache
# B2: Frequently accessed items that have been evicted from cache
self.T1 = {}  # Recent cache
self.T2 = {}  # Frequent cache
self.B1 = {}  # Ghost entries for recent
self.B2 = {}  # Ghost entries for frequent
```

The target size for T1 vs T2 (the p parameter in ARC) adapts dynamically based on whether hits are occurring in B1 or B2, allowing the cache to adjust to changing workloads.

### Disk-tier Implementation

The disk cache uses a simple yet effective structure:

- Content is stored as individual files named based on the content key
- An index file maps keys to file paths and metadata
- Files are removed according to heat-based eviction policy when space is needed

### Integration with Other Components

The tiered cache system is designed to integrate with:

- **IPFS FSSpec**: Provides filesystem-like access to IPFS content
- **Content Routing**: Learns content availability patterns to optimize routing
- **Cluster State**: Shares cache state across cluster nodes
- **Pinning Strategies**: Influences pinning decisions based on access patterns

## Extension Points

The tiered cache system is designed for extensibility:

- **Additional Tiers**: Add new storage tiers (S3, IPFS Cluster, etc.)
- **Custom Policies**: Implement specialized eviction policies
- **Cache Warming**: Prefetch content based on predicted access patterns
- **Observability Hooks**: Add monitoring and telemetry
- **Content Transcoding**: Optimize storage format based on access patterns