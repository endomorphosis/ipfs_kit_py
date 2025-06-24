"""
Tests for the enhanced libp2p integration functionality with AnyIO support.

These tests verify the integration between the enhanced DHT discovery,
content routing, and IPFSKit components using AnyIO for async operations.
"""

import os
import sys
import tempfile
import time
import unittest
import anyio
import pytest
import atexit
from unittest.mock import MagicMock, patch

# Ensure package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Try to import the new test fixtures
try:
    from test.test_fixtures.libp2p_test_fixtures import (
        SimulatedNode, NetworkSimulator, MockLibp2pPeer, NetworkScenario
    )
    FIXTURES_AVAILABLE = True
except ImportError:
    FIXTURES_AVAILABLE = False

# Mock the libp2p module and its imports first
# This needs to happen before importing IPFSLibp2pPeer
mock_libp2p = MagicMock()
mock_libp2p.new_host = MagicMock()
mock_libp2p.peer = MagicMock()
mock_libp2p.peer.peerinfo = MagicMock()
mock_libp2p.peer.peerinfo.PeerInfo = MagicMock()
mock_libp2p.peer.id = MagicMock()
mock_libp2p.peer.id.ID = MagicMock()
mock_libp2p.typing = MagicMock()
mock_libp2p.typing.TProtocol = MagicMock()
mock_libp2p.network = MagicMock()
mock_libp2p.network.stream = MagicMock()
mock_libp2p.network.stream.net_stream_interface = MagicMock()
mock_libp2p.network.stream.net_stream_interface.INetStream = MagicMock()
mock_libp2p.crypto = MagicMock()
mock_libp2p.crypto.keys = MagicMock()
mock_libp2p.crypto.keys.KeyPair = MagicMock()
mock_libp2p.crypto.keys.PrivateKey = MagicMock()
mock_libp2p.crypto.keys.PublicKey = MagicMock()
mock_libp2p.crypto.serialization = MagicMock()
mock_libp2p.tools = MagicMock()
mock_libp2p.tools.pubsub = MagicMock()
mock_libp2p.tools.pubsub.utils = MagicMock()
mock_libp2p.tools.constants = MagicMock()
mock_libp2p.tools.constants.ALPHA_VALUE = 3
mock_libp2p.kademlia = MagicMock()
mock_libp2p.kademlia.network = MagicMock()
mock_libp2p.kademlia.network.KademliaServer = MagicMock()
mock_libp2p.discovery = MagicMock()
mock_libp2p.discovery.mdns = MagicMock()
mock_libp2p.transport = MagicMock()
mock_libp2p.transport.upgrader = MagicMock()
mock_libp2p.transport.tcp = MagicMock()
mock_libp2p.transport.tcp.tcp = MagicMock()

# Add the mocks to sys.modules
sys.modules["libp2p"] = mock_libp2p
sys.modules["libp2p.peer"] = mock_libp2p.peer
sys.modules["libp2p.peer.peerinfo"] = mock_libp2p.peer.peerinfo
sys.modules["libp2p.peer.id"] = mock_libp2p.peer.id
sys.modules["libp2p.typing"] = mock_libp2p.typing
sys.modules["libp2p.network"] = mock_libp2p.network
sys.modules["libp2p.network.stream"] = mock_libp2p.network.stream
sys.modules["libp2p.network.stream.net_stream_interface"] = (
    mock_libp2p.network.stream.net_stream_interface
)
sys.modules["libp2p.crypto"] = mock_libp2p.crypto
sys.modules["libp2p.crypto.keys"] = mock_libp2p.crypto.keys
sys.modules["libp2p.crypto.serialization"] = mock_libp2p.crypto.serialization
sys.modules["libp2p.tools"] = mock_libp2p.tools
sys.modules["libp2p.tools.pubsub"] = mock_libp2p.tools.pubsub
sys.modules["libp2p.tools.pubsub.utils"] = mock_libp2p.tools.pubsub.utils
sys.modules["libp2p.tools.constants"] = mock_libp2p.tools.constants
sys.modules["libp2p.kademlia"] = mock_libp2p.kademlia
sys.modules["libp2p.kademlia.network"] = mock_libp2p.kademlia.network
sys.modules["libp2p.discovery"] = mock_libp2p.discovery
sys.modules["libp2p.discovery.mdns"] = mock_libp2p.discovery.mdns
sys.modules["libp2p.transport"] = mock_libp2p.transport
sys.modules["libp2p.transport.upgrader"] = mock_libp2p.transport.upgrader
sys.modules["libp2p.transport.tcp"] = mock_libp2p.transport.tcp
sys.modules["libp2p.transport.tcp.tcp"] = mock_libp2p.transport.tcp.tcp


