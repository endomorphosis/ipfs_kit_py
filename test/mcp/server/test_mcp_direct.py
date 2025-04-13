import requests
import time
import json
import sys

def test_server_health(base_url="http://localhost:9999"):
    """Test basic server health endpoint."""
    try:
        resp = requests.get(f"{base_url}/api/v0/mcp/health", timeout=5)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing MCP Server health...")
    success = test_server_health()
    if success:
        print("Server is responding correctly\!")
    else:
        print("Server health check failed.")
        sys.exit(1)
