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