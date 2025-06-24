#!/usr/bin/env python3
"""Simple script to test API endpoints"""

import requests
import json
import sys

# Define potential base URLs and prefixes to try
urls_to_try = [
    "http://localhost:9999/api/v0/mcp",
    "http://localhost:9999",
    "http://localhost:9999/api/v0",
    "http://localhost:9999/mcp"
]

# Try health endpoint
print("Testing health endpoints...")
for base_url in urls_to_try:
    try:
        health_url = f"{base_url}/health"
        print(f"Trying: {health_url}")
        response = requests.get(health_url)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Found working health endpoint at: {health_url}")
            print(f"Response: {response.text}")
            print("\nNow testing IPFS cat endpoint...")

            # Try the test CID
            test_cid = "QmTest123"
            cat_url = f"{base_url}/ipfs/cat/{test_cid}"
            print(f"Trying: {cat_url}")
            response = requests.get(cat_url)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:100] if response.status_code == 200 else response.text}")
    except Exception as e:
        print(f"Error: {e}")

print("\nDone testing API endpoints")
