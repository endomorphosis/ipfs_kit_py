"""
Test suite for ipfs_datasets_py integration in ipfs_kit_py.

This test validates:
1. Integration works when ipfs_datasets_py is available
2. Fallback behavior works when ipfs_datasets_py is not available
3. Filesystem journal properly logs dataset operations
4. Event and provenance logs are correctly maintained
5. CI/CD scenarios without the package are handled gracefully
"""

import os
import sys
import tempfile
import shutil
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ipfs_kit_py.ipfs_datasets_integration import (
    DatasetIPFSBackend,
    IPFSDatasetsManager,
    get_ipfs_datasets_manager,
    reset_manager,
    IPFS_DATASETS_AVAILABLE
)


class TestIPFSDatasetsIntegration(unittest.TestCase):
    """Test the ipfs_datasets integration module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_dataset = os.path.join(self.test_dir, "test_dataset.json")
        
        # Create a simple test dataset
        with open(self.test_dataset, 'w') as f:
            json.dump({"data": [1, 2, 3], "label": [0, 1, 0]}, f)
        
        # Reset manager singleton for clean tests
        reset_manager()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        reset_manager()
    
    def test_backend_initialization(self):
        """Test DatasetIPFSBackend initialization."""
        backend = DatasetIPFSBackend(base_path=self.test_dir)
        
        # Check that base path was created
        self.assertTrue(os.path.exists(backend.base_path))
        
        # Check availability reflects actual package status
        if IPFS_DATASETS_AVAILABLE:
            # If package is available, backend might be available
            # (depending on successful initialization)
            pass
        else:
            # If package not available, backend should not be available
            self.assertFalse(backend.is_available())
    
    def test_store_dataset_local_fallback(self):
        """Test dataset storage with local fallback."""
        backend = DatasetIPFSBackend(
            base_path=self.test_dir,
            enable_distributed=False  # Force local mode
        )
        
        metadata = {"description": "Test dataset", "version": "1.0"}
        result = backend.store_dataset(self.test_dataset, metadata)
        
        # Should succeed even without distributed mode
        self.assertTrue(result["success"])
        self.assertIn("local_path", result)
        self.assertFalse(result.get("distributed", True))
        self.assertEqual(result["metadata"]["description"], "Test dataset")
    
    def test_store_nonexistent_dataset(self):
        """Test storing a dataset that doesn't exist."""
        backend = DatasetIPFSBackend(base_path=self.test_dir)
        
        result = backend.store_dataset("/nonexistent/path.json")
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_load_dataset_local_path(self):
        """Test loading dataset from local path."""
        backend = DatasetIPFSBackend(base_path=self.test_dir)
        
        result = backend.load_dataset(self.test_dataset)
        
        # Should succeed for local path
        self.assertTrue(result["success"])
        self.assertIn("path", result)
        self.assertEqual(result["path"], str(self.test_dataset))
    
    def test_load_nonexistent_dataset(self):
        """Test loading a dataset that doesn't exist."""
        backend = DatasetIPFSBackend(base_path=self.test_dir)
        
        result = backend.load_dataset("/nonexistent/dataset.json")
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_version_dataset_local_fallback(self):
        """Test dataset versioning with local fallback."""
        backend = DatasetIPFSBackend(
            base_path=self.test_dir,
            enable_distributed=False
        )
        
        metadata = {"notes": "Fixed data quality issues"}
        result = backend.version_dataset(
            dataset_id="test-dataset",
            version="1.1.0",
            metadata=metadata
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["version"], "1.1.0")
        self.assertIn("metadata", result)
        self.assertFalse(result.get("distributed", True))
    
    def test_get_metadata_local(self):
        """Test metadata retrieval for local dataset."""
        backend = DatasetIPFSBackend(base_path=self.test_dir)
        
        # Create a metadata file
        metadata_path = Path(self.test_dataset).with_suffix('.metadata.json')
        test_metadata = {"author": "test", "created": "2024-01-01"}
        with open(metadata_path, 'w') as f:
            json.dump(test_metadata, f)
        
        result = backend.get_metadata(self.test_dataset)
        
        self.assertTrue(result["success"])
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["author"], "test")
    
    def test_manager_initialization(self):
        """Test IPFSDatasetsManager initialization."""
        manager = IPFSDatasetsManager(enable=False)
        
        # Manager should be created even without distributed mode
        self.assertIsNotNone(manager)
        self.assertFalse(manager.is_available())
        self.assertEqual(len(manager.event_log), 0)
        self.assertEqual(len(manager.provenance_log), 0)
    
    def test_manager_store_with_event_logging(self):
        """Test that manager logs events when storing datasets."""
        manager = IPFSDatasetsManager(enable=False)
        
        result = manager.store(self.test_dataset, {"test": "metadata"})
        
        # Check operation result
        self.assertTrue(result["success"])
        
        # Check event log
        event_log = manager.get_event_log()
        self.assertEqual(len(event_log), 1)
        self.assertEqual(event_log[0]["operation"], "store")
        self.assertEqual(event_log[0]["path"], str(self.test_dataset))
        self.assertTrue(event_log[0]["success"])
    
    def test_manager_version_with_provenance_logging(self):
        """Test that manager logs provenance when versioning datasets."""
        manager = IPFSDatasetsManager(enable=False)
        
        result = manager.version(
            dataset_id="test-ds",
            version="2.0.0",
            parent_version="1.0.0",
            transformations=["normalize", "augment"]
        )
        
        # Check operation result
        self.assertTrue(result["success"])
        
        # Check provenance log
        prov_log = manager.get_provenance_log()
        self.assertEqual(len(prov_log), 1)
        self.assertEqual(prov_log[0]["dataset_id"], "test-ds")
        self.assertEqual(prov_log[0]["version"], "2.0.0")
        self.assertEqual(prov_log[0]["parent_version"], "1.0.0")
        self.assertEqual(len(prov_log[0]["transformations"]), 2)
    
    def test_singleton_manager(self):
        """Test that get_ipfs_datasets_manager returns singleton."""
        manager1 = get_ipfs_datasets_manager(enable=False)
        manager2 = get_ipfs_datasets_manager(enable=False)
        
        # Should be the same instance
        self.assertIs(manager1, manager2)
        
        # Reset and get new instance
        reset_manager()
        manager3 = get_ipfs_datasets_manager(enable=False)
        
        # Should be a different instance
        self.assertIsNot(manager1, manager3)
    
    def test_ci_cd_graceful_degradation(self):
        """Test that system works gracefully when ipfs_datasets_py is not available."""
        # This simulates CI/CD environment without the package
        backend = DatasetIPFSBackend(
            base_path=self.test_dir,
            enable_distributed=True  # Request distributed mode
        )
        
        # Operations should still work with local fallback
        result = backend.store_dataset(self.test_dataset)
        self.assertTrue(result["success"])
        self.assertIn("local_path", result)
        
        # Availability should correctly reflect package status
        if not IPFS_DATASETS_AVAILABLE:
            self.assertFalse(backend.is_available())
            # When distributed is False, there might or might not be a message
            # Just check that it falls back correctly
            self.assertFalse(result.get("distributed", True))


