"""
Test IPLD integration with ipfs_kit.

This module tests the integration of IPLD components with the main ipfs_kit class.
"""

import unittest
import tempfile
import os
import base64
from unittest.mock import patch, MagicMock

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ipld_extension import IPLDExtension


class TestIPLDIntegrationWithKit(unittest.TestCase):
    """Test IPLD integration with ipfs_kit."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.write(b"IPLD test data")
        self.temp_file.close()

        # We'll use direct patching in each test instead of a patcher for the whole class
        self.patcher = None
        
        # Set up mock handlers that will be used in the tests
        self.mock_car_handler = MagicMock()
        self.mock_car_handler.available = True
        
        self.mock_dag_pb_handler = MagicMock()
        self.mock_dag_pb_handler.available = True
        
        self.mock_unixfs_handler = MagicMock()
        self.mock_unixfs_handler.available = True
        
        # Configure mock extension
        self.mock_extension_instance = MagicMock()
        self.mock_extension_instance.car_handler = self.mock_car_handler
        self.mock_extension_instance.dag_pb_handler = self.mock_dag_pb_handler
        self.mock_extension_instance.unixfs_handler = self.mock_unixfs_handler
        
        # Configure return values for extension methods
        self.mock_extension_instance.create_car.return_value = {
            "success": True,
            "car_data_base64": base64.b64encode(b"mock_car_data").decode('utf-8'),
            "size": 12
        }
        
        self.mock_extension_instance.extract_car.return_value = {
            "success": True,
            "roots": ["root1", "root2"],
            "blocks": [{"cid": "block1", "data_base64": "data1", "size": 10}]
        }
        
        self.mock_extension_instance.add_car_to_ipfs.return_value = {
            "success": True,
            "root_cids": ["root1", "root2"]
        }
        
        self.mock_extension_instance.create_node.return_value = {
            "success": True,
            "cid": "node_cid",
            "size": 100
        }
        
        self.mock_extension_instance.chunk_file.return_value = {
            "success": True,
            "file_path": self.temp_file.name,
            "chunk_count": 1
        }

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary file
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_ipld_extension_initialization(self):
        """Test initialization of IPLD extension in ipfs_kit."""
        # Use direct patching for this test since it involves initialization
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_init:
            # Return our mock extension instance
            mock_extension_init.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Verify extension was initialized
            self.assertIsNotNone(kit.ipld_extension)
            
            # Verify mock was called
            mock_extension_init.assert_called_once()

    def test_create_car(self):
        """Test create_car method."""
        # Patch the IPLDExtension class
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_class:
            # Configure the mock to return our extension instance
            mock_extension_class.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Call method
            roots = ["root1", "root2"]
            blocks = [("block1", b"data1")]
            result = kit.create_car(roots, blocks)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["size"], 12)
            
            # Verify mock was called
            self.mock_extension_instance.create_car.assert_called_once_with(roots, blocks)

    def test_extract_car(self):
        """Test extract_car method."""
        # Patch the IPLDExtension class
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_class:
            # Configure the mock to return our extension instance
            mock_extension_class.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Call method
            car_data = base64.b64encode(b"car_data").decode('utf-8')
            result = kit.extract_car(car_data)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["roots"], ["root1", "root2"])
            
            # Verify mock was called
            self.mock_extension_instance.extract_car.assert_called_once_with(car_data)

    def test_add_car_to_ipfs(self):
        """Test add_car_to_ipfs method."""
        # Patch the IPLDExtension class
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_class:
            # Configure the mock to return our extension instance
            mock_extension_class.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Call method
            car_data = base64.b64encode(b"car_data").decode('utf-8')
            result = kit.add_car_to_ipfs(car_data)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["root_cids"], ["root1", "root2"])
            
            # Verify mock was called
            self.mock_extension_instance.add_car_to_ipfs.assert_called_once_with(car_data)

    def test_create_dag_node(self):
        """Test create_dag_node method."""
        # Patch the IPLDExtension class
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_class:
            # Configure the mock to return our extension instance
            mock_extension_class.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Call method
            data = b"node_data"
            links = [{"Name": "link1", "Hash": "cid1", "Tsize": 100}]
            result = kit.create_dag_node(data, links)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["cid"], "node_cid")
            
            # Verify mock was called
            self.mock_extension_instance.create_node.assert_called_once_with(data, links)

    def test_chunk_file(self):
        """Test chunk_file method."""
        # Patch the IPLDExtension class
        with patch('ipfs_kit_py.ipfs_kit.IPLDExtension') as mock_extension_class:
            # Configure the mock to return our extension instance
            mock_extension_class.return_value = self.mock_extension_instance
            
            # Create kit with IPLD enabled
            kit = ipfs_kit(metadata={"enable_ipld": True})
            
            # Call method
            file_path = self.temp_file.name
            chunk_size = 1024
            result = kit.chunk_file(file_path, chunk_size)
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["file_path"], file_path)
            
            # Verify mock was called
            self.mock_extension_instance.chunk_file.assert_called_once_with(file_path, chunk_size)

    def test_error_handling_extension_not_initialized(self):
        """Test error handling when extension not initialized."""
        # Create kit with IPLD disabled
        kit = ipfs_kit(metadata={"enable_ipld": False})
        
        # Attempt to call methods
        result = kit.create_car(["root"], [("block", b"data")])
        
        # Verify error handling
        self.assertFalse(result["success"])
        self.assertIn("IPLD extension not initialized", result["error"])


if __name__ == "__main__":
    unittest.main()