#!/usr/bin/env python3
"""
Test WebRTC streaming endpoint in the MCP server.
"""

import sys
import json
import requests

def test_webrtc_streaming(port=9999):
    """Test the WebRTC streaming endpoint."""
    url = f"http://localhost:{port}/api/v0/mcp/webrtc/stream"
    print(f"Testing WebRTC streaming at: {url}")

    # Test CID - use a valid CID if you want to test with real content
    test_cid = "QmTest123"

    # Request data
    data = {
        "cid": test_cid,
        "address": "127.0.0.1",
        "port": 8080,
        "quality": "high",
        "ice_servers": [{"urls": ["stun:stun.l.google.com:19302"]}],
        "benchmark": True
    }

    try:
        # Make the POST request to start streaming
        response = requests.post(url, json=data)
        print(f"Response status: {response.status_code}")

        # Parse and print the response
        if response.status_code == 200:
            result = response.json()
            print("\nResponse:")
            print(json.dumps(result, indent=2))

            # Check for stream URL
            if result.get("success", False):
                print(f"\nStream started successfully!")
                print(f"Stream URL: {result.get('url')}")
                print(f"Server ID: {result.get('server_id')}")
            else:
                print(f"\nStream failed to start:")
                print(f"Error: {result.get('error')}")
                print(f"Error type: {result.get('error_type')}")

                # Check for dependency issues
                if "dependencies" in result:
                    print("\nDependency issues detected:")
                    for dep, status in result.get("dependencies", {}).items():
                        print(f"- {dep}: {'✅' if status else '❌'}")

            return True
        else:
            print(f"Error: Received status code {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        return False

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    test_webrtc_streaming(port)
