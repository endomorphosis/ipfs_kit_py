"""
MCP RPC Handler for get_peer_stats

Uses the unified libp2p peer manager singleton for thread-safe peer statistics.
Category: peer
Priority: 2 (Important)
Complexity: 2 (Medium)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class GetPeerStatsHandler:
    """Handler for get_peer_stats MCP RPC calls using unified peer manager singleton."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "peer"
        self.priority = 2
        self.complexity = 2
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get_peer_stats RPC call.
        
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
                    "method": "get_peer_stats",
                    "stats": {}
                }
            
            # Get statistics from the singleton
            stats = peer_manager.get_peer_statistics()
            
            return {
                "success": True,
                "method": "get_peer_stats",
                "category": "peer",
                "stats": stats,
                "source": "unified_peer_manager"
            }
            
        except Exception as e:
            logger.error(f"Error in get_peer_stats handler: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "method": "get_peer_stats",
                "category": "peer",
                "stats": {}
            }
