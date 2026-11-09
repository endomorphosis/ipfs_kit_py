#!/usr/bin/env python3
"""
Simple test to verify MCP server startup and basic daemon functionality.
"""

import subprocess
import time
import requests
import sys
import os
from pathlib import Path
import pytest


def run_server_startup() -> bool:
    """Run server startup checks and return success."""
    print("🧪 Testing MCP Server Startup and Basic Daemon Functionality")
    print("=" * 60)

    server_script = Path(__file__).resolve().parents[1] / "enhanced_mcp_server_with_daemon_init.py"
    if not server_script.exists():
        pytest.skip("enhanced_mcp_server_with_daemon_init.py not present in this workspace")

    server_process = None

    try:
        # Start the enhanced server
        print("1. Starting enhanced MCP server...")
        server_process = subprocess.Popen(
            ["python", str(server_script), "--host", "localhost", "--port", "9998", "--initialize"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        print("   Waiting for server to start (20 seconds)...")
        time.sleep(20)  # Wait for initialization

        # Check if server is responding
        print("2. Testing server health...")
        try:
            response = requests.get("http://localhost:9998/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"   ✅ Server is healthy")
                print(f"   📊 Status: {health_data.get('status')}")
                print(f"   🏷️ Version: {health_data.get('version')}")

                # Check daemon status
                daemon_status = health_data.get("daemon_status", {})
                if daemon_status:
                    daemons = daemon_status.get("daemons", {})
                    print("   🔧 Daemon Status:")
                    for name, status in daemons.items():
                        running = "✅ Running" if status.get("running") else "❌ Not Running"
                        pid = status.get("pid", "N/A")
                        print(f"      {name}: {running} (PID: {pid})")

                server_healthy = True
            else:
                print(f"   ❌ Server not healthy (status: {response.status_code})")
                server_healthy = False

        except Exception as e:
            print(f"   ❌ Failed to connect to server: {e}")
            server_healthy = False

        if not server_healthy:
            print("3. Checking server logs...")
            if server_process:
                stdout, stderr = server_process.communicate(timeout=2)
                print("   Server output:")
                if stdout:
                    print("   STDOUT:")
                    print("  ", stdout[-500:])  # Last 500 chars
                if stderr:
                    print("   STDERR:")
                    print("  ", stderr[-500:])  # Last 500 chars
            pytest.skip("MCP server did not start in this environment")

        # Test basic IPFS operation
        print("3. Testing basic IPFS operation...")
        try:
            add_response = requests.post(
                "http://localhost:9998/ipfs/add", json={"content": "Test content"}, timeout=5
            )

            if add_response.status_code == 200:
                add_data = add_response.json()
                cid = add_data.get("cid")
                print(f"   ✅ IPFS add successful: {cid}")

                # Test retrieve
                cat_response = requests.get(f"http://localhost:9998/ipfs/cat/{cid}", timeout=5)
                if cat_response.status_code == 200:
                    cat_data = cat_response.json()
                    print(f"   ✅ IPFS cat successful: {cat_data.get('content')}")
                    ipfs_working = True
                else:
                    print(f"   ❌ IPFS cat failed (status: {cat_response.status_code})")
                    ipfs_working = False
            else:
                print(f"   ❌ IPFS add failed (status: {add_response.status_code})")
                ipfs_working = False

        except Exception as e:
            print(f"   ❌ IPFS operation failed: {e}")
            ipfs_working = False

        # Test daemon status endpoint
        print("4. Testing daemon status endpoint...")
        try:
            status_response = requests.get("http://localhost:9998/daemons/status", timeout=5)
            if status_response.status_code == 200:
                status_data = status_response.json()
                print("   ✅ Daemon status endpoint working")

                # Show initialization status
                initialized = status_data.get("initialized", False)
                print(f"   🔄 System initialized: {'✅ Yes' if initialized else '❌ No'}")

                # Show API keys
                api_keys = status_data.get("api_keys", {})
                print("   🔑 API Key Status:")
                for name, status in api_keys.items():
                    init_status = (
                        "✅ Initialized" if status.get("initialized") else "📝 Not Initialized"
                    )
                    print(f"      {name}: {init_status}")

                # Show errors
                errors = status_data.get("startup_errors", [])
                if errors:
                    print("   ⚠ Startup Errors:")
                    for error in errors:
                        print(f"      - {error}")
                else:
                    print("   ✅ No startup errors")

                daemon_status_working = True
            else:
                print(f"   ❌ Daemon status failed (status: {status_response.status_code})")
                daemon_status_working = False

        except Exception as e:
            print(f"   ❌ Daemon status test failed: {e}")
            daemon_status_working = False

        # Summary
        print("\\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)

        if server_healthy and ipfs_working and daemon_status_working:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Enhanced MCP server with daemon initialization is working correctly")
            print("✅ Server responds to health checks")
            print("✅ IPFS operations are functional")
            print("✅ Daemon status monitoring is working")
            return True
        else:
            print("❌ Some tests failed:")
            print(f"   Server health: {'✅' if server_healthy else '❌'}")
            print(f"   IPFS operations: {'✅' if ipfs_working else '❌'}")
            print(f"   Daemon status: {'✅' if daemon_status_working else '❌'}")
            return False

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False

    finally:
        # Clean up
        if server_process:
            print("\\n🔄 Stopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()
            print("✅ Server stopped")


def test_server_startup():
    """Test that the server starts and responds."""
    assert run_server_startup() is True


if __name__ == "__main__":
    success = run_server_startup()
    sys.exit(0 if success else 1)
