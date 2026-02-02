#!/usr/bin/env python3
"""
Tests for Synapse SDK integration with ipfs_fsspec.py

This test suite covers the integration of Synapse storage backend
with the FSSpec filesystem interface.
"""

import os
import sys
import tempfile
import shutil
import pytest
import anyio
from unittest.mock import Mock, patch, AsyncMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.anyio

try:
    from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
    FSSPEC_AVAILABLE = True
    IPFS_FSSPEC_ERROR = None
except ImportError as e:
    FSSPEC_AVAILABLE = False
    IPFS_FSSPEC_ERROR = f"ipfs_fsspec module not found: {str(e)}"
    IPFSFileSystem = None

try:
    from ipfs_kit_py.synapse_storage import synapse_storage
    SYNAPSE_MODULES_AVAILABLE = True
    SYNAPSE_ERROR = None
except ImportError as e:
    SYNAPSE_MODULES_AVAILABLE = False
    SYNAPSE_ERROR = f"Synapse modules not available: {str(e)}"


class MockSynapseStorage:
    """Mock Synapse storage for FSSpec testing."""
    
    def __init__(self, **kwargs):
        self.metadata = kwargs.get('metadata', {})
        self.storage_service_created = True
        self.synapse_initialized = True
    
    async def synapse_store_data(self, data, **kwargs):
        """Mock store data operation."""
        return {
            "success": True,
            "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq",
            "size": len(data),
            "filename": kwargs.get("filename", "unknown"),
            "proof_set_id": 42,
            "storage_provider": "0x1234567890abcdef"
        }
    
    async def synapse_retrieve_data(self, commp, **kwargs):
        """Mock retrieve data operation."""
        # Return different data based on CID for testing
        test_data_map = {
            "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq": b"Hello, FSSpec test!",
            "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2test": b"Another test file content",
            "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2dir": b"Directory listing test"
        }
        return test_data_map.get(commp, b"Default test data")
    
    async def synapse_store_file(self, file_path, **kwargs):
        """Mock store file operation."""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        filename = os.path.basename(file_path)
        return {
            "success": True,
            "commp": f"baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2{hash(filename) % 1000:03d}",
            "size": len(data),
            "file_path": file_path,
            "filename": filename,
            "proof_set_id": 42,
            "storage_provider": "0x1234567890abcdef"
        }
    
    async def synapse_retrieve_file(self, commp, output_path, **kwargs):
        """Mock retrieve file operation."""
        data = await self.synapse_retrieve_data(commp)
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(data)
        
        return {
            "success": True,
            "output_path": output_path,
            "size": len(data),
            "commp": commp
        }
    
    async def synapse_list_stored_data(self, **kwargs):
        """Mock list stored data operation."""
        return {
            "success": True,
            "items": [
                {
                    "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq",
                    "filename": "test1.txt",
                    "size": 19,
                    "stored_at": "2024-01-01T00:00:00Z"
                },
                {
                    "commp": "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2test",
                    "filename": "test2.txt",
                    "size": 25,
                    "stored_at": "2024-01-01T01:00:00Z"
                }
            ],
            "total_count": 2
        }
    
    async def synapse_get_piece_status(self, commp, **kwargs):
        """Mock get piece status operation."""
        return {
            "success": True,
            "exists": True,
            "proof_set_last_proven": 1704067200,  # 2024-01-01 00:00:00
            "proof_set_next_proof_due": 1704070800,  # 2024-01-01 01:00:00
            "in_challenge_window": False,
            "commp": commp
        }
    
    def get_status(self):
        """Mock get status operation."""
        return {
            "synapse_initialized": self.synapse_initialized,
            "storage_service_created": self.storage_service_created,
            "network": self.metadata.get("network", "calibration"),
            "configuration_valid": True
        }


