#!/usr/bin/env python3
"""
Direct fix for server.py file
"""

import os

SERVER_PATH = "/home/barberb/ipfs_kit_py/docs/mcp-python-sdk/src/mcp/server/lowlevel/server.py"

def fix_server_file():
    """Fix the server.py file directly by replacing the problematic section."""
    try:
        with open(SERVER_PATH, 'r') as f:
            content = f.read()

        # Identify the section to replace
        start_marker = "                # Reset the global state after we are done"
        end_marker = "            except Exception as e:"

        # Find the positions
        start_pos = content.find(start_marker)
        if start_pos == -1:
            print("❌ Could not find the start marker in the file")
            return False

        # Find the next occurrence of the end marker after the start position
        search_pos = start_pos + len(start_marker)
        end_pos = content.find(end_marker, search_pos)
        if end_pos == -1:
            print("❌ Could not find the end marker in the file")
            return False

        # The corrected code section with proper indentation
        corrected_section = """                # Reset the global state after we are done
                if token is not None:
                    request_ctx.reset(token)

            try:
                await message.respond(response)
            except Exception as e:
                logger.warning(f"Error responding to message: {e}")
        else:
            try:
                await message.respond(
                    types.ErrorData(
                        code=types.METHOD_NOT_FOUND,
                        message="Method not found",
                    )
"""

        # Replace the problematic section
        new_content = content[:start_pos] + corrected_section + content[end_pos:]

        # Write the fixed content back to the file
        with open(SERVER_PATH, 'w') as f:
            f.write(new_content)

        print("✅ Fixed server.py file with proper indentation")
        return True
    except Exception as e:
        print(f"❌ Error fixing server.py: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists(SERVER_PATH):
        print(f"❌ File not found: {SERVER_PATH}")
        exit(1)

    if fix_server_file():
        print("✅ Successfully fixed the server.py file")
        print("Please restart the direct MCP server for the changes to take effect")
    else:
        print("❌ Failed to fix the server.py file")
        exit(1)
