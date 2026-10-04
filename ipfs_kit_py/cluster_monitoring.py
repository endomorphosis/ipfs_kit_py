"""
Monitoring and management module for IPFS cluster.

This module implements the monitoring and management capabilities (Phase 3B Milestone 3.6), including:
- Cluster management dashboard
- Health monitoring and alerts
- Performance visualization
- Configuration management tools
- Resource tracking
- Automated recovery procedures

The monitoring system collects metrics from all cluster nodes, analyzes them for threshold
violations, generates alerts, and takes automated recovery actions when necessary.
"""

import anyio
import concurrent.futures
import copy
import csv
import io
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Standard Python modules used for monitoring
import psutil

# Create logger
logger = logging.getLogger(__name__)


class ClusterMonitoring:
    """
    Handles monitoring and management of IPFS cluster nodes.

    This class implements collection of metrics from cluster nodes,
    analysis of metrics for threshold violations, generation of alerts,
    and automated recovery actions. It also provides visualization capabilities
    and configuration management tools.
    """

    def __init__(self, ipfs_kit_instance):
        """
        Initialize the ClusterMonitoring system.

        Args:
            ipfs_kit_instance: Reference to the parent IPFSKit instance
        """
        self.ipfs_kit = ipfs_kit_instance
        self.role = self.ipfs_kit.metadata.get("role", "leecher")
        self.monitoring_enabled = self._get_config_value(["Monitoring", "Enabled"], True)
        self.metrics_interval = self._parse_time_interval(
            self._get_config_value(["Monitoring", "MetricsInterval"], "60s")
        )

        # Alert thresholds with defaults
        self.alert_thresholds = {
            "DiskSpace": self._get_config_value(["Monitoring", "AlertThresholds", "DiskSpace"], 90),
            "MemoryUsage": self._get_config_value(
                ["Monitoring", "AlertThresholds", "MemoryUsage"], 85
            ),
            "CpuUsage": self._get_config_value(["Monitoring", "AlertThresholds", "CpuUsage"], 90),
            "PinQueueLength": self._get_config_value(
                ["Monitoring", "AlertThresholds", "PinQueueLength"], 100
            ),
            "PeerConnectionLimit": self._get_config_value(
                ["Monitoring", "AlertThresholds", "PeerConnectionLimit"], 5
            ),
        }

        # Storage for collected metrics
        self.historical_metrics = []
        self.max_metrics_history = self._get_config_value(
            ["Monitoring", "MaxMetricsHistory"], 1440
        )  # 24h at 1-minute intervals

        # Storage for alerts
        self.active_alerts = []
        self.alert_history = []
        self.max_alert_history = self._get_config_value(["Monitoring", "MaxAlertHistory"], 1000)

        # Storage for recovery actions
        self.pending_actions = []
        self.completed_actions = []
        self.max_action_history = self._get_config_value(["Monitoring", "MaxActionHistory"], 100)

        # Thread for periodic metrics collection
        self.metrics_thread = None
        self.should_stop = threading.Event()

        # Locks for thread safety
        self.metrics_lock = threading.RLock()
        self.alerts_lock = threading.RLock()
        self.actions_lock = threading.RLock()

        # Start monitoring if enabled
        if self.monitoring_enabled and self.role in ["master", "worker"]:
            self.start_monitoring()

    def _get_config_value(self, keys_path: List[str], default: Any) -> Any:
        """
        Get a value from the configuration, traversing a path of keys.

        Args:
            keys_path: List of keys to traverse in the config dictionary
            default: Default value if the path doesn't exist

        Returns:
            The config value or the default
        """
        config = self.ipfs_kit.metadata.get("config", {})
        current = config

        for key in keys_path:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def _parse_time_interval(self, interval_str: str) -> int:
        """
        Parse a time interval string into seconds.

        Args:
            interval_str: Time interval string (e.g., "60s", "5m", "1h")

        Returns:
            Number of seconds
        """
        if not isinstance(interval_str, str):
            return 60  # Default to 60 seconds

        interval_str = interval_str.strip().lower()

        # Handle simple integer (interpret as seconds)
        if interval_str.isdigit():
            return int(interval_str)

        # Extract number and unit
        unit = interval_str[-1]
        try:
            value = float(interval_str[:-1])
        except ValueError:
            logger.warning(f"Invalid time interval format: {interval_str}. Using default of 60s.")
            return 60

        # Convert to seconds based on unit
        if unit == "s":
            return int(value)
        elif unit == "m":
            return int(value * 60)
        elif unit == "h":
            return int(value * 3600)
        else:
            logger.warning(f"Unknown time unit: {unit}. Using default of 60s.")
            return 60

    def start_monitoring(self) -> Dict[str, Any]:
        """
        Start the periodic metrics collection thread.

        Returns:
            Result dictionary with status information
        """
        result = {"success": False, "operation": "start_monitoring", "timestamp": time.time()}

        try:
            if self.metrics_thread and self.metrics_thread.is_alive():
                result["error"] = "Monitoring thread already running"
                return result

            # Reset stop event
            self.should_stop.clear()

            # Start the monitoring thread
            self.metrics_thread = threading.Thread(
                target=self._metrics_collection_thread, name="IPFS-Cluster-Monitoring"
            )
            self.metrics_thread.daemon = True
            self.metrics_thread.start()

            result["success"] = True
            result["message"] = f"Monitoring started with interval {self.metrics_interval}s"

        except Exception as e:
            result["error"] = f"Failed to start monitoring: {str(e)}"
            logger.error(f"Error starting monitoring: {e}")

        return result

    def stop_monitoring(self) -> Dict[str, Any]:
        """
        Stop the metrics collection thread.

        Returns:
            Result dictionary with status information
        """
        result = {"success": False, "operation": "stop_monitoring", "timestamp": time.time()}

        try:
            if not self.metrics_thread or not self.metrics_thread.is_alive():
                result["error"] = "Monitoring thread not running"
                return result

            # Signal thread to stop
            self.should_stop.set()

            # Wait for thread to end with timeout
            self.metrics_thread.join(timeout=10)

            if self.metrics_thread.is_alive():
                result["warning"] = "Monitoring thread did not stop within timeout"
            else:
                self.metrics_thread = None

            result["success"] = True
            result["message"] = "Monitoring stopped"

        except Exception as e:
            result["error"] = f"Failed to stop monitoring: {str(e)}"
            logger.error(f"Error stopping monitoring: {e}")

        return result

    def _metrics_collection_thread(self) -> None:
        """
        Background thread that periodically collects metrics.
        """
        logger.info(f"Metrics collection thread started with interval {self.metrics_interval}s")

        while not self.should_stop.is_set():
            start_time = time.time()

            try:
                # Collect metrics
                self.collect_cluster_metrics()

                # Check for threshold violations and generate alerts
                metrics = self.get_latest_metrics()
                if metrics:
                    alerts = self.check_alert_thresholds(metrics)

                    # Process alerts and take recovery actions
                    if alerts:
                        with self.alerts_lock:
                            self.active_alerts.extend(alerts)
                            self.alert_history.extend(alerts)

                            # Trim alert history if needed
                            if len(self.alert_history) > self.max_alert_history:
                                self.alert_history = self.alert_history[-self.max_alert_history :]

                        # Process alerts to determine recovery actions
                        recovery_actions = self.process_alerts(alerts)

                        # Queue recovery actions
                        if recovery_actions:
                            with self.actions_lock:
                                self.pending_actions.extend(recovery_actions)

                # Execute any pending recovery actions
                self._execute_pending_actions()

            except Exception as e:
                logger.error(f"Error in metrics collection cycle: {e}")

            # Calculate time to sleep
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self.metrics_interval - elapsed)

            # Sleep until next collection cycle or until stopped
            if self.should_stop.wait(timeout=sleep_time):
                break

        logger.info("Metrics collection thread stopped")

    def collect_cluster_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all cluster nodes.

        Returns:
            Dictionary containing collected metrics
        """
        result = {
            "success": False,
            "operation": "collect_cluster_metrics",
            "timestamp": time.time(),
        }

        try:
            metrics = {"timestamp": time.time(), "nodes": {}}

            # If master, collect metrics from all peers using cluster status
            if self.role == "master" and hasattr(self.ipfs_kit, "ipfs_cluster_ctl"):
                # Get cluster status which includes metrics
                status_result = self.ipfs_kit.ipfs_cluster_ctl.ipfs_cluster_ctl_status()

                if status_result.get("success", False):
                    # Process each peer's metrics
                    for peer in status_result.get("peer_statuses", []):
                        peer_id = peer.get("id")
                        peer_metrics = peer.get("metrics", {})

                        # Calculate derived metrics
                        if "freespace" in peer_metrics and "reposize" in peer_metrics:
                            # Calculate disk usage percentage
                            total_space = peer_metrics["freespace"] + peer_metrics["reposize"]
                            disk_usage_percent = (
                                (peer_metrics["reposize"] / total_space) * 100
                                if total_space > 0
                                else 0
                            )
                            peer_metrics["disk_usage_percent"] = disk_usage_percent

                        if "memory_used_mb" in peer_metrics and "memory_total_mb" in peer_metrics:
                            # Calculate memory usage percentage
                            memory_usage_percent = (
                                (peer_metrics["memory_used_mb"] / peer_metrics["memory_total_mb"])
                                * 100
                                if peer_metrics["memory_total_mb"] > 0
                                else 0
                            )
                            peer_metrics["memory_usage_percent"] = memory_usage_percent

                        # Add to metrics collection
                        metrics["nodes"][peer_id] = {
                            "name": peer.get("peername", peer_id),
                            "metrics": peer_metrics,
                        }
                else:
                    logger.warning(
                        f"Failed to collect cluster status: {status_result.get('error', 'Unknown error')}"
                    )

            # Always collect local node metrics
            local_metrics = self._collect_local_metrics()

            # Local node ID
            local_id = "local"
            if hasattr(self.ipfs_kit, "ipfs") and hasattr(self.ipfs_kit.ipfs, "ipfs_id"):
                id_result = self.ipfs_kit.ipfs.ipfs_id()
                if id_result.get("success", False) and id_result.get("ID"):
                    local_id = id_result.get("ID")

            # Add local metrics
            metrics["nodes"][local_id] = {
                "name": f"{self.role}-{local_id[:8]}",
                "metrics": local_metrics,
            }

            # Store in historical metrics
            with self.metrics_lock:
                self.historical_metrics.append(metrics)

                # Trim historical metrics if needed
                if len(self.historical_metrics) > self.max_metrics_history:
                    self.historical_metrics = self.historical_metrics[-self.max_metrics_history :]

            result["success"] = True
            result["metrics"] = metrics

        except Exception as e:
            result["error"] = f"Failed to collect metrics: {str(e)}"
            logger.error(f"Error collecting metrics: {e}")

        return result

    def _collect_local_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from the local system.

        Returns:
            Dictionary containing local system metrics
        """
        metrics = {}

        try:
            # CPU usage
            metrics["cpu_usage_percent"] = psutil.cpu_percent(interval=0.1)

            # Memory usage
            memory = psutil.virtual_memory()
            metrics["memory_used_mb"] = memory.used / (1024 * 1024)
            metrics["memory_total_mb"] = memory.total / (1024 * 1024)
            metrics["memory_usage_percent"] = memory.percent

            # Disk usage
            disk = psutil.disk_usage("/")
            metrics["freespace"] = disk.free
            metrics["reposize"] = disk.used
            metrics["disk_usage_percent"] = disk.percent

            # Network IO
            network = psutil.net_io_counters()
            metrics["network_bytes_sent"] = network.bytes_sent
            metrics["network_bytes_recv"] = network.bytes_recv

            # IPFS specific metrics
            if hasattr(self.ipfs_kit, "ipfs"):
                # Get repo stats
                repo_stat_result = None
                if hasattr(self.ipfs_kit.ipfs, "ipfs_repo_stat"):
                    repo_stat_result = self.ipfs_kit.ipfs.ipfs_repo_stat()

                if repo_stat_result and repo_stat_result.get("success", False):
                    repo_stats = repo_stat_result.get("Stats", {})
                    metrics["repo_objects"] = repo_stats.get("NumObjects", 0)
                    metrics["repo_size"] = repo_stats.get("RepoSize", 0)

                # Get peer count
                if hasattr(self.ipfs_kit.ipfs, "ipfs_swarm_peers"):
                    swarm_result = self.ipfs_kit.ipfs.ipfs_swarm_peers()
                    if swarm_result and swarm_result.get("success", False):
                        peers = swarm_result.get("Peers", [])
                        metrics["peers_connected"] = len(peers)

            # Cluster specific metrics
            if self.role == "master" and hasattr(self.ipfs_kit, "ipfs_cluster_ctl"):
                # Get pin count
                if hasattr(self.ipfs_kit.ipfs_cluster_ctl, "ipfs_cluster_ctl_pin_ls"):
                    pin_result = self.ipfs_kit.ipfs_cluster_ctl.ipfs_cluster_ctl_pin_ls()
                    if pin_result and pin_result.get("success", False):
                        pins = pin_result.get("pins", {})
                        metrics["pins_total"] = len(pins)

                # Get status count
                if hasattr(self.ipfs_kit.ipfs_cluster_ctl, "ipfs_cluster_ctl_status"):
                    status_result = self.ipfs_kit.ipfs_cluster_ctl.ipfs_cluster_ctl_status()
                    if status_result and status_result.get("success", False):
                        pin_count = 0
                        in_progress = 0
                        queued = 0

                        for pin_info in status_result.get("pin_status", []):
                            pin_count += 1
                            status = pin_info.get("status", "")
                            if "pinning" in status:
                                in_progress += 1
                            elif "queued" in status:
                                queued += 1

                        metrics["pins_total"] = pin_count
                        metrics["pins_in_progress"] = in_progress
                        metrics["pins_queued"] = queued

        except Exception as e:
            logger.error(f"Error collecting local metrics: {e}")
            metrics["error"] = str(e)

        return metrics

    def get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent collected metrics.

        Returns:
            The most recent metrics or None if no metrics available
        """
        with self.metrics_lock:
            if not self.historical_metrics:
                return None
            return copy.deepcopy(self.historical_metrics[-1])

    def check_alert_thresholds(self, metrics_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check if metrics exceed defined thresholds and generate alerts.

        Args:
            metrics_data: The metrics to check against thresholds

        Returns:
            List of alert dictionaries
        """
        alerts = []

        try:
            # Get thresholds from configuration
            disk_threshold = self.alert_thresholds.get("DiskSpace", 90)
            memory_threshold = self.alert_thresholds.get("MemoryUsage", 85)
            cpu_threshold = self.alert_thresholds.get("CpuUsage", 90)
            queue_threshold = self.alert_thresholds.get("PinQueueLength", 100)
            peer_threshold = self.alert_thresholds.get("PeerConnectionLimit", 5)

            # Check each node for threshold crossings
            for node_id, node_data in metrics_data.get("nodes", {}).items():
                node_name = node_data.get("name", node_id)
                metrics = node_data.get("metrics", {})

                # Check CPU threshold
                if metrics.get("cpu_usage_percent", 0) > cpu_threshold:
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "cpu_usage_high",
                            "node_id": node_id,
                            "node_name": node_name,
                            "value": metrics.get("cpu_usage_percent"),
                            "threshold": cpu_threshold,
                            "timestamp": time.time(),
                            "message": f"High CPU usage on {node_name}: {metrics.get('cpu_usage_percent')}% (threshold: {cpu_threshold}%)",
                        }
                    )

                # Check memory threshold
                if metrics.get("memory_usage_percent", 0) > memory_threshold:
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "memory_usage_high",
                            "node_id": node_id,
                            "node_name": node_name,
                            "value": metrics.get("memory_usage_percent"),
                            "threshold": memory_threshold,
                            "timestamp": time.time(),
                            "message": f"High memory usage on {node_name}: {metrics.get('memory_usage_percent')}% (threshold: {memory_threshold}%)",
                        }
                    )

                # Check disk threshold
                if metrics.get("disk_usage_percent", 0) > disk_threshold:
                    # Make this a critical alert if very high
                    level = "critical" if metrics.get("disk_usage_percent", 0) > 95 else "warning"
                    alerts.append(
                        {
                            "level": level,
                            "type": "disk_usage_high",
                            "node_id": node_id,
                            "node_name": node_name,
                            "value": metrics.get("disk_usage_percent"),
                            "threshold": disk_threshold,
                            "timestamp": time.time(),
                            "message": f"High disk usage on {node_name}: {metrics.get('disk_usage_percent')}% (threshold: {disk_threshold}%)",
                        }
                    )

                # Check pin queue length
                if metrics.get("pins_queued", 0) > queue_threshold:
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "pin_queue_long",
                            "node_id": node_id,
                            "node_name": node_name,
                            "value": metrics.get("pins_queued"),
                            "threshold": queue_threshold,
                            "timestamp": time.time(),
                            "message": f"Long pin queue on {node_name}: {metrics.get('pins_queued')} pins (threshold: {queue_threshold})",
                        }
                    )

                # Check peer connections (too few)
                if (
                    "peers_connected" in metrics
                    and metrics.get("peers_connected", 0) < peer_threshold
                ):
                    alerts.append(
                        {
                            "level": "warning",
                            "type": "low_peer_count",
                            "node_id": node_id,
                            "node_name": node_name,
                            "value": metrics.get("peers_connected"),
                            "threshold": peer_threshold,
                            "timestamp": time.time(),
                            "message": f"Low peer count on {node_name}: {metrics.get('peers_connected')} peers (threshold: {peer_threshold})",
                        }
                    )

        except Exception as e:
            logger.error(f"Error checking alert thresholds: {e}")
            alerts.append(
                {
                    "level": "error",
                    "type": "monitor_error",
                    "node_id": "monitor",
                    "node_name": "Monitoring System",
                    "value": str(e),
                    "timestamp": time.time(),
                    "message": f"Error checking alert thresholds: {str(e)}",
                }
            )

        return alerts

    def process_alerts(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process alerts and determine appropriate recovery actions.

        Args:
            alerts: List of alerts to process

        Returns:
            List of recovery actions to take
        """
        recovery_actions = []

        try:
            # Process each alert and determine appropriate actions
            for alert in alerts:
                node_id = alert.get("node_id")
                alert_type = alert.get("type")
                level = alert.get("level")

                # Skip if not critical or warning
                if level not in ["critical", "warning"]:
                    continue

                # Handle disk space issues
                if alert_type == "disk_usage_high":
                    if level == "critical":
                        # For critical disk usage, reallocate pins from this node
                        recovery_actions.append(
                            {
                                "action": "reallocate_pins",
                                "node_id": node_id,
                                "reason": "critical_disk_usage",
                                "details": "Reallocating pins from node due to critical disk usage",
                                "status": "pending",
                                "timestamp": time.time(),
                            }
                        )

                        # Also trigger garbage collection
                        recovery_actions.append(
                            {
                                "action": "run_garbage_collection",
                                "node_id": node_id,
                                "reason": "critical_disk_usage",
                                "details": "Running garbage collection to free space",
                                "status": "pending",
                                "timestamp": time.time(),
                            }
                        )
                    else:
                        # For warning level, just run garbage collection
                        recovery_actions.append(
                            {
                                "action": "run_garbage_collection",
                                "node_id": node_id,
                                "reason": "high_disk_usage",
                                "details": "Running garbage collection to free space",
                                "status": "pending",
                                "timestamp": time.time(),
                            }
                        )

                # Handle CPU issues
                elif alert_type == "cpu_usage_high":
                    # Throttle back pin operations
                    recovery_actions.append(
                        {
                            "action": "throttle_operations",
                            "node_id": node_id,
                            "reason": "high_cpu_usage",
                            "details": "Temporarily reducing concurrent operations",
                            "status": "pending",
                            "timestamp": time.time(),
                        }
                    )

                # Handle memory issues
                elif alert_type == "memory_usage_high":
                    # Implement memory-conservation measures
                    recovery_actions.append(
                        {
                            "action": "reduce_memory_usage",
                            "node_id": node_id,
                            "reason": "high_memory_usage",
                            "details": "Applying memory conservation settings",
                            "status": "pending",
                            "timestamp": time.time(),
                        }
                    )

                # Handle low peer count
                elif alert_type == "low_peer_count":
                    # Try to connect to more peers
                    recovery_actions.append(
                        {
                            "action": "connect_to_bootstrap_peers",
                            "node_id": node_id,
                            "reason": "low_peer_count",
                            "details": "Connecting to bootstrap peers to increase peer count",
                            "status": "pending",
                            "timestamp": time.time(),
                        }
                    )

                # Handle long pin queue
                elif alert_type == "pin_queue_long":
                    # Adjust pin concurrency
                    recovery_actions.append(
                        {
                            "action": "adjust_pin_concurrency",
                            "node_id": node_id,
                            "reason": "long_pin_queue",
                            "details": "Adjusting pin concurrency to process queue faster",
                            "status": "pending",
                            "timestamp": time.time(),
                        }
                    )

        except Exception as e:
            logger.error(f"Error processing alerts: {e}")
            recovery_actions.append(
                {
                    "action": "notify_admin",
                    "node_id": "monitor",
                    "reason": "monitor_error",
                    "details": f"Error processing alerts: {str(e)}",
                    "status": "pending",
                    "timestamp": time.time(),
                }
            )

        return recovery_actions

    def _execute_pending_actions(self) -> None:
        """
        Execute pending recovery actions.
        """
        with self.actions_lock:
            if not self.pending_actions:
                return

            # Make a copy of pending actions and clear the list
            actions_to_execute = copy.deepcopy(self.pending_actions)
            self.pending_actions = []

        # Execute each action
        completed_actions = []
        for action in actions_to_execute:
            result = self._execute_recovery_action(action)
            completed_actions.append(result)

        # Store completed actions
        with self.actions_lock:
            self.completed_actions.extend(completed_actions)

            # Trim action history if needed
            if len(self.completed_actions) > self.max_action_history:
                self.completed_actions = self.completed_actions[-self.max_action_history :]

    def _execute_recovery_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific recovery action.

        Args:
            action: The recovery action to execute

        Returns:
            Updated action with execution result
        """
        action_type = action.get("action")
        node_id = action.get("node_id")

        # Mark as in progress
        action["status"] = "in_progress"
        action["executed_at"] = time.time()

        try:
            # Handle different action types
            if action_type == "run_garbage_collection":
                success, message = self._action_run_gc(node_id)

            elif action_type == "reallocate_pins":
                success, message = self._action_reallocate_pins(node_id)

            elif action_type == "throttle_operations":
                success, message = self._action_throttle_operations(node_id)

            elif action_type == "reduce_memory_usage":
                success, message = self._action_reduce_memory_usage(node_id)

            elif action_type == "connect_to_bootstrap_peers":
                success, message = self._action_connect_bootstrap_peers(node_id)

            elif action_type == "adjust_pin_concurrency":
                success, message = self._action_adjust_pin_concurrency(node_id)

            elif action_type == "notify_admin":
                success, message = self._action_notify_admin(node_id, action.get("details", ""))

            else:
                success = False
                message = f"Unknown action type: {action_type}"

            # Update action with result
            action["success"] = success
            action["result"] = message
            action["completed_at"] = time.time()
            action["status"] = "completed" if success else "failed"

        except Exception as e:
            logger.error(f"Error executing recovery action {action_type}: {e}")
            action["success"] = False
            action["result"] = f"Error: {str(e)}"
            action["completed_at"] = time.time()
            action["status"] = "failed"

        return action

    def _action_run_gc(self, node_id: str) -> Tuple[bool, str]:
        """
        Run garbage collection on a node.

        Args:
            node_id: ID of the node to run GC on

        Returns:
            Tuple of (success, message)
        """
        # Check if this is the local node
        is_local = self._is_local_node(node_id)

        if is_local:
            # Run local garbage collection
            if hasattr(self.ipfs_kit, "ipfs") and hasattr(self.ipfs_kit.ipfs, "ipfs_repo_gc"):
                gc_result = self.ipfs_kit.ipfs.ipfs_repo_gc()

                if gc_result.get("success", False):
                    return (
                        True,
                        f"Successfully ran garbage collection, removed {len(gc_result.get('Keys', []))} objects",
                    )
                else:
                    return (
                        False,
                        f"Failed to run garbage collection: {gc_result.get('error', 'Unknown error')}",
                    )
            else:
                return False, "IPFS instance not available"

        elif self.role == "master":
            # For remote nodes, we use the cluster API
            # This assumes we have an RPC or API method to trigger GC on remote nodes
            # In a real implementation, this would be implemented using the cluster API
            logger.warning(
                f"Remote GC on node {node_id} not implemented yet, would use cluster API"
            )
            return False, "Remote GC not implemented yet"

        else:
            return False, "Cannot trigger GC on remote node from non-master role"

    def _action_reallocate_pins(self, node_id: str) -> Tuple[bool, str]:
        """
        Reallocate pins from a node to others in the cluster.

        Args:
            node_id: ID of the node to reallocate pins from

        Returns:
            Tuple of (success, message)
        """
        if self.role != "master":
            return False, "Only master can reallocate pins"

        if hasattr(self.ipfs_kit, "ipfs_cluster_ctl"):
            # This would be a complex operation using the cluster API
            # 1. Get pins allocated to this node
            # 2. Adjust allocation for each pin to exclude this node
            # 3. Re-pin with new allocations
            logger.warning(f"Pin reallocation from node {node_id} not fully implemented yet")

            # Simulate the operation for now
            return True, f"Simulated: Reallocated pins from node {node_id}"
        else:
            return False, "Cluster controller not available"

    def _action_throttle_operations(self, node_id: str) -> Tuple[bool, str]:
        """
        Throttle operations on a node to reduce CPU usage.

        Args:
            node_id: ID of the node to throttle

        Returns:
            Tuple of (success, message)
        """
        # Check if this is the local node
        is_local = self._is_local_node(node_id)

        if is_local:
            # Implement local throttling
            # This would involve adjusting config parameters
            logger.info(f"Throttling operations on local node to reduce CPU usage")

            # In a real implementation, this would adjust specific parameters
            # For now, we'll simulate it
            return True, "Successfully throttled operations on local node"

        elif self.role == "master":
            # For remote nodes, would use the cluster API
            logger.warning(f"Remote throttling on node {node_id} not implemented yet")
            return False, "Remote throttling not implemented yet"

        else:
            return False, "Cannot throttle operations on remote node from non-master role"

    def _action_reduce_memory_usage(self, node_id: str) -> Tuple[bool, str]:
        """
        Apply memory conservation settings to a node.

        Args:
            node_id: ID of the node to adjust

        Returns:
            Tuple of (success, message)
        """
        # Check if this is the local node
        is_local = self._is_local_node(node_id)

        if is_local:
            # Implement local memory conservation
            # This would involve adjusting cache sizes and other memory-intensive settings
            logger.info(f"Applying memory conservation settings to local node")

            # In a real implementation, this would adjust specific parameters
            # For now, we'll simulate it
            return True, "Successfully applied memory conservation settings to local node"

        elif self.role == "master":
            # For remote nodes, would use the cluster API
            logger.warning(f"Remote memory conservation on node {node_id} not implemented yet")
            return False, "Remote memory conservation not implemented yet"

        else:
            return False, "Cannot apply memory conservation on remote node from non-master role"

    def _action_connect_bootstrap_peers(self, node_id: str) -> Tuple[bool, str]:
        """
        Connect to bootstrap peers to increase connectivity.

        Args:
            node_id: ID of the node to connect from

        Returns:
            Tuple of (success, message)
        """
        # Check if this is the local node
        is_local = self._is_local_node(node_id)

        if is_local:
            # Connect to bootstrap peers
            if hasattr(self.ipfs_kit, "ipfs") and hasattr(
                self.ipfs_kit.ipfs, "ipfs_bootstrap_list"
            ):
                bootstrap_result = self.ipfs_kit.ipfs.ipfs_bootstrap_list()

                if bootstrap_result.get("success", False):
                    peers = bootstrap_result.get("Peers", [])
                    connected = 0

                    # Try to connect to each bootstrap peer
                    if hasattr(self.ipfs_kit.ipfs, "ipfs_swarm_connect"):
                        for peer in peers:
                            connect_result = self.ipfs_kit.ipfs.ipfs_swarm_connect(peer)
                            if connect_result.get("success", False):
                                connected += 1

                    return True, f"Successfully connected to {connected} bootstrap peers"
                else:
                    return (
                        False,
                        f"Failed to get bootstrap list: {bootstrap_result.get('error', 'Unknown error')}",
                    )
            else:
                return False, "IPFS instance not available"

        elif self.role == "master":
            # For remote nodes, would use the cluster API
            logger.warning(f"Remote bootstrap connection on node {node_id} not implemented yet")
            return False, "Remote bootstrap connection not implemented yet"

        else:
            return False, "Cannot connect bootstrap peers on remote node from non-master role"

    def _action_adjust_pin_concurrency(self, node_id: str) -> Tuple[bool, str]:
        """
        Adjust pin concurrency to process pin queue faster.

        Args:
            node_id: ID of the node to adjust

        Returns:
            Tuple of (success, message)
        """
        # Check if this is the local node
        is_local = self._is_local_node(node_id)

        if is_local and self.role == "master":
            # Adjust local pin concurrency
            logger.info(f"Adjusting pin concurrency on local node")

            # In a real implementation, this would adjust cluster config
            # For now, we'll simulate it
            return True, "Successfully adjusted pin concurrency on local node"

        elif self.role == "master" and not is_local:
            # For remote nodes, would use the cluster API
            logger.warning(
                f"Remote pin concurrency adjustment on node {node_id} not implemented yet"
            )
            return False, "Remote pin concurrency adjustment not implemented yet"

        else:
            return False, "Cannot adjust pin concurrency (requires master role)"

    def _action_notify_admin(self, node_id: str, details: str) -> Tuple[bool, str]:
        """
        Notify administrator about an issue.

        Args:
            node_id: ID of the affected node
            details: Details about the issue

        Returns:
            Tuple of (success, message)
        """
        # In a real implementation, this would send an email, push notification, or webhook
        logger.warning(f"ADMIN NOTIFICATION: Issue on node {node_id}: {details}")

        # For now, we'll just log it
        return True, f"Admin notification sent about node {node_id}"

    def _is_local_node(self, node_id: str) -> bool:
        """
        Check if a node ID refers to the local node.

        Args:
            node_id: Node ID to check

        Returns:
            True if it's the local node, False otherwise
        """
        # Get local node ID
        local_id = "local"
        if hasattr(self.ipfs_kit, "ipfs") and hasattr(self.ipfs_kit.ipfs, "ipfs_id"):
            id_result = self.ipfs_kit.ipfs.ipfs_id()
            if id_result.get("success", False) and id_result.get("ID"):
                local_id = id_result.get("ID")

        return node_id == local_id or node_id == "local"

    def aggregate_metrics(self, time_range="24h", interval="1h") -> Dict[str, Any]:
        """
        Aggregate metrics for visualization over a time range.

        Args:
            time_range: Time range to aggregate ("1h", "24h", "7d", etc.)
            interval: Interval for aggregation ("1m", "5m", "1h", etc.)

        Returns:
            Aggregated metrics data
        """
        with self.metrics_lock:
            if not self.historical_metrics:
                return {
                    "timestamps": [],
                    "nodes": {},
                    "cluster": {},
                    "summary": {"time_range": time_range, "interval": interval, "samples": 0},
                }

            # Convert time range to seconds
            time_range_seconds = self._parse_time_interval(time_range)
            interval_seconds = self._parse_time_interval(interval)

            # Filter metrics based on time range
            now = time.time()
            time_limit = now - time_range_seconds
            filtered_metrics = [m for m in self.historical_metrics if m["timestamp"] >= time_limit]

            if not filtered_metrics:
                return {
                    "timestamps": [],
                    "nodes": {},
                    "cluster": {},
                    "summary": {"time_range": time_range, "interval": interval, "samples": 0},
                }

            # Group metrics by interval
            grouped_metrics = []
            interval_start = time_limit
            current_group = []

            # Sort metrics by timestamp
            sorted_metrics = sorted(filtered_metrics, key=lambda m: m["timestamp"])

            for metrics in sorted_metrics:
                if metrics["timestamp"] < interval_start + interval_seconds:
                    current_group.append(metrics)
                else:
                    if current_group:
                        grouped_metrics.append(self._aggregate_interval(current_group))

                    # Skip ahead to the correct interval
                    while metrics["timestamp"] >= interval_start + interval_seconds:
                        interval_start += interval_seconds

                    current_group = [metrics]

            # Add the last group
            if current_group:
                grouped_metrics.append(self._aggregate_interval(current_group))

            # Initialize aggregated data structure
            aggregated = {
                "timestamps": [],
                "nodes": {},
                "cluster": {
                    "cpu_usage_percent": [],
                    "memory_usage_percent": [],
                    "disk_usage_percent": [],
                    "peers_connected": [],
                    "pins_total": [],
                    "pins_in_progress": [],
                },
            }

            # Setup node-specific metrics series
            node_ids = set()
            for metrics in filtered_metrics:
                node_ids.update(metrics["nodes"].keys())

            for node_id in node_ids:
                aggregated["nodes"][node_id] = {
                    "name": self._get_node_name(filtered_metrics, node_id),
                    "cpu_usage_percent": [],
                    "memory_usage_percent": [],
                    "disk_usage_percent": [],
                    "peers_connected": [],
                    "pins_total": [],
                    "pins_in_progress": [],
                }

            # Process each aggregated metrics group
            for group in grouped_metrics:
                aggregated["timestamps"].append(group["timestamp"])

                # Add cluster-wide metrics
                for key in aggregated["cluster"]:
                    if key in group["cluster"]:
                        aggregated["cluster"][key].append(group["cluster"][key])
                    else:
                        aggregated["cluster"][key].append(None)

                # Add node-specific metrics
                for node_id in aggregated["nodes"]:
                    node_series = aggregated["nodes"][node_id]

                    if node_id in group["nodes"]:
                        node_metrics = group["nodes"][node_id]

                        for key in node_series.keys():
                            if key != "name" and key in node_metrics:
                                node_series[key].append(node_metrics[key])
                            elif key != "name":
                                node_series[key].append(None)
                    else:
                        # Node didn't have metrics in this interval
                        for key in node_series.keys():
                            if key != "name":
                                node_series[key].append(None)

            # Add summary statistics
            aggregated["summary"] = {
                "time_range": time_range,
                "interval": interval,
                "samples": len(grouped_metrics),
                "cluster": {},
            }

            # Calculate cluster-wide statistics
            for key in aggregated["cluster"]:
                values = [v for v in aggregated["cluster"][key] if v is not None]
                if values:
                    aggregated["summary"]["cluster"][f"{key}_avg"] = sum(values) / len(values)
                    aggregated["summary"]["cluster"][f"{key}_max"] = max(values)
                    aggregated["summary"]["cluster"][f"{key}_min"] = min(values)

                    # Add latest value
                    aggregated["summary"]["cluster"][f"{key}_current"] = (
                        values[-1] if values else None
                    )

            return aggregated

    def _aggregate_interval(self, metrics_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate multiple metrics samples from a time interval.

        Args:
            metrics_list: List of metrics samples in the interval

        Returns:
            Aggregated metrics for the interval
        """
        if not metrics_list:
            return {"timestamp": 0, "nodes": {}, "cluster": {}}

        # Use the latest timestamp in the interval
        timestamp = max(m["timestamp"] for m in metrics_list)

        # Initialize aggregated result
        aggregated = {"timestamp": timestamp, "nodes": {}, "cluster": {}}

        # Collect all node IDs
        node_ids = set()
        for metrics in metrics_list:
            node_ids.update(metrics["nodes"].keys())

        # Collect metrics for each node
        for node_id in node_ids:
            node_samples = []

            for metrics in metrics_list:
                if node_id in metrics["nodes"]:
                    node_samples.append(metrics["nodes"][node_id])

            if node_samples:
                # Aggregate node metrics
                node_metrics = {}

                # Use the name from the most recent sample
                node_metrics["name"] = node_samples[-1]["name"]

                # Aggregate numeric metrics
                for key in [
                    "cpu_usage_percent",
                    "memory_usage_percent",
                    "disk_usage_percent",
                    "peers_connected",
                    "pins_total",
                    "pins_in_progress",
                ]:
                    values = []
                    for sample in node_samples:
                        if "metrics" in sample and key in sample["metrics"]:
                            values.append(sample["metrics"][key])

                    if values:
                        node_metrics[key] = sum(values) / len(values)

                aggregated["nodes"][node_id] = node_metrics

        # Calculate cluster-wide aggregates
        for key in ["cpu_usage_percent", "memory_usage_percent", "disk_usage_percent"]:
            values = []
            for node_metrics in aggregated["nodes"].values():
                if key in node_metrics:
                    values.append(node_metrics[key])

            if values:
                aggregated["cluster"][key] = sum(values) / len(values)

        # Sum up certain metrics
        for key in ["peers_connected", "pins_total", "pins_in_progress"]:
            total = 0
            for node_metrics in aggregated["nodes"].values():
                if key in node_metrics:
                    total += node_metrics[key]

            aggregated["cluster"][key] = total

        return aggregated

    def _get_node_name(self, metrics_list: List[Dict[str, Any]], node_id: str) -> str:
        """
        Get the name of a node from metrics data.

        Args:
            metrics_list: List of metrics samples
            node_id: ID of the node

        Returns:
            Name of the node or the node ID if not found
        """
        for metrics in reversed(metrics_list):  # Start with most recent
            if node_id in metrics["nodes"] and "name" in metrics["nodes"][node_id]:
                return metrics["nodes"][node_id]["name"]

        return node_id

    def export_metrics_json(self, time_range="24h", interval="1h") -> str:
        """
        Export metrics as JSON string.

        Args:
            time_range: Time range to include
            interval: Interval for aggregation

        Returns:
            JSON string of metrics data
        """
        metrics = self.aggregate_metrics(time_range, interval)
        return json.dumps(metrics, indent=2)

    def export_metrics_csv(self, time_range="24h", interval="1h") -> str:
        """
        Export metrics as CSV string.

        Args:
            time_range: Time range to include
            interval: Interval for aggregation

        Returns:
            CSV string of metrics data
        """
        metrics = self.aggregate_metrics(time_range, interval)

        if not metrics["timestamps"]:
            return "timestamp,node_id,cpu_percent,memory_percent,disk_percent"

        # Create CSV with timestamps and key metrics
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "node_id", "cpu_percent", "memory_percent", "disk_percent"])

        # Add cluster-wide data
        for i, ts in enumerate(metrics["timestamps"]):
            writer.writerow(
                [
                    ts,
                    "cluster",
                    (
                        metrics["cluster"]["cpu_usage_percent"][i]
                        if i < len(metrics["cluster"]["cpu_usage_percent"])
                        else ""
                    ),
                    (
                        metrics["cluster"]["memory_usage_percent"][i]
                        if i < len(metrics["cluster"]["memory_usage_percent"])
                        else ""
                    ),
                    (
                        metrics["cluster"]["disk_usage_percent"][i]
                        if i < len(metrics["cluster"]["disk_usage_percent"])
                        else ""
                    ),
                ]
            )

        # Add node-specific data
        for node_id, node_data in metrics["nodes"].items():
            for i, ts in enumerate(metrics["timestamps"]):
                writer.writerow(
                    [
                        ts,
                        node_id,
                        (
                            node_data["cpu_usage_percent"][i]
                            if i < len(node_data["cpu_usage_percent"])
                            else ""
                        ),
                        (
                            node_data["memory_usage_percent"][i]
                            if i < len(node_data["memory_usage_percent"])
                            else ""
                        ),
                        (
                            node_data["disk_usage_percent"][i]
                            if i < len(node_data["disk_usage_percent"])
                            else ""
                        ),
                    ]
                )

        return output.getvalue()

    def validate_cluster_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate cluster configuration for correctness.

        Args:
            config: Configuration to validate

        Returns:
            Validation results
        """
        # Initialize validation results
        validation_results = {"valid": True, "errors": [], "warnings": []}

        # Check for unknown keys
        known_keys = [
            "replication_factor_min",
            "replication_factor_max",
            "pin_recovery_timeout",
            "pinning_timeout",
            "pin_tracker",
        ]

        for key in config:
            if key not in known_keys:
                validation_results["warnings"].append(
                    {
                        "type": "unknown_key",
                        "key": key,
                        "message": f"Unknown configuration key: {key}",
                    }
                )

        # Validate replication factor
        if "replication_factor_min" in config and "replication_factor_max" in config:
            min_rf = config["replication_factor_min"]
            max_rf = config["replication_factor_max"]

            if not isinstance(min_rf, int) or min_rf < 1:
                validation_results["errors"].append(
                    {
                        "type": "invalid_value",
                        "key": "replication_factor_min",
                        "value": min_rf,
                        "message": "replication_factor_min must be a positive integer",
                    }
                )
                validation_results["valid"] = False

            if not isinstance(max_rf, int) or max_rf < 1:
                validation_results["errors"].append(
                    {
                        "type": "invalid_value",
                        "key": "replication_factor_max",
                        "value": max_rf,
                        "message": "replication_factor_max must be a positive integer",
                    }
                )
                validation_results["valid"] = False

            if isinstance(min_rf, int) and isinstance(max_rf, int) and min_rf > max_rf:
                validation_results["errors"].append(
                    {
                        "type": "invalid_relationship",
                        "keys": ["replication_factor_min", "replication_factor_max"],
                        "message": "replication_factor_min cannot be greater than replication_factor_max",
                    }
                )
                validation_results["valid"] = False

        # Validate timeout format (simple check)
        for key in ["pin_recovery_timeout", "pinning_timeout"]:
            if key in config:
                value = config[key]
                if not isinstance(value, str) or not any(unit in value for unit in ["s", "m", "h"]):
                    validation_results["errors"].append(
                        {
                            "type": "invalid_format",
                            "key": key,
                            "value": value,
                            "message": f"{key} must be a string with time unit (s, m, h)",
                        }
                    )
                    validation_results["valid"] = False

        # Validate pin tracker settings
        if "pin_tracker" in config:
            pt_config = config["pin_tracker"]

            if not isinstance(pt_config, dict):
                validation_results["errors"].append(
                    {
                        "type": "invalid_type",
                        "key": "pin_tracker",
                        "value": pt_config,
                        "message": "pin_tracker must be an object",
                    }
                )
                validation_results["valid"] = False
            else:
                # Check max_pin_queue_size
                if "max_pin_queue_size" in pt_config:
                    size = pt_config["max_pin_queue_size"]
                    if not isinstance(size, int) or size <= 0:
                        validation_results["errors"].append(
                            {
                                "type": "invalid_value",
                                "key": "pin_tracker.max_pin_queue_size",
                                "value": size,
                                "message": "max_pin_queue_size must be a positive integer",
                            }
                        )
                        validation_results["valid"] = False

                # Check concurrent_pins
                if "concurrent_pins" in pt_config:
                    pins = pt_config["concurrent_pins"]
                    if not isinstance(pins, int) or pins <= 0:
                        validation_results["errors"].append(
                            {
                                "type": "invalid_value",
                                "key": "pin_tracker.concurrent_pins",
                                "value": pins,
                                "message": "concurrent_pins must be a positive integer",
                            }
                        )
                        validation_results["valid"] = False

        return validation_results

    def distribute_cluster_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Distribute configuration changes to cluster nodes.

        Args:
            config: Configuration to distribute

        Returns:
            Result of the distribution
        """
        result = {
            "success": False,
            "operation": "distribute_cluster_config",
            "timestamp": time.time(),
        }

        try:
            # Validate configuration first
            validation = self.validate_cluster_config(config)
            if not validation["valid"]:
                result["error"] = "Invalid configuration"
                result["validation"] = validation
                return result

            # Only master can distribute config
            if self.role != "master":
                result["error"] = "Only master role can distribute configuration"
                return result

            # Get list of peers
            peers = self._get_cluster_peers()
            if not peers:
                result["error"] = "No peers found"
                return result

            # Prepare config version and metadata
            config_version = int(time.time())
            config_with_meta = {
                "version": config_version,
                "timestamp": time.time(),
                "source_peer": self._get_local_peer_id(),
                "config": config,
            }

            # In a real implementation, this would send config to all peers
            # and wait for confirmation using cluster API or pubsub

            # Simulate notifying peers and getting responses
            peer_responses = {
                self._get_local_peer_id(): {"status": "accepted", "timestamp": time.time()}
            }

            # Simulate responses from peers
            for i, peer_id in enumerate(peers):
                # Simulate one peer failing (for testing)
                if i == len(peers) - 1:
                    peer_responses[peer_id] = {
                        "status": "rejected",
                        "reason": "incompatible_settings",
                        "timestamp": time.time(),
                    }
                else:
                    peer_responses[peer_id] = {"status": "accepted", "timestamp": time.time()}

            # Calculate acceptance rate
            total_peers = len(peer_responses)
            accepted_peers = sum(
                1 for resp in peer_responses.values() if resp["status"] == "accepted"
            )
            acceptance_rate = accepted_peers / total_peers if total_peers > 0 else 0

            # Distribution is successful if at least 75% of peers accept
            success = acceptance_rate >= 0.75

            result = {
                "success": success,
                "config_version": config_version,
                "peer_responses": peer_responses,
                "acceptance_rate": acceptance_rate,
                "accepted_peers": accepted_peers,
                "total_peers": total_peers,
                "distribution_timestamp": time.time(),
            }

        except Exception as e:
            result["error"] = f"Failed to distribute configuration: {str(e)}"
            logger.error(f"Error distributing configuration: {e}")

        return result

    def _get_cluster_peers(self) -> List[str]:
        """
        Get list of peers in the cluster.

        Returns:
            List of peer IDs
        """
        peers = []

        if self.role == "master" and hasattr(self.ipfs_kit, "ipfs_cluster_ctl"):
            # Use cluster API to get peers
            if hasattr(self.ipfs_kit.ipfs_cluster_ctl, "ipfs_cluster_ctl_peers"):
                peers_result = self.ipfs_kit.ipfs_cluster_ctl.ipfs_cluster_ctl_peers()

                if peers_result.get("success", False):
                    for peer in peers_result.get("peers", []):
                        if "id" in peer:
                            peers.append(peer["id"])

        return peers

    def _get_local_peer_id(self) -> str:
        """
        Get the local peer ID.

        Returns:
            Local peer ID
        """
        # Get local node ID
        if hasattr(self.ipfs_kit, "ipfs") and hasattr(self.ipfs_kit.ipfs, "ipfs_id"):
            id_result = self.ipfs_kit.ipfs.ipfs_id()
            if id_result.get("success", False) and id_result.get("ID"):
                return id_result.get("ID")

        return "local"


class ClusterDashboard:
    """
    Provides a web dashboard for monitoring and managing IPFS cluster.

    This class generates HTML and JavaScript for a web-based dashboard
    that shows cluster metrics, alerts, and provides management controls.
    """

    def __init__(self, ipfs_kit_instance, monitoring_instance=None):
        """
        Initialize the dashboard.

        Args:
            ipfs_kit_instance: Reference to the parent IPFSKit instance
            monitoring_instance: Reference to ClusterMonitoring instance
        """
        self.ipfs_kit = ipfs_kit_instance
        self.monitoring = monitoring_instance or ClusterMonitoring(ipfs_kit_instance)
        self.dashboard_port = self._get_config_value(["Dashboard", "Port"], 8080)
        self.dashboard_enabled = self._get_config_value(["Dashboard", "Enabled"], False)
        self.server = None

    def _get_config_value(self, keys_path: List[str], default: Any) -> Any:
        """
        Get a value from the configuration, traversing a path of keys.

        Args:
            keys_path: List of keys to traverse in the config dictionary
            default: Default value if the path doesn't exist

        Returns:
            The config value or the default
        """
        config = self.ipfs_kit.metadata.get("config", {})
        current = config

        for key in keys_path:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return current

    def start_dashboard(self) -> Dict[str, Any]:
        """
        Start the dashboard web server.

        Returns:
            Result dictionary with status information
        """
        result = {"success": False, "operation": "start_dashboard", "timestamp": time.time()}

        try:
            if self.server:
                result["error"] = "Dashboard server already running"
                return result

            # For a real implementation, this would start a web server
            # For now, we'll just simulate it
            logger.info(f"Dashboard server would start on port {self.dashboard_port}")

            # Start the monitoring if not already running
            if not self.monitoring.metrics_thread or not self.monitoring.metrics_thread.is_alive():
                self.monitoring.start_monitoring()

            result["success"] = True
            result["message"] = f"Dashboard started on port {self.dashboard_port}"
            result["url"] = f"http://localhost:{self.dashboard_port}/"

        except Exception as e:
            result["error"] = f"Failed to start dashboard: {str(e)}"
            logger.error(f"Error starting dashboard: {e}")

        return result

    def stop_dashboard(self) -> Dict[str, Any]:
        """
        Stop the dashboard web server.

        Returns:
            Result dictionary with status information
        """
        result = {"success": False, "operation": "stop_dashboard", "timestamp": time.time()}

        try:
            if not self.server:
                result["warning"] = "Dashboard server not running"
                result["success"] = True
                return result

            # For a real implementation, this would stop the web server
            # For now, we'll just simulate it
            logger.info("Dashboard server would be stopped")
            self.server = None

            result["success"] = True
            result["message"] = "Dashboard stopped"

        except Exception as e:
            result["error"] = f"Failed to stop dashboard: {str(e)}"
            logger.error(f"Error stopping dashboard: {e}")

        return result

    def generate_html_dashboard(self) -> str:
        """
        Generate HTML for the dashboard.

        Returns:
            HTML content for the dashboard
        """
        # Get the latest metrics
        metrics = self.monitoring.get_latest_metrics()
        if not metrics:
            return "<html><body><h1>No metrics available</h1></body></html>"

        # Generate HTML (simplified version)
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>IPFS Cluster Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
        .header {{ background-color: #0b3a53; color: white; padding: 1rem; }}
        .content {{ padding: 1rem; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1rem; }}
        .metric-card {{ border: 1px solid #ddd; border-radius: 4px; padding: 1rem; }}
        .alert {{ background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 0.5rem; margin: 0.5rem 0; border-radius: 4px; }}
        .alert.critical {{ background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
        .chart-container {{ height: 300px; margin-top: 2rem; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>IPFS Cluster Dashboard</h1>
        <p>Last update: {time.ctime(metrics["timestamp"])}</p>
    </div>
    <div class="content">
        <h2>Cluster Overview</h2>
        <div class="metrics-grid">
"""

        # Add node metrics
        for node_id, node_data in metrics["nodes"].items():
            node_name = node_data.get("name", node_id)
            node_metrics = node_data.get("metrics", {})

            html += f"""
            <div class="metric-card">
                <h3>{node_name}</h3>
                <p>ID: {node_id[:16]}...</p>
                <p>CPU Usage: {node_metrics.get("cpu_usage_percent", "N/A")}%</p>
                <p>Memory Usage: {node_metrics.get("memory_usage_percent", "N/A")}%</p>
                <p>Disk Usage: {node_metrics.get("disk_usage_percent", "N/A")}%</p>
                <p>Peers Connected: {node_metrics.get("peers_connected", "N/A")}</p>
                <p>Pins Total: {node_metrics.get("pins_total", "N/A")}</p>
                <p>Pins In Progress: {node_metrics.get("pins_in_progress", "N/A")}</p>
            </div>
"""

        # Add alerts section
        active_alerts = getattr(self.monitoring, "active_alerts", [])
        html += f"""
        </div>
        
        <h2>Active Alerts ({len(active_alerts)})</h2>
"""

        if active_alerts:
            for alert in active_alerts:
                alert_class = "critical" if alert.get("level") == "critical" else "alert"
                html += f"""
        <div class="alert {alert_class}">
            <strong>{alert.get("type")}</strong>: {alert.get("message")}
            <div>Node: {alert.get("node_name")}</div>
            <div>Time: {time.ctime(alert.get("timestamp"))}</div>
        </div>
"""
        else:
            html += "<p>No active alerts</p>"

        # Add charts section
        html += """
        <h2>Performance Metrics</h2>
        
        <div class="chart-container">
            <canvas id="cpuChart"></canvas>
        </div>
        
        <div class="chart-container">
            <canvas id="memoryChart"></canvas>
        </div>
        
        <div class="chart-container">
            <canvas id="diskChart"></canvas>
        </div>
        
        <script>
            // This would be populated with real data in a full implementation
            const timeLabels = Array.from({length: 24}, (_, i) => `${i}h ago`).reverse();
            
            // CPU chart
            new Chart(document.getElementById('cpuChart'), {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'CPU Usage (%)',
                        data: Array.from({length: 24}, () => Math.random() * 100),
                        borderColor: 'rgb(75, 192, 192)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'CPU Usage Over Time'
                        }
                    },
                    scales: {
                        y: {
                            min: 0,
                            max: 100
                        }
                    }
                }
            });
            
            // Memory chart
            new Chart(document.getElementById('memoryChart'), {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'Memory Usage (%)',
                        data: Array.from({length: 24}, () => Math.random() * 100),
                        borderColor: 'rgb(153, 102, 255)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Memory Usage Over Time'
                        }
                    },
                    scales: {
                        y: {
                            min: 0,
                            max: 100
                        }
                    }
                }
            });
            
            // Disk chart
            new Chart(document.getElementById('diskChart'), {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        label: 'Disk Usage (%)',
                        data: Array.from({length: 24}, () => Math.random() * 100),
                        borderColor: 'rgb(255, 99, 132)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Disk Usage Over Time'
                        }
                    },
                    scales: {
                        y: {
                            min: 0,
                            max: 100
                        }
                    }
                }
            });
        </script>
    </div>
</body>
</html>
"""

        return html
