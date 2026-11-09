# IPFS Kit Cluster Management

This module provides advanced cluster management capabilities for IPFS Kit, enabling efficient coordination and task distribution across nodes with different roles. It implements Phase 3B of the development roadmap with a focus on role-based architecture, distributed coordination, and monitoring.

## Features

### Role-Based Architecture

- **Smart role detection** based on available resources
- **Automatic role optimization** for different node types
- **Dynamic role switching** in response to changing conditions
- **Role-specific configurations** to optimize performance

### Distributed Coordination

- **Cluster membership management** with health checking
- **Leader election** for master node selection
- **Task distribution** across worker nodes
- **Consensus protocols** for configuration changes
- **Specialized task handlers** for different task types
- **Configuration consensus** with proposal and voting
- **Comprehensive metrics collection** and analysis

### Monitoring and Metrics

- **Health monitoring** of cluster and individual nodes
- **Performance metrics collection** with historical data
- **Alert generation** for issues and anomalies
- **Resource utilization tracking** for optimization

## Components

### Role Manager (`role_manager.py`)

The role manager is responsible for:

- Detecting the optimal role for a node based on its resources
- Configuring the node according to its role
- Dynamically switching roles when conditions change
- Applying role-specific optimizations
- Authenticating peers for secure operations

```python
from ipfs_kit_py.cluster.role_manager import NodeRole, RoleManager

# Initialize role manager
role_manager = RoleManager(
    initial_role="worker",
    resources={"memory_available_mb": 2048, "disk_available_gb": 20},
    auto_detect=True,
    role_switching_enabled=True
)

# Check if role can handle a capability
can_route = role_manager.can_handle_capability("content_routing")

# Get configuration for current role
role_config = role_manager.get_role_config()
```

### Distributed Coordination (`distributed_coordination.py`)

This component handles:

- Cluster membership tracking
- Leader election and consensus
- Task distribution and status tracking
- Peer-to-peer coordination
- Task handler registration and management
- Configuration change proposals and voting
- Detailed metrics aggregation and analysis

```python
from ipfs_kit_py.cluster.distributed_coordination import ClusterCoordinator, MembershipManager

# Create membership manager
membership_manager = MembershipManager(
    cluster_id="my-cluster",
    node_id="node-123",
    heartbeat_interval=30
)

# Create cluster coordinator
coordinator = ClusterCoordinator(
    cluster_id="my-cluster",
    node_id="node-123",
    is_master=True,
    membership_manager=membership_manager
)

# Create a new cluster
coordinator.create_cluster()

# Submit a task for execution
task_id = coordinator.submit_task({
    "type": "process_content",
    "cid": "QmExample123",
    "parameters": {"transform": "resize"}
})
```

### Monitoring (`monitoring.py`)

Provides monitoring and metrics collection:

- System resource utilization tracking
- Cluster health monitoring
- Performance metrics collection
- Alert generation for issues

```python
from ipfs_kit_py.cluster.monitoring import ClusterMonitor, MetricsCollector

# Create metrics collector
metrics_collector = MetricsCollector(
    node_id="node-123",
    metrics_dir="~/.ipfs/metrics"
)

# Register custom metrics source
metrics_collector.register_metric_source(
    "resources", 
    lambda: {"cpu_percent": 25, "memory_percent": 40}
)

# Create cluster monitor
monitor = ClusterMonitor(
    node_id="node-123",
    metrics_collector=metrics_collector,
    alert_callback=lambda source, alert: print(f"ALERT: {alert['message']}")
)

# Get cluster health
health = monitor.get_cluster_health()
```

## Node Roles

The module supports these node roles:

### Master Node

- Orchestrates the entire content ecosystem
- Coordinates task distribution
- Manages metadata indexes
- Handles cluster membership
- Requires significant resources

### Worker Node

- Processes individual content items
- Executes computational tasks
- Optimized for processing rather than storage
- Participates in content routing
- Moderate resource requirements

### Leecher Node

- Consumes network resources with minimal contribution
- Optimized for content consumption
- Minimal resource requirements
- Can operate offline with limited subset of content

### Gateway Node

- Provides HTTP gateway access to IPFS content
- Optimized for serving content to external clients
- High bandwidth requirements
- Does not participate in cluster management

### Observer Node

- Monitors cluster health and metrics
- Does not store or process content
- Minimal resource requirements
- Useful for external monitoring

## Dynamic Adaptation

The module includes intelligent adaptation to changing conditions:

- **Resource trend tracking**: Monitors resource usage trends over time
- **Fine-grained adaptation**: Adjusts parameters without changing roles
- **Configurable thresholds**: Customizable thresholds for adaptations
- **Performance optimization**: Automatically optimizes based on workload

## Examples

See `examples/cluster_management_example.py` for a complete example of:

1. Creating a cluster with a master node
2. Adding worker and leecher nodes
3. Monitoring cluster health
4. Using role-based optimizations

```bash
# Run a master node
python examples/cluster_management_example.py --role master

# Run a worker node
python examples/cluster_management_example.py --role worker --cluster example-cluster --master 192.168.1.100:9096

# Run a leecher node
python examples/cluster_management_example.py --role leecher --cluster example-cluster --master 192.168.1.100:9096
```