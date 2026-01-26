#!/usr/bin/env python3
"""Cluster services legacy test (skipped).

This suite depended on `enhanced_daemon_manager_with_cluster` which is no longer
part of the active codebase. Retained for historical reference; skipped to keep
CI green while cluster subsystem is unmaintained.
"""

import pytest
pytest.skip("Cluster services subsystem deprecated / module missing", allow_module_level=True)

# Original content below retained for reference (not executed):
# ---------------------------------------------------------------------------

import pytest
import anyio
import threading
import time
import json
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# (Imports removed due to skip)

# Test configuration
CLUSTER_TEST_TIMEOUT = 30  # seconds
MAX_CONCURRENT_OPERATIONS = 10

class TestNodeRole:
    """Test the NodeRole enum and priority system"""
    
    def test_role_values(self):
        """Test that roles have correct string values"""
        assert NodeRole.MASTER.value == "master"
        assert NodeRole.WORKER.value == "worker"
        assert NodeRole.LEECHER.value == "leecher"
    
    def test_role_priorities(self):
        """Test that role priorities are correct for leader election"""
        assert NodeRole.get_priority(NodeRole.MASTER) == 0
        assert NodeRole.get_priority(NodeRole.WORKER) == 1
        assert NodeRole.get_priority(NodeRole.LEECHER) == 999
        
        # Master should have highest priority (lowest number)
        assert NodeRole.get_priority(NodeRole.MASTER) < NodeRole.get_priority(NodeRole.WORKER)
        assert NodeRole.get_priority(NodeRole.WORKER) < NodeRole.get_priority(NodeRole.LEECHER)


class TestPeerInfo:
    """Test the PeerInfo dataclass"""
    
    def test_peer_info_creation(self):
        """Test creating PeerInfo instances"""
        peer = PeerInfo(
            id="test-peer",
            role=NodeRole.MASTER,
            address="127.0.0.1",
            port=9998
        )
        
        assert peer.id == "test-peer"
        assert peer.role == NodeRole.MASTER
        assert peer.address == "127.0.0.1"
        assert peer.port == 9998
        assert peer.is_healthy is True
        assert isinstance(peer.last_seen, datetime)
    
    def test_peer_info_to_dict(self):
        """Test converting PeerInfo to dictionary"""
        peer = PeerInfo(
            id="test-peer",
            role=NodeRole.WORKER,
            address="192.168.1.1",
            port=10000,
            capabilities={"storage": True, "compute": False}
        )
        
        peer_dict = peer.to_dict()
        
        assert peer_dict["id"] == "test-peer"
        assert peer_dict["role"] == "worker"
        assert peer_dict["address"] == "192.168.1.1"
        assert peer_dict["port"] == 10000
        assert peer_dict["is_healthy"] is True
        assert "last_seen" in peer_dict
        assert peer_dict["capabilities"]["storage"] is True


