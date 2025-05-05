#!/usr/bin/env python3
"""
VFS Function Patcher for MCP Server

This script patches the direct_mcp_server.py file to implement the missing 
virtual filesystem functions:
- register_all_fs_tools
- register_fs_journal_tools
- register_integration_tools
"""

import os
import sys
import re
import shutil
import logging
import traceback
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SERVER_FILE = 'direct_mcp_server.py'

def backup_server_file():
    """Create a backup of the server file"""
    backup_path = f"{SERVER_FILE}.bak.vfs_patched"
    shutil.copy2(SERVER_FILE, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def create_vfs_functions():
    """Return the code for the VFS functions"""
    return """
# VFS Tool Integration Functions
# These functions are added by the VFS patcher script

def register_all_fs_tools(server):
    \"\"\"Register all virtual filesystem tools with the MCP server.\"\"\"
    logger.info("Registering virtual filesystem tools...")
    
    # Basic file operations tools
    server.register_tool(
        name="vfs_list_files",
        description="List files in a directory",
        function=lambda path, recursive=False: {
            "files": os.listdir(path) if not recursive else [
                os.path.join(dp, f) for dp, dn, filenames in os.walk(path) 
                for f in filenames
            ],
            "directories": [
                d for d in os.listdir(path) 
                if os.path.isdir(os.path.join(path, d))
            ] if not recursive else [
                dp for dp, dn, filenames in os.walk(path)
            ]
        },
        parameter_descriptions={
            "path": "Path to the directory to list",
            "recursive": "Whether to list files recursively (default: False)"
        },
    )
    
    server.register_tool(
        name="vfs_read_file",
        description="Read the contents of a file",
        function=lambda path: {
            "content": open(path, 'r').read(),
            "size": os.path.getsize(path),
            "last_modified": os.path.getmtime(path)
        },
        parameter_descriptions={
            "path": "Path to the file to read"
        },
    )
    
    server.register_tool(
        name="vfs_write_file",
        description="Write content to a file",
        function=lambda path, content, append=False: {
            "success": bool(open(path, 'a' if append else 'w').write(content) >= 0),
            "path": path,
            "size": os.path.getsize(path) if os.path.exists(path) else 0,
        },
        parameter_descriptions={
            "path": "Path to the file to write",
            "content": "Content to write to the file",
            "append": "Whether to append to the file (default: False)"
        },
    )
    
    server.register_tool(
        name="vfs_delete_file",
        description="Delete a file",
        function=lambda path: {
            "success": not os.path.exists(path) if os.remove(path) is None else False,
            "path": path
        },
        parameter_descriptions={
            "path": "Path to the file to delete"
        },
    )
    
    server.register_tool(
        name="vfs_file_exists",
        description="Check if a file exists",
        function=lambda path: {
            "exists": os.path.exists(path),
            "is_file": os.path.isfile(path) if os.path.exists(path) else False,
            "is_directory": os.path.isdir(path) if os.path.exists(path) else False,
        },
        parameter_descriptions={
            "path": "Path to check"
        },
    )
    
    logger.info("✅ Successfully registered basic VFS tools")
    return True

def register_fs_journal_tools(server):
    \"\"\"Register filesystem journal tools with the MCP server.\"\"\"
    logger.info("Registering filesystem journal tools...")
    
    # Import the fs_journal_tools module if available
    try:
        import fs_journal_tools
        if hasattr(fs_journal_tools, "register_tools"):
            return fs_journal_tools.register_tools(server)
    except ImportError:
        pass
    
    # If fs_journal_tools is not available, register basic journal tools
    journal_db = {}
    
    server.register_tool(
        name="fs_journal_record",
        description="Record a filesystem operation in the journal",
        function=lambda operation, path, metadata=None: {
            "success": bool(journal_db.setdefault(path, []).append({
                "operation": operation,
                "timestamp": import_module("time").time(),
                "metadata": metadata or {}
            })),
            "journal_size": sum(len(entries) for entries in journal_db.values())
        },
        parameter_descriptions={
            "operation": "Operation performed (create, read, update, delete)",
            "path": "Path to the file or directory",
            "metadata": "Additional metadata about the operation"
        },
    )
    
    server.register_tool(
        name="fs_journal_get_history",
        description="Get the history of operations for a file or directory",
        function=lambda path: {
            "history": journal_db.get(path, []),
            "count": len(journal_db.get(path, [])),
        },
        parameter_descriptions={
            "path": "Path to the file or directory"
        },
    )
    
    logger.info("✅ Successfully registered basic FS journal tools")
    return True

def register_integration_tools(server):
    \"\"\"Register IPFS-FS bridge tools with the MCP server.\"\"\"
    logger.info("Registering IPFS-FS bridge tools...")
    
    # Import the ipfs_mcp_fs_integration module if available
    try:
        import ipfs_mcp_fs_integration
        if hasattr(ipfs_mcp_fs_integration, "register_integration_tools"):
            return ipfs_mcp_fs_integration.register_integration_tools(server)
    except ImportError:
        pass
    
    # If ipfs_mcp_fs_integration is not available, register stub tools
    server.register_tool(
        name="ipfs_fs_pin_file",
        description="Pin a file to IPFS and return the CID",
        function=lambda path: {
            "success": False,
            "error": "IPFS-FS integration not available",
            "path": path
        },
        parameter_descriptions={
            "path": "Path to the file to pin"
        },
    )
    
    server.register_tool(
        name="ipfs_fs_get_file",
        description="Get a file from IPFS by CID and save it to the local filesystem",
        function=lambda cid, path: {
            "success": False,
            "error": "IPFS-FS integration not available",
            "cid": cid,
            "path": path
        },
        parameter_descriptions={
            "cid": "IPFS CID of the file",
            "path": "Path to save the file"
        },
    )
    
    logger.info("✅ Successfully registered IPFS-FS bridge stub tools")
    return True

# End of VFS Tool Integration Functions
"""

def add_import_statements(content):
    """Add any missing import statements needed for VFS functions"""
    imports_to_add = ["import os", "import time", "from importlib import import_module"]
    
    for imp in imports_to_add:
        if imp not in content:
            # Find a good place to add imports - after the existing imports but before code
            import_section_end = content.find("# Configure logging")
            if import_section_end == -1:
                import_section_end = content.find("logging.basicConfig")
            
            if import_section_end != -1:
                content = content[:import_section_end] + f"{imp}\n" + content[import_section_end:]
            else:
                # If we can't find a good spot, add it at the top
                content = f"{imp}\n" + content
    
    return content

def patch_server_file():
    """Patch the server file with VFS functions"""
    try:
        # Backup the file first
        backup_path = backup_server_file()
        
        # Read the file content
        with open(SERVER_FILE, 'r') as f:
            content = f.read()
        
        # Check if our functions are already there
        if "# VFS Tool Integration Functions" in content:
            logger.info("VFS functions already added to server file")
            return True
        
        # Add import statements if needed
        content = add_import_statements(content)
        
        # Add our VFS functions
        vfs_functions = create_vfs_functions()
        
        # Look for a good place to insert - before the register_all_tools function
        register_all_tools_pos = content.find("def register_all_tools(")
        if register_all_tools_pos == -1:
            logger.error("Could not find register_all_tools function in server file")
            return False
        
        # Find the start of the function section
        function_section_start = content.rfind("\n\n", 0, register_all_tools_pos)
        if function_section_start == -1:
            function_section_start = register_all_tools_pos
        
        # Insert our VFS functions before register_all_tools
        content = content[:function_section_start] + vfs_functions + content[function_section_start:]
        
        # Write back the modified content
        with open(SERVER_FILE, 'w') as f:
            f.write(content)
        
        logger.info("✅ Successfully patched server file with VFS functions")
        return True
    except Exception as e:
        logger.error(f"Error patching server file: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    logger.info("🚀 Starting VFS function patcher")
    
    if not os.path.exists(SERVER_FILE):
        logger.error(f"Server file {SERVER_FILE} not found")
        sys.exit(1)
    
    if patch_server_file():
        logger.info("✅ Server file patched successfully")
        logger.info("📋 Restart the MCP server to apply changes")
    else:
        logger.error("❌ Failed to patch server file")
        sys.exit(1)

if __name__ == "__main__":
    main()
