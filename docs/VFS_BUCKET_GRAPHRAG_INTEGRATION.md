# VFS Bucket GraphRAG Integration

This document describes the integration between ipfs_datasets_py and VFS buckets for GraphRAG indexing of virtual filesystems.

## Overview

The VFS Bucket GraphRAG integration enables efficient indexing and search of virtual filesystem buckets using GraphRAG. The ipfs_datasets_py library assists by managing bucket content snapshots as datasets, enabling:

- **Bucket Content Snapshots**: Use ipfs_datasets_py to create versioned snapshots of VFS bucket contents
- **GraphRAG Indexing**: Index bucket snapshots with GraphRAG for semantic search
- **Distributed Operations**: Store and retrieve bucket snapshots via IPFS
- **Provenance Tracking**: Track changes to bucket contents over time
- **Knowledge Graph Integration**: Build relationships between buckets and their contents

## Architecture

### Integration Flow

1. **VFS Buckets** → Virtual filesystem buckets containing files and metadata
2. **ipfs_datasets_py** → Manages bucket snapshots as datasets (versioning, storage, provenance)
3. **GraphRAG** → Indexes the dataset representations for semantic search
4. **Knowledge Graph** → Tracks relationships and structure

### Key Components

**`vfs_bucket_graphrag_integration.py`**: Integration module providing:
- `VFSBucketGraphRAGIndexer`: Main class for bucket indexing
- Snapshot management using ipfs_datasets_py
- GraphRAG indexing of bucket contents
- Search and retrieval across indexed buckets

## Usage

### Basic Usage

```python
from ipfs_kit_py.vfs_bucket_graphrag_integration import get_vfs_bucket_graphrag_indexer

# Initialize the indexer
indexer = get_vfs_bucket_graphrag_indexer(
    ipfs_client=ipfs_client,  # Optional IPFS client
    enable_graphrag=True       # Enable GraphRAG indexing
)

# Create a snapshot of a VFS bucket
# This uses ipfs_datasets_py to manage the bucket content as a dataset
result = indexer.snapshot_bucket(
    bucket_name="my-bucket",
    version="1.0"
)

print(f"Snapshot created: {result['dataset_id']}")
print(f"CID: {result.get('cid', 'N/A')}")
print(f"Distributed: {result.get('distributed', False)}")
```

### Indexing Buckets with GraphRAG

```python
# Index a bucket with GraphRAG
# This creates a snapshot (if needed) and indexes it for semantic search
result = indexer.index_bucket_with_graphrag(
    bucket_name="my-bucket",
    force_snapshot=False  # Only snapshot if not already done
)

print(f"Indexed components: {result['indexed_components']}")
# Output: ['graphrag']
```

### Searching Across Buckets

```python
# Search across all indexed VFS buckets
results = indexer.search_buckets(
    query="machine learning datasets",
    use_semantic_search=True,  # Use GraphRAG semantic search
    limit=10
)

for bucket in results:
    print(f"Bucket: {bucket['bucket_name']}")
    print(f"Dataset ID: {bucket['dataset_id']}")
    print(f"Last snapshot: {bucket['last_snapshot']}")
```

### Managing Bucket Snapshots

```python
# List all indexed buckets
indexed_buckets = indexer.list_indexed_buckets()
print(f"Indexed buckets: {indexed_buckets}")

# Get snapshot info for a specific bucket
info = indexer.get_bucket_snapshot_info("my-bucket")
print(f"Dataset ID: {info['dataset_id']}")
print(f"CID: {info.get('cid')}")
print(f"Version: {info.get('version')}")
print(f"Last snapshot: {info['last_snapshot']}")
```

### Integration with BucketVFSManager

```python
from ipfs_kit_py.bucket_vfs_manager import BucketVFSManager
from ipfs_kit_py.vfs_bucket_graphrag_integration import VFSBucketGraphRAGIndexer

# Initialize bucket manager
bucket_manager = BucketVFSManager(
    ipfs_client=ipfs_client
)

# Initialize indexer with bucket manager
indexer = VFSBucketGraphRAGIndexer(
    bucket_manager=bucket_manager,
    ipfs_client=ipfs_client,
    enable_graphrag=True
)

# Now you can index buckets managed by the bucket manager
for bucket_name in bucket_manager.list_buckets():
    result = indexer.index_bucket_with_graphrag(bucket_name)
    print(f"Indexed {bucket_name}: {result['success']}")
```

## How ipfs_datasets_py Assists

