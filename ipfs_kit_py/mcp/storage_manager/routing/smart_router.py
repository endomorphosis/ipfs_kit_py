"""Smart Content Router."""

import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class SmartRouter:
    """Intelligent content routing system."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._access_patterns = {}
        logger.info("SmartRouter initialized")
    
    def select_backend_for_storage(self, content_size: int, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Select optimal backend for storage."""
        metadata = metadata or {}
        
        if metadata.get("access_frequency") == "high":
            return "saturn"
        if content_size < 100 * 1024 * 1024:
            return "ipfs"
        return "filecoin_pin"
    
    def select_backend_for_retrieval(self, cid: str, available_backends: List[str]) -> str:
        """Select optimal backend for retrieval."""
        priority = ["saturn", "ipfs", "filecoin_pin"]
        
        for backend in priority:
            if backend in available_backends:
                return backend
        
        return available_backends[0] if available_backends else "ipfs"
    
    def track_access(self, cid: str) -> None:
        """Track content access."""
        if cid not in self._access_patterns:
            self._access_patterns[cid] = {"count": 0, "last_access": None}
        
        self._access_patterns[cid]["count"] += 1
        self._access_patterns[cid]["last_access"] = time.time()
    
    def get_access_pattern(self, cid: str) -> Dict[str, Any]:
        """Get access pattern."""
        return self._access_patterns.get(cid, {"count": 0, "last_access": None})
