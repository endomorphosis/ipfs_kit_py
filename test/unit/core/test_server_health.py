#!/usr/bin/env python3
"""Test script to check if the MCP server is running."""
import requests

try:
    response = requests.get("http://localhost:9999/api/v0/health", timeout=5)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
