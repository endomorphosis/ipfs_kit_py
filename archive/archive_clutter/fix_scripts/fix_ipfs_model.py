#!/usr/bin/env python3
"""
Fix the IPFSModel class to add missing attributes and methods
"""

import os
import sys
import inspect

# Define the path to the ipfs_model.py file
mcp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ipfs_kit_py', 'mcp')
models_dir = os.path.join(mcp_dir, 'models')
ipfs_model_path = os.path.join(models_dir, 'ipfs_model.py')

# Check if the file exists
if not os.path.exists(ipfs_model_path):
    print(f"Error: Cannot find ipfs_model.py at {ipfs_model_path}")
    sys.exit(1)

# Read the current content of the file
with open(ipfs_model_path, 'r') as f:
    content = f.read()

# Check if the class needs to be modified
if 'isolation_mode' not in content:
    # Find the IPFSModel class constructor
    constructor_match = None
    
    # Look for the __init__ method
    init_patterns = [
        "def __init__(self, host=None, port=None",
        "def __init__(self, host=",
        "def __init__(self",
    ]
    
    for pattern in init_patterns:
        if pattern in content:
            init_index = content.find(pattern)
            if init_index != -1:
                # Find the end of the method signature (the colon)
                sig_end = content.find(":", init_index)
                if sig_end != -1:
                    constructor_match = content[init_index:sig_end+1]
                    break
    
    if constructor_match:
        # Add isolation_mode parameter to the constructor if not already there
        new_constructor = constructor_match
        if "isolation_mode=" not in constructor_match:
            # If there's a closing parenthesis, insert before it
            if ")" in constructor_match:
                new_constructor = constructor_match.replace(")", ", isolation_mode=False)")
            else:
                new_constructor = constructor_match + ", isolation_mode=False):"
        
        # Update the constructor signature
        content = content.replace(constructor_match, new_constructor)
        
        # Find where to add the isolation_mode attribute in the __init__ method body
        init_body_start = content.find(":", content.find(constructor_match)) + 1
        
        # Look for common patterns like self.host = host or self.ipfs_host = host
        # to find where to insert our new attribute
        common_self_attrs = ["self.host", "self.port", "self.ipfs_host", "self.ipfs_port"]
        for attr in common_self_attrs:
            attr_pos = content.find(attr, init_body_start)
            if attr_pos != -1:
                # Find the end of this line
                line_end = content.find("\n", attr_pos)
                if line_end != -1:
                    # Insert after this line
                    content = content[:line_end+1] + "        self.isolation_mode = isolation_mode\n" + content[line_end+1:]
                    break
        
        print(f"✅ Added isolation_mode attribute to IPFSModel constructor in {ipfs_model_path}")
    else:
        print(f"❌ Could not find the constructor in {ipfs_model_path}")
else:
    print(f"✅ isolation_mode attribute already exists in {ipfs_model_path}")

# Add any missing methods or attributes
missing_methods = []

if "def get_available_backends(self" not in content:
    missing_methods.append("""
    def get_available_backends(self):
        """Get a dictionary of available storage backends."""
        return {
            "ipfs": True,
            "filecoin": False,
            "huggingface": False,
            "s3": False,
            "storacha": False,
            "lassie": False
        }
    """)

# Add the missing methods if any
if missing_methods:
    # Find a good place to insert the new methods - just before the end of the class
    class_end = content.rfind("\n\n")
    if class_end != -1:
        content = content[:class_end] + "\n" + "\n".join(missing_methods) + content[class_end:]
        print(f"✅ Added missing methods to IPFSModel in {ipfs_model_path}")
    else:
        # Just append at the end
        content += "\n" + "\n".join(missing_methods)
        print(f"✅ Added missing methods to IPFSModel at end of {ipfs_model_path}")

# Write the modified content back to the file
with open(ipfs_model_path, 'w') as f:
    f.write(content)

print("\nNow try running the MCP server again with: python ./enhanced_mcp_server_fixed.py")
