"""
MCP RPC Handler for get_peers

Uses the unified libp2p peer manager singleton for thread-safe peer management.
Category: peer
Priority: 2 (Important)
Complexity: 2 (Medium)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class GetPeersHandler:
    """Handler for get_peers MCP RPC calls using unified peer manager singleton."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "peer"
        self.priority = 2
        self.complexity = 2
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_peers RPC call.
        
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
                    "method": "get_peers",
                    "peers": []
                }
            
            # Get all peers from the singleton
            peers_dict = peer_manager.get_all_peers()
            peers = list(peers_dict.values())
            
            # Filter based on params if provided
            status_filter = params.get("status")
            if status_filter:
                peers = [p for p in peers if p.get("connected") == (status_filter == "connected")]
            
            search_query = params.get("search")
            if search_query:
                query_lower = search_query.lower()
                peers = [
                    p for p in peers 
                    if query_lower in p.get("peer_id", "").lower() or
                       query_lower in str(p.get("multiaddrs", [])).lower()
                ]
            
            return {
                "success": True,
                "method": "get_peers",
                "category": "peer",
                "peers": peers,
                "total": len(peers),
                "source": "unified_peer_manager"
            }
            
        except Exception as e:
            logger.error(f"Error in get_peers handler: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "method": "get_peers",
                "category": "peer",
                "peers": []
            }
