#!/usr/bin/env python
"""
Test script for the AnyIO-based MCP server.

This script tests the basic functionality of the AnyIO-based MCP server,
including both asyncio and trio backends.
"""

import anyio
import sys
import time
import json
import logging
import argparse
import subprocess
import anyio
import httpx

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_health_endpoint(client, base_url):
    """Test the health endpoint."""
    response = await client.get(f"{base_url}/health")
    if response.status_code == 200:
        logger.info("Health endpoint test: SUCCESS")
        return True
    else:
        logger.error(f"Health endpoint test: FAILED (Status code: {response.status_code})")
        return False

async def test_version_endpoint(client, base_url):
    """Test the CLI version endpoint."""
    response = await client.get(f"{base_url}/cli/version")
    if response.status_code == 200:
        logger.info("Version endpoint test: SUCCESS")
        data = response.json()
        logger.info(f"IPFS Kit version: {data.get('ipfs_kit_py_version', 'unknown')}")
        return True
    else:
        logger.error(f"Version endpoint test: FAILED (Status code: {response.status_code})")
        return False

async def test_pins_endpoint(client, base_url):
    """Test the CLI pins endpoint."""
    response = await client.get(f"{base_url}/cli/pins")
    if response.status_code == 200:
        logger.info("Pins endpoint test: SUCCESS")
        return True
    else:
        logger.error(f"Pins endpoint test: FAILED (Status code: {response.status_code})")
        return False

async def test_exists_endpoint(client, base_url):
    """Test the CLI exists endpoint with a well-known CID."""
    test_cid = "QmPK1s3pNYLi9ERiq3BDxKa4XosgWwFRQUydHUtz4YgpqB"  # IPFS logo
    response = await client.get(f"{base_url}/cli/exists/{test_cid}")
    if response.status_code == 200:
        logger.info("Exists endpoint test: SUCCESS")
        return True
    else:
        logger.error(f"Exists endpoint test: FAILED (Status code: {response.status_code})")
        return False

async def test_stats_endpoint(client, base_url):
    """Test the stats endpoint."""
    response = await client.get(f"{base_url}/ipfs/stats")
    if response.status_code == 200:
        logger.info("Stats endpoint test: SUCCESS")
        return True
    else:
        logger.error(f"Stats endpoint test: FAILED (Status code: {response.status_code})")
        return False

async def run_tests(backend, port):
    """Run all tests against the server."""
    base_url = f"http://localhost:{port}/api/v0/mcp"

    logger.info(f"Starting MCP server tests using {backend} backend on port {port}")

    # Start the server
    server_process = subprocess.Popen(
        [sys.executable, "run_mcp_server_anyio.py",
         "--port", str(port),
         "--backend", backend,
         "--debug",
         "--isolation"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give the server time to start
    logger.info("Waiting for server to start...")
    await anyio.sleep(5)

    # Check if server is running
    try:
        server_running = False
        retries = 0

        async with httpx.AsyncClient() as client:
            while not server_running and retries < 5:
                try:
                    response = await client.get(f"{base_url}/health")
                    if response.status_code == 200:
                        server_running = True
                        logger.info("Server is running")
                    else:
                        retries += 1
                        await anyio.sleep(2)
                except httpx.ConnectError:
                    retries += 1
                    logger.info(f"Server not ready, retrying ({retries}/5)...")
                    await anyio.sleep(2)

            if not server_running:
                logger.error("Failed to connect to server after multiple attempts")
                server_process.terminate()
                return False

            # Run the tests sequentially
            results = []
            results.append(await test_health_endpoint(client, base_url))
            results.append(await test_version_endpoint(client, base_url))
            results.append(await test_pins_endpoint(client, base_url))
            results.append(await test_exists_endpoint(client, base_url))
            results.append(await test_stats_endpoint(client, base_url))

            success = all(results)
    except Exception as e:
        logger.error(f"Test error: {e}")
        success = False
    finally:
        # Terminate the server
        logger.info("Terminating server process")
        try:
            server_process.terminate()
            server_process.wait(timeout=5)  # Wait for clean termination
        except subprocess.TimeoutExpired:
            logger.warning("Server didn't terminate cleanly, sending SIGKILL")
            server_process.kill()  # Force kill if it doesn't terminate cleanly

        # Get server output
        stdout, stderr = server_process.communicate()
        if stdout:
            logger.info(f"Server stdout: {stdout}")
        if stderr:
            logger.info(f"Server stderr: {stderr}")

    return success

async def main():
    """Run the tests with both asyncio and trio backends."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Test AnyIO-based MCP server")
    parser.add_argument("--asyncio-port", type=int, default=8101, help="Port for asyncio backend tests")
    parser.add_argument("--trio-port", type=int, default=8102, help="Port for trio backend tests")
    parser.add_argument("--backend", choices=["asyncio", "trio", "both"], default="both",
                        help="Which backend(s) to test")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    # Track overall success
    success = True

    # Test with asyncio backend
    if args.backend in ["asyncio", "both"]:
        logger.info("Running tests with asyncio backend")
        asyncio_success = await run_tests("asyncio", args.asyncio_port)
        if asyncio_success:
            logger.info("All asyncio backend tests PASSED")
        else:
            logger.error("Some asyncio backend tests FAILED")
            success = False

    # Test with trio backend
    if args.backend in ["trio", "both"]:
        logger.info("Running tests with trio backend")
        trio_success = await run_tests("trio", args.trio_port)
        if trio_success:
            logger.info("All trio backend tests PASSED")
        else:
            logger.error("Some trio backend tests FAILED")
            success = False

    # Final results
    if success:
        logger.info("ALL TESTS PASSED")
        return 0
    else:
        logger.error("SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(anyio.run(main))
