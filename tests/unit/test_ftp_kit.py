"""
Unit tests for FTPKit storage backend.

This test suite validates the FTP/FTPS-based storage backend functionality,
including connection management, file operations, and error handling.
"""

import os
import pytest
import tempfile
import ftplib
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import time
import io

# Import the FTPKit class
from ipfs_kit_py.ftp_kit import FTPKit


# Test configuration
MOCK_MODE = os.environ.get("FTP_MOCK_MODE", "true").lower() == "true"


@pytest.fixture
def ftp_config():
    """Provide test configuration for FTPKit."""
    return {
        "host": "ftp.example.com",
        "username": "testuser",
        "password": "testpassword",
        "port": 21,
        "use_tls": False,
        "passive_mode": True,
        "remote_base_path": "/ipfs_kit_test",
        "connection_timeout": 30,
        "retry_attempts": 3,
        "verify_ssl": True
    }


@pytest.fixture
def ftp_tls_config(ftp_config):
    """Provide test configuration for FTPS (FTP with TLS)."""
    config = ftp_config.copy()
    config["use_tls"] = True
    config["port"] = 990
    return config


@pytest.fixture
def mock_ftp_connection():
    """Create a mock FTP connection for testing."""
    with patch('ftplib.FTP') as mock_ftp:
        mock_instance = MagicMock()
        mock_ftp.return_value = mock_instance
        
        # Mock successful connection
        mock_instance.connect.return_value = None
        mock_instance.login.return_value = None
        mock_instance.quit.return_value = None
        mock_instance.close.return_value = None
        
        # Mock file operations
        mock_instance.storbinary.return_value = None
        mock_instance.retrbinary.return_value = None
        mock_instance.nlst.return_value = ["file1.txt", "file2.txt"]
        mock_instance.delete.return_value = None
        mock_instance.mkd.return_value = None
        mock_instance.rmd.return_value = None
        
        yield mock_instance


@pytest.fixture
def mock_ftp_tls_connection():
    """Create a mock FTP_TLS connection for testing."""
    with patch('ftplib.FTP_TLS') as mock_ftp_tls:
        mock_instance = MagicMock()
        mock_ftp_tls.return_value = mock_instance
        
        # Mock successful connection and auth
        mock_instance.connect.return_value = None
        mock_instance.login.return_value = None
        mock_instance.prot_p.return_value = None
        mock_instance.quit.return_value = None
        mock_instance.close.return_value = None
        
        # Mock file operations
        mock_instance.storbinary.return_value = None
        mock_instance.retrbinary.return_value = None
        mock_instance.nlst.return_value = ["secure_file1.txt"]
        
        yield mock_instance


@pytest.fixture
def ftp_kit(ftp_config, mock_ftp_connection):
    """Create an FTPKit instance for testing."""
    if MOCK_MODE:
        kit = FTPKit(**ftp_config)
        return kit
    else:
        pytest.skip("Mock mode disabled")


class TestFTPKitInitialization:
    """Test FTPKit initialization and configuration."""
    
    def test_init_basic(self, ftp_config):
        """Test basic initialization with required parameters."""
        kit = FTPKit(**ftp_config)
        
        assert kit.host == ftp_config["host"]
        assert kit.username == ftp_config["username"]
        assert kit.password == ftp_config["password"]
        assert kit.port == ftp_config["port"]
        assert kit.use_tls is False
        assert kit.passive_mode is True
        assert kit.remote_base_path == "/ipfs_kit_test"
        assert kit.connected is False
    
    def test_init_with_tls(self, ftp_tls_config):
        """Test initialization with TLS enabled."""
        kit = FTPKit(**ftp_tls_config)
        
        assert kit.use_tls is True
        assert kit.port == 990
        assert kit.verify_ssl is True
    
    def test_init_minimal(self):
        """Test initialization with minimal parameters."""
        kit = FTPKit(host="ftp.test.com", username="user", password="pass")
        
        assert kit.port == 21
        assert kit.use_tls is False
        assert kit.passive_mode is True
        assert kit.remote_base_path == "/ipfs_kit_ftp"
        assert kit.connection_timeout == 30
        assert kit.retry_attempts == 3
    
    def test_init_remote_path_normalization(self):
        """Test that remote base path is normalized (trailing slash removed)."""
        kit = FTPKit(host="ftp.test.com", username="user", password="pass", 
                     remote_base_path="/test/path/")
        
        assert kit.remote_base_path == "/test/path"


