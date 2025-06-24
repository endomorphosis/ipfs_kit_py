"""
Test the WebRTCController's handling of interpreter shutdown.

This test checks the enhanced WebRTCController's ability to handle interpreter shutdown
gracefully when the "can't create new thread at interpreter shutdown" error occurs.
"""

import sys
import logging
import unittest
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class TestWebRTCInterpreterShutdown(unittest.TestCase):
    """Test WebRTCController's handling of interpreter shutdown."""

    def setUp(self):
        """Set up the test environment."""
        from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController
        from unittest.mock import MagicMock

        # Create a mock ipfs_model
        self.mock_ipfs_model = MagicMock()

        # Create a WebRTCController with the mock model
        self.webrtc_controller = WebRTCController(ipfs_model=self.mock_ipfs_model)

        # Add some fake data to the controller for testing
        self.webrtc_controller.active_streaming_servers = {
            "server1": {"cid": "Qm123", "started_at": time.time()},
            "server2": {"cid": "Qm456", "started_at": time.time()}
        }
        self.webrtc_controller.active_connections = {
            "conn1": {"added_at": time.time(), "server_id": "server1"},
            "conn2": {"added_at": time.time(), "server_id": "server2"}
        }

        logger.info("Test setup complete")

    def test_interpreter_shutdown_handling(self):
        """Test handling of interpreter shutdown during WebRTC controller shutdown."""
        logger.info("Starting test_interpreter_shutdown_handling")

        # Configure the mock model to raise the "can't create new thread" error
        # when close_all_webrtc_connections is called
        def raise_thread_error(*args, **kwargs):
            raise RuntimeError("can't create new thread at interpreter shutdown")
        self.mock_ipfs_model.close_all_webrtc_connections.side_effect = raise_thread_error

        # Mock sys.is_finalizing to simulate interpreter shutdown
        original_is_finalizing = getattr(sys, 'is_finalizing', lambda: False)

        try:
            # Patch sys.is_finalizing to return True
            setattr(sys, 'is_finalizing', lambda: True)

            # Call sync_shutdown and verify it handles the error gracefully
            self.webrtc_controller.sync_shutdown()

            # Verify that active_streaming_servers and active_connections were cleared
            self.assertEqual(len(self.webrtc_controller.active_streaming_servers), 0)
            self.assertEqual(len(self.webrtc_controller.active_connections), 0)

            logger.info("Successfully completed shutdown during interpreter shutdown simulation")

        finally:
            # Restore the original is_finalizing method
            if hasattr(sys, 'is_finalizing'):
                if original_is_finalizing:
                    setattr(sys, 'is_finalizing', original_is_finalizing)
                else:
                    delattr(sys, 'is_finalizing')

    def tearDown(self):
        """Clean up after the test."""
        # Clean up the controller manually just to be safe
        try:
            self.webrtc_controller.active_streaming_servers.clear()
            self.webrtc_controller.active_connections.clear()
            self.webrtc_controller = None
        except Exception as e:
            logger.warning(f"Error during teardown: {e}")

        logger.info("Test teardown complete")

if __name__ == "__main__":
    unittest.main()
