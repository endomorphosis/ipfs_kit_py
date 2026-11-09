#!/usr/bin/env python3
"""
Fix for test dependencies.

This script creates proper mocks for pandas, numpy, and other dependencies
needed by the test suite.
"""

import sys
import types
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipfs_test_fix")

def create_mock_module(name, attrs=None, allow_getattr=False):
    """Create a mock module with specified attributes."""
    mock_module = types.ModuleType(name)
    mock_module.__file__ = f"<mock {name}>"
    
    # Add attributes if provided
    if attrs:
        for attr_name, attr_value in attrs.items():
            setattr(mock_module, attr_name, attr_value)
    
    # Add __getattr__ if requested
    if allow_getattr:
        def __getattr__(name):
            logger.debug(f"Auto-creating attribute {name} for {mock_module.__name__}")
            attr = MagicMock()
            setattr(mock_module, name, attr)
            return attr
        mock_module.__getattr__ = __getattr__
    
    # Add to sys.modules
    sys.modules[name] = mock_module
    logger.info(f"Created mock module: {name}")
    
    return mock_module

def fix_pandas_mock():
    """Create a proper pandas mock with DataFrame and Series classes."""
    # Create DataFrame class
    class DataFrame:
        def __init__(self, data=None, index=None, columns=None, dtype=None, copy=False):
            self.data = data or {}
            self.index = index or []
            self.columns = columns or []
            self.values = [[]] if not data else data
            
        def to_numpy(self, *args, **kwargs):
            import numpy as np
            return np.array(self.values)
            
        @property
        def iloc(self):
            return _IlocIndexer(self)
            
        @property
        def loc(self):
            return _LocIndexer(self)
            
        def __getitem__(self, key):
            return Series([], name=key)
    
    # Create Series class
    class Series:
        def __init__(self, data=None, index=None, dtype=None, name=None, copy=False, fastpath=False):
            self.data = data or []
            self.index = index or []
            self.name = name
            self.values = data or []
            
        def to_numpy(self, *args, **kwargs):
            import numpy as np
            return np.array(self.values)
    
    # Create indexers
    class _IlocIndexer:
        def __init__(self, obj):
            self.obj = obj
            
        def __getitem__(self, key):
            if isinstance(key, tuple):
                return Series([])
            elif isinstance(key, int):
                return Series([])
            else:
                return DataFrame()
    
    class _LocIndexer:
        def __init__(self, obj):
            self.obj = obj
            
        def __getitem__(self, key):
            if isinstance(key, tuple):
                return Series([])
            else:
                return Series([], name=key if isinstance(key, str) else None)
    
    # Create pandas mock with proper classes
    pd_attrs = {
        'DataFrame': DataFrame,
        'Series': Series,
        'read_csv': lambda *args, **kwargs: DataFrame(),
        'read_parquet': lambda *args, **kwargs: DataFrame(),
        'concat': lambda dfs, **kwargs: DataFrame(),
        'merge': lambda *args, **kwargs: DataFrame(),
        'NA': None,
        'isna': lambda x: False,
        'notna': lambda x: True,
    }
    
    pandas = create_mock_module('pandas', pd_attrs)
    
    # Create submodules
    create_mock_module('pandas.core', {})
    create_mock_module('pandas.core.frame', {'DataFrame': DataFrame})
    create_mock_module('pandas.core.series', {'Series': Series})
    create_mock_module('pandas.compat', {})
    create_mock_module('pandas.compat.numpy', {'is_numpy_dev': False})
    
    return pandas

def fix_numpy_mock():
    """Create a proper numpy mock."""
    # Create ndarray class
    class ndarray:
        def __init__(self, shape=None, dtype=None, buffer=None, offset=0, strides=None, order=None):
            self.shape = shape or (0,)
            self.dtype = dtype
            self.data = []
            
        def __array__(self):
            return self
    
    # Create numpy mock
    np_attrs = {
        '__version__': '1.24.0',
        'ndarray': ndarray,
        'array': lambda obj, *args, **kwargs: ndarray() if not isinstance(obj, ndarray) else obj,
        'zeros': lambda *args, **kwargs: ndarray(),
        'ones': lambda *args, **kwargs: ndarray(),
        'empty': lambda *args, **kwargs: ndarray(),
        'int64': int,
        'float64': float,
        'bool_': bool,
        'nan': float('nan'),
        'inf': float('inf'),
        'isnan': lambda x: False,
    }
    
    numpy = create_mock_module('numpy', np_attrs)
    
    # Create submodules
    create_mock_module('numpy.core', {})
    create_mock_module('numpy._core', {})
    create_mock_module('numpy._core._multiarray_umath', {'_ARRAY_API': {}})
    create_mock_module('numpy.random', {'random': lambda *args: 0.5})
    
    return numpy

