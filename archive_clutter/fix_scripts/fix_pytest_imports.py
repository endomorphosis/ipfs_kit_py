#!/usr/bin/env python3
"""
Fix import issues in pytest environment.

This script provides fixes for common pytest import issues,
particularly around module attributes for mocked modules.
"""

import sys
import types
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_pytest_imports")

# Patch _pytest.assertion.rewrite to add missing attributes
try:
    from _pytest.assertion import rewrite
    if not hasattr(rewrite, "assertion"):
        rewrite.assertion = MagicMock()
        logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
except ImportError:
    logger.warning("Could not import _pytest.assertion.rewrite")

# Fix numpy mock
def fix_numpy_mock():
    """Fix the numpy mock module to include version and other required attributes."""
    if 'numpy' in sys.modules:
        numpy = sys.modules['numpy']
        if not hasattr(numpy, '__version__'):
            numpy.__version__ = '1.24.0'  # Set a reasonable version
            logger.info("Added missing '__version__' attribute to numpy mock")
        
        # Add other commonly needed numpy attributes
        for attr_name, value in {
            "_core": types.ModuleType("numpy._core"),
            "ndarray": type('ndarray', (), {"__init__": lambda self, *args, **kwargs: None}),
            "dtype": type('dtype', (), {"__init__": lambda self, *args, **kwargs: None}),
            "float32": type('float32', (), {}),
            "float64": type('float64', (), {}),
            "int32": type('int32', (), {}),
            "int64": type('int64', (), {}),
            "bool_": type('bool_', (), {}),
            "array": lambda *args, **kwargs: MagicMock(),
            "zeros": lambda *args, **kwargs: MagicMock(),
            "ones": lambda *args, **kwargs: MagicMock(),
            "uint8": type('uint8', (), {}),
            "uint16": type('uint16', (), {}),
            "uint32": type('uint32', (), {}),
            "uint64": type('uint64', (), {})
        }.items():
            if not hasattr(numpy, attr_name):
                setattr(numpy, attr_name, value)
                
        # Add _core._multiarray_umath
        if hasattr(numpy, "_core") and not hasattr(numpy._core, "_multiarray_umath"):
            numpy._core._multiarray_umath = types.ModuleType("numpy._core._multiarray_umath")
            numpy._core._multiarray_umath.ndarray = numpy.ndarray

    return True

# Apply fixes
logger.info("Applying pytest import fixes...")
fix_numpy_mock()
logger.info("Successfully applied pytest import fixes")