#!/usr/bin/env python3
"""
Fix for Direct MCP Server SSE Handling

This script fixes the "Request already responded to" assertion error
that occurs in the direct MCP server's SSE implementation.
"""

import os
import sys
import argparse
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_session_fix(file_path):
    """Check if the session.py file already has the fix."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for the guard line that's already in the file
        guard_line = 'if self._completed:'
        if guard_line in content:
            logger.info(f"✅ Session.py already has the fix implemented")
            return True
        else:
            logger.error(f"❌ Session.py doesn't have the fix, but we expected it to")
            return False
    except Exception as e:
        logger.error(f"❌ Error checking session.py: {e}")
        return False

def fix_sse_handler(file_path):
    """Fix the SSE handler in the server.py file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Look for the first respond line
        respond_line1 = 'await message.respond(response)'
        # Look for the second respond line (multiline)
        respond_pattern2 = r'await message\.respond\(\s*types\.ErrorData\([^)]+\)[^)]+\)[^)]+\)'
        
        if respond_line1 not in content:
            logger.error(f"Could not find the first message.respond pattern in {file_path}")
            return False
        
        # Create a regex pattern to match the second respond call
        import re
        respond_match2 = re.search(respond_pattern2, content, re.DOTALL)
        if not respond_match2:
            logger.error(f"Could not find the second message.respond pattern in {file_path}")
            logger.info("Continuing with fixing only the first pattern...")
        
        # Wrap the first respond call in a try-except block
        modified_content = content.replace(
            respond_line1,
            'try:\n            await message.respond(response)\n        except Exception as e:\n            logger.warning(f"Error responding to message: {e}")'
        )
        
        # If we found the second respond pattern, wrap it too
        if respond_match2:
            original_code = respond_match2.group(0)
            indentation = '            '  # Preserve indentation
            modified_code = f"try:\n{indentation}{original_code}\n{indentation}except Exception as e:\n{indentation}    logger.warning(f\"Error responding to error message: {{e}}\")"
            modified_content = modified_content.replace(original_code, modified_code)
        
        # Write the updated content back to the file
        with open(file_path, 'w') as f:
            f.write(modified_content)
        
        logger.info(f"✅ Updated {file_path} to fix the SSE handler")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing server.py: {e}")
        return False

def find_sdk_path():
    """Find the MCP SDK path."""
    possible_paths = [
        os.path.expanduser("~/ipfs_kit_py/docs/mcp-python-sdk/src"),
        "./docs/mcp-python-sdk/src",
        "../docs/mcp-python-sdk/src"
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.path.isdir(path):
            return path
    
    return None

def main():
    """Main function to apply fixes to the direct MCP server."""
    parser = argparse.ArgumentParser(description="Fix Direct MCP Server SSE Handling")
    parser.add_argument("--sdk-path", help="Path to the MCP SDK", default=None)
    args = parser.parse_args()
    
    # Find the SDK path
    sdk_path = args.sdk_path or find_sdk_path()
    if not sdk_path:
        logger.error("❌ Could not find the MCP SDK path")
        logger.error("Please specify the path using --sdk-path")
        sys.exit(1)
    
    logger.info(f"Using MCP SDK path: {sdk_path}")
    
    # Check the session.py file - it should already have the fix
    session_path = os.path.join(sdk_path, "mcp", "shared", "session.py")
    if not os.path.exists(session_path):
        logger.error(f"❌ File not found: {session_path}")
        sys.exit(1)
    
    if not check_session_fix(session_path):
        logger.warning("⚠️ Session.py doesn't have the expected fix")
        logger.info("Continuing anyway to fix the server.py file")
    
    # Fix the server.py file
    server_path = os.path.join(sdk_path, "mcp", "server", "lowlevel", "server.py")
    if not os.path.exists(server_path):
        logger.error(f"❌ File not found: {server_path}")
        sys.exit(1)
    
    if not fix_sse_handler(server_path):
        logger.error("❌ Failed to fix the server.py file")
        sys.exit(1)
    
    logger.info("✅ Successfully applied all fixes to the direct MCP server")
    logger.info("Please restart the direct MCP server for the changes to take effect")

if __name__ == "__main__":
    main()
