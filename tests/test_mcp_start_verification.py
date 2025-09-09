#!/usr/bin/env python3
"""
Test script to verify that 'ipfs-kit mcp start' uses the refactored dashboard
with proper backend/services/buckets management tabs.
"""

import asyncio
import subprocess
import time
import requests
import signal
import sys


def test_dashboard_startup():
    """Test that the dashboard starts and serves the refactored version."""
    print("🔍 Testing MCP dashboard startup and management functionality...")
    
    # Start the MCP server in background
    print("🚀 Starting MCP server...")
    proc = subprocess.Popen([
        sys.executable, "-m", "ipfs_kit_py.cli", 
        "mcp", "start", "--port", "8005", "--host", "127.0.0.1"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    try:
        # Give server time to start
        print("⏳ Waiting for server to start...")
        time.sleep(10)
        
        # Test if server is running
        try:
            response = requests.get("http://127.0.0.1:8005", timeout=5)
            print(f"✅ Dashboard responded with status code: {response.status_code}")
            
            # Check if it's the refactored version (not migration notice)
            content = response.text
            if "Dashboard Migration Notice" in content:
                print("❌ Dashboard is showing migration notice - using old version")
                return False
            elif "Services Status" in content and "Storage Backends" in content and "Total Buckets" in content:
                print("✅ Dashboard shows management tabs for Services, Backends, and Buckets")
                
                # Test API endpoints
                api_tests = [
                    ("/api/services", "Services API"),
                    ("/api/backends", "Backends API"),
                    ("/api/buckets", "Buckets API"),
                    ("/api/system", "System API")
                ]
                
                for endpoint, name in api_tests:
                    try:
                        api_response = requests.get(f"http://127.0.0.1:8005{endpoint}", timeout=5)
                        if api_response.status_code == 200:
                            print(f"✅ {name} endpoint working")
                        else:
                            print(f"⚠️  {name} endpoint returned {api_response.status_code}")
                    except Exception as e:
                        print(f"❌ {name} endpoint failed: {e}")
                
                return True
            else:
                print("❌ Dashboard content doesn't show expected management tabs")
                print("Content preview:", content[:500])
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to connect to dashboard: {e}")
            return False
            
    finally:
        # Clean up - terminate the server
        print("🛑 Stopping MCP server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("✅ Server stopped")


def main():
    """Main test function."""
    print("=" * 60)
    print("🧪 MCP Dashboard Management Features Test")
    print("=" * 60)
    
    success = test_dashboard_startup()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ PASS: Dashboard properly shows management tabs")
        print("📋 Available management features:")
        print("   - Services Status & Management")
        print("   - Storage Backends Management") 
        print("   - Buckets Management")
        print("   - System Metrics & Status")
    else:
        print("❌ FAIL: Dashboard not showing expected management features")
        print("💡 The CLI should use the refactored dashboard with all management tabs")
    print("=" * 60)


if __name__ == "__main__":
    main()
