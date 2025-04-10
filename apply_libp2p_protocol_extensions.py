#!/usr/bin/env python3
"""
Utility script to apply libp2p protocol extensions to IPFSLibp2pPeer.

This script applies GossipSub protocol and enhanced DHT discovery methods
to the IPFSLibp2pPeer class using monkey patching. The script should be
run once during the package installation or initialization process.
"""

import logging
import importlib.util
import sys
import os
from typing import Type, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def apply_protocol_extensions():
    """Apply protocol extensions to the IPFSLibp2pPeer class."""
    try:
        # First try to import the module and class
        logger.info("Applying GossipSub and enhanced DHT discovery protocols to IPFSLibp2pPeer...")
        
        # Import the libp2p_peer module
        spec = importlib.util.find_spec("ipfs_kit_py.libp2p_peer")
        if spec is None:
            logger.error("Could not find ipfs_kit_py.libp2p_peer module")
            return False
            
        libp2p_peer_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(libp2p_peer_module)
        
        # Get the IPFSLibp2pPeer class
        if not hasattr(libp2p_peer_module, "IPFSLibp2pPeer"):
            logger.error("IPFSLibp2pPeer class not found in libp2p_peer module")
            return False
            
        IPFSLibp2pPeer = getattr(libp2p_peer_module, "IPFSLibp2pPeer")
        
        # Import the extension functions
        try:
            from ipfs_kit_py.libp2p.gossipsub_protocol import add_gossipsub_methods, add_enhanced_dht_discovery_methods
        except ImportError as e:
            logger.error(f"Could not import protocol extension functions: {e}")
            return False
            
        # Apply the extensions
        logger.info("Adding GossipSub protocol methods...")
        IPFSLibp2pPeer = add_gossipsub_methods(IPFSLibp2pPeer)
        
        logger.info("Adding enhanced DHT discovery methods...")
        IPFSLibp2pPeer = add_enhanced_dht_discovery_methods(IPFSLibp2pPeer)
        
        # Update the class in the module
        setattr(libp2p_peer_module, "IPFSLibp2pPeer", IPFSLibp2pPeer)
        
        # Verify that methods were added
        has_gossipsub = (hasattr(IPFSLibp2pPeer, "publish_to_topic") and 
                         hasattr(IPFSLibp2pPeer, "subscribe_to_topic") and 
                         hasattr(IPFSLibp2pPeer, "unsubscribe_from_topic") and 
                         hasattr(IPFSLibp2pPeer, "get_topic_peers") and 
                         hasattr(IPFSLibp2pPeer, "list_topics"))
                         
        has_enhanced_dht = (hasattr(IPFSLibp2pPeer, "integrate_enhanced_dht_discovery") and 
                           hasattr(IPFSLibp2pPeer, "find_providers_enhanced"))
        
        if has_gossipsub and has_enhanced_dht:
            logger.info("✅ Successfully applied protocol extensions to IPFSLibp2pPeer")
            return True
        else:
            logger.error("❌ Failed to apply protocol extensions to IPFSLibp2pPeer")
            return False
            
    except Exception as e:
        logger.error(f"Error applying protocol extensions: {e}", exc_info=True)
        return False

def create_hooks():
    """Create import hooks to automatically apply extensions when module is imported."""
    try:
        # Create a hook file in the ipfs_kit_py/libp2p directory
        hooks_file = os.path.join(os.path.dirname(__file__), "ipfs_kit_py", "libp2p", "hooks.py")
        
        hooks_content = """'''
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
"""
        
        # Write the hooks file
        with open(hooks_file, 'w') as f:
            f.write(hooks_content)
        
        logger.info(f"Created import hooks file at {hooks_file}")
        
        # Create an __init__.py update script
        init_patch_file = os.path.join(os.path.dirname(__file__), "update_init.py")
        
        init_patch_content = """#!/usr/bin/env python3
'''
Update the __init__.py file to include import hooks.

This script adds an import statement for the hooks module to the
ipfs_kit_py/libp2p/__init__.py file to ensure hooks are loaded.
'''

import os
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_init_file():
    '''Update the __init__.py file to include import hooks.'''
    # Find the __init__.py file
    init_file = os.path.join(os.path.dirname(__file__), "ipfs_kit_py", "libp2p", "__init__.py")
    
    if not os.path.exists(init_file):
        logger.error(f"__init__.py file not found at {init_file}")
        return False
        
    # Read the current content
    with open(init_file, 'r') as f:
        content = f.read()
        
    # Check if hooks import already exists
    if "import ipfs_kit_py.libp2p.hooks" in content:
        logger.info("Hooks import already exists in __init__.py")
        return True
        
    # Add the import statement after other imports
    import_pattern = r'(import\s+.*?\n\n)'
    
    if re.search(import_pattern, content, re.DOTALL):
        # Add after the last import block
        new_content = re.sub(
            import_pattern,
            r'\\1# Import hooks to automatically apply protocol extensions\nimport ipfs_kit_py.libp2p.hooks\n\n',
            content,
            count=1,
            flags=re.DOTALL
        )
    else:
        # Add at the beginning of the file
        new_content = "# Import hooks to automatically apply protocol extensions\nimport ipfs_kit_py.libp2p.hooks\n\n" + content
        
    # Write the updated content
    with open(init_file, 'w') as f:
        f.write(new_content)
        
    logger.info(f"Updated {init_file} with hooks import")
    return True

if __name__ == "__main__":
    update_init_file()
"""
        
        # Write the init patch script
        with open(init_patch_file, 'w') as f:
            f.write(init_patch_content)
            
        logger.info(f"Created init patch script at {init_patch_file}")
        
        # Make the script executable
        os.chmod(init_patch_file, 0o755)
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating hooks: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Apply protocol extensions directly
    success = apply_protocol_extensions()
    
    # Create hooks for automatic application
    if success:
        hooks_success = create_hooks()
        if hooks_success:
            logger.info("Created import hooks for automatic protocol extension application")
    
    sys.exit(0 if success else 1)