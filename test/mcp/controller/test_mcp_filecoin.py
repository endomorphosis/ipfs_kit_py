#!/usr/bin/env python
"""
Test script for Filecoin communication via the MCP server.

This script tests if the MCP server can successfully communicate with the Filecoin network
by exercising the FilecoinModelAnyIO capabilities.
"""

import os
import time
import json
import tempfile
import logging
import anyio
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("mcp_filecoin_test")

# Import MCP server components
from ipfs_kit_py.mcp_server.server_bridge import MCPServer  # Refactored import
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.lotus_kit import lotus_kit

# Define some test constants
TEST_RESULTS_DIR = "test_results"
TEST_RESULTS_FILE = os.path.join(TEST_RESULTS_DIR, "filecoin_test_results.json")

async def test_filecoin_connectivity(server: MCPServer) -> Dict[str, Any]:
    """
    Test if the Filecoin model can connect to the Filecoin network.
    
    Args:
        server: MCP server instance with Filecoin model
        
    Returns:
        Test results dictionary
    """
    results = {
        "success": False,
        "tests": {},
        "timestamp": time.time()
    }
    
    # Get the Filecoin model
    try:
        filecoin_model = server.models.get("storage_filecoin")
        if not filecoin_model:
            results["error"] = "Filecoin model not found in MCP server"
            results["error_type"] = "MissingModel"
            return results
            
        logger.info("Successfully acquired Filecoin model from MCP server")
    except Exception as e:
        results["error"] = f"Failed to get Filecoin model: {str(e)}"
        results["error_type"] = "ModelAccessError"
        return results
    
    # 1. Test connectivity to Lotus API
    logger.info("1. Testing connection to Lotus API...")
    connection_result = filecoin_model.check_connection()
    results["tests"]["connection"] = connection_result
    
    # If connection failed, no need to continue
    if not connection_result.get("success", False):
        results["error"] = connection_result.get("error", "Failed to connect to Lotus API")
        results["error_type"] = connection_result.get("error_type", "ConnectionError")
        return results
    
    logger.info(f"Connection successful: {connection_result.get('version', 'unknown version')}")
    
    # 2. List all wallets
    logger.info("2. Listing wallets...")
    wallets_result = filecoin_model.list_wallets()
    results["tests"]["list_wallets"] = wallets_result
    
    if wallets_result.get("success", False):
        wallets = wallets_result.get("wallets", [])
        logger.info(f"Found {len(wallets)} wallets")
        
        if len(wallets) > 0:
            default_wallet = wallets[0]
            
            # 3. Get wallet balance if we found at least one wallet
            logger.info(f"3. Getting balance for wallet {default_wallet}...")
            balance_result = filecoin_model.get_wallet_balance(default_wallet)
            results["tests"]["wallet_balance"] = balance_result
            
            if balance_result.get("success", False):
                logger.info(f"Wallet balance: {balance_result.get('balance', 'unknown')}")
            else:
                logger.warning(f"Failed to get wallet balance: {balance_result.get('error', 'unknown error')}")
    else:
        logger.warning(f"Failed to list wallets: {wallets_result.get('error', 'unknown error')}")
    
    # 4. List miners
    logger.info("4. Listing miners...")
    miners_result = filecoin_model.list_miners()
    results["tests"]["list_miners"] = miners_result
    
    if miners_result.get("success", False):
        miners = miners_result.get("miners", [])
        logger.info(f"Found {len(miners)} miners")
        
        if len(miners) > 0:
            example_miner = miners[0]
            
            # 5. Get miner info for the first miner
            logger.info(f"5. Getting miner info for {example_miner}...")
            miner_info_result = filecoin_model.get_miner_info(example_miner)
            results["tests"]["miner_info"] = miner_info_result
            
            if miner_info_result.get("success", False):
                logger.info(f"Successfully retrieved miner info for {example_miner}")
            else:
                logger.warning(f"Failed to get miner info: {miner_info_result.get('error', 'unknown error')}")
    else:
        logger.warning(f"Failed to list miners: {miners_result.get('error', 'unknown error')}")
    
    # 6. List deals
    logger.info("6. Listing existing deals...")
    deals_result = filecoin_model.list_deals()
    results["tests"]["list_deals"] = deals_result
    
    if deals_result.get("success", False):
        deals = deals_result.get("deals", [])
        logger.info(f"Found {len(deals)} deals")
    else:
        logger.warning(f"Failed to list deals: {deals_result.get('error', 'unknown error')}")
    
    # 7. Test import file if IPFS has a test file
    try:
        # Check if IPFS model exists
        ipfs_model = server.models.get("ipfs")
        if ipfs_model:
            logger.info("7. Testing IPFS integration by importing a file...")
            
            # Create a test file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
                temp_path = temp_file.name
                content = f"Test file for Filecoin integration, generated at {time.time()}"
                temp_file.write(content.encode('utf-8'))
                temp_file.flush()
            
            try:
                # Add file to IPFS
                logger.info(f"7.1 Adding test file to IPFS: {temp_path}")
                add_result = ipfs_model.add_file(temp_path)
                results["tests"]["ipfs_add_file"] = add_result
                
                if add_result.get("success", False):
                    cid = add_result.get("cid")
                    logger.info(f"Successfully added file to IPFS with CID: {cid}")
                    
                    # Now test IPFS to Filecoin integration if we have both wallets and miners
                    if wallets_result.get("success", False) and miners_result.get("success", False):
                        # Only try to import to Filecoin if we have wallets and miners
                        if len(wallets) > 0 and len(miners) > 0:
                            default_wallet = wallets[0]
                            example_miner = miners[0]
                            
                            logger.info(f"7.2 Testing IPFS to Filecoin with CID: {cid}")
                            ipfs_to_filecoin_result = filecoin_model.ipfs_to_filecoin(
                                cid=cid,
                                miner=example_miner,
                                price="0",  # Free deal for testing
                                duration=518400,  # ~6 months in epochs
                                wallet=default_wallet,
                                verified=False,
                                fast_retrieval=True,
                                pin=True
                            )
                            results["tests"]["ipfs_to_filecoin"] = ipfs_to_filecoin_result
                            
                            if ipfs_to_filecoin_result.get("success", False):
                                logger.info(f"Successfully started deal for IPFS content to Filecoin")
                                logger.info(f"Deal CID: {ipfs_to_filecoin_result.get('deal_cid', 'unknown')}")
                            else:
                                logger.warning(f"Failed to start IPFS to Filecoin deal: {ipfs_to_filecoin_result.get('error', 'unknown error')}")
                else:
                    logger.warning(f"Failed to add file to IPFS: {add_result.get('error', 'unknown error')}")
            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
    except Exception as e:
        logger.warning(f"Error during IPFS integration test: {e}")
        results["tests"]["ipfs_integration_error"] = str(e)
    
    # Determine overall success
    # We consider the test successful if at least the connection test passed
    results["success"] = connection_result.get("success", False)
    results["message"] = "Filecoin connectivity test completed"
    
    return results

