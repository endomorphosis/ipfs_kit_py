# Arrow-based Cluster State Management

## Overview

The ipfs_kit_py project implements a high-performance, distributed cluster state management system using Apache Arrow's zero-copy data sharing capabilities. This system enables efficient sharing of cluster state (nodes, tasks, content) across processes with minimal overhead.

## Key Components

### Core Features

- **Zero-copy data sharing**: Using Arrow's Plasma store for memory-efficient IPC
- **Cross-language interoperability**: Shared state accessible from Python, C++, Rust, etc.
- **Atomic state updates**: Thread-safe state manipulation
- **Schema evolution**: Support for state schema versioning
- **Rich query capabilities**: Efficient filtering and aggregation of state data
- **Persistence**: Durable state storage with Parquet format
- **Observability**: Metrics and visualization for cluster state

### Arrow Schema Design

The cluster state is represented using a columnar schema with the following structure:

```python
schema = pa.schema([
    # Cluster metadata
    pa.field('cluster_id', pa.string()),
    pa.field('master_id', pa.string()),
    pa.field('updated_at', pa.timestamp('ms')),
    
    # Nodes in the cluster (array of structs)
    pa.field('nodes', pa.list_(
        pa.struct([
            pa.field('id', pa.string()),
            pa.field('role', pa.string()),
            pa.field('status', pa.string()),
            pa.field('peers', pa.list_(pa.string())),
            pa.field('capabilities', pa.list_(pa.string())),
            pa.field('resources', pa.struct([
                pa.field('cpu_count', pa.int32()),
                pa.field('cpu_load', pa.float32()),
                pa.field('gpu_count', pa.int32()),
                pa.field('gpu_available', pa.bool_()),
                pa.field('memory_total', pa.int64()),
                pa.field('memory_available', pa.int64()),
                pa.field('disk_total', pa.int64()),
                pa.field('disk_available', pa.int64())
            ]))
        ])
    )),
    
    # Tasks in the cluster (array of structs)
    pa.field('tasks', pa.list_(
        pa.struct([
            pa.field('id', pa.string()),
            pa.field('type', pa.string()),
            pa.field('status', pa.string()),
            pa.field('created_at', pa.timestamp('ms')),
            pa.field('updated_at', pa.timestamp('ms')),
            pa.field('assigned_to', pa.string()),
            pa.field('resources', pa.struct([
                pa.field('cpu_cores', pa.int32()),
                pa.field('gpu_cores', pa.int32()),
                pa.field('memory_mb', pa.int32())
            ])),
            pa.field('input_cid', pa.string()),
            pa.field('output_cid', pa.string()),
            pa.field('input_cids', pa.list_(pa.string())),
            pa.field('output_cids', pa.list_(pa.string()))
        ])
    )),
    
    # Content in the cluster (array of structs)
    pa.field('content', pa.list_(
        pa.struct([
            pa.field('cid', pa.string()),
            pa.field('size', pa.int64()),
            pa.field('created_at', pa.timestamp('ms')),
            pa.field('providers', pa.list_(pa.string())),
            pa.field('pinned', pa.bool_()),
            pa.field('replication', pa.int32())
        ])
    ))
])
```

### Helper Functions

The `cluster_state_helpers.py` module provides a comprehensive set of functions for accessing and querying the cluster state:

#### State Access
- `get_state_path_from_metadata()`: Find the cluster state directory
- `connect_to_state_store()`: Connect to the Plasma store
- `get_cluster_state()`: Get the complete cluster state as an Arrow table
- `get_cluster_state_as_dict()`: Get the state as a Python dictionary
- `get_cluster_state_as_pandas()`: Get the state as pandas DataFrames
- `get_cluster_metadata()`: Get basic cluster metadata

#### Node Management
- `get_all_nodes()`: Get all nodes in the cluster
- `get_node_by_id()`: Get a specific node by ID
- `find_nodes_by_role()`: Find nodes with a specific role
- `find_nodes_by_capability()`: Find nodes with a specific capability
- `find_nodes_with_gpu()`: Find nodes with available GPUs
- `get_node_resource_utilization()`: Calculate resource utilization for a node

