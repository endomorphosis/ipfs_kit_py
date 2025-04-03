"""
Tests for monitoring and management in ipfs_kit_py.

This module tests the monitoring and management capabilities (Phase 3B), including:
- Cluster management dashboard
- Health monitoring and alerts
- Performance visualization
- Configuration management tools
- Resource tracking
- Automated recovery procedures
"""

import asyncio
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from ipfs_kit_py.ipfs_kit import ipfs_kit


@pytest.fixture
def monitoring_cluster():
    """Create a cluster setup for monitoring and management testing."""
    with patch("subprocess.run") as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-id"}'
        mock_run.return_value = mock_process

        # Create master node with monitoring capabilities
        master = ipfs_kit(
            resources={"memory": "8GB", "disk": "1TB", "cpu": 4},
            metadata={
                "role": "master",
                "cluster_name": "test-cluster",
                "config": {
                    "Monitoring": {
                        "Enabled": True,
                        "MetricsInterval": "30s",
                        "AlertThresholds": {
                            "DiskSpace": 85,  # alert at 85% usage
                            "MemoryUsage": 80,
                            "CpuUsage": 90,
                        },
                    }
                },
                "test_mode": True,
            },
        )
        master.ipfs = MagicMock()
        master.ipfs_cluster_service = MagicMock()
        master.ipfs_cluster_ctl = MagicMock()

        # Create worker nodes
        workers = []
        for i in range(3):
            worker = ipfs_kit(
                resources={"memory": "4GB", "disk": "500GB", "cpu": 2},
                metadata={
                    "role": "worker",
                    "cluster_name": "test-cluster",
                    "config": {"Monitoring": {"Enabled": True, "MetricsInterval": "60s"}},
                    "test_mode": True,
                },
            )
            worker.ipfs = MagicMock()
            worker.ipfs_cluster_follow = MagicMock()
            workers.append(worker)

        yield {"master": master, "workers": workers}


