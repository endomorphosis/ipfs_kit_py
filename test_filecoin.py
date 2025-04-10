#!/usr/bin/env python3
"""
Test script specifically for the Filecoin/Lotus integration in the MCP server.
"""

import requests
import json
import time
import sys

# Configuration
MCP_URL = "http://127.0.0.1:9999"

def test_filecoin_status():
    """Test the status of Filecoin integration."""
    print("Testing Filecoin status...")
    
    try:
        # First try the direct status endpoint
        response = requests.get(f"{MCP_URL}/api/v0/mcp/storage/filecoin/status")
        print(f"Direct status endpoint response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
            
        # Try alternate endpoints that might exist
        alt_endpoints = [
            "/api/v0/mcp/filecoin/status",
            "/api/v0/mcp/storage/filecoin/info",
            "/api/v0/mcp/lotus/status"
        ]
        
        for endpoint in alt_endpoints:
            try:
                response = requests.get(f"{MCP_URL}{endpoint}")
                print(f"\nAlternate endpoint {endpoint} response ({response.status_code}):")
                if response.status_code == 200:
                    print(json.dumps(response.json(), indent=2))
                else:
                    print(response.text)
            except Exception as e:
                print(f"Error accessing {endpoint}: {e}")
        
        # Check if Lotus daemon is running via daemon status endpoint
        response = requests.get(f"{MCP_URL}/api/v0/mcp/daemon/status")
        if response.status_code == 200:
            daemon_data = response.json()
            print("\nDaemon status contains Lotus info:")
            if "daemon_status" in daemon_data:
                for daemon, status in daemon_data["daemon_status"].items():
                    if "lotus" in daemon.lower():
                        print(f"Lotus daemon: {daemon}")
                        print(json.dumps(status, indent=2))
        
        # Check debug endpoint for Lotus info
        response = requests.get(f"{MCP_URL}/api/v0/mcp/debug")
        if response.status_code == 200:
            debug_data = response.json()
            print("\nDebug endpoint may contain Lotus info:")
            # Check for lotus in daemon_management section
            if "server_info" in debug_data and "daemon_management" in debug_data["server_info"]:
                daemon_mgmt = debug_data["server_info"]["daemon_management"]
                if "daemon_status" in daemon_mgmt:
                    for daemon, status in daemon_mgmt["daemon_status"].items():
                        if "lotus" in daemon.lower():
                            print(f"Lotus daemon from debug: {daemon}")
                            print(json.dumps(status, indent=2))
    
    except Exception as e:
        print(f"Error in Filecoin status test: {e}")

def test_start_lotus():
    """Try to start the Lotus daemon."""
    print("\nTrying to start Lotus daemon...")
    
    try:
        response = requests.post(f"{MCP_URL}/api/v0/mcp/daemon/start/lotus")
        print(f"Start Lotus response ({response.status_code}):")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(response.text)
    except Exception as e:
        print(f"Error starting Lotus daemon: {e}")

def test_lotus_integration():
    """Test Lotus integration options."""
    print("\nTesting Lotus integration...")
    
    try:
        # Check if there's a Lotus controller in OpenAPI docs
        response = requests.get(f"{MCP_URL}/openapi.json")
        if response.status_code == 200:
            openapi = response.json()
            lotus_paths = [path for path in openapi.get('paths', {}).keys() 
                          if '/lotus/' in path or '/filecoin/' in path]
            
            print(f"Found {len(lotus_paths)} Lotus/Filecoin-related paths:")
            for path in sorted(lotus_paths):
                print(f"  {path}")
                
            # Try each path that might provide useful info
            for path in lotus_paths:
                if any(method in path.lower() for method in ['delete', 'upload', 'create']):
                    continue  # Skip methods that might make changes
                    
                try:
                    print(f"\nTrying {path}...")
                    response = requests.get(f"{MCP_URL}{path}")
                    print(f"Response ({response.status_code}):")
                    if response.status_code == 200:
                        print(json.dumps(response.json(), indent=2))
                    else:
                        print(response.text)
                except Exception as e:
                    print(f"Error accessing {path}: {e}")
            
    except Exception as e:
        print(f"Error in Lotus integration test: {e}")

if __name__ == "__main__":
    print("=== Filecoin/Lotus Integration Tests ===\n")
    test_filecoin_status()
    
    # Uncomment to try starting the daemon
    #test_start_lotus()
    
    test_lotus_integration()
    print("\nTests completed.")