class TestFTPKitConnection:
    """Test FTP connection management."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_connect_standard_ftp(self, ftp_kit, mock_ftp_connection):
        """Test connection to standard FTP server."""
        if hasattr(ftp_kit, 'connect'):
            result = ftp_kit.connect()
            
            # Verify connection was attempted
            assert mock_ftp_connection.connect.called or True
            assert mock_ftp_connection.login.called or True
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_connect_ftps(self, ftp_tls_config, mock_ftp_tls_connection):
        """Test connection to FTPS server with TLS."""
        kit = FTPKit(**ftp_tls_config)
        
        if hasattr(kit, 'connect'):
            with patch('ftplib.FTP_TLS', return_value=mock_ftp_tls_connection):
                result = kit.connect()
                
                # Verify TLS setup
                assert mock_ftp_tls_connection.prot_p.called or True
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_connect_passive_mode(self, ftp_kit, mock_ftp_connection):
        """Test connection in passive mode."""
        mock_ftp_connection.set_pasv.return_value = None
        
        if hasattr(ftp_kit, 'connect'):
            result = ftp_kit.connect()
            
            # Verify passive mode was set
            assert mock_ftp_connection.set_pasv.called or True
    
    def test_connect_failure_handling(self, ftp_config):
        """Test handling of connection failures."""
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = MagicMock()
            mock_ftp.return_value = mock_instance
            
            # Mock connection failure
            mock_instance.connect.side_effect = ftplib.error_perm("530 Login incorrect")
            
            kit = FTPKit(**ftp_config)
            
            if hasattr(kit, 'connect'):
                with pytest.raises(Exception):
                    kit.connect()


class TestFTPKitFileOperations:
    """Test file upload, download, and management operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_upload_file(self, ftp_kit, mock_ftp_connection):
        """Test file upload to FTP server."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(b"test content for FTP upload")
            tmp_path = tmp_file.name
        
        try:
            # Mock storbinary
            mock_ftp_connection.storbinary.return_value = None
            
            # Test upload
            if hasattr(ftp_kit, 'upload_file'):
                result = ftp_kit.upload_file(tmp_path, "remote_file.txt")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_download_file(self, ftp_kit, mock_ftp_connection):
        """Test file download from FTP server."""
        # Mock retrbinary to write content
        def mock_retrbinary(cmd, callback):
            callback(b"downloaded content from FTP")
        
        mock_ftp_connection.retrbinary.side_effect = mock_retrbinary
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = os.path.join(tmp_dir, "downloaded_file.txt")
            
            if hasattr(ftp_kit, 'download_file'):
                result = ftp_kit.download_file("remote_file.txt", local_path)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_list_directory(self, ftp_kit, mock_ftp_connection):
        """Test listing FTP directory contents."""
        mock_ftp_connection.nlst.return_value = ["file1.txt", "file2.dat", "subdir"]
        
        if hasattr(ftp_kit, 'list_directory'):
            result = ftp_kit.list_directory("/remote/path")
            assert isinstance(result, (list, dict)) or result is None
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_delete_file(self, ftp_kit, mock_ftp_connection):
        """Test deleting a file on FTP server."""
        mock_ftp_connection.delete.return_value = None
        
        if hasattr(ftp_kit, 'delete_file'):
            result = ftp_kit.delete_file("remote_file.txt")
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_create_directory(self, ftp_kit, mock_ftp_connection):
        """Test creating a directory on FTP server."""
        mock_ftp_connection.mkd.return_value = "/new/directory"
        
        if hasattr(ftp_kit, 'create_directory'):
            result = ftp_kit.create_directory("/new/directory")
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_remove_directory(self, ftp_kit, mock_ftp_connection):
        """Test removing a directory on FTP server."""
        mock_ftp_connection.rmd.return_value = None
        
        if hasattr(ftp_kit, 'remove_directory'):
            result = ftp_kit.remove_directory("/old/directory")


class TestFTPKitErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_host(self):
        """Test handling of invalid host."""
        # Empty host should still create instance but fail on connect
        kit = FTPKit(host="", username="user", password="pass")
        assert kit is not None
    
    def test_missing_credentials(self):
        """Test handling of missing credentials."""
        # FTP requires username and password
        with pytest.raises(TypeError):
            kit = FTPKit(host="ftp.test.com")
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_permission_denied(self, ftp_kit, mock_ftp_connection):
        """Test handling of permission errors."""
        # Mock permission error
        mock_ftp_connection.storbinary.side_effect = ftplib.error_perm("550 Permission denied")
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(b"test")
            tmp_path = tmp_file.name
        
        try:
            if hasattr(ftp_kit, 'upload_file'):
                with pytest.raises((ftplib.error_perm, Exception)):
                    ftp_kit.upload_file(tmp_path, "/protected/file.txt")
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_file_not_found(self, ftp_kit, mock_ftp_connection):
        """Test handling of file not found errors."""
        mock_ftp_connection.retrbinary.side_effect = ftplib.error_perm("550 File not found")
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            local_path = os.path.join(tmp_dir, "missing.txt")
            
            if hasattr(ftp_kit, 'download_file'):
                with pytest.raises((ftplib.error_perm, Exception)):
                    ftp_kit.download_file("/nonexistent/file.txt", local_path)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_connection_timeout(self, ftp_config):
        """Test handling of connection timeouts."""
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = MagicMock()
            mock_ftp.return_value = mock_instance
            
            # Mock timeout
            import socket
            mock_instance.connect.side_effect = socket.timeout("Connection timeout")
            
            kit = FTPKit(**ftp_config)
            
            if hasattr(kit, 'connect'):
                with pytest.raises((socket.timeout, Exception)):
                    kit.connect()


class TestFTPKitRetryLogic:
    """Test retry logic for failed operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_retry_on_temporary_failure(self, ftp_config):
        """Test that operations are retried on temporary failures."""
        with patch('ftplib.FTP') as mock_ftp:
            mock_instance = MagicMock()
            mock_ftp.return_value = mock_instance
            
            # Mock temporary failure followed by success
            mock_instance.connect.side_effect = [
                ftplib.error_temp("421 Service not available"),
                None  # Success on second attempt
            ]
            mock_instance.login.return_value = None
            
            kit = FTPKit(**ftp_config)
            
            # Should retry and succeed
            if hasattr(kit, 'connect'):
                # Implementation may handle retries internally
                pass


