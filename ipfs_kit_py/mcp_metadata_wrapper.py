"""
MCP Metadata Wrapper

This module wraps MCP tools to check metadata in ~/.ipfs_kit/ before making calls
to the ipfs_kit_py library, as specified in the requirements.
"""

import logging
import functools
from typing import Dict, Any, Optional, Callable, Union
import asyncio

from .metadata_manager import get_metadata_manager
from .service_registry import get_service_registry

logger = logging.getLogger(__name__)


class MCPMetadataWrapper:
    """
    Wrapper for MCP tools that checks metadata before library calls.
    
    This class intercepts MCP tool calls and:
    1. Checks ~/.ipfs_kit/ metadata first
    2. Uses cached/stored information when available
    3. Falls back to ipfs_kit_py library calls when needed
    """
    
    def __init__(self):
        self.metadata_manager = get_metadata_manager()
        self.service_registry = get_service_registry()
        self._cache = {}
        
    def metadata_first(self, service_name: str = None, cache_ttl: int = 300):
        """
        Decorator to check metadata before calling the actual method.
        
        Args:
            service_name: Name of the service to check
            cache_ttl: Time to live for cached results in seconds
        """
        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{func.__name__}:{service_name}:{hash(str(args) + str(sorted(kwargs.items())))}"
                
                # Check metadata first
                metadata_result = await self._check_metadata(func.__name__, service_name, *args, **kwargs)
                if metadata_result is not None:
                    logger.debug(f"Using metadata result for {func.__name__}")
                    return metadata_result
                
                # Check cache
                if cache_key in self._cache:
                    cached_result = self._cache[cache_key]
                    if cached_result.get("ttl", 0) > asyncio.get_event_loop().time():
                        logger.debug(f"Using cached result for {func.__name__}")
                        return cached_result["data"]
                
                # Fall back to library call
                logger.debug(f"Making library call for {func.__name__}")
                try:
                    result = await func(*args, **kwargs)
                    
                    # Cache the result
                    self._cache[cache_key] = {
                        "data": result,
                        "ttl": asyncio.get_event_loop().time() + cache_ttl
                    }
                    
                    # Update metadata if successful
                    await self._update_metadata(func.__name__, service_name, result, *args, **kwargs)
                    
                    return result
                except Exception as e:
                    logger.error(f"Library call failed for {func.__name__}: {e}")
                    raise
                    
            return wrapper
        return decorator
    
    async def _check_metadata(self, method_name: str, service_name: str, *args, **kwargs) -> Optional[Any]:
        """
        Check metadata for the requested information.
        
        Args:
            method_name: Name of the method being called
            service_name: Service name to check
            
        Returns:
            Metadata result if available, None otherwise
        """
        if not service_name:
            return None
            
        try:
            # Check service state
            service_state = self.metadata_manager.get_service_state(service_name)
            
            # Handle common method patterns
            if method_name.endswith("_status") or method_name == "status":
                return await self._get_status_from_metadata(service_name, service_state)
            
            elif method_name.endswith("_config") or method_name == "get_config":
                return self._get_config_from_metadata(service_name)
            
            elif method_name.startswith("list_"):
                return await self._get_list_from_metadata(service_name, method_name, *args, **kwargs)
            
            elif method_name in ["get_stats", "stats"]:
                return await self._get_stats_from_metadata(service_name)
            
            # Add more method pattern handlers as needed
            return None
            
        except Exception as e:
            logger.warning(f"Failed to check metadata for {method_name}: {e}")
            return None
    
    async def _get_status_from_metadata(self, service_name: str, service_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get service status from metadata."""
        if not service_state or service_state.get("status") == "unknown":
            return None
        
        # Get additional monitoring data
        monitoring_data = self.metadata_manager.get_monitoring_data(service_name)
        
        status = {
            "service": service_name,
            "status": service_state.get("status", "unknown"),
            "last_updated": service_state.get("last_updated"),
        }
        
        # Add monitoring data if available
        if monitoring_data and "data" in monitoring_data:
            status.update(monitoring_data["data"])
        
        return status
    
    def _get_config_from_metadata(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service configuration from metadata."""
        config = self.metadata_manager.get_service_config(service_name)
        if config and "config" in config:
            return config["config"]
        return None
    
    async def _get_list_from_metadata(self, service_name: str, method_name: str, *args, **kwargs) -> Optional[Any]:
        """Get list data from metadata."""
        # This could be enhanced to cache list results
        # For now, return None to force library call
        return None
    
    async def _get_stats_from_metadata(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics from metadata."""
        monitoring_data = self.metadata_manager.get_monitoring_data(service_name, "stats")
        if monitoring_data and "data" in monitoring_data:
            return monitoring_data["data"]
        return None
    
    async def _update_metadata(self, method_name: str, service_name: str, result: Any, *args, **kwargs):
        """
        Update metadata with the result of a library call.
        
        Args:
            method_name: Name of the method that was called
            service_name: Service name
            result: Result from the library call
        """
        try:
            if not service_name:
                return
                
            # Update service state based on result
            if method_name.endswith("_status") or method_name == "status":
                await self._update_service_status(service_name, result)
            
            elif method_name == "get_stats" or method_name == "stats":
                await self._update_service_stats(service_name, result)
            
            # Add more update handlers as needed
            
        except Exception as e:
            logger.warning(f"Failed to update metadata for {method_name}: {e}")
    
    async def _update_service_status(self, service_name: str, status_result: Dict[str, Any]):
        """Update service status in metadata."""
        state = {
            "status": status_result.get("status", "unknown"),
            "last_checked": status_result.get("timestamp", "unknown"),
            "details": status_result
        }
        self.metadata_manager.set_service_state(service_name, state)
    
    async def _update_service_stats(self, service_name: str, stats_result: Dict[str, Any]):
        """Update service statistics in metadata."""
        self.metadata_manager.set_monitoring_data(service_name, stats_result, "stats")


# Global wrapper instance
_mcp_wrapper = None


def get_mcp_wrapper() -> MCPMetadataWrapper:
    """Get the global MCP metadata wrapper instance."""
    global _mcp_wrapper
    if _mcp_wrapper is None:
        _mcp_wrapper = MCPMetadataWrapper()
    return _mcp_wrapper


# Convenience decorators
def with_metadata_check(service_name: str = None, cache_ttl: int = 300):
    """Convenience decorator for metadata checking."""
    wrapper = get_mcp_wrapper()
    return wrapper.metadata_first(service_name=service_name, cache_ttl=cache_ttl)


# Enhanced MCP tool wrappers
class EnhancedMCPTools:
    """
    Enhanced MCP tools that use metadata-first approach.
    """
    
    def __init__(self):
        self.wrapper = get_mcp_wrapper()
        self.service_registry = get_service_registry()
    
    @with_metadata_check(service_name="ipfs", cache_ttl=60)
    async def ipfs_status(self) -> Dict[str, Any]:
        """Get IPFS status with metadata check."""
        # This will be intercepted by the metadata wrapper
        # Actual implementation would call ipfs_kit_py
        from ..ipfs import ipfs_py
        ipfs = ipfs_py()
        return await ipfs.id()
    
    @with_metadata_check(service_name="ipfs_cluster", cache_ttl=60)
    async def ipfs_cluster_status(self) -> Dict[str, Any]:
        """Get IPFS Cluster status with metadata check."""
        service_status = await self.service_registry.get_service_status("ipfs_cluster")
        if service_status:
            return service_status
        
        # Fall back to library call
        from ..ipfs_cluster_service import ipfs_cluster_service
        cluster = ipfs_cluster_service()
        return await cluster.status()
    
    @with_metadata_check(service_name="s3", cache_ttl=300)
    async def s3_status(self) -> Dict[str, Any]:
        """Get S3 status with metadata check."""
        service_status = await self.service_registry.get_service_status("s3")
        if service_status:
            return service_status
        
        # Fall back to library call
        from ..s3_kit import s3_kit
        s3 = s3_kit()
        return {"status": "available", "backend": "s3"}
    
    @with_metadata_check(cache_ttl=60)
    async def get_all_service_status(self) -> Dict[str, Any]:
        """Get status of all services with metadata check."""
        return await self.service_registry.get_all_service_status()
    
    async def add_service(self, service_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Add a service to the registry."""
        return await self.service_registry.add_service(service_name, config)
    
    async def remove_service(self, service_name: str) -> bool:
        """Remove a service from the registry."""
        return await self.service_registry.remove_service(service_name)
    
    async def update_service_config(self, service_name: str, config: Dict[str, Any]) -> bool:
        """Update service configuration."""
        if service_name not in self.service_registry.services:
            return False
        
        service = self.service_registry.services[service_name]
        return service.set_config(config)
    
    async def start_service(self, service_name: str) -> bool:
        """Start a service."""
        return await self.service_registry.start_service(service_name)
    
    async def stop_service(self, service_name: str) -> bool:
        """Stop a service."""
        return await self.service_registry.stop_service(service_name)


# Global enhanced tools instance
_enhanced_tools = None


def get_enhanced_mcp_tools() -> EnhancedMCPTools:
    """Get the global enhanced MCP tools instance."""
    global _enhanced_tools
    if _enhanced_tools is None:
        _enhanced_tools = EnhancedMCPTools()
    return _enhanced_tools