#!/usr/bin/env python3
"""
Simple server startup test
"""
import subprocess
import sys
import time
import requests

def main():
    print("🚀 Starting IPFS Kit MCP Server Test")
    
    # Start server in background
    print("Starting server...")
    try:
        process = subprocess.Popen([
            sys.executable, "final_mcp_server.py",
            "--port", "9998",
            "--host", "0.0.0.0"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for startup
        time.sleep(5)
        
        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get("http://localhost:9998/health", timeout=5)
        
        if response.status_code == 200:
            print("✅ Server is healthy!")
            
            # Test server info
            info_response = requests.get("http://localhost:9998/")
            if info_response.status_code == 200:
                data = info_response.json()
                print(f"✅ Server info: {data.get('registered_tools_count', 0)} tools registered")
                print("🎉 All tests passed!")
                
                # Clean up
                process.terminate()
                return 0
            else:
                print("❌ Server info endpoint failed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Clean up
    try:
        process.terminate()
    except:
        pass
        
    return 1

if __name__ == "__main__":
    sys.exit(main())