async def main():
    """Main function for running the MCP Filecoin test."""
    # Create temp directory for MCP server persistence
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Created temporary directory for MCP server: {temp_dir}")
        
        # Create MCP server with debug mode enabled
        logger.info("Initializing MCP server...")
        mcp_server = MCPServer(
            debug_mode=True,
            log_level="INFO",
            persistence_path=temp_dir,
            isolation_mode=True  # Use isolation mode to avoid affecting the host system
        )
        
        try:
            logger.info("Running Filecoin connectivity test...")
            results = await test_filecoin_connectivity(mcp_server)
            
            # Save the test results
            with open(TEST_RESULTS_FILE, 'w') as f:
                json.dump(results, f, indent=2)
            
            if results["success"]:
                logger.info("✅ Filecoin connectivity test successful!")
            else:
                logger.error(f"❌ Filecoin connectivity test failed: {results.get('error', 'unknown error')}")
            
            logger.info(f"Test results saved to {TEST_RESULTS_FILE}")
            
            # Print summary
            print("\n📋 Test Summary:")
            
            print(f"- Connection to Lotus API: {'✅ Success' if results['tests'].get('connection', {}).get('success', False) else '❌ Failed'}")
            
            if 'list_wallets' in results['tests']:
                wallet_result = results['tests']['list_wallets']
                print(f"- List wallets: {'✅ Success' if wallet_result.get('success', False) else '❌ Failed'}")
                if wallet_result.get('success', False):
                    print(f"  Found {wallet_result.get('count', 0)} wallets")
            
            if 'list_miners' in results['tests']:
                miner_result = results['tests']['list_miners']
                print(f"- List miners: {'✅ Success' if miner_result.get('success', False) else '❌ Failed'}")
                if miner_result.get('success', False):
                    print(f"  Found {miner_result.get('count', 0)} miners")
            
            if 'list_deals' in results['tests']:
                deals_result = results['tests']['list_deals']
                print(f"- List deals: {'✅ Success' if deals_result.get('success', False) else '❌ Failed'}")
                if deals_result.get('success', False):
                    print(f"  Found {deals_result.get('count', 0)} deals")
            
            if 'ipfs_to_filecoin' in results['tests']:
                ipfs_to_filecoin_result = results['tests']['ipfs_to_filecoin']
                print(f"- IPFS to Filecoin: {'✅ Success' if ipfs_to_filecoin_result.get('success', False) else '❌ Failed'}")
                if ipfs_to_filecoin_result.get('success', False):
                    print(f"  Deal CID: {ipfs_to_filecoin_result.get('deal_cid', 'unknown')}")
            
        finally:
            # Clean up MCP server
            logger.info("Shutting down MCP server...")
            mcp_server.shutdown()
            
            logger.info("Test completed!")

if __name__ == "__main__":
    # Run the test
    anyio.run(main())