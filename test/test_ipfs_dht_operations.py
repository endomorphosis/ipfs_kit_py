#!/usr/bin/env python3
"""
Test IPFS DHT Operations

This module tests the DHT (Distributed Hash Table) operations added to the IPFS backend.
These operations enhance the network participation capabilities of the MCP server.
"""

import os
import sys
import time
import unittest
import unittest.mock
from typing import Dict, Any

# Add parent directory to path for importing
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import ipfs_backend


class MockIPFSResponse:
    """Mock response for IPFS operations."""
    
    @staticmethod
    def success_response(**kwargs) -> Dict[str, Any]:
        """Create a success response with the given fields."""
        response = {"success": True}
        response.update(kwargs)
        return response
    
    @staticmethod
    def error_response(error="Mock error") -> Dict[str, Any]:
        """Create an error response with the given message."""
        return {"success": False, "error": error}


class TestIPFSDHTOperations(unittest.TestCase):
    """Test cases for IPFS DHT operations."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a backend with a mock IPFS client
        self.backend = ipfs_backend.IPFSStorageBackend()
        
        # Replace the client with our controlled mock
        self.mock_ipfs = unittest.mock.MagicMock()
        self.backend.ipfs = self.mock_ipfs
        self.backend.is_mock = False  # Pretend it's a real implementation
    
    def test_dht_provide(self):
        """Test providing content via DHT."""
        # Set up mock response
        test_cid = "QmTest123456789"
        self.mock_ipfs.ipfs_dht_provide.return_value = MockIPFSResponse.success_response(
            cid=test_cid,
            provided=True
        )
        
        # Call the method
        result = self.backend.dht_provide(test_cid, recursive=True)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["identifier"], test_cid)
        self.assertEqual(result["backend"], "ipfs")
        
        # Verify the mock was called correctly
        self.mock_ipfs.ipfs_dht_provide.assert_called_once_with(test_cid, recursive=True)
        
        # Verify performance stats were updated
        self.assertEqual(self.backend.performance_stats["dht_provide"]["count"], 1)
        self.assertGreaterEqual(self.backend.performance_stats["dht_provide"]["total_time"], 0)
    
    def test_dht_provide_failure(self):
        """Test providing content via DHT with failure."""
        # Set up mock response for failure
        test_cid = "QmTest123456789"
        error_msg = "Failed to provide content"
        self.mock_ipfs.ipfs_dht_provide.return_value = MockIPFSResponse.error_response(error_msg)
        
        # Call the method
        result = self.backend.dht_provide(test_cid)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["identifier"], test_cid)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["details"]["error"], error_msg)
    
    def test_dht_find_providers(self):
        """Test finding providers via DHT."""
        # Set up mock response
        test_cid = "QmTest123456789"
        mock_providers = [
            {"id": "QmPeer1", "addresses": ["/ip4/127.0.0.1/tcp/4001"]},
            {"id": "QmPeer2", "addresses": ["/ip4/192.168.1.1/tcp/4001"]}
        ]
        self.mock_ipfs.ipfs_dht_find_providers.return_value = MockIPFSResponse.success_response(
            cid=test_cid,
            providers=mock_providers
        )
        
        # Call the method
        result = self.backend.dht_find_providers(test_cid, num_providers=5, timeout=30)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["identifier"], test_cid)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["providers"], mock_providers)
        
        # Verify the mock was called correctly
        self.mock_ipfs.ipfs_dht_find_providers.assert_called_once_with(
            test_cid, num_providers=5, timeout=30
        )
        
        # Verify performance stats were updated
        self.assertEqual(self.backend.performance_stats["dht_find_provider"]["count"], 1)
        self.assertGreaterEqual(self.backend.performance_stats["dht_find_provider"]["total_time"], 0)
    
    def test_dht_find_providers_failure(self):
        """Test finding providers via DHT with failure."""
        # Set up mock response for failure
        test_cid = "QmTest123456789"
        error_msg = "Failed to find providers"
        self.mock_ipfs.ipfs_dht_find_providers.return_value = MockIPFSResponse.error_response(error_msg)
        
        # Call the method
        result = self.backend.dht_find_providers(test_cid)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["identifier"], test_cid)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["error"], error_msg)
    
    def test_dht_find_peer(self):
        """Test finding a peer via DHT."""
        # Set up mock response
        test_peer_id = "QmPeer1"
        mock_peer_info = {
            "id": test_peer_id,
            "addresses": ["/ip4/127.0.0.1/tcp/4001", "/ip4/192.168.1.1/tcp/4001"]
        }
        self.mock_ipfs.ipfs_dht_find_peer.return_value = MockIPFSResponse.success_response(
            peer_id=test_peer_id,
            peer_info=mock_peer_info,
            addresses=mock_peer_info["addresses"]
        )
        
        # Call the method
        result = self.backend.dht_find_peer(test_peer_id, timeout=30)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["peer_id"], test_peer_id)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["peer_info"], mock_peer_info)
        self.assertEqual(result["addresses"], mock_peer_info["addresses"])
        
        # Verify the mock was called correctly
        self.mock_ipfs.ipfs_dht_find_peer.assert_called_once_with(test_peer_id, timeout=30)
        
        # Verify performance stats were updated
        self.assertEqual(self.backend.performance_stats["dht_find_peer"]["count"], 1)
        self.assertGreaterEqual(self.backend.performance_stats["dht_find_peer"]["total_time"], 0)
    
    def test_dht_find_peer_failure(self):
        """Test finding a peer via DHT with failure."""
        # Set up mock response for failure
        test_peer_id = "QmPeer1"
        error_msg = "Failed to find peer"
        self.mock_ipfs.ipfs_dht_find_peer.return_value = MockIPFSResponse.error_response(error_msg)
        
        # Call the method
        result = self.backend.dht_find_peer(test_peer_id)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["peer_id"], test_peer_id)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["error"], error_msg)
    
    def test_dht_query(self):
        """Test querying the DHT for a key."""
        # Set up mock response
        test_key = "/ipns/QmTest123456789"
        mock_responses = [
            {"id": "QmPeer1", "value": "test value 1"},
            {"id": "QmPeer2", "value": "test value 2"}
        ]
        self.mock_ipfs.ipfs_dht_query.return_value = MockIPFSResponse.success_response(
            key=test_key,
            responses=mock_responses
        )
        
        # Call the method
        result = self.backend.dht_query(test_key, timeout=30)
        
        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["key"], test_key)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["responses"], mock_responses)
        
        # Verify the mock was called correctly
        self.mock_ipfs.ipfs_dht_query.assert_called_once_with(test_key, timeout=30)
        
        # Verify performance stats were updated
        self.assertEqual(self.backend.performance_stats["dht_query"]["count"], 1)
        self.assertGreaterEqual(self.backend.performance_stats["dht_query"]["total_time"], 0)
    
    def test_dht_query_failure(self):
        """Test querying the DHT for a key with failure."""
        # Set up mock response for failure
        test_key = "/ipns/QmTest123456789"
        error_msg = "Failed to query DHT"
        self.mock_ipfs.ipfs_dht_query.return_value = MockIPFSResponse.error_response(error_msg)
        
        # Call the method
        result = self.backend.dht_query(test_key)
        
        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["key"], test_key)
        self.assertEqual(result["backend"], "ipfs")
        self.assertEqual(result["error"], error_msg)


if __name__ == "__main__":
    unittest.main()