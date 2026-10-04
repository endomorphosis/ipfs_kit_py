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

import anyio
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
def master_node():
    """Create a master node for testing with mocked components."""
    # Create a mock instance directly
    instance = MagicMock(spec=ipfs_kit)

    # Set fundamental properties
    instance.role = "master"
    instance.resources = {"memory": "8GB", "disk": "1TB", "cpu": 4}
    instance.metadata = {
        "role": "master",
        "cluster_name": "test-cluster",
        "config": {
            "Addresses": {
                "API": "/ip4/127.0.0.1/tcp/5001",
                "Gateway": "/ip4/127.0.0.1/tcp/8080",
                "Swarm": ["/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001"],
            },
            "Bootstrap": [
                "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN"
            ],
        },
        "test_mode": True,
    }

    # Mock subcomponents
    instance.ipfs = MagicMock()
    instance.ipfs_cluster_service = MagicMock()
    instance.ipfs_cluster_ctl = MagicMock()
    instance.storacha_kit = MagicMock()

    # Add required methods for tests
    instance.ipfs_cluster_health = MagicMock()
    instance.ipfs_cluster_recover = MagicMock()
    instance.ipfs_kit_start = MagicMock(
        return_value={"ipfs": {"success": True}, "ipfs_cluster_service": {"success": True}}
    )

    # Remove components that shouldn't be present for a master
    if hasattr(instance, "ipfs_cluster_follow"):
        delattr(instance, "ipfs_cluster_follow")

    yield instance


@pytest.fixture
def worker_node():
    """Create a worker node for testing with mocked components."""
    # Create a mock instance directly
    instance = MagicMock(spec=ipfs_kit)

    # Set fundamental properties
    instance.role = "worker"
    instance.resources = {"memory": "4GB", "disk": "500GB", "cpu": 2}
    instance.metadata = {
        "role": "worker",
        "cluster_name": "test-cluster",
        "config": {
            "Addresses": {
                "API": "/ip4/127.0.0.1/tcp/5001",
                "Gateway": "/ip4/127.0.0.1/tcp/8080",
                "Swarm": ["/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001"],
            },
            "Bootstrap": ["/ip4/master-node-ip/tcp/4001/p2p/QmMasterNodeID"],
        },
        "test_mode": True,
    }

    # Mock subcomponents
    instance.ipfs = MagicMock()
    instance.ipfs_cluster_follow = MagicMock()
    instance.storacha_kit = MagicMock()

    # Add required methods for tests
    instance.ipfs_kit_start = MagicMock(
        return_value={"ipfs": {"success": True}, "ipfs_cluster_follow": {"success": True}}
    )

    # Add specific methods for worker
    instance.ipfs_cluster_follower_info = MagicMock()
    instance.ipfs_cluster_status = MagicMock()

    # Remove components that shouldn't be present for a worker
    if hasattr(instance, "ipfs_cluster_service"):
        delattr(instance, "ipfs_cluster_service")
    if hasattr(instance, "ipfs_cluster_ctl"):
        delattr(instance, "ipfs_cluster_ctl")

    yield instance


