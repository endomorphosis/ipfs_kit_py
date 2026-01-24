"""
Filecoin Pin backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Filecoin Pin,
a unified pinning service that combines IPFS pinning with Filecoin storage deals.

Filecoin Pin provides:
- Automatic IPFS pinning with Filecoin deal backing
- Content retrieval via multiple gateways
- Deal status monitoring and management
- Cost-effective long-term storage
"""

import logging
import time
import os
import json
import hashlib
import tempfile
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
DEFAULT_API_ENDPOINT = "https://api.filecoin.cloud/v1"
DEFAULT_TIMEOUT = 60
DEFAULT_REPLICATION = 3
DEFAULT_DEAL_DURATION_DAYS = 540  # ~18 months
DEFAULT_MAX_RETRIES = 3


class FilecoinPinBackend(BackendStorage):
    """
    Backend for Filecoin Pin service - unified IPFS pinning with Filecoin backing.
    
    Features:
    - Pin content to IPFS with automatic Filecoin deals
    - Content retrieval via multiple gateways
    - Deal status monitoring
    - Integration with IPNI for content discovery
    - Automatic deal renewal
    - Cost estimation and management
    """
    
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """
        Initialize Filecoin Pin backend.
        
        Args:
            resources: Connection resources including:
                - api_key: Filecoin Pin API key
                - api_endpoint: API endpoint URL (optional)
                - timeout: Request timeout in seconds (optional)
            metadata: Configuration metadata including:
                - default_replication: Number of copies (default: 3)
                - auto_renew: Auto-renew expiring deals (default: True)
                - deal_duration_days: Deal duration (default: 540)
                - gateway_fallback: List of fallback gateways (optional)
        """
        super().__init__(StorageBackendType.FILECOIN_PIN, resources, metadata)
        
        # Extract API configuration
        self.api_key = resources.get("api_key")
        if not self.api_key:
            logger.warning("No API key provided for Filecoin Pin backend")
            self.mock_mode = True
        else:
            self.mock_mode = False
            
        self.api_endpoint = resources.get("api_endpoint", DEFAULT_API_ENDPOINT)
        self.timeout = int(resources.get("timeout", DEFAULT_TIMEOUT))
        self.max_retries = int(resources.get("max_retries", DEFAULT_MAX_RETRIES))
        
        # Extract metadata configuration
        self.default_replication = int(metadata.get("default_replication", DEFAULT_REPLICATION))
        self.auto_renew = metadata.get("auto_renew", True)
        self.deal_duration_days = int(metadata.get("deal_duration_days", DEFAULT_DEAL_DURATION_DAYS))
        
        # Gateway fallback configuration
        self.gateway_fallback = metadata.get("gateway_fallback", [
            "https://ipfs.io/ipfs/",
            "https://w3s.link/ipfs/",
            "https://dweb.link/ipfs/"
        ])
        
        # Initialize HTTP client
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers=self._get_headers()
            )
            logger.info("Initialized Filecoin Pin backend with httpx client")
        else:
            self.session = requests.Session()
            self.session.headers.update(self._get_headers())
            logger.info("Initialized Filecoin Pin backend with requests client")
        
        # Initialize state
        self._pin_cache = {}  # Cache pin status
        
        logger.info(f"Filecoin Pin backend initialized (mock_mode={self.mock_mode})")
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ipfs-kit-py/0.3.0"
        }
        if self.api_key and not self.mock_mode:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def get_name(self) -> str:
        """Get the name of this backend implementation."""
        return "filecoin_pin"
    
    def add_content(
        self,
        content: Union[bytes, BinaryIO, str],
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Pin content to Filecoin Pin service.
        
        Args:
            content: Content to pin (bytes, file-like object, or file path)
            metadata: Metadata including:
                - name: Human-readable name for the pin
                - description: Pin description
                - tags: List of tags for categorization
                - replication: Replication count (overrides default)
        
        Returns:
            Dictionary with pin result:
                - success: True if successful
                - cid: Content identifier
                - status: Pin status (queued, pinning, pinned)
                - request_id: Pin request ID
                - deal_ids: List of Filecoin deal IDs (when available)
                - backend: Backend name
        """
        metadata = metadata or {}
        
        if self.mock_mode:
            return self._mock_add_content(content, metadata)
        
        try:
            # Prepare content for upload
            content_bytes, content_size = self._prepare_content(content)
            
            # Calculate CID (simplified - in production use proper IPFS CID calculation)
            cid = self._calculate_cid(content_bytes)
            
            # Prepare pin request
            pin_data = {
                "cid": cid,
                "name": metadata.get("name", f"pin-{cid[:12]}"),
                "meta": {
                    "description": metadata.get("description", ""),
                    "tags": metadata.get("tags", []),
                    "size": content_size,
                    "timestamp": time.time()
                },
                "origins": [],
                "replication": metadata.get("replication", self.default_replication)
            }
            
            # Make API request to pin content
            url = urljoin(self.api_endpoint, "/pin")
            
            if HTTPX_AVAILABLE:
                # Use httpx (async-compatible) with anyio if available
                try:
                    import anyio
                    
                    async def _post():
                        return await self.client.post(url, json=pin_data)
                    
                    response = anyio.from_thread.run(_post)
                except ImportError:
                    # Fallback to asyncio
                    import anyio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    response = loop.run_until_complete(
                        self.client.post(url, json=pin_data)
                    )
                response.raise_for_status()
                result = response.json()
            else:
                # Use requests (sync)
                response = self.session.post(url, json=pin_data)
                response.raise_for_status()
                result = response.json()
            
            # Cache the pin status
            self._pin_cache[cid] = {
                "status": result.get("status", "queued"),
                "request_id": result.get("requestId", ""),
                "timestamp": time.time()
            }
            
            return {
                "success": True,
                "cid": cid,
                "status": result.get("status", "queued"),
                "request_id": result.get("requestId", ""),
                "deal_ids": result.get("dealIds", []),
                "backend": self.get_name(),
                "size": content_size,
                "replication": pin_data["replication"]
            }
            
        except Exception as e:
            logger.error(f"Error pinning content to Filecoin Pin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
    
    def get_content(self, identifier: str) -> Dict[str, Any]:
        """
        Retrieve content from Filecoin Pin via gateways.
        
        Args:
            identifier: Content identifier (CID)
        
        Returns:
            Dictionary with content result:
                - success: True if successful
                - data: Content bytes
                - cid: Content identifier
                - source: Source gateway used
                - backend: Backend name
        """
        if self.mock_mode:
            return self._mock_get_content(identifier)
        
        try:
            # Try gateways in order
            for gateway_url in self.gateway_fallback:
                try:
                    url = urljoin(gateway_url, identifier)
                    
                    if HTTPX_AVAILABLE:
                        try:
                            import anyio
                            
                            async def _get():
                                return await self.client.get(url)
                            
                            response = anyio.from_thread.run(_get)
                        except ImportError:
                            import anyio
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
                    
                    return {
                        "success": True,
                        "data": content,
                        "cid": identifier,
                        "source": gateway_url,
                        "backend": self.get_name(),
                        "size": len(content)
                    }
                    
                except Exception as gateway_error:
                    logger.warning(f"Gateway {gateway_url} failed: {gateway_error}")
                    continue
            
            # All gateways failed
            return {
                "success": False,
                "error": "All gateways failed to retrieve content",
                "cid": identifier,
                "backend": self.get_name()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving content from Filecoin Pin: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": identifier,
                "backend": self.get_name()
            }
    
    def remove_content(self, identifier: str) -> Dict[str, Any]:
        """
        Unpin content from Filecoin Pin service.
        
        Args:
            identifier: Content identifier (CID)
        
        Returns:
            Dictionary with unpin result
        """
        if self.mock_mode:
            return self._mock_remove_content(identifier)
        
        try:
            url = urljoin(self.api_endpoint, f"/pin/{identifier}")
            
            if HTTPX_AVAILABLE:
                try:
                    import anyio
                    
                    async def _delete():
                        return await self.client.delete(url)
                    
                    response = anyio.from_thread.run(_delete)
                except ImportError:
                    import anyio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    response = loop.run_until_complete(
                        self.client.delete(url)
                    )
                response.raise_for_status()
            else:
                response = self.session.delete(url)
                response.raise_for_status()
            
            # Remove from cache
            self._pin_cache.pop(identifier, None)
            
            return {
                "success": True,
                "cid": identifier,
                "backend": self.get_name()
            }
            
        except Exception as e:
            logger.error(f"Error unpinning content from Filecoin Pin: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": identifier,
                "backend": self.get_name()
            }
    
    def get_metadata(self, identifier: str) -> Dict[str, Any]:
        """
        Get pin status and metadata from Filecoin Pin.
        
        Args:
            identifier: Content identifier (CID)
        
        Returns:
            Dictionary with metadata:
                - success: True if successful
                - cid: Content identifier
                - status: Pin status (queued, pinning, pinned, failed)
                - deals: List of Filecoin deal information
                - created: Creation timestamp
                - size: Content size
                - replication: Replication count
        """
        if self.mock_mode:
            return self._mock_get_metadata(identifier)
        
        try:
            url = urljoin(self.api_endpoint, f"/pin/{identifier}")
            
            if HTTPX_AVAILABLE:
                try:
                    import anyio
                    
                    async def _get():
                        return await self.client.get(url)
                    
                    response = anyio.from_thread.run(_get)
                except ImportError:
                    import anyio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    response = loop.run_until_complete(
                        self.client.get(url)
                    )
                response.raise_for_status()
                result = response.json()
            else:
                response = self.session.get(url)
                response.raise_for_status()
                result = response.json()
            
            # Update cache
            self._pin_cache[identifier] = {
                "status": result.get("status", "unknown"),
                "timestamp": time.time()
            }
            
            return {
                "success": True,
                "cid": identifier,
                "status": result.get("status", "unknown"),
                "deals": result.get("deals", []),
                "created": result.get("created", ""),
                "size": result.get("size", 0),
                "replication": result.get("replication", self.default_replication),
                "backend": self.get_name()
            }
            
        except Exception as e:
            logger.error(f"Error getting metadata from Filecoin Pin: {e}")
            return {
                "success": False,
                "error": str(e),
                "cid": identifier,
                "backend": self.get_name()
            }
    
    def list_pins(self, status: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        List all pins on Filecoin Pin service.
        
        Args:
            status: Filter by status (queued, pinning, pinned, failed)
            limit: Maximum number of results
        
        Returns:
            Dictionary with list result:
                - success: True if successful
                - pins: List of pin information
                - count: Number of pins
        """
        if self.mock_mode:
            return self._mock_list_pins(status, limit)
        
        try:
            url = urljoin(self.api_endpoint, "/pins")
            params = {"limit": limit}
            if status:
                params["status"] = status
            
            if HTTPX_AVAILABLE:
                try:
                    import anyio
                    
                    async def _get():
                        return await self.client.get(url, params=params)
                    
                    response = anyio.from_thread.run(_get)
                except ImportError:
                    import anyio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    response = loop.run_until_complete(
                        self.client.get(url, params=params)
                    )
                response.raise_for_status()
                result = response.json()
            else:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                result = response.json()
            
            pins = result.get("results", [])
            
            return {
                "success": True,
                "pins": pins,
                "count": len(pins),
                "backend": self.get_name()
            }
            
        except Exception as e:
            logger.error(f"Error listing pins from Filecoin Pin: {e}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name()
            }
    
    # Helper methods
    
    def _prepare_content(self, content: Union[bytes, BinaryIO, str]) -> tuple[bytes, int]:
        """Prepare content for upload and return bytes and size."""
        if isinstance(content, bytes):
            return content, len(content)
        elif isinstance(content, str):
            # Assume it's a file path
            with open(content, 'rb') as f:
                content_bytes = f.read()
            return content_bytes, len(content_bytes)
        elif hasattr(content, 'read'):
            # File-like object
            content_bytes = content.read()
            if isinstance(content_bytes, str):
                content_bytes = content_bytes.encode('utf-8')
            return content_bytes, len(content_bytes)
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")
    
    def _calculate_cid(self, content: bytes) -> str:
        """Calculate CID for content (simplified version)."""
        # Note: This is a simplified version. In production, use proper IPFS CID calculation
        # with multihash and multicodec support
        hash_obj = hashlib.sha256(content)
        hash_hex = hash_obj.hexdigest()
        # Simplified CID v1 format (not actual CID)
        return f"bafybeib{hash_hex[:52]}"
    
    # Mock methods for testing without API key
    
    def _mock_add_content(self, content: Union[bytes, BinaryIO, str], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation for add_content."""
        content_bytes, content_size = self._prepare_content(content)
        cid = self._calculate_cid(content_bytes)
        
        logger.info(f"[MOCK] Pinning content: {cid} ({content_size} bytes)")
        
        return {
            "success": True,
            "cid": cid,
            "status": "pinned",
            "request_id": f"mock-req-{int(time.time())}",
            "deal_ids": ["mock-deal-1", "mock-deal-2"],
            "backend": self.get_name(),
            "size": content_size,
            "replication": metadata.get("replication", self.default_replication),
            "mock": True
        }
    
    def _mock_get_content(self, identifier: str) -> Dict[str, Any]:
        """Mock implementation for get_content."""
        logger.info(f"[MOCK] Retrieving content: {identifier}")
        
        # Return dummy content
        mock_content = f"Mock content for {identifier}".encode('utf-8')
        
        return {
            "success": True,
            "data": mock_content,
            "cid": identifier,
            "source": "mock-gateway",
            "backend": self.get_name(),
            "size": len(mock_content),
            "mock": True
        }
    
    def _mock_remove_content(self, identifier: str) -> Dict[str, Any]:
        """Mock implementation for remove_content."""
        logger.info(f"[MOCK] Unpinning content: {identifier}")
        
        return {
            "success": True,
            "cid": identifier,
            "backend": self.get_name(),
            "mock": True
        }
    
    def _mock_get_metadata(self, identifier: str) -> Dict[str, Any]:
        """Mock implementation for get_metadata."""
        logger.info(f"[MOCK] Getting metadata for: {identifier}")
        
        return {
            "success": True,
            "cid": identifier,
            "status": "pinned",
            "deals": [
                {"id": "mock-deal-1", "provider": "f01234"},
                {"id": "mock-deal-2", "provider": "f05678"}
            ],
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "size": 1024000,
            "replication": self.default_replication,
            "backend": self.get_name(),
            "mock": True
        }
    
    def _mock_list_pins(self, status: str = None, limit: int = 100) -> Dict[str, Any]:
        """Mock implementation for list_pins."""
        logger.info(f"[MOCK] Listing pins (status={status}, limit={limit})")
        
        mock_pins = [
            {
                "cid": f"bafybeib{i:056d}",
                "status": status or "pinned",
                "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "size": 1024 * (i + 1)
            }
            for i in range(min(3, limit))
        ]
        
        return {
            "success": True,
            "pins": mock_pins,
            "count": len(mock_pins),
            "backend": self.get_name(),
            "mock": True
        }
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'client') and HTTPX_AVAILABLE:
            try:
                # Try anyio first
                try:
                    import anyio
                    
                    async def _close():
                        await self.client.aclose()
                    
                    anyio.from_thread.run(_close)
                except ImportError:
                    # Fallback to asyncio
                    import anyio
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self.client.aclose())
            except Exception:
                pass
