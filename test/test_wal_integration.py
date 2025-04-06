#!/usr/bin/env python3
# test/test_wal_integration.py

"""
Unit tests for the WAL integration module.

These tests validate the integration of the WAL system with the high-level API, including:
1. Decorator functionality
2. Parameter extraction
3. Operation handling
4. Error handling
"""

import os
import time
import shutil
import unittest
import tempfile
from unittest.mock import MagicMock, patch

from ipfs_kit_py.wal_integration import WALIntegration, with_wal
from ipfs_kit_py.storage_wal import (
    StorageWriteAheadLog,
    BackendHealthMonitor,
    OperationType,
    OperationStatus,
    BackendType
)

class TestWALIntegration(unittest.TestCase):
    """Test cases for the WALIntegration class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory for WAL storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock WAL
        self.mock_wal = MagicMock(spec=StorageWriteAheadLog)
        self.mock_wal.add_operation.return_value = {"success": True, "operation_id": "test-op-id"}
        self.mock_wal.update_operation_status.return_value = True
        self.mock_wal.get_operation.return_value = {"operation_id": "test-op-id", "status": "pending"}
        self.mock_wal.health_monitor = MagicMock()
        self.mock_wal.health_monitor.is_backend_available.return_value = True
        
        # Initialize the WAL integration with the mock WAL
        self.wal_integration = WALIntegration(wal=self.mock_wal)
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test initialization of WALIntegration."""
        # Test initialization with an existing WAL
        self.assertIsNotNone(self.wal_integration)
        self.assertEqual(self.wal_integration.wal, self.mock_wal)
        
        # Test initialization with config instead of WAL
        with patch('ipfs_kit_py.wal_integration.StorageWriteAheadLog') as mock_wal_class:
            with patch('ipfs_kit_py.wal_integration.BackendHealthMonitor') as mock_monitor_class:
                # Configure mocks
                mock_wal_instance = MagicMock()
                mock_wal_class.return_value = mock_wal_instance
                mock_monitor_instance = MagicMock()
                mock_monitor_class.return_value = mock_monitor_instance
                
                # Initialize with config
                config = {
                    "base_path": self.temp_dir,
                    "enable_health_monitoring": True
                }
                wal_integration = WALIntegration(config=config)
                
                # Check that WAL was created with config values
                mock_monitor_class.assert_called_once()
                mock_wal_class.assert_called_once()
                self.assertEqual(wal_integration.wal, mock_wal_instance)
    
    def test_decorator(self):
        """Test the with_wal decorator."""
        # Create a mock function to decorate
        mock_func = MagicMock(return_value={"success": True, "result": "test-result"})
        
        # Apply the decorator
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )(mock_func)
        
        # Call the decorated function
        result = decorated_func("arg1", "arg2", kwarg1="value1")
        
        # Check that WAL methods were called
        self.mock_wal.add_operation.assert_called_once()
        args, kwargs = self.mock_wal.add_operation.call_args
        self.assertEqual(args[0], OperationType.ADD)
        self.assertEqual(args[1], BackendType.IPFS)
        
        # Check that original function was called
        mock_func.assert_called_once_with("arg1", "arg2", kwarg1="value1")
        
        # Check that operation ID was added to result
        self.assertIn("wal_operation_id", result)
        self.assertEqual(result["wal_operation_id"], "test-op-id")
    
    def test_skip_wal_parameter(self):
        """Test the skip_wal parameter."""
        # Create a mock function to decorate
        mock_func = MagicMock(return_value={"success": True})
        
        # Apply the decorator
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )(mock_func)
        
        # Call the decorated function with skip_wal=True
        result = decorated_func("arg1", skip_wal=True)
        
        # Check that WAL methods were NOT called
        self.mock_wal.add_operation.assert_not_called()
        
        # Check that original function was called with skip_wal removed
        mock_func.assert_called_once_with("arg1")
    
    def test_parameter_extraction(self):
        """Test parameter extraction from method arguments."""
        # Test with string argument
        params = self.wal_integration._extract_parameters("test_method", ("self", "/path/to/file.txt"), {})
        self.assertEqual(params["path"], "/path/to/file.txt")
        
        # Test with CID argument
        params = self.wal_integration._extract_parameters("test_method", ("self", "QmTESTCID"), {})
        self.assertEqual(params["cid"], "QmTESTCID")
        
        # Test with content argument (bytes)
        content = b"Test content"
        params = self.wal_integration._extract_parameters("test_method", ("self", content), {})
        self.assertEqual(params["content_sample"], "Test content")
        
        # Test with keyword arguments
        params = self.wal_integration._extract_parameters(
            "test_method", 
            ("self",), 
            {"path": "/path/to/file.txt", "recursive": True}
        )
        self.assertEqual(params["path"], "/path/to/file.txt")
        self.assertTrue(params["recursive"])
    
    def test_wait_for_operation(self):
        """Test waiting for an operation to complete."""
        # Configure mock WAL to return specific operation
        operation_result = {
            "success": True,
            "status": OperationStatus.COMPLETED.value,
            "result": {"cid": "QmTest"}
        }
        self.mock_wal.wait_for_operation.return_value = operation_result
        
        # Call wait_for_operation
        result = self.wal_integration.wait_for_operation("test-op-id", timeout=10)
        
        # Check that WAL method was called with correct arguments
        self.mock_wal.wait_for_operation.assert_called_once_with("test-op-id", 10)
        
        # Check that result was returned correctly
        self.assertEqual(result, operation_result)
    
    def test_get_operation(self):
        """Test getting an operation by ID."""
        # Configure mock WAL to return specific operation
        operation = {
            "operation_id": "test-op-id",
            "status": OperationStatus.COMPLETED.value,
            "result": {"cid": "QmTest"}
        }
        self.mock_wal.get_operation.return_value = operation
        
        # Call get_operation
        result = self.wal_integration.get_operation("test-op-id")
        
        # Check that WAL method was called with correct arguments
        self.mock_wal.get_operation.assert_called_once_with("test-op-id")
        
        # Check that result was returned correctly
        self.assertEqual(result, operation)
    
    def test_decorator_with_failed_operation(self):
        """Test decorator behavior with a failed operation."""
        # Create a mock function that returns a failed result
        mock_func = MagicMock(return_value={"success": False, "error": "Test error"})
        
        # Apply the decorator
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )(mock_func)
        
        # Call the decorated function
        result = decorated_func("arg1")
        
        # Check that WAL methods were called
        self.mock_wal.add_operation.assert_called_once()
        self.mock_wal.update_operation_status.assert_called_once()
        
        # Verify that the operation was marked as failed
        args, kwargs = self.mock_wal.update_operation_status.call_args
        self.assertEqual(args[1], OperationStatus.FAILED)
        self.assertIn("error", kwargs[0])
        self.assertEqual(kwargs[0]["error"], "Test error")
        
        # Check that result contains WAL metadata
        self.assertIn("wal_operation_id", result)
        self.assertEqual(result["wal_status"], "failed")
    
    def test_decorator_with_exception(self):
        """Test decorator behavior when function raises an exception."""
        # Create a mock function that raises an exception
        mock_func = MagicMock(side_effect=ValueError("Test exception"))
        
        # Apply the decorator
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )(mock_func)
        
        # Call the decorated function
        with self.assertRaises(ValueError):
            decorated_func("arg1")
        
        # Check that WAL methods were called
        self.mock_wal.add_operation.assert_called_once()
        self.mock_wal.update_operation_status.assert_called_once()
        
        # Verify that the operation was marked as failed
        args, kwargs = self.mock_wal.update_operation_status.call_args
        self.assertEqual(args[1], OperationStatus.FAILED)
        self.assertIn("error", kwargs[0])
        self.assertEqual(kwargs[0]["error"], "Test exception")
        self.assertEqual(kwargs[0]["error_type"], "ValueError")
    
    def test_wait_for_completion(self):
        """Test decorator with wait_for_completion=True."""
        # Create a mock function
        mock_func = MagicMock(return_value={"success": True, "result": "test-result"})
        
        # Configure the wait_for_operation method to return a specific result
        wait_result = {
            "success": True,
            "status": OperationStatus.COMPLETED.value,
            "result": {"cid": "QmTest"}
        }
        self.wal_integration.wait_for_operation = MagicMock(return_value=wait_result)
        
        # Apply the decorator with wait_for_completion=True
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS,
            wait_for_completion=True
        )(mock_func)
        
        # Call the decorated function
        result = decorated_func("arg1")
        
        # Check that wait_for_operation was called
        self.wal_integration.wait_for_operation.assert_called_once()
        
        # Check that the result from wait_for_operation was returned
        self.assertEqual(result, wait_result)
    
    def test_backend_unavailable(self):
        """Test decorator behavior when backend is unavailable."""
        # Configure health monitor to indicate backend is unavailable
        self.mock_wal.health_monitor.is_backend_available.return_value = False
        
        # Create a mock function
        mock_func = MagicMock(return_value={"success": True})
        
        # Apply the decorator
        decorated_func = self.wal_integration.with_wal(
            operation_type=OperationType.ADD,
            backend=BackendType.IPFS
        )(mock_func)
        
        # Call the decorated function
        result = decorated_func("arg1")
        
        # Check that WAL add_operation was called
        self.mock_wal.add_operation.assert_called_once()
        
        # Check that original function was NOT called
        mock_func.assert_not_called()
        
        # Check that result indicates operation is pending
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "pending")
        self.assertIn("operation_id", result)
    
    def test_with_wal_function(self):
        """Test the with_wal global function."""
        with patch('ipfs_kit_py.wal_integration.WALIntegration.with_wal') as mock_with_wal:
            # Configure mock
            mock_decorator = MagicMock()
            mock_with_wal.return_value = mock_decorator
            
            # Create a mock WAL integration
            mock_integration = MagicMock()
            
            # Call the global with_wal function
            from ipfs_kit_py.wal_integration import with_wal as global_with_wal
            result = global_with_wal(
                operation_type=OperationType.ADD,
                backend=BackendType.IPFS,
                wal_integration=mock_integration,
                wait_for_completion=True
            )
            
            # Check that the instance method was called with correct arguments
            mock_with_wal.assert_called_once_with(
                operation_type=OperationType.ADD,
                backend=BackendType.IPFS,
                wait_for_completion=True,
                max_wait_time=60
            )
            
            # Check that the result is the mock decorator
            self.assertEqual(result, mock_decorator)
    
    def test_close(self):
        """Test closing the WAL integration."""
        # Call close method
        self.wal_integration.close()
        
        # Check that WAL close method was called
        self.mock_wal.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()