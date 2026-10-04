"""
MCP RPC Handler for list_peers

Uses the unified libp2p peer manager singleton for thread-safe peer listing.
Category: peer
Priority: 2 (Important)  
Complexity: 2 (Medium)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ListPeersHandler:
    """Handler for list_peers MCP RPC calls using unified peer manager singleton."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "peer"
        self.priority = 2
        self.complexity = 2
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list_peers RPC call.
        
        Uses the unified peer manager singleton for thread-safe access.
        """
        try:
            # Import the peer manager singleton
            from ipfs_kit_py.libp2p.peer_manager import get_peer_manager, start_peer_manager
            
            # Get or start the singleton peer manager (thread-safe)
            try:
                peer_manager = await start_peer_manager(config_dir=None, ipfs_kit=None)
            except Exception as e:
                logger.warning(f"Failed to start peer manager, using existing instance: {e}")
                peer_manager = get_peer_manager()
            
            if not peer_manager:
                return {
                    "success": False,
                    "error": "Peer manager not available",
                    "method": "list_peers",
                    "peers": []
                }
            
            # Get all peers from the singleton
            peers_dict = peer_manager.get_all_peers()
            peers = list(peers_dict.values())
            
            # Apply filters if provided
            limit = params.get("limit", 50)
            offset = params.get("offset", 0)
            filter_protocol = params.get("filter_protocol")
            filter_connected = params.get("filter_connected")
            
            # Filter by protocol
            if filter_protocol:
                peers = [
                    p for p in peers
                    if filter_protocol in p.get("protocols", [])
                ]
            
            # Filter by connection status
            if filter_connected is not None:
                peers = [
                    p for p in peers
                    if p.get("connected", False) == filter_connected
                ]
            
            # Sort by last seen (most recent first)
            peers.sort(key=lambda p: p.get("last_seen", 0), reverse=True)
            
            # Paginate
            total = len(peers)
            paginated_peers = peers[offset:offset + limit]
            
            return {
                "success": True,
                "method": "list_peers",
                "category": "peer",
                "peers": paginated_peers,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                },
                "source": "unified_peer_manager"
            }
            
        except Exception as e:
            logger.error(f"Error in list_peers handler: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "method": "list_peers",
                "category": "peer",
                "peers": []
            }
