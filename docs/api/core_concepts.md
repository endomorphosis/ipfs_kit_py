# IPFS Kit Core Concepts

> **Status**: ✅ **Production Ready** - Core concepts implemented and operational  
> **Implementation**: Multi-backend storage with distributed cluster architecture  
> **Current System**: See **[MCP Development Status](../ARCHIVE/status-reports/MCP_DEVELOPMENT_STATUS.md)** for production implementation details

This document explains the fundamental concepts behind the `ipfs_kit_py` library, providing a comprehensive overview of its production-ready architecture, components, and usage patterns.

## Content Addressing: The Foundation

At the heart of IPFS Kit is content addressing - a method of identifying data by its content rather than its location, enhanced with multi-backend storage capabilities. 

### Content Identifiers (CIDs)

Content addressing in IPFS uses Content Identifiers (CIDs), which are unique fingerprints generated from the data itself:

```
QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx  # Example CIDv0
bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi  # Example CIDv1
```

Key properties of content addressing:

1. **Immutability**: The same content always produces the same CID
2. **Integrity**: Any change to the content produces a different CID
3. **Deduplication**: Identical content stored once, regardless of how many times it's added
4. **Location Independence**: Content can be retrieved from any peer that has it
5. **Verifiability**: You can verify that received content matches its CID

IPFS Kit leverages content addressing for reproducible data workflows, with CIDs serving as the foundation for its distributed architecture.

## Main Architecture

The `ipfs_kit_py` library implements a layered architecture with these key components:

```
┌───────────────────────────────────────────────────────────┐
│                   IPFSSimpleAPI (High-Level API)          │
└───────────────────────────────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────┐
│                        ipfs_kit                           │
└───────────┬──────────┬──────────┬───────────┬─────────────┘
            │          │          │           │
            ▼          ▼          ▼           ▼
┌──────────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐
│   ipfs_py    │ │ ipget   │ │ s3_kit  │ │ storacha_kit  │
└──────────────┘ └─────────┘ └─────────┘ └───────────────┘
       │
       │
       ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│ ipfs_cluster_service │◄───┤    Role-specific            │
└──────────────────────┘    │    components based on      │
       │                    │    master/worker/leecher    │
       │                    └─────────────────────────────┘
       ▼
┌────────────────────────┐
│ Advanced Components:   │
│ - FSSpec Integration   │
│ - Tiered Cache         │
│ - Arrow Metadata Index │
│ - libp2p Direct P2P    │
│ - IPLD Knowledge Graph │
│ - AI/ML Integration    │
└────────────────────────┘
```

## Main `ipfs_kit` Class

The central point of interaction is the `ipfs_kit` class found in `ipfs_kit_py/ipfs_kit.py`. It acts as an orchestrator, initializing and providing access to various IPFS-related functionalities based on configuration and node role.

### Initialization

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Basic initialization (defaults to 'leecher' role)
kit = ipfs_kit()

# Initialize with a specific role and configuration
config_data = {
    "role": "worker",
    "cluster_name": "my-cluster",
    "ipfs_path": "~/.ipfs-worker",
    "enable_libp2p": True,
    "cache_config": {
        "memory_cache_size": 512 * 1024 * 1024,  # 512MB
        "disk_cache_path": "~/.ipfs_cache",
        "disk_cache_size": 10 * 1024 * 1024 * 1024  # 10GB
    },
    "enable_ai_ml": True
}
kit_worker = ipfs_kit(metadata=config_data)

# Initialize master with cluster management enabled
kit_master = ipfs_kit(
    metadata={
        "role": "master", 
        "enable_cluster_management": True,
        "cluster_config": {
            "replication_factor": 3,
            "consensus": "crdt"
        }
    }
)
```

The `metadata` dictionary passed during initialization is crucial for configuring the kit's behavior and enabling specific features.

### Initialization Process

When you create an instance of `ipfs_kit`, it performs these steps:

1. **Parse configuration**: Combine explicit parameters, environment variables, and config files
2. **Determine role**: Set up as master, worker, or leecher
3. **Initialize core IPFS daemon**: Set up connection to the IPFS daemon
4. **Initialize role-specific components**: Start cluster services, followers, etc.
5. **Set up advanced components**: Based on configuration (FSSpec, cache, etc.)
6. **Enable optional features**: AI/ML integration, libp2p direct, metadata index, etc.

### Error Handling Pattern

The `ipfs_kit` library uses a consistent error handling pattern with structured result dictionaries:

```python
# All operations return a structured result dictionary
result = kit.ipfs.add("my_file.txt")

