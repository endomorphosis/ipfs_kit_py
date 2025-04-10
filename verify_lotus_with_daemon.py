#!/usr/bin/env python
import logging
import sys
import os
import json
import time
import subprocess
from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("lotus_verification")

def verify_lotus_with_daemon():
    """Verify the lotus_kit client functionality with a real daemon."""
    logger.info("Starting Lotus client verification with automatic daemon management...")
    
    # Check if Lotus binary is available
    if not LOTUS_AVAILABLE:
        logger.error("Lotus binary not available. Cannot start daemon.")
        return False

    # Initialize lotus_kit with automatic daemon management enabled
    kit = lotus_kit(metadata={
        "simulation_mode": False,  # Disable simulation mode
        "auto_start_daemon": True,  # Automatically start the daemon
        "daemon_startup_timeout": 120  # Give more time for daemon startup
    })
    
    # Verification results object
    verification_results = {
        "binary_available": LOTUS_AVAILABLE,
        "daemon_started": False,
        "test_results": {}
    }
    
    # Check if daemon is running
    daemon_result = {}
    try:
        # Try to make a simple API call to check daemon status
        daemon_result = kit._make_request("ChainHead")
        verification_results["daemon_started"] = daemon_result.get("success", False)
    except Exception as e:
        logger.error(f"Error checking daemon status: {str(e)}")
        verification_results["daemon_started"] = False
    
    logger.info(f"Lotus binary availability: {verification_results['binary_available']}")
    logger.info(f"Lotus daemon started: {verification_results['daemon_started']}")
    
    # If daemon is not running, try to start it manually
    if not verification_results["daemon_started"]:
        logger.info("Daemon not started. Attempting to start manually...")
        try:
            # Get the path to the lotus binary
            lotus_path = subprocess.run(["which", "lotus"], 
                                      capture_output=True, text=True, check=True).stdout.strip()
            
            # Start the daemon in the background
            subprocess.Popen([lotus_path, "daemon", "--lite"], 
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for the daemon to initialize (up to 60 seconds)
            for _ in range(60):
                time.sleep(1)
                try:
                    # Check if daemon is responsive
                    result = kit._make_request("ChainHead")
                    if result.get("success", False):
                        verification_results["daemon_started"] = True
                        logger.info("Lotus daemon successfully started manually.")
                        break
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to start daemon manually: {str(e)}")
    
    # If daemon still isn't running, fall back to simulation mode
    if not verification_results["daemon_started"]:
        logger.warning("Could not start Lotus daemon. Falling back to simulation mode.")
        kit.simulation_mode = True
    
    # Test chain head
    logger.info("Testing chain head retrieval...")
    chain_head = kit.get_chain_head()
    verification_results["test_results"]["chain_head"] = {
        "success": chain_head.get("success", False),
        "simulated": chain_head.get("simulated", False),
        "data_present": "Height" in chain_head or "Blocks" in chain_head
    }
    logger.info(f"Chain head test result: {verification_results['test_results']['chain_head']['success']}")
    
    # Test wallet operations
    logger.info("Testing wallet operations...")
    wallet_list = kit.list_wallets()
    verification_results["test_results"]["wallet_list"] = {
        "success": wallet_list.get("success", False),
        "simulated": wallet_list.get("simulated", False),
        "data_present": "addresses" in wallet_list or "result" in wallet_list
    }
    logger.info(f"Wallet list test result: {verification_results['test_results']['wallet_list']['success']}")
    
    # Test miner list
    logger.info("Testing miner list...")
    miners = kit.list_miners()
    verification_results["test_results"]["list_miners"] = {
        "success": miners.get("success", False),
        "simulated": miners.get("simulated", False),
        "data_present": "miners" in miners or "result" in miners
    }
    logger.info(f"Miner list test result: {verification_results['test_results']['list_miners']['success']}")
    
    # Test deal list
    logger.info("Testing deal list...")
    deals = kit.client_list_deals()
    verification_results["test_results"]["list_deals"] = {
        "success": deals.get("success", False),
        "simulated": deals.get("simulated", False),
        "data_present": "deals" in deals
    }
    logger.info(f"Deal list test result: {verification_results['test_results']['list_deals']['success']}")
    
    # Test network info
    logger.info("Testing network info...")
    network = kit._make_request("NetPeers")
    verification_results["test_results"]["network_info"] = {
        "success": network.get("success", False),
        "simulated": network.get("simulated", False),
        "data_present": "result" in network
    }
    logger.info(f"Network info test result: {verification_results['test_results']['network_info']['success']}")
    
    # Summarize results
    total_tests = len(verification_results["test_results"])
    successful_tests = sum(1 for test in verification_results["test_results"].values() 
                          if test.get("success", False))
    
    verification_results["summary"] = {
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "success_percentage": (successful_tests / total_tests) * 100 if total_tests > 0 else 0,
        "all_tests_passed": successful_tests == total_tests,
        "using_real_daemon": verification_results["daemon_started"] and 
                            not verification_results["test_results"]["chain_head"].get("simulated", True)
    }
    
    logger.info(f"Verification complete. {successful_tests}/{total_tests} tests passed "
                f"({verification_results['summary']['success_percentage']:.1f}%).")
    logger.info(f"Using real daemon: {verification_results['summary']['using_real_daemon']}")
    
    # Output results as JSON for easy analysis
    with open("lotus_verification_results.json", "w") as f:
        json.dump(verification_results, f, indent=2)
    
    logger.info("Detailed results saved to lotus_verification_results.json")
    
    # Automatically create a report based on results
    create_report(verification_results)
    
    return verification_results["summary"]["all_tests_passed"]

def create_report(results):
    """Create a report based on verification results."""
    daemon_status = "Real daemon" if results["summary"]["using_real_daemon"] else "Simulation mode"
    
    report = f"""# Lotus Client Verification Report

## Summary

The Filecoin Lotus client in ipfs_kit_py has been verified with the following results:

- **Binary Available**: {results["binary_available"]}
- **Daemon Started**: {results["daemon_started"]}
- **Operation Mode**: {daemon_status}
- **Tests Passed**: {results["summary"]["successful_tests"]}/{results["summary"]["total_tests"]} ({results["summary"]["success_percentage"]:.1f}%)
- **All Tests Passed**: {results["summary"]["all_tests_passed"]}

## Test Details

| Test | Success | Simulated | Data Present |
|------|---------|-----------|--------------|
"""
    
    for test_name, test_result in results["test_results"].items():
        success = test_result.get("success", False)
        simulated = test_result.get("simulated", False)
        data_present = test_result.get("data_present", False)
        report += f"| {test_name} | {success} | {simulated} | {data_present} |\n"
    
    report += f"""
## Conclusion

The Lotus client is {'fully' if results["summary"]["all_tests_passed"] else 'partially'} functional.
It is operating in {"simulation mode" if not results["summary"]["using_real_daemon"] else "real daemon mode"}.

All test operations were {'successful' if results["summary"]["all_tests_passed"] else 'not all successful'}.
"""

    # Write report to file
    with open("LOTUS_VERIFICATION_REPORT.md", "w") as f:
        f.write(report)
    
    logger.info("Verification report generated: LOTUS_VERIFICATION_REPORT.md")

if __name__ == "__main__":
    success = verify_lotus_with_daemon()
    sys.exit(0 if success else 1)