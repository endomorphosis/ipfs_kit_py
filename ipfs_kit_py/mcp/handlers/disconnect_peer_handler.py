"""
MCP RPC Handler for disconnect_peer

Uses the unified libp2p peer manager singleton for thread-safe peer disconnections.
Category: peer
Priority: 2 (Important)
Complexity: 2 (Medium)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DisconnectPeerHandler:
    """Handler for disconnect_peer MCP RPC calls using unified peer manager singleton."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "peer"
        self.priority = 2
        self.complexity = 2
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle disconnect_peer RPC call.
        
        Uses the unified peer manager singleton for thread-safe access.
        """
        try:
            # Validate required parameters
            peer_id = params.get("peer_id")
            if not peer_id:
                return {
                    "success": False,
                    "error": "peer_id parameter is required",
                    "method": "disconnect_peer"
                }
            
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
                    "method": "disconnect_peer"
                }
            
            # Disconnect from the peer using the singleton
            result = await peer_manager.disconnect_from_peer(peer_id)
            
            return {
                "success": result.get("success", False),
                "method": "disconnect_peer",
                "category": "peer",
                "peer_id": peer_id,
                "message": result.get("message", ""),
                "error": result.get("error"),
                "source": "unified_peer_manager"
            }
            
        except Exception as e:
            logger.error(f"Error in disconnect_peer handler: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "method": "disconnect_peer",
                "category": "peer"
            }
