#!/usr/bin/env python3
"""
Fix for the JSON-RPC dispatcher in the MCP server.
This script adds the missing dispatch method to the Dispatcher class.
"""

import os
import sys
import logging
import json
from pathlib import Path
import shutil

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def find_direct_mcp_server():
    """Find the direct_mcp_server.py file in the current directory or subdirectories."""
    direct_mcp_server = Path("direct_mcp_server.py")
    if direct_mcp_server.exists():
        return direct_mcp_server

    # Search in subdirectories if not in the current directory
    for root, _, files in os.walk("."):
        if "direct_mcp_server.py" in files:
            return Path(root) / "direct_mcp_server.py"

    return None

def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_dispatcher_issue(file_path):
    """Fix the dispatcher issue in the MCP server."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if Dispatcher class exists
    if 'class Dispatcher' in content:
        # Add dispatch method if it doesn't exist
        if 'def dispatch(' not in content:
            # Find the Dispatcher class
            parts = content.split('class Dispatcher')
            if len(parts) > 1:
                class_definition = parts[1]
                # Find the end of the class definition
                class_lines = class_definition.split('\n')
                indentation = 0

                # Find the indentation level
                for i, line in enumerate(class_lines):
                    if line.strip() and i > 0:  # Skip the class definition line
                        indentation = len(line) - len(line.lstrip())
                        break

                # Insert the dispatch method
                dispatch_method = f"\n{' ' * indentation}def dispatch(self, request):\n"
                dispatch_method += f"{' ' * (indentation + 4)}\"\"\"Dispatch method for JSON-RPC requests.\"\"\"\n"
                dispatch_method += f"{' ' * (indentation + 4)}if not isinstance(request, dict):\n"
                dispatch_method += f"{' ' * (indentation + 8)}return {{'jsonrpc': '2.0', 'error': {{'code': -32600, 'message': 'Invalid Request'}}, 'id': None}}\n"
                dispatch_method += f"{' ' * (indentation + 4)}method = request.get('method')\n"
                dispatch_method += f"{' ' * (indentation + 4)}params = request.get('params', {{}})\n"
                dispatch_method += f"{' ' * (indentation + 4)}req_id = request.get('id', None)\n"
                dispatch_method += f"{' ' * (indentation + 4)}if not method:\n"
                dispatch_method += f"{' ' * (indentation + 8)}return {{'jsonrpc': '2.0', 'error': {{'code': -32600, 'message': 'Invalid Request - method missing'}}, 'id': req_id}}\n"
                dispatch_method += f"{' ' * (indentation + 4)}try:\n"
                dispatch_method += f"{' ' * (indentation + 8)}if method == 'get_tools':\n"
                dispatch_method += f"{' ' * (indentation + 12)}return {{'jsonrpc': '2.0', 'result': self.get_tools(), 'id': req_id}}\n"
                dispatch_method += f"{' ' * (indentation + 8)}elif method == 'use_tool':\n"
                dispatch_method += f"{' ' * (indentation + 12)}return {{'jsonrpc': '2.0', 'result': self.use_tool(params.get('tool_name', ''), params.get('arguments', {{}})), 'id': req_id}}\n"
                dispatch_method += f"{' ' * (indentation + 8)}else:\n"
                dispatch_method += f"{' ' * (indentation + 12)}return {{'jsonrpc': '2.0', 'error': {{'code': -32601, 'message': f'Method {{method}} not found'}}, 'id': req_id}}\n"
                dispatch_method += f"{' ' * (indentation + 4)}except Exception as e:\n"
                dispatch_method += f"{' ' * (indentation + 8)}logger.error(f'Error dispatching request: {{e}}')\n"
                dispatch_method += f"{' ' * (indentation + 8)}return {{'jsonrpc': '2.0', 'error': {{'code': -32603, 'message': str(e)}}, 'id': req_id}}\n"

                # Find a good position to insert the method
                class_end_index = 0
                for i, line in enumerate(class_lines):
                    if line.strip().startswith("def "):
                        class_end_index = i
                        break

                # If no methods found, insert at the end of the class
                if class_end_index == 0:
                    class_lines.insert(1, dispatch_method)
                else:
                    class_lines.insert(class_end_index, dispatch_method)

                # Reconstruct the class definition
                parts[1] = '\n'.join(class_lines)
                updated_content = 'class Dispatcher'.join(parts)

                # Write the updated content back to the file
                with open(file_path, 'w') as f:
                    f.write(updated_content)

                logger.info("Added dispatch method to Dispatcher class")
                return True
            else:
                logger.error("Could not find the end of the Dispatcher class definition")
                return False
        else:
            logger.info("dispatch method already exists in Dispatcher class")
            return True
    else:
        logger.error("Could not find Dispatcher class in the file")
        return False

def fix_jsonrpc_handler(file_path):
    """Fix the JSON-RPC handler to use the dispatch method."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if the JSON-RPC handler exists
    if 'async def jsonrpc_handler' in content:
        # Check if it's already using dispatch
        if '.dispatch(' not in content and 'dispatch(' not in content:
            # Replace the handler implementation
            lines = content.split('\n')
            handler_start = None
            handler_end = None
            indentation = 0

            # Find the handler
            for i, line in enumerate(lines):
                if 'async def jsonrpc_handler' in line:
                    handler_start = i
                    indentation = len(line) - len(line.lstrip())
                    break

            if handler_start is not None:
                # Find the end of the handler
                in_handler = False
                for i in range(handler_start + 1, len(lines)):
                    line = lines[i]
                    if line.strip() and len(line) - len(line.lstrip()) <= indentation:
                        handler_end = i
                        break
                    if i == len(lines) - 1:
                        handler_end = i + 1

                if handler_end is not None:
                    # Create the new handler
                    new_handler = []
                    new_handler.append(lines[handler_start])  # Keep the function signature
                    base_indent = ' ' * (indentation + 4)

                    # Add the implementation
                    new_handler.append(f"{base_indent}try:")
                    new_handler.append(f"{base_indent}    body = await request.json()")
                    new_handler.append(f"{base_indent}    response = dispatcher.dispatch(body)")
                    new_handler.append(f"{base_indent}    return JSONResponse(response)")
                    new_handler.append(f"{base_indent}except json.JSONDecodeError:")
                    new_handler.append(f"{base_indent}    return JSONResponse({{")
                    new_handler.append(f"{base_indent}        'jsonrpc': '2.0',")
                    new_handler.append(f"{base_indent}        'error': {{'code': -32700, 'message': 'Parse error'}},")
                    new_handler.append(f"{base_indent}        'id': None")
                    new_handler.append(f"{base_indent}    }}, status_code=400)")
                    new_handler.append(f"{base_indent}except Exception as e:")
                    new_handler.append(f"{base_indent}    logger.error(f'Error handling JSON-RPC request: {{e}}')")
                    new_handler.append(f"{base_indent}    return JSONResponse({{")
                    new_handler.append(f"{base_indent}        'jsonrpc': '2.0',")
                    new_handler.append(f"{base_indent}        'error': {{'code': -32603, 'message': str(e)}},")
                    new_handler.append(f"{base_indent}        'id': None")
                    new_handler.append(f"{base_indent}    }}, status_code=500)")

                    # Replace the handler in the content
                    lines[handler_start:handler_end] = new_handler

                    # Write the updated content back to the file
                    with open(file_path, 'w') as f:
                        f.write('\n'.join(lines))

                    logger.info("Updated JSON-RPC handler to use dispatch method")
                    return True

            logger.error("Could not find the JSON-RPC handler in the file")
            return False
        else:
            logger.info("JSON-RPC handler already using dispatch method")
            return True
    else:
        logger.error("Could not find JSON-RPC handler in the file")
        return False

