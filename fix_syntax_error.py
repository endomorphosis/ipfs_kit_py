#!/usr/bin/env python3
"""
Fix Syntax Error in IPFS Tool Adapters

This script fixes the syntax error in ipfs_tool_adapters.py
"""

import os

def fix_syntax_error():
    """Fix the syntax error in ipfs_tool_adapters.py"""
    filepath = "/home/barberb/ipfs_kit_py/ipfs_tool_adapters.py"
    
    # Read the file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the problematic section
    problem_section = """                content = ctx.content
            elif hasattr(ctx, 'data'):
                content = ctx.data
            elif hasattr(ctx, 'text'):"""
    
    # Create the fixed section
    fixed_section = """                # Check attribute access one by one
                if hasattr(ctx, 'content'):
                    content = ctx.content
                elif hasattr(ctx, 'data'):
                    content = ctx.data
                elif hasattr(ctx, 'text'):"""
    
    # Replace the problem section with the fixed section
    fixed_content = content.replace(problem_section, fixed_section)
    
    # Write the fixed content back to the file
    with open(filepath, 'w') as f:
        f.write(fixed_content)
    
    print(f"Fixed syntax error in {filepath}")

if __name__ == "__main__":
    print("Fixing syntax error in ipfs_tool_adapters.py...")
    fix_syntax_error()
    print("Done")
