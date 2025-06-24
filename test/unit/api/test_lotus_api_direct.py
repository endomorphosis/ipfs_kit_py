#!/usr/bin/env python3
"""
Direct Lotus API Test Script

This script tests connectivity to a Lotus node's JSON-RPC API without any dependencies
on the ipfs_kit_py package. It implements a minimal client for the Lotus API and
tests basic operations like connection, wallet listing, and miner listing.
"""

import os
import json
import logging
import time
import datetime
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class LotusAPIClient:
    """Minimal client for Lotus JSON-RPC API"""

    def __init__(self, api_url=None, token=None):
        """Initialize Lotus API client.

        Args:
            api_url: Lotus API URL, defaults to localhost:1234
            token: Authorization token for Lotus API
        """
        self.api_url = api_url or os.environ.get("LOTUS_API", "http://localhost:1234/rpc/v0")
        self.token = token or os.environ.get("LOTUS_TOKEN", "")
        logger.info(f"Initialized Lotus API client with URL: {self.api_url}")

    def _make_request(self, method, params=None, timeout=60):
        """Make a request to the Lotus JSON-RPC API.

        Args:
            method: The Lotus API method name
            params: List of parameters for the method
            timeout: Request timeout in seconds

        Returns:
            Dict with operation result
        """
        result = {
            "success": False,
            "operation": method,
            "timestamp": time.time()
        }

        try:
            headers = {"Content-Type": "application/json"}

            # Add authorization token if available
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            # Prepare request data
            request_data = {
                "jsonrpc": "2.0",
                "method": f"Filecoin.{method}",
                "params": params or [],
                "id": 1
            }

            # Make the API request
            response = requests.post(
                self.api_url,
                headers=headers,
                json=request_data,
                timeout=timeout
            )

            # Check for HTTP errors
            response.raise_for_status()

            # Parse response
            response_data = response.json()

            # Check for JSON-RPC errors
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                error_code = response_data["error"].get("code", -1)
                result["error"] = f"Error {error_code}: {error_msg}"
                result["error_type"] = "RPCError"
                return result

            # Return successful result
            result["success"] = True
            result["result"] = response_data.get("result")
            return result

        except requests.exceptions.Timeout:
            result["error"] = f"Request timed out after {timeout} seconds"
            result["error_type"] = "TimeoutError"

        except requests.exceptions.ConnectionError as e:
            result["error"] = f"Failed to connect to Lotus API: {str(e)}"
            result["error_type"] = "ConnectionError"

        except requests.exceptions.HTTPError as e:
            result["error"] = f"HTTP error: {str(e)}"
            result["error_type"] = "HTTPError"

        except Exception as e:
            logger.exception(f"Error in {method}: {str(e)}")
            result["error"] = str(e)
            result["error_type"] = type(e).__name__

        return result

    def check_connection(self):
        """Check connection to the Lotus API."""
        return self._make_request("Version")

    def list_wallets(self):
        """List all wallet addresses."""
        return self._make_request("WalletList")

    def get_wallet_balance(self, address):
        """Get wallet balance."""
        return self._make_request("WalletBalance", params=[address])

    def list_miners(self):
        """List all miners in the network."""
        return self._make_request("StateListMiners", params=[[]])

    def get_miner_info(self, miner_address):
        """Get information about a specific miner."""
        return self._make_request("StateMinerInfo", params=[miner_address, []])

    def list_deals(self):
        """List all deals made by the client."""
        return self._make_request("ClientListDeals")


