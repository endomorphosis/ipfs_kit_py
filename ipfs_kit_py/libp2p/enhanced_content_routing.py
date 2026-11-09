"""
Enhanced content routing implementation for IPFS libp2p.

This module provides enhanced content routing capabilities on top of 
the standard libp2p content routing.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Callable, Awaitable

logger = logging.getLogger(__name__)

class EnhancedContentRouter:
    """
    Enhanced content router that adds additional capabilities to the standard
    libp2p content router.
    """
    
    def __init__(self, base_router=None, **kwargs):
        self.base_router = base_router
        self.providers = {}
        self.content_index = {}
        self.metrics = {
            "provides": 0,
            "lookups": 0,
            "successful_lookups": 0
        }
        self.options = kwargs
        logger.info("Initialized EnhancedContentRouter")
        
    async def provide(self, cid, **kwargs):
        """
        Announce that this node can provide a value for the given key.
        """
        if isinstance(cid, bytes):
            cid_str = cid.hex()
        else:
            cid_str = str(cid)
            
        self.providers[cid_str] = kwargs.get("provider_info", {})
        self.metrics["provides"] += 1
        
        logger.info(f"Added provider for CID {cid_str[:10]}...")
        
        # Call base router if available
        if self.base_router and hasattr(self.base_router, "provide"):
            try:
                await self.base_router.provide(cid, **kwargs)
            except Exception as e:
                logger.warning(f"Base router provide failed: {e}")
                
        return True
        
    async def find_providers(self, cid, limit=20, **kwargs):
        """
        Find providers for the given CID.
        """
        self.metrics["lookups"] += 1
        
        if isinstance(cid, bytes):
            cid_str = cid.hex()
        else:
            cid_str = str(cid)
            
        result = []
        
        # First check local cache
        if cid_str in self.providers:
            result.append({
                "id": "local", 
                "addrs": ["/ip4/127.0.0.1/tcp/4001"],
                "metadata": self.providers[cid_str]
            })
            
        # Then call base router if available
        if self.base_router and hasattr(self.base_router, "find_providers"):
            try:
                base_results = await self.base_router.find_providers(cid, limit=limit, **kwargs)
                if base_results:
                    result.extend(base_results)
            except Exception as e:
                logger.warning(f"Base router find_providers failed: {e}")
        
        if result:
            self.metrics["successful_lookups"] += 1
            
        logger.info(f"Found {len(result)} providers for CID {cid_str[:10]}...")
        return result[:limit]
        
    async def put_value(self, key, value, **kwargs):
        """
        Put a value in the DHT for the given key.
        """
        if isinstance(key, bytes):
            key_str = key.hex()
        else:
            key_str = str(key)
            
        self.content_index[key_str] = value
        
        # Call base router if available
        if self.base_router and hasattr(self.base_router, "put_value"):
            try:
                await self.base_router.put_value(key, value, **kwargs)
            except Exception as e:
                logger.warning(f"Base router put_value failed: {e}")
                
        logger.info(f"Put value for key {key_str[:10]}...")
        return True
        
    async def get_value(self, key, **kwargs):
        """
        Get a value from the DHT for the given key.
        """
        if isinstance(key, bytes):
            key_str = key.hex()
        else:
            key_str = str(key)
            
        # First check local cache
        if key_str in self.content_index:
            logger.info(f"Found value for key {key_str[:10]}... in local cache")
            return self.content_index[key_str]
            
        # Then call base router if available
        if self.base_router and hasattr(self.base_router, "get_value"):
            try:
                result = await self.base_router.get_value(key, **kwargs)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Base router get_value failed: {e}")
                
        logger.warning(f"Value not found for key {key_str[:10]}...")
        return None
        
    def get_metrics(self):
        """
        Get metrics for this router.
        """
        return self.metrics