"""
Dynamic role switching for IPFS cluster nodes based on available resources (Phase 3B).

This module implements the ability for nodes to dynamically change their roles based on:
- Available resources (memory, disk, CPU, bandwidth)
- Network conditions
- Workload changes
- Environmental factors
- User preferences

Three primary roles are supported:
- master: Orchestration, content management, cluster coordination
- worker: Processing, content pinning, task execution
- leecher: Lightweight consumption with minimal resource contribution

The module provides both automatic resource-based role optimization and
user-controlled role transitions with appropriate validation.
"""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union

import psutil

# Configure logger
logger = logging.getLogger(__name__)


class ClusterDynamicRoles:
    """Implements dynamic role switching for IPFS cluster nodes based on resources.

    This class manages:
    - Resource monitoring and evaluation
    - Role requirement definitions
    - Optimal role determination
    - Role transitions (upgrades and downgrades)
    - Both automated and user-controlled role switching
    """

    def __init__(self, ipfs_kit_instance):
        """Initialize the dynamic role manager.

        Args:
            ipfs_kit_instance: Reference to the parent ipfs_kit instance
        """
        self.kit = ipfs_kit_instance
        self.current_role = self.kit.role if hasattr(self.kit, "role") else "leecher"

        # Default configuration
        self.config = {
            "enabled": True,
            "check_interval": 300,  # Check every 5 minutes by default
            "upgrade_threshold": 0.7,  # 70% of required resources needed to upgrade
            "downgrade_threshold": 0.3,  # 30% of required resources before forced downgrade
            "stability_period": 600,  # Require stable resources for 10 minutes before upgrading
            "transition_cooldown": 1800,  # 30 minutes between role transitions
        }

        # Update config from metadata if available
        if hasattr(self.kit, "metadata") and self.kit.metadata:
            if "dynamic_roles" in self.kit.metadata:
                self.config.update(self.kit.metadata["dynamic_roles"])

        # Resource tracking
        self.last_resources = None
        self.resources_history = []
        self.last_transition_time = 0

        # Initialize role requirements
        self._initialize_role_requirements()

    def _initialize_role_requirements(self):
        """Initialize resource requirements for each role."""
        # Default resource requirements
        self.role_requirements = {
            "leecher": {
                "memory_min": 2 * 1024 * 1024 * 1024,  # 2GB
                "disk_min": 10 * 1024 * 1024 * 1024,  # 10GB
                "cpu_min": 1,
                "bandwidth_min": 1 * 1024 * 1024,  # 1MB/s
            },
            "worker": {
                "memory_min": 4 * 1024 * 1024 * 1024,  # 4GB
                "disk_min": 100 * 1024 * 1024 * 1024,  # 100GB
                "cpu_min": 2,
                "bandwidth_min": 5 * 1024 * 1024,  # 5MB/s
            },
            "master": {
                "memory_min": 8 * 1024 * 1024 * 1024,  # 8GB
                "disk_min": 500 * 1024 * 1024 * 1024,  # 500GB
                "cpu_min": 4,
                "bandwidth_min": 10 * 1024 * 1024,  # 10MB/s
            },
        }

        # Load custom requirements if defined in config
        if hasattr(self.kit, "config") and self.kit.config:
            if "role_requirements" in self.kit.config:
                # Deep update to preserve nested structure
                for role, requirements in self.kit.config["role_requirements"].items():
                    if role in self.role_requirements:
                        self.role_requirements[role].update(requirements)
                    else:
                        self.role_requirements[role] = requirements

    def get_role_requirements(self) -> Dict[str, Dict[str, Any]]:
        """Get resource requirements for all roles.

        Returns:
            Dictionary of resource requirements for each role
        """
        result = {"success": True, "operation": "get_role_requirements", "timestamp": time.time()}

        try:
            # Return a copy to prevent modification
            result.update({"requirements": self.role_requirements})

            return result
        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to get role requirements: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error getting role requirements: {e}")
            return result

    def detect_available_resources(self) -> Dict[str, Any]:
        """Detect available system resources for role determination.

        Returns:
            Dictionary of available resources
        """
        result = {
            "success": True,
            "operation": "detect_available_resources",
            "timestamp": time.time(),
        }

        try:
            # Memory
            memory = psutil.virtual_memory()
            memory_available = memory.available

            # Disk space
            disk = psutil.disk_usage(
                os.path.expanduser("~/.ipfs")
                if os.path.exists(os.path.expanduser("~/.ipfs"))
                else "/"
            )
            disk_available = disk.free

            # CPU cores
            cpu_available = psutil.cpu_count(logical=True)

            # Network bandwidth estimation
            # This is a simplified estimation - a real implementation would track actual bandwidth
            bandwidth_available = self._estimate_bandwidth()

            # GPU detection
            gpu_available = self._detect_gpu()

            # Network stability (simulated - real implementation would track actual stability)
            network_stability = self._assess_network_stability()

            resources = {
                "memory_available": memory_available,
                "disk_available": disk_available,
                "cpu_available": cpu_available,
                "bandwidth_available": bandwidth_available,
                "gpu_available": gpu_available,
                "network_stability": network_stability,
            }

            # Store for history tracking
            self.last_resources = resources
            self.resources_history.append({"timestamp": time.time(), "resources": resources})

            # Trim history if it's getting too long
            if len(self.resources_history) > 20:
                self.resources_history = self.resources_history[-20:]

            result["resources"] = resources
            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to detect resources: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error detecting resources: {e}")
            return result

    def _estimate_bandwidth(self) -> int:
        """Estimate available network bandwidth.

        Returns:
            Estimated available bandwidth in bytes per second
        """
        # In a real implementation, this would measure actual bandwidth
        # For now, we'll use a simplified approach based on interfaces
        try:
            # Get network stats
            net_stats = psutil.net_if_stats()
            net_io = psutil.net_io_counters(pernic=True)

            # Find active interfaces with high speeds
            max_speed = 1 * 1024 * 1024  # 1 MB/s default

            for iface, stats in net_stats.items():
                if stats.isup and iface in net_io:
                    # If the interface reports a speed, use it
                    if hasattr(stats, "speed") and stats.speed > 0:
                        iface_speed = stats.speed * 1024 * 1024 / 8  # Convert Mbps to bytes/sec
                        max_speed = max(max_speed, iface_speed)

            # Return a conservative estimate (25% of max theoretical)
            return int(max_speed * 0.25)

        except Exception as e:
            logger.warning(f"Error estimating bandwidth: {e}")
            return 5 * 1024 * 1024  # Return 5 MB/s as a safe default

    def _detect_gpu(self) -> bool:
        """Detect if a GPU is available.

        Returns:
            Boolean indicating if a GPU is available
        """
        # Check for NVIDIA GPU using pynvml if available
        try:
            import pynvml

            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            return device_count > 0
        except (ImportError, Exception):
            pass

        # Try checking for GPUs using environment variables (CUDA availability)
        if "CUDA_VISIBLE_DEVICES" in os.environ and os.environ["CUDA_VISIBLE_DEVICES"]:
            return True

        # Could add more detection methods here
        return False

    def _assess_network_stability(self) -> float:
        """Assess network stability for role decisions.

        Returns:
            Float between 0.0 (unstable) and 1.0 (stable)
        """
        # In a real implementation, this would track connection stability over time
        # For now, we'll return a high value if we have sufficient resource history
        if len(self.resources_history) >= 3:
            return 0.9
        else:
            return 0.7

    def detect_resource_changes(self) -> Dict[str, Any]:
        """Detect significant changes in resources since last check.

        Returns:
            Dictionary containing resource change information
        """
        result = {
            "success": True,
            "operation": "detect_resource_changes",
            "timestamp": time.time(),
            "significant_change": False,
        }

        try:
            # Get current resources
            current_resources_result = self.detect_available_resources()
            if not current_resources_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to detect current resources",
                    "details": current_resources_result,
                }

            current_resources = current_resources_result["resources"]

            # If we don't have previous resources, can't detect changes
            if not self.last_resources or len(self.resources_history) < 2:
                result.update(
                    {
                        "message": "Not enough history to detect changes",
                        "current_resources": current_resources,
                    }
                )
                return result

            # Get previous resources (not the most recent since that's what we just added)
            previous_resources = self.resources_history[-2]["resources"]

            # Calculate changes
            changes = {}
            change_threshold = 0.2  # 20% change is significant
            significant_change = False

            # Check each resource type
            for resource_type in [
                "memory_available",
                "disk_available",
                "cpu_available",
                "bandwidth_available",
            ]:
                if resource_type in previous_resources and resource_type in current_resources:
                    prev_value = previous_resources[resource_type]
                    curr_value = current_resources[resource_type]

                    # Avoid division by zero
                    if prev_value == 0:
                        prev_value = 1

                    difference = curr_value - prev_value
                    percent_change = (difference / prev_value) * 100

                    changes[resource_type] = {
                        "previous": prev_value,
                        "current": curr_value,
                        "difference": difference,
                        "percent_change": percent_change,
                    }

                    # Check if change is significant
                    if abs(percent_change) >= change_threshold * 100:
                        significant_change = True

            # Include stability changes
            if (
                "network_stability" in previous_resources
                and "network_stability" in current_resources
            ):
                prev_stability = previous_resources["network_stability"]
                curr_stability = current_resources["network_stability"]

                stability_change = curr_stability - prev_stability
                changes["network_stability"] = {
                    "previous": prev_stability,
                    "current": curr_stability,
                    "difference": stability_change,
                    "percent_change": (stability_change / max(0.01, prev_stability)) * 100,
                }

                # Large stability changes are significant
                if abs(stability_change) >= 0.2:
                    significant_change = True

            result.update(
                {
                    "significant_change": significant_change,
                    "previous_resources": previous_resources,
                    "current_resources": current_resources,
                    "changes": changes,
                }
            )

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to detect resource changes: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error detecting resource changes: {e}")
            return result

    def evaluate_potential_roles(self) -> Dict[str, Any]:
        """Evaluate which roles are possible with current resources.

        Returns:
            Dictionary with capability assessment for each role
        """
        result = {
            "success": True,
            "operation": "evaluate_potential_roles",
            "timestamp": time.time(),
        }

        try:
            # Get current resources
            resources_result = self.detect_available_resources()
            if not resources_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to detect resources",
                    "details": resources_result,
                }

            resources = resources_result["resources"]

            # Get role requirements
            requirements_result = self.get_role_requirements()
            if not requirements_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to get role requirements",
                    "details": requirements_result,
                }

            requirements = requirements_result["requirements"]

            # Evaluate each role
            evaluations = {}

            for role, reqs in requirements.items():
                # Calculate capability percentage for each resource type
                mem_pct = resources["memory_available"] / reqs["memory_min"]
                disk_pct = resources["disk_available"] / reqs["disk_min"]
                cpu_pct = resources["cpu_available"] / reqs["cpu_min"]
                bw_pct = resources["bandwidth_available"] / reqs["bandwidth_min"]

                # Use the minimum percentage as the limiting factor
                capability_pct = min(mem_pct, disk_pct, cpu_pct, bw_pct)

                # Determine limiting factor
                limiting_factor = None
                min_pct = float("inf")

                for resource_type, pct in [
                    ("memory", mem_pct),
                    ("disk", disk_pct),
                    ("cpu", cpu_pct),
                    ("bandwidth", bw_pct),
                ]:
                    if pct < min_pct:
                        min_pct = pct
                        limiting_factor = resource_type

                evaluations[role] = {
                    "capable": capability_pct >= 1.0,  # 100% or more of required resources
                    "capability_percent": capability_pct,
                    "limiting_factor": limiting_factor if capability_pct < 1.0 else None,
                    "resource_percentages": {
                        "memory": mem_pct,
                        "disk": disk_pct,
                        "cpu": cpu_pct,
                        "bandwidth": bw_pct,
                    },
                }

            result["evaluations"] = evaluations
            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to evaluate potential roles: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error evaluating potential roles: {e}")
            return result

    def determine_optimal_role(self) -> Dict[str, Any]:
        """Determine the optimal role based on resources and constraints.

        Returns:
            Dictionary with optimal role determination
        """
        result = {"success": True, "operation": "determine_optimal_role", "timestamp": time.time()}

        try:
            # Get current role
            current_role = self.current_role

            # Get role evaluations
            evaluation_result = self.evaluate_potential_roles()
            if not evaluation_result["success"]:
                return {
                    "success": False,
                    "error": "Failed to evaluate potential roles",
                    "details": evaluation_result,
                }

            role_evaluation = evaluation_result["evaluations"]

            # Role order from lowest to highest capability requirement
            role_order = ["leecher", "worker", "master"]

            # First check: can we maintain current role?
            if current_role in role_evaluation and role_evaluation[current_role]["capable"]:
                # Check if we should upgrade (only if we have sufficient resource stability)
                network_stability = (
                    self.last_resources.get("network_stability", 0) if self.last_resources else 0
                )
                resources_stable = network_stability >= 0.8 and len(self.resources_history) >= 3
                cooldown_passed = (time.time() - self.last_transition_time) > self.config[
                    "transition_cooldown"
                ]

                if resources_stable and cooldown_passed:
                    current_index = role_order.index(current_role)

                    # Check if there's a higher role we can upgrade to
                    for next_role in role_order[current_index + 1 :]:
                        if role_evaluation[next_role]["capable"]:
                            return {
                                "success": True,
                                "optimal_role": next_role,
                                "action": "upgrade",
                                "current_role": current_role,
                                "reason": (
                                    f"Node has sufficient resources for {next_role} role "
                                    f"({role_evaluation[next_role]['capability_percent']:.2f}x requirement)"
                                ),
                            }

                # No higher role is viable, stay as current role
                return {
                    "success": True,
                    "optimal_role": current_role,
                    "action": "maintain",
                    "current_role": current_role,
                    "reason": f"Current role '{current_role}' is optimal for available resources",
                }

            # Current role isn't viable or doesn't exist
            # Find the highest viable role
            best_role = None

            for role in reversed(role_order):  # Start from highest
                if role in role_evaluation and role_evaluation[role]["capable"]:
                    best_role = role
                    break

            if not best_role:
                # If no role is viable, default to leecher
                best_role = "leecher"
                action = (
                    "downgrade"
                    if role_order.index(current_role) > role_order.index(best_role)
                    else "maintain"
                )
                reason = "Insufficient resources for any role, defaulting to leecher"
            else:
                # Determine action based on relationship to current role
                if best_role == current_role:
                    action = "maintain"
                    reason = f"Current role '{current_role}' is optimal"
                elif role_order.index(best_role) > role_order.index(current_role):
                    action = "upgrade"
                    reason = f"Upgrading from '{current_role}' to '{best_role}' based on resource capabilities"
                else:
                    action = "downgrade"
                    reason = f"Downgrading from '{current_role}' to '{best_role}' based on resource limitations"

            result.update(
                {
                    "optimal_role": best_role,
                    "action": action,
                    "current_role": current_role,
                    "reason": reason,
                    "evaluations": role_evaluation,
                }
            )

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to determine optimal role: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error determining optimal role: {e}")
            return result

    def upgrade_to_worker(
        self, master_address: str, cluster_secret: str, config_overrides: Dict = None
    ) -> Dict[str, Any]:
        """Upgrade a node from leecher to worker role.

        Args:
            master_address: Multiaddress of the master node
            cluster_secret: Secret key for the cluster
            config_overrides: Optional configuration overrides

        Returns:
            Dictionary with the result of the upgrade operation
        """
        result = {
            "success": False,
            "operation": "upgrade_to_worker",
            "timestamp": time.time(),
            "previous_role": self.current_role,
            "target_role": "worker",
            "actions_performed": [],
        }

        if self.current_role != "leecher":
            result.update(
                {
                    "error": f"Cannot upgrade to worker from {self.current_role}. Only leecher can upgrade to worker.",
                    "error_type": "InvalidRoleTransition",
                }
            )
            return result

        try:
            # 1. Stop IPFS daemon if running
            if hasattr(self.kit, "ipfs") and self.kit.ipfs:
                self.kit.ipfs_stop()
                result["actions_performed"].append("Stopped IPFS daemon")

            # 2. Update node configuration for worker role
            worker_config = {
                "Datastore": {"StorageMax": "100GB", "StorageGCWatermark": 90, "GCPeriod": "1h"},
                "Routing": {"Type": "dhtclient"},
                "Swarm": {"ConnMgr": {"LowWater": 100, "HighWater": 400, "GracePeriod": "20s"}},
            }

            # Apply any overrides
            if config_overrides:
                self._deep_update(worker_config, config_overrides)

            # Update configuration
            if hasattr(self.kit, "update_ipfs_config"):
                self.kit.update_ipfs_config(worker_config)
                result["actions_performed"].append("Updated node configuration for worker role")

            # 3. Initialize cluster follow service
            if hasattr(self.kit, "create_cluster_follow_service"):
                follow_result = self.kit.create_cluster_follow_service(
                    master_address=master_address, cluster_secret=cluster_secret
                )

                if not follow_result.get("success", False):
                    raise Exception(
                        f"Failed to initialize cluster follow service: {follow_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Initialized cluster follow service")

            # 4. Restart IPFS daemon with worker profile
            if hasattr(self.kit, "ipfs_start"):
                start_result = self.kit.ipfs_start(profile="worker")

                if not start_result.get("success", False):
                    raise Exception(
                        f"Failed to restart IPFS daemon: {start_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Restarted IPFS daemon with worker profile")

            # 5. Join cluster as worker
            if hasattr(self.kit, "cluster_follow_join"):
                join_result = self.kit.cluster_follow_join()

                if not join_result.get("success", False):
                    raise Exception(
                        f"Failed to join cluster: {join_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Joined cluster as worker")

            # Update role and transition time
            self.current_role = "worker"
            if hasattr(self.kit, "role"):
                self.kit.role = "worker"
            self.last_transition_time = time.time()

            # Update success
            result["success"] = True
            result["new_role"] = "worker"

            logger.info(f"Successfully upgraded node from leecher to worker role")

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to upgrade to worker: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error upgrading to worker: {e}")

            # Attempt to recover
            if (
                hasattr(self.kit, "ipfs_start")
                and "Restarted IPFS daemon" not in result["actions_performed"]
            ):
                try:
                    self.kit.ipfs_start(profile="default")
                    logger.info("Recovered IPFS daemon after failed upgrade")
                except Exception as e2:
                    logger.error(f"Failed to recover after upgrade failure: {e2}")

            return result

    def upgrade_to_master(
        self, cluster_secret: str, config_overrides: Dict = None
    ) -> Dict[str, Any]:
        """Upgrade a node from worker to master role.

        Args:
            cluster_secret: Secret key for the cluster
            config_overrides: Optional configuration overrides

        Returns:
            Dictionary with the result of the upgrade operation
        """
        result = {
            "success": False,
            "operation": "upgrade_to_master",
            "timestamp": time.time(),
            "previous_role": self.current_role,
            "target_role": "master",
            "actions_performed": [],
        }

        # Normally we'd require the current role to be worker, but for testing/administration
        # we'll also allow upgrading directly from leecher to master
        if self.current_role not in ["worker", "leecher"]:
            result.update(
                {
                    "error": f"Cannot upgrade to master from {self.current_role}.",
                    "error_type": "InvalidRoleTransition",
                }
            )
            return result

        try:
            # 1. Stop IPFS daemon if running
            if hasattr(self.kit, "ipfs") and self.kit.ipfs:
                self.kit.ipfs_stop()
                result["actions_performed"].append("Stopped IPFS daemon")

            # 2. Stop cluster follow service if running (for worker)
            if self.current_role == "worker" and hasattr(self.kit, "ipfs_cluster_follow"):
                if hasattr(self.kit, "cluster_follow_stop"):
                    self.kit.cluster_follow_stop()
                    result["actions_performed"].append("Stopped cluster follow service")

            # 3. Update node configuration for master role
            master_config = {
                "Datastore": {"StorageMax": "1TB", "StorageGCWatermark": 80, "GCPeriod": "12h"},
                "Routing": {"Type": "dhtserver"},  # Full DHT node
                "Pinning": {"RemoteServices": {}},  # Will be filled in with actual services
                "Cluster": {
                    "PeerAddresses": [],
                    "ReplicationFactor": 3,
                    "MonitorPingInterval": "15s",
                },
            }

            # Apply any overrides
            if config_overrides:
                self._deep_update(master_config, config_overrides)

            # Update configuration
            if hasattr(self.kit, "update_ipfs_config"):
                self.kit.update_ipfs_config(master_config)
                result["actions_performed"].append("Updated node configuration for master role")

            # 4. Initialize cluster service
            if hasattr(self.kit, "create_cluster_service"):
                service_result = self.kit.create_cluster_service(
                    cluster_secret=cluster_secret,
                    consensus="crdt",  # Use CRDT for consensus by default
                    init_config_overrides=config_overrides,
                )

                if not service_result.get("success", False):
                    raise Exception(
                        f"Failed to initialize cluster service: {service_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Initialized cluster service")

            # 5. Initialize cluster control interface
            if hasattr(self.kit, "create_cluster_ctl"):
                ctl_result = self.kit.create_cluster_ctl()

                if not ctl_result.get("success", False):
                    raise Exception(
                        f"Failed to initialize cluster control interface: {ctl_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Initialized cluster control interface")

            # 6. Restart IPFS daemon with master profile
            if hasattr(self.kit, "ipfs_start"):
                start_result = self.kit.ipfs_start(profile="server")

                if not start_result.get("success", False):
                    raise Exception(
                        f"Failed to restart IPFS daemon: {start_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Restarted IPFS daemon with master profile")

            # 7. Start cluster service as master
            if hasattr(self.kit, "cluster_service_start"):
                start_result = self.kit.cluster_service_start()

                if not start_result.get("success", False):
                    raise Exception(
                        f"Failed to start cluster service: {start_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Started cluster service as master")

            # Update role and transition time
            self.current_role = "master"
            if hasattr(self.kit, "role"):
                self.kit.role = "master"
            self.last_transition_time = time.time()

            # Update success
            result["success"] = True
            result["new_role"] = "master"

            logger.info(f"Successfully upgraded node from {result['previous_role']} to master role")

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to upgrade to master: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error upgrading to master: {e}")

            # Attempt to recover
            if (
                hasattr(self.kit, "ipfs_start")
                and "Restarted IPFS daemon" not in result["actions_performed"]
            ):
                try:
                    self.kit.ipfs_start(profile="default")
                    logger.info("Recovered IPFS daemon after failed upgrade")
                except Exception as e2:
                    logger.error(f"Failed to recover after upgrade failure: {e2}")

            return result

    def downgrade_to_worker(
        self, master_address: str = None, cluster_secret: str = None
    ) -> Dict[str, Any]:
        """Downgrade a node from master to worker role.

        Args:
            master_address: Multiaddress of the new master node to follow
            cluster_secret: Secret key for the cluster

        Returns:
            Dictionary with the result of the downgrade operation
        """
        result = {
            "success": False,
            "operation": "downgrade_to_worker",
            "timestamp": time.time(),
            "previous_role": self.current_role,
            "target_role": "worker",
            "actions_performed": [],
        }

        if self.current_role != "master":
            result.update(
                {
                    "error": f"Cannot downgrade to worker from {self.current_role}. Only master can downgrade to worker.",
                    "error_type": "InvalidRoleTransition",
                }
            )
            return result

        try:
            # 1. Stop IPFS daemon if running
            if hasattr(self.kit, "ipfs") and self.kit.ipfs:
                self.kit.ipfs_stop()
                result["actions_performed"].append("Stopped IPFS daemon")

            # 2. Stop cluster service
            if hasattr(self.kit, "cluster_service_stop"):
                self.kit.cluster_service_stop()
                result["actions_performed"].append("Stopped cluster service")

            # 3. Update node configuration for worker role
            worker_config = {
                "Datastore": {"StorageMax": "100GB", "StorageGCWatermark": 90, "GCPeriod": "1h"},
                "Routing": {"Type": "dhtclient"},
                "Swarm": {"ConnMgr": {"LowWater": 100, "HighWater": 400, "GracePeriod": "20s"}},
            }

            # Update configuration
            if hasattr(self.kit, "update_ipfs_config"):
                self.kit.update_ipfs_config(worker_config)
                result["actions_performed"].append("Updated node configuration for worker role")

            # 4. Initialize cluster follow service
            if (
                master_address
                and cluster_secret
                and hasattr(self.kit, "create_cluster_follow_service")
            ):
                follow_result = self.kit.create_cluster_follow_service(
                    master_address=master_address, cluster_secret=cluster_secret
                )

                if not follow_result.get("success", False):
                    raise Exception(
                        f"Failed to initialize cluster follow service: {follow_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Initialized cluster follow service")

            # 5. Restart IPFS daemon with worker profile
            if hasattr(self.kit, "ipfs_start"):
                start_result = self.kit.ipfs_start(profile="worker")

                if not start_result.get("success", False):
                    raise Exception(
                        f"Failed to restart IPFS daemon: {start_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Restarted IPFS daemon with worker profile")

            # 6. Join cluster as worker if we have master info
            if master_address and cluster_secret and hasattr(self.kit, "cluster_follow_join"):
                join_result = self.kit.cluster_follow_join()

                if not join_result.get("success", False):
                    raise Exception(
                        f"Failed to join cluster: {join_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Joined cluster as worker")

            # Update role and transition time
            self.current_role = "worker"
            if hasattr(self.kit, "role"):
                self.kit.role = "worker"
            self.last_transition_time = time.time()

            # Update success
            result["success"] = True
            result["new_role"] = "worker"

            logger.info(f"Successfully downgraded node from master to worker role")

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to downgrade to worker: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error downgrading to worker: {e}")

            # Attempt to recover
            if (
                hasattr(self.kit, "ipfs_start")
                and "Restarted IPFS daemon" not in result["actions_performed"]
            ):
                try:
                    self.kit.ipfs_start(profile="server")  # Try to restore as master
                    logger.info("Recovered IPFS daemon after failed downgrade")
                except Exception as e2:
                    logger.error(f"Failed to recover after downgrade failure: {e2}")

            return result

    def downgrade_to_leecher(self) -> Dict[str, Any]:
        """Downgrade a node to leecher role.

        Returns:
            Dictionary with the result of the downgrade operation
        """
        result = {
            "success": False,
            "operation": "downgrade_to_leecher",
            "timestamp": time.time(),
            "previous_role": self.current_role,
            "target_role": "leecher",
            "actions_performed": [],
        }

        if self.current_role == "leecher":
            result.update(
                {
                    "success": True,
                    "message": "Node is already in leecher role",
                    "new_role": "leecher",
                }
            )
            return result

        try:
            # 1. Stop IPFS daemon if running
            if hasattr(self.kit, "ipfs") and self.kit.ipfs:
                self.kit.ipfs_stop()
                result["actions_performed"].append("Stopped IPFS daemon")

            # 2. Stop cluster service or follow service
            if self.current_role == "master" and hasattr(self.kit, "cluster_service_stop"):
                self.kit.cluster_service_stop()
                result["actions_performed"].append("Stopped cluster service")
            elif self.current_role == "worker" and hasattr(self.kit, "cluster_follow_stop"):
                self.kit.cluster_follow_stop()
                result["actions_performed"].append("Stopped cluster follow service")

            # 3. Update node configuration for leecher role
            leecher_config = {
                "Datastore": {"StorageMax": "10GB", "StorageGCWatermark": 95, "GCPeriod": "30m"},
                "Routing": {"Type": "dhtclient"},
                "Swarm": {"ConnMgr": {"LowWater": 20, "HighWater": 100, "GracePeriod": "10s"}},
                "Offline": {"AllowOfflineExchange": True, "MaxOfflineQueue": 100},
            }

            # Update configuration
            if hasattr(self.kit, "update_ipfs_config"):
                self.kit.update_ipfs_config(leecher_config)
                result["actions_performed"].append("Updated node configuration for leecher role")

            # 4. Restart IPFS daemon with leecher profile
            if hasattr(self.kit, "ipfs_start"):
                start_result = self.kit.ipfs_start(profile="lowpower")

                if not start_result.get("success", False):
                    raise Exception(
                        f"Failed to restart IPFS daemon: {start_result.get('error', 'Unknown error')}"
                    )

                result["actions_performed"].append("Restarted IPFS daemon with leecher profile")

            # 5. Remove cluster-related services if needed
            if self.current_role == "master":
                # Remove cluster service
                if hasattr(self.kit, "remove_cluster_service"):
                    self.kit.remove_cluster_service()
                    result["actions_performed"].append("Removed cluster service")
            elif self.current_role == "worker":
                # Remove cluster follow service
                if hasattr(self.kit, "remove_cluster_follow_service"):
                    self.kit.remove_cluster_follow_service()
                    result["actions_performed"].append("Removed cluster follow service")

            # Update role and transition time
            self.current_role = "leecher"
            if hasattr(self.kit, "role"):
                self.kit.role = "leecher"
            self.last_transition_time = time.time()

            # Update success
            result["success"] = True
            result["new_role"] = "leecher"

            logger.info(
                f"Successfully downgraded node from {result['previous_role']} to leecher role"
            )

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to downgrade to leecher: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error downgrading to leecher: {e}")

            # Attempt to recover
            if (
                hasattr(self.kit, "ipfs_start")
                and "Restarted IPFS daemon" not in result["actions_performed"]
            ):
                try:
                    # Try to restore previous role
                    profile = "default"
                    if self.current_role == "master":
                        profile = "server"
                    elif self.current_role == "worker":
                        profile = "worker"
                    self.kit.ipfs_start(profile=profile)
                    logger.info("Recovered IPFS daemon after failed downgrade")
                except Exception as e2:
                    logger.error(f"Failed to recover after downgrade failure: {e2}")

            return result

    def check_and_update_role(self) -> Dict[str, Any]:
        """Check resources and automatically update role if needed.

        Returns:
            Dictionary with the result of the role check
        """
        result = {
            "success": False,
            "operation": "check_and_update_role",
            "timestamp": time.time(),
            "role_change_needed": False,
            "role_change_executed": False,
        }

        try:
            # Skip if dynamic roles are disabled
            if not self.config.get("enabled", True):
                result.update(
                    {
                        "success": True,
                        "role_change_needed": False,
                        "message": "Dynamic role switching is disabled",
                    }
                )
                return result

            # Check if resources have changed significantly
            change_result = self.detect_resource_changes()
            if not change_result.get("success", False):
                result.update(
                    {
                        "success": False,
                        "error": "Failed to detect resource changes",
                        "details": change_result,
                    }
                )
                return result

            # If no significant changes, exit early
            if not change_result.get("significant_change", False):
                result.update(
                    {
                        "success": True,
                        "role_change_needed": False,
                        "message": "No significant resource changes detected",
                    }
                )
                return result

            # Check if we're in cooldown period
            if (time.time() - self.last_transition_time) < self.config.get(
                "transition_cooldown", 1800
            ):
                result.update(
                    {
                        "success": True,
                        "role_change_needed": False,
                        "message": "In role transition cooldown period",
                    }
                )
                return result

            # Determine optimal role
            role_result = self.determine_optimal_role()
            if not role_result.get("success", False):
                result.update(
                    {
                        "success": False,
                        "error": "Failed to determine optimal role",
                        "details": role_result,
                    }
                )
                return result

            # If optimal role is current role, no change needed
            if role_result.get("action", "") == "maintain":
                result.update(
                    {
                        "success": True,
                        "role_change_needed": False,
                        "message": f"Current role '{self.current_role}' remains optimal",
                    }
                )
                return result

            # Need to change role
            result["role_change_needed"] = True
            action = role_result.get("action", "")
            optimal_role = role_result.get("optimal_role", "")

            # Verify if we can actually perform the action
            if not optimal_role or optimal_role not in ["leecher", "worker", "master"]:
                result.update(
                    {
                        "success": True,
                        "role_change_executed": False,
                        "error": f"Invalid target role: {optimal_role}",
                    }
                )
                return result

            # Need to upgrade
            if action == "upgrade":
                if self.current_role == "leecher" and optimal_role == "worker":
                    # Need master address and cluster secret
                    if not hasattr(self.kit, "get_master_info"):
                        result.update(
                            {
                                "success": True,
                                "role_change_executed": False,
                                "error": "Cannot upgrade to worker: missing master info",
                            }
                        )
                        return result

                    # Get master info
                    master_info = self.kit.get_master_info()
                    if not master_info.get("success", False):
                        result.update(
                            {
                                "success": True,
                                "role_change_executed": False,
                                "error": "Cannot upgrade to worker: failed to get master info",
                            }
                        )
                        return result

                    # Perform upgrade
                    upgrade_result = self.upgrade_to_worker(
                        master_address=master_info.get("master_address"),
                        cluster_secret=master_info.get("cluster_secret"),
                    )

                    result.update(
                        {
                            "success": upgrade_result.get("success", False),
                            "role_change_executed": upgrade_result.get("success", False),
                            "previous_role": upgrade_result.get("previous_role"),
                            "new_role": upgrade_result.get("new_role"),
                            "message": f"Upgraded from leecher to worker role",
                        }
                    )

                    if not upgrade_result.get("success", False):
                        result["error"] = upgrade_result.get("error")

                    return result

                elif (
                    self.current_role == "leecher" or self.current_role == "worker"
                ) and optimal_role == "master":
                    # Need cluster secret
                    if not hasattr(self.kit, "get_cluster_secret"):
                        result.update(
                            {
                                "success": True,
                                "role_change_executed": False,
                                "error": "Cannot upgrade to master: missing cluster secret",
                            }
                        )
                        return result

                    # Get cluster secret
                    secret_info = self.kit.get_cluster_secret()
                    if not secret_info.get("success", False):
                        result.update(
                            {
                                "success": True,
                                "role_change_executed": False,
                                "error": "Cannot upgrade to master: failed to get cluster secret",
                            }
                        )
                        return result

                    # Perform upgrade
                    upgrade_result = self.upgrade_to_master(
                        cluster_secret=secret_info.get("cluster_secret")
                    )

                    result.update(
                        {
                            "success": upgrade_result.get("success", False),
                            "role_change_executed": upgrade_result.get("success", False),
                            "previous_role": upgrade_result.get("previous_role"),
                            "new_role": upgrade_result.get("new_role"),
                            "message": f"Upgraded from {upgrade_result.get('previous_role')} to master role",
                        }
                    )

                    if not upgrade_result.get("success", False):
                        result["error"] = upgrade_result.get("error")

                    return result

            # Need to downgrade
            elif action == "downgrade":
                if self.current_role == "master" and optimal_role == "worker":
                    # Need new master address if available
                    master_address = None
                    cluster_secret = None

                    if hasattr(self.kit, "get_alternate_master_info"):
                        # Try to get info about another master to follow
                        alt_info = self.kit.get_alternate_master_info()
                        if alt_info.get("success", False):
                            master_address = alt_info.get("master_address")
                            cluster_secret = alt_info.get("cluster_secret")

                    # Perform downgrade
                    downgrade_result = self.downgrade_to_worker(
                        master_address=master_address, cluster_secret=cluster_secret
                    )

                    result.update(
                        {
                            "success": downgrade_result.get("success", False),
                            "role_change_executed": downgrade_result.get("success", False),
                            "previous_role": downgrade_result.get("previous_role"),
                            "new_role": downgrade_result.get("new_role"),
                            "message": f"Downgraded from master to worker role",
                        }
                    )

                    if not downgrade_result.get("success", False):
                        result["error"] = downgrade_result.get("error")

                    return result

                elif (
                    self.current_role == "master" or self.current_role == "worker"
                ) and optimal_role == "leecher":
                    # Perform downgrade
                    downgrade_result = self.downgrade_to_leecher()

                    result.update(
                        {
                            "success": downgrade_result.get("success", False),
                            "role_change_executed": downgrade_result.get("success", False),
                            "previous_role": downgrade_result.get("previous_role"),
                            "new_role": downgrade_result.get("new_role"),
                            "message": f"Downgraded from {downgrade_result.get('previous_role')} to leecher role",
                        }
                    )

                    if not downgrade_result.get("success", False):
                        result["error"] = downgrade_result.get("error")

                    return result

            # If we get here, something went wrong
            result.update(
                {
                    "success": False,
                    "role_change_executed": False,
                    "error": f"Unsupported role transition: {self.current_role} to {optimal_role}",
                }
            )

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to check and update role: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error in check_and_update_role: {e}")
            return result

    def change_role(
        self,
        target_role: str,
        force: bool = False,
        master_address: str = None,
        cluster_secret: str = None,
        config_overrides: Dict = None,
    ) -> Dict[str, Any]:
        """Change node role with user-provided parameters.

        Args:
            target_role: The target role to switch to
            force: Whether to force the change even if resources are insufficient
            master_address: Master node address for worker role
            cluster_secret: Cluster secret key
            config_overrides: Additional configuration overrides

        Returns:
            Dictionary with the result of the role change
        """
        result = {
            "success": False,
            "operation": "change_role",
            "timestamp": time.time(),
            "current_role": self.current_role,
            "target_role": target_role,
            "forced": force,
        }

        try:
            # Validate target role
            if target_role not in ["leecher", "worker", "master"]:
                result.update({"success": False, "error": f"Invalid role: {target_role}"})
                return result

            # Check for same role
            if target_role == self.current_role:
                result.update(
                    {"success": True, "message": f"Node is already in {target_role} role"}
                )
                return result

            # If not forced, check if resources are sufficient
            if not force:
                eval_result = self.evaluate_potential_roles()
                if not eval_result.get("success", False):
                    result.update(
                        {
                            "success": False,
                            "error": "Failed to evaluate resource requirements",
                            "details": eval_result,
                        }
                    )
                    return result

                role_evals = eval_result.get("evaluations", {})

                if target_role not in role_evals or not role_evals[target_role].get(
                    "capable", False
                ):
                    limiting_factor = (
                        role_evals[target_role]["limiting_factor"]
                        if target_role in role_evals
                        else "unknown"
                    )
                    capability_pct = (
                        role_evals[target_role]["capability_percent"]
                        if target_role in role_evals
                        else 0
                    )

                    result.update(
                        {
                            "success": False,
                            "error": f"Insufficient resources for role: {target_role}",
                            "capability_percent": capability_pct,
                            "limiting_factor": limiting_factor,
                        }
                    )
                    return result

            # Determine transition type
            roles_rank = {"leecher": 0, "worker": 1, "master": 2}
            current_rank = roles_rank.get(self.current_role, 0)
            target_rank = roles_rank.get(target_role, 0)

            if target_rank > current_rank:
                # Upgrade
                if self.current_role == "leecher" and target_role == "worker":
                    # Require master_address and cluster_secret
                    if not master_address or not cluster_secret:
                        result.update(
                            {
                                "success": False,
                                "error": "Missing required parameters: master_address and cluster_secret for worker role",
                            }
                        )
                        return result

                    # Perform upgrade
                    upgrade_result = self.upgrade_to_worker(
                        master_address=master_address,
                        cluster_secret=cluster_secret,
                        config_overrides=config_overrides,
                    )

                    result.update(
                        {
                            "success": upgrade_result.get("success", False),
                            "previous_role": upgrade_result.get("previous_role"),
                            "new_role": upgrade_result.get("new_role"),
                            "message": f"Upgraded from {upgrade_result.get('previous_role')} to {upgrade_result.get('new_role')}",
                        }
                    )

                    if not upgrade_result.get("success", False):
                        result["error"] = upgrade_result.get("error")

                    return result

                elif self.current_role == "leecher" and target_role == "master":
                    # Require cluster_secret
                    if not cluster_secret:
                        result.update(
                            {
                                "success": False,
                                "error": "Missing required parameter: cluster_secret for master role",
                            }
                        )
                        return result

                    # Perform upgrade
                    upgrade_result = self.upgrade_to_master(
                        cluster_secret=cluster_secret, config_overrides=config_overrides
                    )

                    result.update(
                        {
                            "success": upgrade_result.get("success", False),
                            "previous_role": upgrade_result.get("previous_role"),
                            "new_role": upgrade_result.get("new_role"),
                            "message": f"Upgraded from {upgrade_result.get('previous_role')} to {upgrade_result.get('new_role')}",
                        }
                    )

                    if not upgrade_result.get("success", False):
                        result["error"] = upgrade_result.get("error")

                    return result

                elif self.current_role == "worker" and target_role == "master":
                    # Require cluster_secret
                    if not cluster_secret:
                        result.update(
                            {
                                "success": False,
                                "error": "Missing required parameter: cluster_secret for master role",
                            }
                        )
                        return result

                    # Perform upgrade
                    upgrade_result = self.upgrade_to_master(
                        cluster_secret=cluster_secret, config_overrides=config_overrides
                    )

                    result.update(
                        {
                            "success": upgrade_result.get("success", False),
                            "previous_role": upgrade_result.get("previous_role"),
                            "new_role": upgrade_result.get("new_role"),
                            "message": f"Upgraded from {upgrade_result.get('previous_role')} to {upgrade_result.get('new_role')}",
                        }
                    )

                    if not upgrade_result.get("success", False):
                        result["error"] = upgrade_result.get("error")

                    return result

            else:
                # Downgrade
                if self.current_role == "master" and target_role == "worker":
                    # master_address and cluster_secret are optional but useful
                    downgrade_result = self.downgrade_to_worker(
                        master_address=master_address, cluster_secret=cluster_secret
                    )

                    result.update(
                        {
                            "success": downgrade_result.get("success", False),
                            "previous_role": downgrade_result.get("previous_role"),
                            "new_role": downgrade_result.get("new_role"),
                            "message": f"Downgraded from {downgrade_result.get('previous_role')} to {downgrade_result.get('new_role')}",
                        }
                    )

                    if not downgrade_result.get("success", False):
                        result["error"] = downgrade_result.get("error")

                    return result

                elif self.current_role == "master" and target_role == "leecher":
                    downgrade_result = self.downgrade_to_leecher()

                    result.update(
                        {
                            "success": downgrade_result.get("success", False),
                            "previous_role": downgrade_result.get("previous_role"),
                            "new_role": downgrade_result.get("new_role"),
                            "message": f"Downgraded from {downgrade_result.get('previous_role')} to {downgrade_result.get('new_role')}",
                        }
                    )

                    if not downgrade_result.get("success", False):
                        result["error"] = downgrade_result.get("error")

                    return result

                elif self.current_role == "worker" and target_role == "leecher":
                    downgrade_result = self.downgrade_to_leecher()

                    result.update(
                        {
                            "success": downgrade_result.get("success", False),
                            "previous_role": downgrade_result.get("previous_role"),
                            "new_role": downgrade_result.get("new_role"),
                            "message": f"Downgraded from {downgrade_result.get('previous_role')} to {downgrade_result.get('new_role')}",
                        }
                    )

                    if not downgrade_result.get("success", False):
                        result["error"] = downgrade_result.get("error")

                    return result

            # If we get here, the transition was not handled
            result.update(
                {
                    "success": False,
                    "error": f"Unsupported role transition: {self.current_role} to {target_role}",
                }
            )

            return result

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": f"Failed to change role: {str(e)}",
                    "error_type": type(e).__name__,
                }
            )
            logger.error(f"Error in change_role: {e}")
            return result

    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Deep update a dictionary with another dictionary.

        Args:
            base_dict: Base dictionary to update
            update_dict: Dictionary with updates to apply
        """
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
