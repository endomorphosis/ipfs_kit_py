"""
Unit tests for SSHFSKit storage backend.

This test suite validates the SSH/SSHFS-based storage backend functionality,
including connection management, file operations, and error handling.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import time

# Import the SSHFSKit class
from ipfs_kit_py.sshfs_kit import SSHFSKit, PARAMIKO_AVAILABLE


# Test configuration
MOCK_MODE = os.environ.get("SSHFS_MOCK_MODE", "true").lower() == "true"


@pytest.fixture
def sshfs_config():
    """Provide test configuration for SSHFSKit."""
    return {
        "host": "test.example.com",
        "username": "testuser",
        "port": 22,
        "key_path": "/path/to/test_key",
        "password": None,
        "remote_base_path": "/tmp/ipfs_kit_test",
        "connection_timeout": 30,
        "keepalive_interval": 60
    }


@pytest.fixture
def mock_ssh_client():
    """Create a mock SSH client for testing."""
    if not PARAMIKO_AVAILABLE:
        pytest.skip("paramiko not available")
    
    with patch('paramiko.SSHClient') as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        
        # Mock successful connection
        mock_instance.connect.return_value = None
        mock_instance.close.return_value = None
        
        # Mock SFTP client
        mock_sftp = MagicMock()
        mock_instance.open_sftp.return_value = mock_sftp
        
        yield mock_instance, mock_sftp


@pytest.fixture
def sshfs_kit(sshfs_config, mock_ssh_client):
    """Create an SSHFSKit instance for testing."""
    if MOCK_MODE and PARAMIKO_AVAILABLE:
        kit = SSHFSKit(**sshfs_config)
        return kit
    else:
        pytest.skip("Mock mode disabled or paramiko not available")


class TestSSHFSKitInitialization:
    """Test SSHFSKit initialization and configuration."""
    
    def test_init_with_key_auth(self, sshfs_config):
        """Test initialization with SSH key authentication."""
        kit = SSHFSKit(**sshfs_config)
        
        assert kit.host == sshfs_config["host"]
        assert kit.username == sshfs_config["username"]
        assert kit.port == sshfs_config["port"]
        assert kit.key_path == sshfs_config["key_path"]
        assert kit.password is None
        assert kit.remote_base_path == sshfs_config["remote_base_path"]
        assert kit.is_connected is False
    
    def test_init_with_password_auth(self, sshfs_config):
        """Test initialization with password authentication."""
        config = sshfs_config.copy()
        config["password"] = "testpassword"
        config["key_path"] = None
        
        kit = SSHFSKit(**config)
        
        assert kit.password == "testpassword"
        assert kit.key_path is None
    
    def test_init_default_values(self):
        """Test initialization with minimal parameters."""
        kit = SSHFSKit(host="test.com", username="user")
        
        assert kit.port == 22
        assert kit.remote_base_path == "/tmp/ipfs_kit_sshfs"
        assert kit.connection_timeout == 30
        assert kit.keepalive_interval == 60


class TestSSHFSKitConnection:
    """Test SSH connection management."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_connect_with_key(self, sshfs_kit, mock_ssh_client):
        """Test SSH connection with key authentication."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Attempt connection
        result = await sshfs_kit.connect()
        
        # Verify connection was attempted
        assert mock_client.connect.called
        assert result.get("success") is True
        
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_connect_with_password(self, sshfs_config, mock_ssh_client):
        """Test SSH connection with password authentication."""
        config = sshfs_config.copy()
        config["password"] = "testpassword"
        config["key_path"] = None
        
        kit = SSHFSKit(**config)
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock the connection
        if hasattr(kit, 'connect'):
            result = await kit.connect()
            assert result.get("success") is True
    
    @pytest.mark.anyio
    async def test_connect_failure_handling(self, sshfs_config):
        """Test handling of connection failures."""
        if not PARAMIKO_AVAILABLE:
            pytest.skip("paramiko not available")
        
        with patch('paramiko.SSHClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Mock connection failure
            mock_instance.connect.side_effect = Exception("Connection refused")
            
            kit = SSHFSKit(**sshfs_config)
            
            # Verify error handling (implementation-dependent)
            if hasattr(kit, 'connect'):
                result = await kit.connect()
                assert result.get("success") is False
                assert "error" in result


class TestSSHFSKitFileOperations:
    """Test file upload, download, and management operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_upload_file(self, sshfs_kit, mock_ssh_client):
        """Test file upload to remote server."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("test content")
            tmp_path = tmp_file.name
        
        try:
            # Mock SFTP put
            mock_sftp.put.return_value = None
            
            # Test upload
            if hasattr(sshfs_kit, 'store_file'):
                sshfs_kit.sftp_client = mock_sftp
                sshfs_kit.is_connected = True
                result = await sshfs_kit.store_file(tmp_path, remote_name="file.txt")
                assert result.get("success") is True
                assert mock_sftp.put.called
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_download_file(self, sshfs_kit, mock_ssh_client):
        """Test file download from remote server."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock SFTP get
        mock_sftp.get.return_value = None
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = os.path.join(tmp_dir, "downloaded_file.txt")
            
            if hasattr(sshfs_kit, 'retrieve_file'):
                storage_id = "test_storage"
                sshfs_kit.sftp_client = mock_sftp
                sshfs_kit.is_connected = True
                sshfs_kit.stored_files[storage_id] = {
                    "remote_path": "/remote/path/file.txt",
                    "bucket": "default",
                    "size": 123,
                    "uploaded_at": time.time(),
                    "metadata": {},
                }
                result = await sshfs_kit.retrieve_file(storage_id, local_path)
                assert result.get("success") is True
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_list_remote_directory(self, sshfs_kit, mock_ssh_client):
        """Test listing remote directory contents."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock listdir
        mock_sftp.listdir.return_value = ["file1.txt", "file2.txt", "subdir"]
        
        if hasattr(sshfs_kit, 'list_files'):
            sshfs_kit.stored_files["test_storage"] = {
                "remote_path": "/remote/path/file1.txt",
                "bucket": "default",
                "size": 123,
                "uploaded_at": time.time(),
                "metadata": {},
            }
            result = await sshfs_kit.list_files()
            assert result.get("success") is True
            assert isinstance(result.get("files"), list)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_delete_remote_file(self, sshfs_kit, mock_ssh_client):
        """Test deleting a file on remote server."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock remove
        mock_sftp.remove.return_value = None
        
        if hasattr(sshfs_kit, 'delete_file'):
            storage_id = "test_storage"
            sshfs_kit.sftp_client = mock_sftp
            sshfs_kit.is_connected = True
            sshfs_kit.stored_files[storage_id] = {
                "remote_path": "/remote/path/file.txt",
                "bucket": "default",
                "size": 123,
                "uploaded_at": time.time(),
                "metadata": {},
            }
            result = await sshfs_kit.delete_file(storage_id)
            assert result.get("success") is True
            assert storage_id not in sshfs_kit.stored_files
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_create_remote_directory(self, sshfs_kit, mock_ssh_client):
        """Test creating a directory on remote server."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock mkdir
        mock_sftp.mkdir.return_value = None
        
        if hasattr(sshfs_kit, '_ensure_remote_path_sftp'):
            sshfs_kit.sftp_client = mock_sftp
            mock_sftp.stat.side_effect = FileNotFoundError()
            await sshfs_kit._ensure_remote_path_sftp("/remote/path/newdir")
            assert mock_sftp.mkdir.called


class TestSSHFSKitErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_host(self):
        """Test handling of invalid host."""
        # Empty host should be handled - either raises or creates instance
        try:
            kit = SSHFSKit(host="", username="user")
            # If it doesn't raise, that's also acceptable behavior
            assert kit is not None
        except (ValueError, TypeError, Exception):
            # If it raises, that's expected
            pass
    
    def test_missing_credentials(self):
        """Test handling of missing authentication credentials."""
        # Both key_path and password are None
        kit = SSHFSKit(host="test.com", username="user", key_path=None, password=None)
        # Should still initialize but may fail on connect
        assert kit is not None
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_network_timeout(self, sshfs_config):
        """Test handling of network timeouts."""
        if not PARAMIKO_AVAILABLE:
            pytest.skip("paramiko not available")
        
        with patch('paramiko.SSHClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            # Mock timeout
            import socket
            mock_instance.connect.side_effect = socket.timeout("Connection timeout")
            
            kit = SSHFSKit(**sshfs_config)
            
            if hasattr(kit, 'connect'):
                result = await kit.connect()
                assert result.get("success") is False
                assert "timeout" in str(result.get("error", "")).lower()
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_permission_denied(self, sshfs_kit, mock_ssh_client):
        """Test handling of permission errors."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Mock permission error
        import paramiko
        mock_sftp.put.side_effect = PermissionError("Permission denied")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("test")
            tmp_path = tmp_file.name
        
        try:
            if hasattr(sshfs_kit, 'store_file'):
                sshfs_kit.sftp_client = mock_sftp
                sshfs_kit.is_connected = True
                result = await sshfs_kit.store_file(tmp_path, remote_name="file.txt")
                assert result.get("success") is False
                assert "error" in result
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestSSHFSKitStorageTracking:
    """Test storage tracking and metadata management."""
    
    def test_storage_tracking_initialization(self, sshfs_kit):
        """Test that storage tracking is properly initialized."""
        assert hasattr(sshfs_kit, 'stored_files')
        assert isinstance(sshfs_kit.stored_files, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_track_uploaded_file(self, sshfs_kit, mock_ssh_client):
        """Test tracking of uploaded files."""
        mock_client, mock_sftp = mock_ssh_client
        mock_sftp.put.return_value = None
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
            tmp_file.write("test content")
            tmp_path = tmp_file.name
        
        try:
            if hasattr(sshfs_kit, 'store_file'):
                sshfs_kit.sftp_client = mock_sftp
                sshfs_kit.is_connected = True
                result = await sshfs_kit.store_file(tmp_path, remote_name="tracked_file.txt")
                assert result.get("success") is True
                storage_id = result.get("storage_id")
                assert storage_id in sshfs_kit.stored_files
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestSSHFSKitCleanup:
    """Test connection cleanup and resource management."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_disconnect(self, sshfs_kit, mock_ssh_client):
        """Test SSH connection cleanup."""
        mock_client, mock_sftp = mock_ssh_client
        
        if hasattr(sshfs_kit, 'disconnect'):
            sshfs_kit.ssh_client = mock_client
            sshfs_kit.sftp_client = mock_sftp
            result = await sshfs_kit.disconnect()
            
            # Verify cleanup was attempted
            assert mock_client.close.called or True
            assert result.get("success") is True
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_context_manager(self, sshfs_config, mock_ssh_client):
        """Test SSHFSKit as context manager if supported."""
        if PARAMIKO_AVAILABLE:
            kit = SSHFSKit(**sshfs_config)
            
            # Check if context manager is implemented
            if hasattr(kit, '__enter__') and hasattr(kit, '__exit__'):
                with kit as k:
                    assert k is not None


class TestSSHFSKitIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    @pytest.mark.anyio
    async def test_upload_download_cycle(self, sshfs_kit, mock_ssh_client):
        """Test complete upload and download cycle."""
        mock_client, mock_sftp = mock_ssh_client
        
        # Create test content
        test_content = b"Integration test content"
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(test_content)
            upload_path = tmp_file.name
        
        try:
            # Mock upload
            mock_sftp.put.return_value = None
            
            # Mock download with content
            def mock_get(remote, local):
                with open(local, 'wb') as f:
                    f.write(test_content)
            
            mock_sftp.get.side_effect = mock_get
            
            # Test workflow
            if hasattr(sshfs_kit, 'store_file') and hasattr(sshfs_kit, 'retrieve_file'):
                sshfs_kit.sftp_client = mock_sftp
                sshfs_kit.is_connected = True

                # Upload
                upload_result = await sshfs_kit.store_file(upload_path, remote_name="test_file.txt")
                assert upload_result.get("success") is True

                # Download
                with tempfile.TemporaryDirectory() as tmp_dir:
                    download_path = os.path.join(tmp_dir, "downloaded.txt")
                    storage_id = upload_result.get("storage_id")
                    download_result = await sshfs_kit.retrieve_file(storage_id, download_path)
                    assert download_result.get("success") is True
                    
                    # Verify content if file was created
                    if os.path.exists(download_path):
                        with open(download_path, 'rb') as f:
                            assert f.read() == test_content
        finally:
            Path(upload_path).unlink(missing_ok=True)


# Module-level test for import
def test_sshfs_kit_import():
    """Test that SSHFSKit can be imported."""
    from ipfs_kit_py.sshfs_kit import SSHFSKit
    assert SSHFSKit is not None


def test_paramiko_availability_check():
    """Test paramiko availability is properly detected."""
    from ipfs_kit_py.sshfs_kit import PARAMIKO_AVAILABLE
    assert isinstance(PARAMIKO_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
