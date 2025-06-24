#!/usr/bin/env python3
"""
Manual test for the Aria2 MCP integration.

This test assumes that the Aria2 daemon has already been started
using start_aria2_daemon.py. It tests the API endpoints for
the Aria2 controller.

Usage:
  1. Start Aria2 daemon: python start_aria2_daemon.py
  2. Run this test: python test_mcp_aria2_manual.py
"""

import time
import requests
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# The MCP server URL - this will be started temporarily for testing
MCP_SERVER_URL = "http://localhost:9999/mcp"

def test_aria2_endpoints():
    """Test Aria2 endpoints using direct HTTP requests."""
    # First start the MCP server using subprocess
    import subprocess
    import os
    import signal

    logger.info("Starting MCP server for testing...")
    server_process = subprocess.Popen(
        ["python", "-c",
         "from fastapi import FastAPI; "
         "from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import; "
         "import uvicorn; "
         "app = FastAPI(); "
         "mcp_server = MCPServer(debug_mode=True); "
         "mcp_server.register_with_app(app, prefix='/mcp'); "
         "uvicorn.run(app, host='localhost', port=9999)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Give the server time to start
    time.sleep(2)

    try:
        # Test health endpoint
        logger.info("Testing Aria2 health endpoint...")
        response = requests.get(f"{MCP_SERVER_URL}/aria2/health")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Aria2 health: {data.get('status', 'unknown')}")
            if data.get('daemon_running', False):
                logger.info("Aria2 daemon is running")
            else:
                logger.warning("Aria2 daemon is not running - some tests will fail")
        else:
            logger.error(f"Health endpoint error: {response.status_code}")

        # Test version endpoint
        logger.info("Testing Aria2 version endpoint...")
        response = requests.get(f"{MCP_SERVER_URL}/aria2/version")
        if response.status_code == 200:
            data = response.json()
            version = data.get('version', {}).get('version', 'unknown')
            logger.info(f"Aria2 version: {version}")
        else:
            logger.error(f"Version endpoint error: {response.status_code}, {response.text}")

        # Test adding a download
        logger.info("Testing add URI endpoint...")
        test_data = {
            "uris": "https://example.com/",
            "filename": "example.html",
            "options": {
                "dir": "/tmp",
                "out": "example.html"
            }
        }
        response = requests.post(
            f"{MCP_SERVER_URL}/aria2/add",
            json=test_data
        )

        gid = None
        if response.status_code == 200:
            data = response.json()
            gid = data.get('gid')
            logger.info(f"Added download with GID: {gid}")

            # Test download status
            if gid:
                time.sleep(1)  # Give download time to start
                logger.info(f"Testing status endpoint for GID: {gid}")
                response = requests.get(f"{MCP_SERVER_URL}/aria2/status/{gid}")
                if response.status_code == 200:
                    status = response.json()
                    logger.info(f"Download status: {status.get('state', 'unknown')}")
                    logger.info(f"Progress: {status.get('completed_length', 0)}/{status.get('total_length', 0)}")
                else:
                    logger.error(f"Status endpoint error: {response.status_code}, {response.text}")

                # Test pause download
                logger.info(f"Testing pause endpoint for GID: {gid}")
                response = requests.post(
                    f"{MCP_SERVER_URL}/aria2/pause",
                    json={"gid": gid}
                )
                if response.status_code == 200:
                    logger.info("Download paused successfully")
                else:
                    logger.error(f"Pause endpoint error: {response.status_code}, {response.text}")

                # Test resume download
                logger.info(f"Testing resume endpoint for GID: {gid}")
                response = requests.post(
                    f"{MCP_SERVER_URL}/aria2/resume",
                    json={"gid": gid}
                )
                if response.status_code == 200:
                    logger.info("Download resumed successfully")
                else:
                    logger.error(f"Resume endpoint error: {response.status_code}, {response.text}")
        else:
            logger.error(f"Add URI endpoint error: {response.status_code}, {response.text}")

        # Test listing downloads
        logger.info("Testing list downloads endpoint...")
        response = requests.get(f"{MCP_SERVER_URL}/aria2/list")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Downloads found: {len(data.get('downloads', []))}")
        else:
            logger.error(f"List endpoint error: {response.status_code}, {response.text}")

        # Test global stats
        logger.info("Testing global stats endpoint...")
        response = requests.get(f"{MCP_SERVER_URL}/aria2/global-stats")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Download speed: {data.get('download_speed', 0)} bytes/sec")
            logger.info(f"Upload speed: {data.get('upload_speed', 0)} bytes/sec")
            logger.info(f"Active downloads: {data.get('num_active', 0)}")
        else:
            logger.error(f"Global stats endpoint error: {response.status_code}, {response.text}")

        # Test removing a download if we added one
        if gid:
            logger.info(f"Testing remove endpoint for GID: {gid}")
            response = requests.post(
                f"{MCP_SERVER_URL}/aria2/remove",
                json={"gid": gid}
            )
            if response.status_code == 200:
                logger.info("Download removed successfully")
            else:
                logger.error(f"Remove endpoint error: {response.status_code}, {response.text}")

    finally:
        # Kill the server
        logger.info("Stopping MCP server...")
        os.kill(server_process.pid, signal.SIGTERM)
        server_process.wait()

if __name__ == "__main__":
    test_aria2_endpoints()
