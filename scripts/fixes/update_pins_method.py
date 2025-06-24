#!/usr/bin/env python
"""
Update the pins method in IPFSSimpleAPI to accept the 'type' parameter
"""

import os
import re
import sys

def update_pins_method():
    """
    Update the pins method in IPFSSimpleAPI to accept the 'type' parameter
    """
    source_file = os.path.join(os.path.dirname(__file__), 'ipfs_kit_py', 'high_level_api.py')
    backup_file = source_file + '.bak_update_pins'

    # Create backup
    print(f"Creating backup at {backup_file}")
    with open(source_file, 'r') as src:
        with open(backup_file, 'w') as dst:
            dst.write(src.read())

    # Read the source file
    with open(source_file, 'r') as f:
        lines = f.readlines()

    # Find the pins method
    pins_method_idx = None
    for i, line in enumerate(lines):
        if "def pins(self)" in line:
            pins_method_idx = i
            break

    if pins_method_idx is None:
        print("Could not find pins method in IPFSSimpleAPI class")
        return False

    # Update the pins method to match list_pins parameters
    updated_pins_method = [
        "    def pins(self, type=None, quiet=None, verify=None, **kwargs):\n",
        "        \"\"\"Alias for list_pins method.\"\"\"\n",
        "        return self.list_pins(type=type, quiet=quiet, verify=verify, **kwargs)\n"
    ]

    # Replace the pins method
    start_idx = pins_method_idx
    end_idx = pins_method_idx + 3  # Assumes 3 lines for the basic method
    lines = lines[:start_idx] + updated_pins_method + lines[end_idx:]

    # Write the updated content
    with open(source_file, 'w') as f:
        f.writelines(lines)

    print("Successfully updated 'pins' method in IPFSSimpleAPI class")
    return True

if __name__ == "__main__":
    if update_pins_method():
        sys.exit(0)
    sys.exit(1)
