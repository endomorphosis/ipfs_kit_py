'''
Import hooks for IPFS Kit libp2p.

This module contains hooks that are executed when the libp2p_peer module is imported.
The hooks apply protocol extensions to the IPFSLibp2pPeer class automatically.
'''

import sys
import importlib
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Flag to track whether hooks have been applied
_hooks_applied = False

def apply_hooks():
    '''Apply import hooks to the IPFSLibp2pPeer class.'''
    global _hooks_applied
    
    if _hooks_applied:
        return  # Only apply once
        
    logger.debug("Applying libp2p import hooks...")
    
    # Get the original import function
    original_import = __import__
    
    def patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        '''Patched import function that applies protocol extensions.'''
        module = original_import(name, globals, locals, fromlist, level)
        
        # Check if this is the libp2p_peer module
        if name == 'ipfs_kit_py.libp2p_peer' or (fromlist and 'IPFSLibp2pPeer' in fromlist):
            try:
                # Import the protocol extension functions
                from ipfs_kit_py.libp2p.protocol_integration import apply_protocol_extensions
                
                # Check if IPFSLibp2pPeer is in the module
                if hasattr(module, 'IPFSLibp2pPeer'):
                    # Apply the extensions
                    module.IPFSLibp2pPeer = apply_protocol_extensions(module.IPFSLibp2pPeer)
                    logger.debug("Applied protocol extensions to IPFSLibp2pPeer")
            except Exception as e:
                logger.error(f"Error applying protocol extensions during import: {e}")
                
        return module
        
    # Replace the built-in import function
    sys.modules['builtins'].__import__ = patched_import
    _hooks_applied = True
    logger.debug("Import hooks applied successfully")

# Apply hooks when this module is imported
apply_hooks()
