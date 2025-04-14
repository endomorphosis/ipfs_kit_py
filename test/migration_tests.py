"""
Cross-Backend Migration Tests

This module provides end-to-end tests for cross-backend migrations,
verifying the MCP storage manager's ability to move content between
different types of storage backends.
"""

import os
import time
import uuid
import logging
import unittest
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migration-tests")

# Import storage backends
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
from ipfs_kit_py.mcp.storage_manager.backends.s3_backend import S3Backend
from ipfs_kit_py.mcp.storage_manager.backends.storacha_backend import StorachaBackend
from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

# Import migration controller
from ipfs_kit_py.mcp.storage_manager.migration import MigrationController, MigrationPolicy, MigrationPriorityLevel
from ipfs_kit_py.mcp.storage_manager.storage_types import ContentReference


# Mock UnifiedStorageManager for testing
class MockStorageManager:
    """Mock storage manager for testing with real backends."""
    
    def __init__(self):
        """Initialize the mock storage manager."""
        self.backends = {}
        self.content_registry = {}
        self.options = {
            "state_path": f"migration_test_state_{uuid.uuid4().hex[:8]}.json"
        }
    
    def add_backend(self, backend_type, backend):
        """Add a backend to the storage manager."""
        self.backends[backend_type] = backend
    
    def get_backends(self):
        """Get all available backends."""
        return [
            {"type": backend_type.value, "name": backend.get_name()}
            for backend_type, backend in self.backends.items()
        ]
    
    def get_statistics(self):
        """Get statistics about the storage system."""
        return {
            "content_count": len(self.content_registry),
            "total_content_size": sum(ref.metadata.get("size", 0) for ref in self.content_registry.values()),
            "backend_counts": {
                backend_type.value: len([
                    ref for ref in self.content_registry.values() 
                    if ref.has_location(backend_type)
                ])
                for backend_type in self.backends.keys()
            }
        }
    
    def register_content(self, content_id, backend_type, identifier, metadata=None):
        """Register content with the storage manager."""
        if content_id not in self.content_registry:
            self.content_registry[content_id] = ContentReference(content_id)
        
        self.content_registry[content_id].add_location(backend_type, identifier)
        
        if metadata:
            current_metadata = self.content_registry[content_id].metadata
            self.content_registry[content_id].metadata = {**current_metadata, **metadata}
    
    def _save_content_registry(self):
        """Mock method to save content registry for controller compatibility."""
        pass


