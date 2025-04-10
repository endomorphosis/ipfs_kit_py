#!/usr/bin/env python3
"""
Minimal direct test of Filecoin/Lotus connectivity.
This script bypasses the MCP framework completely and directly tests the lotus_kit.
"""

import os
import json
import logging
import time
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Import lotus_kit directly
try:
    from ipfs_kit_py.lotus_kit import lotus_kit
    logger.info("Successfully imported lotus_kit")
except ImportError as e:
    logger.error(f"Failed to import lotus_kit: {e}")
    exit(1)

def test_lotus_connectivity():
    """Test basic connectivity to the Lotus API."""
    
    results = {
        "test_time": datetime.datetime.now().isoformat(),
        "tests": {},
        "overall_success": False
    }
    
    # Initialize lotus_kit directly
    logger.info("Initializing lotus_kit...")
    
    # Check if we have custom API parameters from environment
    api_url = os.environ.get("LOTUS_API", "http://localhost:1234/rpc/v0")
    token = os.environ.get("LOTUS_TOKEN", "")
    
    metadata = {
        "api_url": api_url,
        "token": token
    }
    
    try:
        client = lotus_kit(resources={}, metadata=metadata)
        logger.info(f"lotus_kit initialized with API URL: {api_url}")
        results["tests"]["initialization"] = {"success": True}
    except Exception as e:
        logger.error(f"Failed to initialize lotus_kit: {e}")
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
                balance_result = client.wallet_balance(wallet_address)
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
                miner_info_result = client.miner_get_info(miner_address)
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
        deals_result = client.client_list_deals()
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
    logger.info("Starting direct Lotus connectivity test")
    
    test_results = test_lotus_connectivity()
    
    # Save results to a file
    results_file = "lotus_test_results.json"
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