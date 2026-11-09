#!/usr/bin/env python3
"""
Test script for MCP server resources/list functionality
"""

import subprocess
import json
import time

def test_mcp_resources():
    """Test the MCP server's resources/list method."""
    
    # Test requests
    test_requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
    ]
    
    print("Starting MCP server test...")
    
    # Start the MCP server
    process = subprocess.Popen(
        ['python3', 'mcp_stdio_server.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0
    )
    
    try:
        for i, request in enumerate(test_requests):
            print(f"\nSending request {i+1}: {request['method']}")
            
            # Send request
            request_json = json.dumps(request) + '\n'
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Read response with timeout
            time.sleep(0.5)  # Give server time to process
            
            # Try to read response
            try:
                response_line = process.stdout.readline()
                if response_line:
                    response = json.loads(response_line.strip())
                    print(f"Response: {json.dumps(response, indent=2)}")
                else:
                    print("No response received")
            except json.JSONDecodeError as e:
                print(f"Invalid JSON response: {e}")
            except Exception as e:
                print(f"Error reading response: {e}")
                
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            
        # Print any stderr output
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"\nServer stderr:\n{stderr_output}")

if __name__ == "__main__":
    test_mcp_resources()
