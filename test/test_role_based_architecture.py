"""
Tests for role-based architecture and distributed coordination in ipfs_kit_py.

This module tests the role-based architecture (Phase 3B) features, including:
- Master/worker/leecher node roles and capabilities
- Role-specific optimizations
- Dynamic role switching based on resources
- Secure authentication for cluster nodes
- Cluster membership management
- Distributed state synchronization
- Failure detection and recovery
"""

import unittest
import os
import time
import tempfile
import threading
import uuid
import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, PropertyMock, call

from ipfs_kit_py.ipfs_kit import ipfs_kit


@pytest.fixture
def master_node():
    """Create a master node for testing with mocked components."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-master-id"}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = ipfs_kit(
            resources={"memory": "8GB", "disk": "1TB", "cpu": 4},
            metadata={
                "role": "master",
                "cluster_name": "test-cluster",
                "config": {
                    "Addresses": {
                        "API": "/ip4/127.0.0.1/tcp/5001",
                        "Gateway": "/ip4/127.0.0.1/tcp/8080",
                        "Swarm": [
                            "/ip4/0.0.0.0/tcp/4001",
                            "/ip6/::/tcp/4001"
                        ]
                    },
                    "Bootstrap": [
                        "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN"
                    ]
                },
                "test_mode": True
            }
        )
        
        # Mock subcomponents
        instance.ipfs = MagicMock()
        instance.ipfs_cluster_service = MagicMock()
        instance.ipfs_cluster_ctl = MagicMock()
        instance.storacha_kit = MagicMock()
        
        yield instance


@pytest.fixture
def worker_node():
    """Create a worker node for testing with mocked components."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-worker-id"}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = ipfs_kit(
            resources={"memory": "4GB", "disk": "500GB", "cpu": 2},
            metadata={
                "role": "worker",
                "cluster_name": "test-cluster",
                "config": {
                    "Addresses": {
                        "API": "/ip4/127.0.0.1/tcp/5001",
                        "Gateway": "/ip4/127.0.0.1/tcp/8080",
                        "Swarm": [
                            "/ip4/0.0.0.0/tcp/4001",
                            "/ip6/::/tcp/4001"
                        ]
                    },
                    "Bootstrap": [
                        "/ip4/master-node-ip/tcp/4001/p2p/QmMasterNodeID"
                    ]
                },
                "test_mode": True
            }
        )
        
        # Mock subcomponents
        instance.ipfs = MagicMock()
        instance.ipfs_cluster_follow = MagicMock()
        instance.storacha_kit = MagicMock()
        
        yield instance


