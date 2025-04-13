#!/usr/bin/env python3
"""
Script to permanently fix the pins method in the IPFSSimpleAPI class.
"""

import os
import re
import sys
import shutil

def fix_pins_method():
    """Fix the pins method in high_level_api.py."""
    # Path to high_level_api.py
    api_path = os.path.join(os.path.dirname(__file__), 'ipfs_kit_py', 'high_level_api.py')
    
    # Make sure the file exists
    if not os.path.exists(api_path):
        print(f"Error: File not found at {api_path}")
        return False
    
    # Create backup
    backup_path = f"{api_path}.bak_fix_pins"
    shutil.copy2(api_path, backup_path)
    print(f"Created backup at {backup_path}")
    
    # Read the file
    with open(api_path, 'r') as f:
        content = f.read()
    
    # Look for the pins method
    pins_pattern = r'def pins\(self[^)]*\):'
    pins_match = re.search(pins_pattern, content)
    
    if not pins_match:
        print("Error: pins method not found in the file")
        return False
    
    # Get the current pins method signature
    current_signature = pins_match.group(0)
    
    # Check if the method already accepts the required parameters
    if "type" in current_signature:
        print("pins method already accepts 'type' parameter. Ensuring it has all needed parameters...")
        if all(param in current_signature for param in ["type", "quiet", "verify"]):
            print("All required parameters already exist. Nothing to fix.")
            return True
    
    # Fix the pins method
    fixed_content = re.sub(
        pins_pattern,
        "def pins(self, type=None, quiet=None, verify=None, **kwargs):",
        content
    )
    
    # Make sure the method body calls list_pins with the parameters
    body_pattern = r'def pins\(self[^)]*\):.*?return self\.list_pins\([^)]*\)'
    body_regex = re.compile(body_pattern, re.DOTALL)
    body_match = body_regex.search(content)
    
    if body_match:
        fixed_content = re.sub(
            body_pattern,
            "def pins(self, type=None, quiet=None, verify=None, **kwargs):\n        \"\"\"Alias for list_pins method.\"\"\"\n        return self.list_pins(type=type, quiet=quiet, verify=verify, **kwargs)",
            fixed_content, 
            flags=re.DOTALL
        )
    
    # Write the fixed content back to the file
    with open(api_path, 'w') as f:
        f.write(fixed_content)
    
    print("Successfully fixed the pins method in IPFSSimpleAPI class")
    return True

if __name__ == "__main__":
    success = fix_pins_method()
    if success:
        print("Fixed high_level_api.py. Restart the server for changes to take effect.")
        sys.exit(0)
    else:
        print("Failed to fix high_level_api.py")
        sys.exit(1)