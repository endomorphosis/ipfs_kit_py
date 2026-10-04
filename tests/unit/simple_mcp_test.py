#!/usr/bin/env python3
"""
Simple MCP Server Test
======================

A basic test to verify the MCP server starts and responds.
"""

import sys
import time
import subprocess
import requests

def test_server():
    print("🧪 Simple MCP Server Test")
    print("=" * 50)
    
    # Check if server file exists
    import os
    if not os.path.exists("final_mcp_server_enhanced.py"):
        print("❌ final_mcp_server_enhanced.py not found")
        return False
    
    print("✅ Server file found")
    
    # Try to start server
    print("🚀 Starting server...")
    try:
        # Kill any existing servers
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False, capture_output=True)
        time.sleep(1)
        
        # Start server
        server_proc = subprocess.Popen([
            sys.executable, "final_mcp_server_enhanced.py", 
            "--host", "0.0.0.0", "--port", "9998"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for startup
        print("⏳ Waiting for server to start...")
        for i in range(30):
            try:
                response = requests.get("http://localhost:9998/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Server started successfully!")
                    print(f"Health check: {response.json()}")
                    
                    # Test basic endpoint
                    try:
                        info_response = requests.get("http://localhost:9998/", timeout=2)
                        print(f"✅ Info endpoint: {info_response.status_code}")
                    except:
                        print("⚠️ Info endpoint failed")
                    
                    # Cleanup
                    server_proc.terminate()
                    try:
                        server_proc.wait(timeout=5)
                    except:
                        server_proc.kill()
                    
                    return True
            except:
                time.sleep(1)
        
        print("❌ Server failed to start within 30 seconds")
        server_proc.terminate()
        return False
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return False

if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)
