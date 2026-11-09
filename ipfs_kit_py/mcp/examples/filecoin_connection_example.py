"""
Example demonstrating the enhanced FilecoinConnectionManager.

This example shows how to use the new connection manager with its reliability features.
"""

import logging
import sys
import time
import json
from typing import Dict, Any, Optional, List
import os

# Import the enhanced connection manager
from ipfs_kit_py.mcp.extensions.filecoin_connection import (
    FilecoinConnectionManager,
    FilecoinApiError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("filecoin_example")


def load_token() -> Optional[str]:
    """
    Load Filecoin API token from a configuration file or environment variable.
    This is just an example - you should use a secure method to store credentials.
    """
    try:
        # Check for environment variable
        token = os.environ.get("FILECOIN_TOKEN")
        if token:
            return token
            
        # Check for config file in home directory
        config_path = os.path.expanduser("~/.lotus/token")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return f.read().strip()
        
    except Exception as e:
        logger.warning(f"Error loading token: {e}")
    
    # For demo purposes, continue without a token
    logger.warning("No API token found, using public endpoints only")
    return None


def pretty_print_json(data: Dict[str, Any]) -> None:
    """Print JSON data with proper formatting."""
    print(json.dumps(data, indent=2, sort_keys=True))


def simulate_various_scenarios(connection: FilecoinConnectionManager):
    """
    Simulate various scenarios to demonstrate connection manager features.
    """
    # Scenario 1: Basic Chain Information
    logger.info("SCENARIO 1: Basic Chain Information")
    try:
        # Get node info
        logger.info("Getting node information...")
        node_info = connection.get_node_info()
        print("\nNode Information:")
        pretty_print_json(node_info)
        
        # Get current chain head
        logger.info("Getting chain head...")
        chain_head = connection.get_chain_head()
        print("\nChain Head:")
        print(f"  Height: {chain_head.get('Height')}")
        print(f"  Blocks: {len(chain_head.get('Blocks', []))}")
        
        # Get base fee
        logger.info("Getting base fee...")
        base_fee = connection.get_base_fee()
        print(f"\nCurrent Base Fee: {base_fee}")
        
    except FilecoinApiError as e:
        logger.error(f"API error: {e}")
    
    # Show current status
    print_connection_status(connection)
    
    # Scenario 2: Endpoint Failover Simulation
    logger.info("\nSCENARIO 2: Endpoint Failover Simulation")
    # Force the connection to use a non-existent endpoint
    original_endpoints = connection.endpoints.copy()
    nonexistent_endpoint = "https://nonexistent.example.com"
    
    # Save the original endpoint health data
    original_endpoint_health = connection.endpoint_health.copy()
    
    try:
        # Add a non-existent endpoint as the primary endpoint
        connection.endpoints = [nonexistent_endpoint] + connection.endpoints
        connection.endpoint_health[nonexistent_endpoint] = {
            "healthy": None,
            "last_checked": 0,
            "failures": 0,
            "total_failures": 0,
            "circuit_open": False,
            "circuit_open_until": 0,
            "success_rate": 100.0,
            "avg_response_time": 0,
            "last_latency": 0,
            "requests_count": 0,
            "success_count": 0,
            "version": None,
            "height": None
        }
        connection.working_endpoint = nonexistent_endpoint
        
        # Try to make a request, which should trigger failover
        logger.info(f"Attempting request with bad endpoint: {nonexistent_endpoint}")
        node_info = connection.get_node_info()
        logger.info(f"Request succeeded with failover to: {connection.working_endpoint}")
        
    except FilecoinApiError as e:
        logger.error(f"API error (expected due to simulation): {e}")
    finally:
        # Restore original endpoints
        connection.endpoints = original_endpoints
        connection.endpoint_health = original_endpoint_health
        connection.working_endpoint = None  # Force re-validation
    
    # Show updated status after failover testing
    print_connection_status(connection)
    
    # Scenario 3: Getting Miner Information
    logger.info("\nSCENARIO 3: Miner Information")
    try:
        # List of example miners to query
        miners = ["f01234", "f0127595", "f01248"]
        
        for miner_addr in miners:
            logger.info(f"Getting information for miner {miner_addr}...")
            try:
                miner_info = connection.get_miner_info(miner_addr)
                print(f"\nMiner {miner_addr} Information:")
                pretty_print_json(miner_info)
            except FilecoinApiError as e:
                logger.warning(f"Could not get miner info for {miner_addr}: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    
    # Show final status
    print_connection_status(connection)
    
    # Scenario 4: Gas Estimation
    logger.info("\nSCENARIO 4: Gas Estimation")
    try:
        # Example message for gas estimation
        message = {
            "Version": 0,
            "To": "f01234",
            "From": "f137fjlk....",  # Some wallet address
            "Nonce": 0,
            "Value": "1000000000000000000",  # 1 FIL in attoFIL
            "GasLimit": 0,
            "GasFeeCap": "0",
            "GasPremium": "0",
            "Method": 0,
            "Params": ""
        }
        
        try:
            gas_estimate = connection.estimate_gas(message)
            print("\nGas Estimation:")
            pretty_print_json(gas_estimate)
        except FilecoinApiError as e:
            logger.warning(f"Gas estimation failed: {e}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def print_connection_status(connection: FilecoinConnectionManager):
    """Print the current status of the connection manager."""
    status = connection.get_status()
    
    print("\n=== CONNECTION STATUS ===")
    print(f"Working Endpoint: {status['working_endpoint']}")
    print(f"Total Requests: {status['total_requests']}")
    print(f"Success Rate: {status['success_rate']:.1f}%")
    
    print("\nChain Stats:")
    print(f"  Height: {status['chain_stats']['height']}")
    print(f"  Base Fee: {status['chain_stats']['base_fee']}")
    
    print("\nEndpoint Health:")
    for endpoint in status['endpoints']:
        health_status = "🟢 Healthy" if endpoint['healthy'] else "🔴 Unhealthy" if endpoint['healthy'] is not None else "⚪ Unknown"
        circuit_status = "🔓 Open" if endpoint['circuit_open'] else "🔒 Closed"
        print(f"  {endpoint['url']}:")
        print(f"    Status: {health_status}")
        print(f"    Circuit Breaker: {circuit_status}")
        print(f"    Success Rate: {endpoint['success_rate']:.1f}%")
        print(f"    Avg Response Time: {endpoint['avg_response_time']:.1f}ms")
        print(f"    Version: {endpoint['version'] or 'Unknown'}")
        print(f"    Failures: {endpoint['failures']} (consecutive), {endpoint['total_failures']} (total)")
        print()


def main():
    """Main function to demonstrate the FilecoinConnectionManager."""
    logger.info("Starting FilecoinConnectionManager demonstration")
    
    # 1. Create a connection manager
    token = load_token()
    connection = FilecoinConnectionManager(
        token=token,
        # Use both public and commonly known endpoints
        endpoints=[
            "https://api.node.glif.io/rpc/v0",       # Glif mainnet node
            "https://filecoin.infura.io/v3/public",  # Infura public node
            "https://lotus.miner.report/rpc/v0",     # Lotus Miner Report API
            "https://api.chain.love/rpc/v0"          # Chain Love API
        ],
        max_retries=3,
        timeout=30,
        validate_endpoints=True,
        circuit_breaker_threshold=3,
        circuit_breaker_reset_time=60  # Short reset time for demo purposes
    )
    
    # 2. Run the demonstration scenarios
    simulate_various_scenarios(connection)
    
    logger.info("FilecoinConnectionManager demonstration complete")


if __name__ == "__main__":
    main()