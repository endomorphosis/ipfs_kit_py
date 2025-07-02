#!/usr/bin/env python3
"""
Test updated MCP server with resources support
"""

import subprocess
import json
import time

def test_resources_support():
    """Test the MCP server's resources support."""
    
    # Test requests
    test_requests = [
        {
            "jsonrpc": "2.0", 
            "id": 1, 
            "method": "initialize", 
            "params": {
                "protocolVersion": "2024-11-05", 
                "capabilities": {}, 
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        },
        {
            "jsonrpc": "2.0", 
            "id": 2, 
            "method": "resources/list", 
            "params": {}
        },
        {
            "jsonrpc": "2.0", 
            "id": 3, 
            "method": "resources/templates/list", 
            "params": {}
        },
        {
            "jsonrpc": "2.0", 
            "id": 4, 
            "method": "tools/list", 
            "params": {}
        }
    ]
    
    print("Testing MCP server with resources support...")
    
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
            print(f"\nTest {i+1}: {request['method']}")
            print("-" * 40)
            
            # Send request
            request_json = json.dumps(request) + '\n'
            process.stdin.write(request_json)
            process.stdin.flush()
            
            # Wait for response
            time.sleep(0.5)
            
            # Read response
            try:
                response_line = process.stdout.readline()
                if response_line:
                    response = json.loads(response_line.strip())
                    if "error" in response:
                        print(f"❌ ERROR: {response['error']}")
                    else:
                        print(f"✅ SUCCESS")
                        if request['method'] == 'initialize':
                            capabilities = response.get('result', {}).get('capabilities', {})
                            print(f"   Capabilities: {list(capabilities.keys())}")
                        elif request['method'] == 'resources/list':
                            resources = response.get('result', {}).get('resources', [])
                            print(f"   Resources count: {len(resources)}")
                        elif request['method'] == 'resources/templates/list':
                            templates = response.get('result', {}).get('resourceTemplates', [])
                            print(f"   Resource templates count: {len(templates)}")
                        elif request['method'] == 'tools/list':
                            tools = response.get('result', {}).get('tools', [])
                            print(f"   Tools count: {len(tools)}")
                else:
                    print("❌ No response received")
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON response: {e}")
            except Exception as e:
                print(f"❌ Error reading response: {e}")
                
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            
        # Print any stderr output for debugging
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"\n" + "="*50)
            print("Server stderr output:")
            print("="*50)
            print(stderr_output)

if __name__ == "__main__":
    test_resources_support()
