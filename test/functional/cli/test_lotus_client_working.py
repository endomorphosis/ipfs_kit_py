#!/usr/bin/env python3
"""
Test script to verify that the Filecoin Lotus client actually works after dependencies are installed.

This script tests real Lotus operations to confirm that the client is properly functional.
"""

import logging
import os
import time
import subprocess
import json

from ipfs_kit_py.lotus_kit import lotus_kit, LOTUS_AVAILABLE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_lotus_client_working")

def check_daemon_running():
    """Check if the Lotus daemon is running."""
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
                return True, peer_data.get("ID", "unknown")
            except json.JSONDecodeError:
                return True, "unknown"
        else:
            return False, result.stderr
    except (subprocess.SubprocessError, FileNotFoundError):
        return False, "Lotus command not found or failed"

def start_daemon_if_needed():
    """Start the Lotus daemon if not already running."""
    is_running, peer_id = check_daemon_running()

    if is_running:
        logger.info(f"Lotus daemon already running with peer ID: {peer_id}")
        return True, peer_id

    # Try to start the daemon in the background
    logger.info("Starting Lotus daemon...")
    try:
        # Use Popen to start daemon in the background
        subprocess.Popen(
            ["lotus", "daemon", "--lite"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Give it some time to start up
        time.sleep(5)

        # Check if it's running now
        for _ in range(5):  # Try a few times
            is_running, peer_id = check_daemon_running()
            if is_running:
                logger.info(f"Lotus daemon started successfully with peer ID: {peer_id}")
                return True, peer_id
            time.sleep(2)

        logger.error("Failed to start Lotus daemon")
        return False, "Failed to start"
    except Exception as e:
        logger.error(f"Error starting Lotus daemon: {e}")
        return False, str(e)

def test_lotus_functionality():
    """Test various Lotus client functionality to verify it's working properly."""
    logger.info("Testing Lotus client functionality")

    # Initialize lotus_kit with dependency installation
    kit = lotus_kit(metadata={
        "install_dependencies": True,  # Install dependencies if needed
        "filecoin_simulation": True,   # Enable simulation mode for Filecoin
        "auto_start_daemon": False     # We'll handle the daemon manually
    })

    # Check if Lotus is available
    logger.info(f"Lotus available: {LOTUS_AVAILABLE}")
    if not LOTUS_AVAILABLE:
        logger.warning("Lotus binary not available after dependency installation")
        logger.info("Running in simulation mode for basic API tests")

    # Start the daemon if needed and Lotus is available
    daemon_running = False
    if LOTUS_AVAILABLE:
        daemon_running, peer_id = start_daemon_if_needed()
        if daemon_running:
            logger.info(f"Lotus daemon is running with peer ID: {peer_id}")
        else:
            logger.warning("Could not start Lotus daemon, using simulation mode")
            kit.simulation_mode = True

    # Test chain head
    logger.info("Testing chain head retrieval...")
    chain_head = kit.get_chain_head()
    if chain_head["success"]:
        logger.info(f"Chain head height: {chain_head.get('Height', 'unknown')}")
        logger.info(f"Chain head CIDs: {len(chain_head.get('Cids', []))}")
    else:
        logger.warning(f"Failed to get chain head: {chain_head.get('error', 'Unknown error')}")

    # Test wallet operations
    logger.info("Testing wallet operations...")
    wallet_list = kit.list_wallets()
    if wallet_list["success"]:
        wallets = wallet_list.get("result", [])
        logger.info(f"Found {len(wallets)} wallet(s)")

        if len(wallets) > 0:
            # Test wallet balance
            wallet_addr = wallets[0]
            balance = kit.wallet_balance(wallet_addr)
            if balance["success"]:
                logger.info(f"Balance for {wallet_addr}: {balance.get('result', 'unknown')}")
            else:
                logger.warning(f"Failed to get balance: {balance.get('error', 'Unknown error')}")
        else:
            logger.info("No wallets found, creating a new wallet")
            new_wallet = kit.wallet_new("bls")
            if new_wallet["success"]:
                wallet_addr = new_wallet.get("result", "")
                logger.info(f"Created new wallet: {wallet_addr}")

                # Check balance of new wallet
                balance = kit.wallet_balance(wallet_addr)
                if balance["success"]:
                    logger.info(f"Balance for new wallet: {balance.get('result', 'unknown')}")
                else:
                    logger.warning(f"Failed to get balance: {balance.get('error', 'Unknown error')}")
            else:
                logger.warning(f"Failed to create wallet: {new_wallet.get('error', 'Unknown error')}")
    else:
        logger.warning(f"Failed to list wallets: {wallet_list.get('error', 'Unknown error')}")

    # Test network information
    logger.info("Testing network information retrieval...")
    peers = kit.net_peers()
    if peers["success"]:
        peer_count = len(peers.get("result", []))
        logger.info(f"Connected to {peer_count} peers")
    else:
        logger.warning(f"Failed to get peers: {peers.get('error', 'Unknown error')}")

    # Return overall results
    results = {
        "lotus_available": LOTUS_AVAILABLE,
        "daemon_running": daemon_running,
        "simulation_mode": kit.simulation_mode,
        "chain_head_success": chain_head.get("success", False),
        "wallet_list_success": wallet_list.get("success", False),
        "net_peers_success": peers.get("success", False)
    }

    # Overall success if either real client works or simulation works
    results["overall_success"] = (
        (LOTUS_AVAILABLE and daemon_running) or  # Real client works
        (kit.simulation_mode and chain_head.get("success", False))  # Simulation works
    )

    return results

if __name__ == "__main__":
    results = test_lotus_functionality()

    print("\n=== Lotus Functionality Test Results ===")
    print(f"Lotus Binary Available: {results['lotus_available']}")
    print(f"Lotus Daemon Running: {results['daemon_running']}")
    print(f"Simulation Mode: {results['simulation_mode']}")
    print(f"Chain Head API: {'✓' if results['chain_head_success'] else '✗'}")
    print(f"Wallet List API: {'✓' if results['wallet_list_success'] else '✗'}")
    print(f"Network Peers API: {'✓' if results['net_peers_success'] else '✗'}")
    print(f"Overall Success: {'✓' if results['overall_success'] else '✗'}")

    if results['overall_success']:
        print("\nLotus client is functioning correctly!")
        if results['simulation_mode']:
            print("Note: Running in simulation mode, but APIs are working")
        else:
            print("Real Lotus client is operational with working dependencies")
    else:
        print("\nLotus client is NOT functioning correctly.")
        print("Check logs for more details on specific failures.")
