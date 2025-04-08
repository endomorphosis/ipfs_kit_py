"""Test the fixed get_filesystem implementation in fixed_high_level_api.py."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the fixed implementation
from ipfs_kit_py.fixed_high_level_api import IPFSSimpleAPI

# Create a mock version of IPFSSimpleAPI for testing
class MockIPFSKit(IPFSSimpleAPI):
    """Mock version of IPFSSimpleAPI for testing."""
    
    def __init__(self, config=None):
        """Initialize with test configuration."""
        self.config = config or {}
        self.kit = MagicMock()
        self._filesystem = None
        self.plugins = {}
        self.extensions = {}
    
    def _initialize_kit(self):
        """Mock kit initialization."""
        return MagicMock()

class TestImprovedGetFilesystem(unittest.TestCase):
    """Test cases for the improved get_filesystem implementation."""

    def setUp(self):
        """Set up mocks and test instances."""
        # Create patches
        self.fsspec_patcher = patch("ipfs_kit_py.fixed_high_level_api.FSSPEC_AVAILABLE", True)
        self.logger_patcher = patch("ipfs_kit_py.fixed_high_level_api.logger")
        
        # Start patches
        self.mock_fsspec_available = self.fsspec_patcher.start()
        self.mock_logger = self.logger_patcher.start()
        
        # Mock the kit initialization
        self.kit_patcher = patch("ipfs_kit_py.fixed_high_level_api.IPFSSimpleAPI._initialize_kit")
        self.mock_kit = self.kit_patcher.start()
        self.mock_kit.return_value = MagicMock()
        
        # Create a mock IPFSFileSystem
        self.mock_ipfs_filesystem = MagicMock()
        
        # Configure mock IPFSFileSystem
        self.mock_filesystem_instance = MagicMock()
        self.mock_ipfs_filesystem.return_value = self.mock_filesystem_instance
        
        # Create a mock ipfs_fsspec module since it's dynamically imported
        self.mock_ipfs_fsspec_module = MagicMock()
        self.mock_ipfs_fsspec_module.IPFSFileSystem = self.mock_ipfs_filesystem
        
        # Create sys.modules patcher for ipfs_kit_py.ipfs_fsspec
        self.sys_modules_patcher = patch.dict('sys.modules', {
            'ipfs_kit_py.ipfs_fsspec': self.mock_ipfs_fsspec_module
        })
        self.sys_modules_patcher.start()
        
        # Create test instance with a configuration
        self.test_config = {
            "role": "test_role",
            "cache": {"memory_size": 1000000},
            "gateway_urls": ["https://example.com"],
            "use_gateway_fallback": True,
            "gateway_only": False,
            "ipfs_path": "/test/ipfs",
            "socket_path": "/test/socket",
            "use_mmap": True,
            "enable_metrics": True
        }
        # Override fs initialization to test it independently
        with patch.object(IPFSSimpleAPI, 'get_filesystem', return_value=None):
            self.test_instance = IPFSSimpleAPI(config=self.test_config)
        
    def tearDown(self):
        """Clean up patches."""
        self.fsspec_patcher.stop()
        self.logger_patcher.stop()
        self.kit_patcher.stop()
        self.sys_modules_patcher.stop()
    
    def test_cache_reuse(self):
        """Test that the filesystem instance is cached and reused."""
        # First call should create the filesystem
        fs1 = self.test_instance.get_filesystem()
        self.assertEqual(fs1, self.mock_filesystem_instance)
        self.mock_ipfs_filesystem.assert_called_once()
        
        # Reset the mock to verify it's not called again
        self.mock_ipfs_filesystem.reset_mock()
        
        # Second call should reuse the cached instance
        fs2 = self.test_instance.get_filesystem()
        self.assertEqual(fs2, self.mock_filesystem_instance)
        self.mock_ipfs_filesystem.assert_not_called()
    
    def test_explicit_parameters(self):
        """Test that explicit parameters override config values."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Call with explicit parameters
        test_gateway_urls = ["https://override.com"]
        self.test_instance.get_filesystem(gateway_urls=test_gateway_urls)
        
        # Verify the parameters were passed correctly
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["gateway_urls"], test_gateway_urls)
    
    def test_config_parameters(self):
        """Test that config values are used when no explicit parameters provided."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Call method without explicit parameters
        self.test_instance.get_filesystem()
        
        # Verify config values were used
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["gateway_urls"], self.test_config["gateway_urls"])
        self.assertEqual(call_kwargs["use_gateway_fallback"], self.test_config["use_gateway_fallback"])
        self.assertEqual(call_kwargs["ipfs_path"], self.test_config["ipfs_path"])
    
    def test_cache_config_mapping(self):
        """Test the special case for cache_config mapping to config["cache"]."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Call method
        self.test_instance.get_filesystem()
        
        # Verify the cache config was correctly mapped
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["cache_config"], self.test_config["cache"])
    
    def test_fsspec_not_available(self):
        """Test behavior when fsspec is not available."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        self.mock_logger.reset_mock()
        
        # Create a fresh instance without caching
        fresh_instance = MockIPFSKit(config=self.test_config)
        
        # Need to patch the FSSPEC_AVAILABLE value in the instance's method
        # This is because the method will re-check FSSPEC_AVAILABLE internally
        with patch.object(fresh_instance, '_check_fsspec_available', return_value=False):
            # Should raise ImportError
            with self.assertRaises(ImportError):
                fresh_instance.get_filesystem()
                
            # Should return mock with return_mock=True
            mock_fs = fresh_instance.get_filesystem(return_mock=True)
            self.assertEqual(mock_fs.protocol, "ipfs")
            self.mock_logger.warning.assert_called()
    
    def test_import_error_handling(self):
        """Test handling of import errors for IPFSFileSystem."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        self.mock_logger.reset_mock()
        
        # Temporarily stop our sys.modules patch
        self.sys_modules_patcher.stop()
        
        # Create a patch that will cause the import to fail
        with patch.dict('sys.modules', {'ipfs_kit_py.ipfs_fsspec': None}):
            # Create a custom import handler
            def import_error(*args, **kwargs):
                raise ImportError("Mock import error")
                
            # Patch the import to fail
            with patch("ipfs_kit_py.fixed_high_level_api.FSSPEC_AVAILABLE", True):
                with patch.object(IPFSSimpleAPI, '_import_ipfs_filesystem', side_effect=import_error):
                    # Should raise ImportError
                    with self.assertRaises(ImportError):
                        fresh_instance = MockIPFSKit(config=self.test_config)
                        fresh_instance.get_filesystem()
                    
                    # Should return mock with return_mock=True
                    fresh_instance = MockIPFSKit(config=self.test_config)
                    mock_fs = fresh_instance.get_filesystem(return_mock=True)
                    self.assertEqual(mock_fs.protocol, "ipfs")
        
        # Restore our original sys.modules patch
        self.sys_modules_patcher = patch.dict('sys.modules', {
            'ipfs_kit_py.ipfs_fsspec': self.mock_ipfs_fsspec_module
        })
        self.sys_modules_patcher.start()
    
    def test_initialization_error(self):
        """Test handling of errors during IPFSFileSystem initialization."""
        # Reset mocks for clean test
        self.mock_logger.reset_mock()
        
        # Make the IPFSFileSystem initialization raise an error
        self.mock_ipfs_filesystem.side_effect = Exception("Test initialization error")
        
        # Should re-raise the exception
        with self.assertRaises(Exception):
            fresh_instance = MockIPFSKit(config=self.test_config)
            fresh_instance.get_filesystem()
            
        # Should return mock with return_mock=True
        fresh_instance = MockIPFSKit(config=self.test_config)
        mock_fs = fresh_instance.get_filesystem(return_mock=True)
        self.assertEqual(mock_fs.protocol, "ipfs")
        self.mock_logger.error.assert_called()
        
        # Restore normal behavior
        self.mock_ipfs_filesystem.side_effect = None
        self.mock_ipfs_filesystem.return_value = self.mock_filesystem_instance
    
    def test_kwargs_handling(self):
        """Test that additional kwargs are passed through correctly."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Call with additional kwargs
        additional_kwargs = {"extra_param": "value", "another_param": 123}
        self.test_instance.get_filesystem(**additional_kwargs)
        
        # Verify the additional kwargs were passed
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["extra_param"], "value")
        self.assertEqual(call_kwargs["another_param"], 123)
    
    def test_default_values(self):
        """Test that default values are used when neither explicit nor config values are present."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Create instance without config
        with patch.object(IPFSSimpleAPI, 'get_filesystem', return_value=None):
            instance_no_config = IPFSSimpleAPI()
        
        # Get filesystem
        instance_no_config.get_filesystem()
        
        # Verify default values were used
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["role"], "leecher")
        self.assertEqual(call_kwargs["use_mmap"], True)

    def test_return_mock_parameter(self):
        """Test that the return_mock parameter works correctly."""
        # Reset mock for clean test
        self.mock_ipfs_filesystem.reset_mock()
        
        # Make the IPFSFileSystem initialization raise an error
        self.mock_ipfs_filesystem.side_effect = Exception("Test initialization error")
        
        # With return_mock=True, should return a mock filesystem
        mock_fs = self.test_instance.get_filesystem(return_mock=True)
        self.assertEqual(mock_fs.protocol, "ipfs")
        self.mock_logger.error.assert_called()
        
        # Restore normal behavior
        self.mock_ipfs_filesystem.side_effect = None
        self.mock_ipfs_filesystem.return_value = self.mock_filesystem_instance

    def test_parameter_precedence(self):
        """Test the parameter precedence (explicit > kwargs > config > defaults)."""
        # Case 1: Explicit parameter should override everything
        # Create a fresh test instance and reset the mocks
        self.mock_ipfs_filesystem.reset_mock()
        test_instance = self.test_instance
        
        # Make sure the instance doesn't have a cached filesystem
        test_instance._filesystem = None
        
        # Call with explicit parameters
        test_instance.get_filesystem(
            gateway_urls=["https://explicit.com"],
            use_gateway_fallback=False,
            some_param="explicit"
        )
        
        # Verify the call arguments
        self.assertTrue(self.mock_ipfs_filesystem.called, "IPFSFileSystem constructor was not called")
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["gateway_urls"], ["https://explicit.com"])
        self.assertEqual(call_kwargs["use_gateway_fallback"], False)
        self.assertEqual(call_kwargs["some_param"], "explicit")
        
        # Case 2: kwargs should override config but not explicit params
        # Create a new test instance to avoid caching
        self.mock_ipfs_filesystem.reset_mock()
        with patch.object(IPFSSimpleAPI, 'get_filesystem', return_value=None):
            test_instance = IPFSSimpleAPI(config=self.test_config)
        
        # Call with explicit parameters and kwargs
        test_instance.get_filesystem(
            gateway_urls=["https://explicit.com"],  # Explicit will win
            **{"use_gateway_fallback": False, "some_param": "from_kwargs"}
        )
        
        # Verify the call arguments
        self.assertTrue(self.mock_ipfs_filesystem.called, "IPFSFileSystem constructor was not called")
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["gateway_urls"], ["https://explicit.com"])  # From explicit param
        self.assertEqual(call_kwargs["use_gateway_fallback"], False)  # From kwargs
        self.assertEqual(call_kwargs["some_param"], "from_kwargs")  # From kwargs
        
        # Case 3: Config should override defaults but not kwargs or explicit
        # Create instance with a different config
        self.mock_ipfs_filesystem.reset_mock()
        config_with_defaults = {
            "role": "config_role",
            "use_mmap": False  # Different from default
        }
        with patch.object(IPFSSimpleAPI, 'get_filesystem', return_value=None):
            instance_with_defaults = IPFSSimpleAPI(config=config_with_defaults)
        
        # Call without overriding params
        instance_with_defaults.get_filesystem()
        
        # Verify the call arguments
        self.assertTrue(self.mock_ipfs_filesystem.called, "IPFSFileSystem constructor was not called")
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["role"], "config_role")  # From config
        self.assertEqual(call_kwargs["use_mmap"], False)  # From config
        
        # Case 4: Defaults should be used when no other source provides the value
        # Create a new test instance without any config
        self.mock_ipfs_filesystem.reset_mock()
        with patch.object(IPFSSimpleAPI, 'get_filesystem', return_value=None):
            empty_config_instance = IPFSSimpleAPI(config={})
        
        # Call get_filesystem
        empty_config_instance.get_filesystem()
        
        # Verify the call arguments
        self.assertTrue(self.mock_ipfs_filesystem.called, "IPFSFileSystem constructor was not called")
        call_kwargs = self.mock_ipfs_filesystem.call_args[1]
        self.assertEqual(call_kwargs["role"], "leecher")  # Default value
        self.assertEqual(call_kwargs["use_mmap"], True)  # Default value

if __name__ == "__main__":
    unittest.main()