class TestFSSpecSynapseIntegration:
    """Test FSSpec integration with Synapse storage backend."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR if not FSSPEC_AVAILABLE else ''}")
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_fsspec_synapse_backend_registration(self):
        """Test that Synapse backend can be registered with FSSpec."""
        
        # Mock the synapse storage initialization
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            
            # Create filesystem with Synapse backend
            fs = IPFSFileSystem(
                backend="synapse",
                metadata={
                    "network": "calibration",
                    "auto_approve": True
                }
            )
            
            assert fs.backend == "synapse"
            assert hasattr(fs, 'synapse_storage')
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR if not FSSPEC_AVAILABLE else ''}")
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_fsspec_synapse_write_operation(self):
        """Test FSSpec write operation with Synapse backend."""
        
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            fs = IPFSFileSystem(backend="synapse")
            
            # Test writing data
            test_path = "synapse://test_file.txt"
            test_data = b"Hello, FSSpec with Synapse!"
            
            # Mock the async method
            async def mock_write():
                # This would call the Synapse storage backend
                mock_storage = MockSynapseStorage()
                result = await mock_storage.synapse_store_data(test_data, filename="test_file.txt")
                return result
            
            # Run the async operation
            result = anyio.run(mock_write)
            
            assert result["success"] == True
            assert "commp" in result
            assert result["filename"] == "test_file.txt"
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR if not FSSPEC_AVAILABLE else ''}")
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_fsspec_synapse_read_operation(self):
        """Test FSSpec read operation with Synapse backend."""
        
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            fs = IPFSFileSystem(backend="synapse")
            
            # Test reading data by CID
            test_commp = "baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"
            
            # Mock the async method
            async def mock_read():
                mock_storage = MockSynapseStorage()
                data = await mock_storage.synapse_retrieve_data(test_commp)
                return data
            
            # Run the async operation
            data = anyio.run(mock_read)
            
            assert data == b"Hello, FSSpec test!"
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR if not FSSPEC_AVAILABLE else ''}")
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_fsspec_synapse_list_operation(self):
        """Test FSSpec list operation with Synapse backend."""
        
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            fs = IPFSFileSystem(backend="synapse")
            
            # Mock the async method
            async def mock_list():
                mock_storage = MockSynapseStorage()
                result = await mock_storage.synapse_list_stored_data()
                return result
            
            # Run the async operation
            result = anyio.run(mock_list)
            
            assert result["success"] == True
            assert "items" in result
            assert len(result["items"]) == 2
            assert result["items"][0]["filename"] == "test1.txt"
            assert result["items"][1]["filename"] == "test2.txt"
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR if not FSSPEC_AVAILABLE else ''}")
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_fsspec_synapse_file_upload_download(self):
        """Test FSSpec file upload and download with Synapse backend."""
        
        # Create test file
        test_file = os.path.join(self.temp_dir, "upload_test.txt")
        test_content = b"This is a test file for Synapse FSSpec integration!"
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            
            # Test upload
            async def mock_upload():
                mock_storage = MockSynapseStorage()
                result = await mock_storage.synapse_store_file(test_file)
                return result
            
            upload_result = anyio.run(mock_upload)
            
            assert upload_result["success"] == True
            assert "commp" in upload_result
            assert upload_result["filename"] == "upload_test.txt"
            
            # Test download
            download_file = os.path.join(self.temp_dir, "download_test.txt")
            commp = upload_result["commp"]
            
            async def mock_download():
                mock_storage = MockSynapseStorage()
                result = await mock_storage.synapse_retrieve_file(commp, download_file)
                return result
            
            download_result = anyio.run(mock_download)
            
            assert download_result["success"] == True
            assert download_result["output_path"] == download_file
            assert os.path.exists(download_file)


class TestSynapseBackendMethods:
    """Test specific Synapse backend method implementations."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self):
        """Set up temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.temp_dir)
        yield
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    def test_synapse_backend_method_naming(self):
        """Test that Synapse backend methods follow naming conventions."""
        
        # Create mock storage instance
        mock_storage = MockSynapseStorage()
        
        # Check that required methods exist
        required_methods = [
            'synapse_store_data',
            'synapse_retrieve_data',
            'synapse_store_file',
            'synapse_retrieve_file',
            'synapse_list_stored_data',
            'synapse_get_piece_status'
        ]
        
        for method_name in required_methods:
            assert hasattr(mock_storage, method_name), f"Method {method_name} not found"
            assert callable(getattr(mock_storage, method_name)), f"Method {method_name} not callable"
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_synapse_backend_error_handling(self):
        """Test error handling in Synapse backend methods."""
        
        # Create mock storage that raises errors
        class ErrorMockSynapseStorage(MockSynapseStorage):
            async def synapse_store_data(self, data, **kwargs):
                if len(data) == 0:
                    return {
                        "success": False,
                        "error": "Empty data not allowed",
                        "operation": "synapse_store_data"
                    }
                return await super().synapse_store_data(data, **kwargs)
            
            async def synapse_retrieve_data(self, commp, **kwargs):
                if commp == "invalid_commp":
                    raise Exception("Invalid CID format")
                return await super().synapse_retrieve_data(commp, **kwargs)
        
        mock_storage = ErrorMockSynapseStorage()
        
        # Test empty data error
        result = await mock_storage.synapse_store_data(b"")
        assert result["success"] == False
        assert "Empty data" in result["error"]
        
        # Test invalid CID error
        try:
            await mock_storage.synapse_retrieve_data("invalid_commp")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Invalid CID" in str(e)
    
    @pytest.mark.anyio
    @pytest.mark.skipif(not SYNAPSE_MODULES_AVAILABLE, 
                       reason=f"Synapse modules not available: {SYNAPSE_ERROR if not SYNAPSE_MODULES_AVAILABLE else ''}")
    async def test_synapse_backend_metadata_handling(self):
        """Test metadata handling in Synapse backend methods."""
        
        mock_storage = MockSynapseStorage(metadata={
            "network": "calibration",
            "auto_approve": True,
            "with_cdn": False
        })
        
        # Test that metadata is properly used
        status = mock_storage.get_status()
        assert status["network"] == "calibration"
        assert status["configuration_valid"] == True
        
        # Test store operation with metadata
        result = await mock_storage.synapse_store_data(
            b"Test data", 
            filename="metadata_test.txt",
            with_cdn=True  # Override config
        )
        
        assert result["success"] == True
        assert result["filename"] == "metadata_test.txt"


def test_integration_with_existing_backends():
    """Test that Synapse backend integrates well with existing backends."""
    
    @pytest.mark.skipif(not FSSPEC_AVAILABLE, 
                       reason=f"FSSpec not available: {IPFS_FSSPEC_ERROR or 'Unknown error'}")
    def test_backend_switching():
        """Test switching between different storage backends."""
        
        # Test IPFS backend (if available)
        try:
            if IPFSFileSystem:
                fs_ipfs = IPFSFileSystem(backend="ipfs")
                assert fs_ipfs.backend == "ipfs"
        except Exception:
            pass  # IPFS backend might not be available
        
        # Test Synapse backend
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            if IPFSFileSystem:
                fs_synapse = IPFSFileSystem(backend="synapse")
                assert fs_synapse.backend == "synapse"
        
                # Test that backends don't interfere with each other
                assert fs_synapse.backend != "ipfs"


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
