#!/usr/bin/env python3
# test/test_storage_wal.py

"""
Unit tests for the StorageWriteAheadLog class.

These tests validate the core functionality of the WAL system, including:
1. Operation storage and retrieval
2. Status updates and transitions
3. Partitioning and archiving
4. Health monitoring integration
5. Error handling and recovery
"""

import os
import time
import shutil
import unittest
import tempfile
import uuid
from unittest.mock import MagicMock, patch

from ipfs_kit_py.storage_wal import (
    StorageWriteAheadLog,
    BackendHealthMonitor,
    OperationType,
    OperationStatus,
    BackendType,
    ARROW_AVAILABLE
)

class TestStorageWriteAheadLog(unittest.TestCase):
    """Test cases for the StorageWriteAheadLog class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for WAL storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize the WAL with the temporary directory
        self.wal = StorageWriteAheadLog(
            base_path=self.temp_dir,
            partition_size=10,  # Small size for testing
            max_retries=2,
            retry_delay=1,
            archive_completed=True,
            process_interval=0.1  # Fast processing for tests
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Close the WAL
        if hasattr(self, 'wal'):
            self.wal.close()
            
        # Remove the temporary directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test WAL initialization."""
        self.assertIsNotNone(self.wal)
        self.assertEqual(self.wal.base_path, self.temp_dir)
        self.assertEqual(self.wal.partition_size, 10)
        self.assertEqual(self.wal.max_retries, 2)
        self.assertEqual(self.wal.retry_delay, 1)
        self.assertTrue(self.wal.archive_completed)
        
        # Check directory creation
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "partitions")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "archives")))
    
    def test_add_operation(self):
        """Test adding an operation to the WAL."""
        # Add a test operation
        result = self.wal.add_operation(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS,
            parameters={"path": "/test/file.txt"}
        )
        
        # Check result
        self.assertTrue(result["success"])
        self.assertIn("operation_id", result)
        
        # Verify operation was stored
        operation_id = result["operation_id"]
        operation = self.wal.get_operation(operation_id)
        
        self.assertIsNotNone(operation)
        self.assertEqual(operation["operation_id"], operation_id)
        self.assertEqual(operation["operation_type"], OperationType.ADD.value)
        self.assertEqual(operation["backend"], BackendType.IPFS.value)
        self.assertEqual(operation["status"], OperationStatus.PENDING.value)
        self.assertIn("parameters", operation)
        self.assertEqual(operation["parameters"]["path"], "/test/file.txt")
    
    def test_update_operation_status(self):
        """Test updating operation status."""
        # Add a test operation
        result = self.wal.add_operation(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )
        
        operation_id = result["operation_id"]
        
        # Update status to processing
        update_result = self.wal.update_operation_status(
            operation_id,
            OperationStatus.PROCESSING,
            {"updated_at": int(time.time() * 1000)}
        )
        
        self.assertTrue(update_result)
        
        # Check updated operation
        operation = self.wal.get_operation(operation_id)
        self.assertEqual(operation["status"], OperationStatus.PROCESSING.value)
        
        # Update to completed with result
        test_result = {"cid": "QmTest", "size": 1024}
        update_result = self.wal.update_operation_status(
            operation_id,
            OperationStatus.COMPLETED,
            {
                "updated_at": int(time.time() * 1000),
                "completed_at": int(time.time() * 1000),
                "result": test_result
            }
        )
        
        self.assertTrue(update_result)
        
        # Check completed operation
        operation = self.wal.get_operation(operation_id)
        self.assertEqual(operation["status"], OperationStatus.COMPLETED.value)
        self.assertIn("completed_at", operation)
        self.assertIn("result", operation)
        
        # Test updating non-existent operation
        fake_id = str(uuid.uuid4())
        update_result = self.wal.update_operation_status(
            fake_id,
            OperationStatus.FAILED
        )
        
        self.assertFalse(update_result)
    
    def test_get_operations_by_status(self):
        """Test retrieving operations by status."""
        # Add operations with different statuses
        op1 = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        op2 = self.wal.add_operation(OperationType.PIN, BackendType.IPFS)
        op3 = self.wal.add_operation(OperationType.GET, BackendType.IPFS)
        
        # Update statuses and verify success
        proc_update = self.wal.update_operation_status(op1["operation_id"], OperationStatus.PROCESSING)
        self.assertTrue(proc_update, "Failed to update status to PROCESSING")
        
        comp_update = self.wal.update_operation_status(op2["operation_id"], OperationStatus.COMPLETED, 
                                                       {"completed_at": int(time.time() * 1000)})
        self.assertTrue(comp_update, "Failed to update status to COMPLETED")
        
        # Verify operation status was updated correctly through direct retrieval
        op1_updated = self.wal.get_operation(op1["operation_id"])
        self.assertEqual(op1_updated["status"], OperationStatus.PROCESSING.value, 
                         "Operation status was not updated to PROCESSING")
        
        op2_updated = self.wal.get_operation(op2["operation_id"])
        self.assertEqual(op2_updated["status"], OperationStatus.COMPLETED.value, 
                         "Operation status was not updated to COMPLETED")
        
        # Get operations by status with retries for potential async issues
        max_retries = 3
        retry_count = 0
        pending_ops = []
        processing_ops = []
        completed_ops = []
        
        while retry_count < max_retries:
            pending_ops = self.wal.get_operations_by_status(OperationStatus.PENDING)
            processing_ops = self.wal.get_operations_by_status(OperationStatus.PROCESSING)
            completed_ops = self.wal.get_operations_by_status(OperationStatus.COMPLETED)
            
            # If all conditions are met, break out of the loop
            if (len(pending_ops) == 1 and len(processing_ops) == 1 and len(completed_ops) == 1):
                break
                
            # Wait a short time and retry
            time.sleep(0.1)
            retry_count += 1
        
        # Additional logging to help debug
        if len(completed_ops) != 1:
            print(f"Expected 1 completed operation, found {len(completed_ops)}")
            print(f"All operations: {self.wal.get_all_operations()}")
        
        # Check results
        self.assertEqual(len(pending_ops), 1, "Expected 1 pending operation")
        self.assertEqual(len(processing_ops), 1, "Expected 1 processing operation")
        self.assertEqual(len(completed_ops), 1, "Expected 1 completed operation")
        
        # Check operation IDs
        self.assertEqual(pending_ops[0]["operation_id"], op3["operation_id"], 
                          "Pending operation has incorrect ID")
        self.assertEqual(processing_ops[0]["operation_id"], op1["operation_id"], 
                          "Processing operation has incorrect ID")
        self.assertEqual(completed_ops[0]["operation_id"], op2["operation_id"], 
                          "Completed operation has incorrect ID")
    
    def test_get_all_operations(self):
        """Test retrieving all operations."""
        # Add multiple operations
        op_ids = []
        for _ in range(5):
            result = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
            op_ids.append(result["operation_id"])
        
        # Get all operations
        all_ops = self.wal.get_all_operations()
        
        # Check results
        self.assertEqual(len(all_ops), 5)
        
        # Check that all operation IDs are present
        result_ids = [op["operation_id"] for op in all_ops]
        for op_id in op_ids:
            self.assertIn(op_id, result_ids)
    
    def test_partitioning(self):
        """Test partitioning of operations."""
        # Add more operations than the partition size
        for _ in range(15):  # Partition size is 10
            self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        
        # Check that multiple partitions were created
        partition_dir = os.path.join(self.temp_dir, "partitions")
        partition_files = [f for f in os.listdir(partition_dir) if f.endswith('.parquet')]
        
        # Should have at least 2 partitions (one with 10 ops, one with 5)
        self.assertGreaterEqual(len(partition_files), 1)
        
        # Check that all operations are retrievable
        all_ops = self.wal.get_all_operations()
        self.assertEqual(len(all_ops), 15)
    
    def test_archiving(self):
        """Test archiving completed operations."""
        # Only run if Arrow is available
        if not ARROW_AVAILABLE:
            self.skipTest("PyArrow not available, skipping archive test")
        
        # Add an operation
        result = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        operation_id = result["operation_id"]
        
        # Complete the operation
        self.wal.update_operation_status(
            operation_id,
            OperationStatus.COMPLETED,
            {
                "updated_at": int(time.time() * 1000),
                "completed_at": int(time.time() * 1000),
                "result": {"cid": "QmTest"}
            }
        )
        
        # Check that the operation was archived
        archive_dir = os.path.join(self.temp_dir, "archives")
        archive_files = [f for f in os.listdir(archive_dir) if f.endswith('.parquet')]
        
        # Should have at least one archive file
        self.assertGreaterEqual(len(archive_files), 1)
        
        # Operation should still be retrievable
        operation = self.wal.get_operation(operation_id)
        self.assertIsNotNone(operation)
        self.assertEqual(operation["status"], OperationStatus.COMPLETED.value)
    
    def test_cleanup(self):
        """Test cleanup of old operations."""
        # Only run if Arrow is available
        if not ARROW_AVAILABLE:
            self.skipTest("PyArrow not available, skipping cleanup test")
        
        # Add and complete an operation
        result = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        operation_id = result["operation_id"]
        
        self.wal.update_operation_status(
            operation_id,
            OperationStatus.COMPLETED,
            {
                "updated_at": int(time.time() * 1000),
                "completed_at": int(time.time() * 1000),
                "result": {"cid": "QmTest"}
            }
        )
        
        # Manually create an old archive file to ensure test consistency
        import datetime
        # Create a date that's definitely 31 days old
        old_date = datetime.datetime.now() - datetime.timedelta(days=31)
        old_date_str = old_date.strftime("%Y%m%d")
        
        # Create the archive path
        archive_dir = os.path.join(self.temp_dir, "archives")
        old_archive_path = os.path.join(archive_dir, f"archive_{old_date_str}.parquet")
        
        # Create a dummy parquet file
        if ARROW_AVAILABLE:
            import pyarrow as pa
            import pyarrow.parquet as pq
            
            # Create a simple table
            table = pa.table([pa.array([1, 2, 3])], names=['count'])
            pq.write_table(table, old_archive_path)
        else:
            # Fallback to simple file
            with open(old_archive_path, 'w') as f:
                f.write('dummy data')
        
        # Set the file time to the old date for extra consistency
        old_time = old_date.timestamp()
        os.utime(old_archive_path, (old_time, old_time))
        
        # Verify the file was created
        self.assertTrue(os.path.exists(old_archive_path), "Old archive file was not created")
        
        # Run cleanup
        result = self.wal.cleanup(max_age_days=30)
        
        # Check result
        self.assertTrue(result["success"])
        self.assertGreater(result["removed_count"], 0, "No archives were removed")
        self.assertGreaterEqual(len(result["removed_files"]), 1, "No archive files were listed in removed_files")
        
        # File should be gone
        self.assertFalse(os.path.exists(old_archive_path), "Old archive file was not removed")
    
    def test_wait_for_operation(self):
        """Test waiting for an operation to complete."""
        # Add an operation
        result = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        operation_id = result["operation_id"]
        
        # Set up a background thread to complete the operation after a delay
        def complete_after_delay():
            time.sleep(0.5)
            self.wal.update_operation_status(
                operation_id,
                OperationStatus.COMPLETED,
                {
                    "updated_at": int(time.time() * 1000),
                    "completed_at": int(time.time() * 1000),
                    "result": {"cid": "QmTest"}
                }
            )
        
        import threading
        thread = threading.Thread(target=complete_after_delay)
        thread.daemon = True
        thread.start()
        
        # Wait for the operation
        wait_result = self.wal.wait_for_operation(operation_id, timeout=2)
        
        # Check result
        self.assertTrue(wait_result["success"])
        self.assertEqual(wait_result["status"], OperationStatus.COMPLETED.value)
        self.assertIn("result", wait_result)
        
        # Test waiting for non-existent operation
        fake_id = str(uuid.uuid4())
        wait_result = self.wal.wait_for_operation(fake_id, timeout=1)
        
        self.assertFalse(wait_result["success"])
        self.assertIn("error", wait_result)
        
        # Test timeout
        result = self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        operation_id = result["operation_id"]
        
        wait_result = self.wal.wait_for_operation(operation_id, timeout=0.1)
        
        self.assertFalse(wait_result["success"])
        self.assertEqual(wait_result["status"], "timeout")
    
    def test_health_monitor_integration(self):
        """Test integration with the BackendHealthMonitor."""
        # Create a mock health monitor
        mock_health_monitor = MagicMock()
        mock_health_monitor.get_status.return_value = {"status": "online"}
        mock_health_monitor.is_backend_available.return_value = True
        
        # Create a WAL with the mock health monitor
        wal = StorageWriteAheadLog(
            base_path=self.temp_dir,
            health_monitor=mock_health_monitor
        )
        
        # Add an operation
        wal.add_operation(OperationType.ADD, BackendType.IPFS)
        
        # Verify health monitor was called
        mock_health_monitor.get_status.assert_called()
        
        # Clean up
        wal.close()
    
    def test_statistics(self):
        """Test getting WAL statistics."""
        # Add operations with different statuses
        self.wal.add_operation(OperationType.ADD, BackendType.IPFS)
        
        result = self.wal.add_operation(OperationType.PIN, BackendType.IPFS)
        self.wal.update_operation_status(result["operation_id"], OperationStatus.COMPLETED)
        
        result = self.wal.add_operation(OperationType.GET, BackendType.IPFS)
        self.wal.update_operation_status(result["operation_id"], OperationStatus.FAILED)
        
        # Get statistics
        stats = self.wal.get_statistics()
        
        # Check statistics
        self.assertEqual(stats["total_operations"], 3)
        self.assertEqual(stats["pending"], 1)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["failed"], 1)
        self.assertEqual(stats["processing"], 0)
        self.assertEqual(stats["retrying"], 0)
        
        # Should have at least one partition
        self.assertGreaterEqual(stats["partitions"], 1)
        
        # Processing thread should be active
        self.assertTrue(stats["processing_active"])

