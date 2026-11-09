"""
Enhanced Gateway Chain with IPNI and Saturn integration.

This module extends the basic GatewayChain with intelligent provider
discovery using IPNI and Saturn CDN acceleration.
"""

import logging
import time
import anyio
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

from .gateway_chain import GatewayChain
from ..discovery.ipni_client import IPNIClient

# Configure logger
logger = logging.getLogger(__name__)


class EnhancedGatewayChain(GatewayChain):
    """
    Enhanced gateway chain with IPNI provider discovery and Saturn CDN.
    
    This extends the basic gateway chain with:
    - IPNI integration for finding optimal providers
    - Saturn CDN node selection
    - Provider-specific routing
    - Performance-based provider ranking
    """
    
    def __init__(
        self,
        gateways: Optional[List[Dict[str, Any]]] = None,
        enable_lassie: bool = True,
        enable_saturn: bool = True,
        enable_ipni: bool = True,
        enable_parallel: bool = False,
        cache_duration: int = 3600
    ):
        """
        Initialize enhanced gateway chain.
        
        Args:
            gateways: List of gateway configurations
            enable_lassie: Enable Lassie retrieval
            enable_saturn: Enable Saturn CDN
            enable_ipni: Enable IPNI provider discovery
            enable_parallel: Enable parallel fetching
            cache_duration: Cache duration in seconds
        """
        super().__init__(
            gateways=gateways,
            enable_lassie=enable_lassie,
            enable_saturn=enable_saturn,
            enable_parallel=enable_parallel,
            cache_duration=cache_duration
        )
        
        self.enable_ipni = enable_ipni
        
        # Initialize IPNI client if enabled
        if self.enable_ipni:
            self.ipni_client = IPNIClient(cache_duration=cache_duration)
            logger.info("IPNI client initialized for provider discovery")
        
        # Saturn node cache
        self._saturn_nodes = []
        
        # Provider performance tracking
        self._provider_metrics = {}
        
        logger.info("Enhanced Gateway Chain initialized with IPNI and Saturn support")
    
    async def fetch_with_discovery(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Fetch content using IPNI provider discovery.
        
        This method:
        1. Queries IPNI for providers
        2. Ranks providers by performance history
        3. Tries providers in optimal order
        4. Falls back to standard gateway chain
        
        Args:
            cid: Content identifier
            timeout: Request timeout in seconds
        
        Returns:
            Tuple of (content_bytes, metrics_dict)
        """
        # Check cache first
        cached = self._get_from_cache(cid)
        if cached:
            return cached, {
                "source": "cache",
                "duration_ms": 0,
                "size_bytes": len(cached),
                "cached": True,
                "method": "cache"
            }
        
        # Try IPNI-discovered providers if enabled
        if self.enable_ipni:
            try:
                content, metrics = await self._fetch_from_ipni_providers(cid, timeout)
                if content:
                    return content, metrics
            except Exception as e:
                logger.warning(f"IPNI provider fetch failed: {e}")
        
        # Try Saturn CDN if enabled
        if self.enable_saturn:
            try:
                content, metrics = await self._fetch_from_saturn(cid, timeout)
                if content:
                    return content, metrics
            except Exception as e:
                logger.debug(f"Saturn fetch failed: {e}")
        
        # Fall back to standard gateway chain
        logger.debug(f"Falling back to standard gateway chain for {cid}")
        return await self.fetch_with_metrics(cid, timeout)
    
    async def _fetch_from_ipni_providers(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """Fetch content from IPNI-discovered providers."""
        start_time = time.time()
        
        # Find providers via IPNI
        providers = await self.ipni_client.find_providers(cid, protocol="bitswap", limit=5)
        
        if not providers:
            logger.debug(f"No providers found for {cid} via IPNI")
            return None, {}
        
        logger.info(f"Found {len(providers)} providers for {cid} via IPNI")
        
        # Rank providers by performance history
        ranked_providers = self._rank_providers(providers)
        
        # Try providers in order
        for provider in ranked_providers:
            try:
                provider_id = provider["provider_id"]
                
                # Try HTTP protocol if available
                if "http" in provider.get("protocols", []):
                    content = await self._fetch_from_http_provider(provider, cid, timeout)
                    if content:
                        duration_ms = int((time.time() - start_time) * 1000)
                        
                        # Update provider metrics
                        self._update_provider_metrics(provider_id, True, duration_ms)
                        
                        # Cache the result
                        self._add_to_cache(cid, content)
                        
                        return content, {
                            "source": "ipni_provider",
                            "provider_id": provider_id,
                            "protocol": "http",
                            "duration_ms": duration_ms,
                            "size_bytes": len(content),
                            "method": "ipni_discovery"
                        }
                
            except Exception as e:
                logger.debug(f"Provider {provider.get('provider_id')} failed: {e}")
                self._update_provider_metrics(provider.get("provider_id"), False, 0)
                continue
        
        return None, {}
    
    async def _fetch_from_saturn(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[Optional[bytes], Dict[str, Any]]:
        """Fetch content from Saturn CDN."""
        start_time = time.time()
        
        # Get Saturn nodes
        nodes = await self._get_saturn_nodes()
        
        if not nodes:
            return None, {}
        
        # Try Saturn nodes
        for node in nodes[:3]:  # Try top 3 nodes
            try:
                url = urljoin(node, f"ipfs/{cid}")
                req_timeout = timeout or 30
                
                if hasattr(self, 'client'):
                    response = await self.client.get(url, timeout=req_timeout)
                    response.raise_for_status()
                    content = response.content
                else:
                    # Sync fallback
                    content = await anyio.to_thread.run_sync(
                        lambda: self.session.get(url, timeout=req_timeout).content
                    )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Cache the result
                self._add_to_cache(cid, content)
                
                return content, {
                    "source": "saturn",
                    "node": node,
                    "duration_ms": duration_ms,
                    "size_bytes": len(content),
                    "method": "saturn_cdn",
                    "success": True,
                }
                
            except Exception as e:
                logger.debug(f"Saturn node {node} failed: {e}")
                continue
        
        return None, {}
    
    async def _fetch_from_http_provider(
        self,
        provider: Dict[str, Any],
        cid: str,
        timeout: Optional[int] = None
    ) -> Optional[bytes]:
        """Fetch content from an HTTP-capable provider."""
        # Extract HTTP address from provider
        for addr in provider.get("addresses", []):
            if "/http" in addr or "https://" in addr:
                try:
                    # Parse multiaddr or direct URL
                    if addr.startswith("http"):
                        url = urljoin(addr, f"ipfs/{cid}")
                    else:
                        # Skip complex multiaddr parsing for now
                        continue
                    
                    req_timeout = timeout or 30
                    
                    if hasattr(self, 'client'):
                        response = await self.client.get(url, timeout=req_timeout)
                        response.raise_for_status()
                        return response.content
                    else:
                        response = self.session.get(url, timeout=req_timeout)
                        response.raise_for_status()
                        return response.content
                        
                except Exception as e:
                    logger.debug(f"HTTP provider fetch failed: {e}")
                    continue
        
        return None
    
    async def _get_saturn_nodes(self) -> List[str]:
        """Get list of Saturn CDN nodes."""
        # Use cached nodes if available
        if self._saturn_nodes:
            return self._saturn_nodes
        
        # Try to get nodes from Saturn orchestrator
        try:
            orchestrator_url = "https://orchestrator.saturn.ms/nodes"
            
            if hasattr(self, 'client'):
                response = await self.client.get(orchestrator_url, timeout=10)
                response.raise_for_status()
                nodes_data = response.json()
            else:
                response = self.session.get(orchestrator_url, timeout=10)
                response.raise_for_status()
                nodes_data = response.json()
            
            # Extract node URLs
            if isinstance(nodes_data, list):
                self._saturn_nodes = [
                    node["url"] if isinstance(node, dict) else node
                    for node in nodes_data[:10]  # Top 10 nodes
                ]
            
            logger.info(f"Retrieved {len(self._saturn_nodes)} Saturn nodes")
            
        except Exception as e:
            logger.warning(f"Failed to get Saturn nodes: {e}")
            # Use fallback nodes
            self._saturn_nodes = [
                "https://node1.saturn.ms/",
                "https://node2.saturn.ms/"
            ]
        
        return self._saturn_nodes
    
    def _rank_providers(self, providers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank providers by performance history."""
        ranked = []
        
        for provider in providers:
            provider_id = provider["provider_id"]
            metrics = self._provider_metrics.get(provider_id, {
                "success_count": 0,
                "fail_count": 0,
                "avg_time_ms": 0
            })
            
            # Calculate score (higher is better)
            total_requests = metrics["success_count"] + metrics["fail_count"]
            if total_requests > 0:
                success_rate = metrics["success_count"] / total_requests
                # Score: success_rate * 1000 - avg_time_ms
                score = (success_rate * 1000) - metrics.get("avg_time_ms", 500)
            else:
                # New provider gets neutral score
                score = 500
            
            ranked.append({
                **provider,
                "score": score
            })
        
        # Sort by score (descending)
        ranked.sort(key=lambda p: p["score"], reverse=True)
        
        return ranked
    
    def _update_provider_metrics(
        self,
        provider_id: str,
        success: bool,
        duration_ms: int
    ) -> None:
        """Update performance metrics for a provider."""
        if provider_id not in self._provider_metrics:
            self._provider_metrics[provider_id] = {
                "success_count": 0,
                "fail_count": 0,
                "avg_time_ms": 0
            }
        
        metrics = self._provider_metrics[provider_id]
        
        if success:
            metrics["success_count"] += 1
            # Update running average
            success_count = metrics["success_count"]
            current_avg = metrics["avg_time_ms"]
            metrics["avg_time_ms"] = ((current_avg * (success_count - 1)) + duration_ms) / success_count
        else:
            metrics["fail_count"] += 1
    
    def get_provider_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for all providers."""
        return self._provider_metrics.copy()
