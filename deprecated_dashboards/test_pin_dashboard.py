#!/usr/bin/env python3
"""
Test script for comprehensive pin management dashboard
"""

import asyncio
import json
import requests
import time
from pathlib import Path

async def test_pin_features():
    """Test all pin features in the dashboard"""
    base_url = "http://127.0.0.1:8083"
    jsonrpc_url = f"{base_url}/api/jsonrpc"
    
    # Test data
    test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"
    
    def make_jsonrpc_request(method, params=None):
        """Make a JSON-RPC request"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1
        }
        
        try:
            response = requests.post(jsonrpc_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    print("🧪 Testing Comprehensive Pin Management Features")
    print("=" * 60)
    
    # Test 1: Add a pin
    print("\n1. Testing pin add...")
    result = make_jsonrpc_request("ipfs.pin.add", {
        "cid_or_file": test_cid,
        "name": "test-document",
        "recursive": True,
        "metadata": {"description": "Test document for pin management"}
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 2: List pins
    print("\n2. Testing pin list...")
    result = make_jsonrpc_request("ipfs.pin.ls", {
        "limit": 10,
        "metadata": True
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 3: Search pins
    print("\n3. Testing pin search...")
    result = make_jsonrpc_request("ipfs.pin.search", {
        "query": "test",
        "limit": 5
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 4: Pending operations
    print("\n4. Testing pending operations...")
    result = make_jsonrpc_request("ipfs.pin.pending", {
        "limit": 5,
        "metadata": True
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 5: Pin verification
    print("\n5. Testing pin verification...")
    result = make_jsonrpc_request("ipfs.pin.verify", {
        "cid": test_cid
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 6: Bulk pin add
    print("\n6. Testing bulk pin add...")
    result = make_jsonrpc_request("ipfs.pin.bulk_add", {
        "cids": ["QmTest1", "QmTest2", "QmTest3"],
        "recursive": True,
        "name_prefix": "bulk_test"
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 7: Pin cleanup
    print("\n7. Testing pin cleanup...")
    result = make_jsonrpc_request("ipfs.pin.cleanup", {
        "dry_run": True
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 8: Export metadata
    print("\n8. Testing metadata export...")
    result = make_jsonrpc_request("ipfs.pin.export_metadata", {
        "max_shard_size": 100
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 9: Pin status
    print("\n9. Testing pin status...")
    result = make_jsonrpc_request("ipfs.pin.status", {
        "operation_id": "pin_op_001"
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 10: Pin get (download)
    print("\n10. Testing pin get...")
    result = make_jsonrpc_request("ipfs.pin.get", {
        "cid": test_cid,
        "output_path": "/tmp/test_download"
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 11: Pin cat (stream content)
    print("\n11. Testing pin cat...")
    result = make_jsonrpc_request("ipfs.pin.cat", {
        "cid": test_cid,
        "limit": 1000
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    # Test 12: Remove pin
    print("\n12. Testing pin remove...")
    result = make_jsonrpc_request("ipfs.pin.rm", {
        "cid": test_cid
    })
    print(f"   Result: {json.dumps(result, indent=2)}")
    
    print("\n" + "=" * 60)
    print("✅ Pin management testing completed!")
    print("\nYou can now:")
    print("  1. Open http://127.0.0.1:8083 in your browser")
    print("  2. Navigate to the 'Pins' tab")
    print("  3. Test all the pin management features")
    print("  4. Use the modals for adding pins, bulk operations, etc.")

def check_server_running():
    """Check if the server is running"""
    try:
        response = requests.get("http://127.0.0.1:8083/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def main():
    """Main function"""
    print("🚀 IPFS Kit - Pin Management Dashboard Test")
    print("=" * 50)
    
    if not check_server_running():
        print("❌ Server is not running on port 8083")
        print("Please start the server first:")
        print("  python launch_unified_mcp_dashboard.py --port 8083")
        return 1
    
    print("✅ Server is running, proceeding with tests...")
    
    # Run the async tests
    asyncio.run(test_pin_features())
    
    return 0

if __name__ == "__main__":
    exit(main())
