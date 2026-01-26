#!/usr/bin/env python3
"""
Centralized Just-in-Time (JIT) Import Management System for IPFS-Kit

This module provides a centralized system for managing imports across the IPFS-Kit package,
enabling fast startup times by loading heavy dependencies only when needed.

Features:
- Lazy loading of heavy modules (pandas, numpy, duckdb, etc.)
- Feature detection with caching
- Smart dependency resolution
- Shared import state across CLI, MCP server, and daemon
- Performance monitoring and metrics
- Graceful fallbacks for missing dependencies

Usage:
    from ipfs_kit_py.jit_imports import JITImports
    
    jit = JITImports()
    
    # Check if feature is available (fast)
    if jit.is_available('enhanced_features'):
        # Load modules only when needed
        enhanced_pin_index = jit.import_module('enhanced_pin_index')
        bucket_index = jit.import_module('enhanced_bucket_index')
"""

import sys
import time
import threading
import importlib
from pathlib import Path
from typing import Dict, Any, Optional, Set, Callable, Union
from dataclasses import dataclass, field
from functools import wraps, lru_cache


@dataclass
class ImportMetrics:
    """Metrics for tracking import performance."""
    total_imports: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_import_time: float = 0.0
    feature_checks: int = 0
    feature_check_time: float = 0.0
    startup_time: float = 0.0


@dataclass 
class FeatureDefinition:
    """Definition of a feature and its dependencies."""
    name: str
    modules: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    check_function: Optional[Callable] = None
    lazy_load: bool = True
    priority: int = 1  # 1=low, 2=medium, 3=high
    description: str = ""


