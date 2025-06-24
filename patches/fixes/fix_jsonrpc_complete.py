#!/usr/bin/env python3
"""
Complete fix for the JSON-RPC functionality in the MCP server.
This script directly modifies the handler function without relying on external libraries
and uses all the correct attribute names.
"""

import os
import sys
import logging
import shutil
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak.complete"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_jsonrpc_handler():
    """Fix the JSON-RPC handler."""
    file_path = Path("direct_mcp_server.py")

    # Create a backup
    backup_file(file_path)

    with open(file_path, 'r') as f:
        content = f.read()

    # Find the handle_jsonrpc function
    if 'async def handle_jsonrpc(' in content:
        # Replace the function with our simplified version
        start_marker = 'async def handle_jsonrpc('
        end_marker = None

        lines = content.split('\n')
        start_idx = None
        end_idx = None

        # Find the function definition
        indentation = 4  # Default indentation in case we can't determine it
        for i, line in enumerate(lines):
            if start_marker in line:
                start_idx = i
                # Find the indentation level
                indentation = len(line) - len(line.lstrip())
                break

        if start_idx is not None:
            # Find where the function ends (next line with same or less indentation)
            for i in range(start_idx + 1, len(lines)):
                line = lines[i].rstrip()
                if line and len(line) - len(line.lstrip()) <= indentation:
                    end_idx = i
                    break

            # If didn't find an end, assume it's the last function in the file
            if end_idx is None:
                end_idx = len(lines)

            # Create the new implementation
            new_function = [
                "async def handle_jsonrpc(request):",
                "    \"\"\"Handle JSON-RPC requests.\"\"\"",
                "    try:",
                "        request_json = await request.json()",
                "        logger.debug(\"Received JSON-RPC request: %s\", request_json)",
                "",
                "        method = request_json.get('method')",
                "        params = request_json.get('params', {})",
                "        req_id = request_json.get('id', None)",
                "",
                "        if not method:",
                "            return JSONResponse({",
                "                'jsonrpc': '2.0',",
                "                'error': {'code': -32600, 'message': 'Invalid Request - method missing'},",
                "                'id': req_id",
                "            })",
                "",
                "        # Handle specific methods",
                "        if method == 'get_tools':",
                "            # Get all registered tools",
                "            tools = []",
                "            for tool_name, tool in server._tool_manager._tools.items():",
                "                tools.append({",
                "                    'name': tool_name,",
                "                    'description': tool.description,",
                "                    'schema': tool.schema",
                "                })",
                "            return JSONResponse({",
                "                'jsonrpc': '2.0',",
                "                'result': tools,",
                "                'id': req_id",
                "            })",
                "        elif method == 'use_tool':",
                "            tool_name = params.get('tool_name', '')",
                "            arguments = params.get('arguments', {})",
                "",
                "            if not tool_name:",
                "                return JSONResponse({",
                "                    'jsonrpc': '2.0',",
                "                    'error': {'code': -32602, 'message': 'Invalid params - tool_name missing'},",
                "                    'id': req_id",
                "                })",
                "",
                "            # Find the tool",
                "            tool = server._tool_manager.get_tool(tool_name)",
                "            if not tool:",
                "                return JSONResponse({",
                "                    'jsonrpc': '2.0',",
                "                    'error': {'code': -32601, 'message': f'Method {tool_name} not found'},",
                "                    'id': req_id",
                "                })",
                "",
                "            # Use the tool",
                "            try:",
                "                result = await tool.use(arguments)",
                "                return JSONResponse({",
                "                    'jsonrpc': '2.0',",
                "                    'result': result,",
                "                    'id': req_id",
                "                })",
                "            except Exception as e:",
                "                logger.error(f\"Error using tool {tool_name}: {e}\")",
                "                return JSONResponse({",
                "                    'jsonrpc': '2.0',",
                "                    'error': {'code': -32603, 'message': str(e)},",
                "                    'id': req_id",
                "                })",
                "        else:",
                "            return JSONResponse({",
                "                'jsonrpc': '2.0',",
                "                'error': {'code': -32601, 'message': f'Method {method} not found'},",
                "                'id': req_id",
                "            })",
                "    except json.JSONDecodeError:",
                "        return JSONResponse({",
                "            'jsonrpc': '2.0',",
                "            'error': {'code': -32700, 'message': 'Parse error'},",
                "            'id': None",
                "        }, status_code=400)",
                "    except Exception as e:",
                "        logger.error(\"Error handling JSON-RPC request: %s\", e, exc_info=True)",
                "        return JSONResponse({",
                "            'jsonrpc': '2.0',",
                "            'error': {'code': -32603, 'message': str(e)},",
                "            'id': None",
                "        }, status_code=500)"
            ]

            # Add proper indentation
            indent_spaces = ' ' * indentation
            for i in range(len(new_function)):
                if new_function[i]:
                    new_function[i] = indent_spaces + new_function[i]

            # Replace the old function with the new one
            lines[start_idx:end_idx] = new_function

            # Remove any references to jsonrpc_dispatcher.dispatch
            modified_content = '\n'.join(lines)

            # Remove imported libraries we no longer need
            modified_content = modified_content.replace('from jsonrpc.dispatcher import Dispatcher', '# Import removed: from jsonrpc.dispatcher import Dispatcher')
            modified_content = modified_content.replace('from jsonrpc.exceptions import JSONRPCDispatchException', '# Import removed: from jsonrpc.exceptions import JSONRPCDispatchException')

            # Remove the dispatcher initialization
            modified_content = modified_content.replace('jsonrpc_dispatcher = Dispatcher()', '# Removed: jsonrpc_dispatcher = Dispatcher()')

            # Remove the decorator lines
            modified_content = modified_content.replace('@jsonrpc_dispatcher.add_method', '# Removed: @jsonrpc_dispatcher.add_method')

            # Write the modified content back to the file
            with open(file_path, 'w') as f:
                f.write(modified_content)

            logger.info("Successfully replaced the handle_jsonrpc function")
            return True
        else:
            logger.error("Could not find the handle_jsonrpc function in the file")
            return False
    else:
        logger.error("Could not find the handle_jsonrpc function in the file")
        return False

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC handler...")

    # Fix the JSON-RPC handler
    if fix_jsonrpc_handler():
        logger.info("\n✅ JSON-RPC handler fix completed")
        logger.info("The MCP server should now correctly handle JSON-RPC requests")
        logger.info("Restart the MCP server to apply the changes:")
        logger.info("  1. Stop the current server: ./stop_enhanced_mcp_server.sh")
        logger.info("  2. Start the server again: ./start_enhanced_mcp_server.sh")
        return 0
    else:
        logger.error("Failed to fix the JSON-RPC handler")
        return 1

if __name__ == "__main__":
    sys.exit(main())
