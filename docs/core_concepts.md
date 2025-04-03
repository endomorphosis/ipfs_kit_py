# IPFS Kit Core Concepts

This document explains the fundamental concepts behind the `ipfs_kit_py` library.

## Main `ipfs_kit` Class

The central point of interaction is the `ipfs_kit` class found in `ipfs_kit_py/ipfs_kit.py`. It acts as an orchestrator, initializing and providing access to various IPFS-related functionalities based on configuration and node role.

**Initialization:**

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
    # ... other config options
}
kit_worker = ipfs_kit(metadata=config_data)

# Initialize master with cluster management enabled
kit_master = ipfs_kit(
    metadata={"role": "master", "enable_cluster_management": True}
)
```

The `metadata` dictionary passed during initialization is crucial for configuring the kit's behavior and enabling specific features.

## Node Roles

IPFS Kit operates with different node roles, each optimized for specific tasks within a distributed system:

1.  **Master:**
    *   **Purpose:** Coordinates the cluster, manages pinning across nodes, distributes tasks, maintains the global state/metadata index.
    *   **Components:** Runs `ipfs daemon`, `ipfs-cluster-service`, and uses `ipfs-cluster-ctl`. May also run advanced `ClusterManager`.
    *   **Resources:** Typically requires more resources (CPU, memory, disk) than other roles.

2.  **Worker:**
    *   **Purpose:** Executes tasks assigned by the master, stores and serves content as directed by the cluster, participates in distributed computations.
    *   **Components:** Runs `ipfs daemon` and `ipfs-cluster-follow` (or connects to `ClusterManager`).
    *   **Resources:** Balanced resources, often optimized for computation (CPU/GPU).

3.  **Leecher:**
    *   **Purpose:** Primarily consumes content from the network with minimal resource contribution. Acts as a standard IPFS peer.
    *   **Components:** Runs `ipfs daemon`.
    *   **Resources:** Optimized for low resource usage.

The role determines which underlying components (`ipfs_py`, `ipfs_cluster_service`, `ipfs_cluster_follow`, `ClusterManager`, etc.) are initialized and how the `ipfs_kit` instance behaves.

## Interaction Patterns

You can interact with the `ipfs_kit` instance in several ways:

1.  **Direct Method Calls:** Access methods directly on the `kit` object or its sub-components.

    ```python
    # Add a file using the ipfs component
    add_result = kit.ipfs.add("my_file.txt")

    # If master, add pin to cluster
    if kit.role == "master" and hasattr(kit, 'ipfs_cluster_ctl'):
       pin_result = kit.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin(add_result['Hash'])

    # Get node ID
    id_result = kit.ipfs_id()
    ```

2.  **Callable Interface:** Use the `kit` object itself as a function, passing the method name as the first argument. This provides a unified way to call methods across different underlying components based on the node's role.

    ```python
    # Add a file (delegates appropriately based on role)
    add_result = kit("ipfs_add_path", path="my_file.txt")

    # Pin content (delegates appropriately based on role)
    pin_result = kit("ipfs_add_pin", pin=add_result['cid'])

    # Get cluster status (only works if master/worker with cluster components)
    try:
        status = kit("ipfs_cluster_status")
    except (AttributeError, PermissionError) as e:
        print(f"Operation not available for role {kit.role}: {e}")
    ```

## Configuration

Configuration can be provided via:

-   The `metadata` dictionary during `ipfs_kit` initialization.
-   Environment variables (e.g., `IPFS_KIT_ROLE`).
-   YAML/JSON configuration files (primarily used by the `IPFSSimpleAPI` and `CLI`).

The `ipfs_kit` class prioritizes explicit parameters, then environment variables, then configuration file settings.

## Key Sub-Modules

-   `ipfs.py`: Handles core IPFS daemon interactions.
-   `ipfs_cluster_service.py`: Manages the IPFS Cluster daemon (Master role).
-   `ipfs_cluster_ctl.py`: Interface for controlling the IPFS Cluster (Master role).
-   `ipfs_cluster_follow.py`: Manages following the cluster pinset (Worker role).
-   `cluster/`: Contains modules for advanced cluster management (coordination, state sync, monitoring, dynamic roles, etc.).
-   `ipfs_fsspec.py`: Implements the FSSpec interface.
-   `tiered_cache.py`: Provides the tiered caching system.
-   `arrow_metadata_index.py`: Manages the metadata index.
-   `libp2p_peer.py`: Handles direct P2P communication.
-   `ai_ml_integration.py`: Contains AI/ML specific tools like the DataLoader.
-   `high_level_api.py`: Provides the simplified `IPFSSimpleAPI`.
-   `cli.py`: Implements the command-line interface.
-   `storacha_kit.py` / `s3_kit.py`: Interfaces for external storage backends.

Understanding these core concepts is essential for effectively using and extending the `ipfs_kit_py` library. Refer to the specific documentation files for each component for more details.
