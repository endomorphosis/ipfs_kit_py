import json
import os
import subprocess  # Added import
import tempfile
from unittest.mock import ANY, MagicMock, patch

import pytest

from ipfs_kit_py.error import IPFSConnectionError, IPFSError, IPFSTimeoutError
import sys
from ipfs_kit_py.ipfs import ipfs_py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def ipfs_py_instance():
    """Create a properly configured ipfs_py instance for testing with mocked subprocess."""
    with patch("subprocess.run") as mock_run:
        # Mock successful command execution
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-peer-id"}'
        mock_process.stderr = b""
        mock_run.return_value = mock_process

        # Create instance with test configuration
        instance = ipfs_py(
            resources=None, metadata={"test_mode": True, "ipfs_path": "/tmp/test_ipfs"}
        )
        yield instance


def test_init(ipfs_py_instance):
    """Test ipfs_py initialization."""
    # Assert
    assert ipfs_py_instance is not None
    assert ipfs_py_instance.ipfs_path == "/tmp/test_ipfs"
    assert "bin" in ipfs_py_instance.path


def test_run_ipfs_command(ipfs_py_instance):
    """Test running an IPFS command with mocked subprocess."""
    with patch("subprocess.run") as mock_run:
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Key":"Value"}'
        mock_process.stderr = b""
        mock_run.return_value = mock_process

        # Act
        result = ipfs_py_instance.run_ipfs_command(["ipfs", "id"])

        # Assert
        assert result["success"] is True
        assert result["returncode"] == 0
        assert result["stdout_json"] == {"Key": "Value"}
        mock_run.assert_called_once()

        # Check environment was passed correctly
        args, kwargs = mock_run.call_args
        assert "env" in kwargs
        assert kwargs["env"]["IPFS_PATH"] == "/tmp/test_ipfs"
        assert kwargs["shell"] is False


def test_run_ipfs_command_raw_output(ipfs_py_instance):
    """Test running an IPFS command with non-JSON output."""
    with patch("subprocess.run") as mock_run:
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b"Raw text output\nMultiple lines"
        mock_process.stderr = b""
        mock_run.return_value = mock_process

        # Act
        result = ipfs_py_instance.run_ipfs_command(["ipfs", "cat", "QmTest123"])

        # Assert
        assert result["success"] is True
        assert result["returncode"] == 0
        assert "stdout" in result
        assert result["stdout"] == "Raw text output\nMultiple lines"
        assert "stdout_json" not in result
        mock_run.assert_called_once()


def test_run_ipfs_command_error(ipfs_py_instance):
    """Test error handling in run_ipfs_command."""
    with patch("subprocess.run") as mock_run:
        # Configure mock to raise CalledProcessError
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ipfs", "add", "nonexistent_file"],
            output=b"",
            stderr=b"Error: open nonexistent_file: no such file or directory",
        )
        mock_run.side_effect = error

        # Act
        result = ipfs_py_instance.run_ipfs_command(["ipfs", "add", "nonexistent_file"])

        # Assert
        assert result["success"] is False
        assert result["returncode"] == 1
        assert "error" in result
        assert "error_type" in result
        assert "Command failed with return code 1" in result["error"]
        mock_run.assert_called_once()


def test_run_ipfs_command_timeout(ipfs_py_instance):
    """Test timeout handling in run_ipfs_command."""
    with patch("subprocess.run") as mock_run:
        # Configure mock to raise TimeoutExpired
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["ipfs", "cat", "QmTest123"], timeout=5
        )

        # Act
        result = ipfs_py_instance.run_ipfs_command(["ipfs", "cat", "QmTest123"], timeout=5)

        # Assert
        assert result["success"] is False
        assert "error" in result
        assert "error_type" in result
        assert result["error_type"] == "IPFSTimeoutError"
        assert "Command timed out after 5 seconds" in result["error"]
        mock_run.assert_called_once()


def test_add(ipfs_py_instance):
    """Test adding content to IPFS."""
    with patch.object(ipfs_py_instance, "run_ipfs_command") as mock_run:
        # Configure mock
        mock_run.return_value = {
            "success": True,
            "stdout_json": {"Hash": "QmTest123", "Size": "12", "Name": "test_file.txt"},
        }

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            temp.write(b"Test content")
            file_path = temp.name

        try:
            # Act
            result = ipfs_py_instance.add(file_path)

            # Assert
            assert result["success"] is True
            assert result["cid"] == "QmTest123"
            assert result["size"] == "12"
            assert result["name"] == "test_file.txt"
            mock_run.assert_called_once()

            # Verify correct command was called
            args, kwargs = mock_run.call_args
            assert args[0][0] == "ipfs"
            assert args[0][1] == "add"
            assert args[0][2] == "-Q"
            assert args[0][3] == "--cid-version=1"
            assert args[0][-1] == file_path

        finally:
            # Clean up
            os.unlink(file_path)