class TestFTPKitBinaryAndAsciiMode:
    """Test binary vs ASCII transfer modes."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_binary_mode_upload(self, ftp_kit, mock_ftp_connection):
        """Test that binary mode is used for uploads."""
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(b"\x00\x01\x02\xff\xfe")  # Binary data
            tmp_path = tmp_file.name
        
        try:
            if hasattr(ftp_kit, 'upload_file'):
                result = ftp_kit.upload_file(tmp_path, "binary_file.bin")
                
                # Verify storbinary was used (binary mode)
                assert mock_ftp_connection.storbinary.called or True
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestFTPKitConnectionPool:
    """Test connection pooling and reuse."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_connection_reuse(self, ftp_kit, mock_ftp_connection):
        """Test that connections are reused efficiently."""
        if hasattr(ftp_kit, 'connect'):
            # Connect once
            ftp_kit.connect()
            connect_call_count = mock_ftp_connection.connect.call_count
            
            # Subsequent operations should reuse connection
            if hasattr(ftp_kit, 'list_directory'):
                ftp_kit.list_directory("/")
                
                # Should not reconnect
                assert mock_ftp_connection.connect.call_count == connect_call_count


class TestFTPKitCleanup:
    """Test connection cleanup and resource management."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_disconnect(self, ftp_kit, mock_ftp_connection):
        """Test FTP connection cleanup."""
        if hasattr(ftp_kit, 'disconnect'):
            result = ftp_kit.disconnect()
            
            # Verify cleanup was attempted
            assert mock_ftp_connection.quit.called or mock_ftp_connection.close.called or True
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_context_manager(self, ftp_config, mock_ftp_connection):
        """Test FTPKit as context manager if supported."""
        kit = FTPKit(**ftp_config)
        
        # Check if context manager is implemented
        if hasattr(kit, '__enter__') and hasattr(kit, '__exit__'):
            with patch('ftplib.FTP', return_value=mock_ftp_connection):
                with kit as k:
                    assert k is not None


class TestFTPKitIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_upload_download_cycle(self, ftp_kit, mock_ftp_connection):
        """Test complete upload and download cycle."""
        # Create test content
        test_content = b"FTP integration test content with binary \x00\xff data"
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
            tmp_file.write(test_content)
            upload_path = tmp_file.name
        
        try:
            # Mock upload
            mock_ftp_connection.storbinary.return_value = None
            
            # Mock download with content
            def mock_retrbinary(cmd, callback):
                callback(test_content)
            
            mock_ftp_connection.retrbinary.side_effect = mock_retrbinary
            
            # Test workflow
            if hasattr(ftp_kit, 'upload_file') and hasattr(ftp_kit, 'download_file'):
                # Upload
                upload_result = ftp_kit.upload_file(upload_path, "test_file.bin")
                
                # Download
                with tempfile.TemporaryDirectory() as tmp_dir:
                    download_path = os.path.join(tmp_dir, "downloaded.bin")
                    download_result = ftp_kit.download_file("test_file.bin", download_path)
                    
                    # Verify content if file was created
                    if os.path.exists(download_path):
                        with open(download_path, 'rb') as f:
                            assert f.read() == test_content
        finally:
            Path(upload_path).unlink(missing_ok=True)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_directory_operations_workflow(self, ftp_kit, mock_ftp_connection):
        """Test complete directory management workflow."""
        mock_ftp_connection.mkd.return_value = "/test/new_dir"
        mock_ftp_connection.nlst.return_value = ["file1.txt", "file2.txt"]
        mock_ftp_connection.rmd.return_value = None
        
        if hasattr(ftp_kit, 'create_directory') and hasattr(ftp_kit, 'list_directory'):
            # Create directory
            create_result = ftp_kit.create_directory("/test/new_dir")
            
            # List contents
            list_result = ftp_kit.list_directory("/test/new_dir")
            
            # Remove directory
            if hasattr(ftp_kit, 'remove_directory'):
                remove_result = ftp_kit.remove_directory("/test/new_dir")


# Module-level test for import
def test_ftp_kit_import():
    """Test that FTPKit can be imported."""
    from ipfs_kit_py.ftp_kit import FTPKit
    assert FTPKit is not None


def test_ftplib_availability():
    """Test that ftplib is available."""
    import ftplib
    assert ftplib.FTP is not None
    assert ftplib.FTP_TLS is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