class JITImports:
    """Centralized Just-in-Time import management system."""
    
    def __init__(self, enable_metrics: bool = True):
        self.enable_metrics = enable_metrics
        self.metrics = ImportMetrics()
        self._lock = threading.RLock()
        self._cached_modules: Dict[str, Any] = {}
        self._cached_features: Dict[str, bool] = {}
        self._failed_imports: Set[str] = set()
        self._startup_time = time.time()
        
        # Define feature groups
        self._features = {
            'daemon': FeatureDefinition(
                name='daemon',
                modules=['ipfs_kit_daemon'],
                check_function=self._check_daemon_available,
                description="IPFS-Kit daemon components"
            ),
            'enhanced_features': FeatureDefinition(
                name='enhanced_features',
                modules=[
                    'ipfs_kit_py.enhanced_pin_index',
                    'ipfs_kit_py.enhanced_pin_cli',
                    'pyarrow',
                    'duckdb'
                ],
                pip_packages=['pyarrow', 'duckdb'],
                check_function=self._check_enhanced_features_available,
                description="Enhanced pin management with Parquet/DuckDB"
            ),
            'wal_system': FeatureDefinition(
                name='wal_system',
                modules=['ipfs_kit_py.pin_wal'],
                check_function=self._check_wal_available,
                description="Write-Ahead Log system for pin operations"
            ),
            'bucket_index': FeatureDefinition(
                name='bucket_index',
                modules=[
                    'ipfs_kit_py.enhanced_bucket_index',
                    'ipfs_kit_py.bucket_vfs_manager'
                ],
                check_function=self._check_bucket_index_available,
                description="Enhanced bucket discovery and indexing"
            ),
            'bucket_vfs': FeatureDefinition(
                name='bucket_vfs',
                modules=['ipfs_kit_py.bucket_vfs_manager'],
                check_function=self._check_bucket_vfs_available,
                description="Virtual filesystem management for buckets"
            ),
            'mcp_server': FeatureDefinition(
                name='mcp_server',
                modules=[
                    'fastapi',
                    'uvicorn',
                    'jinja2',
                    'mcp'
                ],
                pip_packages=['fastapi', 'uvicorn', 'jinja2', 'mcp'],
                check_function=self._check_mcp_server_available,
                description="Model Context Protocol server components"
            ),
            'multiprocessing_enhanced': FeatureDefinition(
                name='multiprocessing_enhanced',
                modules=[
                    'multiprocessing',
                    'concurrent.futures',
                    'async' 'io',
                    'threading'
                ],
                check_function=self._check_multiprocessing_enhanced_available,
                description="Enhanced multiprocessing capabilities"
            ),
            'analytics': FeatureDefinition(
                name='analytics',
                modules=[
                    'pandas',
                    'numpy',
                    'matplotlib',
                    'plotly'
                ],
                pip_packages=['pandas', 'numpy', 'matplotlib', 'plotly'],
                check_function=self._check_analytics_available,
                description="Data analytics and visualization"
            ),
            'networking': FeatureDefinition(
                name='networking',
                modules=[
                    'aiohttp',
                    'websockets',
                    'requests'
                ],
                pip_packages=['aiohttp', 'websockets', 'requests'],
                check_function=self._check_networking_available,
                description="Advanced networking capabilities"
            )
        }
        
        # Initialize startup metrics
        if self.enable_metrics:
            self.metrics.startup_time = time.time() - self._startup_time
    
    def is_available(self, feature_name: str) -> bool:
        """Check if a feature is available (cached for performance)."""
        if self.enable_metrics:
            start_time = time.time()
            self.metrics.feature_checks += 1
        
        try:
            # Check cache first
            if feature_name in self._cached_features:
                if self.enable_metrics:
                    self.metrics.cache_hits += 1
                return self._cached_features[feature_name]
            
            # Cache miss - perform check
            if self.enable_metrics:
                self.metrics.cache_misses += 1
            
            if feature_name not in self._features:
                self._cached_features[feature_name] = False
                return False
            
            feature = self._features[feature_name]
            
            # Use custom check function if available
            if feature.check_function:
                available = feature.check_function()
            else:
                # Default check - try importing modules
                available = self._check_modules_available(feature.modules)
            
            # Cache the result
            self._cached_features[feature_name] = available
            return available
            
        finally:
            if self.enable_metrics:
                self.metrics.feature_check_time += time.time() - start_time
    
    def import_module(self, module_name: str, 
                     lazy: bool = True, 
                     required: bool = False,
                     feature_group: Optional[str] = None) -> Optional[Any]:
        """Import a module with JIT loading and caching."""
        if self.enable_metrics:
            start_time = time.time()
            self.metrics.total_imports += 1
        
        try:
            # Check cache first
            if module_name in self._cached_modules:
                if self.enable_metrics:
                    self.metrics.cache_hits += 1
                return self._cached_modules[module_name]
            
            # Check if this module has previously failed
            if module_name in self._failed_imports and not required:
                return None
            
            # Cache miss - attempt import
            if self.enable_metrics:
                self.metrics.cache_misses += 1
            
            # Check feature group availability first
            if feature_group and not self.is_available(feature_group):
                return None
            
            try:
                module = importlib.import_module(module_name)
                
                # Cache successful import
                with self._lock:
                    self._cached_modules[module_name] = module
                
                return module
                
            except ImportError as e:
                # Mark as failed to avoid repeated attempts
                with self._lock:
                    self._failed_imports.add(module_name)
                
                if required:
                    raise ImportError(f"Required module '{module_name}' not available: {e}")
                
                return None
                
        finally:
            if self.enable_metrics:
                self.metrics.total_import_time += time.time() - start_time
    
    def import_from_module(self, module_name: str, 
                          item_name: str,
                          lazy: bool = True,
                          required: bool = False,
                          feature_group: Optional[str] = None) -> Optional[Any]:
        """Import a specific item from a module."""
        module = self.import_module(module_name, lazy=lazy, required=required, feature_group=feature_group)
        if module is None:
            return None
        
        try:
            return getattr(module, item_name)
        except AttributeError as e:
            if required:
                raise AttributeError(f"Required item '{item_name}' not found in module '{module_name}': {e}")
            return None
    
    def clear_cache(self, module_name: Optional[str] = None):
        """Clear import cache (for testing or development)."""
        with self._lock:
            if module_name:
                self._cached_modules.pop(module_name, None)
                self._cached_features.pop(module_name, None)
                self._failed_imports.discard(module_name)
            else:
                self._cached_modules.clear()
                self._cached_features.clear()
                self._failed_imports.clear()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get import performance metrics."""
        if not self.enable_metrics:
            return {"metrics_disabled": True}
        
        total_time = self.metrics.total_import_time + self.metrics.feature_check_time
        
        return {
            "startup_time": self.metrics.startup_time,
            "total_imports": self.metrics.total_imports,
            "cache_hits": self.metrics.cache_hits,
            "cache_misses": self.metrics.cache_misses,
            "cache_hit_ratio": self.metrics.cache_hits / max(1, self.metrics.cache_hits + self.metrics.cache_misses),
            "total_import_time": self.metrics.total_import_time,
            "feature_checks": self.metrics.feature_checks,
            "feature_check_time": self.metrics.feature_check_time,
            "total_time": total_time,
            "cached_modules": len(self._cached_modules),
            "cached_features": len(self._cached_features),
            "failed_imports": len(self._failed_imports),
            "available_features": [name for name, available in self._cached_features.items() if available]
        }
    
    def get_feature_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all defined features."""
        status = {}
        for name, feature in self._features.items():
            status[name] = {
                "available": self.is_available(name),
                "description": feature.description,
                "modules": feature.modules,
                "pip_packages": feature.pip_packages,
                "priority": feature.priority,
                "lazy_load": feature.lazy_load
            }
        return status
    
    def preload_features(self, features: list[str], background: bool = False):
        """Preload specific features (useful for warming up cache)."""
        def _preload():
            for feature in features:
                if feature in self._features:
                    feature_def = self._features[feature]
                    for module in feature_def.modules:
                        self.import_module(module, lazy=False)
        
        if background:
            import threading
            thread = threading.Thread(target=_preload, daemon=True)
            thread.start()
        else:
            _preload()
    
    # Feature check implementations
    
    def _check_daemon_available(self) -> bool:
        """Check if daemon components are available by checking program state."""
        try:
            # First try to check if daemon is running via standalone program state
            import sys
            import os
            standalone_path = os.path.dirname(os.path.dirname(__file__))
            if standalone_path not in sys.path:
                sys.path.insert(0, standalone_path)
            from standalone_program_state import StandaloneFastStateReader
            
            reader = StandaloneFastStateReader()
            summary = reader.get_summary()
            # If we can read state and cluster_status is running, daemon is available
            return summary.get('cluster_status') == 'running'
        except (ImportError, FileNotFoundError, Exception):
            # Fallback to original method if standalone state is not available
            try:
                # Try the package-internal program state
                from .program_state import FastStateReader
                reader = FastStateReader()
                summary = reader.get_summary()
                return summary.get('cluster_status') == 'running'
            except (ImportError, FileNotFoundError, Exception):
                # Final fallback to original import-based check
                try:
                    import ipfs_kit_daemon
                    return True
                except ImportError:
                    return False
    
    def _check_enhanced_features_available(self) -> bool:
        """Check if enhanced features are available."""
        required_modules = [
            'ipfs_kit_py.enhanced_pin_index',
            'ipfs_kit_py.enhanced_pin_cli'
        ]
        
        # Check core modules
        if not self._check_modules_available(required_modules):
            return False
        
        # Check optional dependencies
        try:
            import pyarrow
            import duckdb
            return True
        except ImportError:
            return False
    
    def _check_wal_available(self) -> bool:
        """Check if WAL system is available."""
        return self._check_modules_available(['ipfs_kit_py.pin_wal'])
    
    def _check_bucket_index_available(self) -> bool:
        """Check if bucket index system is available."""
        required_modules = [
            'ipfs_kit_py.enhanced_bucket_index'
        ]
        return self._check_modules_available(required_modules)
    
    def _check_bucket_vfs_available(self) -> bool:
        """Check if bucket VFS system is available."""
        return self._check_modules_available(['ipfs_kit_py.bucket_vfs_manager'])
    
    def _check_mcp_server_available(self) -> bool:
        """Check if MCP server components are available."""
        required_modules = ['fastapi', 'uvicorn']
        return self._check_modules_available(required_modules)
    
    def _check_multiprocessing_enhanced_available(self) -> bool:
        """Check if enhanced multiprocessing is available."""
        try:
            import multiprocessing
            import concurrent.futures
            import anyio
            import threading
            return True
        except ImportError:
            return False
    
    def _check_analytics_available(self) -> bool:
        """Check if analytics components are available."""
        optional_modules = ['pandas', 'numpy', 'matplotlib', 'plotly']
        # At least one analytics module should be available
        return any(self._check_modules_available([module]) for module in optional_modules)
    
    def _check_networking_available(self) -> bool:
        """Check if networking components are available."""
        optional_modules = ['aiohttp', 'websockets', 'requests']
        # At least one networking module should be available
        return any(self._check_modules_available([module]) for module in optional_modules)
    
    def _check_modules_available(self, modules: list[str]) -> bool:
        """Check if a list of modules are available."""
        for module in modules:
            try:
                importlib.import_module(module)
            except ImportError:
                return False
        return True


