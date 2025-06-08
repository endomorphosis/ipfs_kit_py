"""
Tests for the LibP2PModel class in the MCP framework.
"""

import time
from unittest.mock import MagicMock

import pytest

from ipfs_kit_py.mcp.models.libp2p_model import LibP2PModel

# Import the class to test


# Mock the dependencies that LibP2PModel might try to import or use
# Mock IPFSLibp2pPeer and related components if HAS_LIBP2P is True during test setup
mock_libp2p_peer = MagicMock()
mock_libp2p_peer.get_peer_id.return_value = "MockPeerID"
mock_libp2p_peer.get_listen_addresses.return_value = ["/ip4/127.0.0.1/tcp/4001"]
mock_libp2p_peer.get_connected_peers.return_value = ["Peer1", "Peer2"]
mock_libp2p_peer.dht = MagicMock()
mock_libp2p_peer.dht.routing_table.get_peers.return_value = ["DHTPeer1"]
mock_libp2p_peer.protocol_handlers = {"/test/1.0": MagicMock()}
mock_libp2p_peer.role = "leecher"
mock_libp2p_peer.start = MagicMock(return_value=True)
mock_libp2p_peer.close = MagicMock()
mock_libp2p_peer.discover_peers_dht = MagicMock(return_value=["DHTPeerDiscovered"])
mock_libp2p_peer.discover_peers_mdns = MagicMock(return_value=["MDNSPeerDiscovered"])
mock_libp2p_peer.connect_peer = MagicMock(return_value=True)
mock_libp2p_peer.find_providers = MagicMock(return_value=["ProviderPeer1"])
mock_libp2p_peer.retrieve_content = MagicMock(return_value=b"mock_content_data")
mock_libp2p_peer.store_content_locally = MagicMock()
mock_libp2p_peer.announce_content = MagicMock()
mock_libp2p_peer.get_peer_info = MagicMock(
    return_value={"protocols": ["/test/1.0"], "latency": 0.1}
)
mock_libp2p_peer.find_peer_addresses = MagicMock(return_value=["/ip4/1.2.3.4/tcp/4001"])
mock_libp2p_peer.provide_content = MagicMock(return_value=True)
# Mock pubsub methods directly on the peer mock
mock_libp2p_peer.publish_message = MagicMock(return_value=True)
mock_libp2p_peer.subscribe = MagicMock(return_value=True)
mock_libp2p_peer.unsubscribe = MagicMock(return_value=True)
mock_libp2p_peer.get_topics = MagicMock(return_value=["/test/topic"])
mock_libp2p_peer.get_topic_peers = MagicMock(return_value=["PubSubPeer1"])
# Add bootstrap_peers attribute to mock
mock_libp2p_peer.bootstrap_peers = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN"
]


# Mock CacheManager
mock_cache_manager = MagicMock()
mock_cache_manager.get.return_value = None
mock_cache_manager.put = MagicMock()
mock_cache_manager.delete = MagicMock()
mock_cache_manager.list_keys = MagicMock(return_value=["libp2p_health", "libp2p_content_abc"])

# Mock CredentialManager
mock_credential_manager = MagicMock()

# Mock EnhancedDHTDiscovery if needed
mock_enhanced_dht_discovery = MagicMock()
mock_enhanced_dht_discovery.discover_peers = MagicMock(return_value=["EnhancedDHTPeer"])


