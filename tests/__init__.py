# Tests package
try:
    import pytest
    pytestmark = pytest.mark.anyio
except ImportError:
    # pytest not available, tests will run with unittest
    pass
