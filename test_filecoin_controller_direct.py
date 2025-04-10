#!/usr/bin/env python3
"""
Direct test of FilecoinController with real network interactions.

This script tests the FilecoinController by creating an instance with a real
FilecoinModel and sending test requests to its endpoints, bypassing FastAPI
to directly evaluate the controller's methods.

It supports both real network mode and mock mode, automatically detecting
if credentials are available.

Usage:
    python test_filecoin_controller_direct.py
"""

import os
import sys
import time
import logging
import tempfile
import random
import json
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("filecoin-controller-test")

# Import required modules
try:
    from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_KIT_AVAILABLE
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import (
        WalletRequest, DealRequest, RetrieveRequest, IPFSToFilecoinRequest,
        FilecoinToIPFSRequest, ImportFileRequest, MinerInfoRequest
    )
    from ipfs_kit_py.credential_manager import CredentialManager
except ImportError as e:
    logger.error(f"Import error: {e}")
    print(f"Failed to import required modules: {e}")
    sys.exit(1)

def check_api_credentials():
    """Check if Filecoin API credentials are available."""
    try:
        # Check for direct environment variable
        if os.environ.get("LOTUS_API_TOKEN"):
            logger.info("Found Filecoin API token in environment variables")
            return True
            
        # Try to get stored credentials from credential manager
        cred_manager = CredentialManager()
        filecoin_creds = cred_manager.get_filecoin_credentials("default")
        
        if not filecoin_creds:
            logger.warning("No Filecoin credentials found in credential store")
            return False
            
        logger.info("Found Filecoin credentials in credential store")
        return True
    except Exception as e:
        logger.error(f"Error checking credentials: {e}")
        return False

def generate_test_content(size_kb=10):
    """Generate random test content of specified size in KB."""
    # Create random data
    data = bytes(random.getrandbits(8) for _ in range(size_kb * 1024))
    return data

