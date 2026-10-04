"""
Cluster Manager for IPFS Kit.

This module integrates all cluster management components into a unified interface,
providing a single point of access for role management, distributed coordination,
and monitoring capabilities.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .distributed_coordination import ClusterCoordinator, MembershipManager
from .monitoring import ClusterMonitor, MetricsCollector
from .role_manager import NodeRole, RoleManager, role_capabilities

# Configure logger
logger = logging.getLogger(__name__)


class ClusterManager:
    """
    Unified manager for IPFS cluster operations.

    This class integrates the role-based architecture, distributed coordination,
    and monitoring components into a cohesive system for managing IPFS clusters.

    Key responsibilities:
    1. Managing node roles and capabilities
    2. Coordinating task distribution and execution
    3. Maintaining cluster membership and leader election
    4. Collecting metrics and monitoring cluster health
    5. Adapting to changing resource conditions
    6. Managing configuration across the cluster
    """

    def __init__(
        self,
        node_id: str,
        role: str = "leecher",
        peer_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        enable_libp2p: bool = False,
    ):
        """
        Initialize the cluster manager.

        Args:
            node_id: Unique identifier for this node
            role: Initial role (master, worker, leecher, gateway, observer)
            peer_id: libp2p peer ID (if available)
            config: Configuration parameters
            resources: Available resources (CPU, memory, disk, etc.)
            metadata: Additional metadata
            enable_libp2p: Whether libp2p direct P2P is available
        """
        self.node_id = node_id
        self.peer_id = peer_id or node_id
        self.initial_role = role
        self.config = config or {}
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.enable_libp2p = enable_libp2p

        # Extract cluster ID from config or generate a default
        self.cluster_id = self.config.get("cluster_id", "default-cluster")

        # Initialize flags
        self.is_running = False
        self.shutdown_event = threading.Event()

        # Track component status
        self.component_status = {
            "role_manager": False,
            "membership_manager": False,
            "cluster_coordinator": False,
            "metrics_collector": False,
            "cluster_monitor": False,
        }

        # Set up role manager with configuration callback
        self.role_manager = RoleManager(
            initial_role=self.initial_role,
            resources=self.resources,
            metadata=self.metadata,
            auto_detect=True,
            role_switching_enabled=True,
            configuration_callback=self._handle_role_configuration_change,
            cluster_discovery_callback=self._handle_cluster_discovery,
        )

        # Set up metrics collector
        self.metrics_collector = MetricsCollector(
            node_id=self.node_id,
            role=self.initial_role,
            collection_interval=self.config.get("metrics_interval", 60),
        )

        # Set up membership manager
        self.membership_manager = MembershipManager(
            cluster_id=self.cluster_id,
            node_id=self.node_id,
            role=self.initial_role,
            peer_id=self.peer_id,
            heartbeat_interval=self.config.get("heartbeat_interval", 30),
            membership_timeout=self.config.get("membership_timeout", 90),
            membership_callback=self._handle_membership_change,
        )

        # Determine if this node should initially act as master
        is_master = self.initial_role == "master"

        # Set up cluster coordinator
        self.cluster_coordinator = ClusterCoordinator(
            cluster_id=self.cluster_id,
            node_id=self.node_id,
            is_master=is_master,
            election_timeout=self.config.get("election_timeout", 30),
            leadership_callback=self._handle_leadership_change,
            membership_manager=self.membership_manager,
        )

        # Set up cluster monitor
        self.cluster_monitor = ClusterMonitor(
            node_id=self.node_id,
            metrics_collector=self.metrics_collector,
            check_interval=self.config.get("check_interval", 60),
            alert_callback=self._handle_alert,
        )

        # Track key metrics
        self.metrics = {
            "start_time": None,
            "uptime": 0,
            "role_switches": 0,
            "adaptations": 0,
            "tasks_processed": 0,
            "leadership_changes": 0,
            "membership_changes": 0,
            "alerts_generated": 0,
        }

        logger.info(
            f"Cluster manager initialized with role {self.initial_role} for cluster {self.cluster_id}"
        )

    def start(self) -> Dict[str, Any]:
        """
        Start all cluster management components.

        Returns:
            Dictionary with start status for each component
        """
        if self.is_running:
            return {"success": False, "error": "Cluster manager is already running"}

        logger.info(f"Starting cluster manager for node {self.node_id}...")

        result = {"success": True, "components": {}}

        # Start role manager
        try:
            self.role_manager.start()
            self.component_status["role_manager"] = True
            result["components"]["role_manager"] = "Started"
        except Exception as e:
            logger.error(f"Failed to start role manager: {str(e)}")
            result["components"]["role_manager"] = f"Failed: {str(e)}"
            result["success"] = False

        # Start metrics collector
        try:
            self.metrics_collector.start()
            self.component_status["metrics_collector"] = True
            result["components"]["metrics_collector"] = "Started"
        except Exception as e:
            logger.error(f"Failed to start metrics collector: {str(e)}")
            result["components"]["metrics_collector"] = f"Failed: {str(e)}"
            result["success"] = False

        # Start membership manager
        try:
            self.membership_manager.start()
            self.component_status["membership_manager"] = True
            result["components"]["membership_manager"] = "Started"
        except Exception as e:
            logger.error(f"Failed to start membership manager: {str(e)}")
            result["components"]["membership_manager"] = f"Failed: {str(e)}"
            result["success"] = False

        # Start cluster coordinator
        try:
            self.cluster_coordinator.start()
            self.component_status["cluster_coordinator"] = True
            result["components"]["cluster_coordinator"] = "Started"
        except Exception as e:
            logger.error(f"Failed to start cluster coordinator: {str(e)}")
            result["components"]["cluster_coordinator"] = f"Failed: {str(e)}"
            result["success"] = False

        # Start cluster monitor
        try:
            self.cluster_monitor.start()
            self.component_status["cluster_monitor"] = True
            result["components"]["cluster_monitor"] = "Started"
        except Exception as e:
            logger.error(f"Failed to start cluster monitor: {str(e)}")
            result["components"]["cluster_monitor"] = f"Failed: {str(e)}"
            result["success"] = False

        # Start background thread for periodic management
        self.shutdown_event.clear()
        self.management_thread = threading.Thread(target=self._management_loop, daemon=True)
        self.management_thread.start()

        self.is_running = True
        self.metrics["start_time"] = time.time()

        logger.info(f"Cluster manager started with result: {result}")
        return result

    def stop(self) -> Dict[str, Any]:
        """
        Stop all cluster management components.

        Returns:
            Dictionary with stop status for each component
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        logger.info(f"Stopping cluster manager for node {self.node_id}...")

        # Signal management thread to stop
        self.shutdown_event.set()

        if hasattr(self, "management_thread") and self.management_thread.is_alive():
            self.management_thread.join(timeout=10)

        result = {"success": True, "components": {}}

        # Stop components in reverse order of dependency

        # Stop cluster monitor
        try:
            self.cluster_monitor.stop()
            self.component_status["cluster_monitor"] = False
            result["components"]["cluster_monitor"] = "Stopped"
        except Exception as e:
            logger.error(f"Failed to stop cluster monitor: {str(e)}")
            result["components"]["cluster_monitor"] = f"Failed: {str(e)}"
            result["success"] = False

        # Stop cluster coordinator
        try:
            self.cluster_coordinator.stop()
            self.component_status["cluster_coordinator"] = False
            result["components"]["cluster_coordinator"] = "Stopped"
        except Exception as e:
            logger.error(f"Failed to stop cluster coordinator: {str(e)}")
            result["components"]["cluster_coordinator"] = f"Failed: {str(e)}"
            result["success"] = False

        # Stop membership manager
        try:
            self.membership_manager.stop()
            self.component_status["membership_manager"] = False
            result["components"]["membership_manager"] = "Stopped"
        except Exception as e:
            logger.error(f"Failed to stop membership manager: {str(e)}")
            result["components"]["membership_manager"] = f"Failed: {str(e)}"
            result["success"] = False

        # Stop metrics collector
        try:
            self.metrics_collector.stop()
            self.component_status["metrics_collector"] = False
            result["components"]["metrics_collector"] = "Stopped"
        except Exception as e:
            logger.error(f"Failed to stop metrics collector: {str(e)}")
            result["components"]["metrics_collector"] = f"Failed: {str(e)}"
            result["success"] = False

        # Stop role manager
        try:
            self.role_manager.stop()
            self.component_status["role_manager"] = False
            result["components"]["role_manager"] = "Stopped"
        except Exception as e:
            logger.error(f"Failed to stop role manager: {str(e)}")
            result["components"]["role_manager"] = f"Failed: {str(e)}"
            result["success"] = False

        self.is_running = False

        # Calculate final metrics
        self.metrics["uptime"] = (
            time.time() - self.metrics["start_time"] if self.metrics["start_time"] else 0
        )

        logger.info(f"Cluster manager stopped with result: {result}")
        return result

    def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 1,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Submit a task to the cluster for processing.

        Args:
            task_type: Type of task to execute
            payload: Task data and parameters
            priority: Task priority (1-10, higher is more important)
            timeout: Maximum time to wait for task completion (seconds)

        Returns:
            Dictionary with task submission status and task_id
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        # Validate task parameters
        if not task_type:
            return {"success": False, "error": "Task type must be specified"}

        if not isinstance(payload, dict):
            return {"success": False, "error": "Payload must be a dictionary"}

        # Add metadata to the task
        task_metadata = {
            "submitter_node_id": self.node_id,
            "submit_time": time.time(),
            "priority": priority,
        }

        # Submit the task to the coordinator
        result = self.cluster_coordinator.submit_task(
            task_type=task_type, payload=payload, metadata=task_metadata, timeout=timeout
        )

        if result.get("success", False):
            self.metrics["tasks_processed"] += 1

        return result

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a submitted task.

        Args:
            task_id: ID of the task to check

        Returns:
            Dictionary with task status information
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        return self.cluster_coordinator.get_task_status(task_id)

    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about the cluster.

        This includes information about:
        - All connected nodes and their roles
        - Current master node
        - Overall cluster health
        - Resource utilization
        - Task statistics

        Returns:
            Dictionary with cluster status information
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        # Get member information
        members = self.membership_manager.get_members()

        # Get current master
        master_info = self.cluster_coordinator.get_master_info()

        # Get health status
        health_status = self.cluster_monitor.get_health_status()

        # Get task statistics
        task_stats = self.cluster_coordinator.get_task_statistics()

        # Get resource utilization (from metrics collector)
        resource_utilization = self.metrics_collector.get_latest_metrics() or {}

        # Return comprehensive status
        return {
            "success": True,
            "cluster_id": self.cluster_id,
            "node_id": self.node_id,
            "role": self.role_manager.get_current_role(),
            "is_master": self.cluster_coordinator.is_master,
            "master_node": master_info,
            "members": members,
            "health": health_status,
            "uptime": time.time() - self.metrics["start_time"] if self.metrics["start_time"] else 0,
            "component_status": self.component_status,
            "resource_utilization": resource_utilization,
            "task_statistics": task_stats,
            "metrics": {k: v for k, v in self.metrics.items() if k != "start_time"},
        }

    def get_node_roles(self) -> Dict[str, str]:
        """
        Get the roles of all nodes in the cluster.

        Returns:
            Dictionary mapping node_id to role
        """
        if not self.is_running:
            return {}

        members = self.membership_manager.get_members()
        return {node_id: info.get("role", "unknown") for node_id, info in members.items()}

    def register_task_handler(
        self, task_type: str, handler_func: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> bool:
        """
        Register a handler function for a specific task type.

        Args:
            task_type: Type of task to handle
            handler_func: Function to call when task is received
                         Should accept a payload dict and return a result dict

        Returns:
            Boolean indicating successful registration
        """
        if not self.is_running:
            return False

        return self.cluster_coordinator.register_task_handler(
            task_type=task_type, handler_func=handler_func
        )

    def propose_configuration_change(self, key: str, value: Any) -> Dict[str, Any]:
        """
        Propose a configuration change to the cluster.

        This will initiate a consensus process where nodes vote on the change.
        The change will only be applied if a majority of nodes approve.

        Args:
            key: Configuration key to change
            value: New value to set

        Returns:
            Dictionary with proposal status and ID
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        # Prepare proposal
        proposal = {
            "type": "config_change",
            "key": key,
            "value": value,
            "proposer": self.node_id,
            "timestamp": time.time(),
        }

        # Submit proposal for consensus
        return self.cluster_coordinator.submit_proposal(proposal)

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics about the node and cluster.

        Returns:
            Dictionary with various performance metrics
        """
        if not self.is_running:
            return {"success": False, "error": "Cluster manager is not running"}

        # Get latest metrics from collector
        node_metrics = self.metrics_collector.get_latest_metrics() or {}

        # Get role-specific metrics
        role_metrics = self.role_manager.get_metrics() or {}

        # Combine all metrics
        return {
            "success": True,
            "node_id": self.node_id,
            "role": self.role_manager.get_current_role(),
            "uptime": time.time() - self.metrics["start_time"] if self.metrics["start_time"] else 0,
            "node_metrics": node_metrics,
            "role_metrics": role_metrics,
            "cluster_metrics": self.metrics,
        }

    def get_cluster_metrics(
        self, include_members: bool = True, include_history: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive metrics about the cluster.

        This is a specialized version of get_metrics() that provides additional
        metrics about the cluster as a whole, including membership and historical data.

        Args:
            include_members: Whether to include metrics for all member nodes
            include_history: Whether to include historical metrics (time series)

        Returns:
            Dictionary with various performance metrics
        """
        # First get the base metrics
        result = self.get_metrics()

        try:
            # Include member metrics if requested
            if include_members and hasattr(self, "membership_manager"):
                member_metrics = {}
                members = self.membership_manager.get_members()

                for node_id, member_info in members.items():
                    if node_id == self.node_id:
                        continue  # Skip self, already included

                    # Extract metrics from member info
                    member_metrics[node_id] = {
                        "role": member_info.get("role", "unknown"),
                        "last_seen": member_info.get("last_seen", 0),
                        "status": member_info.get("status", "unknown"),
                        "resources": member_info.get("resources", {}),
                        "capabilities": member_info.get("capabilities", []),
                    }

                result["member_metrics"] = member_metrics

                # Add aggregate statistics across all nodes
                aggregate = {
                    "total_nodes": len(members) + 1,  # Including self
                    "nodes_by_role": {},
                    "total_resources": {
                        "cpu_cores": 0,
                        "memory_gb": 0,
                        "disk_gb": 0,
                        "gpu_count": 0,
                    },
                }

                # Count nodes by role
                roles = set(
                    [member_info.get("role", "unknown") for _, member_info in members.items()]
                )
                roles.add(self.current_role)  # Add self

                for role in roles:
                    count = len(
                        [
                            1
                            for _, member_info in members.items()
                            if member_info.get("role", "unknown") == role
                        ]
                    )
                    if self.current_role == role:
                        count += 1  # Count self
                    aggregate["nodes_by_role"][role] = count

                # Aggregate resources
                for _, member_info in members.items():
                    resources = member_info.get("resources", {})
                    aggregate["total_resources"]["cpu_cores"] += resources.get("cpu_count", 0)
                    aggregate["total_resources"]["memory_gb"] += resources.get(
                        "memory_total", 0
                    ) / (1024 * 1024 * 1024)
                    aggregate["total_resources"]["disk_gb"] += resources.get("disk_total", 0) / (
                        1024 * 1024 * 1024
                    )
                    aggregate["total_resources"]["gpu_count"] += resources.get("gpu_count", 0)

                # Add self resources
                if "node_metrics" in result:
                    aggregate["total_resources"]["cpu_cores"] += result["node_metrics"].get(
                        "cpu_count", 0
                    )
                    aggregate["total_resources"]["memory_gb"] += result["node_metrics"].get(
                        "memory_total", 0
                    ) / (1024 * 1024 * 1024)
                    aggregate["total_resources"]["disk_gb"] += result["node_metrics"].get(
                        "disk_total", 0
                    ) / (1024 * 1024 * 1024)
                    aggregate["total_resources"]["gpu_count"] += result["node_metrics"].get(
                        "gpu_count", 0
                    )

                result["aggregate"] = aggregate

            # Include historical metrics if requested
            if include_history and hasattr(self, "metrics_collector"):
                # Check if we have historical data available
                if hasattr(self.metrics_collector, "get_historical_metrics"):
                    result["historical_metrics"] = self.metrics_collector.get_historical_metrics()
                else:
                    result["historical_metrics"] = {
                        "available": False,
                        "message": "Historical metrics not enabled",
                    }

            # Get task statistics if task coordinator is available
            if hasattr(self, "cluster_coordinator") and self.cluster_coordinator is not None:
                if hasattr(self.cluster_coordinator, "get_task_statistics"):
                    result["task_statistics"] = self.cluster_coordinator.get_task_statistics() or {}

        except Exception as e:
            self.logger.error(f"Error getting cluster metrics: {str(e)}")
            if "errors" not in result:
                result["errors"] = []
            result["errors"].append(str(e))

        return result

    def _management_loop(self):
        """
        Background thread for periodic management tasks.

        This handles:
        - Resource monitoring
        - Role adaptation
        - Heartbeat coordination
        - Configuration synchronization
        """
        while not self.shutdown_event.is_set():
            try:
                # Check if role needs to be adapted
                current_role = self.role_manager.get_current_role()

                # Update resource metrics
                resource_metrics = self._gather_resource_metrics()
                if resource_metrics:
                    self.role_manager.update_resources(resource_metrics)

                # Check for role adaptations
                adaptation_result = self.role_manager.adapt_if_needed()
                if adaptation_result.get("adapted", False):
                    new_role = adaptation_result.get("new_role")
                    if new_role != current_role:
                        logger.info(f"Role changed from {current_role} to {new_role}")
                        self.metrics["role_switches"] += 1

                        # Update components with new role
                        self.membership_manager.update_role(new_role)
                        self.metrics_collector.update_role(new_role)

                        # Update master status if role is now master
                        if new_role == "master" and not self.cluster_coordinator.is_master:
                            self.cluster_coordinator.propose_self_as_master()

                # Update key metrics
                self.metrics["uptime"] = (
                    time.time() - self.metrics["start_time"] if self.metrics["start_time"] else 0
                )

            except Exception as e:
                logger.error(f"Error in cluster management loop: {str(e)}")

            # Sleep with early wake-up support
            self.shutdown_event.wait(timeout=15)  # 15-second management cycle

    def _gather_resource_metrics(self) -> Dict[str, Any]:
        """
        Gather current resource metrics from the system.

        Returns:
            Dictionary with resource metrics
        """
        resources = {}

        try:
            # Try to get resource information using psutil
            import psutil

            # CPU information
            resources["cpu_count"] = psutil.cpu_count(logical=True)
            resources["cpu_percent"] = psutil.cpu_percent(interval=0.1)

            # Memory information
            mem = psutil.virtual_memory()
            resources["memory_total"] = mem.total
            resources["memory_available"] = mem.available
            resources["memory_percent_used"] = mem.percent

            # Disk information
            disk = psutil.disk_usage("/")
            resources["disk_total"] = disk.total
            resources["disk_free"] = disk.free
            resources["disk_percent_used"] = disk.percent

            # Network information
            net_io = psutil.net_io_counters()
            resources["net_bytes_sent"] = net_io.bytes_sent
            resources["net_bytes_recv"] = net_io.bytes_recv

        except ImportError:
            # psutil not available, return empty dict
            pass
        except Exception as e:
            logger.warning(f"Error getting resource metrics: {str(e)}")

        return resources

    def _handle_role_configuration_change(self, role: str, config: Dict[str, Any]):
        """
        Handle role configuration changes.

        Args:
            role: New role that was activated
            config: Role-specific configuration
        """
        logger.info(f"Role configuration changed to {role}")

        # Update components with new configuration
        if role == "master" and not self.cluster_coordinator.is_master:
            # This node is now a master, propose leadership
            self.cluster_coordinator.propose_self_as_master()

        # Update role in membership info
        self.membership_manager.update_role(role)

        # Update metrics collector with new role
        self.metrics_collector.update_role(role)

    def _handle_cluster_discovery(self, cluster_info: Dict[str, Any]):
        """
        Handle discovery of a cluster.

        Args:
            cluster_info: Information about the discovered cluster
        """
        logger.info(f"Discovered cluster: {cluster_info}")

        # Extract master information if available
        if "master_addr" in cluster_info:
            # Join the cluster by connecting to the master
            self.membership_manager.join_cluster(
                master_addr=cluster_info["master_addr"],
                cluster_id=cluster_info.get("cluster_id", self.cluster_id),
            )

    def _handle_membership_change(
        self, change_type: str, node_id: str, node_info: Dict[str, Any]
    ) -> None:
        """
        Handle changes in cluster membership.

        Args:
            change_type: Type of change (join, leave, update)
            node_id: ID of the node that changed
            node_info: Information about the node
        """
        logger.info(f"Membership change: {change_type} for node {node_id}")
        self.metrics["membership_changes"] += 1

        # Notify the cluster coordinator
        self.cluster_coordinator.handle_membership_change(change_type, node_id, node_info)

        # Notify the monitor for health tracking
        self.cluster_monitor.handle_membership_change(change_type, node_id, node_info)

    def _handle_leadership_change(self, master_id: str, is_self: bool) -> None:
        """
        Handle changes in cluster leadership.

        Args:
            master_id: ID of the new master node
            is_self: Whether this node is the new master
        """
        logger.info(f"Leadership changed to node {master_id}")
        self.metrics["leadership_changes"] += 1

        # If this node became master, but role is not master, update role
        if is_self and self.role_manager.get_current_role() != "master":
            self.role_manager.switch_role("master")

    def _handle_alert(self, alert_type: str, alert_data: Dict[str, Any]) -> None:
        """
        Handle alerts from the monitoring system.

        Args:
            alert_type: Type of alert (resource, health, error)
            alert_data: Alert data and context
        """
        self.metrics["alerts_generated"] += 1

        severity = alert_data.get("severity", "info")
        node_id = alert_data.get("node_id", "unknown")

        if severity == "critical":
            logger.critical(
                f"CRITICAL ALERT from {node_id}: {alert_type} - {alert_data.get('message', '')}"
            )
        elif severity == "error":
            logger.error(
                f"ERROR ALERT from {node_id}: {alert_type} - {alert_data.get('message', '')}"
            )
        elif severity == "warning":
            logger.warning(
                f"WARNING ALERT from {node_id}: {alert_type} - {alert_data.get('message', '')}"
            )
        else:
            logger.info(
                f"INFO ALERT from {node_id}: {alert_type} - {alert_data.get('message', '')}"
            )

        # If this is a resource alert for this node, trigger adaptation
        if alert_type == "resource" and node_id == self.node_id:
            self.role_manager.adapt_if_needed(force=True)
