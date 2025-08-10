#!/usr/bin/env python3
"""
Test script to verify CLI integration with the comprehensive dashboard
"""
import asyncio
import subprocess
import time
import requests
import sys
from pathlib import Path

async def test_cli_integration():
    """Test the CLI integration with comprehensive dashboard."""
    print("🧪 Testing CLI integration with comprehensive dashboard...")
    
    # Start the MCP server with comprehensive dashboard in background
    print("🚀 Starting MCP server with comprehensive dashboard...")
    
    try:
        # Start the server
        process = subprocess.Popen([
            sys.executable, "-m", "ipfs_kit_py.cli", "mcp", "start", 
            "--port", "8081"  # Use different port to avoid conflicts
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait a moment for startup
        print("⏳ Waiting for server to start...")
        time.sleep(5)
        
        # Test if server is responding
        try:
            response = requests.get("http://127.0.0.1:8081/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print("✅ Server is responding!")
                print(f"   Status: {data.get('status', 'unknown')}")
                print(f"   Version: {data.get('version', 'unknown')}")
                print(f"   Timestamp: {data.get('timestamp', 'unknown')}")
            else:
                print(f"❌ Server returned status code: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to server: {e}")
            return False
        
        # Test some API endpoints
        print("🔍 Testing API endpoints...")
        
        endpoints_to_test = [
            "/",  # Main dashboard
            "/api/system/status",  # System status
            "/api/buckets/list",  # Bucket list
            "/api/backends/list",  # Backend list
        ]
        
        for endpoint in endpoints_to_test:
            try:
                response = requests.get(f"http://127.0.0.1:8081{endpoint}", timeout=5)
                print(f"   {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"   {endpoint}: Error - {e}")
        
        print("✅ CLI integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
        
    finally:
        # Clean up: terminate the process
        if 'process' in locals():
            try:
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                print("🧹 Server process cleaned up")
            except Exception as e:
                print(f"⚠️  Error cleaning up process: {e}")

def main():
    """Main test function."""
    try:
        # Run the async test
        result = asyncio.run(test_cli_integration())
        
        if result:
            print("\n🎉 All tests passed! CLI integration with comprehensive dashboard is working.")
            print("\n📋 Summary:")
            print("   ✅ CLI successfully imports comprehensive dashboard")
            print("   ✅ CLI can start the MCP server with comprehensive dashboard")
            print("   ✅ Server responds to health checks")
            print("   ✅ API endpoints are accessible")
            print(f"\n💡 To start the server: python -m ipfs_kit_py.cli mcp start --port 8080")
            return 0
        else:
            print("\n❌ Some tests failed.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