async def run_tests():
    """Run the tests against the FilecoinController."""
    logger.info("Setting up FilecoinController test...")
    
    # Check for credentials
    has_credentials = check_api_credentials()
    
    # Initialize metadata with defaults or environment variables
    metadata = {
        "api_url": os.environ.get("LOTUS_API_URL", "http://localhost:1234/rpc/v0"),
        "token": os.environ.get("LOTUS_API_TOKEN", ""),
        "lotus_path": os.environ.get("LOTUS_PATH", "/tmp/lotus"),
        "mock_mode": not has_credentials
    }
    
    # Try to get stored credentials if environment variables not set
    if not metadata["token"] and has_credentials:
        try:
            cred_manager = CredentialManager()
            filecoin_creds = cred_manager.get_filecoin_credentials("default")
            if filecoin_creds:
                metadata["token"] = filecoin_creds.get("api_key", "")
        except Exception as e:
            logger.warning(f"Could not get credentials from manager: {e}")
    
    # Create a temporary test file
    test_data = generate_test_content()
    fd, test_file_path = tempfile.mkstemp()
    with os.fdopen(fd, 'wb') as f:
        f.write(test_data)
    
    logger.info(f"Created test file at {test_file_path} with size {len(test_data)/1024} KB")
    
    # Initialize FilecoinModel and FilecoinController
    try:
        # Initialize the model
        lotus = lotus_kit(metadata=metadata)
        logger.info(f"Initialized lotus_kit (mock_mode={metadata['mock_mode']})")
        
        filecoin_model = FilecoinModel(lotus_kit_instance=lotus)
        logger.info("Initialized FilecoinModel")
        
        # Create the controller
        controller = FilecoinController(filecoin_model)
        logger.info("Initialized FilecoinController")
        
        # Run tests on controller methods
        results = {}
        
        # Test 1: Status check
        logger.info("Testing status check...")
        try:
            result = await controller.handle_status_request()
            results["status"] = {
                "success": True,
                "result": result
            }
            logger.info(f"Status check result: {result.get('is_available')}")
        except Exception as e:
            results["status"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in status check: {e}")
        
        # Test 2: List wallets
        logger.info("Testing wallet listing...")
        try:
            result = await controller.handle_list_wallets_request()
            results["list_wallets"] = {
                "success": True,
                "result": result
            }
            logger.info(f"Found {result.get('count', 0)} wallets")
            
            # Store wallet for later tests if available
            if result.get("wallets") and len(result.get("wallets", [])) > 0:
                test_wallet = result["wallets"][0]
                logger.info(f"Using wallet {test_wallet} for tests")
            else:
                test_wallet = None
        except Exception as e:
            results["list_wallets"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in wallet listing: {e}")
            test_wallet = None
        
        # Test 3: Create wallet (if needed)
        if not test_wallet:
            logger.info("Testing wallet creation...")
            try:
                wallet_request = WalletRequest(wallet_type="secp256k1")
                result = await controller.handle_create_wallet_request(wallet_request)
                results["create_wallet"] = {
                    "success": True,
                    "result": result
                }
                
                if result.get("success") and result.get("address"):
                    test_wallet = result["address"]
                    logger.info(f"Created wallet {test_wallet}")
                else:
                    logger.warning("Wallet creation did not return an address")
            except Exception as e:
                results["create_wallet"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in wallet creation: {e}")
        
        # Test 4: Wallet balance
        if test_wallet:
            logger.info(f"Testing wallet balance for {test_wallet}...")
            try:
                result = await controller.handle_wallet_balance_request(test_wallet)
                results["wallet_balance"] = {
                    "success": True,
                    "result": result
                }
                logger.info(f"Wallet balance: {result.get('balance', 'Unknown')}")
            except Exception as e:
                results["wallet_balance"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in wallet balance check: {e}")
        
        # Test 5: Import file
        logger.info("Testing file import...")
        try:
            import_request = ImportFileRequest(file_path=test_file_path)
            result = await controller.handle_import_file_request(import_request)
            results["import_file"] = {
                "success": True,
                "result": result
            }
            
            if result.get("success") and result.get("root"):
                test_cid = result["root"]
                logger.info(f"Imported file with CID {test_cid}")
            else:
                logger.warning("File import did not return a CID")
                test_cid = None
        except Exception as e:
            results["import_file"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in file import: {e}")
            test_cid = None
        
        # Test 6: List imports
        logger.info("Testing import listing...")
        try:
            result = await controller.handle_list_imports_request()
            results["list_imports"] = {
                "success": True,
                "result": result
            }
            logger.info(f"Found {result.get('count', 0)} imports")
        except Exception as e:
            results["list_imports"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in import listing: {e}")
        
        # Test 7: List deals
        logger.info("Testing deal listing...")
        try:
            result = await controller.handle_list_deals_request()
            results["list_deals"] = {
                "success": True,
                "result": result
            }
            logger.info(f"Found {result.get('count', 0)} deals")
            
            # Store deal ID for later tests if available
            if result.get("deals") and len(result.get("deals", [])) > 0:
                test_deal_id = result["deals"][0].get("DealID")
                if test_deal_id:
                    logger.info(f"Using deal {test_deal_id} for tests")
                else:
                    test_deal_id = None
            else:
                test_deal_id = None
        except Exception as e:
            results["list_deals"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in deal listing: {e}")
            test_deal_id = None
        
        # Test 8: Deal info (if a deal exists)
        if test_deal_id:
            logger.info(f"Testing deal info for deal {test_deal_id}...")
            try:
                result = await controller.handle_deal_info_request(test_deal_id)
                results["deal_info"] = {
                    "success": True,
                    "result": result
                }
                logger.info(f"Got info for deal {test_deal_id}")
            except Exception as e:
                results["deal_info"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in deal info check: {e}")
        
        # Test 9: List miners
        logger.info("Testing miner listing...")
        try:
            result = await controller.handle_list_miners_request()
            results["list_miners"] = {
                "success": True,
                "result": result
            }
            logger.info(f"Found {result.get('count', 0)} miners")
            
            # Store miner for later tests if available
            if result.get("miners") and len(result.get("miners", [])) > 0:
                test_miner = result["miners"][0]
                logger.info(f"Using miner {test_miner} for tests")
            else:
                test_miner = None
        except Exception as e:
            results["list_miners"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"Error in miner listing: {e}")
            test_miner = None
        
        # Test 10: Miner info (if a miner exists)
        if test_miner:
            logger.info(f"Testing miner info for miner {test_miner}...")
            try:
                miner_request = MinerInfoRequest(miner_address=test_miner)
                result = await controller.handle_miner_info_request(miner_request)
                results["miner_info"] = {
                    "success": True,
                    "result": result
                }
                logger.info(f"Got info for miner {test_miner}")
            except Exception as e:
                results["miner_info"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in miner info check: {e}")
        
        # Test 11: IPFS to Filecoin (if we have CID, wallet, and miner)
        if test_cid and test_wallet and test_miner:
            logger.info(f"Testing IPFS to Filecoin transfer...")
            try:
                ipfs_to_filecoin_request = IPFSToFilecoinRequest(
                    cid=test_cid,
                    miner=test_miner,
                    price="0",
                    duration=518400,
                    wallet=test_wallet,
                    verified=False,
                    fast_retrieval=True,
                    pin=True
                )
                result = await controller.handle_ipfs_to_filecoin_request(ipfs_to_filecoin_request)
                results["ipfs_to_filecoin"] = {
                    "success": True,
                    "result": result
                }
                logger.info(f"Transferred content from IPFS to Filecoin")
            except Exception as e:
                results["ipfs_to_filecoin"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in IPFS to Filecoin transfer: {e}")
        
        # Test 12: Filecoin to IPFS (if we have CID)
        if test_cid:
            logger.info(f"Testing Filecoin to IPFS transfer...")
            try:
                filecoin_to_ipfs_request = FilecoinToIPFSRequest(
                    data_cid=test_cid,
                    pin=True
                )
                result = await controller.handle_filecoin_to_ipfs_request(filecoin_to_ipfs_request)
                results["filecoin_to_ipfs"] = {
                    "success": True,
                    "result": result
                }
                logger.info(f"Transferred content from Filecoin to IPFS")
            except Exception as e:
                results["filecoin_to_ipfs"] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"Error in Filecoin to IPFS transfer: {e}")
        
        # Generate test summary
        successful_tests = sum(1 for test in results.values() if test.get("success", False))
        total_tests = len(results)
        
        summary = {
            "timestamp": time.time(),
            "mode": "real_api" if has_credentials else "mock_mode",
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": round(successful_tests / total_tests * 100, 2) if total_tests > 0 else 0,
            "results": results
        }
        
        print("\n" + "=" * 70)
        print("FILECOIN CONTROLLER TEST SUMMARY")
        print("=" * 70)
        print(f"Mode: {'REAL API' if has_credentials else 'MOCK MODE'}")
        print(f"Tests run: {total_tests}")
        print(f"Tests succeeded: {successful_tests}")
        print(f"Success rate: {summary['success_rate']}%")
        print("=" * 70)
        
        # Print individual test results
        print("\nIndividual Test Results:")
        for test_name, test_result in results.items():
            status = "SUCCESS" if test_result.get("success", False) else "FAILED"
            print(f"- {test_name}: {status}")
            if not test_result.get("success", False):
                print(f"  Error: {test_result.get('error', 'Unknown error')}")
        print("=" * 70)
        
        # Save results to file
        with open("filecoin_controller_test_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Test results saved to filecoin_controller_test_results.json")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
    finally:
        # Clean up
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)
            logger.info(f"Removed test file {test_file_path}")

async def main():
    """Main function."""
    await run_tests()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())