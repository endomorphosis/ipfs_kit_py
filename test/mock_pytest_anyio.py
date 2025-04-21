"""
Mock implementation of pytest_anyio for tests.

This provides a compatible interface for tests that use pytest_anyio
without requiring the actual package to be installed.
"""

import sys
import pytest
import logging
import functools
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

# Create simple async fixture decorator that wraps pytest.fixture
def fixture(*args, **kwargs):
    """Mock pytest_anyio.fixture that passes through to pytest.fixture."""
    return pytest.fixture(*args, **kwargs)

# Add module to sys.modules so it can be imported
sys.modules["pytest_anyio"] = sys.modules[__name__]
logger.info("Registered mock pytest_anyio module")

# Helper to run async functions in tests
async def run_async(coro):
    """Run an async coroutine and return its result."""
    return await coro