#!/usr/bin/env python
import logging
import sys
import os
import json
from ipfs_kit_py.lotus_kit import lotus_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("debug_lotus_client")

def main():
    """Debug the lotus_kit client functionality in simulation mode."""
    logger.info("Starting Lotus client debug...")

    # Initialize lotus_kit with simulation mode enabled
    kit = lotus_kit(metadata={
        "simulation_mode": True,
        "auto_start_daemon": False,
        "filecoin_simulation": True,
        "debug": True  # Enable debug logging
    })

    # Print any attributes that might help us understand simulation state
    logger.info(f"Simulation mode: {kit.simulation_mode}")
    from ipfs_kit_py.lotus_kit import LOTUS_AVAILABLE
    logger.info(f"Lotus available: {LOTUS_AVAILABLE}")

    # Test chain head - one of the failing operations
    logger.info("Testing chain head retrieval...")
    result = kit.get_chain_head()
    logger.info(f"Chain head result: {json.dumps(result, indent=2)}")

    # Test wallet operations - another failing operation
    logger.info("Testing wallet operations...")
    wallet_result = kit.list_wallets()
    logger.info(f"Wallet list result: {json.dumps(wallet_result, indent=2)}")

    # Test miner list - a working operation
    logger.info("Testing miner list...")
    miners = kit.list_miners()
    logger.info(f"Miner list result: {json.dumps(miners, indent=2)}")

    logger.info("Debug complete")

if __name__ == "__main__":
    main()
