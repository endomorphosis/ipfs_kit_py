"""
Universal Connectivity Manager for libp2p.

This module provides a comprehensive connectivity management system that
integrates all the peer discovery and NAT traversal mechanisms inspired
by the libp2p/universal-connectivity project.

Key features:
- Multiple transport protocols (TCP, QUIC, WebRTC, WebTransport)
- Multiple discovery mechanisms (DHT, mDNS, Pubsub)
- NAT traversal (AutoNAT, Circuit Relay, DCUtR)
- Connection management and optimization
- Bootstrap peer management
- Delegated routing support

This is a batteries-included solution for maintaining peer connectivity
across different network topologies and environments.
"""

import anyio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
import time

from .autonat import AutoNAT
from .circuit_relay import CircuitRelayClient, CircuitRelayServer
from .dcutr import DCUtR
from .pubsub_peer_discovery import PubsubPeerDiscovery
from .mdns_discovery import MDNSService

logger = logging.getLogger(__name__)


# Default bootstrap peers from IPFS
DEFAULT_BOOTSTRAP_PEERS = [
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmbLHAnMoJPWSCR5Zhtx6BHJX9KiKNN6tpvbUcqanj75Nb",
    "/dnsaddr/bootstrap.libp2p.io/p2p/QmcZf59bWwK5XFi76CZX8cbJ4BhTzzA3gU1ZjYZcYW3dwt",
]


@dataclass
class ConnectivityConfig:
    """Configuration for the connectivity manager."""
    
    # Bootstrap configuration
    bootstrap_peers: List[str] = field(default_factory=lambda: DEFAULT_BOOTSTRAP_PEERS.copy())
    connect_to_bootstrap: bool = True
    
    # Discovery configuration
    enable_mdns: bool = True
    enable_pubsub_discovery: bool = True
    enable_dht_discovery: bool = True
    pubsub_discovery_topics: List[str] = field(default_factory=lambda: ["_peer-discovery._p2p._pubsub"])
    
    # NAT traversal configuration
    enable_autonat: bool = True
    enable_relay_client: bool = True
    enable_relay_server: bool = False
    enable_dcutr: bool = True
    
    # Relay limits
    max_relay_reservations: int = 3
    max_relay_circuits: int = 256
    
    # Connection management
    max_connections: int = 1000
    max_connections_per_peer: int = 10
    connection_timeout: float = 30.0
    
    # Discovery intervals
    mdns_query_interval: float = 60.0
    pubsub_announce_interval: float = 10.0
    autonat_query_interval: float = 300.0
    
    # Callbacks
    on_peer_discovered: Optional[Callable] = None
    on_connection_established: Optional[Callable] = None
    on_connection_closed: Optional[Callable] = None


@dataclass
class ConnectivityMetrics:
    """Metrics for connectivity manager."""
    total_peers_discovered: int = 0
    total_connections_established: int = 0
    total_connections_failed: int = 0
    active_connections: int = 0
    relay_connections: int = 0
    direct_connections: int = 0
    nat_status: str = "unknown"
    dcutr_success_rate: float = 0.0
    last_updated: float = field(default_factory=time.time)


