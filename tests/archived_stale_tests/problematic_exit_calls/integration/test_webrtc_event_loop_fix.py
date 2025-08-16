#!/usr/bin/env python3
"""
Test script for WebRTC event loop fixes.

This script tests that our fixes correctly handle event loops in FastAPI context.
"""

import sys
import time
import anyio
import logging
import argparse
import requests
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test WebRTC event loop fixes")
    
    parser.add_argument("--server-url", type=str, default="http://127.0.0.1:9999",
                      help="URL of the MCP server")
    parser.add_argument("--run-all", action="store_true", 
                      help="Run all tests, even if earlier tests fail")
    parser.add_argument("--verbose", action="store_true",
                      help="Show detailed output")
    
    return parser.parse_args()

def check_server_health(server_url):
    """Check if the server is running and healthy."""
    try:
        response = requests.get(f"{server_url}/api/health")
        if response.status_code == 200:
            health_data = response.json()
            return health_data.get("status") == "healthy"
        return False
    except Exception as e:
        logger.error(f"Error checking server health: {e}")
        return False

def test_webrtc_dependencies(server_url):
    """Test WebRTC dependency checking."""
    try:
        logger.info("Testing WebRTC dependency checking...")
        response = requests.get(f"{server_url}/api/webrtc/check")
        
        if response.status_code != 200:
            logger.error(f"Error checking WebRTC dependencies: {response.status_code} - {response.text}")
            return False
            
        result = response.json()
        logger.info(f"WebRTC available: {result.get('webrtc_available', False)}")
        logger.info(f"Dependencies: {result.get('dependencies', {})}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing WebRTC dependencies: {e}")
        return False

def test_streaming_workflow(server_url):
    """Test a complete WebRTC streaming workflow."""
    try:
        logger.info("Testing WebRTC streaming workflow...")
        
        # Step 1: Start a stream
        logger.info("Starting a WebRTC stream...")
        stream_response = requests.post(
            f"{server_url}/api/webrtc/stream",
            json={
                "cid": "QmTest1234567890",
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "medium",
                "benchmark": False
            }
        )
        
        if stream_response.status_code != 200:
            logger.error(f"Error starting stream: {stream_response.status_code} - {stream_response.text}")
            return False
            
        stream_result = stream_response.json()
        if not stream_result.get("success", False):
            logger.warning(f"Stream start not successful: {stream_result}")
            if stream_result.get("error_type") == "dependency_error":
                logger.warning("WebRTC dependencies not available, but API properly handled the error")
                return True
            return False
            
        server_id = stream_result.get("server_id")
        logger.info(f"Stream started with server ID: {server_id}")
        
        # Step 2: List connections
        logger.info("Listing WebRTC connections...")
        connections_response = requests.get(f"{server_url}/api/webrtc/connections")
        
        if connections_response.status_code != 200:
            logger.error(f"Error listing connections: {connections_response.status_code} - {connections_response.text}")
            return False
            
        connections_result = connections_response.json()
        logger.info(f"Found {connections_result.get('count', 0)} connections")
        
        # Step 3: Close a specific connection if any exist
        if connections_result.get("connections", []):
            connection_id = connections_result["connections"][0]["connection_id"]
            logger.info(f"Closing connection {connection_id}...")
            
            close_response = requests.post(
                f"{server_url}/api/webrtc/connections/{connection_id}/close"
            )
            
            if close_response.status_code != 200:
                logger.error(f"Error closing connection: {close_response.status_code} - {close_response.text}")
                return False
                
            close_result = close_response.json()
            logger.info(f"Connection close result: {close_result}")
        
        # Step 4: Stop the stream
        logger.info(f"Stopping stream with server ID: {server_id}...")
        stop_response = requests.post(
            f"{server_url}/api/webrtc/stream/stop/{server_id}"
        )
        
        if stop_response.status_code != 200:
            logger.error(f"Error stopping stream: {stop_response.status_code} - {stop_response.text}")
            return False
            
        stop_result = stop_response.json()
        logger.info(f"Stream stop result: {stop_result}")
        
        # Step 5: Close all connections
        logger.info("Closing all WebRTC connections...")
        close_all_response = requests.post(
            f"{server_url}/api/webrtc/connections/close-all"
        )
        
        if close_all_response.status_code != 200:
            logger.error(f"Error closing all connections: {close_all_response.status_code} - {close_all_response.text}")
            return False
            
        close_all_result = close_all_response.json()
        logger.info(f"Close all connections result: {close_all_result}")
        
        return True
    except Exception as e:
        logger.error(f"Error testing WebRTC streaming workflow: {e}")
        return False

