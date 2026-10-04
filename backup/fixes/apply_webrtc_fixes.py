#!/usr/bin/env python3
"""
Apply WebRTC event loop fixes to MCP server.

This script patches the problematic WebRTC methods in the MCP server
to properly handle event loops in FastAPI context.
"""

import os
import sys
import logging
import importlib
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(parent_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def apply_fixes(mcp_server=None):
    """
    Apply WebRTC event loop fixes to MCP server.

    Args:
        mcp_server: Optional MCP server instance to patch directly
                   If None, the fix will be applied to the module for future instances

    Returns:
        True if fixes were applied successfully, False otherwise
    """
    try:
        # Import the fix module
        from fixes.webrtc_event_loop_fix import (
            patch_ipfs_model_methods,
            patch_webrtc_controller_methods
        )

        # If a server instance was provided, patch it directly
        if mcp_server is not None:
            logger.info("Applying WebRTC event loop fixes to MCP server instance")

            # Patch the IPFS model
            if hasattr(mcp_server, 'models') and 'ipfs' in mcp_server.models:
                patch_ipfs_model_methods(mcp_server.models['ipfs'])
                logger.info("Patched IPFS model in server instance")
            else:
                logger.warning("Could not find IPFS model in server instance")

            # Patch the WebRTC controller if it exists
            if (hasattr(mcp_server, 'controllers') and
                any(isinstance(c, WebRTCController) for c in mcp_server.controllers.values())):
                for name, controller in mcp_server.controllers.items():
                    if hasattr(controller, 'ipfs_model'):
                        patch_webrtc_controller_methods(controller)
                        logger.info(f"Patched WebRTC controller {name} in server instance")

            return True

        # Otherwise, patch the modules for all future instances
        else:
            logger.info("Applying WebRTC event loop fixes to modules")

            # Import models and controller modules
            from ipfs_kit_py.mcp.models import ipfs_model

            # Monkey patch the IPFS model module
            original_stop_streaming = ipfs_model.IPFSModel.stop_webrtc_streaming
            original_close_connection = ipfs_model.IPFSModel.close_webrtc_connection
            original_close_all_connections = ipfs_model.IPFSModel.close_all_webrtc_connections

            # Get our fixed methods
            from fixes.webrtc_event_loop_fix import (
                patched_stop_webrtc_streaming,
                patched_close_webrtc_connection,
                patched_close_all_webrtc_connections,
                async_stop_webrtc_streaming,
                async_close_webrtc_connection,
                async_close_all_webrtc_connections
            )

            # Replace the methods in the class
            ipfs_model.IPFSModel.stop_webrtc_streaming = patched_stop_webrtc_streaming
            ipfs_model.IPFSModel.close_webrtc_connection = patched_close_webrtc_connection
            ipfs_model.IPFSModel.close_all_webrtc_connections = patched_close_all_webrtc_connections

            # Add async methods
            ipfs_model.IPFSModel.async_stop_webrtc_streaming = async_stop_webrtc_streaming
            ipfs_model.IPFSModel.async_close_webrtc_connection = async_close_webrtc_connection
            ipfs_model.IPFSModel.async_close_all_webrtc_connections = async_close_all_webrtc_connections

            logger.info("Successfully patched IPFS model module")

            # Try to patch the WebRTC controller if it exists
            try:
                from ipfs_kit_py.mcp.controllers import webrtc_controller
                from fixes.webrtc_event_loop_fix import patch_webrtc_controller_methods

                # Store original methods for reference
                original_controller_stop = webrtc_controller.WebRTCController.stop_streaming
                original_controller_close = webrtc_controller.WebRTCController.close_connection
                original_controller_close_all = webrtc_controller.WebRTCController.close_all_connections

                # Create wrapper methods for the controller
                async def new_stop_streaming(self, server_id: str):
                    return await self.ipfs_model.async_stop_webrtc_streaming(server_id)

                async def new_close_connection(self, connection_id: str):
                    return await self.ipfs_model.async_close_webrtc_connection(connection_id)

                async def new_close_all_connections(self):
                    return await self.ipfs_model.async_close_all_webrtc_connections()

                # Replace the methods
                webrtc_controller.WebRTCController.stop_streaming = new_stop_streaming
                webrtc_controller.WebRTCController.close_connection = new_close_connection
                webrtc_controller.WebRTCController.close_all_connections = new_close_all_connections

                logger.info("Successfully patched WebRTC controller module")

            except ImportError:
                logger.warning("WebRTC controller module not found, skipping controller patches")

            return True

    except Exception as e:
        logger.error(f"Error applying WebRTC fixes: {e}")
        return False

if __name__ == "__main__":
    # Apply fixes to modules for future MCP server instances
    success = apply_fixes()

    if success:
        print("✅ Successfully applied WebRTC event loop fixes")
        sys.exit(0)
    else:
        print("❌ Failed to apply WebRTC event loop fixes")
        sys.exit(1)
