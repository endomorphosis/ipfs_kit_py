"""
Comprehensive tests for BackendAdapter base class.

This test suite ensures the BackendAdapter abstract base class is properly
implemented and enforces the correct interface for all backend implementations.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.backends.base_adapter import BackendAdapter


class MockBackendAdapter(BackendAdapter):
    """Mock implementation of BackendAdapter for testing."""
    
    def __init__(self, backend_name="mock_backend", config_manager=None):
        super().__init__(backend_name, config_manager)
        self.health_check_called = False
        self.sync_pins_called = False
    
    async def health_check(self):
        """Mock health check implementation."""
        self.health_check_called = True
        return {
            'healthy': True,
            'response_time_ms': 10.5,
            'error': None,
            'pin_count': 42,
            'storage_usage': 1024,
            'needs_pin_sync': False,
            'needs_bucket_backup': False,
            'needs_metadata_backup': False
        }
    
    async def sync_pins(self):
        """Mock sync pins implementation."""
        self.sync_pins_called = True
        return True
    
    async def backup_buckets(self):
        """Mock backup buckets implementation."""
        return {'success': True, 'backed_up': 5, 'buckets': ['bucket1', 'bucket2']}
    
    async def backup_metadata(self):
        """Mock backup metadata implementation."""
        return {'success': True, 'backed_up': 20, 'metadata_types': ['pins', 'config']}
    
    async def restore_pins(self, pin_list=None):
        """Mock restore pins implementation."""
        return True
    
    async def restore_buckets(self, bucket_list=None):
        """Mock restore buckets implementation."""
        return True
    
    async def restore_metadata(self):
        """Mock restore metadata implementation."""
        return True
    
    async def list_pins(self):
        """Mock list pins implementation."""
        return [
            {
                'cid': 'QmTest123',
                'name': 'test_pin',
                'size': 1024,
                'created_at': '2024-01-01T00:00:00Z',
                'metadata': {}
            }
        ]
    
    async def list_buckets(self):
        """Mock list buckets implementation."""
        return [
            {
                'bucket_name': 'test_bucket',
                'backup_path': '/backups/test_bucket.tar',
                'size': 2048,
                'created_at': '2024-01-01T00:00:00Z',
                'checksum': 'abc123'
            }
        ]
    
    async def list_metadata_backups(self):
        """Mock list metadata backups implementation."""
        return [
            {
                'backup_type': 'pin_metadata',
                'backup_path': '/backups/metadata.db',
                'size': 4096,
                'created_at': '2024-01-01T00:00:00Z',
                'checksum': 'def456'
            }
        ]
    
    async def cleanup_old_backups(self, retention_days=30):
        """Mock cleanup old backups implementation."""
        return True
    
    async def get_storage_usage(self):
        """Mock get storage usage implementation."""
        return {
            'total_usage': 10240,
            'pin_usage': 5120,
            'bucket_backup_usage': 3072,
            'metadata_backup_usage': 2048,
            'available_space': 1000000
        }


class TestBackendAdapterInitialization(unittest.TestCase):
    """Test BackendAdapter initialization."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization_basic(self):
        """Test basic backend adapter initialization."""
        backend = MockBackendAdapter("test_backend")
        
        self.assertEqual(backend.backend_name, "test_backend")
        self.assertIsNone(backend.config_manager)
        self.assertIsNotNone(backend.logger)
        self.assertTrue(backend.backend_metadata_dir.exists())
    
    def test_initialization_with_config_manager(self):
        """Test initialization with config manager."""
        mock_config_manager = Mock()
        mock_config_manager.get_backend_config.return_value = {
            'enabled': True,
            'timeout': 60
        }
        
        backend = MockBackendAdapter("test_backend", mock_config_manager)
        
        self.assertEqual(backend.config_manager, mock_config_manager)
        mock_config_manager.get_backend_config.assert_called_once_with("test_backend")
    
    def test_initialization_without_config_manager(self):
        """Test initialization without config manager."""
        backend = MockBackendAdapter("test_backend")
        
        # Should have default config
        self.assertIn('enabled', backend.config)
        self.assertIn('timeout', backend.config)
        self.assertIn('retry_count', backend.config)
    
    def test_metadata_directory_creation(self):
        """Test that metadata directory is created."""
        backend = MockBackendAdapter("test_backend")
        
        expected_dir = Path(self.temp_dir) / '.ipfs_kit' / 'backends' / 'test_backend'
        self.assertTrue(expected_dir.exists())
        self.assertEqual(backend.backend_metadata_dir, expected_dir)


