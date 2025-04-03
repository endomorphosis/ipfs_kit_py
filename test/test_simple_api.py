"""
Simple test for API module to isolate and fix issues.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

# Check if FastAPI is available
try:
    from fastapi.testclient import TestClient

    # Import the api module to check available exports
    import ipfs_kit_py.api

    # Determine if we have real FastAPI or dummy implementation
    FASTAPI_AVAILABLE = ipfs_kit_py.api.FASTAPI_AVAILABLE

    # If FastAPI is not available, skip all tests
    if not FASTAPI_AVAILABLE:
        pytestmark = pytest.mark.skip(reason="FastAPI not available, skipping tests")
except ImportError:
    FASTAPI_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="Could not import api module, skipping tests")

# Import the app from the api module for direct testing
if FASTAPI_AVAILABLE:
    from ipfs_kit_py.api import app
    from ipfs_kit_py.error import IPFSError
else:
    # Define a placeholder IPFSError for testing
    class IPFSError(Exception):
        pass

    app = None


# Create a mocked API class for testing
class MockIPFSSimpleAPI:
    """Mocked IPFSSimpleAPI for testing."""

    def __init__(self, config_path=None):
        """Initialize with test configuration."""
        self.config = {"role": "master", "timeouts": {"default": 30}}
        test_func = lambda: "test"
        test_func.__doc__ = "Test extension documentation"
        test_func2 = lambda: "test2"
        test_func2.__doc__ = "Another test extension"
        self.extensions = {"test_extension": test_func, "another_ext": test_func2}

    def __call__(self, method_name, *args, **kwargs):
        """Call method dispatcher."""
        if method_name == "test_method":
            return {"method": method_name, "args": args, "kwargs": kwargs}
        elif method_name == "binary_method":
            return b"binary data"
        elif method_name == "error_method":
            raise IPFSError("Test error")
        return {"method": "unknown", "args": args}

    def add(self, content, pin=True, wrap_with_directory=False):
        """Add content to IPFS."""
        return {"success": True, "cid": "QmTest", "size": len(content) if content else 0}

    def get(self, cid):
        """Get content from IPFS."""
        return b"test file content"


# Set up test client with the mocked API if FastAPI is available
if FASTAPI_AVAILABLE:
    app.state.ipfs_api = MockIPFSSimpleAPI()
    client = TestClient(app)
else:
    client = None


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_method():
    """Test API method endpoint."""
    response = client.post("/api/test_method", json={"args": [1, 2], "kwargs": {"test": "value"}})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["method"] == "test_method"
    assert result["args"] == [1, 2]
    assert result["kwargs"] == {"test": "value"}


def test_api_method_binary():
    """Test API method endpoint with binary response."""
    response = client.post("/api/binary_method", json={"args": [], "kwargs": {}})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["encoding"] == "base64"
    assert base64.b64decode(result["data"]) == b"binary data"


def test_api_method_error():
    """Test API method endpoint with error."""
    response = client.post("/api/error_method", json={"args": [], "kwargs": {}})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert "Test IPFS error" in result["error"]
    assert result["error_type"] == "IPFSError"


def test_api_config():
    """Test config endpoint."""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "master"
    assert "timeouts" in data
    assert isinstance(data["features"], dict)


def test_api_methods():
    """Test methods listing endpoint."""
    response = client.get("/api/methods")
    assert response.status_code == 200
    data = response.json()
    assert "methods" in data
    # Check for extensions
    extensions = [m for m in data["methods"] if m.get("type") == "extension"]
    assert len(extensions) > 0


def test_file_download():
    """Test file download endpoint."""
    # Test simple download
    response = client.get("/api/download/QmTest")

    # Verify response
    assert response.status_code == 200
    assert response.content == b"test file content"

    # Test with filename parameter
    response = client.get("/api/download/QmTest?filename=test.txt")

    assert response.status_code == 200
    assert response.content == b"test file content"
    assert response.headers["Content-Disposition"] == 'attachment; filename="test.txt"'
