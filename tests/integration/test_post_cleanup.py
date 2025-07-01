#!/usr/bin/env python3
"""
Test MCP Server Functionality After Cleanup
"""

import os
import sys
import subprocess
import time
import json
from pathlib import Path

def test_server_from_new_location():
    """Test that the MCP server works from src/ directory"""
    print("🧪 Testing MCP server functionality after cleanup...")
    
    # Test the enhanced server from src/
    server_path = Path("src/final_mcp_server_enhanced.py")
    if not server_path.exists():
        print("❌ Enhanced server not found in src/")
        return False
    
    print(f"✅ Found server at: {server_path}")
    
    # Start the server
    print("🚀 Starting server...")
    try:
        # Kill any existing servers
        subprocess.run(["pkill", "-f", "final_mcp_server"], check=False)
        time.sleep(2)
        
        # Start server from src directory
        venv_python = Path.cwd() / ".venv" / "bin" / "python"
        cmd = [str(venv_python), str(server_path), "--host", "0.0.0.0", "--port", "9999"]
        
        with open("test_server_cleanup.log", "w") as log_file:
            server_proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
        
        # Wait for startup
        print("⏳ Waiting for server startup...")
        for i in range(15):
            try:
                result = subprocess.run([
                    "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                    "http://localhost:9999/health"
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0 and result.stdout == "200":
                    print("✅ Server started successfully!")
                    break
            except:
                pass
            time.sleep(1)
        else:
            print("❌ Server failed to start")
            server_proc.terminate()
            return False
        
        # Test basic functionality
        print("🔍 Testing basic endpoints...")
        
        # Test health endpoint
        result = subprocess.run([
            "curl", "-s", "http://localhost:9999/health"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Health endpoint working")
        else:
            print("❌ Health endpoint failed")
            server_proc.terminate()
            return False
        
        # Test IPFS add
        print("🔧 Testing IPFS functionality...")
        result = subprocess.run([
            "curl", "-s", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-d", '{"content": "Test after cleanup"}',
            "http://localhost:9999/ipfs/add"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            try:
                response = json.loads(result.stdout)
                if response.get("success"):
                    print("✅ IPFS add working")
                    print(f"   CID: {response.get('cid')}")
                else:
                    print("❌ IPFS add failed")
                    server_proc.terminate()
                    return False
            except:
                print("❌ IPFS add response invalid")
                server_proc.terminate()
                return False
        else:
            print("❌ IPFS add request failed")
            server_proc.terminate()
            return False
        
        # Stop server
        print("🛑 Stopping server...")
        server_proc.terminate()
        server_proc.wait(timeout=10)
        
        print("🎉 All tests passed! Server works perfectly from new location.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

def main():
    """Main test function"""
    print("🧹 Testing workspace after cleanup")
    print("=" * 50)
    
    # Check directory structure
    print("📁 Checking directory structure...")
    essential_dirs = ["src", "tests", "tools", "docs", "scripts", "docker", "config", "archive", "backup"]
    for dir_name in essential_dirs:
        if Path(dir_name).exists():
            print(f"✅ {dir_name}/ exists")
        else:
            print(f"❌ {dir_name}/ missing")
    
    print("\n" + "=" * 50)
    
    # Test server functionality
    if test_server_from_new_location():
        print("\n🎉 SUCCESS: Workspace cleanup complete and server fully functional!")
        return True
    else:
        print("\n❌ FAILURE: Server not working properly after cleanup")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