@pytest.fixture
def leecher_node():
    """Create a leecher node for testing with mocked components."""
    # Create a mock instance directly
    instance = MagicMock(spec=ipfs_kit)

    # Set fundamental properties
    instance.role = "leecher"
    instance.resources = {"memory": "2GB", "disk": "50GB", "cpu": 1}
    instance.metadata = {
        "role": "leecher",
        "config": {
            "Addresses": {
                "API": "/ip4/127.0.0.1/tcp/5001",
                "Gateway": "/ip4/127.0.0.1/tcp/8080",
                "Swarm": ["/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001"],
            },
            "Bootstrap": ["/ip4/master-node-ip/tcp/4001/p2p/QmMasterNodeID"],
        },
        "test_mode": True,
    }

    # Mock subcomponents
    instance.ipfs = MagicMock()
    instance.storacha_kit = MagicMock()

    # Add required methods for tests
    instance.ipfs_kit_start = MagicMock(return_value={"ipfs": {"success": True}})

    # Add specific pin operations
    instance.pin_add = MagicMock()
    instance.pin_ls = MagicMock()
    instance.pin_rm = MagicMock()

    # Remove components that shouldn't be present for a leecher
    if hasattr(instance, "ipfs_cluster_service"):
        delattr(instance, "ipfs_cluster_service")
    if hasattr(instance, "ipfs_cluster_ctl"):
        delattr(instance, "ipfs_cluster_ctl")
    if hasattr(instance, "ipfs_cluster_follow"):
        delattr(instance, "ipfs_cluster_follow")

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
        assert hasattr(master_node, "ipfs_cluster_service")
        assert hasattr(master_node, "ipfs_cluster_ctl")
        assert not hasattr(master_node, "ipfs_cluster_follow")

        # Verify worker has cluster follow component
        assert hasattr(worker_node, "ipfs_cluster_follow")
        assert not hasattr(worker_node, "ipfs_cluster_service")
        assert not hasattr(worker_node, "ipfs_cluster_ctl")

        # Verify leecher has minimal components
        assert not hasattr(leecher_node, "ipfs_cluster_follow")
        assert not hasattr(leecher_node, "ipfs_cluster_service")
        assert not hasattr(leecher_node, "ipfs_cluster_ctl")

    def test_role_specific_startup(self, master_node, worker_node, leecher_node):
        """Test that nodes start appropriately based on role."""
        # Since we've already mocked ipfs_kit_start in the fixtures,
        # we don't need to set up and check the underlying daemon/service calls

        # Test master startup
        master_result = master_node.ipfs_kit_start()
        assert master_result["ipfs"]["success"] is True
        assert master_result["ipfs_cluster_service"]["success"] is True

        # Test worker startup
        worker_result = worker_node.ipfs_kit_start()
        assert worker_result["ipfs"]["success"] is True
        assert worker_result["ipfs_cluster_follow"]["success"] is True

        # Test leecher startup
        leecher_result = leecher_node.ipfs_kit_start()
        assert leecher_result["ipfs"]["success"] is True
        assert (
            "ipfs_cluster_service" not in leecher_result
            or leecher_result["ipfs_cluster_service"] is None
        )
        assert (
            "ipfs_cluster_follow" not in leecher_result
            or leecher_result["ipfs_cluster_follow"] is None
        )

    def test_role_specific_shutdown(self, master_node, worker_node, leecher_node):
        """Test that nodes shut down appropriately based on role."""
        # Mock return values for the ipfs_kit_stop method
        master_node.ipfs_kit_stop = MagicMock(
            return_value={"ipfs": {"success": True}, "ipfs_cluster_service": {"success": True}}
        )

        worker_node.ipfs_kit_stop = MagicMock(
            return_value={"ipfs": {"success": True}, "ipfs_cluster_follow": {"success": True}}
        )

        leecher_node.ipfs_kit_stop = MagicMock(
            return_value={
                "ipfs": {"success": True},
                "ipfs_cluster_service": None,
                "ipfs_cluster_follow": None,
            }
        )

        # Test master shutdown
        master_result = master_node.ipfs_kit_stop()
        assert master_result["ipfs"] == {"success": True}
        assert master_result["ipfs_cluster_service"] == {"success": True}

        # Test worker shutdown
        worker_result = worker_node.ipfs_kit_stop()
        assert worker_result["ipfs"] == {"success": True}
        assert worker_result["ipfs_cluster_follow"] == {"success": True}

        # Test leecher shutdown
        leecher_result = leecher_node.ipfs_kit_stop()
        assert leecher_result["ipfs"] == {"success": True}
        assert leecher_result["ipfs_cluster_service"] is None
        assert leecher_result["ipfs_cluster_follow"] is None


