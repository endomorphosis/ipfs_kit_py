# Metadata Index

The Arrow-based Metadata Index is a high-performance system for storing, querying, and synchronizing metadata about IPFS content. It leverages Apache Arrow's columnar format for efficient storage and retrieval, and provides distributed synchronization capabilities using IPFS pubsub and DAG.

## Features

- **Efficient Storage**: Apache Arrow columnar format for optimal memory usage and query performance
- **Durable Persistence**: Parquet files for efficient on-disk storage
- **Multi-tier Access**: Memory-mapped access for large indexes with tiered caching
- **Rich Query Capabilities**: Flexible filtering with support for complex conditions
- **Distributed Synchronization**: Automatic metadata sharing between nodes
- **Role-based Optimization**: Different behavior for master, worker, and leecher nodes
- **Content Discovery**: Locate content across multiple storage systems
- **Zero-copy Access**: Share index data with other processes using Arrow C Data Interface
- **PubSub Integration**: Real-time updates via IPFS pubsub messaging
- **DAG Publishing**: Make index discoverable via IPFS DAG

## Integration with IPFS Kit

The Metadata Index is fully integrated with IPFS Kit and can be easily enabled through the configuration:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with metadata index enabled
kit = ipfs_kit(
    metadata={"enable_metadata_index": True}
)

# Get the metadata index
index = kit.get_metadata_index()
```

## Python 3.12 Compatibility

As of Python 3.12, PyArrow's Schema objects are immutable, which requires a different approach for working with schemas in test environments. The library includes compatibility layer for this change:

- Uses a standalone comparison function `mock_schema_equals` rather than patching the Schema's `equals` method directly
- Handles MagicMock objects correctly in schema comparisons for testing
- Transparently maintains backward compatibility with earlier Python versions

This ensures the library works seamlessly across Python versions while maintaining test compatibility.

## Schema

The Metadata Index uses a comprehensive schema to capture all relevant information about IPFS content:

| Field | Type | Description |
|-------|------|-------------|
| `cid` | string | Content Identifier (CID) |
| `cid_version` | int8 | CID version (0 or 1) |
| `multihash_type` | string | Multihash algorithm used |
| `size_bytes` | int64 | Content size in bytes |
| `blocks` | int32 | Number of blocks in the content |
| `links` | int32 | Number of links in the DAG |
| `mime_type` | string | Content MIME type |
| `local` | bool | Whether content is available locally |
| `pinned` | bool | Whether content is pinned locally |
| `pin_types` | list[string] | Types of pins (direct, recursive, etc.) |
| `replication` | int16 | Replication factor in cluster |
| `created_at` | timestamp | When the content was added |
| `last_accessed` | timestamp | When the content was last accessed |
| `access_count` | int32 | Number of times content was accessed |
| `path` | string | UnixFS path if part of a directory |
| `filename` | string | Original filename if known |
| `extension` | string | File extension if applicable |
| `tags` | list[string] | User-defined tags |
| `metadata` | struct | Additional metadata fields |
| `properties` | map | Arbitrary key-value properties |
| `storage_locations` | struct | Where content is stored (multiple backends) |

## Storage Locations Tracking

The index can track content across multiple storage systems:

```python
# Example record with multiple storage locations
record = {
    "cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
    "size_bytes": 1024,
    "mime_type": "text/plain",
    "storage_locations": {
        # IPFS node storage
        "ipfs": {
            "pinned": True,
            "local": True,
            "pin_types": ["recursive"],
            "gateway_urls": ["https://ipfs.io/ipfs/QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx"]
        },
        # IPFS Cluster storage
        "ipfs_cluster": {
            "pinned": True,
            "replication_factor": 3,
            "allocation_nodes": ["QmNode1", "QmNode2", "QmNode3"],
            "pin_status": "pinned"
        },
        # Available on these libp2p peers
        "libp2p": {
            "peers": ["QmPeer1", "QmPeer2"],
            "protocols": ["/ipfs/bitswap/1.2.0"],
            "multiaddrs": ["/ip4/192.168.1.1/tcp/4001/p2p/QmPeer1"]
        },
        # Storacha/Web3.Storage
        "storacha": {
            "car_cid": "QmCarFile",
            "upload_id": "upload-123",
            "space_did": "did:key:123",
            "stored_timestamp": "2023-06-15T14:22:31Z"
        },
        # S3 storage (multiple buckets/regions)
        "s3": [
            {
                "provider": "aws",
                "region": "us-east-1",
                "bucket": "mybucket",
                "key": "example.txt",
                "storage_class": "STANDARD"
            },
            {
                "provider": "minio",
                "region": "us-east-1",
                "bucket": "backup",
                "key": "archived/example.txt"
            }
        ],
        # Filecoin storage
        "filecoin": {
            "deal_id": "deal-123456",
            "providers": ["f01234", "f05678"],
            "replication_factor": 2,
            "deal_expiration": "2024-06-15T14:22:31Z",
            "verified_deal": True
        },
        # HuggingFace Hub
        "huggingface_hub": {
            "repo_id": "user/model",
            "repo_type": "model",
            "file_path": "example.txt",
            "revision": "main",
            "commit_hash": "1234abcd"
        }
    }
}
```

## Basic Usage

### Adding Records

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with metadata index enabled
kit = ipfs_kit(
    metadata={"enable_metadata_index": True}
)
index = kit.get_metadata_index()

# Add a record
record = {
    "cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
    "size_bytes": 1024,
    "mime_type": "text/plain",
    "filename": "example.txt",
    "metadata": {
        "title": "Example Document",
        "description": "This is a test document"
    }
}
result = index.add_record(record)
print(f"Added record: {result['success']}")
```

