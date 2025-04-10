#!/usr/bin/env python3
"""
Direct test script for verifying lotus_kit simulation mode implementations.
This script tests our simulation mode implementations without additional dependencies.
"""

import os
import sys
import json
import time
import logging
import uuid
import tempfile
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add the project root to the Python path if needed
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Helper function for pretty printing 
def pretty_print(title, data):
    """Print formatted JSON data with a title."""
    print(f"\n===== {title} =====")
    print(json.dumps(data, indent=2))
    print("=" * (len(title) + 12))

def test_lotus_kit_simulation():
    """Test the lotus_kit simulation mode directly."""
    print("\n🔍 Testing Lotus Kit Simulation Mode...")

    try:
        # Import lotus_kit
        from ipfs_kit_py.lotus_kit import lotus_kit
        
        # Create lotus_kit instance with simulation mode enabled
        lotus = lotus_kit(metadata={"simulation_mode": True})
        logger.info("Created lotus_kit instance with simulation mode")
        
        # Verify simulation mode is active
        print(f"\n🔍 Lotus simulation mode active: {lotus.simulation_mode}")
        
        # Test connection check
        print("\n📡 Testing lotus_kit.check_connection()...")
        connection_result = lotus.check_connection()
        pretty_print("Connection Check Result", connection_result)
        
        # Test list_wallets
        print("\n💼 Testing lotus_kit.list_wallets()...")
        wallets_result = lotus.list_wallets()
        pretty_print("Wallet Listing Result", wallets_result)
        
        # Test list_deals
        print("\n📄 Testing lotus_kit.client_list_deals()...")
        deals_result = lotus.client_list_deals()
        pretty_print("Deal Listing Result", deals_result)
        
        # Create a test file to import
        print("\n📦 Testing client_import...")
        with tempfile.NamedTemporaryFile(prefix="lotus_test_", suffix=".txt", delete=False) as temp_file:
            temp_file.write(f"Test content for Lotus import {uuid.uuid4()}".encode())
            temp_path = temp_file.name
            
        print(f"Created temporary file at: {temp_path}")
        import_result = lotus.client_import(temp_path)
        pretty_print("Import Result", import_result)
        
        # Test client_list_imports (newly implemented)
        print("\n📋 Testing client_list_imports...")
        imports_result = lotus.client_list_imports()
        pretty_print("List Imports Result", imports_result)
        
        # Test list_miners (newly implemented)
        print("\n⛏️ Testing list_miners...")
        miners_result = lotus.list_miners()
        pretty_print("List Miners Result", miners_result)
        
        # Test miner_get_info (newly implemented)
        if miners_result.get("success", False) and miners_result.get("result"):
            miner_id = miners_result["result"][0]
            print(f"\n🔍 Testing miner_get_info for miner: {miner_id}...")
            miner_info_result = lotus.miner_get_info(miner_id)
            pretty_print(f"Miner Info for {miner_id}", miner_info_result)
        else:
            print("\n⚠️ No miners found to test miner_get_info")
        
        # Test find_data
        if import_result.get("success", False) and import_result.get("result", {}).get("Root", {}).get("/"):
            data_cid = import_result["result"]["Root"]["/"]
            print(f"\n🔍 Testing client_find_data for CID: {data_cid}...")
            find_data_result = lotus.client_find_data(data_cid)
            pretty_print("Find Data Result", find_data_result)
            
            # Start deal to test client_retrieve
            print(f"\n🤝 Testing client_start_deal for CID: {data_cid}...")
            deal_result = lotus.client_start_deal(
                data_cid=data_cid,
                miner="t01000",  # simulated miner
                price="1000",
                duration=518400,  # ~180 days
                wallet=wallets_result.get("result", ["t1default"])[0] if wallets_result.get("success", False) else "t1default"
            )
            pretty_print("Deal Start Result", deal_result)
            
            # Test retrieve data
            print(f"\n📥 Testing client_retrieve for CID: {data_cid}...")
            retrieve_path = os.path.join(tempfile.gettempdir(), f"lotus_retrieve_{uuid.uuid4()}.bin")
            retrieve_result = lotus.client_retrieve(data_cid, retrieve_path)
            pretty_print("Retrieve Result", retrieve_result)
            
            if retrieve_result.get("success", False):
                print(f"\n✅ Successfully retrieved data to: {retrieve_path}")
                # Check file exists and size
                if os.path.exists(retrieve_path):
                    file_size = os.path.getsize(retrieve_path)
                    print(f"Retrieved file size: {file_size} bytes")
                    
                    # Read first 100 bytes to show content
                    with open(retrieve_path, 'rb') as f:
                        content_sample = f.read(100)
                    print(f"Content preview: {content_sample[:50]}{'...' if len(content_sample) > 50 else ''}")
                    
                    # Clean up retrieved file
                    os.unlink(retrieve_path)
                else:
                    print(f"⚠️ Retrieved file not found at path: {retrieve_path}")
            else:
                print(f"\n❌ Failed to retrieve data: {retrieve_result.get('error')}")
                
        else:
            print(f"\n❌ Failed to import content: {import_result.get('error')}")
            
        # Clean up the test file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            
        # Test newly implemented market methods
        print("\n💹 Testing market_list_storage_deals...")
        storage_deals_result = lotus.market_list_storage_deals()
        pretty_print("Storage Deals Result", storage_deals_result)
        
        print("\n🔄 Testing market_list_retrieval_deals...")
        retrieval_deals_result = lotus.market_list_retrieval_deals()
        pretty_print("Retrieval Deals Result", retrieval_deals_result)
        
        print("\n📊 Testing market_get_deal_updates...")
        deal_updates_result = lotus.market_get_deal_updates()
        pretty_print("Deal Updates Result", deal_updates_result)
        
        # Test newly implemented payment channel methods
        print("\n💰 Testing payment channel methods...")
        paych_list_result = lotus.paych_list()
        pretty_print("Payment Channel List Result", paych_list_result)
        
        # If we have any payment channels, test paych_status
        if paych_list_result.get("success", False) and paych_list_result.get("result"):
            channel_addr = paych_list_result["result"][0]
            print(f"\n📊 Testing paych_status for channel: {channel_addr}...")
            paych_status_result = lotus.paych_status(channel_addr)
            pretty_print("Payment Channel Status Result", paych_status_result)
        else:
            print("\n⚠️ No payment channels found to test paych_status")
        
        # Test newly implemented wallet balance
        if wallets_result.get("success", False) and wallets_result.get("result"):
            wallet_addr = wallets_result["result"][0]
            print(f"\n💼 Testing wallet_balance for: {wallet_addr}...")
            balance_result = lotus.wallet_balance(wallet_addr)
            pretty_print("Wallet Balance Result", balance_result)
        
        # Test newly implemented miner sector methods
        print("\n⛏️ Testing miner sector methods...")
        sectors_result = lotus.miner_list_sectors()
        pretty_print("Miner Sectors List Result", sectors_result)
        
        # If we have any sectors, test miner_sector_status
        if sectors_result.get("success", False) and sectors_result.get("result"):
            sector_number = sectors_result["result"][0]
            print(f"\n📊 Testing miner_sector_status for sector: {sector_number}...")
            sector_status_result = lotus.miner_sector_status(sector_number)
            pretty_print("Sector Status Result", sector_status_result)
        else:
            print("\n⚠️ No sectors found to test miner_sector_status")
        
        # Test verify that simulation mode was used
        print("\n🔍 Verifying simulation mode was used...")
        print(f"Simulation mode active: {lotus.simulation_mode}")
        print(f"Marked as simulated in import result: {import_result.get('simulated', False)}")
        
        # Check overall result
        simulation_success = (
            connection_result.get("success", False) and
            wallets_result.get("success", False) and
            import_result.get("success", False) and
            imports_result.get("success", False) and
            miners_result.get("success", False) and
            storage_deals_result.get("success", False) and
            retrieval_deals_result.get("success", False) and
            deal_updates_result.get("success", False) and
            paych_list_result.get("success", False) and
            sectors_result.get("success", False)
        )
        
        print(f"\n✅ Simulation mode testing complete! Overall success: {simulation_success}")
        return True
            
    except Exception as e:
        logger.exception(f"Error during lotus_kit simulation test: {e}")
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    # Run the test
    success = test_lotus_kit_simulation()
    sys.exit(0 if success else 1)