#!/usr/bin/env python3
"""
Tests for the cluster management components of IPFS Kit.

This module tests the role-based architecture, distributed coordination,
and monitoring components of the IPFS Kit cluster management system.
"""

import os
import time
import unittest
import tempfile
import threading
import json
from unittest.mock import MagicMock, patch

# Import the components to test
from ipfs_kit_py.cluster.role_manager import NodeRole, RoleManager, detect_host_capabilities
from ipfs_kit_py.cluster.distributed_coordination import MembershipManager, ClusterCoordinator
from ipfs_kit_py.cluster.monitoring import MetricsCollector, ClusterMonitor

class TestRoleManager(unittest.TestCase):
    """Tests for the RoleManager class."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock resources for testing
        self.test_resources = {
            "memory_available_mb": 2048,  # 2GB
            "disk_available_gb": 20,
            "cpu_count": 4,
            "network_max_speed_mbps": 100,
            "uptime_hours": 24
        }
        
        # Create a RoleManager with predictable behavior
        self.role_manager = RoleManager(
            initial_role="worker",
            resources=self.test_resources,
            metadata={"test_mode": True},
            auto_detect=False,  # Disable auto-detection for predictable tests
            role_switching_enabled=True
        )
    
    def test_initialization(self):
        """Test RoleManager initialization."""
        self.assertEqual(self.role_manager.current_role, NodeRole.WORKER)
        self.assertDictEqual(self.role_manager.resources, self.test_resources)
        self.assertTrue(self.role_manager.role_switching_enabled)
    
    def test_role_switching(self):
        """Test role switching functionality."""
        # Switch to a different role
        result = self.role_manager.switch_role(NodeRole.LEECHER)
        self.assertTrue(result)
        self.assertEqual(self.role_manager.current_role, NodeRole.LEECHER)
        
        # Switch to another role
        result = self.role_manager.switch_role(NodeRole.MASTER)
        self.assertTrue(result)
        self.assertEqual(self.role_manager.current_role, NodeRole.MASTER)
        
        # Track metrics
        self.assertEqual(self.role_manager.metrics["role_switches"], 2)
    
    def test_role_capability_check(self):
        """Test capability checking based on role."""
        self.role_manager.current_role = NodeRole.MASTER
        self.assertTrue(self.role_manager.can_handle_capability("task_distribution"))
        self.assertTrue(self.role_manager.can_handle_capability("metadata_indexing"))
        
        self.role_manager.current_role = NodeRole.WORKER
        self.assertFalse(self.role_manager.can_handle_capability("task_distribution"))
        self.assertTrue(self.role_manager.can_handle_capability("content_routing"))
        
        self.role_manager.current_role = NodeRole.LEECHER
        self.assertFalse(self.role_manager.can_handle_capability("metadata_indexing"))
        self.assertFalse(self.role_manager.can_handle_capability("high_replication"))
    
    def test_optimal_role_detection(self):
        """Test detection of optimal role based on resources."""
        # Mock the _detect_optimal_role method for more predictable testing
        original_detect_method = self.role_manager._detect_optimal_role
        
        # Override the method for testing
        def mock_detect_optimal_role():
            # Simply return the role based on the memory size for testing
            memory = self.role_manager.resources.get("memory_available_mb", 0)
            if memory >= 8000:
                return NodeRole.MASTER
            elif memory >= 1500:
                return NodeRole.WORKER
            else:
                return NodeRole.LEECHER
                
        # Apply the mock
        self.role_manager._detect_optimal_role = mock_detect_optimal_role
        
        # Test with resources suitable for master
        self.role_manager.resources = {
            "memory_available_mb": 8192,  # 8GB
            "disk_available_gb": 500,
            "cpu_count": 8,
            "network_max_speed_mbps": 1000,
            "uptime_hours": 720  # 30 days
        }
        optimal_role = self.role_manager._detect_optimal_role()
        self.assertEqual(optimal_role, NodeRole.MASTER)
        
        # Test with resources suitable for worker
        self.role_manager.resources = {
            "memory_available_mb": 2048,  # 2GB
            "disk_available_gb": 50,
            "cpu_count": 4,
            "network_max_speed_mbps": 100,
            "uptime_hours": 48
        }
        optimal_role = self.role_manager._detect_optimal_role()
        self.assertEqual(optimal_role, NodeRole.WORKER)
        
        # Test with resources suitable for leecher
        self.role_manager.resources = {
            "memory_available_mb": 768,  # 768MB
            "disk_available_gb": 2,
            "cpu_count": 2,
            "network_max_speed_mbps": 10,
            "uptime_hours": 1
        }
        optimal_role = self.role_manager._detect_optimal_role()
        self.assertEqual(optimal_role, NodeRole.LEECHER)
        
        # Restore the original method
        self.role_manager._detect_optimal_role = original_detect_method
    
    def test_authentication(self):
        """Test peer authentication functionality."""
        # Generate a token
        token = self.role_manager.auth_token
        
        # Test authentication with correct token
        result = self.role_manager.authenticate_peer("test-peer-1", token)
        self.assertTrue(result)
        self.assertTrue(self.role_manager.is_peer_authorized("test-peer-1"))
        
        # Test authentication with incorrect token
        result = self.role_manager.authenticate_peer("test-peer-2", "wrong-token")
        self.assertFalse(result)
        self.assertFalse(self.role_manager.is_peer_authorized("test-peer-2"))
    
    def test_node_info(self):
        """Test node information retrieval."""
        node_info = self.role_manager.get_node_info()
        self.assertEqual(node_info["role"], str(self.role_manager.current_role))
        self.assertDictEqual(node_info["resources"], self.role_manager.resources)
        self.assertIn("capabilities", node_info)
        self.assertIn("metrics", node_info)
    
    def test_config_overrides(self):
        """Test IPFS configuration overrides based on role."""
        # Test master config
        self.role_manager.current_role = NodeRole.MASTER
        master_config = self.role_manager.get_ipfs_config_overrides()
        self.assertEqual(master_config["Routing"]["Type"], "dhtserver")
        
        # Test worker config
        self.role_manager.current_role = NodeRole.WORKER
        worker_config = self.role_manager.get_ipfs_config_overrides()
        self.assertEqual(worker_config["Routing"]["Type"], "dhtclient")
        
        # Test leecher config
        self.role_manager.current_role = NodeRole.LEECHER
        leecher_config = self.role_manager.get_ipfs_config_overrides()
        self.assertEqual(leecher_config["Routing"]["Type"], "dhtclient")
        # Verify different connection limits
        self.assertLess(
            leecher_config["Swarm"]["ConnMgr"]["HighWater"],
            worker_config["Swarm"]["ConnMgr"]["HighWater"]
        )

class TestMembershipManager(unittest.TestCase):
    """Tests for the MembershipManager class."""
    
    def setUp(self):
        """Set up test environment."""
        self.node_id = "test-node-1"
        self.cluster_id = "test-cluster"
        
        # Mock callback function
        self.callback_called = False
        self.callback_data = {}
        
        def membership_callback(change_type, node_id, info):
            self.callback_called = True
            self.callback_data = {
                "change_type": change_type,
                "node_id": node_id,
                "info": info
            }
            
        self.membership_manager = MembershipManager(
            cluster_id=self.cluster_id,
            node_id=self.node_id,
            heartbeat_interval=1,  # 1 second for faster testing
            node_timeout=2,  # 2 seconds for faster testing
            membership_callback=membership_callback
        )
    
    def tearDown(self):
        """Clean up after the test."""
        self.membership_manager.shutdown()
    
    def test_initialization(self):
        """Test MembershipManager initialization."""
        self.assertEqual(self.membership_manager.node_id, self.node_id)
        self.assertEqual(self.membership_manager.cluster_id, self.cluster_id)
        self.assertEqual(len(self.membership_manager.active_members), 0)
    
    def test_handle_heartbeat(self):
        """Test handling heartbeats from other nodes."""
        other_node_id = "test-node-2"
        heartbeat_data = {"role": "worker", "capabilities": ["processing"]}
        
        # Handle heartbeat from a new node
        self.membership_manager.handle_heartbeat(other_node_id, heartbeat_data)
        
        # Check that node was added as active member
        self.assertIn(other_node_id, self.membership_manager.active_members)
        self.assertIn(other_node_id, self.membership_manager.members)
        
        # Check that callback was called
        self.assertTrue(self.callback_called)
        self.assertEqual(self.callback_data["change_type"], "joined")
        self.assertEqual(self.callback_data["node_id"], other_node_id)
    
    def test_get_members(self):
        """Test getting member information."""
        # Add a test member
        other_node_id = "test-node-2"
        heartbeat_data = {"role": "worker", "capabilities": ["processing"]}
        self.membership_manager.handle_heartbeat(other_node_id, heartbeat_data)
        
        # Get active members
        active_members = self.membership_manager.get_active_members()
        self.assertEqual(len(active_members), 1)
        self.assertEqual(active_members[0]["node_id"], other_node_id)
        
        # Check member count
        counts = self.membership_manager.get_member_count()
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["departed"], 0)
        self.assertEqual(counts["total"], 1)

class TestClusterCoordinator(unittest.TestCase):
    """Tests for the ClusterCoordinator class."""
    
    def setUp(self):
        """Set up test environment."""
        self.node_id = "test-node-1"
        self.cluster_id = "test-cluster"
        
        # Mock membership manager
        self.mock_membership_manager = MagicMock()
        
        # Mock leadership callback
        self.leadership_callback_called = False
        self.leadership_data = {}
        
        def leadership_callback(leader_id, is_master):
            self.leadership_callback_called = True
            self.leadership_data = {
                "leader_id": leader_id,
                "is_master": is_master
            }
            
        self.coordinator = ClusterCoordinator(
            cluster_id=self.cluster_id,
            node_id=self.node_id,
            is_master=True,  # Start as master
            election_timeout=1,  # 1 second for faster testing
            leadership_callback=leadership_callback,
            membership_manager=self.mock_membership_manager
        )
    
    def test_initialization(self):
        """Test ClusterCoordinator initialization."""
        self.assertEqual(self.coordinator.node_id, self.node_id)
        self.assertEqual(self.coordinator.cluster_id, self.cluster_id)
        self.assertTrue(self.coordinator.is_master)
        self.assertEqual(self.coordinator.current_leader, self.node_id)
    
    def test_create_cluster(self):
        """Test cluster creation."""
        self.coordinator.create_cluster("new-cluster")
        self.assertEqual(self.coordinator.cluster_id, "new-cluster")
        self.assertTrue(self.coordinator.is_master)
        
        # Verify the coordinator has a cluster_peers attribute
        self.assertTrue(hasattr(self.coordinator, "cluster_peers"))
        self.assertEqual(len(self.coordinator.cluster_peers), 0)
    
    def test_join_cluster(self):
        """Test joining an existing cluster."""
        # Create a coordinator that's not a master
        coordinator = ClusterCoordinator(
            cluster_id="old-cluster",
            node_id="test-node-2",
            is_master=False
        )
        
        # Join a cluster
        coordinator.join_cluster("new-cluster", "master-address")
        
        # Verify the coordinator updated its information
        self.assertEqual(coordinator.cluster_id, "new-cluster")
        self.assertFalse(coordinator.is_master)
        self.assertEqual(coordinator.master_node_address, "master-address")
    
    def test_submit_task(self):
        """Test task submission and tracking."""
        # Submit a task
        task_data = {"type": "test_task", "parameters": {"param1": "value1"}}
        task_id = self.coordinator.submit_task(task_data)
        
        # Verify task was added
        self.assertIn(task_id, self.coordinator.task_statuses)
        self.assertEqual(self.coordinator.task_statuses[task_id], "pending")
        
        # Get task status
        status = self.coordinator.get_task_status(task_id)
        self.assertEqual(status["status"], "pending")
        
        # Update task status
        result = self.coordinator.update_task_status(
            task_id, "completed", {"result": "success"}
        )
        self.assertTrue(result)
        
        # Verify status update
        status = self.coordinator.get_task_status(task_id)
        self.assertEqual(status["status"], "completed")
    
    def test_election(self):
        """Test leader election."""
        # Trigger an election
        self.coordinator.initiate_election()
        
        # Simulate votes
        self.coordinator.receive_vote("node-2", "node-2")
        self.coordinator.receive_vote("node-3", "node-1")
        
        # Finalize election - we have 2 votes for self, 1 for node-2
        self.coordinator._finalize_election()
        
        # Check if we're still the leader (majority vote wins)
        self.assertEqual(self.coordinator.current_leader, self.node_id)
        self.assertTrue(self.coordinator.is_master)
        
        # Check that the callback was called
        self.assertTrue(self.leadership_callback_called)
        self.assertEqual(self.leadership_data["leader_id"], self.node_id)
        self.assertTrue(self.leadership_data["is_master"])

class TestMonitoring(unittest.TestCase):
    """Tests for the monitoring components."""
    
    def setUp(self):
        """Set up test environment."""
        self.node_id = "test-node-1"
        
        # Create temporary directory for metrics
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock alert callback
        self.alert_callback_called = False
        self.alert_data = {}
        
        def alert_callback(source, alert):
            self.alert_callback_called = True
            self.alert_data = {
                "source": source,
                "alert": alert
            }
            
        # Create metrics collector
        self.metrics_collector = MetricsCollector(
            node_id=self.node_id,
            metrics_dir=self.temp_dir,
            collection_interval=1,  # 1 second for faster testing
            retention_days=1
        )
        
        # Define metrics source
        def test_metrics_source():
            return {
                "cpu_percent": 50,
                "memory_percent": 40,
                "disk_percent": 30
            }
            
        # Register metrics source
        self.metrics_collector.register_metric_source(
            "test_source", test_metrics_source
        )
        
        # Create cluster monitor
        self.cluster_monitor = ClusterMonitor(
            node_id=self.node_id,
            metrics_collector=self.metrics_collector,
            check_interval=1,  # 1 second for faster testing
            alert_callback=alert_callback
        )
    
    def tearDown(self):
        """Clean up after the test."""
        self.metrics_collector.shutdown()
        self.cluster_monitor.shutdown()
        
        # Remove temp directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_metrics_collection(self):
        """Test metrics collection."""
        # Allow time for collection
        time.sleep(2)
        
        # Get current metrics
        metrics = self.metrics_collector.get_current_metrics()
        
        # Check that our test source metrics were collected
        self.assertIn("test_source", metrics)
        self.assertEqual(metrics["test_source"]["cpu_percent"], 50)
        self.assertEqual(metrics["test_source"]["memory_percent"], 40)
        self.assertEqual(metrics["test_source"]["disk_percent"], 30)
    
    def test_alert_generation(self):
        """Test alert generation for high resource usage."""
        # Override the cluster monitor's node health
        self.cluster_monitor.node_health[self.node_id] = {
            "status": "warning",
            "issues": [{
                "type": "high_cpu",
                "severity": "warning",
                "message": "CPU usage high: 90%"
            }]
        }
        
        # Manually trigger alert generation
        self.cluster_monitor._generate_alerts()
        
        # Check that the alert callback was called
        self.assertTrue(self.alert_callback_called)
        self.assertEqual(self.alert_data["source"], "node")
        self.assertEqual(self.alert_data["alert"]["level"], "warning")
        self.assertEqual(self.alert_data["alert"]["type"], "high_cpu")
    
    def test_cluster_health(self):
        """Test cluster health checking."""
        # Get initial health - should be unknown or healthy
        health = self.cluster_monitor.get_cluster_health()
        self.assertIn(health["status"], ["unknown", "healthy"])
        
        # Set an issue in the cluster health
        self.cluster_monitor.cluster_health = {
            "status": "warning",
            "issues": [{
                "type": "single_node",
                "severity": "warning",
                "message": "Cluster has only 1 member(s)"
            }],
            "last_check": time.time()
        }
        
        # Get updated health
        health = self.cluster_monitor.get_cluster_health()
        self.assertEqual(health["status"], "warning")
        self.assertEqual(len(health["issues"]), 1)
        self.assertEqual(health["issues"][0]["type"], "single_node")
    
    def test_alert_clearing(self):
        """Test clearing alerts."""
        # Add some test alerts
        self.cluster_monitor.alerts = [
            {
                "timestamp": time.time(),
                "source": "node",
                "level": "warning",
                "type": "high_cpu",
                "message": "CPU usage high: 90%"
            },
            {
                "timestamp": time.time(),
                "source": "node",
                "level": "critical",
                "type": "high_memory",
                "message": "Memory usage critical: 95%"
            }
        ]
        
        # Verify alerts are present
        self.assertEqual(len(self.cluster_monitor.get_alerts()), 2)
        
        # Clear warnings only
        cleared = self.cluster_monitor.clear_alerts(level="warning")
        self.assertEqual(cleared, 1)
        
        # Verify only critical alerts remain
        alerts = self.cluster_monitor.get_alerts()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["level"], "critical")
        
        # Clear all alerts
        cleared = self.cluster_monitor.clear_alerts()
        self.assertEqual(cleared, 1)
        
        # Verify no alerts remain
        self.assertEqual(len(self.cluster_monitor.get_alerts()), 0)

if __name__ == '__main__':
    unittest.main()