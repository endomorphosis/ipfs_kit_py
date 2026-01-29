"""
Test suite for VFS bucket GraphRAG integration.

This test validates the integration between ipfs_datasets_py and VFS buckets
for GraphRAG indexing of virtual filesystems.
"""

import os
import sys
import tempfile
import shutil
import json
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ipfs_kit_py.vfs_bucket_graphrag_integration import (
    VFSBucketGraphRAGIndexer,
    get_vfs_bucket_graphrag_indexer,
    reset_indexer
)


class TestVFSBucketGraphRAGIndexer(unittest.TestCase):
    """Test the VFS bucket GraphRAG indexing integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.index_dir = os.path.join(self.test_dir, "vfs_index")
        
        # Reset singleton
        reset_indexer()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        reset_indexer()
    
    def test_indexer_initialization(self):
        """Test VFSBucketGraphRAGIndexer initialization."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Check that indexer was created
        self.assertIsNotNone(indexer)
        self.assertTrue(os.path.exists(indexer.base_path))
    
    def test_is_available(self):
        """Test availability check."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Should report availability status
        result = indexer.is_available()
        self.assertIsInstance(result, bool)
    
    def test_snapshot_bucket_without_manager(self):
        """Test snapshot creation without bucket manager."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        result = indexer.snapshot_bucket("test-bucket")
        
        # Should fail gracefully
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_index_persistence(self):
        """Test that bucket index persists."""
        # Create indexer and add to index
        indexer1 = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Manually add to index
        indexer1.bucket_index["test-bucket"] = {
            "dataset_id": "vfs_bucket_test-bucket",
            "version": "1.0"
        }
        indexer1._save_index()
        
        # Create new indexer with same base_path
        indexer2 = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Should have loaded the previous index
        self.assertIn("test-bucket", indexer2.bucket_index)
        self.assertEqual(
            indexer2.bucket_index["test-bucket"]["dataset_id"],
            "vfs_bucket_test-bucket"
        )
    
    def test_list_indexed_buckets(self):
        """Test listing indexed buckets."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Add some buckets to index
        indexer.bucket_index["bucket1"] = {"dataset_id": "ds1"}
        indexer.bucket_index["bucket2"] = {"dataset_id": "ds2"}
        
        # List buckets
        buckets = indexer.list_indexed_buckets()
        
        self.assertEqual(len(buckets), 2)
        self.assertIn("bucket1", buckets)
        self.assertIn("bucket2", buckets)
    
    def test_get_bucket_snapshot_info(self):
        """Test retrieving bucket snapshot information."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Add bucket info
        indexer.bucket_index["test-bucket"] = {
            "dataset_id": "vfs_bucket_test-bucket",
            "version": "1.0",
            "last_snapshot": "2024-01-28T00:00:00"
        }
        
        # Get info
        info = indexer.get_bucket_snapshot_info("test-bucket")
        
        self.assertIsNotNone(info)
        self.assertEqual(info["dataset_id"], "vfs_bucket_test-bucket")
        self.assertEqual(info["version"], "1.0")
        
        # Non-existent bucket
        none_info = indexer.get_bucket_snapshot_info("nonexistent")
        self.assertIsNone(none_info)
    
    def test_search_buckets_simple(self):
        """Test simple bucket search."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Add buckets to index
        indexer.bucket_index["ml-training-data"] = {
            "dataset_id": "ds1",
            "last_snapshot": "2024-01-28T00:00:00"
        }
        indexer.bucket_index["web-assets"] = {
            "dataset_id": "ds2",
            "last_snapshot": "2024-01-28T00:00:00"
        }
        
        # Search
        results = indexer.search_buckets("training")
        
        # Should find the ML bucket
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["bucket_name"], "ml-training-data")
    
    def test_singleton_indexer(self):
        """Test singleton pattern."""
        indexer1 = get_vfs_bucket_graphrag_indexer(
            ipfs_client=None,
            enable_graphrag=False
        )
        
        indexer2 = get_vfs_bucket_graphrag_indexer(
            ipfs_client=None,
            enable_graphrag=False
        )
        
        # Should be the same instance
        self.assertIs(indexer1, indexer2)
        
        # Reset and get new instance
        reset_indexer()
        indexer3 = get_vfs_bucket_graphrag_indexer(
            ipfs_client=None,
            enable_graphrag=False
        )
        
        # Should be a different instance
        self.assertIsNot(indexer1, indexer3)
    
    def test_export_bucket_structure(self):
        """Test bucket structure export."""
        indexer = VFSBucketGraphRAGIndexer(
            bucket_manager=None,
            ipfs_client=None,
            enable_graphrag=False,
            base_path=self.index_dir
        )
        
        # Export structure (will be empty without actual bucket)
        structure = indexer._export_bucket_structure("test-bucket")
        
        # Check structure
        self.assertEqual(structure["bucket_name"], "test-bucket")
        self.assertIn("exported_at", structure)
        self.assertIn("files", structure)
        self.assertIn("metadata", structure)
        self.assertIn("statistics", structure)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestVFSBucketGraphRAGIndexer))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