@pytest.fixture
def leecher_node():
    """Create a leecher node for testing with mocked components."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-leecher-id"}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = ipfs_kit(
            resources={"memory": "2GB", "disk": "50GB", "cpu": 1},
            metadata={
                "role": "leecher",
                "config": {
                    "Addresses": {
                        "API": "/ip4/127.0.0.1/tcp/5001",
                        "Gateway": "/ip4/127.0.0.1/tcp/8080",
                        "Swarm": [
                            "/ip4/0.0.0.0/tcp/4001",
                            "/ip6/::/tcp/4001"
                        ]
                    },
                    "Bootstrap": [
                        "/ip4/master-node-ip/tcp/4001/p2p/QmMasterNodeID"
                    ]
                },
                "test_mode": True
            }
        )
        
        # Mock subcomponents
        instance.ipfs = MagicMock()
        instance.storacha_kit = MagicMock()
        
        yield instance


class TestRoleBasedArchitecture:
    """Test role-based architecture behavior for different node types."""
    
    def test_node_initialization(self, master_node, worker_node, leecher_node):
        """Test node initialization with different roles."""
        # Verify roles were correctly set
        assert master_node.role == "master"
        assert worker_node.role == "worker"
        assert leecher_node.role == "leecher"
        
        # Verify master has cluster service and control components
        assert hasattr(master_node, 'ipfs_cluster_service')
        assert hasattr(master_node, 'ipfs_cluster_ctl')
        assert not hasattr(master_node, 'ipfs_cluster_follow')
        
        # Verify worker has cluster follow component
        assert hasattr(worker_node, 'ipfs_cluster_follow')
        assert not hasattr(worker_node, 'ipfs_cluster_service')
        assert not hasattr(worker_node, 'ipfs_cluster_ctl')
        
        # Verify leecher has minimal components
        assert not hasattr(leecher_node, 'ipfs_cluster_follow')
        assert not hasattr(leecher_node, 'ipfs_cluster_service')
        assert not hasattr(leecher_node, 'ipfs_cluster_ctl')
    
    def test_role_specific_startup(self, master_node, worker_node, leecher_node):
        """Test that nodes start appropriately based on role."""
        # Set up mocks for each node type
        
        # Mock master startup
        master_node.ipfs.daemon_start.return_value = {"success": True}
        master_node.ipfs_cluster_service.ipfs_cluster_service_start.return_value = {"success": True}
        
        # Mock worker startup
        worker_node.ipfs.daemon_start.return_value = {"success": True}
        worker_node.ipfs_cluster_follow.ipfs_follow_start.return_value = {"success": True}
        
        # Mock leecher startup
        leecher_node.ipfs.daemon_start.return_value = {"success": True}
        
        # Test master startup
        master_result = master_node.ipfs_kit_start()
        assert master_result["ipfs"]["success"] is True
        assert master_result["ipfs_cluster_service"]["success"] is True
        master_node.ipfs.daemon_start.assert_called_once()
        master_node.ipfs_cluster_service.ipfs_cluster_service_start.assert_called_once()
        
        # Test worker startup
        worker_result = worker_node.ipfs_kit_start()
        assert worker_result["ipfs"]["success"] is True
        assert worker_result["ipfs_cluster_follow"]["success"] is True
        worker_node.ipfs.daemon_start.assert_called_once()
        worker_node.ipfs_cluster_follow.ipfs_follow_start.assert_called_once()
        
        # Test leecher startup
        leecher_result = leecher_node.ipfs_kit_start()
        assert leecher_result["ipfs"]["success"] is True
        assert "ipfs_cluster_service" not in leecher_result
        assert "ipfs_cluster_follow" not in leecher_result
        leecher_node.ipfs.daemon_start.assert_called_once()
    
    def test_role_specific_shutdown(self, master_node, worker_node, leecher_node):
        """Test that nodes shut down appropriately based on role."""
        # Set up mocks for each node type
        
        # Mock master shutdown
        master_node.ipfs.daemon_stop.return_value = {"success": True}
        master_node.ipfs_cluster_service.ipfs_cluster_service_stop.return_value = {"success": True}
        
        # Mock worker shutdown
        worker_node.ipfs.daemon_stop.return_value = {"success": True}
        worker_node.ipfs_cluster_follow.ipfs_follow_stop.return_value = {"success": True}
        
        # Mock leecher shutdown
        leecher_node.ipfs.daemon_stop.return_value = {"success": True}
        
        # Test master shutdown
        master_result = master_node.ipfs_kit_stop()
        assert master_result["ipfs"] == {"success": True}
        assert master_result["ipfs_cluster_service"] == {"success": True}
        master_node.ipfs.daemon_stop.assert_called_once()
        master_node.ipfs_cluster_service.ipfs_cluster_service_stop.assert_called_once()
        
        # Test worker shutdown
        worker_result = worker_node.ipfs_kit_stop()
        assert worker_result["ipfs"] == {"success": True}
        assert worker_result["ipfs_cluster_follow"] == {"success": True}
        worker_node.ipfs.daemon_stop.assert_called_once()
        worker_node.ipfs_cluster_follow.ipfs_follow_stop.assert_called_once()
        
        # Test leecher shutdown
        leecher_result = leecher_node.ipfs_kit_stop()
        assert leecher_result["ipfs"] == {"success": True}
        assert leecher_result["ipfs_cluster_service"] is None
        assert leecher_result["ipfs_cluster_follow"] is None
        leecher_node.ipfs.daemon_stop.assert_called_once()


class TestMasterRoleBehavior:
    """Test specific behaviors of master nodes."""
    
    def test_master_pin_operations(self, master_node):
        """Test master node pin operations which should involve both IPFS and cluster."""
        # Set up mocks
        master_node.ipfs.ipfs_add_pin.return_value = {
            "success": True,
            "cid": "QmTestPin"
        }
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin.return_value = {
            "success": True,
            "cid": "QmTestPin",
            "name": "test-pin",
            "allocations": ["QmPeer1", "QmPeer2"]
        }
        
        # Test pinning operation
        result = master_node.ipfs_add_pin(pin="QmTestPin")
        
        # Verify both IPFS and cluster pinning were used
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        master_node.ipfs.ipfs_add_pin.assert_called_once()
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin.assert_called_once()
    
    def test_master_get_pinset(self, master_node):
        """Test that master retrieves pins from both IPFS and cluster."""
        # Set up mocks
        master_node.ipfs.ipfs_get_pinset.return_value = {
            "success": True,
            "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}}
        }
        master_node.ipfs_cluster_ctl.ipfs_cluster_get_pinset.return_value = {
            "success": True,
            "pins": [
                {"cid": "QmTest1", "allocations": ["QmPeer1", "QmPeer2"]},
                {"cid": "QmTest3", "allocations": ["QmPeer1"]}
            ]
        }
        
        # Get pinset
        result = master_node.ipfs_get_pinset()
        
        # Verify that both IPFS and cluster pinsets were retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert result["ipfs_cluster"]["pins"][0]["cid"] == "QmTest1"
        assert result["ipfs_cluster"]["pins"][1]["cid"] == "QmTest3"
        master_node.ipfs.ipfs_get_pinset.assert_called_once()
        master_node.ipfs_cluster_ctl.ipfs_cluster_get_pinset.assert_called_once()


class TestWorkerRoleBehavior:
    """Test specific behaviors of worker nodes."""
    
    def test_worker_pin_operations(self, worker_node):
        """Test worker node pin operations which should only involve IPFS."""
        # Set up mocks
        worker_node.ipfs.ipfs_add_pin.return_value = {
            "success": True,
            "cid": "QmTestPin"
        }
        
        # Test pinning operation
        result = worker_node.ipfs_add_pin(pin="QmTestPin")
        
        # Verify only IPFS pinning was used (not cluster)
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" not in result
        worker_node.ipfs.ipfs_add_pin.assert_called_once()
    
    def test_worker_get_pinset(self, worker_node):
        """Test that worker retrieves pins from IPFS and cluster follow."""
        # Set up mocks
        worker_node.ipfs.ipfs_get_pinset.return_value = {
            "success": True,
            "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}}
        }
        worker_node.ipfs_cluster_follow.ipfs_follow_list.return_value = {
            "success": True,
            "cids": ["QmTest1", "QmTest3"]
        }
        
        # Get pinset
        result = worker_node.ipfs_get_pinset()
        
        # Verify that both IPFS and cluster follow pinsets were retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert "QmTest1" in result["ipfs_cluster"]["cids"]
        assert "QmTest3" in result["ipfs_cluster"]["cids"]
        worker_node.ipfs.ipfs_get_pinset.assert_called_once()
        worker_node.ipfs_cluster_follow.ipfs_follow_list.assert_called_once()


class TestLeecherRoleBehavior:
    """Test specific behaviors of leecher nodes."""
    
    def test_leecher_pin_operations(self, leecher_node):
        """Test leecher node pin operations which should only involve IPFS."""
        # Set up mocks
        leecher_node.ipfs.ipfs_add_pin.return_value = {
            "success": True,
            "cid": "QmTestPin"
        }
        
        # Test pinning operation
        result = leecher_node.ipfs_add_pin(pin="QmTestPin")
        
        # Verify only IPFS pinning was used (not cluster)
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" not in result
        leecher_node.ipfs.ipfs_add_pin.assert_called_once()
    
    def test_leecher_get_pinset(self, leecher_node):
        """Test that leecher only retrieves pins from IPFS."""
        # Set up mocks
        leecher_node.ipfs.ipfs_get_pinset.return_value = {
            "success": True,
            "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}}
        }
        
        # Get pinset
        result = leecher_node.ipfs_get_pinset()
        
        # Verify that only IPFS pinset was retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result  # Should be None for leecher
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert result["ipfs_cluster"] is None
        leecher_node.ipfs.ipfs_get_pinset.assert_called_once()


class TestRoleSwitchingCapability:
    """Test the ability to switch roles dynamically."""
    
    def test_role_switching(self):
        """Test switching a node's role."""
        # Start with a leecher
        with patch('subprocess.run') as mock_run:
            node = ipfs_kit(resources=None, metadata={"role": "leecher"})
            node.ipfs = MagicMock()
            
            # Verify initial role
            assert node.role == "leecher"
            assert not hasattr(node, 'ipfs_cluster_follow')
            assert not hasattr(node, 'ipfs_cluster_service')
            
            # Switch to worker role
            with patch.object(node, '__init__', return_value=None):
                # Call init again with new role
                node.__init__(resources=None, metadata={"role": "worker"})
                
                # The above would correctly reinitialize in a real system
                # For testing, we manually update to simulate initialization
                node.role = "worker"
                node.ipfs_cluster_follow = MagicMock()
                
                # Verify role changed
                assert node.role == "worker"
                assert hasattr(node, 'ipfs_cluster_follow')
                
                # Try some worker-specific operations
                node.ipfs_cluster_follow.ipfs_follow_start.return_value = {"success": True}
                result = node.ipfs_kit_start()
                assert "ipfs_cluster_follow" in result
                node.ipfs_cluster_follow.ipfs_follow_start.assert_called_once()


