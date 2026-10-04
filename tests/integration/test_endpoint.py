import requests
import json

try:
    # Test the libp2p health endpoint on port 8001
    response = requests.get("http://localhost:8001/api/v0/libp2p/health")
    print(f"Status code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"Error: {str(e)}")
