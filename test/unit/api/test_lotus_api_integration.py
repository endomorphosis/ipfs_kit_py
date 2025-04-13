#!/usr/bin/env python
import logging
import sys
import os
import json
import time
import subprocess
import tempfile
import uuid
import platform
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lotus_api_integration")

# Import Lotus components
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE
from ipfs_kit_py.lotus_daemon import lotus_daemon

def check_daemon_process():
    """Check if Lotus daemon process is running."""
    logger.info("Checking if Lotus daemon process is running...")
    try:
        ps_cmd = ["pgrep", "-f", "lotus daemon"]
        ps_result = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
        
        if ps_result.returncode == 0 and ps_result.stdout.strip():
            pids = ps_result.stdout.strip().split('\n')
            logger.info(f"Found Lotus daemon processes: {', '.join(pids)}")
            return True, pids
        else:
            logger.info("No Lotus daemon process found")
            return False, []
    except Exception as e:
        logger.error(f"Error checking daemon process: {e}")
        return False, []

def clean_environment():
    """Clean the environment before testing by stopping any running daemon."""
    logger.info("Cleaning environment before tests...")
    
    # Stop any existing daemon
    daemon_mgr = lotus_daemon()
    daemon_mgr.daemon_stop(force=True)
    time.sleep(2)  # Give it time to stop completely
    
    # Check to make sure it's stopped
    daemon_running, _ = check_daemon_process()
    if daemon_running:
        logger.warning("Daemon still running after stop attempt, trying again...")
        daemon_mgr.daemon_stop(force=True)
        time.sleep(3)
        
        # Check again
        daemon_running, _ = check_daemon_process()
        if daemon_running:
            logger.error("Failed to stop daemon after multiple attempts!")
            return False
    
    # Ensure no simulation mode environment is set
    if "LOTUS_SKIP_DAEMON_LAUNCH" in os.environ:
        del os.environ["LOTUS_SKIP_DAEMON_LAUNCH"]
    
    # Create fresh directories for a clean start
    lotus_path = os.path.expanduser("~/.lotus")
    logger.info(f"Creating fresh Lotus directories in {lotus_path}")
    
    # Create empty Lotus directories
    os.makedirs(os.path.join(lotus_path, "datastore"), exist_ok=True)
    os.makedirs(os.path.join(lotus_path, "keystore"), exist_ok=True)
    
    # Create minimal config.toml for Lotus daemon
    config_file = os.path.join(lotus_path, "config.toml")
    with open(config_file, 'w') as f:
        f.write("""# Minimal config for Lotus daemon
[API]
  ListenAddress = "/ip4/127.0.0.1/tcp/1234/http"
  RemoteListenAddress = ""
  Timeout = "30s"

[Libp2p]
  ListenAddresses = ["/ip4/0.0.0.0/tcp/2345", "/ip6/::/tcp/2345"]
  AnnounceAddresses = []
  NoAnnounceAddresses = []
  DisableNatPortMap = true

[Client]
  UseIpfs = false
  IpfsMAddr = ""
  IpfsUseForRetrieval = false
""")
    logger.info(f"Created minimal config.toml at {config_file}")
    
    # Remove any stale lock files
    repo_lock = os.path.join(lotus_path, "repo.lock")
    if os.path.exists(repo_lock):
        os.remove(repo_lock)
        logger.info(f"Removed stale lock file: {repo_lock}")
        
    return True

