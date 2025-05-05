#!/usr/bin/env python3
"""
Update MCP Server with Virtual Filesystem Tools

This script updates the MCP server configuration to include the comprehensive
virtual filesystem tools from the ipfs_kit_py project.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def backup_file(file_path: str) -> bool:
    """Create a backup of the specified file"""
    try:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.bak"
            logger.info(f"Creating backup of {file_path} to {backup_path}")
            with open(file_path, 'r') as src:
                with open(backup_path, 'w') as dst:
                    dst.write(src.read())
            return True
        else:
            logger.warning(f"File not found: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return False

def update_cline_mcp_settings():
    """Update the Claude MCP settings file to include the virtual filesystem tools"""
    mcp_settings_path = os.path.expanduser("~/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
    
    # If the file doesn't exist, check alternative paths
    if not os.path.exists(mcp_settings_path):
        alternatives = [
            os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
            os.path.expanduser("~/.vscode/extensions/saoudrizwan.claude-dev-*/settings/cline_mcp_settings.json"),
            os.path.expanduser("~/.vscode-insiders/extensions/saoudrizwan.claude-dev-*/settings/cline_mcp_settings.json")
        ]
        
        for alt_path in alternatives:
            # Check for wildcard paths
            if '*' in alt_path:
                import glob
                potential_paths = glob.glob(alt_path)
                if potential_paths:
                    mcp_settings_path = potential_paths[0]
                    break
            elif os.path.exists(alt_path):
                mcp_settings_path = alt_path
                break
    
    if not os.path.exists(mcp_settings_path):
        logger.warning(f"Could not find Claude MCP settings file")
        return False
    
    try:
        # Backup the file
        backup_file(mcp_settings_path)
        
        # Read the current settings
        with open(mcp_settings_path, 'r') as f:
            settings = json.load(f)
        
        # Check if we need to add a localhost server
        if "mcpServers" not in settings:
            settings["mcpServers"] = {}
        
        if "localhost" not in settings["mcpServers"]:
            # Add localhost server
            settings["mcpServers"]["localhost"] = {
                "name": "localhost",
                "description": "Local IPFS MCP Server with virtual filesystem",
                "url": "http://localhost:3000/api/v0/sse",
                "enabled": True,
                "transportType": "sse",
                "timeout": 60,
                "authentication": {
                    "type": "none"
                },
                "resources": [],
                "tools": []
            }
        
        # Add or update the virtual filesystem tools
        fs_tools = [
            {
                "name": "fs_journal_get_history",
                "description": "Get the operation history for a path in the virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to get operation history for",
                            "default": "/"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of operations to return",
                            "default": 100
                        },
                        "operation_type": {
                            "type": "string",
                            "description": "Filter by operation type (read, write, mkdir, etc.)",
                            "enum": ["read", "write", "mkdir", "rm", "mv", "cp", "stat", "all"],
                            "default": "all"
                        }
                    }
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "operations": {
                            "type": "array",
                            "description": "List of operations"
                        },
                        "total": {
                            "type": "integer",
                            "description": "Total number of operations"
                        }
                    }
                }
            },
            {
                "name": "vfs_list",
                "description": "List files in a virtual filesystem directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list",
                            "default": "/"
                        }
                    }
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "entries": {
                            "type": "array",
                            "description": "List of directory entries"
                        }
                    }
                }
            },
            {
                "name": "vfs_read",
                "description": "Read a file from the virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to read"
                        }
                    },
                    "required": ["path"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "File content"
                        }
                    }
                }
            },
            {
                "name": "vfs_write",
                "description": "Write to a file in the virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "File path to write to"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write"
                        }
                    },
                    "required": ["path", "content"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the write was successful"
                        }
                    }
                }
            },
            {
                "name": "ipfs_fs_export_to_ipfs",
                "description": "Export a file from the virtual filesystem to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path in the virtual filesystem to export"
                        }
                    },
                    "required": ["path"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "Content identifier (CID) of the exported content"
                        }
                    }
                }
            },
            {
                "name": "ipfs_fs_import_from_ipfs",
                "description": "Import a file from IPFS to the virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to import"
                        },
                        "path": {
                            "type": "string",
                            "description": "Path in the virtual filesystem to import to"
                        }
                    },
                    "required": ["cid", "path"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "success": {
                            "type": "boolean",
                            "description": "Whether the import was successful"
                        }
                    }
                }
            }
        ]
        
        # Update tools in the localhost server
        for server in settings["mcpServers"].values():
            if server["name"] == "localhost" or "ipfs" in server["name"].lower():
                # Check if tools exist
                if "tools" not in server:
                    server["tools"] = []
                
                # Update or add tools
                for fs_tool in fs_tools:
                    # Check if tool already exists
                    tool_exists = False
                    for i, tool in enumerate(server["tools"]):
                        if tool["name"] == fs_tool["name"]:
                            # Update tool
                            server["tools"][i] = fs_tool
                            tool_exists = True
                            break
                    
                    if not tool_exists:
                        # Add tool
                        server["tools"].append(fs_tool)
                
                logger.info(f"Updated server {server['name']} with virtual filesystem tools")
        
        # Write updated settings
        with open(mcp_settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        
        logger.info(f"✅ Successfully updated Claude MCP settings with virtual filesystem tools")
        return True
    
    except Exception as e:
        logger.error(f"Error updating Claude MCP settings: {e}")
        return False

def update_direct_mcp_server():
    """Update direct_mcp_server.py to import and use our virtual filesystem tools"""
    mcp_server_path = "direct_mcp_server.py"
    
    # Check if file exists
    if not os.path.exists(mcp_server_path):
        logger.error(f"File not found: {mcp_server_path}")
        return False
    
    # Create backup
    if not backup_file(mcp_server_path):
        return False
    
    try:
        # Read the file
        with open(mcp_server_path, 'r') as f:
            content = f.read()
        
        # Check if our module is already imported
        if "from enhance_vfs_mcp_integration import register_all_fs_tools" in content:
            logger.info("Virtual filesystem integration already imported")
        else:
            # Import statements to add
            imports_to_add = "\nfrom enhance_vfs_mcp_integration import register_all_fs_tools"
            
            # Try to find import section (after existing imports)
            import_section_end = content.find("# --- Global Variables ---")
            if import_section_end == -1:
                import_section_end = content.find("# Configure logging")
            
            if import_section_end == -1:
                # If we can't find a good spot, add after the first import
                first_import = content.find("import ")
                if first_import != -1:
                    next_line = content.find("\n", first_import)
                    if next_line != -1:
                        content = content[:next_line + 1] + imports_to_add + content[next_line + 1:]
                        logger.info("Added import after the first import statement")
            else:
                # Add after the import section
                content = content[:import_section_end] + imports_to_add + "\n" + content[import_section_end:]
                logger.info("Added import after existing imports")
        
        # Check if our tool registration is already added
        if "register_all_fs_tools" in content and not "from enhance_vfs_mcp_integration import register_all_fs_tools" in content:
            logger.info("Virtual filesystem tool registration already added")
        else:
            # Try to find the register_ipfs_tools call
            register_ipfs = content.find("register_ipfs_tools(")
            if register_ipfs != -1:
                # Find the end of the line or statement
                register_end = content.find("\n", register_ipfs)
                if register_end != -1:
                    # Add our registration after the IPFS registration
                    registration_code = "\n    # Register virtual filesystem tools\n    register_all_fs_tools(server)"
                    content = content[:register_end + 1] + registration_code + content[register_end + 1:]
                    logger.info("Added tool registration after IPFS registration")
            else:
                # Try to find main function or server initialization
                server_init = content.find("server = ")
                if server_init != -1:
                    # Find the end of the line
                    server_end = content.find("\n", server_init)
                    if server_end != -1:
                        # Add our registration after server initialization
                        registration_code = "\n    # Register virtual filesystem tools\n    register_all_fs_tools(server)"
                        content = content[:server_end + 1] + registration_code + content[server_end + 1:]
                        logger.info("Added tool registration after server initialization")
                else:
                    logger.warning("Could not find a place to add tool registration")
        
        # Write the updated content
        with open(mcp_server_path, 'w') as f:
            f.write(content)
        
        logger.info(f"✅ Successfully updated {mcp_server_path} to use virtual filesystem tools")
        return True
    
    except Exception as e:
        logger.error(f"Error updating direct_mcp_server.py: {e}")
        return False

def create_restart_script():
    """Create a script to restart the MCP server with the virtual filesystem tools"""
    try:
        with open("restart_mcp_with_vfs.sh", "w") as f:
            f.write("""#!/bin/bash