# Standard result structure
if result.get("success"):
    cid = result.get("cid") or result.get("Hash")
    print(f"Successfully added file with CID: {cid}")
else:
    error = result.get("error")
    error_type = result.get("error_type")
    print(f"Operation failed: {error} (Type: {error_type})")
```

## Node Roles

IPFS Kit operates with different node roles, each optimized for specific tasks within a distributed system:

### Role Comparison

| Feature | Master | Worker | Leecher |
|---------|--------|--------|---------|
| **Purpose** | Network coordination | Processing and storage | Content consumption |
| **IPFS Components** | Full IPFS daemon | Full IPFS daemon | IPFS daemon (minimal) |
| **Cluster Components** | `ipfs-cluster-service` | `ipfs-cluster-follow` | None |
| **Resource Requirements** | High CPU/RAM/Disk | Medium CPU/RAM, high disk | Low CPU/RAM/Disk |
| **Responsibilities** | Content orchestration, metadata management, task distribution | Content processing, storage, task execution | Content retrieval, local caching |
| **Preferred Deployment** | Stable server | Cloud instance or powerful workstation | Edge device, laptop, client |
| **Common Operations** | Pin management, cluster administration | Content processing, data transformation | Content retrieval, viewing |
| **Scalability Role** | Central coordinator (limited horizontal scaling) | Compute/storage worker (horizontal scaling) | Edge client (unlimited scaling) |

### 1. Master Role

The master role is designed to coordinate the IPFS network and cluster:

```python
# Initialize as a master node
kit_master = ipfs_kit(
    metadata={
        "role": "master",
        "enable_cluster_management": True,
        "cluster_config": {
            "secret": "your-cluster-secret-key",  # Required for security
            "replication_factor": 3,  # Content replicated to 3 nodes
            "consensus": "crdt"  # Using CRDT consensus (recommended)
        }
    }
)

# Operations specific to master nodes
# Add content and pin across the cluster
add_result = kit_master.ipfs.add("important_data.txt")
if add_result.get("success"):
    cid = add_result.get("Hash")
    # Pin to the cluster, which will distribute to worker nodes
    pin_result = kit_master.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(cid)
    print(f"Content {cid} pinned to cluster with status: {pin_result.get('status')}")
    
    # Monitor pinning status across the cluster
    status_result = kit_master.ipfs_cluster_ctl.ipfs_cluster_ctl_status(cid)
    for peer_id, status in status_result.get('peer_map', {}).items():
        print(f"Peer {peer_id}: {status.get('status')}")
```

### 2. Worker Role

The worker role focuses on executing tasks and storing content:

```python
# Initialize as a worker node that follows a master
kit_worker = ipfs_kit(
    metadata={
        "role": "worker",
        "cluster_name": "my-cluster",
        "master_multiaddress": "/ip4/192.168.1.100/tcp/9096/p2p/QmMasterPeerID",
        "enable_processing": True,  # Enable content processing capabilities
        "worker_resources": {
            "storage_quota": "100GB",
            "processing_threads": 4,
            "gpu_enabled": True
        }
    }
)

# Worker-specific operations
# Check connection to master
follow_status = kit_worker.ipfs_cluster_follow.get_status()
if follow_status.get("success"):
    print(f"Following master with {follow_status.get('pin_count')} pins")

# Process a task received from the cluster
def process_task(task_data):
    task_type = task_data.get("type")
    if task_type == "transform_image":
        # Process image transformation task
        input_cid = task_data.get("input_cid")
        # Get the image content
        content = kit_worker.ipfs.cat(input_cid)
        # ... transformation logic ...
        # Store result back to IPFS
        result_cid = kit_worker.ipfs.add_bytes(transformed_content)
        return {"success": True, "result_cid": result_cid}
    return {"success": False, "error": "Unknown task type"}