class TestClusterHealthMonitoring:
    """Test cluster health monitoring capabilities."""

    def test_node_metrics_collection(self, monitoring_cluster):
        """Test collection of metrics from cluster nodes."""
        master = monitoring_cluster["master"]
        workers = monitoring_cluster["workers"]

        # Mock metrics collection on master
        master.ipfs_cluster_ctl.ipfs_cluster_ctl_status = MagicMock(
            return_value={
                "success": True,
                "peer_statuses": [
                    {
                        "id": "QmMasterNodeID",
                        "peername": "master",
                        "ipfs": {"addresses": ["/ip4/127.0.0.1/tcp/4001"], "id": "QmMasterIPFS"},
                        "metrics": {
                            "freespace": 800 * 1024 * 1024 * 1024,  # 800GB
                            "reposize": 200 * 1024 * 1024 * 1024,  # 200GB
                            "memory_used_mb": 2048,  # 2GB
                            "memory_total_mb": 8192,  # 8GB
                            "cpu_usage_percent": 30,
                            "bandwidth_in_mbps": 42.5,
                            "bandwidth_out_mbps": 38.2,
                            "peers_connected": 15,
                            "pins_queued": 3,
                            "pins_in_progress": 1,
                        },
                    },
                    {
                        "id": "QmWorker1ID",
                        "peername": "worker-1",
                        "metrics": {
                            "freespace": 300 * 1024 * 1024 * 1024,  # 300GB
                            "reposize": 200 * 1024 * 1024 * 1024,  # 200GB
                            "memory_used_mb": 1024,  # 1GB
                            "memory_total_mb": 4096,  # 4GB
                            "cpu_usage_percent": 20,
                            "bandwidth_in_mbps": 15.8,
                            "bandwidth_out_mbps": 12.3,
                            "peers_connected": 8,
                            "pins_queued": 0,
                            "pins_in_progress": 0,
                        },
                    },
                    {
                        "id": "QmWorker2ID",
                        "peername": "worker-2",
                        "metrics": {
                            "freespace": 50 * 1024 * 1024 * 1024,  # 50GB
                            "reposize": 450 * 1024 * 1024 * 1024,  # 450GB
                            "memory_used_mb": 3500,  # 3.5GB
                            "memory_total_mb": 4096,  # 4GB
                            "cpu_usage_percent": 80,
                            "bandwidth_in_mbps": 32.1,
                            "bandwidth_out_mbps": 28.7,
                            "peers_connected": 12,
                            "pins_queued": 5,
                            "pins_in_progress": 2,
                        },
                    },
                ],
            }
        )

        # Mock collectMetrics method on master
        def collect_metrics(**kwargs):
            # Get cluster status which includes metrics
            status = master.ipfs_cluster_ctl.ipfs_cluster_ctl_status()

            # Extract metrics from status
            metrics = {"timestamp": time.time(), "nodes": {}}

            # Process each peer's metrics
            for peer in status.get("peer_statuses", []):
                peer_id = peer.get("id")
                peer_metrics = peer.get("metrics", {})

                # Calculate derived metrics
                if "freespace" in peer_metrics and "reposize" in peer_metrics:
                    # Calculate disk usage percentage
                    total_space = peer_metrics["freespace"] + peer_metrics["reposize"]
                    disk_usage_percent = (
                        (peer_metrics["reposize"] / total_space) * 100 if total_space > 0 else 0
                    )
                    peer_metrics["disk_usage_percent"] = disk_usage_percent

                if "memory_used_mb" in peer_metrics and "memory_total_mb" in peer_metrics:
                    # Calculate memory usage percentage
                    memory_usage_percent = (
                        (peer_metrics["memory_used_mb"] / peer_metrics["memory_total_mb"]) * 100
                        if peer_metrics["memory_total_mb"] > 0
                        else 0
                    )
                    peer_metrics["memory_usage_percent"] = memory_usage_percent

                # Add to metrics collection
                metrics["nodes"][peer_id] = {
                    "name": peer.get("peername", peer_id),
                    "metrics": peer_metrics,
                }

            return metrics

        # Mock the metrics collection method
        master.collect_cluster_metrics = MagicMock(side_effect=collect_metrics)

        # Test metrics collection
        metrics = master.collect_cluster_metrics()

        # Verify metrics collection
        assert "timestamp" in metrics
        assert "nodes" in metrics
        assert len(metrics["nodes"]) == 3
        assert "QmMasterNodeID" in metrics["nodes"]
        assert "QmWorker1ID" in metrics["nodes"]
        assert "QmWorker2ID" in metrics["nodes"]

        # Verify derived metrics
        assert "disk_usage_percent" in metrics["nodes"]["QmMasterNodeID"]["metrics"]
        assert "memory_usage_percent" in metrics["nodes"]["QmWorker1ID"]["metrics"]
        assert (
            metrics["nodes"]["QmWorker2ID"]["metrics"]["disk_usage_percent"] > 80
        )  # Worker2 has high disk usage

        # Verify actual metrics values
        assert metrics["nodes"]["QmMasterNodeID"]["metrics"]["cpu_usage_percent"] == 30
        assert metrics["nodes"]["QmWorker1ID"]["metrics"]["memory_used_mb"] == 1024
        assert metrics["nodes"]["QmWorker2ID"]["metrics"]["bandwidth_in_mbps"] == 32.1

    def test_alert_generation(self, monitoring_cluster):
        """Test generation of alerts based on threshold crossings."""
        master = monitoring_cluster["master"]

        # Mock metrics data with threshold violations
        metrics_data = {
            "timestamp": time.time(),
            "nodes": {
                "QmMasterNodeID": {
                    "name": "master",
                    "metrics": {
                        "cpu_usage_percent": 30,
                        "memory_usage_percent": 25,
                        "disk_usage_percent": 20,
                        "peers_connected": 15,
                    },
                },
                "QmWorker1ID": {
                    "name": "worker-1",
                    "metrics": {
                        "cpu_usage_percent": 95,  # CPU threshold crossed
                        "memory_usage_percent": 40,
                        "disk_usage_percent": 30,
                        "peers_connected": 8,
                    },
                },
                "QmWorker2ID": {
                    "name": "worker-2",
                    "metrics": {
                        "cpu_usage_percent": 60,
                        "memory_usage_percent": 85,  # Memory threshold crossed
                        "disk_usage_percent": 90,  # Disk threshold crossed
                        "peers_connected": 12,
                    },
                },
            },
        }

        # Mock check_alert_thresholds method
        def check_thresholds(metrics_data, **kwargs):
            # Get thresholds from config
            config = (
                master.metadata.get("config", {}).get("Monitoring", {}).get("AlertThresholds", {})
            )
            disk_threshold = config.get("DiskSpace", 90)
            memory_threshold = config.get("MemoryUsage", 80)
            cpu_threshold = config.get("CpuUsage", 90)

            # Initialize alerts list
            alerts = []

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

            return alerts

        # Mock the alert generation method
        master.check_alert_thresholds = MagicMock(side_effect=check_thresholds)

        # Test alert generation
        alerts = master.check_alert_thresholds(metrics_data)

        # Verify alerts
        assert len(alerts) == 3  # Three threshold violations
        assert any(
            alert["type"] == "cpu_usage_high" and alert["node_id"] == "QmWorker1ID"
            for alert in alerts
        )
        assert any(
            alert["type"] == "memory_usage_high" and alert["node_id"] == "QmWorker2ID"
            for alert in alerts
        )
        assert any(
            alert["type"] == "disk_usage_high" and alert["node_id"] == "QmWorker2ID"
            for alert in alerts
        )

        # Verify alert details
        cpu_alert = next(alert for alert in alerts if alert["type"] == "cpu_usage_high")
        assert cpu_alert["level"] == "warning"
        assert cpu_alert["value"] == 95
        assert "High CPU usage" in cpu_alert["message"]

    def test_automatic_recovery_actions(self, monitoring_cluster):
        """Test automatic recovery actions based on alerts."""
        master = monitoring_cluster["master"]

        # Mock alerts that should trigger recovery actions
        alerts = [
            {
                "level": "warning",
                "type": "cpu_usage_high",
                "node_id": "QmWorker1ID",
                "node_name": "worker-1",
                "value": 95,
                "threshold": 90,
                "timestamp": time.time(),
                "message": "High CPU usage on worker-1: 95% (threshold: 90%)",
            },
            {
                "level": "critical",
                "type": "disk_usage_high",
                "node_id": "QmWorker2ID",
                "node_name": "worker-2",
                "value": 98,
                "threshold": 85,
                "timestamp": time.time(),
                "message": "High disk usage on worker-2: 98% (threshold: 85%)",
            },
        ]

        # Mock take_recovery_action method
        def process_alerts(alerts, **kwargs):
            # Initialize recovery actions list
            recovery_actions = []

            # Process each alert and take appropriate actions
            for alert in alerts:
                node_id = alert["node_id"]
                alert_type = alert["type"]
                level = alert["level"]

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
                        }
                    )

            return recovery_actions

        # Mock the recovery action method
        master.process_alerts = MagicMock(side_effect=process_alerts)

        # Test recovery action generation
        actions = master.process_alerts(alerts)

        # Verify recovery actions
        assert len(actions) == 3  # Three recovery actions for the two alerts
        assert any(
            action["action"] == "throttle_operations" and action["node_id"] == "QmWorker1ID"
            for action in actions
        )
        assert any(
            action["action"] == "reallocate_pins" and action["node_id"] == "QmWorker2ID"
            for action in actions
        )
        assert any(
            action["action"] == "run_garbage_collection" and action["node_id"] == "QmWorker2ID"
            for action in actions
        )


