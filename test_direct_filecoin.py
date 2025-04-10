#!/usr/bin/env python3
"""
Direct test script to verify communication with the Filecoin network.

This script tests the FilecoinModel directly without using the full MCP server.
"""

import json
import logging
import os
import sys
import time
from typing import Dict, Any

from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_filecoin_communication():
    """Test direct communication with the Filecoin network."""
    results = {
        "success": False,
        "tests": {},
        "timestamp": time.time()
    }
    
    # Initialize lotus_kit
    logger.info("Initializing lotus_kit...")
    metadata = {
        "api_url": "http://localhost:1234/rpc/v0",  # Default Lotus API URL
        "token": "",  # No token by default
        "lotus_path": os.path.expanduser("~/.lotus")  # Default Lotus path
    }
    lotus_instance = lotus_kit(metadata=metadata)
    
    # Initialize FilecoinModel
    logger.info("Initializing FilecoinModel...")
    filecoin_model = FilecoinModel(lotus_kit_instance=lotus_instance)
    
    # Test 1: Check connection to Lotus API
    logger.info("Testing connection to Lotus API...")
    connection_result = filecoin_model.check_connection()
    results["tests"]["connection"] = connection_result
    
    if connection_result.get("success", False):
        logger.info(f"✅ Connection successful: {connection_result.get('version', 'unknown')}")
        results["success"] = True
    else:
        logger.error(f"❌ Connection failed: {connection_result.get('error', 'Unknown error')}")
        logger.error(f"Error type: {connection_result.get('error_type', 'Unknown')}")
        # If connection fails, no need to continue with other tests
        results["error"] = connection_result.get("error", "Failed to connect to Lotus API")
        results["error_type"] = connection_result.get("error_type", "ConnectionError")
        return results
    
    # Test 2: List wallets
    logger.info("Testing wallet listing...")
    wallet_result = filecoin_model.list_wallets()
    results["tests"]["list_wallets"] = wallet_result
    
    if wallet_result.get("success", False):
        wallets = wallet_result.get("wallets", [])
        logger.info(f"✅ Found {len(wallets)} wallet(s)")
        
        # If wallets exist, test getting balance of first wallet
        if wallets:
            address = wallets[0]
            logger.info(f"Testing balance retrieval for wallet: {address}")
            
            balance_result = filecoin_model.get_wallet_balance(address)
            results["tests"]["wallet_balance"] = balance_result
            
            if balance_result.get("success", False):
                logger.info(f"✅ Balance retrieved: {balance_result.get('balance', 'Unknown')}")
            else:
                logger.warning(f"⚠️ Failed to get wallet balance: {balance_result.get('error', 'Unknown error')}")
    else:
        logger.warning(f"⚠️ Failed to list wallets: {wallet_result.get('error', 'Unknown error')}")
    
    # Test 3: List miners
    logger.info("Testing miner listing...")
    miners_result = filecoin_model.list_miners()
    results["tests"]["list_miners"] = miners_result
    
    if miners_result.get("success", False):
        miners = miners_result.get("miners", [])
        logger.info(f"✅ Found {len(miners)} miner(s)")
        
        # If miners exist, test getting info for first miner
        if miners:
            miner = miners[0]
            logger.info(f"Testing miner info retrieval for: {miner}")
            
            miner_info_result = filecoin_model.get_miner_info(miner)
            results["tests"]["miner_info"] = miner_info_result
            
            if miner_info_result.get("success", False):
                logger.info(f"✅ Miner info retrieved successfully")
            else:
                logger.warning(f"⚠️ Failed to get miner info: {miner_info_result.get('error', 'Unknown error')}")
    else:
        logger.warning(f"⚠️ Failed to list miners: {miners_result.get('error', 'Unknown error')}")
    
    # Test 4: List deals
    logger.info("Testing deal listing...")
    deals_result = filecoin_model.list_deals()
    results["tests"]["list_deals"] = deals_result
    
    if deals_result.get("success", False):
        deals = deals_result.get("deals", [])
        logger.info(f"✅ Found {len(deals)} deal(s)")
    else:
        logger.warning(f"⚠️ Failed to list deals: {deals_result.get('error', 'Unknown error')}")
    
    # Print summary
    logger.info("\n=== Test Summary ===")
    for test_name, result in results["tests"].items():
        status = "✅ PASSED" if result.get("success", False) else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    # At this point we've completed basic connectivity tests
    return results

if __name__ == "__main__":
    # Run the test
    try:
        logger.info("Starting Filecoin communication test...")
        results = test_filecoin_communication()
        
        # Save results to file
        os.makedirs("test_results", exist_ok=True)
        result_file = os.path.join("test_results", "direct_filecoin_test_results.json")
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Test results saved to {result_file}")
        
        # Determine overall success
        overall_success = results.get("success", False)
        logger.info(f"\nOverall test result: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
        
        # Exit with appropriate code
        sys.exit(0 if overall_success else 1)
        
    except Exception as e:
        logger.exception(f"Error running test: {e}")
        sys.exit(1)