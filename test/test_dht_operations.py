#!/usr/bin/env python3
"""
Test and demonstrate the enhanced DHT operations for IPFS Kit.

This script tests the new DHT operations functionality and demonstrates
how to use the connection pool and DHT operations modules.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_dht_operations")

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our modules
from ipfs_connection_pool import IPFSConnectionConfig, IPFSConnectionPool, get_connection_pool
from ipfs_dht_operations import DHTOperations, DHTRecord

def pretty_print(data: Any) -> None:
    """Print formatted JSON data."""
    print(json.dumps(data, indent=2, sort_keys=True))

def test_connection_pool(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test the IPFS connection pool."""
    logger.info(f"Testing connection pool with API URL: {api_url}")

    # Create connection config
    config = IPFSConnectionConfig(
        base_url=api_url,
        max_connections=5,
        connection_timeout=30,
        idle_timeout=120,
    )

    # Create pool
    pool = IPFSConnectionPool(config)

    # Test with a simple API call
    try:
        logger.info("Testing connection with version API call")
        response = pool.post("version")

        if response.status_code == 200:
            version_info = response.json()
            logger.info(f"IPFS Version: {version_info.get('Version', 'unknown')}")
            logger.info("Connection pool test successful")
        else:
            logger.error(f"Connection failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")

    # Test multiple concurrent requests
    logger.info("Testing multiple concurrent requests")
    results = []

    def callback(response):
        """Callback for async requests."""
        if response.status_code == 200:
            data = response.json()
            results.append(data)

    # Submit multiple async requests
    futures = []
    for _ in range(10):
        future = pool.async_execute("POST", "id", callback=callback)
        futures.append(future)

    # Wait for all to complete
    for future in futures:
        future.result()

    logger.info(f"Completed {len(results)} concurrent requests")

    # Shutdown the pool
    pool.shutdown()
    logger.info("Connection pool shutdown complete")

