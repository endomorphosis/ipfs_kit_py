#!/usr/bin/env python3
"""
Test script to verify Filecoin Lotus client functionality, attempting real daemon first.

This script attempts to:
1. Connect to a real Lotus daemon if available
2. Fall back to simulation mode if no daemon is available
3. Verify that all operations work correctly in both modes
"""

import logging
import os
import sys
import time
import subprocess
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_lotus_real_daemon")

def find_lotus_binary():
    """Find the lotus binary in common locations."""
    # Check project bin directory first
    project_root = os.path.dirname(os.path.abspath(__file__))
    project_bin = os.path.join(project_root, "bin", "lotus")
    if os.path.exists(project_bin) and os.access(project_bin, os.X_OK):
        return project_bin
        
    # Check if it's in PATH
    try:
        which_output = subprocess.check_output(["which", "lotus"], text=True).strip()
        if which_output and os.path.exists(which_output):
            return which_output
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
        
    return None

def check_daemon_running():
    """Check if a Lotus daemon is already running."""
    try:
        # Try to get the daemon ID
        result = subprocess.run(
            ["lotus", "net", "id"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse JSON response to get peer ID
            try:
                peer_data = json.loads(result.stdout)
                return True, peer_data
            except json.JSONDecodeError:
                return True, {"ID": result.stdout.strip()}
        else:
            return False, result.stderr.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, "Lotus command not found or failed"

def test_lotus_client():
    """Test the lotus_kit client with real daemon if possible, fallback to simulation."""
    # Import and initialize lotus_kit
    try:
        from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE
        
        # Check if Lotus binary is available
        lotus_bin = find_lotus_binary()
        logger.info(f"Lotus binary found: {lotus_bin is not None}")
        logger.info(f"LOTUS_AVAILABLE from module: {LOTUS_AVAILABLE}")
        
        # Check if daemon is running
        daemon_running, peer_info = check_daemon_running()
        logger.info(f"Lotus daemon running: {daemon_running}")
        if daemon_running:
            logger.info(f"Connected to daemon with peer ID: {peer_info}")
        
        # Initialize lotus_kit - try real daemon first
        kit = lotus_kit(metadata={
            "filecoin_simulation": True,  # Always enable simulation mode for fallback
            "auto_start_daemon": False    # Don't try to start daemon automatically
        })
        
        # Check if we're in simulation mode
        logger.info(f"Running in simulation mode: {kit.simulation_mode}")
        
        # Run a series of tests to verify functionality
        results = {}
        
        # Test 1: Chain head
        logger.info("Test 1: Chain head")
        chain_head = kit.get_chain_head()
        results["chain_head"] = {
            "success": chain_head.get("success", False),
            "simulated": chain_head.get("simulated", False),
            "error": chain_head.get("error", None)
        }
        logger.info(f"Chain head result: success={results['chain_head']['success']}, simulated={results['chain_head']['simulated']}")
        
        # Test 2: Wallet operations
        logger.info("Test 2: Wallet operations")
        wallet_list = kit.list_wallets()
        results["wallet_list"] = {
            "success": wallet_list.get("success", False),
            "simulated": wallet_list.get("simulated", False), 
            "error": wallet_list.get("error", None),
            "count": len(wallet_list.get("result", [])) if wallet_list.get("success", False) else 0
        }
        logger.info(f"Wallet list result: success={results['wallet_list']['success']}, simulated={results['wallet_list']['simulated']}, count={results['wallet_list']['count']}")
        
        # Test 3: Network information
        logger.info("Test 3: Network information")
        net_info = kit.net_info()
        results["net_info"] = {
            "success": net_info.get("success", False),
            "simulated": net_info.get("simulated", False),
            "error": net_info.get("error", None)
        }
        logger.info(f"Network info result: success={results['net_info']['success']}, simulated={results['net_info']['simulated']}")
        
        # Test 4: Deal listing
        logger.info("Test 4: Deal listing")
        deals = kit.client_list_deals()
        results["deals"] = {
            "success": deals.get("success", False),
            "simulated": deals.get("simulated", False),
            "error": deals.get("error", None),
            "count": len(deals.get("result", [])) if deals.get("success", False) else 0
        }
        logger.info(f"Deals result: success={results['deals']['success']}, simulated={results['deals']['simulated']}, count={results['deals']['count']}")
        
        # Test 5: Miner listing
        logger.info("Test 5: Miner listing")
        miners = kit.list_miners()
        results["miners"] = {
            "success": miners.get("success", False),
            "simulated": miners.get("simulated", False),
            "error": miners.get("error", None),
            "count": len(miners.get("result", [])) if miners.get("success", False) else 0
        }
        logger.info(f"Miners result: success={results['miners']['success']}, simulated={results['miners']['simulated']}, count={results['miners']['count']}")
        
        # Overall success - all operations should succeed, either with real daemon or simulation
        all_succeeded = all(result["success"] for result in results.values())
        simulated = any(result["simulated"] for result in results.values() if result["success"])
        
        # Determine real daemon success - if any operation succeeded and was NOT simulated
        real_daemon_success = any(
            result["success"] and not result.get("simulated", False) 
            for result in results.values()
        )
        
        results_summary = {
            "lotus_binary_available": lotus_bin is not None,
            "daemon_running": daemon_running,
            "simulation_mode": kit.simulation_mode,
            "all_operations_succeeded": all_succeeded,
            "real_daemon_success": real_daemon_success,
            "simulated_success": simulated,
            "detailed_results": results
        }
        
        return results_summary
    
    except ImportError as e:
        logger.error(f"Failed to import lotus_kit: {e}")
        return {"error": f"Import error: {e}"}
    except Exception as e:
        logger.error(f"Error testing lotus client: {e}")
        return {"error": f"Unexpected error: {e}"}

if __name__ == "__main__":
    print("=== Testing Lotus Client ===\n")
    
    results = test_lotus_client()
    
    print("\n=== Lotus Client Test Results ===")
    print(f"Lotus binary available: {results.get('lotus_binary_available', False)}")
    print(f"Lotus daemon running: {results.get('daemon_running', False)}")
    print(f"Client using simulation mode: {results.get('simulation_mode', True)}")
    print(f"All operations succeeded: {results.get('all_operations_succeeded', False)}")
    
    if results.get('real_daemon_success', False):
        print("\n✅ SUCCESS: Lotus client works with a real daemon!")
        print("Verified real (non-simulated) API operations.")
    elif results.get('simulated_success', False):
        print("\n✅ SUCCESS: Lotus client works in simulation mode!")
        print("Verified simulated API operations when real daemon is not available.")
    else:
        print("\n❌ FAILURE: Lotus client is not functioning correctly.")
        print("Neither real daemon nor simulation mode is working.")
    
    # Print detailed operation results
    print("\nDetailed Operation Results:")
    for op_name, op_result in results.get('detailed_results', {}).items():
        status = "✅" if op_result.get('success', False) else "❌"
        mode = "SIMULATED" if op_result.get('simulated', False) else "REAL"
        error = f" - Error: {op_result.get('error')}" if op_result.get('error') else ""
        count = f" - Count: {op_result.get('count')}" if 'count' in op_result else ""
        print(f"{status} {op_name}: {mode}{count}{error}")
    
    # Exit with appropriate status code
    if results.get('all_operations_succeeded', False):
        sys.exit(0)  # Success
    else:
        sys.exit(1)  # Failure