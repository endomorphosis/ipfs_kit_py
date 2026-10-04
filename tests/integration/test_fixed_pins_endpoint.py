import requests
import json

# Test the fixed pins endpoint on port 9991
try:
    response = requests.get("http://localhost:9991/api/v0/mcp/cli/pins")
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {str(e)}")
