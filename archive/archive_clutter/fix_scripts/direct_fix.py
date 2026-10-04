#!/usr/bin/env python3
"""
Direct fix script to properly add LOTUS_KIT_AVAILABLE to the lotus_kit module.
"""

import sys
import os
import importlib
import inspect

print("Checking ipfs_kit_py structure...")

# Check what type of object lotus_kit is
try:
    import ipfs_kit_py
    
    print(f"ipfs_kit_py.__file__ = {ipfs_kit_py.__file__}")
    print(f"dir(ipfs_kit_py) = {dir(ipfs_kit_py)}")
    
    # Check if lotus_kit is in the directory listing
    if 'lotus_kit' in dir(ipfs_kit_py):
        lotus_kit_obj = getattr(ipfs_kit_py, 'lotus_kit')
        print(f"Type of ipfs_kit_py.lotus_kit: {type(lotus_kit_obj)}")
        print(f"Is class: {inspect.isclass(lotus_kit_obj)}")
        print(f"Is module: {inspect.ismodule(lotus_kit_obj)}")
        
        # If it's a class, we need to add the constant to the module containing the class
        if inspect.isclass(lotus_kit_obj):
            print("lotus_kit is a class, looking for its module...")
            module_name = lotus_kit_obj.__module__
            print(f"lotus_kit class is defined in module: {module_name}")
            
            # Import the module containing the class
            module = importlib.import_module(module_name)
            print(f"Module file: {module.__file__}")
            
            # Add LOTUS_KIT_AVAILABLE to the module
            if not hasattr(module, 'LOTUS_KIT_AVAILABLE'):
                print("Adding LOTUS_KIT_AVAILABLE to the module...")
                module.LOTUS_KIT_AVAILABLE = True
                print(f"Added: {module.LOTUS_KIT_AVAILABLE}")
                
                # Now directly add it to the file
                with open(module.__file__, 'r') as f:
                    content = f.read()
                    
                # Find the class definition
                class_def = f"class lotus_kit:"
                if class_def in content:
                    # Add the constant just before the class definition
                    insert_index = content.find(class_def)
                    new_content = content[:insert_index] + "\n# Flag to indicate lotus_kit is available\nLOTUS_KIT_AVAILABLE = True\n\n" + content[insert_index:]
                    
                    # Write the updated file
                    with open(module.__file__, 'w') as f:
                        f.write(new_content)
                    print(f"Updated {module.__file__} with LOTUS_KIT_AVAILABLE constant")
                else:
                    print(f"Could not find '{class_def}' in the file")
            else:
                print(f"LOTUS_KIT_AVAILABLE already exists in module: {module.LOTUS_KIT_AVAILABLE}")
    else:
        print("lotus_kit not found in ipfs_kit_py module")
        
    # Look for lotus_kit.py file
    pkg_dir = os.path.dirname(ipfs_kit_py.__file__)
    lotus_kit_file = os.path.join(pkg_dir, "lotus_kit.py")
    if os.path.exists(lotus_kit_file):
        print(f"Found lotus_kit.py at {lotus_kit_file}")
        
        # Check file content
        with open(lotus_kit_file, 'r') as f:
            content = f.read()
            
        # Look for LOTUS_KIT_AVAILABLE in the file
        if 'LOTUS_KIT_AVAILABLE' not in content:
            # Find a suitable location to add the constant
            class_def = "class lotus_kit:"
            if class_def in content:
                # Add the constant just before the class definition
                insert_index = content.find(class_def)
                new_content = content[:insert_index] + "\n# Flag to indicate lotus_kit is available\nLOTUS_KIT_AVAILABLE = True\n\n" + content[insert_index:]
                
                # Write the updated file
                with open(lotus_kit_file, 'w') as f:
                    f.write(new_content)
                print(f"Updated {lotus_kit_file} with LOTUS_KIT_AVAILABLE constant")
            else:
                print(f"Could not find '{class_def}' in the file")
        else:
            print(f"LOTUS_KIT_AVAILABLE already exists in {lotus_kit_file}")
    else:
        print(f"lotus_kit.py not found at {lotus_kit_file}")
        
except ImportError as e:
    print(f"Error importing ipfs_kit_py: {e}")
except Exception as e:
    print(f"Error: {e}")
    
print("\nNow let's verify the fixes worked:")
try:
    # Force reload all relevant modules
    if 'ipfs_kit_py.lotus_kit' in sys.modules:
        del sys.modules['ipfs_kit_py.lotus_kit']
    if 'ipfs_kit_py' in sys.modules:
        del sys.modules['ipfs_kit_py']
        
    # Import again
    import ipfs_kit_py.lotus_kit
    
    # Check if LOTUS_KIT_AVAILABLE exists
    if hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'):
        print(f"SUCCESS: LOTUS_KIT_AVAILABLE is now defined as {ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE}")
    else:
        print("FAILED: LOTUS_KIT_AVAILABLE is still not defined")
except Exception as e:
    print(f"Error during verification: {e}")