#!/usr/bin/env python3
"""
This script tests the WebRTC dependency handling in ipfs_kit_py.
It checks that the module can be imported without errors, regardless of whether
the optional dependencies are available.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_webrtc_imports():
    """Test that webrtc_streaming can be imported safely."""
    logger.info("Testing WebRTC module imports...")

    try:
        # Try importing the webrtc_streaming module
        from ipfs_kit_py.webrtc_streaming import (
            HAVE_WEBRTC, HAVE_AV, HAVE_CV2, HAVE_NUMPY, HAVE_AIORTC
        )

        logger.info("WebRTC dependency status:")
        logger.info(f"  HAVE_WEBRTC: {HAVE_WEBRTC}")
        logger.info(f"  HAVE_AV: {HAVE_AV}")
        logger.info(f"  HAVE_CV2: {HAVE_CV2}")
        logger.info(f"  HAVE_NUMPY: {HAVE_NUMPY}")
        logger.info(f"  HAVE_AIORTC: {HAVE_AIORTC}")

        # Try to import the WebRTCStreamingManager
        try:
            from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager
            logger.info("Successfully imported WebRTCStreamingManager")

            # Attempt to create an instance (should raise ImportError if dependencies missing)
            try:
                manager = WebRTCStreamingManager(ipfs_api=None)
                logger.info("Successfully created WebRTCStreamingManager instance")
            except ImportError as e:
                logger.info(f"Expected import error when creating WebRTCStreamingManager: {e}")

        except ImportError as e:
            logger.error(f"Failed to import WebRTCStreamingManager: {e}")
            return False

        # Try to import the IPFSMediaStreamTrack
        try:
            from ipfs_kit_py.webrtc_streaming import IPFSMediaStreamTrack
            logger.info("Successfully imported IPFSMediaStreamTrack")

            # Attempt to create an instance (should raise ImportError if dependencies missing)
            try:
                track = IPFSMediaStreamTrack()
                logger.info("Successfully created IPFSMediaStreamTrack instance")
            except ImportError as e:
                logger.info(f"Expected import error when creating IPFSMediaStreamTrack: {e}")

        except ImportError as e:
            logger.error(f"Failed to import IPFSMediaStreamTrack: {e}")
            return False

        # Try importing handle_webrtc_signaling
        try:
            from ipfs_kit_py.webrtc_streaming import handle_webrtc_signaling
            logger.info("Successfully imported handle_webrtc_signaling")
        except ImportError as e:
            logger.error(f"Failed to import handle_webrtc_signaling: {e}")
            return False

        return True

    except ImportError as e:
        logger.error(f"Failed to import webrtc_streaming: {e}")
        return False

def test_high_level_api_imports():
    """Test that high_level_api can be imported safely."""
    logger.info("Testing high_level_api imports...")

    try:
        # Try importing the high_level_api module
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        logger.info("Successfully imported IPFSSimpleAPI from high_level_api")

        # Check WebRTC availability flag
        from ipfs_kit_py.high_level_api import HAVE_WEBRTC
        logger.info(f"HAVE_WEBRTC in high_level_api: {HAVE_WEBRTC}")

        return True

    except ImportError as e:
        logger.error(f"Failed to import high_level_api: {e}")
        return False

if __name__ == "__main__":
    webrtc_result = test_webrtc_imports()
    high_level_api_result = test_high_level_api_imports()

    if webrtc_result and high_level_api_result:
        logger.info("All tests passed! WebRTC dependency handling is working correctly.")
        sys.exit(0)
    else:
        logger.error("Tests failed! WebRTC dependency handling needs fixing.")
        sys.exit(1)
