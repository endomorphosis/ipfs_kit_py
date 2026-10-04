#!/usr/bin/env python3
"""
Direct Fix for IPFS Parameter Handling

This script directly modifies the ipfs_tool_adapters.py file to improve parameter handling.
"""

import os
import logging
import traceback
import inspect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct-fix")

def fix_ipfs_tool_adapters():
    """Directly modify the ipfs_tool_adapters.py file to improve parameter handling."""
    filepath = "/home/barberb/ipfs_kit_py/ipfs_tool_adapters.py"
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Find the handle_ipfs_add function
        handle_ipfs_add_line = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("async def handle_ipfs_add(ctx):"):
                handle_ipfs_add_line = i
                break
        
        if handle_ipfs_add_line == -1:
            logger.error("Could not find handle_ipfs_add function")
            return False
        
        # Add additional debug logging to the handle_ipfs_add function
        for i in range(handle_ipfs_add_line, len(lines)):
            if "if not content:" in lines[i]:
                # Add logging before this line
                debug_line = '    logger.debug(f"IPFS_ADD HANDLER: Content extraction result: {content is not None}, type: {type(content).__name__ if content else None}")\n'
                lines.insert(i, debug_line)
                break
        
        # Enhance the content parameter extraction
        for i in range(handle_ipfs_add_line, len(lines)):
            if "content = arguments.get('content'" in lines[i]:
                # Replace with more comprehensive extraction
                lines[i] = '            # Try multiple parameter names for content\n'
                lines.insert(i+1, '            content = None\n')
                lines.insert(i+2, '            for param_name in [\'content\', \'data\', \'text\', \'value\', \'file_content\']:\n')
                lines.insert(i+3, '                if param_name in arguments and arguments[param_name]:\n')
                lines.insert(i+4, '                    content = arguments[param_name]\n')
                lines.insert(i+5, '                    logger.debug(f"Found content in {param_name}")\n')
                lines.insert(i+6, '                    break\n')
                break
        
        # Add similar fallback logic for direct ctx access
        for i in range(handle_ipfs_add_line, len(lines)):
            if "if hasattr(ctx, 'content'):" in lines[i]:
                # Replace with more comprehensive extraction
                lines[i] = '            # Try multiple attribute names for content\n'
                lines.insert(i+1, '            content = None\n')
                lines.insert(i+2, '            for attr_name in [\'content\', \'data\', \'text\', \'value\', \'file_content\']:\n')
                lines.insert(i+3, '                if hasattr(ctx, attr_name) and getattr(ctx, attr_name) is not None:\n')
                lines.insert(i+4, '                    content = getattr(ctx, attr_name)\n')
                lines.insert(i+5, '                    logger.debug(f"Found content in attribute {attr_name}")\n')
                lines.insert(i+6, '                    break\n')
                break
        
        # Update the handler for mock_add_content
        for i in range(handle_ipfs_add_line, len(lines)):
            if "add_content.__name__ == 'not_implemented':" in lines[i]:
                # Enhance the mock implementation to better handle different content types
                mock_impl = '''            # Provide a mock implementation for testing
            logger.warning("Using mock implementation for add_content")
            import hashlib
            # Handle different content types
            if isinstance(content, str):
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            elif isinstance(content, bytes):
                content_hash = hashlib.sha256(content).hexdigest()
            else:
                # Convert to string if not string or bytes
                content_str = str(content)
                content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
                
            cid = f"QmTest{content_hash[:36]}"  # Mock CID
            logger.info(f"Created mock CID: {cid}")
            return {"cid": cid, "size": len(str(content))}
'''
                # Find the end of the block
                end_block = i + 1
                while end_block < len(lines) and lines[end_block].startswith('            '):
                    end_block += 1
                
                # Replace the block
                lines[i+1:end_block] = mock_impl.split('\n')
                break
        
        # Add comprehensive TOOL_HANDLERS dictionary at the end of the file
        tool_handlers = '''
# Dictionary mapping tool names to handler functions
TOOL_HANDLERS = {
    # IPFS Core tools
    "ipfs_add": handle_ipfs_add,
    "ipfs_cat": handle_ipfs_cat,
    
    # IPFS Pin tools
    "ipfs_pin_add": handle_ipfs_pin_add,
    "ipfs_pin_rm": handle_ipfs_pin_rm,
    "ipfs_pin_ls": handle_ipfs_pin_ls,
    
    # IPFS MFS tools
    "ipfs_files_mkdir": handle_ipfs_files_mkdir,
    "ipfs_files_write": handle_ipfs_files_write,
    "ipfs_files_read": handle_ipfs_files_read,
    "ipfs_files_ls": handle_ipfs_files_ls,
    "ipfs_files_rm": handle_ipfs_files_rm,
    "ipfs_files_stat": handle_ipfs_files_stat,
    "ipfs_files_cp": handle_ipfs_files_cp,
    "ipfs_files_mv": handle_ipfs_files_mv,
}

def get_tool_handler(tool_name):
    """Get a handler function for a tool by name."""
    return TOOL_HANDLERS.get(tool_name)
'''
        
        # Check if TOOL_HANDLERS is already defined
        tool_handlers_defined = False
        for line in lines:
            if line.strip().startswith("TOOL_HANDLERS = {"):
                tool_handlers_defined = True
                break
        
        # Add the tool handlers if not already defined
        if not tool_handlers_defined:
            lines.append(tool_handlers)
        
        # Write the modified file
        with open(filepath, 'w') as f:
            f.writelines(lines)
        
        logger.info("Successfully modified ipfs_tool_adapters.py")
        return True
        
    except Exception as e:
        logger.error(f"Error modifying ipfs_tool_adapters.py: {e}")
        logger.error(traceback.format_exc())
        return False