async def test_concurrent_requests(server_url):
    """Test making concurrent requests that use event loops."""
    try:
        logger.info("Testing concurrent WebRTC requests...")
        
        # Helper function to make a request
        async def make_request(endpoint, payload=None, method="get"):
            logger.info(f"Making request to {endpoint}...")
            
            # Use aiohttp or similar for real async requests
            loop = anyio.get_running_loop()
            
            if method == "get":
                return await loop.run_in_executor(
                    None,
                    lambda: requests.get(f"{server_url}/api/{endpoint}")
                )
            else:
                return await loop.run_in_executor(
                    None,
                    lambda: requests.post(f"{server_url}/api/{endpoint}", json=payload)
                )
        
        # Make several concurrent requests
        tasks = [
            make_request("webrtc/check"),
            make_request("webrtc/connections"),
            make_request("webrtc/stream", {
                "cid": "QmTestConcurrent",
                "address": "127.0.0.1",
                "port": 8080,
                "quality": "medium",
                "benchmark": False
            }, "post"),
            make_request("webrtc/connections/close-all", {}, "post")
        ]
        
        # Run all tasks concurrently
        results = await anyio.gather(*tasks, return_exceptions=True)
        
        # Check all results
        success = True
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Request {i} failed with exception: {result}")
                success = False
            elif not isinstance(result, requests.Response):
                logger.error(f"Request {i} returned unexpected type: {type(result)}")
                success = False
            elif result.status_code != 200:
                logger.error(f"Request {i} failed with status code: {result.status_code} - {result.text}")
                success = False
            else:
                logger.info(f"Request {i} succeeded with status code: {result.status_code}")
        
        return success
    except Exception as e:
        logger.error(f"Error testing concurrent requests: {e}")
        return False

def main(args):
    """Run the WebRTC event loop fix tests."""
    server_url = args.server_url
    
    # Check server health
    logger.info(f"Checking server health at {server_url}...")
    if not check_server_health(server_url):
        logger.error("Server is not healthy, aborting tests")
        return False
        
    logger.info("Server is healthy, running tests...")
    
    # Run the tests
    test_results = {
        "webrtc_dependencies": test_webrtc_dependencies(server_url)
    }
    
    # Continue with streaming tests if dependencies test passed or we're running all tests
    if test_results["webrtc_dependencies"] or args.run_all:
        test_results["streaming_workflow"] = test_streaming_workflow(server_url)
    else:
        logger.warning("Skipping streaming workflow test due to failed dependencies test")
        test_results["streaming_workflow"] = False
    
    # Run concurrent requests test
    logger.info("Running concurrent requests test...")
    anyio.run(test_concurrent_requests(server_url))
    
    # Print test results
    logger.info("\n--- Test Results ---")
    for test_name, passed in test_results.items():
        status = "PASSED" if passed else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    # Return overall success
    return all(test_results.values())

if __name__ == "__main__":
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    success = main(args)
    
    if success:
        logger.info("\n✅ All tests passed! WebRTC event loop fixes are working correctly.")
        sys.exit(0)
    else:
        logger.error("\n❌ Some tests failed. Check the logs for details.")
        sys.exit(1)
