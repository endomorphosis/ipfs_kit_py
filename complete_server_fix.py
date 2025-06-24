#!/usr/bin/env python3
"""
Complete server.py fix

This script completely rewrites the problematic section of the server.py file
to fix all syntax issues.
"""

import os
import sys

SERVER_PATH = "/home/barberb/ipfs_kit_py/docs/mcp-python-sdk/src/mcp/server/lowlevel/server.py"

def fix_server_file():
    """Fix the server.py file completely."""
    try:
        with open(SERVER_PATH, 'r') as f:
            content = f.read()

        # Find the start of the method
        method_start = content.find("async def _handle_request(")
        if method_start == -1:
            print("❌ Could not find the _handle_request method")
            return False

        # Find where the method ends (next def or end of file)
        next_def = content.find("\n    async def", method_start + 1)
        if next_def == -1:
            next_def = len(content)

        # Extract the method implementation
        method_impl = content[method_start:next_def]

        # Identify the section we want to replace
        start_marker = "            finally:"
        end_marker = "\n    async def _handle_notification"

        start_pos = method_impl.find(start_marker)
        if start_pos == -1:
            print("❌ Could not find the finally block")
            return False

        # Create the corrected implementation
        corrected_section = """            finally:
                # Reset the global state after we are done
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
                )
            except Exception as e:
                logger.warning(f"Error responding to error message: {e}")"""

        # Replace in the method implementation
        method_end = method_impl.find(end_marker, start_pos)
        if method_end == -1:
            method_end = len(method_impl)

        fixed_method = method_impl[:start_pos] + corrected_section

        # Rebuild the file content
        fixed_content = content[:method_start] + fixed_method + content[method_start + method_end:]

        # Write the fixed content back to the file
        with open(SERVER_PATH, 'w') as f:
            f.write(fixed_content)

        print("✅ Fixed server.py file with proper syntax and indentation")
        return True
    except Exception as e:
        print(f"❌ Error fixing server.py: {e}")
        return False

if __name__ == "__main__":
    if not os.path.exists(SERVER_PATH):
        print(f"❌ File not found: {SERVER_PATH}")
        sys.exit(1)

    if fix_server_file():
        print("✅ Successfully fixed the server.py file")
        print("Please restart the direct MCP server for the changes to take effect")
    else:
        print("❌ Failed to fix the server.py file")
        sys.exit(1)
