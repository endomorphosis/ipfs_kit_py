import requests
import json

def test_endpoint(url, params=None, json_data=None):
    try:
        # If this is a POST with JSON data, use json parameter
        if json_data:
            response = requests.post(url, json=json_data)
        else:
            response = requests.post(url, params=params)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        try:
            return response.json()
        except:
            return None

    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Base URL
base_url = 'http://localhost:8005/api/v0'

# Test DHT findpeer
print("\nTesting DHT findpeer")
test_endpoint(
    f'{base_url}/ipfs/dht/findpeer',
    {'peer_id': 'QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn'}
)

# Test DHT findprovs
print("\nTesting DHT findprovs")
test_endpoint(
    f'{base_url}/ipfs/dht/findprovs',
    {'cid': 'QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn'}
)

# Test files mkdir - using JSON body
print("\nTesting files mkdir with JSON body")
test_endpoint(
    f'{base_url}/ipfs/files/mkdir',
    json_data={
        'path': '/test_dir',
        'parents': True,
        'flush': True
    }
)

# Test files ls - using JSON body for long parameter
print("\nTesting files ls with JSON body including long parameter")
test_endpoint(
    f'{base_url}/ipfs/files/ls',
    json_data={
        'path': '/',
        'long': True
    }
)

# Test files stat with JSON body
print("\nTesting files stat with JSON body")
test_endpoint(
    f'{base_url}/ipfs/files/stat',
    json_data={
        'path': '/'
    }
)
