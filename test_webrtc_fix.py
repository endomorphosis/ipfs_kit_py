#!/usr/bin/env python
"""
Test script to verify our WebRTC event loop fixes.
"""

import requests
import json
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Server URL
base_url = "http://localhost:9999"

def make_request(method, endpoint, **kwargs):
    """Make a request to the MCP server."""
    url = f"{base_url}{endpoint}"
    method_func = getattr(requests, method.lower())
    
    try:
        response = method_func(url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response:
            try:
                error_detail = e.response.json()
                logger.error(f"Error details: {error_detail}")
                return error_detail
            except:
                logger.error(f"Response text: {e.response.text}")
                return {"success": False, "error": str(e), "status_code": e.response.status_code}
        return {"success": False, "error": str(e)}

def test_webrtc_dependency_check():
    """Test WebRTC dependency check."""
    logger.info("Testing WebRTC dependency check...")
    response = make_request("get", "/api/v0/mcp/webrtc/check")
    logger.info(f"Response: {json.dumps(response, indent=2)}")
    return response

def test_close_all_connections():
    """Test closing all WebRTC connections."""
    logger.info("Testing close all WebRTC connections...")
    response = make_request("post", "/api/v0/mcp/webrtc/connections/close-all")
    logger.info(f"Response: {json.dumps(response, indent=2)}")
    return response

def test_stream_content(cid="QmTkzDwWqPbnAh5YiV5VwcTLnGdwSNsNTn2aDxdXBFca7D"):
    """Test streaming content via WebRTC."""
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
    logger.info(f"Response: {json.dumps(response, indent=2)}")
    return response

def test_stop_streaming(server_id):
    """Test stopping a WebRTC streaming server."""
    logger.info(f"Testing stopping WebRTC stream server: {server_id}...")
    response = make_request("post", f"/api/v0/mcp/webrtc/stream/stop/{server_id}")
    logger.info(f"Response: {json.dumps(response, indent=2)}")
    return response

def main():
    """Run the WebRTC tests."""
    # Test the WebRTC dependency check
    dep_check = test_webrtc_dependency_check()
    
    # Only proceed if WebRTC is available
    if not dep_check.get("webrtc_available", False):
        logger.error("WebRTC is not available, skipping other tests")
        return
    
    # Test streaming content
    stream_result = test_stream_content()
    server_id = stream_result.get("server_id")
    
    if server_id:
        # Test stopping the stream
        time.sleep(1)  # Give the server some time to set up
        stop_result = test_stop_streaming(server_id)
    
    # Test closing all connections (after starting and stopping a stream)
    close_all_result = test_close_all_connections()
    
    # Report results
    if all([
        dep_check.get("success", False),
        stream_result.get("success", False),
        stop_result.get("success", False) if 'stop_result' in locals() else True,
        close_all_result.get("success", False)
    ]):
        logger.info("✅ All WebRTC tests passed!")
    else:
        logger.error("❌ Some WebRTC tests failed")

if __name__ == "__main__":
    main()