#!/usr/bin/env python3
"""
Simple test script to verify that the health endpoint returns controller information.
"""

import json
import time
import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.server_anyio import MCPServer

# Create a server instance
server = MCPServer(debug_mode=True)

# Create FastAPI app
app = FastAPI()

# Register server with app
server.register_with_app(app, prefix="/mcp")

# Create test client
client = TestClient(app)

# Test the health endpoint
response = client.get("/mcp/health")
print(f"Status code: {response.status_code}")
data = response.json()
print(json.dumps(data, indent=2))

# Check if the data contains controller information
if "controllers" in data:
    print("\nControllers found in response:")
    for controller_name in data["controllers"]:
        print(f"- {controller_name}")
else:
    print("\nERROR: No controllers found in response!")

# Test without controllers (should still work)
print("\nTesting with empty controllers dictionary...")
server.controllers = {}
response = client.get("/mcp/health")
data = response.json()
print(f"Status code: {response.status_code}")
if "controllers" in data:
    print("SUCCESS: controllers key exists with empty dictionary")
else:
    print("ERROR: controllers key missing!")