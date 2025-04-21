"""
Mock classes for MCP discovery testing.

This module provides mock implementations of MCP discovery classes
to allow tests to run without actual implementation.
"""

import json
import logging
import asyncio
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union, Callable, Set

logger = logging.getLogger(__name__)


class MCPMessageType(Enum):
    """Types of messages used in MCP discovery protocol."""
    ANNOUNCE = auto()
    DISCOVER = auto()
    PUBLISH = auto()
    SUBSCRIBE = auto()
    UNSUBSCRIBE = auto()
    HEARTBEAT = auto()
    STATUS = auto()
    ERROR = auto()
    RESPONSE = auto()
    ACK = auto()


class MCPServerRole(Enum):
    """Roles for MCP servers in the discovery network."""
    MASTER = "master"
    WORKER = "worker"
    LEECHER = "leecher"
    GATEWAY = "gateway"
    RELAY = "relay"


class MCPServerCapabilities:
    """Mock for MCP Server capabilities."""
    
    def __init__(self, **kwargs):
        self.storage_backends = kwargs.get("storage_backends", ["ipfs", "filecoin"])
        self.content_routing = kwargs.get("content_routing", ["ipfs-dht", "ipfs-delegated"])
        self.pubsub_protocols = kwargs.get("pubsub_protocols", ["floodsub", "gossipsub"])
        self.supported_apis = kwargs.get("supported_apis", ["ipfs", "libp2p", "search", "storage"])
        self.version = kwargs.get("version", "0.1.0")
        self.extensions = kwargs.get("extensions", ["auth", "metrics", "search"])
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert capabilities to dictionary format."""
        return {
            "storage_backends": self.storage_backends,
            "content_routing": self.content_routing,
            "pubsub_protocols": self.pubsub_protocols,
            "supported_apis": self.supported_apis,
            "version": self.version,
            "extensions": self.extensions
        }
        
    def to_json(self) -> str:
        """Convert capabilities to JSON string."""
        return json.dumps(self.to_dict())
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPServerCapabilities':
        """Create capabilities from dictionary."""
        return cls(**data)
        
    @classmethod
    def from_json(cls, json_str: str) -> 'MCPServerCapabilities':
        """Create capabilities from JSON string."""
        return cls.from_dict(json.loads(json_str))


class MCPDiscoveryMock:
    """Mock implementation of MCP discovery functionality."""
    
    def __init__(self):
        self.peers = {}
        self.announcements = []
        self.subscriptions = []
        self.listeners = []
    
    def announce(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Announce a server to the discovery network."""
        server_id = server_info.get("id", f"server-{len(self.peers)}")
        self.peers[server_id] = server_info
        self.announcements.append(server_info)
        logger.info(f"Server announced: {server_id}")
        return {"success": True, "server_id": server_id}
    
    async def announce_async(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronous version of announce."""
        return self.announce(server_info)
    
    def discover(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Discover servers based on filter criteria."""
        if not filter_criteria:
            return list(self.peers.values())
        
        result = []
        for peer_id, peer_info in self.peers.items():
            match = True
            for key, value in filter_criteria.items():
                if key not in peer_info or peer_info[key] != value:
                    match = False
                    break
            if match:
                result.append(peer_info)
        
        logger.info(f"Discovered {len(result)} peers matching criteria: {filter_criteria}")
        return result
    
    async def discover_async(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Asynchronous version of discover."""
        return self.discover(filter_criteria)
    
    def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to a discovery topic."""
        subscription_id = f"sub-{len(self.subscriptions)}"
        self.subscriptions.append({
            "id": subscription_id,
            "topic": topic,
            "callback": callback
        })
        logger.info(f"Subscribed to topic: {topic} with ID: {subscription_id}")
        return subscription_id
    
    async def subscribe_async(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> str:
        """Asynchronous version of subscribe."""
        return self.subscribe(topic, callback)
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from a discovery topic."""
        for i, sub in enumerate(self.subscriptions):
            if sub["id"] == subscription_id:
                self.subscriptions.pop(i)
                logger.info(f"Unsubscribed from subscription: {subscription_id}")
                return True
        
        logger.warning(f"Subscription not found: {subscription_id}")
        return False
    
    async def unsubscribe_async(self, subscription_id: str) -> bool:
        """Asynchronous version of unsubscribe."""
        return self.unsubscribe(subscription_id)
    
    def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a discovery topic."""
        logger.info(f"Publishing to topic: {topic}, message: {message}")
        for sub in self.subscriptions:
            if sub["topic"] == topic:
                try:
                    sub["callback"](message)
                except Exception as e:
                    logger.error(f"Error in subscription callback: {e}")
        return True
    
    async def publish_async(self, topic: str, message: Dict[str, Any]) -> bool:
        """Asynchronous version of publish."""
        return self.publish(topic, message)
    
    def register_listener(self, listener: Callable[[Dict[str, Any]], None]) -> str:
        """Register a listener for all discovery events."""
        listener_id = f"listener-{len(self.listeners)}"
        self.listeners.append({
            "id": listener_id,
            "callback": listener
        })
        logger.info(f"Registered discovery listener: {listener_id}")
        return listener_id
    
    async def register_listener_async(self, listener: Callable[[Dict[str, Any]], None]) -> str:
        """Asynchronous version of register_listener."""
        return self.register_listener(listener)
    
    def unregister_listener(self, listener_id: str) -> bool:
        """Unregister a discovery listener."""
        for i, listener in enumerate(self.listeners):
            if listener["id"] == listener_id:
                self.listeners.pop(i)
                logger.info(f"Unregistered discovery listener: {listener_id}")
                return True
        
        logger.warning(f"Listener not found: {listener_id}")
        return False
    
    async def unregister_listener_async(self, listener_id: str) -> bool:
        """Asynchronous version of unregister_listener."""
        return self.unregister_listener(listener_id)
    
    def notify_listeners(self, event: Dict[str, Any]) -> None:
        """Notify all listeners of an event."""
        for listener in self.listeners:
            try:
                listener["callback"](event)
            except Exception as e:
                logger.error(f"Error in listener callback: {e}")
    
    async def notify_listeners_async(self, event: Dict[str, Any]) -> None:
        """Asynchronous version of notify_listeners."""
        self.notify_listeners(event)


class MockMCPDiscoveryModel:
    """Mock implementation of the MCP Discovery Model for testing."""
    
    def __init__(self):
        self.discovery_service = MCPDiscoveryMock()
        self.server_id = None
        self.server_info = {}
        self.discovered_peers = []
        self.is_connected = False
        
    async def connect(self) -> Dict[str, Any]:
        """Connect to the discovery network."""
        self.is_connected = True
        logger.info("Connected to discovery network")
        return {"success": True, "message": "Connected to discovery network"}
        
    async def disconnect(self) -> Dict[str, Any]:
        """Disconnect from the discovery network."""
        self.is_connected = False
        logger.info("Disconnected from discovery network")
        return {"success": True, "message": "Disconnected from discovery network"}
        
    async def announce(self, server_info: Dict[str, Any]) -> Dict[str, Any]:
        """Announce this server to the discovery network."""
        self.server_info = server_info
        result = await self.discovery_service.announce_async(server_info)
        self.server_id = result.get("server_id")
        return result
        
    async def discover(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Discover servers on the network."""
        self.discovered_peers = await self.discovery_service.discover_async(filter_criteria)
        return self.discovered_peers
        
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> str:
        """Subscribe to discovery notifications."""
        return await self.discovery_service.subscribe_async(topic, callback)
        
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from discovery notifications."""
        return await self.discovery_service.unsubscribe_async(subscription_id)
        
    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to the discovery network."""
        return await self.discovery_service.publish_async(topic, message)


class MCPDiscoveryService:
    """Mock for MCP Discovery Service."""
    
    def __init__(self, **kwargs):
        self.server_id = kwargs.get("server_id", "test-server-id")
        self.capabilities = kwargs.get("capabilities", MCPServerCapabilities())
        self.peers = kwargs.get("peers", {})
        self.bootstrap_nodes = kwargs.get("bootstrap_nodes", [])
        
    async def announce(self) -> bool:
        """Announce this server to the network."""
        logger.info(f"Announcing server {self.server_id} to network")
        return True
        
    async def discover(self, max_peers: int = 10) -> List[Dict[str, Any]]:
        """Discover other MCP servers in the network."""
        logger.info(f"Discovering up to {max_peers} peers")
        return [{"id": peer_id, "capabilities": caps.to_dict()} 
                for peer_id, caps in self.peers.items()][:max_peers]
                
    async def get_server_capabilities(self, server_id: str) -> Optional[MCPServerCapabilities]:
        """Get capabilities of a specific server."""
        if server_id in self.peers:
            return self.peers[server_id]
        logger.warning(f"Server {server_id} not found")
        return None
        
    async def update_capabilities(self, capabilities: MCPServerCapabilities) -> bool:
        """Update this server's capabilities."""
        self.capabilities = capabilities
        logger.info(f"Updated server {self.server_id} capabilities")
        return True


class MCPFeatureSet:
    """Represents a set of features supported by an MCP node."""
    
    def __init__(self, features: Optional[Set[str]] = None):
        """Initialize the feature set with optional initial values."""
        self.features = features or set()
    
    def has_feature(self, feature: str) -> bool:
        """Check if a specific feature is supported."""
        return feature in self.features
    
    def add_feature(self, feature: str) -> None:
        """Add a feature to the set of supported features."""
        self.features.add(feature)
    
    def remove_feature(self, feature: str) -> None:
        """Remove a feature from the set of supported features."""
        if feature in self.features:
            self.features.remove(feature)
    
    def get_all_features(self) -> Set[str]:
        """Get all supported features."""
        return self.features.copy()
    
    def is_compatible_with(self, other: 'MCPFeatureSet') -> bool:
        """Check if this feature set is compatible with another feature set."""
        return bool(self.features.intersection(other.features))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "features": list(self.features)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPFeatureSet':
        """Create from dictionary representation."""
        return cls(set(data.get("features", [])))


class EnhancedMCPDiscoveryTest:
    """Enhanced MCP Discovery Test."""
    
    def __init__(self, **kwargs):
        self.test_id = kwargs.get("test_id", "enhanced-test")
        self.discovery = MCPDiscoveryService(**kwargs)
        self.feature_set = kwargs.get("feature_set", MCPFeatureSet())
        
    async def run_discovery_test(self) -> Dict[str, Any]:
        """Run a comprehensive discovery test."""
        logger.info(f"Running enhanced discovery test {self.test_id}")
        peers = await self.discovery.discover()
        return {
            "test_id": self.test_id,
            "peers_found": len(peers),
            "peers": peers,
            "success": True,
            "features": self.feature_set.to_dict()
        }
        
    async def test_capabilities_exchange(self) -> Dict[str, Any]:
        """Test capabilities exchange between peers."""
        logger.info(f"Testing capabilities exchange for test {self.test_id}")
        return {
            "test_id": self.test_id,
            "capabilities_exchanged": True,
            "success": True,
            "features": self.feature_set.get_all_features()
        }