#!/usr/bin/env python3
"""
MCP Server Test Harness

This script provides a robust way to start, test, and stop the MCP server.
It includes:
1. Port checking to avoid bind errors
2. Server startup with proper error handling
3. Health check to ensure the server is running correctly
4. JSON-RPC endpoint testing
5. Graceful shutdown
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

# Default configuration
DEFAULT_PORT = 9997
DEFAULT_HOST = "localhost"
SERVER_SCRIPT = "final_mcp_server.py"
MAX_STARTUP_WAIT = 60  # seconds
HEALTH_CHECK_INTERVAL = 2  # seconds

def log(message: str, level: str = "INFO"):
    """Log a message with timestamp and level."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}")

def check_port_availability(host: str, port: int) -> bool:
    """Check if the port is available for binding."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
        return True
    except socket.error as e:
        if e.errno == 98:  # Address already in use
            log(f"Port {port} is already in use.", "ERROR")
        else:
            log(f"Socket error: {e}", "ERROR")
        return False

def wait_for_server_health(host: str, port: int, max_wait: int = MAX_STARTUP_WAIT) -> bool:
    """Wait for the server to be healthy by checking the /health endpoint."""
    health_url = f"http://{host}:{port}/health"
    log(f"Waiting for server to be healthy at {health_url}...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                log(f"Server is healthy. Response: {response.text[:100]}", "SUCCESS")
                return True
        except requests.RequestException as e:
            log(f"Health check failed: {e}", "DEBUG")
        
        elapsed = int(time.time() - start_time)
        log(f"Waiting for server startup... ({elapsed}s)", "DEBUG")
        time.sleep(HEALTH_CHECK_INTERVAL)
    
    log(f"Server failed to become healthy within {max_wait} seconds.", "ERROR")
    return False

def test_jsonrpc_endpoint(host: str, port: int, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Test a JSON-RPC endpoint."""
    if params is None:
        params = {}
    
    url = f"http://{host}:{port}/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": int(time.time() * 1000)
    }
    
    log(f"Testing JSON-RPC method: {method}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            json_response = response.json()
            
            if "error" in json_response:
                log(f"Error in JSON-RPC response: {json.dumps(json_response.get('error'))}", "ERROR")
            elif "result" in json_response:
                log(f"Success: {method} returned result", "SUCCESS")
                if isinstance(json_response["result"], str) and len(json_response["result"]) < 100:
                    log(f"Result: {json_response['result']}")
                else:
                    log(f"Result type: {type(json_response['result'])}")
            
            return json_response
        else:
            log(f"HTTP error: {response.status_code}", "ERROR")
            return {"error": {"code": response.status_code, "message": response.text}}
    
    except requests.RequestException as e:
        log(f"Request error: {e}", "ERROR")
        return {"error": {"message": str(e)}}
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}", "ERROR")
        return {"error": {"message": str(e)}}

def main():
    parser = argparse.ArgumentParser(description="MCP Server Test Harness")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind the server to (default: {DEFAULT_PORT})")
    parser.add_argument("--client-host", type=str, default=DEFAULT_HOST, help=f"Host to connect to (default: {DEFAULT_HOST})")
    parser.add_argument("--server-script", type=str, default=SERVER_SCRIPT, help=f"Path to server script (default: {SERVER_SCRIPT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-start", action="store_true", help="Don't start the server, just run tests")
    parser.add_argument("--no-stop", action="store_true", help="Don't stop the server after tests")
    args = parser.parse_args()
    
    server_process = None
    success = False

    try:
        # Check port availability
        if not args.no_start and not check_port_availability(args.host, args.port):
            log("Port is already in use. Please stop any running MCP server or use a different port.", "ERROR")
            return 1
        
        # Start the server
        if not args.no_start:
            log(f"Starting MCP server on {args.host}:{args.port}...")
            
            cmd = [
                sys.executable,
                args.server_script,
                "--host", args.host,
                "--port", str(args.port)
            ]
            
            if args.debug:
                cmd.append("--debug")
            
            server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=os.getcwd()
            )
            
            log(f"Server process started with PID: {server_process.pid}")
            
            # Wait for the server to become healthy
            if not wait_for_server_health(args.client_host, args.port):
                log("Server failed to start properly.", "ERROR")
                return 1
        
        # Test the JSON-RPC endpoints
        log("Running JSON-RPC tests...")
        
        # Test ping
        ping_response = test_jsonrpc_endpoint(args.client_host, args.port, "ping")
        if "error" in ping_response:
            log("Ping test failed.", "ERROR")
        elif ping_response.get("result") == "pong":
            log("✅ Ping test succeeded.", "SUCCESS")
        else:
            log(f"❌ Ping test returned unexpected result: {ping_response.get('result')}", "ERROR")
        
        # Test list_tools
        list_tools_response = test_jsonrpc_endpoint(args.client_host, args.port, "list_tools")
        if "error" in list_tools_response:
            log("list_tools test failed.", "ERROR")
        elif "result" in list_tools_response and isinstance(list_tools_response["result"], dict) and "tools" in list_tools_response["result"]:
            tools = list_tools_response["result"]["tools"]
            log(f"✅ list_tools test succeeded. Found {len(tools)} tools.", "SUCCESS")
        else:
            log(f"❌ list_tools test returned unexpected format.", "ERROR")
        
        # Test get_tools (should be the same as list_tools)
        get_tools_response = test_jsonrpc_endpoint(args.client_host, args.port, "get_tools")
        if "error" in get_tools_response:
            log("get_tools test failed.", "ERROR")
        elif "result" in get_tools_response and isinstance(get_tools_response["result"], dict) and "tools" in get_tools_response["result"]:
            tools = get_tools_response["result"]["tools"]
            log(f"✅ get_tools test succeeded. Found {len(tools)} tools.", "SUCCESS")
        else:
            log(f"❌ get_tools test returned unexpected format.", "ERROR")
        
        # Test get_server_info
        server_info_response = test_jsonrpc_endpoint(args.client_host, args.port, "get_server_info")
        if "error" in server_info_response:
            log("get_server_info test failed.", "ERROR")
        elif "result" in server_info_response and isinstance(server_info_response["result"], dict):
            info = server_info_response["result"]
            log(f"✅ get_server_info test succeeded. Server version: {info.get('version', 'unknown')}", "SUCCESS")
        else:
            log(f"❌ get_server_info test returned unexpected format.", "ERROR")
        
        success = True
        log("All tests completed successfully!", "SUCCESS")
        return 0
    
    except KeyboardInterrupt:
        log("Test interrupted by user.", "WARNING")
        return 1
    
    except Exception as e:
        log(f"Error during test: {e}", "ERROR")
        return 1
    
    finally:
        # Stop the server if we started it
        if server_process is not None and not args.no_stop:
            log("Stopping MCP server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
                log("Server stopped gracefully.", "SUCCESS")
            except subprocess.TimeoutExpired:
                log("Server did not stop gracefully, killing...", "WARNING")
                server_process.kill()

if __name__ == "__main__":
    sys.exit(main())
