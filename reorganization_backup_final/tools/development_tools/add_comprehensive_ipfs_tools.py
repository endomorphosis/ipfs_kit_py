#!/usr/bin/env python3
"""
Comprehensive IPFS tools for MCP integration.

This module defines a comprehensive set of IPFS tools that can be registered with the
MCP server. It includes tools for IPFS operations and filesystem integration.
"""

import os
import sys
import json
import time
import base64
import tempfile
from typing import Dict, List, Any, Optional, Callable

# Tool handler type
ToolHandler = Dict[str, Any]

# Define the IPFS tool definitions
IPFS_TOOL_DEFINITIONS = {
    # Swarm operations
    "swarm_peers": {
        "name": "swarm_peers",
        "description": "List connected peers in the IPFS network",
        "parameters": [],
        "method": "swarm_peers"
    },
    "swarm_connect": {
        "name": "swarm_connect",
        "description": "Connect to a peer in the IPFS network",
        "parameters": [
            {
                "name": "peer_id",
                "type": "string",
                "description": "The peer ID to connect to (e.g. /ip4/104.131.131.82/tcp/4001/p2p/QmaCpDMGvV2BGHeYERUEnRQAwe3N8SzbUtfsmvsqQLuvuJ)",
                "required": True
            }
        ],
        "method": "swarm_connect"
    },
    "swarm_disconnect": {
        "name": "swarm_disconnect",
        "description": "Disconnect from a peer in the IPFS network",
        "parameters": [
            {
                "name": "peer_id",
                "type": "string",
                "description": "The peer ID to disconnect from",
                "required": True
            }
        ],
        "method": "swarm_disconnect"
    },

    # MFS operations
    "list_files": {
        "name": "list_files",
        "description": "List files in an MFS directory",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the directory in MFS",
                "required": False,
                "default": "/"
            },
            {
                "name": "long",
                "type": "boolean",
                "description": "Use long listing format",
                "required": False,
                "default": False
            }
        ],
        "method": "list_files"
    },
    "stat_file": {
        "name": "stat_file",
        "description": "Get information about a file or directory in MFS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the file or directory in MFS",
                "required": True
            }
        ],
        "method": "stat_file"
    },
    "make_directory": {
        "name": "make_directory",
        "description": "Create a directory in MFS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the directory to create in MFS",
                "required": True
            },
            {
                "name": "parents",
                "type": "boolean",
                "description": "Create parent directories as needed",
                "required": False,
                "default": True
            }
        ],
        "method": "make_directory"
    },
    "read_file": {
        "name": "read_file",
        "description": "Read content from a file in MFS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the file in MFS",
                "required": True
            },
            {
                "name": "offset",
                "type": "integer",
                "description": "Byte offset to start reading from",
                "required": False,
                "default": 0
            },
            {
                "name": "count",
                "type": "integer",
                "description": "Maximum number of bytes to read",
                "required": False,
                "default": -1
            }
        ],
        "method": "read_file"
    },
    "write_file": {
        "name": "write_file",
        "description": "Write content to a file in MFS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the file in MFS",
                "required": True
            },
            {
                "name": "content",
                "type": "string",
                "description": "Content to write to the file",
                "required": True
            },
            {
                "name": "create",
                "type": "boolean",
                "description": "Create the file if it does not exist",
                "required": False,
                "default": True
            },
            {
                "name": "truncate",
                "type": "boolean",
                "description": "Truncate the file before writing",
                "required": False,
                "default": True
            }
        ],
        "method": "write_file"
    },
    "remove_file": {
        "name": "remove_file",
        "description": "Remove a file or directory from MFS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to the file or directory in MFS",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Recursively remove directories",
                "required": False,
                "default": False
            },
            {
                "name": "force",
                "type": "boolean",
                "description": "Force removal",
                "required": False,
                "default": False
            }
        ],
        "method": "remove_file"
    },

    # Content operations
    "add_content": {
        "name": "add_content",
        "description": "Add content to IPFS",
        "parameters": [
            {
                "name": "content",
                "type": "string",
                "description": "Content to add to IPFS",
                "required": True
            },
            {
                "name": "filename",
                "type": "string",
                "description": "Filename to use",
                "required": False,
                "default": "file.txt"
            },
            {
                "name": "pin",
                "type": "boolean",
                "description": "Pin the content",
                "required": False,
                "default": True
            }
        ],
        "method": "add_content"
    },
    "get_content": {
        "name": "get_content",
        "description": "Get content from IPFS by CID",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the content to get",
                "required": True
            }
        ],
        "method": "get_content"
    },
    "get_content_as_tar": {
        "name": "get_content_as_tar",
        "description": "Download content as a TAR archive",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the content to get",
                "required": True
            },
            {
                "name": "output_path",
                "type": "string",
                "description": "Path to save the TAR archive",
                "required": False,
                "default": "ipfs_content.tar"
            }
        ],
        "method": "get_content_as_tar"
    },

    # Pin operations
    "pin_content": {
        "name": "pin_content",
        "description": "Pin content to IPFS",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the content to pin",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Recursively pin the content",
                "required": False,
                "default": True
            }
        ],
        "method": "pin_content"
    },
    "unpin_content": {
        "name": "unpin_content",
        "description": "Unpin content from IPFS",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the content to unpin",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Recursively unpin the content",
                "required": False,
                "default": True
            }
        ],
        "method": "unpin_content"
    },
    "list_pins": {
        "name": "list_pins",
        "description": "List pinned content",
        "parameters": [
            {
                "name": "type",
                "type": "string",
                "description": "Type of pins to list (all, direct, indirect, recursive)",
                "required": False,
                "default": "all"
            }
        ],
        "method": "list_pins"
    },

    # IPNS operations
    "publish_name": {
        "name": "publish_name",
        "description": "Publish an IPFS path to IPNS",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "IPFS path to publish (e.g. /ipfs/QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG)",
                "required": True
            },
            {
                "name": "lifetime",
                "type": "string",
                "description": "Time duration that the record will be valid for",
                "required": False,
                "default": "24h"
            },
            {
                "name": "ttl",
                "type": "string",
                "description": "Time duration that the record should be cached",
                "required": False,
                "default": "24h"
            }
        ],
        "method": "publish_name"
    },
    "resolve_name": {
        "name": "resolve_name",
        "description": "Resolve an IPNS name to an IPFS path",
        "parameters": [
            {
                "name": "name",
                "type": "string",
                "description": "IPNS name to resolve (e.g. /ipns/QmSrPmbaUKA3ZodhzPWZnpFgcPMFWF4QsxXbkWfEptTBJd)",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Resolve until the result is not an IPNS name",
                "required": False,
                "default": True
            },
            {
                "name": "nocache",
                "type": "boolean",
                "description": "Do not use cached entries",
                "required": False,
                "default": False
            }
        ],
        "method": "resolve_name"
    },

    # DAG operations
    "dag_put": {
        "name": "dag_put",
        "description": "Add a DAG node to IPFS",
        "parameters": [
            {
                "name": "data",
                "type": "object",
                "description": "Data to add as a DAG node",
                "required": True
            },
            {
                "name": "format",
                "type": "string",
                "description": "Format to use (cbor, protobuf, json)",
                "required": False,
                "default": "cbor"
            },
            {
                "name": "pin",
                "type": "boolean",
                "description": "Pin the DAG node",
                "required": False,
                "default": True
            }
        ],
        "method": "dag_put"
    },
    "dag_get": {
        "name": "dag_get",
        "description": "Get a DAG node from IPFS",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the DAG node to get",
                "required": True
            },
            {
                "name": "path",
                "type": "string",
                "description": "Path within the DAG node to get",
                "required": False,
                "default": ""
            }
        ],
        "method": "dag_get"
    },
    "dag_resolve": {
        "name": "dag_resolve",
        "description": "Resolve a path through a DAG structure",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Path to resolve (e.g. /ipfs/QmYPNmahJAvkMTU6tDx5zvhEkoLzEFeTDz6azDCSNqzKkz/a/b/c)",
                "required": True
            }
        ],
        "method": "dag_resolve"
    },

    # Block operations
    "block_put": {
        "name": "block_put",
        "description": "Add a raw block to IPFS",
        "parameters": [
            {
                "name": "data",
                "type": "string",
                "description": "Data to add as a raw block (base64 encoded)",
                "required": True
            },
            {
                "name": "format",
                "type": "string",
                "description": "Format to use for the block CID",
                "required": False,
                "default": "v0"
            }
        ],
        "method": "block_put"
    },
    "block_get": {
        "name": "block_get",
        "description": "Get a raw block from IPFS",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the block to get",
                "required": True
            }
        ],
        "method": "block_get"
    },
    "block_stat": {
        "name": "block_stat",
        "description": "Get stats about a block",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the block to get stats for",
                "required": True
            }
        ],
        "method": "block_stat"
    },

    # DHT operations
    "dht_findpeer": {
        "name": "dht_findpeer",
        "description": "Find a peer using the DHT",
        "parameters": [
            {
                "name": "peer_id",
                "type": "string",
                "description": "Peer ID to find",
                "required": True
            }
        ],
        "method": "dht_findpeer"
    },
    "dht_findprovs": {
        "name": "dht_findprovs",
        "description": "Find providers for a CID",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID to find providers for",
                "required": True
            },
            {
                "name": "num_providers",
                "type": "integer",
                "description": "Maximum number of providers to find",
                "required": False,
                "default": 20
            }
        ],
        "method": "dht_findprovs"
    },

    # Node operations
    "get_node_id": {
        "name": "get_node_id",
        "description": "Get node identity information",
        "parameters": [],
        "method": "get_node_id"
    },
    "get_version": {
        "name": "get_version",
        "description": "Get IPFS version information",
        "parameters": [],
        "method": "get_version"
    },
    "get_stats": {
        "name": "get_stats",
        "description": "Get statistics about IPFS operations",
        "parameters": [
            {
                "name": "stats_type",
                "type": "string",
                "description": "Type of stats to get (bw, repo)",
                "required": False,
                "default": "bw"
            }
        ],
        "method": "get_stats"
    },
    "check_daemon_status": {
        "name": "check_daemon_status",
        "description": "Check status of IPFS daemons",
        "parameters": [],
        "method": "check_daemon_status"
    },
    "get_replication_status": {
        "name": "get_replication_status",
        "description": "Get replication status for a CID",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID to check replication status for",
                "required": True
            }
        ],
        "method": "get_replication_status"
    }
}

