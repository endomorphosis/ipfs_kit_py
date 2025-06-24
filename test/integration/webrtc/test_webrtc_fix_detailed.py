#!/usr/bin/env python
"""
Detailed test script to verify our WebRTC event loop fixes.
"""

import requests
import json
import time
import logging
import traceback
from pprint import pformat

# Configure logging with more detail
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Server URL
base_url = "http://localhost:9999"

def make_request(method, endpoint, **kwargs):
    """Make a request to the MCP server with detailed logging."""
    url = f"{base_url}{endpoint}"
    logger.debug(f"Making {method.upper()} request to: {url}")
    if "json" in kwargs:
        logger.debug(f"Request JSON: {json.dumps(kwargs['json'], indent=2)}")

    method_func = getattr(requests, method.lower())
    response_data = None

    try:
        response = method_func(url, **kwargs)
        logger.debug(f"Response status: {response.status_code}")

        try:
            response_data = response.json()
            logger.debug(f"Response JSON: {json.dumps(response_data, indent=2)}")
        except json.JSONDecodeError:
            logger.debug(f"Response text (non-JSON): {response.text[:500]}")
            response_data = {"success": False, "error": "Non-JSON response", "text": response.text[:500]}

        response.raise_for_status()
        return response_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json()
                logger.error(f"Error details: {pformat(error_detail)}")
                response_data = error_detail
            except json.JSONDecodeError:
                text = e.response.text
                logger.error(f"Response text: {text}")
                response_data = {"success": False, "error": str(e), "status_code": e.response.status_code, "text": text}
            except Exception as inner_e:
                logger.error(f"Error processing error response: {inner_e}")
                logger.error(traceback.format_exc())
                response_data = {"success": False, "error": str(e), "inner_error": str(inner_e)}
        return response_data or {"success": False, "error": str(e)}

def test_webrtc_dependency_check():
    """Test WebRTC dependency check with detailed output."""
    logger.info("Testing WebRTC dependency check...")
    response = make_request("get", "/api/v0/mcp/webrtc/check")
    logger.info(f"Dependency check result: {response.get('webrtc_available', False)}")
    return response

def test_list_connections():
    """Test listing WebRTC connections with detailed output."""
    logger.info("Testing WebRTC connection listing...")
    response = make_request("get", "/api/v0/mcp/webrtc/connections")
    active_count = len(response.get("connections", []))
    logger.info(f"Active connections: {active_count}")
    return response

def test_close_all_connections():
    """Test closing all WebRTC connections with detailed output."""
    logger.info("Testing close all WebRTC connections...")
    response = make_request("post", "/api/v0/mcp/webrtc/connections/close-all")
    logger.info(f"Close all result: {response}")
    return response

def test_stream_content(cid="QmTkzDwWqPbnAh5YiV5VwcTLnGdwSNsNTn2aDxdXBFca7D"):
    """Test streaming content via WebRTC with detailed output."""
    logger.info(f"Testing WebRTC streaming for CID: {cid}...")

    request_data = {
        "cid": cid,
        "address": "127.0.0.1",
        "port": 8081,
        "quality": "medium",
        "benchmark": True,
        "ice_servers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    }

    response = make_request("post", "/api/v0/mcp/webrtc/stream", json=request_data)
    if response.get("success", False):
        logger.info(f"Stream created successfully with server_id: {response.get('server_id')}")
    else:
        logger.error(f"Failed to create stream: {response.get('error', 'Unknown error')}")
    return response

def test_stop_streaming(server_id):
    """Test stopping a WebRTC streaming server with detailed output."""
    logger.info(f"Testing stopping WebRTC stream server: {server_id}...")
    try:
        response = make_request("post", f"/api/v0/mcp/webrtc/stream/stop/{server_id}")
        logger.info(f"Stop streaming result: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in stop_streaming request: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}

def check_fastapi_endpoint_handler():
    """Directly examine the FastAPI endpoint handler."""
    try:
        # This is a diagnostic request to get more information about the error
        info_response = make_request("get", "/docs")

        logger.debug("OpenAPI docs accessed successfully. Server is running.")

        # Try to access debug information
        debug_response = make_request("get", "/api/v0/mcp/debug")
        logger.debug(f"Debug info: {debug_response}")

        return True
    except Exception as e:
        logger.error(f"Error checking FastAPI endpoint: {e}")
        return False

def main():
    """Run detailed WebRTC tests with extensive logging."""
    logger.info("=== Starting detailed WebRTC tests ===")

    # Check if FastAPI is responding properly
    check_fastapi_endpoint_handler()

    # Test the WebRTC dependency check
    dep_check = test_webrtc_dependency_check()

    # Only proceed if WebRTC is available
    if not dep_check.get("webrtc_available", False):
        logger.error("WebRTC is not available, skipping other tests")
        return

    # Test listing connections first to make sure endpoint works
    connections_result = test_list_connections()

    # Test streaming content
    stream_result = test_stream_content()
    server_id = stream_result.get("server_id")

    # Test listing connections again to see if our new connection appears
    connections_after = test_list_connections()

    # Test stopping the stream if we created one
    stop_result = None
    if server_id:
        # Give the server some time to set up the stream
        logger.info("Waiting 2 seconds for stream setup...")
        time.sleep(2)
        stop_result = test_stop_streaming(server_id)

    # Test closing all connections
    close_all_result = test_close_all_connections()

    # Report results
    logger.info("=== WebRTC Test Results Summary ===")
    logger.info(f"Dependency check: {'PASS' if dep_check.get('success', False) else 'FAIL'}")
    logger.info(f"Stream content: {'PASS' if stream_result.get('success', False) else 'FAIL'}")
    logger.info(f"Stop streaming: {'PASS' if stop_result and stop_result.get('success', False) else 'FAIL or SKIPPED'}")
    logger.info(f"Close connections: {'PASS' if close_all_result.get('success', False) else 'FAIL'}")

    if all([
        dep_check.get("success", False),
        stream_result.get("success", False),
        (stop_result and stop_result.get("success", False)) if stop_result else True,
        close_all_result.get("success", False)
    ]):
        logger.info("✅ All WebRTC tests passed!")
    else:
        logger.error("❌ Some WebRTC tests failed")

if __name__ == "__main__":
    main()