def fix_final_mcp_server():
    """Add debug logging to the final_mcp_server.py file."""
    filepath = "/home/barberb/ipfs_kit_py/final_mcp_server.py"
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Find the execute_tool method
        execute_tool_line = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("async def execute_tool(self,"):
                execute_tool_line = i
                break
        
        if execute_tool_line == -1:
            logger.error("Could not find execute_tool method")
            return False
        
        # Add logging for IPFS tool calls
        for i in range(execute_tool_line, len(lines)):
            if "arguments = arguments or {};" in lines[i]:
                # Add logging after this line
                debug_logging = '''        # Enhanced diagnostic logging for IPFS tools
        if tool_name.startswith('ipfs_'):
            logger.info(f"IPFS tool call: {tool_name}")
            if arguments:
                # Log each argument with type info
                for k, v in arguments.items():
                    value_type = type(v).__name__
                    if k == 'content' or k == 'data' or k == 'text':
                        # Don't log the full content
                        logger.info(f"Argument {k}: type={value_type}, length={len(str(v)) if hasattr(v, '__len__') else 'unknown'}")
                    else:
                        # Log other arguments in full
                        value_str = str(v)
                        value_preview = value_str[:50] + '...' if len(value_str) > 50 else value_str
                        logger.info(f"Argument {k}: type={value_type}, value={value_preview}")
            else:
                logger.warning(f"No arguments provided for {tool_name}")
'''
                lines.insert(i+1, debug_logging)
                break
        
        # Add special handling for IPFS tools
        for i in range(execute_tool_line, len(lines)):
            if "# Special handling for IPFS tools" in lines[i]:
                # Already has special handling
                break
            elif "except Exception as e:" in lines[i] and i > execute_tool_line:
                # Add special handling for IPFS tools
                special_handling = '''            # Special handling for IPFS tools to improve diagnostics
            if tool_name.startswith('ipfs_'):
                logger.warning(f"IPFS tool error for {tool_name}. Attempting fallback implementation...")
                try:
                    # Try using our own implementation if available
                    from ipfs_tool_adapters import get_tool_handler
                    direct_handler = get_tool_handler(tool_name)
                    if direct_handler:
                        logger.info(f"Found direct handler for {tool_name}, trying that...")
                        try:
                            if inspect.iscoroutinefunction(direct_handler):
                                # Try with context object first
                                result = await direct_handler(context_obj)
                                return result
                            else:
                                # Try with direct function call
                                result = direct_handler(context_obj)
                                return result
                        except Exception as handler_e:
                            logger.error(f"Direct handler failed with {handler_e}, trying with arguments")
                            # Try with arguments dict instead
                            if inspect.iscoroutinefunction(direct_handler):
                                result = await direct_handler(arguments)
                                return result
                            else:
                                result = direct_handler(arguments)
                                return result
                except Exception as inner_e:
                    logger.error(f"Fallback also failed: {inner_e}")
'''
                lines.insert(i+1, special_handling)
                break
        
        # Write the modified file
        with open(filepath, 'w') as f:
            f.writelines(lines)
        
        logger.info("Successfully modified final_mcp_server.py")
        return True
        
    except Exception as e:
        logger.error(f"Error modifying final_mcp_server.py: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Applying direct fixes for IPFS parameter handling...")
    
    # Fix the ipfs_tool_adapters.py file
    if fix_ipfs_tool_adapters():
        logger.info("Successfully fixed ipfs_tool_adapters.py")
    else:
        logger.error("Failed to fix ipfs_tool_adapters.py")
    
    # Fix the final_mcp_server.py file
    if fix_final_mcp_server():
        logger.info("Successfully fixed final_mcp_server.py")
    else:
        logger.error("Failed to fix final_mcp_server.py")
    
    logger.info("All fixes have been applied.")
    logger.info("Please restart the MCP server and run tests to validate the fixes.")
