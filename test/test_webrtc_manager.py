"""Test the WebRTC streaming manager."""

import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import uuid

class TestWebRTCManager(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment."""
        # Import the manager class
        try:
            from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager, HAVE_WEBRTC
            self.HAVE_WEBRTC = HAVE_WEBRTC
            self.WebRTCStreamingManager = WebRTCStreamingManager
        except ImportError as e:
            self.skipTest(f"WebRTC dependencies not available: {e}")
    
    def test_manager_initialization(self):
        """Test initializing the WebRTC streaming manager."""
        # Skip if WebRTC is not available
        if not self.HAVE_WEBRTC:
            self.skipTest("WebRTC dependencies not available")
            
        # Create a mock API object
        mock_api = MagicMock()
        
        try:
            # Initialize the manager - this will raise ImportError if dependencies are missing
            manager = self.WebRTCStreamingManager(ipfs_api=mock_api)
            
            # Verify manager was initialized with the API
            self.assertEqual(manager.ipfs, mock_api)
            
            # Verify empty dictionaries are initialized
            self.assertEqual(len(manager.peer_connections), 0)
            self.assertEqual(len(manager.connection_stats), 0)
            self.assertEqual(len(manager.tracks), 0)
            
            # Print success message
            print("Successfully initialized WebRTC streaming manager")
        except ImportError as e:
            self.skipTest(f"Error initializing WebRTC manager: {e}")
            
    def test_check_webrtc_dependencies(self):
        """Test checking WebRTC dependencies."""
        # Call the module-level function
        from ipfs_kit_py.webrtc_streaming import check_webrtc_dependencies
        
        # Get the dependency report
        report = check_webrtc_dependencies()
        
        # Verify the report structure
        self.assertIn("webrtc_available", report)
        self.assertIn("dependencies", report)
        
        # Print the report for debugging
        print(f"WebRTC dependencies: {report}")
        
        # Verify dependencies
        deps = report["dependencies"]
        self.assertIn("numpy", deps)
        self.assertIn("opencv", deps)
        self.assertIn("av", deps)
        self.assertIn("aiortc", deps)

if __name__ == "__main__":
    unittest.main()