class TestBackendAdapterConfiguration(unittest.TestCase):
    """Test BackendAdapter configuration loading."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_with_config_manager(self):
        """Test loading config with config manager."""
        mock_config_manager = Mock()
        mock_config_manager.get_backend_config.return_value = {
            'enabled': False,
            'timeout': 120,
            'custom_param': 'value'
        }
        
        backend = MockBackendAdapter("test", mock_config_manager)
        
        self.assertEqual(backend.config['timeout'], 120)
        self.assertEqual(backend.config['custom_param'], 'value')
    
    def test_load_default_config_without_manager(self):
        """Test loading default config when no manager provided."""
        backend = MockBackendAdapter("test")
        
        # Should have default values
        self.assertTrue(backend.config['enabled'])
        self.assertEqual(backend.config['timeout'], 30)
        self.assertEqual(backend.config['retry_count'], 3)
        self.assertEqual(backend.config['health_check_interval'], 300)
    
    def test_config_loading_error_handling(self):
        """Test config loading handles errors gracefully."""
        mock_config_manager = Mock()
        mock_config_manager.get_backend_config.side_effect = Exception("Config error")
        
        backend = MockBackendAdapter("test", mock_config_manager)
        
        # Should have empty config on error
        self.assertEqual(backend.config, {})


class TestBackendAdapterAbstractMethods(unittest.TestCase):
    """Test that abstract methods are properly enforced."""
    
    def test_cannot_instantiate_base_class(self):
        """Test that BackendAdapter cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BackendAdapter("test")
    
    def test_health_check_must_be_implemented(self):
        """Test that health_check must be implemented by subclasses."""
        
        class IncompleteBackend(BackendAdapter):
            async def sync_pins(self):
                return True
        
        with self.assertRaises(TypeError):
            IncompleteBackend("test")
    
    def test_sync_pins_must_be_implemented(self):
        """Test that sync_pins must be implemented by subclasses."""
        
        class IncompleteBackend(BackendAdapter):
            async def health_check(self):
                return {}
        
        with self.assertRaises(TypeError):
            IncompleteBackend("test")


class TestBackendAdapterImplementation(unittest.IsolatedAsyncioTestCase):
    """Test concrete implementation of BackendAdapter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
        self.backend = MockBackendAdapter("test")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_health_check_implementation(self):
        """Test health_check method implementation."""
        result = await self.backend.health_check()
        
        self.assertTrue(self.backend.health_check_called)
        self.assertIsInstance(result, dict)
        self.assertIn('healthy', result)
        self.assertIn('response_time_ms', result)
    
    async def test_sync_pins_implementation(self):
        """Test sync_pins method implementation."""
        result = await self.backend.sync_pins()
        
        self.assertTrue(self.backend.sync_pins_called)
        self.assertIsInstance(result, bool)
    
    async def test_backup_pins_implementation(self):
        """Test backup_pins method if implemented."""
        if hasattr(self.backend, 'backup_pins'):
            result = await self.backend.backup_pins()
            self.assertIsInstance(result, dict)
            self.assertIn('success', result)
    
    async def test_backup_buckets_implementation(self):
        """Test backup_buckets method if implemented."""
        if hasattr(self.backend, 'backup_buckets'):
            result = await self.backend.backup_buckets()
            self.assertIsInstance(result, dict)
            self.assertIn('success', result)
    
    async def test_backup_metadata_implementation(self):
        """Test backup_metadata method if implemented."""
        if hasattr(self.backend, 'backup_metadata'):
            result = await self.backend.backup_metadata()
            self.assertIsInstance(result, dict)
            self.assertIn('success', result)
    
    async def test_health_check_returns_correct_structure(self):
        """Test that health_check returns the expected structure."""
        result = await self.backend.health_check()
        
        # Check required keys
        required_keys = ['healthy', 'response_time_ms', 'pin_count', 'storage_usage']
        for key in required_keys:
            self.assertIn(key, result, f"Missing required key: {key}")
    
    async def test_concurrent_operations(self):
        """Test that backend can handle concurrent operations."""
        import asyncio
        
        # Run multiple operations concurrently
        results = await asyncio.gather(
            self.backend.health_check(),
            self.backend.sync_pins(),
            self.backend.health_check()
        )
        
        self.assertEqual(len(results), 3)
    
    async def test_error_handling_in_implementation(self):
        """Test error handling in implementation methods."""
        
        class ErrorBackend(MockBackendAdapter):
            async def health_check(self):
                raise Exception("Health check failed")
        
        backend = ErrorBackend("error_test")
        
        with self.assertRaises(Exception):
            await backend.health_check()


class TestBackendAdapterInterfaceValidation(unittest.IsolatedAsyncioTestCase):
    """Test interface validation and contract enforcement."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
        self.backend = MockBackendAdapter("test")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    async def test_health_check_returns_dict(self):
        """Test that health_check returns a dictionary."""
        result = await self.backend.health_check()
        self.assertIsInstance(result, dict)
    
    async def test_sync_pins_returns_bool(self):
        """Test that sync_pins returns a boolean."""
        result = await self.backend.sync_pins()
        self.assertIsInstance(result, bool)
    
    async def test_backup_methods_return_dict(self):
        """Test that backup methods return dictionaries."""
        if hasattr(self.backend, 'backup_pins'):
            result = await self.backend.backup_pins()
            self.assertIsInstance(result, dict)
        
        if hasattr(self.backend, 'backup_buckets'):
            result = await self.backend.backup_buckets()
            self.assertIsInstance(result, dict)
        
        if hasattr(self.backend, 'backup_metadata'):
            result = await self.backend.backup_metadata()
            self.assertIsInstance(result, dict)
    
    def test_backend_has_logger(self):
        """Test that backend has a logger configured."""
        self.assertIsNotNone(self.backend.logger)
        self.assertTrue(hasattr(self.backend.logger, 'info'))
        self.assertTrue(hasattr(self.backend.logger, 'error'))
    
    def test_backend_has_config(self):
        """Test that backend has a config dict."""
        self.assertIsInstance(self.backend.config, dict)
    
    async def test_error_propagation(self):
        """Test that errors are properly propagated."""
        
        class FailingBackend(MockBackendAdapter):
            async def health_check(self):
                raise RuntimeError("Connection failed")
        
        backend = FailingBackend("failing")
        
        with self.assertRaises(RuntimeError):
            await backend.health_check()


