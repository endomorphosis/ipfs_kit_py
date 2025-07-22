"""
Legacy LibP2P Peer Manager Backend - Thin Wrapper.

This module now serves as a thin wrapper around the unified
ipfs_kit_py.libp2p.peer_manager for backward compatibility.
All functionality has been moved to the main ipfs_kit_py library.
"""
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# Import the unified peer manager
from ipfs_kit_py.libp2p.peer_manager import Libp2pPeerManager, get_peer_manager

logger = logging.getLogger(__name__)


class LibP2PPeerManager:
    """
    Legacy peer manager - now a thin wrapper around the unified manager.
    
    This class provides backward compatibility for existing code while
    delegating all operations to the unified ipfs_kit_py.libp2p.peer_manager.
    """
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir
        self.unified_manager = get_peer_manager(config_dir=config_dir)
        
        logger.info("Legacy LibP2PPeerManager initialized as wrapper around unified manager")
    
    @property
    def host(self):
        """Get the libp2p host from unified manager."""
        return self.unified_manager.host
    
    @property
    def peers(self):
        """Get peers from unified manager."""
        return self.unified_manager.get_all_peers()
    
    @property
    def discovery_active(self):
        """Get discovery status from unified manager."""
        return self.unified_manager.discovery_active
    
    @property
    def bootstrap_peers(self):
        """Get bootstrap peers from unified manager."""
        return self.unified_manager.bootstrap_peers
    
    @property
    def protocols(self):
        """Get supported protocols from unified manager."""
        return self.unified_manager.protocols
    
    @property
    def discovery_events(self):
        """Get discovery events from unified manager."""
        return self.unified_manager.get_discovery_events()
    
    @property
    def peer_metadata(self):
        """Get peer metadata from unified manager."""
        return self.unified_manager.peer_metadata
    
    async def initialize(self):
        """Initialize the peer manager (delegates to unified manager)."""
        await self.unified_manager.start()
    
    async def start(self):
        """Start the peer manager (delegates to unified manager)."""
        await self.unified_manager.start()
    
    async def stop(self):
        """Stop the peer manager (delegates to unified manager)."""
        await self.unified_manager.stop()
    
    async def start_discovery(self):
        """Start peer discovery (delegates to unified manager)."""
        await self.unified_manager.start_discovery()
    
    async def stop_discovery(self):
        """Stop peer discovery (delegates to unified manager)."""
        await self.unified_manager.stop_discovery()
    
    async def connect_to_peer(self, peer_id: str, multiaddr: Optional[str] = None):
        """Connect to a peer (delegates to unified manager)."""
        return await self.unified_manager.connect_to_peer(peer_id, multiaddr)
    
    async def disconnect_from_peer(self, peer_id: str):
        """Disconnect from a peer (delegates to unified manager)."""
        return await self.unified_manager.disconnect_from_peer(peer_id)
    
    async def bootstrap_from_ipfs(self):
        """Bootstrap from IPFS (delegates to unified manager)."""
        await self.unified_manager.bootstrap_from_ipfs()
    
    async def bootstrap_from_cluster(self):
        """Bootstrap from cluster (delegates to unified manager)."""
        await self.unified_manager.bootstrap_from_cluster()
    
    async def discover_peers(self):
        """Discover peers (delegates to unified manager)."""
        await self.unified_manager._discover_peers()
    
    async def get_peer_files(self, peer_id: str):
        """Get peer files (delegates to unified manager)."""
        content = await self.unified_manager.get_peer_pinset(peer_id)
        return content
    
    async def retrieve_file_from_peer(self, peer_id: str, file_hash: str):
        """Retrieve file from peer (mock implementation)."""
        logger.info(f"Retrieving file {file_hash} from peer {peer_id}")
        return {"success": True, "data": b"mock file data"}
    
    async def query_peer_metadata(self, peer_id: str, query: Dict[str, Any]):
        """Query peer metadata (delegates to unified manager)."""
        return await self.unified_manager.get_peer_metadata(peer_id)
    
    async def query_peer_filesystem(self, peer_id: str, path: str):
        """Query peer filesystem (mock implementation)."""
        files = await self.unified_manager._get_local_files(path)
        return {"files": files}
    
    def get_peer_statistics(self):
        """Get peer statistics (delegates to unified manager)."""
        return self.unified_manager.get_peer_statistics()
    
    async def get_network_stats(self):
        """Get network statistics (delegates to unified manager)."""
        return self.unified_manager.get_peer_statistics()
    
    def add_bootstrap_peer(self, multiaddr: str):
        """Add bootstrap peer (delegates to unified manager)."""
        self.unified_manager.add_bootstrap_peer(multiaddr)
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import subprocess
import hashlib


