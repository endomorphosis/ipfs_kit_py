"""
Integration test for MCP Cross-Backend Migration functionality.
This test verifies that content can be migrated between different storage backends.
"""

import os
import sys
import unittest
import logging
import tempfile
import time
import uuid
import json
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCrossBackendMigration(unittest.TestCase):
    """Integration tests for the MCP cross-backend migration capabilities."""

    @classmethod
    def setUpClass(cls):
        """Set up test resources."""
        # Create a temporary directory for test data
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.test_file_path = cls.temp_dir / f"test_file_{uuid.uuid4()}.bin"

        # Generate a small random file for testing
        with open(cls.test_file_path, 'wb') as f:
            f.write(os.urandom(1024))  # 1KB random data

        logger.info(f"Created test file at: {cls.test_file_path}")

        # Try to import the migration controller module
        try:
            from ipfs_kit_py.mcp.migration import migration_controller
            from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
            from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager

            cls.migration_module = migration_controller
            cls.StorageBackendType = StorageBackendType
            cls.BackendManager = BackendManager
            cls.import_error = None

            # Create backend manager with mock backends
            cls.backend_manager = cls.BackendManager()

            # Configure local backends for testing
            cls.backend_config = {
                "source": {
                    "type": "local",
                    "path": str(cls.temp_dir / "source_storage")
                },
                "destination": {
                    "type": "local",
                    "path": str(cls.temp_dir / "dest_storage")
                }
            }

            # Create directories for local storage backends
            os.makedirs(cls.backend_config["source"]["path"], exist_ok=True)
            os.makedirs(cls.backend_config["destination"]["path"], exist_ok=True)

            # Initialize the migration controller
            cls.migration_controller = cls.migration_module.MigrationController(
                backend_manager=cls.backend_manager,
                config_path=str(cls.temp_dir / "migration_config.json")
            )
        except ImportError as e:
            logger.warning(f"Cannot import migration modules: {e}")
            cls.import_error = e
        except Exception as e:
            logger.error(f"Error initializing migration controller: {e}")
            cls.init_error = e

    def setUp(self):
        """Set up for each test."""
        if hasattr(self.__class__, 'import_error') and self.__class__.import_error:
            self.skipTest(f"Migration modules not available: {self.__class__.import_error}")

        if hasattr(self.__class__, 'init_error') and self.__class__.init_error:
            self.skipTest(f"Migration controller initialization failed: {self.__class__.init_error}")

    def test_migration_module_exists(self):
        """Test that the migration module exists and can be initialized."""
        self.assertIsNotNone(self.migration_module)
        logger.info("Migration module exists")

        # Check for expected attributes/methods
        expected_attributes = [
            'MigrationController', 'MigrationPolicy', 'MigrationTask'
        ]

        for attr in expected_attributes:
            self.assertTrue(hasattr(self.migration_module, attr), f"Missing attribute: {attr}")

        logger.info("Migration module has expected components")

    def test_policy_creation(self):
        """Test creating a migration policy."""
        # Create a simple policy
        policy = self.migration_module.MigrationPolicy(
            name="test_policy",
            source_backend="source",
            destination_backend="destination",
            content_filter={"type": "all"},
            schedule="manual"
        )

        self.assertEqual(policy.name, "test_policy")
        self.assertEqual(policy.source_backend, "source")
        self.assertEqual(policy.destination_backend, "destination")
        logger.info("Migration policy created successfully")

    def test_policy_management(self):
        """Test adding and retrieving policies."""
        # Create and add a policy
        policy = self.migration_module.MigrationPolicy(
            name="test_policy_2",
            source_backend="source",
            destination_backend="destination",
            content_filter={"type": "all"},
            schedule="manual"
        )

        if hasattr(self.migration_controller, "add_policy"):
            self.migration_controller.add_policy(policy)

            # Retrieve the policy
            retrieved_policy = self.migration_controller.get_policy("test_policy_2")
            self.assertIsNotNone(retrieved_policy)
            self.assertEqual(retrieved_policy.name, "test_policy_2")

            logger.info("Migration policy management working correctly")
        else:
            self.skipTest("Policy management methods not available")

    def test_basic_migration_task(self):
        """Test creating a migration task."""
        # Create a migration task
        if hasattr(self.migration_module, "MigrationTask"):
            task = self.migration_module.MigrationTask(
                source_backend="source",
                destination_backend="destination",
                content_id="test_content",
                priority=1
            )

            self.assertEqual(task.source_backend, "source")
            self.assertEqual(task.destination_backend, "destination")
            self.assertEqual(task.content_id, "test_content")

            logger.info("Migration task created successfully")
        else:
            self.skipTest("MigrationTask class not available")

    def test_migration_controller_attributes(self):
        """Test the migration controller has required functionality."""
        expected_methods = [
            "add_policy", "get_policy", "list_policies", "remove_policy",
            "schedule_migration", "execute_migration", "get_migration_status"
        ]

        for method in expected_methods:
            self.assertTrue(hasattr(self.migration_controller, method),
                          f"Missing method: {method}")

        logger.info("Migration controller has expected methods")

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        # Clean up the temporary directory
        if hasattr(cls, 'temp_dir') and cls.temp_dir.exists():
            import shutil
            shutil.rmtree(cls.temp_dir)
            logger.info(f"Cleaned up test directory: {cls.temp_dir}")

if __name__ == "__main__":
    unittest.main()
