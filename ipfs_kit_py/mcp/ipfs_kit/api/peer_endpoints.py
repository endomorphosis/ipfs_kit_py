"""
LibP2P Peer Management API Endpoints.

Provides REST API endpoints for peer discovery, management, and content access
using the unified ipfs_kit_py.libp2p.peer_manager.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
import anyio

# Import from the unified peer manager
from ipfs_kit_py.libp2p.peer_manager import get_peer_manager, start_peer_manager

logger = logging.getLogger(__name__)

# Create the FastAPI router
router = APIRouter(prefix="/api/v0/libp2p", tags=["libp2p", "peers"])


class PeerEndpoints:
    """API endpoints for peer management functionality using unified peer manager."""
    
    # Class-level lock to ensure thread-safe singleton access
    _init_lock = anyio.Lock()
    _initialized = False
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        # Don't store peer_manager locally - always use the singleton
        
        # Initialize peer manager safely using singleton pattern
        try:
            # Try to schedule initialization if we're in an async context
            anyio.get_current_task()
            anyio.lowlevel.spawn_system_task(self._initialize_peer_manager)
        except RuntimeError:
            # No running event loop - defer initialization until first API call
            logger.info("No running event loop, peer manager will be initialized on first API call")
    
    async def _initialize_peer_manager(self):
        """Initialize the unified peer manager singleton."""
        # Use class-level lock to prevent multiple threads from initializing
        async with PeerEndpoints._init_lock:
            if PeerEndpoints._initialized:
                logger.debug("Peer manager already initialized by another thread")
                return
            
            try:
                # Initialize the global singleton peer manager
                await start_peer_manager(
                    config_dir=None,  # Use default config directory
                    ipfs_kit=getattr(self.backend_monitor, 'ipfs_kit', None)
                )
                PeerEndpoints._initialized = True
                logger.info("✓ Unified LibP2P peer manager singleton initialized")
            except Exception as e:
                logger.error(f"Failed to initialize unified peer manager: {e}")
    
    async def _ensure_peer_manager(self):
        """Ensure peer manager singleton is initialized."""
        if not PeerEndpoints._initialized:
            await self._initialize_peer_manager()
        # Always return the global singleton
        return get_peer_manager()
    
    async def get_peers_summary(self) -> Dict[str, Any]:
        """Get summary of all discovered peers."""
        try:
            peer_manager = await self._ensure_peer_manager()
            if not peer_manager:
                return {"success": False, "error": "Peer manager not initialized"}
            
            # Get peer statistics from unified manager
            stats = peer_manager.get_peer_statistics()
            
            # Get protocol distribution
            peers = peer_manager.get_all_peers()
            protocols = {}
            for peer in peers.values():
                for protocol in peer.get('protocols', []):
                    protocols[protocol] = protocols.get(protocol, 0) + 1
            
            # Get recent discovery events
            recent_events = peer_manager.get_discovery_events()
            
            return {
                "success": True,
                "data": {
                    "total_peers": stats["total_peers"],
                    "connected_peers": stats["connected_peers"],
                    "discovery_active": stats["discovery_active"],
                    "protocols": protocols,
                    "recent_events": recent_events[-20:],  # Last 20 events
                    "stats": stats,
                    "bootstrap_peers": stats["bootstrap_peers"]
                }
            }
        except Exception as e:
            logger.error(f"Error getting peer summary: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_peers_list(
        self, 
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        filter_protocol: Optional[str] = Query(None),
        filter_connected: Optional[bool] = Query(None)
    ) -> Dict[str, Any]:
        """Get paginated list of discovered peers with optional filtering."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            peers = peer_manager.get_all_peers()
            peers_data = list(peers.values())
            
            # Apply filters
            if filter_protocol:
                peers_data = [
                    peer for peer in peers_data
                    if filter_protocol in peer.get('protocols', [])
                ]
            
            if filter_connected is not None:
                peers_data = [
                    peer for peer in peers_data
                    if peer.get('connected', False) == filter_connected
                ]
            
            # Sort by last seen (most recent first)
            peers_data.sort(key=lambda p: p.get('last_seen', 0), reverse=True)
            
            # Paginate
            total = len(peers_data)
            paginated_peers = peers_data[offset:offset + limit]
            
            return {
                "success": True,
                "data": {
                    "peers": paginated_peers,
                    "pagination": {
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                        "has_more": offset + limit < total
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error getting peers list: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_peer_details(self, peer_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            peers = peer_manager.get_all_peers()
            peer_data = peers.get(peer_id)
            
            if not peer_data:
                raise HTTPException(status_code=404, detail="Peer not found")
            
            # Get peer metadata, pinset, and knowledge base info
            metadata = await peer_manager.get_peer_metadata(peer_id)
            pinset = await peer_manager.get_peer_pinset(peer_id)
            kb_info = await peer_manager.get_peer_knowledgebase(peer_id)
            
            # Combine all information
            shared_content = {
                "pins": pinset,
                "files": peer_data.get("shared_files", []),
                "metadata": metadata,
                "knowledge_base": kb_info
            }
            
            return {
                "success": True,
                "data": {
                    "peer": peer_data,
                    "metadata": metadata,
                    "shared_content": shared_content,
                    "connection_history": peer_data.get('connection_history', [])
                }
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting peer details for {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_peer_content(self, peer_id: str) -> Dict[str, Any]:
        """Get content (pins/files) shared by a specific peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            # Get pinset and metadata from unified manager
            pinset = await peer_manager.get_peer_pinset(peer_id)
            metadata = await peer_manager.get_peer_metadata(peer_id)
            kb_info = await peer_manager.get_peer_knowledgebase(peer_id)
            
            peers = peer_manager.get_all_peers()
            peer_data = peers.get(peer_id, {})
            
            content = {
                "pins": pinset,
                "files": peer_data.get("shared_files", []),
                "metadata": metadata,
                "knowledge_base": kb_info
            }
            
            return {
                "success": True,
                "data": content
            }
        except Exception as e:
            logger.error(f"Error getting peer content for {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def connect_to_peer(self, peer_id: str, multiaddr: Optional[str] = None) -> Dict[str, Any]:
        """Connect to a specific peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            result = await peer_manager.connect_to_peer(peer_id, multiaddr)
            return result
            
        except Exception as e:
            logger.error(f"Error connecting to peer {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def disconnect_from_peer(self, peer_id: str) -> Dict[str, Any]:
        """Disconnect from a specific peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            result = await peer_manager.disconnect_from_peer(peer_id)
            return result
            
        except Exception as e:
            logger.error(f"Error disconnecting from peer {peer_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_peers(self, query: str) -> Dict[str, Any]:
        """Search peers by various criteria."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            peers = peer_manager.get_all_peers()
            matching_peers = []
            query_lower = query.lower()
            
            for peer_id, peer_data in peers.items():
                # Search in peer ID
                if query_lower in peer_id.lower():
                    matching_peers.append(peer_data)
                    continue
                
                # Search in protocols
                if any(query_lower in protocol.lower() for protocol in peer_data.get('protocols', [])):
                    matching_peers.append(peer_data)
                    continue
                
                # Search in agent version
                agent_version = peer_data.get('agent_version', '')
                if query_lower in agent_version.lower():
                    matching_peers.append(peer_data)
                    continue
            
            return {
                "success": True,
                "data": {
                    "peers": matching_peers,
                    "total": len(matching_peers),
                    "query": query
                }
            }
        except Exception as e:
            logger.error(f"Error searching peers: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_peer_discovery_status(self) -> Dict[str, Any]:
        """Get the status of peer discovery."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            stats = peer_manager.get_peer_statistics()
            events = peer_manager.get_discovery_events()
            
            return {
                "success": True,
                "data": {
                    "discovery_active": stats["discovery_active"],
                    "total_discovered": stats["total_peers"],
                    "discovery_events": events[-10:],  # Last 10 events
                    "bootstrap_peers": list(peer_manager.bootstrap_peers),
                    "supported_protocols": stats["protocols_supported"]
                }
            }
        except Exception as e:
            logger.error(f"Error getting discovery status: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_peer_discovery(self) -> Dict[str, Any]:
        """Start peer discovery."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            await peer_manager.start_discovery()
            return {
                "success": True,
                "message": "Peer discovery started"
            }
        except Exception as e:
            logger.error(f"Error starting peer discovery: {e}")
            return {"success": False, "error": str(e)}
    
    async def stop_peer_discovery(self) -> Dict[str, Any]:
        """Stop peer discovery."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            await peer_manager.stop_discovery()
            return {
                "success": True,
                "message": "Peer discovery stopped"
            }
        except Exception as e:
            logger.error(f"Error stopping peer discovery: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_bootstrap_peer(self, multiaddr: str) -> Dict[str, Any]:
        """Add a bootstrap peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            peer_manager.add_bootstrap_peer(multiaddr)
            return {
                "success": True,
                "message": f"Bootstrap peer added: {multiaddr}"
            }
        except Exception as e:
            logger.error(f"Error adding bootstrap peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_bootstrap_peer(self, multiaddr: str) -> Dict[str, Any]:
        """Remove a bootstrap peer."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            peer_manager.bootstrap_peers.discard(multiaddr)
            return {
                "success": True,
                "message": f"Bootstrap peer removed: {multiaddr}"
            }
        except Exception as e:
            logger.error(f"Error removing bootstrap peer: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_peer_network_stats(self) -> Dict[str, Any]:
        """Get network statistics for the peer network."""
        try:
            peer_manager = await self._ensure_peer_manager()

            if not peer_manager:

                return {"success": False, "error": "Peer manager not initialized"}
            
            stats = peer_manager.get_peer_statistics()
            return {
                "success": True,
                "data": stats
            }
        except Exception as e:
            logger.error(f"Error getting network stats: {e}")
            return {"success": False, "error": str(e)}


# Global peer endpoints instance
peer_endpoints = None


def get_peer_endpoints(backend_monitor=None):
    """Get or create the peer endpoints instance."""
    global peer_endpoints
    if peer_endpoints is None:
        peer_endpoints = PeerEndpoints(backend_monitor)
    return peer_endpoints


# FastAPI router endpoints
@router.get("/peers/summary")
async def get_peers_summary():
    """Get summary of all discovered peers."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peers_summary()


@router.get("/peers/list")
async def get_peers_list():
    """Get detailed list of all peers."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peers_list()


@router.post("/peers/connect/{peer_id}")
async def connect_to_peer(peer_id: str, multiaddr: Optional[str] = None):
    """Connect to a specific peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.connect_to_peer(peer_id, multiaddr)


@router.post("/peers/disconnect/{peer_id}")
async def disconnect_from_peer(peer_id: str):
    """Disconnect from a specific peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.disconnect_from_peer(peer_id)


@router.get("/peers/{peer_id}/metadata")
async def get_peer_metadata(peer_id: str):
    """Get metadata for a specific peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peer_metadata(peer_id)


@router.get("/peers/{peer_id}/pinset")
async def get_peer_pinset(peer_id: str):
    """Get pinset for a specific peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peer_pinset(peer_id)


@router.get("/peers/{peer_id}/files")
async def get_peer_files(peer_id: str):
    """Get files for a specific peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peer_files(peer_id)


@router.post("/discovery/start")
async def start_peer_discovery():
    """Start peer discovery."""
    endpoints = get_peer_endpoints()
    return await endpoints.start_peer_discovery()


@router.post("/discovery/stop")
async def stop_peer_discovery():
    """Stop peer discovery."""
    endpoints = get_peer_endpoints()
    return await endpoints.stop_peer_discovery()


@router.post("/bootstrap/add")
async def add_bootstrap_peer(multiaddr: str = Query(..., description="Multiaddr of the bootstrap peer")):
    """Add a bootstrap peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.add_bootstrap_peer(multiaddr)


@router.post("/bootstrap/remove")
async def remove_bootstrap_peer(multiaddr: str = Query(..., description="Multiaddr of the bootstrap peer")):
    """Remove a bootstrap peer."""
    endpoints = get_peer_endpoints()
    return await endpoints.remove_bootstrap_peer(multiaddr)


@router.get("/network/stats")
async def get_network_stats():
    """Get network statistics."""
    endpoints = get_peer_endpoints()
    return await endpoints.get_peer_network_stats()
