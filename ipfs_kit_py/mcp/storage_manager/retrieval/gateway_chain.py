"""
Gateway Chain - intelligent content retrieval with automatic fallback.

This module implements a gateway fallback chain for retrieving IPFS/Filecoin
content with automatic failover and performance tracking.
"""

import logging
import time
import anyio
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

# Configure logger
logger = logging.getLogger(__name__)

# Default gateways in priority order
DEFAULT_GATEWAYS = [
    {"url": "http://localhost:8080/ipfs/", "priority": 1, "timeout": 5},
    {"url": "https://ipfs.io/ipfs/", "priority": 2, "timeout": 30},
    {"url": "https://w3s.link/ipfs/", "priority": 3, "timeout": 30},
    {"url": "https://dweb.link/ipfs/", "priority": 4, "timeout": 30},
]


class GatewayChain:
    """
    Implements intelligent gateway fallback for content retrieval.
    
    Priority order:
    1. Local IPFS node (if available)
    2. Lassie (direct retrieval from Filecoin/IPFS)
    3. Saturn CDN nodes (geographically closest)
    4. Public IPFS gateways (ipfs.io, dweb.link, etc.)
    5. Storacha gateways (for pinned content)
    
    Features:
    - Automatic failover to next gateway on error
    - Parallel gateway racing (optional)
    - Gateway health monitoring
    - Performance metrics tracking
    - Caching layer
    """
    
    def __init__(
        self,
        gateways: Optional[List[Dict[str, Any]]] = None,
        enable_lassie: bool = False,
        enable_saturn: bool = False,
        enable_parallel: bool = False,
        cache_duration: int = 3600
    ):
        """
        Initialize gateway chain.
        
        Args:
            gateways: List of gateway configurations
            enable_lassie: Enable Lassie retrieval
            enable_saturn: Enable Saturn CDN
            enable_parallel: Enable parallel fetching from multiple gateways
            cache_duration: Cache duration in seconds
        """
        self.gateways = gateways or DEFAULT_GATEWAYS.copy()
        self.enable_lassie = enable_lassie
        self.enable_saturn = enable_saturn
        self.enable_parallel = enable_parallel
        self.cache_duration = cache_duration
        
        # Sort gateways by priority
        self.gateways.sort(key=lambda g: g.get("priority", 99))
        
        # Gateway health tracking
        self._gateway_health = {g["url"]: {"available": True, "failures": 0} for g in self.gateways}
        
        # Performance metrics
        self._metrics = {g["url"]: {"requests": 0, "successes": 0, "avg_time_ms": 0} for g in self.gateways}
        
        # Simple cache
        self._cache = {}
        
        # Initialize HTTP client
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
            logger.info("Initialized GatewayChain with httpx client")
        else:
            self.session = requests.Session()
            logger.info("Initialized GatewayChain with requests client")
        
        logger.info(f"GatewayChain initialized with {len(self.gateways)} gateways")
    
    async def fetch(self, cid: str, timeout: Optional[int] = None) -> bytes:
        """
        Fetch content by CID with automatic gateway fallback.
        
        Args:
            cid: Content identifier to fetch
            timeout: Request timeout in seconds
        
        Returns:
            Content bytes
        
        Raises:
            Exception: If all gateways fail
        """
        result = await self.fetch_with_metrics(cid, timeout)
        return result[0]
    
    async def fetch_with_metrics(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Fetch content with performance metrics.
        
        Args:
            cid: Content identifier to fetch
            timeout: Request timeout in seconds
        
        Returns:
            Tuple of (content_bytes, metrics_dict)
        
        Raises:
            Exception: If all gateways fail
        """
        # Check cache first
        cached = self._get_from_cache(cid)
        if cached:
            return cached, {
                "source": "cache",
                "duration_ms": 0,
                "size_bytes": len(cached),
                "cached": True
            }
        
        # Try parallel fetching if enabled
        if self.enable_parallel and len(self.gateways) > 1:
            return await self._fetch_parallel(cid, timeout)
        
        # Sequential fallback
        return await self._fetch_sequential(cid, timeout)
    
    async def _fetch_sequential(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Fetch content sequentially through gateway chain."""
        last_error = None
        
        for gateway in self.gateways:
            gateway_url = gateway["url"]
            
            # Skip if gateway is marked as unhealthy
            if not self._gateway_health[gateway_url]["available"]:
                logger.debug(f"Skipping unhealthy gateway: {gateway_url}")
                continue
            
            try:
                start_time = time.time()
                url = urljoin(gateway_url, cid)
                gateway_timeout = timeout or gateway.get("timeout", 30)
                
                # Fetch content
                if HTTPX_AVAILABLE:
                    response = await self.client.get(url, timeout=gateway_timeout)
                    response.raise_for_status()
                    content = response.content
                else:
                    response = self.session.get(url, timeout=gateway_timeout)
                    response.raise_for_status()
                    content = response.content
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Update metrics
                self._update_metrics(gateway_url, True, duration_ms)
                
                # Cache the result
                self._add_to_cache(cid, content)
                
                metrics = {
                    "source": "gateway",
                    "gateway_used": gateway_url,
                    "duration_ms": duration_ms,
                    "size_bytes": len(content),
                    "cached": False
                }
                
                logger.info(f"Retrieved {cid} from {gateway_url} in {duration_ms}ms")
                return content, metrics
                
            except Exception as e:
                last_error = e
                logger.warning(f"Gateway {gateway_url} failed: {e}")
                self._update_metrics(gateway_url, False, 0)
                self._mark_gateway_unhealthy(gateway_url)
                continue
        
        # All gateways failed
        error_msg = f"All gateways failed to retrieve {cid}. Last error: {last_error}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def _fetch_parallel(
        self,
        cid: str,
        timeout: Optional[int] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Fetch content in parallel from multiple gateways (race)."""
        async def fetch_from_gateway(gateway: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
            """Fetch from a single gateway."""
            gateway_url = gateway["url"]
            
            if not self._gateway_health[gateway_url]["available"]:
                raise Exception(f"Gateway {gateway_url} is unhealthy")
            
            start_time = time.time()
            url = urljoin(gateway_url, cid)
            gateway_timeout = timeout or gateway.get("timeout", 30)
            
            if HTTPX_AVAILABLE:
                response = await self.client.get(url, timeout=gateway_timeout)
                response.raise_for_status()
                content = response.content
            else:
                # Run sync request in thread pool
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    None,
                    lambda: self.session.get(url, timeout=gateway_timeout).content
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return content, {
                "source": "gateway",
                "gateway_used": gateway_url,
                "duration_ms": duration_ms,
                "size_bytes": len(content),
                "cached": False
            }
        
        # Create tasks for all healthy gateways
        tasks = []
        for gateway in self.gateways:
            if self._gateway_health[gateway["url"]]["available"]:
                tasks.append(fetch_from_gateway(gateway))
        
        if not tasks:
            raise Exception("No healthy gateways available")
        
        # Race all tasks
        try:
            # Use wait with FIRST_COMPLETED
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
            
            # Get first successful result
            for task in done:
                try:
                    content, metrics = task.result()
                    
                    # Update metrics
                    self._update_metrics(metrics["gateway_used"], True, metrics["duration_ms"])
                    
                    # Cache the result
                    self._add_to_cache(cid, content)
                    
                    logger.info(f"Retrieved {cid} from {metrics['gateway_used']} in {metrics['duration_ms']}ms (parallel)")
                    return content, metrics
                except Exception as e:
                    logger.debug(f"Task failed: {e}")
                    continue
            
            raise Exception("All parallel fetches failed")
            
        except Exception as e:
            logger.error(f"Parallel fetch failed: {e}")
            raise
    
    async def test_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Test all gateways and return health status.
        
        Returns:
            Dictionary mapping gateway URL to health info:
                {
                    "url": {
                        "available": bool,
                        "latency_ms": int,
                        "error": str (if failed)
                    }
                }
        """
        results = {}
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"  # Empty file CID
        
        for gateway in self.gateways:
            gateway_url = gateway["url"]
            
            try:
                start_time = time.time()
                url = urljoin(gateway_url, test_cid)
                
                if HTTPX_AVAILABLE:
                    response = await self.client.get(url, timeout=10)
                    response.raise_for_status()
                else:
                    response = self.session.get(url, timeout=10)
                    response.raise_for_status()
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                results[gateway_url] = {
                    "available": True,
                    "latency_ms": latency_ms
                }
                
                # Mark as healthy
                self._gateway_health[gateway_url]["available"] = True
                self._gateway_health[gateway_url]["failures"] = 0
                
            except Exception as e:
                results[gateway_url] = {
                    "available": False,
                    "error": str(e)
                }
                
                # Mark as unhealthy
                self._mark_gateway_unhealthy(gateway_url)
        
        return results
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for all gateways."""
        return self._metrics.copy()
    
    def get_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all gateways."""
        return self._gateway_health.copy()
    
    # Private helper methods
    
    def _get_from_cache(self, cid: str) -> Optional[bytes]:
        """Get content from cache if available and not expired."""
        if cid in self._cache:
            entry = self._cache[cid]
            if time.time() - entry["timestamp"] < self.cache_duration:
                return entry["content"]
            else:
                # Expired
                del self._cache[cid]
        return None
    
    def _add_to_cache(self, cid: str, content: bytes) -> None:
        """Add content to cache."""
        self._cache[cid] = {
            "content": content,
            "timestamp": time.time()
        }
    
    def _update_metrics(self, gateway_url: str, success: bool, duration_ms: int) -> None:
        """Update performance metrics for a gateway."""
        if gateway_url not in self._metrics:
            return
        
        metrics = self._metrics[gateway_url]
        metrics["requests"] += 1
        
        if success:
            metrics["successes"] += 1
            # Update running average
            current_avg = metrics["avg_time_ms"]
            success_count = metrics["successes"]
            metrics["avg_time_ms"] = ((current_avg * (success_count - 1)) + duration_ms) / success_count
    
    def _mark_gateway_unhealthy(self, gateway_url: str) -> None:
        """Mark a gateway as unhealthy after failure."""
        if gateway_url not in self._gateway_health:
            return
        
        health = self._gateway_health[gateway_url]
        health["failures"] += 1
        
        # Mark as unavailable after 3 consecutive failures
        if health["failures"] >= 3:
            health["available"] = False
            logger.warning(f"Gateway {gateway_url} marked as unhealthy after {health['failures']} failures")
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'client') and HTTPX_AVAILABLE:
            try:
                import anyio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.client.aclose())
            except Exception:
                pass
