import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from ipfs_kit_py.error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSContentNotFoundError,
    IPFSPinningError,
    IPFSTimeoutError,
    IPFSValidationError,
)

# Import the module we want to test
from ipfs_kit_py.ipfs import ipfs_py


@patch("subprocess.run")
def test_error_classification(mock_run):
    """Test that different error types are properly classified."""
    # Set up test fixtures
    resources = {}
    metadata = {
        "role": "leecher",  # Use leecher role for simplest setup
        "testing": True,  # Mark as testing to avoid real daemon calls
    }

    # Create temporary directory
    temp_dir = tempfile.TemporaryDirectory()
    test_dir = temp_dir.name

    # Create a test file
    test_file_path = os.path.join(test_dir, "test_file.txt")
    with open(test_file_path, "w") as f:
        f.write("This is test content for IPFS operations")

    # Create the IPFS object under test
    ipfs = ipfs_py(resources, metadata)

    # Mock different error types

    # 1. Connection Error
    mock_run.side_effect = ConnectionError("Failed to connect to IPFS daemon")
    result = ipfs.ipfs_add_file(test_file_path)
    print("RESULT 1:", result)

    # 2. Timeout Error
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="ipfs add", timeout=30)
    result = ipfs.ipfs_add_file(test_file_path)
    print("RESULT 2:", result)

    # 3. File Not Found Error
    mock_run.side_effect = FileNotFoundError("No such file or directory")
    result = ipfs.ipfs_add_file(test_file_path)
    print("RESULT 3:", result)

    # 4. Unexpected Error
    mock_run.side_effect = Exception("Unexpected error")
    result = ipfs.ipfs_add_file(test_file_path)
    print("RESULT 4:", result)

    # Clean up the temporary directory
    temp_dir.cleanup()


if __name__ == "__main__":
    test_error_classification()
