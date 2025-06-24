#!/usr/bin/env python3
"""
CLI Controller Test Script

This script specifically tests the CLI controller endpoints of the MCP server
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

def create_test_file(content="Test content for CLI tests"):
    """Create a temporary test file."""
    import tempfile
    fd, path = tempfile.mkstemp(prefix="cli_test_", suffix=".txt")
    os.close(fd)

    with open(path, "w") as f:
        f.write(content)

    return path

def test_cli_add_content_with_proper_format():
    """Test adding content with the proper format."""
    print("\n=== Testing CLI Add Content (Proper Format) ===")

    # Create test content
    content = f"Test content for CLI add operation - {time.time()}"

    # Create request with all required fields
    add_data = {
        "command": "add",
        "content": content,
        "args": [],
        "params": {"wrap-with-directory": False, "pin": True},
        "format": "json"
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/cli/add", "POST",
                       data=add_data, headers=headers,
                       test_name="CLI Add Content (Proper Format)")

    if response and response.status_code == 200:
        result = response.json()
        if result.get("success") and result.get("result"):
            cid = None
            if isinstance(result.get("result"), dict) and "Hash" in result.get("result"):
                cid = result["result"]["Hash"]

            if cid:
                print(f"Successfully added content with CID: {cid}")

                # Test retrieving the content
                test_cli_cat_content(cid)
                return cid

    return None

def test_cli_cat_content(cid):
    """Test retrieving content via CLI controller."""
    print(f"\n=== Testing CLI Cat Content for CID: {cid} ===")

    # Test using the cat endpoint
    cat_data = {
        "cid": cid
    }

    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/cli/cat", "POST",
                       data=cat_data, headers=headers,
                       test_name=f"CLI Cat Content: {cid}")

    return response and response.status_code == 200

def test_cli_version():
    """Test getting CLI version information."""
    print("\n=== Testing CLI Version ===")

    response = run_test("/api/v0/mcp/cli/version", "GET",
                       test_name="CLI Version")

    return response and response.status_code == 200

def test_cli_with_command_arg_format():
    """Test CLI with command/args/params format."""
    print("\n=== Testing CLI with Command/Args Format ===")

    # Create test content
    test_path = create_test_file()
    print(f"Created test file: {test_path}")

    try:
        # Test with command/args/params format
        add_data = {
            "command": "add",
            "args": [test_path],
            "params": {"wrap-with-directory": False, "pin": True},
            "format": "json",
            "content": open(test_path, "r").read()  # Add the required content field
        }

        headers = {"Content-Type": "application/json"}
        response = run_test("/api/v0/mcp/cli/add", "POST",
                           data=add_data, headers=headers,
                           test_name="CLI Add with Command/Args Format")

        return response and response.status_code == 200
    finally:
        # Clean up
        if os.path.exists(test_path):
            os.remove(test_path)
            print(f"Removed test file: {test_path}")

def test_with_multipart_form():
    """Test adding content via multipart form data."""
    print("\n=== Testing CLI Add with Multipart Form ===")

    # Create test content
    test_path = create_test_file("Multipart form test content")
    print(f"Created test file: {test_path}")

    try:
        # Create multipart form data
        with open(test_path, "rb") as f:
            content = f.read().decode('utf-8')

        # Create form data with CLI add command format
        form_data = {
            "command": "add",
            "content": content,
            "args": [],
            "params": {"wrap-with-directory": False, "pin": True},
            "format": "json"
        }

        headers = {"Content-Type": "application/json"}
        response = run_test("/api/v0/mcp/cli/add", "POST",
                           data=form_data, headers=headers,
                           test_name="CLI Add with Multipart Form")

        return response and response.status_code == 200
    finally:
        # Clean up
        if os.path.exists(test_path):
            os.remove(test_path)
            print(f"Removed test file: {test_path}")

def test_with_raw_file_multipart():
    """Test adding raw file with multipart."""
    print("\n=== Testing CLI Add with Raw File Multipart ===")

    # Create test content
    test_path = create_test_file("Raw file multipart test content")
    print(f"Created test file: {test_path}")

    try:
        # Create multipart form with file
        files = {
            "file": ("test_file.txt", open(test_path, "rb")),
            "wrap_with_directory": (None, "false"),
            "pin": (None, "true")
        }

        response = run_test("/api/v0/mcp/ipfs/add", "POST",
                           files=files,
                           test_name="CLI Add with Raw File Multipart")

        return response and response.status_code == 200
    finally:
        # Clean up
        if os.path.exists(test_path):
            try:
                os.remove(test_path)
                print(f"Removed test file: {test_path}")
            except:
                print(f"Warning: Could not remove test file: {test_path}")

def run_all_tests():
    """Run all CLI controller tests."""
    print("\n=== Running All CLI Controller Tests ===")

    success_count = 0
    total_tests = 5

    # Test 1: CLI Version
    if test_cli_version():
        success_count += 1

    # Test 2: CLI Add Content (Proper Format)
    if test_cli_add_content_with_proper_format():
        success_count += 1

    # Test 3: CLI with Command/Args Format
    if test_cli_with_command_arg_format():
        success_count += 1

    # Test 4: Test with Multipart Form
    if test_with_multipart_form():
        success_count += 1

    # Test 5: Test with Raw File Multipart
    if test_with_raw_file_multipart():
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
