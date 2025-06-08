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
    logger.debug("Import hooks are no longer applied.")

# Apply hooks when this module is imported
apply_hooks()
