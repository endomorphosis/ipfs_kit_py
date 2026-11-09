"""
Fix for Kademlia integration with libp2p.

This script applies a patched version of the apply_kademlia_extensions function
that avoids the error when trying to replace magic methods.
"""

import sys
import logging
import importlib
from typing import Any, Type

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kademlia_fix")

def fix_kademlia_extensions():
    """
    Apply a fix to the Kademlia extensions in the protocol_integration module.
    """
    try:
        # Import the protocol_integration module
        from ipfs_kit_py.libp2p.protocol_integration import apply_kademlia_extensions
        import ipfs_kit_py.libp2p.protocol_integration

        # Define the patched version of apply_kademlia_extensions
        def patched_apply_kademlia_extensions(peer_class: Type) -> Type:
            """
            Apply Kademlia DHT extensions to the IPFSLibp2pPeer class.

            This patched version avoids replacing the __init__ magic method.

            Args:
                peer_class: The IPFSLibp2pPeer class to extend

            Returns:
                The enhanced peer class
            """
            try:
                # Instead of replacing __init__, add a new initialize_kademlia_config method
                def initialize_kademlia_config(self, dht_config=None):
                    """
                    Initialize Kademlia configuration.

                    Args:
                        dht_config: Configuration dictionary for DHT
                    """
                    if dht_config is None:
                        dht_config = {}

                    # Set up Kademlia attributes if they don't exist
                    if not hasattr(self, 'kademlia_initialized'):
                        self.kademlia_initialized = False

                    if not hasattr(self, 'kad_routing_table'):
                        self.kad_routing_table = None

                    if not hasattr(self, 'kad_datastore'):
                        self.kad_datastore = None

                    # Store DHT configuration
                    self.dht_config = dht_config

                # Add the initialization method
                peer_class.initialize_kademlia_config = initialize_kademlia_config

                # Patch the original start method if it exists
                if hasattr(peer_class, 'start') and callable(getattr(peer_class, 'start')):
                    original_start = peer_class.start

                    # Create an enhanced start method that initializes Kademlia
                    async def enhanced_start(self):
                        # First make sure kademlia config is initialized if not already
                        if not hasattr(self, 'kademlia_initialized'):
                            self.initialize_kademlia_config(getattr(self, 'dht_config', {}))

                        # Call original start method
                        result = original_start(self)

                        # Check if we need to await the result
                        import inspect
                        if inspect.isawaitable(result):
                            await result

                        # Initialize Kademlia if needed
                        if hasattr(self, 'initialize_kademlia') and not self.kademlia_initialized:
                            await self.initialize_kademlia()

                        return result

                    # Replace the start method
                    peer_class.start = enhanced_start

                # Add Kademlia methods
                from ipfs_kit_py.libp2p.protocol_integration import add_kademlia_methods
                add_kademlia_methods(peer_class)

                # Add a post-initialization hook method that can be called after __init__
                def post_init_setup(self, dht_config=None):
                    """
                    Run setup tasks that should happen after initialization.

                    Args:
                        dht_config: Configuration dictionary for DHT
                    """
                    # Initialize Kademlia configuration
                    self.initialize_kademlia_config(dht_config or getattr(self, 'dht_config', {}))

                # Add the post-initialization hook
                peer_class.post_init_setup = post_init_setup

                return peer_class

            except Exception as e:
                logger.error(f"Error applying Kademlia extensions: {e}")
                return peer_class

        # Replace the original function with our patched version
        ipfs_kit_py.libp2p.protocol_integration.apply_kademlia_extensions = patched_apply_kademlia_extensions

        logger.info("Successfully patched apply_kademlia_extensions function")
        return True

    except ImportError as e:
        logger.error(f"Could not import protocol_integration module: {e}")
        return False
    except Exception as e:
        logger.error(f"Error patching apply_kademlia_extensions function: {e}")
        return False

if __name__ == "__main__":
    if fix_kademlia_extensions():
        print("Successfully applied Kademlia extension fix")
    else:
        print("Failed to apply Kademlia extension fix")
        sys.exit(1)
