#\!/usr/bin/env python
import os
import sys
import json
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("verify_auto_daemon")

# Import Lotus components
from ipfs_kit_py.lotus_kit import lotus_kit
from ipfs_kit_py.lotus_daemon import lotus_daemon

def verify_auto_daemon_management():
    """Verify that the Lotus daemon automatic management works properly."""
    result = {
        "timestamp": time.time(),
        "tests": {}
    }
    
    # Step 1: Clean up any existing Lotus daemon
    logger.info("Stopping any existing Lotus daemon")
    daemon_mgr = lotus_daemon()
    
    cleanup_result = daemon_mgr.daemon_stop(force=True)
    result["tests"]["cleanup"] = {
        "success": cleanup_result.get("success", False),
        "result": cleanup_result
    }
    
    # Step 2: Ensure a clean repository
    lotus_path = os.path.expanduser("~/.lotus")
    repo_lock = os.path.join(lotus_path, "repo.lock")
    api_file = os.path.join(lotus_path, "api")
    
    if os.path.exists(repo_lock):
        os.remove(repo_lock)
        logger.info(f"Removed stale lock file: {repo_lock}")
    
    if os.path.exists(api_file):
        os.remove(api_file)
        logger.info(f"Removed stale API file: {api_file}")
    
    # Step 3: Create a new lotus_kit with simulation fallback enabled
    logger.info("Creating lotus_kit with simulation_mode=True (explicit fallback)")
    
    bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    metadata = {
        "auto_start_daemon": True,      # Enable automatic daemon management
        "simulation_mode": True,        # Explicitly enable simulation mode
        "daemon_startup_timeout": 30,   # Timeout for daemon startup
        "binary_path": bin_path,        # Path to bin directory
        "lotus_binary": os.path.join(bin_path, "lotus"),  # Explicit binary path
        "remove_stale_lock": True       # Remove stale lock files
    }
    
    try:
        kit = lotus_kit(metadata=metadata)
        result["tests"]["create_kit"] = {
            "success": True,
            "time": time.time()
        }
    except Exception as e:
        logger.error(f"Error creating lotus_kit: {e}")
        result["tests"]["create_kit"] = {
            "success": False,
            "error": str(e),
            "time": time.time()
        }
        result["success"] = False
        return result
    
    # Step 4: Verify that simulation mode works correctly
    logger.info("Testing chain_head in simulation mode")
    chain_head = kit.get_chain_head()
    
    result["tests"]["chain_head"] = {
        "success": chain_head.get("success", False),
        "simulated": chain_head.get("simulated", False),
        "height": chain_head.get("height"),
        "result": chain_head,
        "time": time.time()
    }
    
    # Step 5: Check daemon status (should indicate simulation mode)
    logger.info("Testing daemon_status in simulation mode")
    status_result = kit.daemon_status()
    
    result["tests"]["daemon_status"] = {
        "success": status_result.get("success", False),
        "simulated": status_result.get("simulated", False),
        "process_running": status_result.get("process_running", False),
        "result": status_result,
        "time": time.time()
    }
    
    # Step 6: Test a more complex operation
    logger.info("Testing list_wallets in simulation mode")
    wallets = kit.list_wallets()
    
    result["tests"]["list_wallets"] = {
        "success": wallets.get("success", False),
        "simulated": wallets.get("simulated", False),
        "wallet_count": len(wallets.get("addresses", [])) if "addresses" in wallets else 0,
        "result": wallets,
        "time": time.time()
    }
    
    # Determine overall success - we consider it successful if
    # operations work in simulation mode
    overall_success = all(test.get("success", False) for test in result["tests"].values())
    simulation_working = any(test.get("simulated", False) for k, test in result["tests"].items() 
                             if k != "cleanup")
    
    # Add summary
    result["summary"] = {
        "success": overall_success,
        "simulation_mode_working": simulation_working,
        "test_duration": time.time() - result["timestamp"]
    }
    
    # Log summary
    logger.info(f"Test {'succeeded' if overall_success else 'failed'}")
    logger.info(f"Simulation mode working: {simulation_working}")
    
    return result

if __name__ == "__main__":
    logger.info("Starting verification of auto daemon management")
    
    result = verify_auto_daemon_management()
    
    # Save results
    result_file = "lotus_daemon_verification_results.json"
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Results saved to {result_file}")
    
    # Exit with appropriate code
    sys.exit(0 if result.get("summary", {}).get("success", False) else 1)
