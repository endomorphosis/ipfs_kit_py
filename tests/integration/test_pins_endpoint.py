import requests
import json

# Test the pins endpoint
try:
    # Check the server port
    response = requests.get("http://localhost:9990/api/v0/health")
    print(f"Health check on port 9990: {response.status_code}")
except Exception as e:
    print(f"Error on port 9990: {str(e)}")

try:
    response = requests.get("http://localhost:9991/api/v0/health")
    print(f"Health check on port 9991: {response.status_code}")
except Exception as e:
    print(f"Error on port 9991: {str(e)}")

# Use the port that's working
server_port = 9990
try:
    response = requests.get(f"http://localhost:{server_port}/api/v0/mcp/cli/pins")
    print(f"Status code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error connecting to http://localhost:{server_port}/api/v0/mcp/cli/pins: {str(e)}")

    # Try alternative port
    server_port = 9991
    try:
        response = requests.get(f"http://localhost:{server_port}/api/v0/mcp/cli/pins")
        print(f"Status code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error connecting to http://localhost:{server_port}/api/v0/mcp/cli/pins: {str(e)}")
