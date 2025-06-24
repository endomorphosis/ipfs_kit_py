#!/usr/bin/env python3
"""
Simple script to test a single MCP API endpoint.
This helps diagnose server issues by focusing on just one endpoint.
"""

import os
import sys
import time
import json
import requests
import subprocess
import tempfile
import atexit

# Configuration
SERVER_PORT = 9000
SERVER_URL = f"http://localhost:{SERVER_PORT}"
API_PREFIX = "/api/v0"
API_URL = f"{SERVER_URL}{API_PREFIX}"

def start_server():
    """Start the MCP test server."""
    print("Starting MCP test server...")

    # Make sure start_test_mcp_server.py exists
    server_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "start_test_mcp_server.py")
    if not os.path.exists(server_script):
        print(f"Server script not found at {server_script}")
        return None

    # Start the server on a different port
    cmd = [
        sys.executable,
        server_script,
        "--host", "127.0.0.1",
        "--port", str(SERVER_PORT)
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Register cleanup function
    atexit.register(lambda: process.terminate())

    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(10):
        time.sleep(1)
        try:
            # Try root endpoint
            response = requests.get(f"{SERVER_URL}/")
            if response.status_code == 200:
                print("Server started successfully!")
                return process
        except requests.exceptions.RequestException:
            print(f"Waiting for server... (attempt {i+1}/10)")

    # If we get here, failed to start
    print("Failed to start server!")
    process.terminate()
    return None

def test_endpoints():
    """Test various API endpoints."""
    # Test root endpoint
    print("\nTesting root endpoint...")
    try:
        response = requests.get(f"{SERVER_URL}/")
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Root endpoint response:")
            print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Test health endpoint
    print("\nTesting health endpoint...")
    try:
        response = requests.get(f"{API_URL}/health")
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Health endpoint response:")
            print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # List all available routes
    print("\nGetting all available routes...")
    try:
        response = requests.get(f"{SERVER_URL}/")
        if response.status_code == 200:
            data = response.json()
            if "available_endpoints" in data:
                print("Available endpoints:")
                for route in data["available_endpoints"]:
                    print(f"  {route['path']} - {', '.join(route['methods'])}")
    except Exception as e:
        print(f"Error: {e}")

    # Test IPFS add endpoint
    print("\nTesting IPFS add endpoint...")
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = b"Hello, MCP Server! Test content."
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Upload the file
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            response = requests.post(
                f"{API_URL}/ipfs/add",
                files=files
            )

        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Add response:")
            print(json.dumps(response.json(), indent=2))

            # Save the CID for further tests
            cid = response.json().get("cid") or response.json().get("Hash")
            if cid:
                print(f"Got CID: {cid}")

                # Try to retrieve the content
                print("\nTesting IPFS cat endpoint...")
                response = requests.get(f"{API_URL}/ipfs/cat/{cid}")
                print(f"Status code: {response.status_code}")
                if response.status_code == 200:
                    print(f"Retrieved content: {response.content}")

                # Try to pin the content
                print("\nTesting IPFS pin endpoint...")
                response = requests.post(
                    f"{API_URL}/ipfs/pin",
                    json={"cid": cid}
                )
                print(f"Status code: {response.status_code}")
                if response.status_code == 200:
                    print("Pin response:")
                    print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Test Files API (MFS)
    print("\nTesting Files API (MFS)...")
    try:
        # Try to create a directory
        print("Testing mkdir...")
        response = requests.post(
            f"{API_URL}/ipfs/files/mkdir",
            json={"path": "/test-dir", "parents": True}
        )
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Mkdir response:")
            print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # Test Block API
    print("\nTesting Block API...")
    if 'cid' in locals():
        try:
            # Try to get block stats
            print("Testing block/stat...")
            response = requests.get(
                f"{API_URL}/ipfs/block/stat",
                params={"cid": cid}
            )
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                print("Block stat response:")
                print(json.dumps(response.json(), indent=2))

            # Try to get block content
            print("Testing block/get...")
            response = requests.get(f"{API_URL}/ipfs/block/get/{cid}")
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                print(f"Block content: {response.content}")
        except Exception as e:
            print(f"Error: {e}")

    print("\nTests completed!")

if __name__ == "__main__":
    server_process = start_server()
    if server_process is not None:
        try:
            test_endpoints()
        finally:
            print("\nStopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
