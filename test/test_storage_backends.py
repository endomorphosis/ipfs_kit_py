"""
Comprehensive test suite for storage backends.

This module contains tests for the various storage backends supported
by IPFS Kit, including IPFS, S3, and tiered storage.
"""

import os
import sys
import pytest
import tempfile
import logging
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the modules we need
try:
    from ipfs_kit_py.mcp.storage_manager import BackendStorage
    from ipfs_kit_py.mcp.storage_manager.backends import IPFSBackend, S3Backend
    from ipfs_kit_py.mcp.storage_manager.tiered_storage import TieredStorage
    from ipfs_kit_py.mcp.storage_manager.cache_manager import CacheManager
except ImportError as e:
    logger.error(f"Error importing storage modules: {e}")
    # Create mock versions for testing
    class BackendStorage:
        def __init__(self, config=None):
            self.config = config or {}
            self.backends = {}
            self.default_backend = None
            
            if config and "storage" in config:
                for backend in config["storage"].get("backends", []):
                    backend_id = backend.get("id", "default")
                    self.backends[backend_id] = MagicMock()
                
                self.default_backend = config["storage"].get("default_backend")
        
        def get(self, cid, backend_id=None):
            backend_id = backend_id or self.default_backend
            if backend_id in self.backends:
                return self.backends[backend_id].get(cid)
            return None
        
        def put(self, content, backend_id=None):
            backend_id = backend_id or self.default_backend
            if backend_id in self.backends:
                return self.backends[backend_id].put(content)
            return None
    
    class IPFSBackend:
        def __init__(self, config):
            self.config = config
        
        def get(self, cid):
            return b"test content"
        
        def put(self, content):
            return "QmTestCID"
    
    class S3Backend:
        def __init__(self, config):
            self.config = config
        
        def get(self, key):
            return b"s3 test content"
        
        def put(self, content):
            return "s3-test-key"
    
    class TieredStorage:
        def __init__(self, backends=None, cache_config=None):
            self.backends = backends or {}
            self.cache = CacheManager(cache_config)
        
        def get(self, cid):
            return b"tiered content"
        
        def put(self, content):
            return "QmTieredCID"
    
    class CacheManager:
        def __init__(self, config=None):
            self.config = config or {}
            self.cache = {}
        
        def get(self, key):
            return self.cache.get(key)
        
        def put(self, key, value):
            self.cache[key] = value
            return key

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname)

@pytest.fixture
def test_content():
    """Create test content for storage tests."""
    return b"Test content for storage backends"

@pytest.fixture
def test_storage_config(temp_dir):
    """Create a test storage configuration."""
    config_path = temp_dir / "storage_config.json"
    config = {
        "storage": {
            "backends": [
                {
                    "type": "ipfs",
                    "id": "local",
                    "api_url": "http://localhost:5001/api/v0",
                    "gateway_url": "http://localhost:8080/ipfs"
                },
                {
                    "type": "s3",
                    "id": "test-s3",
                    "endpoint_url": "http://localhost:9000",
                    "access_key": "test",
                    "secret_key": "test",
                    "bucket": "test-bucket"
                }
            ],
            "default_backend": "local",
            "tiered": {
                "enabled": True,
                "cache_size": 1024 * 1024 * 100,  # 100MB
                "cache_policy": "lru",
                "tiers": [
                    {
                        "backend_id": "local",
                        "priority": 1
                    },
                    {
                        "backend_id": "test-s3",
                        "priority": 2
                    }
                ]
            }
        }
    }
    
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    return config_path