```

### 3. Leecher Role

The leecher role is optimized for content consumption with minimal resource usage:

```python
# Initialize as a leecher node
kit_leecher = ipfs_kit(
    metadata={
        "role": "leecher",
        "bootstrap_peers": [
            "/ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ"
        ],
        "cache_config": {
            "memory_cache_size": 128 * 1024 * 1024,  # 128MB memory cache
            "disk_cache_size": 1 * 1024 * 1024 * 1024  # 1GB disk cache
        }
    }
)

# Leecher-specific operations
# Retrieve content with local caching
content = kit_leecher.ipfs.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
if content.get("success"):
    data = content.get("content")
    print(f"Retrieved {len(data)} bytes of content")
    
    # Access as filesystem (uses cache)
    fs = kit_leecher.get_filesystem()
    with fs.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "r") as f:
        data = f.read()
```

## Interaction Patterns

You can interact with the `ipfs_kit` instance in several ways:

### 1. Direct Method Calls

Access methods directly on the `kit` object or its sub-components:

```python
# Add a file using the ipfs component
add_result = kit.ipfs.add("my_file.txt")
if add_result.get("success"):
    cid = add_result.get("Hash")
    print(f"Added file with CID: {cid}")

# If master, add pin to cluster
if kit.role == "master" and hasattr(kit, 'ipfs_cluster_ctl'):
   pin_result = kit.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(cid)
   print(f"Pinned to cluster: {pin_result.get('status')}")

# Get node ID
id_result = kit.ipfs_id()
if id_result.get("success"):
    peer_id = id_result.get("ID")
    print(f"Node ID: {peer_id}")
```

### 2. Callable Interface

Use the `kit` object itself as a function, passing the method name as the first argument. This provides a unified way to call methods across different underlying components based on the node's role:

```python
# Add a file (delegates appropriately based on role)
add_result = kit("ipfs_add_path", path="my_file.txt")
if add_result.get("success"):
    cid = add_result.get("cid") or add_result.get("Hash")
    print(f"Added file with CID: {cid}")

# Pin content (delegates appropriately based on role)
# - On master: uses cluster pin
# - On worker/leecher: uses local pin
pin_result = kit("ipfs_add_pin", cid=cid)
if pin_result.get("success"):
    print(f"Content pinned successfully")

# Get cluster status (only works if master/worker with cluster components)
try:
    status = kit("ipfs_cluster_status")
    if status.get("success"):
        print(f"Cluster has {len(status.get('peer_map', {}))} peers")
except (AttributeError, PermissionError) as e:
    print(f"Operation not available for role {kit.role}: {e}")
```

### 3. High-Level API

For simpler interactions, the `IPFSSimpleAPI` provides a streamlined interface:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Create a simple API instance
simple_api = IPFSSimpleAPI()

# Add content
cid = simple_api.add_file("my_file.txt")

# Get content
content = simple_api.cat(cid)

# Pin content
simple_api.pin(cid)
```

See the [High-Level API documentation](high_level_api.md) for more details.

## Configuration

Configuration can be provided via:

### 1. Metadata Dictionary

The most direct method is passing a metadata dictionary during initialization:

```python
kit = ipfs_kit(metadata={
    "role": "worker",
    "ipfs_path": "~/.ipfs-custom",
    "enable_libp2p": True,
    "cache_config": {
        "memory_cache_size": 512 * 1024 * 1024,  # 512MB
        "disk_cache_size": 5 * 1024 * 1024 * 1024  # 5GB
    }
})
```

### 2. Environment Variables

Environment variables can be used to configure the kit:

```bash
# Set environment variables
export IPFS_KIT_ROLE="master"
export IPFS_KIT_CLUSTER_NAME="production-cluster"
export IPFS_KIT_ENABLE_LIBP2P="true"
export IPFS_KIT_MEMORY_CACHE_SIZE="1073741824"  # 1GB
```

```python
# Environment variables will be automatically used
kit = ipfs_kit()  # Will be a master node due to environment variable
```

### 3. Configuration File

YAML or JSON configuration files can be used, especially with the High-Level API:

