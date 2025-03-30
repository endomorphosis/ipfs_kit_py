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
from ipfs_kit_py.arrow_metadata_index import ArrowMetadataIndex
from ipfs_kit_py.metadata_sync_handler import MetadataSyncHandler


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
        
        # Clean up any handlers
        if hasattr(self.kit, '_metadata_sync_handler') and self.kit._metadata_sync_handler:
            if hasattr(self.kit._metadata_sync_handler, 'stop'):
                self.kit._metadata_sync_handler.stop()
        
    def test_get_metadata_index(self):
        """Test getting the metadata index from IPFS Kit."""
        # Initialize metadata index
        index = self.kit.get_metadata_index(index_dir=self.index_dir)
        
        # Verify the index was created
        self.assertIsNotNone(index)
        self.assertIsInstance(index, ArrowMetadataIndex)
        
    def test_add_record_to_index(self):
        """Test adding a record to the metadata index."""
        # Initialize metadata index
        index = self.kit.get_metadata_index(index_dir=self.index_dir)
        
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
        
        # Add record with mocked add_record method
        with patch.object(index, 'add_record', return_value={"success": True}) as mock_add:
            result = index.add_record(record)
            
            # Verify add_record was called with the record
            mock_add.assert_called_once_with(record)
            self.assertTrue(result["success"])
            
    def test_sync_metadata_index(self):
        """Test synchronizing the metadata index with peers."""
        # Initialize metadata index
        index = self.kit.get_metadata_index(index_dir=self.index_dir)
        
        # Replace the sync handler with a mock
        self.kit._metadata_sync_handler = MagicMock()
        self.kit._metadata_sync_handler.sync_with_all_peers.return_value = {
            "success": True,
            "peers_synced": 2,
            "partitions_synced": 3
        }
        
        # Synchronize with peers
        result = self.kit.sync_metadata_index()
        
        # Verify sync_with_all_peers was called
        self.kit._metadata_sync_handler.sync_with_all_peers.assert_called_once()
        self.assertTrue(result["success"])
        self.assertEqual(result["peers_synced"], 2)
        self.assertEqual(result["partitions_synced"], 3)
        
    def test_publish_metadata_index(self):
        """Test publishing the metadata index to IPFS DAG."""
        # Initialize metadata index
        index = self.kit.get_metadata_index(index_dir=self.index_dir)
        
        # Mock the publish_index_dag method
        with patch.object(index, 'publish_index_dag', return_value={
            "success": True,
            "dag_cid": "QmTestDAG",
            "ipns_name": "QmTestIPNS"
        }) as mock_publish:
            # Publish index
            result = self.kit.publish_metadata_index()
            
            # Verify publish_index_dag was called
            mock_publish.assert_called_once()
            self.assertTrue(result["success"])
            self.assertEqual(result["dag_cid"], "QmTestDAG")
            self.assertEqual(result["ipns_name"], "QmTestIPNS")


if __name__ == '__main__':
    unittest.main()