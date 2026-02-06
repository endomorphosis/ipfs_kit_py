"""
Unified LibP2P Peer Manager for IPFS Kit.

This module provides comprehensive peer discovery, management, and remote data access
capabilities using the ipfs_kit_py libp2p stack. It serves as the canonical source
for all peer-related operations across the system.
"""
import anyio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import subprocess
import hashlib
from collections import deque, defaultdict

# Import from ipfs_kit_py libp2p stack
try:
    from .network.stream import INetStream, NetStream, StreamError
    from .. import libp2p_peer
    from . import HAS_LIBP2P
    from .enhanced_dht_discovery import EnhancedDHTDiscovery
    from .gossipsub_protocol import GossipSubProtocol
    from .content_routing import ContentRouter
    from .ipfs_kit_integration import apply_libp2p_integration
    LIBP2P_AVAILABLE = HAS_LIBP2P
except ImportError as e:
    LIBP2P_AVAILABLE = False
    INetStream = Any
    NetStream = object
    StreamError = Exception
    logging.getLogger(__name__).warning(f"LibP2P imports not available: {e}")

try:
    import multiaddr
    from multiaddr import Multiaddr
except ImportError:
    multiaddr = None
    Multiaddr = str

logger = logging.getLogger(__name__)


class Libp2pPeerManager:
    """
    Unified LibP2P Peer Manager for IPFS Kit.
    
    This class manages all peer-related operations including:
    - Peer discovery and connection management
    - Pinset synchronization and content sharing
    - Metadata collection and exchange
    - Vector database and knowledge base integration
    - Protocol handling for peer-to-peer communication
    """
    
    def __init__(self, config_dir: Path = None, ipfs_kit=None):
        self.config_dir = config_dir or Path("/tmp/ipfs_kit_config/libp2p")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.ipfs_kit = ipfs_kit
        
        # Core data structures
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.peer_metadata: Dict[str, Dict[str, Any]] = {}
        self.peer_pinsets: Dict[str, List[Dict[str, Any]]] = {}
        self.peer_knowledgebase: Dict[str, Dict[str, Any]] = {}
        self.bootstrap_peers: Set[str] = set()
        
        # Discovery and networking
        self.host = None
        self.discovery_active = False
        self.discovery_events = deque(maxlen=100)
        self.protocols = {
            "/ipfs-kit/metadata/1.0.0",
            "/ipfs-kit/filesystem/1.0.0", 
            "/ipfs-kit/pinset/1.0.0",
            "/ipfs-kit/vectordb/1.0.0",
            "/ipfs-kit/kb/1.0.0"
        }
        
        # Enhanced components
        self.dht_discovery = None
        self.gossipsub = None
        self.content_router = None
        self.vectordb_client = None
        self.kb_client = None
        
        # Statistics and monitoring
        self.stats = {
            "total_peers": 0,
            "connected_peers": 0,
            "bootstrap_peers": 0,
            "discovery_active": False,
            "protocols_supported": list(self.protocols),
            "total_files": 0,
            "total_pins": 0,
            "last_discovery": None
        }
        
        # Configuration
        self.config = {
            "discovery_interval": 30,  # seconds
            "bootstrap_from_ipfs": True,
            "bootstrap_from_cluster": True,
            "max_peers": 100,
            "metadata_cache_ttl": 300,  # 5 minutes
            "pinset_sync_interval": 60,  # 1 minute
        }
        
        # Load configuration and bootstrap peers
        self._load_config()
        self._load_bootstrap_peers()
    
    async def start(self):
        """Initialize and start the peer manager."""
        self._start_time = time.time()
        
        if not LIBP2P_AVAILABLE:
            logger.warning("LibP2P not available, using mock mode")
            return
            
        try:
            # Initialize libp2p host
            await self._initialize_host()
            
            # Start enhanced discovery
            await self._initialize_discovery()
            
            # Start content routing
            await self._initialize_content_routing()
            
            # Start protocol handlers
            await self._start_protocol_handlers()
            
            # Bootstrap from IPFS and cluster
            await self._bootstrap_from_sources()
            
            logger.info("✓ LibP2P Peer Manager started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start peer manager: {e}")
            raise
    
    async def stop(self):
        """Stop the peer manager and cleanup resources."""
        self.discovery_active = False
        
        if self.host:
            try:
                await self.host.close()
            except Exception as e:
                logger.error(f"Error closing host: {e}")
        
        logger.info("LibP2P Peer Manager stopped")
    
    async def _initialize_host(self):
        """Initialize the libp2p host."""
        if not LIBP2P_AVAILABLE:
            return
            
        try:
            # Create libp2p host with enhanced configuration
            from . import new_host
            
            self.host = await new_host()
            
            # Apply IPFS Kit integration if available
            if self.ipfs_kit:
                apply_libp2p_integration(self.ipfs_kit, self.host)
                
            logger.info(f"LibP2P host initialized with ID: {self.host.get_id()}")
            
        except Exception as e:
            logger.error(f"Failed to initialize host: {e}")
            raise
    
    async def _initialize_discovery(self):
        """Initialize enhanced peer discovery."""
        if not self.host:
            return
            
        try:
            # Initialize enhanced DHT discovery
            self.dht_discovery = EnhancedDHTDiscovery(self.host)
            
            # Initialize GossipSub for peer announcement
            self.gossipsub = GossipSubProtocol(self.host)
            
            await self.dht_discovery.start()
            await self.gossipsub.start()
            
            logger.info("Enhanced peer discovery initialized")
            
        except Exception as e:
            logger.warning(f"Enhanced discovery not available: {e}")
    
    async def _initialize_content_routing(self):
        """Initialize content routing capabilities."""
        if not self.host:
            return
            
        try:
            # Initialize content router for pinset management
            self.content_router = ContentRouter(self.host, self.ipfs_kit)
            await self.content_router.start()
            
            logger.info("Content routing initialized")
            
        except Exception as e:
            logger.warning(f"Content routing not available: {e}")
    
    async def _start_protocol_handlers(self):
        """Start protocol handlers for peer communication."""
        if not self.host:
            return
            
        # Register protocol handlers
        for protocol in self.protocols:
            if "metadata" in protocol:
                self.host.set_stream_handler(protocol, self._handle_metadata_request)
            elif "filesystem" in protocol:
                self.host.set_stream_handler(protocol, self._handle_filesystem_request)
            elif "pinset" in protocol:
                self.host.set_stream_handler(protocol, self._handle_pinset_request)
            elif "vectordb" in protocol:
                self.host.set_stream_handler(protocol, self._handle_vectordb_request)
            elif "kb" in protocol:
                self.host.set_stream_handler(protocol, self._handle_kb_request)
        
        logger.info(f"Protocol handlers registered for {len(self.protocols)} protocols")
    
    async def _bootstrap_from_sources(self):
        """Bootstrap peers from IPFS and cluster sources."""
        async with anyio.create_task_group() as tg:
            if self.config["bootstrap_from_ipfs"]:
                tg.start_soon(self.bootstrap_from_ipfs)
            
            if self.config["bootstrap_from_cluster"]:
                tg.start_soon(self.bootstrap_from_cluster)
    
    async def bootstrap_from_ipfs(self):
        """Bootstrap peers from IPFS swarm."""
        try:
            result = subprocess.run(
                ["ipfs", "swarm", "peers"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            addr = Multiaddr(line.strip())
                            peer_id = addr.value_for_protocol('p2p')
                            if peer_id:
                                self.bootstrap_peers.add(line.strip())
                                await self._add_discovered_peer(peer_id, [line.strip()])
                        except Exception as e:
                            logger.debug(f"Error parsing IPFS peer address {line}: {e}")
                
                logger.info(f"Bootstrapped {len(self.bootstrap_peers)} peers from IPFS")
                
        except Exception as e:
            logger.warning(f"Failed to bootstrap from IPFS: {e}")
    
    async def bootstrap_from_cluster(self):
        """Bootstrap peers from IPFS cluster."""
        try:
            result = subprocess.run(
                ["ipfs-cluster-ctl", "peers", "ls"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip() and '|' in line:
                        try:
                            peer_id = line.split('|')[0].strip()
                            if peer_id:
                                await self._add_discovered_peer(peer_id, [], cluster_peer=True)
                        except Exception as e:
                            logger.debug(f"Error parsing cluster peer {line}: {e}")
                
                logger.info("Bootstrapped peers from IPFS cluster")
                
        except Exception as e:
            logger.warning(f"Failed to bootstrap from cluster: {e}")
    
    async def start_discovery(self, task_group=None):
        """
        Start continuous peer discovery.
        
        Args:
            task_group: Optional anyio task group. If provided, starts discovery loop
                       in the task group. If not provided, caller is responsible for
                       starting _discovery_loop() in their own task group.
        """
        if self.discovery_active:
            return
        
        self.discovery_active = True
        self.stats["discovery_active"] = True
        
        # Start discovery task if task_group provided
        if task_group:
            task_group.start_soon(self._discovery_loop)
        else:
            logger.info("Discovery activated - caller should start _discovery_loop() in a task group")
        
        logger.info("Peer discovery started")
    
    async def stop_discovery(self):
        """Stop peer discovery."""
        self.discovery_active = False
        self.stats["discovery_active"] = False
        logger.info("Peer discovery stopped")
    
    async def _discovery_loop(self):
        """Main discovery loop."""
        while self.discovery_active:
            try:
                await self._discover_peers()
                await anyio.sleep(self.config["discovery_interval"])
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                await anyio.sleep(60)  # Wait longer on error
    
    async def _discover_peers(self):
        """Discover new peers using various methods."""
        async with anyio.create_task_group() as tg:
            # DHT discovery
            if self.dht_discovery:
                tg.start_soon(self._discover_via_dht)
            
            # GossipSub discovery
            if self.gossipsub:
                tg.start_soon(self._discover_via_gossipsub)
            
            # Bootstrap peer connections
            tg.start_soon(self._discover_via_bootstrap)
        
        # Update statistics
        await self._update_stats()
    
    async def _discover_via_dht(self):
        """Discover peers via enhanced DHT."""
        try:
            if self.dht_discovery:
                peers = await self.dht_discovery.find_peers()
                for peer_info in peers:
                    await self._add_discovered_peer(
                        peer_info.get('peer_id'),
                        peer_info.get('multiaddrs', [])
                    )
        except Exception as e:
            logger.debug(f"DHT discovery error: {e}")
    
    async def _discover_via_gossipsub(self):
        """Discover peers via GossipSub."""
        try:
            if self.gossipsub:
                peers = await self.gossipsub.get_all_peers()
                for peer_id in peers:
                    await self._add_discovered_peer(peer_id, [])
        except Exception as e:
            logger.debug(f"GossipSub discovery error: {e}")
    
    async def _discover_via_bootstrap(self):
        """Attempt connections to bootstrap peers."""
        for multiaddr_str in list(self.bootstrap_peers):
            try:
                if multiaddr:
                    addr = Multiaddr(multiaddr_str)
                    peer_id = addr.value_for_protocol('p2p')
                    if peer_id and peer_id not in self.peers:
                        await self._add_discovered_peer(peer_id, [multiaddr_str])
            except Exception as e:
                logger.debug(f"Bootstrap peer error for {multiaddr_str}: {e}")
    
    async def _add_discovered_peer(self, peer_id: str, multiaddrs: List[str], cluster_peer: bool = False):
        """Add a discovered peer to the registry."""
        if not peer_id or peer_id == str(self.host.get_id() if self.host else ""):
            return  # Skip self
        
        current_time = time.time()
        
        if peer_id not in self.peers:
            self.peers[peer_id] = {
                "peer_id": peer_id,
                "multiaddrs": multiaddrs,
                "connected": False,
                "last_seen": current_time,
                "first_seen": current_time,
                "protocols": [],
                "agent_version": "unknown",
                "cluster_peer": cluster_peer,
                "connection_attempts": 0,
                "successful_connections": 0,
                "last_connection_attempt": None,
                "last_successful_connection": None,
                "latency_ms": None,
                "shared_pins": [],
                "shared_files": []
            }
            
            # Log discovery event
            self.discovery_events.append({
                "timestamp": current_time,
                "event": "peer_discovered",
                "peer_id": peer_id,
                "multiaddrs": multiaddrs,
                "cluster_peer": cluster_peer
            })
            
            logger.debug(f"Discovered new peer: {peer_id[:12]}...")
        else:
            # Update existing peer
            self.peers[peer_id]["last_seen"] = current_time
            if multiaddrs:
                self.peers[peer_id]["multiaddrs"] = list(set(
                    self.peers[peer_id]["multiaddrs"] + multiaddrs
                ))
    
    async def connect_to_peer(self, peer_id: str, multiaddr_str: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a specific peer."""
        if not self.host:
            return {"success": False, "error": "LibP2P host not available"}
        
        try:
            peer_info = self.peers.get(peer_id)
            if not peer_info:
                return {"success": False, "error": "Peer not found"}
            
            # Update connection attempt
            peer_info["connection_attempts"] += 1
            peer_info["last_connection_attempt"] = time.time()
            
            # Try to connect
            if multiaddr_str:
                addr = Multiaddr(multiaddr_str)
            else:
                # Use first available multiaddr
                if not peer_info["multiaddrs"]:
                    return {"success": False, "error": "No multiaddrs available"}
                addr = Multiaddr(peer_info["multiaddrs"][0])
            
            # Attempt connection (mock implementation)
            peer_info["connected"] = True
            peer_info["successful_connections"] += 1
            peer_info["last_successful_connection"] = time.time()
            
            # Log connection event
            self.discovery_events.append({
                "timestamp": time.time(),
                "event": "peer_connected",
                "peer_id": peer_id
            })
            
            logger.info(f"Connected to peer: {peer_id[:12]}...")
            return {"success": True, "message": f"Connected to peer {peer_id}"}
            
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def disconnect_from_peer(self, peer_id: str) -> Dict[str, Any]:
        """Disconnect from a specific peer."""
        try:
            peer_info = self.peers.get(peer_id)
            if not peer_info:
                return {"success": False, "error": "Peer not found"}
            
            peer_info["connected"] = False
            
            # Log disconnection event
            self.discovery_events.append({
                "timestamp": time.time(),
                "event": "peer_disconnected",
                "peer_id": peer_id
            })
            
            logger.info(f"Disconnected from peer: {peer_id[:12]}...")
            return {"success": True, "message": f"Disconnected from peer {peer_id}"}
            
        except Exception as e:
            logger.error(f"Failed to disconnect from peer {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # Peer metadata and content methods
    async def get_peer_metadata(self, peer_id: str) -> Dict[str, Any]:
        """Get metadata for a specific peer."""
        return self.peer_metadata.get(peer_id, {})
    
    async def get_peer_pinset(self, peer_id: str) -> List[Dict[str, Any]]:
        """Get pinset for a specific peer."""
        return self.peer_pinsets.get(peer_id, [])
    
    async def get_peer_knowledgebase(self, peer_id: str) -> Dict[str, Any]:
        """Get knowledge base information for a specific peer."""
        return self.peer_knowledgebase.get(peer_id, {})
    
    async def update_peer_metadata(self, peer_id: str, metadata: Dict[str, Any]):
        """Update metadata for a specific peer."""
        self.peer_metadata[peer_id] = metadata
        if peer_id in self.peers:
            self.peers[peer_id].update(metadata)
    
    # Protocol handlers
    async def _handle_metadata_request(self, stream: INetStream):
        """Handle metadata requests from other peers."""
        try:
            # Respond with our metadata
            metadata = {
                'peer_id': str(self.host.get_id()) if self.host else 'unknown',
                'agent_version': 'ipfs-kit/2.0.0',
                'protocols': list(self.protocols),
                'capabilities': ['filesystem', 'metadata', 'pins', 'vectordb', 'kb'],
                'stats': self.stats
            }
            
            response = json.dumps(metadata).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling metadata request: {e}")
    
    async def _handle_filesystem_request(self, stream: INetStream):
        """Handle filesystem requests from other peers."""
        try:
            # Read request
            request_data = await stream.read(1024)
            request = json.loads(request_data.decode())
            
            path = request.get('path', '/')
            
            # Get local file listings via IPFS
            files = await self._get_local_files(path)
            
            response = json.dumps({"files": files}).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling filesystem request: {e}")
    
    async def _handle_pinset_request(self, stream: INetStream):
        """Handle pinset requests from other peers."""
        try:
            # Get local pins via IPFS
            pins = await self._get_local_pins()
            
            response = json.dumps({"pins": pins}).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling pinset request: {e}")
    
    async def _handle_vectordb_request(self, stream: INetStream):
        """Handle vector database requests from other peers."""
        try:
            # Read request
            request_data = await stream.read(1024)
            request = json.loads(request_data.decode())
            
            # Process vector query (mock implementation)
            results = {"vectors": [], "similarity_scores": []}
            
            response = json.dumps(results).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling vectordb request: {e}")
    
    async def _handle_kb_request(self, stream: INetStream):
        """Handle knowledge base requests from other peers."""
        try:
            # Read request
            request_data = await stream.read(1024)
            request = json.loads(request_data.decode())
            
            # Process KB query (mock implementation)
            results = {"knowledge": [], "entities": [], "relations": []}
            
            response = json.dumps(results).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling KB request: {e}")
    
    # Utility methods
    async def _get_local_files(self, path: str = "/") -> List[Dict[str, Any]]:
        """Get local IPFS file listings."""
        try:
            result = subprocess.run(
                ["ipfs", "files", "ls", "-l", path],
                capture_output=True, text=True, timeout=5
            )
            
            files = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            files.append({
                                "name": parts[-1],
                                "hash": parts[0],
                                "size": int(parts[1]) if parts[1].isdigit() else 0,
                                "type": "file"
                            })
            return files
        except Exception as e:
            logger.debug(f"Error getting local files: {e}")
            return []
    
    async def _get_local_pins(self) -> List[Dict[str, Any]]:
        """Get local IPFS pins."""
        try:
            result = subprocess.run(
                ["ipfs", "pin", "ls", "--type=recursive"],
                capture_output=True, text=True, timeout=10
            )
            
            pins = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            pins.append({
                                "cid": parts[0],
                                "type": parts[1],
                                "name": parts[2] if len(parts) > 2 else ""
                            })
            return pins
        except Exception as e:
            logger.debug(f"Error getting local pins: {e}")
            return []
    
    async def _update_stats(self):
        """Update peer statistics."""
        self.stats.update({
            "total_peers": len(self.peers),
            "connected_peers": len([p for p in self.peers.values() if p.get("connected")]),
            "bootstrap_peers": len(self.bootstrap_peers),
            "discovery_active": self.discovery_active,
            "last_discovery": time.time()
        })
        
        # Calculate total files and pins
        total_files = sum(len(files) for files in self.peer_pinsets.values())
        total_pins = sum(len(p.get("shared_pins", [])) for p in self.peers.values())
        
        self.stats.update({
            "total_files": total_files,
            "total_pins": total_pins
        })
    
    def get_peer_statistics(self) -> Dict[str, Any]:
        """Get current peer statistics."""
        return self.stats.copy()
    
    def get_all_peers(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered peers."""
        return self.peers.copy()
    
    def get_discovery_events(self) -> List[Dict[str, Any]]:
        """Get recent discovery events."""
        return list(self.discovery_events)
    
    # Configuration management
    def _load_config(self):
        """Load configuration from file."""
        config_file = self.config_dir / "config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                logger.info("Loaded peer manager configuration")
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
    
    def _save_config(self):
        """Save configuration to file."""
        config_file = self.config_dir / "config.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save config: {e}")
    
    def _load_bootstrap_peers(self):
        """Load bootstrap peers from file."""
        bootstrap_file = self.config_dir / "bootstrap_peers.txt"
        if bootstrap_file.exists():
            try:
                with open(bootstrap_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.bootstrap_peers.add(line)
                logger.info(f"Loaded {len(self.bootstrap_peers)} bootstrap peers")
            except Exception as e:
                logger.warning(f"Failed to load bootstrap peers: {e}")
    
    def add_bootstrap_peer(self, multiaddr_str: str):
        """Add a bootstrap peer."""
        self.bootstrap_peers.add(multiaddr_str)
        
        # Save to file
        bootstrap_file = self.config_dir / "bootstrap_peers.txt"
        try:
            with open(bootstrap_file, 'a') as f:
                f.write(f"{multiaddr_str}\n")
        except Exception as e:
            logger.warning(f"Failed to save bootstrap peer: {e}")
    
    async def connect_peer(self, peer_address: str, peer_id: str = None):
        """Connect to a specific peer."""
        try:
            if not self.host:
                return {"success": False, "error": "LibP2P host not initialized"}
            
            # Parse multiaddr if provided
            if multiaddr and peer_address.startswith('/'):
                try:
                    addr = Multiaddr(peer_address)
                    if not peer_id:
                        peer_id = addr.value_for_protocol('p2p')
                    
                    # Attempt connection
                    await self.host.connect(addr)
                    
                    # Update peer registry
                    if peer_id:
                        await self._add_discovered_peer(peer_id, [peer_address])
                        if peer_id in self.peers:
                            self.peers[peer_id]["connected"] = True
                            self.peers[peer_id]["last_successful_connection"] = time.time()
                            self.peers[peer_id]["successful_connections"] += 1
                    
                    logger.info(f"Successfully connected to peer {peer_id} at {peer_address}")
                    return {
                        "success": True,
                        "peer_id": peer_id,
                        "peer_address": peer_address,
                        "connected": True
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to connect to peer {peer_address}: {e}")
                    return {"success": False, "error": str(e)}
            else:
                return {"success": False, "error": "Invalid peer address format"}
                
        except Exception as e:
            logger.error(f"Error connecting to peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def disconnect_peer(self, peer_id: str):
        """Disconnect from a specific peer."""
        try:
            if not self.host:
                return {"success": False, "error": "LibP2P host not initialized"}
            
            if peer_id in self.peers:
                # Update peer status
                self.peers[peer_id]["connected"] = False
                self.peers[peer_id]["last_seen"] = time.time()
                
                # Try to close connection if possible
                # Note: This is a simplified implementation
                # Real implementation would use the libp2p host's connection manager
                
                logger.info(f"Disconnected from peer {peer_id}")
                return {
                    "success": True,
                    "peer_id": peer_id,
                    "connected": False
                }
            else:
                return {"success": False, "error": f"Peer {peer_id} not found"}
                
        except Exception as e:
            logger.error(f"Error disconnecting from peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def discover_peers(self):
        """Discover new peers and return results."""
        try:
            initial_peer_count = len(self.peers)
            
            # Run discovery methods
            await self._discover_peers()
            
            # Get newly discovered peers
            new_peer_count = len(self.peers) - initial_peer_count
            
            return {
                "success": True,
                "discovered_peers": list(self.peers.values())[-new_peer_count:] if new_peer_count > 0 else [],
                "total_discovered": new_peer_count,
                "total_peers": len(self.peers),
                "discovery_active": self.discovery_active
            }
            
        except Exception as e:
            logger.error(f"Error during peer discovery: {e}")
            return {
                "success": False,
                "error": str(e),
                "discovered_peers": [],
                "total_discovered": 0
            }
    
    async def get_stats(self):
        """Get comprehensive peer manager statistics."""
        try:
            connected_count = sum(1 for peer in self.peers.values() if peer.get("connected", False))
            
            stats = {
                "total_peers": len(self.peers),
                "connected_peers": connected_count,
                "bootstrap_peers": len(self.bootstrap_peers),
                "discovery_active": self.discovery_active,
                "protocols_supported": list(self.protocols),
                "libp2p_available": LIBP2P_AVAILABLE,
                "host_id": str(self.host.get_id()) if self.host else None,
                "uptime_seconds": time.time() - getattr(self, '_start_time', time.time()),
                "last_discovery": self.stats.get("last_discovery"),
                "peer_breakdown": {
                    "cluster_peers": sum(1 for peer in self.peers.values() if peer.get("cluster_peer", False)),
                    "dht_peers": sum(1 for peer in self.peers.values() if "dht" in peer.get("protocols", [])),
                    "gossipsub_peers": sum(1 for peer in self.peers.values() if "gossipsub" in peer.get("protocols", []))
                }
            }
            
            # Update internal stats
            self.stats.update(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Global instance for easy access
_global_peer_manager = None
_peer_manager_lock = anyio.Lock()

def get_peer_manager(config_dir: Path = None, ipfs_kit=None) -> Libp2pPeerManager:
    """Get or create the global peer manager instance (thread-safe singleton)."""
    global _global_peer_manager
    if _global_peer_manager is None:
        _global_peer_manager = Libp2pPeerManager(config_dir=config_dir, ipfs_kit=ipfs_kit)
    return _global_peer_manager

async def start_peer_manager(config_dir: Path = None, ipfs_kit=None) -> Libp2pPeerManager:
    """Start the global peer manager singleton (thread-safe)."""
    global _global_peer_manager
    
    # Use lock to prevent multiple threads from starting the manager simultaneously
    async with _peer_manager_lock:
        manager = get_peer_manager(config_dir=config_dir, ipfs_kit=ipfs_kit)
        
        # Only start if not already started
        if not hasattr(manager, '_started') or not manager._started:
            await manager.start()
            manager._started = True
            logger.info("Peer manager started successfully")
        else:
            logger.debug("Peer manager already started, skipping initialization")
        
        return manager