try:
    import multiaddr
except ImportError:
    multiaddr = None

try:
    from libp2p import new_host
    from libp2p.network.stream.net_stream_interface import INetStream
    from libp2p.peer.peerinfo import info_from_p2p_addr
    from libp2p.tools.constants import GOSSIPSUB_PARAMS
except ImportError:
    INetStream = Any
    new_host = None
    info_from_p2p_addr = None
    GOSSIPSUB_PARAMS = None

logger = logging.getLogger(__name__)


class LibP2PPeerManager:
    """Manages libp2p peer discovery, connections, and remote data access."""
    
    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("/tmp/ipfs_kit_config/libp2p")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.host = None
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.peer_metadata: Dict[str, Dict[str, Any]] = {}
        self.bootstrap_peers: Set[str] = set()
        self.discovery_active = False
        self.protocols = {
            "/ipfs/kad/1.0.0",
            "/ipfs/id/1.0.0", 
            "/ipfs/ping/1.0.0",
            "/ipfs-kit/metadata/1.0.0",
            "/ipfs-kit/filesystem/1.0.0"
        }
        
        # Load saved peer data
        self._load_peer_cache()
        
    async def initialize(self):
        """Initialize the libp2p host and networking."""
        try:
            if not self.host:
                # Create libp2p host
                self.host = new_host()
                await self.host.get_network().listen(multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0"))
                
                # Register protocol handlers
                self.host.set_stream_handler("/ipfs-kit/metadata/1.0.0", self._handle_metadata_request)
                self.host.set_stream_handler("/ipfs-kit/filesystem/1.0.0", self._handle_filesystem_request)
                
                logger.info(f"Libp2p host initialized with peer ID: {self.host.get_id()}")
                
                # Start peer discovery
                await self._start_discovery()
                
        except Exception as e:
            logger.error(f"Error initializing libp2p host: {e}")
            
    async def shutdown(self):
        """Shutdown the libp2p host."""
        self.discovery_active = False
        if self.host:
            await self.host.close()
            self.host = None
            
    async def bootstrap_from_ipfs(self) -> List[str]:
        """Bootstrap peer list from IPFS daemon."""
        peers = []
        try:
            # Get IPFS swarm peers
            result = subprocess.run(
                ["ipfs", "swarm", "peers"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        peers.append(line.strip())
                        self.bootstrap_peers.add(line.strip())
                        
            logger.info(f"Bootstrapped {len(peers)} peers from IPFS")
            
        except Exception as e:
            logger.error(f"Error bootstrapping from IPFS: {e}")
            
        return peers
        
    async def bootstrap_from_cluster(self) -> List[str]:
        """Bootstrap peer list from IPFS Cluster."""
        peers = []
        try:
            # Get cluster peers
            result = subprocess.run(
                ["ipfs-cluster-ctl", "peers", "ls"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.strip() and '>' in line:
                        # Parse cluster peer format
                        peer_info = line.strip().split('>')[-1].strip()
                        if peer_info:
                            peers.append(peer_info)
                            self.bootstrap_peers.add(peer_info)
                            
            logger.info(f"Bootstrapped {len(peers)} peers from IPFS Cluster")
            
        except Exception as e:
            logger.error(f"Error bootstrapping from cluster: {e}")
            
        return peers
        
    async def discover_peers(self) -> List[Dict[str, Any]]:
        """Discover peers through various methods."""
        discovered_peers = []
        
        # Bootstrap from IPFS and cluster
        ipfs_peers = await self.bootstrap_from_ipfs()
        cluster_peers = await self.bootstrap_from_cluster()
        
        # Combine and deduplicate
        all_bootstrap_peers = list(set(ipfs_peers + cluster_peers))
        
        for peer_addr in all_bootstrap_peers:
            try:
                peer_info = await self._analyze_peer(peer_addr)
                if peer_info:
                    discovered_peers.append(peer_info)
                    self.peers[peer_info['peer_id']] = peer_info
                    
            except Exception as e:
                logger.error(f"Error analyzing peer {peer_addr}: {e}")
                
        # Save discovered peers
        self._save_peer_cache()
        
        return discovered_peers
        
    async def _analyze_peer(self, peer_addr: str) -> Optional[Dict[str, Any]]:
        """Analyze a peer and gather metadata."""
        try:
            # Parse multiaddr if possible
            if multiaddr:
                try:
                    maddr = multiaddr.Multiaddr(peer_addr)
                    peer_id = None
                    ip = None
                    port = None
                    
                    for protocol, value in maddr.items():
                        if protocol.name == 'p2p':
                            peer_id = value
                        elif protocol.name == 'ip4':
                            ip = value
                        elif protocol.name == 'tcp':
                            port = value
                            
                except Exception:
                    # Fallback parsing
                    if '/p2p/' in peer_addr:
                        peer_id = peer_addr.split('/p2p/')[-1]
                    else:
                        peer_id = hashlib.sha256(peer_addr.encode()).hexdigest()[:20]
                    ip = "unknown"
                    port = "unknown"
            else:
                # Simple parsing fallback
                if '/p2p/' in peer_addr:
                    peer_id = peer_addr.split('/p2p/')[-1]
                else:
                    peer_id = hashlib.sha256(peer_addr.encode()).hexdigest()[:20]
                ip = "unknown"
                port = "unknown"
                
            # Get peer metadata
            metadata = await self._get_peer_metadata(peer_addr, peer_id)
            
            peer_info = {
                'peer_id': peer_id,
                'multiaddr': peer_addr,
                'ip': ip,
                'port': port,
                'protocols': metadata.get('protocols', []),
                'agent_version': metadata.get('agent_version', 'unknown'),
                'public_key': metadata.get('public_key', ''),
                'last_seen': datetime.now().isoformat(),
                'connection_status': 'discovered',
                'pin_count': metadata.get('pin_count', 0),
                'repo_size': metadata.get('repo_size', 0),
                'files': metadata.get('files', []),
                'directories': metadata.get('directories', [])
            }
            
            return peer_info
            
        except Exception as e:
            logger.error(f"Error analyzing peer {peer_addr}: {e}")
            return None
            
    async def _get_peer_metadata(self, peer_addr: str, peer_id: str) -> Dict[str, Any]:
        """Get metadata from a peer."""
        metadata = {
            'protocols': [],
            'agent_version': 'unknown',
            'public_key': '',
            'pin_count': 0,
            'repo_size': 0,
            'files': [],
            'directories': []
        }
        
        try:
            # Try to get IPFS peer info
            result = subprocess.run(
                ["ipfs", "id", peer_id],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                peer_data = json.loads(result.stdout)
                metadata.update({
                    'protocols': peer_data.get('Protocols', []),
                    'agent_version': peer_data.get('AgentVersion', 'unknown'),
                    'public_key': peer_data.get('PublicKey', '')
                })
                
            # Try to get pin information
            try:
                pin_result = subprocess.run(
                    ["ipfs", "--api", f"/ip4/{peer_addr.split('/')[2]}/tcp/{peer_addr.split('/')[4]}", "pin", "ls", "--type=recursive"],
                    capture_output=True, text=True, timeout=10
                )
                
                if pin_result.returncode == 0:
                    pins = pin_result.stdout.strip().split('\n')
                    metadata['pin_count'] = len([p for p in pins if p.strip()])
                    
            except Exception:
                pass
                
            # Try to get file listings (limited)
            try:
                files_result = subprocess.run(
                    ["ipfs", "--api", f"/ip4/{peer_addr.split('/')[2]}/tcp/{peer_addr.split('/')[4]}", "files", "ls", "/"],
                    capture_output=True, text=True, timeout=5
                )
                
                if files_result.returncode == 0:
                    files_data = files_result.stdout.strip().split('\n')
                    metadata['files'] = [f.strip() for f in files_data if f.strip()][:20]  # Limit to 20
                    
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Error getting metadata for peer {peer_id}: {e}")
            
        return metadata
        
    async def connect_to_peer(self, peer_id: str) -> bool:
        """Connect to a specific peer."""
        try:
            if peer_id in self.peers:
                peer_info = self.peers[peer_id]
                multiaddr_str = peer_info['multiaddr']
                
                if self.host:
                    # Try to connect via libp2p
                    try:
                        peer_info_obj = info_from_p2p_addr(multiaddr.Multiaddr(multiaddr_str))
                        await self.host.connect(peer_info_obj)
                        
                        self.peers[peer_id]['connection_status'] = 'connected'
                        self.peers[peer_id]['last_connected'] = datetime.now().isoformat()
                        
                        logger.info(f"Successfully connected to peer {peer_id}")
                        return True
                        
                    except Exception as e:
                        logger.error(f"Libp2p connection failed for {peer_id}: {e}")
                        
                # Fallback: try IPFS swarm connect
                try:
                    result = subprocess.run(
                        ["ipfs", "swarm", "connect", multiaddr_str],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if result.returncode == 0:
                        self.peers[peer_id]['connection_status'] = 'connected'
                        self.peers[peer_id]['last_connected'] = datetime.now().isoformat()
                        return True
                        
                except Exception as e:
                    logger.error(f"IPFS swarm connect failed for {peer_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error connecting to peer {peer_id}: {e}")
            
        return False
        
    async def get_peer_files(self, peer_id: str, path: str = "/") -> List[Dict[str, Any]]:
        """Get file listings from a peer."""
        files = []
        
        try:
            if peer_id in self.peers:
                peer_info = self.peers[peer_id]
                
                # Try to list files via IPFS API
                api_addr = f"/ip4/{peer_info['ip']}/tcp/{peer_info['port']}"
                
                result = subprocess.run(
                    ["ipfs", "--api", api_addr, "files", "ls", "-l", path],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                files.append({
                                    'name': parts[-1],
                                    'hash': parts[0],
                                    'size': parts[1] if parts[1].isdigit() else 0,
                                    'type': 'directory' if parts[2] == '-' else 'file'
                                })
                                
        except Exception as e:
            logger.error(f"Error getting files from peer {peer_id}: {e}")
            
        return files
        
    async def retrieve_file_from_peer(self, peer_id: str, file_hash: str) -> Optional[bytes]:
        """Retrieve a file from a peer."""
        try:
            if peer_id in self.peers:
                peer_info = self.peers[peer_id]
                api_addr = f"/ip4/{peer_info['ip']}/tcp/{peer_info['port']}"
                
                result = subprocess.run(
                    ["ipfs", "--api", api_addr, "cat", file_hash],
                    capture_output=True, timeout=30
                )
                
                if result.returncode == 0:
                    return result.stdout
                    
        except Exception as e:
            logger.error(f"Error retrieving file {file_hash} from peer {peer_id}: {e}")
            
        return None
        
    def get_all_peers(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered peers."""
        return self.peers.copy()
        
    def get_peer_statistics(self) -> Dict[str, Any]:
        """Get peer discovery statistics."""
        total_peers = len(self.peers)
        connected_peers = len([p for p in self.peers.values() if p.get('connection_status') == 'connected'])
        total_files = sum(len(p.get('files', [])) for p in self.peers.values())
        total_pins = sum(p.get('pin_count', 0) for p in self.peers.values())
        
        return {
            'total_peers': total_peers,
            'connected_peers': connected_peers,
            'bootstrap_peers': len(self.bootstrap_peers),
            'total_files': total_files,
            'total_pins': total_pins,
            'protocols_supported': list(self.protocols),
            'discovery_active': self.discovery_active
        }
        
    def _load_peer_cache(self):
        """Load cached peer data."""
        try:
            cache_file = self.config_dir / "peer_cache.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    self.peers = cached_data.get('peers', {})
                    self.bootstrap_peers = set(cached_data.get('bootstrap_peers', []))
                    
                logger.info(f"Loaded {len(self.peers)} cached peers")
                
        except Exception as e:
            logger.error(f"Error loading peer cache: {e}")
            
    def _save_peer_cache(self):
        """Save peer data to cache."""
        try:
            cache_file = self.config_dir / "peer_cache.json"
            cache_data = {
                'peers': self.peers,
                'bootstrap_peers': list(self.bootstrap_peers),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving peer cache: {e}")
            
    async def _start_discovery(self):
        """Start peer discovery process."""
        self.discovery_active = True
        
        # Initial discovery
        await self.discover_peers()
        
        # Periodic discovery (every 5 minutes)
        asyncio.create_task(self._periodic_discovery())
        
    async def _periodic_discovery(self):
        """Periodic peer discovery task."""
        while self.discovery_active:
            try:
                await asyncio.sleep(300)  # 5 minutes
                if self.discovery_active:
                    await self.discover_peers()
                    
            except Exception as e:
                logger.error(f"Error in periodic discovery: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
                
    async def _handle_metadata_request(self, stream: INetStream):
        """Handle metadata requests from other peers."""
        try:
            # Respond with our metadata
            metadata = {
                'peer_id': str(self.host.get_id()),
                'agent_version': 'ipfs-kit/1.0.0',
                'protocols': list(self.protocols),
                'capabilities': ['filesystem', 'metadata', 'pins']
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
            
            # Get local file listings
            files = []
            try:
                result = subprocess.run(
                    ["ipfs", "files", "ls", "-l", path],
                    capture_output=True, text=True, timeout=5
                )
                
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                files.append({
                                    'name': parts[-1],
                                    'hash': parts[0],
                                    'size': int(parts[1]) if parts[1].isdigit() else 0,
                                    'type': 'directory' if parts[2] == '-' else 'file'
                                })
            except Exception:
                pass
                
            response = json.dumps({'files': files}).encode()
            await stream.write(response)
            await stream.close()
            
        except Exception as e:
            logger.error(f"Error handling filesystem request: {e}")
