#!/usr/bin/env python3
"""
Test script to verify that 'ipfs-kit mcp start' uses the refactored dashboard
with proper backend/services/buckets management tabs.
"""

import subprocess
import time
import requests
import signal
import sys
import socket


def _find_available_port(preferred: int = 8005) -> int:
    """Return a free TCP port, preferring the provided port if available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_dashboard_startup_check() -> bool:
    """Run the dashboard startup check.

    Returns a boolean so this file can still be executed as a script; pytest asserts it.
    """
    print("🔍 Testing MCP dashboard startup and management functionality...")
    
    # Start the MCP server in background
    print("🚀 Starting MCP server...")
    port = _find_available_port(8005)
    if port != 8005:
        print(f"⚠️  Port 8005 in use, using free port {port} for test")

    proc = subprocess.Popen([
        sys.executable, "-m", "ipfs_kit_py.cli", 
        "mcp", "start", "--port", str(port), "--host", "127.0.0.1"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    try:
        # Give server time to start
        print("⏳ Waiting for server to start...")
        deadline = time.time() + 30
        response = None
        last_error = None
        while time.time() < deadline:
            try:
                response = requests.get(f"http://127.0.0.1:{port}", timeout=5)
                break
            except requests.exceptions.RequestException as e:
                last_error = e
                time.sleep(1)
        
        # Test if server is running
        try:
            if response is None:
                raise requests.exceptions.RequestException(last_error)
            
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
                        api_response = requests.get(f"http://127.0.0.1:{port}{endpoint}", timeout=5)
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


def test_dashboard_startup():
    assert run_dashboard_startup_check()


def main():
    """Main test function."""
    print("=" * 60)
    print("🧪 MCP Dashboard Management Features Test")
    print("=" * 60)
    
    success = run_dashboard_startup_check()
    
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
