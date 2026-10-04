#!/usr/bin/env python3
"""
Test script to upload a file to IPFS using both MCP server and direct ipfs_kit.
"""

import os
import sys
import time
import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.storacha_kit import storacha_kit
from ipfs_kit_py.s3_kit import s3_kit

TEST_FILE = "/tmp/random_1mb.bin"
MCP_URL = "http://127.0.0.1:8765"

def main():
    """Upload test file to IPFS and report results."""
    # Ensure test file exists
    if not os.path.exists(TEST_FILE):
        print(f"Creating test file: {TEST_FILE}")
        os.system(f"dd if=/dev/urandom of={TEST_FILE} bs=1M count=1")
    
    print(f"Test file size: {os.path.getsize(TEST_FILE)} bytes")
    
    results = {}
    
    # Direct upload with ipfs_kit
    print("\n=== Testing Direct IPFS Upload with ipfs_kit ===")
    try:
        kit = ipfs_kit()
        with open(TEST_FILE, 'rb') as f:
            content = f.read()
        result = kit.ipfs_add(content)
        if result["success"]:
            print(f"IPFS upload successful")
            print(f"CID: {result['Hash']}")
            results["ipfs_direct"] = result
        else:
            print(f"IPFS upload failed: {result.get('error')}")
    except Exception as e:
        print(f"Error in direct IPFS upload: {e}")
    
    # Direct upload with storacha_kit
    print("\n=== Testing Direct Storacha Upload with storacha_kit ===")
    if "ipfs_direct" in results:
        ipfs_cid = results["ipfs_direct"].get("Hash")
        try:
            # Initialize storacha kit
            storacha = storacha_kit()
            
            # List spaces
            spaces_result = storacha.w3_list_spaces()
            if spaces_result["success"]:
                print(f"Available spaces: {len(spaces_result.get('spaces', []))}")
                
                # Set a current space if available
                if spaces_result.get("spaces"):
                    space_did = spaces_result["spaces"][0]
                    storacha.w3_use(space_did)
                    print(f"Using space: {space_did}")
                    
                    # Try to upload
                    upload_result = storacha.upload_from_ipfs(ipfs_cid)
                    results["storacha_direct"] = upload_result
                    if upload_result["success"]:
                        print(f"Storacha upload successful")
                        print(f"Upload ID: {upload_result.get('upload_id')}")
                    else:
                        print(f"Storacha upload failed: {upload_result.get('error')}")
                else:
                    print("No spaces available for Storacha")
            else:
                print(f"Failed to list spaces: {spaces_result.get('error')}")
        except Exception as e:
            print(f"Error in direct Storacha upload: {e}")
    
    # MCP server upload
    print("\n=== Testing IPFS Upload via MCP ===")
    try:
        with open(TEST_FILE, 'rb') as file:
            data = MultipartEncoder(fields={'file': ('random_1mb.bin', file, 'application/octet-stream')})
            response = requests.post(f"{MCP_URL}/api/v0/mcp/ipfs/add", 
                                  data=data,
                                  headers={'Content-Type': data.content_type})
            if response.status_code == 200:
                result = response.json()
                print(f"MCP IPFS upload successful")
                print(f"CID: {result.get('Hash')}")
                results["ipfs_mcp"] = result
            else:
                print(f"MCP IPFS upload failed: {response.status_code}")
    except Exception as e:
        print(f"Error in MCP IPFS upload: {e}")
    
    # Summary
    print("\n=== Upload Results Summary ===")
    for method, result in results.items():
        status = "SUCCESS" if result.get("success", False) else "FAILURE"
        print(f"{method.upper()}: {status}")
        if result.get("Hash"):
            print(f"  CID: {result.get('Hash')}")
    
    print("\n=== Detail Results ===")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()