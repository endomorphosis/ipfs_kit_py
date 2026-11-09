#!/usr/bin/env python3
"""
Fix the indentation issue in the if block around line 1021-1024
"""

import os
import sys
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_if_block_indentation():
    """Fix the indentation issue in the if block"""
    try:
        filename = "direct_mcp_server_with_tools.py"
        # Check if the file exists
        if not os.path.exists(filename):
            logger.error(f"{filename} not found")
            return False

        # Read the file content
        with open(filename, "r") as f:
            content = f.read()

        # Look for the problematic pattern
        pattern = r'([ ]*if method == \'get_tools\':\n[ ]*# Get all registered tools\n)# Enhanced IPFS tools registered\ntools = \['
        match = re.search(pattern, content)

        if match:
            # Get the indentation from the first line of the if block
            if_line = match.group(1)
            indent_match = re.match(r'^([ ]*)', if_line)
            base_indent = indent_match.group(1) if indent_match else ''

            # The if block needs an extra level of indentation
            extra_indent = base_indent + '    '

            # Replace with properly indented code
            replacement = f"{if_line}{extra_indent}# Enhanced IPFS tools registered\n{extra_indent}tools = ["
            fixed_content = content.replace(match.group(0), replacement)

            # Ensure the entire tools array is properly indented
            # Find the start of the tools list
            tools_match = re.search(r'tools = \[\n([ ]*)\{', fixed_content)
            if tools_match:
                current_indent = tools_match.group(1)
                correct_indent = extra_indent + '    '  # Indent of if block + 4 spaces

                # If the current indentation is not correct, fix it
                if current_indent != correct_indent:
                    # Find the whole tools block
                    tools_block_pattern = r'tools = \[\n(.*?)\n[ ]*\]'
                    tools_block_match = re.search(tools_block_pattern, fixed_content, re.DOTALL)
                    if tools_block_match:
                        tools_block = tools_block_match.group(0)
                        lines = tools_block.split('\n')

                        # Fix indentation for each line except the first and last
                        for i in range(1, len(lines) - 1):
                            # Remove current indentation and add correct indentation
                            stripped_line = lines[i].lstrip()
                            lines[i] = correct_indent + stripped_line

                        # Fix the closing bracket indentation
                        lines[-1] = extra_indent + ']'

                        # Reconstruct the block with fixed indentation
                        fixed_tools_block = '\n'.join(lines)
                        fixed_content = fixed_content.replace(tools_block_match.group(0), fixed_tools_block)

            # Write the fixed content back to the file
            with open(filename, "w") as f:
                f.write(fixed_content)

            logger.info(f"Fixed indentation in the if block at lines 1021-1024")
            return True
        else:
            logger.error("Could not find the expected pattern in the file")
            return False

    except Exception as e:
        logger.error(f"Error fixing indentation: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to fix indentation issue in the if block...")

    # Fix indentation
    if not fix_if_block_indentation():
        logger.error("❌ Failed to fix indentation issue")
        return 1

    logger.info("\n✅ Successfully fixed indentation issue in the if block")
    logger.info("You can now run the server with './restart_mcp_with_tools.sh'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
