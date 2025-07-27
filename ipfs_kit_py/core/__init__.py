#!/usr/bin/env python3
"""
IPFS-Kit Core Module with Integrated JIT Import Management

This core module provides the foundational import management system for the entire
ipfs_kit_py package, enabling fast startup times and lazy loading of heavy dependencies.

The JIT (Just-in-Time) import system is integrated at the package core level to:
- Minimize startup time by deferring heavy imports
- Provide consistent import patterns across CLI, MCP server, and daemon
- Enable graceful fallbacks for missing dependencies
- Monitor import performance and provide metrics

Usage:
    # Import the core JIT system
    from ipfs_kit_py.core import jit_manager
    
    # Check feature availability (fast)
    if jit_manager.is_available('enhanced_features'):
        # Load modules only when needed
        enhanced_index = jit_manager.get_module('enhanced_pin_index')
    
    # Use decorators for automatic JIT loading
    from ipfs_kit_py.core import lazy_import
    
    @lazy_import('enhanced_features')
    def get_enhanced_pin_manager():
        from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
        return get_global_enhanced_pin_index()
"""

import sys
import time
import logging
from typing import Dict, Any, Optional, Union, Callable
from functools import wraps

# Configure logger for core module
logger = logging.getLogger(__name__)

# Import the centralized JIT system
_JIT_AVAILABLE = False
_jit_instance = None

def _initialize_jit():
    """Initialize JIT system with lazy loading to avoid circular imports."""
    global _JIT_AVAILABLE, _jit_instance
    
    if _jit_instance is not None:
        return _jit_instance
    
    try:
        # Import directly from the file to avoid triggering main package import
        import sys
        from pathlib import Path
        import importlib.util
        
        # Get the jit_imports module path relative to this file
        core_dir = Path(__file__).parent
        jit_imports_path = core_dir.parent / 'jit_imports.py'
        
        # Use importlib to load the module directly
        spec = importlib.util.spec_from_file_location("jit_imports", jit_imports_path)
        if spec is None or spec.loader is None:
            raise ImportError("Could not create spec for jit_imports")
            
        jit_imports_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(jit_imports_module)
        
        _jit_instance = jit_imports_module.get_jit_imports()
        _JIT_AVAILABLE = True
        logger.debug("JIT imports loaded successfully via lazy initialization")
        return _jit_instance
    except Exception as e:
        logger.warning(f"JIT imports not available: {e}")
        _JIT_AVAILABLE = False
        return None


class CoreJITManager:
    """
    Core JIT manager that integrates deeply with the package infrastructure.
    
    This manager provides the primary interface for all JIT operations throughout
    the ipfs_kit_py package, ensuring consistent performance and behavior.
    """
    
    def __init__(self):
        self._start_time = time.time()
        self._jit_instance = None
        self._initialization_complete = False
        self._cached_modules: Dict[str, Any] = {}
        
        # Initialize JIT system if available
        self._jit_instance = _initialize_jit()
        self._initialization_complete = True
        
        # Log initialization metrics
        init_time = time.time() - self._start_time
        logger.debug(f"Core JIT manager initialization took {init_time:.3f}s")
    
    @property
    def is_available(self) -> bool:
        """Check if JIT system is available and functional."""
        return _JIT_AVAILABLE and self._jit_instance is not None
    
    @property
    def available_features(self) -> Dict[str, bool]:
        """Get a dictionary of all available features and their status."""
        if not self.is_available or self._jit_instance is None:
            return {}
        
        try:
            # Get available features from the underlying JIT system using get_feature_status
            if hasattr(self._jit_instance, 'get_feature_status'):
                feature_status = self._jit_instance.get_feature_status()
                return {name: status['available'] for name, status in feature_status.items()}
            else:
                # Fallback: test common features manually
                common_features = [
                    'enhanced_features', 'transformers', 'torch', 'faiss',
                    'datasets', 'duckdb', 'protobuf', 'libp2p', 'lotus',
                    'webrtc', 'av', 'cv2', 'numpy'
                ]
                return {
                    feature: self.check_feature(feature) 
                    for feature in common_features
                }
        except Exception as e:
            logger.warning(f"Failed to get available features: {e}")
            return {}
    
    def check_feature(self, feature_name: str) -> bool:
        """
        Check if a feature is available with core-level caching.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if feature is available, False otherwise
        """
        if not self.is_available or self._jit_instance is None:
            return False
        
        try:
            return self._jit_instance.is_available(feature_name)
        except Exception as e:
            logger.warning(f"Feature check failed for {feature_name}: {e}")
            return False
    
    def get_module(self, module_name: str, fallback: Any = None) -> Any:
        """
        Get a module using JIT loading with core-level caching.
        
        Args:
            module_name: Name of the module to import
            fallback: Fallback value if import fails
            
        Returns:
            Imported module or fallback value
        """
        # Check local cache first
        if module_name in self._cached_modules:
            return self._cached_modules[module_name]
        
        if not self.is_available or self._jit_instance is None:
            logger.warning(f"JIT system not available, cannot load {module_name}")
            return fallback
        
        try:
            module = self._jit_instance.import_module(module_name)
            # Cache successful imports
            if module is not None:
                self._cached_modules[module_name] = module
                return module
            else:
                return fallback
        except Exception as e:
            logger.warning(f"Failed to load module {module_name}: {e}")
            return fallback
    
    def get_import_metrics(self) -> Dict[str, Any]:
        """Get comprehensive import metrics from the JIT system."""
        if not self.is_available or self._jit_instance is None:
            return {
                "jit_available": False,
                "core_init_time": time.time() - self._start_time,
                "cached_modules": len(self._cached_modules)
            }
        
        try:
            jit_metrics = self._jit_instance.get_metrics()
            return {
                "jit_available": True,
                "core_init_time": time.time() - self._start_time,
                "cached_modules": len(self._cached_modules),
                "jit_metrics": jit_metrics
            }
        except Exception as e:
            logger.warning(f"Failed to get JIT metrics: {e}")
            return {"error": str(e)}
    
    def preload_features(self, feature_names: list[str]) -> Dict[str, bool]:
        """
        Preload specified features for better performance.
        
        Args:
            feature_names: List of feature names to preload
            
        Returns:
            Dictionary mapping feature names to success status
        """
        results = {}
        
        for feature_name in feature_names:
            try:
                available = self.check_feature(feature_name)
                results[feature_name] = available
                
                if available:
                    logger.debug(f"Feature {feature_name} preloaded successfully")
                else:
                    logger.debug(f"Feature {feature_name} not available")
                    
            except Exception as e:
                logger.warning(f"Failed to preload feature {feature_name}: {e}")
                results[feature_name] = False
        
        return results
    
    def reset_cache(self):
        """Reset all cached modules and force re-import on next access."""
        self._cached_modules.clear()
        if self.is_available and self._jit_instance is not None:
            try:
                self._jit_instance.clear_cache()
                logger.debug("JIT cache cleared successfully")
            except Exception as e:
                logger.warning(f"Failed to clear JIT cache: {e}")


