"""
Test Suite for ipfs_datasets_py and ipfs_accelerate_py Integration in VFS Systems

Tests the integration of distributed dataset storage and compute acceleration
across all VFS-related modules including bucket management, version tracking,
and indexing systems.
"""

import unittest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVFSIntegration(unittest.TestCase):
    """Test VFS integration with ipfs_datasets_py and ipfs_accelerate_py."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_bucket_vfs_manager_integration(self):
        """Test BucketVFSManager has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.bucket_vfs_manager import BucketVFSManager, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check manager can be initialized with integration params
            manager = BucketVFSManager(
                storage_path=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(manager, 'enable_dataset_storage'))
            self.assertTrue(hasattr(manager, 'enable_compute_layer'))
            
            print(f"✓ BucketVFSManager integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"BucketVFSManager not available: {e}")
    
    def test_vfs_manager_integration(self):
        """Test VFSManager has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.vfs_manager import VFSManager, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check manager can be initialized with integration params
            manager = VFSManager(
                storage_path=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(manager, 'enable_dataset_storage'))
            self.assertTrue(hasattr(manager, 'enable_compute_layer'))
            
            print(f"✓ VFSManager integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"VFSManager not available: {e}")
    
    def test_vfs_version_tracker_integration(self):
        """Test VFSVersionTracker has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.vfs_version_tracker import VFSVersionTracker, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check tracker can be initialized with integration params
            tracker = VFSVersionTracker(
                vfs_root=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(tracker, 'enable_dataset_storage'))
            self.assertTrue(hasattr(tracker, 'enable_compute_layer'))
            
            print(f"✓ VFSVersionTracker integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"VFSVersionTracker not available: {e}")
    
    def test_enhanced_bucket_index_integration(self):
        """Test EnhancedBucketIndex has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.enhanced_bucket_index import EnhancedBucketIndex, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check index can be initialized with integration params
            index = EnhancedBucketIndex(
                index_dir=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(index, 'enable_dataset_storage'))
            self.assertTrue(hasattr(index, 'enable_compute_layer'))
            
            print(f"✓ EnhancedBucketIndex integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"EnhancedBucketIndex not available: {e}")
    
    def test_arrow_metadata_index_integration(self):
        """Test ArrowMetadataIndex has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check index can be initialized with integration params
            index = ArrowMetadataIndex(
                index_dir=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(index, 'enable_dataset_storage'))
            self.assertTrue(hasattr(index, 'enable_compute_layer'))
            
            print(f"✓ ArrowMetadataIndex integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"ArrowMetadataIndex not available: {e}")
    
    def test_pin_metadata_index_integration(self):
        """Test PinMetadataIndex has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.pin_metadata_index import PinMetadataIndex, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check index can be initialized with integration params
            index = PinMetadataIndex(
                data_dir=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(index, 'enable_dataset_storage'))
            self.assertTrue(hasattr(index, 'enable_compute_layer'))
            
            print(f"✓ PinMetadataIndex integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"PinMetadataIndex not available: {e}")
    
    def test_unified_bucket_interface_integration(self):
        """Test UnifiedBucketInterface has dataset/accelerate integration."""
        try:
            from ipfs_kit_py.unified_bucket_interface import UnifiedBucketInterface, HAS_DATASETS, HAS_ACCELERATE
            
            # Check flags exist
            self.assertIsInstance(HAS_DATASETS, bool)
            self.assertIsInstance(HAS_ACCELERATE, bool)
            
            # Check interface can be initialized with integration params
            interface = UnifiedBucketInterface(
                storage_path=self.test_dir,
                enable_dataset_storage=True,
                enable_compute_layer=True
            )
            
            # Verify attributes exist
            self.assertTrue(hasattr(interface, 'enable_dataset_storage'))
            self.assertTrue(hasattr(interface, 'enable_compute_layer'))
            
            print(f"✓ UnifiedBucketInterface integration: datasets={HAS_DATASETS}, accelerate={HAS_ACCELERATE}")
            
        except ImportError as e:
            self.skipTest(f"UnifiedBucketInterface not available: {e}")
    
    def test_all_integrations_have_fallbacks(self):
        """Verify all integrations work without optional packages."""
        modules_to_test = [
            ('bucket_vfs_manager', 'BucketVFSManager'),
            ('vfs_manager', 'VFSManager'),
            ('vfs_version_tracker', 'VFSVersionTracker'),
            ('enhanced_bucket_index', 'EnhancedBucketIndex'),
            ('arrow_metadata_index', 'ArrowMetadataIndex'),
            ('pin_metadata_index', 'PinMetadataIndex'),
            ('unified_bucket_interface', 'UnifiedBucketInterface'),
        ]
        
        tested = 0
        for module_name, class_name in modules_to_test:
            try:
                module = __import__(f'ipfs_kit_py.{module_name}', fromlist=[class_name])
                
                # Check that HAS_DATASETS and HAS_ACCELERATE flags exist
                self.assertTrue(hasattr(module, 'HAS_DATASETS'))
                self.assertTrue(hasattr(module, 'HAS_ACCELERATE'))
                
                # Verify they're boolean
                self.assertIsInstance(module.HAS_DATASETS, bool)
                self.assertIsInstance(module.HAS_ACCELERATE, bool)
                
                tested += 1
                print(f"✓ {class_name} has proper fallback flags")
                
            except ImportError:
                # Module not available, skip
                pass
        
        # At least some modules should be testable
        self.assertGreater(tested, 0, "No VFS modules were testable")
        print(f"\n✓ Tested {tested} VFS modules - all have proper fallbacks")


class TestVFSDatasetOperations(unittest.TestCase):
    """Test VFS operations with dataset storage."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_bucket_operation_tracking(self):
        """Test that bucket operations can be tracked to datasets."""
        try:
            from ipfs_kit_py.bucket_vfs_manager import BucketVFSManager, HAS_DATASETS
            
            manager = BucketVFSManager(
                storage_path=self.test_dir,
                enable_dataset_storage=True
            )
            
            # Verify dataset storage is properly configured
            if HAS_DATASETS:
                self.assertTrue(manager.enable_dataset_storage)
                self.assertIsNotNone(manager._dataset_manager)
                self.assertIsNotNone(manager._operation_buffer)
                print("✓ Bucket operations can be tracked to datasets")
            else:
                self.assertFalse(manager.enable_dataset_storage)
                print("✓ Bucket manager works without dataset support")
                
        except ImportError as e:
            self.skipTest(f"BucketVFSManager not available: {e}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
