"""
Tests for ipfs_datasets_py and ipfs_accelerate_py integration in VFS/MCP files.
Validates graceful fallbacks and CI/CD compatibility.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestVFSMCPIntegration(unittest.TestCase):
    """Test VFS and MCP integration with ipfs_datasets_py and ipfs_accelerate_py."""

    def test_vfs_journal_has_integration_flags(self):
        """Test that VFSJournalManager has HAS_DATASETS and HAS_ACCELERATE flags."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_journal import VFSJournalManager
            from ipfs_kit_py.mcp.ipfs_kit.backends import vfs_journal
            
            # Check that flags exist
            self.assertTrue(hasattr(vfs_journal, 'HAS_DATASETS'))
            self.assertTrue(hasattr(vfs_journal, 'HAS_ACCELERATE'))
            self.assertIsInstance(vfs_journal.HAS_DATASETS, bool)
            self.assertIsInstance(vfs_journal.HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"VFSJournalManager not available: {e}")

    def test_vfs_journal_has_init_parameters(self):
        """Test that VFSJournalManager accepts integration parameters."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_journal import VFSJournalManager
            
            # Test initialization with parameters
            manager = VFSJournalManager(
                log_dir="/tmp/test_vfs_journal",
                enable_dataset_storage=False,
                enable_compute_layer=False
            )
            
            self.assertFalse(manager.enable_dataset_storage)
            self.assertFalse(manager.enable_compute_layer)
            self.assertIsNone(manager.dataset_manager)
            self.assertIsNone(manager.compute_layer)
        except ImportError as e:
            self.skipTest(f"VFSJournalManager not available: {e}")
        except TypeError as e:
            self.fail(f"VFSJournalManager doesn't accept integration parameters: {e}")

    def test_vfs_journal_graceful_fallback(self):
        """Test that VFSJournalManager works without ipfs_datasets_py."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_journal import VFSJournalManager
            
            # Create manager with dataset storage enabled (should fallback gracefully)
            manager = VFSJournalManager(
                log_dir="/tmp/test_vfs_journal",
                enable_dataset_storage=True  # This should not fail even if package unavailable
            )
            
            # Should work fine without the package
            manager.add_journal_entry(
                backend="test",
                operation_type="file_operations",
                operation="create",
                path="/test/path",
                status="success"
            )
            
            # Manual flush should also not fail
            manager.flush_to_dataset()
            
        except ImportError as e:
            self.skipTest(f"VFSJournalManager not available: {e}")

    def test_vfs_observer_has_integration_flags(self):
        """Test that VFSObservabilityManager has HAS_DATASETS and HAS_ACCELERATE flags."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer import VFSObservabilityManager
            from ipfs_kit_py.mcp.ipfs_kit.backends import vfs_observer
            
            # Check that flags exist
            self.assertTrue(hasattr(vfs_observer, 'HAS_DATASETS'))
            self.assertTrue(hasattr(vfs_observer, 'HAS_ACCELERATE'))
            self.assertIsInstance(vfs_observer.HAS_DATASETS, bool)
            self.assertIsInstance(vfs_observer.HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"VFSObservabilityManager not available: {e}")

    def test_vfs_observer_has_init_parameters(self):
        """Test that VFSObservabilityManager accepts integration parameters."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer import VFSObservabilityManager
            
            # Test initialization with parameters
            manager = VFSObservabilityManager(
                enable_dataset_storage=False,
                enable_compute_layer=False
            )
            
            self.assertFalse(manager.enable_dataset_storage)
            self.assertFalse(manager.enable_compute_layer)
            self.assertIsNone(manager.dataset_manager)
            self.assertIsNone(manager.compute_layer)
        except ImportError as e:
            self.skipTest(f"VFSObservabilityManager not available: {e}")
        except TypeError as e:
            self.fail(f"VFSObservabilityManager doesn't accept integration parameters: {e}")

    def test_vfs_observer_graceful_fallback(self):
        """Test that VFSObservabilityManager works without ipfs_datasets_py."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer import VFSObservabilityManager
            
            # Create manager with dataset storage enabled (should fallback gracefully)
            manager = VFSObservabilityManager(
                enable_dataset_storage=True  # This should not fail even if package unavailable
            )
            
            # Should work fine without the package
            manager.log_vfs_operation(
                backend="test",
                operation="read",
                path="/test/path",
                status="success"
            )
            
            # Manual flush should also not fail
            manager.flush_to_dataset()
            
        except ImportError as e:
            self.skipTest(f"VFSObservabilityManager not available: {e}")

    def test_mcp_vfs_wrapper_has_integration_flags(self):
        """Test that MCP VFSManager wrapper has HAS_DATASETS and HAS_ACCELERATE flags."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.vfs import VFSManager
            from ipfs_kit_py.mcp.ipfs_kit import vfs as vfs_module
            
            # Check that flags exist
            self.assertTrue(hasattr(vfs_module, 'HAS_DATASETS'))
            self.assertTrue(hasattr(vfs_module, 'HAS_ACCELERATE'))
            self.assertIsInstance(vfs_module.HAS_DATASETS, bool)
            self.assertIsInstance(vfs_module.HAS_ACCELERATE, bool)
        except ImportError as e:
            self.skipTest(f"MCP VFSManager not available: {e}")

    def test_mcp_vfs_wrapper_has_init_parameters(self):
        """Test that MCP VFSManager accepts integration parameters."""
        try:
            from ipfs_kit_py.mcp.ipfs_kit.vfs import VFSManager
            
            # Test initialization with parameters
            manager = VFSManager(
                enable_dataset_storage=False,
                enable_compute_layer=False
            )
            
            self.assertFalse(manager.enable_dataset_storage)
            self.assertFalse(manager.enable_compute_layer)
            self.assertIsNone(manager.dataset_manager)
            self.assertIsNone(manager.compute_layer)
        except ImportError as e:
            self.skipTest(f"MCP VFSManager not available: {e}")
        except TypeError as e:
            self.fail(f"MCP VFSManager doesn't accept integration parameters: {e}")

    def test_all_vfs_modules_have_flush_method(self):
        """Test that all VFS modules have flush_to_dataset method."""
        modules_to_test = [
            ('ipfs_kit_py.mcp.ipfs_kit.backends.vfs_journal', 'VFSJournalManager'),
            ('ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer', 'VFSObservabilityManager'),
            ('ipfs_kit_py.mcp.ipfs_kit.vfs', 'VFSManager'),
        ]
        
        for module_name, class_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                
                # Check flush_to_dataset method exists
                self.assertTrue(hasattr(cls, 'flush_to_dataset'),
                              f"{class_name} missing flush_to_dataset method")
            except ImportError as e:
                self.skipTest(f"Module {module_name} not available: {e}")

    def test_ci_cd_compatibility(self):
        """Test that all modules work in CI/CD without optional dependencies."""
        # This test validates that imports don't fail even when
        # ipfs_datasets_py and ipfs_accelerate_py are not available
        
        modules_to_test = [
            'ipfs_kit_py.mcp.ipfs_kit.backends.vfs_journal',
            'ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer',
            'ipfs_kit_py.mcp.ipfs_kit.vfs',
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                # If import succeeds, the module handles missing dependencies gracefully
                self.assertTrue(True)
            except ImportError as e:
                error_msg = str(e)
                # Skip if it's about anyio (known MCP dependency) or the module itself
                if 'anyio' in error_msg or 'ipfs_kit_py' in error_msg:
                    self.skipTest(f"Module {module_name} not available: {e}")
                # Only fail if it's about ipfs_datasets_py or ipfs_accelerate_py being required
                elif 'ipfs_datasets' in error_msg or 'ipfs_accelerate' in error_msg:
                    self.fail(f"Module {module_name} has hard dependency on optional package: {e}")
                else:
                    # Other import errors, skip
                    self.skipTest(f"Module {module_name} not available: {e}")


if __name__ == '__main__':
    unittest.main()