def test_lotus_connectivity():
    """Test basic connectivity to the Lotus API."""

    results = {
        "test_time": datetime.datetime.now().isoformat(),
        "tests": {},
        "overall_success": False
    }

    # Initialize LotusAPIClient
    logger.info("Initializing Lotus API client...")

    try:
        client = LotusAPIClient()
        results["tests"]["initialization"] = {"success": True}
    except Exception as e:
        logger.error(f"Failed to initialize Lotus API client: {e}")
        results["tests"]["initialization"] = {
            "success": False,
            "error": str(e)
        }
        return results

    # Test 1: Check connection
    try:
        logger.info("Testing connectivity to Lotus API...")
        connection_result = client.check_connection()
        results["tests"]["check_connection"] = connection_result

        if connection_result.get("success"):
            logger.info("✅ Successfully connected to Lotus API!")
            logger.info(f"Lotus version: {connection_result.get('result')}")
        else:
            logger.warning(f"❌ Failed to connect to Lotus API: {connection_result.get('error')}")
    except Exception as e:
        logger.error(f"Exception during connection test: {e}")
        results["tests"]["check_connection"] = {
            "success": False,
            "error": str(e)
        }

    # Determine overall success (at least basic connectivity test passed)
    results["overall_success"] = results["tests"].get("check_connection", {}).get("success", False)

    # Only continue with other tests if connection successful
    if not results["overall_success"]:
        logger.warning("Skipping remaining tests due to connection failure")
        return results

    # Test 2: List wallets
    try:
        logger.info("Testing wallet listing...")
        wallet_result = client.list_wallets()
        results["tests"]["list_wallets"] = wallet_result

        if wallet_result.get("success"):
            wallets = wallet_result.get("result", [])
            logger.info(f"Found {len(wallets)} wallets")

            # Test wallet balance if wallets exist
            if wallets:
                wallet_address = wallets[0]
                logger.info(f"Testing balance for wallet: {wallet_address}")
                balance_result = client.get_wallet_balance(wallet_address)
                results["tests"]["wallet_balance"] = balance_result

                if balance_result.get("success"):
                    logger.info(f"Wallet balance: {balance_result.get('result')}")
                else:
                    logger.warning(f"Failed to get wallet balance: {balance_result.get('error')}")
        else:
            logger.warning(f"Failed to list wallets: {wallet_result.get('error')}")
    except Exception as e:
        logger.error(f"Exception during wallet test: {e}")
        results["tests"]["wallet_operations"] = {
            "success": False,
            "error": str(e)
        }

    # Test 3: List miners
    try:
        logger.info("Testing miner listing...")
        miners_result = client.list_miners()
        results["tests"]["list_miners"] = miners_result

        if miners_result.get("success"):
            miners = miners_result.get("result", [])
            logger.info(f"Found {len(miners)} miners")

            # Test getting miner info if miners exist
            if miners:
                miner_address = miners[0]
                logger.info(f"Testing miner info for: {miner_address}")
                miner_info_result = client.get_miner_info(miner_address)
                results["tests"]["miner_info"] = miner_info_result

                if miner_info_result.get("success"):
                    logger.info(f"Successfully retrieved miner info")
                else:
                    logger.warning(f"Failed to get miner info: {miner_info_result.get('error')}")
        else:
            logger.warning(f"Failed to list miners: {miners_result.get('error')}")
    except Exception as e:
        logger.error(f"Exception during miner test: {e}")
        results["tests"]["miner_operations"] = {
            "success": False,
            "error": str(e)
        }

    # Test 4: List deals
    try:
        logger.info("Testing deal listing...")
        deals_result = client.list_deals()
        results["tests"]["list_deals"] = deals_result

        if deals_result.get("success"):
            deals = deals_result.get("result", [])
            logger.info(f"Found {len(deals)} deals")
        else:
            logger.warning(f"Failed to list deals: {deals_result.get('error')}")
    except Exception as e:
        logger.error(f"Exception during deals test: {e}")
        results["tests"]["deal_operations"] = {
            "success": False,
            "error": str(e)
        }

    return results

if __name__ == "__main__":
    logger.info("Starting direct Lotus API connectivity test")

    test_results = test_lotus_connectivity()

    # Save results to a file
    results_file = "lotus_api_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(test_results, f, indent=2)

    logger.info(f"Test results saved to {results_file}")

    # Print final summary
    if test_results["overall_success"]:
        logger.info("✅ Successfully connected to Filecoin network via Lotus API!")
    else:
        logger.error("❌ Failed to connect to Filecoin network via Lotus API!")

    # Print test summary
    for test_name, result in test_results["tests"].items():
        success = result.get("success", False)
        status = "✅ SUCCESS" if success else "❌ FAILED"
        if not success and result.get("skipped"):
            status = "⏭️ SKIPPED"
        logger.info(f"{status}: {test_name}")