class TestLeaderElection:
    """Test the leader election system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.peers = {
            "master-1": PeerInfo("master-1", NodeRole.MASTER, "127.0.0.1", 9998),
            "master-2": PeerInfo("master-2", NodeRole.MASTER, "127.0.0.1", 9999),
            "worker-1": PeerInfo("worker-1", NodeRole.WORKER, "127.0.0.1", 10000),
            "worker-2": PeerInfo("worker-2", NodeRole.WORKER, "127.0.0.1", 10001),
            "leecher-1": PeerInfo("leecher-1", NodeRole.LEECHER, "127.0.0.1", 10002),
        }
    
    def test_master_node_election(self):
        """Test that master node is elected as leader"""
        election = LeaderElection("master-1", NodeRole.MASTER, self.peers)
        leader = election.elect_leader()
        
        assert leader is not None
        assert leader.id == "master-1"  # Should elect self as master with lowest ID
        assert leader.role == NodeRole.MASTER
    
    def test_worker_node_election_without_masters(self):
        """Test worker election when no masters available"""
        # Remove masters from peers
        worker_peers = {k: v for k, v in self.peers.items() if v.role != NodeRole.MASTER}
        
        election = LeaderElection("worker-1", NodeRole.WORKER, worker_peers)
        leader = election.elect_leader()
        
        assert leader is not None
        assert leader.role == NodeRole.WORKER
        assert leader.id == "worker-1"  # Should elect self as first worker
    
    def test_leecher_cannot_be_leader(self):
        """Test that leechers are never elected as leaders"""
        # Only leechers in cluster
        leecher_peers = {k: v for k, v in self.peers.items() if v.role == NodeRole.LEECHER}
        
        election = LeaderElection("leecher-1", NodeRole.LEECHER, leecher_peers)
        leader = election.elect_leader()
        
        assert leader is None  # No eligible leader
    
    def test_role_hierarchy_priority(self):
        """Test that role hierarchy is respected in election"""
        election = LeaderElection("worker-1", NodeRole.WORKER, self.peers)
        leader = election.elect_leader()
        
        # Should elect a master, not the worker running the election
        assert leader is not None
        assert leader.role == NodeRole.MASTER
        assert leader.id in ["master-1", "master-2"]
    
    def test_deterministic_election(self):
        """Test that elections are deterministic with same inputs"""
        election1 = LeaderElection("worker-1", NodeRole.WORKER, self.peers)
        election2 = LeaderElection("worker-2", NodeRole.WORKER, self.peers)
        
        leader1 = election1.elect_leader()
        leader2 = election2.elect_leader()
        
        # Both should elect the same leader
        assert leader1.id == leader2.id
        assert leader1.role == leader2.role
    
    def test_unhealthy_peer_exclusion(self):
        """Test that unhealthy peers are excluded from election"""
        # Mark master-1 as unhealthy
        self.peers["master-1"].is_healthy = False
        
        election = LeaderElection("worker-1", NodeRole.WORKER, self.peers)
        leader = election.elect_leader()
        
        # Should elect master-2, not the unhealthy master-1
        assert leader is not None
        assert leader.id == "master-2"
        assert leader.role == NodeRole.MASTER
    
    def test_heartbeat_monitoring(self):
        """Test heartbeat monitoring functionality"""
        election = LeaderElection("worker-1", NodeRole.WORKER, self.peers)
        
        # Simulate receiving heartbeat
        leader_id = "master-1"
        election.receive_heartbeat(leader_id)
        
        assert leader_id in election.last_heartbeat
        assert isinstance(election.last_heartbeat[leader_id], datetime)
    
    def test_leader_health_check(self):
        """Test leader health checking"""
        election = LeaderElection("worker-1", NodeRole.WORKER, self.peers)
        election.current_leader = self.peers["master-1"]
        
        # No heartbeat received - should be unhealthy
        assert election.check_leader_health() is False
        
        # Receive recent heartbeat - should be healthy
        election.receive_heartbeat("master-1")
        assert election.check_leader_health() is True
        
        # Old heartbeat - should be unhealthy
        old_time = datetime.now() - timedelta(seconds=election.heartbeat_interval * 4)
        election.last_heartbeat["master-1"] = old_time
        assert election.check_leader_health() is False


class TestReplicationManager:
    """Test the replication management system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_ipfs_kit = Mock()
        self.mock_ipfs_kit.role = NodeRole.MASTER
    
    def test_master_can_initiate_replication(self):
        """Test that master nodes can initiate replication"""
        manager = ReplicationManager(NodeRole.MASTER, self.mock_ipfs_kit)
        
        assert manager.can_initiate_replication() is True
    
    def test_worker_cannot_initiate_replication(self):
        """Test that worker nodes cannot initiate replication"""
        manager = ReplicationManager(NodeRole.WORKER, self.mock_ipfs_kit)
        
        assert manager.can_initiate_replication() is False
    
    def test_leecher_cannot_initiate_replication(self):
        """Test that leecher nodes cannot initiate replication"""
        manager = ReplicationManager(NodeRole.LEECHER, self.mock_ipfs_kit)
        
        assert manager.can_initiate_replication() is False
    
    def test_master_and_worker_can_receive_replication(self):
        """Test that master and worker nodes can receive replication"""
        master_manager = ReplicationManager(NodeRole.MASTER, self.mock_ipfs_kit)
        worker_manager = ReplicationManager(NodeRole.WORKER, self.mock_ipfs_kit)
        
        assert master_manager.can_receive_replication() is True
        assert worker_manager.can_receive_replication() is True
    
    def test_leecher_cannot_receive_replication(self):
        """Test that leecher nodes cannot receive replication"""
        manager = ReplicationManager(NodeRole.LEECHER, self.mock_ipfs_kit)
        
        assert manager.can_receive_replication() is False
    
    @pytest.mark.anyio
    async def test_replication_from_master(self):
        """Test successful replication from master node"""
        manager = ReplicationManager(NodeRole.MASTER, self.mock_ipfs_kit)
        
        target_peers = [
            PeerInfo("worker-1", NodeRole.WORKER, "127.0.0.1", 10000),
            PeerInfo("master-2", NodeRole.MASTER, "127.0.0.1", 9999),
        ]
        
        result = await manager.replicate_content("QmTestCID123", target_peers)
        
        assert result["success"] is True
        assert result["cid"] == "QmTestCID123"
        assert result["target_count"] == 2
        assert "results" in result
    
    @pytest.mark.anyio
    async def test_replication_from_non_master_fails(self):
        """Test that replication from non-master nodes fails"""
        manager = ReplicationManager(NodeRole.WORKER, self.mock_ipfs_kit)
        
        target_peers = [
            PeerInfo("master-1", NodeRole.MASTER, "127.0.0.1", 9998),
        ]
        
        result = await manager.replicate_content("QmTestCID123", target_peers)
        
        assert result["success"] is False
        assert "Only master nodes can initiate replication" in result["message"]
    
    @pytest.mark.anyio
    async def test_replication_filters_invalid_targets(self):
        """Test that replication filters out invalid target peers"""
        manager = ReplicationManager(NodeRole.MASTER, self.mock_ipfs_kit)
        
        target_peers = [
            PeerInfo("worker-1", NodeRole.WORKER, "127.0.0.1", 10000),
            PeerInfo("leecher-1", NodeRole.LEECHER, "127.0.0.1", 10002),  # Should be filtered out
            PeerInfo("master-2", NodeRole.MASTER, "127.0.0.1", 9999),
        ]
        target_peers[1].is_healthy = False  # Also mark leecher as unhealthy
        
        result = await manager.replicate_content("QmTestCID123", target_peers)
        
        assert result["success"] is True
        assert result["target_count"] == 2  # Only worker and master, leecher filtered out
    
    def test_replication_status_tracking(self):
        """Test replication status tracking"""
        manager = ReplicationManager(NodeRole.MASTER, self.mock_ipfs_kit)
        
        # Initially no tasks
        status = manager.get_replication_status()
        assert status["total_tasks"] == 0
        
        # Add a task manually for testing
        task = ReplicationTask("QmTestCID123", ["peer-1", "peer-2"])
        manager.replication_tasks["test-task"] = task
        
        status = manager.get_replication_status()
        assert status["total_tasks"] == 1
        
        # Get specific task status
        task_status = manager.get_replication_status("test-task")
        assert task_status["cid"] == "QmTestCID123"
        assert task_status["target_peers"] == ["peer-1", "peer-2"]


