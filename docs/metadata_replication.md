# Metadata Replication

## Overview

The Metadata Replication system in IPFS Kit ensures durability and fault tolerance by maintaining multiple copies of filesystem metadata across nodes. It implements sophisticated replication policies with configurable minimum, target, and maximum replication factors.

## Key Features

- **Minimum Replication Factor (3)**: Ensures at least 3 copies of metadata exist for fault tolerance, allowing the system to survive up to 2 node failures
- **Target Replication Factor (4)**: The system aims to maintain 4 copies of metadata under normal operations for optimal balance between redundancy and resource usage
- **Maximum Replication Factor (5)**: Sets an upper bound of 5 copies to prevent excessive replication and control resource usage
- **Quorum-Based Consensus**: Uses a quorum of nodes (max(3, (N/2)+1)) for consistency operations
- **Role-Based Replication**: Different behaviors for master, worker, and leecher nodes
- **Success Level Reporting**: Granular reporting of replication status (TARGET_ACHIEVED, QUORUM_ACHIEVED, BELOW_QUORUM, NO_REPLICATION)
- **Automatic Recovery**: Recovers metadata state after node failures
- **Vector Clock Synchronization**: Uses vector clocks for tracking causality in distributed operations

## Architecture

### Components

The Metadata Replication system consists of the following components:

1. **MetadataReplicationManager**: Core implementation managing replication policies
   - Handles peer registration and monitoring
   - Enforces replication factors
   - Tracks replication status
   - Manages recovery processes

2. **ReplicationLevel**: Defines different replication consistency levels
   - SINGLE: Only replicate to master node
   - QUORUM: Replicate to quorum of nodes (min 3)
   - ALL: Replicate to all available nodes
   - LOCAL_DURABILITY: Ensure local durability before acknowledging
   - TIERED: Replicate across different storage tiers
   - PROGRESSIVE: Progressive replication across tiers and nodes

3. **ReplicationStatus**: Tracks operation status
   - PENDING: Replication requested but not started
   - IN_PROGRESS: Replication in progress
   - COMPLETE: Replication completed successfully
   - PARTIAL: Replication succeeded on some nodes but not all
   - FAILED: Replication failed
   - CONFLICT: Conflict detected during replication

### Replication Flow

The replication process follows these steps:

1. **Initialization**: The system initializes with minimum, target, and maximum replication factors
2. **Peer Discovery**: Available nodes are identified based on their role
3. **Node Selection**: Nodes are selected for replication (up to the maximum factor)
4. **Content Distribution**: Metadata is replicated to selected nodes
5. **Status Verification**: Success is determined based on the number of successful replications
6. **Success Level Reporting**: Detailed status is reported based on which replication goals were achieved

## Usage Guide

### Basic Usage with High-Level API

To use the metadata replication system with the high-level API:

```python
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# Initialize API with metadata replication enabled
api = IPFSSimpleAPI(
    config={
        "role": "master",
        "metadata_replication": {
            "enabled": True,
            "min_replication_factor": 3,  # Minimum for fault tolerance
            "target_replication_factor": 4,  # Target for optimal performance
            "max_replication_factor": 5,   # Maximum to limit resource usage
            "replication_level": "QUORUM",  # Ensure quorum consistency
            "progressive_replication": True  # Enable tiered replication
        }
    }
)

# Store metadata with replication
metadata = {
    "id": "metadata-123",
    "name": "example.txt",
    "size": 1024,
    "created_at": time.time(),
    "tags": ["example", "documentation"]
}

result = api.store_metadata(
    metadata=metadata,
    replicate=True,  # Enable replication
    replication_level="QUORUM"  # Specify consistency level
)

print(f"Replication succeeded: {result['success']}")
print(f"Success level: {result.get('success_level', 'N/A')}")
print(f"Replicated to {result.get('successful_replications', 0)} nodes")
```

### Advanced Configuration