# Global JIT imports instance
_global_jit_imports = None
_jit_lock = threading.Lock()


def get_jit_imports(enable_metrics: bool = True) -> JITImports:
    """Get or create the global JIT imports instance."""
    global _global_jit_imports
    
    if _global_jit_imports is None:
        with _jit_lock:
            if _global_jit_imports is None:
                _global_jit_imports = JITImports(enable_metrics=enable_metrics)
    
    return _global_jit_imports


def jit_import(module_name: str, 
               lazy: bool = True,
               required: bool = False,
               feature_group: Optional[str] = None) -> Optional[Any]:
    """Convenience function for JIT importing."""
    jit = get_jit_imports()
    return jit.import_module(module_name, lazy=lazy, required=required, feature_group=feature_group)


def jit_import_from(module_name: str, 
                   item_name: str,
                   lazy: bool = True,
                   required: bool = False,
                   feature_group: Optional[str] = None) -> Optional[Any]:
    """Convenience function for JIT importing specific items."""
    jit = get_jit_imports()
    return jit.import_from_module(module_name, item_name, lazy=lazy, required=required, feature_group=feature_group)


def is_feature_available(feature_name: str) -> bool:
    """Convenience function for checking feature availability."""
    jit = get_jit_imports()
    return jit.is_available(feature_name)


