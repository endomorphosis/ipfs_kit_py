# Cluster State Management

The Cluster State system in IPFS Kit provides a robust framework for maintaining and synchronizing distributed state across IPFS cluster nodes. It uses Apache Arrow for efficient state representation and synchronization.

## Overview

The cluster state system serves as the foundation for distributed coordination in IPFS Kit clusters. It enables:

- Efficient state representation using Apache Arrow's columnar format
- Role-based state distribution (master, worker, leecher)
- Real-time state synchronization between nodes
- Resource-aware task allocation
- Failure detection and recovery mechanisms

## Architecture

The cluster state system consists of several components:

- **ArrowClusterState**: Core state management class that leverages Apache Arrow
- **ClusterStateSync**: Handles state synchronization between nodes
- **ClusterStateHelpers**: Utility functions for common state operations

## Implementation Details

### Arrow-based State Representation

The state is represented using Apache Arrow Tables with a predefined schema that includes:

- Cluster metadata (ID, master node)
- Node information (IDs, roles, status)
- Task data (IDs, status, assignments)
- Content metadata (CIDs, size, replication)

### Python 3.12 Compatibility

As of Python 3.12, PyArrow's Schema objects are immutable, which affects testing with mock objects. The system includes compatibility measures:

- Uses standalone comparison functions for schema equality checks
- Provides alternative patching mechanisms for testing with mocks
- Maintains backward compatibility with previous Python versions

In test environments, the `mock_schema_equals` function handles comparisons between schema objects, including MagicMock instances, without modifying the immutable Schema class.

### Role-Based State Management

State management behavior differs based on node roles:

- **Master Nodes**: Maintain the authoritative state and distribute to workers
- **Worker Nodes**: Receive state updates from masters and provide their local state
- **Leecher Nodes**: Receive minimal state information needed for operation

## Usage Examples

### Basic Initialization

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.cluster_state import ArrowClusterState

# Through IPFS Kit (recommended)
kit = ipfs_kit(
    metadata={
        "role": "master",
        "cluster_name": "test-cluster"
    }
)
# State is automatically initialized and managed

# Direct initialization (advanced usage)
state = ArrowClusterState(
    cluster_id="test-cluster",
    role="master",
    state_path="/path/to/state",
    ipfs_client=kit.ipfs
)
state.init_state()
```

### State Operations

```python
# Register a new node
result = state.register_node(
    node_id="worker-1",
    role="worker",
    resources={"cpu": 4, "memory": "8GB"},
    metadata={"location": "us-east"}
)

# Update node status
state.update_node_status(node_id="worker-1", status="online")

# Add and assign a task
task_result = state.add_task(
    task_id="task-123",
    task_type="process",
    payload={"cid": "QmTest", "options": {"format": "json"}}
)

assign_result = state.assign_task(
    task_id="task-123",
    node_id="worker-1"
)

# Update task status
state.update_task(
    task_id="task-123",
    status="completed",
    result={"success": True, "output_cid": "QmOutput"}
)

# Get the current state
current_state = state.get_state()
```

### Working with the State Table

```python
# Get the current state as an Arrow Table
state_table = state.get_state()

# Convert to pandas DataFrame for analysis
import pandas as pd
df = state_table.to_pandas()

# View node information
nodes_df = pd.DataFrame.from_records([n.as_py() for n in state_table["nodes"][0]])
print(nodes_df)

# View task information
tasks_df = pd.DataFrame.from_records([t.as_py() for t in state_table["tasks"][0]])
print(tasks_df)
```

## State Synchronization

The system automatically synchronizes state between nodes based on their roles:

```python
# Master node publishes state updates
if kit.role == "master":
    sync_result = kit.publish_cluster_state()
    print(f"Published state update: {sync_result['success']}")

# Worker node requests state update
if kit.role == "worker":
    sync_result = kit.sync_cluster_state()
    print(f"Synced state from master: {sync_result['success']}")
```

## Access from External Processes

The state can be accessed from external processes using the Arrow C Data Interface:

```python
# Get state interface information
info = kit.get_state_interface_info()

# In another process
from ipfs_kit_py.cluster_state_helpers import connect_to_state_store
state = connect_to_state_store(info["shared_memory_name"])
```

## Helper Functions

The `cluster_state_helpers` module provides utility functions for common operations:

```python
from ipfs_kit_py.cluster_state_helpers import (
    find_nodes_by_role,
    find_tasks_by_status,
    find_available_node_for_task,
    get_cluster_status_summary
)

# Find all worker nodes
workers = find_nodes_by_role(state_table, "worker")

# Find all pending tasks
pending_tasks = find_tasks_by_status(state_table, "pending")

# Find an available node for a task
best_node = find_available_node_for_task(
    state_table,
    task_requirements={"cpu": 2, "memory": "4GB"}
)

# Get a summary of the cluster status
summary = get_cluster_status_summary(state_table)
print(summary)
```

## Testing

The system includes comprehensive test fixtures for working with the cluster state in test environments:

```python
# Example test using the provided fixtures
def test_with_cluster_state(mock_cluster_state):
    # The mock_cluster_state fixture provides a pre-configured state instance
    result = mock_cluster_state.register_node("test-node", "worker")
    assert result["success"] is True
    assert result["node_id"] == "test-node"
    
    # The fixture handles Python 3.12 compatibility with PyArrow schemas
```

## Performance Considerations

- **Memory Efficiency**: Uses Arrow's memory-efficient columnar format
- **Serialization Speed**: Fast serialization/deserialization for network transfers
- **Update Size**: Supports partial state updates to minimize network traffic
- **Concurrent Access**: Thread-safe state access
- **Scaling**: Designed to handle thousands of nodes and tasks