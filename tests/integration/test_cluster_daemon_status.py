"""Test the daemon status for IPFS cluster daemons."""
import requests
import json

# Base URL of the MCP server
BASE_URL = "http://127.0.0.1:9999"

# Test daemon status for ipfs_cluster_service
print("Testing daemon status for ipfs_cluster_service...")
try:
    response = requests.post(
        f"{BASE_URL}/api/v0/ipfs/daemon/status",
        json={"daemon_type": "ipfs_cluster_service"},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ Test passed for ipfs_cluster_service status check.")
    else:
        print(f"Error response: {response.text}")
        print("❌ Test failed: Endpoint returned non-200 status code.")
except Exception as e:
    print(f"❌ Error: {str(e)}")

# Test daemon status for ipfs_cluster_follow
print("\nTesting daemon status for ipfs_cluster_follow...")
try:
    response = requests.post(
        f"{BASE_URL}/api/v0/ipfs/daemon/status",
        json={"daemon_type": "ipfs_cluster_follow"},
        headers={"Content-Type": "application/json"}
    )
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ Test passed for ipfs_cluster_follow status check.")
    else:
        print(f"Error response: {response.text}")
        print("❌ Test failed: Endpoint returned non-200 status code.")
except Exception as e:
    print(f"❌ Error: {str(e)}")