### Querying Records

```python
# Simple query with conditions
results = index.query([
    ("mime_type", "==", "text/plain"),
    ("size_bytes", "<", 10000)
])

# Convert to pandas DataFrame for analysis
import pandas as pd
df = results.to_pandas()
print(df.head())

# Find records with specific tags
tagged_results = index.query([
    ("tags", "contains", "important")
])

# Find records by creation date
recent_results = index.query([
    ("created_at", ">", "2023-06-01T00:00:00Z")
])

# Combine multiple conditions
complex_results = index.query([
    ("mime_type", "==", "application/pdf"),
    ("size_bytes", ">", 1024 * 1024),  # Larger than 1MB
    ("pinned", "==", True)
])
```

### Finding Content Locations

```python
# Find all available storage locations for a specific CID
locations = index.find_content_locations(cid="QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")

# Check if the content is locally available
if locations["success"]:
    for location in locations["locations"]:
        if location["type"] == "ipfs" and location["local"]:
            print(f"Content available locally with pinned status: {location['pinned']}")
            
    # Get the fastest retrieval path
    fastest = locations["fastest_retrieval_path"]
    print(f"Fastest retrieval: {fastest['type']} with estimated latency {fastest['latency_estimate_ms']}ms")
```

### Synchronizing with Peers

Master and worker nodes can synchronize their index with peers:

```python
# Synchronize with all known peers
result = kit.sync_metadata_index()
print(f"Synchronized with {result.get('peers_synced', 0)} peers")

# Synchronize with specific peers
result = kit.sync_metadata_index(
    peer_ids=["QmPeerID1", "QmPeerID2"]
)
```

### Publishing the Index

Make the index discoverable via IPFS DAG:

```python
# Publish the index to IPFS DAG
result = kit.publish_metadata_index()
print(f"Published index with DAG CID: {result.get('dag_cid')}")
print(f"IPNS name: {result.get('ipns_name')}")
```

## Advanced Usage

### Text Search

The metadata index supports text search across fields:

```python
# Search for documents containing specific text
search_results = index.text_search("machine learning", fields=["metadata.title", "metadata.description"])

# Combine text search with other conditions
combined_results = index.text_search(
    "neural network",
    fields=["metadata.title", "metadata.description"],
    filters=[
        ("mime_type", "==", "application/pdf"),
        ("created_at", ">", "2023-01-01T00:00:00Z")
    ]
)
```

### Zero-copy Access from Other Processes

Access the index from other processes using Arrow C Data Interface:

```python
from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex

# Get access information from the index
c_data_interface = index.get_c_data_interface()

# In another process
result = ArrowMetadataIndex.access_via_c_data_interface(c_data_interface)
if result["success"]:
    table = result["table"]
    print(f"Accessed index with {table.num_rows} records via C Data Interface")
```

### Low-level PubSub Control

For advanced control over synchronization:

```python
# Manually start/stop the sync handler
sync_handler = kit._metadata_sync_handler

# Stop synchronization
sync_handler.stop()

# Restart with custom interval
sync_handler.start(sync_interval=120)  # 2 minutes

# Manually send partition request to a peer
sync_handler.request_partition_metadata(peer_id="QmPeerID", partition_id=3)

# Manually request a specific partition
sync_handler.request_partition_data(peer_id="QmPeerID", partition_id=3)
```

## Role-Based Behavior

The metadata index behaves differently based on the node's role:

- **Master Nodes**:
  - Maintain a complete index
  - Actively publish index DAG
  - Accept and process sync requests from workers and leechers
  - Periodically synchronize with other master nodes

- **Worker Nodes**:
  - Maintain a partial index focused on their workload
  - Subscribe to index updates from master nodes
  - Process sync requests from leechers
  - Contribute index data to master nodes

- **Leecher Nodes**:
  - Maintain minimal index focused on recently accessed content
  - Subscribe to index updates but don't publish
  - Don't process sync requests from other nodes
  - Query master and worker nodes for content location

## Performance Considerations

- **Memory Usage**: The index uses memory mapping for efficient handling of large datasets
- **Partitioning**: Large indexes are automatically partitioned for better performance
- **Compression**: Parquet files use compression for efficient storage
- **Cache Optimization**: Frequently accessed records are kept in memory
- **Sync Frequency**: Adjust sync_interval based on network conditions and update frequency
- **C Data Interface**: Use zero-copy access for sharing index data with other processes

## Implementation Details

The metadata index consists of two main components:

1. **ArrowMetadataIndex**: Core class that manages the data storage, querying, and persistence
2. **MetadataSyncHandler**: Manages pubsub subscriptions and synchronization with peers

The integration with IPFS Kit allows easy access to these components through simple methods while handling the complexity of initialization, configuration, and error handling internally.