class TestIndexingService:
    """Test the indexing service system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        pass
    
    def test_master_can_modify_index(self):
        """Test that master nodes can modify indexes"""
        service = IndexingService(NodeRole.MASTER)
        
        assert service.can_modify_index() is True
    
    def test_non_master_cannot_modify_index(self):
        """Test that non-master nodes cannot modify indexes"""
        worker_service = IndexingService(NodeRole.WORKER)
        leecher_service = IndexingService(NodeRole.LEECHER)
        
        assert worker_service.can_modify_index() is False
        assert leecher_service.can_modify_index() is False
    
    def test_all_nodes_can_read_index(self):
        """Test that all node types can read indexes"""
        master_service = IndexingService(NodeRole.MASTER)
        worker_service = IndexingService(NodeRole.WORKER)
        leecher_service = IndexingService(NodeRole.LEECHER)
        
        assert master_service.can_read_index() is True
        assert worker_service.can_read_index() is True
        assert leecher_service.can_read_index() is True
    
    @pytest.mark.anyio
    async def test_add_index_data_master(self):
        """Test adding index data from master node"""
        service = IndexingService(NodeRole.MASTER)
        
        test_data = {"vector": [0.1, 0.2, 0.3], "content": "test document"}
        result = await service.add_index_data("embeddings", "doc-1", test_data)
        
        assert result["success"] is True
        assert result["key"] == "doc-1"
        assert result["index_type"] == "embeddings"
    
    @pytest.mark.anyio
    async def test_add_index_data_non_master_fails(self):
        """Test that adding index data from non-master fails"""
        service = IndexingService(NodeRole.WORKER)
        
        test_data = {"vector": [0.1, 0.2, 0.3], "content": "test document"}
        result = await service.add_index_data("embeddings", "doc-1", test_data)
        
        assert result["success"] is False
        assert "Only master nodes can modify indexes" in result["message"]
    
    @pytest.mark.anyio
    async def test_remove_index_data_master(self):
        """Test removing index data from master node"""
        service = IndexingService(NodeRole.MASTER)
        
        # First add data
        test_data = {"vector": [0.1, 0.2, 0.3], "content": "test document"}
        await service.add_index_data("embeddings", "doc-1", test_data)
        
        # Then remove it
        result = await service.remove_index_data("embeddings", "doc-1")
        
        assert result["success"] is True
    
    @pytest.mark.anyio
    async def test_remove_nonexistent_data(self):
        """Test removing non-existent index data"""
        service = IndexingService(NodeRole.MASTER)
        
        result = await service.remove_index_data("embeddings", "nonexistent-key")
        
        assert result["success"] is False
        assert "not found" in result["message"]
    
    @pytest.mark.anyio
    async def test_get_index_data_single_key(self):
        """Test retrieving single key from index"""
        service = IndexingService(NodeRole.MASTER)
        
        # Add test data
        test_data = {"vector": [0.1, 0.2, 0.3], "content": "test document"}
        await service.add_index_data("embeddings", "doc-1", test_data)
        
        # Retrieve it
        result = await service.get_index_data("embeddings", "doc-1")
        
        assert result["success"] is True
        assert result["key"] == "doc-1"
        assert result["data"]["data"] == test_data
    
    @pytest.mark.anyio
    async def test_get_index_data_all_keys(self):
        """Test retrieving all keys from index"""
        service = IndexingService(NodeRole.MASTER)
        
        # Add multiple test entries
        test_data_1 = {"vector": [0.1, 0.2, 0.3], "content": "document 1"}
        test_data_2 = {"vector": [0.4, 0.5, 0.6], "content": "document 2"}
        
        await service.add_index_data("embeddings", "doc-1", test_data_1)
        await service.add_index_data("embeddings", "doc-2", test_data_2)
        
        # Retrieve all
        result = await service.get_index_data("embeddings")
        
        assert result["success"] is True
        assert result["total_entries"] == 2
        assert "doc-1" in result["data"]
        assert "doc-2" in result["data"]
    
    @pytest.mark.anyio
    async def test_invalid_index_type(self):
        """Test operations with invalid index type"""
        service = IndexingService(NodeRole.MASTER)
        
        result = await service.add_index_data("invalid_type", "key", {"data": "value"})
        
        assert result["success"] is False
        assert "Invalid index type" in result["message"]
    
    @pytest.mark.anyio
    async def test_embedding_search(self):
        """Test embedding similarity search"""
        service = IndexingService(NodeRole.MASTER)
        
        # Add test embeddings
        embedding_1 = {"vector": [0.1, 0.2, 0.3], "content": "document 1"}
        embedding_2 = {"vector": [0.4, 0.5, 0.6], "content": "document 2"}
        
        await service.add_index_data("embeddings", "doc-1", embedding_1)
        await service.add_index_data("embeddings", "doc-2", embedding_2)
        
        # Search for similar embeddings
        query_vector = [0.2, 0.3, 0.4]
        result = await service.search_embeddings(query_vector, top_k=2)
        
        assert result["success"] is True
        assert len(result["results"]) <= 2
        assert result["query_vector_dim"] == 3
    
    def test_index_statistics(self):
        """Test getting index statistics"""
        service = IndexingService(NodeRole.MASTER)
        
        stats = service.get_index_stats()
        
        assert stats["node_role"] == "master"
        assert stats["total_indexes"] == 5  # Should have 5 index types
        assert "indexes" in stats
        
        # Check each index type
        for index_type in ["embeddings", "peer_lists", "knowledge_graph", "content_metadata", "replication_state"]:
            assert index_type in stats["indexes"]
            assert stats["indexes"][index_type]["can_modify"] is True
            assert stats["indexes"][index_type]["can_read"] is True
    
    def test_thread_safety(self):
        """Test thread safety of index operations"""
        service = IndexingService(NodeRole.MASTER)
        errors = []
        results = []
        
        def add_data(thread_id):
            try:
                async def async_add():
                    result = await service.add_index_data(
                        "embeddings", 
                        f"doc-{thread_id}", 
                        {"vector": [thread_id, thread_id, thread_id], "content": f"document {thread_id}"}
                    )
                    return result
                
                result = anyio.run(async_add)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=add_data, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Thread safety test failed with errors: {errors}"
        assert len(results) == 10
        assert all(result["success"] for result in results)


class TestEnhancedDaemonManager:
    """Test the enhanced daemon manager with cluster capabilities"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Mock the base daemon manager to avoid actual daemon operations
        with patch('enhanced_daemon_manager_with_cluster.BaseDaemonManager.__init__', return_value=None):
            self.manager = EnhancedDaemonManager(
                node_id="test-node",
                node_role=NodeRole.MASTER,
                daemon_type="ipfs"
            )
    
    def test_manager_initialization(self):
        """Test enhanced daemon manager initialization"""
        assert self.manager.node_id == "test-node"
        assert self.manager.node_role == NodeRole.MASTER
        assert isinstance(self.manager.leader_election, LeaderElection)
        assert isinstance(self.manager.replication_manager, ReplicationManager)
        assert isinstance(self.manager.indexing_service, IndexingService)
    
    def test_add_peer(self):
        """Test adding peers to the cluster"""
        peer = PeerInfo("peer-1", NodeRole.WORKER, "127.0.0.1", 10000)
        
        self.manager.add_peer(peer)
        
        assert "peer-1" in self.manager.peers
        assert self.manager.peers["peer-1"] == peer
    
    def test_remove_peer(self):
        """Test removing peers from the cluster"""
        peer = PeerInfo("peer-1", NodeRole.WORKER, "127.0.0.1", 10000)
        self.manager.add_peer(peer)
        
        self.manager.remove_peer("peer-1")
        
        assert "peer-1" not in self.manager.peers
    
    def test_cluster_status(self):
        """Test getting cluster status"""
        # Add some test peers
        peer1 = PeerInfo("peer-1", NodeRole.WORKER, "127.0.0.1", 10000)
        peer2 = PeerInfo("peer-2", NodeRole.LEECHER, "127.0.0.1", 10001)
        
        self.manager.add_peer(peer1)
        self.manager.add_peer(peer2)
        
        status = self.manager.get_cluster_status()
        
        assert status["node_info"]["id"] == "test-node"
        assert status["node_info"]["role"] == "master"
        assert status["cluster_info"]["total_peers"] == 2
        assert status["cluster_info"]["healthy_peers"] == 2
        assert status["services"]["replication_manager"]["can_initiate"] is True
        assert status["services"]["indexing_service"]["node_role"] == "master"
    
    @patch('enhanced_daemon_manager_with_cluster.subprocess.Popen')
    def test_start_mcp_server(self, mock_popen):
        """Test starting MCP server subprocess"""
        mock_process = Mock()
        mock_popen.return_value = mock_process
        
        self.manager._start_mcp_server()
        
        assert self.manager.mcp_server_process == mock_process
        mock_popen.assert_called_once()
    
    def test_health_monitoring_setup(self):
        """Test health monitoring thread setup"""
        with patch('enhanced_daemon_manager_with_cluster.threading.Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            self.manager._start_health_monitoring()
            
            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()


class TestConcurrencyAndPerformance:
    """Test concurrency and performance aspects"""
    
    @pytest.mark.anyio
    async def test_concurrent_replication_operations(self):
        """Test concurrent replication operations"""
        manager = ReplicationManager(NodeRole.MASTER, Mock())
        
        # Create multiple replication tasks
        tasks = []
        for i in range(5):
            target_peers = [
                PeerInfo(f"worker-{i}", NodeRole.WORKER, "127.0.0.1", 10000 + i)
            ]
            task = manager.replicate_content(f"QmTestCID{i}", target_peers)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = []
        async with anyio.create_task_group() as task_group:
            async def run_task(task_coro):
                try:
                    result = await task_coro
                except Exception as exc:
                    result = exc
                results.append(result)

            for task in tasks:
                task_group.start_soon(run_task, task)
        
        # Check all succeeded
        for result in results:
            assert not isinstance(result, Exception)
            assert result["success"] is True
    
    @pytest.mark.anyio
    async def test_concurrent_indexing_operations(self):
        """Test concurrent indexing operations"""
        service = IndexingService(NodeRole.MASTER)
        
        # Create multiple indexing tasks
        tasks = []
        for i in range(10):
            task = service.add_index_data(
                "embeddings",
                f"doc-{i}",
                {"vector": [i, i, i], "content": f"document {i}"}
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = []
        async with anyio.create_task_group() as task_group:
            async def run_task(task_coro):
                try:
                    result = await task_coro
                except Exception as exc:
                    result = exc
                results.append(result)

            for task in tasks:
                task_group.start_soon(run_task, task)
        
        # Check all succeeded
        for result in results:
            assert not isinstance(result, Exception)
            assert result["success"] is True
        
        # Verify all data was added correctly
        all_data = await service.get_index_data("embeddings")
        assert all_data["total_entries"] == 10
    
    def test_leader_election_performance(self):
        """Test leader election performance with large peer sets"""
        # Create a large set of peers
        peers = {}
        for i in range(100):
            role = NodeRole.MASTER if i < 10 else NodeRole.WORKER if i < 50 else NodeRole.LEECHER
            peers[f"peer-{i}"] = PeerInfo(f"peer-{i}", role, "127.0.0.1", 9000 + i)
        
        # Time the election
        start_time = time.time()
        election = LeaderElection("peer-50", NodeRole.WORKER, peers)
        leader = election.elect_leader()
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 1.0  # Less than 1 second
        assert leader is not None
        assert leader.role == NodeRole.MASTER


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.anyio
    async def test_replication_with_no_eligible_peers(self):
        """Test replication when no peers are eligible"""
        manager = ReplicationManager(NodeRole.MASTER, Mock())
        
        # Only leecher peers (not eligible for replication)
        target_peers = [
            PeerInfo("leecher-1", NodeRole.LEECHER, "127.0.0.1", 10000),
            PeerInfo("leecher-2", NodeRole.LEECHER, "127.0.0.1", 10001),
        ]
        
        result = await manager.replicate_content("QmTestCID123", target_peers)
        
        assert result["success"] is False
        assert "No eligible target peers" in result["message"]
    
    @pytest.mark.anyio
    async def test_indexing_with_invalid_permissions(self):
        """Test indexing operations with invalid permissions"""
        service = IndexingService(NodeRole.LEECHER)
        
        # Try to add data as leecher
        result = await service.add_index_data("embeddings", "doc-1", {"data": "test"})
        
        assert result["success"] is False
        assert "Only master nodes can modify indexes" in result["message"]
    
    def test_leader_election_with_empty_peer_set(self):
        """Test leader election with no peers"""
        election = LeaderElection("lonely-node", NodeRole.MASTER, {})
        leader = election.elect_leader()
        
        # Should elect self as leader
        assert leader is not None
        assert leader.id == "lonely-node"
        assert leader.role == NodeRole.MASTER
    
    def test_leader_election_with_all_unhealthy_peers(self):
        """Test leader election when all peers are unhealthy"""
        peers = {
            "peer-1": PeerInfo("peer-1", NodeRole.MASTER, "127.0.0.1", 9998),
            "peer-2": PeerInfo("peer-2", NodeRole.WORKER, "127.0.0.1", 10000),
        }
        
        # Mark all peers as unhealthy
        for peer in peers.values():
            peer.is_healthy = False
        
        election = LeaderElection("healthy-node", NodeRole.WORKER, peers)
        leader = election.elect_leader()
        
        # Should elect self as only healthy node
        assert leader is not None
        assert leader.id == "healthy-node"
        assert leader.role == NodeRole.WORKER


# Test fixtures and utilities
@pytest.fixture
def cluster_setup():
    """Fixture to set up a test cluster"""
    managers = {}
    
    # Create different node types
    for node_type, role in [("master-1", NodeRole.MASTER), ("worker-1", NodeRole.WORKER), ("leecher-1", NodeRole.LEECHER)]:
        with patch('enhanced_daemon_manager_with_cluster.BaseDaemonManager.__init__', return_value=None):
            manager = EnhancedDaemonManager(
                node_id=node_type,
                node_role=role,
                daemon_type="ipfs"
            )
        managers[node_type] = manager
    
    # Set up peer relationships
    all_peers = {}
    for node_id, manager in managers.items():
        peer = PeerInfo(node_id, manager.node_role, "127.0.0.1", 9998)
        all_peers[node_id] = peer
    
    for node_id, manager in managers.items():
        for peer_id, peer in all_peers.items():
            if peer_id != node_id:
                manager.add_peer(peer)
    
    return managers


class TestIntegrationScenarios:
    """Integration tests for complete cluster scenarios"""
    
    def test_cluster_bootstrap(self, cluster_setup):
        """Test complete cluster bootstrap scenario"""
        managers = cluster_setup
        
        # Each node should elect the same leader
        leaders = {}
        for node_id, manager in managers.items():
            leader = manager.leader_election.elect_leader()
            leaders[node_id] = leader
        
        # All nodes should agree on the same leader
        unique_leaders = set(leader.id for leader in leaders.values())
        assert len(unique_leaders) == 1
        
        # Leader should be a master
        elected_leader = list(leaders.values())[0]
        assert elected_leader.role == NodeRole.MASTER
    
    @pytest.mark.anyio
    async def test_full_cluster_workflow(self, cluster_setup):
        """Test a complete cluster workflow"""
        managers = cluster_setup
        master_manager = managers["master-1"]
        
        # 1. Leader election
        leader = master_manager.leader_election.elect_leader()
        assert leader.role == NodeRole.MASTER
        
        # 2. Add data to index (master only)
        result = await master_manager.indexing_service.add_index_data(
            "embeddings",
            "workflow-doc",
            {"vector": [1.0, 2.0, 3.0], "content": "workflow test"}
        )
        assert result["success"] is True
        
        # 3. Replicate content (master only)
        target_peers = [peer for peer in master_manager.peers.values() 
                       if peer.role in [NodeRole.MASTER, NodeRole.WORKER]]
        
        replication_result = await master_manager.replication_manager.replicate_content(
            "QmWorkflowTest",
            target_peers
        )
        assert replication_result["success"] is True
        
        # 4. Check cluster status
        status = master_manager.get_cluster_status()
        assert status["services"]["replication_manager"]["can_initiate"] is True
        assert status["services"]["indexing_service"]["node_role"] == "master"


if __name__ == "__main__":
    # Run tests directly if executed as script
    pytest.main([__file__, "-v", "--tb=short"])
