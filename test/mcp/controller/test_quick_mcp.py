#!/usr/bin/env python3
import requests
import json
import sys

def main():
    """Test the MCP server endpoints."""
    base_url = "http://localhost:9990/api/v0/mcp"

    try:
        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("Health endpoint responded with 200 OK")
            health_data = response.json()
            print(f"Server ID: {health_data.get('server_id')}")
            print(f"Status: {health_data.get('status')}")

            # Check if controllers are available
            controllers = health_data.get('controllers', {})
            available_controllers = [name for name, available in controllers.items() if available]
            print(f"Available controllers: {', '.join(available_controllers)}")
        else:
            print(f"Error: Health endpoint returned status code {response.status_code}")
            print(response.text)

        # Test storage status endpoint
        print("\nTesting storage status endpoint...")
        response = requests.get(f"{base_url}/storage/status")
        if response.status_code == 200:
            print("Storage status endpoint responded with 200 OK")
            status_data = response.json()
            print(f"Success: {status_data.get('success')}")

            # Check available backends
            backends = status_data.get('backends', {})
            available_backends = [name for name, info in backends.items()
                                 if info.get('available', False)]
            print(f"Available backends: {', '.join(available_backends) or 'None'}")

            # Check if this is the fallback implementation
            if status_data.get('fallback', False):
                print("WARNING: Using fallback storage status endpoint")
        else:
            print(f"Error: Storage status endpoint returned status code {response.status_code}")
            print(response.text)

        return 0
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to MCP server. Make sure it's running at http://localhost:9990")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
