import json
from pathlib import Path
import logging
import hashlib
import base64
import time

logger = logging.getLogger(__name__)

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
CONTENT_PATH = IPFS_KIT_PATH / 'content.json'

class ContentManager:
    def __init__(self):
        self.content_data = self._load_content()

    def _load_content(self):
        if not CONTENT_PATH.exists():
            return []
        try:
            with open(CONTENT_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading content data: {e}")
            return []

    def _save_content(self):
        CONTENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONTENT_PATH, 'w') as f:
                json.dump(self.content_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving content data: {e}")

    def list_content(self):
        return {"content_items": self.content_data, "total": len(self.content_data)}

    def get_content_details(self, cid):
        for item in self.content_data:
            if item.get("cid") == cid:
                return {"content_item": item}
        return {"error": "Content not found"}

    def generate_content_address(self, data):
        # Simple hash for demonstration
        content_str = json.dumps(data, sort_keys=True)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        cid = f"sha256-{content_hash}"
        
        new_item = {
            "cid": cid,
            "name": data.get("name", ""),
            "size": len(content_str),
            "content_type": data.get("content_type", "application/json"),
            "created": time.time(),
            "hash_algorithm": "sha256",
            "multihash": base64.b64encode(bytes.fromhex(content_hash)).decode(),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {})
        }
        self.content_data.append(new_item)
        self._save_content()
        return {"status": "Content address generated", "cid": cid, "item": new_item}

    def verify_content_integrity(self, cid, expected_hash):
        for item in self.content_data:
            if item.get("cid") == cid:
                # Re-calculate hash and compare
                # For this basic manager, we'll just compare the stored hash
                if item.get("multihash") == base64.b64encode(bytes.fromhex(expected_hash)).decode():
                    return {"status": "Integrity verified", "cid": cid, "valid": True}
                else:
                    return {"status": "Integrity check failed", "cid": cid, "valid": False}
        return {"error": "Content not found"}
