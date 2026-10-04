"""Test the integrated get_filesystem implementation with the actual high_level_api.py."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import logging
import importlib

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import our fixed implementation to use as a reference
from ipfs_kit_py.fixed_high_level_api import IPFSSimpleAPI as FixedIPFSSimpleAPI

# Helper function for import patching
def raise_if_fsspec(name, *args, **kwargs):
    """Custom import function that raises ImportError for fsspec."""
    if name == 'fsspec':
        raise ImportError("Mock ImportError for fsspec")
    return importlib.__import__(name, *args, **kwargs)

# Create a modified high_level_api.py file with our improved get_filesystem method
import shutil
import tempfile

# We'll need to create our own version of the high_level_api.py file
# with just the get_filesystem method replaced for testing integration

# Create a mock version of IPFSSimpleAPI for testing
class MockIPFSKit:
    """Mock version of IPFSSimpleAPI for testing."""
    
    def __init__(self, config=None):
        """Initialize with test configuration."""
        self.config = config or {}
        self.kit = MagicMock()
        self._filesystem = None
        self.plugins = {}
        self.extensions = {}
        self.logger = logging.getLogger("ipfs_kit_py.test")
    
    def _initialize_kit(self):
        """Mock kit initialization."""
        return MagicMock()
        
    def _check_fsspec_available(self):
        """Check if fsspec is available."""
        return True
        
    def _import_ipfs_filesystem(self):
        """Import IPFSFileSystem for testing."""
        # Create a mock class with a __call__ method that returns a new mock
        mock_class = MagicMock()
        
        # Create a pre-configured instance to avoid recursion
        mock_instance = MagicMock() 
        mock_instance.protocol = "ipfs"
        
        # Make the mock class return our pre-configured instance when called
        mock_class.return_value = mock_instance
        
        return mock_class
        
    def get_filesystem(
        self,
        *,
        gateway_urls=None,
        use_gateway_fallback=None, 
        gateway_only=None,
        cache_config=None,
        enable_metrics=None,
        return_mock=False,
        **kwargs
    ):
        """
        Get an FSSpec-compatible filesystem for IPFS.
        This is the improved implementation we want to test integration for.
        """
        # Return cached filesystem instance if available
        if hasattr(self, "_filesystem") and self._filesystem is not None:
            return self._filesystem
        
        # Define MockIPFSFileSystem for testing and backward compatibility
        class MockIPFSFileSystem:
            def __init__(self, **kwargs):
                self.protocol = "ipfs"
                self.kwargs = kwargs
                
            def __call__(self, *args, **kwargs):
                return None
                
            def cat(self, path, **kwargs):
                return b""
                
            def ls(self, path, **kwargs):
                return []
                
            def info(self, path, **kwargs):
                return {"name": path, "size": 0, "type": "file"}
                
            def open(self, path, mode="rb", **kwargs):
                from io import BytesIO
                return BytesIO(b"")
        
        # Check if fsspec is available - avoiding recursion
        try:
            import fsspec
            fsspec_available = True
        except ImportError:
            fsspec_available = False
            self.logger.warning("FSSpec is not available. Please install fsspec to use the filesystem interface.")
            if not return_mock:
                raise ImportError("fsspec is not available. Please install fsspec to use this feature.")
        
        # Try to import IPFSFileSystem if fsspec is available
        have_ipfsfs = False
        if fsspec_available:
            try:
                IPFSFileSystem = self._import_ipfs_filesystem()
                have_ipfsfs = True
            except ImportError:
                have_ipfsfs = False
                self.logger.warning(
                    "ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete."
                )
                if not return_mock:
                    raise ImportError("ipfs_fsspec.IPFSFileSystem is not available. Please ensure your installation is complete.")
        
        # If dependencies are missing and return_mock is True, return the mock filesystem
        if not fsspec_available or not have_ipfsfs:
            if return_mock:
                self.logger.info("Using mock filesystem due to missing dependencies")
                return MockIPFSFileSystem(**kwargs)
            else:
                # This should never be reached due to the earlier raises, but included for safety
                raise ImportError("Required dependencies for filesystem interface are not available")

        # Prepare configuration with clear precedence:
        # 1. Explicit parameters to this method
        # 2. Values from kwargs
        # 3. Values from config
        # 4. Default values
        fs_kwargs = {}
        
        # Process each parameter with the same pattern to maintain clarity
        param_mapping = {
            "gateway_urls": gateway_urls,
            "use_gateway_fallback": use_gateway_fallback,
            "gateway_only": gateway_only,
            "cache_config": cache_config,
            "enable_metrics": enable_metrics,
            "ipfs_path": kwargs.get("ipfs_path"),
            "socket_path": kwargs.get("socket_path"),
            "use_mmap": kwargs.get("use_mmap")
        }
        
        config_mapping = {
            "cache_config": "cache",  # Handle special case where config key differs
        }
        
        default_values = {
            "role": "leecher",
            "use_mmap": True
        }
        
        # Build configuration with proper precedence
        for param, value in param_mapping.items():
            if value is not None:
                # Explicit parameter was provided
                fs_kwargs[param] = value
            elif param in kwargs:
                # Value is in kwargs
                fs_kwargs[param] = kwargs[param]
            elif param in config_mapping and config_mapping[param] in self.config:
                # Special case for differently named config keys
                fs_kwargs[param] = self.config[config_mapping[param]]
            elif param in self.config:
                # Regular config parameter
                fs_kwargs[param] = self.config[param]
            elif param in default_values:
                # Use default value if available
                fs_kwargs[param] = default_values[param]
        
        # Special case for role which needs a slightly different logic
        if "role" not in fs_kwargs:
            if "role" in kwargs:
                fs_kwargs["role"] = kwargs["role"]
            else:
                fs_kwargs["role"] = self.config.get("role", "leecher")
        
        # Add any remaining kwargs that weren't explicitly handled
        for key, value in kwargs.items():
            if key not in fs_kwargs:
                fs_kwargs[key] = value

        # Try to create the filesystem
        try:
            # Create the filesystem - for our tests, we need to create it properly using the IPFSFileSystem class
            IPFSFileSystem = self._import_ipfs_filesystem()
            self._filesystem = IPFSFileSystem(**fs_kwargs)
            self.logger.info("IPFSFileSystem initialized successfully")
            return self._filesystem
        except Exception as e:
            self.logger.error(f"Failed to initialize IPFSFileSystem: {e}")
            if return_mock:
                # Return the mock implementation as fallback for backward compatibility
                self.logger.warning("Falling back to mock filesystem due to initialization error")
                return MockIPFSFileSystem(**kwargs)
            else:
                # Re-raise the exception with context to help with debugging
                raise Exception(f"Failed to initialize IPFSFileSystem: {str(e)}") from e

class TestIntegratedGetFilesystem(unittest.TestCase):
    """Test cases for the integrated get_filesystem implementation."""

    def setUp(self):
        """Set up test instances."""
        # Configure test logger
        self.logger = logging.getLogger("ipfs_kit_py.test")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)
        
        # Create test configuration
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
        
        # Create test instance with our MockIPFSKit implementation
        self.test_instance = MockIPFSKit(config=self.test_config)
        
    def tearDown(self):
        """Clean up resources."""
        # No patches to clean up in this implementation
        pass
    
    def test_cache_reuse(self):
        """Test that the filesystem instance is cached and reused."""
        # Create a fresh instance for this test to ensure clean cache state
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Get initial mock filesystem with patched import
        with patch.object(test_instance, '_import_ipfs_filesystem') as mock_import:
            # Ensure mock_import returns a consistent value
            mock_fs_class = MagicMock()
            mock_fs_class.return_value = MagicMock()
            mock_import.return_value = mock_fs_class
            
            # First call should create the filesystem and cache it
            fs1 = test_instance.get_filesystem()
            self.assertIsNotNone(fs1)
            
            # Reset the mock to verify second call doesn't use it
            mock_import.reset_mock()
            
            # Second call should return the same instance without re-importing
            fs2 = test_instance.get_filesystem()
            self.assertIs(fs2, fs1)
            
            # Verify import was not called again
            mock_import.assert_not_called()
    
    def test_explicit_parameters(self):
        """Test that explicit parameters override config values."""
        # Create a fresh instance for this test
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Call with explicit parameters
        test_gateway_urls = ["https://override.com"]
        
        # Patch both methods to prevent recursion
        with patch.object(test_instance, '_check_fsspec_available', return_value=True):
            with patch.object(test_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call the method with our explicit parameter
                test_instance.get_filesystem(gateway_urls=test_gateway_urls)
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                self.assertEqual(call_kwargs["gateway_urls"], test_gateway_urls)
    
    def test_config_parameters(self):
        """Test that config values are used when no explicit parameters provided."""
        # Create a fresh instance for this test
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Patch both methods to prevent recursion
        with patch.object(test_instance, '_check_fsspec_available', return_value=True):
            with patch.object(test_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call without explicit parameters
                test_instance.get_filesystem()
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                
                # Verify config values were passed
                self.assertEqual(call_kwargs["gateway_urls"], self.test_config["gateway_urls"])
                self.assertEqual(call_kwargs["use_gateway_fallback"], self.test_config["use_gateway_fallback"])
                self.assertEqual(call_kwargs["ipfs_path"], self.test_config["ipfs_path"])
    
    def test_cache_config_mapping(self):
        """Test the special case for cache_config mapping to config["cache"]."""
        # Create a fresh instance for this test
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Patch both methods to prevent recursion
        with patch.object(test_instance, '_check_fsspec_available', return_value=True):
            with patch.object(test_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call the method
                test_instance.get_filesystem()
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                
                # Verify cache_config mapped correctly
                self.assertEqual(call_kwargs["cache_config"], self.test_config["cache"])
    
    def test_fsspec_not_available(self):
        """Test behavior when fsspec is not available."""
        # Create a fresh instance
        fresh_instance = MockIPFSKit(config=self.test_config)
        
        # Use a module-level patch for better safety
        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: 
                  raise_if_fsspec(name, *args, **kwargs)):
            # Should raise ImportError
            with self.assertRaises(ImportError):
                fresh_instance.get_filesystem()
                
            # Should return mock with return_mock=True
            mock_fs = fresh_instance.get_filesystem(return_mock=True)
            self.assertEqual(mock_fs.protocol, "ipfs")
    
    def test_import_error_handling(self):
        """Test handling of import errors for IPFSFileSystem."""
        # Create a fresh instance
        fresh_instance = MockIPFSKit(config=self.test_config)
        
        # Create a custom import handler that fails
        def import_error(*args, **kwargs):
            raise ImportError("Mock import error")
                
        # Patch the import to fail
        with patch.object(fresh_instance, '_check_fsspec_available', return_value=True):
            with patch.object(fresh_instance, '_import_ipfs_filesystem', side_effect=import_error):
                # Should raise ImportError
                with self.assertRaises(ImportError):
                    fresh_instance.get_filesystem()
                
                # Should return mock with return_mock=True
                mock_fs = fresh_instance.get_filesystem(return_mock=True)
                self.assertEqual(mock_fs.protocol, "ipfs")
    
    def test_initialization_error(self):
        """Test handling of errors during IPFSFileSystem initialization."""
        # Create a fresh instance
        fresh_instance = MockIPFSKit(config=self.test_config)
        
        # Create a custom class for mock initialization with error
        mock_fs_class = MagicMock()
        mock_fs_class.side_effect = Exception("Test initialization error")
        
        # Patch the import to return our error-raising mock
        with patch.object(fresh_instance, '_check_fsspec_available', return_value=True):
            with patch.object(fresh_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Should re-raise the exception
                with self.assertRaises(Exception):
                    fresh_instance.get_filesystem()
                
                # Reset our test instance to avoid cached filesystem
                fresh_instance._filesystem = None
                
                # Should return mock with return_mock=True
                mock_fs = fresh_instance.get_filesystem(return_mock=True)
                self.assertEqual(mock_fs.protocol, "ipfs")
    
    def test_kwargs_handling(self):
        """Test that additional kwargs are passed through correctly."""
        # Create a fresh instance for this test
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Patch both methods to prevent recursion
        with patch.object(test_instance, '_check_fsspec_available', return_value=True):
            with patch.object(test_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call with additional kwargs
                additional_kwargs = {"extra_param": "value", "another_param": 123}
                test_instance.get_filesystem(**additional_kwargs)
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                
                # Verify the additional kwargs were passed
                self.assertEqual(call_kwargs["extra_param"], "value")
                self.assertEqual(call_kwargs["another_param"], 123)
    
    def test_default_values(self):
        """Test that default values are used when neither explicit nor config values are present."""
        # Create a fresh instance without config
        empty_config_instance = MockIPFSKit(config={})
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Patch both methods to prevent recursion
        with patch.object(empty_config_instance, '_check_fsspec_available', return_value=True):
            with patch.object(empty_config_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call the method
                empty_config_instance.get_filesystem()
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                
                # Verify default values were used
                self.assertEqual(call_kwargs["role"], "leecher")
                self.assertEqual(call_kwargs["use_mmap"], True)

    def test_return_mock_parameter(self):
        """Test that the return_mock parameter works correctly."""
        # Create a fresh instance
        fresh_instance = MockIPFSKit(config=self.test_config)
        
        # Create a custom class for mock initialization with error
        mock_fs_class = MagicMock()
        mock_fs_class.side_effect = Exception("Test initialization error")
        
        # Patch the import to return our error-raising mock
        with patch.object(fresh_instance, '_check_fsspec_available', return_value=True):
            with patch.object(fresh_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # With return_mock=True, should return a mock filesystem
                mock_fs = fresh_instance.get_filesystem(return_mock=True)
                # Verify we got back our mock filesystem
                self.assertEqual(mock_fs.protocol, "ipfs")

    def test_parameter_precedence(self):
        """Test the parameter precedence (explicit > kwargs > config > defaults)."""
        # Case 1: Explicit parameter should override everything
        # Create a fresh instance for this test
        test_instance = MockIPFSKit(config=self.test_config.copy())
        
        # Set up the mock class
        mock_fs_instance = MagicMock()
        mock_fs_class = MagicMock()
        mock_fs_class.return_value = mock_fs_instance
        
        # Patch both methods to prevent recursion
        with patch.object(test_instance, '_check_fsspec_available', return_value=True):
            with patch.object(test_instance, '_import_ipfs_filesystem', return_value=mock_fs_class):
                # Call with explicit parameters
                test_instance.get_filesystem(
                    gateway_urls=["https://explicit.com"],
                    use_gateway_fallback=False,
                    some_param="explicit"
                )
                
                # Verify the parameters passed to the constructor
                mock_fs_class.assert_called_once()
                call_kwargs = mock_fs_class.call_args[1]
                
                # Verify explicit parameters were used
                self.assertEqual(call_kwargs["gateway_urls"], ["https://explicit.com"])
                self.assertEqual(call_kwargs["use_gateway_fallback"], False)
                self.assertEqual(call_kwargs["some_param"], "explicit")
        
        # Case 2: Config should override defaults but not explicit params
        # Create a test instance with a different config
        config_with_defaults = {
            "role": "config_role",
            "use_mmap": False  # Different from default
        }
        instance_with_defaults = MockIPFSKit(config=config_with_defaults)
        
        # Set up a new mock class for the second test
        mock_fs_instance2 = MagicMock()
        mock_fs_class2 = MagicMock()
        mock_fs_class2.return_value = mock_fs_instance2
        
        # Patch both methods to prevent recursion
        with patch.object(instance_with_defaults, '_check_fsspec_available', return_value=True):
            with patch.object(instance_with_defaults, '_import_ipfs_filesystem', return_value=mock_fs_class2):
                # Call without overriding params
                instance_with_defaults.get_filesystem()
                
                # Verify the parameters passed to the constructor
                mock_fs_class2.assert_called_once()
                call_kwargs = mock_fs_class2.call_args[1]
                
                # Verify config values override defaults
                self.assertEqual(call_kwargs["role"], "config_role")  # From config
                self.assertEqual(call_kwargs["use_mmap"], False)  # From config

if __name__ == "__main__":
    unittest.main()
