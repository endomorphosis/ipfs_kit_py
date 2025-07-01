#!/usr/bin/env python
"""
Add missing 'pins' method to the IPFSSimpleAPI class in high_level_api.py
"""

import os
import re
import sys

def add_pins_method():
    """
    Add the pins method to IPFSSimpleAPI class in high_level_api.py
    """
    source_file = os.path.join(os.path.dirname(__file__), 'ipfs_kit_py', 'high_level_api.py')
    backup_file = source_file + '.bak_add_pins'

    # Create backup
    print(f"Creating backup at {backup_file}")
    with open(source_file, 'r') as src:
        with open(backup_file, 'w') as dst:
            dst.write(src.read())

    # Read the source file
    with open(source_file, 'r') as f:
        lines = f.readlines()

    # Find the class definition line
    class_line_idx = None
    for i, line in enumerate(lines):
        if "class IPFSSimpleAPI" in line:
            class_line_idx = i
            break

    if class_line_idx is None:
        print("Could not find IPFSSimpleAPI class in high_level_api.py")
        return False

    # Find the list_pins method
    list_pins_line_idx = None
    for i, line in enumerate(lines[class_line_idx:], class_line_idx):
        if "def list_pins" in line:
            list_pins_line_idx = i
            break

    if list_pins_line_idx is None:
        print("Could not find list_pins method in IPFSSimpleAPI class")
        return False

    # Find the end of the list_pins method
    end_list_pins_idx = None
    indent_level = len(lines[list_pins_line_idx]) - len(lines[list_pins_line_idx].lstrip())
    for i, line in enumerate(lines[list_pins_line_idx+1:], list_pins_line_idx+1):
        if line.strip() and len(line) - len(line.lstrip()) <= indent_level:
            if "def " in line:
                # Next method found
                end_list_pins_idx = i
                break

    if end_list_pins_idx is None:
        # Method might be at the end of the class or file
        for i, line in enumerate(lines[list_pins_line_idx+1:], list_pins_line_idx+1):
            if line.strip() and len(line) - len(line.lstrip()) < indent_level:
                # End of class found
                end_list_pins_idx = i
                break

        if end_list_pins_idx is None:
            # Use end of file
            end_list_pins_idx = len(lines)

    # Add the pins method
    pins_method_lines = [
        "\n",
        "    def pins(self):\n",
        "        \"\"\"Alias for list_pins method.\"\"\"\n",
        "        return self.list_pins()\n"
    ]

    # Insert the pins method after the list_pins method
    lines = lines[:end_list_pins_idx] + pins_method_lines + lines[end_list_pins_idx:]

    # Write the updated content
    with open(source_file, 'w') as f:
        f.writelines(lines)

    print("Successfully added 'pins' method to IPFSSimpleAPI class")
    return True

if __name__ == "__main__":
    if add_pins_method():
        sys.exit(0)
    sys.exit(1)