@pytest.fixture
def mock_dependencies(monkeypatch):
    """Fixture to mock external dependencies."""
    # Patch HAS_LIBP2P directly in the model's namespace
    monkeypatch.setattr("ipfs_kit_py.mcp.models.libp2p_model.HAS_LIBP2P", True, raising=False)
    # Mock the IPFSLibp2pPeer class at its source location
    # We also need to mock the import within the model file itself in case it was already imported
    monkeypatch.setattr(
        "ipfs_kit_py.libp2p_peer.IPFSLibp2pPeer",
        MagicMock(return_value=mock_libp2p_peer),
        raising=False,
    )
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.IPFSLibp2pPeer",
        MagicMock(return_value=mock_libp2p_peer),
        raising=False,
    )
    # Mock check_dependencies and install_dependencies
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.check_dependencies",
        MagicMock(),
        raising=False,
    )
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.install_dependencies",
        MagicMock(return_value=True),
        raising=False,
    )
    # Mock the EnhancedDHTDiscovery variable directly within the model's namespace
    # This assumes the variable exists at the module level after import.
    # We mock it to be a callable that returns our mock instance.
    # Also need to mock the get_enhanced_dht_discovery function it relies on
    monkeypatch.setattr(
        "ipfs_kit_py.libp2p.get_enhanced_dht_discovery",
        MagicMock(return_value=MagicMock(return_value=mock_enhanced_dht_discovery)),
        raising=False,
    )
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.EnhancedDHTDiscovery",
        MagicMock(return_value=mock_enhanced_dht_discovery),
        raising=False,
    )
    # Mock apply_protocol_extensions_to_instance
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.apply_protocol_extensions_to_instance",
        MagicMock(),
        raising=False,
    )
    # Patch EnhancedDHTDiscovery directly to the mock object
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.EnhancedDHTDiscovery",
        mock_enhanced_dht_discovery,
        raising=False,
    )
    # Patch is_available directly on the CLASS within the dependency fixture
    # monkeypatch.setattr(LibP2PModel, "is_available", MagicMock(return_value=True)) # Removed - will patch instance


@pytest.fixture
def libp2p_model(mock_dependencies):
    """Fixture to create a LibP2PModel instance with mocked dependencies."""
    # Reset mocks before each test
    mock_libp2p_peer.reset_mock()
    mock_cache_manager.reset_mock()
    mock_credential_manager.reset_mock()
    mock_enhanced_dht_discovery.reset_mock()
    # Reset direct pubsub method mocks
    mock_libp2p_peer.publish_message.reset_mock()
    mock_libp2p_peer.subscribe.reset_mock()
    mock_libp2p_peer.unsubscribe.reset_mock()
    # Ensure cache mock starts clean for each test using this fixture
    mock_cache_manager.get.return_value = None

    # Create the instance first
    model = LibP2PModel(
        cache_manager=mock_cache_manager,
        credential_manager=mock_credential_manager,
        metadata={"auto_start": False},  # Prevent auto-start during init
    )
    # Force assign mocks AFTER instance creation to bypass __init__ issues
    model.libp2p_peer = mock_libp2p_peer
    model.dht_discovery = mock_enhanced_dht_discovery
    # Patch is_available directly on the instance for this fixture
    model.is_available = MagicMock(return_value=True)
    # Add assertion to verify peer assignment
    assert model.libp2p_peer is mock_libp2p_peer
    return model


@pytest.fixture
def libp2p_model_no_deps(mock_dependencies, monkeypatch):
    """Fixture for model when dependencies are missing."""
    monkeypatch.setattr("ipfs_kit_py.mcp.models.libp2p_model.HAS_LIBP2P", False)
    # Ensure IPFSLibp2pPeer is not used
    monkeypatch.setattr(
        "ipfs_kit_py.mcp.models.libp2p_model.IPFSLibp2pPeer",
        MagicMock(side_effect=ImportError),
        raising=False,
    )
    # Ensure cache mock starts clean for this fixture too
    mock_cache_manager.get.return_value = None

    # Patch is_available directly on the CLASS for the no_deps case
    # monkeypatch.setattr(LibP2PModel, "is_available", MagicMock(return_value=False)) # Removed - will patch instance

    model = LibP2PModel(
        cache_manager=mock_cache_manager,
        credential_manager=mock_credential_manager,
        metadata={"auto_install_dependencies": False},  # Prevent auto-install attempt
    )
    # Ensure the instance reflects the desired state for this fixture
    model.is_available = MagicMock(return_value=False)  # Patch instance directly
    model.libp2p_peer = None  # Ensure peer is None
    return model


