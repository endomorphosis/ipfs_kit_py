#!/usr/bin/env python3
"""
Compatibility layer for testing.

This module provides compatibility functions and classes for tests,
primarily handling cases where optional dependencies may not be available.
"""

import pytest


# Handle pytest_anyio availability
try:
    import pytest_anyio
    HAS_PYTEST_ANYIO = True
except ImportError:
    HAS_PYTEST_ANYIO = False
    # Create dummy versions for compatibility
    class DummyAnyioFixture:
        def __call__(self, func):
            return pytest.fixture(func)

    pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})