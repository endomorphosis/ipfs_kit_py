#!/usr/bin/env python3
"""
Comprehensive mock system for test dependencies.

This module creates mock implementations of external dependencies
to enable tests to run without the actual packages installed.
"""

import sys
import types
import logging
import json
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_dependencies")

# Dictionary to store mock modules
MOCK_MODULES = {}

def create_pandas_mock():
    """Create comprehensive pandas mock with DataFrame and Series classes."""
    pandas_module = types.ModuleType("pandas")
    pandas_module.__version__ = "2.0.0"
    
    # Create DataFrame class
    class DataFrame:
        def __init__(self, data=None, index=None, columns=None):
            self.data = data or {}
            self.index = index or []
            self.columns = columns or []
            self.shape = (len(self.index) if self.index else 0, len(self.columns) if self.columns else 0)
            self.iloc = MagicMock()
            self.loc = MagicMock()
        
        def to_numpy(self, *args, **kwargs):
            return []
            
        def __getitem__(self, key):
            return MagicMock()
    
    # Create Series class
    class Series:
        def __init__(self, data=None, index=None, name=None):
            self.data = data or []
            self.index = index or []
            self.name = name
            self.shape = (len(self.index) if self.index else 0,)
            self.iloc = MagicMock()
        
        def to_numpy(self, *args, **kwargs):
            return []
            
        def __getitem__(self, key):
            return MagicMock()
    
    # Add classes to module
    pandas_module.DataFrame = DataFrame
    pandas_module.Series = Series
    
    # Create core modules
    pandas_module.core = types.ModuleType("pandas.core")
    pandas_module.core.frame = types.ModuleType("pandas.core.frame")
    pandas_module.core.frame.DataFrame = DataFrame
    pandas_module.core.series = types.ModuleType("pandas.core.series")
    pandas_module.core.series.Series = Series
    
    # Create compat module
    pandas_module.compat = types.ModuleType("pandas.compat")
    pandas_module.compat.numpy = types.ModuleType("pandas.compat.numpy")
    pandas_module.compat.numpy.is_numpy_dev = False
    
    # Add to sys.modules
    sys.modules["pandas"] = pandas_module
    sys.modules["pandas.core"] = pandas_module.core
    sys.modules["pandas.core.frame"] = pandas_module.core.frame
    sys.modules["pandas.core.series"] = pandas_module.core.series
    sys.modules["pandas.compat"] = pandas_module.compat
    sys.modules["pandas.compat.numpy"] = pandas_module.compat.numpy
    
    logger.info("Created comprehensive pandas mock with DataFrame and Series classes")
    return pandas_module

def create_numpy_mock():
    """Create comprehensive numpy mock with ndarray and dtype classes."""
    numpy_module = types.ModuleType("numpy")
    numpy_module.__version__ = "1.24.0"
    
    # Create ndarray class
    class ndarray:
        def __init__(self, shape=None, dtype=None, buffer=None, offset=0, strides=None, order=None):
            self.shape = shape or (0,)
            self.dtype = dtype
            self.size = 0
            self.ndim = len(self.shape)
        
        def __array__(self, dtype=None):
            return self
            
        def __getitem__(self, key):
            return self
    
    # Create dtype class
    class dtype:
        def __init__(self, obj, align=False, copy=False):
            self.name = str(obj)
            self.kind = 'i'
            self.itemsize = 4
    
    # Add classes and functions to module
    numpy_module.ndarray = ndarray
    numpy_module.dtype = dtype
    numpy_module.float32 = dtype('float32')
    numpy_module.float64 = dtype('float64')
    numpy_module.int32 = dtype('int32')
    numpy_module.int64 = dtype('int64')
    numpy_module.uint8 = dtype('uint8')
    numpy_module.uint16 = dtype('uint16')
    numpy_module.uint32 = dtype('uint32')
    numpy_module.uint64 = dtype('uint64')
    numpy_module.bool_ = dtype('bool')
    
    # Add functions
    numpy_module.array = lambda *args, **kwargs: ndarray()
    numpy_module.zeros = lambda *args, **kwargs: ndarray()
    numpy_module.ones = lambda *args, **kwargs: ndarray()
    numpy_module.empty = lambda *args, **kwargs: ndarray()
    numpy_module.asarray = lambda *args, **kwargs: ndarray()
    
    # Add core modules
    numpy_module.core = types.ModuleType("numpy.core")
    numpy_module._core = types.ModuleType("numpy._core")
    numpy_module._core._multiarray_umath = types.ModuleType("numpy._core._multiarray_umath")
    numpy_module._core._multiarray_umath.__cpu_features__ = {}
    numpy_module._core._multiarray_umath._ARRAY_API = MagicMock()
    
    # Add random module
    numpy_module.random = types.ModuleType("numpy.random")
    numpy_module.random.default_rng = lambda seed=None: MagicMock()
    
    # Register in sys.modules
    sys.modules["numpy"] = numpy_module
    sys.modules["numpy.core"] = numpy_module.core
    sys.modules["numpy._core"] = numpy_module._core
    sys.modules["numpy._core._multiarray_umath"] = numpy_module._core._multiarray_umath
    sys.modules["numpy.random"] = numpy_module.random
    
    logger.info("Created comprehensive numpy mock with ndarray and dtype classes")
    return numpy_module

