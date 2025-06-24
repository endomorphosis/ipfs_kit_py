#!/usr/bin/env python3
"""
Test script to upload a file to all storage backends through the MCP server and verify they work.
"""

import os
import sys
import time
import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

MCP_URL = "http://127.0.0.1:9999"
TEST_FILE = "/tmp/random_1mb.bin"

def main():
    """Upload test file to all available storage backends and report results."""
    # Ensure test file exists
    if not os.path.exists(TEST_FILE):
        print(f"Creating test file: {TEST_FILE}")
        os.system(f"dd if=/dev/urandom of={TEST_FILE} bs=1M count=1")

    print(f"Test file size: {os.path.getsize(TEST_FILE)} bytes")

    # Check if server is running
    try:
        response = requests.get(f"{MCP_URL}/api/v0/mcp/health")
        if response.status_code == 200:
            print(f"MCP server is running: {response.json().get('server_id')}")
        else:
            print("MCP server is not responding correctly")
            return
    except requests.exceptions.ConnectionError:
        print(f"Failed to connect to MCP server at {MCP_URL}")
        return

    results = {}

    # Test 1: Upload to IPFS
    print("\n=== Testing IPFS Upload ===")
    try:
        with open(TEST_FILE, 'rb') as file:
            data = MultipartEncoder(fields={'file': ('random_1mb.bin', file, 'application/octet-stream')})
            response = requests.post(f"{MCP_URL}/api/v0/mcp/ipfs/add",
                                   data=data,
                                   headers={'Content-Type': data.content_type})
            if response.status_code == 200:
                result = response.json()
                print(f"IPFS upload successful")
                print(f"CID: {result.get('Hash')}")
                results["ipfs"] = result
            else:
                print(f"IPFS upload failed: {response.status_code}")
    except Exception as e:
        print(f"Error in IPFS upload: {e}")

    # Test 2: Upload to Storacha (Web3.Storage)
    print("\n=== Testing Storacha Upload ===")
    if "ipfs" in results:
        ipfs_cid = results["ipfs"].get("Hash")
        try:
            response = requests.post(
                f"{MCP_URL}/api/v0/mcp/storage/storacha/ipfs-to-storacha",
                json={"cid": ipfs_cid, "correlation_id": "test-upload"}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Storacha upload successful")
                print(f"Upload ID: {result.get('upload_id')}")
                print(f"Space DID: {result.get('space_did')}")
                results["storacha"] = result
            else:
                print(f"Storacha upload failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error in Storacha upload: {e}")

    # Test 3: Upload to Filecoin/Lotus
    print("\n=== Testing Filecoin Upload ===")
    if "ipfs" in results:
        ipfs_cid = results["ipfs"].get("Hash")
        try:
            response = requests.post(
                f"{MCP_URL}/api/v0/mcp/storage/filecoin/store",
                json={"cid": ipfs_cid, "correlation_id": "test-upload"}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Filecoin upload successful")
                print(f"Deal ID: {result.get('deal_id')}")
                results["filecoin"] = result
            else:
                print(f"Filecoin upload failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error in Filecoin upload: {e}")

    # Test 4: Upload to HuggingFace
    print("\n=== Testing HuggingFace Upload ===")
    if "ipfs" in results:
        ipfs_cid = results["ipfs"].get("Hash")
        try:
            response = requests.post(
                f"{MCP_URL}/api/v0/mcp/storage/huggingface/ipfs-to-hub",
                json={"cid": ipfs_cid, "repo_id": "test-repo", "path": "test-data.bin", "correlation_id": "test-upload"}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"HuggingFace upload successful")
                print(f"Repository: {result.get('repo_id')}")
                print(f"File path: {result.get('path')}")
                results["huggingface"] = result
            else:
                print(f"HuggingFace upload failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error in HuggingFace upload: {e}")

    # Test 5: Upload to S3 (will likely fail without credentials)
    print("\n=== Testing S3 Upload ===")
    if "ipfs" in results:
        ipfs_cid = results["ipfs"].get("Hash")
        try:
            response = requests.post(
                f"{MCP_URL}/api/v0/mcp/storage/s3/ipfs-to-s3",
                json={"cid": ipfs_cid, "bucket": "test-bucket", "key": "test-data.bin", "correlation_id": "test-upload"}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"S3 upload successful")
                print(f"Bucket: {result.get('bucket')}")
                print(f"Key: {result.get('key')}")
                results["s3"] = result
            else:
                print(f"S3 upload failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error in S3 upload: {e}")

    # Summary
    print("\n=== Upload Results Summary ===")
    for backend, result in results.items():
        status = "SUCCESS" if result.get("success", False) else "FAILURE"
        print(f"{backend.upper()}: {status}")

    print("\n=== Detail Results ===")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
