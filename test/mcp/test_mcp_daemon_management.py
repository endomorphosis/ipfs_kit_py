#!/usr/bin/env python3
"""
Script to test the MCP server's daemon management functionality.

This script makes HTTP requests to the MCP server to verify that
the daemon management endpoints are working correctly.
"""

import sys
import json
import time
import argparse
import requests
from pprint import pprint

def check_health(base_url):
    """Check the MCP server's health endpoint."""
    url = f"{base_url}/health"
    print(f"Checking health at {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print("Health check successful:")
        pprint(data)
        
        if "ipfs_daemon_running" in data:
            print(f"\nIPFS daemon status: {'Running' if data['ipfs_daemon_running'] else 'Not running'}")
        
        if "daemon_health_monitor_running" in data:
            print(f"Daemon monitor status: {'Running' if data['daemon_health_monitor_running'] else 'Not running'}")
            
        return data
        
    except Exception as e:
        print(f"Health check failed: {e}")
        return None

def get_daemon_status(base_url):
    """Get the status of all daemons."""
    url = f"{base_url}/daemon/status"
    print(f"Getting daemon status from {url}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print("Daemon status:")
        pprint(data)
        
        return data
        
    except Exception as e:
        print(f"Failed to get daemon status: {e}")
        return None

def toggle_daemon(base_url, daemon_type, action):
    """Start or stop a daemon."""
    url = f"{base_url}/daemon/{action}/{daemon_type}"
    print(f"{action.capitalize()}ing {daemon_type} daemon via {url}...")
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        data = response.json()
        
        print(f"Daemon {action} result:")
        pprint(data)
        
        return data
        
    except Exception as e:
        print(f"Failed to {action} daemon: {e}")
        return None

def toggle_monitor(base_url, action, check_interval=None):
    """Start or stop the daemon health monitor."""
    url = f"{base_url}/daemon/monitor/{action}"
    if action == "start" and check_interval:
        url += f"?check_interval={check_interval}"
        
    print(f"{action.capitalize()}ing daemon health monitor via {url}...")
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        data = response.json()
        
        print(f"Monitor {action} result:")
        pprint(data)
        
        return data
        
    except Exception as e:
        print(f"Failed to {action} monitor: {e}")
        return None

def main():
    """Main function to test daemon management functionality."""
    parser = argparse.ArgumentParser(description="Test MCP server daemon management")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v0/mcp",
                       help="Base URL for MCP server")
    parser.add_argument("--action", choices=["health", "status", "start", "stop", "monitor", "all"],
                       default="all", help="Action to perform")
    parser.add_argument("--daemon-type", choices=["ipfs", "ipfs_cluster_service", "ipfs_cluster_follow"],
                       default="ipfs", help="Daemon type to control")
    parser.add_argument("--check-interval", type=int, default=30,
                       help="Check interval for daemon monitor (seconds)")
    
    # Only parse args when running the script directly, not when imported by pytest
    
    if __name__ == "__main__":
    
        args = parser.parse_args()
    
    else:
    
        # When run under pytest, use default values
    
        args = parser.parse_args([])
    
    # Execute the requested action
    if args.action == "health" or args.action == "all":
        check_health(args.base_url)
        print()
        
    if args.action == "status" or args.action == "all":
        get_daemon_status(args.base_url)
        print()
        
    if args.action == "start" or args.action == "all":
        toggle_daemon(args.base_url, args.daemon_type, "start")
        print()
        
    if args.action == "stop":
        toggle_daemon(args.base_url, args.daemon_type, "stop")
        print()
        
    if args.action == "monitor" or args.action == "all":
        # Start the monitor
        toggle_monitor(args.base_url, "start", args.check_interval)
        print()
        
        if args.action == "all":
            # Wait a bit
            print("Waiting 3 seconds...")
            time.sleep(3)
            
            # Check status
            get_daemon_status(args.base_url)
            print()
            
            # Stop the monitor
            toggle_monitor(args.base_url, "stop")
            print()
            
    print("Tests completed")

if __name__ == "__main__":
    main()