```yaml
# config.yaml
role: worker
cluster_name: production-cluster
ipfs_path: ~/.ipfs-worker
enable_libp2p: true
cache_config:
  memory_cache_size: 536870912  # 512MB
  disk_cache_size: 5368709120   # 5GB
```

```python
# Load from configuration file
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

api = IPFSSimpleAPI(config_path="config.yaml")
```

### Configuration Priority

The `ipfs_kit` class prioritizes configurations in this order:
1. Explicit parameters in the `metadata` dictionary
2. Environment variables
3. Configuration file settings

## Multi-Tiered Caching System

IPFS Kit implements a sophisticated multi-tiered caching system that optimizes performance for content access:

```
┌──────────────────┐
│ Memory Cache     │ ◄─── Fastest access (ARC algorithm)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Disk Cache       │ ◄─── Persistent local storage
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Local IPFS Node  │ ◄─── Content pinned locally
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ IPFS Cluster     │ ◄─── Content pinned across cluster
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ IPFS Swarm       │ ◄─── Content available on the network
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Gateway/Storacha │ ◄─── Backup content sources
└──────────────────┘
```

The caching system automatically manages content movement between tiers based on access patterns, using an Adaptive Replacement Cache (ARC) algorithm that balances recency and frequency.

```python
# Configure the caching system
kit = ipfs_kit(metadata={
    "cache_config": {
        "memory_cache_size": 512 * 1024 * 1024,  # 512MB memory cache
        "disk_cache_path": "~/.ipfs_cache",      # Location for disk cache
        "disk_cache_size": 10 * 1024 * 1024 * 1024,  # 10GB disk cache
        "min_item_size": 4096,  # Items smaller than 4KB always go to memory
        "max_memory_item_size": 50 * 1024 * 1024,  # Items larger than 50MB skip memory
        "prefetch_enabled": True  # Enable predictive prefetching
    }
})

# The cache is used automatically when accessing content
content1 = kit.ipfs.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")  # First access (not cached)
content2 = kit.ipfs.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")  # Cached access (much faster)

# Access cache metrics
if hasattr(kit, 'tiered_cache'):
    metrics = kit.tiered_cache.get_metrics()
    print(f"Memory cache hit rate: {metrics.get('memory_hit_rate', 0):.2f}")
    print(f"Disk cache hit rate: {metrics.get('disk_hit_rate', 0):.2f}")
    print(f"Average access time: {metrics.get('avg_access_time_ms', 0):.2f}ms")
```

See the [Tiered Cache documentation](../reference/tiered_cache.md) for more details.

## Content Operations

IPFS Kit provides various methods for working with content:

### Adding Content

```python
# Add a file
add_result = kit.ipfs.add("/path/to/file.txt")
if add_result.get("success"):
    cid = add_result.get("Hash")
    print(f"Added file with CID: {cid}")

# Add a directory recursively
dir_result = kit.ipfs.add_directory("/path/to/folder")
if dir_result.get("success"):
    dir_cid = dir_result.get("Hash")
    print(f"Added directory with CID: {dir_cid}")

# Add content from memory
content = b"Hello, IPFS!"
bytes_result = kit.ipfs.add_bytes(content)
if bytes_result.get("success"):
    bytes_cid = bytes_result.get("Hash")
    print(f"Added bytes with CID: {bytes_cid}")
```

### Retrieving Content

```python
# Retrieve file content
cat_result = kit.ipfs.cat("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
if cat_result.get("success"):
    content = cat_result.get("content")
    print(f"Retrieved {len(content)} bytes")

# Get a file to a specific location
get_result = kit.ipfs.get("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "/tmp/retrieved_file.txt")
if get_result.get("success"):
    print(f"Retrieved file to: {get_result.get('output_path')}")

# List directory contents
ls_result = kit.ipfs.ls("QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
if ls_result.get("success"):
    for item in ls_result.get("Objects", [{}])[0].get("Links", []):
        print(f"{item.get('Name')} ({item.get('Hash')}) - {item.get('Size')} bytes")
```

### Pinning Content

