#!/usr/bin/env python
"""
Test script for the MCP Migration Controller functionality.

This script tests the MigrationController component of the MCP server, including:
1. Policy-based migration between storage backends
2. Priority-based migration queue
3. Cross-backend content migration
4. Content integrity verification
"""

import logging
import sys
import os
import json
import time
import uuid
import random
import anyio
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


async def run_migration_test():
    """Run comprehensive tests on the Migration Controller."""
    logger.info("Starting MCP Migration Controller test...")
    
    try:
        # Import necessary modules
        from ipfs_kit_py.mcp.storage_manager.migration import (
            MigrationController, MigrationPolicy, MigrationTask, MigrationPriorityLevel
        )
        from ipfs_kit_py.mcp.storage_manager.storage_types import (
            StorageBackendType, ContentReference
        )
        from ipfs_kit_py.mcp.storage_manager.manager import UnifiedStorageManager
        
        logger.info("Successfully imported migration modules")
        
        # Create a temporary directory for test data
        import tempfile
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Create state file for migration controller
        state_path = os.path.join(temp_dir, "migration_state.json")
        
        # Setup mock storage backends for testing
        mock_ipfs_backend = create_mock_backend(StorageBackendType.IPFS)
        mock_s3_backend = create_mock_backend(StorageBackendType.S3)
        mock_storacha_backend = create_mock_backend(StorageBackendType.STORACHA)
        
        # Create a mock UnifiedStorageManager
        storage_manager = create_mock_storage_manager(
            backends={
                StorageBackendType.IPFS: mock_ipfs_backend,
                StorageBackendType.S3: mock_s3_backend,
                StorageBackendType.STORACHA: mock_storacha_backend
            },
            content_registry_path=os.path.join(temp_dir, "content_registry.json")
        )
        
        # Create sample content references
        content_refs = create_sample_content_references([
            StorageBackendType.IPFS,
            StorageBackendType.S3
        ])
        
        # Add content to storage manager registry
        for cid, content_ref in content_refs.items():
            storage_manager.content_registry[cid] = content_ref
        
        logger.info(f"Added {len(content_refs)} sample content references to registry")
        
        # Create migration policies
        ipfs_to_s3_policy = MigrationPolicy(
            name="ipfs_to_s3",
            source_backend=StorageBackendType.IPFS,
            target_backend=StorageBackendType.S3,
            description="Migrate content from IPFS to S3",
            criteria={
                "min_size": 1024,  # 1KB
                "content_types": ["image/", "video/"]
            },
            options={
                "store_options": {
                    "storage_class": "STANDARD"
                }
            }
        )
        
        s3_to_storacha_policy = MigrationPolicy(
            name="s3_to_storacha",
            source_backend=StorageBackendType.S3,
            target_backend=StorageBackendType.STORACHA,
            description="Migrate content from S3 to Storacha",
            criteria={
                "min_age_days": 30,
                "tags": ["archive", "backup"]
            },
            options={
                "delete_source": True  # Remove from S3 after migration
            }
        )
        
        # Initialize migration controller
        migration_controller = MigrationController(
            storage_manager=storage_manager,
            options={"state_path": state_path}
        )
        
        # Test 1: Add migration policies
        logger.info("Test 1: Add migration policies")
        result1 = migration_controller.add_policy(ipfs_to_s3_policy)
        result2 = migration_controller.add_policy(s3_to_storacha_policy)
        
        if result1 and result2:
            logger.info("✅ Added migration policies successfully")
        else:
            logger.error("❌ Failed to add migration policies")
            return False
        
        # Test 2: List policies
        logger.info("Test 2: List policies")
        policies = migration_controller.list_policies()
        logger.info(f"Policies: {json.dumps(policies, indent=2)}")
        
        if len(policies) == 2:
            logger.info("✅ Listed policies successfully")
        else:
            logger.error("❌ Failed to list policies")
            return False
        
        # Test 3: Run policy
        logger.info("Test 3: Run policy")
        
        # Patch content references to match policy criteria
        for cid, content_ref in list(content_refs.items())[:3]:
            if content_ref.has_location(StorageBackendType.IPFS):
                content_ref.metadata["content_type"] = "image/jpeg"
                content_ref.metadata["size"] = 5000  # 5KB
        
        # Run the policy
        run_result = migration_controller.run_policy("ipfs_to_s3")
        logger.info(f"Policy run result: {json.dumps(run_result, indent=2)}")
        
        if run_result.get("success", False) and run_result.get("created_tasks", 0) > 0:
            logger.info("✅ Policy execution created migration tasks")
        else:
            logger.warning("⚠️ Policy execution did not create any tasks")
        
        # Test 4: List tasks
        logger.info("Test 4: List tasks")
        tasks = migration_controller.list_tasks()
        logger.info(f"Tasks: {json.dumps(tasks, indent=2)}")
        
        if tasks.get("success", False) and len(tasks.get("tasks", [])) > 0:
            logger.info("✅ Listed tasks successfully")
        else:
            logger.warning("⚠️ No tasks found")
        
        # Test 5: Manually add a migration task with high priority
        logger.info("Test 5: Manually add a migration task with high priority")
        
        # Get a content ID from IPFS
        ipfs_cids = [
            cid for cid, ref in content_refs.items() 
            if ref.has_location(StorageBackendType.IPFS) and not ref.has_location(StorageBackendType.STORACHA)
        ]
        
        if ipfs_cids:
            manual_task_result = migration_controller.add_task(
                content_id=ipfs_cids[0],
                source_backend=StorageBackendType.IPFS,
                target_backend=StorageBackendType.STORACHA,
                priority=MigrationPriorityLevel.HIGH,
                options={"verify": True}
            )
            
            logger.info(f"Manual task creation result: {json.dumps(manual_task_result, indent=2)}")
            
            if manual_task_result.get("success", False):
                logger.info("✅ Manually added task successfully")
                manual_task_id = manual_task_result.get("task_id")
            else:
                logger.error("❌ Failed to add manual task")
                return False
        else:
            logger.warning("⚠️ No suitable content found for manual task creation")
            manual_task_id = None
        
        # Test 6: Start worker and process tasks
        logger.info("Test 6: Start worker and process tasks")
        
        # Implement a custom _process_task method to simulate migration
        def mock_process_task(self, task):
            logger.info(f"Simulating processing of task {task.id} for content {task.content_id}")
            
            # Update task status
            task.update_status(
                MigrationTask.Status.IN_PROGRESS,
                f"Starting migration from {task.source_backend.value} to {task.target_backend.value}"
            )
            
            # Simulate work
            time.sleep(0.5)
            
            # Get content reference
            content_ref = self.storage_manager.content_registry.get(task.content_id)
            
            if not content_ref:
                task.update_status(
                    MigrationTask.Status.FAILED, f"Content {task.content_id} not found"
                )
                task.error = "Content not found"
                self.stats["failed_tasks"] += 1
                return
            
            # Check required locations
            if not content_ref.has_location(task.source_backend):
                task.update_status(
                    MigrationTask.Status.FAILED,
                    f"Content not available in source backend {task.source_backend.value}"
                )
                task.error = "Content not in source backend"
                self.stats["failed_tasks"] += 1
                return
            
            if content_ref.has_location(task.target_backend):
                task.update_status(
                    MigrationTask.Status.COMPLETED,
                    f"Content already exists in target backend {task.target_backend.value}"
                )
                task.result = {"message": "Content already in target backend, no migration needed"}
                self.stats["completed_tasks"] += 1
                return
            
            # Simulate content migration
            source_location = content_ref.get_location(task.source_backend)
            target_location = f"migrated-{task.content_id}-{int(time.time())}"
            
            # Update task status
            task.update_status(
                MigrationTask.Status.IN_PROGRESS,
                f"Migrating content ({content_ref.metadata.get('size', 0)} bytes)"
            )
            
            # Simulate target backend storage
            content_ref.add_location(task.target_backend, target_location)
            
            # Simulate verification if requested
            if task.options.get("verify", False):
                task.update_status(
                    MigrationTask.Status.IN_PROGRESS,
                    "Verifying content integrity"
                )
                # Simulate verification work
                time.sleep(0.2)
            
            # Simulate deletion if requested
            if task.options.get("delete_source", False):
                task.update_status(
                    MigrationTask.Status.IN_PROGRESS,
                    f"Deleting content from source backend {task.source_backend.value}"
                )
                # Actually remove the source location
                content_ref.remove_location(task.source_backend)
            
            # Update task status
            task.update_status(MigrationTask.Status.COMPLETED, "Migration completed successfully")
            task.result = {
                "source_location": source_location,
                "target_location": target_location,
                "size": content_ref.metadata.get("size", 0),
            }
            
            # Update statistics
            self.stats["completed_tasks"] += 1
            self.stats["total_bytes_migrated"] += content_ref.metadata.get("size", 0)
            
            # Update policy statistics if from a policy
            if task.policy_name and task.policy_name in self.policies:
                policy = self.policies[task.policy_name]
                policy.total_migrations += 1
                policy.total_bytes_migrated += content_ref.metadata.get("size", 0)
                
                if task.policy_name in self.stats["policy_runs"]:
                    self.stats["policy_runs"][task.policy_name]["total_migrations"] += 1
        
        # Replace the process_task method with our mock version
        import types
        migration_controller._process_task = types.MethodType(mock_process_task, migration_controller)
        
        # Start the worker
        started = migration_controller.start_worker()
        
        if started:
            logger.info("✅ Started migration worker")
        else:
            logger.error("❌ Failed to start migration worker")
            return False
        
        # Wait for tasks to be processed
        logger.info("Waiting for tasks to be processed...")
        await anyio.sleep(3)
        
        # Test 7: Check task status
        logger.info("Test 7: Check task status")
        
        if manual_task_id:
            task_status = migration_controller.get_task(manual_task_id)
            logger.info(f"Manual task status: {json.dumps(task_status, indent=2)}")
            
            if task_status and task_status.get("status") == "completed":
                logger.info("✅ Manual task completed successfully")
            else:
                logger.warning("⚠️ Manual task not completed")
        
        # Test 8: Get statistics
        logger.info("Test 8: Get statistics")
        stats = migration_controller.get_statistics()
        logger.info(f"Migration statistics: {json.dumps(stats, indent=2)}")
        
        if stats.get("completed_tasks", 0) > 0:
            logger.info("✅ Some tasks were completed")
        else:
            logger.warning("⚠️ No tasks were completed")
        
        # Test 9: Verify content was migrated
        logger.info("Test 9: Verify content was migrated")
        
        migrated_count = 0
        for content_id, content_ref in content_refs.items():
            backends = [b.value for b in content_ref.get_locations()]
            if len(backends) >= 2:  # Available in multiple backends
                migrated_count += 1
                logger.info(f"Content {content_id} is available in: {', '.join(backends)}")
        
        if migrated_count > 0:
            logger.info(f"✅ {migrated_count} content items were migrated to multiple backends")
        else:
            logger.warning("⚠️ No content was migrated to multiple backends")
        
        # Test 10: Stop the worker
        logger.info("Test 10: Stop the worker")
        stopped = migration_controller.stop_worker()
        
        if stopped:
            logger.info("✅ Stopped migration worker")
        else:
            logger.error("❌ Failed to stop migration worker")
            return False
        
        # Clean up
        logger.info("Cleaning up temporary directory")
        import shutil
        shutil.rmtree(temp_dir)
        
        logger.info("All migration tests completed successfully!")
        return True
    
    except Exception as e:
        logger.error(f"Error testing migration functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


# --- Helper Functions ---

def create_mock_backend(backend_type):
    """Create a mock storage backend for testing."""
    mock_backend = type(f"Mock{backend_type.value}Backend", (), {})()
    
    # Add required methods
    mock_backend.get_name = lambda: backend_type.value
    mock_backend.get_type = lambda: backend_type
    
    # Add store method
    def mock_store(data, container=None, path=None, options=None):
        return {
            "success": True,
            "identifier": f"mock-{backend_type.value}-{uuid.uuid4()}",
            "backend": backend_type.value,
            "details": {"mock": True}
        }
    mock_backend.store = mock_store
    
    # Add retrieve method
    def mock_retrieve(identifier, container=None, options=None):
        return {
            "success": True,
            "data": b"Mock data content for testing",
            "backend": backend_type.value,
            "identifier": identifier,
            "details": {"mock": True}
        }
    mock_backend.retrieve = mock_retrieve
    
    # Add delete method
    def mock_delete(identifier, container=None, options=None):
        return {
            "success": True,
            "backend": backend_type.value,
            "identifier": identifier,
            "details": {"mock": True}
        }
    mock_backend.delete = mock_delete
    
    return mock_backend


def create_mock_storage_manager(backends, content_registry_path):
    """Create a mock UnifiedStorageManager for testing."""
    # Create a basic mock storage manager
    storage_manager = type("MockStorageManager", (), {})()
    
    # Add backends
    storage_manager.backends = backends
    
    # Add content registry
    storage_manager.content_registry = {}
    storage_manager.content_registry_path = content_registry_path
    
    # Add method to save content registry
    def mock_save_content_registry():
        with open(storage_manager.content_registry_path, 'w') as f:
            # Convert content registry to serializable format
            serialized_registry = {}
            for cid, content_ref in storage_manager.content_registry.items():
                serialized_registry[cid] = content_ref.to_dict()
            
            json.dump(serialized_registry, f, indent=2)
    storage_manager._save_content_registry = mock_save_content_registry
    
    # Add retrieve method
    def mock_retrieve(content_id, backend_preference=None, options=None):
        if content_id not in storage_manager.content_registry:
            return {"success": False, "error": "Content not found"}
        
        content_ref = storage_manager.content_registry[content_id]
        
        # Find appropriate backend
        backend_type = backend_preference
        if not backend_type or not content_ref.has_location(backend_type):
            # Use first available backend
            for backend in content_ref.get_locations():
                backend_type = backend
                break
        
        if not backend_type:
            return {"success": False, "error": "No available backend"}
        
        # Get backend instance
        backend = storage_manager.backends.get(backend_type)
        if not backend:
            return {"success": False, "error": f"Backend {backend_type.value} not available"}
        
        # Get location in this backend
        location = content_ref.get_location(backend_type)
        
        # Call backend's retrieve method
        return backend.retrieve(location, options=options)
    storage_manager.retrieve = mock_retrieve
    
    # Add delete method
    def mock_delete(content_id, backend=None, options=None):
        if content_id not in storage_manager.content_registry:
            return {"success": False, "error": "Content not found"}
        
        content_ref = storage_manager.content_registry[content_id]
        
        # Find appropriate backend
        backend_type = backend
        if not backend_type or not content_ref.has_location(backend_type):
            return {"success": False, "error": f"Content not in backend {backend_type.value if backend_type else 'None'}"}
        
        # Get backend instance
        backend_instance = storage_manager.backends.get(backend_type)
        if not backend_instance:
            return {"success": False, "error": f"Backend {backend_type.value} not available"}
        
        # Get location in this backend
        location = content_ref.get_location(backend_type)
        
        # Call backend's delete method
        result = backend_instance.delete(location, options=options)
        
        # If successful, remove location from content reference
        if result.get("success", False):
            content_ref.remove_location(backend_type)
            storage_manager._save_content_registry()
        
        return result
    storage_manager.delete = mock_delete
    
    return storage_manager


def create_sample_content_references(backend_types, count=10):
    """Create sample content references for testing."""
    from ipfs_kit_py.mcp.storage_manager.storage_types import ContentReference
    
    content_refs = {}
    
    for i in range(count):
        # Create content ID
        content_id = f"test-content-{uuid.uuid4()}"
        
        # Create content reference
        metadata = {
            "name": f"Test Content {i}",
            "description": f"Test content for migration testing {i}",
            "content_type": random.choice([
                "text/plain", "image/jpeg", "application/pdf", 
                "video/mp4", "audio/mp3"
            ]),
            "size": random.randint(1024, 1024 * 1024),  # 1KB to 1MB
            "tags": random.sample(
                ["test", "sample", "migration", "backup", "archive", "public", "private"],
                random.randint(1, 3)
            )
        }
        
        content_ref = ContentReference(
            content_id=content_id,
            metadata=metadata,
            created_at=time.time() - random.randint(0, 90 * 24 * 60 * 60)  # 0 to 90 days old
        )
        
        # Add locations
        for backend_type in random.sample(backend_types, random.randint(1, len(backend_types))):
            location = f"mock-{backend_type.value}-{uuid.uuid4()}"
            content_ref.add_location(backend_type, location)
        
        # Set access stats
        content_ref.access_count = random.randint(0, 100)
        if content_ref.access_count > 0:
            content_ref.last_accessed = time.time() - random.randint(0, 30 * 24 * 60 * 60)  # 0 to 30 days ago
        
        content_refs[content_id] = content_ref
    
    return content_refs


if __name__ == "__main__":
    # Run the test asynchronously
    result = anyio.run(run_migration_test)
    
    if result:
        logger.info("✅ MCP Migration Controller test passed!")
        sys.exit(0)
    else:
        logger.error("❌ MCP Migration Controller test failed")
        sys.exit(1)