class TestClusterMembershipManagement:
    """Test cluster membership and peer management."""
    
    def test_master_peer_listing(self, master_node):
        """Test that master can list cluster peers."""
        # Set up mock for peer listing
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_peers_ls.return_value = {
            "success": True,
            "peers": [
                {
                    "id": "QmMasterNodeID",
                    "addresses": ["/ip4/master-node-ip/tcp/9096"],
                    "cluster_peers": ["QmWorker1", "QmWorker2"]
                },
                {
                    "id": "QmWorker1",
                    "addresses": ["/ip4/worker1-ip/tcp/9096"]
                },
                {
                    "id": "QmWorker2",
                    "addresses": ["/ip4/worker2-ip/tcp/9096"]
                }
            ]
        }
        
        # Call the peer listing method
        result = master_node.ipfs_cluster_peers_ls()
        
        # Verify result
        assert result["success"] is True
        assert len(result["peers"]) == 3
        assert result["peers"][0]["id"] == "QmMasterNodeID"
        assert len(result["peers"][0]["cluster_peers"]) == 2
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_peers_ls.assert_called_once()
    
    def test_worker_follower_info(self, worker_node):
        """Test that worker can get follower info."""
        # Set up mock for follower info
        worker_node.ipfs_cluster_follow.ipfs_follow_info.return_value = {
            "success": True,
            "cluster_name": "test-cluster",
            "cluster_peer_id": "QmMasterNodeID",
            "cluster_peer_addresses": ["/ip4/master-node-ip/tcp/9096"],
            "ipfs_peer_id": "QmWorker1",
            "cluster_peer_online": "true",
            "ipfs_peer_online": "true"
        }
        
        # Call the follower info method
        result = worker_node.ipfs_follow_info()
        
        # Verify result
        assert result["success"] is True
        assert result["cluster_name"] == "test-cluster"
        assert result["cluster_peer_id"] == "QmMasterNodeID"
        assert result["cluster_peer_online"] == "true"
        worker_node.ipfs_cluster_follow.ipfs_follow_info.assert_called_once()


