#!/usr/bin/env python3
"""
Enhanced direct test of FilecoinController with real network interactions.

This script tests the FilecoinController by creating an instance with a real
FilecoinModel and IPFS model for complete end-to-end testing of the storage
backend bridge functionality.

It installs and manages the Lotus daemon automatically, ensuring it's running
for the tests. If real credentials are available, it will connect to the real
Filecoin network; otherwise, it falls back to mock mode.

Usage:
    python test_filecoin_controller_direct_enhanced.py [options]
    
Options:
    --force-mock         Force mock mode even if daemon available
    --debug              Enable debug logging
    --lotus-path PATH    Custom Lotus path
    --api-token TOKEN    Custom API token
    --skip-daemon-stop   Don't stop daemon after tests
"""

import os
import sys
import time
import logging
import tempfile
import random
import json
import subprocess
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("filecoin-controller-test")

# Import required modules
try:
    from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_KIT_AVAILABLE
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import FilecoinController
    from ipfs_kit_py.mcp.controllers.storage.filecoin_controller import (
        WalletRequest, DealRequest, RetrieveRequest, IPFSToFilecoinRequest,
        FilecoinToIPFSRequest, ImportFileRequest, MinerInfoRequest
    )
    from ipfs_kit_py.credential_manager import CredentialManager
    from ipfs_kit_py.lotus_daemon import lotus_daemon
    from install_lotus import install_lotus as LotusInstaller
except ImportError as e:
    logger.error(f"Import error: {e}")
    print(f"Failed to import required modules: {e}")
    sys.exit(1)