def test_dht_operations(api_url: str = "http://127.0.0.1:5001/api/v0") -> None:
    """Test the DHT operations."""
    logger.info(f"Testing DHT operations with API URL: {api_url}")

    # Create connection config and pool
    config = IPFSConnectionConfig(base_url=api_url)
    pool = get_connection_pool(config)

    # Create DHT operations instance
    dht = DHTOperations(pool)

    # Test basic IPFS operations to ensure connectivity
    logger.info("Testing basic IPFS operations")
    try:
        response = pool.post("id")
        if response.status_code == 200:
            node_info = response.json()
            peer_id = node_info.get("ID")
            logger.info(f"Local node ID: {peer_id}")
        else:
            logger.error(f"Failed to get node ID: {response.status_code} - {response.text}")
            return
    except Exception as e:
        logger.error(f"Error connecting to IPFS node: {str(e)}")
        return

    # Test DHT put/get operations
    logger.info("Testing DHT put/get operations")

    # Create test key and value
    test_key = f"/test/dht-key-{int(time.time())}"
    test_value = f"Test value at {time.time()}".encode()

    # Put value
    logger.info(f"Putting value with key: {test_key}")
    put_result = dht.put_value(test_key, test_value)
    pretty_print(put_result)

    if put_result["success"]:
        logger.info("Put operation successful")

        # Get value
        logger.info(f"Getting value with key: {test_key}")
        get_result = dht.get_value(test_key)
        pretty_print(get_result)

        if get_result["success"] and get_result.get("value"):
            retrieved_value = get_result["value"]
            logger.info(f"Retrieved value: {retrieved_value.decode()}")

            # Verify value
            if retrieved_value == test_value:
                logger.info("Retrieved value matches original value ✓")
            else:
                logger.error("Retrieved value does not match original value ✗")
        else:
            logger.error("Failed to get value from DHT")
    else:
        logger.error("Failed to put value in DHT")

    # Test DHT provide/find providers operations
    logger.info("Testing DHT provide/find providers operations")

    # Add test content to IPFS
    logger.info("Adding test content to IPFS")
    test_content = f"Test content at {time.time()}".encode()
    add_response = pool.post("add", files={"file": ("test.txt", test_content)})

    if add_response.status_code == 200:
        add_result = json.loads(add_response.text)
        test_cid = add_result.get("Hash")
        logger.info(f"Added content with CID: {test_cid}")

        # Provide content
        logger.info(f"Announcing as provider for CID: {test_cid}")
        provide_result = dht.provide(test_cid)
        pretty_print(provide_result)

        if provide_result["success"]:
            logger.info("Provide operation successful")

            # Find providers
            logger.info(f"Finding providers for CID: {test_cid}")
            providers_result = dht.find_providers(test_cid)
            pretty_print(providers_result)

            if providers_result["success"]:
                logger.info(f"Found {len(providers_result.get('providers', []))} providers")
            else:
                logger.error("Failed to find providers")
        else:
            logger.error("Failed to provide content")
    else:
        logger.error(f"Failed to add test content: {add_response.status_code} - {add_response.text}")

    # Test finding peer
    logger.info(f"Testing find peer operation with local peer ID: {peer_id}")
    find_peer_result = dht.find_peer(peer_id)
    pretty_print(find_peer_result)

    if find_peer_result["success"]:
        logger.info(f"Found peer with {len(find_peer_result.get('addresses', []))} addresses")
    else:
        logger.error("Failed to find peer")

    # Test DHT query
    logger.info(f"Testing DHT query operation with peer ID: {peer_id}")
    query_result = dht.query(peer_id)
    pretty_print(query_result)

    if query_result["success"]:
        logger.info("Query operation successful")
    else:
        logger.error("Failed to query DHT")

    # Test routing table
    logger.info("Testing DHT routing table retrieval")
    routing_table_result = dht.get_routing_table()

    if routing_table_result["success"]:
        peers_count = routing_table_result.get("count", 0)
        logger.info(f"Retrieved routing table with {peers_count} peers")
    else:
        logger.error("Failed to get routing table")

    # Test network diagnostics
    logger.info("Testing network diagnostics")
    diagnostics_result = dht.get_network_diagnostics()

    if diagnostics_result["success"]:
        diagnostics = diagnostics_result.get("diagnostics", {})
        routing_table = diagnostics.get("routing_table", {})
        swarm_peers = diagnostics.get("swarm_peers", {})

        logger.info(f"DHT Routing table peers: {routing_table.get('peer_count', 0)}")
        logger.info(f"Connected swarm peers: {swarm_peers.get('count', 0)}")
    else:
        logger.error("Failed to get network diagnostics")

    # Test peer discovery
    logger.info("Testing peer discovery (limited to 10 peers)")
    discovery_result = dht.discover_peers(max_peers=10, timeout=30)

    if discovery_result["success"]:
        discovered_count = len(discovery_result.get("discovered_peers", []))
        logger.info(f"Discovered {discovered_count} peers in the network")
    else:
        logger.error("Failed to discover peers")

    # Get DHT metrics
    logger.info("Getting DHT operation metrics")
    metrics_result = dht.get_metrics()
    pretty_print(metrics_result)

    # Shutdown the connection pool
    pool.shutdown()
    logger.info("Test completed")

def main():
    """Main entry point for testing."""
    parser = argparse.ArgumentParser(description="Test IPFS DHT operations")
    parser.add_argument("--api", default="http://127.0.0.1:5001/api/v0", help="IPFS API URL")
    parser.add_argument("--test", choices=["pool", "dht", "all"], default="all", help="Test to run")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    logger.info(f"Testing with IPFS API: {args.api}")

    if args.test in ["pool", "all"]:
        test_connection_pool(args.api)

    if args.test in ["dht", "all"]:
        test_dht_operations(args.api)

if __name__ == "__main__":
    main()
