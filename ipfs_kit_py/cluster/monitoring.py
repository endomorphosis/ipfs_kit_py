"""
Monitoring and metrics collection for IPFS Kit clusters.

This module provides components for monitoring cluster health, collecting metrics,
and visualizing cluster performance.
"""

import json
import logging
import os
import threading
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Setup logging
logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and stores metrics about cluster operation.

    This component is responsible for:
    1. Collecting performance metrics from various components
    2. Aggregating metrics over time
    3. Providing historical and real-time metrics data
    4. Persisting metrics for long-term analysis
    """

    def __init__(
        self,
        node_id: str,
        metrics_dir: Optional[str] = None,
        collection_interval: int = 60,
        retention_days: int = 7,
    ):
        """
        Initialize the metrics collector.

        Args:
            node_id: ID of this node
            metrics_dir: Directory to store metrics data
            collection_interval: How often to collect metrics (seconds)
            retention_days: How long to retain metrics data (days)
        """
        self.node_id = node_id
        self.collection_interval = collection_interval
        self.retention_days = retention_days

        # Set up metrics directory
        if metrics_dir:
            self.metrics_dir = os.path.expanduser(metrics_dir)
            os.makedirs(self.metrics_dir, exist_ok=True)
        else:
            self.metrics_dir = None

        # Initialize metrics storage
        self.current_metrics = {}
        self.historical_metrics = {
            "node": {},
            "cluster": {},
            "content": {},
            "network": {},
            "resources": {},
        }

        # Initialize time-series data
        self.time_series = {
            "timestamps": deque(maxlen=1440),  # Store up to 24 hours at 1-minute intervals
            "node": {
                "cpu_percent": deque(maxlen=1440),
                "memory_percent": deque(maxlen=1440),
                "disk_percent": deque(maxlen=1440),
                "content_count": deque(maxlen=1440),
                "peer_count": deque(maxlen=1440),
            },
            "cluster": {
                "member_count": deque(maxlen=1440),
                "master_count": deque(maxlen=1440),
                "worker_count": deque(maxlen=1440),
                "leecher_count": deque(maxlen=1440),
            },
            "content": {
                "added_count": deque(maxlen=1440),
                "retrieved_count": deque(maxlen=1440),
                "pinned_count": deque(maxlen=1440),
                "total_size_bytes": deque(maxlen=1440),
            },
            "network": {
                "bandwidth_in_bytes": deque(maxlen=1440),
                "bandwidth_out_bytes": deque(maxlen=1440),
                "peer_connections": deque(maxlen=1440),
                "content_requests": deque(maxlen=1440),
            },
        }

        # Register data sources
        self.metric_sources = {}

        # Start collection thread
        self.stop_collection = threading.Event()
        self.collection_thread = threading.Thread(
            target=self._collection_loop, daemon=True, name="metrics-collector"
        )
        self.collection_thread.start()

        # Start retention management thread
        if self.metrics_dir:
            self.retention_thread = threading.Thread(
                target=self._manage_retention, daemon=True, name="metrics-retention"
            )
            self.retention_thread.start()

        logger.info(f"Initialized MetricsCollector for node {node_id}")

    def _collection_loop(self):
        """Background thread that collects metrics at regular intervals."""
        while not self.stop_collection.is_set():
            try:
                self._collect_metrics()
                self._update_time_series()

                # Persist metrics if directory is configured
                if self.metrics_dir:
                    self._persist_metrics()

            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")

            # Sleep until next collection interval
            time.sleep(self.collection_interval)

    def _collect_metrics(self):
        """Collect metrics from all registered sources."""
        # Get current timestamp
        current_time = time.time()

        # Update timestamp in current metrics
        self.current_metrics["timestamp"] = current_time

        # Collect metrics from registered sources
        for source_name, source_func in self.metric_sources.items():
            try:
                metrics = source_func()
                self.current_metrics[source_name] = metrics
            except Exception as e:
                logger.error(f"Error collecting metrics from {source_name}: {e}")

    def _update_time_series(self):
        """Update time series data with current metrics."""
        current_time = time.time()

        # Add timestamp
        self.time_series["timestamps"].append(current_time)

        # Extract metrics for time series
        try:
            # Node metrics
            if "resources" in self.current_metrics:
                resources = self.current_metrics["resources"]
                self.time_series["node"]["cpu_percent"].append(resources.get("cpu_percent", 0))
                self.time_series["node"]["memory_percent"].append(
                    resources.get("memory_percent", 0)
                )
                self.time_series["node"]["disk_percent"].append(resources.get("disk_percent", 0))

            if "content" in self.current_metrics:
                content = self.current_metrics["content"]
                self.time_series["node"]["content_count"].append(content.get("total_count", 0))

            if "network" in self.current_metrics:
                network = self.current_metrics["network"]
                self.time_series["node"]["peer_count"].append(network.get("peer_count", 0))

            # Cluster metrics
            if "cluster" in self.current_metrics:
                cluster = self.current_metrics["cluster"]
                self.time_series["cluster"]["member_count"].append(cluster.get("member_count", 0))
                self.time_series["cluster"]["master_count"].append(cluster.get("master_count", 0))
                self.time_series["cluster"]["worker_count"].append(cluster.get("worker_count", 0))
                self.time_series["cluster"]["leecher_count"].append(cluster.get("leecher_count", 0))

            # Content metrics
            if "content" in self.current_metrics:
                content = self.current_metrics["content"]
                self.time_series["content"]["added_count"].append(content.get("added_count", 0))
                self.time_series["content"]["retrieved_count"].append(
                    content.get("retrieved_count", 0)
                )
                self.time_series["content"]["pinned_count"].append(content.get("pinned_count", 0))
                self.time_series["content"]["total_size_bytes"].append(
                    content.get("total_size_bytes", 0)
                )

            # Network metrics
            if "network" in self.current_metrics:
                network = self.current_metrics["network"]
                self.time_series["network"]["bandwidth_in_bytes"].append(
                    network.get("bandwidth_in_bytes", 0)
                )
                self.time_series["network"]["bandwidth_out_bytes"].append(
                    network.get("bandwidth_out_bytes", 0)
                )
                self.time_series["network"]["peer_connections"].append(
                    network.get("peer_connections", 0)
                )
                self.time_series["network"]["content_requests"].append(
                    network.get("content_requests", 0)
                )

        except Exception as e:
            logger.error(f"Error updating time series: {e}")

    def _persist_metrics(self):
        """Persist metrics to disk."""
        if not self.metrics_dir:
            return

        try:
            # Generate filename based on timestamp
            current_time = time.time()
            date_str = time.strftime("%Y-%m-%d", time.localtime(current_time))
            hour_str = time.strftime("%H", time.localtime(current_time))

            # Create date directory if it doesn't exist
            date_dir = os.path.join(self.metrics_dir, date_str)
            os.makedirs(date_dir, exist_ok=True)

            # Write metrics to file
            filename = f"{hour_str}_{int(current_time)}.json"
            file_path = os.path.join(date_dir, filename)

            with open(file_path, "w") as f:
                json.dump(self.current_metrics, f)

        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")

    def _manage_retention(self):
        """Manage retention of metrics data."""
        if not self.metrics_dir:
            return

        while not self.stop_collection.is_set():
            try:
                # Sleep for a day
                time.sleep(86400)  # 24 hours

                # Calculate cutoff date
                cutoff_time = time.time() - (self.retention_days * 86400)
                cutoff_date = time.strftime("%Y-%m-%d", time.localtime(cutoff_time))

                # List directories
                for item in os.listdir(self.metrics_dir):
                    if os.path.isdir(os.path.join(self.metrics_dir, item)) and item < cutoff_date:
                        # Directory is older than retention period, remove it
                        logger.info(f"Removing old metrics directory: {item}")
                        self._remove_directory(os.path.join(self.metrics_dir, item))

            except Exception as e:
                logger.error(f"Error managing metrics retention: {e}")

    def _remove_directory(self, directory: str):
        """Safely remove a directory and all its contents."""
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    self._remove_directory(item_path)

            os.rmdir(directory)
        except Exception as e:
            logger.error(f"Error removing directory {directory}: {e}")

    def register_metric_source(self, name: str, source_func: Callable[[], Dict[str, Any]]):
        """
        Register a function that provides metrics.

        Args:
            name: Name of the metric source
            source_func: Function that returns metrics dictionary
        """
        self.metric_sources[name] = source_func
        logger.debug(f"Registered metrics source: {name}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get the most recent metrics.

        Returns:
            Dictionary of current metrics
        """
        return self.current_metrics.copy()

    def get_historical_metrics(self, timeframe: str = "1h") -> Dict[str, Any]:
        """
        Get historical metrics for a specified timeframe.

        Args:
            timeframe: Timeframe for metrics (e.g. "1h", "6h", "24h")

        Returns:
            Dictionary of historical metrics
        """
        # Parse timeframe to determine how many data points to include
        if timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            points = min(hours * 60, len(self.time_series["timestamps"]))
        elif timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            points = min(minutes, len(self.time_series["timestamps"]))
        else:
            # Default to all available points
            points = len(self.time_series["timestamps"])

        if points == 0:
            return {"timestamps": [], "metrics": {}}

        # Extract relevant time series data
        result = {"timestamps": list(self.time_series["timestamps"])[-points:], "metrics": {}}

        # Extract metrics
        for category in ["node", "cluster", "content", "network"]:
            result["metrics"][category] = {}

            for metric_name, values in self.time_series[category].items():
                if len(values) > 0:
                    result["metrics"][category][metric_name] = list(values)[-points:]

        return result

    def get_aggregated_metrics(self, timeframe: str = "1h") -> Dict[str, Any]:
        """
        Get aggregated metrics for a specified timeframe.

        Args:
            timeframe: Timeframe for metrics (e.g. "1h", "6h", "24h")

        Returns:
            Dictionary of aggregated metrics
        """
        # Get historical metrics
        historical = self.get_historical_metrics(timeframe)

        if not historical["timestamps"]:
            return {"timeframe": timeframe, "aggregates": {}}

        # Calculate aggregates
        aggregates = {
            "timeframe": timeframe,
            "node": {},
            "cluster": {},
            "content": {},
            "network": {},
        }

        try:
            # Aggregate node metrics
            for metric in self.time_series["node"]:
                values = historical["metrics"]["node"].get(metric, [])
                if values:
                    aggregates["node"][metric] = {
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "current": values[-1] if values else None,
                    }

            # Aggregate cluster metrics
            for metric in self.time_series["cluster"]:
                values = historical["metrics"]["cluster"].get(metric, [])
                if values:
                    aggregates["cluster"][metric] = {
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "current": values[-1] if values else None,
                    }

            # Aggregate content metrics
            for metric in self.time_series["content"]:
                values = historical["metrics"]["content"].get(metric, [])
                if values:
                    aggregates["content"][metric] = {
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "current": values[-1] if values else None,
                    }

            # Aggregate network metrics
            for metric in self.time_series["network"]:
                values = historical["metrics"]["network"].get(metric, [])
                if values:
                    aggregates["network"][metric] = {
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "current": values[-1] if values else None,
                    }
        except Exception as e:
            logger.error(f"Error calculating aggregated metrics: {e}")

        return aggregates

    def shutdown(self):
        """Shut down the metrics collector."""
        logger.info("Shutting down MetricsCollector")
        self.stop_collection.set()

        if hasattr(self, "collection_thread"):
            self.collection_thread.join(timeout=5)

        if hasattr(self, "retention_thread"):
            self.retention_thread.join(timeout=1)


