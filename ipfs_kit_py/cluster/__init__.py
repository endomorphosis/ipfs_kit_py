"""Cluster management package.

Keep this module intentionally lightweight.

Historically, this package imported many submodules at import-time. That caused
hard-to-debug circular imports (notably when other parts of the project import
`ipfs_kit_py.ipfs_kit` during startup).

To keep imports safe and predictable, public symbols are exposed via lazy loading.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple


_LAZY: Dict[str, Tuple[str, str]] = {
    # Cluster management
    "ClusterManager": ("ipfs_kit_py.cluster.cluster_manager", "ClusterManager"),
    "ClusterCoordinator": ("ipfs_kit_py.cluster.distributed_coordination", "ClusterCoordinator"),
    "MembershipManager": ("ipfs_kit_py.cluster.distributed_coordination", "MembershipManager"),
    "ClusterMonitor": ("ipfs_kit_py.cluster.monitoring", "ClusterMonitor"),
    "MetricsCollector": ("ipfs_kit_py.cluster.monitoring", "MetricsCollector"),
    "NodeRole": ("ipfs_kit_py.cluster.role_manager", "NodeRole"),
    "RoleManager": ("ipfs_kit_py.cluster.role_manager", "RoleManager"),
    "role_capabilities": ("ipfs_kit_py.cluster.role_manager", "role_capabilities"),
    "get_gpu_info": ("ipfs_kit_py.cluster.utils", "get_gpu_info"),
    # Daemon management with cluster capabilities
    "EnhancedDaemonManager": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "EnhancedDaemonManager"),
    "DaemonNodeRole": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "NodeRole"),
    "DaemonPeerInfo": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "PeerInfo"),
    "LeaderElection": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "LeaderElection"),
    "ReplicationManager": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "ReplicationManager"),
    "IndexingService": ("ipfs_kit_py.cluster.enhanced_daemon_manager_with_cluster", "IndexingService"),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    entry = _LAZY.get(name)
    if not entry:
        raise AttributeError(name)
    module_name, attr_name = entry
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY.keys())