# Define the filesystem integration tool definitions
FILESYSTEM_TOOL_DEFINITIONS = {
    "map_ipfs_to_fs": {
        "name": "map_ipfs_to_fs",
        "description": "Map an IPFS CID to a virtual filesystem path",
        "parameters": [
            {
                "name": "cid",
                "type": "string",
                "description": "CID of the IPFS content to map",
                "required": True
            },
            {
                "name": "path",
                "type": "string",
                "description": "Virtual filesystem path to map to",
                "required": True
            },
            {
                "name": "auto_pin",
                "type": "boolean",
                "description": "Automatically pin the content",
                "required": False,
                "default": True
            }
        ],
        "method": "map_ipfs_to_fs"
    },
    "unmap_ipfs_from_fs": {
        "name": "unmap_ipfs_from_fs",
        "description": "Remove a mapping between IPFS and filesystem",
        "parameters": [
            {
                "name": "path",
                "type": "string",
                "description": "Virtual filesystem path to unmap",
                "required": True
            },
            {
                "name": "auto_unpin",
                "type": "boolean",
                "description": "Automatically unpin the content",
                "required": False,
                "default": False
            }
        ],
        "method": "unmap_ipfs_from_fs"
    },
    "sync_fs_to_ipfs": {
        "name": "sync_fs_to_ipfs",
        "description": "Synchronize a filesystem directory to IPFS",
        "parameters": [
            {
                "name": "fs_path",
                "type": "string",
                "description": "Filesystem path to synchronize",
                "required": True
            },
            {
                "name": "ipfs_path",
                "type": "string",
                "description": "IPFS path to synchronize to",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Recursively synchronize directories",
                "required": False,
                "default": True
            }
        ],
        "method": "sync_fs_to_ipfs"
    },
    "sync_ipfs_to_fs": {
        "name": "sync_ipfs_to_fs",
        "description": "Synchronize IPFS directory to filesystem",
        "parameters": [
            {
                "name": "ipfs_path",
                "type": "string",
                "description": "IPFS path to synchronize",
                "required": True
            },
            {
                "name": "fs_path",
                "type": "string",
                "description": "Filesystem path to synchronize to",
                "required": True
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "Recursively synchronize directories",
                "required": False,
                "default": True
            }
        ],
        "method": "sync_ipfs_to_fs"
    },
    "list_fs_ipfs_mappings": {
        "name": "list_fs_ipfs_mappings",
        "description": "List mappings between filesystem and IPFS",
        "parameters": [],
        "method": "list_fs_ipfs_mappings"
    },
    "mount_ipfs_to_fs": {
        "name": "mount_ipfs_to_fs",
        "description": "Mount IPFS to a filesystem path",
        "parameters": [
            {
                "name": "mount_point",
                "type": "string",
                "description": "Filesystem path to mount IPFS to",
                "required": True
            }
        ],
        "method": "mount_ipfs_to_fs"
    },
    "unmount_ipfs_from_fs": {
        "name": "unmount_ipfs_from_fs",
        "description": "Unmount IPFS from a filesystem path",
        "parameters": [
            {
                "name": "mount_point",
                "type": "string",
                "description": "Filesystem path to unmount IPFS from",
                "required": True
            }
        ],
        "method": "unmount_ipfs_from_fs"
    }
}

