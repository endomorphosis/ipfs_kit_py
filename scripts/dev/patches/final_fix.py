#!/usr/bin/env python3
"""
Final direct fix for ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE.

This script directly modifies the module structure to ensure the constant is available
at both levels of the namespace.
"""

import sys
import importlib
import types

def apply_fix():
    """Apply the fix to make LOTUS_KIT_AVAILABLE accessible."""
    # First, try direct import
    try:
        import ipfs_kit_py
        
        # Check if LOTUS_KIT_AVAILABLE exists at the package level
        if hasattr(ipfs_kit_py, 'LOTUS_KIT_AVAILABLE'):
            print(f"LOTUS_KIT_AVAILABLE exists at package level: {ipfs_kit_py.LOTUS_KIT_AVAILABLE}")
            
            # Now ensure it's also available in the lotus_kit module
            if hasattr(ipfs_kit_py, 'lotus_kit'):
                # Get the module where lotus_kit is defined
                lotus_kit_class = ipfs_kit_py.lotus_kit
                if hasattr(lotus_kit_class, '__module__'):
                    module_name = lotus_kit_class.__module__
                    print(f"lotus_kit is defined in module: {module_name}")
                    
                    # Get or create the module
                    if module_name in sys.modules:
                        module = sys.modules[module_name]
                    else:
                        # Import the module
                        module = importlib.import_module(module_name)
                    
                    # Add LOTUS_KIT_AVAILABLE to the module
                    if not hasattr(module, 'LOTUS_KIT_AVAILABLE'):
                        module.LOTUS_KIT_AVAILABLE = ipfs_kit_py.LOTUS_KIT_AVAILABLE
                        print(f"Added LOTUS_KIT_AVAILABLE to {module_name}")
                    else:
                        print(f"LOTUS_KIT_AVAILABLE already defined in {module_name}")
                        
                    # The most important part - add it to the lotus_kit class namespace
                    lotus_kit_class.LOTUS_KIT_AVAILABLE = ipfs_kit_py.LOTUS_KIT_AVAILABLE
                    print(f"Added LOTUS_KIT_AVAILABLE to lotus_kit class namespace")
                else:
                    print("lotus_kit object doesn't have __module__ attribute")
            else:
                print("lotus_kit not found in ipfs_kit_py")
        else:
            # Add it to the package level
            ipfs_kit_py.LOTUS_KIT_AVAILABLE = True
            print(f"Added LOTUS_KIT_AVAILABLE to package level: {ipfs_kit_py.LOTUS_KIT_AVAILABLE}")
            
            # Then recursively call this function to add it to the module level
            apply_fix()
            
        return True
    except Exception as e:
        print(f"Error in apply_fix: {e}")
        return False

def verify_fix():
    """Verify that the fix has been applied successfully."""
    try:
        # Clear module caches
        for modname in list(sys.modules.keys()):
            if modname.startswith('ipfs_kit_py'):
                del sys.modules[modname]
                
        # Import fresh
        import ipfs_kit_py.lotus_kit
        
        # Try to access the constant
        if hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'):
            value = ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE
            print(f"SUCCESS: ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE = {value}")
            return True
        else:
            print("FAILED: ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE still not defined")
            return False
    except Exception as e:
        print(f"Error in verify_fix: {e}")
        return False

if __name__ == "__main__":
    print("Applying final fix for LOTUS_KIT_AVAILABLE...")
    success = apply_fix()
    
    if success:
        print("\nVerifying fix...")
        verify_success = verify_fix()
        
        if verify_success:
            print("\nFIX SUCCESSFUL! LOTUS_KIT_AVAILABLE is now properly defined.")
        else:
            print("\nWarning: Fix applied but verification failed.")
    else:
        print("\nFailed to apply fix.")