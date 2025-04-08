#!/usr/bin/env python3
"""
Test script to check if WebRTC dependencies are correctly detected.
This script imports the webrtc_streaming module and prints the dependency flags.
"""

import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to test WebRTC dependency detection."""
    print("Testing WebRTC dependency detection...")
    
    # First, try normal import
    try:
        print("Importing webrtc_streaming module...")
        from ipfs_kit_py.webrtc_streaming import (
            HAVE_WEBRTC, HAVE_NUMPY, HAVE_CV2, HAVE_AV, HAVE_AIORTC,
            HAVE_WEBSOCKETS, HAVE_NOTIFICATIONS, check_webrtc_dependencies
        )
        
        print(f"\nWebRTC dependency flags:")
        print(f"HAVE_WEBRTC: {HAVE_WEBRTC}")
        print(f"HAVE_NUMPY: {HAVE_NUMPY}")
        print(f"HAVE_CV2: {HAVE_CV2}")
        print(f"HAVE_AV: {HAVE_AV}")
        print(f"HAVE_AIORTC: {HAVE_AIORTC}")
        print(f"HAVE_WEBSOCKETS: {HAVE_WEBSOCKETS}")
        print(f"HAVE_NOTIFICATIONS: {HAVE_NOTIFICATIONS}")
        
        # Get detailed dependency report
        print("\nDependency report from check_webrtc_dependencies():")
        report = check_webrtc_dependencies()
        for key, value in report.items():
            if key == "dependencies":
                print(f"{key}:")
                for dep_key, dep_value in value.items():
                    print(f"  {dep_key}: {dep_value}")
            else:
                print(f"{key}: {value}")
        
    except ImportError as e:
        print(f"Import error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    # Now try importing and creating an instance
    try:
        print("\nTrying to create WebRTCStreamingManager instance...")
        from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager
        
        if HAVE_WEBRTC:
            manager = WebRTCStreamingManager()
            print("Successfully created WebRTCStreamingManager instance")
        else:
            print("Cannot create WebRTCStreamingManager as HAVE_WEBRTC is False")
            
    except ImportError as e:
        print(f"Import error when creating manager: {e}")
    except Exception as e:
        print(f"Error creating manager: {type(e).__name__}: {e}")
        
    # Now check the high-level API integration
    try:
        print("\nChecking high_level_api WebRTC integration...")
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI, HAVE_WEBRTC as HL_HAVE_WEBRTC
        
        print(f"high_level_api.HAVE_WEBRTC: {HL_HAVE_WEBRTC}")
        
        api = IPFSSimpleAPI()
        # Check if the API has webrtc-related methods by name (don't call them)
        webrtc_methods = [method for method in dir(api) if "webrtc" in method.lower()]
        print(f"WebRTC-related methods in IPFSSimpleAPI: {webrtc_methods}")
        
    except ImportError as e:
        print(f"Import error when checking high-level API: {e}")
    except Exception as e:
        print(f"Error checking high-level API: {type(e).__name__}: {e}")
    
    print("\nTest completed")

if __name__ == "__main__":
    main()