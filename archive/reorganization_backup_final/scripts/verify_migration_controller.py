#!/usr/bin/env python3
"""
Verification script for the Migration Controller.

This script verifies that the Cross-Backend Data Migration functionality
mentioned in the roadmap is working correctly.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration_test")

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

def test_migration_imports():
    """Test the migration module imports correctly."""
    try:
        from ipfs_kit_py.mcp.migration import (
            MigrationController,
            MigrationPolicy,
            MigrationTask,
            MigrationStatus,
            MigrationPriority
        )
        
        logger.info("✅ Successfully imported migration module")
        return True, {
            "controller": MigrationController,
            "policy": MigrationPolicy,
            "task": MigrationTask,
            "status": MigrationStatus,
            "priority": MigrationPriority
        }
    except ImportError as e:
        logger.error(f"❌ Failed to import migration module: {e}")
        return False, None

def test_policy_management(migration_classes):
    """Test policy management functionality."""
    MigrationController = migration_classes["controller"]
    MigrationPolicy = migration_classes["policy"]
    
    # Create a temporary file for the controller
    temp_file = f"/tmp/migration_test_{int(time.time())}.json"
    
    # Initialize controller
    controller = MigrationController(config_path=temp_file)
    
    # Create a test policy
    policy = MigrationPolicy(
        name="test_policy",
        source_backend="ipfs",
        destination_backend="s3",
        content_filter={"type": "all"},
        schedule="manual"
    )
    
    # Add policy
    if not controller.add_policy(policy):
        logger.error("❌ Failed to add policy")
        return False
    
    # Get policy
    retrieved_policy = controller.get_policy("test_policy")
    if not retrieved_policy or retrieved_policy.name != "test_policy":
        logger.error("❌ Failed to retrieve policy")
        return False
    
    # List policies
    policies = controller.list_policies()
    if len(policies) != 1 or policies[0].name != "test_policy":
        logger.error("❌ Failed to list policies")
        return False
    
    # Remove policy
    if not controller.remove_policy("test_policy"):
        logger.error("❌ Failed to remove policy")
        return False
    
    # Verify policy was removed
    policies = controller.list_policies()
    if len(policies) != 0:
        logger.error("❌ Policy was not removed")
        return False
    
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    logger.info("✅ Policy management tests passed")
    return True

def test_task_management(migration_classes):
    """Test task management functionality."""
    MigrationController = migration_classes["controller"]
    MigrationTask = migration_classes["task"]
    
    # Create a temporary file for the controller
    temp_file = f"/tmp/migration_task_test_{int(time.time())}.json"
    
    # Initialize controller
    controller = MigrationController(config_path=temp_file)
    
    # Create a test task
    task = MigrationTask(
        source_backend="ipfs",
        destination_backend="s3",
        content_id="test_content_id"
    )
    
    # Schedule task
    if not controller.schedule_migration(task):
        logger.error("❌ Failed to schedule migration task")
        return False
    
    # Get task status
    status = controller.get_migration_status(task.id)
    if not status or status.id != task.id:
        logger.error("❌ Failed to retrieve task status")
        return False
    
    # Cancel task
    if not controller.cancel_migration(task.id):
        logger.error("❌ Failed to cancel migration task")
        return False
    
    # Verify task was cancelled
    status = controller.get_migration_status(task.id)
    if not status or status.status.value != "cancelled":
        logger.error("❌ Task was not properly cancelled")
        return False
    
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    logger.info("✅ Task management tests passed")
    return True

def test_policy_execution(migration_classes):
    """Test policy execution functionality."""
    # For this test, we'll create a mock backend manager that
    # can simulate listing content from a backend
    
    MigrationController = migration_classes["controller"]
    MigrationPolicy = migration_classes["policy"]
    
    class MockBackend:
        def __init__(self, name, items=None):
            self.name = name
            self.items = items or []
        
        def list(self, prefix=None):
            if prefix:
                filtered_items = [
                    item for item in self.items
                    if item["identifier"].startswith(prefix)
                ]
            else:
                filtered_items = self.items
            
            return {
                "success": True,
                "items": filtered_items
            }
        
        def get_content(self, content_id):
            return {
                "success": True,
                "data": f"Content for {content_id}".encode()
            }
        
        def get_metadata(self, content_id):
            return {
                "success": True,
                "metadata": {"content_id": content_id}
            }
        
        def add_content(self, content, metadata=None):
            return {
                "success": True,
                "identifier": f"new_{hash(content)}"
            }
    
    class MockBackendManager:
        def __init__(self):
            self.backends = {}
        
        def add_backend(self, name, backend):
            self.backends[name] = backend
        
        def get_backend(self, name):
            return self.backends.get(name)
    
    # Create a temporary file for the controller
    temp_file = f"/tmp/migration_policy_test_{int(time.time())}.json"
    
    # Create mock backend manager with test data
    manager = MockBackendManager()
    
    # Create mock backends
    source_backend = MockBackend("ipfs", [
        {"identifier": "item1", "metadata": {"type": "document"}},
        {"identifier": "item2", "metadata": {"type": "image"}},
        {"identifier": "prefix_item3", "metadata": {"type": "document"}}
    ])
    
    dest_backend = MockBackend("s3")
    
    # Add backends to manager
    manager.add_backend("ipfs", source_backend)
    manager.add_backend("s3", dest_backend)
    
    # Initialize controller with mock backend manager
    controller = MigrationController(backend_manager=manager, config_path=temp_file)
    
    # Create a test policy
    policy = MigrationPolicy(
        name="test_execution_policy",
        source_backend="ipfs",
        destination_backend="s3",
        content_filter={"type": "all"},
        schedule="manual"
    )
    
    # Add policy
    controller.add_policy(policy)
    
    # Execute policy
    task_ids = controller.execute_policy("test_execution_policy")
    
    # Verify tasks were created
    if len(task_ids) != len(source_backend.items):
        logger.error(f"❌ Expected {len(source_backend.items)} tasks, got {len(task_ids)}")
        return False
    
    # Create a filtered policy
    filtered_policy = MigrationPolicy(
        name="filtered_policy",
        source_backend="ipfs",
        destination_backend="s3",
        content_filter={"prefix": "prefix_"},
        schedule="manual"
    )
    
    # Add policy
    controller.add_policy(filtered_policy)
    
    # Execute policy
    filtered_task_ids = controller.execute_policy("filtered_policy")
    
    # Verify filtered tasks were created
    expected_filtered_count = len([
        item for item in source_backend.items
        if item["identifier"].startswith("prefix_")
    ])
    
    if len(filtered_task_ids) != expected_filtered_count:
        logger.error(f"❌ Expected {expected_filtered_count} filtered tasks, got {len(filtered_task_ids)}")
        return False
    
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    logger.info("✅ Policy execution tests passed")
    return True

def main():
    """Run all migration verification tests."""
    logger.info("Starting Migration Controller verification tests...")
    
    # Test 1: Import the migration module
    import_success, migration_classes = test_migration_imports()
    if not import_success:
        logger.error("❌ Migration module import tests failed")
        return False
    
    # Test 2: Test policy management
    if not test_policy_management(migration_classes):
        logger.error("❌ Policy management tests failed")
        return False
    
    # Test 3: Test task management
    if not test_task_management(migration_classes):
        logger.error("❌ Task management tests failed")
        return False
    
    # Test 4: Test policy execution
    if not test_policy_execution(migration_classes):
        logger.error("❌ Policy execution tests failed")
        return False
    
    logger.info("\n=== TEST RESULT ===")
    logger.info("✅ All Migration Controller tests passed!")
    logger.info("The Cross-Backend Data Migration functionality is working correctly.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)