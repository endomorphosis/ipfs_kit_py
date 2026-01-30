"""
Cluster Management Package for IPFS Kit.

This package provides advanced cluster management capabilities for IPFS Kit,
enabling efficient coordination and task distribution across nodes with different
roles (master, worker, leecher). It implements Phase 3B of the development roadmap.

Components:
- role_manager: Handles node role detection, switching, and optimization
- distributed_coordination: Manages cluster membership, leader election, and consensus
- monitoring: Provides health monitoring, metrics collection, and visualization
- cluster_manager: Integrates all components into a unified management system
"""

from .cluster_manager import ClusterManager
from .distributed_coordination import ClusterCoordinator, MembershipManager
from .monitoring import ClusterMonitor, MetricsCollector
from .role_manager import NodeRole, RoleManager, role_capabilities
from .utils import get_gpu_info


# Daemon management with cluster capabilities
from .enhanced_daemon_manager_with_cluster import (
    EnhancedDaemonManager,
    NodeRole as DaemonNodeRole,
    PeerInfo as DaemonPeerInfo,
    LeaderElection,
    ReplicationManager,
    IndexingService,
)

# Practical cluster setup utilities
# Note: practical_cluster_setup is primarily a script, 
# import it directly if needed: from ipfs_kit_py.cluster import practical_cluster_setup

__all__ = [
    # Existing cluster management
    "NodeRole",
    "RoleManager",
    "role_capabilities",
    "ClusterCoordinator",
    "MembershipManager",
    "ClusterMonitor",
    "MetricsCollector",
    "ClusterManager",
    "get_gpu_info",
    # Daemon management with cluster
    "EnhancedDaemonManager",
    "DaemonNodeRole",
    "DaemonPeerInfo",
    "LeaderElection",
    "ReplicationManager",
    "IndexingService",
]
