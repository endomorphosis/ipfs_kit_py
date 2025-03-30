#!/usr/bin/env python3
"""
Tests for IPFS Gateway compatibility in the FSSpec implementation.

This module tests the ability to use remote IPFS gateways as alternatives to a
local IPFS daemon, with proper fallback mechanisms and handling of gateway-specific
features and limitations.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path to import ipfs_kit_py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.error import IPFSConnectionError, IPFSContentNotFoundError

class TestGatewayCompatibility(unittest.TestCase):
    """Test case for IPFS gateway compatibility features."""
    
    def setUp(self):
        """Set up test environment."""
        # Public test CID known to exist on the IPFS network
        # This is a small text file that should be available via most gateways
        self.test_cid = "QmPChd2hVbrJ6bfo3WBcTW4iZnpHm8TEzWkLHmLpXhF68A"
        
        # Set up mocks to avoid actual network/daemon dependencies
        self.session_patcher = patch('requests.Session')
        self.mock_session = self.session_patcher.start()
        self.mock_session_instance = MagicMock()
        self.mock_session.return_value = self.mock_session_instance
        
        # Mock response for successful API call
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.content = b"Test content"
        self.mock_session_instance.post.return_value = self.mock_response
        
        # Create IPFS kit instance
        self.kit = ipfs_kit()
        
    def tearDown(self):
        """Clean up after tests."""
        self.session_patcher.stop()
    
    def test_gateway_configuration(self):
        """Test that gateway configuration can be set."""
        # Get filesystem with gateway configuration
        fs = self.kit.get_filesystem(
            gateway_urls=[
                "https://ipfs.io/ipfs/",
                "https://cloudflare-ipfs.com/ipfs/",
                "https://dweb.link/ipfs/"
            ]
        )
        
        # Check that the gateway URLs are properly set
        self.assertEqual(len(fs.gateway_urls), 3)
        self.assertIn("https://ipfs.io/ipfs/", fs.gateway_urls)
    
    def test_local_daemon_fallback_to_gateway(self):
        """Test that the filesystem falls back to gateways when local daemon is unavailable."""
        # Make local daemon connection fail
        self.mock_session_instance.post.side_effect = [
            IPFSConnectionError("Failed to connect to local daemon"),  # First attempt
            self.mock_response  # Gateway attempt succeeds
        ]
        
        # Get filesystem with gateway fallback enabled
        fs = self.kit.get_filesystem(
            gateway_urls=["https://ipfs.io/ipfs/"],
            use_gateway_fallback=True
        )
        
        # Try to get content - should succeed via gateway
        content = fs.cat(self.test_cid)
        
        # Check that content was fetched
        self.assertEqual(content, b"Test content")
        
        # Verify that a second request was made to the gateway
        self.assertEqual(self.mock_session_instance.post.call_count, 2)
    
    def test_gateway_fallback_chain(self):
        """Test that the filesystem tries multiple gateways in order."""
        # Mock multiple gateway responses: first fails, second succeeds
        self.mock_session_instance.post.side_effect = [
            IPFSConnectionError("Failed to connect to local daemon"),  # Local daemon
            IPFSConnectionError("Failed to connect to first gateway"),  # First gateway
            self.mock_response  # Second gateway succeeds
        ]
        
        # Get filesystem with multiple gateways
        fs = self.kit.get_filesystem(
            gateway_urls=[
                "https://gateway1.example.com/ipfs/",
                "https://gateway2.example.com/ipfs/"
            ],
            use_gateway_fallback=True
        )
        
        # Try to get content - should succeed via second gateway
        content = fs.cat(self.test_cid)
        
        # Check that content was fetched
        self.assertEqual(content, b"Test content")
        
        # Verify that three requests were made (daemon, gateway1, gateway2)
        self.assertEqual(self.mock_session_instance.post.call_count, 3)
    
    def test_gateway_only_mode(self):
        """Test that the filesystem can operate in gateway-only mode without local daemon."""
        # Get filesystem in gateway-only mode
        fs = self.kit.get_filesystem(
            gateway_urls=["https://ipfs.io/ipfs/"],
            gateway_only=True
        )
        
        # Try to get content - should go directly to gateway
        content = fs.cat(self.test_cid)
        
        # Check that content was fetched
        self.assertEqual(content, b"Test content")
        
        # Verify that only one request was made (directly to gateway)
        self.assertEqual(self.mock_session_instance.post.call_count, 1)
        
        # Check that the request URL was correctly formed
        args, kwargs = self.mock_session_instance.post.call_args
        self.assertIn("https://ipfs.io/ipfs/", args[0])
    
    def test_gateway_content_cached(self):
        """Test that content fetched from gateways is properly cached."""
        # Get filesystem in gateway-only mode
        fs = self.kit.get_filesystem(
            gateway_urls=["https://ipfs.io/ipfs/"],
            gateway_only=True
        )
        
        # First fetch - should go to gateway
        content1 = fs.cat(self.test_cid)
        
        # Reset mock to verify next call
        self.mock_session_instance.post.reset_mock()
        
        # Second fetch - should come from cache
        content2 = fs.cat(self.test_cid)
        
        # Both contents should be the same
        self.assertEqual(content1, content2)
        
        # No additional network requests should have been made
        self.mock_session_instance.post.assert_not_called()
    
    def test_gateway_operation_metrics(self):
        """Test that gateway operations are properly tracked in metrics."""
        # Get filesystem with metrics enabled
        fs = self.kit.get_filesystem(
            gateway_urls=["https://ipfs.io/ipfs/"],
            gateway_only=True,
            enable_metrics=True
        )
        
        # Perform a few operations
        fs.cat(self.test_cid)
        fs.cat(self.test_cid)
        fs.cat(self.test_cid)
        
        # Get metrics
        metrics = fs.get_performance_metrics()
        
        # Check that gateway operations are tracked
        self.assertIn('operations', metrics)
        self.assertIn('gateway_fetch', metrics['operations'])
        
        # First request goes to gateway, rest to cache
        self.assertEqual(metrics['operations']['gateway_fetch']['count'], 1)
        
        # Cache metrics should show appropriate hits
        self.assertEqual(metrics['cache']['total'], 3)
        self.assertEqual(metrics['cache']['memory_hits'], 2)
    
    def test_gateway_path_formatting(self):
        """Test that paths are correctly formatted for different gateway types."""
        # First gateway - subdomain format (e.g., https://cid.ipfs.example.com)
        self.mock_session_instance.post.reset_mock()
        fs1 = self.kit.get_filesystem(
            gateway_urls=["https://{cid}.ipfs.example.com"],  # Subdomain gateway
            gateway_only=True
        )
        
        fs1.cat(self.test_cid)
        
        # Check that the URL was correctly formatted as a subdomain
        args1, _ = self.mock_session_instance.post.call_args
        self.assertIn(f"https://{self.test_cid}.ipfs.example.com", args1[0])
        
        # Second gateway - path format (e.g., https://example.com/ipfs/cid)
        self.mock_session_instance.post.reset_mock()
        fs2 = self.kit.get_filesystem(
            gateway_urls=["https://example.com/ipfs/{cid}"],  # Path gateway
            gateway_only=True
        )
        
        fs2.cat(self.test_cid)
        
        # Check that the URL was correctly formatted as a path
        args2, _ = self.mock_session_instance.post.call_args
        self.assertIn(f"https://example.com/ipfs/{self.test_cid}", args2[0])
        
        # Third gateway - URL template without placeholders
        self.mock_session_instance.post.reset_mock()
        fs3 = self.kit.get_filesystem(
            gateway_urls=["https://example.com/ipfs/"],  # Path gateway without placeholder
            gateway_only=True
        )
        
        fs3.cat(self.test_cid)
        
        # Check that the URL was correctly formatted
        args3, _ = self.mock_session_instance.post.call_args
        self.assertIn(f"https://example.com/ipfs/{self.test_cid}", args3[0])
        
    def test_gateway_http_method_handling(self):
        """Test that different HTTP methods are correctly used for different gateway operations."""
        # Get filesystem in gateway-only mode
        fs = self.kit.get_filesystem(
            gateway_urls=["https://ipfs.io/ipfs/"],
            gateway_only=True
        )
        
        # Reset mock to track calls
        self.mock_session_instance.post.reset_mock()
        self.mock_session_instance.get = MagicMock(return_value=self.mock_response)
        
        # Test cat operation (should use GET for gateways)
        fs.cat(self.test_cid)
        
        # Check that GET was used for gateway request
        self.mock_session_instance.get.assert_called_once()
        self.mock_session_instance.post.assert_not_called()

if __name__ == "__main__":
    unittest.main()