For more advanced configuration:

```python
from ipfs_kit_py.fs_journal_replication import (
    MetadataReplicationManager,
    ReplicationLevel,
    ReplicationStatus
)

# Create a replication manager with custom configuration
replication_manager = MetadataReplicationManager(
    node_id="my-node-id",
    role="worker",
    config={
        "quorum_size": 3,                    # Minimum replication factor
        "target_replication_factor": 4,      # Target number of copies
        "max_replication_factor": 5,         # Maximum number of copies
        "default_replication_level": ReplicationLevel.QUORUM,
        "checkpoint_interval": 300,          # 5 minutes
        "sync_interval": 30,                 # 30 seconds
        "auto_recovery": True                # Automatically recover on startup
    }
)

# Register peer nodes
replication_manager.register_peer("master-node", {"role": "master"})
replication_manager.register_peer("worker-node-1", {"role": "worker"})
replication_manager.register_peer("worker-node-2", {"role": "worker"})

# Replicate a journal entry
result = replication_manager.replicate_journal_entry(
    journal_entry={
        "entry_id": "entry-123",
        "timestamp": time.time(),
        "path": "/virtual_fs/example.txt",
        "data": {"size": 1024, "is_directory": False}
    },
    replication_level=ReplicationLevel.QUORUM
)

# Check replication status
if result["success"]:
    print(f"Replication succeeded with level: {result['success_level']}")
    print(f"Replicated to {result['success_count']} nodes")
    print(f"Target was {result['target_factor']} nodes")
    print(f"Quorum size was {result['quorum_size']} nodes")
else:
    print(f"Replication failed: {result.get('error', 'Unknown error')}")
```

### Checking Replication Status

To check the status of replication with the high-level API:

```python
# Verify replication status for a specific metadata item
verification_result = api.verify_metadata_replication("metadata-123")

if verification_result["success"]:
    print(f"Replication status: {verification_result['status']}")
    print(f"Success level: {verification_result.get('success_level', 'N/A')}")
    print(f"Replicated to {verification_result.get('replicated_nodes', [])} nodes")
    print(f"Current replication factor: {len(verification_result.get('replicated_nodes', []))}")
    print(f"Target factor: {verification_result.get('target_factor', 0)}")
    print(f"Min factor (quorum): {verification_result.get('quorum_size', 0)}")
else:
    print(f"Verification failed: {verification_result.get('error', 'Unknown error')}")

# Access the metadata
metadata = api.get_metadata("metadata-123")
if metadata:
    print(f"Retrieved metadata: {metadata}")
else:
    print("Failed to retrieve metadata")
```

Or with the lower-level replication manager:

```python
# Get status for a specific entry
status = replication_manager.get_replication_status("entry-123")
if status:
    print(f"Entry status: {status['status']}")
    print(f"Success level: {status.get('success_level', 'N/A')}")
    print(f"Replicated to {status.get('success_count', 0)} nodes")

# Get all replication statuses
all_statuses = replication_manager.get_all_replication_status()
print(f"Total entries: {len(all_statuses)}")
```

### Role-Based Configuration

The replication behavior changes based on the node's role:

- **Master Nodes**:
  - Primary source of truth for metadata
  - Coordinate replication across the cluster
  - Maintain complete metadata state

- **Worker Nodes**:
  - Participate in replication for fault tolerance
  - Contribute to the replication quorum
  - Can serve as backup if master nodes fail

- **Leecher Nodes**:
  - Typically don't participate in metadata replication
  - Focus on consuming content rather than maintaining metadata
  - Minimal resource usage for constrained devices

## Implementation Details

### Quorum Size Calculation

The system ensures a minimum replication factor of 3 by calculating the quorum size as:

```python
quorum_size = max(3, (cluster_size // 2) + 1)
```

This formula ensures:
- With 1-4 nodes: Minimum of 3 copies (or all available nodes if fewer than 3)
- With 5+ nodes: Standard majority quorum (N/2 + 1)

