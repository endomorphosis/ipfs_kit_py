#!/usr/bin/env python3
"""
MCP Server Integration Test

This script tests the MCP server by directly instantiating it and simulating FastAPI requests,
without having to start a full HTTP server.
"""

import os
import sys
import json
import time
import logging
import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Run the test suite."""
    logger.info("Starting MCP server integration test")

    # Import patch to fix missing methods
    try:
        import patch_missing_methods
        logger.info("Successfully patched missing methods")
    except Exception as e:
        logger.error(f"Failed to patch missing methods: {e}")
        return 1

    # Create FastAPI app
    app = FastAPI(
        title="IPFS MCP Server Test",
        description="Test instance for MCP Server",
        version="0.1.0"
    )

    # Import and initialize MCP server
    try:
        from ipfs_kit_py.mcp.server import MCPServer
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        
        # Create kit instance
        kit = ipfs_kit()
        
        # Create MCP server with appropriate settings
        mcp_server = MCPServer(
            debug_mode=True,
            isolation_mode=False,
            persistence_path=os.path.expanduser("~/.ipfs_kit/mcp_test"),
            ipfs_kit_instance=kit
        )
        
        # Register server with app
        mcp_server.register_with_app(app, prefix="/api/v0")
        logger.info("MCP server initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MCP server: {e}")
        return 1

    # Create test client
    client = TestClient(app)
    logger.info("Test client created")
    
    # Helper function to run tests
    def run_test(name, endpoint, method="GET", json_data=None, params=None, expected_status=200):
        logger.info(f"Testing {name}...")
        if method == "GET":
            response = client.get(endpoint, params=params)
        else:
            response = client.post(endpoint, json=json_data, params=params)
            
        status_ok = response.status_code == expected_status
        result_prefix = "✅" if status_ok else "❌"
        logger.info(f"{result_prefix} {name}: Status {response.status_code}")
        
        # Log response details
        try:
            response_json = response.json()
            logger.info(f"Response: {json.dumps(response_json, indent=2)}")
        except Exception:
            logger.info(f"Response: {response.text}")
            
        return status_ok, response
    
    # Run the tests
    results = {}
    
    # Test health endpoint
    results["health"] = run_test(
        name="Health Check",
        endpoint="/api/v0/health"
    )
    
    # Test DHT findpeer
    results["dht_findpeer"] = run_test(
        name="DHT FindPeer",
        endpoint="/api/v0/ipfs/dht/findpeer",
        method="GET",
        params={"peer_id": "QmTest123"}
    )
    
    # Test DHT findprovs
    results["dht_findprovs"] = run_test(
        name="DHT FindProviders",
        endpoint="/api/v0/ipfs/dht/findprovs",
        method="GET",
        params={"cid": "QmTest123"}
    )
    
    # Test files mkdir
    test_dir = f"/test_dir_{int(time.time())}"
    results["files_mkdir"] = run_test(
        name="Files Mkdir",
        endpoint="/api/v0/ipfs/files/mkdir",
        method="POST",
        json_data={"path": test_dir, "parents": True}
    )
    
    # Test files ls (standard)
    results["files_ls_standard"] = run_test(
        name="Files List (Standard)",
        endpoint="/api/v0/ipfs/files/ls",
        method="POST",
        json_data={"path": "/"}
    )
    
    # Test files ls with long parameter (our fix)
    results["files_ls_long"] = run_test(
        name="Files List (with Long parameter)",
        endpoint="/api/v0/ipfs/files/ls",
        method="POST",
        json_data={"path": "/", "long": True}
    )
    
    # Test files stat (our fix)
    results["files_stat"] = run_test(
        name="Files Stat",
        endpoint="/api/v0/ipfs/files/stat",
        method="GET",
        params={"path": "/"}
    )
    
    # Print summary
    logger.info("\n=== Test Summary ===")
    all_passed = True
    for name, (status, _) in results.items():
        result_prefix = "✅" if status else "❌"
        logger.info(f"{result_prefix} {name}")
        if not status:
            all_passed = False
    
    logger.info(f"\nTest {'PASSED' if all_passed else 'FAILED'}")
    return 0 if all_passed else 1

if __name__ == "__main__":
    # Run the async main function
    if sys.version_info >= (3, 7):
        anyio.run(main())
    else:
        # For Python 3.6
        loop = anyio.get_event_loop()
        loop.run_until_complete(main())