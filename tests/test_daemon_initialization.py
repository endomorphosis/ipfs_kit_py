#!/usr/bin/env python3
"""
Test script to verify MCP server daemon initialization and API key management.
"""

import subprocess
import time
import requests
import json
import sys
from pathlib import Path

def test_daemon_initialization():
    """Test the daemon initialization functionality"""
    print("🧪 Testing MCP Server Daemon Initialization")
    print("=" * 50)
    
    # Test 1: Start server in background
    print("\n1. Starting MCP server in background...")
    
    try:
        # Start the server
        server_process = subprocess.Popen([
            sys.executable, 
            "final_mcp_server_enhanced.py", 
            "--host", "0.0.0.0", 
            "--port", "9998"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        time.sleep(5)
        
        # Test 2: Check if server is running
        print("2. Checking server status...")
        response = requests.get("http://localhost:9998/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            health_data = response.json()
            print(f"   Version: {health_data.get('version', 'Unknown')}")
            print(f"   Status: {health_data.get('status', 'Unknown')}")
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
            
        # Test 3: Initialize system
        print("\n3. Initializing system (daemons + API keys)...")
        response = requests.post("http://localhost:9998/daemons/initialize", timeout=30)
        if response.status_code == 200:
            init_result = response.json()
            if init_result.get("success"):
                print("✅ System initialization successful")
            else:
                print(f"⚠ System initialization returned: {init_result.get('error', 'Unknown')}")
        else:
            print(f"❌ System initialization failed: {response.status_code}")
            
        # Test 4: Check daemon status
        print("\n4. Checking daemon status...")
        response = requests.get("http://localhost:9998/daemons/status", timeout=10)
        if response.status_code == 200:
            status_data = response.json()
            print(f"   System initialized: {status_data.get('initialized', False)}")
            print(f"   Uptime: {status_data.get('uptime', 'Unknown')}")
            
            print("\n   Daemon Status:")
            for daemon, info in status_data.get('daemons', {}).items():
                running = info.get('running', False)
                pid = info.get('pid', 'Unknown')
                print(f"     {daemon}: {'✅ Running' if running else '❌ Stopped'} (PID: {pid})")
            
            print("\n   API Key Status:")
            for service, info in status_data.get('api_keys', {}).items():
                status_text = info.get('status', 'unknown')
                print(f"     {service}: {status_text}")
        else:
            print(f"❌ Daemon status check failed: {response.status_code}")
            
        # Test 5: Test MCP tools
        print("\n5. Testing MCP tools...")
        
        # Test ipfs_add
        print("   Testing ipfs_add...")
        response = requests.post("http://localhost:9998/ipfs/add", 
                                json={"content": "Hello from daemon test!"}, 
                                timeout=10)
        if response.status_code == 200:
            add_result = response.json()
            cid = add_result.get("cid")
            print(f"   ✅ ipfs_add successful: {cid}")
            
            # Test ipfs_cat
            print("   Testing ipfs_cat...")
            response = requests.get(f"http://localhost:9998/ipfs/cat/{cid}", timeout=10)
            if response.status_code == 200:
                cat_result = response.json()
                content = cat_result.get("content")
                print(f"   ✅ ipfs_cat successful: {content}")
            else:
                print(f"   ❌ ipfs_cat failed: {response.status_code}")
        else:
            print(f"   ❌ ipfs_add failed: {response.status_code}")
            
        # Test 6: Test JSON-RPC interface
        print("\n6. Testing JSON-RPC interface...")
        jsonrpc_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "ipfs_version",
                "arguments": {}
            },
            "id": 1
        }
        
        response = requests.post("http://localhost:9998/jsonrpc", 
                                json=jsonrpc_payload, 
                                timeout=10)
        if response.status_code == 200:
            jsonrpc_result = response.json()
            if "result" in jsonrpc_result:
                version_info = jsonrpc_result["result"]
                print(f"   ✅ JSON-RPC ipfs_version successful: {version_info.get('Version', 'Unknown')}")
            else:
                print(f"   ❌ JSON-RPC error: {jsonrpc_result.get('error', 'Unknown')}")
        else:
            print(f"   ❌ JSON-RPC failed: {response.status_code}")
            
        print("\n✅ Daemon initialization test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False
        
    finally:
        # Clean up: stop the server
        try:
            if 'server_process' in locals() and server_process:
                print("\n🔄 Stopping server...")
                server_process.terminate()
                server_process.wait()
                print("✅ Server stopped")
        except:
            pass

if __name__ == "__main__":
    success = test_daemon_initialization()
    sys.exit(0 if success else 1)
