#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_tests.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

#\!/usr/bin/env python
"""
Run all MCP server tests.

This script starts the MCP server and runs all the test scripts:
- Comprehensive MCP server test
- WebRTC functionality test
- Peer WebSocket functionality test

The script handles server startup and shutdown automatically.
"""

import argparse
import logging
import sys
import subprocess
import time
import os
import signal
import atexit
import tempfile
import json
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class MCPTestRunner:
    """MCP Server test runner that manages server process."""

    def __init__(self, server_cmd, host="localhost", port=9992, debug=False):
        """
        Initialize the test runner.

        Args:
            server_cmd: Command to start the MCP server
            host: Host to bind the server to
            port: Port to bind the server to
            debug: Whether to run in debug mode
        """
        self.server_cmd = server_cmd
        self.host = host
        self.port = port
        self.debug = debug
        self.server_process = None
        self.server_output_file = None
        self.results_file = tempfile.NamedTemporaryFile(
            mode='w+',
            suffix='.json',
            prefix='mcp_test_results_',
            delete=False
        )
        self.results_path = self.results_file.name
        self.results = {
            "overall": {
                "success": False,
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0
            },
            "tests": {}
        }

        # Register cleanup handler
        atexit.register(self.cleanup)

    def start_server(self):
        """Start the MCP server process."""
        logger.info(f"Starting MCP server on {self.host}:{self.port}...")

        # Create output file for server logs
        self.server_output_file = tempfile.NamedTemporaryFile(
            mode='w+',
            suffix='.log',
            prefix='mcp_server_',
            delete=False
        )

        # Start the MCP server with the run_mcp_server_anyio.py script
        cmd = ["python", "run_mcp_server_anyio.py", "--host", self.host, "--port", str(self.port), "--backend", "asyncio"]

        if self.debug:
            cmd.append("--debug")

        # Start server process
        logger.info(f"Running command: {' '.join(cmd)}")
        self.server_process = subprocess.Popen(
            cmd,
            stdout=self.server_output_file,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Wait for server to start
        logger.info(f"Waiting for server to start (PID: {self.server_process.pid})...")
        time.sleep(3)  # Wait a few seconds for server to initialize

        # Check if process is still running
        if self.server_process.poll() is not None:
            logger.error(f"Server process exited with code {self.server_process.returncode}")
            # Display server output
            with open(self.server_output_file.name, 'r') as f:
                logger.error(f"Server output:\n{f.read()}")
            return False

        # Check if server is responding
        try:
            import requests
            response = requests.get(f"http://{self.host}:{self.port}/api/v0/mcp/health")
            response.raise_for_status()
            logger.info("Server is running and responding to health checks")
            return True
        except Exception as e:
            logger.error(f"Server is not responding: {e}")
            return False

    def stop_server(self):
        """Stop the MCP server process."""
        if self.server_process:
            logger.info(f"Stopping MCP server (PID: {self.server_process.pid})...")

            # Try graceful shutdown first
            self.server_process.terminate()

            # Wait for process to terminate
            try:
                self.server_process.wait(timeout=5)
                logger.info("Server process terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if not terminating
                logger.warning("Server not responding to termination, sending SIGKILL")
                self.server_process.kill()
                self.server_process.wait()

            self.server_process = None

    def run_test(self, test_script, test_name, args=None):
        """
        Run a test script.

        Args:
            test_script: Path to test script
            test_name: Name of the test for reporting
            args: Additional arguments for the test script

        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"Running test: {test_name}")

        # Build command
        cmd = ["python", test_script, "--url", f"http://{self.host}:{self.port}"]

        # Add any additional arguments
        if args:
            cmd.extend(args)

        logger.info(f"Running command: {' '.join(cmd)}")

        # Run test process
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # Store test results
            test_passed = result.returncode == 0
            self.results["tests"][test_name] = {
                "success": test_passed,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

            # Update overall results
            self.results["overall"]["tests_run"] += 1
            if test_passed:
                self.results["overall"]["tests_passed"] += 1
                logger.info(f"✅ Test {test_name} passed")
            else:
                self.results["overall"]["tests_failed"] += 1
                logger.error(f"❌ Test {test_name} failed (code: {result.returncode})")
                logger.error(f"Error output: {result.stderr}")

            return test_passed

        except Exception as e:
            logger.error(f"Error running test {test_name}: {e}")

            # Store test results
            self.results["tests"][test_name] = {
                "success": False,
                "error": str(e)
            }

            # Update overall results
            self.results["overall"]["tests_run"] += 1
            self.results["overall"]["tests_failed"] += 1

            return False

    def run_all_tests(self):
        """Run all test scripts."""
        logger.info("Running all MCP server tests...")

        # Get script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Define test scripts
        tests = [
            {
                "script": os.path.join(script_dir, "test_mcp_comprehensive.py"),
                "name": "comprehensive_test"
            },
            {
                "script": os.path.join(script_dir, "test_mcp_webrtc.py"),
                "name": "webrtc_test"
            },
            {
                "script": os.path.join(script_dir, "test_mcp_features.py"),
                "name": "mcp_features_test",
                "args": ["--verbose"]  # Run with verbose output
            }
        ]

        # Check for optional peer websocket test
        peer_websocket_script = os.path.join(script_dir, "test_mcp_peer_websocket.py")
        if os.path.exists(peer_websocket_script):
            tests.append({
                "script": peer_websocket_script,
                "name": "peer_websocket_test"
            })
        else:
            logger.warning(f"Peer WebSocket test script not found: {peer_websocket_script}")
            # Add a skipped test result
            self.results["tests"]["peer_websocket_test"] = {
                "success": False,
                "skipped": True,
                "error": "Test script not found"
            }

        # Run each test
        for test in tests:
            # Check if script exists
            if os.path.exists(test["script"]):
                # Extract test args if provided
                test_args = test.get("args", [])
                self.run_test(test["script"], test["name"], args=test_args)
            else:
                logger.warning(f"Test script not found: {test['script']}")
                # Add a skipped test result
                self.results["tests"][test["name"]] = {
                    "success": False,
                    "skipped": True,
                    "error": "Test script not found"
                }

        # Update overall success (only consider tests that weren't skipped)
        tests_executed = sum(1 for t in self.results["tests"].values() if not t.get("skipped", False))
        tests_passed = sum(1 for t in self.results["tests"].values() if t.get("success", False))

        self.results["overall"]["success"] = (
            tests_executed > 0 and tests_passed == tests_executed
        )

        # Save results
        self.save_results()

        return self.results["overall"]["success"]

    def save_results(self):
        """Save test results to file."""
        logger.info(f"Saving test results to {self.results_path}")

        with open(self.results_path, 'w') as f:
            json.dump(self.results, f, indent=2)

    def cleanup(self):
        """Clean up resources."""
        # Stop server if still running
        self.stop_server()

        # Close and remove output file
        if self.server_output_file:
            self.server_output_file.close()
            if os.path.exists(self.server_output_file.name):
                logger.info(f"Server log saved to: {self.server_output_file.name}")

        # Close results file
        if hasattr(self, 'results_file') and self.results_file:
            self.results_file.close()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run all MCP server tests")
    parser.add_argument(
        "--host",
        default="localhost",
        help="Host to bind the server to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9992,
        help="Port to bind the server to"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode"
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Don't start a server, just run tests against existing server"
    )
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()

    # Create test runner
    runner = MCPTestRunner(
        server_cmd="run_mcp_server_anyio.py",
        host=args.host,
        port=args.port,
        debug=args.debug
    )

    try:
        # Start server if needed
        if not args.no_server:
            if not runner.start_server():
                logger.error("Failed to start MCP server, aborting tests")
                return 1

        # Run all tests
        success = runner.run_all_tests()

        # Report results
        tests_run = runner.results["overall"]["tests_run"]
        tests_passed = runner.results["overall"]["tests_passed"]
        tests_failed = runner.results["overall"]["tests_failed"]

        logger.info(f"Test results: {tests_passed}/{tests_run} passed, {tests_failed} failed")
        logger.info(f"Detailed results saved to: {runner.results_path}")

        if success:
            logger.info("✅ All tests passed")
            return 0
        else:
            logger.error("❌ Some tests failed")
            return 1

    finally:
        # Clean up
        if not args.no_server:
            runner.stop_server()

if __name__ == "__main__":
    sys.exit(main())
