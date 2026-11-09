#!/usr/bin/env python3
"""
Direct fix for the LibP2PModel class to resolve coroutine never awaited warnings.

This script directly edits the LibP2PModel class in the MCP server architecture
to properly handle asynchronous methods and fix issues with the async methods.
"""

import os
import logging
import inspect
import fileinput
import re
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_direct_fixes():
    """Apply fixes directly to the libp2p_model.py file."""
    try:
        # Find the libp2p_model.py file
        file_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/libp2p_model.py"
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        logger.info(f"Applying fixes directly to {file_path}")
        
        # Read the current file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix for async is_available method
        logger.info("Fixing async is_available method...")
        content = content.replace(
            "async def is_available(self) -> bool:\n"
            "        \"\"\"\n"
            "        Async version of is_available for use with async controllers.\n"
            "        \n"
            "        Returns:\n"
            "            bool: True if libp2p is available, False otherwise\n"
            "        \"\"\"\n"
            "        # Use anyio to run the synchronous version in a thread\n"
            "        import anyio\n"
            "        return await anyio.to_thread.run_sync(LibP2PModel._is_available_sync, self)",
            
            "async def is_available(self) -> bool:\n"
            "        \"\"\"\n"
            "        Async version of is_available for use with async controllers.\n"
            "        \n"
            "        Returns:\n"
            "            bool: True if libp2p is available, False otherwise\n"
            "        \"\"\"\n"
            "        # Use anyio to run the synchronous version in a thread\n"
            "        import anyio\n"
            "        return await anyio.to_thread.run_sync(lambda: self._is_available_sync())"
        )
        
        # Fix for all other async methods
        for method_name in [
            'get_health', 'discover_peers', 'connect_peer', 'disconnect_peer',
            'find_content', 'retrieve_content', 'get_content', 'announce_content',
            'get_connected_peers', 'get_peer_info', 'reset', 'start', 'stop',
            'dht_find_peer', 'dht_provide', 'dht_find_providers',
            'pubsub_publish', 'pubsub_subscribe', 'pubsub_unsubscribe',
            'pubsub_get_topics', 'pubsub_get_peers', 'list_message_handlers',
            'publish_message', 'subscribe_topic', 'unsubscribe_topic', 'peer_info'
        ]:
            logger.info(f"Fixing async {method_name} method...")
            
            # Pattern to match the old method implementation
            pattern = rf"async def {method_name}\((.*?)\).*?await anyio\.to_thread\.run_sync\(LibP2PModel\.{method_name}, self(.*?)\)"
            
            # Create replacement with lambda function
            replacement = rf"async def {method_name}(\1):\n        \"\"\"\n        Async version of {method_name} for use with async controllers.\n        \"\"\"\n        # Use anyio to run the synchronous version in a thread\n        import anyio\n        return await anyio.to_thread.run_sync(lambda: self.{method_name}(\2))"
            
            # Apply the replacement
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Fix for register_message_handler specifically
        logger.info("Fixing register_message_handler method...")
        register_pattern = r"async def register_message_handler\(self, handler_id: str, protocol_id: str, description: Optional\[str\] = None\) -> Dict\[str, Any\]:(.*?)return await anyio\.to_thread\.run_sync\(LibP2PModel\.register_message_handler, self, protocol_id, lambda x: x, handler_id\)"
        register_replacement = """async def register_message_handler(self, handler_id: str, protocol_id: str, description: Optional[str] = None) -> Dict[str, Any]:
        \"\"\"
        Async version of register_message_handler for use with async controllers.
        
        Args:
            handler_id: Unique identifier for the handler
            protocol_id: Protocol ID to handle
            description: Optional description of the handler
            
        Returns:
            Dict with registration status
        \"\"\"
        # Create a dummy handler function
        def dummy_handler(message):
            pass
        
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(lambda: self.register_message_handler(protocol_id, dummy_handler, handler_id))"""
        
        content = re.sub(register_pattern, register_replacement, content, flags=re.DOTALL)
        
        # Fix for unregister_message_handler specifically
        logger.info("Fixing unregister_message_handler method...")
        unregister_pattern = r"async def unregister_message_handler\(self, handler_id: str, protocol_id: str\) -> Dict\[str, Any\]:(.*?)return await anyio\.to_thread\.run_sync\(LibP2PModel\.unregister_message_handler, self, protocol_id, handler_id\)"
        unregister_replacement = """async def unregister_message_handler(self, handler_id: str, protocol_id: str) -> Dict[str, Any]:
        \"\"\"
        Async version of unregister_message_handler for use with async controllers.
        
        Args:
            handler_id: ID of the handler to unregister
            protocol_id: Protocol ID the handler is registered for
            
        Returns:
            Dict with unregistration status
        \"\"\"
        # Use anyio to run the synchronous version in a thread
        import anyio
        return await anyio.to_thread.run_sync(lambda: self.unregister_message_handler(protocol_id, handler_id))"""
        
        content = re.sub(unregister_pattern, unregister_replacement, content, flags=re.DOTALL)
        
        # Add logger attribute if missing
        if "self.logger" in content and "LibP2PModel.logger" not in content:
            logger.info("Adding logger attribute to LibP2PModel class...")
            # Add after class definition
            content = content.replace(
                "class LibP2PModel:",
                "class LibP2PModel:\n    # Class logger\n    logger = logging.getLogger(__name__)"
            )
        
        # Write the updated content back to the file
        with open(file_path, 'w') as f:
            f.write(content)
        
        logger.info("Fixes applied successfully to LibP2PModel class!")
        return True
    
    except Exception as e:
        logger.error(f"Error applying direct fixes: {e}")
        return False

if __name__ == "__main__":
    success = apply_direct_fixes()
    if success:
        print("Successfully applied direct fixes to LibP2PModel class!")
        print("This resolves the 'coroutine never awaited' warnings by properly")
        print("implementing sync and async methods in the LibP2PModel class.")
    else:
        print("Failed to apply direct fixes. See logs for details.")
        sys.exit(1)