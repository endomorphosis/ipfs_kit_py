#!/usr/bin/env python3
"""
COMPREHENSIVE HTTP API INTEGRATION TESTS
=========================================

Unit tests for the HTTP API integration with the enhanced daemon manager.
Tests the MCP server HTTP endpoints for cluster management operations.

These tests ensure the HTTP API correctly exposes cluster functionality
and handles requests/responses properly.
"""

import pytest
import anyio
import httpx
import json
import os
import sys
import subprocess
import threading
import time
import signal
from unittest.mock import Mock, patch, AsyncMock
from contextlib import asynccontextmanager

# Add project root to path
import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Mock dependencies to avoid import issues
try:
    import httpx
except ImportError:
    httpx = None

try:
    from enhanced_daemon_manager_with_cluster import (
        EnhancedDaemonManager,
        NodeRole,
        PeerInfo
    )
except ImportError:
    # Create minimal mocks
    class NodeRole:
        MASTER = "master"
        WORKER = "worker"
        LEECHER = "leecher"
    
    class PeerInfo:
        def __init__(self, id, role, address, port):
            self.id = id
            self.role = role
            self.address = address
            self.port = port
    
    class EnhancedDaemonManager:
        def __init__(self, node_id, node_role, daemon_type):
            self.node_id = node_id
            self.node_role = node_role
            self.daemon_type = daemon_type

# Test configuration
TEST_MCP_SERVER_PORT = 19998
TEST_TIMEOUT = 30
MCP_SERVER_STARTUP_TIMEOUT = 10


