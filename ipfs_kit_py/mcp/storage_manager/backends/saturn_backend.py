"""
Saturn CDN backend implementation for the Unified Storage Manager.

Saturn is a decentralized content delivery network that provides fast,
geo-distributed access to IPFS content.
"""

import logging
import time
import hashlib
from typing import Dict, Any, Optional, Union, BinaryIO, List
from urllib.parse import urljoin

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_ORCHESTRATOR_URL = "https://orchestrator.saturn.ms"
DEFAULT_TIMEOUT = 30
DEFAULT_CACHE_DURATION = 3600


class SaturnBackend(BackendStorage):
    """
    Backend for Saturn CDN - decentralized content delivery network.
    
    Saturn provides:
    - Geographic node selection for optimal performance
    - Caching layer for hot content
    - Automatic fallback to IPFS gateways
    - Performance monitoring
    """
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """
        Initialize Saturn backend.
        
        Args:
            resources: Connection resources including:
                - orchestrator_url: Saturn orchestrator URL (optional)
                - timeout: Request timeout in seconds (optional)
            metadata: Configuration metadata including:
                - enable_geographic_routing: Use closest nodes (default: True)
                - cache_duration: Cache duration in seconds
        """
        super().__init__(StorageBackendType.SATURN, resources, metadata)
        
        self.orchestrator_url = resources.get("orchestrator_url", DEFAULT_ORCHESTRATOR_URL)
        self.timeout = int(resources.get("timeout", DEFAULT_TIMEOUT))
        
        # Configuration
        self.enable_geographic_routing = metadata.get("enable_geographic_routing", True)
        self.cache_duration = int(metadata.get("cache_duration", DEFAULT_CACHE_DURATION))
        
        # Saturn node cache
        self._node_cache = {}
        self._content_cache = {}
        
        # Initialize HTTP client
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True
            )
            logger.info("Initialized Saturn backend with httpx client")
        else:
            self.session = requests.Session()
            logger.info("Initialized Saturn backend with requests client")
        
        # Get initial node list
        self._refresh_nodes()
        
        logger.info(f"Saturn backend initialized")
    
    def get_name(self) -> str:
        """Get the name of this backend implementation."""
        return "saturn"
    
    def add_content(
        self,
        content: Union[bytes, BinaryIO, str],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Saturn is read-only - content cannot be added directly.
        
        Returns:
            Error result indicating read-only nature
        """
        return {
            "success": False,
            "error": "Saturn backend is read-only (CDN for retrieval only)",
            "backend": self.get_name()
        }
    
    def get_content(self, identifier: str) -> Dict[str, Any]:
        """
        Retrieve content from Saturn CDN.
        
        Args:
            identifier: Content identifier (CID)
        
        Returns:
            Dictionary with content result
        """
        # Check cache first
        cached = self._get_from_cache(identifier)
        if cached:
            return {
                "success": True,
                "data": cached,
                "cid": identifier,
                "source": "cache",
                "backend": self.get_name(),
                "size": len(cached),
                "cached": True
            }
        
        try:
            # Get Saturn nodes
            nodes = self._get_nodes()
            
            if not nodes:
                return {
                    "success": False,
                    "error": "No Saturn nodes available",
                    "cid": identifier,
                    "backend": self.get_name()
                }
            
            # Try nodes in order
            for node in nodes:
                try:
                    start_time = time.time()
                    url = self._build_url(node, identifier)
                    
                    if HTTPX_AVAILABLE:
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        response = loop.run_until_complete(
                            self.client.get(url)
                        )
                        response.raise_for_status()
                        content = response.content
                    else:
                        response = self.session.get(url, timeout=self.timeout)
                        response.raise_for_status()
                        content = response.content
                    
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    # Cache the content
                    self._add_to_cache(identifier, content)
                    
                    return {
                        "success": True,
                        "data": content,
                        "cid": identifier,
                        "source": "saturn",
                        "node": node,
                        "backend": self.get_name(),
                        "size": len(content),
                        "duration_ms": duration_ms,
                        "cached": False
                    }
                    
                except Exception as node_error:
                    logger.debug(f"Saturn node {node} failed: {node_error}")
                    continue
            
            # All nodes failed
            return {
                "success": False,
                "error": "All Saturn nodes failed to retrieve content",
                "cid": identifier,
                "backend": self.get_name()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving from Saturn: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": identifier,
                "backend": self.get_name()
            }
    
    def remove_content(self, identifier: str) -> Dict[str, Any]:
        """
        Saturn is read-only - content cannot be removed.
        
        Returns:
            Error result indicating read-only nature
        """
        return {
            "success": False,
            "error": "Saturn backend is read-only (CDN for retrieval only)",
            "backend": self.get_name()
        }
    
    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        """
        Get metadata about content availability on Saturn.
        
        Args:
            identifier: Content identifier (CID)
        
        Returns:
            Dictionary with metadata
        """
        return {
            "success": True,
            "cid": identifier,
            "backend": self.get_name(),
            "available": len(self._get_nodes()) > 0,
            "nodes": len(self._get_nodes()),
            "cached": identifier in self._content_cache
        }
    
    def _refresh_nodes(self) -> None:
        """Refresh the list of Saturn nodes from orchestrator."""
        try:
            url = urljoin(self.orchestrator_url, "/nodes")
            
            if HTTPX_AVAILABLE:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                response = loop.run_until_complete(
                    self.client.get(url, timeout=10)
                )
                response.raise_for_status()
                nodes_data = response.json()
            else:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                nodes_data = response.json()
            
            # Extract node URLs
            nodes = []
            if isinstance(nodes_data, list):
                for node in nodes_data[:10]:  # Limit to top 10 nodes
                    if isinstance(node, dict) and "url" in node:
                        nodes.append(node["url"])
                    elif isinstance(node, str):
                        nodes.append(node)
            
            self._node_cache = {
                "nodes": nodes,
                "timestamp": time.time()
            }
            
            logger.info(f"Refreshed Saturn node list: {len(nodes)} nodes")
            
        except Exception as e:
            logger.warning(f"Failed to refresh Saturn nodes: {e}")
            # Use fallback nodes if orchestrator fails
            if not self._node_cache:
                self._node_cache = {
                    "nodes": [
                        "https://node1.saturn.ms",
                        "https://node2.saturn.ms"
                    ],
                    "timestamp": time.time()
                }
    
    def _get_nodes(self) -> List[str]:
        """Get list of Saturn nodes, refreshing if necessary."""
        # Refresh if cache is old or empty
        if not self._node_cache or \
           (time.time() - self._node_cache.get("timestamp", 0)) > 3600:
            self._refresh_nodes()
        
        return self._node_cache.get("nodes", [])
    
    def _build_url(self, node: str, cid: str) -> str:
        """Build URL for content retrieval from Saturn node."""
        # Saturn nodes typically use /ipfs/<cid> format
        if not node.endswith("/"):
            node += "/"
        return urljoin(node, f"ipfs/{cid}")
    
    def _get_from_cache(self, cid: str) -> Optional[bytes]:
        """Get content from cache if available and not expired."""
        if cid in self._content_cache:
            entry = self._content_cache[cid]
            if time.time() - entry["timestamp"] < self.cache_duration:
                return entry["content"]
            else:
                del self._content_cache[cid]
        return None
    
    def _add_to_cache(self, cid: str, content: bytes) -> None:
        """Add content to cache."""
        self._content_cache[cid] = {
            "content": content,
            "timestamp": time.time()
        }
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'client') and HTTPX_AVAILABLE:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.client.aclose())
            except Exception:
                pass