#### Task Management
- `get_all_tasks()`: Get all tasks in the cluster
- `get_task_by_id()`: Get a specific task by ID
- `find_tasks_by_status()`: Find tasks with a specific status
- `find_tasks_by_type()`: Find tasks of a specific type
- `find_tasks_by_node()`: Find tasks assigned to a specific node
- `find_tasks_by_resource_requirements()`: Find tasks that require specific resources
- `find_available_node_for_task()`: Find a suitable node for a task
- `get_task_execution_metrics()`: Generate metrics about task execution
- `estimate_time_to_completion()`: Estimate the time to completion for a task

#### Content Management
- `get_all_content()`: Get all content items in the cluster
- `find_content_by_cid()`: Find a content item by CID
- `find_content_by_provider()`: Find content available from a specific provider
- `find_orphaned_content()`: Find content items that have no active references
- `get_content_availability_map()`: Map content CIDs to provider nodes

#### Cluster Analysis
- `get_cluster_status_summary()`: Get a summary of cluster status
- `get_network_topology()`: Get the network topology of the cluster
- `export_state_to_json()`: Export the cluster state to a JSON file

## Usage Examples

### Basic State Access

```python
from ipfs_kit_py.cluster_state_helpers import get_cluster_state_as_dict

# Get state path (or provide explicitly)
state_path = get_state_path_from_metadata()

# Get complete state as dictionary
state = get_cluster_state_as_dict(state_path)
if state:
    print(f"Cluster ID: {state['cluster_id']}")
    print(f"Master node: {state['master_id']}")
    print(f"Last updated: {state['updated_at']}")
    print(f"Number of nodes: {len(state['nodes'])}")
    print(f"Number of tasks: {len(state['tasks'])}")
    print(f"Number of content items: {len(state['content'])}")
```

### Finding Suitable Nodes for Tasks

```python
from ipfs_kit_py.cluster_state_helpers import (
    find_tasks_by_status,
    find_available_node_for_task
)

# Get state path
state_path = get_state_path_from_metadata()

# Find pending tasks
pending_tasks = find_tasks_by_status(state_path, "pending")

# Find suitable nodes for each task
for task in pending_tasks:
    task_id = task["id"]
    print(f"Finding node for task {task_id}")
    
    node = find_available_node_for_task(state_path, task_id)
    if node:
        print(f"  → Best node: {node['id']}")
        print(f"    CPU: {node['resources']['cpu_count']} cores")
        print(f"    Memory: {node['resources']['memory_available'] / (1024*1024*1024):.1f} GB")
        if node['resources'].get('gpu_count', 0) > 0:
            print(f"    GPU: {node['resources']['gpu_count']} GPUs")
    else:
        print("  → No suitable node found")
```

### Resource Utilization Monitoring

```python
from ipfs_kit_py.cluster_state_helpers import (
    get_all_nodes,
    get_node_resource_utilization
)

# Get state path
state_path = get_state_path_from_metadata()

# Get all nodes
nodes = get_all_nodes(state_path)
if not nodes:
    print("No nodes found")
    exit()

# Calculate and display utilization for each node
print("Node Utilization:")
print("----------------")
for node in nodes:
    node_id = node["id"]
    util = get_node_resource_utilization(state_path, node_id)
    if util:
        print(f"Node {node_id} ({node['role']}):")
        print(f"  CPU: {util['cpu_utilization']:.1%}")
        print(f"  Memory: {util['memory_utilization']:.1%}")
        print(f"  Disk: {util['disk_utilization']:.1%}")
        if util['gpu_utilization'] is not None:
            print(f"  GPU: {util['gpu_utilization']:.1%}")
        print(f"  Active tasks: {util['active_tasks']}")
        print(f"  Success rate: {util['success_rate']:.1%}")
        print()
```

### Cross-Language Access

The Arrow-based cluster state can be accessed from other languages using the Arrow C Data Interface:

