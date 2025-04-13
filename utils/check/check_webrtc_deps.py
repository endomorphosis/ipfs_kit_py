#!/usr/bin/env python3
"""
Simple test script to check the availability of WebRTC dependencies
"""

import os
import sys

# Set environment variables to force WebRTC availability
os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
os.environ["FORCE_WEBRTC_TESTS"] = "1"

def check_webrtc_availability():
    """Check if WebRTC dependencies are available."""
    
    print("Checking WebRTC dependencies...\n")
    
    # Try to import the webrtc_streaming module
    try:
        from ipfs_kit_py import webrtc_streaming
        print(f"webrtc_streaming imported successfully")
        print(f"HAVE_WEBRTC: {webrtc_streaming.HAVE_WEBRTC}")
        print(f"HAVE_NUMPY: {webrtc_streaming.HAVE_NUMPY}")
        print(f"HAVE_CV2: {webrtc_streaming.HAVE_CV2}")
        print(f"HAVE_AV: {webrtc_streaming.HAVE_AV}")
        print(f"HAVE_AIORTC: {webrtc_streaming.HAVE_AIORTC}")
        print(f"HAVE_NOTIFICATIONS: {webrtc_streaming.HAVE_NOTIFICATIONS}")
    except ImportError as e:
        print(f"Failed to import webrtc_streaming: {e}")
    except AttributeError as e:
        print(f"AttributeError when accessing WebRTC flags: {e}")
    
    # Try to import high_level_api
    try:
        from ipfs_kit_py import high_level_api
        print(f"\nhigh_level_api imported successfully")
        print(f"HAVE_WEBRTC: {high_level_api.HAVE_WEBRTC}")
    except ImportError as e:
        print(f"Failed to import high_level_api: {e}")
    except AttributeError as e:
        print(f"AttributeError when accessing WebRTC flags: {e}")
    
    # Check if the individual packages are available
    try:
        import numpy
        print(f"\nnumpy: {numpy.__version__}")
    except ImportError:
        print("\nnumpy: Not available")
    
    try:
        import cv2
        print(f"cv2: {cv2.__version__}")
    except ImportError:
        print("cv2: Not available")
    
    try:
        import av
        print(f"av: {av.__version__}")
    except ImportError:
        print("av: Not available")
    
    try:
        import aiortc
        print(f"aiortc: {aiortc.__version__}")
    except ImportError:
        print("aiortc: Not available")

if __name__ == "__main__":
    check_webrtc_availability()