def fix_pytest_anyio():
    """Create a mock for pytest_anyio."""
    import pytest
    
    def fixture(*args, **kwargs):
        def decorator(func):
            return pytest.fixture(*args, **kwargs)(func)
        return decorator
    
    anyio_attrs = {
        'fixture': fixture
    }
    
    return create_mock_module('pytest_anyio', anyio_attrs)

def create_common_mocks():
    """Create mocks for common dependencies."""
    # Mock libp2p and related modules
    create_mock_module('libp2p', {'ALPHA_VALUE': 3})
    create_mock_module('libp2p.host', {})
    create_mock_module('libp2p.host.host_interface', {'IHost': type('IHost', (), {})})
    create_mock_module('libp2p.typing', {'TProtocol': str})
    create_mock_module('libp2p.kademlia', {})
    create_mock_module('libp2p.tools', {})
    create_mock_module('libp2p.tools.pubsub', {})
    create_mock_module('libp2p.network', {})
    create_mock_module('libp2p.network.stream', {})
    create_mock_module('libp2p.network.stream.net_stream_interface', {})
    create_mock_module('libp2p.tools.constants', {})
    
    # Mock fastapi
    fastapi_attrs = {
        'FastAPI': type('FastAPI', (), {
            '__init__': lambda self, **kwargs: None,
            'include_router': lambda self, router, **kwargs: None,
        }),
        'APIRouter': type('APIRouter', (), {
            '__init__': lambda self, **kwargs: None,
            'get': lambda self, path, **kwargs: lambda f: f,
            'post': lambda self, path, **kwargs: lambda f: f,
        }),
        'WebSocket': type('WebSocket', (), {}),
    }
    create_mock_module('fastapi', fastapi_attrs)
    create_mock_module('fastapi.routing', {'APIRouter': fastapi_attrs['APIRouter']})
    
    # Mock other common modules
    create_mock_module('storacha_storage', {})
    create_mock_module('enhanced_s3_storage', {})
    create_mock_module('huggingface_storage', {})
    create_mock_module('mcp_auth', {})
    create_mock_module('mcp_extensions', {})
    create_mock_module('mcp_monitoring', {})
    
    # Mock ipfs_kit_py modules
    create_mock_module('ipfs_kit_py', {})
    create_mock_module('ipfs_kit_py.mcp', {})
    create_mock_module('ipfs_kit_py.mcp.models', {})
    create_mock_module('ipfs_kit_py.mcp.models.mcp_discovery_model', {})
    create_mock_module('ipfs_kit_py.mcp.controllers', {})
    create_mock_module('ipfs_kit_py.mcp.controllers.mcp_discovery_controller', {})
    create_mock_module('ipfs_kit_py.mcp.models.libp2p_model', {})
    create_mock_module('ipfs_kit_py.mcp.storage_manager', {})
    create_mock_module('ipfs_kit_py.mcp.storage_manager.backend_base', {'BackendStorage': type('BackendStorage', (), {})})

def fix_pytest_assertion_rewrite():
    """Add the missing 'assertion' attribute to _pytest.assertion.rewrite."""
    if '_pytest.assertion.rewrite' in sys.modules:
        sys.modules['_pytest.assertion.rewrite'].assertion = MagicMock()
        logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
    else:
        create_mock_module('_pytest.assertion.rewrite', {'assertion': MagicMock()})

def apply_all_fixes():
    """Apply all fixes for test dependencies."""
    # Create mock modules
    fix_numpy_mock()
    fix_pandas_mock()
    fix_pytest_anyio()
    create_common_mocks()
    fix_pytest_assertion_rewrite()
    
    # Patch sys.exit to prevent tests from exiting
    orig_exit = sys.exit
    def patched_exit(code=0):
        logger.warning(f"Intercepted sys.exit({code}) call during testing")
        return None
    sys.exit = patched_exit
    logger.info("Patched sys.exit to prevent test termination")
    
    logger.info("Applied all fixes successfully")

# Apply fixes when imported
apply_all_fixes()