"""
Tests for the anyio-based WebSocket peer discovery functionality.

These tests verify the functionality of the PeerWebSocketServer and
PeerWebSocketClient classes implemented with anyio.
"""

import time
import json
import pytest
from ipfs_kit_py.peer_websocket_anyio import (
    PeerInfo, PeerRole, MessageType,
    PeerWebSocketServer, PeerWebSocketClient
)

# Mark all tests in this module as anyio tests
pytestmark = pytest.mark.anyio

class TestPeerInfo:
    """Tests for the PeerInfo class."""

    def test_peer_info_initialization(self):
        """Test initializing PeerInfo with various parameters."""
        # Basic initialization
        peer = PeerInfo(
            peer_id="test-peer-1",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-peer-1"]
        )
        assert peer.peer_id == "test-peer-1"
        assert peer.multiaddrs == ["/ip4/127.0.0.1/tcp/4001/p2p/test-peer-1"]
        assert peer.role == PeerRole.LEECHER  # Default role
        assert peer.capabilities == []  # Default capabilities
        assert isinstance(peer.resources, dict)
        assert isinstance(peer.metadata, dict)
        assert peer.connection_success_rate == 1.0

        # Initialization with all parameters
        peer = PeerInfo(
            peer_id="test-peer-2",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-peer-2"],
            role=PeerRole.MASTER,
            capabilities=["ipfs", "tiered_cache"],
            resources={"cpu_cores": 4},
            metadata={"version": "1.0.0"}
        )
        assert peer.peer_id == "test-peer-2"
        assert peer.role == PeerRole.MASTER
        assert peer.capabilities == ["ipfs", "tiered_cache"]
        assert peer.resources == {"cpu_cores": 4}
        assert peer.metadata == {"version": "1.0.0"}

    def test_peer_info_to_dict(self):
        """Test converting PeerInfo to dictionary."""
        peer = PeerInfo(
            peer_id="test-peer",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"],
            role=PeerRole.WORKER,
            capabilities=["ipfs"]
        )

        peer_dict = peer.to_dict()
        assert peer_dict["peer_id"] == "test-peer"
        assert peer_dict["multiaddrs"] == ["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"]
        assert peer_dict["role"] == PeerRole.WORKER
        assert peer_dict["capabilities"] == ["ipfs"]
        assert "last_seen" in peer_dict
        assert "connection_success_rate" in peer_dict

    def test_peer_info_from_dict(self):
        """Test creating PeerInfo from dictionary."""
        peer_dict = {
            "peer_id": "test-peer",
            "multiaddrs": ["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"],
            "role": PeerRole.MASTER,
            "capabilities": ["ipfs", "ipfs_cluster"],
            "resources": {"memory_gb": 8},
            "metadata": {"uptime": 3600},
            "last_seen": time.time(),
            "connection_success_rate": 0.9
        }

        peer = PeerInfo.from_dict(peer_dict)
        assert peer.peer_id == "test-peer"
        assert peer.multiaddrs == ["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"]
        assert peer.role == PeerRole.MASTER
        assert peer.capabilities == ["ipfs", "ipfs_cluster"]
        assert peer.resources == {"memory_gb": 8}
        assert peer.metadata == {"uptime": 3600}
        assert abs(peer.last_seen - peer_dict["last_seen"]) < 0.001
        assert peer.connection_success_rate == 0.9

    def test_peer_info_update_from_dict(self):
        """Test updating PeerInfo from dictionary."""
        peer = PeerInfo(
            peer_id="test-peer",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"],
            role=PeerRole.LEECHER,
            capabilities=["ipfs"],
            resources={"cpu_cores": 2},
            metadata={"version": "1.0.0"}
        )

        update_dict = {
            "multiaddrs": ["/ip4/192.168.1.1/tcp/4001/p2p/test-peer"],
            "role": PeerRole.WORKER,
            "capabilities": ["ipfs", "tiered_cache"],
            "resources": {"cpu_cores": 4, "memory_gb": 16},
            "metadata": {"uptime": 3600}
        }

        # Store original last_seen
        original_last_seen = peer.last_seen

        # Wait a tiny bit to ensure last_seen changes
        time.sleep(0.001)

        # Update peer info
        peer.update_from_dict(update_dict)

        # Verify updates
        assert peer.multiaddrs == ["/ip4/192.168.1.1/tcp/4001/p2p/test-peer"]
        assert peer.role == PeerRole.WORKER
        assert peer.capabilities == ["ipfs", "tiered_cache"]
        assert peer.resources == {"cpu_cores": 4, "memory_gb": 16}
        assert peer.metadata == {"version": "1.0.0", "uptime": 3600}  # Merged metadata
        assert peer.last_seen > original_last_seen  # Should be updated

    def test_record_connection_attempt(self):
        """Test recording connection attempts."""
        peer = PeerInfo(
            peer_id="test-peer",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-peer"]
        )

        # Initial values
        assert peer.connection_attempts == 0
        assert peer.successful_connections == 0
        assert peer.connection_success_rate == 1.0

        # Record successful attempt
        peer.record_connection_attempt(True)
        assert peer.connection_attempts == 1
        assert peer.successful_connections == 1
        assert peer.connection_success_rate == 1.0

        # Record failed attempt
        peer.record_connection_attempt(False)
        assert peer.connection_attempts == 2
        assert peer.successful_connections == 1
        assert peer.connection_success_rate == 0.5

        # Record another successful attempt
        peer.record_connection_attempt(True)
        assert peer.connection_attempts == 3
        assert peer.successful_connections == 2
        assert pytest.approx(peer.connection_success_rate) == 2/3

