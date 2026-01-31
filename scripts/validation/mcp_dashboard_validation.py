#!/usr/bin/env python3
"""
MCP Dashboard Validation Script

This script validates that the MCP dashboard is working correctly
and the CI/CD changes haven't adversely affected functionality.
"""

import anyio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import subprocess

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


class MCPDashboardValidator:
    """Validates MCP Dashboard functionality"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8004):
        self.base_url = f"http://{host}:{port}"
        self.results: Dict[str, Any] = {
            "passed": [],
            "failed": [],
            "warnings": [],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def test_server_health(self) -> bool:
        """Test if the MCP server is responding"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/mcp/status", timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    self.results["passed"].append(
                        f"✅ MCP server is healthy (total_tools: {data.get('total_tools', 'unknown')})"
                    )
                    return True
                else:
                    self.results["failed"].append(
                        f"❌ MCP server returned status {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.results["failed"].append(f"❌ Cannot connect to MCP server: {e}")
            return False

    async def test_ui_accessible(self) -> bool:
        """Test if the UI is accessible"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, timeout=5.0)
                if response.status_code == 200:
                    content = response.text
                    if "IPFS Kit" in content and "MCP Dashboard" in content:
                        self.results["passed"].append("✅ UI is accessible and rendering")
                        return True
                    else:
                        self.results["warnings"].append(
                            "⚠️  UI accessible but content may be incomplete"
                        )
                        return True
                else:
                    self.results["failed"].append(
                        f"❌ UI returned status {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.results["failed"].append(f"❌ Cannot access UI: {e}")
            return False

    async def test_mcp_tools(self) -> bool:
        """Test MCP tools endpoint"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mcp/tools/list",
                    json={"jsonrpc": "2.0", "method": "list", "id": 1},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        tools = data["result"]
                        tool_count = len(tools) if isinstance(tools, list) else len(
                            tools.get("tools", [])
                        )
                        self.results["passed"].append(
                            f"✅ MCP tools endpoint working ({tool_count} tools)"
                        )
                        return True
                    else:
                        self.results["warnings"].append(
                            "⚠️  MCP tools endpoint returned unexpected format"
                        )
                        return True
                else:
                    self.results["failed"].append(
                        f"❌ MCP tools endpoint returned status {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.results["failed"].append(f"❌ MCP tools endpoint error: {e}")
            return False

    async def test_buckets_api(self) -> bool:
        """Test buckets API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mcp/tools/call",
                    json={
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "name": "list_buckets",
                            "arguments": {"include_metadata": True},
                        },
                        "id": 1,
                    },
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        self.results["passed"].append("✅ Buckets API is functional")
                        return True
                    else:
                        self.results["warnings"].append(
                            "⚠️  Buckets API returned unexpected format"
                        )
                        return True
                else:
                    self.results["failed"].append(
                        f"❌ Buckets API returned status {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.results["failed"].append(f"❌ Buckets API error: {e}")
            return False

    async def test_services_api(self) -> bool:
        """Test services API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/mcp/tools/call",
                    json={
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "name": "list_services",
                            "arguments": {"include_metadata": True},
                        },
                        "id": 1,
                    },
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        self.results["passed"].append("✅ Services API is functional")
                        return True
                    else:
                        self.results["warnings"].append(
                            "⚠️  Services API returned unexpected format"
                        )
                        return True
                else:
                    self.results["failed"].append(
                        f"❌ Services API returned status {response.status_code}"
                    )
                    return False
        except Exception as e:
            self.results["failed"].append(f"❌ Services API error: {e}")
            return False

    async def run_all_tests(self) -> bool:
        """Run all validation tests"""
        print(f"\n{'='*70}")
        print("MCP Dashboard Validation")
        print(f"{'='*70}\n")
        print(f"Testing MCP Dashboard at {self.base_url}")
        print(f"Timestamp: {self.results['timestamp']}\n")

        tests = [
            ("Server Health", self.test_server_health),
            ("UI Accessibility", self.test_ui_accessible),
            ("MCP Tools Endpoint", self.test_mcp_tools),
            ("Buckets API", self.test_buckets_api),
            ("Services API", self.test_services_api),
        ]

        all_passed = True
        for test_name, test_func in tests:
            print(f"Running: {test_name}...", end=" ")
            try:
                result = await test_func()
                if result:
                    print("✅ PASS")
                else:
                    print("❌ FAIL")
                    all_passed = False
            except Exception as e:
                print(f"❌ ERROR: {e}")
                all_passed = False

        return all_passed

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print("Test Summary")
        print(f"{'='*70}\n")

        if self.results["passed"]:
            print("✅ PASSED TESTS:")
            for test in self.results["passed"]:
                print(f"   {test}")
            print()

        if self.results["warnings"]:
            print("⚠️  WARNINGS:")
            for warning in self.results["warnings"]:
                print(f"   {warning}")
            print()

        if self.results["failed"]:
            print("❌ FAILED TESTS:")
            for test in self.results["failed"]:
                print(f"   {test}")
            print()

        total = (
            len(self.results["passed"])
            + len(self.results["warnings"])
            + len(self.results["failed"])
        )
        passed = len(self.results["passed"])
        failed = len(self.results["failed"])

        print(f"{'='*70}")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Warnings: {len(self.results['warnings'])}")
        print(f"Failed: {failed}")
        print(f"{'='*70}\n")

        if failed == 0:
            print("✅ ALL TESTS PASSED!")
            return True
        else:
            print("❌ SOME TESTS FAILED!")
            return False


async def main():
    """Main validation function"""
    validator = MCPDashboardValidator()

    # Run tests
    all_passed = await validator.run_all_tests()

    # Print summary
    success = validator.print_summary()

    # Save results to file
    output_dir = Path(__file__).parent.parent.parent / "data" / "test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "mcp_dashboard_validation.json"

    with open(output_file, "w") as f:
        json.dump(validator.results, f, indent=2)

    print(f"Results saved to: {output_file}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    anyio.run(main)
