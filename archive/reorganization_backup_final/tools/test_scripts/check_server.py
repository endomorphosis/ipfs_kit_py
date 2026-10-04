#!/usr/bin/env python3
"""
Simple script to check if the MCP server is running and responsive.
This script can also list registered tools and attempt to start the server if it's not running.
"""

import sys
import os
import requests
import argparse
import time
import subprocess
import json
import signal
from typing import Dict, List, Any, Optional

def check_server(host="localhost", port=9998):
    """Check if the MCP server is running and responsive."""
    url = f"http://{host}:{port}/health"
    print(f"Checking server at {url}")
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"Server is running! Response: {response.json()}")
            return True
        else:
            print(f"Server returned status code {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"Connection refused. Server may not be running on {host}:{port}")
        return False
    except Exception as e:
        print(f"Error checking server: {e}")
        return False

def ping_jsonrpc(host="localhost", port=9998):
    """Send a ping to the server's JSON-RPC endpoint."""
    url = f"http://{host}:{port}/jsonrpc"
    print(f"Pinging JSON-RPC endpoint at {url}")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "ping",
        "params": {},
        "id": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "result" in data and data["result"] == "pong":
                print("Ping successful! Server responded with 'pong'")
                return True
            else:
                print(f"Unexpected response: {data}")
                return False
        else:
            print(f"Server returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"Error pinging server: {e}")
        return False

def list_tools(host="localhost", port=9998):
    """List all tools registered in the MCP server."""
    url = f"http://{host}:{port}/jsonrpc"
    print(f"Fetching tools from {url}")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "get_tools",
        "params": {},
        "id": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                tools = data["result"]
                print(f"Found {len(tools)} registered tools:")
                
                # Organize tools by category
                categories = {}
                for tool in tools:
                    # Extract category from tool name (assuming naming convention)
                    category = "unknown"
                    name = tool["name"]
                    
                    if name.startswith("ipfs_"):
                        category = "IPFS Tools"
                    elif name.startswith("fs_journal_"):
                        category = "Filesystem Journal Tools"
                    elif name.startswith("vfs_"):
                        category = "Virtual Filesystem Tools"
                    elif name.startswith("multi_backend_") or name.startswith("mbfs_"):
                        category = "Multi Backend Tools"
                    
                    if category not in categories:
                        categories[category] = []
                        
                    categories[category].append(tool)
                
                # Print tools by category
                for category, category_tools in categories.items():
                    print(f"\n{category} ({len(category_tools)}):")
                    for tool in category_tools:
                        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                        
                return True
            else:
                print(f"No tools found in response: {data}")
                return False
        else:
            print(f"Server returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"Error fetching tools: {e}")
        return False

def get_server_info(host="localhost", port=9998):
    """Get detailed server information."""
    url = f"http://{host}:{port}/jsonrpc"
    print(f"Fetching server information from {url}")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "get_server_info",
        "params": {},
        "id": int(time.time() * 1000)
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                info = data["result"]
                print("\nServer Information:")
                print(f"  Version:      {info.get('version', 'Unknown')}")
                print(f"  Uptime:       {info.get('uptime_seconds', 0):.2f} seconds")
                print(f"  Port:         {info.get('port', 'Unknown')}")
                print(f"  Tool Count:   {info.get('registered_tools', 0)}")
                print(f"  Categories:   {', '.join(info.get('registered_tool_categories', []))}")
                return True
            else:
                print(f"No server information in response: {data}")
                return False
        else:
            print(f"Server returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"Error fetching server information: {e}")
        return False

def start_server(host="0.0.0.0", port=9998):
    """Attempt to start the MCP server."""
    server_script = "final_mcp_server.py"
    if not os.path.exists(server_script):
        print(f"Error: Server script {server_script} not found")
        return False
        
    print(f"Attempting to start MCP server on {host}:{port}...")
    
    try:
        # Start server process in the background
        cmd = [
            sys.executable,
            server_script,
            "--host", host,
            "--port", str(port),
            "--debug"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=open("final_mcp_server.log", "w"),
            stderr=subprocess.STDOUT
        )
        
        # Save PID for future reference
        with open("final_mcp_server.pid", "w") as f:
            f.write(str(process.pid))
            
        print(f"Server process started with PID {process.pid}")
        print("Waiting for server to become responsive...")
        
        # Wait for server to become responsive
        for i in range(15):
            if check_server(host if host != "0.0.0.0" else "localhost", port):
                print("Server started successfully!")
                return True
                
            print(f"Waiting... ({i+1}/15)")
            time.sleep(2)
            
        print("Server did not become responsive within the timeout period")
        print("Check server logs in final_mcp_server.log for details")
        return False
    except Exception as e:
        print(f"Error starting server: {e}")
        return False

def stop_server():
    """Stop the MCP server if running."""
    if not os.path.exists("final_mcp_server.pid"):
        print("No PID file found, server may not be running")
        return False
        
    try:
        with open("final_mcp_server.pid", "r") as f:
            pid = int(f.read().strip())
            
        print(f"Attempting to stop server process with PID {pid}...")
        
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(5):
                try:
                    os.kill(pid, 0)  # Check if process exists
                    time.sleep(1)
                except OSError:
                    break  # Process is gone
            
            # If still running, force kill
            try:
                os.kill(pid, 0)
                print("Process did not terminate gracefully, force killing...")
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass  # Process is already gone
                
            # Clean up PID file
            os.unlink("final_mcp_server.pid")
            print("Server stopped successfully")
            return True
        except OSError as e:
            print(f"Error stopping server: {e}")
            # Clean up stale PID file
            os.unlink("final_mcp_server.pid")
            return False
    except Exception as e:
        print(f"Error reading PID file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and manage MCP server")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=9998, help="Server port (default: 9998)")
    parser.add_argument("--start", action="store_true", help="Start server if not running")
    parser.add_argument("--stop", action="store_true", help="Stop server if running")
    parser.add_argument("--restart", action="store_true", help="Restart the server")
    parser.add_argument("--list-tools", action="store_true", help="List all registered tools")
    parser.add_argument("--info", action="store_true", help="Get detailed server information")
    
    args = parser.parse_args()
    
    # Handle stop/restart before other operations
    if args.stop or args.restart:
        stop_server()
        if args.stop:
            sys.exit(0)
    
    # Start server if requested or as part of restart
    if args.start or args.restart:
        if not start_server("0.0.0.0", args.port):
            sys.exit(1)
    
    # Check server status
    server_running = check_server(args.host, args.port)
    
    # Only proceed with other operations if server is running
    if server_running:
        ping_jsonrpc(args.host, args.port)
        
        if args.list_tools:
            list_tools(args.host, args.port)
        
        if args.info:
            get_server_info(args.host, args.port)
    elif args.start or args.restart:
        print("Failed to verify server is running after start/restart attempt")
        sys.exit(1)
    
    if not server_running and not (args.start or args.restart or args.stop):
        print("\nTo start the server manually:")
        print(f"python3 final_mcp_server.py --host 0.0.0.0 --port {args.port} --debug")
        print("\nOr use this script with the --start option:")
        print(f"python3 {sys.argv[0]} --start --port {args.port}")
        sys.exit(1)
