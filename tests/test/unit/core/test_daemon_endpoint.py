"""Test the daemon status endpoint."""
import requests
import json

# Base URL of the MCP server
BASE_URL = "http://127.0.0.1:9999"

# Test daemon status with parameter
print("Testing daemon status with parameter...")
try:
    response = requests.post(
        f"{BASE_URL}/api/v0/ipfs/daemon/status",
        json={"daemon_type": "ipfs"},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ Test passed! Daemon status endpoint works with parameter.")
    else:
        print(f"Error response: {response.text}")
        print("❌ Test failed: Endpoint returned non-200 status code.")
except Exception as e:
    print(f"❌ Error: {str(e)}")

# Test daemon status without parameter
print("\nTesting daemon status without parameter...")
try:
    response = requests.post(
        f"{BASE_URL}/api/v0/ipfs/daemon/status",
        json={},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ Test passed! Daemon status endpoint works without parameter.")
    else:
        print(f"Error response: {response.text}")
        print("❌ Test failed: Endpoint returned non-200 status code.")
except Exception as e:
    print(f"❌ Error: {str(e)}")