```python
# Pin content locally
pin_result = kit.ipfs.pin_add("QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx")
if pin_result.get("success"):
    print("Content pinned locally")

# Pin to cluster (master/worker only)
if kit.role in ["master", "worker"] and hasattr(kit, "ipfs_cluster_ctl"):
    cluster_pin = kit.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(
        "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
        replication_factor=3
    )
    if cluster_pin.get("success"):
        print(f"Pinned to cluster with replication factor 3")

# List pinned content
pins_result = kit.ipfs.pin_ls()
if pins_result.get("success"):
    pins = pins_result.get("Keys", {})
    print(f"Locally pinned items: {len(pins)}")
```

## FSSpec Integration

IPFS Kit includes an FSSpec-compatible filesystem interface, enabling seamless integration with data science libraries:

```python
# Get the filesystem interface
fs = kit.get_filesystem()

# FSSpec operations
# List directory contents
files = fs.ls("ipfs://QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn")
for file in files:
    print(file)

# Open and read a file
with fs.open("ipfs://QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx", "r") as f:
    content = f.read()
    print(f"Read {len(content)} bytes")

# Integration with data science libraries
import pandas as pd

# Read a CSV file directly from IPFS
df = pd.read_csv("ipfs://QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV", filesystem=fs)
print(df.head())

# Read a Parquet file from IPFS
import pyarrow.parquet as pq
table = pq.read_table("ipfs://QmXH6qjnYXCSfc5Wn1jZyZV8AtrNKgWbXLLGJvXVYzk4wC", filesystem=fs)
df2 = table.to_pandas()
print(df2.head())
```

See the [FSSpec Integration documentation](../integration/fsspec_integration.md) for more details.

## Key Sub-Modules

The `ipfs_kit_py` library is organized into several key modules, each responsible for specific functionality:

### Core Components

-   `ipfs.py`: Handles core IPFS daemon interactions and content operations
-   `ipfs_multiformats.py`: Utilities for working with CIDs and multiaddresses

### Cluster Components

-   `ipfs_cluster_service.py`: Manages the IPFS Cluster daemon (Master role)
-   `ipfs_cluster_ctl.py`: Interface for controlling the IPFS Cluster (Master role)
-   `ipfs_cluster_follow.py`: Manages following the cluster pinset (Worker role)
-   `cluster/`: Advanced cluster management modules:
    - `cluster_management.py`: Core cluster management operations
    - `cluster_state.py`: Shared state management across the cluster
    - `cluster_state_helpers.py`: Helper functions for state operations
    - `cluster_monitoring.py`: Monitoring and metrics for cluster operations
    - `cluster_dynamic_roles.py`: Dynamic role switching based on resources
    - `distributed_coordination.py`: Distributed task coordination

### Storage and Retrieval

-   `ipfs_fsspec.py`: Implements the FSSpec interface for filesystem-like access
-   `tiered_cache.py`: Multi-tier caching system with adaptive replacement algorithm
-   `s3_kit.py`: Amazon S3-compatible storage integration
-   `storacha_kit.py`: Web3.Storage/Storacha integration

### Metadata and Indexing

-   `arrow_metadata_index.py`: Arrow-based metadata indexing for efficient queries
-   `ipld_knowledge_graph.py`: IPLD-based knowledge graph implementation

### Networking

-   `libp2p/`: Direct P2P communication modules:
    - `libp2p_peer.py`: Direct libp2p peer implementation
    - `enhanced_dht_discovery.py`: Enhanced peer discovery mechanisms
    - `p2p_integration.py`: Integration with the libp2p ecosystem

### AI/ML Integration

-   `ai_ml_integration.py`: Machine learning integration components:
    - `ModelRegistry`: Model storage and versioning
    - `DatasetManager`: Dataset management
    - `IPFSDataLoader`: High-performance data loader for training
    - `LangchainIntegration` / `LlamaIndexIntegration`: LLM framework connectors
    - `DistributedTraining`: ML training across cluster nodes

### API and CLI

-   `high_level_api.py`: Simplified `IPFSSimpleAPI` interface
-   `cli.py`: Command-line interface
-   `api.py`: FastAPI-based REST API server

## Example Workflows

### Basic Content Management

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize kit
kit = ipfs_kit()