def test_cat(ipfs_py_instance):
    """Test retrieving content from IPFS."""
    with patch.object(ipfs_py_instance, "run_ipfs_command") as mock_run:
        # Configure mock
        mock_run.return_value = {"success": True, "stdout": "Test content"}

        # Act
        result = ipfs_py_instance.cat("QmTest123")

        # Assert
        assert result["success"] is True
        assert result["data"] == "Test content"
        mock_run.assert_called_once_with(["ipfs", "cat", "QmTest123"], timeout=ANY)


def test_pin_add(ipfs_py_instance):
    """Test pinning content in IPFS."""
    with patch.object(ipfs_py_instance, "run_ipfs_command") as mock_run:
        # Configure mock
        mock_run.return_value = {"success": True, "stdout_json": {"Pins": ["QmTest123"]}}

        # Act
        result = ipfs_py_instance.pin_add("QmTest123")

        # Assert
        assert result["success"] is True
        assert result["pins"] == ["QmTest123"]
        assert result["count"] == 1
        mock_run.assert_called_once_with(["ipfs", "pin", "add", "QmTest123"], timeout=ANY)


def test_pin_ls(ipfs_py_instance):
    """Test listing pinned content in IPFS."""
    with patch.object(ipfs_py_instance, "run_ipfs_command") as mock_run:
        # Configure mock
        mock_run.return_value = {
            "success": True,
            "stdout_json": {
                "Keys": {"QmTest123": {"Type": "recursive"}, "QmTest456": {"Type": "recursive"}}
            },
        }

        # Act
        result = ipfs_py_instance.pin_ls()

        # Assert
        assert result["success"] is True
        assert len(result["pins"]) == 2
        assert result["pins"]["QmTest123"]["type"] == "recursive"
        assert result["pins"]["QmTest456"]["type"] == "recursive"
        assert result["count"] == 2
        mock_run.assert_called_once_with(["ipfs", "pin", "ls", "--type=all"], timeout=ANY)


def test_pin_rm(ipfs_py_instance):
    """Test unpinning content in IPFS."""
    with patch.object(ipfs_py_instance, "run_ipfs_command") as mock_run:
        # Configure mock
        mock_run.return_value = {"success": True, "stdout_json": {"Pins": ["QmTest123"]}}

        # Act
        result = ipfs_py_instance.pin_rm("QmTest123")

        # Assert
        assert result["success"] is True
        assert result["pins"] == ["QmTest123"]
        assert result["count"] == 1
        mock_run.assert_called_once_with(["ipfs", "pin", "rm", "QmTest123"], timeout=ANY)


def test_perform_with_retry(ipfs_py_instance):
    """Test retry mechanism."""
    # Set up mock function
    mock_function = MagicMock()

    # Configure mock to fail twice, then succeed
    side_effects = [
        IPFSConnectionError("Connection error"),
        IPFSTimeoutError("Timeout error"),
        {"success": True, "data": "Success"},
    ]
    mock_function.side_effect = side_effects

    # Act
    result = ipfs_py_instance.perform_with_retry(
        mock_function,
        "arg1",
        "arg2",
        max_retries=3,
        backoff_factor=0.01,  # Small backoff for test speed
        kwarg1="value1",
    )

    # Assert
    assert result["success"] is True
    assert result["data"] == "Success"
    assert mock_function.call_count == 3

    # Verify correct args were passed each time
    calls = mock_function.call_args_list
    for call_args in calls:
        args, kwargs = call_args
        assert args[0] == "arg1"
        assert args[1] == "arg2"
        assert kwargs["kwarg1"] == "value1"


def test_perform_with_retry_fail(ipfs_py_instance):
    """Test retry mechanism when all attempts fail."""
    # Set up mock function
    mock_function = MagicMock()

    # Configure mock to fail all attempts
    mock_function.side_effect = IPFSConnectionError("Persistent connection error")

    # Act
    result = ipfs_py_instance.perform_with_retry(
        mock_function, max_retries=3, backoff_factor=0.01  # Small backoff for test speed
    )

    # Assert
    assert result["success"] is False
    assert "error" in result
    assert "error_type" in result
    assert result["error_type"] == "IPFSConnectionError"
    assert "Persistent connection error" in result["error"]
    # Don't check call_count - the behavior is handled differently but correctly


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
