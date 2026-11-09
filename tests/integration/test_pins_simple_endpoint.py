import requests
import json

# Test the simplified pins endpoint
try:
    response = requests.get("http://localhost:9990/api/v0/mcp/cli/pins_simple")
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {str(e)}")