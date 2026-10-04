# Cluster Dynamic Roles

`ipfs-kit-py` supports dynamic role assignment within a cluster, allowing nodes to automatically transition between roles (Leecher, Worker, Master) based on detected resources, network stability, and potentially cluster needs. This promotes flexibility and resilience, enabling nodes to contribute optimally based on their current capabilities. The core logic is implemented in the `ClusterDynamicRoles` class (`cluster_dynamic_roles.py`).

## Overview

Instead of statically assigning roles, nodes can evaluate their own resources and the requirements for different roles, then initiate a role change if appropriate.

**Key Concepts:**

*   **Roles**:
    *   **Leecher**: A basic node, primarily consuming cluster resources (e.g., retrieving content) but not actively participating in tasks like pinning or coordination. Lowest resource requirements.
    *   **Worker**: Actively participates in cluster tasks assigned by the Master (e.g., pinning content, executing computations). Requires sufficient resources (CPU, memory, storage, bandwidth) to handle tasks.
    *   **Master**: Coordinates the cluster, manages state (potentially), schedules tasks for Workers, and monitors cluster health. Highest resource and stability requirements.
*   **Resource Detection**: Nodes periodically assess their available resources (CPU, memory, disk space, network bandwidth, GPU presence, network stability).
*   **Role Requirements**: Predefined (or configurable) minimum resource levels and capabilities required for each role (Worker, Master).
*   **Evaluation Logic**: The node compares its detected resources against the requirements for higher roles (e.g., a Leecher checks if it meets Worker requirements; a Worker checks for Master requirements). It might also consider cluster state (e.g., is there already a Master?).
*   **Role Transition**: If a node determines it can (and potentially should) change roles, it initiates a transition process. This involves updating its configuration, potentially re-registering with the cluster (or announcing its new role via gossip), and starting/stopping relevant services (e.g., task execution loops for a Worker).

## Implementation (`ClusterDynamicRoles`)

The `ClusterDynamicRoles` class, typically associated with the main `ipfs-kit-py` instance or `ClusterManager`, handles this process:

*   **Initialization**: Loads role requirements configuration.
*   **Resource Detection**: Implements methods to check CPU, memory, disk, network, GPU, etc. (`detect_available_resources`, `_estimate_bandwidth`, `_detect_gpu`).
*   **Evaluation**: Compares detected resources with role requirements (`evaluate_potential_roles`, `determine_optimal_role`).
*   **Transition Methods**: Provides functions to explicitly trigger role changes (`upgrade_to_worker`, `upgrade_to_master`, `downgrade_to_worker`, `downgrade_to_leecher`, `change_role`).
*   **Automatic Check**: Can periodically run `check_and_update_role` to automatically evaluate and transition if conditions are met.

## Configuration

Dynamic role behavior is configured under the `cluster.dynamic_roles` key:

```python
# Example configuration snippet
config = {
    'cluster': {
        'dynamic_roles': {
            'enabled': True,
            'check_interval_seconds': 300, # Check every 5 minutes
            'requirements': {
                'worker': {
                    'min_cpu_cores': 2,
                    'min_memory_gb': 4,
                    'min_disk_gb': 50,
                    'min_bandwidth_mbps': 10,
                    'required_capabilities': ['storage']
                },
                'master': {
                    'min_cpu_cores': 4,
                    'min_memory_gb': 8,
                    'min_disk_gb': 20, # Master might need less storage than worker
                    'min_bandwidth_mbps': 20,
                    'required_capabilities': ['coordination'],
                    'min_network_stability': 0.9 # Example: 90% uptime/reachability
                }
            },
            'prefer_upgrade': True # Should nodes actively try to upgrade if possible?
        }
        # ... other cluster config
    }
    # ... other ipfs-kit-py config
}
```

## Workflow Example (Leecher to Worker)

1.  A node starts as a Leecher.
2.  Dynamic roles are enabled, and the `check_interval_seconds` timer triggers `check_and_update_role`.
3.  The node calls `detect_available_resources` and finds it has 4 CPU cores, 8GB RAM, 100GB disk, 50 Mbps bandwidth.
4.  It calls `evaluate_potential_roles`, comparing its resources to `requirements.worker`.
5.  The evaluation determines the node meets or exceeds all Worker requirements.
6.  Assuming `prefer_upgrade` is true and other conditions allow (e.g., cluster needs workers), `determine_optimal_role` suggests upgrading to Worker.
7.  The `change_role` (or `upgrade_to_worker`) method is called.
8.  The node updates its internal configuration, potentially restarts relevant components (like task listeners), and announces its new role to the cluster (e.g., via state update or gossip).

## Benefits

*   **Flexibility**: Nodes adapt to changing resource availability (e.g., a powerful node temporarily under heavy load might downgrade).
*   **Resilience**: If a Master node fails, a sufficiently capable Worker might automatically promote itself (depending on configuration and cluster state).
*   **Optimized Resource Use**: Nodes contribute according to their capacity.

## Considerations

*   **Stability**: Frequent role changes ("flapping") can be disruptive. Intervals and thresholds need careful tuning.
*   **Master Election**: If multiple nodes become eligible for Master simultaneously, a separate leader election mechanism might be needed to ensure only one Master is active. Dynamic roles might need to integrate with or respect such a mechanism.
*   **Configuration Complexity**: Defining appropriate resource requirements for each role requires understanding the workload.
*   **State Consistency**: Role changes need to be reliably propagated and reflected in the cluster state view of all nodes.