def install_lotus_binary():
    """Install the Lotus binary if not already installed.
    
    Returns:
        bool: True if Lotus is installed (either found or newly installed), False otherwise
    """
    try:
        # Check if lotus is already installed
        try:
            result = subprocess.run(["which", "lotus"], 
                                   check=False, 
                                   capture_output=True)
            if result.returncode == 0 and result.stdout.strip():
                binary_path = result.stdout.strip().decode()
                logger.info(f"Lotus binary already installed at: {binary_path}")
                
                # Check version
                try:
                    version_result = subprocess.run(["lotus", "--version"],
                                                  check=False,
                                                  capture_output=True)
                    if version_result.returncode == 0:
                        version_str = version_result.stdout.strip().decode()
                        logger.info(f"Lotus version: {version_str}")
                    else:
                        logger.warning("Could not determine Lotus version, but binary exists")
                except Exception as e:
                    logger.warning(f"Error checking Lotus version: {e}")
                
                return True
        except Exception as e:
            logger.debug(f"Error checking for lotus binary: {e}")
            pass
            
        logger.info("Lotus binary not found. Installing...")
        
        # Create installer instance with lite version to minimize download size
        installer_metadata = {
            "version": os.environ.get("LOTUS_VERSION", "1.24.0"),
            "skip_params": True,  # Skip large parameter download for test purposes
            "force": False,
            "bin_dir": os.path.expanduser("~/.local/bin")
        }
        installer = LotusInstaller(metadata=installer_metadata)
        
        # Install lotus daemon
        logger.info("Installing Lotus daemon (this may take a few minutes)...")
        install_result = installer.install_lotus_daemon()
        
        if install_result.get("success", False):
            logger.info("Successfully installed Lotus daemon")
            
            # Add binary directory to PATH if not already in it
            bin_dir = installer_metadata["bin_dir"]
            if bin_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
                logger.info(f"Added {bin_dir} to PATH")
            
            return True
        else:
            logger.error(f"Failed to install Lotus daemon: {install_result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        logger.error(f"Error installing Lotus binary: {e}")
        return False

def ensure_lotus_daemon_running():
    """Ensure the Lotus daemon is running.
    
    This function checks if the Lotus daemon is running, and if not, starts it with appropriate
    configuration for test purposes.
    
    Returns:
        bool: True if the daemon is running (either was already running or successfully started),
              False otherwise
    """
    try:
        # Set LOTUS_PATH environment variable if not set
        if "LOTUS_PATH" not in os.environ:
            default_lotus_path = os.path.expanduser("~/.lotus")
            os.environ["LOTUS_PATH"] = default_lotus_path
            logger.info(f"Set LOTUS_PATH to {default_lotus_path}")
            
            # Create LOTUS_PATH directory if it doesn't exist
            os.makedirs(default_lotus_path, exist_ok=True)
            
        # Create daemon manager
        daemon = lotus_daemon()
        
        # Check daemon status
        logger.info("Checking Lotus daemon status...")
        status_result = daemon.daemon_status()
        
        if status_result.get("process_running", False):
            logger.info(f"Lotus daemon is already running with PID {status_result.get('pid')}")
            
            # Verify API is responsive by checking chain head
            try:
                logger.info("Verifying API responsiveness...")
                check_cmd = ["lotus", "chain", "head"]
                check_result = subprocess.run(check_cmd, 
                                           check=False, 
                                           capture_output=True,
                                           timeout=5)
                
                if check_result.returncode == 0:
                    logger.info("Lotus API is responsive")
                    return True
                else:
                    logger.warning("Lotus API is not responsive. Restarting daemon...")
                    daemon.daemon_stop(force=True)
                    time.sleep(2)  # Wait for shutdown
            except Exception as e:
                logger.warning(f"Error verifying API responsiveness: {e}. Restarting daemon...")
                daemon.daemon_stop(force=True)
                time.sleep(2)  # Wait for shutdown
            
        # Daemon is not running or not responsive, start it
        logger.info("Lotus daemon is not running. Starting...")
        
        # Configure daemon with lite mode for faster startup and appropriate metadata
        daemon_flags = {
            "lite": True,  # Lite mode for faster startup
            "bootstrap-peers": "",  # Empty for faster startup in test mode
            "api": 1234,  # API port
        }
        
        # Start with detailed flags to optimize for test environment
        start_result = daemon.daemon_start(
            lite=True,
            remove_stale_lock=True,
            api_port=1234,  # Default API port
        )
        
        if start_result.get("success", False):
            method = start_result.get("method", "unknown")
            pid = start_result.get("pid", "unknown")
            logger.info(f"Successfully started Lotus daemon via {method} method with PID {pid}")
            
            # Wait for daemon to fully initialize
            logger.info("Waiting for Lotus daemon to initialize...")
            initialized = False
            max_wait = 30  # seconds
            start_time = time.time()
            
            while not initialized and (time.time() - start_time) < max_wait:
                try:
                    check_cmd = ["lotus", "chain", "head"]
                    check_result = subprocess.run(check_cmd, 
                                               check=False, 
                                               capture_output=True,
                                               timeout=5)
                    
                    if check_result.returncode == 0:
                        initialized = True
                        logger.info("Lotus daemon is fully initialized and responsive")
                    else:
                        logger.debug("Lotus daemon not fully initialized yet. Waiting...")
                        time.sleep(2)
                except Exception as e:
                    logger.debug(f"Waiting for daemon initialization: {e}")
                    time.sleep(2)
            
            if initialized:
                return True
            else:
                logger.error("Lotus daemon started but failed to become responsive within timeout")
                return False
        else:
            error = start_result.get("error", "Unknown error")
            logger.error(f"Failed to start Lotus daemon: {error}")
            
            # Try to provide more details about the failure
            if "attempts" in start_result:
                logger.error(f"Startup attempt details: {json.dumps(start_result['attempts'], indent=2)}")
                
            return False
    except Exception as e:
        logger.error(f"Error managing Lotus daemon: {e}")
        return False

def check_api_credentials():
    """Check if Filecoin API credentials are available.
    
    This function checks for Filecoin API credentials from various sources:
    1. Direct environment variables
    2. Credential manager
    3. Default Lotus token file
    
    Returns:
        bool: True if credentials are available, False otherwise
    """
    try:
        # Check for direct environment variable
        if os.environ.get("LOTUS_API_TOKEN"):
            logger.info("Found Filecoin API token in environment variables")
            return True
        
        # Try to get stored credentials from credential manager
        try:
            cred_manager = CredentialManager()
            filecoin_creds = cred_manager.get_filecoin_credentials("default")
            
            if filecoin_creds and filecoin_creds.get("api_key"):
                logger.info("Found Filecoin credentials in credential store")
                
                # Set as environment variable for other components
                os.environ["LOTUS_API_TOKEN"] = filecoin_creds["api_key"]
                
                return True
        except Exception as e:
            logger.debug(f"Error checking credential manager: {e}")
        
        # Check for token file in default location
        lotus_path = os.environ.get("LOTUS_PATH", os.path.expanduser("~/.lotus"))
        token_path = os.path.join(lotus_path, "token")
        
        if os.path.exists(token_path):
            try:
                with open(token_path, 'r') as f:
                    token = f.read().strip()
                    if token:
                        logger.info(f"Found Lotus API token in {token_path}")
                        
                        # Set as environment variable for other components
                        os.environ["LOTUS_API_TOKEN"] = token
                        
                        return True
            except Exception as e:
                logger.debug(f"Error reading token file: {e}")
                
        # No credentials found in any location
        logger.warning("No Filecoin credentials found in any location")
        return False
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
    
    # Track daemon startup for cleanup
    daemon_started = False
    daemon_instance = None
    test_file_path = None
    
    # Get command line arguments
    import sys
    args = None
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--force-mock", action="store_true")
        parser.add_argument("--skip-daemon-stop", action="store_true")
        args, _ = parser.parse_known_args()
    
    try:
        # Check for force mock mode from command line
        if args and args.force_mock:
            logger.info("Forced mock mode requested via command line")
            real_mode = False
            has_credentials = False
        else:
            # Install Lotus binary if needed
            lotus_installed = install_lotus_binary()
            
            # Check if we need to use mock mode
            real_mode = False
            if lotus_installed:
                # Ensure Lotus daemon is running
                daemon_running = ensure_lotus_daemon_running()
                if daemon_running:
                    daemon_started = True
                    # Create daemon instance for later cleanup
                    daemon_instance = lotus_daemon()
                    
                    # Check for credentials
                    has_credentials = check_api_credentials()
                    if has_credentials:
                        real_mode = True
                        logger.info("Using REAL MODE with actual Lotus daemon")
                    else:
                        logger.info("Lotus daemon is running but no credentials found, using MOCK MODE")
                else:
                    logger.info("Lotus daemon could not be started, using MOCK MODE")
                    has_credentials = False
            else:
                logger.info("Lotus binary could not be installed, using MOCK MODE")
                has_credentials = False
                
        # Initialize metadata with defaults or environment variables
        metadata = {
            "api_url": os.environ.get("LOTUS_API_URL", "http://localhost:1234/rpc/v0"),
            "token": os.environ.get("LOTUS_API_TOKEN", ""),
            "lotus_path": os.environ.get("LOTUS_PATH", "/tmp/lotus"),
            "mock_mode": not real_mode
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
        
        # Initialize the models and controller
        kit = ipfs_kit(metadata={"role": "leecher"})
        ipfs_model = IPFSModel(ipfs_kit_instance=kit)
        logger.info("Initialized IPFS model")
        
        # Add test content to IPFS to get a real CID
        add_result = ipfs_model.add_content(test_data)
        
        if add_result.get("success", False):
            test_ipfs_cid = add_result["cid"]
            logger.info(f"Added test content to IPFS with CID: {test_ipfs_cid}")
        else:
            logger.warning("Failed to add test content to IPFS")
            test_ipfs_cid = "QmTest123456789"  # Fallback mock CID
        
        # Initialize lotus_kit and FilecoinModel
        lotus = lotus_kit(metadata=metadata)
        logger.info(f"Initialized lotus_kit (mock_mode={metadata['mock_mode']})")
        
        filecoin_model = FilecoinModel(lotus_kit_instance=lotus, ipfs_model=ipfs_model)
        logger.info("Initialized FilecoinModel with IPFS model")
        
        # Create the controller
        controller = FilecoinController(filecoin_model)
        logger.info("Initialized FilecoinController")
        
        # Run tests on controller methods
        results = {}
        
        # Run all tests
        async def run_individual_tests():
            # Dictionary to store test results
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
            if test_ipfs_cid and test_wallet and test_miner:
                logger.info(f"Testing IPFS to Filecoin transfer...")
                try:
                    ipfs_to_filecoin_request = IPFSToFilecoinRequest(
                        cid=test_ipfs_cid,
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
                    if result.get("success") and result.get("filecoin_cid"):
                        filecoin_test_cid = result["filecoin_cid"]
                    else:
                        filecoin_test_cid = test_ipfs_cid  # Fallback to test IPFS CID
                except Exception as e:
                    results["ipfs_to_filecoin"] = {
                        "success": False,
                        "error": str(e)
                    }
                    logger.error(f"Error in IPFS to Filecoin transfer: {e}")
                    filecoin_test_cid = test_ipfs_cid  # Fallback to test IPFS CID
            else:
                filecoin_test_cid = test_ipfs_cid  # Fallback to test IPFS CID
            
            # Test 12: Filecoin to IPFS (if we have CID)
            if filecoin_test_cid:
                logger.info(f"Testing Filecoin to IPFS transfer...")
                try:
                    filecoin_to_ipfs_request = FilecoinToIPFSRequest(
                        data_cid=filecoin_test_cid,
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
            
            return results
            
        # Run all the tests
        results = await run_individual_tests()
        
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
        print("FILECOIN CONTROLLER TEST SUMMARY (ENHANCED)")
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
        with open("filecoin_controller_enhanced_test_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Test results saved to filecoin_controller_enhanced_test_results.json")
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Unexpected error: {e}")
    finally:
        # Clean up test file
        if 'test_file_path' in locals() and os.path.exists(test_file_path):
            os.unlink(test_file_path)
            logger.info(f"Removed test file {test_file_path}")
            
        # Stop the Lotus daemon if we started it and not skipping daemon stop
        if daemon_started and daemon_instance:
            # Check for skip-daemon-stop flag
            import sys
            args = None
            if len(sys.argv) > 1:
                import argparse
                parser = argparse.ArgumentParser()
                parser.add_argument("--skip-daemon-stop", action="store_true")
                args, _ = parser.parse_known_args()
                
            if args and args.skip_daemon_stop:
                logger.info("Skipping Lotus daemon shutdown as requested")
            else:
                logger.info("Stopping Lotus daemon...")
                try:
                    stop_result = daemon_instance.daemon_stop()
                    if stop_result.get("success", False):
                        logger.info("Successfully stopped Lotus daemon")
                    else:
                        logger.warning(f"Failed to stop Lotus daemon: {stop_result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Error stopping Lotus daemon: {e}")

async def main():
    """Main function."""
    await run_tests()

if __name__ == "__main__":
    # Process command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Test FilecoinController with automatic daemon management.")
    parser.add_argument("--force-mock", action="store_true", help="Force mock mode even if daemon available")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--lotus-path", help="Custom Lotus path")
    parser.add_argument("--api-token", help="Custom API token")
    parser.add_argument("--skip-daemon-stop", action="store_true", help="Don't stop daemon after tests")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        # Set root logger to debug as well
        logging.getLogger().setLevel(logging.DEBUG)
        
    # Set custom Lotus path if provided
    if args.lotus_path:
        os.environ["LOTUS_PATH"] = args.lotus_path
        logger.info(f"Using custom Lotus path: {args.lotus_path}")
        
    # Set custom API token if provided
    if args.api_token:
        os.environ["LOTUS_API_TOKEN"] = args.api_token
        logger.info("Using custom API token from command line")
    
    # Run the tests
    import asyncio
    asyncio.run(main())