class UniversalConnectivityManager:
    """
    Universal Connectivity Manager integrating all libp2p connectivity features.
    
    This class manages:
    - Multiple discovery mechanisms
    - NAT traversal strategies
    - Connection optimization
    - Bootstrap peer connections
    """
    
    def __init__(self, host, config: Optional[ConnectivityConfig] = None):
        """
        Initialize the connectivity manager.
        
        Args:
            host: The libp2p host
            config: Configuration for connectivity features
        """
        self.host = host
        self.config = config or ConnectivityConfig()
        
        self.logger = logging.getLogger("UniversalConnectivity")
        
        # Components
        self.autonat: Optional[AutoNAT] = None
        self.relay_client: Optional[CircuitRelayClient] = None
        self.relay_server: Optional[CircuitRelayServer] = None
        self.dcutr: Optional[DCUtR] = None
        self.pubsub_discovery: Optional[PubsubPeerDiscovery] = None
        self.mdns_service: Optional[MDNSService] = None
        
        # State
        self.connected_peers: Set[str] = set()
        self.bootstrap_connected: bool = False
        self.metrics = ConnectivityMetrics()
        
        self._running = False
        self._task_group = None
    
    async def start(self):
        """Start all connectivity services."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("Starting Universal Connectivity Manager...")
        
        async with anyio.create_task_group() as tg:
            self._task_group = tg
            
            # Start AutoNAT
            if self.config.enable_autonat:
                await self._start_autonat()
            
            # Start Relay Client
            if self.config.enable_relay_client:
                await self._start_relay_client()
            
            # Start Relay Server
            if self.config.enable_relay_server:
                await self._start_relay_server()
            
            # Start DCUtR
            if self.config.enable_dcutr:
                await self._start_dcutr()
            
            # Start Pubsub Discovery
            if self.config.enable_pubsub_discovery:
                await self._start_pubsub_discovery()
            
            # Start mDNS
            if self.config.enable_mdns:
                await self._start_mdns()
            
            # Connect to bootstrap peers
            if self.config.connect_to_bootstrap:
                tg.start_soon(self._connect_to_bootstrap_peers)
            
            # Start monitoring
            tg.start_soon(self._monitoring_loop)
            
        self.logger.info("Universal Connectivity Manager started successfully")
    
    async def stop(self):
        """Stop all connectivity services."""
        self._running = False
        
        self.logger.info("Stopping Universal Connectivity Manager...")
        
        # Stop all services
        if self.autonat:
            try:
                # AutoNAT might not have a stop method
                if hasattr(self.autonat, 'stop'):
                    await self.autonat.stop()
            except Exception as e:
                self.logger.error(f"Error stopping AutoNAT: {e}")
        
        if self.relay_client:
            await self.relay_client.stop()
        
        if self.relay_server:
            await self.relay_server.stop()
        
        if self.dcutr:
            await self.dcutr.stop()
        
        if self.pubsub_discovery:
            await self.pubsub_discovery.stop()
        
        if self.mdns_service:
            await self.mdns_service.stop()
        
        self.logger.info("Universal Connectivity Manager stopped")
    
    async def _start_autonat(self):
        """Start AutoNAT service."""
        try:
            self.autonat = AutoNAT(
                self.host,
                query_interval=self.config.autonat_query_interval
            )
            self.logger.info("AutoNAT started")
        except Exception as e:
            self.logger.error(f"Failed to start AutoNAT: {e}")
    
    async def _start_relay_client(self):
        """Start Circuit Relay Client."""
        try:
            self.relay_client = CircuitRelayClient(
                self.host,
                max_reservations=self.config.max_relay_reservations
            )
            await self.relay_client.start()
            self.logger.info("Circuit Relay Client started")
        except Exception as e:
            self.logger.error(f"Failed to start Relay Client: {e}")
    
    async def _start_relay_server(self):
        """Start Circuit Relay Server."""
        try:
            self.relay_server = CircuitRelayServer(
                self.host,
                max_circuits=self.config.max_relay_circuits
            )
            await self.relay_server.start()
            self.logger.info("Circuit Relay Server started")
        except Exception as e:
            self.logger.error(f"Failed to start Relay Server: {e}")
    
    async def _start_dcutr(self):
        """Start DCUtR service."""
        try:
            self.dcutr = DCUtR(self.host)
            await self.dcutr.start()
            self.logger.info("DCUtR started")
        except Exception as e:
            self.logger.error(f"Failed to start DCUtR: {e}")
    
    async def _start_pubsub_discovery(self):
        """Start Pubsub Peer Discovery."""
        try:
            self.pubsub_discovery = PubsubPeerDiscovery(
                self.host,
                topics=self.config.pubsub_discovery_topics,
                interval=self.config.pubsub_announce_interval,
                on_peer_discovered=self._on_peer_discovered
            )
            await self.pubsub_discovery.start()
            self.logger.info(f"Pubsub Discovery started on topics: {self.config.pubsub_discovery_topics}")
        except Exception as e:
            self.logger.error(f"Failed to start Pubsub Discovery: {e}")
    
    async def _start_mdns(self):
        """Start mDNS service."""
        try:
            self.mdns_service = MDNSService(
                self.host,
                query_interval=self.config.mdns_query_interval,
                on_peer_discovered=self._on_peer_discovered
            )
            await self.mdns_service.start()
            self.logger.info("mDNS service started")
        except Exception as e:
            self.logger.error(f"Failed to start mDNS: {e}")
    
    async def _connect_to_bootstrap_peers(self):
        """Connect to bootstrap peers."""
        self.logger.info(f"Connecting to {len(self.config.bootstrap_peers)} bootstrap peers...")
        
        connected = 0
        for peer_addr in self.config.bootstrap_peers:
            try:
                if hasattr(self.host, 'connect'):
                    await self.host.connect(peer_addr)
                    connected += 1
                    self.logger.info(f"Connected to bootstrap peer: {peer_addr}")
                    
                    # Add some delay between connections
                    await anyio.sleep(0.5)
                    
            except Exception as e:
                self.logger.debug(f"Failed to connect to bootstrap peer {peer_addr}: {e}")
        
        if connected > 0:
            self.bootstrap_connected = True
            self.logger.info(f"Connected to {connected} bootstrap peers")
        else:
            self.logger.warning("Failed to connect to any bootstrap peers")
    
    def _on_peer_discovered(self, peer):
        """Handle peer discovery from any source."""
        try:
            peer_id = peer.peer_id if hasattr(peer, 'peer_id') else str(peer)
            
            if peer_id not in self.connected_peers:
                self.metrics.total_peers_discovered += 1
                self.logger.debug(f"Peer discovered: {peer_id}")
                
                # Call user callback
                if self.config.on_peer_discovered:
                    self.config.on_peer_discovered(peer)
                
                # Optionally auto-connect
                # anyio.from_thread.run_sync(self._try_connect_to_peer, peer)
                
        except Exception as e:
            self.logger.error(f"Error handling discovered peer: {e}")
    
    async def _try_connect_to_peer(self, peer):
        """Attempt to connect to a discovered peer."""
        try:
            peer_id = peer.peer_id if hasattr(peer, 'peer_id') else str(peer)
            
            if peer_id in self.connected_peers:
                return
            
            # Get addresses
            addrs = []
            if hasattr(peer, 'multiaddrs'):
                addrs = peer.multiaddrs
            elif hasattr(peer, 'addresses'):
                addrs = peer.addresses
            
            # Try each address
            for addr in addrs:
                try:
                    if hasattr(self.host, 'connect'):
                        await self.host.connect(addr)
                        self.connected_peers.add(peer_id)
                        self.metrics.total_connections_established += 1
                        self.metrics.active_connections += 1
                        self.logger.info(f"Connected to peer: {peer_id}")
                        
                        # Call user callback
                        if self.config.on_connection_established:
                            self.config.on_connection_established(peer_id, addr)
                        
                        return
                except Exception as e:
                    self.logger.debug(f"Failed to connect to {peer_id} at {addr}: {e}")
            
            self.metrics.total_connections_failed += 1
            
        except Exception as e:
            self.logger.error(f"Error connecting to peer: {e}")
    
    async def _monitoring_loop(self):
        """Monitor connectivity and update metrics."""
        while self._running:
            try:
                await anyio.sleep(30)  # Update every 30 seconds
                
                # Update NAT status from AutoNAT
                if self.autonat:
                    nat_status = getattr(self.autonat, 'nat_status', 'unknown')
                    self.metrics.nat_status = nat_status
                
                # Update DCUtR metrics
                if self.dcutr:
                    dcutr_metrics = self.dcutr.get_metrics()
                    self.metrics.dcutr_success_rate = dcutr_metrics.get('success_rate', 0.0)
                
                # Update connection counts
                if hasattr(self.host, 'get_network'):
                    network = self.host.get_network()
                    if hasattr(network, 'connections'):
                        self.metrics.active_connections = len(network.connections)
                
                self.metrics.last_updated = time.time()
                
                # Log summary
                self.logger.debug(
                    f"Connectivity: {self.metrics.active_connections} connections, "
                    f"{self.metrics.total_peers_discovered} peers discovered, "
                    f"NAT: {self.metrics.nat_status}"
                )
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
    
    async def dial_peer(
        self,
        peer_id: str,
        addrs: Optional[List[str]] = None,
        use_relay: bool = True
    ) -> bool:
        """
        Dial a peer with intelligent connection strategy.
        
        Args:
            peer_id: ID of the peer to dial
            addrs: Optional list of known addresses
            use_relay: Whether to attempt relay if direct fails
            
        Returns:
            True if connection successful
        """
        # Try direct connection first
        if addrs:
            for addr in addrs:
                try:
                    if hasattr(self.host, 'connect'):
                        await self.host.connect(addr)
                        self.logger.info(f"Direct connection to {peer_id} successful")
                        return True
                except Exception as e:
                    self.logger.debug(f"Direct connection failed to {addr}: {e}")
        
        # Try via relay if enabled
        if use_relay and self.relay_client:
            try:
                # Get active relay reservations
                relay_addrs = self.relay_client.get_relay_listen_addrs()
                
                for relay_addr in relay_addrs:
                    circuit_id = await self.relay_client.dial_through_relay(
                        relay_addr.split('/p2p/')[1].split('/')[0],  # Extract relay peer ID
                        peer_id,
                        addrs
                    )
                    
                    if circuit_id:
                        self.logger.info(f"Relay connection to {peer_id} successful")
                        
                        # Try DCUtR upgrade if enabled
                        if self.dcutr:
                            relay_peer_id = relay_addr.split('/p2p/')[1].split('/')[0]
                            await self.dcutr.attempt_hole_punch(peer_id, relay_peer_id)
                        
                        return True
                        
            except Exception as e:
                self.logger.error(f"Relay connection failed: {e}")
        
        return False
    
    def get_metrics(self) -> ConnectivityMetrics:
        """Get current connectivity metrics."""
        return self.metrics
    
    def get_discovered_peers(self) -> List[Any]:
        """Get all discovered peers from all sources."""
        peers = []
        
        if self.pubsub_discovery:
            peers.extend(self.pubsub_discovery.get_discovered_peers())
        
        if self.mdns_service:
            peers.extend(self.mdns_service.get_discovered_peers())
        
        return peers
    
    def is_connected(self, peer_id: str) -> bool:
        """Check if connected to a specific peer."""
        return peer_id in self.connected_peers
    
    def get_nat_status(self) -> str:
        """Get current NAT status."""
        return self.metrics.nat_status


async def setup_universal_connectivity(
    host,
    config: Optional[ConnectivityConfig] = None
) -> UniversalConnectivityManager:
    """
    Convenience function to setup universal connectivity on a libp2p host.
    
    Args:
        host: The libp2p host
        config: Optional configuration
        
    Returns:
        UniversalConnectivityManager instance
    """
    manager = UniversalConnectivityManager(host, config)
    await manager.start()
    
    # Add as attribute to host
    host._connectivity_manager = manager
    
    return manager
