#!/usr/bin/env python3
"""
Fix syntax error in direct_mcp_server_with_tools.py
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_syntax_error():
    """Fix the syntax error in direct_mcp_server_with_tools.py"""
    try:
        # Check if the file exists
        if not os.path.exists("direct_mcp_server_with_tools.py"):
            logger.error("direct_mcp_server_with_tools.py not found")
            return False
        
        # Read the file content
        with open("direct_mcp_server_with_tools.py", "r") as f:
            content = f.read()
        
        # Find the problematic section
        if "tools = [" in content and "])" in content:
            # Fix the syntax error by replacing "])" with "]"
            fixed_content = content.replace("])", "]")
            
            # Write the fixed content back to the file
            with open("direct_mcp_server_with_tools.py", "w") as f:
                f.write(fixed_content)
            
            logger.info("✅ Fixed syntax error in direct_mcp_server_with_tools.py")
            return True
        else:
            # If we can't find the exact issue, let's try a more general approach
            # Find the last occurrence of the tools array
            tools_start = content.rfind("tools = [")
            if tools_start != -1:
                # Find the matching closing bracket
                bracket_count = 1
                pos = tools_start + len("tools = [")
                while pos < len(content) and bracket_count > 0:
                    if content[pos] == '[':
                        bracket_count += 1
                    elif content[pos] == ']':
                        bracket_count -= 1
                    pos += 1
                
                if pos < len(content):
                    # We found the closing bracket, now check if there's an extra parenthesis
                    if pos < len(content) and content[pos] == ')':
                        # Remove the extra parenthesis
                        fixed_content = content[:pos] + content[pos+1:]
                        
                        # Write the fixed content back to the file
                        with open("direct_mcp_server_with_tools.py", "w") as f:
                            f.write(fixed_content)
                        
                        logger.info("✅ Fixed syntax error in direct_mcp_server_with_tools.py")
                        return True
            
            # If we still can't fix it, let's try to find the unmatched parenthesis
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.strip() == ')':
                    # This is likely the unmatched parenthesis
                    lines[i] = '# Removed unmatched parenthesis'
                    
                    # Write the fixed content back to the file
                    with open("direct_mcp_server_with_tools.py", "w") as f:
                        f.write('\n'.join(lines))
                    
                    logger.info("✅ Fixed syntax error in direct_mcp_server_with_tools.py")
                    return True
            
            logger.error("Could not identify the syntax error in direct_mcp_server_with_tools.py")
            return False
    
    except Exception as e:
        logger.error(f"Error fixing syntax error: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix syntax error in direct_mcp_server_with_tools.py...")
    
    # Fix syntax error
    if not fix_syntax_error():
        logger.error("❌ Failed to fix syntax error")
        return 1
    
    logger.info("\n✅ Successfully fixed syntax error in direct_mcp_server_with_tools.py")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
