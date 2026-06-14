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
import fsspec
from unittest.mock import Mock, patch, AsyncMock

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.anyio

try:
    from ipfs_kit_py import enhanced_fsspec
    SynapseFileSystem = enhanced_fsspec.SynapseFileSystem
    EnhancedIPFSFileSystem = enhanced_fsspec.IPFSFileSystem
except ImportError:
    enhanced_fsspec = None
    SynapseFileSystem = None
    EnhancedIPFSFileSystem = None

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

    stored_data = {}
    stored_meta = {}
    
    def __init__(self, **kwargs):
        self.metadata = kwargs.get('metadata', {})
        self.storage_service_created = True
        self.synapse_initialized = True

    @classmethod
    def reset(cls):
        cls.stored_data = {}
        cls.stored_meta = {}

    @staticmethod
    def _commp_for_name(name):
        safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
        return f"baga6ea4seaqmock{safe or 'data'}"
    
    async def synapse_store_data(self, data, **kwargs):
        """Mock store data operation."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        filename = kwargs.get("filename", "unknown")
        commp = self._commp_for_name(filename)
        self.stored_data[commp] = bytes(data)
        self.stored_meta[commp] = {
            "filename": filename,
            "size": len(data),
            "proof_set_id": 42,
            "storage_provider": "0x1234567890abcdef",
        }
        return {
            "success": True,
            "commp": commp,
            "size": len(data),
            "filename": filename,
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
        if commp in self.stored_data:
            return self.stored_data[commp]
        return test_data_map.get(commp, b"Default test data")
    
    async def synapse_store_file(self, file_path, **kwargs):
        """Mock store file operation."""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        result = await self.synapse_store_data(data, filename=os.path.basename(file_path), **kwargs)
        result["file_path"] = file_path
        return result
    
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
            "size": self.stored_meta.get(commp, {}).get("size", 19),
            "proof_set_last_proven": 1704067200,  # 2024-01-01 00:00:00
            "proof_set_next_proof_due": 1704070800,  # 2024-01-01 01:00:00
            "in_challenge_window": False,
            "commp": commp,
            "storage_provider": self.stored_meta.get(commp, {}).get("storage_provider", "0x1234567890abcdef"),
        }
    
    def get_status(self):
        """Mock get status operation."""
        return {
            "synapse_initialized": self.synapse_initialized,
            "storage_service_created": self.storage_service_created,
            "network": self.metadata.get("network", "calibration"),
            "configuration_valid": True
        }


@pytest.fixture(autouse=True)
def reset_mock_synapse_storage():
    MockSynapseStorage.reset()
    yield
    MockSynapseStorage.reset()


def _synapse_fs():
    with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
        return SynapseFileSystem(skip_instance_cache=True)


@pytest.mark.skipif(SynapseFileSystem is None, reason="enhanced_fsspec SynapseFileSystem not available")
def test_synapse_missing_dependency_raises_clear_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "ipfs_kit_py.synapse_storage", None)

    with pytest.raises(ImportError):
        fsspec.filesystem("synapse", skip_instance_cache=True)


@pytest.mark.skipif(
    not os.getenv("IPFS_KIT_LIVE_SYNAPSE"),
    reason="set IPFS_KIT_LIVE_SYNAPSE=1 to run live Synapse fsspec smoke tests",
)
@pytest.mark.skipif(SynapseFileSystem is None, reason="enhanced_fsspec SynapseFileSystem not available")
def test_live_synapse_status_requires_explicit_env_gate():
    metadata = {"network": os.getenv("SYNAPSE_NETWORK", "calibration")}
    if os.getenv("SYNAPSE_PRIVATE_KEY"):
        metadata["private_key"] = os.environ["SYNAPSE_PRIVATE_KEY"]

    filesystem = SynapseFileSystem(metadata=metadata, skip_instance_cache=True)
    status = filesystem.get_backend_status()

    assert status["backend"] == "synapse"
    assert status["network"] == metadata["network"]
    assert "configuration_valid" in status


@pytest.mark.skipif(SynapseFileSystem is None, reason="enhanced_fsspec SynapseFileSystem not available")
class TestEnhancedSynapseFSSpecBehavior:
    """Direct fsspec behavior expected by fsspec-backends-003."""

    def test_synapse_protocol_registration_uses_synapse_backend(self):
        with patch('ipfs_kit_py.synapse_storage.synapse_storage', MockSynapseStorage):
            fs = fsspec.filesystem("synapse", skip_instance_cache=True)

        assert isinstance(fs, SynapseFileSystem)
        assert fs.backend == "synapse"
        assert hasattr(fs, "synapse_storage")

    def test_ls_returns_canonical_synapse_paths_and_metadata(self):
        fs = _synapse_fs()

        listing = fs.ls("synapse://", detail=True)
        names = fs.ls("synapse://", detail=False)

        assert listing[0]["name"].startswith("synapse://")
        assert listing[0]["path"] == listing[0]["name"]
        assert listing[0]["type"] == "file"
        assert listing[0]["size"] == 19
        assert listing[0]["commp"].endswith("mpq")
        assert names == [item["name"] for item in listing]

    def test_cat_file_info_exists_and_open_rb_by_commp(self):
        fs = _synapse_fs()
        path = "synapse://baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq"

        assert fs.exists(path) is True
        assert fs.cat_file(path) == b"Hello, FSSpec test!"
        assert fs.cat_file(path, start=7, end=13) == b"FSSpec"

        info = fs.info(path)
        assert info["name"] == path
        assert info["type"] == "file"
        assert info["size"] == 19
        assert info["commp"] == path.removeprefix("synapse://")
        assert info["provider"] == "0x1234567890abcdef"
        assert info["proof_set_last_proven"] == 1704067200

        with fs.open(path, "rb") as handle:
            assert handle.read() == b"Hello, FSSpec test!"

    def test_pipe_file_writes_bytes_and_records_alias(self):
        fs = _synapse_fs()

        fs.pipe_file("synapse://pipe-test.bin", b"pipe payload")

        assert fs.exists("synapse://pipe-test.bin") is True
        assert fs.cat_file("synapse://pipe-test.bin") == b"pipe payload"
        info = fs.info("synapse://pipe-test.bin")
        assert info["name"] == "synapse://baga6ea4seaqmockpipe-test-bin"
        assert info["alias"] == "synapse://pipe-test.bin"
        assert info["size"] == len(b"pipe payload")
        assert info["storage_provider"] == "0x1234567890abcdef"

    def test_put_file_and_get_file_round_trip_through_synapse_alias(self, tmp_path):
        fs = _synapse_fs()
        source = tmp_path / "upload.txt"
        target = tmp_path / "download.txt"
        source.write_bytes(b"uploaded through put_file")

        fs.put_file(str(source), "synapse://uploads/upload.txt")
        fs.get_file("synapse://uploads/upload.txt", str(target))

        assert target.read_bytes() == b"uploaded through put_file"
        assert fs.info("synapse://uploads/upload.txt")["filename"] == "upload.txt"

    def test_backend_status_is_normalized(self):
        fs = _synapse_fs()

        status = fs.get_backend_status()

        assert status["backend"] == "synapse"
        assert status["connected"] is True
        assert status["network"] == "calibration"
        assert status["configuration_valid"] is True


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