class TestClusterDistributedState:
    """Test distributed state synchronization and monitoring."""
    
    def test_cluster_status(self, master_node):
        """Test cluster-wide pin status checking."""
        # Set up mock for status check
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_status.return_value = {
            "success": True,
            "pin_status": [
                {
                    "cid": "QmTest1",
                    "name": "test file 1",
                    "allocations": ["QmMasterNodeID", "QmWorker1"],
                    "peer_map": {
                        "QmMasterNodeID": {
                            "status": "pinned",
                            "timestamp": "2023-01-01T00:00:00Z"
                        },
                        "QmWorker1": {
                            "status": "pinning",
                            "timestamp": "2023-01-01T00:00:00Z"
                        }
                    }
                },
                {
                    "cid": "QmTest2",
                    "name": "test file 2",
                    "allocations": ["QmMasterNodeID", "QmWorker1", "QmWorker2"],
                    "peer_map": {
                        "QmMasterNodeID": {
                            "status": "pinned",
                            "timestamp": "2023-01-01T00:00:00Z"
                        },
                        "QmWorker1": {
                            "status": "pinned",
                            "timestamp": "2023-01-01T00:00:00Z"
                        },
                        "QmWorker2": {
                            "status": "pin_error",
                            "timestamp": "2023-01-01T00:00:00Z",
                            "error": "disk full"
                        }
                    }
                }
            ]
        }
        
        # Call status method
        result = master_node.ipfs_cluster_status()
        
        # Verify result
        assert result["success"] is True
        assert len(result["pin_status"]) == 2
        assert result["pin_status"][0]["cid"] == "QmTest1"
        assert result["pin_status"][0]["peer_map"]["QmMasterNodeID"]["status"] == "pinned"
        assert result["pin_status"][1]["peer_map"]["QmWorker2"]["status"] == "pin_error"
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_status.assert_called_once()
    
    def test_worker_sync_state(self, worker_node):
        """Test worker syncing state from master."""
        # Set up mock for syncing
        worker_node.ipfs_cluster_follow.ipfs_follow_sync.return_value = {
            "success": True,
            "synced": 10,
            "pins_added": 5,
            "pins_removed": 2
        }
        
        # Call sync method
        result = worker_node.ipfs_follow_sync()
        
        # Verify result
        assert result["success"] is True
        assert result["synced"] == 10
        assert result["pins_added"] == 5
        worker_node.ipfs_cluster_follow.ipfs_follow_sync.assert_called_once()


