"""
LibP2P Peer Manager for IPFS Kit MCP Server
Integrates with the main ipfs_kit_py libp2p infrastructure for peer discovery and management
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Set, Union
from datetime import datetime, timedelta
import hashlib

# Import from the main ipfs_kit_py library
try:
    from ipfs_kit_py.libp2p_peer import IPFSLibp2pPeer, HAS_LIBP2P
    from ipfs_kit_py.metadata_sync_handler import MetadataSyncHandler
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    LibP2PPeerType = IPFSLibp2pPeer
    MetadataSyncType = MetadataSyncHandler
    IPFSAPIType = IPFSSimpleAPI
except ImportError as e:
    logging.warning(f"Failed to import ipfs_kit_py components: {e}")
    IPFSLibp2pPeer = None
    MetadataSyncHandler = None
    IPFSSimpleAPI = None
    HAS_LIBP2P = False
    LibP2PPeerType = Any
    MetadataSyncType = Any
    IPFSAPIType = Any

logger = logging.getLogger(__name__)


class LibP2PPeerManager:
    """Manages libp2p peer discovery and content synchronization using the main ipfs_kit_py infrastructure"""
    
    def __init__(self, ipfs_api: Optional[Any] = None):
        self.ipfs_api = ipfs_api
        self.libp2p_peer: Optional[Any] = None
        self.metadata_sync: Optional[Any] = None
        
        # Peer management data structures
        self.discovered_peers: Dict[str, Dict[str, Any]] = {}
        self.connected_peers: Set[str] = set()
        self.peer_content: Dict[str, List[Dict[str, Any]]] = {}
        self.peer_metadata: Dict[str, Dict[str, Any]] = {}
        self.peer_pinsets: Dict[str, List[str]] = {}
        
        # Discovery and synchronization state
        self.discovery_active = False
        self.sync_active = False
        
    async def initialize(self) -> bool:
        """Initialize the peer manager with libp2p integration"""
        try:
            if not HAS_LIBP2P or IPFSLibp2pPeer is None:
                logger.warning("libp2p dependencies not available, using mock mode")
                return await self._initialize_mock_mode()
            
            logger.info("Initializing LibP2P Peer Manager with ipfs_kit_py integration")
            
            # Initialize libp2p peer if not already available
            if not self.libp2p_peer:
                self.libp2p_peer = IPFSLibp2pPeer(
                    role="leecher",  # Default role for MCP server
                    enable_mdns=True,
                    enable_hole_punching=True,
                    enable_relay=True
                )
                
                # Start the libp2p peer
                if hasattr(self.libp2p_peer, 'start'):
                    await self.libp2p_peer.start()
            
            # Initialize metadata sync handler if we have an IPFS API
            if self.ipfs_api and hasattr(self.ipfs_api, 'client') and MetadataSyncHandler is not None:
                peer_id = None
                if self.libp2p_peer and hasattr(self.libp2p_peer, 'get_peer_id'):
                    try:
                        peer_id = self.libp2p_peer.get_peer_id()
                    except Exception:
                        peer_id = "unknown"
                
                self.metadata_sync = MetadataSyncHandler(
                    index=None,  # We'll manage metadata ourselves
                    ipfs_client=self.ipfs_api.client,
                    node_id=peer_id or "unknown"
                )
            
            # Bootstrap from existing IPFS connections
            await self._bootstrap_from_ipfs()
            
            # Start discovery
            await self._start_discovery()
            
            logger.info("LibP2P Peer Manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize peer manager: {e}")
            return await self._initialize_mock_mode()
    
    async def _initialize_mock_mode(self) -> bool:
        """Initialize in mock mode when libp2p is not available"""
        logger.info("Initializing LibP2P Peer Manager in mock mode")
        
        # Generate some mock peers for demonstration
        await self._generate_mock_peers()
        
        logger.info("Mock mode initialization completed")
        return True
    
    async def _generate_mock_peers(self):
        """Generate mock peers for testing when libp2p is not available"""
        mock_peers = [
            {
                'peer_id': f"MOCK{i:04d}" + hashlib.sha256(f"mock_peer_{i}".encode()).hexdigest()[:40],
                'addresses': [f"/ip4/192.168.1.{100+i}/tcp/4001/p2p/MOCK{i:04d}" + hashlib.sha256(f"mock_peer_{i}".encode()).hexdigest()[:40]],
                'status': 'discovered',
                'last_seen': datetime.utcnow().isoformat(),
                'discovered_from': 'mock',
                'connection_attempts': 0,
                'protocols': ['ipfs', 'kad-dht', 'bitswap'],
                'agent_version': 'go-ipfs/0.12.0',
                'latency': 50 + i * 20,
                'metadata': {
                    'mock_peer': True,
                    'content_count': i * 5,
                    'pin_count': i * 2,
                    'repo_size': 1024 * 1024 * (i + 1)
                }
            }
            for i in range(10)
        ]
        
        for peer in mock_peers:
            self.discovered_peers[peer['peer_id']] = peer
            
            # Generate mock content for each peer
            content = []
            for j in range(peer['metadata']['content_count']):
                content_hash = hashlib.sha256(f"{peer['peer_id']}_content_{j}".encode()).hexdigest()
                content.append({
                    'hash': content_hash,
                    'type': ['file', 'directory', 'metadata'][j % 3],
                    'size': 1024 + (hash(content_hash) % 1024000),
                    'name': f"content_{j}_{peer['peer_id'][:8]}",
                    'created_at': (datetime.utcnow() - timedelta(days=hash(content_hash) % 30)).isoformat(),
                    'metadata': {
                        'mime_type': ['text/plain', 'image/jpeg', 'application/json'][j % 3],
                        'pins': hash(content_hash) % 5,
                        'provider_confidence': 0.8 + (hash(content_hash) % 20) / 100
                    }
                })
            
            self.peer_content[peer['peer_id']] = content
            
            # Generate mock pinsets
            pinsets = [content[k]['hash'] for k in range(min(peer['metadata']['pin_count'], len(content)))]
            self.peer_pinsets[peer['peer_id']] = pinsets
    
    async def _bootstrap_from_ipfs(self):
        """Bootstrap peer discovery from existing IPFS connections"""
        try:
            if self.ipfs_api:
                # Get IPFS swarm peers
                swarm_peers = await self.ipfs_api.get_swarm_peers()
                
                for peer_addr in swarm_peers:
                    await self._analyze_and_add_peer(peer_addr, 'ipfs_swarm')
                
                logger.info(f"Bootstrapped {len(swarm_peers)} peers from IPFS swarm")
                
        except Exception as e:
            logger.warning(f"Failed to bootstrap from IPFS: {e}")
    
    async def _start_discovery(self):
        """Start peer discovery mechanisms"""
        self.discovery_active = True
        
        if self.libp2p_peer:
            # Start libp2p discovery
            await self.libp2p_peer.start_discovery()
            
            # Set up discovery event handlers
            # Note: This would need to be implemented in the libp2p_peer class
            # For now, we'll simulate periodic discovery
            asyncio.create_task(self._periodic_discovery())
        else:
            # Mock discovery
            asyncio.create_task(self._mock_discovery())
    
    async def _periodic_discovery(self):
        """Periodic peer discovery task"""
        while self.discovery_active:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if self.discovery_active:
                    await self.discover_peers()
                    
            except Exception as e:
                logger.error(f"Error in periodic discovery: {e}")
                await asyncio.sleep(60)
    
    async def _mock_discovery(self):
        """Mock discovery for testing"""
        while self.discovery_active:
            try:
                await asyncio.sleep(30)  # 30 seconds for mock
                if self.discovery_active:
                    # Randomly add a new mock peer
                    new_peer_id = f"DISC{len(self.discovered_peers):04d}" + hashlib.sha256(f"discovered_peer_{len(self.discovered_peers)}".encode()).hexdigest()[:40]
                    new_peer = {
                        'peer_id': new_peer_id,
                        'addresses': [f"/ip4/10.0.0.{len(self.discovered_peers) % 255}/tcp/4001/p2p/{new_peer_id}"],
                        'status': 'discovered',
                        'last_seen': datetime.utcnow().isoformat(),
                        'discovered_from': 'dht',
                        'connection_attempts': 0,
                        'protocols': ['ipfs', 'kad-dht'],
                        'agent_version': 'js-ipfs/0.60.0',
                        'latency': None,
                        'metadata': {
                            'content_count': 3,
                            'recently_discovered': True
                        }
                    }
                    self.discovered_peers[new_peer_id] = new_peer
                    
            except Exception as e:
                logger.error(f"Error in mock discovery: {e}")
                await asyncio.sleep(60)
    
    async def _analyze_and_add_peer(self, peer_addr: str, discovery_source: str):
        """Analyze a peer address and add it to our discovered peers"""
        try:
            # Extract peer ID from multiaddress
            if '/p2p/' in peer_addr:
                peer_id = peer_addr.split('/p2p/')[-1]
            else:
                peer_id = hashlib.sha256(peer_addr.encode()).hexdigest()[:50]
            
            # Skip if we already know this peer
            if peer_id in self.discovered_peers:
                return
            
            peer_info = {
                'peer_id': peer_id,
                'addresses': [peer_addr],
                'status': 'discovered',
                'last_seen': datetime.utcnow().isoformat(),
                'discovered_from': discovery_source,
                'connection_attempts': 0,
                'protocols': [],
                'agent_version': 'unknown',
                'latency': None,
                'metadata': {}
            }
            
            # Try to get additional metadata if we have libp2p peer
            if self.libp2p_peer:
                try:
                    # This would call into the libp2p_peer to get peer info
                    # For now, we'll use basic info
                    peer_info['protocols'] = ['ipfs', 'kad-dht']
                except Exception as e:
                    logger.debug(f"Failed to get extended peer info for {peer_id}: {e}")
            
            self.discovered_peers[peer_id] = peer_info
            
        except Exception as e:
            logger.error(f"Error analyzing peer {peer_addr}: {e}")
    
    async def discover_peers(self) -> List[Dict[str, Any]]:
        """Discover peers on the network"""
        try:
            logger.info("Starting peer discovery")
            
            if self.libp2p_peer:
                # Use libp2p peer discovery
                # Note: This would need specific methods in IPFSLibp2pPeer
                # For now, we'll bootstrap from IPFS
                await self._bootstrap_from_ipfs()
            else:
                # Use mock discovery
                await self._generate_mock_peers()
            
            peers = list(self.discovered_peers.values())
            logger.info(f"Discovered {len(peers)} peers")
            return peers
            
        except Exception as e:
            logger.error(f"Error during peer discovery: {e}")
            return []
    
    async def connect_to_peer(self, peer_id: str) -> bool:
        """Connect to a specific peer"""
        try:
            if peer_id not in self.discovered_peers:
                logger.warning(f"Peer {peer_id} not found in discovered peers")
                return False
            
            peer = self.discovered_peers[peer_id]
            
            if self.libp2p_peer:
                # Use libp2p peer connection
                success = False
                for addr in peer['addresses']:
                    if self.libp2p_peer.connect_peer(addr):
                        success = True
                        break
                
                if success:
                    peer['status'] = 'connected'
                    peer['connected_at'] = datetime.utcnow().isoformat()
                    self.connected_peers.add(peer_id)
                    logger.info(f"Successfully connected to peer {peer_id}")
                    return True
                else:
                    peer['connection_attempts'] += 1
                    logger.warning(f"Failed to connect to peer {peer_id}")
                    return False
            else:
                # Mock connection
                peer['status'] = 'connected'
                peer['connected_at'] = datetime.utcnow().isoformat()
                peer['connection_attempts'] += 1
                self.connected_peers.add(peer_id)
                logger.info(f"Mock connected to peer {peer_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_id}: {e}")
            return False
    
    async def disconnect_from_peer(self, peer_id: str) -> bool:
        """Disconnect from a specific peer"""
        try:
            if peer_id in self.connected_peers:
                self.connected_peers.remove(peer_id)
                
            if peer_id in self.discovered_peers:
                peer = self.discovered_peers[peer_id]
                peer['status'] = 'disconnected'
                peer['disconnected_at'] = datetime.utcnow().isoformat()
                
            logger.info(f"Disconnected from peer {peer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect from peer {peer_id}: {e}")
            return False
    
    async def get_peer_content(self, peer_id: str) -> List[Dict[str, Any]]:
        """Get content available from a specific peer"""
        try:
            if peer_id not in self.connected_peers:
                logger.warning(f"Not connected to peer {peer_id}")
                return []
            
            if peer_id in self.peer_content:
                return self.peer_content[peer_id]
            
            # Query peer for content
            logger.info(f"Querying content from peer {peer_id}")
            
            if self.libp2p_peer:
                # Use libp2p to query peer content
                # This would require implementing content query protocols
                # For now, return empty list
                content = []
            else:
                # Use mock content
                content = self.peer_content.get(peer_id, [])
            
            self.peer_content[peer_id] = content
            logger.info(f"Retrieved {len(content)} content items from peer {peer_id}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to get content from peer {peer_id}: {e}")
            return []
    
    async def get_peer_pinsets(self, peer_id: str) -> List[str]:
        """Get pinsets from a specific peer"""
        try:
            if peer_id not in self.connected_peers:
                logger.warning(f"Not connected to peer {peer_id}")
                return []
            
            if peer_id in self.peer_pinsets:
                return self.peer_pinsets[peer_id]
            
            # Query peer for pinsets
            if self.libp2p_peer:
                # Use libp2p to query peer pinsets
                # This would require implementing pinset query protocols
                pinsets = []
            else:
                # Use mock pinsets
                pinsets = self.peer_pinsets.get(peer_id, [])
            
            self.peer_pinsets[peer_id] = pinsets
            return pinsets
            
        except Exception as e:
            logger.error(f"Failed to get pinsets from peer {peer_id}: {e}")
            return []
    
    async def sync_metadata_with_peer(self, peer_id: str) -> Dict[str, Any]:
        """Synchronize metadata with a specific peer"""
        try:
            if peer_id not in self.connected_peers:
                logger.warning(f"Not connected to peer {peer_id}")
                return {}
            
            if self.metadata_sync:
                # Use metadata sync handler
                # This would require implementing metadata sync protocols
                metadata = {}
            else:
                # Mock metadata
                metadata = {
                    'filesystem_entries': 100,
                    'last_sync': datetime.utcnow().isoformat(),
                    'sync_status': 'completed'
                }
            
            self.peer_metadata[peer_id] = metadata
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to sync metadata with peer {peer_id}: {e}")
            return {}
    
    async def query_all_peer_content(self) -> Dict[str, List[Dict[str, Any]]]:
        """Query content from all connected peers"""
        try:
            all_content = {}
            
            for peer_id in self.connected_peers:
                content = await self.get_peer_content(peer_id)
                if content:
                    all_content[peer_id] = content
            
            logger.info(f"Queried content from {len(all_content)} peers")
            return all_content
            
        except Exception as e:
            logger.error(f"Failed to query all peer content: {e}")
            return {}
    
    async def get_peer_statistics(self) -> Dict[str, Any]:
        """Get comprehensive peer statistics"""
        try:
            total_peers = len(self.discovered_peers)
            connected_count = len(self.connected_peers)
            total_content = sum(len(content) for content in self.peer_content.values())
            total_pinsets = sum(len(pinsets) for pinsets in self.peer_pinsets.values())
            
            # Calculate status distribution
            status_counts = {}
            for peer in self.discovered_peers.values():
                status = peer.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Calculate discovery source distribution
            source_counts = {}
            for peer in self.discovered_peers.values():
                source = peer.get('discovered_from', 'unknown')
                source_counts[source] = source_counts.get(source, 0) + 1
            
            return {
                'total_peers': total_peers,
                'connected_peers': connected_count,
                'disconnected_peers': status_counts.get('disconnected', 0),
                'discovered_peers': status_counts.get('discovered', 0),
                'peers_with_content': len(self.peer_content),
                'peers_with_pinsets': len(self.peer_pinsets),
                'total_content_items': total_content,
                'total_pinsets': total_pinsets,
                'discovery_active': self.discovery_active,
                'sync_active': self.sync_active,
                'status_distribution': status_counts,
                'source_distribution': source_counts,
                'libp2p_available': HAS_LIBP2P,
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get peer statistics: {e}")
            return {}
    
    async def get_all_peers(self, page: int = 1, page_size: int = 20, 
                           status_filter: Optional[str] = None,
                           search_query: Optional[str] = None) -> Dict[str, Any]:
        """Get paginated list of all peers with filtering"""
        try:
            peers = list(self.discovered_peers.values())
            
            # Apply status filter
            if status_filter:
                peers = [p for p in peers if p.get('status') == status_filter]
            
            # Apply search filter
            if search_query:
                query_lower = search_query.lower()
                peers = [
                    p for p in peers 
                    if query_lower in p.get('peer_id', '').lower() or
                       query_lower in str(p.get('addresses', [])).lower() or
                       query_lower in str(p.get('metadata', {})).lower()
                ]
            
            # Calculate pagination
            total_peers = len(peers)
            total_pages = max(1, (total_peers + page_size - 1) // page_size)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_peers = peers[start_idx:end_idx]
            
            return {
                'peers': page_peers,
                'pagination': {
                    'current_page': page,
                    'total_pages': total_pages,
                    'page_size': page_size,
                    'total_peers': total_peers,
                    'has_previous': page > 1,
                    'has_next': page < total_pages
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get peers: {e}")
            return {'peers': [], 'pagination': {}}
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Cleaning up LibP2P Peer Manager")
            
            self.discovery_active = False
            self.sync_active = False
            
            # Cleanup libp2p peer
            if self.libp2p_peer:
                await self.libp2p_peer.stop()
            
            # Cleanup metadata sync
            if self.metadata_sync:
                # Stop metadata sync if it has a stop method
                if hasattr(self.metadata_sync, 'stop'):
                    self.metadata_sync.stop()
            
            # Clear data structures
            self.discovered_peers.clear()
            self.connected_peers.clear()
            self.peer_content.clear()
            self.peer_metadata.clear()
            self.peer_pinsets.clear()
            
            logger.info("LibP2P Peer Manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
