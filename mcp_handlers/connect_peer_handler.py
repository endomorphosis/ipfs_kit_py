"""
MCP RPC Handler for connect_peer

Uses the unified libp2p peer manager singleton for thread-safe peer connections.
Category: peer
Priority: 2 (Important)
Complexity: 3 (Complex)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ConnectPeerHandler:
    """Handler for connect_peer MCP RPC calls using unified peer manager singleton."""
    
    def __init__(self, ipfs_kit_dir: Path):
        self.ipfs_kit_dir = ipfs_kit_dir
        self.category = "peer"
        self.priority = 2
        self.complexity = 3
    
    async def handle(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle connect_peer RPC call.
        
        Uses the unified peer manager singleton for thread-safe access.
        """
        try:
            # Validate required parameters
            peer_id = params.get("peer_id")
            if not peer_id:
                return {
                    "success": False,
                    "error": "peer_id parameter is required",
                    "method": "connect_peer"
                }
            
            multiaddr = params.get("multiaddr")
            
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
                    "method": "connect_peer"
                }
            
            # Connect to the peer using the singleton
            result = await peer_manager.connect_to_peer(peer_id, multiaddr)
            
            return {
                "success": result.get("success", False),
                "method": "connect_peer",
                "category": "peer",
                "peer_id": peer_id,
                "message": result.get("message", ""),
                "error": result.get("error"),
                "source": "unified_peer_manager"
            }
            
        except Exception as e:
            logger.error(f"Error in connect_peer handler: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "method": "connect_peer",
                "category": "peer"
            }
