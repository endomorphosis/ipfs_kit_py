"""Test script to test the daemon status endpoint."""
import requests
import json
import time

SERVER_URL = "http://localhost:9999/api/v0/ipfs/daemon/status"

def test_daemon_status():
    """Test the daemon status endpoint."""
    print("Testing daemon status endpoint...")
    
    # Test with daemon_type parameter
    print("\n1. Testing with daemon_type=ipfs:")
    try:
        response = requests.post(
            SERVER_URL,
            json={"daemon_type": "ipfs"},
            timeout=10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request with daemon_type=ipfs worked!")
        else:
            print("❌ FAILED: Request with daemon_type=ipfs returned non-200 status code")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        # Try to get error details from response
        try:
            print(f"Response text: {response.text}")
        except:
            pass
    
    time.sleep(1)
    
    # Test without daemon_type parameter
    print("\n2. Testing without daemon_type parameter:")
    try:
        response = requests.post(
            SERVER_URL,
            json={},
            timeout=10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request without daemon_type parameter worked!")
        else:
            print("❌ FAILED: Request without daemon_type parameter returned non-200 status code")
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        # Try to get error details from response
        try:
            print(f"Response text: {response.text}")
        except:
            pass
    
    # Test healthcheck to verify server is running
    print("\n3. Testing server health endpoint:")
    try:
        response = requests.get(
            "http://localhost:9999/api/v0/health",
            timeout=5
        )
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("✅ SUCCESS: Server is running and healthy")
        else:
            print("❌ FAILED: Server health check failed")
    except Exception as e:
        print(f"❌ ERROR connecting to server: {str(e)}")
        # Try to get error details from response
        try:
            print(f"Response text: {response.text}")
        except:
            pass

if __name__ == "__main__":
    test_daemon_status()