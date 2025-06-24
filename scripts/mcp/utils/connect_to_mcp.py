#!/usr/bin/env python3
"""
Simple script to connect to and interact with the MCP server.
"""

import requests
import json
import sys

# MCP server configuration
MCP_SERVER_URL = "http://localhost:9992"
API_PREFIX = "/api/v0"

def print_json(data):
    """Print JSON data in a readable format."""
    print(json.dumps(data, indent=2))

def get_server_info():
    """Get basic information about the MCP server."""
    response = requests.get(f"{MCP_SERVER_URL}/")
    return response.json()

def get_server_health():
    """Check the health of the MCP server."""
    response = requests.get(f"{MCP_SERVER_URL}{API_PREFIX}/health")
    return response.json()

def get_ipfs_version():
    """Get the IPFS version information."""
    response = requests.get(f"{MCP_SERVER_URL}{API_PREFIX}/ipfs/version")
    return response.json()

def get_daemon_status():
    """Get the status of the IPFS daemon."""
    response = requests.get(f"{MCP_SERVER_URL}{API_PREFIX}/daemon/status")
    return response.json()

def list_pins():
    """List pinned items."""
    response = requests.get(f"{MCP_SERVER_URL}{API_PREFIX}/ipfs/pin/ls")
    return response.json()

def list_available_methods():
    """List all available API methods."""
    # This is a custom endpoint we're assuming exists (common in MCP servers)
    response = requests.get(f"{MCP_SERVER_URL}{API_PREFIX}/available_methods")
    if response.status_code == 404:
        return {"error": "available_methods endpoint not found"}
    return response.json()

def main():
    """Main function to demonstrate MCP server connectivity."""
    print("\n=== Connecting to MCP Server ===")

    # Get basic server info
    print("\n>> Getting server information...")
    try:
        server_info = get_server_info()
        print_json(server_info)
    except Exception as e:
        print(f"Error getting server info: {e}")
        sys.exit(1)

    # Check server health
    print("\n>> Checking server health...")
    try:
        health_info = get_server_health()
        print_json(health_info)
    except Exception as e:
        print(f"Error checking server health: {e}")

    # Try to get IPFS version
    print("\n>> Getting IPFS version...")
    try:
        version_info = get_ipfs_version()
        print_json(version_info)
    except Exception as e:
        print(f"Error getting IPFS version: {e}")

    # Get daemon status
    print("\n>> Checking daemon status...")
    try:
        daemon_status = get_daemon_status()
        print_json(daemon_status)
    except Exception as e:
        print(f"Error checking daemon status: {e}")

    # List pins
    print("\n>> Listing pinned items...")
    try:
        pins = list_pins()
        print_json(pins)
    except Exception as e:
        print(f"Error listing pins: {e}")

    print("\n=== MCP Server Connection Test Complete ===")

if __name__ == "__main__":
    main()
