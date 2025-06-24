#\!/usr/bin/env python
"""
Test script for MCP server peer WebSocket functionality.

This script tests the peer WebSocket-related endpoints in the MCP server:
- Finding peers via WebSocket
- Getting peer information
- Connecting to discovered peers
"""

import argparse
import logging
import sys
import requests
import random
import time
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class PeerWebSocketTester:
    """MCP Server peer WebSocket functionality tester."""

    def __init__(self, base_url):
        """
        Initialize the peer WebSocket tester.

        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url
        self.api_base = f"{base_url}"  # Use base URL directly
        self.session = requests.Session()
        self.discovered_peers = {}

    def request(self, method, endpoint, **kwargs):
        """
        Make a request to the MCP server.

        Args:
            method: HTTP method (get, post, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            Response object
        """
        # We'll use the endpoint as provided without adding any prefix
        # The server routes already include the full path

        url = urljoin(self.base_url, endpoint)
        logger.debug(f"Request URL: {url}")
        method_func = getattr(self.session, method.lower())

        try:
            response = method_func(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Error details: {error_detail}")
                except:
                    logger.error(f"Response text: {e.response.text}")
            return {"success": False, "error": str(e)}

    def test_find_peers_websocket(self, discovery_servers=None, filter_role=None):
        """
        Test finding peers via WebSocket.

        Args:
            discovery_servers: List of WebSocket server URLs
            filter_role: Filter for peer role

        Returns:
            Response dictionary
        """
        logger.info("Testing finding peers via WebSocket...")

        # Build request parameters
        params = {
            "max_peers": 10,
            "timeout": 10
        }

        if discovery_servers:
            params["discovery_servers"] = discovery_servers

        if filter_role:
            params["filter_role"] = filter_role

        response = self.request("get", "/api/v0/mcp/peer/websocket/peers", params=params)
        logger.info(f"Find peers response: {response}")

        if response.get("success", False):
            logger.info("✅ WebSocket peer discovery succeeded")
            peers = response.get("peers", [])
            logger.info(f"Found {len(peers)} peers")

            # Store discovered peers for later use
            for peer in peers:
                peer_id = peer.get("peer_id")
                if peer_id:
                    self.discovered_peers[peer_id] = peer
                    logger.info(f"Peer ID: {peer_id}, Role: {peer.get('role', 'unknown')}")
        else:
            logger.error("❌ WebSocket peer discovery failed")

        return response

    def test_get_peer_info(self, peer_id=None):
        """
        Test getting information about a peer.

        Args:
            peer_id: ID of peer to query, or None for all peers

        Returns:
            Response dictionary
        """
        # Determine endpoint based on whether peer_id is provided
        if peer_id:
            endpoint = f"/api/v0/mcp/peer/websocket/peers/{peer_id}"
            logger.info(f"Testing getting info for peer: {peer_id}...")
        else:
            endpoint = "/api/v0/mcp/peer/websocket/peers"
            logger.info("Testing getting info for all peers...")

        response = self.request("get", endpoint)

        if response.get("success", False):
            if peer_id:
                logger.info("✅ Peer info retrieval succeeded")
                peer_info = response.get("peer", {})
                logger.info(f"Peer info: {peer_info}")
            else:
                logger.info("✅ All peers info retrieval succeeded")
                peers = response.get("peers", {})
                logger.info(f"Got info for {len(peers)} peers")
        else:
            logger.error("❌ Peer info retrieval failed")

        return response

    def test_connect_to_peer(self, peer_id=None):
        """
        Test connecting to a discovered peer.

        Args:
            peer_id: ID of peer to connect to, or None to use a random one

        Returns:
            Response dictionary
        """
        # If no peer ID provided, try to use one from discovered peers
        if peer_id is None:
            if not self.discovered_peers:
                # Discover peers first
                self.test_find_peers_websocket()

            if not self.discovered_peers:
                logger.warning("No peers discovered for connection test")
                return {"success": False, "error": "No peers discovered"}

            # Get a random peer ID
            peer_id = random.choice(list(self.discovered_peers.keys()))

        logger.info(f"Testing connecting to peer: {peer_id}...")

        params = {
            "timeout": 30
        }

        response = self.request("post", f"/api/v0/mcp/peer/websocket/client/connect/{peer_id}", params=params)
        logger.info(f"Connect to peer response: {response}")

        if response.get("success", False):
            logger.info("✅ Peer connection succeeded")
            connected_address = response.get("connected_address")
            logger.info(f"Connected to address: {connected_address}")
        else:
            logger.error("❌ Peer connection failed")

        return response

    def run_all_tests(self, discovery_servers=None):
        """
        Run all peer WebSocket tests.

        Args:
            discovery_servers: List of WebSocket server URLs

        Returns:
            Dictionary with test results
        """
        all_results = {}

        # Step 1: Find peers
        all_results["find_peers"] = self.test_find_peers_websocket(discovery_servers)

        # Step 2: Get info for all peers
        all_results["get_all_peers_info"] = self.test_get_peer_info()

        # Step 3: Get info for a specific peer (if peers discovered)
        if self.discovered_peers:
            peer_id = list(self.discovered_peers.keys())[0]
            all_results["get_specific_peer_info"] = self.test_get_peer_info(peer_id)

            # Step 4: Connect to a peer
            all_results["connect_to_peer"] = self.test_connect_to_peer(peer_id)

        return all_results

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test MCP server peer WebSocket functionality")
    parser.add_argument(
        "--url",
        default="http://localhost:9992",
        help="Base URL of the MCP server (default: http://localhost:9992)"
    )
    parser.add_argument(
        "--discovery-server",
        action="append",
        help="WebSocket discovery server URL (can be specified multiple times)"
    )
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()

    logger.info(f"Testing MCP server peer WebSocket functionality at {args.url}")

    tester = PeerWebSocketTester(args.url)
    results = tester.run_all_tests(args.discovery_server)

    successes = sum(1 for r in results.values() if r.get("success", False))
    failures = len(results) - successes

    logger.info(f"Tests completed: {len(results)} total, {successes} passed, {failures} failed")

    if failures > 0:
        logger.error("❌ Some tests failed")
        return 1
    else:
        logger.info("✅ All tests passed")
        return 0

if __name__ == "__main__":
    sys.exit(main())
