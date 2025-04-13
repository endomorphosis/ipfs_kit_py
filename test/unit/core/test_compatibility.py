#!/usr/bin/env python3
"""
Compatibility layer for testing.

This module provides compatibility functions and classes for tests,
primarily handling cases where optional dependencies may not be available.
"""

import pytest


# Handle pytest_asyncio availability
try:
    import pytest_asyncio
    HAS_PYTEST_ASYNCIO = True
except ImportError:
    HAS_PYTEST_ASYNCIO = False
    # Create dummy versions for compatibility
    class DummyAsyncioFixture:
        def __call__(self, func):
            return pytest.fixture(func)
    
    pytest_asyncio = type('DummyPytestAsyncio', (), {'fixture': DummyAsyncioFixture()})