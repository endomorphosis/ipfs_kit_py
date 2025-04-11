"""
Test module for BaseStorageModel in the MCP server.

This module contains unit tests for the BaseStorageModel class, which serves
as the foundation for all storage backend models in the MCP server.
"""

import unittest
import time
import os
import tempfile
from unittest.mock import MagicMock, patch

# Import the BaseStorageModel class
from ipfs_kit_py.mcp.models.storage.base_storage_model import BaseStorageModel

class TestBaseStorageModel(unittest.TestCase):
    """
    Test case for the BaseStorageModel class.
    
    This test case covers the initialization, statistics tracking, error handling,
    and utility methods provided by the BaseStorageModel class.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_kit = MagicMock()
        self.mock_cache_manager = MagicMock()
        self.mock_credential_manager = MagicMock()
        
        # Create test model
        self.model = BaseStorageModel(
            kit_instance=self.mock_kit,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )
        
        # Create temp file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        with open(self.temp_file.name, 'w') as f:
            f.write('test content')
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Delete temp file
        if hasattr(self, 'temp_file') and os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_initialization(self):
        """Test model initialization."""
        # Test with all dependencies
        model = BaseStorageModel(
            kit_instance=self.mock_kit,
            cache_manager=self.mock_cache_manager,
            credential_manager=self.mock_credential_manager
        )
        self.assertEqual(model.backend_name, "BaseStorage")
        self.assertEqual(model.kit, self.mock_kit)
        self.assertEqual(model.cache_manager, self.mock_cache_manager)
        self.assertEqual(model.credential_manager, self.mock_credential_manager)
        
        # Test with no dependencies
        model = BaseStorageModel()
        self.assertEqual(model.backend_name, "BaseStorage")
        self.assertIsNone(model.kit)
        self.assertIsNone(model.cache_manager)
        self.assertIsNone(model.credential_manager)
    
    def test_backend_name_derivation(self):
        """Test backend name derivation from class name."""
        # Test with standard class name (ending with 'Model')
        class TestModel(BaseStorageModel):
            pass
        
        model = TestModel()
        self.assertEqual(model.backend_name, "Test")
        
        # Test with non-standard class name (not ending with 'Model')
        class TestBackend(BaseStorageModel):
            pass
        
        model = TestBackend()
        self.assertEqual(model.backend_name, "TestBackend")
        
        # Test with custom backend name override
        class CustomModel(BaseStorageModel):
            def _get_backend_name(self):
                return "CustomName"
        
        model = CustomModel()
        self.assertEqual(model.backend_name, "CustomName")
    
    def test_stats_initialization(self):
        """Test statistics initialization."""
        stats = self.model.operation_stats
        
        # Verify required fields
        required_fields = [
            "upload_count", "download_count", "list_count", "delete_count",
            "total_operations", "success_count", "failure_count",
            "bytes_uploaded", "bytes_downloaded", "start_time", "last_operation_time"
        ]
        
        for field in required_fields:
            self.assertIn(field, stats)
            
        # Verify initial values
        self.assertEqual(stats["upload_count"], 0)
        self.assertEqual(stats["download_count"], 0)
        self.assertEqual(stats["list_count"], 0)
        self.assertEqual(stats["delete_count"], 0)
        self.assertEqual(stats["total_operations"], 0)
        self.assertEqual(stats["success_count"], 0)
        self.assertEqual(stats["failure_count"], 0)
        self.assertEqual(stats["bytes_uploaded"], 0)
        self.assertEqual(stats["bytes_downloaded"], 0)
        self.assertIsNone(stats["last_operation_time"])
        self.assertIsNotNone(stats["start_time"])
    
    def test_get_stats(self):
        """Test getting statistics."""
        stats = self.model.get_stats()
        
        # Verify result structure
        self.assertIn("backend_name", stats)
        self.assertIn("operation_stats", stats)
        self.assertIn("timestamp", stats)
        self.assertIn("uptime_seconds", stats)
        
        # Verify values
        self.assertEqual(stats["backend_name"], "BaseStorage")
        self.assertIsInstance(stats["operation_stats"], dict)
        self.assertIsInstance(stats["timestamp"], float)
        self.assertIsInstance(stats["uptime_seconds"], float)
    
    def test_reset(self):
        """Test resetting statistics."""
        # Modify some stats
        self.model.operation_stats["upload_count"] = 5
        self.model.operation_stats["download_count"] = 10
        self.model.operation_stats["bytes_uploaded"] = 1024
        
        # Reset stats
        result = self.model.reset()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "reset_stats")
        self.assertEqual(result["backend_name"], "BaseStorage")
        self.assertIn("previous_stats", result)
        self.assertIn("timestamp", result)
        
        # Verify previous stats in result
        self.assertEqual(result["previous_stats"]["upload_count"], 5)
        self.assertEqual(result["previous_stats"]["download_count"], 10)
        self.assertEqual(result["previous_stats"]["bytes_uploaded"], 1024)
        
        # Verify stats were reset
        self.assertEqual(self.model.operation_stats["upload_count"], 0)
        self.assertEqual(self.model.operation_stats["download_count"], 0)
        self.assertEqual(self.model.operation_stats["bytes_uploaded"], 0)
    
    def test_update_stats(self):
        """Test updating statistics."""
        # Test upload success
        # The method signature is: _update_stats(operation, success, duration_ms, bytes_count=None)
        # Note: duration_ms is required
        self.model._update_stats("upload", True, 100.0, 1024)  # Add duration_ms parameter
        self.assertEqual(self.model.operation_stats["upload_count"], 1)
        self.assertEqual(self.model.operation_stats["total_operations"], 1)
        self.assertEqual(self.model.operation_stats["success_count"], 1)
        self.assertEqual(self.model.operation_stats["failure_count"], 0)
        self.assertEqual(self.model.operation_stats["bytes_uploaded"], 1024)
        self.assertIsNotNone(self.model.operation_stats["last_operation_time"])
        
        # Test download failure
        self.model._update_stats("download", False, 200.0, 512)  # Add duration_ms parameter
        self.assertEqual(self.model.operation_stats["download_count"], 1)
        self.assertEqual(self.model.operation_stats["total_operations"], 2)
        self.assertEqual(self.model.operation_stats["success_count"], 1)
        self.assertEqual(self.model.operation_stats["failure_count"], 1)
        self.assertEqual(self.model.operation_stats["bytes_downloaded"], 512)
        
        # Test list operation
        self.model._update_stats("list", True, 50.0)  # Add duration_ms parameter
        self.assertEqual(self.model.operation_stats["list_count"], 1)
        self.assertEqual(self.model.operation_stats["total_operations"], 3)
        self.assertEqual(self.model.operation_stats["success_count"], 2)
        
        # Test delete operation
        self.model._update_stats("delete", True, 75.0)  # Add duration_ms parameter
        self.assertEqual(self.model.operation_stats["delete_count"], 1)
        self.assertEqual(self.model.operation_stats["total_operations"], 4)
        self.assertEqual(self.model.operation_stats["success_count"], 3)
    
    def test_create_operation_id(self):
        """Test creating operation IDs."""
        # Get multiple operation IDs
        op_id1 = self.model._create_operation_id("test")
        op_id2 = self.model._create_operation_id("test")
        
        # Verify format
        self.assertTrue(op_id1.startswith("basestorage_test_"))
        
        # Verify uniqueness
        self.assertNotEqual(op_id1, op_id2)
    
    def test_create_result_template(self):
        """Test creating result templates."""
        result = self.model._create_result_template("test_operation")
        
        # Verify structure
        self.assertIn("success", result)
        self.assertIn("operation", result)
        self.assertIn("operation_id", result)
        self.assertIn("backend_name", result)
        self.assertIn("timestamp", result)
        
        # Verify values
        self.assertFalse(result["success"])  # Default to False
        self.assertEqual(result["operation"], "test_operation")
        self.assertTrue(result["operation_id"].startswith("basestorage_test_operation_"))
        self.assertEqual(result["backend_name"], "BaseStorage")
        self.assertIsInstance(result["timestamp"], float)
    
    def test_handle_operation_result(self):
        """Test handling operation results."""
        # Create result template
        result = self.model._create_result_template("test_operation")
        result["success"] = True
        
        # Handle result
        start_time = time.time() - 1  # 1 second ago
        final_result = self.model._handle_operation_result(result, "upload", start_time, 2048)
        
        # Verify duration was added
        self.assertIn("duration_ms", final_result)
        self.assertGreater(final_result["duration_ms"], 900)  # At least ~900ms (accounting for potential timing variations)
        
        # Verify stats were updated
        self.assertEqual(self.model.operation_stats["upload_count"], 1)
        self.assertEqual(self.model.operation_stats["total_operations"], 1)
        self.assertEqual(self.model.operation_stats["success_count"], 1)
        self.assertEqual(self.model.operation_stats["bytes_uploaded"], 2048)
    
    def test_handle_exception(self):
        """Test handling exceptions."""
        # Create result template
        result = self.model._create_result_template("test_operation")
        
        # Create test exception
        test_exception = ValueError("Test error")
        
        # Handle exception
        handled_result = self.model._handle_exception(test_exception, result, "test_operation")
        
        # Verify error information was added
        self.assertFalse(handled_result["success"])
        self.assertEqual(handled_result["error"], "Test error")
        self.assertEqual(handled_result["error_type"], "ValueError")
        
        # Test with response-like exception
        class ResponseError(Exception):
            def __init__(self):
                self.response = MagicMock()
                self.response.status_code = 404
        
        response_error = ResponseError()
        handled_result = self.model._handle_exception(response_error, result, "test_operation")
        
        # Verify status code was added
        self.assertEqual(handled_result["status_code"], 404)
    
    def test_get_credentials_with_manager(self):
        """Test getting credentials with a credential manager."""
        # Set up mock credentials
        self.mock_credential_manager.get_credentials.return_value = {
            "api_key": "test_key",
            "secret": "test_secret"
        }
        
        # Get credentials
        credentials = self.model._get_credentials()
        
        # Verify result
        self.assertEqual(credentials["api_key"], "test_key")
        self.assertEqual(credentials["secret"], "test_secret")
        
        # Verify credential manager was called with correct service name
        self.mock_credential_manager.get_credentials.assert_called_with("basestorage")
        
        # Test with custom service name
        self.model._get_credentials("custom_service")
        self.mock_credential_manager.get_credentials.assert_called_with("custom_service")
    
    def test_get_credentials_without_manager(self):
        """Test getting credentials without a credential manager."""
        # Create model without credential manager
        model = BaseStorageModel(kit_instance=self.mock_kit)
        
        # Get credentials
        credentials = model._get_credentials()
        
        # Verify empty dict is returned
        self.assertEqual(credentials, {})
    
    def test_get_file_size(self):
        """Test getting file size."""
        # Get size of test file
        size = self.model._get_file_size(self.temp_file.name)
        
        # Verify size is correct
        self.assertEqual(size, 12)  # "test content" is 12 bytes
        
        # Test with nonexistent file
        size = self.model._get_file_size("/nonexistent/file")
        self.assertEqual(size, 0)
    
    def test_cache_operations(self):
        """Test cache operations."""
        # Test cache_put
        self.model._cache_put("test_key", "test_value", {"test_meta": "data"})
        
        # Verify cache manager was called with correct parameters
        self.mock_cache_manager.put.assert_called_with(
            "basestorage:test_key", 
            "test_value", 
            {"test_meta": "data"}
        )
        
        # Test cache_get
        self.mock_cache_manager.get.return_value = "cached_value"
        value = self.model._cache_get("test_key")
        
        # Verify cache manager was called with correct key
        self.mock_cache_manager.get.assert_called_with("basestorage:test_key")
        
        # Verify returned value
        self.assertEqual(value, "cached_value")
    
    def test_cache_operations_without_cache_manager(self):
        """Test cache operations without a cache manager."""
        # Create model without cache manager
        model = BaseStorageModel(kit_instance=self.mock_kit)
        
        # Test cache_put
        result = model._cache_put("test_key", "test_value")
        self.assertFalse(result)
        
        # Test cache_get
        value = model._cache_get("test_key")
        self.assertIsNone(value)
    
    def test_health_check(self):
        """Test health check method."""
        # Test with all dependencies available
        result = self.model.health_check()
        
        # Verify structure and values
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "health_check")
        self.assertEqual(result["backend_name"], "BaseStorage")
        self.assertTrue(result["kit_available"])
        self.assertTrue(result["cache_available"])
        self.assertTrue(result["credential_available"])
        self.assertIn("duration_ms", result)
        
        # Test with version getter
        self.mock_kit.get_version = MagicMock(return_value="1.2.3")
        result = self.model.health_check()
        self.assertEqual(result["version"], "1.2.3")
        
        # Test with version getter that raises exception
        self.mock_kit.get_version.side_effect = Exception("Version error")
        result = self.model.health_check()
        self.assertEqual(result["version"], "unknown")
        
        # Test without kit
        model = BaseStorageModel()
        result = model.health_check()
        self.assertFalse(result["success"])
        self.assertFalse(result["kit_available"])
        self.assertFalse(result["cache_available"])
        self.assertFalse(result["credential_available"])
    
    def test_health_check_exception_handling(self):
        """Test health check exception handling."""
        # Mock kit to raise exception during health check
        self.mock_kit.side_effect = Exception("Test error")
        
        # Create a model class that raises an exception in health check but properly handles it
        class ErrorModel(BaseStorageModel):
            def health_check(self):
                result = self._create_result_template("health_check")
                start_time = time.time()
                try:
                    raise ValueError("Test health check error")
                except Exception as e:
                    return self._handle_exception(e, result, "health_check")
                
        # Create model instance
        model = ErrorModel(kit_instance=self.mock_kit)
        
        # Patch handle_exception to verify it's called
        with patch.object(model, '_handle_exception') as mock_handle_exception:
            mock_handle_exception.return_value = {"success": False, "error": "Test error"}
            
            # Call health_check
            result = model.health_check()
            
            # Verify handle_exception was called
            mock_handle_exception.assert_called_once()
            
            # Verify error handling result
            self.assertEqual(result, {"success": False, "error": "Test error"})

if __name__ == '__main__':
    unittest.main()