# Restart MCP server with enhanced virtual filesystem tools

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server" || true
sleep 2

echo "Starting MCP server with virtual filesystem tools..."
python direct_mcp_server.py --with-vfs-integration &
SERVER_PID=$!
echo "MCP server started with PID $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 3

echo "✅ MCP server is now running with virtual filesystem tools"
echo "You can use the new tools through the MCP interface"
echo "To test, try using the fs_journal_status or vfs_list tool"
""")
        
        # Make the script executable
        os.chmod("restart_mcp_with_vfs.sh", 0o755)
        
        logger.info(f"✅ Created restart script at restart_mcp_with_vfs.sh")
        return True
    
    except Exception as e:
        logger.error(f"Error creating restart script: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        import asyncio
        import aiohttp
        
        # Check for optional dependencies
        try:
            import boto3
            s3_available = True
        except ImportError:
            s3_available = False
            logger.warning("boto3 not installed - S3 backend will not be available")
        
        try:
            import aioipfs
            aioipfs_available = True
        except ImportError:
            aioipfs_available = False
            logger.warning("aioipfs not installed - some IPFS features may not be available")
        
        logger.info("✅ Core dependencies are available")
        return True
    
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False

def create_installation_script():
    """Create a script to install all dependencies"""
    try:
        with open("install_vfs_dependencies.sh", "w") as f:
            f.write("""#!/bin/bash