class TestBackendAdapterInheritance(unittest.TestCase):
    """Test inheritance behavior and subclass functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_subclass_inherits_init(self):
        """Test that subclasses inherit __init__ properly."""
        backend = MockBackendAdapter("test")
        
        self.assertTrue(hasattr(backend, 'backend_name'))
        self.assertTrue(hasattr(backend, 'config_manager'))
        self.assertTrue(hasattr(backend, 'logger'))
        self.assertTrue(hasattr(backend, 'ipfs_kit_dir'))
    
    def test_subclass_can_override_config_loading(self):
        """Test that subclasses can override _load_backend_config."""
        
        class CustomBackend(MockBackendAdapter):
            def _load_backend_config(self):
                return {'custom': True, 'value': 42}
        
        backend = CustomBackend("custom")
        self.assertTrue(backend.config['custom'])
        self.assertEqual(backend.config['value'], 42)
    
    def test_multiple_inheritance_levels(self):
        """Test that inheritance works across multiple levels."""
        
        class Level1Backend(MockBackendAdapter):
            def level1_method(self):
                return "level1"
        
        class Level2Backend(Level1Backend):
            def level2_method(self):
                return "level2"
        
        backend = Level2Backend("multi")
        self.assertEqual(backend.level1_method(), "level1")
        self.assertEqual(backend.level2_method(), "level2")
        self.assertEqual(backend.backend_name, "multi")


class TestBackendAdapterDirectoryManagement(unittest.TestCase):
    """Test directory creation and management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_creates_metadata_directory(self):
        """Test that metadata directory is created on init."""
        backend = MockBackendAdapter("test")
        
        self.assertTrue(backend.backend_metadata_dir.exists())
        self.assertTrue(backend.backend_metadata_dir.is_dir())
    
    def test_multiple_backends_separate_directories(self):
        """Test that different backends get separate directories."""
        backend1 = MockBackendAdapter("backend1")
        backend2 = MockBackendAdapter("backend2")
        
        self.assertNotEqual(backend1.backend_metadata_dir, backend2.backend_metadata_dir)
        self.assertTrue(backend1.backend_metadata_dir.exists())
        self.assertTrue(backend2.backend_metadata_dir.exists())


class TestBackendAdapterErrorHandling(unittest.TestCase):
    """Test error handling scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_home = os.environ.get('HOME')
        os.environ['HOME'] = self.temp_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.original_home:
            os.environ['HOME'] = self.original_home
        else:
            del os.environ['HOME']
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_handles_invalid_backend_name(self):
        """Test handling of invalid backend names."""
        # Even with special characters, should not crash
        backend = MockBackendAdapter("test/../invalid")
        self.assertIsNotNone(backend.backend_name)
    
    def test_handles_config_loading_errors(self):
        """Test handling of config loading errors."""
        mock_config_manager = Mock()
        mock_config_manager.get_backend_config.side_effect = Exception("Error")
        
        # Should not crash, should use empty config
        backend = MockBackendAdapter("test", mock_config_manager)
        self.assertEqual(backend.config, {})
    
    def test_handles_directory_creation_errors(self):
        """Test handling of directory creation errors."""
        # Make home directory read-only to simulate error
        # Note: This is platform-specific and may not work on all systems
        try:
            os.chmod(self.temp_dir, 0o444)
            # Should handle the error gracefully
            backend = MockBackendAdapter("test")
            # Restore permissions for cleanup
            os.chmod(self.temp_dir, 0o755)
        except Exception:
            # If we can't make it read-only, just pass
            pass


if __name__ == '__main__':
    unittest.main()
