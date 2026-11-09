import json
from pathlib import Path
import logging
import time

logger = logging.getLogger(__name__)

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
PEERS_PATH = IPFS_KIT_PATH / 'peers.json'

class PeerManager:
    def __init__(self):
        self.peers_data = self._load_peers()

    def _load_peers(self):
        if not PEERS_PATH.exists():
            return []
        try:
            with open(PEERS_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading peers data: {e}")
            return []

    def _save_peers(self):
        PEERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(PEERS_PATH, 'w') as f:
                json.dump(self.peers_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving peers data: {e}")

    def list_peers(self):
        return {"peers": self.peers_data, "total": len(self.peers_data)}

    def connect_peer(self, peer_info):
        # Placeholder for actual peer connection logic
        peer_info["connection_status"] = "connected"
        peer_info["last_seen"] = time.time()
        self.peers_data.append(peer_info)
        self._save_peers()
        return {"status": "Peer connected", "peer": peer_info}

    def disconnect_peer(self, peer_id):
        # Placeholder for actual peer disconnection logic
        initial_len = len(self.peers_data)
        self.peers_data = [p for p in self.peers_data if p.get("peer_id") != peer_id]
        if len(self.peers_data) < initial_len:
            self._save_peers()
            return {"status": "Peer disconnected", "peer_id": peer_id}
        return {"status": "Peer not found", "peer_id": peer_id}

    def get_peer_info(self, peer_id):
        for peer in self.peers_data:
            if peer.get("peer_id") == peer_id:
                return {"peer": peer}
        return {"error": "Peer not found"}
