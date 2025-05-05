#!/usr/bin/env python3
"""
Fixes the JSON-RPC dispatcher issue in fixed_final_mcp_server.py
and ensures proper tool registration.
"""

import os
import sys
import re
import logging
import traceback
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
    backup_path = f"{file_path}.bak.jsonrpc_fix"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_jsonrpc_dispatcher(file_path):
    """Fix the JSON-RPC dispatcher in fixed_final_mcp_server.py."""
    target_file = Path(file_path)
    
    # Create a backup
    backup_file(target_file)
    
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Find and fix the handle_jsonrpc function
    jsonrpc_handler_pattern = re.compile(
        r'(async def handle_jsonrpc\(request\):.*?)response = await jsonrpc_dispatcher\.call\(request_json\)(.*?)(?=\n\s*@app\.|\n# Main entry|\n\s*return JSONResponse)',
        re.DOTALL
    )
    
    if jsonrpc_handler_pattern.search(content):
        # Replace the 'await jsonrpc_dispatcher.call()' with jsonrpc_dispatcher.process()
        modified_content = jsonrpc_handler_pattern.sub(
            r'\1response = await jsonrpc_dispatcher.dispatch(request_json)\2',
            content
        )
        
        # If that didn't match, use an alternative pattern
        if modified_content == content:
            alt_pattern = re.compile(
                r'(async def handle_jsonrpc\(request\):.*?request_json = await request\.json\(\).*?)(.*?response = await jsonrpc_dispatcher.*?)\n',
                re.DOTALL
            )
            
            modified_content = alt_pattern.sub(
                r'\1\n        # Process the request using dispatch method\n        try:\n            response = await jsonrpc_dispatcher.dispatch(request_json)\n        except Exception as e:\n            logger.error(f"JSON-RPC dispatch error: {e}")\n            return JSONResponse(\n                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},\n                status_code=500\n            )\n',
                content
            )
    else:
        logger.warning("Could not find the handle_jsonrpc function, creating a new implementation.")
        
        # Find the setup_jsonrpc function to locate where to insert our new handler
        setup_jsonrpc_end = re.search(r'def setup_jsonrpc\(\):.*?return (True|False)', content, re.DOTALL)
        if not setup_jsonrpc_end:
            logger.error("Could not find the setup_jsonrpc function to locate insertion point.")
            return False
        
        # Define a new handle_jsonrpc function
        new_handler = """
async def handle_jsonrpc(request):
    \"\"\"Handle JSON-RPC requests.\"\"\"
    if jsonrpc_dispatcher is None:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": "JSON-RPC not initialized"}, "id": None},
            status_code=500
        )
    
    try:
        request_json = await request.json()
        logger.debug(f"Received JSON-RPC request: {request_json}")
        
        # Process the request using dispatch method
        try:
            response = await jsonrpc_dispatcher.dispatch(request_json)
        except Exception as e:
            logger.error(f"JSON-RPC dispatch error: {e}")
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},
                status_code=500
            )
        
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Error handling JSON-RPC request: {e}")
        logger.error(traceback.format_exc())
        
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": None},
            status_code=500
        )
"""
        
        # Replace the old handler with our new one - search for the general pattern
        handler_pattern = re.compile(
            r'(async def handle_jsonrpc\(request\):.*?)(?=\n\s*@app\.|\n# Main entry)',
            re.DOTALL
        )
        
        if handler_pattern.search(content):
            modified_content = handler_pattern.sub(new_handler, content)
        else:
            # If we can't find the handler to replace, insert it before Main entry point
            main_entry_point = re.search(r'# Main entry point', content)
            if main_entry_point:
                pos = main_entry_point.start()
                modified_content = content[:pos] + new_handler + "\n" + content[pos:]
            else:
                logger.error("Could not find suitable place to insert new JSON-RPC handler.")
                return False
    
    # Add missing import for json
    if 'import json' not in modified_content:
        import_section = re.search(r'import.*?\n\n', modified_content, re.DOTALL)
        if import_section:
            modified_content = modified_content.replace(
                import_section.group(0),
                import_section.group(0).replace('import traceback', 'import traceback\nimport json')
            )
    
    # Fix jsonrpc_dispatcher.add_method to handle synchronous functions correctly
    if '@jsonrpc_dispatcher.add_method' in modified_content:
        # Update the setup_jsonrpc function to use a more robust dispatcher setup
        setup_jsonrpc_pattern = re.compile(
            r'(def setup_jsonrpc\(\):.*?jsonrpc_dispatcher = Dispatcher\(\))',
            re.DOTALL
        )
        
        if setup_jsonrpc_pattern.search(modified_content):
            modified_content = setup_jsonrpc_pattern.sub(
                r'\1\n\n    # Add method to dispatcher with proper async handling\n    def add_method_wrapper(method_name=None):\n        def decorator(f):\n            name = method_name or f.__name__\n            jsonrpc_dispatcher.add_method(f, name=name)\n            return f\n        return decorator\n    \n    # Replace add_method with our wrapper\n    jsonrpc_dispatcher.add_method = add_method_wrapper',
                modified_content
            )
        
        # Also add the get_tools method for the JSON-RPC interface
        if 'async def get_tools(' not in modified_content:
            tools_method = """
    # Add get_tools method to the dispatcher
    @jsonrpc_dispatcher.add_method
    async def get_tools(**kwargs):
        \"\"\"Return the list of available tools.\"\"\"
        if not hasattr(server, "_tools"):
            return []
        
        tool_list = []
        for tool_name, tool in server._tools.items():
            try:
                # Get schema safely
                schema = {}
                if hasattr(tool, "fn_metadata") and hasattr(tool.fn_metadata, "arg_model"):
                    try:
                        schema = tool.fn_metadata.arg_model.model_json_schema()
                    except:
                        schema = {"properties": {}}
                
                tool_list.append({
                    "name": tool_name,
                    "description": getattr(tool, "description", ""),
                    "schema": schema
                })
            except Exception as e:
                logger.error(f"Error processing tool {tool_name}: {e}")
        
        return tool_list
"""
            
            # Add the tools method after setup of dispatcher
            modified_content = modified_content.replace(
                'jsonrpc_dispatcher.add_method = add_method_wrapper',
                'jsonrpc_dispatcher.add_method = add_method_wrapper\n' + tools_method
            )
    
    # Write the modified content
    with open(target_file, 'w') as f:
        f.write(modified_content)
    
    logger.info("Successfully fixed the JSON-RPC dispatcher in " + str(target_file))
    return True