# Test Storage Manager
class TestStorageManager:
    
    def test_backend_storage_init(self, test_storage_config):
        """Test initializing BackendStorage."""
        with open(test_storage_config) as f:
            config = json.load(f)
        
        with patch('ipfs_kit_py.mcp.storage_manager.backend_registry') as mock_registry:
            mock_registry.get_backend.side_effect = lambda backend_type, backend_config: MagicMock()
            
            storage = BackendStorage(config)
            
            assert storage is not None
            assert "local" in storage.backends
            assert "test-s3" in storage.backends
            assert storage.default_backend == "local"
    
    def test_backend_storage_get(self, test_storage_config):
        """Test BackendStorage.get()."""
        with open(test_storage_config) as f:
            config = json.load(f)
        
        with patch('ipfs_kit_py.mcp.storage_manager.backend_registry') as mock_registry:
            mock_backend = MagicMock()
            mock_backend.get.return_value = b"test content"
            mock_registry.get_backend.return_value = mock_backend
            
            storage = BackendStorage(config)
            content = storage.get("QmTestCID")
            
            assert content == b"test content"
            mock_backend.get.assert_called_once_with("QmTestCID")
    
    def test_backend_storage_put(self, test_storage_config, test_content):
        """Test BackendStorage.put()."""
        with open(test_storage_config) as f:
            config = json.load(f)
        
        with patch('ipfs_kit_py.mcp.storage_manager.backend_registry') as mock_registry:
            mock_backend = MagicMock()
            mock_backend.put.return_value = "QmTestCID"
            mock_registry.get_backend.return_value = mock_backend
            
            storage = BackendStorage(config)
            cid = storage.put(test_content)
            
            assert cid == "QmTestCID"
            mock_backend.put.assert_called_once_with(test_content)

# Test IPFS Backend
class TestIPFSBackend:
    
    @patch('ipfs_kit_py.mcp.storage_manager.backends.ipfs.ipfs')
    def test_ipfs_backend_init(self, mock_ipfs_class):
        """Test initializing IPFSBackend."""
        config = {
            "api_url": "http://localhost:5001/api/v0",
            "gateway_url": "http://localhost:8080/ipfs"
        }
        
        backend = IPFSBackend(config)
        
        assert backend is not None
        mock_ipfs_class.assert_called_once()
    
    @patch('ipfs_kit_py.mcp.storage_manager.backends.ipfs.ipfs')
    def test_ipfs_backend_get(self, mock_ipfs_class):
        """Test IPFSBackend.get()."""
        mock_ipfs_instance = MagicMock()
        mock_ipfs_instance.cat.return_value = b"test content"
        mock_ipfs_class.return_value = mock_ipfs_instance
        
        config = {
            "api_url": "http://localhost:5001/api/v0",
            "gateway_url": "http://localhost:8080/ipfs"
        }
        
        backend = IPFSBackend(config)
        content = backend.get("QmTestCID")
        
        assert content == b"test content"
        mock_ipfs_instance.cat.assert_called_once_with("QmTestCID")
    
    @patch('ipfs_kit_py.mcp.storage_manager.backends.ipfs.ipfs')
    def test_ipfs_backend_put(self, mock_ipfs_class, test_content):
        """Test IPFSBackend.put()."""
        mock_ipfs_instance = MagicMock()
        mock_ipfs_instance.add.return_value = {"Hash": "QmTestCID"}
        mock_ipfs_class.return_value = mock_ipfs_instance
        
        config = {
            "api_url": "http://localhost:5001/api/v0",
            "gateway_url": "http://localhost:8080/ipfs"
        }
        
        backend = IPFSBackend(config)
        cid = backend.put(test_content)
        
        assert cid == "QmTestCID"
        mock_ipfs_instance.add.assert_called_once()