def create_pyarrow_mock():
    """Create comprehensive pyarrow mock with Schema and Table classes."""
    pa_module = types.ModuleType("pyarrow")
    pa_module.__version__ = "14.0.0"
    
    # Create Field class
    class Field:
        def __init__(self, name, type, nullable=True, metadata=None):
            self.name = name
            self.type = type
            self.nullable = nullable
            self.metadata = metadata or {}
    
    # Create Schema class
    class Schema:
        def __init__(self, fields=None):
            self.fields = fields or []
            
        def get_field_index(self, name):
            for i, field in enumerate(self.fields):
                if field.name == name:
                    return i
            raise KeyError(f"Field '{name}' not found")
            
        def __getitem__(self, index):
            if isinstance(index, int):
                return self.fields[index]
            elif isinstance(index, str):
                for field in self.fields:
                    if field.name == index:
                        return field
            raise KeyError(f"Field '{index}' not found")
            
        def equals(self, other):
            if not isinstance(other, Schema):
                return False
            if len(self.fields) != len(other.fields):
                return False
            return True
    
    # Create Table class
    class Table:
        def __init__(self, data=None, schema=None):
            self.data = data or {}
            self.schema = schema or Schema()
            self.num_rows = 0
            self.num_columns = len(self.schema.fields) if self.schema else 0
            
        def column(self, index_or_name):
            if isinstance(index_or_name, int):
                # Get by index
                field_name = self.schema.fields[index_or_name].name
                return self.data.get(field_name, [])
            else:
                # Get by name
                return self.data.get(index_or_name, [])
                
        @classmethod
        def from_arrays(cls, arrays, schema=None, names=None, metadata=None):
            if schema is None and names is not None:
                # Create schema from names
                fields = [Field(name, MagicMock()) for name in names]
                schema = Schema(fields)
            return cls(data={}, schema=schema)
            
        def to_pandas(self, *args, **kwargs):
            # Create a pandas DataFrame
            import pandas as pd
            return pd.DataFrame()
    
    # Add types
    pa_module.string = lambda: "string"
    pa_module.int32 = lambda: "int32"
    pa_module.int64 = lambda: "int64"
    pa_module.float32 = lambda: "float32"
    pa_module.float64 = lambda: "float64"
    pa_module.bool_ = lambda: "bool"
    pa_module.list_ = lambda t: f"list<{t}>"
    pa_module.struct = lambda fields: f"struct<{','.join(fields)}>"
    pa_module.timestamp = lambda unit="ms": f"timestamp[{unit}]"
    pa_module.null = lambda: "null"
    
    # Add classes
    pa_module.Field = Field
    pa_module.Schema = Schema
    pa_module.Table = Table
    pa_module.field = Field
    pa_module.schema = Schema
    
    # Create lib module
    pa_module.lib = types.ModuleType("pyarrow.lib")
    pa_module.lib.ArrowException = Exception
    
    # Register in sys.modules
    sys.modules["pyarrow"] = pa_module
    sys.modules["pyarrow.lib"] = pa_module.lib
    
    logger.info("Created comprehensive pyarrow mock with Schema and Table classes")
    return pa_module

def patch_sys_exit():
    """Patch sys.exit to prevent it from terminating tests."""
    original_exit = sys.exit
    
    def mock_exit(code=0):
        logger.info(f"Intercepted sys.exit({code}) call")
        return None
    
    sys.exit = mock_exit
    logger.info("Patched sys.exit to prevent termination during tests")
    return True

# Apply all patches
create_pandas_mock()
create_numpy_mock()
create_pyarrow_mock()
patch_sys_exit()
logger.info("Test environment setup complete")