def lazy_import(feature_group: str):
    """Decorator for lazy importing within a function."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            jit = get_jit_imports()
            if not jit.is_available(feature_group):
                raise ImportError(f"Feature group '{feature_group}' not available")
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Compatibility layer for existing code
def check_daemon_available() -> bool:
    """Legacy compatibility function."""
    return is_feature_available('daemon')


def check_enhanced_features_available() -> bool:
    """Legacy compatibility function."""
    return is_feature_available('enhanced_features')


def check_wal_available() -> bool:
    """Legacy compatibility function.""" 
    return is_feature_available('wal_system')


def check_bucket_index_available() -> bool:
    """Legacy compatibility function."""
    return is_feature_available('bucket_index')


def check_bucket_vfs_available() -> bool:
    """Legacy compatibility function."""
    return is_feature_available('bucket_vfs')


def check_mcp_server_available() -> bool:
    """Legacy compatibility function."""
    return is_feature_available('mcp_server')


if __name__ == "__main__":
    """Test and demonstration of JIT imports."""
    import json
    
    print("🚀 IPFS-Kit JIT Import System Test")
    print("=" * 50)
    
    jit = get_jit_imports()
    
    # Test feature availability
    print("\n📋 Feature Availability:")
    features = jit.get_feature_status()
    for name, status in features.items():
        available = "✅" if status["available"] else "❌"
        print(f"{available} {name}: {status['description']}")
    
    # Test module importing
    print("\n🔄 Testing Module Imports:")
    
    test_imports = [
        ('sys', True, None),
        ('os', True, None),
        ('ipfs_kit_daemon', False, 'daemon'),
        ('ipfs_kit_py.enhanced_pin_index', False, 'enhanced_features'),
        ('fastapi', False, 'mcp_server'),
        ('pandas', False, 'analytics'),
        ('nonexistent_module', False, None)
    ]
    
    for module, required, feature in test_imports:
        try:
            result = jit.import_module(module, required=required, feature_group=feature)
            status = "✅" if result else "❌"
            print(f"{status} {module}")
        except Exception as e:
            print(f"❌ {module}: {e}")
    
    # Show metrics
    print("\n📊 Performance Metrics:")
    metrics = jit.get_metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")
    
    print("\n✅ JIT Import System Test Complete")
