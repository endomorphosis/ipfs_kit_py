"""
Test the MCP storage controller initialization with various configurations.

This test script validates that the storage controller initialization in MCP server
works correctly and handles errors gracefully.
"""

import unittest
import tempfile
import shutil
import logging
import os
import sys
from unittest.mock import patch, MagicMock

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure that we can import from the root directory
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the MCP server and relevant components
from ipfs_kit_py.mcp.server import MCPServer

class TestMCPStorageControllers(unittest.TestCase):
    """Test the MCP storage controller initialization."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for isolation
        self.temp_dir = tempfile.mkdtemp()
        
        # Create subdirectories for test data
        self.persistence_path = os.path.join(self.temp_dir, "mcp_persistence")
        os.makedirs(self.persistence_path, exist_ok=True)
        
        logger.info(f"Test setup complete, using persistence path: {self.persistence_path}")

    def tearDown(self):
        """Clean up after tests."""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        logger.info("Test cleanup complete")

    def test_storage_controllers_initialization_normal(self):
        """Test normal initialization of storage controllers."""
        # Create MCP server with normal configuration
        with patch('ipfs_kit_py.mcp.server.StorageManager') as mock_storage_manager, \
             patch('ipfs_kit_py.mcp.server.S3Controller') as mock_s3_controller, \
             patch('ipfs_kit_py.mcp.server.HuggingFaceController') as mock_hf_controller, \
             patch('ipfs_kit_py.mcp.server.StorachaController') as mock_storacha_controller, \
             patch('ipfs_kit_py.mcp.server.FilecoinController') as mock_filecoin_controller, \
             patch('ipfs_kit_py.mcp.server.LassieController') as mock_lassie_controller:
            
            # Configure mock storage manager
            mock_storage_manager_instance = MagicMock()
            mock_storage_manager.return_value = mock_storage_manager_instance
            
            # Configure mock storage manager methods
            mock_storage_manager_instance.get_all_models.return_value = {
                "s3": MagicMock(),
                "huggingface": MagicMock(),
                "storacha": MagicMock(),
                "filecoin": MagicMock(),
                "lassie": MagicMock()
            }
            
            mock_storage_manager_instance.get_available_backends.return_value = {
                "s3": True,
                "huggingface": True,
                "storacha": True,
                "filecoin": True,
                "lassie": True
            }
            
            # Create an isolation-mode server for testing
            server = MCPServer(
                debug_mode=True,
                log_level="DEBUG",
                persistence_path=self.persistence_path,
                isolation_mode=True
            )
            
            # Verify that controllers were initialized correctly
            self.assertIn("storage_controllers", server.initialization_results)
            storage_results = server.initialization_results["storage_controllers"]
            
            # Validate success counts
            self.assertGreaterEqual(storage_results["success_count"], 0)
            
            # Check if any controllers were initialized (may be 0 if none are available)
            initialized_controllers = sum([
                1 for name in server.controllers 
                if name.startswith("storage_") and name != "storage_manager"
            ])
            
            logger.info(f"Initialized {initialized_controllers} storage controllers")
            logger.info(f"Initialization results: {storage_results}")
            
            # Verify initialization results match actual controllers
            self.assertEqual(
                storage_results["success_count"],
                initialized_controllers
            )

    def test_storage_controllers_initialization_errors(self):
        """Test storage controllers initialization with errors."""
        # Create MCP server with mocked storage manager that raises errors
        with patch('ipfs_kit_py.mcp.server.StorageManager') as mock_storage_manager, \
             patch('ipfs_kit_py.mcp.server.S3Controller') as mock_s3_controller, \
             patch('ipfs_kit_py.mcp.server.HuggingFaceController') as mock_hf_controller, \
             patch('ipfs_kit_py.mcp.server.StorachaController') as mock_storacha_controller, \
             patch('ipfs_kit_py.mcp.server.FilecoinController') as mock_filecoin_controller, \
             patch('ipfs_kit_py.mcp.server.LassieController') as mock_lassie_controller:
            
            # Configure mock storage manager
            mock_storage_manager_instance = MagicMock()
            mock_storage_manager.return_value = mock_storage_manager_instance
            
            # Set up the models dict with some models that will raise errors
            models_dict = {
                "s3": MagicMock(),
                "huggingface": MagicMock(),
                "storacha": None,  # This should be skipped, not raise error
                "filecoin": MagicMock()
            }
            # No "lassie" key to test missing model case
            
            mock_storage_manager_instance.get_all_models.return_value = models_dict
            
            # Configure controller mocks
            mock_s3_controller.side_effect = None  # Normal initialization
            mock_hf_controller.side_effect = AttributeError("Missing attribute")  # Attribute error
            mock_filecoin_controller.side_effect = ImportError("Module not found")  # Import error
            
            # Create an isolation-mode server for testing
            server = MCPServer(
                debug_mode=True,
                log_level="DEBUG",
                persistence_path=self.persistence_path,
                isolation_mode=True
            )
            
            # Verify that controllers initialization was tracked correctly
            self.assertIn("storage_controllers", server.initialization_results)
            storage_results = server.initialization_results["storage_controllers"]
            
            # Check for expected failure counts
            logger.info(f"Storage controller initialization results: {storage_results}")
            
            # We expect:
            # - S3: Success
            # - HuggingFace: Failed (AttributeError)
            # - Storacha: Skipped (None model)
            # - Filecoin: Failed (ImportError)
            # - Lassie: Skipped (missing model)
            
            # Check success, failure and skip counts
            self.assertEqual(storage_results["success_count"], 1)  # S3 only
            self.assertEqual(storage_results["failed_count"], 2)   # HuggingFace and Filecoin
            self.assertEqual(storage_results["skipped_count"], 2)  # Storacha and Lassie
            
            # Check failure details
            self.assertIn("storage_huggingface", storage_results["failures"])
            self.assertIn("storage_filecoin", storage_results["failures"])
            
            # Verify error types
            self.assertEqual(storage_results["failures"]["storage_huggingface"]["error_type"], "AttributeError")
            self.assertEqual(storage_results["failures"]["storage_filecoin"]["error_type"], "ImportError")
            
            # Verify warnings
            self.assertIn("storage_storacha", storage_results["warnings"])
            self.assertIn("storage_lassie", storage_results["warnings"])
            
            # Check that MCP server continues to function despite errors
            self.assertTrue(server.initialization_results["success"])
            
            # Only S3 controller should be in the controllers dict
            storage_controller_count = sum([
                1 for name in server.controllers 
                if name.startswith("storage_") and name != "storage_manager"
            ])
            self.assertEqual(storage_controller_count, 1)

    def test_storage_controllers_without_storage_manager(self):
        """Test that storage controllers initialization gracefully handles missing storage manager."""
        # Create MCP server with missing storage manager
        with patch('ipfs_kit_py.mcp.server.StorageManager', side_effect=Exception("Storage manager init failed")):
            # Create an isolation-mode server for testing
            server = MCPServer(
                debug_mode=True,
                log_level="DEBUG",
                persistence_path=self.persistence_path,
                isolation_mode=True
            )
            
            # Server should still initialize
            self.assertTrue(hasattr(server, "initialization_results"))
            
            # Check that appropriate errors were logged
            errors = server.initialization_results.get("errors", [])
            error_messages = "\n".join(errors)
            logger.info(f"Initialization errors: {error_messages}")
            
            # There should be an error about storage manager failure
            storage_manager_failed = any("Storage Manager initialization failed" in error for error in errors)
            self.assertTrue(storage_manager_failed, "Should report Storage Manager initialization failure")
            
            # Ensure no storage controllers were initialized
            storage_controller_count = sum([
                1 for name in server.controllers 
                if name.startswith("storage_") and name != "storage_manager"
            ])
            self.assertEqual(storage_controller_count, 0)
            
            # MCP server should still be usable 
            # (though the overall success might be false due to storage manager being required)
            server.reset_state()  # This should work without errors

if __name__ == "__main__":
    unittest.main()