# --- Test Class ---


class TestLibP2PModel:
    def test_initialization_with_deps(self, libp2p_model):
        """Test model initialization when dependencies are available."""
        assert libp2p_model.is_available()
        assert libp2p_model.libp2p_peer is not None
        assert libp2p_model.cache_manager == mock_cache_manager
        assert libp2p_model.credential_manager == mock_credential_manager

    def test_initialization_without_deps(self, libp2p_model_no_deps):
        """Test model initialization when dependencies are missing."""
        assert not libp2p_model_no_deps.is_available()
        assert libp2p_model_no_deps.libp2p_peer is None

    def test_is_available(self, libp2p_model, libp2p_model_no_deps):
        """Test the is_available method."""
        assert libp2p_model.is_available()
        assert not libp2p_model_no_deps.is_available()

    # --- Health & Stats ---

    def test_get_health_success(self, libp2p_model):
        """Test get_health when peer is healthy."""
        result = libp2p_model.get_health()
        assert result["success"]
        assert result["libp2p_available"]
        assert result["peer_initialized"]
        assert result["peer_id"] == "MockPeerID"
        assert result["addresses"] == ["/ip4/127.0.0.1/tcp/4001"]
        assert result["connected_peers"] == 2
        assert "stats" in result
        mock_cache_manager.put.assert_called_once()

    def test_get_health_no_deps(self, libp2p_model_no_deps):
        """Test get_health when dependencies are missing."""
        result = libp2p_model_no_deps.get_health()
        assert not result["success"]
        assert not result["libp2p_available"]
        assert not result["peer_initialized"]
        assert result["error"] == "libp2p is not available"

    def test_get_stats(self, libp2p_model):
        """Test get_stats method."""
        libp2p_model.operation_stats["peers_discovered"] = 5  # Set some stat
        result = libp2p_model.get_stats()
        assert result["success"]
        assert "stats" in result
        assert result["stats"]["peers_discovered"] == 5
        assert "uptime" in result

    def test_reset(self, libp2p_model):
        """Test the reset method."""
        libp2p_model.operation_stats["operation_count"] = 10
        libp2p_model.operation_stats["peers_discovered"] = 5
        result = libp2p_model.reset()
        assert result["success"]
        assert libp2p_model.operation_stats["operation_count"] == 0
        assert libp2p_model.operation_stats["peers_discovered"] == 0
        # Check if cache clear was attempted
        mock_cache_manager.list_keys.assert_called_once()
        assert mock_cache_manager.delete.call_count == 2  # Based on list_keys return value

    # --- Lifecycle ---

    def test_start_success(self, libp2p_model):
        """Test starting the peer."""
        # Ensure peer is mocked as not running initially
        libp2p_model.libp2p_peer._running = False
        result = libp2p_model.start()
        assert result["success"]
        libp2p_model.libp2p_peer.start.assert_called_once()

    def test_start_already_running(self, libp2p_model):
        """Test starting when already running."""
        libp2p_model.libp2p_peer._running = True  # Mock as running
        result = libp2p_model.start()
        assert result["success"]
        assert result.get("already_running")
        libp2p_model.libp2p_peer.start.assert_not_called()

    def test_start_no_deps(self, libp2p_model_no_deps):
        """Test start when dependencies are missing."""
        result = libp2p_model_no_deps.start()
        assert not result["success"]
        assert result["error"] == "libp2p dependencies are not available"

    def test_stop_success(self, libp2p_model):
        """Test stopping the peer."""
        result = libp2p_model.stop()
        assert result["success"]
        libp2p_model.libp2p_peer.close.assert_called_once()

    def test_stop_no_deps(self, libp2p_model_no_deps):
        """Test stop when dependencies are missing."""
        result = libp2p_model_no_deps.stop()
        assert not result["success"]
        assert result["error"] == "libp2p is not available"

    # --- Peer Discovery & Connection ---

    def test_discover_peers_all(self, libp2p_model):
        """Test discovering peers using 'all' methods."""
        # Reset connect_peer mock specifically for this test if needed
        libp2p_model.libp2p_peer.connect_peer.reset_mock()
        mock_enhanced_dht_discovery.discover_peers.reset_mock()  # Reset this too
        libp2p_model.libp2p_peer.discover_peers_mdns.reset_mock()

        result = libp2p_model.discover_peers(discovery_method="all", limit=5)
        assert result["success"]
        # Expect EnhancedDHTPeer now
        assert "EnhancedDHTPeer" in result["peers"]
        assert "MDNSPeerDiscovered" in result["peers"]
        # Check if bootstrap connect was attempted (mock connect_peer)
        libp2p_model.libp2p_peer.connect_peer.assert_called()
        mock_cache_manager.put.assert_called_once()

    def test_discover_peers_dht_only(self, libp2p_model):
        """Test discovering peers using only DHT."""
        # Reset specific mocks for this test
        mock_enhanced_dht_discovery.discover_peers.reset_mock()
        libp2p_model.libp2p_peer.discover_peers_dht.reset_mock()
        libp2p_model.libp2p_peer.discover_peers_mdns.reset_mock()

        result = libp2p_model.discover_peers(discovery_method="dht", limit=5)
        assert result["success"]
        # Expect EnhancedDHTPeer now
        assert result["peers"] == ["EnhancedDHTPeer"]
        # Check that the enhanced discovery mock was called
        mock_enhanced_dht_discovery.discover_peers.assert_called_once_with(limit=5)
        libp2p_model.libp2p_peer.discover_peers_dht.assert_not_called()  # Ensure old method not called
        libp2p_model.libp2p_peer.discover_peers_mdns.assert_not_called()

    def test_discover_peers_no_deps(self, libp2p_model_no_deps):
        """Test discover_peers when dependencies are missing."""
        result = libp2p_model_no_deps.discover_peers()
        assert not result["success"]
        assert result["error"] == "libp2p is not available"

    def test_connect_peer_success(self, libp2p_model):
        """Test connecting to a peer successfully."""
        peer_addr = "/ip4/1.2.3.4/tcp/4002/p2p/PeerToConnect"
        result = libp2p_model.connect_peer(peer_addr)
        assert result["success"]
        libp2p_model.libp2p_peer.connect_peer.assert_called_once_with(peer_addr)
        libp2p_model.libp2p_peer.get_peer_info.assert_called_once_with(
            peer_addr
        )  # Checks if info is fetched after connect

    def test_connect_peer_failure(self, libp2p_model):
        """Test connecting to a peer when the connection fails."""
        libp2p_model.libp2p_peer.connect_peer.return_value = False  # Simulate failure
        peer_addr = "/ip4/1.2.3.4/tcp/4002/p2p/PeerToConnect"
        result = libp2p_model.connect_peer(peer_addr)
        assert not result["success"]
        assert result["error_type"] == "connection_failed"

    def test_connect_peer_no_deps(self, libp2p_model_no_deps):
        """Test connect_peer when dependencies are missing."""
        result = libp2p_model_no_deps.connect_peer("/ip4/1.2.3.4/tcp/4002/p2p/PeerToConnect")
        assert not result["success"]
        assert result["error"] == "libp2p is not available"

    def test_get_connected_peers(self, libp2p_model):
        """Test getting the list of connected peers."""
        result = libp2p_model.get_connected_peers()
        assert result["success"]
        assert result["peers"] == ["Peer1", "Peer2"]
        assert result["peer_count"] == 2
        libp2p_model.libp2p_peer.get_connected_peers.assert_called_once()
        mock_cache_manager.put.assert_called_once()

    def test_get_peer_info_success(self, libp2p_model):
        """Test getting info for a specific peer."""
        peer_id = "Peer1"
        result = libp2p_model.get_peer_info(peer_id)
        assert result["success"]
        assert result["protocols"] == ["/test/1.0"]
        libp2p_model.libp2p_peer.get_peer_info.assert_called_once_with(peer_id)

    def test_get_peer_info_not_found(self, libp2p_model):
        """Test getting info for a peer that is not found."""
        libp2p_model.libp2p_peer.get_peer_info.return_value = None  # Simulate not found
        peer_id = "UnknownPeer"
        result = libp2p_model.get_peer_info(peer_id)
        assert not result["success"]
        assert result["error_type"] == "peer_not_found"

    # --- Content Routing & Retrieval ---

    def test_find_content_success(self, libp2p_model):
        """Test finding content providers successfully."""
        cid = "QmTestContent"
        result = libp2p_model.find_content(cid, timeout=10)
        assert result["success"]
        assert result["providers"] == ["ProviderPeer1"]
        libp2p_model.libp2p_peer.find_providers.assert_called_once_with(cid, timeout=10)
        mock_cache_manager.put.assert_called_once()  # Check caching

    def test_find_content_cached(self, libp2p_model):
        """Test finding content when result is cached."""
        cid = "QmCachedContent"
        cached_data = {
            "success": True,
            "operation": "find_content",
            "cid": cid,
            "timestamp": time.time() - 10,
            "providers": ["CachedProvider"],
            "provider_count": 1,
        }
        mock_cache_manager.get.return_value = cached_data
        result = libp2p_model.find_content(cid)
        assert result == cached_data
        mock_cache_manager.get.assert_called_once_with(f"libp2p_find_content_{cid}")
        libp2p_model.libp2p_peer.find_providers.assert_not_called()

    def test_find_content_no_deps(self, libp2p_model_no_deps):
        """Test find_content when dependencies are missing."""
        result = libp2p_model_no_deps.find_content("QmTestContent")
        assert not result["success"]
        assert result["error"] == "libp2p is not available"

    def test_retrieve_content_info_success(self, libp2p_model):
        """Test retrieving content info successfully."""
        cid = "QmTestContent"
        result = libp2p_model.retrieve_content(cid, timeout=15)
        assert result["success"]
        assert result["content_available"]
        assert result["size"] == len(b"mock_content_data")
        libp2p_model.libp2p_peer.retrieve_content.assert_called_once_with(cid, timeout=15)
        # Check that both content and info are cached
        assert mock_cache_manager.put.call_count == 2

    def test_retrieve_content_info_not_found(self, libp2p_model):
        """Test retrieving content info when content is not found."""
        cid = "QmNotFound"
        libp2p_model.libp2p_peer.retrieve_content.return_value = None  # Simulate not found
        result = libp2p_model.retrieve_content(cid)
        assert not result["success"]
        assert not result["content_available"]
        assert result["error_type"] == "content_not_found"

    def test_get_content_success(self, libp2p_model):
        """Test getting actual content data successfully."""
        cid = "QmGetData"
        # Ensure the mock returns the expected data
        mock_libp2p_peer.retrieve_content.return_value = b"mock_content_data"
        result = libp2p_model.get_content(cid, timeout=20)
        # Check the actual result dictionary for success and data
        assert result.get("success") is True, f"Expected success=True, got {result}"
        assert result.get("data") == b"mock_content_data"
        assert result.get("size") == len(b"mock_content_data")
        libp2p_model.libp2p_peer.retrieve_content.assert_called_once_with(cid, timeout=20)
        mock_cache_manager.put.assert_called_once()  # Check caching

    def test_get_content_cached(self, libp2p_model):
        """Test getting content when it's already cached."""
        cid = "QmCachedData"
        mock_cache_manager.get.return_value = b"cached_data_bytes"
        result = libp2p_model.get_content(cid)
        assert result["success"]
        assert result["data"] == b"cached_data_bytes"
        assert result["from_cache"]
        mock_cache_manager.get.assert_called_once_with(f"libp2p_content_{cid}")
        libp2p_model.libp2p_peer.retrieve_content.assert_not_called()

    def test_announce_content_success(self, libp2p_model):
        """Test announcing content successfully."""
        cid = "QmAnnounce"
        data = b"announce_data"
        result = libp2p_model.announce_content(cid, data=data)
        assert result["success"]
        libp2p_model.libp2p_peer.store_content_locally.assert_called_once_with(cid, data)
        libp2p_model.libp2p_peer.announce_content.assert_called_once_with(cid)
        mock_cache_manager.put.assert_called_once()  # Check caching

    # --- DHT Operations ---

    def test_dht_find_peer_success(self, libp2p_model):
        """Test finding a peer via DHT."""
        peer_id = "DHTFindPeerID"
        result = libp2p_model.dht_find_peer(peer_id, timeout=10)
        assert result["success"]
        assert result["addresses"] == ["/ip4/1.2.3.4/tcp/4001"]
        libp2p_model.libp2p_peer.find_peer_addresses.assert_called_once_with(peer_id, timeout=10)

    def test_dht_find_peer_not_found(self, libp2p_model):
        """Test finding a peer via DHT when not found."""
        libp2p_model.libp2p_peer.find_peer_addresses.return_value = []  # Simulate not found
        peer_id = "DHTNotFoundPeerID"
        result = libp2p_model.dht_find_peer(peer_id)
        assert not result["success"]
        assert result["error_type"] == "peer_not_found"

    def test_dht_provide_success(self, libp2p_model):
        """Test providing content via DHT."""
        cid = "QmProvideContent"
        result = libp2p_model.dht_provide(cid)
        assert result["success"]
        libp2p_model.libp2p_peer.provide_content.assert_called_once_with(cid)

    def test_dht_find_providers_success(self, libp2p_model):
        """Test finding providers via DHT."""
        cid = "QmFindProviders"
        result = libp2p_model.dht_find_providers(cid, timeout=15, limit=5)
        assert result["success"]
        assert result["providers"] == ["ProviderPeer1"]
        libp2p_model.libp2p_peer.find_providers.assert_called_once_with(cid, timeout=15)

    # --- PubSub Operations ---

    def test_pubsub_publish_success(self, libp2p_model):
        """Test publishing a message via PubSub."""
        topic = "/test/publish"
        message = "hello world"
        result = libp2p_model.pubsub_publish(topic, message)
        assert result["success"]
        libp2p_model.libp2p_peer.publish_message.assert_called_once_with(
            topic, message.encode("utf-8")
        )

    def test_pubsub_publish_json_success(self, libp2p_model):
        """Test publishing a JSON message via PubSub."""
        topic = "/test/publish_json"
        message = {"key": "value"}
        expected_data = b'{"key": "value"}'
        result = libp2p_model.pubsub_publish(topic, message)
        assert result["success"]
        libp2p_model.libp2p_peer.publish_message.assert_called_once_with(topic, expected_data)

    def test_pubsub_subscribe_success(self, libp2p_model):
        """Test subscribing to a PubSub topic."""
        topic = "/test/subscribe"
        result = libp2p_model.pubsub_subscribe(topic, handler_id="test_handler_1")
        assert result["success"]
        assert result["handler_id"] == "test_handler_1"
        libp2p_model.libp2p_peer.subscribe.assert_called_once()  # Check direct subscribe call
        assert topic in libp2p_model.active_subscriptions
        assert "test_handler_1" in libp2p_model.active_subscriptions[topic]

    def test_pubsub_unsubscribe_success(self, libp2p_model):
        """Test unsubscribing from a PubSub topic."""
        topic = "/test/unsubscribe"
        # First subscribe to have something to unsubscribe from
        libp2p_model.pubsub_subscribe(topic, handler_id="handler_to_remove")
        libp2p_model.libp2p_peer.subscribe.reset_mock()  # Reset mock after setup

        result = libp2p_model.pubsub_unsubscribe(topic, handler_id="handler_to_remove")
        assert result["success"]
        libp2p_model.libp2p_peer.unsubscribe.assert_called_once_with(
            topic
        )  # Check direct unsubscribe call
        assert topic not in libp2p_model.active_subscriptions  # Check internal tracking

    def test_pubsub_get_topics(self, libp2p_model):
        """Test getting the list of subscribed topics."""
        # Subscribe to setup
        libp2p_model.pubsub_subscribe("/test/topic1", handler_id="h1")
        # Reset mock before the actual call in the method under test
        libp2p_model.libp2p_peer.get_topics.reset_mock()
        libp2p_model.libp2p_peer.get_topics.return_value = ["/test/topic1"]  # Mock underlying call

        result = libp2p_model.pubsub_get_topics()
        assert result["success"]
        libp2p_model.libp2p_peer.get_topics.assert_called_once()  # Verify the correct mock was called
        assert result["topics"] == ["/test/topic1"]
        assert len(result["topic_details"]) == 1
        assert result["topic_details"][0]["topic"] == "/test/topic1"
        assert len(result["topic_details"][0]["handlers"]) == 1
        assert result["topic_details"][0]["handlers"][0]["handler_id"] == "h1"

    def test_pubsub_get_peers_for_topic(self, libp2p_model):
        """Test getting peers for a specific topic."""
        topic = "/test/getpeers"
        # Reset mock before the actual call
        libp2p_model.libp2p_peer.get_topic_peers.reset_mock()
        libp2p_model.libp2p_peer.get_topic_peers.return_value = [
            "PubSubPeer1"
        ]  # Ensure return value is set

        result = libp2p_model.pubsub_get_peers(topic=topic)
        assert result["success"]
        assert result["peers"] == ["PubSubPeer1"]
        libp2p_model.libp2p_peer.get_topic_peers.assert_called_once_with(
            topic
        )  # Verify correct mock

    # --- Message Handlers (Internal, not directly exposed via API but used by PubSub) ---

    def test_register_message_handler(self, libp2p_model):
        """Test registering an internal message handler."""
        topic = "/internal/handler"
        handler_func = MagicMock()
        handler_id = "internal_h1"
        result = libp2p_model.register_message_handler(topic, handler_func, handler_id)
        assert result["success"]
        assert topic in libp2p_model.topic_handlers
        assert handler_id in libp2p_model.topic_handlers[topic]
        # Check if subscribe was called because it was the first handler for the topic
        libp2p_model.libp2p_peer.subscribe.assert_called_once()  # Check direct subscribe call

    def test_unregister_message_handler(self, libp2p_model):
        """Test unregistering an internal message handler."""
        topic = "/internal/handler"
        handler_func = MagicMock()
        handler_id = "internal_h1"
        # Register first
        libp2p_model.register_message_handler(topic, handler_func, handler_id)
        libp2p_model.libp2p_peer.subscribe.reset_mock()  # Reset mock after setup

        result = libp2p_model.unregister_message_handler(topic, handler_id)
        assert result["success"]
        assert topic not in libp2p_model.topic_handlers  # Should be empty now

    def test_list_message_handlers(self, libp2p_model):
        """Test listing registered internal message handlers."""
        topic = "/internal/list"
        handler_func = MagicMock(__name__="mock_handler_func")
        handler_id = "list_h1"
        libp2p_model.register_message_handler(topic, handler_func, handler_id)

        result = libp2p_model.list_message_handlers()
        assert result["success"]
        assert topic in result["handlers"]
        assert handler_id in result["handlers"][topic]
        assert result["handlers"][topic][handler_id]["function_name"] == "mock_handler_func"