# Add a file to IPFS
add_result = kit.ipfs.add("example.txt")
if add_result.get("success"):
    cid = add_result.get("Hash")
    print(f"Added file with CID: {cid}")
    
    # Pin locally for persistence
    kit.ipfs.pin_add(cid)
    
    # Retrieve content
    content = kit.ipfs.cat(cid)
    if content.get("success"):
        print(f"Content: {content.get('content').decode('utf-8')}")
```

### Distributed Dataset Processing

```python
# Master node: Prepare and distribute data
master = ipfs_kit(metadata={"role": "master", "enable_cluster_management": True})

# Add a large dataset to IPFS
dataset_result = master.ipfs.add_directory("/path/to/large_dataset")
if dataset_result.get("success"):
    dataset_cid = dataset_result.get("Hash")
    print(f"Dataset added with CID: {dataset_cid}")
    
    # Pin to cluster (distributes across workers)
    master.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(dataset_cid)
    
    # Create processing tasks for workers
    # (In a real scenario, this would be handled by cluster_management)
    for i in range(10):
        task = {
            "task_id": f"task_{i}",
            "dataset_cid": dataset_cid,
            "process_subset": f"subset_{i}",
            "output_prefix": f"result_{i}"
        }
        master.cluster_manager.submit_task(task)

# Worker node: Process assigned tasks
worker = ipfs_kit(metadata={"role": "worker"})

# Process task (simplified example)
def process_task(task):
    # Get the dataset
    dataset_path = worker.ipfs.get(task["dataset_cid"], "/tmp/dataset")
    if dataset_path.get("success"):
        # Process the data
        result_data = f"Processed result for {task['task_id']}"
        
        # Store result back to IPFS
        result = worker.ipfs.add_str(result_data)
        if result.get("success"):
            result_cid = result.get("Hash")
            
            # Report back to master
            return {"task_id": task["task_id"], "result_cid": result_cid}
```

### Data Science Integration

```python
import pandas as pd
import matplotlib.pyplot as plt
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize kit with FSSpec support
kit = ipfs_kit()
fs = kit.get_filesystem()

# Read a CSV file directly from IPFS
df = pd.read_csv("ipfs://QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV", filesystem=fs)

# Perform analysis
df['value_squared'] = df['value'] ** 2
result = df.groupby('category').agg({'value': 'mean', 'value_squared': 'mean'})

# Create a visualization
plt.figure(figsize=(10, 6))
result.plot(kind='bar')
plt.title('Category Analysis')
plt.savefig('analysis.png')

# Store results back to IPFS
result_csv = result.to_csv()
add_result = kit.ipfs.add_str(result_csv)
if add_result.get("success"):
    result_cid = add_result.get("Hash")
    print(f"Analysis results stored with CID: {result_cid}")
    
    # Store visualization
    img_result = kit.ipfs.add("analysis.png")
    if img_result.get("success"):
        img_cid = img_result.get("Hash")
        print(f"Visualization stored with CID: {img_cid}")
        
        # Create a metadata record linking everything
        metadata = {
            "title": "Category Analysis",
            "source_data": "QmCSVbfpQL6BjGog5c85xwsJ8arFiBg9ACdHF6RbqXegcV",
            "result_data": result_cid,
            "visualization": img_cid,
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        # Store metadata
        meta_result = kit.ipfs.add_json(metadata)
        if meta_result.get("success"):
            meta_cid = meta_result.get("Hash")
            print(f"Complete analysis package available at: {meta_cid}")
            
            # Pin everything for persistence
            kit.ipfs.pin_add(meta_cid)
```

## Related Documentation

For more detailed information on specific components, refer to these documentation files:

- [High-Level API](high_level_api.md): Simplified interface for common operations
- [FSSpec Integration](../integration/fsspec_integration.md): Filesystem-like interface for IPFS
- [Tiered Cache System](../reference/tiered_cache.md): Multi-tier caching architecture
- [Cluster Management](cluster_management.md): Advanced cluster coordination
- [AI/ML Integration](ai_ml.md): Machine learning tools and integrations
- [Knowledge Graph](knowledge_graph.md): IPLD-based knowledge representation
- [Storage Backends](../reference/storage_backends.md): External storage system integrations
