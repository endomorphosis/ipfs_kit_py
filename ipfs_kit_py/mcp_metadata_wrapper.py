"""
MCP Tools Metadata-First Wrapper

This module wraps MCP tools to check ~/.ipfs_kit/ metadata first
before making calls to the ipfs_kit_py library.
"""

import logging
import os
import functools
import time
from typing import Dict, Any, Optional, Callable, Union
from pathlib import Path

from .metadata_manager import get_metadata_manager

logger = logging.getLogger(__name__)


class MetadataFirstMCP:
    """
    Wrapper for MCP tools that checks local metadata before library calls.
    
    This class provides a decorator and wrapper functions to ensure that
    MCP tools check the ~/.ipfs_kit/ metadata directory first before
    making calls to the main ipfs_kit_py library.
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
=======
        self._cache = {}
        
    def metadata_first(self, metadata_key: Optional[str] = None, cache_ttl: int = 300):
        """
        Decorator that checks metadata first before calling the wrapped function.
        
        Args:
            metadata_key: Key to check in metadata (if None, uses function name)
            cache_ttl: Cache time-to-live in seconds
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Determine metadata key
                key = metadata_key or func.__name__
                
                # Check cache first
                cache_key = f"{key}:{hash(str(args) + str(sorted(kwargs.items())))}"
                cached_result = self._get_cached_result(cache_key, cache_ttl)
                if cached_result is not None:
                    logger.debug(f"Returning cached result for {key}")
                    return cached_result
                
                # Check metadata
                metadata_result = self.metadata_manager.get_metadata(key)
                if metadata_result is not None:
                    logger.info(f"Found metadata for {key}, using local data")
                    self._cache_result(cache_key, metadata_result)
                    return metadata_result
                
                # Fall back to original function
                logger.debug(f"No metadata found for {key}, calling original function")
                try:
                    result = func(*args, **kwargs)
                    
                    # Store result in metadata for future use
                    if result is not None:
                        self.metadata_manager.set_metadata(key, result)
                        self._cache_result(cache_key, result)
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error in {func.__name__}: {e}")
                    # Check if we have stale metadata as fallback
                    stale_metadata = self.metadata_manager.get_metadata(f"{key}_stale")
                    if stale_metadata is not None:
                        logger.warning(f"Using stale metadata for {key} due to error")
                        return stale_metadata
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

    def _get_cached_result(self, cache_key: str, ttl: int) -> Optional[Any]:
        """Get cached result if not expired."""
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if cached_data['timestamp'] + ttl > time.time():
                return cached_data['data']
            else:
                # Remove expired cache
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, data: Any):
        """Cache a result."""
        import time
        self._cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def get_backend_config_metadata_first(self, backend_id: str) -> Optional[Dict[str, Any]]:
        """
        Get backend configuration, checking metadata first.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Backend configuration or None
        """
        # Check local metadata first
        config = self.metadata_manager.get_backend_config(backend_id)
        if config:
            logger.info(f"Found backend config in metadata for {backend_id}")
            return config
        
        # If not in metadata, try to load from main library
        try:
            # This would call the main ipfs_kit_py library
            # For now, we'll return None to indicate not found
            logger.debug(f"Backend config not found in metadata for {backend_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error loading backend config for {backend_id}: {e}")
            return None
    
    def set_backend_config_metadata_first(self, backend_id: str, config: Dict[str, Any]) -> bool:
        """
        Set backend configuration in metadata first.
        
        Args:
            backend_id: Backend identifier
            config: Backend configuration
            
        Returns:
            True if successful
        """
        # Store in metadata first
        success = self.metadata_manager.set_backend_config(backend_id, config)
        
        if success:
            # Clear any cached data
            cache_keys_to_remove = [k for k in self._cache.keys() if backend_id in k]
            for key in cache_keys_to_remove:
                del self._cache[key]
                
            logger.info(f"Stored backend config in metadata for {backend_id}")
            
            # Optional: Also sync to main library
            try:
                # This would sync to the main ipfs_kit_py library
                pass
            except Exception as e:
                logger.warning(f"Failed to sync config to main library: {e}")
        
        return success
    
    def wrap_mcp_tool(self, tool_func: Callable, metadata_key: Optional[str] = None) -> Callable:
        """
        Wrap an existing MCP tool to check metadata first.
        
        Args:
            tool_func: The MCP tool function to wrap
            metadata_key: Key for metadata (defaults to function name)
            
        Returns:
            Wrapped function
        """
        key = metadata_key or tool_func.__name__
        
        @functools.wraps(tool_func)
        def wrapped(*args, **kwargs):
            # Check if this operation can be satisfied from metadata
            metadata_result = self._check_metadata_for_operation(key, *args, **kwargs)
            if metadata_result is not None:
                return metadata_result
            
            # Call original function
            try:
                result = tool_func(*args, **kwargs)
                
                # Store result in metadata
                self._store_operation_result(key, result, *args, **kwargs)
                
                return result
                
            except Exception as e:
                logger.error(f"Error in wrapped MCP tool {key}: {e}")
                # Try to get fallback from metadata
                fallback = self._get_fallback_from_metadata(key, *args, **kwargs)
                if fallback is not None:
                    logger.warning(f"Using fallback metadata for {key}")
                    return fallback
                raise
                
        return wrapped
    
    def _check_metadata_for_operation(self, operation: str, *args, **kwargs) -> Optional[Any]:
        """
        Check if an operation result is available in metadata.
        
        Args:
            operation: Operation name
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Cached result or None
        """
        # Create a unique key based on operation and arguments
        import hashlib
        arg_string = str(args) + str(sorted(kwargs.items()))
        arg_hash = hashlib.md5(arg_string.encode()).hexdigest()[:8]
        
        metadata_key = f"{operation}_result_{arg_hash}"
        
        result = self.metadata_manager.get_metadata(metadata_key)
        if result:
            # Check if result is still valid (not too old)
            import time
            result_age = time.time() - result.get('timestamp', 0)
            if result_age < 3600:  # 1 hour TTL
                logger.debug(f"Using cached metadata for {operation}")
                return result.get('data')
        
        return None
    
    def _store_operation_result(self, operation: str, result: Any, *args, **kwargs):
        """
        Store operation result in metadata.
        
        Args:
            operation: Operation name
            result: Operation result
            *args: Operation arguments
            **kwargs: Operation keyword arguments
        """
        import hashlib
        import time
        
        # Create unique key
        arg_string = str(args) + str(sorted(kwargs.items()))
        arg_hash = hashlib.md5(arg_string.encode()).hexdigest()[:8]
        
        metadata_key = f"{operation}_result_{arg_hash}"
        
        # Store with timestamp
        metadata_value = {
            'data': result,
            'timestamp': time.time(),
            'operation': operation,
            'args': args,
            'kwargs': kwargs
        }
        
        self.metadata_manager.set_metadata(metadata_key, metadata_value)
    
    def _get_fallback_from_metadata(self, operation: str, *args, **kwargs) -> Optional[Any]:
        """
        Get fallback result from metadata (even if stale).
        
        Args:
            operation: Operation name
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Fallback result or None
        """
        import hashlib
        
        arg_string = str(args) + str(sorted(kwargs.items()))
        arg_hash = hashlib.md5(arg_string.encode()).hexdigest()[:8]
        
        metadata_key = f"{operation}_result_{arg_hash}"
        
        result = self.metadata_manager.get_metadata(metadata_key)
        if result:
            logger.info(f"Using stale metadata fallback for {operation}")
            return result.get('data')
        
        return None


# Global instance
_metadata_first_mcp = None


def get_metadata_first_mcp() -> MetadataFirstMCP:
    """Get the global metadata-first MCP instance."""
    global _metadata_first_mcp
    if _metadata_first_mcp is None:
        _metadata_first_mcp = MetadataFirstMCP()
    return _metadata_first_mcp


# Convenience functions
def metadata_first_decorator(metadata_key: Optional[str] = None, cache_ttl: int = 300):
    """Convenience decorator for metadata-first operations."""
    return get_metadata_first_mcp().metadata_first(metadata_key, cache_ttl)


def wrap_mcp_tool(tool_func: Callable, metadata_key: Optional[str] = None) -> Callable:
    """Convenience function to wrap MCP tools."""
    return get_metadata_first_mcp().wrap_mcp_tool(tool_func, metadata_key)


# Example usage decorators for common MCP operations
@metadata_first_decorator('backend_list')
def list_backends():
    """Example: List backends with metadata-first approach."""
    # This would be implemented to call the actual MCP backend listing
    pass


@metadata_first_decorator('backend_status')
def get_backend_status(backend_id: str):
    """Example: Get backend status with metadata-first approach."""
    # This would be implemented to call the actual MCP backend status check
    pass
