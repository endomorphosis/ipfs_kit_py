#!/usr/bin/env python3
"""
Fix MCP Initialize Endpoint

This script updates the MCP server's initialize endpoint to include 
complete tool schemas to ensure VS Code and Claude can discover all
the available tools properly.
"""

import os
import json
import re
import sys

# The complete tool schemas
TOOL_SCHEMAS = [
    {
        "name": "list_files",
        "description": "List files in a directory",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to list files from"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list files recursively"
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden files"
                }
            },
            "required": []
        }
    },
    {
        "name": "read_file",
        "description": "Read a file's contents",
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
        "name": "write_file",
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
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "ipfs_add",
        "description": "Add content to IPFS",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to add to IPFS"
                },
                "filename": {
                    "type": "string",
                    "description": "Name of the file in IPFS"
                },
                "pin": {
                    "type": "boolean",
                    "description": "Whether to pin the content"
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "ipfs_cat",
        "description": "Retrieve content from IPFS by CID",
        "parameters": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID of the content to retrieve"
                }
            },
            "required": ["cid"]
        }
    },
    {
        "name": "ipfs_pin",
        "description": "Pin content in IPFS",
        "parameters": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID of the content to pin"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to pin recursively"
                }
            },
            "required": ["cid"]
        }
    },
    {
        "name": "ipfs_unpin",
        "description": "Unpin content in IPFS",
        "parameters": {
            "type": "object",
            "properties": {
                "cid": {
                    "type": "string",
                    "description": "CID of the content to unpin"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to unpin recursively"
                }
            },
            "required": ["cid"]
        }
    },
    {
        "name": "ipfs_list_pins",
        "description": "List pinned items in IPFS",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Type of pins to list (all, direct, recursive, indirect)"
                }
            },
            "required": []
        }
    },
    {
        "name": "ipfs_version",
        "description": "Get IPFS version information",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "ipfs_files_ls",
        "description": "List files in the MFS",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to list files from"
                }
            },
            "required": []
        }
    },
    {
        "name": "ipfs_files_mkdir",
        "description": "Create a directory in the MFS",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to create the directory"
                },
                "parents": {
                    "type": "boolean",
                    "description": "Whether to create parent directories if they don't exist"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "ipfs_files_write",
        "description": "Write content to a file in the MFS",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to write to"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "create": {
                    "type": "boolean",
                    "description": "Whether to create the file if it doesn't exist"
                },
                "truncate": {
                    "type": "boolean",
                    "description": "Whether to truncate the file if it exists"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "ipfs_files_read",
        "description": "Read content from a file in the MFS",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path in the MFS to read from"
                }
            },
            "required": ["path"]
        }
    }
]

def update_mcp_server_with_sse(server_path):
    """Update the MCP server with complete tool schemas."""
    try:
        # Read the server file
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Find the initialize endpoint
        initialize_pattern = r'@app\.get\("/initialize"\)\s+async def initialize\(\):[^}]+}\s+}\s+}'
        initialize_match = re.search(initialize_pattern, content, re.DOTALL)
        
        if not initialize_match:
            print(f"❌ Could not find the initialize endpoint in {server_path}")
            return False
        
        # Build the new initialize endpoint
        new_initialize_endpoint = '''@app.get("/initialize")
async def initialize():
    """Initialize endpoint for MCP protocol."""
    return {
        "capabilities": {
            "tools": ''' + json.dumps(TOOL_SCHEMAS, indent=4) + ''',
            "resources": [
                "ipfs://info",
                "ipfs://stats",
                "storage://backends",
                "file://",
                "mfs://root"
            ]
        },
        "serverInfo": {
            "name": "IPFS MCP Proxy Server",
            "version": "1.0.0",
            "implementationName": "ipfs-kit-py-proxy"
        }
    }'''
        
        # Replace the initialize endpoint
        new_content = content.replace(initialize_match.group(0), new_initialize_endpoint)
        
        # Write the updated file
        with open(server_path, 'w') as f:
            f.write(new_content)
        
        print(f"✅ Updated initialize endpoint in {server_path}")
        print(f"🛠️ Added {len(TOOL_SCHEMAS)} tool schemas to the initialize endpoint")
        return True
    except Exception as e:
        print(f"❌ Error updating MCP server: {e}")
        return False

if __name__ == "__main__":
    # The MCP server to update
    server_path = "mcp_server_with_sse.py"
    
    if update_mcp_server_with_sse(server_path):
        print("✅ Successfully updated the MCP server with complete tool schemas")
        print("Please restart the MCP server for the changes to take effect:")
        print("./stop_mcp_ipfs_integration.sh && ./start_mcp_ipfs_integration.sh")
    else:
        print("❌ Failed to update the MCP server")
        sys.exit(1)