# Install dependencies for virtual filesystem integration

echo "Installing dependencies for virtual filesystem integration..."
pip install asyncio aiohttp boto3 aioipfs

echo "✅ Dependencies installed"
""")
        
        # Make the script executable
        os.chmod("install_vfs_dependencies.sh", 0o755)
        
        logger.info(f"✅ Created installation script at install_vfs_dependencies.sh")
        return True
    
    except Exception as e:
        logger.error(f"Error creating installation script: {e}")
        return False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Update MCP server with virtual filesystem tools")
    parser.add_argument("--update-server", action="store_true", help="Update direct_mcp_server.py with virtual filesystem tools")
    parser.add_argument("--update-settings", action="store_true", help="Update Claude MCP settings with virtual filesystem tools")
    parser.add_argument("--check-dependencies", action="store_true", help="Check if all required dependencies are installed")
    parser.add_argument("--create-scripts", action="store_true", help="Create installation and restart scripts")
    parser.add_argument("--all", action="store_true", help="Perform all updates")
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    return args

def main():
    """Main function to update MCP server with virtual filesystem tools"""
    args = parse_arguments()
    
    # Check dependencies if requested, or if all actions requested
    if args.check_dependencies or args.all:
        check_dependencies()
    
    # Update server if requested, or if all actions requested
    if args.update_server or args.all:
        update_direct_mcp_server()
    
    # Update settings if requested, or if all actions requested
    if args.update_settings or args.all:
        update_cline_mcp_settings()
    
    # Create scripts if requested, or if all actions requested
    if args.create_scripts or args.all:
        create_restart_script()
        create_installation_script()
    
    logger.info("""
✅ MCP server enhancement with virtual filesystem tools completed

Next steps:
1. Make sure all dependencies are installed with:
   ./install_vfs_dependencies.sh

2. Start the enhanced MCP server with:
   ./restart_mcp_with_vfs.sh

3. Test the new tools through the MCP interface
""")

if __name__ == "__main__":
    main()