def ensure_json_import(file_path):
    """Ensure that the json module is imported."""
    with open(file_path, 'r') as f:
        content = f.read()

    if 'import json' not in content:
        # Add the import
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, 'import json')
                break

        # Write the updated content back to the file
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))

        logger.info("Added json import")
        return True
    else:
        logger.info("json module already imported")
        return True

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC dispatcher issue...")

    # Find the direct_mcp_server.py file
    direct_mcp_server = find_direct_mcp_server()
    if not direct_mcp_server:
        logger.error("Could not find direct_mcp_server.py file")
        return 1

    logger.info(f"Found direct_mcp_server.py at {direct_mcp_server}")

    # Create a backup of the file
    backup_file(direct_mcp_server)

    # Ensure json module is imported
    ensure_json_import(direct_mcp_server)

    # Fix the dispatcher issue
    if fix_dispatcher_issue(direct_mcp_server):
        logger.info("Successfully fixed the dispatcher issue")
    else:
        logger.error("Failed to fix the dispatcher issue")
        return 1

    # Fix the JSON-RPC handler
    if fix_jsonrpc_handler(direct_mcp_server):
        logger.info("Successfully fixed the JSON-RPC handler")
    else:
        logger.error("Failed to fix the JSON-RPC handler")
        return 1

    logger.info("\n✅ JSON-RPC dispatcher fix completed")
    logger.info("The MCP server should now correctly handle JSON-RPC requests")
    logger.info("Restart the MCP server to apply the changes:")
    logger.info("  1. Stop the current server: ./stop_enhanced_mcp_server.sh")
    logger.info("  2. Start the server again: ./start_enhanced_mcp_server.sh")

    return 0

if __name__ == "__main__":
    sys.exit(main())