def create_tool_handler(method_name: str, controller: Any, tool_def: Dict[str, Any]) -> Optional[ToolHandler]:
    """
    Create a tool handler for an IPFS method.
    
    Args:
        method_name: Name of the IPFS method
        controller: IPFS controller instance
        tool_def: Tool definition
        
    Returns:
        ToolHandler: Handler for the tool or None if not supported
    """
    if not hasattr(controller, method_name):
        print(f"Warning: Method {method_name} not found in controller")
        return None
        
    # Get the method from the controller
    controller_method = getattr(controller, method_name)
    
    def handle_tool(args):
        """Handle the tool call."""
        try:
            # Extract the arguments from the request
            params = {}
            for param in tool_def["parameters"]:
                name = param["name"]
                if name in args:
                    params[name] = args[name]
                elif "default" in param:
                    params[name] = param["default"]
                    
            # Call the controller method
            result = controller_method(**params)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    # Create the tool handler
    handler = {
        "name": tool_def["name"],
        "description": tool_def["description"],
        "parameters": tool_def["parameters"],
        "handle": handle_tool
    }
    
    return handler

def create_fs_integration_handler(method_name: str, tool_def: Dict[str, Any], controller: Any) -> Optional[ToolHandler]:
    """
    Create a tool handler for a filesystem integration method.
    
    Args:
        method_name: Name of the filesystem integration method
        tool_def: Tool definition
        controller: IPFS controller instance
        
    Returns:
        ToolHandler: Handler for the tool or None if not supported
    """
    # Map filesystem integration methods to controller methods
    fs_method_mapping = {
        "map_ipfs_to_fs": "_map_ipfs_to_fs",
        "unmap_ipfs_from_fs": "_unmap_ipfs_from_fs",
        "sync_fs_to_ipfs": "_sync_fs_to_ipfs",
        "sync_ipfs_to_fs": "_sync_ipfs_to_fs",
        "list_fs_ipfs_mappings": "_list_fs_ipfs_mappings",
        "mount_ipfs_to_fs": "_mount_ipfs_to_fs",
        "unmount_ipfs_from_fs": "_unmount_ipfs_from_fs"
    }
    
    # Get the controller method name for this FS integration method
    controller_method_name = fs_method_mapping.get(method_name)
    if not controller_method_name:
        print(f"Warning: No controller method mapping found for {method_name}")
        return None
        
    # Check if the method exists in the controller
    if not hasattr(controller, controller_method_name):
        # For methods that don't exist in the controller, add a proxy method 
        # that integrates with the rest of the controller's functionality
        
        if method_name == "map_ipfs_to_fs":
            def map_ipfs_to_fs(cid, path, auto_pin=True):
                """Map an IPFS CID to a virtual filesystem path."""
                # Ensure the path starts with /ipfs/
                if not path.startswith("/ipfs/"):
                    path = f"/ipfs/{path.lstrip('/')}"
                
                # Pin the content if requested
                if auto_pin:
                    controller.pin_content(cid, recursive=True)
                
                # Use controller's MFS functionality to create the path
                controller.make_directory(os.path.dirname(path), parents=True)
                
                # Create a symlink from the path to the CID
                controller.remove_file(path, force=True, recursive=False)
                
                # Save the mapping in a special file
                mappings_path = "/.fs_mappings"
                mappings = {}
                try:
                    mappings_data = controller.read_file(mappings_path)
                    mappings = json.loads(mappings_data.get("Content", "{}"))
                except:
                    # Create mappings file if it doesn't exist
                    pass
                
                # Update mappings
                mappings[path] = cid
                controller.write_file(mappings_path, json.dumps(mappings, indent=2))
                
                return {"path": path, "cid": cid, "mapped": True}
            
            setattr(controller, "_map_ipfs_to_fs", map_ipfs_to_fs)
            
        elif method_name == "unmap_ipfs_from_fs":
            def unmap_ipfs_from_fs(path, auto_unpin=False):
                """Remove a mapping between IPFS and filesystem."""
                # Ensure the path starts with /ipfs/
                if not path.startswith("/ipfs/"):
                    path = f"/ipfs/{path.lstrip('/')}"
                
                # Get the current mappings
                mappings_path = "/.fs_mappings"
                mappings = {}
                try:
                    mappings_data = controller.read_file(mappings_path)
                    mappings = json.loads(mappings_data.get("Content", "{}"))
                except:
                    return {"error": "No mappings found"}
                
                if path not in mappings:
                    return {"error": f"Path {path} not found in mappings"}
                
                # Get the CID for this path
                cid = mappings[path]
                
                # Unpin the content if requested
                if auto_unpin:
                    controller.unpin_content(cid, recursive=True)
                
                # Remove the path
                controller.remove_file(path, force=True, recursive=False)
                
                # Update mappings
                del mappings[path]
                controller.write_file(mappings_path, json.dumps(mappings, indent=2))
                
                return {"path": path, "cid": cid, "unmapped": True}
            
            setattr(controller, "_unmap_ipfs_from_fs", unmap_ipfs_from_fs)
            
        elif method_name == "list_fs_ipfs_mappings":
            def list_fs_ipfs_mappings():
                """List mappings between filesystem and IPFS."""
                # Get the current mappings
                mappings_path = "/.fs_mappings"
                mappings = {}
                try:
                    mappings_data = controller.read_file(mappings_path)
                    mappings = json.loads(mappings_data.get("Content", "{}"))
                except:
                    # Return empty mappings if file doesn't exist
                    pass
                
                return {"mappings": mappings}
            
            setattr(controller, "_list_fs_ipfs_mappings", list_fs_ipfs_mappings)
            
        elif method_name == "sync_fs_to_ipfs":
            def sync_fs_to_ipfs(fs_path, ipfs_path, recursive=True):
                """Synchronize a filesystem directory to IPFS."""
                # Ensure ipfs_path starts with /ipfs/
                if not ipfs_path.startswith("/ipfs/"):
                    ipfs_path = f"/ipfs/{ipfs_path.lstrip('/')}"
                
                # Ensure fs_path exists
                if not os.path.exists(fs_path):
                    return {"error": f"Filesystem path {fs_path} does not exist"}
                
                # Create the target directory in IPFS if it doesn't exist
                controller.make_directory(ipfs_path, parents=True)
                
                # If fs_path is a directory and recursive is True, sync all contents
                results = []
                if os.path.isdir(fs_path) and recursive:
                    for root, dirs, files in os.walk(fs_path):
                        # Create relative path from fs_path
                        rel_path = os.path.relpath(root, fs_path)
                        if rel_path == ".":
                            rel_path = ""
                        
                        # Create directories in IPFS
                        for dirname in dirs:
                            ipfs_dir_path = os.path.join(ipfs_path, rel_path, dirname)
                            controller.make_directory(ipfs_dir_path, parents=True)
                        
                        # Copy files to IPFS
                        for filename in files:
                            # Get full paths
                            fs_file_path = os.path.join(root, filename)
                            ipfs_file_path = os.path.join(ipfs_path, rel_path, filename)
                            
                            # Read file content
                            with open(fs_file_path, 'rb') as f:
                                content = f.read()
                            
                            # Write to IPFS
                            controller.write_file(ipfs_file_path, content.decode('utf-8', errors='replace'))
                            
                            results.append({
                                "fs_path": fs_file_path,
                                "ipfs_path": ipfs_file_path,
                                "size": len(content)
                            })
                
                # If fs_path is a file, just copy it
                elif os.path.isfile(fs_path):
                    filename = os.path.basename(fs_path)
                    ipfs_file_path = os.path.join(ipfs_path, filename)
                    
                    # Read file content
                    with open(fs_path, 'rb') as f:
                        content = f.read()
                    
                    # Write to IPFS
                    controller.write_file(ipfs_file_path, content.decode('utf-8', errors='replace'))
                    
                    results.append({
                        "fs_path": fs_path,
                        "ipfs_path": ipfs_file_path,
                        "size": len(content)
                    })
                
                return {"synced": True, "results": results}
            
            setattr(controller, "_sync_fs_to_ipfs", sync_fs_to_ipfs)
            
        elif method_name == "sync_ipfs_to_fs":
            def sync_ipfs_to_fs(ipfs_path, fs_path, recursive=True):
                """Synchronize IPFS directory to filesystem."""
                # Ensure ipfs_path starts with /ipfs/
                if not ipfs_path.startswith("/ipfs/"):
                    ipfs_path = f"/ipfs/{ipfs_path.lstrip('/')}"
                
                # Create the target directory in filesystem if it doesn't exist
                os.makedirs(fs_path, exist_ok=True)
                
                # Get the IPFS directory listing
                try:
                    listing = controller.list_files(ipfs_path, long=True)
                except Exception as e:
                    return {"error": f"Error listing IPFS path: {str(e)}"}
                
                results = []
                
                # Process entries
                entries = listing.get("Entries", [])
                for entry in entries:
                    name = entry.get("Name", "")
                    type_code = entry.get("Type", 0)
                    is_dir = type_code == 1
                    
                    ipfs_entry_path = os.path.join(ipfs_path, name)
                    fs_entry_path = os.path.join(fs_path, name)
                    
                    if is_dir and recursive:
                        # Create directory and recurse
                        os.makedirs(fs_entry_path, exist_ok=True)
                        result = sync_ipfs_to_fs(ipfs_entry_path, fs_entry_path, recursive)
                        results.append({
                            "fs_path": fs_entry_path,
                            "ipfs_path": ipfs_entry_path,
                            "is_dir": True,
                            "synced": "error" not in result
                        })
                    elif not is_dir:
                        # Read file content from IPFS
                        try:
                            file_data = controller.read_file(ipfs_entry_path)
                            content = file_data.get("Content", "")
                            
                            # Write to filesystem
                            with open(fs_entry_path, 'w') as f:
                                f.write(content)
                            
                            results.append({
                                "fs_path": fs_entry_path,
                                "ipfs_path": ipfs_entry_path,
                                "is_dir": False,
                                "size": len(content),
                                "synced": True
                            })
                        except Exception as e:
                            results.append({
                                "fs_path": fs_entry_path,
                                "ipfs_path": ipfs_entry_path,
                                "is_dir": False,
                                "error": str(e),
                                "synced": False
                            })
                
                return {"synced": True, "results": results}
            
            setattr(controller, "_sync_ipfs_to_fs", sync_ipfs_to_fs)
            
        elif method_name == "mount_ipfs_to_fs":
            def mount_ipfs_to_fs(mount_point):
                """Mount IPFS to a filesystem path."""
                # This is a more complex operation that requires FUSE
                # For now, we'll just create a directory and return a message
                os.makedirs(mount_point, exist_ok=True)
                
                try:
                    # Try to use the ipfs mount command
                    import subprocess
                    result = subprocess.run(["ipfs", "mount", "-f", mount_point], 
                                          capture_output=True, text=True, check=True)
                    return {
                        "mounted": True,
                        "mount_point": mount_point,
                        "message": "IPFS mounted successfully (requires FUSE)"
                    }
                except Exception as e:
                    return {
                        "mounted": False,
                        "mount_point": mount_point,
                        "error": str(e),
                        "message": "Failed to mount IPFS. Make sure FUSE is installed and ipfs mount is supported."
                    }
            
            setattr(controller, "_mount_ipfs_to_fs", mount_ipfs_to_fs)
            
        elif method_name == "unmount_ipfs_from_fs":
            def unmount_ipfs_from_fs(mount_point):
                """Unmount IPFS from a filesystem path."""
                try:
                    # Try to use the fusermount command to unmount
                    import subprocess
                    result = subprocess.run(["fusermount", "-u", mount_point], 
                                          capture_output=True, text=True, check=True)
                    return {
                        "unmounted": True,
                        "mount_point": mount_point
                    }
                except Exception as e:
                    return {
                        "unmounted": False,
                        "mount_point": mount_point,
                        "error": str(e),
                        "message": "Failed to unmount IPFS. Make sure FUSE is installed."
                    }
            
            setattr(controller, "_unmount_ipfs_from_fs", unmount_ipfs_from_fs)
    
    # If the method exists now (either originally or after adding it), create a handler
    if hasattr(controller, controller_method_name):
        controller_method = getattr(controller, controller_method_name)
        
        def handle_tool(args):
            """Handle the tool call."""
            try:
                # Extract the arguments from the request
                params = {}
                for param in tool_def["parameters"]:
                    name = param["name"]
                    if name in args:
                        params[name] = args[name]
                    elif "default" in param:
                        params[name] = param["default"]
                        
                # Call the controller method
                result = controller_method(**params)
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}
        
        # Create the tool handler
        handler = {
            "name": tool_def["name"],
            "description": tool_def["description"],
            "parameters": tool_def["parameters"],
            "handle": handle_tool
        }
        
        return handler
    
    return None