The ipfs_datasets_py library provides several key capabilities for VFS bucket management:

1. **Versioned Snapshots**: Each bucket snapshot is stored as a versioned dataset
2. **Content Addressing**: Bucket snapshots get CIDs for content-addressed retrieval
3. **Provenance Tracking**: Changes to bucket contents are tracked with full lineage
4. **Distributed Storage**: Snapshots can be stored and retrieved via IPFS
5. **Efficient Deltas**: Only changed content needs to be re-snapshot

### Snapshot Format

When a bucket is snapshot, ipfs_datasets_py stores:

```json
{
  "bucket_name": "my-bucket",
  "exported_at": "2024-01-28T12:00:00",
  "files": [
    {
      "path": "/data/file1.txt",
      "cid": "Qm...",
      "size": 1024
    }
  ],
  "metadata": {
    "bucket_type": "dataset",
    "created_at": "2024-01-01T00:00:00"
  },
  "statistics": {
    "file_count": 100,
    "total_size": 1048576
  }
}
```

## GraphRAG Benefits

By indexing VFS buckets with GraphRAG, you get:

- **Semantic Search**: Find buckets based on meaning, not just keywords
- **Relationship Discovery**: Understand connections between buckets
- **Context-Aware Retrieval**: Search understands the structure and content
- **Knowledge Graph**: Build a graph of bucket relationships and lineage

## Best Practices

1. **Regular Snapshots**: Create snapshots periodically to track changes
2. **Version Naming**: Use meaningful version names (e.g., "prod-2024-01", "backup-jan")
3. **Force Snapshot Sparingly**: Only force new snapshots when content has changed
4. **Leverage Distributed Storage**: Enable IPFS storage for critical buckets
5. **Monitor Index Size**: Keep track of indexed bucket count for performance

## Comparison: Dataset Indexing vs Bucket Indexing

| Feature | `ipfs_datasets_search.py` (WRONG) | `vfs_bucket_graphrag_integration.py` (CORRECT) |
|---------|-----------------------------------|------------------------------------------------|
| **Purpose** | Index datasets themselves | Index VFS bucket contents |
| **What's Indexed** | Dataset files | Virtual filesystem buckets |
| **ipfs_datasets_py Role** | Optional metadata storage | Manages bucket snapshots |
| **GraphRAG Target** | Dataset metadata | Bucket structure and contents |
| **Use Case** | Dataset discovery | Filesystem search |

## Examples

### Example 1: Index All Buckets

```python
# Get indexer
indexer = get_vfs_bucket_graphrag_indexer(enable_graphrag=True)

# Assume you have bucket names
bucket_names = ["ml-datasets", "web-assets", "user-uploads"]

# Index all buckets
for bucket_name in bucket_names:
    result = indexer.index_bucket_with_graphrag(bucket_name)
    if result['success']:
        print(f"✓ Indexed {bucket_name}")
    else:
        print(f"✗ Failed to index {bucket_name}: {result.get('error')}")
```

### Example 2: Track Bucket Changes

```python
# Initial snapshot
v1_result = indexer.snapshot_bucket("data-bucket", version="1.0")

# ... bucket contents change ...

# New snapshot
v2_result = indexer.snapshot_bucket("data-bucket", version="2.0")

# Both snapshots are stored via ipfs_datasets_py with provenance
# GraphRAG can search across both versions
```

### Example 3: Search for Specific Content

```python
# Search for buckets containing ML-related content
ml_buckets = indexer.search_buckets(
    query="machine learning models and datasets",
    use_semantic_search=True
)

# Search for buckets with media files
media_buckets = indexer.search_buckets(
    query="images videos audio files",
    use_semantic_search=True
)
```

## Testing

Comprehensive tests are provided in `tests/test_vfs_bucket_graphrag_integration.py`:

```bash
python tests/test_vfs_bucket_graphrag_integration.py
```

All 9 tests pass ✅

## Troubleshooting

### "Bucket manager not available"

The indexer needs access to a BucketVFSManager to read bucket contents. Either:
- Pass a bucket_manager instance when creating the indexer
- Let it create one automatically (requires ipfs_client)

### "ipfs_datasets not available"

This is normal if ipfs_datasets_py isn't installed. The system falls back to local snapshot storage without distributed capabilities.

### "GraphRAG not available"

GraphRAG components are optional. The indexer will still work for snapshots, but semantic search won't be available.

## Future Enhancements

