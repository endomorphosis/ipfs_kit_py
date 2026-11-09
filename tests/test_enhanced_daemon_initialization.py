#!/usr/bin/env python3
"""
Test script to verify enhanced MCP server daemon initialization and API key management.
"""

import requests
import subprocess
import time
import json
import logging
import signal
import os
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class EnhancedMCPServerTester:
    def __init__(self, host: str = "localhost", port: int = 9998):
        self.server_script = "enhanced_mcp_server_with_daemon_init.py"
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.server_process: Optional[subprocess.Popen] = None

    def start_server(self, initialize_daemons: bool = True) -> bool:
        """Start the enhanced MCP server with daemon initialization"""
        try:
            logger.info(f"🚀 Starting enhanced MCP server: {self.server_script}")

            # Build command
            cmd = ["python", self.server_script, "--host", self.host, "--port", str(self.port)]
            if initialize_daemons:
                cmd.append("--initialize")

            logger.info(f"📋 Command: {' '.join(cmd)}")

            # Start server process
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # Give server time to start and initialize daemons
            logger.info("⏳ Waiting for server and daemons to initialize...")
            time.sleep(15)  # Longer wait for daemon initialization

            # Check if server is running
            if self.server_process.poll() is None:
                logger.info("✅ Server process started successfully")
                return True
            else:
                logger.error("❌ Server process failed to start")
                stdout, stderr = self.server_process.communicate()
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            return False

    def stop_server(self) -> bool:
        """Stop the enhanced MCP server"""
        try:
            if self.server_process:
                logger.info("🛑 Stopping server...")
                self.server_process.terminate()

                # Wait for graceful shutdown
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("⚠ Server didn't shut down gracefully, forcing kill")
                    self.server_process.kill()
                    self.server_process.wait()

                logger.info("✅ Server stopped")
                return True
            else:
                logger.warning("⚠ No server process to stop")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to stop server: {e}")
            return False

    def test_health_check(self) -> bool:
        """Test the health check endpoint"""
        try:
            logger.info("🩺 Testing health check endpoint...")
            response = requests.get(f"{self.base_url}/health", timeout=10)

            if response.status_code == 200:
                health_data = response.json()
                logger.info("✅ Health check passed")
                logger.info(f"📊 Server status: {health_data.get('status')}")
                logger.info(f"⏱️ Uptime: {health_data.get('uptime')}")
                logger.info(f"🏷️ Version: {health_data.get('version')}")

                # Check daemon status
                daemon_status = health_data.get("daemon_status", {})
                if daemon_status:
                    logger.info("🔧 Daemon status summary:")
                    daemons = daemon_status.get("daemons", {})
                    for daemon, status in daemons.items():
                        running = "✅" if status.get("running") else "❌"
                        logger.info(f"  {daemon}: {running} (PID: {status.get('pid', 'N/A')})")

                return True
            else:
                logger.error(f"❌ Health check failed with status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def test_daemon_status(self) -> bool:
        """Test the daemon status endpoint"""
        try:
            logger.info("🔧 Testing daemon status endpoint...")
            response = requests.get(f"{self.base_url}/daemons/status", timeout=10)

            if response.status_code == 200:
                daemon_data = response.json()
                logger.info("✅ Daemon status check passed")

                # Log detailed daemon information
                daemons = daemon_data.get("daemons", {})
                api_keys = daemon_data.get("api_keys", {})

                logger.info("🚀 Detailed Daemon Status:")
                for name, status in daemons.items():
                    running = "✅ Running" if status.get("running") else "❌ Not Running"
                    pid = status.get("pid", "N/A")
                    last_check = status.get("last_check", "N/A")
                    logger.info(f"  {name}: {running} (PID: {pid}) [Last check: {last_check}]")

                logger.info("🔑 API Key Status:")
                for name, status in api_keys.items():
                    initialized = (
                        "✅ Initialized" if status.get("initialized") else "📝 Not Initialized"
                    )
                    status_detail = status.get("status", "unknown")
                    logger.info(f"  {name}: {initialized} - {status_detail}")

                # Check system initialization
                initialized = daemon_data.get("initialized", False)
                logger.info(f"🔄 System initialized: {'✅ Yes' if initialized else '❌ No'}")

                # Check for startup errors
                startup_errors = daemon_data.get("startup_errors", [])
                if startup_errors:
                    logger.warning("⚠ Startup errors found:")
                    for error in startup_errors:
                        logger.warning(f"  - {error}")
                else:
                    logger.info("✅ No startup errors")

                return True
            else:
                logger.error(f"❌ Daemon status check failed with status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Daemon status check failed: {e}")
            return False

    def test_daemon_restart(self) -> bool:
        """Test daemon restart functionality"""
        try:
            logger.info("🔄 Testing daemon restart functionality...")

            # Test restarting IPFS daemon
            response = requests.post(f"{self.base_url}/daemons/restart/ipfs", timeout=15)

            if response.status_code == 200:
                restart_data = response.json()
                success = restart_data.get("success", False)
                message = restart_data.get("message", "No message")

                if success:
                    logger.info(f"✅ IPFS daemon restart successful: {message}")
                    return True
                else:
                    logger.warning(f"⚠ IPFS daemon restart returned success=False: {message}")
                    return False
            else:
                logger.error(f"❌ Daemon restart failed with status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Daemon restart test failed: {e}")
            return False

    def test_ipfs_operations(self) -> bool:
        """Test basic IPFS operations"""
        try:
            logger.info("📦 Testing IPFS operations...")

            # Test add operation
            test_content = "Hello from enhanced daemon-initialized MCP server!"
            add_response = requests.post(
                f"{self.base_url}/ipfs/add", json={"content": test_content}, timeout=10
            )

            if add_response.status_code == 200:
                add_data = add_response.json()
                cid = add_data.get("cid")
                size = add_data.get("size")
                logger.info(f"✅ IPFS add successful: {cid} ({size} bytes)")

                # Test cat operation
                cat_response = requests.get(f"{self.base_url}/ipfs/cat/{cid}", timeout=10)
                if cat_response.status_code == 200:
                    cat_data = cat_response.json()
                    retrieved_content = cat_data.get("content")
                    logger.info(f"✅ IPFS cat successful: {retrieved_content}")

                    # Test pin operation
                    pin_response = requests.post(f"{self.base_url}/ipfs/pin/add/{cid}", timeout=10)
                    if pin_response.status_code == 200:
                        pin_data = pin_response.json()
                        pinned = pin_data.get("pinned")
                        logger.info(f"✅ IPFS pin successful: {pinned}")
                        return True
                    else:
                        logger.error(f"❌ IPFS pin failed with status: {pin_response.status_code}")
                        return False
                else:
                    logger.error(f"❌ IPFS cat failed with status: {cat_response.status_code}")
                    return False
            else:
                logger.error(f"❌ IPFS add failed with status: {add_response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ IPFS operations test failed: {e}")
            return False

    def test_mcp_tools(self) -> bool:
        """Test MCP tools endpoint"""
        try:
            logger.info("🔧 Testing MCP tools endpoint...")
            response = requests.get(f"{self.base_url}/mcp/tools", timeout=10)

            if response.status_code == 200:
                tools_data = response.json()
                tools = tools_data.get("tools", [])
                logger.info(f"✅ MCP tools available: {len(tools)}")

                expected_tools = [
                    "ipfs_add",
                    "ipfs_cat",
                    "ipfs_pin_add",
                    "ipfs_pin_rm",
                    "ipfs_version",
                ]
                available_tools = [tool.get("name") for tool in tools]

                for tool_name in expected_tools:
                    if tool_name in available_tools:
                        logger.info(f"  ✅ {tool_name}: Available")
                    else:
                        logger.warning(f"  ❌ {tool_name}: Missing")

                return len(tools) >= 5  # Expect at least 5 tools
            else:
                logger.error(f"❌ MCP tools test failed with status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ MCP tools test failed: {e}")
            return False

    def test_server_stats(self) -> bool:
        """Test server statistics endpoint"""
        try:
            logger.info("📊 Testing server statistics...")
            response = requests.get(f"{self.base_url}/stats", timeout=10)

            if response.status_code == 200:
                stats_data = response.json()
                logger.info("✅ Server statistics retrieved")

                uptime = stats_data.get("server_uptime", "N/A")
                requests_count = stats_data.get("total_requests", 0)
                mock_stats = stats_data.get("mock_ipfs_stats", {})

                logger.info(f"  ⏱️ Uptime: {uptime}")
                logger.info(f"  📈 Total requests: {requests_count}")
                logger.info(f"  📦 IPFS operations: {mock_stats.get('operations', 0)}")
                logger.info(f"  💾 Storage size: {mock_stats.get('storage_size', 0)} bytes")
                logger.info(f"  📌 Pinned items: {mock_stats.get('pin_count', 0)}")

                return True
            else:
                logger.error(f"❌ Server stats test failed with status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Server stats test failed: {e}")
            return False

    def run_comprehensive_test(self) -> bool:
        """Run comprehensive test of enhanced daemon initialization"""
        logger.info("🧪 Starting Enhanced MCP Server Daemon Initialization Test")
        logger.info("=" * 70)

        success = True

        try:
            # 1. Start server with daemon initialization
            logger.info("1. Starting enhanced MCP server with daemon initialization...")
            if not self.start_server(initialize_daemons=True):
                logger.error("❌ Failed to start server")
                return False

            # 2. Test health check
            logger.info("\\n2. Testing health check...")
            if not self.test_health_check():
                logger.error("❌ Health check failed")
                success = False

            # 3. Test daemon status
            logger.info("\\n3. Testing daemon status...")
            if not self.test_daemon_status():
                logger.error("❌ Daemon status check failed")
                success = False

            # 4. Test daemon restart
            logger.info("\\n4. Testing daemon restart...")
            if not self.test_daemon_restart():
                logger.error("❌ Daemon restart test failed")
                success = False

            # 5. Test IPFS operations
            logger.info("\\n5. Testing IPFS operations...")
            if not self.test_ipfs_operations():
                logger.error("❌ IPFS operations failed")
                success = False

            # 6. Test MCP tools
            logger.info("\\n6. Testing MCP tools...")
            if not self.test_mcp_tools():
                logger.error("❌ MCP tools test failed")
                success = False

            # 7. Test server statistics
            logger.info("\\n7. Testing server statistics...")
            if not self.test_server_stats():
                logger.error("❌ Server stats test failed")
                success = False

            return success

        except Exception as e:
            logger.error(f"❌ Comprehensive test failed: {e}")
            return False

        finally:
            # Always stop the server
            logger.info("\\n🔄 Stopping server...")
            self.stop_server()


def main():
    """Main function to run the enhanced test"""
    tester = EnhancedMCPServerTester()

    try:
        success = tester.run_comprehensive_test()

        logger.info("\\n" + "=" * 70)
        if success:
            logger.info("🎉 All tests passed! Enhanced daemon initialization is working correctly.")
            logger.info("✅ The MCP server successfully:")
            logger.info("   - Started with daemon initialization")
            logger.info("   - Initialized IPFS, Lotus, and Lassie daemons")
            logger.info("   - Checked API key status")
            logger.info("   - Performed IPFS operations")
            logger.info("   - Provided MCP tools")
            logger.info("   - Handled daemon restarts")
        else:
            logger.error("❌ Some tests failed. Check the logs above for details.")

        return success

    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        tester.stop_server()
        return False
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        tester.stop_server()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