class MigrationTest(unittest.TestCase):
    """Test class for cross-backend migrations."""
    
    def setUp(self):
        """Set up the test environment for migration testing."""
        # Track created content for cleanup
        self.created_content = {}  # {content_id: {backend_type: [identifiers]}}
        
        # Initialize backends
        self.storage_manager = MockStorageManager()
        
        # Try to initialize each backend
        self.initialized_backends = {}
        
        # Initialize IPFS backend
        try:
            ipfs_resources = {
                "ipfs_api_url": os.environ.get("IPFS_API_URL", "http://localhost:5001"),
                "ipfs_gateway_url": os.environ.get("IPFS_GATEWAY_URL", "http://localhost:8080"),
                "mock_mode": os.environ.get("IPFS_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
                "timeout": 30
            }
            ipfs_metadata = {"default_pin": True, "verify_cids": True}
            
            ipfs_backend = IPFSBackend(ipfs_resources, ipfs_metadata)
            self.storage_manager.add_backend(StorageBackendType.IPFS, ipfs_backend)
            self.initialized_backends[StorageBackendType.IPFS] = ipfs_backend
            logger.info("Initialized IPFS backend")
        except Exception as e:
            logger.warning(f"Failed to initialize IPFS backend: {e}")
        
        # Initialize S3 backend
        try:
            # Generate a unique test bucket name
            test_bucket_suffix = uuid.uuid4().hex[:8]
            test_bucket_name = f"mcp-migration-test-{test_bucket_suffix}"
            
            s3_resources = {
                "aws_access_key": os.environ.get("AWS_ACCESS_KEY_ID", ""),
                "aws_secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
                "region": os.environ.get("AWS_REGION", "us-east-1"),
                "endpoint_url": os.environ.get("S3_ENDPOINT_URL", ""),
                "bucket": test_bucket_name,
                "mock_mode": os.environ.get("S3_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
                "max_threads": 5,
                "connection_timeout": 10,
                "read_timeout": 30,
                "max_retries": 3
            }
            s3_metadata = {
                "cache_ttl": 3600,  # 1 hour
                "cache_size_limit": 100 * 1024 * 1024  # 100MB
            }
            
            s3_backend = S3Backend(s3_resources, s3_metadata)
            self.storage_manager.add_backend(StorageBackendType.S3, s3_backend)
            self.initialized_backends[StorageBackendType.S3] = s3_backend
            self.s3_test_bucket = test_bucket_name
            logger.info("Initialized S3 backend")
        except Exception as e:
            logger.warning(f"Failed to initialize S3 backend: {e}")
        
        # Initialize Storacha backend
        try:
            storacha_resources = {
                "api_key": os.environ.get("W3S_API_KEY", ""),
                "endpoints": os.environ.get("W3S_ENDPOINTS", "https://api.web3.storage,https://w3s.link"),
                "mock_mode": os.environ.get("W3S_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
                "max_threads": 5,
                "connection_timeout": 10,
                "read_timeout": 30,
                "max_retries": 3
            }
            
            # If endpoints is a string, convert to list
            if isinstance(storacha_resources["endpoints"], str):
                storacha_resources["endpoints"] = [e.strip() for e in storacha_resources["endpoints"].split(",")]
            
            storacha_metadata = {
                "cache_ttl": 3600,  # 1 hour
                "cache_size_limit": 100 * 1024 * 1024  # 100MB
            }
            
            storacha_backend = StorachaBackend(storacha_resources, storacha_metadata)
            self.storage_manager.add_backend(StorageBackendType.STORACHA, storacha_backend)
            self.initialized_backends[StorageBackendType.STORACHA] = storacha_backend
            logger.info("Initialized Storacha backend")
        except Exception as e:
            logger.warning(f"Failed to initialize Storacha backend: {e}")
        
        # Initialize Filecoin backend
        try:
            filecoin_resources = {
                "api_key": os.environ.get("FILECOIN_API_KEY", ""),
                "endpoint": os.environ.get("FILECOIN_ENDPOINT", ""),
                "mock_mode": os.environ.get("FILECOIN_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
                "max_retries": 3
            }
            
            filecoin_metadata = {
                "default_miner": os.environ.get("FILECOIN_DEFAULT_MINER", "t01000"),
                "replication_count": 1,
                "verify_deals": True,
                "max_price": "100000000000",  # In attoFIL (0.0001 FIL)
                "deal_duration": 518400  # 180 days in epochs
            }
            
            filecoin_backend = FilecoinBackend(filecoin_resources, filecoin_metadata)
            
            # Only add if not in unavailable mode
            if not hasattr(filecoin_backend, 'mode') or filecoin_backend.mode != "unavailable":
                self.storage_manager.add_backend(StorageBackendType.FILECOIN, filecoin_backend)
                self.initialized_backends[StorageBackendType.FILECOIN] = filecoin_backend
                self.filecoin_default_miner = filecoin_metadata["default_miner"]
                logger.info("Initialized Filecoin backend")
        except Exception as e:
            logger.warning(f"Failed to initialize Filecoin backend: {e}")
        
        # Check if we have at least two backends for migration testing
        if len(self.initialized_backends) < 2:
            self.skipTest("Need at least two initialized backends for migration tests")
        
        # Initialize migration controller
        try:
            self.migration_controller = MigrationController(
                storage_manager=self.storage_manager,
                policies=[],
                options={"state_path": f"migration_test_state_{uuid.uuid4().hex[:8]}.json"}
            )
            logger.info("Initialized migration controller")
        except Exception as e:
            logger.error(f"Failed to initialize migration controller: {e}")
            self.skipTest(f"Failed to initialize migration controller: {e}")
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up created content from all backends
        for content_id, backends in self.created_content.items():
            for backend_type, identifiers in backends.items():
                backend = self.initialized_backends.get(backend_type)
                if backend:
                    for identifier in identifiers:
                        try:
                            container = None
                            if backend_type == StorageBackendType.S3 and hasattr(self, "s3_test_bucket"):
                                container = self.s3_test_bucket
                            elif backend_type == StorageBackendType.FILECOIN and hasattr(self, "filecoin_default_miner"):
                                container = self.filecoin_default_miner
                                
                            backend.delete(identifier, container)
                            logger.info(f"Cleaned up {identifier} from {backend_type.value}")
                        except Exception as e:
                            logger.warning(f"Error cleaning up {identifier} from {backend_type.value}: {e}")
        
        # Clean up temp files
        if hasattr(self.migration_controller, "options") and "state_path" in self.migration_controller.options:
            state_path = self.migration_controller.options["state_path"]
            if os.path.exists(state_path):
                try:
                    os.remove(state_path)
                    logger.info(f"Removed migration state file: {state_path}")
                except Exception as e:
                    logger.warning(f"Error removing migration state file {state_path}: {e}")
    
    def _store_test_content(self, backend_type, content="Test content for migration", container=None, path=None):
        """Store test content in a specific backend and track for cleanup."""
        if backend_type not in self.initialized_backends:
            self.skipTest(f"Backend {backend_type.value} not initialized")
        
        backend = self.initialized_backends[backend_type]
        
        # If no container specified, use default for the backend type
        if container is None:
            if backend_type == StorageBackendType.S3 and hasattr(self, "s3_test_bucket"):
                container = self.s3_test_bucket
            elif backend_type == StorageBackendType.FILECOIN and hasattr(self, "filecoin_default_miner"):
                container = self.filecoin_default_miner
        
        # Generate a unique content ID and path if not provided
        content_id = f"mcp-test-content-{uuid.uuid4().hex[:8]}"
        if not path:
            path = f"test-{uuid.uuid4().hex[:8]}.txt"
        
        # Store content in the backend
        result = backend.store(content, container, path)
        self.assertTrue(result.get("success", False), 
                        f"Failed to store content in {backend_type.value}: {result.get('error', 'Unknown error')}")
        
        # Get identifier
        identifier = result.get("identifier")
        self.assertIsNotNone(identifier, f"No identifier returned from store operation in {backend_type.value}")
        
        # Register content with the storage manager
        self.storage_manager.register_content(
            content_id, 
            backend_type, 
            identifier, 
            {"size": len(content) if isinstance(content, (str, bytes)) else 0}
        )
        
        # Track for cleanup
        if content_id not in self.created_content:
            self.created_content[content_id] = {}
        
        if backend_type not in self.created_content[content_id]:
            self.created_content[content_id][backend_type] = []
        
        self.created_content[content_id][backend_type].append(identifier)
        
        return content_id, identifier
    
    def _verify_content_migration(self, content_id, source_backend_type, target_backend_type, 
                                  source_container=None, target_container=None, expected_content=None):
        """Verify that content has been migrated correctly between backends."""
        # Check content exists in source backend
        source_backend = self.initialized_backends.get(source_backend_type)
        self.assertIsNotNone(source_backend, f"Source backend {source_backend_type.value} not initialized")
        
        # Check content exists in target backend
        target_backend = self.initialized_backends.get(target_backend_type)
        self.assertIsNotNone(target_backend, f"Target backend {target_backend_type.value} not initialized")
        
        # Get content reference from storage manager
        content_ref = self.storage_manager.content_registry.get(content_id)
        self.assertIsNotNone(content_ref, f"Content {content_id} not found in storage manager")
        
        # Check if content exists in both backends according to the content reference
        self.assertTrue(content_ref.has_location(source_backend_type), 
                        f"Content should exist in source backend {source_backend_type.value}")
        self.assertTrue(content_ref.has_location(target_backend_type), 
                        f"Content should exist in target backend {target_backend_type.value}")
        
        # Get identifiers
        source_identifier = content_ref.get_location(source_backend_type)
        target_identifier = content_ref.get_location(target_backend_type)
        
        self.assertIsNotNone(source_identifier, f"No source identifier found for {content_id}")
        self.assertIsNotNone(target_identifier, f"No target identifier found for {content_id}")
        
        # Track target identifier for cleanup
        if content_id not in self.created_content:
            self.created_content[content_id] = {}
        
        if target_backend_type not in self.created_content[content_id]:
            self.created_content[content_id][target_backend_type] = []
        
        if target_identifier not in self.created_content[content_id][target_backend_type]:
            self.created_content[content_id][target_backend_type].append(target_identifier)
        
        # If expected content is provided, verify content in both backends
        if expected_content is not None:
            # Retrieve from source
            source_retrieve = source_backend.retrieve(source_identifier, source_container)
            self.assertTrue(source_retrieve.get("success", False), 
                            f"Failed to retrieve content from source: {source_retrieve.get('error', 'Unknown error')}")
            
            source_data = source_retrieve.get("data")
            self.assertIsNotNone(source_data, "No data returned from source backend")
            
            if isinstance(source_data, bytes) and isinstance(expected_content, str):
                source_text = source_data.decode('utf-8')
                self.assertEqual(expected_content, source_text, 
                                 "Source content doesn't match expected content")
            elif isinstance(source_data, bytes) and isinstance(expected_content, bytes):
                self.assertEqual(expected_content, source_data, 
                                 "Source content doesn't match expected content")
            
            # Retrieve from target
            target_retrieve = target_backend.retrieve(target_identifier, target_container)
            self.assertTrue(target_retrieve.get("success", False), 
                            f"Failed to retrieve content from target: {target_retrieve.get('error', 'Unknown error')}")
            
            target_data = target_retrieve.get("data")
            self.assertIsNotNone(target_data, "No data returned from target backend")
            
            if isinstance(target_data, bytes) and isinstance(expected_content, str):
                target_text = target_data.decode('utf-8')
                self.assertEqual(expected_content, target_text, 
                                 "Target content doesn't match expected content")
            elif isinstance(target_data, bytes) and isinstance(expected_content, bytes):
                self.assertEqual(expected_content, target_data, 
                                 "Target content doesn't match expected content")
            
            # Compare source and target directly
            if isinstance(source_data, bytes) and isinstance(target_data, bytes):
                self.assertEqual(source_data, target_data, 
                                 "Source and target content don't match")
        
        return source_identifier, target_identifier
    
    def test_manual_migration(self):
        """Test manual migration of content between backends."""
        # Find two backends to test with
        backend_types = list(self.initialized_backends.keys())
        self.assertGreaterEqual(len(backend_types), 2, "Need at least two backends for migration test")
        
        source_backend_type = backend_types[0]
        target_backend_type = backend_types[1]
        
        logger.info(f"Testing migration from {source_backend_type.value} to {target_backend_type.value}")
        
        # Store test content in source backend
        test_content = f"Manual migration test content {uuid.uuid4().hex[:8]}"
        content_id, source_identifier = self._store_test_content(source_backend_type, test_content)
        
        logger.info(f"Created test content with ID {content_id} in {source_backend_type.value}")
        
        # Create and add migration task
        task_result = self.migration_controller.add_task(
            content_id=content_id,
            source_backend=source_backend_type,
            target_backend=target_backend_type,
            priority=MigrationPriorityLevel.HIGH
        )
        
        self.assertTrue(task_result.get("success", False), 
                        f"Failed to add migration task: {task_result.get('error', 'Unknown error')}")
        
        task_id = task_result.get("task_id")
        self.assertIsNotNone(task_id, "No task ID returned from add_task")
        
        logger.info(f"Created migration task {task_id}")
        
        # Start the migration worker
        self.migration_controller.start_worker()
        
        # Wait for task completion
        max_wait_time = 60  # Maximum wait time in seconds
        wait_interval = 1    # Check interval in seconds
        elapsed_time = 0
        
        task_completed = False
        while elapsed_time < max_wait_time:
            task_info = self.migration_controller.get_task(task_id)
            if task_info is None:
                self.fail(f"Task {task_id} not found")
            
            task_status = task_info.get("status")
            if task_status in ["completed", "failed", "cancelled"]:
                task_completed = True
                break
            
            time.sleep(wait_interval)
            elapsed_time += wait_interval
        
        # Stop the worker
        self.migration_controller.stop_worker()
        
        # Verify task completion
        self.assertTrue(task_completed, f"Migration task didn't complete within {max_wait_time} seconds")
        
        # Get final task status
        final_task = self.migration_controller.get_task(task_id)
        self.assertEqual("completed", final_task.get("status"), 
                         f"Migration task failed: {final_task.get('error', 'Unknown error')}")
        
        logger.info(f"Migration task completed successfully: {final_task.get('result', {})}")
        
        # Verify content was migrated correctly
        source_id, target_id = self._verify_content_migration(
            content_id, source_backend_type, target_backend_type, expected_content=test_content
        )
        
        logger.info(f"Verified content migration: {source_id} to {target_id}")
        
        # Get migration statistics
        stats = self.migration_controller.get_statistics()
        logger.info(f"Migration statistics: {stats}")
        
        self.assertGreaterEqual(stats.get("completed_tasks", 0), 1, 
                                "Migration statistics should show at least one completed task")
    
    def test_policy_based_migration(self):
        """Test policy-based migration of content between backends."""
        # Find two backends to test with
        backend_types = list(self.initialized_backends.keys())
        self.assertGreaterEqual(len(backend_types), 2, "Need at least two backends for policy migration test")
        
        source_backend_type = backend_types[0]
        target_backend_type = backend_types[1]
        
        logger.info(f"Testing policy-based migration from {source_backend_type.value} to {target_backend_type.value}")
        
        # Store test content in source backend
        test_content = f"Policy migration test content {uuid.uuid4().hex[:8]}"
        content_id, source_identifier = self._store_test_content(source_backend_type, test_content)
        
        logger.info(f"Created test content with ID {content_id} in {source_backend_type.value}")
        
        # Create migration policy
        policy = MigrationPolicy(
            name=f"test-policy-{uuid.uuid4().hex[:6]}",
            source_backend=source_backend_type,
            target_backend=target_backend_type,
            description=f"Test migration from {source_backend_type.value} to {target_backend_type.value}",
            criteria={},  # Empty criteria should match all content
            options={}
        )
        
        # Add policy to controller
        self.migration_controller.add_policy(policy)
        
        # Run the policy
        policy_result = self.migration_controller.run_policy(policy.name)
        
        self.assertTrue(policy_result.get("success", False), 
                        f"Failed to run migration policy: {policy_result.get('error', 'Unknown error')}")
        
        task_ids = policy_result.get("task_ids", [])
        self.assertGreaterEqual(len(task_ids), 1, "Policy should have created at least one task")
        
        logger.info(f"Policy created {len(task_ids)} migration tasks")
        
        # Start the migration worker
        self.migration_controller.start_worker()
        
        # Wait for tasks to complete
        max_wait_time = 60  # Maximum wait time in seconds
        wait_interval = 1    # Check interval in seconds
        elapsed_time = 0
        
        tasks_completed = False
        while elapsed_time < max_wait_time:
            # Check if all tasks are completed
            all_completed = True
            for task_id in task_ids:
                task_info = self.migration_controller.get_task(task_id)
                if task_info is None:
                    self.fail(f"Task {task_id} not found")
                
                task_status = task_info.get("status")
                if task_status not in ["completed", "failed", "cancelled"]:
                    all_completed = False
                    break
            
            if all_completed:
                tasks_completed = True
                break
            
            time.sleep(wait_interval)
            elapsed_time += wait_interval
        
        # Stop the worker
        self.migration_controller.stop_worker()
        
        # Verify tasks completion
        self.assertTrue(tasks_completed, f"Migration tasks didn't complete within {max_wait_time} seconds")
        
        # Verify all tasks were successful
        for task_id in task_ids:
            final_task = self.migration_controller.get_task(task_id)
            self.assertEqual("completed", final_task.get("status"), 
                             f"Migration task {task_id} failed: {final_task.get('error', 'Unknown error')}")
        
        logger.info("All migration tasks completed successfully")
        
        # Verify content was migrated correctly
        source_id, target_id = self._verify_content_migration(
            content_id, source_backend_type, target_backend_type, expected_content=test_content
        )
        
        logger.info(f"Verified content migration: {source_id} to {target_id}")
        
        # Get policy statistics
        policies = self.migration_controller.list_policies()
        logger.info(f"Migration policies: {policies}")
        
        # Check policy stats in the first policy (should be our test policy)
        for policy_info in policies:
            if policy_info["name"] == policy.name:
                self.assertGreaterEqual(policy_info.get("run_count", 0), 1, 
                                        "Policy statistics should show at least one run")
                break
    
    def test_multi_backend_migration(self):
        """Test migration across multiple backends (chain migration)."""
        # We need at least 3 backends for this test
        backend_types = list(self.initialized_backends.keys())
        if len(backend_types) < 3:
            self.skipTest("Need at least three backends for multi-backend migration test")
        
        # Select three different backends
        first_backend_type = backend_types[0]
        second_backend_type = backend_types[1]
        third_backend_type = backend_types[2]
        
        logger.info(f"Testing multi-backend migration: {first_backend_type.value} -> {second_backend_type.value} -> {third_backend_type.value}")
        
        # Store test content in first backend
        test_content = f"Multi-backend migration test content {uuid.uuid4().hex[:8]}"
        content_id, first_identifier = self._store_test_content(first_backend_type, test_content)
        
        logger.info(f"Created test content with ID {content_id} in {first_backend_type.value}")
        
        # Create first migration task (first -> second)
        first_task_result = self.migration_controller.add_task(
            content_id=content_id,
            source_backend=first_backend_type,
            target_backend=second_backend_type,
            priority=MigrationPriorityLevel.HIGH
        )
        
        self.assertTrue(first_task_result.get("success", False), 
                        f"Failed to add first migration task: {first_task_result.get('error', 'Unknown error')}")
        
        first_task_id = first_task_result.get("task_id")
        self.assertIsNotNone(first_task_id, "No task ID returned from first add_task")
        
        logger.info(f"Created first migration task {first_task_id}")
        
        # Start the migration worker
        self.migration_controller.start_worker()
        
        # Wait for first task completion
        max_wait_time = 60  # Maximum wait time in seconds
        wait_interval = 1    # Check interval in seconds
        elapsed_time = 0
        
        first_task_completed = False
        while elapsed_time < max_wait_time:
            task_info = self.migration_controller.get_task(first_task_id)
            if task_info is None:
                self.fail(f"Task {first_task_id} not found")
            
            task_status = task_info.get("status")
            if task_status in ["completed", "failed", "cancelled"]:
                first_task_completed = True
                break
            
            time.sleep(wait_interval)
            elapsed_time += wait_interval
        
        # Verify first task completion
        self.assertTrue(first_task_completed, f"First migration task didn't complete within {max_wait_time} seconds")
        
        # Get final task status
        final_first_task = self.migration_controller.get_task(first_task_id)
        self.assertEqual("completed", final_first_task.get("status"), 
                         f"First migration task failed: {final_first_task.get('error', 'Unknown error')}")
        
        logger.info(f"First migration task completed successfully: {final_first_task.get('result', {})}")
        
        # Verify content was migrated to second backend
        first_id, second_id = self._verify_content_migration(
            content_id, first_backend_type, second_backend_type, expected_content=test_content
        )
        
        logger.info(f"Verified first migration: {first_id} to {second_id}")
        
        # Create second migration task (second -> third)
        second_task_result = self.migration_controller.add_task(
            content_id=content_id,
            source_backend=second_backend_type,
            target_backend=third_backend_type,
            priority=MigrationPriorityLevel.HIGH
        )
        
        self.assertTrue(second_task_result.get("success", False), 
                        f"Failed to add second migration task: {second_task_result.get('error', 'Unknown error')}")
        
        second_task_id = second_task_result.get("task_id")
        self.assertIsNotNone(second_task_id, "No task ID returned from second add_task")
        
        logger.info(f"Created second migration task {second_task_id}")
        
        # Reset timer for second task
        elapsed_time = 0
        second_task_completed = False
        
        # Wait for second task completion
        while elapsed_time < max_wait_time:
            task_info = self.migration_controller.get_task(second_task_id)
            if task_info is None:
                self.fail(f"Task {second_task_id} not found")
            
            task_status = task_info.get("status")
            if task_status in ["completed", "failed", "cancelled"]:
                second_task_completed = True
                break
            
            time.sleep(wait_interval)
            elapsed_time += wait_interval
        
        # Stop the worker
        self.migration_controller.stop_worker()
        
        # Verify second task completion
        self.assertTrue(second_task_completed, f"Second migration task didn't complete within {max_wait_time} seconds")
        
        # Get final second task status
        final_second_task = self.migration_controller.get_task(second_task_id)
        self.assertEqual("completed", final_second_task.get("status"), 
                         f"Second migration task failed: {final_second_task.get('error', 'Unknown error')}")
        
        logger.info(f"Second migration task completed successfully: {final_second_task.get('result', {})}")
        
        # Verify content was migrated to third backend
        second_id, third_id = self._verify_content_migration(
            content_id, second_backend_type, third_backend_type, expected_content=test_content
        )
        
        logger.info(f"Verified second migration: {second_id} to {third_id}")
        
        # Verify content exists in all three backends
        content_ref = self.storage_manager.content_registry.get(content_id)
        self.assertIsNotNone(content_ref, f"Content {content_id} not found in storage manager")
        
        self.assertTrue(content_ref.has_location(first_backend_type), 
                        f"Content should exist in first backend {first_backend_type.value}")
        self.assertTrue(content_ref.has_location(second_backend_type), 
                        f"Content should exist in second backend {second_backend_type.value}")
        self.assertTrue(content_ref.has_location(third_backend_type), 
                        f"Content should exist in third backend {third_backend_type.value}")
        
        logger.info(f"Content successfully migrated across all three backends")
        
        # Get migration statistics
        stats = self.migration_controller.get_statistics()
        logger.info(f"Migration statistics: {stats}")
        
        self.assertGreaterEqual(stats.get("completed_tasks", 0), 2, 
                                "Migration statistics should show at least two completed tasks")


# Allow running the tests directly
if __name__ == "__main__":
    unittest.main()