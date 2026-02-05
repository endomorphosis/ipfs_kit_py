"""
Shared Test Fixtures and Utilities for Backend Tests

This module provides shared pytest fixtures and utilities for backend testing,
ensuring consistent patterns across all backend test suites.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock
import time
import uuid


# ============================================================================
# Mock Mode Configuration
# ============================================================================

def get_mock_mode(backend_name):
    """Get mock mode for specific backend from environment.
    
    Args:
        backend_name: Name of the backend (e.g., 'IPFS', 'S3', 'SSHFS')
    
    Returns:
        bool: True if mock mode is enabled
    """
    env_var = f"{backend_name.upper()}_MOCK_MODE"
    return os.environ.get(env_var, "true").lower() == "true"


# ============================================================================
# Common Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    import shutil
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file for tests."""
    temp_path = os.path.join(temp_dir, "test_file.txt")
    with open(temp_path, 'w') as f:
        f.write("Test content")
    yield temp_path


@pytest.fixture
def temp_binary_file(temp_dir):
    """Create a temporary binary file for tests."""
    temp_path = os.path.join(temp_dir, "test_file.bin")
    with open(temp_path, 'wb') as f:
        f.write(b"Binary test content \x00\xff\xfe")
    yield temp_path


@pytest.fixture
def large_temp_file(temp_dir):
    """Create a large temporary file (10MB) for tests."""
    temp_path = os.path.join(temp_dir, "large_file.bin")
    with open(temp_path, 'wb') as f:
        # Write 10MB of data
        f.write(b"X" * (10 * 1024 * 1024))
    yield temp_path


@pytest.fixture
def correlation_id():
    """Generate a correlation ID for request tracking."""
    return str(uuid.uuid4())


# ============================================================================
# Mock HTTP Responses
# ============================================================================

@pytest.fixture
def mock_http_success():
    """Create a mock successful HTTP response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.return_value = {"success": True, "data": "test"}
    mock_response.text = "Success"
    mock_response.content = b"Success content"
    return mock_response


@pytest.fixture
def mock_http_not_found():
    """Create a mock 404 HTTP response."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.ok = False
    mock_response.json.return_value = {"error": "Not found"}
    mock_response.text = "Not found"
    mock_response.content = b"Not found"
    return mock_response


@pytest.fixture
def mock_http_server_error():
    """Create a mock 500 HTTP response."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.ok = False
    mock_response.json.return_value = {"error": "Internal server error"}
    mock_response.text = "Internal server error"
    mock_response.content = b"Internal server error"
    return mock_response


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def test_content_string():
    """Provide test string content."""
    return "Test content for backend storage"


@pytest.fixture
def test_content_binary():
    """Provide test binary content."""
    return b"Binary test content \x00\x01\x02\xff\xfe\xfd"


@pytest.fixture
def test_content_large():
    """Provide large test content (1MB)."""
    return b"X" * (1024 * 1024)


@pytest.fixture
def test_cids():
    """Provide sample CIDs for testing."""
    return {
        "v0": "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",
        "v1": "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        "invalid": "invalid_cid_format"
    }


@pytest.fixture
def test_metadata():
    """Provide test metadata."""
    return {
        "type": "test",
        "description": "Test metadata",
        "version": "1.0",
        "created": time.time()
    }


# ============================================================================
# Helper Functions
# ============================================================================

def assert_result_dict(result, expected_success=True):
    """Assert that a result follows the standard result dictionary pattern.
    
    Args:
        result: Result dictionary to check
        expected_success: Expected success value
    """
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "success" in result, "Result should have 'success' key"
    assert result["success"] == expected_success, f"Expected success={expected_success}"
    
    if expected_success:
        assert "error" not in result or result["error"] is None
    else:
        assert "error" in result, "Failed result should have 'error' key"


def assert_valid_cid(cid):
    """Assert that a string is a valid CID format.
    
    Args:
        cid: CID string to validate
    """
    assert isinstance(cid, str), "CID should be a string"
    assert len(cid) > 0, "CID should not be empty"
    # Basic validation - starts with known prefixes
    assert cid.startswith(("Qm", "bafy", "baf", "zdj")), "CID should start with known prefix"


# ============================================================================
# Parametrize Helpers
# ============================================================================

# Common error scenarios for parametrized testing
COMMON_ERROR_SCENARIOS = [
    ("connection_timeout", ConnectionError("Connection timeout")),
    ("connection_refused", ConnectionRefusedError("Connection refused")),
    ("permission_denied", PermissionError("Permission denied")),
    ("file_not_found", FileNotFoundError("File not found")),
    ("network_unreachable", OSError("Network unreachable")),
]

# Common invalid inputs for parametrized testing
INVALID_INPUTS = [
    ("none", None),
    ("empty_string", ""),
    ("whitespace", "   "),
    ("special_chars", "!@#$%^&*()"),
    ("path_traversal", "../../etc/passwd"),
    ("too_long", "x" * 10000),
]

# Common content types for parametrized testing
CONTENT_TYPES = [
    ("string", "text/plain", "Test string content"),
    ("binary", "application/octet-stream", b"Binary \x00\xff content"),
    ("json", "application/json", '{"key": "value"}'),
    ("large", "application/octet-stream", b"X" * (1024 * 1024)),
]


if __name__ == "__main__":
    print("Shared test fixtures and utilities loaded successfully")