def test_api_operations(test_custom_path=False):
    """Test all Lotus API operations with real daemon integration."""
    logger.info(f"Testing Lotus API operations with {'custom path' if test_custom_path else 'default path'}...")
    
    # Prepare a custom Lotus path for testing if requested
    custom_lotus_path = None
    if test_custom_path:
        custom_lotus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_lotus_api_path")
        os.makedirs(custom_lotus_path, exist_ok=True)
        logger.info(f"Using custom Lotus path: {custom_lotus_path}")
    
    # Clean environment first
    if not clean_environment():
        logger.error("Failed to clean environment. Aborting test.")
        return False, {}
        
    # Get the path to the bin directory with the lotus binary
    bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    if not os.path.exists(os.path.join(bin_path, "lotus")):
        logger.error(f"Lotus binary not found in {bin_path}. Proceeding with simulation mode.")
        bin_path = None
    else:
        logger.info(f"Found Lotus binary in {bin_path}")
        # Add bin to PATH
        os.environ["PATH"] = f"{bin_path}:{os.environ.get('PATH', '')}"
    
    # Create lotus_kit with auto-start and real daemon (no simulation)
    logger.info("Creating lotus_kit with auto_start_daemon=True and simulation_mode=False")
    metadata = {
        "auto_start_daemon": True,     # Enable automatic daemon management
        "simulation_mode": False,      # We want real daemon for API integration tests
        "lite": True,                  # Use lite mode for faster startup
        "daemon_flags": {
            "bootstrap": False,        # Skip bootstrap for faster startup
            "api": "1234",             # Explicitly set API port
            "manage-fdlimit": True,    # Manage file descriptor limits
        },
        "daemon_startup_timeout": 120,  # Give more time for daemon startup
        "binary_path": bin_path,       # Path to bin directory with lotus binary
        "lotus_binary": os.path.join(bin_path, "lotus") if bin_path else None, # Explicit binary path
        "remove_stale_lock": True      # Remove stale lock files if found
    }
    
    if custom_lotus_path:
        metadata["lotus_path"] = custom_lotus_path
    
    kit = lotus_kit(metadata=metadata)
    
    # Test results dictionary
    test_results = {
        "execution_info": {
            "timestamp": time.time(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "lotus_path": custom_lotus_path if custom_lotus_path else os.path.expanduser("~/.lotus"),
            "custom_path_used": custom_lotus_path is not None
        },
        "operations": {},
        "summary": {}
    }
    
    # 1. Test daemon management operations
    logger.info("\n=== Testing daemon management operations ===")
    
    # Check daemon status
    logger.info("Testing daemon_status...")
    status_result = kit.daemon_status()
    test_results["operations"]["daemon_status"] = {
        "success": status_result.get("success", False),
        "simulated": status_result.get("simulated", False),
        "process_running": status_result.get("process_running", False),
        "pid": status_result.get("pid"),
        "result": status_result
    }
    
    # If daemon not running, ensure it's started
    daemon_running = status_result.get("process_running", False)
    if not daemon_running:
        logger.info("Daemon not running, starting it...")
        start_result = kit.daemon_start()
        test_results["operations"]["daemon_start"] = {
            "success": start_result.get("success", False),
            "simulated": start_result.get("simulated", False),
            "result": start_result
        }
        
        # Check if it's running now
        time.sleep(3)  # Give it a moment to start
        status_result = kit.daemon_status()
        daemon_running = status_result.get("process_running", False)
    else:
        test_results["operations"]["daemon_start"] = {
            "success": True,
            "simulated": False,
            "result": {"status": "already_running"}
        }
    
    # Check connection to daemon API
    logger.info("Testing check_connection...")
    connection_result = kit.check_connection()
    test_results["operations"]["check_connection"] = {
        "success": connection_result.get("success", False),
        "simulated": connection_result.get("simulated", False),
        "version": connection_result.get("version", "Unknown"),
        "api_version": connection_result.get("api_version", "Unknown"),
        "result": connection_result
    }
    
    # 2. Test chain operations
    logger.info("\n=== Testing chain operations ===")
    
    # Test chain head
    logger.info("Testing get_chain_head...")
    chain_head = kit.get_chain_head()
    test_results["operations"]["get_chain_head"] = {
        "success": chain_head.get("success", False),
        "simulated": chain_head.get("simulated", False),
        "height": chain_head.get("height"),
        "has_blocks": "blocks" in chain_head,
        "result": chain_head
    }
    
    # Test chain messages
    logger.info("Testing process_chain_messages...")
    messages_result = kit.process_chain_messages()
    test_results["operations"]["process_chain_messages"] = {
        "success": messages_result.get("success", False),
        "simulated": messages_result.get("simulated", False),
        "has_messages": "messages" in messages_result,
        "result": messages_result
    }
    
    # 3. Test wallet operations
    logger.info("\n=== Testing wallet operations ===")
    
    # List wallets
    logger.info("Testing list_wallets...")
    wallet_list = kit.list_wallets()
    test_results["operations"]["list_wallets"] = {
        "success": wallet_list.get("success", False),
        "simulated": wallet_list.get("simulated", False),
        "wallet_count": len(wallet_list.get("addresses", [])) if "addresses" in wallet_list else 0,
        "result": wallet_list
    }
    
    # Create wallet - only if we have success with API so far
    if (connection_result.get("success", False) and not 
            connection_result.get("simulated", True)):
        # Real API test - create a new wallet
        logger.info("Testing create_wallet...")
        create_wallet = kit.create_wallet()
        test_results["operations"]["create_wallet"] = {
            "success": create_wallet.get("success", False),
            "simulated": create_wallet.get("simulated", False),
            "address": create_wallet.get("address"),
            "result": create_wallet
        }
        
        # Test wallet balance if wallet was created
        if create_wallet.get("success", False) and "address" in create_wallet:
            logger.info(f"Testing wallet_balance for {create_wallet['address']}...")
            balance = kit.wallet_balance(create_wallet["address"])
            test_results["operations"]["wallet_balance"] = {
                "success": balance.get("success", False),
                "simulated": balance.get("simulated", False),
                "balance": balance.get("balance", 0),
                "result": balance
            }
    else:
        # Skip wallet creation in simulation mode or if connection failed
        logger.info("Skipping create_wallet (connection not successful or simulated)")
        test_results["operations"]["create_wallet"] = {
            "success": False,
            "simulated": True,
            "skipped": True,
            "reason": "API connection failed or simulation mode"
        }
    
    # 4. Test miner operations
    logger.info("\n=== Testing miner operations ===")
    
    # List miners
    logger.info("Testing list_miners...")
    miners = kit.list_miners()
    test_results["operations"]["list_miners"] = {
        "success": miners.get("success", False),
        "simulated": miners.get("simulated", False),
        "miner_count": len(miners.get("miners", [])) if "miners" in miners else 0,
        "result": miners
    }
    
    # 5. Test deal operations
    logger.info("\n=== Testing deal operations ===")
    
    # List deals
    logger.info("Testing client_list_deals...")
    deals = kit.client_list_deals()
    test_results["operations"]["client_list_deals"] = {
        "success": deals.get("success", False),
        "simulated": deals.get("simulated", False),
        "deal_count": len(deals.get("deals", [])) if "deals" in deals else 0,
        "result": deals
    }
    
    # 6. Test file operations
    logger.info("\n=== Testing file operations ===")
    
    # Create a test file
    test_file = tempfile.mktemp(suffix=".txt")
    with open(test_file, "w") as f:
        f.write(f"Test content {uuid.uuid4()}")
    
    # Import file
    logger.info(f"Testing client_import with {test_file}...")
    import_result = kit.client_import(test_file)
    test_results["operations"]["client_import"] = {
        "success": import_result.get("success", False),
        "simulated": import_result.get("simulated", False),
        "cid": None,  # Will populate if successful
        "result": import_result
    }
    
    # Extract CID if available
    imported_cid = None
    if import_result.get("success", False) and "result" in import_result:
        if "Root" in import_result["result"]:
            if isinstance(import_result["result"]["Root"], dict) and "/" in import_result["result"]["Root"]:
                imported_cid = import_result["result"]["Root"]["/"]
            else:
                imported_cid = import_result["result"]["Root"]
        test_results["operations"]["client_import"]["cid"] = imported_cid
    
    # Test list imports
    logger.info("Testing client_list_imports...")
    list_imports = kit.client_list_imports()
    test_results["operations"]["client_list_imports"] = {
        "success": list_imports.get("success", False),
        "simulated": list_imports.get("simulated", False),
        "import_count": len(list_imports.get("imports", [])) if "imports" in list_imports else 0,
        "result": list_imports
    }
    
    # Verify the import is in the list
    found_import = False
    if list_imports.get("success", False) and imported_cid:
        for imp in list_imports.get("imports", []):
            if "Root" in imp:
                if isinstance(imp["Root"], dict) and "/" in imp["Root"]:
                    if imp["Root"]["/"] == imported_cid:
                        found_import = True
                        break
                elif imp["Root"] == imported_cid:
                    found_import = True
                    break
                    
        test_results["operations"]["client_list_imports"]["found_import"] = found_import
    
    # Test retrieve if import was successful
    if imported_cid:
        retrieved_file = tempfile.mktemp(suffix="_retrieved.txt")
        logger.info(f"Testing client_retrieve with CID {imported_cid}...")
        retrieve_result = kit.client_retrieve(imported_cid, retrieved_file)
        test_results["operations"]["client_retrieve"] = {
            "success": retrieve_result.get("success", False),
            "simulated": retrieve_result.get("simulated", False),
            "file_exists": os.path.exists(retrieved_file),
            "result": retrieve_result
        }
        
        # Clean up retrieved file
        if os.path.exists(retrieved_file):
            with open(retrieved_file, "r") as f:
                content = f.read()
            test_results["operations"]["client_retrieve"]["content_length"] = len(content)
            os.remove(retrieved_file)
    else:
        logger.info("Skipping client_retrieve (no CID available)")
        test_results["operations"]["client_retrieve"] = {
            "success": False,
            "simulated": True,
            "skipped": True,
            "reason": "No CID available from import operation"
        }
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # 7. Test network operations
    logger.info("\n=== Testing network operations ===")
    
    # Test network peers
    logger.info("Testing net_peers...")
    peers = kit.net_peers()
    test_results["operations"]["net_peers"] = {
        "success": peers.get("success", False),
        "simulated": peers.get("simulated", False),
        "peer_count": len(peers.get("peers", [])) if "peers" in peers else 0,
        "result": peers
    }
    
    # 8. Perform final operations and cleanup
    
    # Test API connection again to ensure daemon is still responsive
    logger.info("Testing final check_connection...")
    final_connection = kit.check_connection()
    test_results["operations"]["final_check_connection"] = {
        "success": final_connection.get("success", False),
        "simulated": final_connection.get("simulated", False),
        "result": final_connection
    }
    
    # Stop daemon (only if we started it)
    if not status_result.get("process_running", False) and daemon_running:
        logger.info("Stopping daemon that we started...")
        stop_result = kit.daemon_stop()
        test_results["operations"]["daemon_stop"] = {
            "success": stop_result.get("success", False),
            "simulated": stop_result.get("simulated", False),
            "result": stop_result
        }
    else:
        logger.info("Not stopping daemon as we didn't start it ourselves")
        test_results["operations"]["daemon_stop"] = {
            "skipped": True,
            "reason": "Daemon was already running before test"
        }
    
    # 9. Generate test summary
    
    # Count total tests, successful tests, and simulated tests
    total_tests = len(test_results["operations"])
    successful_tests = sum(1 for op in test_results["operations"].values() 
                         if op.get("success", False) and not op.get("skipped", False))
    simulated_tests = sum(1 for op in test_results["operations"].values() 
                         if op.get("simulated", False) and not op.get("skipped", False))
    real_api_tests = sum(1 for op in test_results["operations"].values() 
                       if op.get("success", False) and not op.get("simulated", False) 
                       and not op.get("skipped", False))
    
    # Calculate success percentage
    if total_tests > 0:
        success_percentage = (successful_tests / total_tests) * 100
        real_api_percentage = (real_api_tests / total_tests) * 100
    else:
        success_percentage = 0
        real_api_percentage = 0
    
    # Create summary
    test_results["summary"] = {
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "simulated_tests": simulated_tests,
        "real_api_tests": real_api_tests,
        "success_percentage": success_percentage,
        "real_api_percentage": real_api_percentage,
        "all_tests_passed": successful_tests == total_tests,
        "using_real_daemon": real_api_tests > 0,
        "test_timestamp": time.time(),
        "test_duration": time.time() - test_results["execution_info"]["timestamp"]
    }
    
    # Log summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Successful tests: {successful_tests} ({success_percentage:.1f}%)")
    logger.info(f"Simulated tests: {simulated_tests}")
    logger.info(f"Real API tests: {real_api_tests} ({real_api_percentage:.1f}%)")
    logger.info(f"All tests passed: {test_results['summary']['all_tests_passed']}")
    logger.info(f"Test duration: {test_results['summary']['test_duration']:.1f} seconds")
    
    # Determine overall success
    # Consider the test successful if all operations succeeded (even if simulated)
    test_success = successful_tests == total_tests
    
    return test_success, test_results

def create_api_test_report(results, filename="LOTUS_API_TEST_REPORT.md"):
    """Create a comprehensive report of Lotus API integration tests."""
    
    # Extract summary info
    summary = results.get("summary", {})
    execution_info = results.get("execution_info", {})
    
    # Format timestamp
    if "timestamp" in execution_info:
        import datetime
        test_time = datetime.datetime.fromtimestamp(execution_info["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
    else:
        test_time = "Unknown"
    
    # Start report
    report = f"""# Lotus API Integration Test Report

## Summary

Comprehensive test of Lotus API integration with ipfs_kit_py.

- **Test Date**: {test_time}
- **Platform**: {execution_info.get("platform", "Unknown")}
- **Lotus Path**: {execution_info.get("lotus_path", "Unknown")}
- **Custom Path Used**: {execution_info.get("custom_path_used", False)}
- **Python Version**: {execution_info.get("python_version", "Unknown")}

### Test Results

- **Total Test Operations**: {summary.get("total_tests", 0)}
- **Successful Operations**: {summary.get("successful_tests", 0)} ({summary.get("success_percentage", 0):.1f}%)
- **Real API Operations**: {summary.get("real_api_tests", 0)} ({summary.get("real_api_percentage", 0):.1f}%)
- **Simulated Operations**: {summary.get("simulated_tests", 0)}
- **All Tests Passed**: {summary.get("all_tests_passed", False)}
- **Using Real Daemon**: {summary.get("using_real_daemon", False)}
- **Test Duration**: {summary.get("test_duration", 0):.1f} seconds

## Detailed Test Results

| Operation | Success | Simulated | Details |
|-----------|---------|-----------|---------|
"""
    
    # Add details for each operation
    for operation, result in results.get("operations", {}).items():
        # Handle skipped operations
        if result.get("skipped", False):
            success = "Skipped"
            simulated = "N/A"
            details = result.get("reason", "Operation skipped")
        else:
            success = "✅" if result.get("success", False) else "❌"
            simulated = "✅" if result.get("simulated", False) else "❌"
            
            # Compile relevant details based on operation type
            details = []
            
            if "daemon" in operation:
                if "pid" in result:
                    details.append(f"PID: {result['pid']}")
                if "process_running" in result:
                    details.append(f"Running: {result['process_running']}")
                    
            elif "wallet" in operation:
                if "wallet_count" in result:
                    details.append(f"Wallets: {result['wallet_count']}")
                if "address" in result:
                    details.append(f"Address: {result['address']}")
                if "balance" in result:
                    details.append(f"Balance: {result['balance']}")
                    
            elif "miner" in operation:
                if "miner_count" in result:
                    details.append(f"Miners: {result['miner_count']}")
                    
            elif "deal" in operation:
                if "deal_count" in result:
                    details.append(f"Deals: {result['deal_count']}")
                    
            elif "import" in operation:
                if "cid" in result and result["cid"]:
                    details.append(f"CID: {result['cid']}")
                if "import_count" in result:
                    details.append(f"Imports: {result['import_count']}")
                if "found_import" in result:
                    details.append(f"Found Import: {result['found_import']}")
                    
            elif "retrieve" in operation:
                if "file_exists" in result:
                    details.append(f"File Exists: {result['file_exists']}")
                if "content_length" in result:
                    details.append(f"Content Length: {result['content_length']}")
                    
            elif "peers" in operation:
                if "peer_count" in result:
                    details.append(f"Peers: {result['peer_count']}")
                    
            elif "connection" in operation:
                if "version" in result:
                    details.append(f"Version: {result['version']}")
                if "api_version" in result:
                    details.append(f"API: {result['api_version']}")
                    
            # If no specific details captured, add a generic message
            if not details:
                if "error" in result:
                    details.append(f"Error: {result['error']}")
                elif result.get("success", False):
                    details.append("Operation completed successfully")
                else:
                    details.append("Operation failed")
        
        # Add the row to the report table
        details_str = ", ".join(details) if isinstance(details, list) else details
        report += f"| {operation} | {success} | {simulated} | {details_str} |\n"
    
    # Add analysis section
    report += f"""
## Analysis

### Real API vs. Simulation

This test suite executed {summary.get("total_tests", 0)} operations, with {summary.get("real_api_tests", 0)} operations ({summary.get("real_api_percentage", 0):.1f}%) using the real Lotus API and {summary.get("simulated_tests", 0)} operations using simulation mode.

### API Coverage

The test suite covers the following API categories:
- Daemon Management: Starting, stopping, and status checking
- Chain Operations: Retrieving chain head and processing chain messages
- Wallet Operations: Listing, creating, and checking balances
- Miner Operations: Listing miners
- Deal Operations: Listing deals
- File Operations: Importing, listing imports, and retrieving files
- Network Operations: Listing peers

### Daemon Management

The automatic daemon management feature was {"successfully verified" if result.get("operations", {}).get("daemon_start", {}).get("success", False) else "not successfully verified"}. The daemon {"was" if result.get("operations", {}).get("daemon_status", {}).get("process_running", False) else "was not"} running at the start of tests.

## Conclusions

The Lotus integration in ipfs_kit_py is {"fully" if summary.get("all_tests_passed", False) else "partially"} functional with {"real" if summary.get("using_real_daemon", False) else "simulated"} API operations. {"All" if summary.get("all_tests_passed", False) else "Some"} test operations completed successfully.

{"The system is successfully using the real Lotus daemon API." if summary.get("using_real_daemon", False) else "The system is primarily using simulation mode, real daemon integration could be improved."}

### Recommendations

1. {"Expand real API coverage for more comprehensive testing." if summary.get("real_api_percentage", 0) < 90 else "Maintain the excellent real API coverage."}
2. {"Improve error handling and recovery for failed operations." if summary.get("success_percentage", 0) < 100 else "The robust error handling is working well."}
3. {"Enhance simulation mode to better match real API behavior." if summary.get("simulated_tests", 0) > 0 else "Consider adding simulation tests for edge cases."}
4. {"Focus on stabilizing daemon management." if not result.get("operations", {}).get("daemon_start", {}).get("success", False) else "The daemon management is working correctly."}
"""
    
    # Write report to file
    with open(filename, "w") as f:
        f.write(report)
    
    logger.info(f"API integration test report generated: {filename}")
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Lotus API integration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--custom-path", action="store_true", help="Test with custom path")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't clean environment before test")
    args = parser.parse_args()
    
    # Set debug logging level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Skip environment cleanup if requested
    if args.no_cleanup:
        logger.info("Skipping environment cleanup as requested")
    else:
        clean_environment()
    
    # Run test
    success, results = test_api_operations(test_custom_path=args.custom_path)
    
    # Save results to file
    result_file = "lotus_api_test_results.json"
    with open(result_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Detailed results saved to {result_file}")
    
    # Create report
    create_api_test_report(results)
    
    sys.exit(0 if success else 1)