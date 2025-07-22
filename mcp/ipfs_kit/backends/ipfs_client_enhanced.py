"""
Enhanced IPFS Client with Connection Pooling, Backoff, and CLI Fallback
"""

import asyncio
import json
import logging
import time
import warnings
from typing import Dict, Any, Optional
import httpx
import subprocess
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EnhancedIPFSClient:
    """Enhanced IPFS client with connection pooling, exponential backoff, and CLI fallback."""
    
    def __init__(self, api_endpoint: str = "http://127.0.0.1:5001", 
                 max_retries: int = 3, initial_backoff: float = 1.0):
        self.api_endpoint = api_endpoint
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        
        # Connection pooling with httpx
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            transport=httpx.AsyncHTTPTransport(retries=0)  # We handle retries manually
        )
        
        # Connection state tracking
        self.connection_failures = 0
        self.last_failure_time = None
        self.is_daemon_available = None
        self.last_health_check = None
        
        # Backoff state
        self.backoff_until = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return self.initial_backoff * (2 ** attempt) + (time.time() % 1)  # Add jitter
        
    def _should_skip_due_to_backoff(self) -> bool:
        """Check if we should skip this attempt due to backoff."""
        if self.backoff_until and datetime.now() < self.backoff_until:
            return True
        return False
        
    def _update_connection_state(self, success: bool):
        """Update connection state based on success/failure."""
        if success:
            self.connection_failures = 0
            self.last_failure_time = None
            self.backoff_until = None
            self.is_daemon_available = True
        else:
            self.connection_failures += 1
            self.last_failure_time = datetime.now()
            self.is_daemon_available = False
            
            # Set backoff period
            if self.connection_failures >= 3:
                backoff_seconds = min(60, self._calculate_backoff_delay(self.connection_failures - 3))
                self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
                logger.warning(f"IPFS connection failed {self.connection_failures} times, backing off for {backoff_seconds:.1f}s")
                
    async def _http_request(self, path: str, method: str = "GET", params: Dict = None, 
                           data: Any = None, timeout: float = 10.0) -> Dict[str, Any]:
        """Make HTTP request to IPFS API with retry logic."""
        
        if self._should_skip_due_to_backoff():
            raise ConnectionError(f"In backoff period until {self.backoff_until}")
            
        url = f"{self.api_endpoint}/api/v0{path}"
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"IPFS HTTP request attempt {attempt + 1}: {method} {url}")
                
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    self._update_connection_state(True)
                    return response.json()
                else:
                    logger.warning(f"IPFS HTTP request failed with status {response.status_code}: {response.text}")
                    
            except (httpx.ConnectError, httpx.TimeoutException, ConnectionRefusedError) as e:
                logger.warning(f"IPFS HTTP request attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.debug(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    self._update_connection_state(False)
                    raise ConnectionError(f"Failed to connect to IPFS daemon after {self.max_retries} attempts: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in IPFS HTTP request: {e}")
                self._update_connection_state(False)
                raise
                
        self._update_connection_state(False)
        raise ConnectionError(f"All {self.max_retries} HTTP attempts failed")
        
    async def _cli_request(self, command: list, timeout: float = 10.0) -> Dict[str, Any]:
        """Make CLI request to IPFS with retry logic."""
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"IPFS CLI request attempt {attempt + 1}: {' '.join(command)}")
                
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    raise TimeoutError(f"CLI command timed out after {timeout}s")
                    
                if process.returncode == 0:
                    self._update_connection_state(True)
                    output = stdout.decode('utf-8').strip()
                    try:
                        return json.loads(output)
                    except json.JSONDecodeError:
                        return {"raw_output": output}
                else:
                    error_msg = stderr.decode('utf-8').strip()
                    logger.warning(f"IPFS CLI command failed: {error_msg}")
                    
            except (FileNotFoundError, TimeoutError) as e:
                logger.warning(f"IPFS CLI attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.debug(f"Retrying CLI in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    self._update_connection_state(False)
                    raise ConnectionError(f"CLI command failed after {self.max_retries} attempts: {e}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in IPFS CLI request: {e}")
                self._update_connection_state(False)
                raise
                
        self._update_connection_state(False)
        raise ConnectionError(f"All {self.max_retries} CLI attempts failed")
        
    async def version(self) -> Dict[str, Any]:
        """Get IPFS version with HTTP/CLI fallback."""
        try:
            # Try HTTP first - IPFS API requires POST method
            result = await self._http_request("/version", method="POST")
            return result
        except Exception as http_error:
            logger.info(f"HTTP version request failed, trying CLI: {http_error}")
            try:
                # Fallback to CLI
                result = await self._cli_request(["ipfs", "version", "--json"])
                return result
            except Exception as cli_error:
                logger.error(f"Both HTTP and CLI version requests failed: HTTP={http_error}, CLI={cli_error}")
                raise ConnectionError(f"Failed to get IPFS version: HTTP={http_error}, CLI={cli_error}")
                
    async def stats_repo(self) -> Dict[str, Any]:
        """Get repository statistics."""
        try:
            # Try HTTP first - IPFS API requires POST method
            result = await self._http_request("/repo/stat", method="POST")
            return result
        except Exception as http_error:
            logger.info(f"HTTP repo stats failed, trying CLI: {http_error}")
            try:
                # Fallback to CLI
                result = await self._cli_request(["ipfs", "repo", "stat", "--json"])
                return result
            except Exception as cli_error:
                logger.error(f"Both HTTP and CLI repo stats failed: HTTP={http_error}, CLI={cli_error}")
                raise ConnectionError(f"Failed to get repo stats: HTTP={http_error}, CLI={cli_error}")
                
    async def stats_bw(self) -> Dict[str, Any]:
        """Get bandwidth statistics."""
        try:
            # Try HTTP first - IPFS API requires POST method
            result = await self._http_request("/stats/bw", method="POST")
            return result
        except Exception as http_error:
            logger.info(f"HTTP bandwidth stats failed, trying CLI: {http_error}")
            try:
                # Fallback to CLI  
                result = await self._cli_request(["ipfs", "stats", "bw", "--json"])
                return result
            except Exception as cli_error:
                logger.error(f"Both HTTP and CLI bandwidth stats failed: HTTP={http_error}, CLI={cli_error}")
                raise ConnectionError(f"Failed to get bandwidth stats: HTTP={http_error}, CLI={cli_error}")
                
    async def swarm_peers(self) -> Dict[str, Any]:
        """Get swarm peers."""
        try:
            # Try HTTP first - IPFS API requires POST method
            result = await self._http_request("/swarm/peers", method="POST")
            return result
        except Exception as http_error:
            logger.info(f"HTTP swarm peers failed, trying CLI: {http_error}")
            try:
                # Fallback to CLI
                result = await self._cli_request(["ipfs", "swarm", "peers", "--json"])
                return result
            except Exception as cli_error:
                logger.error(f"Both HTTP and CLI swarm peers failed: HTTP={http_error}, CLI={cli_error}")
                raise ConnectionError(f"Failed to get swarm peers: HTTP={http_error}, CLI={cli_error}")
                
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with caching."""
        now = datetime.now()
        
        # Use cached result if recent
        if (self.last_health_check and 
            (now - self.last_health_check).total_seconds() < 30 and
            self.is_daemon_available is not None):
            return {
                "status": "healthy" if self.is_daemon_available else "unhealthy",
                "cached": True,
                "last_check": self.last_health_check.isoformat()
            }
            
        try:
            # Quick version check as health indicator
            version_data = await self.version()
            
            health_result = {
                "status": "healthy",
                "version": version_data.get("Version", "unknown"),
                "commit": version_data.get("Commit", "unknown"),
                "golang_version": version_data.get("Golang", "unknown"),
                "api_available": True,
                "connection_failures": self.connection_failures,
                "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
            }
            
            # Try to get additional stats (non-blocking)
            try:
                repo_stats = await self.stats_repo()
                health_result.update({
                    "repo_size": repo_stats.get("RepoSize", 0),
                    "storage_max": repo_stats.get("StorageMax", 0),
                    "num_objects": repo_stats.get("NumObjects", 0)
                })
            except Exception as e:
                logger.debug(f"Could not get repo stats during health check: {e}")
                
            try:
                peers = await self.swarm_peers()
                peer_count = len(peers.get("Peers", [])) if isinstance(peers.get("Peers"), list) else 0
                health_result["peer_count"] = peer_count
            except Exception as e:
                logger.debug(f"Could not get peer count during health check: {e}")
                health_result["peer_count"] = 0
                
            self.last_health_check = now
            return health_result
            
        except Exception as e:
            self.last_health_check = now
            return {
                "status": "unhealthy",
                "error": str(e),
                "connection_failures": self.connection_failures,
                "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "in_backoff": self._should_skip_due_to_backoff()
            }


# Singleton instance for reuse
_ipfs_client_instance = None

async def get_ipfs_client() -> EnhancedIPFSClient:
    """Get singleton IPFS client instance."""
    global _ipfs_client_instance
    if _ipfs_client_instance is None:
        _ipfs_client_instance = EnhancedIPFSClient()
    return _ipfs_client_instance