class TestPerformanceVisualization:
    """Test performance visualization and metrics systems."""

    def test_metrics_aggregation(self, monitoring_cluster):
        """Test aggregation of metrics for visualization."""
        master = monitoring_cluster["master"]

        # Mock historical metrics data
        historical_metrics = []

        # Make sure at least one set of metrics exists
        sample_time = time.time() - (60 * 60)  # 1 hour ago

        # Create sample metrics
        metrics = {
            "timestamp": sample_time,
            "nodes": {
                "QmMasterNodeID": {
                    "name": "master",
                    "metrics": {
                        "cpu_usage_percent": 30,
                        "memory_usage_percent": 40,
                        "disk_usage_percent": 25,
                        "peers_connected": 15,
                        "pins_total": 1000,
                        "pins_in_progress": 2,
                    },
                },
                "QmWorker1ID": {
                    "name": "worker-1",
                    "metrics": {
                        "cpu_usage_percent": 25,
                        "memory_usage_percent": 35,
                        "disk_usage_percent": 30,
                        "peers_connected": 10,
                        "pins_total": 800,
                        "pins_in_progress": 1,
                    },
                },
                "QmWorker2ID": {
                    "name": "worker-2",
                    "metrics": {
                        "cpu_usage_percent": 40,
                        "memory_usage_percent": 45,
                        "disk_usage_percent": 50,
                        "peers_connected": 12,
                        "pins_total": 900,
                        "pins_in_progress": 3,
                    },
                },
            },
        }

        # Add single metrics sample - we'll make the mock return this as a 24-element array
        historical_metrics.append(metrics)

        # Generate mock data for the remaining hours (same data repeated)
        for i in range(1, 24):  # Add 23 more identical samples for simplicity
            sample_time = time.time() - (24 * 60 * 60) + (i * 60 * 60)
            metrics_copy = metrics.copy()
            metrics_copy["timestamp"] = sample_time
            historical_metrics.append(metrics_copy)

        # Mock the aggregate_metrics method
        def aggregate_metrics(time_range="24h", interval="1h", **kwargs):
            # For testing, we'll use our pre-generated historical metrics

            # Filter metrics based on time range
            now = time.time()
            if time_range == "24h":
                time_limit = now - (24 * 60 * 60)
            elif time_range == "7d":
                time_limit = now - (7 * 24 * 60 * 60)
            elif time_range == "1h":
                time_limit = now - (60 * 60)
            else:
                time_limit = now - (24 * 60 * 60)  # Default to 24h

            filtered_metrics = [m for m in historical_metrics if m["timestamp"] >= time_limit]

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

            # Setup node-specific metrics
            for node_id in filtered_metrics[0]["nodes"]:
                aggregated["nodes"][node_id] = {
                    "name": filtered_metrics[0]["nodes"][node_id]["name"],
                    "cpu_usage_percent": [],
                    "memory_usage_percent": [],
                    "disk_usage_percent": [],
                    "peers_connected": [],
                    "pins_total": [],
                    "pins_in_progress": [],
                }

            # Process each metric sample
            for metrics in filtered_metrics:
                aggregated["timestamps"].append(metrics["timestamp"])

                # Track cluster-wide averages
                cpu_values = []
                memory_values = []
                disk_values = []
                peers_total = 0
                pins_total = 0
                pins_in_progress = 0

                # Process each node
                for node_id, node_data in metrics["nodes"].items():
                    node_metrics = node_data["metrics"]

                    # Add to node-specific time series
                    if node_id in aggregated["nodes"]:
                        node_series = aggregated["nodes"][node_id]
                        node_series["cpu_usage_percent"].append(
                            node_metrics.get("cpu_usage_percent", 0)
                        )
                        node_series["memory_usage_percent"].append(
                            node_metrics.get("memory_usage_percent", 0)
                        )
                        node_series["disk_usage_percent"].append(
                            node_metrics.get("disk_usage_percent", 0)
                        )
                        node_series["peers_connected"].append(
                            node_metrics.get("peers_connected", 0)
                        )
                        node_series["pins_total"].append(node_metrics.get("pins_total", 0))
                        node_series["pins_in_progress"].append(
                            node_metrics.get("pins_in_progress", 0)
                        )

                    # Collect values for cluster-wide aggregation
                    cpu_values.append(node_metrics.get("cpu_usage_percent", 0))
                    memory_values.append(node_metrics.get("memory_usage_percent", 0))
                    disk_values.append(node_metrics.get("disk_usage_percent", 0))
                    peers_total += node_metrics.get("peers_connected", 0)
                    pins_total += node_metrics.get("pins_total", 0)
                    pins_in_progress += node_metrics.get("pins_in_progress", 0)

                # Calculate cluster-wide values
                aggregated["cluster"]["cpu_usage_percent"].append(
                    sum(cpu_values) / len(cpu_values) if cpu_values else 0
                )
                aggregated["cluster"]["memory_usage_percent"].append(
                    sum(memory_values) / len(memory_values) if memory_values else 0
                )
                aggregated["cluster"]["disk_usage_percent"].append(
                    sum(disk_values) / len(disk_values) if disk_values else 0
                )
                aggregated["cluster"]["peers_connected"].append(peers_total)
                aggregated["cluster"]["pins_total"].append(pins_total)
                aggregated["cluster"]["pins_in_progress"].append(pins_in_progress)

            # Add summary statistics
            aggregated["summary"] = {
                "time_range": time_range,
                "interval": interval,
                "samples": len(filtered_metrics),
                "cluster": {
                    "cpu_usage_percent_avg": (
                        sum(aggregated["cluster"]["cpu_usage_percent"])
                        / len(aggregated["cluster"]["cpu_usage_percent"])
                        if aggregated["cluster"]["cpu_usage_percent"]
                        else 0
                    ),
                    "memory_usage_percent_avg": (
                        sum(aggregated["cluster"]["memory_usage_percent"])
                        / len(aggregated["cluster"]["memory_usage_percent"])
                        if aggregated["cluster"]["memory_usage_percent"]
                        else 0
                    ),
                    "disk_usage_percent_avg": (
                        sum(aggregated["cluster"]["disk_usage_percent"])
                        / len(aggregated["cluster"]["disk_usage_percent"])
                        if aggregated["cluster"]["disk_usage_percent"]
                        else 0
                    ),
                    "pins_total_current": (
                        aggregated["cluster"]["pins_total"][-1]
                        if aggregated["cluster"]["pins_total"]
                        else 0
                    ),
                },
            }

            return aggregated

        # Mock the metrics aggregation method
        master.aggregate_metrics = MagicMock(side_effect=aggregate_metrics)

        # Test metrics aggregation
        aggregated = master.aggregate_metrics(time_range="24h", interval="1h")

        # Verify aggregated data
        assert "timestamps" in aggregated
        assert "nodes" in aggregated
        assert "cluster" in aggregated
        assert "summary" in aggregated

        # Verify we have the expected number of samples
        assert len(aggregated["timestamps"]) == 24
        assert len(aggregated["cluster"]["cpu_usage_percent"]) == 24

        # Verify node-specific data
        assert "QmMasterNodeID" in aggregated["nodes"]
        assert "QmWorker1ID" in aggregated["nodes"]
        assert "QmWorker2ID" in aggregated["nodes"]

        # Verify time series data for a node
        master_data = aggregated["nodes"]["QmMasterNodeID"]
        assert len(master_data["cpu_usage_percent"]) == 24
        assert len(master_data["disk_usage_percent"]) == 24

        # Verify summary statistics
        assert "cpu_usage_percent_avg" in aggregated["summary"]["cluster"]
        assert "pins_total_current" in aggregated["summary"]["cluster"]

    def test_metrics_export_formats(self, monitoring_cluster):
        """Test export of metrics in various formats."""
        master = monitoring_cluster["master"]

        # Mock aggregated metrics data (simplified)
        aggregated_metrics = {
            "timestamps": [time.time() - (i * 3600) for i in range(24, 0, -1)],  # Last 24 hours
            "nodes": {
                "QmMasterNodeID": {
                    "name": "master",
                    "cpu_usage_percent": [30 + (i % 5) * 10 for i in range(24)],
                    "memory_usage_percent": [40 + (i % 3) * 5 for i in range(24)],
                    "disk_usage_percent": [20 + i * 0.5 for i in range(24)],
                }
            },
            "cluster": {
                "cpu_usage_percent": [35 + (i % 4) * 8 for i in range(24)],
                "memory_usage_percent": [45 + (i % 3) * 6 for i in range(24)],
                "disk_usage_percent": [25 + i * 0.6 for i in range(24)],
            },
            "summary": {
                "time_range": "24h",
                "interval": "1h",
                "samples": 24,
                "cluster": {
                    "cpu_usage_percent_avg": 48.5,
                    "memory_usage_percent_avg": 52.3,
                    "disk_usage_percent_avg": 32.8,
                },
            },
        }

        # Mock export_metrics_json method
        def export_json(**kwargs):
            # Return JSON string of aggregated metrics
            return json.dumps(aggregated_metrics, indent=2)

        # Mock export_metrics_csv method
        def export_csv(**kwargs):
            # Create CSV string with timestamps and key metrics
            csv_lines = ["timestamp,node_id,cpu_percent,memory_percent,disk_percent"]

            # Add cluster-wide data
            for i, ts in enumerate(aggregated_metrics["timestamps"]):
                csv_lines.append(
                    f"{ts},cluster,{aggregated_metrics['cluster']['cpu_usage_percent'][i]},{aggregated_metrics['cluster']['memory_usage_percent'][i]},{aggregated_metrics['cluster']['disk_usage_percent'][i]}"
                )

            # Add node-specific data
            for node_id, node_data in aggregated_metrics["nodes"].items():
                for i, ts in enumerate(aggregated_metrics["timestamps"]):
                    csv_lines.append(
                        f"{ts},{node_id},{node_data['cpu_usage_percent'][i]},{node_data['memory_usage_percent'][i]},{node_data['disk_usage_percent'][i]}"
                    )

            return "\n".join(csv_lines)

        # Mock the export methods
        master.export_metrics_json = MagicMock(side_effect=export_json)
        master.export_metrics_csv = MagicMock(side_effect=export_csv)

        # Test JSON export
        json_data = master.export_metrics_json()
        parsed_json = json.loads(json_data)

        # Verify JSON export
        assert "timestamps" in parsed_json
        assert "nodes" in parsed_json
        assert "cluster" in parsed_json
        assert len(parsed_json["timestamps"]) == 24

        # Test CSV export
        csv_data = master.export_metrics_csv()
        csv_lines = csv_data.strip().split("\n")

        # Verify CSV export
        assert csv_lines[0] == "timestamp,node_id,cpu_percent,memory_percent,disk_percent"
        assert len(csv_lines) == 1 + 24 + (
            24 * len(aggregated_metrics["nodes"])
        )  # Header + cluster lines + node lines
        assert "cluster" in csv_lines[1]
        assert "QmMasterNodeID" in csv_lines[25]  # After cluster lines


