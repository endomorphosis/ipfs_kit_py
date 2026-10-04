#!/usr/bin/env python3
"""
Fix IPFS MCP Tool Handlers

This script modifies the final_mcp_server.py and unified_ipfs_tools.py to
properly handle tool registrations and executions.
"""

import os
import sys
import re
import tempfile
import shutil

def fix_execute_tool():
    """Improve the execute_tool method to better handle IPFS tool adapters"""
    filepath = "/home/barberb/ipfs_kit_py/final_mcp_server.py"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the execute_tool method
    pattern = r'async def execute_tool\(self, tool_name: str, arguments: Dict\[str, Any\] = None, context: Optional\[Dict\[str, Any\]\] = None\):(.*?)(?=def|class|@)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("execute_tool method not found")
        return False
    
    old_method = match.group(0)
    new_method = """async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] = None, context: Optional[Dict[str, Any]] = None):
        arguments = arguments or {}; context_obj = SimpleContext(context or {})
        logger.debug(f"Attempting to execute tool: {tool_name} with arguments: {arguments}") # Added logging
        if tool_name not in self.tools:
            logger.error(f"Tool {tool_name} not found")
            return {"error": f"Tool {tool_name} not found"}
        tool = self.tools[tool_name]
        try:
            import inspect
            if isinstance(tool, dict) and "function" in tool:
                func = tool["function"]
            else:
                func = tool  # Tool is the function itself
                
            sig = inspect.signature(func)
            logger.debug(f"Calling tool function: {tool_name}, signature: {sig}") # Added logging
            
            # Try to handle both parameter styles (ctx/context or direct args)
            if "ctx" in sig.parameters or "context" in sig.parameters:
                # Tool expects a context object
                param_name = "ctx" if "ctx" in sig.parameters else "context"
                logger.debug(f"Executing tool {tool_name} with context parameter '{param_name}'")
                
                # Check if the function accepts kwargs
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    # Function accepts kwargs, can pass arguments directly
                    if inspect.iscoroutinefunction(func):
                        kwargs = {param_name: context_obj}
                        kwargs.update(arguments)
                        result = await func(**kwargs)
                    else:
                        kwargs = {param_name: context_obj}
                        kwargs.update(arguments)
                        result = func(**kwargs)
                else:
                    # Function doesn't accept kwargs, just pass the context
                    if inspect.iscoroutinefunction(func):
                        result = await func(context_obj)
                    else:
                        result = func(context_obj)
            else:
                # Tool expects direct arguments
                logger.debug(f"Executing tool {tool_name} with direct arguments")
                if inspect.iscoroutinefunction(func):
                    result = await func(**arguments)
                else:
                    result = func(**arguments)
                    
            logger.debug(f"Tool {tool_name} execution completed. Result type: {type(result)}") # Added logging
            return result
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {e}"
            traceback_msg = traceback.format_exc()
            logger.error(f"{error_msg}\n{traceback_msg}")
            
            # Special handling for IPFS tools to improve diagnostics
            if tool_name.startswith('ipfs_'):
                logger.warning(f"IPFS tool error for {tool_name}. Attempting fallback implementation...")
                try:
                    # Try using our own implementation if available
                    from ipfs_tool_adapters import get_tool_handler
                    direct_handler = get_tool_handler(tool_name)
                    if direct_handler:
                        logger.info(f"Found direct handler for {tool_name}, trying that...")
                        if inspect.iscoroutinefunction(direct_handler):
                            result = await direct_handler(arguments)
                        else:
                            result = direct_handler(arguments)
                        return result
                except Exception as inner_e:
                    logger.error(f"Fallback also failed: {inner_e}")
            
            return {"error": str(e), "detail": traceback_msg}
"""
    
    # Replace the old method with the new one
    new_content = content.replace(old_method, new_method)
    
    # Write back to the file
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("execute_tool method updated successfully")
    return True

def update_tool_wrappers():
    """Add a better wrapper in unified_ipfs_tools.py"""
    filepath = "/home/barberb/ipfs_kit_py/unified_ipfs_tools.py"
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the register_all_ipfs_tools function
    pattern = r'def register_all_ipfs_tools\(mcp_server\):(.*?)(?=def|class|$)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("register_all_ipfs_tools function not found")
        return False
    
    # Add import for ipfs_tool_adapters
    if 'from ipfs_tool_adapters import get_tool_handler' not in content:
        import_section = content.find('import logging')
        if import_section != -1:
            content = content[:import_section + len('import logging')] + '\nimport traceback\ntry:\n    from ipfs_tool_adapters import get_tool_handler\nexcept ImportError:\n    print("ipfs_tool_adapters not available, some features will be limited")\n' + content[import_section + len('import logging'):]
    
    # Add better tool registration inside the function
    register_section = content.find('# Each function with its expected parameters for direct adaptation')
    if register_section != -1:
        direct_handlers_section = """            # Register the direct handlers first for better compatibility
            if using_direct_handlers:
                logger.info("Registering direct tool handlers from ipfs_tool_adapters")
                try:
                    # Get all the tools from ipfs_tool_adapters
                    from ipfs_tool_adapters import TOOL_HANDLERS
                    for tool_name, handler in TOOL_HANDLERS.items():
                        if tool_name.startswith('ipfs_'):
                            logger.info(f"Registering direct handler for {tool_name}")
                            mcp_server.register_tool(tool_name, handler)
                            registered_tools.append(tool_name)
                    logger.info(f"Registered {len(registered_tools)} direct tool handlers")
                except Exception as e:
                    logger.error(f"Error registering direct handlers: {e}\\n{traceback.format_exc()}")
            
"""
        content = content[:register_section] + direct_handlers_section + content[register_section:]
    
    # Write back to the file
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Tool registration in unified_ipfs_tools.py updated successfully")
    return True

if __name__ == "__main__":
    print("Fixing IPFS MCP Tool Handlers...")
    if fix_execute_tool():
        print("MCP Server execute_tool method fixed successfully.")
    else:
        print("Failed to fix execute_tool method.")
    
    if update_tool_wrappers():
        print("Tool wrappers in unified_ipfs_tools.py updated successfully.")
    else:
        print("Failed to update tool wrappers.")
    
    print("All fixes applied. Please restart the MCP server for changes to take effect.")
