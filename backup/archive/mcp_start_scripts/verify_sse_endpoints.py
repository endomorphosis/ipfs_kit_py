#!/usr/bin/env python3
"""
Verification script for SSE endpoints.

This script tests the Server-Sent Events (SSE) endpoints to ensure they are working properly.
"""

import os
import sys
import time
import json
import argparse
import requests
import threading
import socket

def test_sse_endpoint(base_url, endpoint, timeout=5):
    """
    Test an SSE endpoint to verify it's working properly.

    Args:
        base_url: Base URL of the MCP server
        endpoint: SSE endpoint to test
        timeout: Timeout in seconds

    Returns:
        Dictionary with test result
    """
    url = f"{base_url}{endpoint}"
    print(f"Testing SSE endpoint: {url}...")

    try:
        # Set up the SSE connection with a timeout
        session = requests.Session()
        response = session.get(url, stream=True, timeout=timeout)

        if response.status_code != 200:
            print(f"  Error: Unexpected status code {response.status_code}")
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Unexpected status code: {response.status_code}"
            }

        # Check headers for SSE content type
        content_type = response.headers.get('Content-Type', '')
        if 'text/event-stream' not in content_type:
            print(f"  Error: Unexpected content type {content_type}")
            response.close()
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Not an SSE stream. Content-Type: {content_type}"
            }

        # Try to read the first event
        print("  Waiting for initial 'connected' event...")
        line_count = 0
        event_data = None

        for line in response.iter_lines(decode_unicode=True):
            line_count += 1
            if line:
                print(f"  Received: {line}")
                if 'event: connected' in line:
                    # Found the connected event
                    print("  ✅ Found 'connected' event")
                elif line.startswith('data:'):
                    # Extract the data
                    try:
                        event_data = json.loads(line[5:])
                        print(f"  ✅ Parsed JSON data: {event_data}")
                        # If we've seen both event and data, we can stop
                        if 'status' in event_data and event_data['status'] == 'connected':
                            break
                    except json.JSONDecodeError:
                        print(f"  ⚠️ Warning: Could not parse event data as JSON: {line[5:]}")

            # If we've read more than 10 lines and haven't found what we need, something might be wrong
            if line_count > 10:
                break

        # Close the connection
        response.close()

        if event_data and 'status' in event_data and event_data['status'] == 'connected':
            print(f"  ✅ SSE endpoint is working correctly")
            return {
                "success": True,
                "status_code": response.status_code,
                "data_received": True,
                "event_data": event_data
            }
        else:
            print(f"  ❌ Did not receive expected SSE data")
            return {
                "success": False,
                "status_code": response.status_code,
                "data_received": False,
                "error": "Did not receive expected SSE data"
            }

    except requests.exceptions.Timeout:
        print(f"  ❌ Connection timed out after {timeout} seconds")
        return {
            "success": False,
            "error": f"Connection timed out after {timeout} seconds"
        }
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Request failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def main():
    """Run the verification script."""
    parser = argparse.ArgumentParser(description="Verify SSE endpoints on MCP server")
    parser.add_argument("--url", type=str, default="http://localhost:9994", help="Base URL of the MCP server")
    parser.add_argument("--timeout", type=int, default=3, help="Timeout in seconds")

    args = parser.parse_args()

    print(f"Verifying SSE endpoints at {args.url}...")

    # Test root SSE endpoint
    print("\n=== Testing root SSE endpoint ===")
    root_result = test_sse_endpoint(args.url, "/sse", args.timeout)

    # Test API prefixed SSE endpoint
    print("\n=== Testing API prefixed SSE endpoint ===")
    api_result = test_sse_endpoint(args.url, "/api/v0/sse", args.timeout)

    # Print summary
    print("\n=== Summary ===")
    print(f"Root SSE endpoint (/sse): {'✅ Working' if root_result.get('success', False) else '❌ Not working'}")
    print(f"API SSE endpoint (/api/v0/sse): {'✅ Working' if api_result.get('success', False) else '❌ Not working'}")

    # Exit with appropriate code
    if root_result.get('success', False) and api_result.get('success', False):
        print("\nAll SSE endpoints are working correctly! 🎉")
        sys.exit(0)
    else:
        print("\nSome SSE endpoints are not working correctly. 😢")
        sys.exit(1)

if __name__ == "__main__":
    main()