def main():
    """Test the tool definitions."""
    print(f"Defined {len(IPFS_TOOL_DEFINITIONS)} IPFS tools")
    for category, tools in {
        "Swarm Operations": [t for t in IPFS_TOOL_DEFINITIONS if t.startswith("swarm_")],
        "MFS Operations": ["list_files", "stat_file", "make_directory", "read_file", "write_file", "remove_file"],
        "Content Operations": ["add_content", "get_content", "get_content_as_tar"],
        "Pin Operations": ["pin_content", "unpin_content", "list_pins"],
        "IPNS Operations": ["publish_name", "resolve_name"],
        "DAG Operations": [t for t in IPFS_TOOL_DEFINITIONS if t.startswith("dag_")],
        "Block Operations": [t for t in IPFS_TOOL_DEFINITIONS if t.startswith("block_")],
        "DHT Operations": [t for t in IPFS_TOOL_DEFINITIONS if t.startswith("dht_")],
        "Node Operations": ["get_node_id", "get_version", "get_stats", "check_daemon_status", "get_replication_status"],
    }.items():
        print(f"  {category}: {len(tools)} tools")
    
    print(f"Defined {len(FILESYSTEM_TOOL_DEFINITIONS)} filesystem integration tools")

if __name__ == "__main__":
    main()