# Test S3 Backend
@pytest.mark.requires_s3
class TestS3Backend:
    
    @patch('boto3.client')
    def test_s3_backend_init(self, mock_boto3_client):
        """Test initializing S3Backend."""
        config = {
            "endpoint_url": "http://localhost:9000",
            "access_key": "test",
            "secret_key": "test",
            "bucket": "test-bucket"
        }
        
        backend = S3Backend(config)
        
        assert backend is not None
        mock_boto3_client.assert_called_once_with(
            's3',
            endpoint_url=config["endpoint_url"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"]
        )
    
    @patch('boto3.client')
    def test_s3_backend_get(self, mock_boto3_client):
        """Test S3Backend.get()."""
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"s3 test content")
        }
        mock_boto3_client.return_value = mock_s3_client
        
        config = {
            "endpoint_url": "http://localhost:9000",
            "access_key": "test",
            "secret_key": "test",
            "bucket": "test-bucket"
        }
        
        backend = S3Backend(config)
        content = backend.get("test-key")
        
        assert content == b"s3 test content"
        mock_s3_client.get_object.assert_called_once_with(
            Bucket=config["bucket"],
            Key="test-key"
        )
    
    @patch('boto3.client')
    def test_s3_backend_put(self, mock_boto3_client, test_content):
        """Test S3Backend.put()."""
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        config = {
            "endpoint_url": "http://localhost:9000",
            "access_key": "test",
            "secret_key": "test",
            "bucket": "test-bucket"
        }
        
        backend = S3Backend(config)
        key = backend.put(test_content)
        
        assert key is not None
        mock_s3_client.put_object.assert_called_once()

# Test Tiered Storage
class TestTieredStorage:
    
    def test_tiered_storage_init(self):
        """Test initializing TieredStorage."""
        backends = {
            "local": MagicMock(),
            "s3": MagicMock()
        }
        
        cache_config = {
            "size": 1024 * 1024 * 100,
            "policy": "lru"
        }
        
        storage = TieredStorage(backends, cache_config)
        
        assert storage is not None
        assert storage.backends == backends
        assert storage.cache is not None
    
    def test_tiered_storage_get_from_cache(self):
        """Test TieredStorage.get() with cache hit."""
        backends = {
            "local": MagicMock(),
            "s3": MagicMock()
        }
        
        mock_cache = MagicMock()
        mock_cache.get.return_value = b"cached content"
        
        with patch('ipfs_kit_py.mcp.storage_manager.tiered_storage.CacheManager', return_value=mock_cache):
            storage = TieredStorage(backends)
            content = storage.get("QmTestCID")
            
            assert content == b"cached content"
            mock_cache.get.assert_called_once_with("QmTestCID")
            # Backend should not be called if cache hit
            backends["local"].get.assert_not_called()
    
    def test_tiered_storage_get_from_backend(self):
        """Test TieredStorage.get() with cache miss."""
        backends = {
            "local": MagicMock(get=MagicMock(return_value=b"backend content")),
            "s3": MagicMock()
        }
        
        mock_cache = MagicMock()
        mock_cache.get.return_value = None  # Cache miss
        
        with patch('ipfs_kit_py.mcp.storage_manager.tiered_storage.CacheManager', return_value=mock_cache):
            storage = TieredStorage(backends, tier_config={"tiers": [{"backend_id": "local", "priority": 1}]})
            content = storage.get("QmTestCID")
            
            assert content == b"backend content"
            mock_cache.get.assert_called_once_with("QmTestCID")
            backends["local"].get.assert_called_once_with("QmTestCID")
            mock_cache.put.assert_called_once_with("QmTestCID", b"backend content")
    
    def test_tiered_storage_put(self, test_content):
        """Test TieredStorage.put()."""
        backends = {
            "local": MagicMock(put=MagicMock(return_value="QmLocalCID")),
            "s3": MagicMock(put=MagicMock(return_value="s3-test-key"))
        }
        
        mock_cache = MagicMock()
        
        with patch('ipfs_kit_py.mcp.storage_manager.tiered_storage.CacheManager', return_value=mock_cache):
            storage = TieredStorage(backends, tier_config={"tiers": [{"backend_id": "local", "priority": 1}]})
            cid = storage.put(test_content)
            
            assert cid == "QmLocalCID"
            backends["local"].put.assert_called_once_with(test_content)
            mock_cache.put.assert_called_once_with("QmLocalCID", test_content)

if __name__ == "__main__":
    pytest.main(["-v", __file__])
