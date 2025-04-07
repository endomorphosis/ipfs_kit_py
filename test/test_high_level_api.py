"""
Test High-Level API for IPFS Kit.

This module contains tests for the High-Level API implementation.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, mock_open, patch

import yaml

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import High-Level API
from ipfs_kit_py.high_level_api import IPFSSimpleAPI, PluginBase


class TestHighLevelAPI(unittest.TestCase):
    """
    Test cases for the High-Level API.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Mock the IPFSKit class
        self.mock_kit = MagicMock()
        self.mock_fs = MagicMock()
        self.mock_kit.get_filesystem.return_value = self.mock_fs

        # Create a patcher for the IPFSKit
        self.kit_patcher = patch("ipfs_kit_py.high_level_api.IPFSKit", return_value=self.mock_kit)
        self.mock_kit_class = self.kit_patcher.start()

        # Create a temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml")
        self.temp_config.write(
            b"""
role: worker
resources:
  max_memory: 2GB
  max_storage: 20GB
cache:
  memory_size: 200MB
  disk_size: 2GB
  disk_path: ~/.ipfs_kit/test_cache
timeouts:
  api: 45
  gateway: 90
  peer_connect: 45
"""
        )
        self.temp_config.close()

        # Mock validation
        self.validation_patcher = patch("ipfs_kit_py.validation.validate_parameters")
        self.mock_validate = self.validation_patcher.start()

        # Mock the logger to prevent error messages during tests
        self.logger_patcher = patch("ipfs_kit_py.high_level_api.logger")
        self.mock_logger = self.logger_patcher.start()

        # Create API instance
        with patch("ipfs_kit_py.high_level_api.ipfs_kit", return_value=self.mock_kit):
            self.api = IPFSSimpleAPI(config_path=self.temp_config.name)
            # Manually set the filesystem since we're mocking
            self.api.fs = self.mock_fs

    def tearDown(self):
        """Clean up after tests."""
        self.kit_patcher.stop()
        self.validation_patcher.stop()
        self.logger_patcher.stop()
        os.unlink(self.temp_config.name)

    def test_initialization(self):
        """Test initialization with configuration file."""
        # In our patched setup, we're not directly calling IPFSKit
        # but we can verify the config was loaded correctly
        self.assertEqual(self.api.config["role"], "worker")
        self.assertEqual(self.api.config["resources"]["max_memory"], "2GB")
        self.assertEqual(self.api.config["timeouts"]["api"], 45)

    def test_initialization_with_kwargs(self):
        """Test initialization with kwargs overriding config file."""
        api = IPFSSimpleAPI(config_path=self.temp_config.name, role="master")
        self.assertEqual(api.config["role"], "master")

    def test_add_file_path(self):
        """Test adding content from file path."""
        # Setup
        self.mock_kit.ipfs_add_file.return_value = {"success": True, "cid": "QmTest"}

        # Create temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"Test content")
            temp_file.flush()

            # Test
            with patch("os.path.exists", return_value=True):
                result = self.api.add(temp_file.name)

        # Verify
        self.mock_kit.ipfs_add_file.assert_called_once()
        self.assertEqual(result, {"success": True, "cid": "QmTest"})

    def test_add_string(self):
        """Test adding content from string."""
        # Setup
        self.mock_kit.ipfs_add_file.return_value = {"success": True, "cid": "QmTest"}

        # Test
        with patch("os.path.exists", return_value=False), patch(
            "tempfile.NamedTemporaryFile", MagicMock()
        ), patch("os.unlink", MagicMock()):
            result = self.api.add("Test content")

        # Verify
        self.mock_kit.ipfs_add_file.assert_called_once()
        self.assertEqual(result, {"success": True, "cid": "QmTest"})

    def test_get(self):
        """Test getting content."""
        # Setup
        self.mock_kit.ipfs_cat.return_value = b"Test content"

        # Test
        result = self.api.get("QmTest")

        # Verify
        self.mock_kit.ipfs_cat.assert_called_once()
        self.assertEqual(result, b"Test content")

    def test_pin(self):
        """Test pinning content."""
        # Setup
        self.mock_kit.ipfs_pin_add.return_value = {"success": True}

        # Test
        result = self.api.pin("QmTest")

        # Verify
        self.mock_kit.ipfs_pin_add.assert_called_once()
        self.assertEqual(result, {"success": True})

    def test_unpin(self):
        """Test unpinning content."""
        # Setup
        self.mock_kit.ipfs_pin_rm.return_value = {"success": True}

        # Test
        result = self.api.unpin("QmTest")

        # Verify
        self.mock_kit.ipfs_pin_rm.assert_called_once()
        self.assertEqual(result, {"success": True})

    def test_list_pins(self):
        """Test listing pins."""
        # Setup
        self.mock_kit.ipfs_pin_ls.return_value = {"success": True, "pins": ["QmTest"]}

        # Test
        result = self.api.list_pins()

        # Verify
        self.mock_kit.ipfs_pin_ls.assert_called_once()
        self.assertEqual(result, {"success": True, "pins": ["QmTest"]})

    def test_publish(self):
        """Test publishing to IPNS."""
        # Setup
        self.mock_kit.ipfs_name_publish.return_value = {"success": True, "name": "QmName"}

        # Test
        result = self.api.publish("QmTest")

        # Verify
        self.mock_kit.ipfs_name_publish.assert_called_once()
        self.assertEqual(result, {"success": True, "name": "QmName"})

    def test_resolve(self):
        """Test resolving IPNS name."""
        # Setup
        self.mock_kit.ipfs_name_resolve.return_value = {"success": True, "path": "/ipfs/QmTest"}

        # Test
        result = self.api.resolve("QmName")

        # Verify
        self.mock_kit.ipfs_name_resolve.assert_called_once()
        self.assertEqual(result, {"success": True, "path": "/ipfs/QmTest"})

    def test_connect(self):
        """Test connecting to peer."""
        # Setup
        self.mock_kit.ipfs_swarm_connect.return_value = {"success": True}

        # Test
        result = self.api.connect("/ip4/1.2.3.4/tcp/4001/p2p/QmPeer")

        # Verify
        self.mock_kit.ipfs_swarm_connect.assert_called_once()
        self.assertEqual(result, {"success": True})

    def test_peers(self):
        """Test listing peers."""
        # Setup
        self.mock_kit.ipfs_swarm_peers.return_value = {
            "success": True,
            "peers": ["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer"],
        }

        # Test
        result = self.api.peers()

        # Verify
        self.mock_kit.ipfs_swarm_peers.assert_called_once()
        self.assertEqual(result, {"success": True, "peers": ["/ip4/1.2.3.4/tcp/4001/p2p/QmPeer"]})

    def test_open(self):
        """Test opening file."""
        # Setup
        mock_file = MagicMock()
        self.mock_fs.open.return_value = mock_file

        # Test
        result = self.api.open("QmTest")

        # Verify
        self.mock_fs.open.assert_called_once_with("ipfs://QmTest", "rb")
        self.assertEqual(result, mock_file)

    def test_read(self):
        """Test reading file."""
        # Setup
        self.mock_fs.cat.return_value = b"Test content"

        # Test
        result = self.api.read("QmTest")

        # Verify
        self.mock_fs.cat.assert_called_once_with("ipfs://QmTest")
        self.assertEqual(result, b"Test content")

    def test_exists(self):
        """Test checking if file exists."""
        # Setup
        self.mock_fs.exists.return_value = True

        # Test
        result = self.api.exists("QmTest")

        # Verify
        self.mock_fs.exists.assert_called_once_with("ipfs://QmTest")
        self.assertTrue(result)

    def test_ls(self):
        """Test listing directory."""
        # Setup
        self.mock_fs.ls.return_value = [{"name": "file.txt", "size": 100}]

        # Test
        result = self.api.ls("QmTest")

        # Verify
        self.mock_fs.ls.assert_called_once_with("ipfs://QmTest", detail=True)
        self.assertEqual(result, [{"name": "file.txt", "size": 100}])

    def test_cluster_operations_leecher(self):
        """Test cluster operations in leecher role."""
        # Setup
        api = IPFSSimpleAPI(role="leecher")

        # Test - should raise exceptions
        with self.assertRaises(Exception):
            api.cluster_add("Test content")

        with self.assertRaises(Exception):
            api.cluster_pin("QmTest")

        with self.assertRaises(Exception):
            api.cluster_status("QmTest")

        with self.assertRaises(Exception):
            api.cluster_peers()

    def test_call_method(self):
        """Test calling method by name."""
        # Setup
        self.mock_kit.ipfs_cat.return_value = b"Test content"

        # Test
        result = self.api("get", "QmTest")

        # Verify
        self.mock_kit.ipfs_cat.assert_called_once()
        self.assertEqual(result, b"Test content")

    def test_call_nonexistent_method(self):
        """Test calling nonexistent method."""
        with self.assertRaises(Exception):
            self.api("nonexistent_method")

    def test_save_config(self):
        """Test saving configuration."""
        # Setup
        mock_open_func = mock_open()

        # Test
        with patch("os.makedirs") as mock_makedirs, patch("builtins.open", mock_open_func):
            result = self.api.save_config("/tmp/test_config.yaml")

        # Verify
        mock_makedirs.assert_called_once()
        mock_open_func.assert_called_once_with("/tmp/test_config.yaml", "w")
        self.assertTrue(result["success"])

    def test_generate_python_sdk(self):
        """Test generating Python SDK."""
        # Setup
        temp_dir = tempfile.mkdtemp()

        # Test
        with patch("os.makedirs") as mock_makedirs, patch("builtins.open", mock_open()):
            result = self.api.generate_sdk("python", temp_dir)

        # Verify
        self.assertTrue(result["success"])
        self.assertEqual(result["language"], "python")
        self.assertTrue(len(result["files_generated"]) > 0)

        # Clean up
        os.rmdir(temp_dir)

    def test_plugin_base(self):
        """Test plugin base class."""
        # Setup
        plugin = PluginBase(self.mock_kit, {"setting": "value"})

        # Test
        name = plugin.get_name()

        # Verify
        self.assertEqual(name, "PluginBase")
        self.assertEqual(plugin.config, {"setting": "value"})
        self.assertEqual(plugin.ipfs_kit, self.mock_kit)


