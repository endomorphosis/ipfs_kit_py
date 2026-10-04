#!/usr/bin/env python3
"""
Patch to fix coroutine 'LibP2PModel.is_available' never awaited warning in MCP discovery model.

The issue occurs in _detect_available_features where the async is_available() method
is called without being awaited. This patch modifies that method to use 
_is_available_sync() instead, which is the synchronous version of is_available().
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def patch_mcp_discovery_model():
    """
    Patch the MCP discovery model to fix coroutine warnings.
    """
    try:
        # Path to the file we need to patch
        file_path = os.path.join("ipfs_kit_py", "mcp", "models", "mcp_discovery_model.py")
        
        # Check if file exists
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Fix 1: In _detect_available_features method, use _is_available_sync instead of is_available
        # Original code:
        # if hasattr(self.libp2p_model, 'is_available'):
        #     if self.libp2p_model.is_available():
        #         features.append(MCPServerCapabilities.LIBP2P)
        
        # Look for the problematic code section
        original_code = """
                if hasattr(self.libp2p_model, 'is_available'):
                    # Fallback to checking if the attribute exists (but don't call it if it's async)
                    features.append(MCPServerCapabilities.LIBP2P)"""
        
        fixed_code = """
                if hasattr(self.libp2p_model, 'is_available'):
                    # Use synchronous version to avoid async coroutine warning
                    if hasattr(self.libp2p_model, '_is_available_sync'):
                        if self.libp2p_model._is_available_sync():
                            features.append(MCPServerCapabilities.LIBP2P)
                    else:
                        # Fallback to checking if the attribute exists (but don't call it if it's async)
                        features.append(MCPServerCapabilities.LIBP2P)"""
        
        # Replace the code
        new_content = content.replace(original_code, fixed_code)
        
        # Fix 2: In the __init__ method, fix the direct call to is_available
        original_init_code = """
                # Only update if check succeeds
                available = self.libp2p_model.is_available()
                self.has_libp2p = bool(available)  # Convert to bool for safety"""
        
        fixed_init_code = """
                # Use synchronous version to avoid async coroutine warning
                if hasattr(self.libp2p_model, '_is_available_sync'):
                    available = self.libp2p_model._is_available_sync()
                    self.has_libp2p = bool(available)  # Convert to bool for safety
                else:
                    # Fallback to checking attribute existence without calling
                    self.has_libp2p = True"""
        
        # Replace the init code
        new_content = new_content.replace(original_init_code, fixed_init_code)
        
        # Write the patched content back to the file
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Successfully patched {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        return False

if __name__ == "__main__":
    logger.info("Applying patch to fix LibP2P is_available coroutine warnings...")
    success = patch_mcp_discovery_model()
    if success:
        logger.info("Patch applied successfully")
        sys.exit(0)
    else:
        logger.error("Failed to apply patch")
        sys.exit(1)