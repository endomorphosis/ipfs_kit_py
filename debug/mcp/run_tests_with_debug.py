#!/usr/bin/env python3
"""
Run tests with the MCP Debug Server for thread monitoring

This script will:
1. Start the MCP debug server
2. Run the specified test with the debug server enabled
3. Allow real-time monitoring via the dashboard

Usage:
    python mcp/run_tests_with_debug.py [--test TEST_PATH] [--port PORT]
"""
import os
import sys
import time
import argparse
import subprocess
import threading
import webbrowser
from pathlib import Path

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

def start_debug_server(port):
    """Start the MCP debug server in a separate process"""
    script_path = os.path.join(script_dir, "debug_server.py")
    return subprocess.Popen([sys.executable, script_path, "--port", str(port)])

def run_test(test_path, port):
    """Run the specified test with the debug server URL set"""
    env = os.environ.copy()
    env["MCP_DEBUG_URL"] = f"http://localhost:{port}"

    # Add some display so we know what's happening
    print(f"\n\n{'='*80}")
    print(f"Running test: {test_path}")
    print(f"MCP Debug Server: http://localhost:{port}/debug/dashboard")
    print(f"{'='*80}\n")

    # Run the test with pytest
    cmd = ["pytest", test_path, "-v"]
    return subprocess.run(cmd, env=env)

def open_dashboard(port, delay=2):
    """Open the debug dashboard in a browser after a delay"""
    def _open_browser():
        time.sleep(delay)  # Give server time to start
        webbrowser.open(f"http://localhost:{port}/debug/dashboard")

    thread = threading.Thread(target=_open_browser)
    thread.daemon = True
    thread.start()

def main():
    parser = argparse.ArgumentParser(description="Run tests with MCP debug server")
    parser.add_argument("--test", default="test/test_ipfs_dataloader.py::TestIPFSDataLoader::test_advanced_prefetch_thread_management",
                        help="Test path to run")
    parser.add_argument("--port", type=int, default=8765, help="Port for the debug server")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")

    args = parser.parse_args()

    # Start the debug server
    server_process = start_debug_server(args.port)

    try:
        # Open dashboard in browser
        if not args.no_browser:
            open_dashboard(args.port)

        # Wait a bit for server to start
        time.sleep(2)

        # Run the test
        result = run_test(args.test, args.port)

        # Keep server running if the test failed
        if result.returncode != 0:
            print(f"\n\nTest failed with exit code {result.returncode}")
            print("Debug server is still running at http://localhost:{args.port}/debug/dashboard")
            print("Press Ctrl+C to stop the server and exit")

            # Keep the script running until user interrupts
            while True:
                time.sleep(1)

        return result.returncode

    except KeyboardInterrupt:
        print("\nInterrupted by user. Shutting down...")
    finally:
        # Clean up the server process
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()

if __name__ == "__main__":
    sys.exit(main())
