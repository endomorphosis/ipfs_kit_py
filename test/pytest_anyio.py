"""
AnyIO test fixtures for pytest compatibility.

This module provides fixtures and utilities for testing with
pytest-anyio across both asyncio and trio backends.
"""

import pytest
import logging
from typing import Any, Callable, Generator, Optional




# Import pytest_anyio from fix_libp2p_mocks or create a dummy
try:
    import os
    import sys
    import importlib.util

    fix_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fix_libp2p_mocks.py")
    if os.path.exists(fix_script_path):
        spec = importlib.util.spec_from_file_location("fix_libp2p_mocks", fix_script_path)
        fix_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_module)

        # Get pytest_anyio from the module
        pytest_anyio = fix_module.pytest_anyio
    else:
        # Create a dummy implementation
        import pytest
        class DummyAnyioFixture:
            def __call__(self, func):
                return pytest.fixture(func)
        pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
except ImportError as e:
    import pytest
    # Create a dummy implementation
    class DummyAnyioFixture:
        def __call__(self, func):
            return pytest.fixture(func)
    pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
# Import pytest_anyio from fix_libp2p_mocks or create a dummy
try:
    import os
    import sys
    import importlib.util

    fix_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fix_libp2p_mocks.py")
    if os.path.exists(fix_script_path):
        spec = importlib.util.spec_from_file_location("fix_libp2p_mocks", fix_script_path)
        fix_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_module)

        # Get pytest_anyio from the module
        pytest_anyio = fix_module.pytest_anyio
    else:
        # Create a dummy implementation
        import pytest
        class DummyAnyioFixture:
            def __call__(self, func):
                return pytest.fixture(func)
        pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
except ImportError as e:
    import pytest
    # Create a dummy implementation
    class DummyAnyioFixture:
        def __call__(self, func):
            return pytest.fixture(func)
    pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
# Import pytest_anyio from fix_libp2p_mocks or create a dummy
try:
    import os
    import sys
    import importlib.util

    fix_script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fix_libp2p_mocks.py")
    if os.path.exists(fix_script_path):
        spec = importlib.util.spec_from_file_location("fix_libp2p_mocks", fix_script_path)
        fix_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_module)

        # Get pytest_anyio from the module
        pytest_anyio = fix_module.pytest_anyio
    else:
        # Create a dummy implementation
        import pytest
        class DummyAnyioFixture:
            def __call__(self, func):
                return pytest.fixture(func)
        pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
except ImportError as e:
    import pytest
    # Create a dummy implementation
    class DummyAnyioFixture:
        def __call__(self, func):
            return pytest.fixture(func)
    pytest_anyio = type('DummyPytestAnyio', (), {'fixture': DummyAnyioFixture()})
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
