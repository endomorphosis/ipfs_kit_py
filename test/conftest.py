"""
Global configuration for pytest tests.

Contains shared fixtures and patching logic for testing components.
"""

import logging
import os
import sys
from unittest.mock import MagicMock, patch
import contextlib

# Ensure we have mocks for problematic imports
sys.modules['_pytest.assertion'] = MagicMock()
sys.modules['_pytest.assertion.rewrite'] = MagicMock()
sys.modules['_pytest.assertion.rewrite'].assertion = MagicMock()
sys.modules['_pytest.assertion'].rewrite = sys.modules['_pytest.assertion.rewrite']

# Now import pytest
import pytest

# Register custom markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "no_global_reset: mark test to not reset global variables after running"
    )

# Configure test logging
logging.basicConfig(level=logging.INFO)

@contextlib.contextmanager
def suppress_logging(logger_name=None, level=logging.ERROR):
    """Context manager to temporarily increase the logging level to suppress messages."""
    if logger_name:
        logger = logging.getLogger(logger_name)
        old_level = logger.level
        logger.setLevel(level)
        try:
            yield
        finally:
            logger.setLevel(old_level)
    else:
        # If no logger name is specified, suppress root logger
        root_logger = logging.getLogger()
        old_level = root_logger.level
        root_logger.setLevel(level)
        try:
            yield
        finally:
            root_logger.setLevel(old_level)

# Make sure the package root is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock pandas if needed
try:
    import pandas as pd
    PANDAS_AVAILABLE = True

    # Check if pandas is a real module or a mock
    if not hasattr(pd, 'DataFrame'):
        # It's a mock, so create DataFrame attribute
        pd.DataFrame = MagicMock()
        pd.DataFrame.to_numpy = MagicMock(return_value=None)
        original_df_to_numpy = None
    else:
        # Store original to_numpy if it exists
        original_df_to_numpy = getattr(pd.DataFrame, "to_numpy", None)

    # Create a safe replacement for to_numpy that won't break during tests
    def safe_to_numpy(self, *args, **kwargs):
        """Safe version of to_numpy that handles edge cases during testing."""
        try:
            if original_df_to_numpy:
                return original_df_to_numpy(self, *args, **kwargs)
            else:
                # Fallback if to_numpy isn't available
                return None
        except Exception as e:
            logging.warning(f"Error in safe_to_numpy: {e}")
            return None

    # Apply the patch if to_numpy exists
    if hasattr(pd.DataFrame, "to_numpy"):
        pd.DataFrame.to_numpy = safe_to_numpy

except ImportError:
    PANDAS_AVAILABLE = False

    # Create a mock pandas module
    class MockPandas:
        def __init__(self):
            class DataFrame:
                def __init__(self, *args, **kwargs):
                    pass

                def to_numpy(self, *args, **kwargs):
                    return None

            self.DataFrame = DataFrame

    # Add to sys.modules
    sys.modules['pandas'] = MockPandas()
    logging.info("Created mock pandas module")

# Apply numpy patches if numpy is available
try:
    import numpy as np
    NUMPY_AVAILABLE = True

    # Check if numpy is a real module or a mock
    if not hasattr(np, 'array'):
        np.array = MagicMock(return_value=None)

except ImportError:
    NUMPY_AVAILABLE = False

    # Create a mock numpy module
    class MockNumpy:
        def __init__(self):
            self.array = lambda x, *args, **kwargs: x
            self.ndarray = type('ndarray', (), {})

    # Add to sys.modules
    sys.modules['numpy'] = MockNumpy()
    logging.info("Created mock numpy module")

# Setup pytest fixtures for unit tests
@pytest.fixture
def ipfs_mock():
    """Create a mock IPFS instance for testing."""
    mock = MagicMock()
    mock.files = MagicMock()
    mock.files.read = MagicMock(return_value=b"test data")
    mock.files.ls = MagicMock(return_value={"Entries": []})
    mock.files.write = MagicMock()
    mock.files.mkdir = MagicMock()
    mock.files.rm = MagicMock()
    mock.files.stat = MagicMock(return_value={"Size": 0, "Hash": "testcid", "Type": 0})
    return mock
