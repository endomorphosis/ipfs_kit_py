import os
import json
import tempfile
import subprocess
import platform # Added import
import pytest
from unittest.mock import MagicMock, patch
from ipfs_kit_py.storacha_kit import storacha_kit

@pytest.fixture
def storacha_kit_instance():
    """Create a properly configured storacha_kit instance for testing with mocked subprocess."""
    with patch('subprocess.run') as mock_run:
        # Mock successful command execution
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"success": true}'
        mock_run.return_value = mock_process
        
        # Create instance with test configuration
        instance = storacha_kit(
            resources=None,
            metadata={"login": "test@example.com", "test_mode": True}
        )
        yield instance

@pytest.fixture
def mock_spaces_response():
    """Create a mock response for w3 space ls command."""
    return b"""did:mailto:test.com:user * Default Space
did:mailto:test.com:space-123 My Documents
did:mailto:test.com:space-456 Media Library
did:mailto:test.com:space-789 Project Files"""

def test_init(storacha_kit_instance):
    """Test storacha_kit initialization."""
    # Assert
    assert storacha_kit_instance is not None
    assert storacha_kit_instance.metadata["login"] == "test@example.com"
    assert storacha_kit_instance.metadata["test_mode"] is True
    assert storacha_kit_instance.correlation_id is not None

def test_run_w3_command(storacha_kit_instance):
    """Test running a w3 command with mocked subprocess."""
    with patch('subprocess.run') as mock_run:
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'Command output'
        mock_process.stderr = b''
        mock_run.return_value = mock_process
        
        # Act
        result = storacha_kit_instance.run_w3_command(['w3', 'test', 'command'])
        
        # Assert
        assert result["success"] is True
        assert result["returncode"] == 0
        assert result["stdout"] == "Command output"
        mock_run.assert_called_once()
        
        # Get the call arguments
        args, kwargs = mock_run.call_args
        
        # Verify platform-specific command handling
        if platform.system() == "Windows":
            assert args[0][0] == "npx"
            assert args[0][1] == "w3"
        else:
            assert args[0][0] == "w3"
            
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is True
        assert kwargs["shell"] is False

def test_run_w3_command_error(storacha_kit_instance):
    """Test error handling in run_w3_command."""
    with patch('subprocess.run') as mock_run:
        # Configure mock to raise CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, 
            cmd="w3 test command",
            output=b'',
            stderr=b'Error occurred'
        )
        
        # Act
        result = storacha_kit_instance.run_w3_command(['w3', 'test', 'command'])
        
        # Assert
        assert result["success"] is False
        assert result["returncode"] == 1
        assert "error" in result
        assert "error_type" in result

def test_space_ls(storacha_kit_instance, mock_spaces_response):
    """Test the space_ls method with mocked response."""
    with patch('subprocess.run') as mock_run:
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = mock_spaces_response
        mock_process.stderr = b''
        mock_run.return_value = mock_process
        
        # Act
        result = storacha_kit_instance.space_ls()
        
        # Assert
        assert result["success"] is True
        assert len(result["spaces"]) == 4
        assert "Default Space" in result["spaces"]
        assert "My Documents" in result["spaces"]
        assert "Media Library" in result["spaces"]
        assert "Project Files" in result["spaces"]
        assert result["spaces"]["Default Space"] == "did:mailto:test.com:user"
        assert result["count"] == 4

def test_store_add(storacha_kit_instance):
    """Test adding content to store with mocked response."""
    with patch('subprocess.run') as mock_run:
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"Test content")
            file_path = temp_file.name
        
        try:
            # Configure mock to return a successful store add response
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.stdout = b'bagbaieratjbwkujpc5jlmvcnwmni4lw4ukfoixc6twjq5rqkikf3tcemuua'
            mock_process.stderr = b''
            mock_run.return_value = mock_process
            
            # Act
            result = storacha_kit_instance.store_add("Default Space", file_path)
            
            # Assert
            assert result["success"] is True
            assert "bagbaieratjbwkujpc5jlmvcnwmni4lw4ukfoixc6twjq5rqkikf3tcemuua" in result
            mock_run.assert_called_once()
            
        finally:
            # Clean up the temporary file
            os.unlink(file_path)

def test_upload_add_https(storacha_kit_instance):
    """Test upload_add_https method with mocked HTTP response."""
    with patch('requests.post') as mock_post:
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"Test content")
            file_path = temp_file.name
            
        try:
            # Configure mock to return a successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ok": True,
                "value": {
                    "root": {
                        "cid": "bagbaieratjbwkujpc5jlmvcnwmni4lw4ukfoixc6twjq5rqkikf3tcemuua",
                        "shards": []
                    }
                }
            }
            mock_post.return_value = mock_response
            
            # Act
            result = storacha_kit_instance.upload_add_https("Default Space", file_path, os.path.dirname(file_path))
            
            # Assert
            assert result["success"] is True
            assert result["operation"] == "upload_add_https"
            assert result["cid"] == "bagbaieratjbwkujpc5jlmvcnwmni4lw4ukfoixc6twjq5rqkikf3tcemuua"
            assert "shards" in result
            mock_post.assert_called_once()
            
        finally:
            # Clean up the temporary file
            os.unlink(file_path)

def test_space_allocate(storacha_kit_instance):
    """Test space_allocate method with mocked response."""
    with patch('subprocess.run') as mock_run:
        # Configure mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'Allocated 10 GiB to Default Space'
        mock_process.stderr = b''
        mock_run.return_value = mock_process
        
        # Act
        result = storacha_kit_instance.space_allocate("Default Space", 10, "GiB")
        
        # Assert
        assert result["success"] is True
        assert result["operation"] == "space_allocate"
        assert result["space"] == "Default Space"
        assert result["amount"] == 10
        assert result["unit"] == "GiB"
        mock_run.assert_called_once()

def test_batch_operations(storacha_kit_instance):
    """Test batch_operations method with mocked responses."""
    # This is a placeholder test for batch_operations
    # The actual implementation would mock multiple subprocess calls
    with patch.object(storacha_kit_instance, 'upload_add') as mock_upload_add:
        with patch.object(storacha_kit_instance, 'store_get') as mock_store_get:
            # Configure mocks
            mock_upload_add.return_value = {
                "success": True,
                "operation": "upload_add",
                "cid": "bagbaieratjbwkujpc5jlmvcnwmni4lw4ukfoixc6twjq5rqkikf3tcemuua"
            }
            
            mock_store_get.return_value = {
                "success": True,
                "operation": "store_get",
                "cid": "bagbaieratxxxxxxxyyyyyyyyzzzzzzzz"
            }
            
            # Act
            result = storacha_kit_instance.batch_operations(
                "Default Space", 
                ["/path/to/file1.txt", "/path/to/file2.txt"],
                ["bagbaieratxxxxxxxyyyyyyyyzzzzzzzz"]
            )
            
            # Assert
            assert result["success"] is True
            assert "upload_results" in result
            assert "get_results" in result

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