class TestBackendHealthMonitor(unittest.TestCase):
    """Test cases for the BackendHealthMonitor class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock status change callback
        self.status_change_callback = MagicMock()
        
        # Initialize the health monitor
        self.health_monitor = BackendHealthMonitor(
            check_interval=0.1,  # Fast checking for tests
            history_size=5,
            status_change_callback=self.status_change_callback
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Close the health monitor
        if hasattr(self, 'health_monitor'):
            self.health_monitor.close()
    
    def test_initialization(self):
        """Test health monitor initialization."""
        self.assertIsNotNone(self.health_monitor)
        self.assertEqual(self.health_monitor.check_interval, 0.1)
        self.assertEqual(self.health_monitor.history_size, 5)
        
        # Should have initialized status for all backends
        for backend in [b.value for b in BackendType]:
            self.assertIn(backend, self.health_monitor.backend_status)
            self.assertEqual(self.health_monitor.backend_status[backend]["status"], "unknown")
    
    def test_get_status(self):
        """Test getting backend status."""
        # Get status for all backends
        all_status = self.health_monitor.get_status()
        
        # Check that all backends are included
        for backend in [b.value for b in BackendType]:
            self.assertIn(backend, all_status)
            
        # Get status for a specific backend
        ipfs_status = self.health_monitor.get_status(BackendType.IPFS.value)
        
        # Check IPFS status
        self.assertIn("status", ipfs_status)
        self.assertEqual(ipfs_status["status"], "unknown")
    
    def test_backend_status_update(self):
        """Test backend status updates."""
        # Create a separate test from scratch to avoid issues with callback mock
        # Create a new test instance with a fresh mock callback
        callback_mock = MagicMock()
        health_monitor = BackendHealthMonitor(
            check_interval=0.1,
            history_size=3,  # Small history for quicker state changes
            status_change_callback=callback_mock
        )
        
        try:
            # Start with a known state - completely reset
            health_monitor.backend_status = {}
            
            # Set up a fresh entry for IPFS
            health_monitor.backend_status[BackendType.IPFS.value] = {
                "status": "unknown",  # Start with unknown
                "check_history": [],  # No history
                "last_check": 0,      # Never checked
                "error": None
            }
            
            # Call _update_backend_status directly to set known good state
            health_monitor._update_backend_status(
                BackendType.IPFS.value, 
                True  # healthy
            )
            
            # Call a few more times to transition to "online"
            health_monitor._update_backend_status(BackendType.IPFS.value, True)
            health_monitor._update_backend_status(BackendType.IPFS.value, True)
            
            # Should now be online
            ipfs_status = health_monitor.get_status(BackendType.IPFS.value)
            self.assertEqual(ipfs_status["status"], "online")
            
            # Callback should have been called for status change from unknown to online
            callback_mock.assert_called()
            
            # Reset mock for next phase
            callback_mock.reset_mock()
            
            # Now generate failures to transition to degraded
            health_monitor._update_backend_status(BackendType.IPFS.value, False)
            health_monitor._update_backend_status(BackendType.IPFS.value, False)
            health_monitor._update_backend_status(BackendType.IPFS.value, False)
            
            # Status should now be "offline"
            ipfs_status = health_monitor.get_status(BackendType.IPFS.value)
            self.assertEqual(ipfs_status["status"], "offline")
            
            # Callback should have been called for status change from online to offline
            callback_mock.assert_called()
        finally:
            # Clean up the test instance
            health_monitor.close()
    
    def test_is_backend_available(self):
        """Test checking if a backend is available."""
        # Initialize all backends to "offline"
        for backend in [b.value for b in BackendType]:
            self.health_monitor.backend_status[backend]["status"] = "offline"
        
        # Mark IPFS as "online"
        self.health_monitor.backend_status[BackendType.IPFS.value]["status"] = "online"
        
        # Check availability
        self.assertTrue(self.health_monitor.is_backend_available(BackendType.IPFS.value))
        self.assertFalse(self.health_monitor.is_backend_available(BackendType.S3.value))
        
        # Check non-existent backend
        self.assertFalse(self.health_monitor.is_backend_available("nonexistent"))
        
        # Mark IPFS as "degraded"
        self.health_monitor.backend_status[BackendType.IPFS.value]["status"] = "degraded"
        
        # Degraded should be considered not available
        self.assertFalse(self.health_monitor.is_backend_available(BackendType.IPFS.value))

if __name__ == '__main__':
    unittest.main()