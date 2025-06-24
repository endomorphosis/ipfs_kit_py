"""
Tests for DHT operations in the MCP Server.

This module tests the DHT operations (dht_findpeer, dht_findprovs)
in the IPFS Model of the MCP server.
"""

import unittest
from unittest.mock import patch, MagicMock, call
import json
import os
import sys
import time

# Add the parent directory to the path so we can import the ipfs_kit_py module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel


class TestMCPDHTOperations(unittest.TestCase):
    """Test case for DHT operations in the MCP Server."""

    def setUp(self):
        """Set up the test environment."""
        # Create a mock IPFS Kit instance
        self.mock_ipfs_kit = MagicMock()
        self.mock_cache_manager = MagicMock()

        # Create an instance of the IPFS Model with the mock IPFS Kit
        self.ipfs_model = IPFSModel(
            ipfs_kit_instance=self.mock_ipfs_kit,
            cache_manager=self.mock_cache_manager
        )

    def test_dht_findpeer_success(self):
        """Test that dht_findpeer correctly finds a peer."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"

        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {
                    "ID": "QmFoundPeer1",
                    "Addrs": [
                        "/ip4/127.0.0.1/tcp/4001",
                        "/ip6/::1/tcp/4001"
                    ]
                }
            ],
            "Extra": "Some additional info"
        }

        # Mock the dht_findpeer method
        self.mock_ipfs_kit.dht_findpeer.return_value = expected_response

        # Call the method
        result = self.ipfs_model.dht_findpeer(test_peer_id)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findpeer")
        self.assertEqual(result["peer_id"], test_peer_id)
        self.assertIn("responses", result)
        self.assertEqual(len(result["responses"]), 1)
        self.assertEqual(result["responses"][0]["id"], "QmFoundPeer1")
        self.assertEqual(len(result["responses"][0]["addrs"]), 2)

        # Verify the mock was called correctly
        self.mock_ipfs_kit.dht_findpeer.assert_called_once_with(test_peer_id)

    def test_dht_findpeer_empty_response(self):
        """Test handling of empty response from dht_findpeer."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"

        # Empty response
        empty_response = {
            "Responses": []
        }

        # Mock the dht_findpeer method
        self.mock_ipfs_kit.dht_findpeer.return_value = empty_response

        # Call the method
        result = self.ipfs_model.dht_findpeer(test_peer_id)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findpeer")
        self.assertEqual(result["peer_id"], test_peer_id)
        self.assertIn("responses", result)
        self.assertEqual(len(result["responses"]), 0)
        self.assertEqual(result["peers_found"], 0)

    def test_dht_findpeer_error(self):
        """Test error handling in dht_findpeer."""
        # Test peer ID to find
        test_peer_id = "QmTestPeerID"

        # Mock the dht_findpeer method to raise an exception
        self.mock_ipfs_kit.dht_findpeer.side_effect = Exception("DHT error")

        # Call the method
        result = self.ipfs_model.dht_findpeer(test_peer_id)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dht_findpeer")
        self.assertEqual(result["peer_id"], test_peer_id)
        self.assertIn("error", result)
        self.assertIn("DHT error", result["error"])
        self.assertEqual(result["error_type"], "dht_error")

    def test_dht_findprovs_success(self):
        """Test that dht_findprovs correctly finds providers for a CID."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"

        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {
                    "ID": "QmProvider1",
                    "Addrs": [
                        "/ip4/192.168.1.1/tcp/4001",
                        "/ip6/2001:db8::1/tcp/4001"
                    ]
                },
                {
                    "ID": "QmProvider2",
                    "Addrs": [
                        "/ip4/192.168.1.2/tcp/4001"
                    ]
                }
            ],
            "Extra": "Additional information"
        }

        # Mock the dht_findprovs method
        self.mock_ipfs_kit.dht_findprovs.return_value = expected_response

        # Call the method
        result = self.ipfs_model.dht_findprovs(test_cid)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn("providers", result)
        self.assertEqual(len(result["providers"]), 2)
        self.assertEqual(result["providers"][0]["id"], "QmProvider1")
        self.assertEqual(len(result["providers"][0]["addrs"]), 2)
        self.assertEqual(result["providers"][1]["id"], "QmProvider2")
        self.assertEqual(len(result["providers"][1]["addrs"]), 1)
        self.assertEqual(result["count"], 2)

        # Verify the mock was called correctly
        self.mock_ipfs_kit.dht_findprovs.assert_called_once_with(test_cid)

    def test_dht_findprovs_with_num_providers(self):
        """Test that dht_findprovs respects the num_providers parameter."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"
        test_num_providers = 5

        # Test response from IPFS kit
        expected_response = {
            "Responses": [
                {"ID": "QmProvider1", "Addrs": ["/ip4/192.168.1.1/tcp/4001"]},
                {"ID": "QmProvider2", "Addrs": ["/ip4/192.168.1.2/tcp/4001"]}
            ]
        }

        # Mock the dht_findprovs method
        self.mock_ipfs_kit.dht_findprovs.return_value = expected_response

        # Call the method
        result = self.ipfs_model.dht_findprovs(test_cid, num_providers=test_num_providers)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertEqual(result["cid"], test_cid)
        self.assertEqual(result["num_providers"], test_num_providers)

        # Verify the mock was called correctly
        self.mock_ipfs_kit.dht_findprovs.assert_called_once_with(
            test_cid, num_providers=test_num_providers
        )

    def test_dht_findprovs_empty_response(self):
        """Test handling of empty response from dht_findprovs."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"

        # Empty response
        empty_response = {
            "Responses": []
        }

        # Mock the dht_findprovs method
        self.mock_ipfs_kit.dht_findprovs.return_value = empty_response

        # Call the method
        result = self.ipfs_model.dht_findprovs(test_cid)

        # Verify the result
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn("providers", result)
        self.assertEqual(len(result["providers"]), 0)
        self.assertEqual(result["count"], 0)

    def test_dht_findprovs_error(self):
        """Test error handling in dht_findprovs."""
        # Test CID to find providers for
        test_cid = "QmTestContentID"

        # Mock the dht_findprovs method to raise an exception
        self.mock_ipfs_kit.dht_findprovs.side_effect = Exception("DHT error")

        # Call the method
        result = self.ipfs_model.dht_findprovs(test_cid)

        # Verify the result
        self.assertFalse(result["success"])
        self.assertEqual(result["operation"], "dht_findprovs")
        self.assertEqual(result["cid"], test_cid)
        self.assertIn("error", result)
        self.assertIn("DHT error", result["error"])
        self.assertEqual(result["error_type"], "dht_error")


if __name__ == "__main__":
    unittest.main()