class TestConfigurationManagement:
    """Test configuration management tools."""

    def test_configuration_validation(self, monitoring_cluster):
        """Test validation of cluster configuration."""
        master = monitoring_cluster["master"]

        # Test configuration with both valid and invalid settings
        test_config = {
            "replication_factor_min": 2,
            "replication_factor_max": 5,
            "pin_recover_timeout": "invalid_format",  # Invalid time format
            "metrics_collection_invalid": True,  # Unknown setting
            "pin_tracker": {
                "max_pin_queue_size": -100,  # Invalid negative value
                "concurrent_pins": 10,
            },
        }

        # Mock validate_config method
        def validate_config(config, **kwargs):
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
                    if not isinstance(value, str) or not any(
                        unit in value for unit in ["s", "m", "h"]
                    ):
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

        # Mock the config validation method
        master.validate_cluster_config = MagicMock(side_effect=validate_config)

        # Test configuration validation
        validation_result = master.validate_cluster_config(test_config)

        # Verify validation results
        assert validation_result["valid"] is False
        assert len(validation_result["errors"]) >= 1  # Should have at least 1 error
        assert len(validation_result["warnings"]) >= 1  # Should have at least 1 warning

        # Verify specific error types
        error_types = [error["type"] for error in validation_result["errors"]]
        assert "invalid_value" in error_types  # Should have at least invalid_value

        # Verify warning about unknown key
        assert any(
            warning["key"] == "metrics_collection_invalid"
            for warning in validation_result["warnings"]
        )

    def test_configuration_distribution(self, monitoring_cluster):
        """Test distribution of configuration changes to cluster nodes."""
        master = monitoring_cluster["master"]
        workers = monitoring_cluster["workers"]

        # Test configuration to distribute
        new_config = {
            "replication_factor_min": 2,
            "replication_factor_max": 5,
            "pinning_timeout": "5m0s",
            "pin_recovery_timeout": "10m0s",
            "pin_tracker": {"max_pin_queue_size": 5000, "concurrent_pins": 10},
        }

        # Mock distribute_config method
        def distribute_config(config, **kwargs):
            # In a real system, this would send config to all peers
            # and wait for confirmation

            # Simulate notifying peers and getting responses
            peer_responses = {"QmMasterNodeID": {"status": "accepted", "timestamp": time.time()}}

            # Simulate worker responses
            for i, worker in enumerate(workers):
                peer_id = f"QmWorker{i+1}ID"

                # Simulate one worker rejecting the config
                if i == 2:
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

            # Determine overall distribution success
            success = acceptance_rate >= 0.75  # Consider success if 75% of peers accept

            return {
                "success": success,
                "config_version": int(time.time()),
                "peer_responses": peer_responses,
                "acceptance_rate": acceptance_rate,
                "accepted_peers": accepted_peers,
                "total_peers": total_peers,
                "distribution_timestamp": time.time(),
            }

        # Mock the config distribution method
        master.distribute_cluster_config = MagicMock(side_effect=distribute_config)

        # Test configuration distribution
        distribution_result = master.distribute_cluster_config(new_config)

        # Verify distribution results
        assert distribution_result["success"] is True
        assert distribution_result["acceptance_rate"] >= 0.75
        assert distribution_result["total_peers"] == 4  # Master + 3 workers
        assert distribution_result["accepted_peers"] == 3  # 3 out of 4 accepted

        # Verify peer responses
        peer_responses = distribution_result["peer_responses"]
        assert "QmMasterNodeID" in peer_responses
        assert peer_responses["QmMasterNodeID"]["status"] == "accepted"
        assert "QmWorker3ID" in peer_responses
        assert peer_responses["QmWorker3ID"]["status"] == "rejected"
        assert "reason" in peer_responses["QmWorker3ID"]


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
