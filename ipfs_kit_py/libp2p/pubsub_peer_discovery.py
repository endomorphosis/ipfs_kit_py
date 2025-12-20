"""
Pubsub-based peer discovery implementation.

This module implements peer discovery using GossipSub pubsub topics. Peers
periodically announce themselves on a discovery topic, allowing other peers
to discover them without requiring DHT or other infrastructure.

This is particularly useful for:
- Browser peers that can't run full DHT
- Quick peer discovery in small networks
- Application-specific peer discovery
- Discovery within specific communities/rooms

References:
- https://github.com/libp2p/js-libp2p-pubsub-peer-discovery
"""

import anyio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any

try:
    from multiaddr import Multiaddr
    HAS_MULTIADDR = True
except ImportError:
    HAS_MULTIADDR = False
    Multiaddr = object

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPeer:
    """Represents a peer discovered via pubsub."""
    peer_id: str
    multiaddrs: List[str] = field(default_factory=list)
    protocols: List[str] = field(default_factory=list)
    agent_version: Optional[str] = None
    discovered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_stale(self, ttl: float) -> bool:
        """Check if peer info is stale."""
        return (time.time() - self.last_seen) > ttl
    
    def update_seen(self):
        """Update last seen timestamp."""
        self.last_seen = time.time()


class PubsubPeerDiscovery:
    """
    Pubsub-based peer discovery using GossipSub.
    
    This class implements a peer discovery mechanism that uses pubsub topics
    to announce and discover peers. Peers periodically broadcast their
    information on a discovery topic.
    """
    
    def __init__(
        self,
        host,
        topics: Optional[List[str]] = None,
        interval: float = 10.0,
        listen_only: bool = False,
        peer_ttl: float = 300.0,
        on_peer_discovered: Optional[Callable[[DiscoveredPeer], None]] = None
    ):
        """
        Initialize pubsub peer discovery.
        
        Args:
            host: The libp2p host
            topics: List of discovery topics to use
            interval: Interval in seconds between announcements
            listen_only: If True, only listen for peers, don't announce
            peer_ttl: Time-to-live for peer information in seconds
            on_peer_discovered: Callback for when new peer is discovered
        """
        self.host = host
        self.topics = topics or ["_peer-discovery._p2p._pubsub"]
        self.interval = interval
        self.listen_only = listen_only
        self.peer_ttl = peer_ttl
        self.on_peer_discovered = on_peer_discovered
        
        self.discovered_peers: Dict[str, DiscoveredPeer] = {}
        self.subscriptions: Dict[str, Any] = {}
        
        self.logger = logging.getLogger("PubsubPeerDiscovery")
        self._running = False
        self._task_group = None
    
    async def start(self):
        """Start the peer discovery service."""
        if self._running:
            return
        
        self._running = True
        
        # Subscribe to discovery topics
        for topic in self.topics:
            await self._subscribe_to_topic(topic)
        
        # Start announcement loop if not listen-only
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            if not self.listen_only:
                tg.start_soon(self._announcement_loop)
            tg.start_soon(self._cleanup_loop)
        
        self.logger.info(f"Pubsub peer discovery started on topics: {self.topics}")
    
    async def stop(self):
        """Stop the peer discovery service."""
        self._running = False
        
        # Unsubscribe from all topics
        for topic in list(self.subscriptions.keys()):
            await self._unsubscribe_from_topic(topic)
        
        self.logger.info("Pubsub peer discovery stopped")
    
    async def _subscribe_to_topic(self, topic: str):
        """Subscribe to a discovery topic."""
        try:
            # Get pubsub service
            pubsub = self._get_pubsub()
            if not pubsub:
                self.logger.warning("Pubsub service not available")
                return
            
            # Subscribe to topic
            if hasattr(pubsub, 'subscribe'):
                await pubsub.subscribe(topic)
                self.subscriptions[topic] = True
                self.logger.debug(f"Subscribed to discovery topic: {topic}")
                
                # Start listening for messages
                anyio.from_thread.run_sync(self._listen_to_topic, topic)
                
        except Exception as e:
            self.logger.error(f"Failed to subscribe to topic {topic}: {e}")
    
    async def _unsubscribe_from_topic(self, topic: str):
        """Unsubscribe from a discovery topic."""
        try:
            pubsub = self._get_pubsub()
            if pubsub and hasattr(pubsub, 'unsubscribe'):
                await pubsub.unsubscribe(topic)
                del self.subscriptions[topic]
                self.logger.debug(f"Unsubscribed from discovery topic: {topic}")
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from topic {topic}: {e}")
    
    async def _listen_to_topic(self, topic: str):
        """Listen for messages on a discovery topic."""
        pubsub = self._get_pubsub()
        if not pubsub:
            return
        
        try:
            # This depends on the pubsub implementation
            # For GossipSub, we need to handle incoming messages
            if hasattr(pubsub, 'messages'):
                async for message in pubsub.messages(topic):
                    if not self._running:
                        break
                    await self._handle_discovery_message(message)
                    
        except Exception as e:
            self.logger.error(f"Error listening to topic {topic}: {e}")
    
    async def _announcement_loop(self):
        """Periodically announce our presence."""
        while self._running:
            try:
                await self._announce_self()
                await anyio.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Error in announcement loop: {e}")
                await anyio.sleep(self.interval)
    
    async def _announce_self(self):
        """Announce ourselves on discovery topics."""
        announcement = self._create_announcement()
        
        pubsub = self._get_pubsub()
        if not pubsub:
            return
        
        for topic in self.topics:
            try:
                if hasattr(pubsub, 'publish'):
                    await pubsub.publish(topic, announcement)
                    self.logger.debug(f"Announced on topic: {topic}")
            except Exception as e:
                self.logger.error(f"Failed to announce on topic {topic}: {e}")
    
    def _create_announcement(self) -> bytes:
        """Create a peer announcement message."""
        # Get our peer info
        peer_id = str(self.host.get_id()) if hasattr(self.host, 'get_id') else "unknown"
        
        # Get our multiaddrs
        addrs = []
        if hasattr(self.host, 'get_addrs'):
            addrs = [str(addr) for addr in self.host.get_addrs()]
        
        # Get our protocols
        protocols = []
        if hasattr(self.host, 'get_protocols'):
            protocols = list(self.host.get_protocols())
        
        # Create announcement
        announcement = {
            "type": "peer-discovery",
            "peer_id": peer_id,
            "multiaddrs": addrs,
            "protocols": protocols,
            "timestamp": time.time()
        }
        
        # Add optional metadata
        if hasattr(self, 'metadata'):
            announcement["metadata"] = self.metadata
        
        return json.dumps(announcement).encode()
    
    async def _handle_discovery_message(self, message):
        """Handle an incoming discovery message."""
        try:
            # Parse message
            data = message.data if hasattr(message, 'data') else message
            announcement = json.loads(data.decode() if isinstance(data, bytes) else data)
            
            if announcement.get("type") != "peer-discovery":
                return
            
            peer_id = announcement.get("peer_id")
            if not peer_id:
                return
            
            # Don't process our own announcements
            our_id = str(self.host.get_id()) if hasattr(self.host, 'get_id') else None
            if peer_id == our_id:
                return
            
            # Check if we already know this peer
            if peer_id in self.discovered_peers:
                peer = self.discovered_peers[peer_id]
                peer.update_seen()
                
                # Update multiaddrs if changed
                new_addrs = announcement.get("multiaddrs", [])
                if set(new_addrs) != set(peer.multiaddrs):
                    peer.multiaddrs = new_addrs
                    self.logger.debug(f"Updated addresses for peer {peer_id}")
            else:
                # New peer discovered
                peer = DiscoveredPeer(
                    peer_id=peer_id,
                    multiaddrs=announcement.get("multiaddrs", []),
                    protocols=announcement.get("protocols", []),
                    metadata=announcement.get("metadata", {})
                )
                
                self.discovered_peers[peer_id] = peer
                self.logger.info(f"Discovered new peer: {peer_id}")
                
                # Call discovery callback
                if self.on_peer_discovered:
                    try:
                        self.on_peer_discovered(peer)
                    except Exception as e:
                        self.logger.error(f"Error in discovery callback: {e}")
                
                # Optionally auto-connect to discovered peer
                if hasattr(self, 'auto_connect') and self.auto_connect:
                    await self._connect_to_peer(peer)
                    
        except Exception as e:
            self.logger.error(f"Error handling discovery message: {e}")
    
    async def _connect_to_peer(self, peer: DiscoveredPeer):
        """Attempt to connect to a discovered peer."""
        for addr in peer.multiaddrs:
            try:
                if hasattr(self.host, 'connect'):
                    await self.host.connect(addr)
                    self.logger.info(f"Connected to discovered peer {peer.peer_id}")
                    return
            except Exception as e:
                self.logger.debug(f"Failed to connect to {peer.peer_id} at {addr}: {e}")
    
    async def _cleanup_loop(self):
        """Periodically cleanup stale peer information."""
        while self._running:
            try:
                await anyio.sleep(60)  # Cleanup every minute
                
                now = time.time()
                stale_peers = [
                    peer_id for peer_id, peer in self.discovered_peers.items()
                    if peer.is_stale(self.peer_ttl)
                ]
                
                for peer_id in stale_peers:
                    del self.discovered_peers[peer_id]
                    self.logger.debug(f"Removed stale peer: {peer_id}")
                    
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
    
    def _get_pubsub(self):
        """Get the pubsub service from the host."""
        if hasattr(self.host, 'get_pubsub'):
            return self.host.get_pubsub()
        elif hasattr(self.host, 'pubsub'):
            return self.host.pubsub
        elif hasattr(self.host, '_pubsub'):
            return self.host._pubsub
        return None
    
    def get_discovered_peers(self) -> List[DiscoveredPeer]:
        """Get list of discovered peers."""
        return list(self.discovered_peers.values())
    
    def get_peer_by_id(self, peer_id: str) -> Optional[DiscoveredPeer]:
        """Get a specific peer by ID."""
        return self.discovered_peers.get(peer_id)
    
    def clear_stale_peers(self):
        """Manually clear all stale peers."""
        stale_peers = [
            peer_id for peer_id, peer in self.discovered_peers.items()
            if peer.is_stale(self.peer_ttl)
        ]
        
        for peer_id in stale_peers:
            del self.discovered_peers[peer_id]
        
        return len(stale_peers)


def integrate_pubsub_discovery(host, **kwargs):
    """
    Convenience function to integrate pubsub discovery with a libp2p host.
    
    Args:
        host: The libp2p host
        **kwargs: Arguments to pass to PubsubPeerDiscovery
        
    Returns:
        PubsubPeerDiscovery instance
    """
    discovery = PubsubPeerDiscovery(host, **kwargs)
    
    # Add discovery as an attribute to the host
    if not hasattr(host, '_peer_discovery'):
        host._peer_discovery = []
    host._peer_discovery.append(discovery)
    
    # Add convenience methods
    def get_discovered_peers():
        """Get all discovered peers from all discovery services."""
        peers = []
        for disc in getattr(host, '_peer_discovery', []):
            peers.extend(disc.get_discovered_peers())
        return peers
    
    host.get_discovered_peers = get_discovered_peers
    
    return discovery