class ClusterMonitor:
    """
    Monitors the health and performance of the IPFS cluster.

    This component is responsible for:
    1. Tracking the health of cluster nodes
    2. Detecting and reporting issues
    3. Providing visualization of cluster state
    4. Generating alerts for potential problems
    """

    def __init__(
        self,
        node_id: str,
        metrics_collector: Optional[MetricsCollector] = None,
        check_interval: int = 60,
        alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the cluster monitor.

        Args:
            node_id: ID of this node
            metrics_collector: MetricsCollector instance to use
            check_interval: How often to check health (seconds)
            alert_callback: Function to call when alerts are generated
        """
        self.node_id = node_id
        self.check_interval = check_interval
        self.alert_callback = alert_callback

        # Connect to metrics collector
        if metrics_collector:
            self.metrics_collector = metrics_collector
        else:
            # Create a new one
            self.metrics_collector = MetricsCollector(node_id=node_id)

        # Register as a metrics source
        self.metrics_collector.register_metric_source("monitor", self.get_monitoring_metrics)

        # Initialize monitoring state
        self.node_health = {}  # node_id -> health status
        self.cluster_health = {"status": "unknown", "issues": []}
        self.alerts = []
        self.alert_history = deque(maxlen=100)  # Store last 100 alerts

        # Define health check thresholds
        self.thresholds = {
            "cpu_percent_warning": 80,
            "cpu_percent_critical": 95,
            "memory_percent_warning": 80,
            "memory_percent_critical": 95,
            "disk_percent_warning": 80,
            "disk_percent_critical": 95,
            "node_unresponsive_threshold": 300,  # 5 minutes
            "peer_connection_minimum": 3,
            "master_node_minimum": 1,
        }

        # Start health check thread
        self.stop_monitoring = threading.Event()
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True, name="cluster-monitor"
        )
        self.monitoring_thread.start()

        logger.info(f"Initialized ClusterMonitor for node {node_id}")

    def _monitoring_loop(self):
        """Background thread that checks cluster health at regular intervals."""
        while not self.stop_monitoring.is_set():
            try:
                self._check_cluster_health()
                self._check_node_health()
                self._generate_alerts()

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Sleep until next check interval
            time.sleep(self.check_interval)

    def _check_cluster_health(self):
        """Check the health of the cluster as a whole."""
        issues = []

        # Get current metrics
        metrics = self.metrics_collector.get_current_metrics()

        # Check for cluster-wide issues
        if "cluster" in metrics:
            cluster = metrics.get("cluster", {})

            # Check master node count
            master_count = cluster.get("master_count", 0)
            if master_count < self.thresholds["master_node_minimum"]:
                issues.append(
                    {
                        "type": "no_master",
                        "severity": "critical",
                        "message": f"No master node in cluster (count: {master_count})",
                    }
                )

            # Check member count
            member_count = cluster.get("member_count", 0)
            if member_count < 2:
                issues.append(
                    {
                        "type": "single_node",
                        "severity": "warning",
                        "message": f"Cluster has only {member_count} member(s)",
                    }
                )

        # Update cluster health
        if issues:
            # Set overall status based on most severe issue
            if any(issue["severity"] == "critical" for issue in issues):
                status = "critical"
            elif any(issue["severity"] == "warning" for issue in issues):
                status = "warning"
            else:
                status = "healthy"

            self.cluster_health = {"status": status, "issues": issues, "last_check": time.time()}
        else:
            self.cluster_health = {"status": "healthy", "issues": [], "last_check": time.time()}

    def _check_node_health(self):
        """Check the health of individual nodes in the cluster."""
        # Get current metrics
        metrics = self.metrics_collector.get_current_metrics()

        # Check local node health
        local_issues = []

        # Check resource usage
        if "resources" in metrics:
            resources = metrics.get("resources", {})

            # Check CPU usage
            cpu_percent = resources.get("cpu_percent", 0)
            if cpu_percent >= self.thresholds["cpu_percent_critical"]:
                local_issues.append(
                    {
                        "type": "high_cpu",
                        "severity": "critical",
                        "message": f"CPU usage critical: {cpu_percent}%",
                    }
                )
            elif cpu_percent >= self.thresholds["cpu_percent_warning"]:
                local_issues.append(
                    {
                        "type": "high_cpu",
                        "severity": "warning",
                        "message": f"CPU usage high: {cpu_percent}%",
                    }
                )

            # Check memory usage
            memory_percent = resources.get("memory_percent", 0)
            if memory_percent >= self.thresholds["memory_percent_critical"]:
                local_issues.append(
                    {
                        "type": "high_memory",
                        "severity": "critical",
                        "message": f"Memory usage critical: {memory_percent}%",
                    }
                )
            elif memory_percent >= self.thresholds["memory_percent_warning"]:
                local_issues.append(
                    {
                        "type": "high_memory",
                        "severity": "warning",
                        "message": f"Memory usage high: {memory_percent}%",
                    }
                )

            # Check disk usage
            disk_percent = resources.get("disk_percent", 0)
            if disk_percent >= self.thresholds["disk_percent_critical"]:
                local_issues.append(
                    {
                        "type": "high_disk",
                        "severity": "critical",
                        "message": f"Disk usage critical: {disk_percent}%",
                    }
                )
            elif disk_percent >= self.thresholds["disk_percent_warning"]:
                local_issues.append(
                    {
                        "type": "high_disk",
                        "severity": "warning",
                        "message": f"Disk usage high: {disk_percent}%",
                    }
                )

        # Check network connectivity
        if "network" in metrics:
            network = metrics.get("network", {})

            # Check peer connections
            peer_count = network.get("peer_count", 0)
            if peer_count < self.thresholds["peer_connection_minimum"]:
                local_issues.append(
                    {
                        "type": "low_peers",
                        "severity": "warning",
                        "message": f"Low peer connections: {peer_count}",
                    }
                )

        # Update local node health
        if local_issues:
            # Set overall status based on most severe issue
            if any(issue["severity"] == "critical" for issue in local_issues):
                status = "critical"
            elif any(issue["severity"] == "warning" for issue in local_issues):
                status = "warning"
            else:
                status = "healthy"

            self.node_health[self.node_id] = {
                "status": status,
                "issues": local_issues,
                "last_check": time.time(),
            }
        else:
            self.node_health[self.node_id] = {
                "status": "healthy",
                "issues": [],
                "last_check": time.time(),
            }

        # Check other nodes in cluster (if available)
        if "cluster" in metrics and "nodes" in metrics["cluster"]:
            for node in metrics["cluster"]["nodes"]:
                node_id = node.get("node_id", "")
                if node_id and node_id != self.node_id:
                    node_issues = []

                    # Check last seen time
                    last_seen = node.get("last_seen", 0)
                    current_time = time.time()
                    if current_time - last_seen > self.thresholds["node_unresponsive_threshold"]:
                        node_issues.append(
                            {
                                "type": "unresponsive",
                                "severity": "critical",
                                "message": f"Node unresponsive for {int(current_time - last_seen)} seconds",
                            }
                        )

                    # Add any reported issues
                    if "issues" in node:
                        node_issues.extend(node["issues"])

                    # Update node health
                    if node_issues:
                        # Set overall status based on most severe issue
                        if any(issue["severity"] == "critical" for issue in node_issues):
                            status = "critical"
                        elif any(issue["severity"] == "warning" for issue in node_issues):
                            status = "warning"
                        else:
                            status = "healthy"

                        self.node_health[node_id] = {
                            "status": status,
                            "issues": node_issues,
                            "last_check": time.time(),
                        }
                    else:
                        self.node_health[node_id] = {
                            "status": "healthy",
                            "issues": [],
                            "last_check": time.time(),
                        }

    def _generate_alerts(self):
        """Generate alerts based on health issues."""
        # Check cluster health
        if self.cluster_health["status"] in ("warning", "critical"):
            for issue in self.cluster_health["issues"]:
                alert = {
                    "timestamp": time.time(),
                    "source": "cluster",
                    "level": issue["severity"],
                    "type": issue["type"],
                    "message": issue["message"],
                }

                # Add to alerts and history
                self.alerts.append(alert)
                self.alert_history.append(alert)

                # Call alert callback if provided
                if self.alert_callback:
                    try:
                        self.alert_callback("cluster", alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {e}")

        # Check node health
        for node_id, health in self.node_health.items():
            if health["status"] in ("warning", "critical"):
                for issue in health["issues"]:
                    alert = {
                        "timestamp": time.time(),
                        "source": "node",
                        "node_id": node_id,
                        "level": issue["severity"],
                        "type": issue["type"],
                        "message": issue["message"],
                    }

                    # Add to alerts and history
                    self.alerts.append(alert)
                    self.alert_history.append(alert)

                    # Call alert callback if provided
                    if self.alert_callback:
                        try:
                            self.alert_callback("node", alert)
                        except Exception as e:
                            logger.error(f"Error in alert callback: {e}")

    def get_monitoring_metrics(self) -> Dict[str, Any]:
        """
        Get monitoring metrics for the metrics collector.

        Returns:
            Dictionary of monitoring metrics
        """
        return {
            "cluster_health": self.cluster_health,
            "node_health": self.node_health,
            "alert_count": len(self.alerts),
            "thresholds": self.thresholds,
        }

    def get_cluster_health(self) -> Dict[str, Any]:
        """
        Get the health status of the cluster.

        Returns:
            Dictionary containing cluster health information
        """
        return {
            "status": self.cluster_health["status"],
            "issues": self.cluster_health["issues"],
            "last_check": self.cluster_health.get("last_check"),
            "node_statuses": {
                node_id: health["status"] for node_id, health in self.node_health.items()
            },
            "alerts": len(self.alerts),
        }

    def get_node_health(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the health status of a node or all nodes.

        Args:
            node_id: ID of the node (None for all nodes)

        Returns:
            Dictionary containing node health information
        """
        if node_id:
            if node_id in self.node_health:
                return self.node_health[node_id]
            else:
                return {"status": "unknown", "issues": []}
        else:
            return {node_id: health for node_id, health in self.node_health.items()}

    def get_alerts(
        self, count: Optional[int] = None, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active alerts.

        Args:
            count: Maximum number of alerts to return
            level: Filter by alert level

        Returns:
            List of alert dictionaries
        """
        filtered_alerts = self.alerts

        # Filter by level if specified
        if level:
            filtered_alerts = [alert for alert in filtered_alerts if alert["level"] == level]

        # Limit count if specified
        if count is not None:
            filtered_alerts = filtered_alerts[:count]

        return filtered_alerts

    def get_alert_history(
        self, count: Optional[int] = None, level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get alert history.

        Args:
            count: Maximum number of alerts to return
            level: Filter by alert level

        Returns:
            List of alert dictionaries
        """
        filtered_history = list(self.alert_history)

        # Filter by level if specified
        if level:
            filtered_history = [alert for alert in filtered_history if alert["level"] == level]

        # Limit count if specified
        if count is not None:
            filtered_history = filtered_history[-count:]

        return filtered_history

    def set_alert_threshold(self, name: str, value: Any) -> bool:
        """
        Set an alert threshold.

        Args:
            name: Name of the threshold
            value: New threshold value

        Returns:
            True if threshold was set, False otherwise
        """
        if name in self.thresholds:
            self.thresholds[name] = value
            logger.debug(f"Set threshold {name} to {value}")
            return True
        else:
            logger.warning(f"Unknown threshold: {name}")
            return False

    def clear_alerts(self, level: Optional[str] = None) -> int:
        """
        Clear active alerts.

        Args:
            level: Only clear alerts of this level

        Returns:
            Number of alerts cleared
        """
        if level:
            # Only clear alerts of the specified level
            original_count = len(self.alerts)
            self.alerts = [alert for alert in self.alerts if alert["level"] != level]
            return original_count - len(self.alerts)
        else:
            # Clear all alerts
            count = len(self.alerts)
            self.alerts = []
            return count

    def shutdown(self):
        """Shut down the cluster monitor."""
        logger.info("Shutting down ClusterMonitor")
        self.stop_monitoring.set()

        if hasattr(self, "monitoring_thread"):
            self.monitoring_thread.join(timeout=5)

        # Shutdown metrics collector if we created it
        if hasattr(self, "metrics_collector") and self.metrics_collector:
            self.metrics_collector.shutdown()
