#!/usr/bin/env python3
"""
Debug script to check lotus_kit module location and add LOTUS_KIT_AVAILABLE directly.
"""

import sys
import os
import importlib

# Try to import the module
try:
    import ipfs_kit_py.lotus_kit
    module_file = ipfs_kit_py.lotus_kit.__file__
    print(f"lotus_kit module location: {module_file}")
    
    # Check if LOTUS_KIT_AVAILABLE is defined
    if hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'):
        print(f"LOTUS_KIT_AVAILABLE is already defined: {ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE}")
    else:
        print("LOTUS_KIT_AVAILABLE is not defined, adding it now...")
        
        # Add the constant directly to the module
        ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE = True
        print(f"Added LOTUS_KIT_AVAILABLE = {ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE}")
        
        # Now try to update the source file
        if os.path.exists(module_file):
            with open(module_file, 'r') as f:
                content = f.read()
                
            if 'LOTUS_KIT_AVAILABLE' not in content:
                print(f"Adding LOTUS_KIT_AVAILABLE to {module_file}")
                import_section_end = content.find("import requests")
                if import_section_end != -1:
                    # Find the line after the imports
                    line_end = content.find("\n", import_section_end)
                    if line_end != -1:
                        new_content = content[:line_end+1] + "\n# Flag to indicate lotus_kit is available\nLOTUS_KIT_AVAILABLE = True\n" + content[line_end+1:]
                        
                        # Write the modified content back
                        with open(module_file, 'w') as f:
                            f.write(new_content)
                        print(f"Successfully updated {module_file}")
                    else:
                        print("Could not find end of import section")
                else:
                    print("Could not find import section in the file")
            else:
                print(f"LOTUS_KIT_AVAILABLE already exists in {module_file}")
        else:
            print(f"Could not find module file: {module_file}")
            
    # Reload the module to ensure changes take effect
    print("Reloading the module...")
    importlib.reload(ipfs_kit_py.lotus_kit)
    
    # Check again
    if hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'):
        print(f"After reload: LOTUS_KIT_AVAILABLE = {ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE}")
    else:
        print("After reload: LOTUS_KIT_AVAILABLE is still not defined")
        
except ImportError as e:
    print(f"Error importing ipfs_kit_py.lotus_kit: {e}")
    
print("\nPython path:")
for path in sys.path:
    print(f"  {path}")