# Arrow-based Cluster State Management

## Overview

The ipfs_kit_py project implements a distributed cluster state management system using Apache Arrow. This system enables sharing of cluster state (nodes, tasks, content) across processes by persisting the state to Parquet files. While originally designed with Plasma for zero-copy IPC, the current implementation primarily relies on file-based sharing for broader compatibility.

## Key Components

### Core Features

- **Arrow-based State**: Represents cluster state using efficient Arrow tables.
- **Parquet Persistence**: Stores the state durably in the Parquet file format.
- **Cross-language interoperability**: State files (Parquet) can be read by Python, C++, Rust, etc.
- **Atomic state updates**: Mechanisms within the cluster management ensure state consistency (though file access itself requires careful handling in concurrent scenarios).
- **Schema evolution**: Support for state schema versioning (managed by the core state module).
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

The `cluster_state_helpers.py` module provides a comprehensive set of functions for accessing and querying the cluster state stored in Parquet files:

#### State Access
- `get_state_path_from_metadata()`: Find the cluster state directory containing metadata and state files.
- `connect_to_state_store()`: Reads the state metadata file (e.g., `state_metadata.json`) to find the location of the state Parquet file. Returns `(None, metadata_dict)`.
- `get_cluster_state()`: Reads the cluster state Parquet file into an Arrow table.
- `get_cluster_state_as_dict()`: Reads the state and converts the (first row of the) Arrow table into a Python dictionary.
- `get_cluster_state_as_pandas()`: Reads the state and converts the Arrow table into pandas DataFrames (requires `pandas` extra).
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

The Arrow-based cluster state, stored in Parquet files, can be accessed from other languages that have Arrow and Parquet support:

#### C++ Example (Illustrative)
```cpp
#include <arrow/api.h>
#include <arrow/io/api.h>
#include <parquet/arrow/reader.h> // Include Parquet reader
#include <iostream>
#include <string>
#include <memory> // For std::shared_ptr

// Note: Error handling omitted for brevity. Use ARROW_ASSIGN_OR_RAISE.

int main() {
    // Path to the Parquet state file (obtained from state_metadata.json)
    std::string parquet_path = "/path/to/cluster_state/state_cluster.parquet";

    // Open the Parquet file
    std::shared_ptr<arrow::io::ReadableFile> infile;
    PARQUET_ASSIGN_OR_THROW(infile, arrow::io::ReadableFile::Open(parquet_path));

    // Create a Parquet Arrow reader instance
    std::unique_ptr<parquet::arrow::FileReader> reader;
    PARQUET_THROW_NOT_OK(
        parquet::arrow::OpenFile(infile, arrow::default_memory_pool(), &reader));

    // Read the entire table (cluster state typically has one row)
    std::shared_ptr<arrow::Table> table;
    PARQUET_THROW_NOT_OK(reader->ReadTable(&table));

    if (table->num_rows() > 0) {
        // Access data from the first row
        std::cout << "Cluster state information:" << std::endl;
        std::cout << "----------------------" << std::endl;

        // Access cluster ID (assuming column index 0)
        auto cluster_id_chunked_array = table->column(0);
        if (cluster_id_chunked_array && cluster_id_chunked_array->num_chunks() > 0) {
            auto cluster_id_array = std::static_pointer_cast<arrow::StringArray>(cluster_id_chunked_array->chunk(0));
            std::cout << "Cluster ID: " << cluster_id_array->GetString(0) << std::endl;
        }

        // Access master ID (assuming column index 1)
        auto master_id_chunked_array = table->column(1);
         if (master_id_chunked_array && master_id_chunked_array->num_chunks() > 0) {
            auto master_id_array = std::static_pointer_cast<arrow::StringArray>(master_id_chunked_array->chunk(0));
            std::cout << "Master ID: " << master_id_array->GetString(0) << std::endl;
        }

        // Access node information (assuming column index 3, more complex for nested lists)
        auto nodes_chunked_array = table->column(3);
         if (nodes_chunked_array && nodes_chunked_array->num_chunks() > 0) {
            auto nodes_array = std::static_pointer_cast<arrow::ListArray>(nodes_chunked_array->chunk(0));
            // Further processing needed to extract data from the list of structs
            std::cout << "Number of nodes (from list length): " << nodes_array->value_length(0) << std::endl;
         }
    } else {
         std::cout << "Cluster state table is empty." << std::endl;
    }

    return 0;
}
```
*(Note: This C++ example illustrates reading the Parquet file. Accessing nested data requires more complex Arrow C++ API usage.)*

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

## Testing

Testing the Arrow-based cluster state management system requires special handling for PyArrow's immutable objects and strict type checking.

### Key Testing Challenges

1. **Immutable PyArrow Types**: PyArrow Schema objects can't be directly modified or replaced after creation.
2. **Type Strictness**: PyArrow strictly enforces types, rejecting MagicMock objects during testing.
3. **Cleanup Issues**: Errors during cleanup of mocked PyArrow objects can pollute test output.

### Testing Approach

The project uses several techniques to handle these challenges:

#### 1. MonkeyPatching PyArrow Types

```python
# In conftest.py
@pytest.fixture(autouse=True)
def patch_arrow_schema(monkeypatch):
    """Patch PyArrow Schema to handle MagicMock objects."""
    try:
        import pyarrow as pa
        if hasattr(pa, '_patch_schema_equals'):
            pa._patch_schema_equals(monkeypatch)
    except (ImportError, AttributeError):
        pass
    yield
```

#### 2. Special Patching for ArrowClusterState

The `patch_cluster_state.py` module provides custom patches for ArrowClusterState methods to handle MagicMock objects:

```python
def patched_save_to_disk(self):
    """Patched _save_to_disk method to handle MagicMock schema objects."""
    if not self.enable_persistence:
        return
        
    try:
        # First try original method
        return original_save_to_disk(self)
    except Exception as e:
        # Handle schema type mismatches
        error_msg = str(e)
        if ("expected pyarrow.lib.Schema, got MagicMock" in error_msg or 
            "Argument 'schema' has incorrect type" in error_msg):
            # Create a real schema based on column names and write with that
            # ...implementation details...
            return True
        else:
            # Log at debug level to avoid test output noise
            logger.debug(f"Suppressed error in _save_to_disk: {e}")
            return False
```

#### 3. Creating Mock But Valid Arrow Tables

For testing, we create real Arrow Tables with mock data but proper schemas:

```python
# Create a real PyArrow schema for testing
schema = pa.schema([
    pa.field('cluster_id', pa.string()),
    pa.field('master_id', pa.string()),
    pa.field('updated_at', pa.timestamp('ms')),
    # ...other fields...
])

# Create valid PyArrow arrays
cluster_id_array = pa.array(["test-cluster"], type=pa.string())
master_id_array = pa.array(["QmTestMaster"], type=pa.string())
# ...other arrays...

# Create a real table with test data
test_table = pa.Table.from_arrays(
    [cluster_id_array, master_id_array, ...],
    schema=schema
)
```

### Testing Output Suppression

To prevent error messages during testing, we use context managers to temporarily suppress logging:

```python
@contextlib.contextmanager
def suppress_logging(logger_name=None, level=logging.ERROR):
    """Temporarily increase the logging level to suppress messages."""
    logger = logging.getLogger(logger_name or '')
    old_level = logger.level
    logger.setLevel(level)
    try:
        yield
    finally:
        logger.setLevel(old_level)
```

These approaches allow comprehensive testing of the Arrow-based cluster state system without error messages about PyArrow's type checking interfering with test output.
