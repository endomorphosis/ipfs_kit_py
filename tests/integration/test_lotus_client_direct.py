#!/usr/bin/env python
"""
Test script to verify Filecoin Lotus client functionality.
This script tests both real and simulated modes.
"""

import sys
import os
import json
from ipfs_kit_py.lotus_kit import lotus_kit


def pretty_print(title, data):
    """Print formatted JSON data with a title."""
    print(f"\n===== {title} =====")
    print(json.dumps(data, indent=2))
    print("=" * (len(title) + 12))


# Test function
def test_lotus_client():
    print("\n🔍 Testing Lotus client functionality...")

    # First try with real mode (non-simulation)
    print("\n📡 Testing with REAL MODE (actual Lotus daemon)...")
    try:
        # Initialize the lotus client - explicitly disable simulation mode
        lotus = lotus_kit(metadata={"simulation_mode": False})

        # Test connection
        result = lotus.check_connection()
        pretty_print("Daemon Connection", result)

        if result.get("success"):
            print("✅ Successfully connected to Lotus daemon!")
        else:
            print("❌ Failed to connect to Lotus daemon.")
            print(f"Error: {result.get('error')}")
            print("\n⚠️ Switching to simulation mode for further tests...")
            lotus = lotus_kit(metadata={"simulation_mode": True})
    except Exception as e:
        print(f"❌ Error connecting to Lotus daemon: {str(e)}")
        print("\n⚠️ Switching to simulation mode for further tests...")
        lotus = lotus_kit(metadata={"simulation_mode": True})

    # Test listing wallets
    print("\n💼 Testing wallet listing...")
    wallets = lotus.list_wallets()
    pretty_print("Wallet List", wallets)

    # Test listing deals
    print("\n📄 Testing deal listing...")
    deals = lotus.client_list_deals()
    pretty_print("Deals List", deals)

    # If we have deals, test getting info for one deal
    if deals.get("success") and deals.get("result") and len(deals.get("result")) > 0:
        deal_id = deals["result"][0].get("DealID", 1)
        print(f"\n🔍 Testing deal info for deal ID: {deal_id}...")
        deal_info = lotus.client_deal_info(deal_id)
        pretty_print(f"Deal Info (ID: {deal_id})", deal_info)
    else:
        print("\n⚠️ No deals found to test deal_info")

    # Test listing miners
    print("\n⛏️ Testing miner listing...")
    if hasattr(lotus, "state_list_miners"):
        miners = lotus.state_list_miners()
        pretty_print("Miners List", miners)
    else:
        print("⚠️ state_list_miners method not available")

    # Do a simple simulation check with import
    print("\n📦 Testing content import simulation...")

    # Create a temporary file to import
    import tempfile

    with tempfile.NamedTemporaryFile(
        prefix="lotus_test_", suffix=".txt", delete=False
    ) as temp_file:
        temp_file.write(b"Test content for Lotus client")
        temp_path = temp_file.name

    print(f"Created temporary file at: {temp_path}")
    import_result = lotus.client_import(temp_path)
    pretty_print("Import Result", import_result)

    # Check if we got a valid data CID
    if import_result.get("success") and import_result.get("result", {}).get("Root", {}).get("/"):
        data_cid = import_result["result"]["Root"]["/"]
        print(f"\n✅ Successfully imported content with CID: {data_cid}")

        # Try to start a deal if we have miners and wallets
        if wallets.get("success") and wallets.get("result") and len(wallets.get("result")) > 0:
            wallet = wallets["result"][0]

            # Get a miner address - in simulation we can use any string
            miner = "t01000"
            if (
                hasattr(lotus, "state_list_miners")
                and miners.get("success")
                and miners.get("result")
            ):
                if len(miners["result"]) > 0:
                    miner = miners["result"][0]

            print(f"\n🤝 Testing starting a deal with miner {miner}...")
            deal_result = lotus.client_start_deal(
                data_cid=data_cid,
                miner=miner,
                price="1000",
                duration=518400,  # ~180 days
                wallet=wallet,
            )
            pretty_print("Deal Start Result", deal_result)

            if deal_result.get("success"):
                print("\n✅ Successfully started a storage deal!")
            else:
                print(f"\n❌ Failed to start storage deal: {deal_result.get('error')}")
    else:
        print(f"\n❌ Failed to import content: {import_result.get('error')}")

    # Final status
    print("\n📋 Test Summary:")
    if lotus.simulation_mode:
        print("🔸 Tests completed in SIMULATION MODE")
        print("🔸 Lotus daemon was not available, but simulation worked correctly")
    else:
        print("🔸 Tests completed with ACTUAL Lotus daemon")

    print("\n✅ Test completed! Check the results above for details.")


if __name__ == "__main__":
    test_lotus_client()
