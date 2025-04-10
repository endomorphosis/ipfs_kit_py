"""
Tests for tiered storage backend integration.

This module tests the integration of multiple storage backends with the adaptive replacement cache:
- S3
- Storacha
- Filecoin
- HuggingFace
- Lassie
- IPFS

It verifies interoperability between tiers, and tests movement of content between backends.
"""

import os
import time
import uuid
import tempfile
import unittest
import pytest
from unittest.mock import patch, MagicMock

# Import tiered cache manager
from ipfs_kit_py.tiered_cache_manager import TieredCacheManager

# Import storage backends
from ipfs_kit_py.s3_kit import s3_kit
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.huggingface_kit import huggingface_kit, HUGGINGFACE_HUB_AVAILABLE
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.lassie_kit import lassie_kit, LASSIE_KIT_AVAILABLE

# Import MCP components
from ipfs_kit_py.mcp.models.storage_manager import StorageManager
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel


class TestTieredStorageBackends(unittest.TestCase):
    """Test integration of multiple storage backends with the ARC."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Configuration for the tiered cache manager
        self.cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB for testing
            'local_cache_size': 20 * 1024 * 1024,  # 20MB for testing
            'local_cache_path': os.path.join(self.temp_dir, 'cache'),
            'enable_memory_mapping': True,
            'enable_parquet_cache': True,
            'parquet_cache_path': os.path.join(self.temp_dir, 'parquet_cache'),
            'tiers': {
                "memory": {"type": "memory", "priority": 1},
                "disk": {"type": "disk", "priority": 2},
                "ipfs": {"type": "ipfs", "priority": 3},
                "ipfs_cluster": {"type": "ipfs_cluster", "priority": 4},
                "s3": {"type": "s3", "priority": 5},
                "storacha": {"type": "storacha", "priority": 6},
                "filecoin": {"type": "filecoin", "priority": 7},
                "huggingface": {"type": "huggingface", "priority": 8},
                "lassie": {"type": "lassie", "priority": 9}
            }
        }
        
        # Create mock backends
        self.ipfs = ipfs_kit()
        self.s3 = s3_kit()
        self.storacha = storacha_kit()
        if HUGGINGFACE_HUB_AVAILABLE:
            self.huggingface = huggingface_kit()
        if LASSIE_KIT_AVAILABLE:
            self.lassie = lassie_kit()
        
        # Initialize tiered cache manager with mock backends
        self.cache_manager = TieredCacheManager(config=self.cache_config)
        
        # Create test data
        self.test_content = b"Test content for tiered storage backend integration" * 100  # ~5KB
        self.test_cid = "QmTestContentHash123456789"
        
        # Create IPFS model for MCP testing
        self.ipfs_model = IPFSModel(self.ipfs, self.cache_manager)
        
        # Create storage manager
        self.storage_manager = StorageManager(
            ipfs_model=self.ipfs_model,
            cache_manager=self.cache_manager
        )
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_tier_functionality(self):
        """Test basic tier functionality."""
        # Store content in memory tier
        self.cache_manager.put(self.test_cid, self.test_content)
        
        # Verify it's in memory tier
        self.assertIn(self.test_cid, self.cache_manager.memory_cache.T1)
        
        # Get the content
        retrieved_content = self.cache_manager.get(self.test_cid)
        self.assertEqual(retrieved_content, self.test_content)
        
        # Check that metadata was created
        metadata = self.cache_manager.get_metadata(self.test_cid)
        self.assertIsNotNone(metadata)
        
        # Verify tier assignment
        self.assertIn("memory", metadata.get("storage_tier", ""))
    
    @patch('ipfs_kit_py.s3_kit.s3_kit.s3_ul_blob')
    @patch('ipfs_kit_py.s3_kit.s3_kit.s3_dl_blob')
    def test_tier_movement_to_s3(self, mock_s3_dl, mock_s3_ul):
        """Test movement of content to S3 tier."""
        # Setup mocks
        mock_s3_ul.return_value = {"success": True, "ETag": "test-etag"}
        mock_s3_dl.return_value = {"success": True, "Body": self.test_content}
        
        # Store content initially in memory/disk
        self.cache_manager.put(self.test_cid, self.test_content, {
            "source": "test",
            "mimetype": "text/plain",
            "filename": "test.txt"
        })
        
        # Simulate S3 storage
        # In a real implementation, this would be part of TieredCacheManager's move_to_tier method
        s3_backend = self.storage_manager.get_model("s3")
        if s3_backend:
            # Use S3 model to upload to S3
            upload_result = s3_backend.upload_from_memory(
                self.test_content,
                "test-bucket",
                self.test_cid,
                {"ipfs_cid": self.test_cid}
            )
            
            # Update metadata to indicate S3 storage
            self.cache_manager.update_metadata(self.test_cid, {
                "storage_tier": "s3",
                "s3_bucket": "test-bucket",
                "s3_key": self.test_cid,
                "s3_etag": upload_result.get("etag")
            })
            
            # Verify metadata was updated
            metadata = self.cache_manager.get_metadata(self.test_cid)
            self.assertEqual(metadata.get("storage_tier"), "s3")
            self.assertEqual(metadata.get("s3_bucket"), "test-bucket")
    
    @patch('ipfs_kit_py.storacha_kit.storacha_kit.upload_file')
    @patch('ipfs_kit_py.storacha_kit.storacha_kit.download_file')
    def test_tier_movement_to_storacha(self, mock_download, mock_upload):
        """Test movement of content to Storacha tier."""
        # Setup mocks
        mock_upload.return_value = {"success": True, "cid": self.test_cid}
        mock_download.return_value = {"success": True, "content": self.test_content}
        
        # Store content initially in memory/disk
        self.cache_manager.put(self.test_cid, self.test_content, {
            "source": "test",
            "mimetype": "text/plain",
            "filename": "test.txt"
        })
        
        # Simulate Storacha storage
        # In a real implementation, this would be part of TieredCacheManager's move_to_tier method
        storacha_backend = self.storage_manager.get_model("storacha")
        if storacha_backend:
            # Create a temporary file for the test content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(self.test_content)
                temp_path = temp_file.name
            
            # Use Storacha model to upload to Web3.Storage
            upload_result = storacha_backend.upload_file(
                temp_path,
                space_id="test-space",
                metadata={"ipfs_cid": self.test_cid}
            )
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            # Update metadata to indicate Storacha storage
            self.cache_manager.update_metadata(self.test_cid, {
                "storage_tier": "storacha",
                "storacha_space_id": "test-space",
                "storacha_upload_id": upload_result.get("upload_id"),
                "storacha_car_cid": upload_result.get("car_cid")
            })
            
            # Verify metadata was updated
            metadata = self.cache_manager.get_metadata(self.test_cid)
            self.assertEqual(metadata.get("storage_tier"), "storacha")
            self.assertEqual(metadata.get("storacha_space_id"), "test-space")
    
    def test_backend_interoperability(self):
        """Test all backends are interoperable for content movement."""
        # Implement a simplified version of content movement between backends
        
        # 1. First store in memory
        self.cache_manager.put(self.test_cid, self.test_content, {
            "source": "test",
            "mimetype": "text/plain",
            "filename": "test.txt",
            "storage_tier": "memory"
        })
        
        # 2. Check initial state
        metadata = self.cache_manager.get_metadata(self.test_cid)
        self.assertEqual(metadata.get("storage_tier"), "memory")
        
        # 3. Simulate movement to disk tier
        # In real implementation, this would use the move_to_tier method
        self.cache_manager.update_metadata(self.test_cid, {
            "storage_tier": "disk"
        })
        
        # 4. Check updated state
        metadata = self.cache_manager.get_metadata(self.test_cid)
        self.assertEqual(metadata.get("storage_tier"), "disk")
        
        # 5. Verify content is still accessible
        content = self.cache_manager.get(self.test_cid)
        self.assertEqual(content, self.test_content)
        
        # Note: Full backend tests would require actual implementations or more complex mocking
        # This test demonstrates the metadata tracking for tier movement

    @patch('ipfs_kit_py.mcp.models.storage_manager.StorageManager._init_storage_models')
    def test_mcp_integration(self, mock_init_models):
        """Test integration with MCP server."""
        # Create a simplified MCP server for testing
        # Mock storage models initialization to avoid actual backend calls
        mock_init_models.return_value = None
        
        # Create a storage manager with only the IPFS model
        storage_manager = StorageManager(
            ipfs_model=self.ipfs_model,
            cache_manager=self.cache_manager
        )
        
        # Mock the available storage models
        storage_manager.storage_models = {
            "s3": MagicMock(),
            "storacha": MagicMock(),
            "huggingface": MagicMock() if HUGGINGFACE_HUB_AVAILABLE else None,
            "lassie": MagicMock() if LASSIE_KIT_AVAILABLE else None
        }
        
        # Test backend availability
        backends = storage_manager.get_available_backends()
        self.assertTrue(backends["s3"])
        self.assertTrue(backends["storacha"])
        
        # Test that we can get models
        s3_model = storage_manager.get_model("s3")
        self.assertIsNotNone(s3_model)
        
        # Test get stats
        s3_model.get_stats = MagicMock(return_value={
            "operation_stats": {
                "total_operations": 10,
                "bytes_uploaded": 1024 * 1024,  # 1MB
                "bytes_downloaded": 2 * 1024 * 1024  # 2MB
            }
        })
        
        storacha_model = storage_manager.get_model("storacha")
        storacha_model.get_stats = MagicMock(return_value={
            "operation_stats": {
                "total_operations": 5,
                "bytes_uploaded": 512 * 1024,  # 0.5MB
                "bytes_downloaded": 1 * 1024 * 1024  # 1MB
            }
        })
        
        # Get aggregate stats
        stats = storage_manager.get_stats()
        self.assertEqual(stats["aggregate"]["total_operations"], 15)
        self.assertEqual(stats["aggregate"]["bytes_uploaded"], 1024 * 1024 + 512 * 1024)
        self.assertEqual(stats["aggregate"]["bytes_downloaded"], 2 * 1024 * 1024 + 1 * 1024 * 1024)


# Skip marker for environments without PyArrow
PYARROW_AVAILABLE = True
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    PYARROW_AVAILABLE = False


@pytest.mark.skipif(not PYARROW_AVAILABLE, reason="PyArrow not available")
class TestParquetIntegration(unittest.TestCase):
    """Test integration of Parquet and Arrow with the ARC."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Configuration for the tiered cache manager with Parquet enabled
        self.cache_config = {
            'memory_cache_size': 10 * 1024 * 1024,  # 10MB for testing
            'local_cache_size': 20 * 1024 * 1024,  # 20MB for testing
            'local_cache_path': os.path.join(self.temp_dir, 'cache'),
            'enable_memory_mapping': True,
            'enable_parquet_cache': True,
            'parquet_cache_path': os.path.join(self.temp_dir, 'parquet_cache'),
        }
        
        # Initialize tiered cache manager
        self.cache_manager = TieredCacheManager(config=self.cache_config)
        
        # Create test data
        self.test_content = b"Test content for Parquet integration" * 100
        self.test_cid = "QmTestParquetHash123456789"
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parquet_metadata_storage(self):
        """Test that metadata is stored in Parquet format."""
        # Skip if parquet cache isn't enabled
        if not self.cache_manager.parquet_cache:
            self.skipTest("ParquetCIDCache not available")
        
        # Store content with metadata
        self.cache_manager.put(self.test_cid, self.test_content, {
            "source": "test",
            "mimetype": "text/plain",
            "filename": "test.txt",
            "properties": {
                "test_property": "test_value",
                "related_cids": "QmRelated1,QmRelated2"
            }
        })
        
        # Verify metadata was stored in Parquet
        self.assertTrue(self.cache_manager.parquet_cache.contains(self.test_cid))
        
        # Retrieve and verify metadata
        metadata = self.cache_manager.parquet_cache.get_metadata(self.test_cid)
        self.assertEqual(metadata["mimetype"], "text/plain")
        self.assertEqual(metadata["filename"], "test.txt")
        self.assertEqual(metadata["properties"].get("test_property"), "test_value")
    
    def test_parquet_query_capability(self):
        """Test the query capability of ParquetCIDCache."""
        # Skip if parquet cache isn't enabled
        if not self.cache_manager.parquet_cache:
            self.skipTest("ParquetCIDCache not available")
        
        # Store multiple content items with different metadata
        for i in range(5):
            cid = f"QmTest{i}Hash123456789"
            content = f"Test content {i}".encode() * 100
            mimetype = "text/plain" if i % 2 == 0 else "application/json"
            
            self.cache_manager.put(cid, content, {
                "source": f"source{i//2}",
                "mimetype": mimetype,
                "filename": f"test{i}.{'txt' if i % 2 == 0 else 'json'}",
                "size_bytes": len(content),
                "properties": {
                    "index": i,
                    "even": (i % 2 == 0)
                }
            })
        
        # Query by MIME type
        result = self.cache_manager.query_metadata([("mimetype", "==", "text/plain")])
        self.assertTrue(result.get("success", False))
        self.assertEqual(len(result.get("results", [])), 3)  # i=0,2,4
        
        # Query by source
        result = self.cache_manager.query_metadata([("source", "==", "source0")])
        self.assertTrue(result.get("success", False))
        self.assertEqual(len(result.get("results", [])), 2)  # i=0,1
        
        # Query by property
        result = self.cache_manager.query_metadata([("properties.even", "==", True)])
        self.assertTrue(result.get("success", False))
        self.assertEqual(len(result.get("results", [])), 3)  # i=0,2,4
        
        # Compound query
        result = self.cache_manager.query_metadata([
            ("mimetype", "==", "text/plain"),
            ("source", "==", "source0")
        ])
        self.assertTrue(result.get("success", False))
        self.assertEqual(len(result.get("results", [])), 1)  # i=0 only


if __name__ == "__main__":
    unittest.main()