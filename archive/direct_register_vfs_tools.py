#!/usr/bin/env python3
"""
Direct VFS Tools Registration

This script directly registers VFS tools with a running MCP server by using
the JSON-RPC API to add the tools. This approach doesn't require restarting
the server and can be used when the server is already running.
"""

import os
import sys
import json
import time
import logging
import requests
import traceback
from typing import Dict, Any, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server URL
MCP_SERVER_URL = "http://localhost:3000"

def check_server_status() -> bool:
    """Check if the MCP server is running"""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"MCP server is running: {data.get('message')}")
            logger.info(f"Registered tools count: {data.get('registered_tools_count', 0)}")
            return True
        else:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False

def get_registered_tools() -> List[Dict[str, Any]]:
    """Get the list of registered tools from the MCP server"""
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "get_tools",
                "params": {}
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return []
        
        data = response.json()
        if "result" not in data:
            logger.error(f"Invalid response from server: {data}")
            return []
        
        return data["result"]
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return []
    except Exception as e:
        logger.error(f"Error getting registered tools: {e}")
        return []

def register_tool(name: str, description: str, parameters: Dict[str, Any]) -> bool:
    """Register a tool with the MCP server using JSON-RPC"""
    try:
        # Prepare the tool definition
        tool_def = {
            "name": name,
            "description": description,
            "parameters": parameters
        }
        
        # Call the register_tool method using JSON-RPC
        response = requests.post(
            f"{MCP_SERVER_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),  # Use timestamp as ID for uniqueness
                "method": "register_tool",
                "params": tool_def
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Error registering tool {name}: HTTP {response.status_code}")
            return False
        
        data = response.json()
        if "result" not in data:
            logger.error(f"Invalid response when registering tool {name}: {data}")
            return False
        
        logger.info(f"✅ Successfully registered tool: {name}")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to MCP server when registering tool {name}")
        return False
    except Exception as e:
        logger.error(f"Error registering tool {name}: {e}")
        logger.error(traceback.format_exc())
        return False

def register_all_vfs_tools() -> bool:
    """Register all VFS tools with the MCP server"""
    # Check if any VFS tools are already registered
    existing_tools = get_registered_tools()
    existing_tool_names = [tool["name"] for tool in existing_tools]
    
    vfs_prefixes = ["vfs_", "fs_", "filesystem_", "ipfs_fs_"]
    existing_vfs_tools = [name for name in existing_tool_names 
                         if any(name.startswith(prefix) for prefix in vfs_prefixes)]
    
    if existing_vfs_tools:
        logger.info(f"Found {len(existing_vfs_tools)} existing VFS tools: {existing_vfs_tools}")
        should_continue = input("Do you want to register additional VFS tools? (y/n): ").lower()
        if should_continue != 'y':
            logger.info("Aborting tool registration")
            return False
    
    # Define VFS tools
    vfs_tools = [
        {
            "name": "vfs_list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list files recursively",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "vfs_read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "vfs_write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    },
                    "append": {
                        "type": "boolean",
                        "description": "Whether to append to the file",
                        "default": False
                    }
                },
                "required": ["path", "content"]
            }
        },
        {
            "name": "vfs_delete_file",
            "description": "Delete a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to delete"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "vfs_file_exists",
            "description": "Check if a file exists",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to check"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "fs_journal_record",
            "description": "Record a filesystem operation in the journal",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation performed (create, read, update, delete)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to the file or directory"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata about the operation",
                        "default": {}
                    }
                },
                "required": ["operation", "path"]
            }
        },
        {
            "name": "fs_journal_get_history",
            "description": "Get the history of operations for a file or directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file or directory"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_fs_pin_file",
            "description": "Pin a file to IPFS and return the CID",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to pin"
                    }
                },
                "required": ["path"]
            }
        },
        {
            "name": "ipfs_fs_get_file",
            "description": "Get a file from IPFS by CID and save it to the local filesystem",
            "parameters": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "IPFS CID of the file"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to save the file"
                    }
                },
                "required": ["cid", "path"]
            }
        }
    ]
    
    # Register each tool
    successful_registrations = 0
    for tool in vfs_tools:
        # Skip already registered tools
        if tool["name"] in existing_tool_names:
            logger.info(f"Tool {tool['name']} already registered, skipping")
            successful_registrations += 1
            continue
        
        # Register the tool
        if register_tool(tool["name"], tool["description"], tool["parameters"]):
            successful_registrations += 1
        else:
            logger.error(f"Failed to register tool: {tool['name']}")
    
    # Report results
    logger.info(f"Registered {successful_registrations}/{len(vfs_tools)} VFS tools")
    return successful_registrations > 0

def main():
    """Main function"""
    logger.info("🚀 Starting direct VFS tools registration")
    
    # Check if the server is running
    if not check_server_status():
        logger.error("Cannot proceed: MCP server is not running")
        sys.exit(1)
    
    # Register VFS tools
    if register_all_vfs_tools():
        logger.info("✅ VFS tools registration completed successfully")
        
        # Create a test file to demonstrate VFS tools
        timestamp = int(time.time())
        test_content = f"This is a test file created by the VFS integration test at {time.ctime()}"
        test_file = f"vfs_test_{timestamp}.txt"
        
        logger.info(f"Creating a test file using the VFS tools: {test_file}")
        try:
            response = requests.post(
                f"{MCP_SERVER_URL}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "execute_tool",
                    "params": {
                        "name": "vfs_write_file",
                        "arguments": {
                            "path": test_file,
                            "content": test_content
                        }
                    }
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data and data["result"].get("success"):
                    logger.info(f"✅ Successfully created test file: {test_file}")
                    if os.path.isfile(test_file):
                        with open(test_file, 'r') as f:
                            logger.info(f"Test file contents: {f.read()}")
                        logger.info("✅ VFS write operation confirmed")
                    else:
                        logger.error(f"❌ Test file {test_file} was not created on disk")
                else:
                    logger.error(f"❌ Failed to create test file: {data}")
            else:
                logger.error(f"❌ Failed to create test file: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error testing VFS tools: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.error("❌ VFS tools registration failed")
        sys.exit(1)
    
    logger.info("✅ VFS integration completed successfully")

if __name__ == "__main__":
    main()
