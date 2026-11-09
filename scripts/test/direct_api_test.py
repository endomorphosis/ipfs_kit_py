#\!/usr/bin/env python3
"""
Direct testing of the MCP server method_normalizer and simulation methods.
This script tests the IPFSMethodAdapter directly without creating a full MCP server.
"""

import os
import json
import sys
import logging
from ipfs_kit_py.mcp.utils.method_normalizer import IPFSMethodAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def print_result(name, result):
    """Pretty print a result dictionary."""
    print(f"\n===== {name} =====")
    if isinstance(result, dict):
        # Make a copy of the dict to avoid modifying the original
        result_copy = result.copy()
        
        # Handle binary data in the dict
        for key, value in result.items():
            if isinstance(value, bytes):
                # Convert bytes to string representation
                result_copy[key] = f"<binary data: {value[:20]}... ({len(value)} bytes)>"
        
        print(json.dumps(result_copy, indent=2))
    else:
        if isinstance(result, bytes):
            # Handle binary result
            print(f"<binary data: {result[:20]}... ({len(result)} bytes)>")
        else:
            print(result)
    print("=" * (len(name) + 12))

def run_direct_tests():
    """Run direct tests against the method_normalizer."""
    print("Testing IPFSMethodAdapter directly...")
    
    # Create a method adapter in simulation-only mode (no actual IPFS instance)
    adapter = IPFSMethodAdapter(instance=None)
    
    # Test adding content
    print("\nTesting add_content method...")
    content = "Hello, Method Normalizer! This is a direct test."
    result = adapter.add(content)
    print_result("Add content result", result)
    
    # Get the CID for further tests
    cid = result.get("Hash")
    if cid:
        print(f"Got CID: {cid}")
        
        # Test retrieving content
        print("\nTesting cat method...")
        result = adapter.cat(cid)
        print_result("Cat result", result)
        
        # Test pinning content
        print("\nTesting pin method...")
        result = adapter.pin(cid)
        print_result("Pin result", result)
    
    # Test all MFS operations
    test_mfs_operations(adapter)
    
    # Test block operations
    test_block_operations(adapter, cid)
    
    # Test DHT operations
    test_dht_operations(adapter)
    
    # Test IPNS operations
    test_ipns_operations(adapter, cid)
    
    print("\nTests completed!")

def test_mfs_operations(ipfs):
    """Test the MFS operations."""
    print("\nTesting MFS operations...")
    
    # Test files_mkdir
    result = ipfs.files_mkdir("/test-dir", True)
    print_result("files_mkdir result", result)
    
    # Test files_ls
    result = ipfs.files_ls("/")
    print_result("files_ls result", result)
    
    # Test files_stat
    result = ipfs.files_stat("/test-dir")
    print_result("files_stat result", result)
    
    # Test files_write
    test_data = b"Hello, MFS!"
    result = ipfs.files_write("/test-dir/test-file.txt", test_data, create=True)
    print_result("files_write result", result)
    
    # Test files_read
    result = ipfs.files_read("/test-dir/test-file.txt")
    print_result("files_read result", result)
    
    # Test files_rm
    result = ipfs.files_rm("/test-dir/test-file.txt")
    print_result("files_rm result", result)

def test_block_operations(ipfs, existing_cid=None):
    """Test the Block operations."""
    print("\nTesting Block operations...")
    
    # Test block_put
    test_data = b"Test block data"
    result = ipfs.block_put(test_data)
    print_result("block_put result", result)
    
    # Get the CID from the result
    block_cid = result.get("Key", "")
    
    if not block_cid and existing_cid:
        block_cid = existing_cid
    
    if block_cid:
        # Test block_stat
        result = ipfs.block_stat(block_cid)
        print_result("block_stat result", result)
        
        # Test block_get
        result = ipfs.block_get(block_cid)
        print_result("block_get result", result)

def test_dht_operations(ipfs):
    """Test the DHT operations."""
    print("\nTesting DHT operations...")
    
    # Test dht_findpeer
    peer_id = "QmTest123"
    result = ipfs.dht_findpeer(peer_id)
    print_result("dht_findpeer result", result)
    
    # Test dht_findprovs
    cid = "QmTestCID"
    result = ipfs.dht_findprovs(cid)
    print_result("dht_findprovs result", result)

def test_ipns_operations(ipfs, cid=None):
    """Test the IPNS operations."""
    print("\nTesting IPNS operations...")
    
    if not cid:
        cid = "QmTestCID"
    
    # Test name_publish - use try/except to handle potential method signature issues
    try:
        # Try standard signature (cid, key)
        result = ipfs.name_publish(cid, "self")
        print_result("name_publish result", result)
    except TypeError:
        try:
            # Try alternate signature (path, key)
            result = ipfs.name_publish(f"/ipfs/{cid}", "self")
            print_result("name_publish result", result)
        except (TypeError, AttributeError) as e:
            # If both fail, print the error
            print(f"\n===== name_publish result =====")
            print(f"Error: {str(e)}")
            print("=" * 29)
            
            # Use a hardcoded simulated result for testing
            result = {
                "success": True,
                "operation": "name_publish",
                "Name": f"k51qzi5uqu5dilfp55ebnzbkjuinr3eiauiqvqaaaaaapdd5",
                "Value": f"/ipfs/{cid}",
                "simulated": True
            }
    
    # Get the name from the result
    name = result.get("Name", "")
    
    if name:
        # Test name_resolve
        try:
            result = ipfs.name_resolve(name)
            print_result("name_resolve result", result)
        except (TypeError, AttributeError) as e:
            # If name_resolve fails, print the error
            print(f"\n===== name_resolve result =====")
            print(f"Error: {str(e)}")
            print("=" * 30)
            
            # Use a hardcoded simulated result for testing
            result = {
                "success": True,
                "operation": "name_resolve",
                "Path": f"/ipfs/{cid}",
                "simulated": True
            }

if __name__ == "__main__":
    run_direct_tests()