@pytest.fixture
async def server_and_client():
    """Fixture that provides a running server and connected client."""
    # Create server peer
    server_peer = PeerInfo(
        peer_id="test-server-peer",
        multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-server-peer"],
        role=PeerRole.MASTER,
        capabilities=["ipfs", "ipfs_cluster"]
    )

    # Create client peer
    client_peer = PeerInfo(
        peer_id="test-client-peer",
        multiaddrs=["/ip4/127.0.0.1/tcp/4002/p2p/test-client-peer"],
        role=PeerRole.WORKER,
        capabilities=["ipfs"]
    )

    # Create server and client
    server = PeerWebSocketServer(server_peer)
    client = PeerWebSocketClient(client_peer)

    # Use a unique port for tests
    test_port = 9878

    try:
        # Start server in background
        await server.start(host="127.0.0.1", port=test_port)

        # Start client and connect to server
        await client.start()

        # Yield the server and client for testing
        yield (server, client, f"ws://127.0.0.1:{test_port}")

    finally:
        # Clean up
        await client.stop()
        await server.stop()

class TestPeerWebSocket:
    """Tests for the PeerWebSocketServer and PeerWebSocketClient."""

    async def test_server_initialization(self):
        """Test initializing server."""
        # Create server peer
        server_peer = PeerInfo(
            peer_id="test-server-peer",
            multiaddrs=["/ip4/127.0.0.1/tcp/4001/p2p/test-server-peer"],
            role=PeerRole.MASTER,
            capabilities=["ipfs", "ipfs_cluster"]
        )

        # Create server
        server = PeerWebSocketServer(server_peer)

        # Verify initial state
        assert server.local_peer_info == server_peer
        assert server.max_peers == 100  # Default
        assert server.heartbeat_interval == 30  # Default
        assert server.peer_ttl == 300  # Default
        assert server.peers == {}
        assert server.connections == {}
        assert server.server is None
        assert server.cleanup_task is None
        assert server.heartbeat_task is None
        assert server.running is False

    async def test_client_initialization(self):
        """Test initializing client."""
        # Create client peer
        client_peer = PeerInfo(
            peer_id="test-client-peer",
            multiaddrs=["/ip4/127.0.0.1/tcp/4002/p2p/test-client-peer"],
            role=PeerRole.WORKER,
            capabilities=["ipfs"]
        )

        # Create mock callback
        def on_peer_discovered(peer):
            pass

        # Create client
        client = PeerWebSocketClient(
            local_peer_info=client_peer,
            on_peer_discovered=on_peer_discovered,
            auto_connect=True,
            reconnect_interval=10,
            max_reconnect_attempts=3
        )

        # Verify initial state
        assert client.local_peer_info == client_peer
        assert client.on_peer_discovered == on_peer_discovered
        assert client.auto_connect is True
        assert client.reconnect_interval == 10
        assert client.max_reconnect_attempts == 3
        assert client.peers == {client_peer.peer_id: client_peer}  # Should include self
        assert client.connections == {}
        assert client.discovery_servers == {}
        assert client.running is False
        assert client.tasks == set()
        assert client.task_group is None

    @pytest.mark.asyncio
    async def test_client_server_connection(self, server_and_client):
        """Test establishing connection between client and server."""
        server, client, server_url = server_and_client

        # Connect client to server
        connected = await client.connect_to_discovery_server(server_url)
        assert connected is True

        # Give time for connection to establish and exchange messages
        await anyio.sleep(1)

        # Verify client has discovered server
        peer_id = server.local_peer_info.peer_id
        assert peer_id in client.peers

        # Get discovered peer
        discovered_peer = client.get_peer_by_id(peer_id)
        assert discovered_peer is not None
        assert discovered_peer.peer_id == peer_id
        assert discovered_peer.role == PeerRole.MASTER
        assert "ipfs" in discovered_peer.capabilities
        assert "ipfs_cluster" in discovered_peer.capabilities

    @pytest.mark.asyncio
    async def test_peer_list_filtering(self, server_and_client):
        """Test filtering peer lists."""
        server, client, server_url = server_and_client

        # Connect client to server
        await client.connect_to_discovery_server(server_url)

        # Give time for connection to establish and exchange messages
        await anyio.sleep(1)

        # Add some additional peers to client for testing filtering
        client.peers["peer-1"] = PeerInfo(
            peer_id="peer-1",
            multiaddrs=[],
            role=PeerRole.MASTER,
            capabilities=["ipfs", "ipfs_cluster"]
        )

        client.peers["peer-2"] = PeerInfo(
            peer_id="peer-2",
            multiaddrs=[],
            role=PeerRole.WORKER,
            capabilities=["ipfs"]
        )

        client.peers["peer-3"] = PeerInfo(
            peer_id="peer-3",
            multiaddrs=[],
            role=PeerRole.LEECHER,
            capabilities=["ipfs", "tiered_cache"]
        )

        # Test getting all peers (excluding self)
        all_peers = client.get_discovered_peers()
        assert len(all_peers) == 4  # server + 3 added peers

        # Test filtering by role
        master_peers = client.get_discovered_peers(filter_role=PeerRole.MASTER)
        assert len(master_peers) == 2
        assert all(p.role == PeerRole.MASTER for p in master_peers)

        worker_peers = client.get_discovered_peers(filter_role=PeerRole.WORKER)
        assert len(worker_peers) == 1
        assert worker_peers[0].peer_id == "peer-2"

        # Test filtering by capabilities
        ipfs_cluster_peers = client.get_discovered_peers(
            filter_capabilities=["ipfs_cluster"]
        )
        assert len(ipfs_cluster_peers) == 2
        assert all("ipfs_cluster" in p.capabilities for p in ipfs_cluster_peers)

        # Test combined filtering
        master_with_cluster = client.get_discovered_peers(
            filter_role=PeerRole.MASTER,
            filter_capabilities=["ipfs_cluster"]
        )
        assert len(master_with_cluster) == 2
        assert all(p.role == PeerRole.MASTER for p in master_with_cluster)
        assert all("ipfs_cluster" in p.capabilities for p in master_with_cluster)

if __name__ == "__main__":
    pytest.main()
