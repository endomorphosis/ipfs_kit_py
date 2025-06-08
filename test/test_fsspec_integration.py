"""
Comprehensive test suite for FSSpec integration.

This module contains tests for the FSSpec filesystem interface
that allows IPFS to be used as a standard file system in data science workloads.
"""

import os
import sys
import pytest
import tempfile
import logging
from pathlib import Path
import io
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Skip if fsspec is not available
pytest.importorskip("fsspec", reason="fsspec is not installed")

# Try to import the modules we need
try:
    from ipfs_kit_py.fsspec_integration import IPFSFileSystem
except ImportError as e:
    logger.error(f"Error importing FSSpec integration: {e}")
    # Create a mock class for testing
    class IPFSFileSystem:
        def __init__(self, api_url=None, gateway_url=None, **kwargs):
            self.api_url = api_url
            self.gateway_url = gateway_url
            self.kwargs = kwargs
            self._mock_fs = {}
        
        def _make_path(self, path):
            if path.startswith("ipfs://"):
                return path[7:]
            return path
        
        def info(self, path):
            path = self._make_path(path)
            if path in self._mock_fs:
                return {"name": path, "size": len(self._mock_fs[path]), "type": "file"}
            elif path + "/" in self._mock_fs:
                return {"name": path, "size": 0, "type": "directory"}
            raise FileNotFoundError(f"No such file or directory: {path}")
        
        def ls(self, path, **kwargs):
            path = self._make_path(path)
            result = []
            path_prefix = path + "/"
            for key in self._mock_fs:
                if key.startswith(path_prefix) and "/" not in key[len(path_prefix):]:
                    result.append({"name": key, "size": len(self._mock_fs[key]), "type": "file"})
            return result
        
        def open(self, path, mode="rb", **kwargs):
            path = self._make_path(path)
            if mode.startswith("r"):
                if path not in self._mock_fs:
                    raise FileNotFoundError(f"No such file: {path}")
                return io.BytesIO(self._mock_fs[path])
            elif mode.startswith("w"):
                self._mock_fs[path] = b""
                return io.BytesIO(self._mock_fs[path])
            else:
                raise ValueError(f"Unsupported mode: {mode}")
        
        def put_file(self, lpath, rpath, **kwargs):
            with open(lpath, "rb") as f:
                self._mock_fs[self._make_path(rpath)] = f.read()
        
        def get_file(self, rpath, lpath, **kwargs):
            with open(lpath, "wb") as f:
                f.write(self._mock_fs[self._make_path(rpath)])

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture
def mock_ipfs_client():
    """Create a mocked IPFS client."""
    mock = MagicMock()
    mock.add.return_value = {"Hash": "QmTestHash"}
    mock.cat.return_value = b"test content"
    return mock

@pytest.fixture
def test_fs():
    """Create a test IPFSFileSystem instance."""
    with patch('ipfs_kit_py.fsspec_integration.ipfs') as mock_ipfs_class:
        mock_instance = MagicMock()
        mock_instance.add.return_value = {"Hash": "QmTestHash"}
        mock_instance.cat.return_value = b"test content"
        mock_ipfs_class.return_value = mock_instance
        
        fs = IPFSFileSystem(api_url="http://localhost:5001/api/v0", test_mode=True)
        yield fs

# Test FSSpec Integration
class TestFSSpecIntegration:
    
    def test_fs_init(self):
        """Test filesystem initialization."""
        with patch('ipfs_kit_py.fsspec_integration.ipfs') as mock_ipfs_class:
            fs = IPFSFileSystem(api_url="http://localhost:5001/api/v0", test_mode=True)
            assert fs is not None
            mock_ipfs_class.assert_called_once()
    
    def test_fs_open_read(self, test_fs):
        """Test opening a file for reading."""
        with patch.object(test_fs, '_cat_file', return_value=b"test content"):
            with test_fs.open("ipfs://QmTestHash", "rb") as f:
                content = f.read()
                assert content == b"test content"
    
    def test_fs_open_write(self, test_fs):
        """Test opening a file for writing."""
        with patch.object(test_fs, '_add_file', return_value="QmNewHash"):
            with test_fs.open("ipfs://test_file.txt", "wb") as f:
                f.write(b"test write content")
            
            # Since writing to IPFS is immutable, we expect _add_file to be called
            test_fs._add_file.assert_called_once()
    
    def test_fs_exists(self, test_fs):
        """Test checking if a file exists."""
        with patch.object(test_fs, '_cat_file', side_effect=[b"content", FileNotFoundError()]):
            assert test_fs.exists("ipfs://QmTestHash") is True
            assert test_fs.exists("ipfs://QmNonExistent") is False
    
    def test_fs_info(self, test_fs):
        """Test getting file info."""
        test_info = {"name": "QmTestHash", "size": 12, "type": "file"}
        
        with patch.object(test_fs, '_get_file_info', return_value=test_info):
            info = test_fs.info("ipfs://QmTestHash")
            assert info == test_info
    
    def test_fs_ls(self, test_fs):
        """Test listing directory contents."""
        test_listing = [
            {"name": "QmDir/file1", "size": 10, "type": "file"},
            {"name": "QmDir/file2", "size": 20, "type": "file"}
        ]
        
        with patch.object(test_fs, '_ls_directory', return_value=test_listing):
            listing = test_fs.ls("ipfs://QmDir")
            assert listing == test_listing
    
    def test_fs_put_get(self, test_fs, temp_dir):
        """Test putting and getting files."""
        # Create a test file
        test_file = temp_dir / "test_put.txt"
        test_file.write_text("test put content")
        
        # Mock the put function
        with patch.object(test_fs, '_put_file', return_value="QmPutHash"):
            # Put the file
            test_fs.put_file(str(test_file), "ipfs://test_put.txt")
            test_fs._put_file.assert_called_once()
        
        # Create an output file for get
        output_file = temp_dir / "test_get.txt"
        
        # Mock the get function
        with patch.object(test_fs, '_get_file', return_value=None):
            # Get the file
            test_fs.get_file("ipfs://QmTestHash", str(output_file))
            test_fs._get_file.assert_called_once()

# Test integration with data science libraries (pandas, pyarrow)
@pytest.mark.parametrize("lib_name", ["pandas", "pyarrow"])
def test_data_science_integration(lib_name):
    """Test integration with data science libraries."""
    try:
        if lib_name == "pandas":
            pandas = pytest.importorskip("pandas")
            with patch('ipfs_kit_py.fsspec_integration.IPFSFileSystem') as mock_fs_class:
                # Mock the filesystem
                mock_fs = MagicMock()
                mock_fs.open.return_value = io.StringIO("col1,col2\n1,2\n3,4")
                mock_fs_class.return_value = mock_fs
                
                # Test with pandas
                df = pandas.read_csv("ipfs://QmTestCSV")
                assert df is not None
                assert list(df.columns) == ["col1", "col2"]
                assert len(df) == 2
        
        elif lib_name == "pyarrow":
            pa = pytest.importorskip("pyarrow")
            fs = pytest.importorskip("pyarrow.fs")
            with patch('ipfs_kit_py.fsspec_integration.IPFSFileSystem') as mock_fs_class:
                # Mock the filesystem
                mock_fs = MagicMock()
                mock_fs_class.return_value = mock_fs
                
                # Test with pyarrow
                ipfs_fs = fs.PyFileSystem(fs.FSSpecHandler(mock_fs))
                assert ipfs_fs is not None
    
    except (ImportError, ModuleNotFoundError):
        pytest.skip(f"{lib_name} is not installed")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
