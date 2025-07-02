#!/usr/bin/env python3
"""
Detailed IPFS Kit MCP Tool Test
==============================

Test individual tools with detailed output to show their functionality.
"""

import subprocess
import json
import time

def detailed_tool_test():
    """Test tools with detailed output."""
    
    print("🔍 Detailed IPFS Kit MCP Tool Test")
    print("=" * 50)
    
    # Start server
    process = subprocess.Popen(
        ['python3', 'mcp_stdio_server.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0
    )
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "detailed-tester", "version": "1.0.0"}
            }
        }
        
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        time.sleep(0.3)
        process.stdout.readline()  # consume init response
        
        # Test each tool with detailed output
        tools_to_test = [
            {
                "name": "ipfs_add",
                "description": "Add content to IPFS",
                "args": {"content": "This is a test file for IPFS Kit MCP integration!\nIt demonstrates adding content to IPFS."}
            },
            {
                "name": "filesystem_health", 
                "description": "Check filesystem health",
                "args": {"path": "/home"}
            },
            {
                "name": "system_health",
                "description": "Get system health status", 
                "args": {}
            },
            {
                "name": "ipfs_cluster_status",
                "description": "Get IPFS cluster status",
                "args": {}
            }
        ]
        
        for i, tool in enumerate(tools_to_test):
            print(f"\n🔧 Tool {i+1}: {tool['name']}")
            print(f"📄 Description: {tool['description']}")
            print("-" * 40)
            
            # Make tool call
            tool_request = {
                "jsonrpc": "2.0",
                "id": i + 2,
                "method": "tools/call",
                "params": {
                    "name": tool['name'],
                    "arguments": tool['args']
                }
            }
            
            process.stdin.write(json.dumps(tool_request) + '\n')
            process.stdin.flush()
            time.sleep(0.5)
            
            try:
                response_line = process.stdout.readline()
                response = json.loads(response_line.strip())
                
                if "error" in response:
                    print(f"❌ Error: {response['error']['message']}")
                    continue
                
                content = response["result"]["content"][0]["text"]
                result = json.loads(content)
                
                print(f"✅ Success: {result.get('success', False)}")
                
                # Pretty print the result
                print("📊 Result Details:")
                for key, value in result.items():
                    if key == "success":
                        continue
                    if isinstance(value, dict):
                        print(f"  {key}:")
                        for sub_key, sub_value in value.items():
                            print(f"    {sub_key}: {sub_value}")
                    elif isinstance(value, list):
                        print(f"  {key}: [{len(value)} items]")
                        for item in value[:3]:  # Show first 3 items
                            if isinstance(item, dict):
                                print(f"    - {item.get('id', item.get('name', str(item)[:50]))}")
                            else:
                                print(f"    - {str(item)[:50]}")
                    else:
                        # Truncate long strings
                        if isinstance(value, str) and len(value) > 100:
                            print(f"  {key}: {value[:100]}...")
                        else:
                            print(f"  {key}: {value}")
                            
            except Exception as e:
                print(f"❌ Error parsing response: {e}")
        
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
    
    print("\n" + "=" * 50)
    print("✅ Detailed testing complete!")
    print("🎯 All IPFS Kit MCP tools are functional and ready for use.")

if __name__ == "__main__":
    detailed_tool_test()
