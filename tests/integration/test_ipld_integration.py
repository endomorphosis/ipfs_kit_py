"""
Test suite for IPLD integration.

This module tests the integration of py-ipld libraries with IPFS Kit,
verifying CAR file handling, DAG-PB operations, and UnixFS chunking.
"""

import base64
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.ipld.car import IPLDCarHandler
from ipfs_kit_py.ipld.dag_pb import IPLDDagPbHandler
from ipfs_kit_py.ipld.unixfs import IPLDUnixFSHandler
from ipfs_kit_py.ipld_extension import IPLDExtension


class TestIPLDIntegration(unittest.TestCase):
    """Test cases for IPLD integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()
        self.ipfs_client.run_ipfs_command.return_value = {
            "success": True,
            "stdout": b"Pinned root bafy123...",
            "stderr": b"",
            "returncode": 0
        }
        
        # Set up handlers
        with patch('ipfs_kit_py.ipld.car.IPLD_CAR_AVAILABLE', True), \
             patch('ipfs_kit_py.ipld.dag_pb.IPLD_DAG_PB_AVAILABLE', True), \
             patch('ipfs_kit_py.ipld.unixfs.IPLD_UNIXFS_AVAILABLE', True):
            
            self.car_handler = IPLDCarHandler()
            self.dag_pb_handler = IPLDDagPbHandler()
            self.unixfs_handler = IPLDUnixFSHandler()
            self.ipld_extension = IPLDExtension(self.ipfs_client)
        
        # Mock the actual library functions
        self._patch_ipld_libraries()
    
    def _patch_ipld_libraries(self):
        """Patch the IPLD library functions for testing."""
        # Instead of mocking low-level library functions, patch handler methods directly
        
        # Create mock objects that will be used in multiple handlers
        mock_node = MagicMock()
        mock_node.data = b'mock-node-data'
        mock_node.links = []
        
        mock_cid = MagicMock()
        mock_cid.encode.return_value = 'bafy123'
        
        # Mock CAR handler methods
        self.car_handler.encode = MagicMock(return_value=memoryview(b'mock-car-data'))
        self.car_handler.decode = MagicMock(return_value=([mock_cid], [(mock_cid, b'mock-block-data')]))
        self.car_handler.available = True
        
        # Mock DAG-PB handler methods - DIRECTLY mock the handler's methods
        # Don't attempt to patch the module-level PBNode class
        self.dag_pb_handler.create_node = MagicMock(return_value=mock_node)
        self.dag_pb_handler.prepare_node = MagicMock(return_value=mock_node)
        self.dag_pb_handler.prepare = MagicMock(return_value=mock_node)
        self.dag_pb_handler.encode_node = MagicMock(return_value=memoryview(b'mock-encoded-node'))
        self.dag_pb_handler.encode = MagicMock(return_value=memoryview(b'mock-encoded-node'))
        self.dag_pb_handler.decode_node = MagicMock(return_value=mock_node)
        self.dag_pb_handler.decode = MagicMock(return_value=mock_node)
        self.dag_pb_handler.node_to_cid = MagicMock(return_value=mock_cid)
        self.dag_pb_handler.available = True
        
        # Mock UnixFS handler methods
        self.unixfs_handler.chunk_data = MagicMock(return_value=[b'chunk1', b'chunk2'])
        self.unixfs_handler.chunk_file = MagicMock(return_value=[b'chunk1', b'chunk2'])
        self.unixfs_handler.available = True
        
        # Set handlers in the extension
        self.ipld_extension.car_handler = self.car_handler
        self.ipld_extension.dag_pb_handler = self.dag_pb_handler
        self.ipld_extension.unixfs_handler = self.unixfs_handler
    
    def tearDown(self):
        """Clean up resources."""
        patch.stopall()
    
    def test_car_handler(self):
        """Test CAR handler functionality."""
        # Test encoding
        mock_cid = MagicMock()
        mock_cid.encode.return_value = 'bafy123'
        
        # Update the car_handler's mock for this test specifically
        self.car_handler.encode.return_value = memoryview(b'test-car-data')
        result = self.ipld_extension.create_car(["bafy123"], [("bafy123", b"test-data")])
        
        self.assertTrue(result["success"])
        self.assertIn("car_data_base64", result)
        
        # Test decoding
        self.car_handler.decode.return_value = ([mock_cid], [(mock_cid, b'test-block-data')])
        result = self.ipld_extension.extract_car(b'test-car-data')
        
        self.assertTrue(result["success"])
        self.assertEqual(result["roots"], ['bafy123'])
        self.assertEqual(len(result["blocks"]), 1)
    
    def test_dag_pb_handler(self):
        """Test DAG-PB handler functionality."""
        # Create mocks for the test
        mock_node = MagicMock()
        mock_node.data = b'test-data'
        mock_node.links = []
        
        mock_cid = MagicMock()
        mock_cid.encode.return_value = 'bafy123'
        
        # Set up direct mock returns for this test
        self.dag_pb_handler.available = True
        self.dag_pb_handler.create_node.return_value = mock_node
        self.dag_pb_handler.prepare.return_value = mock_node
        self.dag_pb_handler.encode.return_value = memoryview(b'encoded-node')
        self.dag_pb_handler.decode.return_value = mock_node
        self.dag_pb_handler.node_to_cid.return_value = mock_cid
        
        # Test create_node
        result = self.ipld_extension.create_node(b'test-data')
        
        if not result["success"]:
            print("create_node result:", result)
            
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], 'bafy123')
        
        # Test node encoding
        result = self.ipld_extension.encode_node(b'test-data')
        
        if not result["success"]:
            print("encode_node result:", result)
            
        self.assertTrue(result["success"])
        self.assertEqual(result["cid"], 'bafy123')
        
        # Test node decoding
        mock_node.data = b'decoded-data'
        self.dag_pb_handler.decode.return_value = mock_node
        
        result = self.ipld_extension.decode_node(b'encoded-node')
        
        if not result["success"]:
            print("decode_node result:", result)
            
        self.assertTrue(result["success"])
        self.assertTrue(result["has_data"])
    
    def test_unixfs_handler(self):
        """Test UnixFS handler functionality."""
        # Test data chunking
        self.unixfs_handler.chunk_data.return_value = [b'chunk1', b'chunk2']
        
        result = self.ipld_extension.chunk_data(b'test-data')
        
        self.assertTrue(result["success"])
        self.assertEqual(result["chunk_count"], 2)
        
        # Test file chunking - create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b'test file data')
            tmp_path = tmp.name
        
        try:
            self.unixfs_handler.chunk_file.return_value = iter([b'chunk1', b'chunk2'])
            
            # Mock os.path.getsize
            with patch('os.path.getsize', return_value=14):
                result = self.ipld_extension.chunk_file(tmp_path)
                
                self.assertTrue(result["success"])
                self.assertEqual(result["file_size"], 14)
        finally:
            os.unlink(tmp_path)
    
    def test_ipfs_integration(self):
        """Test integration with IPFS."""
        # Test adding CAR to IPFS
        mock_cid = MagicMock()
        mock_cid.encode.return_value = 'bafy123'
        self.car_handler.decode.return_value = ([mock_cid], [(mock_cid, b'data')])
        
        # Mock temporary file creation
        mock_tempfile = MagicMock()
        mock_tempfile.name = "/tmp/mock-car-file.car"
        mock_tempfile.__enter__.return_value = mock_tempfile
        
        with patch('tempfile.NamedTemporaryFile', return_value=mock_tempfile):
            result = self.ipld_extension.add_car_to_ipfs(b'mock-car-data')
            
            self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()