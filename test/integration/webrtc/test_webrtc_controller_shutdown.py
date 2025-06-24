#!/usr/bin/env python3
"""
Test script for the WebRTC Controller shutdown functionality.

This script tests the enhanced WebRTC controller's shutdown procedure to verify
that resources are properly cleaned up during server shutdown.
"""

import os
import sys
import time
import asyncio
import signal
import logging
import argparse
import subprocess
import requests
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class WebRTCShutdownTester:
    """Test the WebRTC controller shutdown procedure."""

    def __init__(self, server_url: str = "http://localhost:9993", timeout: int = 30):
        """Initialize the WebRTC shutdown tester.

        Args:
            server_url: Base URL for the MCP server
            timeout: Timeout in seconds for operations
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def run_test(self) -> bool:
        """Run the shutdown test.

        Returns:
            True if the test passes, False otherwise
        """
        logger.info("Starting WebRTC controller shutdown test")

        try:
            # Check server connectivity
            self._check_server_connectivity()

            # Start a WebRTC server and make connections
            server_id = self._start_webrtc_server()
            if not server_id:
                logger.error("Failed to start WebRTC server")
                return False

            logger.info(f"Successfully started WebRTC server with ID: {server_id}")

            # Check WebRTC status
            webrtc_status = self._get_webrtc_status()
            logger.info(f"WebRTC status: {webrtc_status}")

            # Start a server process to test shutdown
            server_process = self._start_test_server()
            if not server_process:
                logger.error("Failed to start test server")
                return False

            logger.info(f"Started test server with PID: {server_process.pid}")

            # Give the server time to initialize
            time.sleep(5)

            # Verify server is running
            if not self._verify_test_server(server_process):
                logger.error("Test server verification failed")
                return False

            # Stop the server with SIGINT to trigger shutdown
            logger.info("Stopping server with SIGINT to test shutdown")
            server_process.send_signal(signal.SIGINT)

            # Wait for server to exit
            try:
                exit_code = server_process.wait(timeout=self.timeout)
                logger.info(f"Server exited with code: {exit_code}")

                if exit_code != 0:
                    logger.warning(f"Server exited with non-zero code: {exit_code}")

                # Check for any "coroutine was never awaited" warnings in the logs
                log_file = "mcp_anyio_test_server.log"
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        log_content = f.read()

                    if "coroutine was never awaited" in log_content:
                        logger.error("Found 'coroutine was never awaited' warnings in logs")
                        logger.error("WebRTC controller shutdown test FAILED")
                        return False

                logger.info("No coroutine warnings found - shutdown successful!")
                logger.info("WebRTC controller shutdown test PASSED")
                return True

            except subprocess.TimeoutExpired:
                logger.error(f"Server didn't exit within timeout ({self.timeout}s)")
                server_process.kill()
                logger.error("WebRTC controller shutdown test FAILED")
                return False

        except Exception as e:
            logger.error(f"Error during shutdown test: {e}")
            logger.error("WebRTC controller shutdown test FAILED")
            return False

    def _check_server_connectivity(self) -> bool:
        """Check connectivity to the MCP server.

        Returns:
            True if connected, False otherwise
        """
        try:
            response = self.session.get(f"{self.server_url}/api/v0/health", timeout=5)
            if response.status_code == 200:
                logger.info("Successfully connected to MCP server")
                return True
            else:
                logger.error(f"Server returned status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False

    def _start_webrtc_server(self) -> Optional[str]:
        """Start a WebRTC streaming server.

        Returns:
            Server ID if successful, None otherwise
        """
        try:
            # Use the benchmark endpoint to start a temporary server
            response = self.session.post(
                f"{self.server_url}/api/v0/webrtc/benchmark",
                json={"duration": 10, "resolution": "640x480"},
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success", False):
                    return data.get("server_id")
                else:
                    logger.error(f"Failed to start WebRTC server: {data.get('error', 'Unknown error')}")
                    return None
            else:
                logger.warning("Benchmark endpoint not available, trying to create server directly")

                # Try to start a server directly
                response = self.session.post(
                    f"{self.server_url}/api/v0/webrtc/stream",
                    json={"source": "test", "options": {"is_test": True}},
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success", False):
                        return data.get("server_id")
                    else:
                        logger.error(f"Failed to start WebRTC server: {data.get('error', 'Unknown error')}")
                        return None
                else:
                    logger.error(f"Failed to start WebRTC server: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error starting WebRTC server: {e}")
            return None

    def _get_webrtc_status(self) -> Dict[str, Any]:
        """Get WebRTC status.

        Returns:
            WebRTC status dictionary
        """
        try:
            response = self.session.get(
                f"{self.server_url}/api/v0/webrtc/status",
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get WebRTC status: {response.status_code}")
                return {"error": f"Status code: {response.status_code}"}
        except Exception as e:
            logger.warning(f"Error getting WebRTC status: {e}")
            return {"error": str(e)}

    def _start_test_server(self) -> Optional[subprocess.Popen]:
        """Start a test server for shutdown testing.

        Returns:
            Server process if successful, None otherwise
        """
        try:
            # Create a temporary script to run the server
            script_path = os.path.abspath("run_mcp_server_anyio_fixed.py")
            if not os.path.exists(script_path):
                logger.error(f"Server script not found: {script_path}")
                return None

            # Start the server process
            cmd = [
                sys.executable,
                script_path,
                "--port", "9994",  # Use different port for test
                "--debug",  # Enable debug mode for better logging
                "--log-file", "mcp_anyio_test_server.log"
            ]

            logger.info(f"Starting test server with command: {' '.join(cmd)}")

            # Start the process with stdout/stderr redirection
            server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            return server_process

        except Exception as e:
            logger.error(f"Error starting test server: {e}")
            return None

    def _verify_test_server(self, process: subprocess.Popen) -> bool:
        """Verify the test server is running.

        Args:
            process: Server process to verify

        Returns:
            True if running, False otherwise
        """
        try:
            # Check if the process is still running
            if process.poll() is not None:
                logger.error(f"Server process terminated prematurely with code: {process.returncode}")
                return False

            # Try connecting to the test server
            test_url = self.server_url.replace("9993", "9994")
            response = requests.get(f"{test_url}/api/v0/health", timeout=5)

            if response.status_code == 200:
                logger.info("Test server is running")
                return True
            else:
                logger.error(f"Test server returned unexpected status code: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error verifying test server: {e}")
            return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test WebRTC controller shutdown")
    parser.add_argument("--url", default="http://localhost:9993", help="Base URL for MCP server")
    parser.add_argument("--timeout", type=int, default=30, help="Operation timeout in seconds")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    # Create and run the tester
    tester = WebRTCShutdownTester(server_url=args.url, timeout=args.timeout)
    success = tester.run_test()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