This guarantees fault tolerance even in small clusters, allowing the system to survive up to 2 node failures.

### Node Selection for Replication

When selecting nodes for replication:

```python
# Calculate replication parameters
total_nodes = len(eligible_nodes)
quorum_size = min(self.config["quorum_size"], total_nodes)
target_factor = min(self.config["target_replication_factor"], total_nodes)
max_factor = min(self.config["max_replication_factor"], total_nodes)

# Select nodes up to max_factor (limiting to available nodes)
target_nodes = eligible_nodes[:max_factor]
```

This approach ensures that:
1. We never attempt to replicate to more nodes than available
2. We prioritize master nodes over worker nodes
3. We limit replication to the maximum factor (5)
4. The quorum size is adjusted based on available nodes

### Success Level Determination

After replication, the success level is determined based on which replication goals were achieved:

```python
success_count = len(successful_nodes)

if success_count >= target_factor:
    # Achieved target replication factor (4) - complete success
    success_level = "TARGET_ACHIEVED"
elif success_count >= quorum_size:
    # Achieved quorum (3) but not target - partial success
    success_level = "QUORUM_ACHIEVED"
elif success_count > 0:
    # Some replication, but less than quorum - partial failure
    success_level = "BELOW_QUORUM"
else:
    # No successful replication - complete failure
    success_level = "NO_REPLICATION"
```

## Performance Considerations

When configuring the replication system, consider these performance factors:

- **Target Factor**: Higher values provide better fault tolerance but use more resources
- **Maximum Factor**: Limits resource usage but should be high enough for good fault tolerance
- **Sync Interval**: More frequent synchronization increases overhead but reduces potential data loss
- **Checkpoint Interval**: More frequent checkpoints improve recovery but increase overhead
- **Network Topology**: Consider physical location of nodes for optimal replication performance

## Advanced Topics

### Vector Clocks for Causality Tracking

The replication system uses vector clocks to track causality in distributed operations:

```python
# Initialize vector clock
self.vector_clock = VectorClock.create()

# Update vector clock when performing operations
self.vector_clock = VectorClock.increment(self.vector_clock, self.node_id)

# Include vector clock in replicated metadata
replication_data["vector_clock"] = self.vector_clock.copy()
```

This allows the system to correctly order operations and detect conflicts in a distributed environment.

### Recovery Process

When a node restarts after failure:

1. The replication manager loads the last saved state
2. It checks for available checkpoints
3. It recovers from the most recent valid checkpoint
4. It replays any operations that occurred after the checkpoint
5. It synchronizes with peer nodes to catch up on missed updates

### Tiered Storage Integration

The replication system integrates with the tiered storage system for progressive replication:

```python
# Get tier progression
tier_progression = self.config["default_tier_progression"]

# Start with memory tier
current_tier = tier_progression[0]

# Store in tiered backend
content = json.dumps(checkpoint_data).encode('utf-8')
tier_result = self.tiered_backend.store_content(
    content=content,
    target_tier=current_tier,
    metadata={
        "type": "checkpoint",
        "checkpoint_id": checkpoint_id,
        "timestamp": time.time()
    }
)

# Schedule progressive replication through tiers
self._schedule_progressive_tier_replication(
    tier_result["cid"],
    tier_progression,
    current_tier,
    metadata={"type": "checkpoint", "checkpoint_id": checkpoint_id}
)
```

## Related Documentation

- [Filesystem Journal](filesystem_journal.md): Documentation on the filesystem journal system
- [Cluster State](operations/cluster_state.md): Information on the distributed cluster state
- [Tiered Cache](reference/tiered_cache.md): Details on the tiered storage system
- [Write-Ahead Log](reference/write_ahead_log.md): Documentation on the Write-Ahead Log system
- [High-Level API](api/high_level_api.md): Documentation on the high-level API