class TestFilesystemJournalIntegration(unittest.TestCase):
    """Test filesystem journal integration with ipfs_datasets."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.journal_dir = os.path.join(self.test_dir, "journal")
        self.test_dataset = os.path.join(self.test_dir, "dataset.json")
        
        # Create test dataset
        with open(self.test_dataset, 'w') as f:
            json.dump({"data": [1, 2, 3]}, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_journal_with_ipfs_datasets_disabled(self):
        """Test filesystem journal without ipfs_datasets integration."""
        from ipfs_kit_py.filesystem_journal import FilesystemJournal
        
        journal = FilesystemJournal(
            base_path=self.journal_dir,
            enable_ipfs_datasets=False
        )
        
        # Dataset operations should still work with local fallback
        result = journal.store_dataset(self.test_dataset, {"test": "metadata"})
        
        self.assertTrue(result["success"])
        self.assertFalse(result.get("distributed", True))
        
        # Check that journal entry was created
        self.assertGreater(len(journal.journal_entries), 0)
        
        journal.close()
    
    def test_journal_dataset_event_log(self):
        """Test that journal maintains dataset event log."""
        from ipfs_kit_py.filesystem_journal import FilesystemJournal
        
        journal = FilesystemJournal(
            base_path=self.journal_dir,
            enable_ipfs_datasets=False
        )
        
        # Perform dataset operations
        journal.store_dataset(self.test_dataset, {"version": "1.0"})
        journal.version_dataset("test-ds", "1.1.0", parent_version="1.0")
        
        # Get event log
        events = journal.get_dataset_event_log()
        
        # Should have at least the store operation logged
        self.assertGreater(len(events), 0)
        
        journal.close()
    
    def test_journal_provenance_tracking(self):
        """Test that journal tracks dataset provenance."""
        from ipfs_kit_py.filesystem_journal import FilesystemJournal
        
        journal = FilesystemJournal(
            base_path=self.journal_dir,
            enable_ipfs_datasets=False
        )
        
        # Create versioned dataset with lineage
        journal.version_dataset(
            dataset_id="test-ds",
            version="2.0.0",
            parent_version="1.0.0",
            transformations=["clean", "transform"],
            metadata={"notes": "Major update"}
        )
        
        # Get provenance log
        prov_log = journal.get_dataset_provenance_log()
        
        # Should have provenance entry
        self.assertGreater(len(prov_log), 0)
        entry = prov_log[0]
        self.assertEqual(entry["dataset_id"], "test-ds")
        self.assertEqual(entry["version"], "2.0.0")
        self.assertEqual(entry["parent_version"], "1.0.0")
        self.assertEqual(len(entry["transformations"]), 2)
        
        journal.close()


def run_tests():
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add tests
    suite.addTests(loader.loadTestsFromTestCase(TestIPFSDatasetsIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFilesystemJournalIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