# Now patch IPFSLibp2pPeer to avoid the import error
class MockIPFSLibp2pPeer:
    """Mock implementation of IPFSLibp2pPeer for testing."""

    def __init__(
        self,
        identity_path=None,
        bootstrap_peers=None,
        listen_addrs=None,
        role="leecher",
        enable_mdns=True,
        enable_hole_punching=False,
        enable_relay=False,
        tiered_storage_manager=None,
    ):
        self.role = role
        self.identity_path = identity_path
        self.bootstrap_peers = bootstrap_peers or []
        self.listen_addrs = listen_addrs or ["/ip4/0.0.0.0/tcp/0", "/ip4/0.0.0.0/udp/0/quic"]
        self.enable_mdns = enable_mdns
        self.enable_hole_punching = enable_hole_punching
        self.enable_relay_client = enable_relay
        self.enable_relay_server = (role in ["master", "worker"]) and enable_relay
        self.tiered_storage_manager = tiered_storage_manager

        # Initialize components (all mocks)
        self.host = MagicMock()
        self.dht = MagicMock()
        self.pubsub = MagicMock()
        self.protocols = {}
        self.content_store = {}
        self.logger = MagicMock()

        # For testing protocol handlers
        self._protocol_handlers = {}

    def get_peer_id(self):
        """Get peer ID as string."""
        return f"QmMockPeer-{self.role}-{id(self)}"

    def start(self):
        """Start the peer and its components."""
        return True

    def stop(self):
        """Stop the peer and its components."""
        return True

    def add_protocol_handler(self, protocol, handler):
        """Register a protocol handler."""
        self._protocol_handlers[protocol] = handler
        return True

    def connect_peer(self, peer_info):
        """Connect to a remote peer."""
        return True

    def publish(self, topic, data):
        """Publish data to a topic."""
        return True

    def subscribe(self, topic, handler):
        """Subscribe to a topic."""
        return True

    def unsubscribe(self, topic):
        """Unsubscribe from a topic."""
        return True

    async def request_content(self, cid, timeout=30):
        """Request content by CID."""
        # Simulate content lookup and retrieval
        await anyio.sleep(0.1)
        return self.content_store.get(cid, b"Mock Content for " + cid.encode())

    async def provide_content(self, cid, content):
        """Announce content availability."""
        # Store content for future requests
        self.content_store[cid] = content
        await anyio.sleep(0.1)
        return True

    async def find_providers(self, cid, timeout=30, count=5):
        """Find peers providing a CID."""
        # Simulate DHT lookup
        await anyio.sleep(0.1)
        return [f"/ip4/127.0.0.1/tcp/4001/p2p/QmMockProvider-{i}" for i in range(3)]

    async def find_peer(self, peer_id, timeout=30):
        """Find a peer by ID."""
        # Simulate DHT lookup
        await anyio.sleep(0.1)
        return ["/ip4/127.0.0.1/tcp/4001/p2p/" + peer_id]


# Patch the module to use our mock
sys.modules["ipfs_kit_py.libp2p_peer"] = MagicMock()
sys.modules["ipfs_kit_py.libp2p_peer"].IPFSLibp2pPeer = MockIPFSLibp2pPeer

# Now import our modules
from ipfs_kit_py.libp2p.enhanced_dht_discovery import EnhancedDHTDiscovery
from ipfs_kit_py.libp2p.p2p_integration import LibP2PIntegration
from ipfs_kit_py.libp2p.ipfs_kit_integration import IPFSKitLibp2pIntegration


