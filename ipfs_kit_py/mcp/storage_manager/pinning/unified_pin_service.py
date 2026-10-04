"""
Unified Pinning Service - consistent pinning API across backends.

This module provides a unified interface for pinning content across
multiple storage backends that support pinning operations.
"""

import logging
import anyio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)


class UnifiedPinService:
    """
    Provides a consistent pinning API across all backends that support it.
    
    Supported backends:
    - IPFS (local daemon pinning)
    - Filecoin Pin (cloud pinning with Filecoin backing)
    - Storacha (w3up pinning)
    - Pinata (3rd party service - future)
    - Web3.storage (legacy - future)
    """
    
    def __init__(self, storage_manager=None):
        """
        Initialize unified pin service.
        
        Args:
            storage_manager: UnifiedStorageManager instance (optional)
        """
        self.storage_manager = storage_manager
        self._supported_backends = ["ipfs", "filecoin_pin", "storacha"]
        
        logger.info(f"Initialized UnifiedPinService with {len(self._supported_backends)} backends")
    
    async def pin(
        self,
        cid: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        backends: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Pin content to one or more backends.
        
        Args:
            cid: Content identifier to pin
            name: Human-readable name for the pin
            metadata: Additional metadata for the pin
            backends: List of backend names (default: ["ipfs", "filecoin_pin"])
        
        Returns:
            Dictionary with pin results per backend
        """
        if backends is None:
            backends = ["ipfs", "filecoin_pin"]
        
        # Validate backends
        invalid_backends = [b for b in backends if b not in self._supported_backends]
        if invalid_backends:
            logger.warning(f"Invalid backends requested: {invalid_backends}")
            backends = [b for b in backends if b in self._supported_backends]
        
        if not backends:
            return {
                "success": False,
                "error": "No valid backends specified",
                "cid": cid
            }
        
        # Prepare metadata
        pin_metadata = metadata or {}
        pin_metadata["name"] = name or f"pin-{cid[:12]}"
        pin_metadata["pinned_at"] = datetime.utcnow().isoformat()
        
        # Pin to each backend
        results = {}
        overall_success = True
        
        for backend_name in backends:
            try:
                result = await self._pin_to_backend(cid, backend_name, pin_metadata)
                results[backend_name] = result
                
                if not result.get("success", False):
                    overall_success = False
                    
            except Exception as e:
                logger.error(f"Error pinning to {backend_name}: {e}")
                results[backend_name] = {
                    "success": False,
                    "error": str(e)
                }
                overall_success = False
        
        return {
            "success": overall_success,
            "cid": cid,
            "backends": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def unpin(
        self,
        cid: str,
        backends: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Unpin content from one or more backends."""
        if backends is None:
            backends = await self._find_backends_with_cid(cid)
        
        if not backends:
            return {
                "success": False,
                "error": "No backends found with this CID",
                "cid": cid
            }
        
        results = {}
        overall_success = True
        
        for backend_name in backends:
            try:
                result = await self._unpin_from_backend(cid, backend_name)
                results[backend_name] = result
                
                if not result.get("success", False):
                    overall_success = False
                    
            except Exception as e:
                logger.error(f"Error unpinning from {backend_name}: {e}")
                results[backend_name] = {
                    "success": False,
                    "error": str(e)
                }
                overall_success = False
        
        return {
            "success": overall_success,
            "cid": cid,
            "backends": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def list_pins(
        self,
        backend: Optional[str] = None,
        status: Optional[str] = "pinned",
        limit: int = 100
    ) -> Dict[str, Any]:
        """List pins from one or all backends."""
        backends_to_query = [backend] if backend else self._supported_backends
        
        results = {}
        total_count = 0
        overall_success = True
        
        for backend_name in backends_to_query:
            try:
                result = await self._list_pins_from_backend(backend_name, status, limit)
                
                if result.get("success", False):
                    pins = result.get("pins", [])
                    results[backend_name] = {
                        "pins": pins,
                        "count": len(pins)
                    }
                    total_count += len(pins)
                else:
                    results[backend_name] = {
                        "error": result.get("error", "Unknown error"),
                        "count": 0
                    }
                    overall_success = False
                    
            except Exception as e:
                logger.error(f"Error listing pins from {backend_name}: {e}")
                results[backend_name] = {
                    "error": str(e),
                    "count": 0
                }
                overall_success = False
        
        return {
            "success": overall_success,
            "backends": results,
            "total_count": total_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def pin_status(
        self,
        cid: str,
        backend: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get pin status for a CID across backends."""
        backends_to_query = [backend] if backend else self._supported_backends
        
        results = {}
        overall_success = True
        
        for backend_name in backends_to_query:
            try:
                result = await self._get_pin_status_from_backend(cid, backend_name)
                
                if result.get("success", False):
                    results[backend_name] = {
                        "status": result.get("status", "unknown"),
                        "details": result
                    }
                else:
                    results[backend_name] = {
                        "status": "not_found",
                        "error": result.get("error", "Unknown error")
                    }
                    overall_success = False
                    
            except Exception as e:
                logger.error(f"Error getting pin status from {backend_name}: {e}")
                results[backend_name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_success = False
        
        return {
            "success": overall_success,
            "cid": cid,
            "backends": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Private helper methods
    
    async def _pin_to_backend(
        self,
        cid: str,
        backend_name: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Pin content to a specific backend."""
        if self.storage_manager:
            backend = self.storage_manager.get_backend(backend_name)
            if backend:
                return backend.add_content(content=cid, metadata=metadata)
        
        logger.warning(f"No storage manager available, using mock pin for {backend_name}")
        return {
            "success": True,
            "status": "pinned",
            "cid": cid,
            "backend": backend_name,
            "mock": True
        }
    
    async def _unpin_from_backend(self, cid: str, backend_name: str) -> Dict[str, Any]:
        """Unpin content from a specific backend."""
        if self.storage_manager:
            backend = self.storage_manager.get_backend(backend_name)
            if backend:
                return backend.remove_content(cid)
        
        return {"success": True, "cid": cid, "backend": backend_name, "mock": True}
    
    async def _list_pins_from_backend(
        self, backend_name: str, status: Optional[str], limit: int
    ) -> Dict[str, Any]:
        """List pins from a specific backend."""
        if self.storage_manager:
            backend = self.storage_manager.get_backend(backend_name)
            if backend and hasattr(backend, 'list_pins'):
                return backend.list_pins(status=status, limit=limit)
        
        return {"success": True, "pins": [], "count": 0, "mock": True}
    
    async def _get_pin_status_from_backend(
        self, cid: str, backend_name: str
    ) -> Dict[str, Any]:
        """Get pin status from a specific backend."""
        if self.storage_manager:
            backend = self.storage_manager.get_backend(backend_name)
            if backend:
                return backend.get_metadata(cid)
        
        return {"success": True, "status": "unknown", "cid": cid, "mock": True}
    
    async def _find_backends_with_cid(self, cid: str) -> List[str]:
        """Find which backends have a specific CID pinned."""
        backends_with_cid = []
        
        for backend_name in self._supported_backends:
            try:
                result = await self._get_pin_status_from_backend(cid, backend_name)
                if result.get("success") and result.get("status") in ["pinned", "pinning"]:
                    backends_with_cid.append(backend_name)
            except Exception as e:
                logger.debug(f"Error checking {backend_name} for CID {cid}: {e}")
        
        return backends_with_cid
