#!/usr/bin/env python3
"""
Debug VS Code JSON-RPC communication issues.

This script simulates what VS Code does when connecting to the JSON-RPC server.
"""

import requests
import json
import time
import sys

def simulate_initialize_request():
    """Simulate the initialize request that VS Code sends."""
    print("Simulating VS Code initialize request...")

    # Target the enhanced MCP server's JSON-RPC endpoint
    url = "http://localhost:9994/api/v0/jsonrpc"
    headers = {
        "Content-Type": "application/json",
    }

    # This payload mimics what VS Code sends
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "processId": 12345,  # Process ID of the client
            "clientInfo": {
                "name": "Visual Studio Code",
                "version": "1.82.0"
            },
            "rootPath": None,
            "rootUri": None,
            "capabilities": {
                "workspace": {
                    "applyEdit": True,
                    "workspaceEdit": {
                        "documentChanges": True,
                        "resourceOperations": ["create", "rename", "delete"],
                        "failureHandling": "textOnlyTransactional"
                    }
                },
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "willSave": True,
                        "willSaveWaitUntil": True,
                        "didSave": True
                    },
                    "completion": {
                        "dynamicRegistration": True,
                        "completionItem": {
                            "snippetSupport": True,
                            "commitCharactersSupport": True,
                            "documentationFormat": ["markdown", "plaintext"],
                            "deprecatedSupport": True,
                            "preselectSupport": True
                        },
                        "contextSupport": True
                    }
                }
            },
            "trace": "off"
        }
    }

    try:
        print(f"Sending request to {url}...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        print(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Response headers: {response.headers}")
            print(f"Response content type: {response.headers.get('Content-Type', 'Not specified')}")
            print(f"Response body: {json.dumps(result, indent=2)}")

            if "result" in result and "capabilities" in result["result"]:
                print("\n✅ SUCCESS: Server responded correctly to initialize request!")
                return True
            else:
                print("\n❌ ERROR: Server response doesn't contain expected capabilities.")
                return False
        else:
            print(f"\n❌ ERROR: Server returned status code {response.status_code}.")
            print(f"Response text: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Could not connect to {url}. Is the server running?")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request to {url} timed out after 10 seconds.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR: An error occurred while connecting to {url}: {e}")
        return False
    except json.JSONDecodeError:
        print(f"\n❌ ERROR: Server response is not valid JSON: {response.text}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: Unexpected error: {e}")
        return False

def check_sse_connection():
    """Check if we can connect to the SSE endpoint."""
    print("\nChecking SSE endpoint connection...")

    url = "http://localhost:9994/api/v0/sse"
    try:
        print(f"Connecting to {url}...")
        # We're using requests in a way that will capture headers but not wait for streaming data
        response = requests.get(url, stream=True, timeout=5)

        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")

        # Try to get the first data chunk
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                print(f"First chunk received: {chunk.decode('utf-8')}")
                break

        if response.status_code == 200:
            print("\n✅ SUCCESS: Successfully connected to SSE endpoint!")
            return True
        else:
            print(f"\n❌ ERROR: SSE endpoint returned status code {response.status_code}.")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Could not connect to {url}. Is the server running?")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request to {url} timed out after 5 seconds.")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: An error occurred while connecting to SSE endpoint: {e}")
        return False

def main():
    """Main entry point."""
    print("=== VS Code JSON-RPC Communication Debug Tool ===\n")

    jsonrpc_success = simulate_initialize_request()
    sse_success = check_sse_connection()

    print("\n=== Summary ===")
    print(f"JSON-RPC initialize request: {'✅ Passed' if jsonrpc_success else '❌ Failed'}")
    print(f"SSE connection: {'✅ Passed' if sse_success else '❌ Failed'}")

    if jsonrpc_success and sse_success:
        print("\n✅ SUCCESS: Both connections are working correctly!")
        print("If VS Code still can't connect, try restarting VS Code or checking extensions.")
        return 0
    else:
        print("\n❌ ERROR: One or more connections failed. See above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
