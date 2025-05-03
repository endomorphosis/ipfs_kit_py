#!/usr/bin/env python3
"""
Fix the server indentation in direct_mcp_server.py
"""

import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_server_indentation():
    """Fix the server indentation and scoping in direct_mcp_server.py"""
    # Read the current file
    with open("direct_mcp_server.py", "r") as f:
        lines = f.readlines()
    
    # Find the server creation line
    server_lines = []
    server_indented = False
    server_start_index = -1
    server_end_index = -1
    
    # First pass: find the server creation
    for i, line in enumerate(lines):
        if "server = FastMCP(" in line:
            server_start_index = i
            # Check if it's indented
            if line.startswith('    '):
                server_indented = True
            
            # Find where the server definition ends (looking for closing parenthesis)
            j = i
            server_lines.append(line)
            while j < len(lines) - 1 and ")" not in lines[j]:
                j += 1
                server_lines.append(lines[j])
            
            # Include the line with the closing parenthesis
            if ")" in lines[j]:
                server_end_index = j
            break
    
    # Find the register_tools line
    register_line_index = -1
    for i, line in enumerate(lines):
        if "register_ipfs_tools(server)" in line:
            register_line_index = i
            break
    
    if server_start_index == -1 or server_end_index == -1:
        logger.error("❌ Could not find server definition")
        return False
    
    # If the server is indented, we need to fix it
    if server_indented:
        logger.info("📌 Found indented server definition, fixing...")
        
        # Remove the indentation from server creation lines
        fixed_lines = []
        for line in server_lines:
            if line.startswith('    '):
                fixed_lines.append(line[4:])  # Remove 4 spaces
            else:
                fixed_lines.append(line)
        
        # Replace the original lines with the fixed ones
        for i in range(server_start_index, server_end_index + 1):
            lines[i] = fixed_lines[i - server_start_index]
    
    # Now handle the register_tools line
    if register_line_index != -1:
        # Remove the existing register_tools line
        lines.pop(register_line_index)
        
        # If there was a comment before it, remove that too
        if register_line_index > 0 and "# Register IPFS tools" in lines[register_line_index - 1]:
            lines.pop(register_line_index - 1)
    
    # Add the register_tools line right after the server definition
    register_line = "# Register IPFS tools\nregister_ipfs_tools(server)\n\n"
    lines.insert(server_end_index + 1, register_line)
    
    # Write the modified content back
    with open("direct_mcp_server.py", "w") as f:
        f.writelines(lines)
    
    logger.info("✅ Successfully fixed server indentation and register_tools placement")
    return True

if __name__ == "__main__":
    fix_server_indentation()
