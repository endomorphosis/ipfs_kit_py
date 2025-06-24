#!/usr/bin/env python3
"""Test Hugging Face storage backend integration with MCP server."""

import json
import requests
import sys

# Configuration
MCP_URL = "http://127.0.0.1:9999"  # Using port 9999 as the server is running there

def test_huggingface_status():
    """Test the status of Hugging Face integration."""
    print("Testing Hugging Face status...")

    # First try the direct status endpoint
    response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/huggingface/status")
    print(f"Status response ({response.status_code}):")
    try:
        formatted = json.dumps(response.json(), indent=2)
        print(formatted)
    except:
        print(response.text)
    print()

def explore_huggingface_endpoints():
    """Explore available Hugging Face endpoints."""
    print("Exploring Hugging Face endpoints...")

    # Fetch OpenAPI documentation to see what paths are available
    response = requests.get(f"{MCP_URL}/openapi.json")
    if response.status_code == 200:
        api_doc = response.json()
        hf_paths = [path for path in api_doc["paths"].keys()
                  if ("hf" in path.lower() or "huggingface" in path.lower())
                  and path != "/api/v0/mcp/storage/huggingface/status"]

        print(f"Found {len(hf_paths)} Hugging Face-related paths:")
        for path in hf_paths:
            print(f"  {path}")
        print()

        # Test a few key endpoints
        if hf_paths:
            for path in hf_paths:
                # Only test GET endpoints for safety
                if "GET" in api_doc["paths"][path]:
                    print(f"Trying GET {path}...")
                    response = requests.get(f"{MCP_URL}{path}")
                    print(f"Response ({response.status_code}):")
                    try:
                        formatted = json.dumps(response.json(), indent=2)
                        print(formatted)
                    except:
                        print(response.text)
                    print()
    else:
        print("Failed to fetch OpenAPI documentation")
        print(response.text)
        print()

def test_huggingface_repo_operations():
    """Test Hugging Face repository operations if available."""
    print("Testing Hugging Face repository operations...")

    # List repos endpoint (common HF operation)
    repos_endpoint = f"{MCP_URL}/api/v0/mcp/storage/huggingface/repos"
    response = requests.get(repos_endpoint)

    print(f"List repos response ({response.status_code}):")
    try:
        formatted = json.dumps(response.json(), indent=2)
        print(formatted)
    except:
        print(response.text)
    print()

if __name__ == "__main__":
    print("=== Hugging Face Integration Tests ===\n")

    test_huggingface_status()
    explore_huggingface_endpoints()
    test_huggingface_repo_operations()

    print("Tests completed.")
