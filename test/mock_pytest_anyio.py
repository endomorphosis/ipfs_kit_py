"""
Mock implementation of pytest_anyio for tests.

This module provides a mock implementation of the pytest_anyio module to allow
tests to run without this dependency installed.
"""

import sys
import types
import logging
import functools

logger = logging.getLogger(__name__)

# Create a mock fixture decorator
def fixture(*args, **kwargs):
    """Mock fixture decorator that works like pytest.fixture."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    # Allow both @fixture and @fixture(scope="function") syntax
    if len(args) == 1 and callable(args[0]):
        return decorator(args[0])
    return decorator

# Create a mock mark decorator
def mark(*args, **kwargs):
    """Mock mark decorator."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Create pytest_anyio module
pytest_anyio_module = types.ModuleType("pytest_anyio")
pytest_anyio_module.fixture = fixture
pytest_anyio_module.mark = mark
pytest_anyio_module.__version__ = "0.1.0"  # Mock version

# Register the module
sys.modules["pytest_anyio"] = pytest_anyio_module

logger.info("Registered mock pytest_anyio module")