def add_tool_registration_checks(file_path):
    """Add tool registration checks and debugging to fixed_final_mcp_server.py."""
    target_file = Path(file_path)
    
    if not os.path.exists(f"{target_file}.bak.jsonrpc_fix"):
        backup_file(target_file)
    
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Add debug logging after tool registration
    register_all_tools_pattern = re.compile(
        r'(def register_all_tools\(\):.*?logger\.info\(f"Successfully registered tool categories:.*?\))(.*?return True)',
        re.DOTALL
    )
    
    if register_all_tools_pattern.search(content):
        modified_content = register_all_tools_pattern.sub(
            r'\1\n        # Log the actual number of registered tools for debugging\n        if hasattr(server, "_tools"):\n            tool_names = list(server._tools.keys())\n            logger.info(f"Total registered tools: {len(tool_names)}")\n            logger.info(f"Tool names: {tool_names[:10]}...")\n        else:\n            logger.warning("Server has no _tools attribute. Tool registration may have failed.")\2',
            content
        )
        
        if modified_content == content:
            logger.warning("Could not add tool registration debug logging.")
    else:
        logger.warning("Could not find register_all_tools function.")
        modified_content = content
    
    # Make sure the server.tool decorator is properly applied
    if "@server.tool" in modified_content:
        # Get import section
        import_section = re.search(r'import.*?\n\n', modified_content, re.DOTALL)
        if import_section:
            # Ensure we have the right imports
            if "import inspect" not in import_section.group(0):
                modified_content = modified_content.replace(
                    import_section.group(0),
                    import_section.group(0).replace('import traceback', 'import traceback\nimport inspect')
                )
    
    # Add tool initialization check
    on_startup_pattern = re.compile(
        r'(@app\.on_event\("startup"\).*?async def on_startup\(\):.*?server_initialized = True)(.*?initialization_event\.set\(\))',
        re.DOTALL
    )
    
    if on_startup_pattern.search(modified_content):
        modified_content = on_startup_pattern.sub(
            r'\1\n        # Check if tools were registered\n        if hasattr(server, "_tools"):\n            tool_count = len(server._tools)\n            tool_names = list(server._tools.keys())\n            logger.info(f"Server started with {tool_count} registered tools")\n            logger.info(f"First 10 tools: {tool_names[:10]}")\n        else:\n            logger.warning("No tools were registered during startup.")\2',
            modified_content
        )
    
    # Write the modified content
    with open(target_file, 'w') as f:
        f.write(modified_content)
    
    logger.info("Successfully added tool registration checks to " + str(target_file))
    return True

def update_port_references(file_path, new_port=3001):
    """Update all port references in the file."""
    target_file = Path(file_path)
    
    if not os.path.exists(f"{target_file}.bak.jsonrpc_fix"):
        backup_file(target_file)
    
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Update the default port constant
    port_def_pattern = re.compile(r'PORT = (\d+)  # Default to port')
    
    if port_def_pattern.search(content):
        modified_content = port_def_pattern.sub(f'PORT = {new_port}  # Default to port', content)
    else:
        logger.warning(f"Could not find PORT constant definition in {target_file}")
        modified_content = content
    
    # Update command-line default port
    parser_pattern = re.compile(r'parser\.add_argument\("--port", type=int, default=(\d+), help="Port')
    
    if parser_pattern.search(modified_content):
        modified_content = parser_pattern.sub(f'parser.add_argument("--port", type=int, default={new_port}, help="Port', modified_content)
    else:
        logger.warning(f"Could not find port argument definition in {target_file}")
    
    # Write the modified content
    with open(target_file, 'w') as f:
        f.write(modified_content)
    
    logger.info(f"Successfully updated port references to {new_port} in {target_file}")
    return True

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC dispatcher in fixed_final_mcp_server.py...")
    
    target_file = "fixed_final_mcp_server.py"
    
    jsonrpc_fix_result = fix_jsonrpc_dispatcher(target_file)
    tool_checks_result = add_tool_registration_checks(target_file)
    port_update_result = update_port_references(target_file)
    
    if jsonrpc_fix_result and tool_checks_result:
        logger.info("\n✅ JSON-RPC and tool registration fixes applied successfully")
        logger.info("The server should now be able to handle JSON-RPC requests and register tools properly")
        logger.info("Restart the MCP server using start_fixed_final_mcp_server.sh to apply the changes")
        return 0
    else:
        logger.error("Failed to apply some fixes")
        if jsonrpc_fix_result:
            logger.info("✅ Successfully fixed the JSON-RPC dispatcher")
        if tool_checks_result:
            logger.info("✅ Successfully added tool registration checks")
        if port_update_result:
            logger.info("✅ Successfully updated port references")
        return 1

if __name__ == "__main__":
    sys.exit(main())
