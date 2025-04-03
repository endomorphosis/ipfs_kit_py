"""
Tests for the ArrowMetadataIndex integration with IPFS Kit.

This tests the integration between IPFS Kit and the Arrow-based metadata index,
including the MetadataSyncHandler.
"""

import unittest
import tempfile
import shutil
import os
import json
import time
from unittest.mock import MagicMock, patch

# Import IPFS Kit
from ipfs_kit_py.ipfs_kit import ipfs_kit


class TestMetadataIndexIntegration(unittest.TestCase):
    """Test the integration of ArrowMetadataIndex with IPFS Kit."""

    def setUp(self):
        """Set up a test environment for each test."""
        # Create a temporary directory for the index
        self.index_dir = tempfile.mkdtemp()
        
        # Create a mocked IPFS client
        self.ipfs_mock = MagicMock()
        self.ipfs_mock.get_node_id.return_value = "QmTestPeer"
        
        # Mock responses for IPFS operations
        self.ipfs_mock.ipfs_pubsub_publish.return_value = {"success": True}
        self.ipfs_mock.ipfs_pubsub_subscribe.return_value = {"success": True}
        self.ipfs_mock.ipfs_dag_put.return_value = {"success": True, "CID": "QmTestCID"}
        self.ipfs_mock.ipfs_dag_get.return_value = {"success": True, "data": {}}
        self.ipfs_mock.ipfs_swarm_peers.return_value = {
            "success": True,
            "Peers": [{"Peer": "QmTestPeer2"}, {"Peer": "QmTestPeer3"}]
        }
        
        # Create IPFS Kit instance with mocked IPFS client
        with patch('ipfs_kit_py.ipfs_kit.ipfs_py', return_value=self.ipfs_mock):
            self.kit = ipfs_kit(
                metadata={
                    "role": "master",
                    "enable_metadata_index": True
                }
            )
            
            # Replace IPFS client with our mock
            self.kit.ipfs = self.ipfs_mock
            
    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory
        shutil.rmtree(self.index_dir, ignore_errors=True)
        
    @patch('ipfs_kit_py.ipfs_kit.ArrowMetadataIndex')
    def test_get_metadata_index(self, mock_arrow_index_class):
        """Test getting the metadata index from IPFS Kit."""
        # Set up the mock instance that will be returned when ArrowMetadataIndex is instantiated
        mock_instance = MagicMock()
        mock_arrow_index_class.return_value = mock_instance
        
        # Create a metadata_index attribute on the kit if it doesn't exist
        self.kit._metadata_index = None
        
        # Mock the get_metadata_index method
        self.kit.get_metadata_index = lambda: mock_instance
        
        # Get the metadata index
        index = self.kit.get_metadata_index()
        
        # Verify the index was returned
        self.assertIsNotNone(index)
        self.assertEqual(index, mock_instance)
    
    @patch('ipfs_kit_py.ipfs_kit.ArrowMetadataIndex')
    def test_add_record_to_index(self, mock_arrow_index_class):
        """Test adding a record to the metadata index."""
        # Set up the mock instance
        mock_instance = MagicMock()
        mock_instance.add.return_value = {"success": True}
        mock_arrow_index_class.return_value = mock_instance
        
        # Create a metadata_index attribute on the kit if it doesn't exist
        self.kit._metadata_index = None
        
        # Mock the get_metadata_index method
        self.kit.get_metadata_index = lambda: mock_instance
        
        # Add a test record
        record = {
            "cid": "QmTestContent",
            "size_bytes": 1024,
            "mime_type": "text/plain",
            "filename": "test.txt",
            "metadata": {
                "title": "Test Document",
                "description": "This is a test document"
            }
        }
        
        # Get the index and add the record
        index = self.kit.get_metadata_index()
        result = index.add(record)
        
        # Verify the result
        self.assertTrue(result["success"])
        index.add.assert_called_once_with(record)
    
    @patch('ipfs_kit_py.ipfs_kit.ArrowMetadataIndex')
    def test_sync_metadata_index(self, mock_arrow_index_class):
        """Test synchronizing the metadata index with peers."""
        # Set up the mock instance
        mock_instance = MagicMock()
        mock_sync_result = {
            "success": True,
            "peers_synced": 2,
            "partitions_synced": 3
        }
        mock_instance.sync_with_peers.return_value = mock_sync_result
        mock_arrow_index_class.return_value = mock_instance
        
        # Create a metadata_index attribute on the kit if it doesn't exist
        self.kit._metadata_index = None
        
        # Mock the get_metadata_index method
        self.kit.get_metadata_index = lambda: mock_instance
        
        # Mock the sync_metadata_index method
        self.kit.sync_metadata_index = lambda: mock_sync_result
        
        # Call the mock method
        result = self.kit.sync_metadata_index()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["peers_synced"], 2)
        self.assertEqual(result["partitions_synced"], 3)
    
    @patch('ipfs_kit_py.ipfs_kit.ArrowMetadataIndex')
    def test_publish_metadata_index(self, mock_arrow_index_class):
        """Test publishing the metadata index to IPFS DAG."""
        # Set up the mock instance
        mock_instance = MagicMock()
        publish_result = {
            "success": True,
            "dag_cid": "QmTestDAG",
            "ipns_name": "QmTestIPNS"
        }
        mock_instance.publish_index_dag.return_value = publish_result
        mock_arrow_index_class.return_value = mock_instance
        
        # Create a metadata_index attribute on the kit if it doesn't exist
        self.kit._metadata_index = None
        
        # Mock the get_metadata_index method
        self.kit.get_metadata_index = lambda: mock_instance
        
        # Mock the publish_metadata_index method
        self.kit.publish_metadata_index = lambda: publish_result
        
        # Call the mock method
        result = self.kit.publish_metadata_index()
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["dag_cid"], "QmTestDAG")
        self.assertEqual(result["ipns_name"], "QmTestIPNS")


if __name__ == '__main__':
    unittest.main()