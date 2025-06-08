"""
Test script for the MCP data migration functionality.

This script verifies that the migration system works properly,
allowing content to be transferred between different storage backends.
"""

import os
import sys
import time
import json
import logging
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# Import components to test
try:
    from ipfs_kit_py.mcp.storage_manager.migration import (
        MigrationManager, MigrationTask, MigrationResult,
        MigrationType, ValidationLevel, MigrationStatus, MigrationPriority
    )
    from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
    logger.info("Successfully imported migration modules")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


class MockStorage(BackendStorage):
    """Mock storage backend for testing."""
    
    def __init__(self, backend_name="mock", fail_operations=False):
        """Initialize with optional name and failure mode."""
        self.backend_name = backend_name
        self.fail_operations = fail_operations
        self.data_store = {}  # store content by ID
        self.metadata_store = {}  # store metadata by ID
        super().__init__(StorageBackendType.CUSTOM, {}, {})
    
    def get_name(self):
        """Get backend name."""
        return self.backend_name
    
    def add_content(self, content, metadata=None):
        """Add content to mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        # Generate ID if not in metadata
        content_id = metadata.get("content_id") if metadata else None
        if not content_id:
            import uuid
            content_id = f"mock-{uuid.uuid4()}"
        
        # Store content and metadata
        if isinstance(content, bytes):
            self.data_store[content_id] = content
        else:
            # Convert file-like or string to bytes
            try:
                if hasattr(content, 'read'):
                    self.data_store[content_id] = content.read()
                    if hasattr(content, 'seek'):
                        content.seek(0)  # rewind if possible
                elif isinstance(content, str) and os.path.isfile(content):
                    with open(content, 'rb') as f:
                        self.data_store[content_id] = f.read()
                else:
                    # Treat as string
                    self.data_store[content_id] = str(content).encode('utf-8')
            except Exception as e:
                return {
                    "success": False, 
                    "error": f"Error handling content: {str(e)}", 
                    "backend": self.backend_name
                }
        
        # Store metadata
        self.metadata_store[content_id] = metadata or {}
        
        return {
            "success": True,
            "identifier": content_id,
            "backend": self.backend_name,
            "details": {"size": len(self.data_store[content_id])}
        }
    
    def get_content(self, content_id):
        """Retrieve content from mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        if content_id not in self.data_store:
            return {
                "success": False,
                "error": f"Content not found: {content_id}",
                "backend": self.backend_name
            }
        
        return {
            "success": True,
            "data": self.data_store[content_id],
            "backend": self.backend_name,
            "identifier": content_id
        }
    
    def remove_content(self, content_id):
        """Remove content from mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        if content_id not in self.data_store:
            return {
                "success": False,
                "error": f"Content not found: {content_id}",
                "backend": self.backend_name
            }
        
        # Remove content and metadata
        del self.data_store[content_id]
        if content_id in self.metadata_store:
            del self.metadata_store[content_id]
        
        return {
            "success": True,
            "backend": self.backend_name,
            "identifier": content_id
        }
    
    def get_metadata(self, content_id):
        """Get metadata from mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        if content_id not in self.metadata_store:
            return {
                "success": False,
                "error": f"Metadata not found: {content_id}",
                "backend": self.backend_name
            }
        
        return {
            "success": True,
            "metadata": self.metadata_store[content_id],
            "backend": self.backend_name,
            "identifier": content_id
        }
    
    def exists(self, identifier, **kwargs):
        """Check if content exists in mock store."""
        return identifier in self.data_store
    
    def update_metadata(self, identifier, metadata, **kwargs):
        """Update metadata in mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        if identifier not in self.metadata_store:
            return {
                "success": False,
                "error": f"Content not found: {identifier}",
                "backend": self.backend_name
            }
        
        # Update metadata
        self.metadata_store[identifier].update(metadata)
        
        return {
            "success": True,
            "backend": self.backend_name,
            "identifier": identifier
        }
    
    def list(self, prefix=None, **kwargs):
        """List content in mock store."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        items = []
        for content_id in self.data_store.keys():
            if prefix and not content_id.startswith(prefix):
                continue
            
            items.append({
                "identifier": content_id,
                "backend": self.backend_name,
                "metadata": self.metadata_store.get(content_id, {})
            })
        
        return {
            "success": True,
            "items": items,
            "count": len(items),
            "backend": self.backend_name
        }
    
    # Implement the migrate_to method for optimized path testing
    def migrate_to(self, source_identifier, target_backend, **kwargs):
        """Migrate content to another backend."""
        if self.fail_operations:
            return {
                "success": False, 
                "error": "Simulated failure", 
                "backend": self.backend_name
            }
        
        # Get the content
        get_result = self.get_content(source_identifier)
        if not get_result["success"]:
            return {
                "success": False,
                "error": f"Failed to retrieve source content: {get_result.get('error')}",
                "backend": self.backend_name
            }
        
        # Get metadata
        metadata_result = self.get_metadata(source_identifier)
        metadata = metadata_result.get("metadata", {}) if metadata_result.get("success", False) else {}
        
        # Add migration metadata
        migration_metadata = kwargs.get("options", {}).get("migration_metadata", {})
        combined_metadata = {**metadata, **migration_metadata}
        
        # Store in target backend
        store_result = target_backend.add_content(
            get_result["data"], 
            metadata=combined_metadata
        )
        
        if not store_result["success"]:
            return {
                "success": False,
                "error": f"Failed to store content in target: {store_result.get('error')}",
                "backend": self.backend_name,
                "target_backend": target_backend.get_name()
            }
        
        # Get target identifier
        target_identifier = store_result["identifier"]
        
        # Verify if requested
        verification_result = None
        if kwargs.get("options", {}).get("verify", False):
            validation_strategy = kwargs.get("options", {}).get("validation_strategy", "hash")
            
            # Simple verification (just check existence)
            if validation_strategy == "exists":
                target_exists = target_backend.exists(target_identifier)
                verification_result = {
                    "success": target_exists,
                    "validation_level": validation_strategy,
                    "error": None if target_exists else "Content doesn't exist in target"
                }
            else:
                # More comprehensive verification - compare content
                source_data = get_result["data"]
                target_data_result = target_backend.get_content(target_identifier)
                
                if not target_data_result["success"]:
                    verification_result = {
                        "success": False,
                        "validation_level": validation_strategy,
                        "error": f"Failed to retrieve target content: {target_data_result.get('error')}"
                    }
                else:
                    target_data = target_data_result["data"]
                    verification_result = {
                        "success": source_data == target_data,
                        "validation_level": validation_strategy,
                        "error": None if source_data == target_data else "Content mismatch"
                    }
        
        # Build result
        result = {
            "success": True,
            "source_backend": self.backend_name,
            "target_backend": target_backend.get_name(),
            "source_identifier": source_identifier,
            "target_identifier": target_identifier,
            "operation_time": 0.1,  # mock time
        }
        
        # Add verification if performed
        if verification_result:
            result["verification"] = verification_result
            if not verification_result["success"]:
                result["success"] = False
                result["error"] = f"Verification failed: {verification_result.get('error')}"
        
        return result


