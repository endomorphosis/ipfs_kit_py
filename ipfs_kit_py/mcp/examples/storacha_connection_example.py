"""
Example demonstrating the enhanced StorachaConnectionManager.

This example shows how to use the new connection manager with its reliability features.
"""

import logging
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import random
from typing import Dict, Any

# Import the enhanced connection manager
from ipfs_kit_py.mcp.extensions.storacha_connection import (
    StorachaConnectionManager,
    StorachaApiError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("storacha_example")


def load_api_key() -> str:
    """
    Load Storacha API key from a configuration file or environment variable.
    This is just an example - you should use a secure method to store credentials.
    """
    try:
        # Check for config file in home directory
        config_path = Path.home() / ".storacha" / "config.json"
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
                return config.get("api_key", "")
        
        # Check for environment variable
        import os
        api_key = os.environ.get("STORACHA_API_KEY", "")
        if api_key:
            return api_key
    except Exception as e:
        logger.warning(f"Error loading API key: {e}")
    
    # For demo purposes, return a placeholder
    logger.warning("No API key found, using demo mode")
    return "demo_api_key"


def simulate_various_scenarios(connection: StorachaConnectionManager):
    """
    Simulate various scenarios to demonstrate connection manager features.
    """
    # Scenario 1: Basic health check
    logger.info("SCENARIO 1: Basic Health Check")
    try:
        response = connection.get("health")
        logger.info(f"Health check response: {response.status_code}")
        if response.status_code == 200:
            logger.info(f"API is healthy: {response.json()}")
    except StorachaApiError as e:
        logger.error(f"API error: {e}")
    
    # Show current status
    print_connection_status(connection)
    
    # Scenario 2: Upload a small file
    logger.info("\nSCENARIO 2: File Upload")
    try:
        # Create a small temporary file
        temp_file = Path("temp_test_file.txt")
        with open(temp_file, "w") as f:
            f.write(f"Test file created at {datetime.now().isoformat()}\n")
            f.write("This is a test file for the StorachaConnectionManager demo.\n")
        
        # Upload the file
        metadata = {
            "name": "Test File",
            "description": "Generated test file for StorachaConnectionManager demo",
            "timestamp": datetime.now().isoformat()
        }
        
        result = connection.upload_file(str(temp_file), metadata)
        logger.info(f"File uploaded with CID: {result.get('cid')}")
        
        # Clean up
        temp_file.unlink(missing_ok=True)
        
    except StorachaApiError as e:
        logger.error(f"Upload error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    
    # Show updated status
    print_connection_status(connection)
    
    # Scenario 3: Simulate endpoint failures to demonstrate failover
    logger.info("\nSCENARIO 3: Endpoint Failover Simulation")
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
            "success_count": 0
        }
        connection.working_endpoint = nonexistent_endpoint
        
        # Try to make a request, which should trigger failover
        logger.info(f"Attempting request with bad endpoint: {nonexistent_endpoint}")
        response = connection.get("health")
        logger.info(f"Request succeeded with failover to: {connection.working_endpoint}")
        
    except StorachaApiError as e:
        logger.error(f"API error (expected due to simulation): {e}")
    finally:
        # Restore original endpoints
        connection.endpoints = original_endpoints
        connection.endpoint_health = original_endpoint_health
        connection.working_endpoint = None  # Force re-validation
    
    # Show updated status after failover testing
    print_connection_status(connection)
    
    # Scenario 4: Simulate rate limiting
    logger.info("\nSCENARIO 4: Rate Limiting Simulation")
    
    # Save the original rate limiting data
    original_rate_limited_until = connection.rate_limited_until
    
    try:
        # Simulate being rate limited
        connection.rate_limited_until = time.time() + 30  # Rate limited for 30 seconds
        
        # Try to make a request, which should trigger rate limit handling
        logger.info("Attempting request while rate limited")
        try:
            connection.get("health")
        except StorachaApiError as e:
            logger.info(f"Correctly caught rate limiting error: {e}")
        
        # Restore rate limiting
        connection.rate_limited_until = original_rate_limited_until
        logger.info("Rate limit simulation complete")
        
    except Exception as e:
        # Restore rate limiting
        connection.rate_limited_until = original_rate_limited_until
        logger.error(f"Unexpected error during rate limit simulation: {e}")
    
    # Show final status
    print_connection_status(connection)


def print_connection_status(connection: StorachaConnectionManager):
    """Print the current status of the connection manager."""
    status = connection.get_status()
    
    print("\n=== CONNECTION STATUS ===")
    print(f"Working Endpoint: {status['working_endpoint']}")
    print(f"Total Requests: {status['total_requests']}")
    print(f"Success Rate: {status['success_rate']:.1f}%")
    print(f"Rate Limited Until: {datetime.fromtimestamp(status['rate_limited_until']).isoformat() if status['rate_limited_until'] > time.time() else 'Not rate limited'}")
    
    print("\nEndpoint Health:")
    for endpoint in status['endpoints']:
        health_status = "🟢 Healthy" if endpoint['healthy'] else "🔴 Unhealthy" if endpoint['healthy'] is not None else "⚪ Unknown"
        circuit_status = "🔓 Open" if endpoint['circuit_open'] else "🔒 Closed"
        print(f"  {endpoint['url']}:")
        print(f"    Status: {health_status}")
        print(f"    Circuit Breaker: {circuit_status}")
        print(f"    Success Rate: {endpoint['success_rate']:.1f}%")
        print(f"    Avg Response Time: {endpoint['avg_response_time']:.1f}ms")
        print(f"    Failures: {endpoint['failures']} (consecutive), {endpoint['total_failures']} (total)")
        print()


def main():
    """Main function to demonstrate the StorachaConnectionManager."""
    logger.info("Starting StorachaConnectionManager demonstration")
    
    # 1. Create a connection manager
    api_key = load_api_key()
    connection = StorachaConnectionManager(
        api_key=api_key,
        # Use custom endpoints for demonstration
        endpoints=[
            "https://up.storacha.network/bridge",
            "https://api.web3.storage",
            "https://api.storacha.network"
        ],
        max_retries=3,
        timeout=30,
        validate_endpoints=True,
        circuit_breaker_threshold=3,
        circuit_breaker_reset_time=60  # Short reset time for demo purposes
    )
    
    # 2. Run the demonstration scenarios
    simulate_various_scenarios(connection)
    
    logger.info("StorachaConnectionManager demonstration complete")


if __name__ == "__main__":
    main()