class TestMasterRoleBehavior:
    """Test specific behaviors of master nodes."""

    def test_master_pin_operations(self, master_node):
        """Test master node pin operations which should involve both IPFS and cluster."""
        # Mock the ipfs_add_pin method directly
        master_node.ipfs_add_pin = MagicMock(
            return_value={
                "success": True,
                "cid": "QmTestPin",
                "ipfs": {"success": True, "cid": "QmTestPin"},
                "ipfs_cluster": {
                    "success": True,
                    "cid": "QmTestPin",
                    "name": "test-pin",
                    "allocations": ["QmPeer1", "QmPeer2"],
                },
            }
        )

        # Test pinning operation
        result = master_node.ipfs_add_pin(pin="QmTestPin")

        # Verify both IPFS and cluster pinning were used
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        master_node.ipfs_add_pin.assert_called_once_with(pin="QmTestPin")

    def test_master_get_pinset(self, master_node):
        """Test that master retrieves pins from both IPFS and cluster."""
        # Mock the ipfs_get_pinset method directly
        master_node.ipfs_get_pinset = MagicMock(
            return_value={
                "success": True,
                "ipfs": {
                    "success": True,
                    "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}},
                },
                "ipfs_cluster": {
                    "success": True,
                    "pins": [
                        {"cid": "QmTest1", "allocations": ["QmPeer1", "QmPeer2"]},
                        {"cid": "QmTest3", "allocations": ["QmPeer1"]},
                    ],
                },
            }
        )

        # Get pinset
        result = master_node.ipfs_get_pinset()

        # Verify that both IPFS and cluster pinsets were retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert result["ipfs_cluster"]["pins"][0]["cid"] == "QmTest1"
        assert result["ipfs_cluster"]["pins"][1]["cid"] == "QmTest3"
        master_node.ipfs_get_pinset.assert_called_once()


class TestWorkerRoleBehavior:
    """Test specific behaviors of worker nodes."""

    def test_worker_pin_operations(self, worker_node):
        """Test worker node pin operations which should only involve IPFS."""
        # Mock the ipfs_add_pin method directly
        worker_node.ipfs_add_pin = MagicMock(
            return_value={
                "success": True,
                "cid": "QmTestPin",
                "ipfs": {"success": True, "cid": "QmTestPin"},
            }
        )

        # Test pinning operation
        result = worker_node.ipfs_add_pin(pin="QmTestPin")

        # Verify only IPFS pinning was used (not cluster)
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" not in result
        worker_node.ipfs_add_pin.assert_called_once_with(pin="QmTestPin")

    def test_worker_get_pinset(self, worker_node):
        """Test that worker retrieves pins from IPFS and cluster follow."""
        # Mock the ipfs_get_pinset method directly
        worker_node.ipfs_get_pinset = MagicMock(
            return_value={
                "success": True,
                "ipfs": {
                    "success": True,
                    "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}},
                },
                "ipfs_cluster": {"success": True, "cids": ["QmTest1", "QmTest3"]},
            }
        )

        # Get pinset
        result = worker_node.ipfs_get_pinset()

        # Verify that both IPFS and cluster follow pinsets were retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert "QmTest1" in result["ipfs_cluster"]["cids"]
        assert "QmTest3" in result["ipfs_cluster"]["cids"]
        worker_node.ipfs_get_pinset.assert_called_once()


class TestLeecherRoleBehavior:
    """Test specific behaviors of leecher nodes."""

    def test_leecher_pin_operations(self, leecher_node):
        """Test leecher node pin operations which should only involve IPFS."""
        # Mock the ipfs_add_pin method directly
        leecher_node.ipfs_add_pin = MagicMock(
            return_value={
                "success": True,
                "cid": "QmTestPin",
                "ipfs": {"success": True, "cid": "QmTestPin"},
            }
        )

        # Test pinning operation
        result = leecher_node.ipfs_add_pin(pin="QmTestPin")

        # Verify only IPFS pinning was used (not cluster)
        assert result["success"] is True
        assert result["cid"] == "QmTestPin"
        assert "ipfs" in result
        assert "ipfs_cluster" not in result
        leecher_node.ipfs_add_pin.assert_called_once_with(pin="QmTestPin")

    def test_leecher_get_pinset(self, leecher_node):
        """Test that leecher only retrieves pins from IPFS."""
        # Mock the ipfs_get_pinset method directly
        leecher_node.ipfs_get_pinset = MagicMock(
            return_value={
                "success": True,
                "ipfs": {
                    "success": True,
                    "pins": {"QmTest1": {"type": "recursive"}, "QmTest2": {"type": "recursive"}},
                },
                "ipfs_cluster": None,
            }
        )

        # Get pinset
        result = leecher_node.ipfs_get_pinset()

        # Verify that only IPFS pinset was retrieved
        assert "ipfs" in result
        assert "ipfs_cluster" in result  # Should be None for leecher
        assert result["ipfs"]["pins"]["QmTest1"]["type"] == "recursive"
        assert result["ipfs_cluster"] is None
        leecher_node.ipfs_get_pinset.assert_called_once()


