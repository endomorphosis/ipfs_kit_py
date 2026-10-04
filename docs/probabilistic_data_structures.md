# Probabilistic Data Structures

This document provides comprehensive documentation for the probabilistic data structures implemented in the IPFS Kit library. These structures offer significant memory and performance benefits for large-scale operations where exact answers aren't required, trading a small amount of accuracy for substantial resource savings.

## Table of Contents

1. [Overview](#overview)
2. [Available Data Structures](#available-data-structures)
   - [Bloom Filter](#bloom-filter)
   - [HyperLogLog](#hyperloglog)
   - [Count-Min Sketch](#count-min-sketch)
   - [Cuckoo Filter](#cuckoo-filter)
   - [MinHash](#minhash)
   - [TopK](#topk)
3. [ProbabilisticDataStructureManager](#probabilisticdatastructuremanager)
4. [Use Cases in IPFS Kit](#use-cases-in-ipfs-kit)
5. [Memory/Accuracy Tradeoffs](#memoryaccuracy-tradeoffs)
6. [Integration with Tiered Cache](#integration-with-tiered-cache)
7. [Performance Benefits](#performance-benefits)
8. [API Reference](#api-reference)
9. [Examples](#examples)

## Overview

Probabilistic data structures use randomization and hash functions to provide approximate answers to queries with mathematically bounded error rates while using orders of magnitude less memory than exact methods. They're particularly valuable in distributed systems like IPFS where resources are constrained and exact answers are often unnecessary.

The implementation in IPFS Kit's `cache.probabilistic_data_structures` module provides efficient implementations of several key probabilistic data structures, with a unified management interface for easy integration with the tiered cache system.

## Available Data Structures

### Bloom Filter

A space-efficient probabilistic data structure used to test whether an element is a member of a set. False positive matches are possible, but false negatives are not - meaning a Bloom filter will never incorrectly report that an element is not in the set.

**Key features:**
- Constant-time insertions and lookups (O(k) where k is the number of hash functions)
- No removal support
- Configurable false positive rate
- Extreme space efficiency

**Primary use cases:**
- Fast lookup of locally available content
- Prevention of redundant operations
- Efficient caching of negative results
- Quick filtering before more expensive operations

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import BloomFilter

# Create a Bloom filter with capacity for 1 million items and 1% false positive rate
bloom = BloomFilter(capacity=1_000_000, false_positive_rate=0.01)

# Add content identifiers
bloom.add("QmHash1")
bloom.add("QmHash2")

# Check for membership
if "QmHash1" in bloom:
    # Content might be available locally (could be a false positive)
    print("Content might be available locally")
else:
    # Content is definitely not available locally (no false negatives)
    print("Content is definitely not available locally")
```

### HyperLogLog

A probabilistic algorithm for estimating the number of distinct elements (cardinality) in a multiset. It provides a good approximation using minimal memory.

**Key features:**
- Sublinear space complexity (O(log log n))
- Configurable accuracy via precision parameter
- Mergeable structure for distributed counting
- Constant time operations regardless of cardinality

**Primary use cases:**
- Counting unique peers seen by the node
- Estimating the number of distinct content identifiers
- Tracking unique users or requests
- Monitoring system statistics in distributed settings

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import HyperLogLog

# Create a HyperLogLog counter with precision 14 (error ~0.8%)
hll = HyperLogLog(precision=14)

# Track unique peer IDs
for peer_id in peer_connections:
    hll.add(peer_id)

# Get the estimated unique peer count
unique_peers = hll.count()
print(f"Approximately {unique_peers} unique peers seen")
```

### Count-Min Sketch

A probabilistic data structure for estimating the frequency of items in a stream of data. It uses multiple hash functions to maintain several counters for each item, providing frequency estimates with bounded error.

**Key features:**
- Fixed memory usage regardless of stream size
- Configurable accuracy via width and depth parameters
- Fast updates and queries (O(depth) complexity)
- Conservative overestimation (never underestimates)

**Primary use cases:**
- Tracking content popularity
- Identifying frequently accessed CIDs
- Rate limiting and abuse detection
- Resource allocation based on usage patterns

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import CountMinSketch

# Create a Count-Min Sketch with custom dimensions
cms = CountMinSketch(width=10000, depth=5)

# Track content access frequencies
for access in content_accesses:
    cms.add(access.cid)

# Query content popularity
popular_content = []
for cid in all_content:
    estimated_accesses = cms.estimate_count(cid)
    if estimated_accesses > threshold:
        popular_content.append((cid, estimated_accesses))
```

### Cuckoo Filter

An improvement over Bloom filters that supports deletion and has better space efficiency and lookup performance for many workloads.

**Key features:**
- Support for deletion operations (unlike Bloom filters)
- Better lookup performance than Bloom filters
- Comparable false positive rates with better space utilization
- Dynamic resizing capability

**Primary use cases:**
- Content caching with eviction support
- Temporary blacklisting/whitelisting
- Any scenario requiring a Bloom filter with deletion support
- Managing mutable content sets

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import CuckooFilter

# Create a Cuckoo filter
cuckoo = CuckooFilter(capacity=1_000_000, fingerprint_size=8)

# Add content identifiers
cuckoo.add("QmHash1")
cuckoo.add("QmHash2")

# Check membership
if "QmHash1" in cuckoo:
    print("Content might be available")

# Remove an item (not possible with Bloom filters)
cuckoo.remove("QmHash1")
```

### MinHash

A technique for quickly estimating how similar two sets are. It creates a signature for each set, and the similarity of the signatures approximates the Jaccard similarity of the original sets.

**Key features:**
- Fast similarity estimation without needing to compare entire sets
- Configurable accuracy via permutation count
- Support for streaming updates
- Compact representation of sets

**Primary use cases:**
- Finding similar content
- Deduplication of similar files
- Content clustering and recommendation
- Locality-sensitive hashing for nearest neighbor search

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import MinHash

# Create MinHash signatures with 128 permutations
sig1 = MinHash(num_perm=128)
sig2 = MinHash(num_perm=128)

# Update signatures with set elements (e.g., n-grams, chunks, etc.)
for chunk in file1_chunks:
    sig1.update(chunk)
    
for chunk in file2_chunks:
    sig2.update(chunk)
    
# Calculate similarity
similarity = sig1.jaccard(sig2)
print(f"Files are {similarity:.2%} similar")
```

### TopK

A structure for identifying the most frequent items in a data stream, using a Count-Min Sketch and a heap to track candidate frequent items.

**Key features:**
- Memory-efficient tracking of most frequent items
- Configurable with different backing sketches
- Provides both frequency and rank information
- Constant update time with logarithmic retrieval

**Primary use cases:**
- Identifying most requested content
- Resource allocation based on popularity
- Cache prefetching for popular content
- Trend analysis and reporting

**Example usage:**
```python
from ipfs_kit_py.cache.probabilistic_data_structures import TopK

# Create a tracker for the top 100 most frequent items
topk = TopK(k=100, width=10000, depth=5)

# Track content accesses
for access in content_accesses:
    topk.add(access.cid)

# Get the most popular content
most_popular = topk.get_top_k()
for cid, frequency in most_popular:
    print(f"{cid}: approximately {frequency} accesses")
```

## ProbabilisticDataStructureManager

The `ProbabilisticDataStructureManager` provides a unified interface for creating, managing, and persisting probabilistic data structures:

```python
from ipfs_kit_py.cache.probabilistic_data_structures import ProbabilisticDataStructureManager

# Create the manager
pds_manager = ProbabilisticDataStructureManager()

# Create a managed Bloom filter
content_filter = pds_manager.create_bloom_filter(
    name="local_content",
    capacity=1_000_000,
    false_positive_rate=0.01
)

# Create a managed HyperLogLog counter
peer_counter = pds_manager.create_hyperloglog(
    name="unique_peers", 
    precision=14
)

# Access existing structures by name
existing_filter = pds_manager.get_structure("local_content")

# Persist structures to disk
pds_manager.save_to_file("/path/to/save.json")

# Load structures from disk
pds_manager.load_from_file("/path/to/save.json")
```

The manager provides methods for creating all supported data structures with appropriate configuration parameters.

## Use Cases in IPFS Kit

The probabilistic data structures in IPFS Kit are used for several key features:

1. **Fast Content Availability Checking**:
   Bloom filters provide a memory-efficient way to check if content is available locally without expensive disk lookups or database queries.

2. **Unique Peer Tracking**:
   HyperLogLog allows tracking the number of unique peers a node has interacted with, using minimal memory regardless of the actual count.

3. **Content Popularity Monitoring**:
   Count-Min Sketch and TopK structures identify popular content for prefetching, caching, and resource allocation decisions.

4. **Content Similarity Detection**:
   MinHash signatures quickly find similar content for deduplication, clustering, and recommendation.

5. **Tiered Cache Optimization**:
   The structures help optimize caching decisions by tracking access patterns, content heat, and relationships between content items.

## Memory/Accuracy Tradeoffs

All probabilistic data structures involve tradeoffs between memory usage and accuracy. The table below provides general guidelines:

| Data Structure | Memory Usage | Error Characteristics | When to Use |
|----------------|--------------|----------------------|-------------|
| Bloom Filter | ~9-15 bits per element for 1% FPR | False positives only, tunable rate | When memory is extremely constrained and false positives are acceptable |
| HyperLogLog | 2^precision bytes (1.6KB at p=10) | Error decreases with √(1/2^p) | When exact cardinality isn't needed |
| Count-Min Sketch | width × depth × 4 bytes | Overestimation only | When relative frequencies matter more than exact counts |
| Cuckoo Filter | ~8-12 bits per element | Similar to Bloom filter | When deletions are needed |
| MinHash | num_perm × 4 bytes per signature | Error decreases with √(1/num_perm) | When set comparison is expensive |
| TopK | Backing sketch size + k × (element size + count size) | Depends on backing sketch | When only most frequent items matter |

## Integration with Tiered Cache

The probabilistic data structures are deeply integrated with the tiered cache system in IPFS Kit:

1. **Cache Decision Making**:
   - Bloom filters identify likely cache hits before expensive lookups
   - Count-Min Sketch tracks content popularity for promotion decisions
   - MinHash identifies related content for predictive prefetching

2. **Metadata Storage Optimization**:
   - The structures reduce metadata storage requirements by orders of magnitude
   - Enable tracking statistics that would be prohibitively expensive otherwise

3. **Performance Enhancement**:
   - Provide constant-time approximations for frequent operations
   - Reduce memory pressure that would affect cache capacity

4. **Scalability**:
   - Allow the cache to maintain quality of service regardless of the number of unique items
   - Provide predictable resource usage in unpredictable workloads

## Performance Benefits

The performance benefits of using probabilistic data structures in IPFS Kit include:

1. **Memory Efficiency**:
   - Orders of magnitude less memory usage than exact data structures
   - Example: Tracking 10 million unique CIDs with ~99% accuracy requires only ~20KB with HyperLogLog vs. 400MB+ with an exact set

2. **Operation Speed**:
   - Constant-time operations regardless of data volume
   - No need for expensive database lookups or disk access

3. **Scalability**:
   - Resource usage remains bounded regardless of data growth
   - Predictable memory and CPU utilization

4. **Distributed System Support**:
   - Many structures support merging for distributed aggregation
   - Well-suited for peer-to-peer environments with partial information

## API Reference

### BloomFilter

```python
BloomFilter(capacity: int, false_positive_rate: float = 0.01)
```

**Methods**:
- `add(item)`: Add an item to the filter
- `__contains__(item)`: Test membership (`item in filter`)
- `get_info()`: Get information about the filter (size, error rate, etc.)

### HyperLogLog

```python
HyperLogLog(precision: int = 14)
```

**Methods**:
- `add(item)`: Add an item to the counter
- `count()`: Get the estimated cardinality
- `merge(other)`: Merge another HyperLogLog into this one
- `get_info()`: Get information about the counter

### CountMinSketch

```python
CountMinSketch(width: int = 1000, depth: int = 5)
```

**Methods**:
- `add(item, count: int = 1)`: Add an item (with optional count)
- `estimate_count(item)`: Get the estimated count for an item
- `get_info()`: Get information about the sketch

### CuckooFilter

```python
CuckooFilter(capacity: int, fingerprint_size: int = 8, bucket_size: int = 4)
```

**Methods**:
- `add(item)`: Add an item to the filter
- `remove(item)`: Remove an item from the filter
- `__contains__(item)`: Test membership (`item in filter`)
- `get_info()`: Get information about the filter

### MinHash

```python
MinHash(num_perm: int = 128, seed: int = 42)
```

**Methods**:
- `update(items)`: Update signature with set elements
- `jaccard(other)`: Calculate Jaccard similarity with another signature
- `get_info()`: Get information about the signature

### TopK

```python
TopK(k: int = 100, width: int = 2000, depth: int = 5)
```

**Methods**:
- `add(item, count: int = 1)`: Add an item (with optional count)
- `get_top_k()`: Get the top k items with estimated counts
- `get_info()`: Get information about the structure

### ProbabilisticDataStructureManager

```python
ProbabilisticDataStructureManager(storage_path: str = None)
```

**Methods**:
- `create_bloom_filter(name, **kwargs)`: Create a managed Bloom filter
- `create_hyperloglog(name, **kwargs)`: Create a managed HyperLogLog
- `create_count_min_sketch(name, **kwargs)`: Create a managed Count-Min Sketch
- `create_cuckoo_filter(name, **kwargs)`: Create a managed Cuckoo filter
- `create_minhash(name, **kwargs)`: Create a managed MinHash
- `create_topk(name, **kwargs)`: Create a managed TopK
- `get_structure(name)`: Get a structure by name
- `save_to_file(filepath)`: Save all structures to a file
- `load_from_file(filepath)`: Load structures from a file

## Examples

### Basic Examples

For complete example usage, see the comprehensive `probabilistic_data_structures_example.py` file in the examples directory, which demonstrates:

- Performance and memory comparisons with exact data structures
- Accuracy/memory tradeoffs with different parameters
- Visualization of error rates and resource usage
- Practical applications in IPFS content management
- Integration with the tiered cache system

```bash
# Run all examples
python -m examples.probabilistic_data_structures_example

# Run specific examples
python -m examples.probabilistic_data_structures_example bloom hll cms
```

The example also generates visualization plots showing the performance characteristics and accuracy/memory tradeoffs of different structures:

- `bloom_filter_comparison.png`: Memory usage vs. error rate for Bloom filters
- `hyperloglog_evaluation.png`: Estimation accuracy vs. precision for HyperLogLog
- `count_min_sketch_evaluation.png`: Frequency estimation accuracy vs. parameters
- `cuckoo_vs_bloom.png`: Comparison between Cuckoo and Bloom filters
- `minhash_evaluation.png`: Similarity estimation accuracy vs. permutations
- `topk_evaluation.png`: Heavy hitter identification accuracy vs. parameters

These visualizations help in selecting appropriate parameters for different use cases.

### Practical Integration Examples

For a comprehensive example showcasing practical integration of probabilistic data structures with IPFS Kit in real-world scenarios, see the `probabilistic_data_structures_integration_example.py` file. This example demonstrates:

- Tracking content popularity with probabilistic structures
- Integrating with the tiered cache system for efficient monitoring
- Building a real-time IPFS content analytics dashboard
- Memory usage comparisons between probabilistic and exact data structures
- Showing memory savings while maintaining acceptable accuracy bounds
- Real-world content access patterns using Zipfian distribution with temporal locality

```bash
# Run the integration example
python -m examples.probabilistic_data_structures_integration_example
```

This integration example particularly focuses on:

1. **Content tracking system** - Process a simulated stream of CID accesses with minimal memory
2. **Tiered cache integration** - Enhance caching decisions using probabilistic data structures
3. **IPFS Kit integration** - Build a lightweight content analytics dashboard

It also includes visualizations that compare memory usage between probabilistic structures and exact implementations, showing actual memory savings while maintaining configurable accuracy bounds.