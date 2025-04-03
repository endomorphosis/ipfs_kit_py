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

__all__ = [
    "NodeRole",
    "RoleManager",
    "role_capabilities",
    "ClusterCoordinator",
    "MembershipManager",
    "ClusterMonitor",
    "MetricsCollector",
    "ClusterManager",
    "get_gpu_info",
]