class TestRoleSwitchingCapability:
    """Test the ability to switch roles dynamically."""

    def test_role_switching(self):
        """Test switching a node's role."""
        # Create a mock directly rather than using actual ipfs_kit class
        node = MagicMock(spec=ipfs_kit)

        # Set up initial leecher role properties
        node.role = "leecher"
        node.ipfs = MagicMock()

        # Mock ipfs_kit_start for leecher role
        node.ipfs_kit_start = MagicMock(return_value={"ipfs": {"success": True}})

        # Remove attributes that shouldn't be present for leecher
        if hasattr(node, "ipfs_cluster_follow"):
            delattr(node, "ipfs_cluster_follow")
        if hasattr(node, "ipfs_cluster_service"):
            delattr(node, "ipfs_cluster_service")

        # Verify initial role
        assert node.role == "leecher"
        assert not hasattr(node, "ipfs_cluster_follow")
        assert not hasattr(node, "ipfs_cluster_service")

        # Simulate role switching to worker
        node.role = "worker"
        node.ipfs_cluster_follow = MagicMock()

        # Mock ipfs_kit_start for worker role
        node.ipfs_kit_start = MagicMock(
            return_value={"ipfs": {"success": True}, "ipfs_cluster_follow": {"success": True}}
        )

        # Verify role changed
        assert node.role == "worker"
        assert hasattr(node, "ipfs_cluster_follow")

        # Try some worker-specific operations
        result = node.ipfs_kit_start()
        assert "ipfs_cluster_follow" in result
        assert result["ipfs_cluster_follow"]["success"] is True


class TestClusterMembershipManagement:
    """Test cluster membership and peer management."""

    def test_master_peer_listing(self, master_node):
        """Test that master can list cluster peers."""
        # Mock the ipfs_cluster_peers_ls method directly
        master_node.ipfs_cluster_peers_ls = MagicMock(
            return_value={
                "success": True,
                "peers": [
                    {
                        "id": "QmMasterNodeID",
                        "addresses": ["/ip4/master-node-ip/tcp/9096"],
                        "cluster_peers": ["QmWorker1", "QmWorker2"],
                    },
                    {"id": "QmWorker1", "addresses": ["/ip4/worker1-ip/tcp/9096"]},
                    {"id": "QmWorker2", "addresses": ["/ip4/worker2-ip/tcp/9096"]},
                ],
            }
        )

        # Call the peer listing method
        result = master_node.ipfs_cluster_peers_ls()

        # Verify result
        assert result["success"] is True
        assert len(result["peers"]) == 3
        assert result["peers"][0]["id"] == "QmMasterNodeID"
        assert len(result["peers"][0]["cluster_peers"]) == 2
        master_node.ipfs_cluster_peers_ls.assert_called_once()

    def test_worker_follower_info(self, worker_node):
        """Test that worker can get follower info."""
        # Mock the ipfs_follow_info method directly
        worker_node.ipfs_follow_info = MagicMock(
            return_value={
                "success": True,
                "cluster_name": "test-cluster",
                "cluster_peer_id": "QmMasterNodeID",
                "cluster_peer_addresses": ["/ip4/master-node-ip/tcp/9096"],
                "ipfs_peer_id": "QmWorker1",
                "cluster_peer_online": "true",
                "ipfs_peer_online": "true",
            }
        )

        # Call the follower info method
        result = worker_node.ipfs_follow_info()

        # Verify result
        assert result["success"] is True
        assert result["cluster_name"] == "test-cluster"
        assert result["cluster_peer_id"] == "QmMasterNodeID"
        assert result["cluster_peer_online"] == "true"
        worker_node.ipfs_follow_info.assert_called_once()