#### C++ Example
```cpp
#include <arrow/api.h>
#include <arrow/io/api.h>
#include <arrow/ipc/api.h>
#include <plasma/client.h>
#include <iostream>
#include <fstream>
#include <string>

using namespace arrow;

int main() {
    // Load state metadata from JSON file
    std::string metadata_path = "/path/to/cluster_state/state_metadata.json";
    std::ifstream metadata_file(metadata_path);
    if (!metadata_file) {
        std::cerr << "Could not open metadata file" << std::endl;
        return 1;
    }
    
    // Parse JSON (using a simple approach for example)
    std::string json_content((std::istreambuf_iterator<char>(metadata_file)),
                           std::istreambuf_iterator<char>());
    
    // Extract socket path and object ID from JSON
    // In a real implementation, use a proper JSON parser
    size_t socket_pos = json_content.find("plasma_socket");
    size_t object_pos = json_content.find("object_id");
    
    std::string socket_path = "/path/to/socket"; // Extract from JSON
    std::string object_id_hex = "0123456789abcdef"; // Extract from JSON
    
    // Connect to Plasma store
    std::shared_ptr<plasma::PlasmaClient> client = std::make_shared<plasma::PlasmaClient>();
    plasma::Status connect_status = client->Connect(socket_path);
    if (!connect_status.ok()) {
        std::cerr << "Failed to connect to Plasma store: " << connect_status.message() << std::endl;
        return 1;
    }
    
    // Create object ID from hex string
    plasma::ObjectID object_id = plasma::ObjectID::from_binary(object_id_hex);
    
    // Get the object buffer
    std::shared_ptr<Buffer> buffer;
    plasma::Status get_status = client->Get(&object_id, 1, -1, &buffer);
    if (!get_status.ok()) {
        std::cerr << "Failed to get object: " << get_status.message() << std::endl;
        return 1;
    }
    
    // Create Arrow reader
    auto buffer_reader = std::make_shared<io::BufferReader>(buffer);
    std::shared_ptr<ipc::RecordBatchReader> reader;
    Status status = ipc::RecordBatchReader::Open(buffer_reader, &reader);
    if (!status.ok()) {
        std::cerr << "Failed to open record batch reader: " << status.ToString() << std::endl;
        return 1;
    }
    
    // Read record batch
    std::shared_ptr<RecordBatch> batch;
    status = reader->ReadNext(&batch);
    if (!status.ok()) {
        std::cerr << "Failed to read record batch: " << status.ToString() << std::endl;
        return 1;
    }
    
    // Now access data in the record batch
    std::cout << "Cluster state information:" << std::endl;
    std::cout << "----------------------" << std::endl;
    
    // Access cluster ID
    auto cluster_id_array = std::static_pointer_cast<StringArray>(batch->column(0));
    std::cout << "Cluster ID: " << cluster_id_array->GetString(0) << std::endl;
    
    // Access master ID
    auto master_id_array = std::static_pointer_cast<StringArray>(batch->column(1));
    std::cout << "Master ID: " << master_id_array->GetString(0) << std::endl;
    
    // Access node information (more complex with nested structures)
    auto nodes_array = std::static_pointer_cast<ListArray>(batch->column(3));
    int64_t num_nodes = nodes_array->length();
    std::cout << "Number of nodes: " << num_nodes << std::endl;
    
    // Clean up
    client->Disconnect();
    
    return 0;
}
```

### Extending with Custom Helper Functions

You can easily extend the helper functions for your specific needs:

```python
from ipfs_kit_py.cluster_state_helpers import get_all_nodes, get_all_tasks

def find_optimal_task_distribution(state_path):
    """
    Find the optimal distribution of tasks across worker nodes.
    
    Args:
        state_path: Path to the cluster state directory
        
    Returns:
        Dictionary mapping task IDs to node IDs
    """
    nodes = get_all_nodes(state_path)
    tasks = get_all_tasks(state_path)
    
    worker_nodes = [n for n in nodes if n.get("role") == "worker" and n.get("status") == "online"]
    pending_tasks = [t for t in tasks if t.get("status") == "pending"]
    
    # Simple round-robin assignment for this example
    assignments = {}
    for i, task in enumerate(pending_tasks):
        node_idx = i % len(worker_nodes)
        assignments[task["id"]] = worker_nodes[node_idx]["id"]
    
    return assignments
```