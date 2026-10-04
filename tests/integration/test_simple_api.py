#!/usr/bin/env python3
"""
Simple test of the IPFSSimpleAPI to upload content directly.
"""

import os
import json
import time
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

def main():
    """Upload a random file to IPFS using the high-level API."""
    # Create test file
    test_file = "/tmp/random_1mb.bin"
    if not os.path.exists(test_file):
        print(f"Creating test file: {test_file}")
        os.system(f"dd if=/dev/urandom of={test_file} bs=1M count=1")
    
    print(f"Test file size: {os.path.getsize(test_file)} bytes")
    
    # Initialize API
    api = IPFSSimpleAPI()
    
    # Test API functionality
    print("\n=== API Version ===")
    version = api.version()
    print(json.dumps(version, indent=2))
    
    # Upload a file
    print("\n=== Upload Test File ===")
    with open(test_file, 'rb') as f:
        content = f.read()
    
    result = api.add(content)
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        cid = result.get("cid")
        print(f"Successfully uploaded content with CID: {cid}")
        
        # Pin the content
        print("\n=== Pin Content ===")
        pin_result = api.pin(cid)
        print(json.dumps(pin_result, indent=2))
        
        # List pins
        print("\n=== List Pins ===")
        pins_result = api.pins()
        print(json.dumps(pins_result, indent=2))
        
        # Get the content
        print("\n=== Get Content ===")
        get_result = api.cat(cid)
        print(f"Retrieved content size: {len(get_result) if isinstance(get_result, bytes) else 'Error'}")
        
if __name__ == "__main__":
    main()