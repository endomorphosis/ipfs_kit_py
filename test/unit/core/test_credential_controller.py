#!/usr/bin/env python3
"""
Credential Controller Test Script

This script specifically tests the credential controller endpoints of the MCP server
"""

import requests
import json
import time
import sys
import os

def run_test(endpoint, method="GET", data=None, files=None,
           headers=None, test_name=None, expected_status=200, base_url="http://localhost:9999"):
    """Run a test on a specific endpoint."""
    if test_name is None:
        test_name = f"{method} {endpoint}"

    url = f"{base_url}{endpoint}"
    print(f"\n[TEST] {test_name}")
    print(f"Request: {method} {url}")

    if data:
        if isinstance(data, dict) and not any(isinstance(v, (bytes, bytearray)) for v in data.values()):
            try:
                print(f"Data: {json.dumps(data)}")
            except:
                print(f"Data: [Complex data structure]")
        else:
            print(f"Data: [Binary or complex data]")

    start_time = time.time()
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            if files:
                response = requests.post(url, files=files, headers=headers)
            elif headers and headers.get("Content-Type") == "application/json":
                response = requests.post(url, json=data, headers=headers)
            else:
                response = requests.post(url, data=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        elapsed = time.time() - start_time
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.3f}s")

        try:
            response_data = response.json()
            print(f"Response: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response: {response.text[:500]}")

        # Check status
        success = response.status_code == expected_status
        if success:
            print(f"✅ Test passed: {test_name}")
        else:
            print(f"❌ Test failed: {test_name}")
            print(f"Expected status: {expected_status}, got: {response.status_code}")

        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"❌ Test failed: {test_name}")
        return None

def test_list_credentials():
    """Test listing credentials."""
    print("\n=== Testing List Credentials ===")

    response = run_test("/api/v0/mcp/credentials", "GET",
                       test_name="List Credentials")

    return response and response.status_code == 200

def test_add_s3_credentials():
    """Test adding S3 credentials."""
    print("\n=== Testing Add S3 Credentials ===")

    credential_data = {
        "name": "test_s3",
        "aws_access_key_id": "test_access_key",
        "aws_secret_access_key": "test_secret_key",
        "endpoint_url": "https://test-s3-endpoint.example.com",
        "region": "us-east-1"
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/credentials/s3", "POST",
                       data=credential_data, headers=headers,
                       test_name="Add S3 Credentials")

    # Now verify it appears in the list
    if response and response.status_code == 200:
        list_response = run_test("/api/v0/mcp/credentials", "GET",
                                test_name="Verify S3 Credentials Added")

        if list_response and list_response.status_code == 200:
            result = list_response.json()
            if result.get("success"):
                for cred in result.get("credentials", []):
                    if cred.get("name") == "test_s3" and cred.get("service") == "s3":
                        return True

    return False

def test_add_storacha_credentials():
    """Test adding Storacha credentials."""
    print("\n=== Testing Add Storacha Credentials ===")

    credential_data = {
        "name": "test_storacha",
        "api_token": "test_token_123456789",
        "space_did": "did:key:test123"
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/credentials/storacha", "POST",
                       data=credential_data, headers=headers,
                       test_name="Add Storacha Credentials")

    # Verify it appears in the list
    if response and response.status_code == 200:
        list_response = run_test("/api/v0/mcp/credentials", "GET",
                                test_name="Verify Storacha Credentials Added")

        if list_response and list_response.status_code == 200:
            result = list_response.json()
            if result.get("success"):
                for cred in result.get("credentials", []):
                    if cred.get("name") == "test_storacha" and cred.get("service") == "storacha":
                        return True

    return False

def test_add_filecoin_credentials():
    """Test adding Filecoin credentials."""
    print("\n=== Testing Add Filecoin Credentials ===")

    credential_data = {
        "name": "test_filecoin",
        "api_key": "filecoin_api_key_123",
        "api_secret": "filecoin_api_secret_456",
        "wallet_address": "f1abcdefg",
        "provider": "estuary"
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/credentials/filecoin", "POST",
                       data=credential_data, headers=headers,
                       test_name="Add Filecoin Credentials")

    # Verify it appears in the list
    if response and response.status_code == 200:
        list_response = run_test("/api/v0/mcp/credentials", "GET",
                                test_name="Verify Filecoin Credentials Added")

        if list_response and list_response.status_code == 200:
            result = list_response.json()
            if result.get("success"):
                for cred in result.get("credentials", []):
                    if cred.get("name") == "test_filecoin" and cred.get("service") == "filecoin":
                        return True

    return False

def test_add_ipfs_credentials():
    """Test adding IPFS credentials."""
    print("\n=== Testing Add IPFS Credentials ===")

    credential_data = {
        "name": "test_ipfs",
        "identity": "test_ipfs_identity",
        "api_address": "/ip4/127.0.0.1/tcp/5001",
        "cluster_secret": "test_cluster_secret_123"
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/credentials/ipfs", "POST",
                       data=credential_data, headers=headers,
                       test_name="Add IPFS Credentials")

    # Verify it appears in the list
    if response and response.status_code == 200:
        list_response = run_test("/api/v0/mcp/credentials", "GET",
                                test_name="Verify IPFS Credentials Added")

        if list_response and list_response.status_code == 200:
            result = list_response.json()
            if result.get("success"):
                for cred in result.get("credentials", []):
                    if cred.get("name") == "test_ipfs" and cred.get("service") == "ipfs":
                        return True

    return False

def test_remove_credentials():
    """Test removing credentials."""
    print("\n=== Testing Remove Credentials ===")

    # First, make sure we have credentials to remove
    # We'll try to remove the S3 credentials we added earlier
    response = run_test("/api/v0/mcp/credentials/s3/test_s3", "DELETE",
                       test_name="Remove S3 Credentials")

    if response and response.status_code == 200:
        # Verify it's gone
        list_response = run_test("/api/v0/mcp/credentials", "GET",
                                test_name="Verify S3 Credentials Removed")

        if list_response and list_response.status_code == 200:
            result = list_response.json()
            if result.get("success"):
                for cred in result.get("credentials", []):
                    if cred.get("name") == "test_s3" and cred.get("service") == "s3":
                        return False  # Credential still exists, test failed
                return True  # Credential not found, test passed

    return False

def run_all_tests():
    """Run all credential controller tests."""
    print("\n=== Running All Credential Controller Tests ===")

    success_count = 0
    total_tests = 6

    # Test 1: List Credentials
    if test_list_credentials():
        success_count += 1

    # Test 2: Add S3 Credentials
    if test_add_s3_credentials():
        success_count += 1

    # Test 3: Add Storacha Credentials
    if test_add_storacha_credentials():
        success_count += 1

    # Test 4: Add Filecoin Credentials
    if test_add_filecoin_credentials():
        success_count += 1

    # Test 5: Add IPFS Credentials
    if test_add_ipfs_credentials():
        success_count += 1

    # Test 6: Remove Credentials
    if test_remove_credentials():
        success_count += 1

    # Print summary
    print("\n=== Test Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_tests - success_count}")
    print(f"Success rate: {success_count/total_tests:.1%}")


if __name__ == "__main__":
    # Allow specifying base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9999"

    # Run all tests
    run_all_tests()
