#!/usr/bin/env python3
"""Fix syntax error in IPFS controller."""

import os
import sys

def fix_ipfs_controller():
    """Fix syntax error in IPFS controller file."""
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py'
    
    # Make a backup first
    backup_path = file_path + '.bak_syntax_fix'
    os.system(f"cp {file_path} {backup_path}")
    print(f"Created backup at {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find and fix the issue with the else statement
    for i in range(len(lines)):
        if i < len(lines) - 3 and "else:" in lines[i] and "# Standard IPFS daemon check" in lines[i+1]:
            # We found the problematic else section
            print(f"Found problematic else statement at line {i+1}")
            
            # Ensure the next line is properly indented
            if "# Handle daemon type specific checks" in lines[i+2]:
                # Need to fix this line
                indent = " " * 20
                lines[i+1] = indent + "# Standard IPFS daemon check\n"
                lines.insert(i+2, indent + "result = self.ipfs_model.check_daemon_status(daemon_type)\n")
                print("Fixed indentation after else statement")
                break
    
    # Write fixed file
    with open(file_path, 'w') as f:
        f.writelines(lines)
    
    print("Fixed IPFS controller syntax")
    return True

if __name__ == "__main__":
    fix_ipfs_controller()