"""
AnyIO test fixtures for pytest compatibility.

This module provides fixtures and utilities for testing with
pytest-anyio across both asyncio and trio backends.
"""

import pytest
import logging
from typing import Any, Callable, Generator, Optional

logger = logging.getLogger(__name__)

# Re-export pytest.mark.anyio for convenience
anyio = pytest.mark.anyio

# Create a fixture that can be used in tests
@pytest.fixture
async def anyio_backend() -> str:
    """
    Return the current AnyIO backend name.
    
    This is a built-in fixture from pytest-anyio but we redefine it
    here in case it's not available in the testing environment.
    
    Returns:
        The name of the backend ('asyncio' or 'trio')
    """
    try:
        import sniffio
        return sniffio.current_async_library()
    except ImportError:
        return "asyncio"  # Default to asyncio if sniffio not available
    except Exception:
        return "asyncio"  # Default to asyncio for any other error

# Create a fixture wrapper that mimics pytest_anyio.fixture
# This will let us define fixtures that are compatible with anyio
def fixture(*args: Any, **kwargs: Any) -> Callable:
    """
    Define an AnyIO compatible fixture.
    
    This is a thin wrapper around pytest.fixture that ensures fixtures
    work with AnyIO, regardless of the backend.
    
    Args:
        *args: Arguments to pass to pytest.fixture
        **kwargs: Keyword arguments to pass to pytest.fixture
        
    Returns:
        Fixture decorator function
    """
    return pytest.fixture(*args, **kwargs)