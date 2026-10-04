#!/usr/bin/env python3
"""
Integration Test for Unified Observability MCP Server
====================================================

This script tests the integration of:
1. MCP server functionality
2. Dashboard backend monitoring
3. IPFS Kit integration
4. Virtual environment setup
5. Full observability features
"""

import sys
import json
import anyio
import aiohttp
import websockets
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

class UnifiedMCPServerTester:
    """Comprehensive tester for the unified MCP server."""
    
    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/mcp/ws"
        
    async def test_all(self):
        """Run all integration tests."""
        
        print("🧪 Starting Unified MCP Server Integration Tests")
        print("=" * 60)
        
        tests = [
            ("🌐 HTTP Server", self.test_http_server),
            ("🏥 Health Endpoint", self.test_health_endpoint),
            ("📊 Dashboard", self.test_dashboard),
            ("📈 Metrics", self.test_metrics),
            ("🔍 Observability", self.test_observability),
            ("🗄️ Backend Status", self.test_backend_status),
            ("📡 MCP HTTP Endpoint", self.test_mcp_http),
            ("🔌 MCP WebSocket", self.test_mcp_websocket),
            ("🛠️ MCP Tools", self.test_mcp_tools),
            ("📚 API Documentation", self.test_api_docs),
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n{test_name}")
            print("-" * 40)
            
            try:
                result = await test_func()
                if result:
                    print(f"✅ {test_name}: PASSED")
                    results[test_name] = "PASSED"
                else:
                    print(f"❌ {test_name}: FAILED")
                    results[test_name] = "FAILED"
            except Exception as e:
                print(f"❌ {test_name}: ERROR - {e}")
                results[test_name] = f"ERROR: {e}"
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in results.values() if r == "PASSED")
        total = len(results)
        
        for test_name, result in results.items():
            status_icon = "✅" if result == "PASSED" else "❌"
            print(f"{status_icon} {test_name}: {result}")
        
        print(f"\n📊 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 All tests passed! Server is fully functional.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return results
    
    async def test_http_server(self):
        """Test basic HTTP server connectivity."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        print("✓ Server responding")
                        print(f"✓ Status: {response.status}")
                        print(f"✓ Content-Type: {response.headers.get('content-type', 'unknown')}")
                        return True
                    else:
                        print(f"✗ Unexpected status: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    async def test_health_endpoint(self):
        """Test health endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Health status: {data.get('status', 'unknown')}")
                        print(f"✓ Health score: {data.get('health_score', 0):.1f}%")
                        print(f"✓ Uptime: {data.get('uptime_seconds', 0):.1f}s")
                        
                        components = data.get('components', {})
                        available = sum(1 for v in components.values() if v)
                        total = len(components)
                        print(f"✓ Components: {available}/{total} available")
                        
                        return True
                    else:
                        print(f"✗ Health check failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Health check error: {e}")
            return False
    
    async def test_dashboard(self):
        """Test dashboard endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/dashboard") as response:
                    if response.status == 200:
                        content = await response.text()
                        print("✓ Dashboard loads successfully")
                        print(f"✓ Content length: {len(content)} characters")
                        
                        # Check for key dashboard elements
                        checks = [
                            ("Unified IPFS Kit MCP Server", "Title present"),
                            ("System Health", "Health section present"),
                            ("Component Status", "Components section present"),
                            ("MCP Performance", "MCP metrics present")
                        ]
                        
                        for check_text, description in checks:
                            if check_text in content:
                                print(f"✓ {description}")
                            else:
                                print(f"✗ {description}")
                        
                        return True
                    else:
                        print(f"✗ Dashboard failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Dashboard error: {e}")
            return False
    
    async def test_metrics(self):
        """Test metrics endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/metrics") as response:
                    if response.status == 200:
                        content = await response.text()
                        print("✓ Metrics endpoint responding")
                        
                        # Check for key metrics
                        expected_metrics = [
                            "ipfs_kit_mcp_requests_total",
                            "ipfs_kit_mcp_uptime_seconds",
                            "ipfs_kit_health_score"
                        ]
                        
                        for metric in expected_metrics:
                            if metric in content:
                                print(f"✓ Metric present: {metric}")
                            else:
                                print(f"✗ Metric missing: {metric}")
                        
                        return True
                    else:
                        print(f"✗ Metrics failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Metrics error: {e}")
            return False
    
    async def test_observability(self):
        """Test observability endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/observability") as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✓ Observability data available")
                        
                        # Check data structure
                        expected_keys = ["server_state", "components", "health_score", "system_info"]
                        for key in expected_keys:
                            if key in data:
                                print(f"✓ Data section present: {key}")
                            else:
                                print(f"✗ Data section missing: {key}")
                        
                        if "system_info" in data:
                            system_info = data["system_info"]
                            print(f"✓ Platform: {system_info.get('platform', 'unknown')}")
                            print(f"✓ Python: {system_info.get('python_version', 'unknown')}")
                        
                        return True
                    else:
                        print(f"✗ Observability failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Observability error: {e}")
            return False
    
    async def test_backend_status(self):
        """Test backend status endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/dashboard/api/backends") as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Backend monitoring available: {data.get('success', False)}")
                        
                        if data.get("success"):
                            status = data.get("status", {})
                            backends = status.get("backends", {})
                            print(f"✓ Backends detected: {len(backends)}")
                            
                            for name, backend in backends.items():
                                backend_status = backend.get("status", "unknown")
                                print(f"  - {name}: {backend_status}")
                        else:
                            print(f"⚠️  Backend monitoring error: {data.get('error', 'unknown')}")
                        
                        return True
                    else:
                        print(f"✗ Backend status failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Backend status error: {e}")
            return False
    
    async def test_mcp_http(self):
        """Test MCP HTTP endpoint."""
        try:
            # Test tools list
            tools_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/mcp",
                    json=tools_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✓ MCP HTTP endpoint responding")
                        
                        if "result" in data and "tools" in data["result"]:
                            tools = data["result"]["tools"]
                            print(f"✓ Tools available: {len(tools)}")
                            
                            for tool in tools[:3]:  # Show first 3 tools
                                print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', '')[:50]}...")
                        
                        return True
                    else:
                        print(f"✗ MCP HTTP failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ MCP HTTP error: {e}")
            return False
    
    async def test_mcp_websocket(self):
        """Test MCP WebSocket endpoint."""
        try:
            async with websockets.connect(self.ws_url) as websocket:
                print("✓ WebSocket connection established")
                
                # Send tools list request
                request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                }
                
                await websocket.send(json.dumps(request))
                with anyio.fail_after(5.0):
                    response = await websocket.recv()
                data = json.loads(response)
                
                print("✓ WebSocket communication successful")
                
                if "result" in data and "tools" in data["result"]:
                    tools_count = len(data["result"]["tools"])
                    print(f"✓ Tools received via WebSocket: {tools_count}")
                
                return True
                
        except TimeoutError:
            print("✗ WebSocket timeout")
            return False
        except Exception as e:
            print(f"✗ WebSocket error: {e}")
            return False
    
    async def test_mcp_tools(self):
        """Test MCP tool execution."""
        try:
            # Test system_health tool
            tool_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "system_health",
                    "arguments": {}
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/mcp",
                    json=tool_request,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✓ MCP tool execution successful")
                        
                        if "result" in data and "content" in data["result"]:
                            content = data["result"]["content"]
                            if content and len(content) > 0:
                                # Parse the tool result
                                tool_result = json.loads(content[0]["text"])
                                print(f"✓ Tool result received: {tool_result.get('status', 'unknown')}")
                                
                                if "health_score" in tool_result:
                                    print(f"✓ Health score: {tool_result['health_score']:.1f}%")
                        
                        return True
                    else:
                        print(f"✗ Tool execution failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ Tool execution error: {e}")
            return False
    
    async def test_api_docs(self):
        """Test API documentation endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/docs") as response:
                    if response.status == 200:
                        content = await response.text()
                        print("✓ API documentation available")
                        print(f"✓ Content length: {len(content)} characters")
                        
                        # Check for FastAPI docs elements
                        if "swagger" in content.lower() or "openapi" in content.lower():
                            print("✓ OpenAPI/Swagger documentation present")
                        
                        return True
                    else:
                        print(f"✗ API docs failed: {response.status}")
                        return False
        except Exception as e:
            print(f"✗ API docs error: {e}")
            return False


async def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Unified MCP Server Integration")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--wait", type=int, default=10, help="Wait time for server to start")
    
    args = parser.parse_args()
    
    print(f"🧪 Testing server at {args.host}:{args.port}")
    print(f"⏳ Waiting {args.wait} seconds for server to be ready...")
    
    # Wait for server to be ready
    await anyio.sleep(args.wait)
    
    tester = UnifiedMCPServerTester(args.host, args.port)
    results = await tester.test_all()
    
    # Exit with appropriate code
    passed = sum(1 for r in results.values() if r == "PASSED")
    total = len(results)
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} tests failed")
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
