"""Minimal test for WebRTC availability."""

import unittest

class TestMinimalWebRTC(unittest.TestCase):
    
    def test_webrtc_import(self):
        """Test that we can import the WebRTC flag."""
        try:
            from ipfs_kit_py.webrtc_streaming import HAVE_WEBRTC
            self.assertIsNotNone(HAVE_WEBRTC)
            print(f"Successfully imported HAVE_WEBRTC: {HAVE_WEBRTC}")
        except ImportError as e:
            self.fail(f"Failed to import HAVE_WEBRTC: {e}")

if __name__ == "__main__":
    unittest.main()