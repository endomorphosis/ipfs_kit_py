#!/usr/bin/env python3
"""
Integration Test for WebRTC Dashboard and Video Player

This script tests the integration between the WebRTC dashboard and video player.
It verifies:
1. Static file accessibility
2. Dashboard routing
3. Video player routing
4. Parameter passing between components
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from urllib.parse import urljoin, quote
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("integration_test")

# Constants
DEFAULT_HOST = "http://localhost:8000"

REPO_ROOT = Path(__file__).resolve().parents[2]

def test_static_files(base_url):
    """Test if static files are accessible."""
    logger.info("Testing static file access...")
    files = ["webrtc_dashboard.html", "webrtc_video_player.html"]
    
    for file in files:
        url = urljoin(base_url, file)
        try:
            response = requests.get(url)
            if response.status_code == 200:
                logger.info(f"✅ {file} is accessible")
            else:
                logger.error(f"❌ {file} returned status code {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to access {file}: {e}")
            return False
            
    return True

def test_content_integration():
    """Test integration between dashboard and video player."""
    # Check if the necessary components are present in the dashboard
    logger.info("Testing dashboard-player integration...")
    
    with open((REPO_ROOT / "static" / "webrtc_dashboard.html"), "r") as f:
        dashboard_html = f.read()
        
    # Check for open player function
    if "function openVideoPlayer(" in dashboard_html:
        logger.info("✅ Dashboard has openVideoPlayer function")
    else:
        logger.error("❌ Dashboard missing openVideoPlayer function")
        return False
        
    # Check if openPlayer button is present in the table
    if "Open Player" in dashboard_html:
        logger.info("✅ Dashboard has 'Open Player' button")
    else:
        logger.error("❌ Dashboard missing 'Open Player' button")
        return False
    
    # Check video player script for parameter handling
    with open((REPO_ROOT / "static" / "webrtc_video_player.html"), "r") as f:
        player_html = f.read()
        
    if "Back to Dashboard" in player_html:
        logger.info("✅ Video player has 'Back to Dashboard' link")
    else:
        logger.error("❌ Video player missing 'Back to Dashboard' link")
        return False
        
    return True

def test_controller_integration():
    """Test controller implementation for integration."""
    logger.info("Testing controller integration...")
    
    # Check video player controller
    with open((REPO_ROOT / "ipfs_kit_py" / "mcp" / "controllers" / "webrtc_video_controller.py"), "r") as f:
        controller_code = f.read()
        
    # Check for connection parameter handling
    if "connection_id = request.query_params.get" in controller_code:
        logger.info("✅ Video controller handles connection parameters")
    else:
        logger.error("❌ Video controller doesn't handle connection parameters")
        return False
        
    # Check for script injection
    if "Auto-populate connection details" in controller_code:
        logger.info("✅ Video controller has auto-populate script")
    else:
        logger.error("❌ Video controller missing auto-populate script")
        return False
        
    return True

def test_server_integration():
    """Test the server runner integration."""
    logger.info("Testing server runner integration...")
    
    with open((REPO_ROOT / "run_mcp_with_webrtc_dashboard.py"), "r") as f:
        server_code = f.read()
        
    # Check if both controllers are imported
    if "from ipfs_kit_py.mcp.controllers.webrtc_dashboard_controller import" in server_code and \
       "from ipfs_kit_py.mcp.controllers.webrtc_video_controller import" in server_code:
        logger.info("✅ Server imports both controllers")
    else:
        logger.error("❌ Server missing controller imports")
        return False
        
    # Check if both routers are added
    if "app.include_router(dashboard_router)" in server_code and \
       "app.include_router(video_player_router)" in server_code:
        logger.info("✅ Server registers both routers")
    else:
        logger.error("❌ Server doesn't register both routers")
        return False
        
    return True

def test_documentation():
    """Test if documentation is present and complete."""
    logger.info("Testing documentation...")
    
    try:
        with open((REPO_ROOT / "WEBRTC_DASHBOARD_INTEGRATED.md"), "r") as f:
            doc_content = f.read()
            
        # Check if documentation mentions key integration points
        if "Dashboard to Player Navigation" in doc_content and \
           "Parameter Passing" in doc_content and \
           "Auto-Connect Option" in doc_content:
            logger.info("✅ Documentation covers integration points")
        else:
            logger.error("❌ Documentation missing integration details")
            return False
            
        # Check for API documentation
        if "Dashboard API Endpoints" in doc_content and \
           "Video Player API Endpoints" in doc_content:
            logger.info("✅ Documentation includes API endpoints")
        else:
            logger.error("❌ Documentation missing API endpoints")
            return False
            
        return True
    except FileNotFoundError:
        logger.error("❌ Documentation file not found")
        return False

def main():
    """Run the integration tests."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Test WebRTC Dashboard-Player Integration")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Base URL for the static server")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    # Start tests
    logger.info("Starting integration tests...")
    
    # Count passed tests
    passed = 0
    tests = 5
    
    # Run tests
    if test_static_files(args.host):
        passed += 1
    
    if test_content_integration():
        passed += 1
        
    if test_controller_integration():
        passed += 1
        
    if test_server_integration():
        passed += 1
        
    if test_documentation():
        passed += 1
        
    # Print summary
    logger.info(f"Integration tests completed: {passed}/{tests} tests passed")
    
    if passed == tests:
        logger.info("✅ All integration tests passed!")
        return 0
    else:
        logger.error(f"❌ Some tests failed ({tests - passed} failures)")
        return 1

if __name__ == "__main__":
    sys.exit(main())