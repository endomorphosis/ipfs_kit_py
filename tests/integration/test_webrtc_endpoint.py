#!/usr/bin/env python3
"""
Test WebRTC dependency checking endpoint in the MCP server.
"""

import sys
import json
import requests

def test_webrtc_dependency_check(port=9999):
    """Test the WebRTC dependency checking endpoint."""
    url = f"http://localhost:{port}/api/v0/mcp/webrtc/check"
    print(f"Testing WebRTC dependency check at: {url}")
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("Successfully connected to WebRTC dependency check endpoint!")
            data = response.json()
            print("\nResponse:")
            print(json.dumps(data, indent=2))
            
            print("\nWebRTC Availability:")
            print(f"- WebRTC available: {data.get('webrtc_available', False)}")
            
            if "dependencies" in data:
                print("\nDependency Status:")
                for dep, status in data.get("dependencies", {}).items():
                    print(f"- {dep}: {'✅' if status else '❌'}")
                    
            if "installation_command" in data:
                print(f"\nInstallation command: {data.get('installation_command')}")
                
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
    test_webrtc_dependency_check(port)