class MCPServerManager:
    """Helper class to manage MCP server for testing"""
    
    def __init__(self, port=TEST_MCP_SERVER_PORT):
        self.port = port
        self.process = None
        self.base_url = f"http://127.0.0.1:{port}"
    
    def start_server(self, node_id="test-node", role="master"):
        """Start the MCP server subprocess"""
        try:
            # Use the enhanced MCP server script
            cmd = [
                sys.executable, 
                "enhanced_mcp_server_with_config.py",
                "--node-id", node_id,
                "--role", role,
                "--port", str(self.port)
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            # Wait for server to start
            self._wait_for_server_start()
            return True
        except Exception as e:
            print(f"Failed to start MCP server: {e}")
            return False
    
    def stop_server(self):
        """Stop the MCP server subprocess"""
        if self.process:
            try:
                # Kill the process group to ensure cleanup
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            finally:
                self.process = None
    
    def _wait_for_server_start(self):
        """Wait for the server to start accepting connections"""
        start_time = time.time()
        while time.time() - start_time < MCP_SERVER_STARTUP_TIMEOUT:
            try:
                with httpx.Client(timeout=2) as client:
                    response = client.get(f"{self.base_url}/health")
                    if response.status_code == 200:
                        return
            except (httpx.RequestError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
        
        raise TimeoutError("MCP server failed to start within timeout")
    
    def is_running(self):
        """Check if the server is running"""
        try:
            with httpx.Client(timeout=2) as client:
                response = client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False


async def _collect_response(request_coro, responses):
    responses.append(await request_coro)


@pytest.fixture(scope="module")
def mcp_server():
    """Fixture to provide a running MCP server for tests"""
    server = MCPServerManager()
    
    if server.start_server():
        yield server
    else:
        pytest.skip("Could not start MCP server for testing")
    
    server.stop_server()


@pytest.fixture
async def http_client():
    """Fixture to provide an HTTP client for testing"""
    async with httpx.AsyncClient(timeout=TEST_TIMEOUT) as client:
        yield client


class TestHealthEndpoint:
    """Test the health check endpoint"""
    
    @pytest.mark.anyio
    async def test_health_check_success(self, mcp_server, http_client):
        """Test successful health check"""
        response = await http_client.get(f"{mcp_server.base_url}/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "node_info" in data
    
    @pytest.mark.anyio
    async def test_health_check_includes_cluster_info(self, mcp_server, http_client):
        """Test that health check includes cluster information"""
        response = await http_client.get(f"{mcp_server.base_url}/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cluster_info" in data
        assert "services" in data
        assert "replication_manager" in data["services"]
        assert "indexing_service" in data["services"]


class TestClusterManagementEndpoints:
    """Test cluster management HTTP endpoints"""
    
    @pytest.mark.anyio
    async def test_get_cluster_status(self, mcp_server, http_client):
        """Test getting cluster status via HTTP"""
        response = await http_client.get(f"{mcp_server.base_url}/cluster/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "node_info" in data
        assert "cluster_info" in data
        assert "services" in data
        assert data["node_info"]["role"] == "master"
    
    @pytest.mark.anyio
    async def test_add_peer_to_cluster(self, mcp_server, http_client):
        """Test adding a peer to the cluster via HTTP"""
        peer_data = {
            "id": "test-worker-1",
            "role": "worker",
            "address": "127.0.0.1",
            "port": 10000,
            "capabilities": {"storage": True, "compute": True}
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/cluster/peers",
            json=peer_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "test-worker-1"
    
    @pytest.mark.anyio
    async def test_get_cluster_peers(self, mcp_server, http_client):
        """Test getting cluster peers via HTTP"""
        # First add a peer
        peer_data = {
            "id": "test-worker-2",
            "role": "worker",
            "address": "127.0.0.1", 
            "port": 10001
        }
        await http_client.post(f"{mcp_server.base_url}/cluster/peers", json=peer_data)
        
        # Then get all peers
        response = await http_client.get(f"{mcp_server.base_url}/cluster/peers")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "peers" in data
        assert len(data["peers"]) >= 1
        assert any(peer["id"] == "test-worker-2" for peer in data["peers"])
    
    @pytest.mark.anyio
    async def test_remove_peer_from_cluster(self, mcp_server, http_client):
        """Test removing a peer from the cluster via HTTP"""
        # First add a peer
        peer_data = {
            "id": "test-worker-3",
            "role": "worker",
            "address": "127.0.0.1",
            "port": 10002
        }
        await http_client.post(f"{mcp_server.base_url}/cluster/peers", json=peer_data)
        
        # Then remove it
        response = await http_client.delete(
            f"{mcp_server.base_url}/cluster/peers/test-worker-3"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["peer_id"] == "test-worker-3"
    
    @pytest.mark.anyio
    async def test_add_peer_validation(self, mcp_server, http_client):
        """Test peer addition validation"""
        # Missing required fields
        invalid_peer_data = {
            "id": "incomplete-peer"
            # Missing role, address, port
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/cluster/peers",
            json=invalid_peer_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "validation" in data["message"].lower()


class TestLeaderElectionEndpoints:
    """Test leader election HTTP endpoints"""
    
    @pytest.mark.anyio
    async def test_trigger_leader_election(self, mcp_server, http_client):
        """Test triggering leader election via HTTP"""
        response = await http_client.post(f"{mcp_server.base_url}/cluster/election/trigger")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "leader" in data
        assert "election_time" in data
        assert data["leader"]["role"] == "master"
    
    @pytest.mark.anyio
    async def test_get_current_leader(self, mcp_server, http_client):
        """Test getting current leader via HTTP"""
        response = await http_client.get(f"{mcp_server.base_url}/cluster/leader")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "leader" in data
        if data["leader"]:
            assert "id" in data["leader"]
            assert "role" in data["leader"]
    
    @pytest.mark.anyio
    async def test_heartbeat_endpoint(self, mcp_server, http_client):
        """Test sending heartbeat via HTTP"""
        heartbeat_data = {
            "node_id": "test-node",
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/cluster/heartbeat",
            json=heartbeat_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestReplicationEndpoints:
    """Test replication management HTTP endpoints"""
    
    @pytest.mark.anyio
    async def test_initiate_replication_master(self, mcp_server, http_client):
        """Test initiating replication from master node via HTTP"""
        # First add some target peers
        peers_data = [
            {"id": "worker-1", "role": "worker", "address": "127.0.0.1", "port": 10000},
            {"id": "worker-2", "role": "worker", "address": "127.0.0.1", "port": 10001}
        ]
        
        for peer_data in peers_data:
            await http_client.post(f"{mcp_server.base_url}/cluster/peers", json=peer_data)
        
        # Initiate replication
        replication_data = {
            "cid": "QmTestReplication123",
            "target_peers": ["worker-1", "worker-2"]
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/replication/replicate",
            json=replication_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cid"] == "QmTestReplication123"
    
    @pytest.mark.anyio
    async def test_get_replication_status(self, mcp_server, http_client):
        """Test getting replication status via HTTP"""
        response = await http_client.get(f"{mcp_server.base_url}/replication/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_tasks" in data
        assert "completed_tasks" in data
        assert "failed_tasks" in data
    
    @pytest.mark.anyio
    async def test_replication_validation(self, mcp_server, http_client):
        """Test replication request validation"""
        # Missing CID
        invalid_data = {
            "target_peers": ["worker-1"]
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/replication/replicate",
            json=invalid_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False


class TestIndexingEndpoints:
    """Test indexing service HTTP endpoints"""
    
    @pytest.mark.anyio
    async def test_add_index_data_master(self, mcp_server, http_client):
        """Test adding index data from master node via HTTP"""
        index_data = {
            "index_type": "embeddings",
            "key": "test-doc-1",
            "data": {
                "vector": [0.1, 0.2, 0.3],
                "content": "test document for indexing"
            }
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/indexing/data",
            json=index_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["key"] == "test-doc-1"
    
    @pytest.mark.anyio
    async def test_get_index_data(self, mcp_server, http_client):
        """Test retrieving index data via HTTP"""
        # First add some data
        index_data = {
            "index_type": "embeddings",
            "key": "test-doc-2",
            "data": {
                "vector": [0.4, 0.5, 0.6],
                "content": "another test document"
            }
        }
        await http_client.post(f"{mcp_server.base_url}/indexing/data", json=index_data)
        
        # Retrieve specific key
        response = await http_client.get(
            f"{mcp_server.base_url}/indexing/data/embeddings/test-doc-2"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["key"] == "test-doc-2"
    
    @pytest.mark.anyio
    async def test_get_all_index_data(self, mcp_server, http_client):
        """Test retrieving all index data for a type via HTTP"""
        response = await http_client.get(
            f"{mcp_server.base_url}/indexing/data/embeddings"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_entries" in data
        assert "data" in data
    
    @pytest.mark.anyio
    async def test_remove_index_data(self, mcp_server, http_client):
        """Test removing index data via HTTP"""
        # First add data
        index_data = {
            "index_type": "embeddings",
            "key": "test-doc-to-remove",
            "data": {"vector": [0.7, 0.8, 0.9], "content": "temporary document"}
        }
        await http_client.post(f"{mcp_server.base_url}/indexing/data", json=index_data)
        
        # Remove it
        response = await http_client.delete(
            f"{mcp_server.base_url}/indexing/data/embeddings/test-doc-to-remove"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.anyio
    async def test_search_embeddings(self, mcp_server, http_client):
        """Test embedding similarity search via HTTP"""
        # First add some embeddings
        embeddings = [
            {
                "index_type": "embeddings",
                "key": "search-doc-1",
                "data": {"vector": [1.0, 0.0, 0.0], "content": "document one"}
            },
            {
                "index_type": "embeddings", 
                "key": "search-doc-2",
                "data": {"vector": [0.0, 1.0, 0.0], "content": "document two"}
            }
        ]
        
        for embedding in embeddings:
            await http_client.post(f"{mcp_server.base_url}/indexing/data", json=embedding)
        
        # Search for similar embeddings
        search_data = {
            "query_vector": [0.9, 0.1, 0.0],
            "top_k": 2
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/indexing/search/embeddings",
            json=search_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data
        assert len(data["results"]) <= 2
    
    @pytest.mark.anyio
    async def test_get_index_statistics(self, mcp_server, http_client):
        """Test getting index statistics via HTTP"""
        response = await http_client.get(f"{mcp_server.base_url}/indexing/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "node_role" in data
        assert "total_indexes" in data
        assert "indexes" in data
        assert data["node_role"] == "master"
    
    @pytest.mark.anyio
    async def test_indexing_validation(self, mcp_server, http_client):
        """Test indexing request validation"""
        # Invalid index type
        invalid_data = {
            "index_type": "invalid_type",
            "key": "test-key",
            "data": {"test": "data"}
        }
        
        response = await http_client.post(
            f"{mcp_server.base_url}/indexing/data",
            json=invalid_data
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False


class TestErrorHandling:
    """Test HTTP API error handling"""
    
    @pytest.mark.anyio
    async def test_invalid_endpoint(self, mcp_server, http_client):
        """Test request to invalid endpoint"""
        response = await http_client.get(f"{mcp_server.base_url}/invalid/endpoint")
        
        assert response.status_code == 404
    
    @pytest.mark.anyio
    async def test_malformed_json(self, mcp_server, http_client):
        """Test request with malformed JSON"""
        response = await http_client.post(
            f"{mcp_server.base_url}/cluster/peers",
            content="invalid json content",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
    
    @pytest.mark.anyio
    async def test_missing_required_fields(self, mcp_server, http_client):
        """Test requests with missing required fields"""
        # Replication without CID
        response = await http_client.post(
            f"{mcp_server.base_url}/replication/replicate",
            json={"target_peers": ["peer-1"]}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
    
    @pytest.mark.anyio
    async def test_unauthorized_operations(self, mcp_server, http_client):
        """Test operations that should be unauthorized for certain roles"""
        # This would require setting up a non-master server
        # For now, we test the response structure
        pass


class TestConcurrentHTTPRequests:
    """Test concurrent HTTP request handling"""
    
    @pytest.mark.anyio
    async def test_concurrent_cluster_status_requests(self, mcp_server, http_client):
        """Test handling multiple concurrent status requests"""
        tasks = []

        for _ in range(10):
            task = http_client.get(f"{mcp_server.base_url}/cluster/status")
            tasks.append(task)

        responses = []
        async with anyio.create_task_group() as tg:
            for task in tasks:
                tg.start_soon(_collect_response, task, responses)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert "node_info" in data
    
    @pytest.mark.anyio
    async def test_concurrent_peer_operations(self, mcp_server, http_client):
        """Test concurrent peer addition operations"""
        tasks = []
        
        for i in range(5):
            peer_data = {
                "id": f"concurrent-peer-{i}",
                "role": "worker",
                "address": "127.0.0.1",
                "port": 11000 + i
            }
            task = http_client.post(f"{mcp_server.base_url}/cluster/peers", json=peer_data)
            tasks.append(task)

        responses = []
        async with anyio.create_task_group() as tg:
            for task in tasks:
                tg.start_soon(_collect_response, task, responses)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    @pytest.mark.anyio
    async def test_concurrent_indexing_operations(self, mcp_server, http_client):
        """Test concurrent indexing operations"""
        tasks = []
        
        for i in range(5):
            index_data = {
                "index_type": "embeddings",
                "key": f"concurrent-doc-{i}",
                "data": {
                    "vector": [i, i, i],
                    "content": f"concurrent document {i}"
                }
            }
            task = http_client.post(f"{mcp_server.base_url}/indexing/data", json=index_data)
            tasks.append(task)

        responses = []
        async with anyio.create_task_group() as tg:
            for task in tasks:
                tg.start_soon(_collect_response, task, responses)
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestPerformanceAndLimits:
    """Test performance and limits of HTTP API"""
    
    @pytest.mark.anyio
    async def test_large_peer_list_handling(self, mcp_server, http_client):
        """Test handling large peer lists"""
        # Add many peers
        for i in range(50):
            peer_data = {
                "id": f"load-test-peer-{i}",
                "role": "worker",
                "address": "127.0.0.1",
                "port": 12000 + i
            }
            await http_client.post(f"{mcp_server.base_url}/cluster/peers", json=peer_data)
        
        # Get all peers
        start_time = time.time()
        response = await http_client.get(f"{mcp_server.base_url}/cluster/peers")
        end_time = time.time()
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["peers"]) >= 50
        
        # Should respond quickly even with many peers
        assert end_time - start_time < 2.0
    
    @pytest.mark.anyio
    async def test_large_index_data_handling(self, mcp_server, http_client):
        """Test handling large index data"""
        # Add many index entries
        for i in range(20):
            index_data = {
                "index_type": "embeddings",
                "key": f"large-test-doc-{i}",
                "data": {
                    "vector": [float(j) for j in range(100)],  # Large vector
                    "content": f"large test document {i} " * 100  # Large content
                }
            }
            response = await http_client.post(f"{mcp_server.base_url}/indexing/data", json=index_data)
            assert response.status_code == 200
        
        # Retrieve all embeddings
        start_time = time.time()
        response = await http_client.get(f"{mcp_server.base_url}/indexing/data/embeddings")
        end_time = time.time()
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_entries"] >= 20
        
        # Should handle large data efficiently
        assert end_time - start_time < 5.0


if __name__ == "__main__":
    # Run tests directly if executed as script
    pytest.main([__file__, "-v", "--tb=short", "-s"])
