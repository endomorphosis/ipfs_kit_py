#!/usr/bin/env python3
"""
Standalone JIT Import System for IPFS-Kit CLI

A lightweight, standalone version of the JIT import system that doesn't
require importing the heavy ipfs_kit package for fast operations.
"""

import sys
import time
import threading
import importlib
from typing import Dict, Any, Optional, Set
from functools import lru_cache


class StandaloneJIT:
    """Standalone JIT import system for CLI."""
    
    def __init__(self):
        self._cached_modules: Dict[str, Any] = {}
        self._cached_features: Dict[str, bool] = {}
        self._failed_imports: Set[str] = set()
        self._lock = threading.RLock()
        self.startup_time = time.time()
    
    @lru_cache(maxsize=128)
    def is_available(self, feature_name: str) -> bool:
        """Check if a feature is available (cached)."""
        if feature_name == 'daemon':
            return self._check_module_available('ipfs_kit_daemon')
        elif feature_name == 'enhanced_features':
            return (self._check_module_available('ipfs_kit_py.enhanced_pin_index') and 
                   self._check_module_available('pyarrow') and 
                   self._check_module_available('duckdb'))
        elif feature_name == 'wal_system':
            return self._check_module_available('ipfs_kit_py.pin_wal')
        elif feature_name == 'bucket_index':
            return self._check_module_available('ipfs_kit_py.enhanced_bucket_index')
        elif feature_name == 'bucket_vfs':
            return self._check_module_available('ipfs_kit_py.bucket_vfs_manager')
        elif feature_name == 'mcp_server':
            return (self._check_module_available('fastapi') and 
                   self._check_module_available('uvicorn'))
        else:
            return False
    
    def import_module(self, module_name: str) -> Optional[Any]:
        """Import a module with caching."""
        if module_name in self._cached_modules:
            return self._cached_modules[module_name]
        
        if module_name in self._failed_imports:
            return None
        
        try:
            module = importlib.import_module(module_name)
            with self._lock:
                self._cached_modules[module_name] = module
            return module
        except ImportError:
            with self._lock:
                self._failed_imports.add(module_name)
            return None
    
    def import_from_module(self, module_name: str, item_name: str) -> Optional[Any]:
        """Import specific item from a module."""
        module = self.import_module(module_name)
        if module is None:
            return None
        
        try:
            return getattr(module, item_name)
        except AttributeError:
            return None
    
    def _check_module_available(self, module_name: str) -> bool:
        """Check if a module is available."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "startup_time": time.time() - self.startup_time,
            "cached_modules": len(self._cached_modules),
            "failed_imports": len(self._failed_imports),
            "cache_size": len(self._cached_modules) + len(self._cached_features)
        }


# Global instance
_standalone_jit = None


def get_standalone_jit() -> StandaloneJIT:
    """Get the global standalone JIT instance."""
    global _standalone_jit
    if _standalone_jit is None:
        _standalone_jit = StandaloneJIT()
    return _standalone_jit