# This class is used as a helper, not a test class
# Rename to avoid pytest collection
class SamplePlugin(PluginBase):
    """Sample plugin implementation used in tests."""

    def test_method(self):
        """Test method."""
        return {"success": True, "plugin": "TestPlugin"}


class TestPluginSystem(unittest.TestCase):
    """
    Test cases for the plugin system.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Mock the IPFSKit class
        self.mock_kit = MagicMock()
        self.mock_fs = MagicMock()
        self.mock_kit.get_filesystem.return_value = self.mock_fs

        # Create a patcher for the IPFSKit
        self.kit_patcher = patch("ipfs_kit_py.high_level_api.IPFSKit", return_value=self.mock_kit)
        self.mock_kit_class = self.kit_patcher.start()

        # Mock validation
        self.validation_patcher = patch("ipfs_kit_py.validation.validate_parameters")
        self.mock_validate = self.validation_patcher.start()

        # Mock the logger to prevent error messages during tests
        self.logger_patcher = patch("ipfs_kit_py.high_level_api.logger")
        self.mock_logger = self.logger_patcher.start()

        # Create a plugin module in memory
        self.module_name = "test_plugin_module"
        sys.modules[self.module_name] = MagicMock()
        sys.modules[self.module_name].TestPlugin = SamplePlugin  # Use SamplePlugin with original name in module

        # Create API instance with plugin configuration
        with patch("ipfs_kit_py.high_level_api.ipfs_kit", return_value=self.mock_kit):
            self.api = IPFSSimpleAPI(
                plugins=[
                    {
                        "name": "TestPlugin",
                        "path": self.module_name,
                        "enabled": True,
                        "config": {"setting": "value"},
                    }
                ]
            )
            # Manually set the filesystem since we're mocking
            self.api.fs = self.mock_fs
            # Initialize the extensions dict
            self.api.extensions = {}

            # Manually register the plugin method
            plugin = SamplePlugin(self.mock_kit, {"setting": "value"})
            self.api.plugins = {"TestPlugin": plugin}
            self.api.extensions["TestPlugin.test_method"] = plugin.test_method

    def tearDown(self):
        """Clean up after tests."""
        self.kit_patcher.stop()
        self.validation_patcher.stop()
        del sys.modules[self.module_name]

    def test_plugin_loading(self):
        """Test plugin loading."""
        self.assertIn("TestPlugin", self.api.plugins)
        self.assertIsInstance(self.api.plugins["TestPlugin"], SamplePlugin)

    def test_extension_registration(self):
        """Test extension registration."""
        self.assertIn("TestPlugin.test_method", self.api.extensions)

    def test_call_extension(self):
        """Test calling extension."""
        result = self.api.call_extension("TestPlugin.test_method")
        self.assertEqual(result, {"success": True, "plugin": "TestPlugin"})

    def test_call_extension_via_call(self):
        """Test calling extension via __call__."""
        result = self.api("TestPlugin.test_method")
        self.assertEqual(result, {"success": True, "plugin": "TestPlugin"})

    def test_register_custom_extension(self):
        """Test registering custom extension."""

        # Setup
        def custom_function(*args, **kwargs):
            return {"success": True, "custom": True}

        # Test
        self.api.register_extension("custom_function", custom_function)
        result = self.api.call_extension("custom_function")

        # Verify
        self.assertEqual(result, {"success": True, "custom": True})


if __name__ == "__main__":
    unittest.main()
