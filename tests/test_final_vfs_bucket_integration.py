"""
Comprehensive tests for final VFS/bucket ipfs_datasets_py and ipfs_accelerate_py integration.

Tests all recently integrated bucket managers, MCP tools, MCP servers, and controllers
to verify proper integration flags, parameters, and graceful fallbacks.
"""

import unittest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBucketManagerIntegration(unittest.TestCase):
    """Test bucket manager integrations."""
    
    def test_bucket_manager_has_integration_flags(self):
        """Test bucket_manager has HAS_DATASETS and HAS_ACCELERATE flags."""
        try:
            from ipfs_kit_py import bucket_manager
            self.assertTrue(hasattr(bucket_manager, 'HAS_DATASETS'))
            self.assertTrue(hasattr(bucket_manager, 'HAS_ACCELERATE'))
            self.assertIsInstance(bucket_manager.HAS_DATASETS, bool)
            self.assertIsInstance(bucket_manager.HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"bucket_manager not available: {e}")
    
    def test_bucket_manager_accepts_parameters(self):
        """Test bucket_manager accepts dataset storage parameters."""
        try:
            from ipfs_kit_py.bucket_manager import BucketManager
            # Should accept new parameters without error
            manager = BucketManager(
                enable_dataset_storage=False,
                enable_compute_layer=False,
                ipfs_client=None,
                dataset_batch_size=100
            )
            self.assertIsNotNone(manager)
        except ImportError as e:
            self.skipTest(f"BucketManager not available: {e}")
    
    def test_simple_bucket_manager_has_integration(self):
        """Test simple_bucket_manager has integration."""
        try:
            from ipfs_kit_py import simple_bucket_manager
            self.assertTrue(hasattr(simple_bucket_manager, 'HAS_DATASETS'))
            self.assertTrue(hasattr(simple_bucket_manager, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"simple_bucket_manager not available: {e}")
    
    def test_simplified_bucket_manager_has_integration(self):
        """Test simplified_bucket_manager has integration."""
        try:
            from ipfs_kit_py import simplified_bucket_manager
            self.assertTrue(hasattr(simplified_bucket_manager, 'HAS_DATASETS'))
            self.assertTrue(hasattr(simplified_bucket_manager, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"simplified_bucket_manager not available: {e}")


class TestMCPToolsIntegration(unittest.TestCase):
    """Test MCP tools integrations."""
    
    def test_bucket_vfs_mcp_tools_has_integration(self):
        """Test bucket_vfs_mcp_tools has integration flags."""
        try:
            from mcp import bucket_vfs_mcp_tools
            self.assertTrue(hasattr(bucket_vfs_mcp_tools, 'HAS_DATASETS'))
            self.assertTrue(hasattr(bucket_vfs_mcp_tools, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"bucket_vfs_mcp_tools not available: {e}")
    
    def test_vfs_version_mcp_tools_has_integration(self):
        """Test vfs_version_mcp_tools has integration flags."""
        try:
            from mcp import vfs_version_mcp_tools
            self.assertTrue(hasattr(vfs_version_mcp_tools, 'HAS_DATASETS'))
            self.assertTrue(hasattr(vfs_version_mcp_tools, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"vfs_version_mcp_tools not available: {e}")
    
    def test_vfs_tools_has_integration(self):
        """Test mcp vfs_tools has integration."""
        try:
            from mcp.ipfs_kit.mcp_tools import vfs_tools
            self.assertTrue(hasattr(vfs_tools, 'HAS_DATASETS'))
            self.assertTrue(hasattr(vfs_tools, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"vfs_tools not available: {e}")
    
    def test_vfs_tools_class_accepts_parameters(self):
        """Test VFSTools class accepts dataset parameters."""
        try:
            from mcp.ipfs_kit.mcp_tools.vfs_tools import VFSTools
            # Should accept new parameters without error
            tools = VFSTools(
                enable_dataset_storage=False,
                enable_compute_layer=False,
                ipfs_client=None,
                dataset_batch_size=100
            )
            self.assertIsNotNone(tools)
            self.assertTrue(hasattr(tools, 'flush_to_dataset'))
        except ImportError as e:
            self.skipTest(f"VFSTools not available: {e}")


class TestMCPServersIntegration(unittest.TestCase):
    """Test MCP servers integrations."""
    
    def test_enhanced_mcp_server_with_vfs_has_integration(self):
        """Test enhanced_mcp_server_with_vfs has integration."""
        try:
            from mcp import enhanced_mcp_server_with_vfs
            self.assertTrue(hasattr(enhanced_mcp_server_with_vfs, 'HAS_DATASETS'))
            self.assertTrue(hasattr(enhanced_mcp_server_with_vfs, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"enhanced_mcp_server_with_vfs not available: {e}")
    
    def test_enhanced_vfs_mcp_server_has_integration(self):
        """Test enhanced_vfs_mcp_server has integration."""
        try:
            from mcp import enhanced_vfs_mcp_server
            self.assertTrue(hasattr(enhanced_vfs_mcp_server, 'HAS_DATASETS'))
            self.assertTrue(hasattr(enhanced_vfs_mcp_server, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"enhanced_vfs_mcp_server not available: {e}")
    
    def test_standalone_vfs_mcp_server_has_integration(self):
        """Test standalone_vfs_mcp_server has integration."""
        try:
            from mcp import standalone_vfs_mcp_server
            self.assertTrue(hasattr(standalone_vfs_mcp_server, 'HAS_DATASETS'))
            self.assertTrue(hasattr(standalone_vfs_mcp_server, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"standalone_vfs_mcp_server not available: {e}")


class TestControllersIntegration(unittest.TestCase):
    """Test controllers integrations."""
    
    def test_fs_journal_controller_has_integration(self):
        """Test fs_journal_controller has integration."""
        try:
            from mcp.controllers import fs_journal_controller
            self.assertTrue(hasattr(fs_journal_controller, 'HAS_DATASETS'))
            self.assertTrue(hasattr(fs_journal_controller, 'HAS_ACCELERATE'))
        except ImportError as e:
            self.skipTest(f"fs_journal_controller not available: {e}")
    
    def test_fs_journal_controller_accepts_parameters(self):
        """Test FSJournalController accepts dataset parameters."""
        try:
            from mcp.controllers.fs_journal_controller import FSJournalController
            # Should accept new parameters without error
            controller = FSJournalController(
                enable_dataset_storage=False,
                enable_compute_layer=False,
                ipfs_client=None,
                dataset_batch_size=100
            )
            self.assertIsNotNone(controller)
            self.assertTrue(hasattr(controller, 'flush_to_dataset'))
        except ImportError as e:
            self.skipTest(f"FSJournalController not available: {e}")


class TestGracefulFallbacks(unittest.TestCase):
    """Test graceful fallback behavior."""
    
    def test_bucket_manager_works_without_datasets(self):
        """Test BucketManager works when ipfs_datasets_py is unavailable."""
        try:
            from ipfs_kit_py.bucket_manager import BucketManager, HAS_DATASETS
            # Should work even if HAS_DATASETS is False
            manager = BucketManager(enable_dataset_storage=True)
            self.assertIsNotNone(manager)
            # If HAS_DATASETS is False, enable_dataset_storage should be False internally
            if not HAS_DATASETS:
                self.assertFalse(manager.enable_dataset_storage)
        except ImportError as e:
            self.skipTest(f"BucketManager not available: {e}")
    
    def test_flush_method_exists(self):
        """Test flush_to_dataset method exists on integrated classes."""
        try:
            from ipfs_kit_py.bucket_manager import BucketManager
            manager = BucketManager()
            self.assertTrue(hasattr(manager, 'flush_to_dataset'))
            self.assertTrue(callable(manager.flush_to_dataset))
            # Should not raise error even without dataset storage enabled
            manager.flush_to_dataset()
        except ImportError as e:
            self.skipTest(f"BucketManager not available: {e}")


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()