class TestMigration(unittest.TestCase):
    """Test case for the migration functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock backends
        self.source_backend = MockStorage("source_backend")
        self.target_backend = MockStorage("target_backend")
        self.failing_backend = MockStorage("failing_backend", fail_operations=True)
        
        # Create backend registry
        self.backend_registry = {
            "source_backend": self.source_backend,
            "target_backend": self.target_backend,
            "failing_backend": self.failing_backend
        }
        
        # Create migration manager
        self.migration_manager = MigrationManager(self.backend_registry, max_workers=2)
        
        # Add test content to source backend
        self.test_content = b"Hello, Migration World!"
        self.test_metadata = {"content_type": "text/plain", "test": True}
        
        add_result = self.source_backend.add_content(
            self.test_content, 
            metadata={"content_id": "test-content-1", **self.test_metadata}
        )
        self.test_content_id = add_result["identifier"]
        
        # Add more test content
        self.source_backend.add_content(
            b"Test content 2", 
            metadata={"content_id": "test-content-2", "index": 2}
        )
        
        self.source_backend.add_content(
            b"Test content 3", 
            metadata={"content_id": "test-content-3", "index": 3}
        )
    
    def tearDown(self):
        """Clean up after tests."""
        # Shutdown migration manager
        self.migration_manager.shutdown()
    
    def test_create_task(self):
        """Test creating a migration task."""
        # Create a task
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="target_backend",
            source_id=self.test_content_id,
            migration_type=MigrationType.COPY,
            validation_level=ValidationLevel.CONTENT
        )
        
        # Verify task was created
        self.assertIsNotNone(task_id)
        
        # Get task details
        task = self.migration_manager.get_task(task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["source_backend"], "source_backend")
        self.assertEqual(task["target_backend"], "target_backend")
        self.assertEqual(task["source_id"], self.test_content_id)
        self.assertEqual(task["migration_type"], MigrationType.COPY.value)
    
    def test_successful_migration(self):
        """Test successful migration between backends."""
        # Create a migration task
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="target_backend",
            source_id=self.test_content_id
        )
        
        # Wait for migration to complete
        max_wait = 5  # seconds
        start_time = time.time()
        task_complete = False
        
        while not task_complete and (time.time() - start_time < max_wait):
            task = self.migration_manager.get_task(task_id)
            if task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value, 
                                  MigrationStatus.FAILED.value]:
                task_complete = True
            else:
                time.sleep(0.1)
        
        # Verify migration completed successfully
        self.assertTrue(task_complete, "Migration did not complete in time")
        
        task = self.migration_manager.get_task(task_id)
        self.assertTrue(task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value], 
                        f"Migration failed with status {task['status']}")
        
        # Verify content was copied to target
        target_id = task["result"]["target_id"]
        self.assertIsNotNone(target_id)
        
        # Verify content in target
        target_content = self.target_backend.get_content(target_id)
        self.assertTrue(target_content["success"])
        self.assertEqual(target_content["data"], self.test_content)
        
        # Verify metadata was transferred
        target_metadata = self.target_backend.get_metadata(target_id)
        self.assertTrue(target_metadata["success"])
        for key, value in self.test_metadata.items():
            self.assertEqual(target_metadata["metadata"].get(key), value)
    
    def test_failed_migration(self):
        """Test migration that fails due to target backend issues."""
        # Create a migration task to failing backend
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="failing_backend",
            source_id=self.test_content_id
        )
        
        # Wait for migration to complete
        max_wait = 5  # seconds
        start_time = time.time()
        task_complete = False
        
        while not task_complete and (time.time() - start_time < max_wait):
            task = self.migration_manager.get_task(task_id)
            if task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value, 
                                  MigrationStatus.FAILED.value]:
                task_complete = True
            else:
                time.sleep(0.1)
        
        # Verify migration failed
        self.assertTrue(task_complete, "Migration did not complete in time")
        
        task = self.migration_manager.get_task(task_id)
        self.assertEqual(task["status"], MigrationStatus.FAILED.value, 
                        f"Migration unexpectedly succeeded with status {task['status']}")
    
    def test_move_migration(self):
        """Test move migration (copy + delete source)."""
        # Create a migration task with move type
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="target_backend",
            source_id="test-content-2",
            migration_type=MigrationType.MOVE
        )
        
        # Wait for migration to complete
        max_wait = 5  # seconds
        start_time = time.time()
        task_complete = False
        
        while not task_complete and (time.time() - start_time < max_wait):
            task = self.migration_manager.get_task(task_id)
            if task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value, 
                                 MigrationStatus.FAILED.value]:
                task_complete = True
            else:
                time.sleep(0.1)
        
        # Verify migration completed successfully
        self.assertTrue(task_complete, "Migration did not complete in time")
        
        task = self.migration_manager.get_task(task_id)
        self.assertTrue(task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value], 
                       f"Migration failed with status {task['status']}")
        
        # Verify content was moved to target
        target_id = task["result"]["target_id"]
        self.assertIsNotNone(target_id)
        
        # Verify content in target
        target_content = self.target_backend.get_content(target_id)
        self.assertTrue(target_content["success"])
        
        # Verify content was removed from source
        source_content = self.source_backend.get_content("test-content-2")
        self.assertFalse(source_content["success"], "Content still exists in source after move")
    
    def test_scheduled_migration(self):
        """Test scheduling a migration for future execution."""
        # Schedule migration for 1 second in the future
        scheduled_time = datetime.now() + timedelta(seconds=1)
        
        # Create a scheduled migration task
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="target_backend",
            source_id="test-content-3",
            scheduled_time=scheduled_time
        )
        
        # Verify task is scheduled
        task = self.migration_manager.get_task(task_id)
        self.assertEqual(task["status"], MigrationStatus.SCHEDULED.value)
        
        # Wait for migration to become due and complete
        max_wait = 5  # seconds
        start_time = time.time()
        task_complete = False
        
        while not task_complete and (time.time() - start_time < max_wait):
            task = self.migration_manager.get_task(task_id)
            if task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value, 
                                 MigrationStatus.FAILED.value]:
                task_complete = True
            else:
                time.sleep(0.1)
        
        # Verify scheduled migration completed
        self.assertTrue(task_complete, "Scheduled migration did not complete in time")
        
        task = self.migration_manager.get_task(task_id)
        self.assertTrue(task["status"] in [MigrationStatus.COMPLETED.value, MigrationStatus.VALIDATED.value], 
                       f"Migration failed with status {task['status']}")
        
        # Verify content was copied to target
        target_id = task["result"]["target_id"]
        self.assertIsNotNone(target_id)
        target_content = self.target_backend.get_content(target_id)
        self.assertTrue(target_content["success"])
    
    def test_list_tasks(self):
        """Test listing migration tasks."""
        # Create several tasks
        task_ids = []
        for i in range(3):
            task_id = self.migration_manager.create_task(
                source_backend="source_backend",
                target_backend="target_backend",
                source_id=f"test-content-{i+1}"
            )
            task_ids.append(task_id)
        
        # Get task list
        tasks = self.migration_manager.list_tasks(include_completed=True)
        
        # Verify all tasks are in the list
        self.assertGreaterEqual(len(tasks), 3)
        
        # Verify we can filter by status
        pending_tasks = self.migration_manager.list_tasks(status=MigrationStatus.PENDING)
        completed_tasks = self.migration_manager.list_tasks(status=MigrationStatus.COMPLETED, include_completed=True)
        
        # At least some tasks should be pending or completed
        self.assertTrue(len(pending_tasks) > 0 or len(completed_tasks) > 0)
    
    def test_cancel_task(self):
        """Test canceling a migration task."""
        # Create a scheduled task we can cancel
        scheduled_time = datetime.now() + timedelta(seconds=10)
        task_id = self.migration_manager.create_task(
            source_backend="source_backend",
            target_backend="target_backend",
            source_id=self.test_content_id,
            scheduled_time=scheduled_time
        )
        
        # Verify task is scheduled
        task = self.migration_manager.get_task(task_id)
        self.assertEqual(task["status"], MigrationStatus.SCHEDULED.value)
        
        # Cancel the task
        result = self.migration_manager.cancel_task(task_id)
        self.assertTrue(result["success"])
        
        # Verify task was canceled
        task = self.migration_manager.get_task(task_id)
        self.assertEqual(task["status"], MigrationStatus.FAILED.value)


if __name__ == "__main__":
    unittest.main()