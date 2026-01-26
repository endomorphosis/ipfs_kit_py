"""
IPNI (InterPlanetary Network Indexer) Client.

This module provides integration with IPNI for discovering providers
that have specific content (CIDs) available.
"""

import logging
import time
import threading
import anyio
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

# Configure logger
logger = logging.getLogger(__name__)

# Default IPNI endpoints
DEFAULT_IPNI_ENDPOINTS = [
    "https://cid.contact",
    "https://index.pinning.services"
]


class IPNIClient:
    """
    Client for InterPlanetary Network Indexer (IPNI).
    
    IPNI provides a distributed indexing system for finding which providers
    have specific content available on the IPFS/Filecoin network.
    
    Features:
    - Find providers for CIDs
    - Query multiple IPNI endpoints
    - Cache provider information
    - Filter providers by capabilities (IPFS, Filecoin, HTTP)
    """
    
    def __init__(
        self,
        endpoints: Optional[List[str]] = None,
        timeout: int = 10,
        cache_duration: int = 3600
    ):
        """
        Initialize IPNI client.
        
        Args:
            endpoints: List of IPNI endpoint URLs
            timeout: Request timeout in seconds
            cache_duration: Cache duration in seconds
        """
        self.endpoints = endpoints or DEFAULT_IPNI_ENDPOINTS.copy()
        self.timeout = timeout
        self.cache_duration = cache_duration
        
        # Provider cache
        self._cache = {}
        
        # Initialize HTTP client
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
            logger.info("Initialized IPNI client with httpx")
        else:
            self.session = requests.Session()
            logger.info("Initialized IPNI client with requests")
        
        logger.info(f"IPNI client initialized with {len(self.endpoints)} endpoints")
    
    async def find_providers(
        self,
        cid: str,
        protocol: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find providers that have content for the given CID.
        
        Args:
            cid: Content identifier
            protocol: Filter by protocol (bitswap, graphsync-filecoinv1, http)
            limit: Maximum number of providers to return
        
        Returns:
            List of provider information dictionaries
        """
        # Check cache first
        cache_key = f"{cid}:{protocol}"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.debug(f"Using cached providers for {cid}")
            return cached[:limit]
        
        # Query IPNI endpoints
        for endpoint in self.endpoints:
            try:
                providers = await self._query_endpoint(endpoint, cid)
                
                # Filter by protocol if specified
                if protocol:
                    providers = [
                        p for p in providers 
                        if protocol in p.get("protocols", [])
                    ]
                
                # Cache the results
                self._add_to_cache(cache_key, providers)
                
                logger.info(f"Found {len(providers)} providers for {cid} from {endpoint}")
                return providers[:limit]
                
            except Exception as e:
                logger.warning(f"IPNI endpoint {endpoint} failed: {e}")
                continue
        
        # All endpoints failed
        logger.error(f"All IPNI endpoints failed for CID {cid}")
        return []
    
    async def get_provider_info(self, provider_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific provider.
        
        Args:
            provider_id: Provider peer ID
        
        Returns:
            Provider information dictionary
        """
        # Check cache
        cached = self._get_from_cache(f"provider:{provider_id}")
        if cached:
            return cached
        
        for endpoint in self.endpoints:
            try:
                url = urljoin(endpoint, f"/providers/{provider_id}")
                
                if HTTPX_AVAILABLE:
                    response = await self.client.get(url)
                    response.raise_for_status()
                    provider_info = response.json()
                else:
                    response = self.session.get(url, timeout=self.timeout)
                    response.raise_for_status()
                    provider_info = response.json()
                
                # Cache the result
                self._add_to_cache(f"provider:{provider_id}", provider_info)
                
                return provider_info
                
            except Exception as e:
                logger.warning(f"Failed to get provider info from {endpoint}: {e}")
                continue
        
        return {}
    
    async def _query_endpoint(
        self,
        endpoint: str,
        cid: str
    ) -> List[Dict[str, Any]]:
        """Query a specific IPNI endpoint for providers."""
        url = urljoin(endpoint, f"/cid/{cid}")
        
        if HTTPX_AVAILABLE:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
        else:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        
        # Parse response format
        providers = []
        
        # Handle different response formats
        if "MultihashResults" in data:
            # Standard IPNI format
            for result in data.get("MultihashResults", []):
                for provider_result in result.get("ProviderResults", []):
                    provider = {
                        "provider_id": provider_result.get("Provider", {}).get("ID", ""),
                        "addresses": provider_result.get("Provider", {}).get("Addrs", []),
                        "protocols": self._extract_protocols(provider_result),
                        "metadata": provider_result.get("Metadata", {})
                    }
                    providers.append(provider)
        
        elif "providers" in data:
            # Simplified format
            providers = data["providers"]
        
        return providers
    
    def _extract_protocols(self, provider_result: Dict[str, Any]) -> List[str]:
        """Extract protocol names from provider result."""
        protocols = []
        
        # Check ContextID for protocol hints
        context_id = provider_result.get("ContextID", "")
        
        if "bitswap" in context_id.lower():
            protocols.append("bitswap")
        if "graphsync" in context_id.lower():
            protocols.append("graphsync-filecoinv1")
        if "http" in context_id.lower():
            protocols.append("http")
        
        # Check metadata for protocol info
        metadata = provider_result.get("Metadata", {})
        if "Protocols" in metadata:
            protocols.extend(metadata["Protocols"])
        
        # Default to bitswap if nothing found
        if not protocols:
            protocols.append("bitswap")
        
        return list(set(protocols))
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if available and not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["timestamp"] < self.cache_duration:
                return entry["data"]
            else:
                del self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, data: Any) -> None:
        """Add value to cache."""
        self._cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
    
    def clear_cache(self) -> None:
        """Clear the provider cache."""
        self._cache.clear()
        logger.info("IPNI cache cleared")
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'client') and HTTPX_AVAILABLE:
            try:
                client = self.client

                def _close() -> None:
                    try:
                        anyio.run(client.aclose)
                    except Exception:
                        pass

                threading.Thread(target=_close, daemon=True).start()
            except Exception:
                pass