class TestLibp2pIntegration(unittest.TestCase):
    """Test the libp2p integration with enhanced discovery."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for identity
        self.temp_dir = tempfile.mkdtemp(prefix="ipfs_p2p_test_")
        self.identity_path = os.path.join(self.temp_dir, "identity.json")

        # Create basic mocks for testing
        self.mock_peer = MockIPFSLibp2pPeer(
            identity_path=self.identity_path,
            role="worker",
            enable_mdns=True
        )

        # Create the enhanced discovery instance
        self.discovery = EnhancedDHTDiscovery(
            peer=self.mock_peer,
            bootstrap_interval=300,
            rendezvous_strings=["ipfs-test-network"],
            debug_mode=True
        )

        # Create P2P integration instance
        self.p2p_integration = LibP2PIntegration(
            peer=self.mock_peer,
            discovery=self.discovery,
            debug_mode=True
        )

        # Mock IPFS Kit
        self.mock_ipfs_kit = MagicMock()
        self.mock_ipfs_kit.ipfs_add = MagicMock(return_value={"Hash": "QmTestCID"})
        self.mock_ipfs_kit.ipfs_cat = MagicMock(return_value=b"Test content")

        # Create IPFS Kit integration instance
        self.ipfs_integration = IPFSKitLibp2pIntegration(
            ipfs_kit=self.mock_ipfs_kit,
            p2p_integration=self.p2p_integration,
            debug_mode=True
        )

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    def test_initialization(self):
        """Test initialization of components."""
        # Verify enhanced discovery
        self.assertEqual(self.discovery.peer, self.mock_peer)
        self.assertEqual(self.discovery.bootstrap_interval, 300)
        self.assertEqual(self.discovery.rendezvous_strings, ["ipfs-test-network"])
        self.assertTrue(self.discovery.debug_mode)

        # Verify P2P integration
        self.assertEqual(self.p2p_integration.peer, self.mock_peer)
        self.assertEqual(self.p2p_integration.discovery, self.discovery)
        self.assertTrue(self.p2p_integration.debug_mode)

        # Verify IPFS Kit integration
        self.assertEqual(self.ipfs_integration.ipfs_kit, self.mock_ipfs_kit)
        self.assertEqual(self.ipfs_integration.p2p_integration, self.p2p_integration)
        self.assertTrue(self.ipfs_integration.debug_mode)

    @pytest.mark.anyio
    async def test_content_retrieval(self):
        """Test content retrieval workflow."""
        # Prepare test data
        test_cid = "QmTestContentCID"
        test_content = b"This is test content"

        # Store test content in peer's content store
        self.mock_peer.content_store[test_cid] = test_content

        # Set up the mock for ipfs_cat to return None first (forcing P2P retrieval)
        self.mock_ipfs_kit.ipfs_cat.side_effect = [None, test_content]

        # Request content
        content = await self.ipfs_integration.retrieve_content(test_cid)

        # Verify the right content was returned
        self.assertEqual(content, test_content)

        # Verify that an attempt was made to get from IPFS first
        self.mock_ipfs_kit.ipfs_cat.assert_called_with(test_cid)

        # Verify that the content was stored in IPFS after P2P retrieval
        self.mock_ipfs_kit.ipfs_add.assert_called()

    @pytest.mark.anyio
    async def test_content_publication(self):
        """Test content publication workflow."""
        # Prepare test data
        test_content = b"Test content for publication"

        # Mock the add result
        self.mock_ipfs_kit.ipfs_add.return_value = {"Hash": "QmPublishedCID"}

        # Publish content
        result = await self.ipfs_integration.publish_content(test_content)

        # Verify the publishing was successful
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], "QmPublishedCID")

        # Verify content was added to IPFS
        self.mock_ipfs_kit.ipfs_add.assert_called_with(test_content)

    @pytest.mark.anyio
    async def test_peer_discovery(self):
        """Test peer discovery mechanisms."""
        # Mock discovery results
        discovery_results = [
            "/ip4/192.168.1.1/tcp/4001/p2p/QmPeer1",
            "/ip4/192.168.1.2/tcp/4001/p2p/QmPeer2",
            "/ip4/192.168.1.3/tcp/4001/p2p/QmPeer3"
        ]

        # Mock the discovery perform method
        async def mock_discover():
            return discovery_results

        self.discovery.discover_peers = mock_discover

        # Test the discovery
        peers = await self.p2p_integration.discover_peers()

        # Verify the results
        self.assertEqual(peers, discovery_results)

    @pytest.mark.anyio
    async def test_content_provider_search(self):
        """Test finding content providers."""
        # Prepare test data
        test_cid = "QmTestProviderCID"
        provider_peers = [
            "/ip4/192.168.1.1/tcp/4001/p2p/QmProvider1",
            "/ip4/192.168.1.2/tcp/4001/p2p/QmProvider2"
        ]

        # Setup mock
        async def mock_find_providers(cid, **kwargs):
            return provider_peers

        self.mock_peer.find_providers = mock_find_providers

        # Find providers for CID
        providers = await self.p2p_integration.find_content_providers(test_cid)

        # Verify the results
        self.assertEqual(providers, provider_peers)

    @pytest.mark.anyio
    async def test_direct_content_exchange(self):
        """Test direct content exchange between peers."""
        # Prepare test data
        test_cid = "QmDirectExchangeCID"
        test_content = b"Content for direct exchange test"

        # Setup source peer with content
        source_peer = MockIPFSLibp2pPeer(role="worker")
        source_peer.content_store[test_cid] = test_content

        # Setup target peer (our mock peer)
        target_peer = self.mock_peer

        # Store peer info for connection
        source_peer_id = source_peer.get_peer_id()
        mock_peer_info = f"/ip4/127.0.0.1/tcp/4001/p2p/{source_peer_id}"

        # Mock connection and request functions
        target_peer.connect_peer = MagicMock(return_value=True)

        async def mock_request(cid, **kwargs):
            # Simulate getting content from the other peer
            await anyio.sleep(0.1)
            return source_peer.content_store.get(cid)

        target_peer.request_content = mock_request

        # Configure our integration to use the target peer
        p2p_integration = LibP2PIntegration(
            peer=target_peer,
            discovery=self.discovery
        )

        # Request content from source peer directly
        content = await p2p_integration.direct_content_exchange(
            peer_addr=mock_peer_info,
            cid=test_cid
        )

        # Verify the content was exchanged correctly
        self.assertEqual(content, test_content)

        # Verify connection was attempted
        target_peer.connect_peer.assert_called()

    @unittest.skipIf(not FIXTURES_AVAILABLE, "LibP2P test fixtures not available")
    @pytest.mark.anyio
    async def test_simulated_network(self):
        """Test integration in a simulated network environment."""
        # Skip if fixtures aren't available
        if not FIXTURES_AVAILABLE:
            self.skipTest("LibP2P test fixtures not available")

        # Setup a network scenario with 5 nodes
        simulator = NetworkSimulator.get_instance()
        scenario = NetworkScenario(node_count=5)

        # Initialize the network
        await scenario.setup()

        # Create test content
        test_cid = "QmSimulationTestCID"
        test_content = b"Content for network simulation test"

        # Store content on one node
        source_node = scenario.nodes[0]
        source_node.peer.content_store[test_cid] = test_content
        await source_node.peer.provide_content(test_cid, test_content)

        # Have another node try to find and retrieve the content
        target_node = scenario.nodes[2]
        providers = await target_node.peer.find_providers(test_cid)

        # There should be at least one provider
        self.assertTrue(len(providers) > 0)

        # Retrieve content
        content = await target_node.peer.request_content(test_cid)

        # Verify content was retrieved correctly
        self.assertEqual(content, test_content)

        # Clean up the network simulation
        await scenario.teardown()

    def test_protocol_registration(self):
        """Test protocol handler registration."""
        # Create a simple protocol handler
        async def test_handler(stream):
            await anyio.sleep(0.1)
            return b"test response"

        # Register protocol handler
        result = self.p2p_integration.register_protocol_handler(
            protocol="/ipfs/test/1.0.0",
            handler=test_handler
        )

        # Verify registration was successful
        self.assertTrue(result)

        # Verify handler was added to peer's protocol handlers
        protocol_id = "/ipfs/test/1.0.0"
        self.assertIn(protocol_id, self.mock_peer._protocol_handlers)
        self.assertEqual(self.mock_peer._protocol_handlers[protocol_id], test_handler)

    @pytest.mark.anyio
    async def test_ipfs_fallback(self):
        """Test fallback to IPFS when P2P retrieval fails."""
        # Prepare test data
        test_cid = "QmFallbackTestCID"
        test_content = b"Content for fallback test"

        # Mock the peer request_content to fail
        async def mock_request_content_fail(cid, **kwargs):
            await anyio.sleep(0.1)
            return None

        self.mock_peer.request_content = mock_request_content_fail

        # Mock ipfs_cat to succeed
        self.mock_ipfs_kit.ipfs_cat.return_value = test_content

        # Request content
        content = await self.ipfs_integration.retrieve_content(test_cid, use_fallback=True)

        # Verify content was retrieved from IPFS (fallback)
        self.assertEqual(content, test_content)
        self.mock_ipfs_kit.ipfs_cat.assert_called_with(test_cid)


if __name__ == "__main__":
    unittest.main()
