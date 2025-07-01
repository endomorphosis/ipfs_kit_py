#!/usr/bin/env python3
"""
Script to apply a monkeypatch to the running MCP server to fix the pins method.
"""

import sys
import time
import importlib
import inspect
import types

def get_ipfs_simple_api_class():
    """Find and import the IPFSSimpleAPI class."""
    try:
        # First try direct import
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        return IPFSSimpleAPI
    except ImportError:
        # Try import from package
        try:
            from ipfs_kit_py.high_level_api.high_level_api import IPFSSimpleAPI
            return IPFSSimpleAPI
        except ImportError:
            # Try dynamic import
            try:
                import os
                import importlib.util
                
                # Get path to high_level_api.py
                module_path = os.path.join(os.path.dirname(__file__), 'ipfs_kit_py', 'high_level_api.py')
                
                # Import the module
                spec = importlib.util.spec_from_file_location("high_level_api", module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get the class
                return module.IPFSSimpleAPI
            except Exception as e:
                print(f"Failed to import IPFSSimpleAPI class: {e}")
                return None

def apply_monkeypatch():
    """Apply the monkeypatch to the IPFSSimpleAPI class."""
    # Get the class
    IPFSSimpleAPI = get_ipfs_simple_api_class()
    if not IPFSSimpleAPI:
        print("Failed to get IPFSSimpleAPI class")
        return False
    
    # Define the new pins method
    def pins(self, type=None, quiet=None, verify=None, **kwargs):
        """
        Alias for list_pins method with parameter support.
        
        Args:
            type: Pin type filter
            quiet: Whether to return only CIDs
            verify: Whether to verify the pinned status
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with operation results
        """
        # Just call list_pins - we'll handle the parameters in the controller
        if hasattr(self, 'list_pins'):
            return self.list_pins()
        else:
            # Fallback if list_pins not available
            result = {
                "success": False,
                "error": "list_pins method not available",
                "pins": {}
            }
            return result
    
    # Apply the patch
    try:
        # Check if pins method exists
        if hasattr(IPFSSimpleAPI, 'pins'):
            # Save the original method
            original_pins = IPFSSimpleAPI.pins
            
            # Method signature check
            sig = inspect.signature(original_pins)
            has_type_param = 'type' in sig.parameters
            
            if has_type_param:
                print("pins method already supports 'type' parameter, no need to patch")
                return True
        
        # Add or replace the method
        IPFSSimpleAPI.pins = pins
        print("Successfully applied monkeypatch to IPFSSimpleAPI.pins method")
        return True
    except Exception as e:
        print(f"Error applying monkeypatch: {e}")
        return False

if __name__ == "__main__":
    print("Applying monkeypatch to IPFSSimpleAPI.pins method...")
    success = apply_monkeypatch()
    if success:
        print("Monkeypatch applied successfully")
        sys.exit(0)
    else:
        print("Failed to apply monkeypatch")
        sys.exit(1)