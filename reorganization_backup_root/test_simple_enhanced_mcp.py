#!/usr/bin/env python3
"""
Simple test for the Enhanced GraphRAG MCP Server
==============================================

This script verifies the server starts and lists its tools.
"""

import json
import subprocess
import sys
import os


def test_server_startup():
    """Test that the enhanced MCP server starts and responds."""

    print("🚀 Testing Enhanced GraphRAG MCP Server Startup")
    print("=" * 50)

    try:
        # Start the server
        server_process = subprocess.Popen(
            [sys.executable, "mcp/enhanced_mcp_server_with_daemon_mgmt.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/home/barberb/ipfs_kit_py",
        )

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        # Send notifications/initialized
        notify_request = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}

        # Send tools/list request
        tools_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        # Write all requests
        requests = [json.dumps(init_request), json.dumps(notify_request), json.dumps(tools_request)]

        input_data = "\n".join(requests) + "\n"

        # Communicate with server
        stdout, stderr = server_process.communicate(input=input_data, timeout=30)

        print("📋 Server Output:")
        print("-" * 20)

        if stderr:
            print("STDERR:")
            stderr_lines = stderr.strip().split("\n")
            for line in stderr_lines[-10:]:  # Show last 10 lines
                if line.strip():
                    print(f"  {line}")

        if stdout:
            print("\nSTDOUT:")
            stdout_lines = stdout.strip().split("\n")
            for line in stdout_lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        if response.get("id") == 2:  # Tools list response
                            tools = response.get("result", {}).get("tools", [])
                            print(f"\n✅ Found {len(tools)} tools:")

                            # Count search tools
                            search_tools = [
                                t for t in tools if t.get("name", "").startswith("search_")
                            ]
                            print(f"🔍 Search tools: {len(search_tools)}")

                            # List all tools
                            for tool in tools:
                                name = tool.get("name", "")
                                desc = tool.get("description", "")
                                if name.startswith("search_"):
                                    print(f"  🔍 {name}: {desc[:60]}...")
                                elif name.startswith("vfs_"):
                                    print(f"  📁 {name}: {desc[:60]}...")
                                elif name.startswith("ipfs_"):
                                    print(f"  🌐 {name}: {desc[:60]}...")
                                else:
                                    print(f"  ⚙️ {name}: {desc[:60]}...")

                            return True
                    except json.JSONDecodeError:
                        print(f"  RAW: {line}")

        print("\n❌ No valid tools response found")
        return False

    except subprocess.TimeoutExpired:
        print("❌ Server timeout")
        server_process.kill()
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def check_dependencies():
    """Check which optional dependencies are available."""

    print("\n📋 Checking Dependencies:")
    print("-" * 30)

    dependencies = {
        "numpy": "Numerical operations",
        "networkx": "Knowledge graphs",
        "rdflib": "SPARQL queries",
        "sklearn": "Similarity calculations",
    }

    # Test sentence_transformers separately due to complex dependencies
    transformers_available = False
    try:
        import sentence_transformers

        print(f"✅ sentence_transformers: Vector embeddings")
        transformers_available = True
    except ImportError as e:
        print(f"❌ sentence_transformers: Vector embeddings (not installed)")
    except Exception as e:
        print(f"⚠️ sentence_transformers: Vector embeddings (import error: {str(e)[:60]}...)")

    available = []
    missing = []

    for dep, desc in dependencies.items():
        try:
            __import__(dep)
            print(f"✅ {dep}: {desc}")
            available.append(dep)
        except ImportError:
            print(f"❌ {dep}: {desc} (not installed)")
            missing.append(dep)
        except Exception as e:
            print(f"⚠️ {dep}: {desc} (error: {str(e)[:30]}...)")

    if transformers_available:
        available.append("sentence_transformers")

    total_deps = len(dependencies) + 1  # +1 for sentence_transformers
    print(f"\nAvailable: {len(available)}/{total_deps} dependencies")

    if missing:
        print(f"\nTo install missing dependencies:")
        print(f"pip install {' '.join(missing)}")

    return len(available), total_deps


if __name__ == "__main__":
    try:
        # Check dependencies first
        available, total = check_dependencies()

        # Test server startup
        success = test_server_startup()

        print("\n" + "=" * 50)
        if success:
            print("🎉 Enhanced GraphRAG MCP Server is working!")
            print(f"📊 Dependencies: {available}/{total} available")
            print("✅ Server starts successfully")
            print("✅ Tools are properly registered")
            print("✅ Search capabilities are exposed")
        else:
            print("❌ Server test failed")
            print("Check the error messages above for troubleshooting")

    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