# Global core JIT manager instance
jit_manager = CoreJITManager()


def require_feature(feature_name: str, error_message: Optional[str] = None):
    """
    Decorator that ensures a feature is available before executing a function.
    
    Args:
        feature_name: Name of the required feature
        error_message: Custom error message if feature is not available
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not jit_manager.check_feature(feature_name):
                if error_message:
                    raise ImportError(error_message)
                else:
                    raise ImportError(f"Required feature '{feature_name}' is not available")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def optional_feature(feature_name: str, fallback_result: Any = None):
    """
    Decorator that gracefully handles missing features by returning a fallback.
    
    Args:
        feature_name: Name of the optional feature
        fallback_result: Value to return if feature is not available
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not jit_manager.check_feature(feature_name):
                logger.debug(f"Optional feature '{feature_name}' not available, using fallback")
                return fallback_result
            return func(*args, **kwargs)
        return wrapper
    return decorator


def core_lazy_import(module_name: str, feature_name: Optional[str] = None):
    """
    Core-level lazy import decorator that defers module loading until first use.
    
    Args:
        module_name: Name of the module to import
        feature_name: Optional feature name to check before importing
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check feature if specified
            if feature_name and not jit_manager.check_feature(feature_name):
                raise ImportError(f"Feature '{feature_name}' required for {module_name} is not available")
            
            # Get module using JIT system
            module = jit_manager.get_module(module_name)
            if module is None:
                raise ImportError(f"Failed to import {module_name}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Core-level convenience functions that wrap the JIT system
def jit_import(module_name: str, fallback: Any = None) -> Any:
    """
    Core JIT import function with simplified interface.
    
    Args:
        module_name: Name of the module to import
        fallback: Fallback value if import fails
        
    Returns:
        Imported module or fallback value
    """
    jit_instance = _initialize_jit()
    if jit_instance is not None:
        try:
            result = jit_instance.import_module(module_name)
            return result if result is not None else fallback
        except Exception:
            # Fallback if JIT import fails
            pass
    
    # Standard import fallback
    try:
        return __import__(module_name)
    except ImportError:
        return fallback


def jit_import_from(module_name: str, attr_name: str, fallback: Any = None) -> Any:
    """
    Core JIT import from function with simplified interface.
    
    Args:
        module_name: Name of the module to import from
        attr_name: Name of the attribute to import
        fallback: Fallback value if import fails
        
    Returns:
        Imported attribute or fallback value
    """
    jit_instance = _initialize_jit()
    if jit_instance is not None:
        try:
            module = jit_instance.import_module(module_name)
            if module is not None and hasattr(module, attr_name):
                return getattr(module, attr_name)
            else:
                return fallback
        except Exception:
            # Fallback if JIT import fails
            pass
    
    # Standard import fallback
    try:
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name, fallback)
    except (ImportError, AttributeError):
        return fallback


def lazy_import(feature_name: str):
    """
    Core lazy import decorator.
    
    Args:
        feature_name: Name of the feature to check
    """
    jit_instance = _initialize_jit()
    if jit_instance is not None:
        try:
            # Check if feature is available
            if jit_instance.is_available(feature_name):
                def available_decorator(func):
                    return func  # Feature available, return function as-is
                return available_decorator
            else:
                # Feature not available, return a wrapper that returns None
                def unavailable_decorator(func):
                    def wrapper(*args, **kwargs):
                        return None
                    return wrapper
                return unavailable_decorator
        except Exception:
            # Fallback if feature check fails
            pass
    
    # Mock implementation - just return the function as-is
    def fallback_decorator(func):
        return func
    return fallback_decorator


def get_jit_imports():
    """Get the JIT imports instance."""
    if _JIT_AVAILABLE:
        try:
            return get_jit_imports()
        except Exception:
            pass
    return None


# Re-export JIT functions for backward compatibility
if _JIT_AVAILABLE:
    # Export the original JIT functions plus core functions
    __all__ = [
        'jit_manager',
        'require_feature', 
        'optional_feature',
        'core_lazy_import',
        'jit_import',
        'jit_import_from', 
        'lazy_import',
        'get_jit_imports'
    ]
else:
    # Provide mock implementations for missing JIT system
    __all__ = [
        'jit_manager',
        'require_feature',
        'optional_feature', 
        'core_lazy_import',
        'jit_import',
        'jit_import_from',
        'lazy_import'
    ]


# Initialize core features on module load
logger.debug("IPFS-Kit core module with JIT integration loaded")