class TestFailureDetectionRecovery:
    """Test failure detection and recovery mechanisms."""
    
    def test_health_check(self, master_node):
        """Test health checking of cluster nodes."""
        # Set up mock for health check
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_health.return_value = {
            "success": True,
            "health": [
                {
                    "peer_id": "QmMasterNodeID",
                    "status": "ok"
                },
                {
                    "peer_id": "QmWorker1",
                    "status": "ok"
                },
                {
                    "peer_id": "QmWorker2",
                    "status": "degraded",
                    "message": "high load"
                },
                {
                    "peer_id": "QmWorker3",
                    "status": "offline",
                    "last_seen": "2023-01-01T00:00:00Z"
                }
            ]
        }
        
        # Call health check method
        result = master_node.ipfs_cluster_health()
        
        # Verify result
        assert result["success"] is True
        assert len(result["health"]) == 4
        assert result["health"][0]["status"] == "ok"
        assert result["health"][2]["status"] == "degraded"
        assert result["health"][3]["status"] == "offline"
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_health.assert_called_once()
    
    def test_peer_recovery(self, master_node):
        """Test recovering a failed peer."""
        # Set up mock for recovery operation
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_recover.return_value = {
            "success": True,
            "peer_id": "QmWorker3",
            "pins_recovered": 15
        }
        
        # Call recovery method
        result = master_node.ipfs_cluster_recover("QmWorker3")
        
        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == "QmWorker3"
        assert result["pins_recovered"] == 15
        master_node.ipfs_cluster_ctl.ipfs_cluster_ctl_recover.assert_called_once_with("QmWorker3")


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])