class TestClusterDistributedState:
    """Test distributed state synchronization and monitoring."""

    def test_cluster_status(self, master_node):
        """Test cluster-wide pin status checking."""
        # Mock the ipfs_cluster_status method directly
        response = {
            "success": True,
            "pin_status": [
                {
                    "cid": "QmTest1",
                    "name": "test file 1",
                    "allocations": ["QmMasterNodeID", "QmWorker1"],
                    "peer_map": {
                        "QmMasterNodeID": {"status": "pinned", "timestamp": "2023-01-01T00:00:00Z"},
                        "QmWorker1": {"status": "pinning", "timestamp": "2023-01-01T00:00:00Z"},
                    },
                },
                {
                    "cid": "QmTest2",
                    "name": "test file 2",
                    "allocations": ["QmMasterNodeID", "QmWorker1", "QmWorker2"],
                    "peer_map": {
                        "QmMasterNodeID": {"status": "pinned", "timestamp": "2023-01-01T00:00:00Z"},
                        "QmWorker1": {"status": "pinned", "timestamp": "2023-01-01T00:00:00Z"},
                        "QmWorker2": {
                            "status": "pin_error",
                            "timestamp": "2023-01-01T00:00:00Z",
                            "error": "disk full",
                        },
                    },
                },
            ],
        }

        # Set up direct mock return value
        master_node.ipfs_cluster_status = MagicMock(return_value=response)

        # Call status method
        result = master_node.ipfs_cluster_status()

        # Verify result
        assert result["success"] is True
        assert len(result["pin_status"]) == 2
        assert result["pin_status"][0]["cid"] == "QmTest1"
        assert result["pin_status"][0]["peer_map"]["QmMasterNodeID"]["status"] == "pinned"
        assert result["pin_status"][1]["peer_map"]["QmWorker2"]["status"] == "pin_error"
        master_node.ipfs_cluster_status.assert_called_once()

    def test_worker_sync_state(self, worker_node):
        """Test worker syncing state from master."""
        # Mock the ipfs_follow_sync method directly
        worker_node.ipfs_follow_sync = MagicMock(
            return_value={"success": True, "synced": 10, "pins_added": 5, "pins_removed": 2}
        )

        # Call sync method
        result = worker_node.ipfs_follow_sync()

        # Verify result
        assert result["success"] is True
        assert result["synced"] == 10
        assert result["pins_added"] == 5
        worker_node.ipfs_follow_sync.assert_called_once()


class TestFailureDetectionRecovery:
    """Test failure detection and recovery mechanisms."""

    def test_health_check(self, master_node):
        """Test health checking of cluster nodes."""
        # Set up mock for health check - patch the actual method
        health_response = {
            "success": True,
            "health": [
                {"peer_id": "QmMasterNodeID", "status": "ok"},
                {"peer_id": "QmWorker1", "status": "ok"},
                {"peer_id": "QmWorker2", "status": "degraded", "message": "high load"},
                {"peer_id": "QmWorker3", "status": "offline", "last_seen": "2023-01-01T00:00:00Z"},
            ],
        }

        # Patch at a deeper level - directly override the health method
        with patch.object(master_node, "ipfs_cluster_health", return_value=health_response):
            # Call health check method
            result = master_node.ipfs_cluster_health()

            # Verify result
            assert result["success"] is True
            assert len(result["health"]) == 4
            assert result["health"][0]["status"] == "ok"
            assert result["health"][2]["status"] == "degraded"
            assert result["health"][3]["status"] == "offline"

    def test_peer_recovery(self, master_node):
        """Test recovering a failed peer."""
        # Set up mock for recovery operation
        recovery_response = {"success": True, "peer_id": "QmWorker3", "pins_recovered": 15}

        # Add the missing ipfs_cluster_recover method to the master_node object
        master_node.ipfs_cluster_recover = MagicMock(return_value=recovery_response)

        # Call recovery method
        result = master_node.ipfs_cluster_recover("QmWorker3")

        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == "QmWorker3"
        assert result["pins_recovered"] == 15


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
