# Advanced Cluster Management

IPFS Kit provides sophisticated cluster management capabilities beyond the basic IPFS Cluster integration (`ipfs-cluster-service`, `ipfs-cluster-ctl`, `ipfs-cluster-follow`). These features, primarily implemented in the `ipfs_kit_py/cluster/` directory and orchestrated by the `ClusterManager` class, enable more dynamic, resilient, and intelligent distributed systems.

## Enabling Advanced Cluster Management

To use these features, initialize `ipfs_kit` with `enable_cluster_management=True` in the metadata:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Enable for a master node
kit_master = ipfs_kit(
    metadata={
        "role": "master",
        "cluster_name": "advanced-cluster",
        "enable_cluster_management": True,
        # Add specific cluster config if needed
        "cluster_config": {
            "consensus_protocol": "raft", # Example
            "state_sync_interval": 60
        }
    }
)

# Enable for a worker node
kit_worker = ipfs_kit(
    metadata={
        "role": "worker",
        "cluster_name": "advanced-cluster",
        "enable_cluster_management": True,
        "master_addresses": ["/ip4/10.0.0.1/tcp/9096/p2p/QmMasterID"] # Example
    }
)

# Access the manager
if kit_master.cluster_manager:
    status = kit_master.get_cluster_status()
    print(f"Cluster Status: {status}")
```

## Core Components

-   **`ClusterManager` (`cluster_manager.py`):** The central coordinator for advanced features on each node. Manages other cluster components.
-   **`ClusterCoordinator` (`distributed_coordination.py`):** Handles peer discovery (via libp2p), membership management, leader election (if applicable), and task distribution logic.
-   **`ClusterStateSync` (`cluster_state_sync.py`):** Manages the synchronization of the cluster state (potentially using CRDTs or other consensus mechanisms) between nodes. Leverages the Arrow-based state representation.
-   **`ClusterMonitor` (`cluster_monitoring.py`):** Collects metrics from nodes, performs health checks, and can trigger alerts or automated actions (like role changes).
-   **`ClusterAuthentication` (`cluster_authentication.py`):** Handles secure communication and authentication between cluster nodes (e.g., using TLS, UCANs).
-   **`ClusterDynamicRoles` (`cluster_dynamic_roles.py`):** Enables nodes to automatically switch roles (e.g., worker to master) based on resource availability or cluster needs.
-   **`RoleManager` (`role_manager.py`):** Defines the specific capabilities and behaviors associated with each role within the advanced cluster context.

## Key Features

### 1. Distributed Coordination

-   **Peer Discovery & Membership:** Uses libp2p to find and maintain connections with other cluster members.
-   **Leader Election:** Can elect a leader (master) dynamically using consensus protocols (e.g., Raft, Paxos - specific implementation may vary).
-   **Task Distribution:** Intelligently assigns tasks submitted via `submit_cluster_task` to appropriate worker nodes based on role, capabilities, and resource availability.
-   **Configuration Consensus:** Allows proposing and agreeing upon cluster-wide configuration changes.

### 2. State Synchronization

-   **Distributed State:** Maintains a shared understanding of the cluster state (nodes, tasks, content locations) across all members.
-   **Efficient Sync:** Uses mechanisms like CRDTs or gossip protocols, potentially leveraging the Arrow cluster state format for efficient updates.
-   **Conflict Resolution:** Implements strategies (e.g., Last-Write-Wins, vector clocks) to handle concurrent state updates.
-   **Partial Updates:** Can synchronize only changed parts of the state to reduce network overhead.

### 3. Health Monitoring & Alerting

-   **Metrics Collection:** Gathers resource usage (CPU, memory, disk, GPU, network) and performance data from nodes.
-   **Health Checks:** Periodically verifies the status and responsiveness of cluster members.
-   **Alerting:** Triggers alerts based on predefined rules (e.g., high resource usage, offline nodes, task failures).
-   **Automated Recovery:** Can potentially trigger recovery actions or role adjustments based on health status.

### 4. Secure Communication

-   **TLS Encryption:** Secures communication channels between nodes.
-   **Node Authentication:** Verifies the identity of nodes joining the cluster.
-   **Authorization (UCANs):** Uses UCANs (User Controlled Authorization Networks) for fine-grained capability-based access control.

### 5. Dynamic Role Switching

-   **Resource Monitoring:** Continuously monitors local node resources.
-   **Capability Assessment:** Evaluates if the node meets requirements for different roles (Master, Worker).
-   **Automated Switching:** Can automatically upgrade (e.g., Leecher -> Worker, Worker -> Master) or downgrade roles based on resource availability and cluster needs (e.g., if the current master goes offline).
-   **Manual Control:** Allows administrators to manually trigger role changes.

## Usage Examples

```python
# Assuming 'kit' is an initialized ipfs_kit instance with enable_cluster_management=True

# --- Task Management ---
task_payload = {"input_cid": "QmInput", "parameters": {"alpha": 0.1}}
submit_result = kit.submit_cluster_task(task_type="data_processing", payload=task_payload)
if submit_result.get("success"):
    task_id = submit_result.get("task_id")
    print(f"Submitted task: {task_id}")

    # Check status later
    import time
    time.sleep(10)
    status_result = kit.get_task_status(task_id)
    print(f"Task {task_id} status: {status_result.get('status')}")

# --- Cluster Status & Monitoring ---
cluster_status = kit.get_cluster_status()
print(f"Nodes: {len(cluster_status.get('nodes', []))}")
print(f"Tasks: {len(cluster_status.get('tasks', []))}")

# --- Dynamic Roles (Example - requires ClusterDynamicRoles setup) ---
# Note: Direct interaction might be via RoleManager or specific methods if exposed

# Check potential roles based on current resources
# potential_roles = kit.evaluate_potential_roles()

# Manually trigger a role change (if implemented and permitted)
# change_result = kit.change_role(target_role="worker", force=False)

# --- Security (Conceptual - actual methods depend on implementation) ---
# Generate an auth token (if applicable)
# token = kit.generate_auth_token(peer_id="QmWorkerPeer", capabilities=["read", "write"])

# Verify a peer's identity
# verification = kit.verify_peer_identity(peer_id="QmWorkerPeer", presented_token=token)
```

Refer to the specific modules within `ipfs_kit_py/cluster/` and their docstrings for detailed API usage and implementation specifics.