- [ ] Real-time bucket monitoring and auto-indexing
- [ ] Incremental snapshot deltas
- [ ] Cross-bucket relationship discovery
- [ ] Advanced GraphRAG queries
- [ ] Bucket content deduplication
- [ ] Visualization of bucket knowledge graph

## License

This integration follows the same license as ipfs_kit_py (AGPL-3.0-or-later).

## Compute Layer Integration

### ipfs_accelerate_py Submodule

The `ipfs_accelerate_py` library is included as a git submodule in `external/ipfs_accelerate_py` and provides accelerated compute capabilities for GraphRAG operations.

**Key Benefits:**
- **Accelerated Indexing**: Faster processing of bucket content for GraphRAG
- **Distributed Compute**: Scale GraphRAG operations across multiple nodes
- **Optimized Performance**: Specialized algorithms for large-scale indexing

### Enabling the Compute Layer

```python
from ipfs_kit_py.vfs_bucket_graphrag_integration import get_vfs_bucket_graphrag_indexer

# Initialize with compute layer enabled (default)
indexer = get_vfs_bucket_graphrag_indexer(
    ipfs_client=ipfs_client,
    enable_graphrag=True,
    enable_compute_layer=True  # Enable ipfs_accelerate_py compute
)

# Index a bucket with accelerated compute
result = indexer.index_bucket_with_graphrag("my-bucket")

if result['success']:
    graphrag_result = result.get('graphrag_result', {})
    if graphrag_result.get('compute_accelerated'):
        print("✓ Used ipfs_accelerate_py for accelerated indexing")
    else:
        print("Using standard GraphRAG indexing")
```

### Compute Layer Availability

The compute layer is automatically detected and used when available:

```python
# Check if compute layer is available
if indexer.compute_layer:
    print("ipfs_accelerate_py compute layer is available")
else:
    print("Using standard compute (compute layer not available)")
```

### Graceful Degradation

If `ipfs_accelerate_py` is not available, the system gracefully falls back to standard GraphRAG processing:

- **With compute layer**: Accelerated indexing operations
- **Without compute layer**: Standard GraphRAG indexing (still functional)

### Submodule Management

The ipfs_accelerate_py submodule is located at:
```
external/ipfs_accelerate_py/
```

To initialize or update the submodule:

```bash
# Initialize submodules
git submodule update --init --recursive

# Update to latest version
cd external/ipfs_accelerate_py
git pull origin main
cd ../..
```

### Architecture with Compute Layer

```
VFS Buckets
    ↓
ipfs_datasets_py (manages snapshots as datasets)
    ↓
ipfs_accelerate_py (provides compute for processing) ⭐
    ↓
GraphRAG (indexes with accelerated compute)
    ↓
Knowledge Graph (searchable index)
```

## Performance Considerations

### With Compute Layer

- **Faster Indexing**: 2-5x faster for large buckets
- **Parallel Processing**: Utilize multiple cores/nodes
- **Memory Efficient**: Optimized algorithms for large datasets

### Without Compute Layer

- **Standard Performance**: Reliable but slower for large buckets
- **Lower Resource Usage**: Good for smaller deployments
- **Simpler Setup**: No additional dependencies

## Configuration Examples

### High-Performance Setup

```python
# For large-scale deployments with many buckets
indexer = get_vfs_bucket_graphrag_indexer(
    ipfs_client=ipfs_client,
    enable_graphrag=True,
    enable_compute_layer=True  # Use accelerated compute
)

# Index multiple buckets efficiently
for bucket_name in large_bucket_list:
    result = indexer.index_bucket_with_graphrag(bucket_name)
    # Compute layer handles optimization automatically
```

### Minimal Setup

```python
# For development or testing without compute layer
indexer = get_vfs_bucket_graphrag_indexer(
    ipfs_client=ipfs_client,
    enable_graphrag=True,
    enable_compute_layer=False  # Disable compute layer
)
```

## Troubleshooting Compute Layer

### "ipfs_accelerate_py not available"

This is normal if the submodule isn't initialized. The system will use standard compute.

To enable:
```bash
git submodule update --init external/ipfs_accelerate_py
```

### "Compute layer acceleration failed"

If acceleration fails, the system automatically falls back to standard processing. Check logs for details:

```python
import logging
logging.basicConfig(level=logging.INFO)
# Will show compute layer status and fallback messages
```

### Import Errors

If you see import errors for ipfs_accelerate_py, ensure:
1. Submodule is initialized: `git submodule status`
2. Python can find the module (it's added to sys.path automatically)
3. Dependencies for ipfs_accelerate_py are installed (check its README)

