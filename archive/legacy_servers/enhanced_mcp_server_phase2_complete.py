#!/usr/bin/env python3
"""
Enhanced MCP Server for IPFS Kit - Phase 2: MFS Operations
==========================================================

This server extends Phase 1 with MFS (Mutable File System) operations,
providing comprehensive file system capabilities through the MCP protocol.

Phase 2 adds 9 MFS tools:
- ipfs_files_ls - List files in MFS
- ipfs_files_mkdir - Create directories in MFS
- ipfs_files_write - Write files to MFS
- ipfs_files_read - Read files from MFS
- ipfs_files_rm - Remove files/directories from MFS
- ipfs_files_stat - Get file/directory info in MFS
- ipfs_files_cp - Copy files in MFS
- ipfs_files_mv - Move files in MFS
- ipfs_files_flush - Flush MFS changes

Total tools: 26 (17 Phase 1 + 9 Phase 2)
"""

import sys
import json
import asyncio
import logging
import traceback
import hashlib
import os
import time
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("enhanced-mcp-ipfs-kit-phase2")

# Server metadata
__version__ = "2.1.0"


class IPFSInterface:
    """Interface for IPFS operations with real and mock implementations."""
    
    def __init__(self, use_real_ipfs=True):
        self.use_real_ipfs = use_real_ipfs
        self._check_ipfs_availability()
    
    def _check_ipfs_availability(self):
        """Check if IPFS daemon is available."""
        if not self.use_real_ipfs:
            logger.info("Using mock IPFS implementation")
            return
            
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"IPFS available: {result.stdout.strip()}")
                self.ipfs_available = True
            else:
                logger.warning("IPFS command failed, falling back to mock")
                self.use_real_ipfs = False
                self.ipfs_available = False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.warning(f"IPFS not available: {e}, using mock implementation")
            self.use_real_ipfs = False
            self.ipfs_available = False
    
    async def run_ipfs_command(self, cmd_args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run an IPFS command and return the result."""
        if not self.use_real_ipfs:
            return await self._mock_ipfs_command(cmd_args)
        
        try:
            # Run IPFS command
            full_cmd = ['ipfs'] + cmd_args
            logger.info(f"Running IPFS command: {' '.join(full_cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            if process.returncode == 0:
                stdout_text = stdout.decode('utf-8').strip()
                try:
                    # Try to parse as JSON first
                    result = json.loads(stdout_text)
                    return {"success": True, "data": result}
                except json.JSONDecodeError:
                    # Return as text if not JSON
                    return {"success": True, "data": stdout_text}
            else:
                error_text = stderr.decode('utf-8').strip()
                return {"success": False, "error": error_text}
                
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _mock_ipfs_command(self, cmd_args: List[str]) -> Dict[str, Any]:
        """Mock IPFS commands for testing/demo purposes."""
        if not cmd_args:
            return {"success": False, "error": "No command provided"}
        
        command = cmd_args[0]
        
        # Phase 1 commands (existing)
        if command == "add":
            content = "mock content"
            if len(cmd_args) > 1:
                content = cmd_args[1]
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            cid = f"bafkreie{content_hash[:48]}"
            return {
                "success": True,
                "data": {"Hash": cid, "Size": len(content)}
            }
        
        elif command == "cat":
            if len(cmd_args) < 2:
                return {"success": False, "error": "CID required"}
            cid = cmd_args[1]
            return {
                "success": True,
                "data": f"Mock content for CID: {cid}\nRetrieved at: {datetime.now().isoformat()}"
            }
        
        elif command == "ls":
            if len(cmd_args) < 2:
                return {"success": False, "error": "CID required"}
            cid = cmd_args[1]
            return {
                "success": True,
                "data": {
                    "Objects": [{
                        "Hash": cid,
                        "Links": [
                            {"Name": "file1.txt", "Hash": "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12", "Size": 100},
                            {"Name": "file2.txt", "Hash": "bafkreie2345678901bcdef02345678901bcdef02345678901bcdef023", "Size": 200}
                        ]
                    }]
                }
            }
        
        elif command == "dag" and len(cmd_args) > 1:
            subcommand = cmd_args[1]
            if subcommand == "stat":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": {
                        "Size": 1024,
                        "NumBlocks": 1
                    }
                }
            elif subcommand == "get":
                cid = cmd_args[4] if len(cmd_args) > 4 else "bafkreimock"
                return {
                    "success": True,
                    "data": {
                        "data": f"mock dag data for {cid}",
                        "links": []
                    }
                }
        
        elif command == "version":
            return {
                "success": True,
                "data": {
                    "Version": "0.24.0",
                    "Commit": "mock-commit",
                    "Repo": "15",
                    "System": "mock/mock",
                    "Golang": "go1.21.0"
                }
            }
        
        elif command == "id":
            return {
                "success": True,
                "data": {
                    "ID": "12D3KooWMockPeerID",
                    "PublicKey": "CAASpmock",
                    "Addresses": ["/ip4/127.0.0.1/tcp/4001"],
                    "AgentVersion": "go-ipfs/0.24.0/mock",
                    "ProtocolVersion": "ipfs/0.1.0",
                    "Protocols": ["ipfs/id/1.0.0", "ipfs/ping/1.0.0"]
                }
            }
        
        elif command == "pin" and len(cmd_args) > 1:
            subcommand = cmd_args[1]
            if subcommand == "ls":
                return {
                    "success": True,
                    "data": {
                        "Keys": {
                            "bafkreie1": {"Type": "recursive"},
                            "bafkreie2": {"Type": "direct"}
                        }
                    }
                }
            elif subcommand == "add":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": {"Pins": [cid]}
                }
            elif subcommand == "rm":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": {"Pins": [cid]}
                }
        
        elif command == "block":
            subcommand = cmd_args[1] if len(cmd_args) > 1 else ""
            if subcommand == "get":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": f"Mock block data for {cid}"
                }
            elif subcommand == "stat":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": {
                        "Key": cid,
                        "Size": 1024
                    }
                }
        
        elif command == "object":
            subcommand = cmd_args[1] if len(cmd_args) > 1 else ""
            if subcommand == "stat":
                cid = cmd_args[2] if len(cmd_args) > 2 else "bafkreimock"
                return {
                    "success": True,
                    "data": {
                        "Hash": cid,
                        "NumLinks": 0,
                        "BlockSize": 512,
                        "LinksSize": 0,
                        "DataSize": 512,
                        "CumulativeSize": 512
                    }
                }
        
        # Phase 2: MFS commands
        elif command == "files":
            if len(cmd_args) < 2:
                return {"success": False, "error": "MFS subcommand required"}
            
            subcommand = cmd_args[1]
            
            if subcommand == "ls":
                path = cmd_args[2] if len(cmd_args) > 2 else "/"
                return {
                    "success": True,
                    "data": {
                        "Entries": [
                            {"Name": "documents", "Type": 1, "Size": 0, "Hash": "bafkreie1234"},
                            {"Name": "photos", "Type": 1, "Size": 0, "Hash": "bafkreie5678"},
                            {"Name": "readme.txt", "Type": 0, "Size": 256, "Hash": "bafkreie9012"}
                        ]
                    }
                }
            
            elif subcommand == "mkdir":
                path = cmd_args[2] if len(cmd_args) > 2 else "/new_dir"
                return {
                    "success": True,
                    "data": f"Directory created: {path}"
                }
            
            elif subcommand == "write":
                path = cmd_args[2] if len(cmd_args) > 2 else "/new_file.txt"
                return {
                    "success": True,
                    "data": f"File written: {path}"
                }
            
            elif subcommand == "read":
                path = cmd_args[2] if len(cmd_args) > 2 else "/file.txt"
                return {
                    "success": True,
                    "data": f"Mock file content from MFS path: {path}\nRead at: {datetime.now().isoformat()}"
                }
            
            elif subcommand == "rm":
                path = cmd_args[2] if len(cmd_args) > 2 else "/file_to_remove"
                return {
                    "success": True,
                    "data": f"Removed: {path}"
                }
            
            elif subcommand == "stat":
                path = cmd_args[2] if len(cmd_args) > 2 else "/file.txt"
                return {
                    "success": True,
                    "data": {
                        "Hash": "bafkreie1234567890abcdef",
                        "Size": 1024,
                        "CumulativeSize": 1024,
                        "Blocks": 1,
                        "Type": "file"
                    }
                }
            
            elif subcommand == "cp":
                source = cmd_args[2] if len(cmd_args) > 2 else "/source"
                dest = cmd_args[3] if len(cmd_args) > 3 else "/dest"
                return {
                    "success": True,
                    "data": f"Copied {source} to {dest}"
                }
            
            elif subcommand == "mv":
                source = cmd_args[2] if len(cmd_args) > 2 else "/source"
                dest = cmd_args[3] if len(cmd_args) > 3 else "/dest"
                return {
                    "success": True,
                    "data": f"Moved {source} to {dest}"
                }
            
            elif subcommand == "flush":
                path = cmd_args[2] if len(cmd_args) > 2 else "/"
                return {
                    "success": True,
                    "data": {
                        "Hash": "bafkreie1234567890abcdef1234567890abcdef1234567890abcdef12",
                        "Path": path
                    }
                }
        
        # Default fallback
        return {
            "success": False,
            "error": f"Mock command not implemented: {' '.join(cmd_args)}"
        }


class EnhancedMCPServerPhase2:
    """Enhanced MCP Server Phase 2 with MFS operations."""
    
    def __init__(self):
        self.ipfs = IPFSInterface()
        self.tools = {}
        self.register_tools()
        
    def register_tools(self):
        """Register all available tools (Phase 1 + Phase 2)."""
        # Phase 1 tools (17 tools) + Phase 2 MFS tools (9 tools) = 26 total
        self.tools = {
            # Phase 1 tools
            "ipfs_add": {
                "name": "ipfs_add",
                "description": "Add content to IPFS and return the CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to add to IPFS"},
                        "file_path": {"type": "string", "description": "Path to file to add to IPFS"}
                    }
                }
            },
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Retrieve content from IPFS by CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to retrieve"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_pin": {
                "name": "ipfs_pin",
                "description": "Pin content in IPFS to prevent garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to pin"},
                        "recursive": {"type": "boolean", "description": "Pin recursively", "default": True}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_cat": {
                "name": "ipfs_cat",
                "description": "Retrieve and display content from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to retrieve content from"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_ls": {
                "name": "ipfs_ls", 
                "description": "List directory contents in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID of directory to list"},
                        "headers": {"type": "boolean", "description": "Print table headers", "default": False}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_stat": {
                "name": "ipfs_stat",
                "description": "Get metadata and statistics about IPFS objects",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to get statistics for"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_version": {
                "name": "ipfs_version",
                "description": "Get IPFS daemon version information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "all": {"type": "boolean", "description": "Show all version information", "default": False}
                    }
                }
            },
            "ipfs_id": {
                "name": "ipfs_id",
                "description": "Get IPFS node identity and network information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "peer_id": {"type": "string", "description": "Peer ID to get info for (default: self)"}
                    }
                }
            },
            "ipfs_list_pins": {
                "name": "ipfs_list_pins",
                "description": "List all pinned content in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["all", "direct", "indirect", "recursive"], "description": "Type of pins to list", "default": "all"},
                        "quiet": {"type": "boolean", "description": "Write just CIDs", "default": False}
                    }
                }
            },
            "ipfs_unpin": {
                "name": "ipfs_unpin",
                "description": "Remove pins from IPFS content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to unpin"},
                        "recursive": {"type": "boolean", "description": "Recursively unpin the object linked to by the specified object(s)", "default": True}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_block_get": {
                "name": "ipfs_block_get",
                "description": "Get raw block data from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID of block to retrieve"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_block_stat": {
                "name": "ipfs_block_stat",
                "description": "Get statistics about an IPFS block",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID of block to get stats for"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_dag_get": {
                "name": "ipfs_dag_get",
                "description": "Get a DAG object from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID of DAG object to retrieve"},
                        "output_codec": {"type": "string", "enum": ["dag-json", "dag-cbor", "raw"], "description": "Output codec for the data", "default": "dag-json"}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_object_stat": {
                "name": "ipfs_object_stat",
                "description": "Get statistics about an IPFS object",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "CID of object to get stats for"}
                    },
                    "required": ["cid"]
                }
            },
            "filesystem_health": {
                "name": "filesystem_health",
                "description": "Check filesystem health and disk usage",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to check", "default": "/"}
                    }
                }
            },
            "system_health": {
                "name": "system_health",
                "description": "Get comprehensive system health status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_cluster_status": {
                "name": "ipfs_cluster_status",
                "description": "Get IPFS cluster status and peer information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            
            # Phase 2: MFS Operations (9 new tools)
            "ipfs_files_ls": {
                "name": "ipfs_files_ls",
                "description": "List files and directories in IPFS MFS (Mutable File System)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to list (default: /)", "default": "/"},
                        "long": {"type": "boolean", "description": "Use long listing format", "default": False}
                    }
                }
            },
            "ipfs_files_mkdir": {
                "name": "ipfs_files_mkdir",
                "description": "Create a directory in IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path for the new directory"},
                        "parents": {"type": "boolean", "description": "Create parent directories as needed", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_write": {
                "name": "ipfs_files_write",
                "description": "Write content to a file in IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path for the file"},
                        "content": {"type": "string", "description": "Content to write to the file"},
                        "create": {"type": "boolean", "description": "Create the file if it doesn't exist", "default": True},
                        "truncate": {"type": "boolean", "description": "Truncate the file before writing", "default": False}
                    },
                    "required": ["path", "content"]
                }
            },
            "ipfs_files_read": {
                "name": "ipfs_files_read",
                "description": "Read content from a file in IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path of the file to read"},
                        "offset": {"type": "integer", "description": "Byte offset to start reading from", "default": 0},
                        "count": {"type": "integer", "description": "Maximum number of bytes to read"}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_rm": {
                "name": "ipfs_files_rm",
                "description": "Remove files or directories from IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to remove"},
                        "recursive": {"type": "boolean", "description": "Remove directories and their contents recursively", "default": False},
                        "force": {"type": "boolean", "description": "Ignore nonexistent files", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_stat": {
                "name": "ipfs_files_stat",
                "description": "Get information about a file or directory in IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to get information about"},
                        "format": {"type": "string", "description": "Output format", "default": "default"},
                        "hash": {"type": "boolean", "description": "Print only the hash", "default": False},
                        "size": {"type": "boolean", "description": "Print only the size", "default": False}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_files_cp": {
                "name": "ipfs_files_cp",
                "description": "Copy files within IPFS MFS or from IPFS to MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source path (MFS path or IPFS CID)"},
                        "destination": {"type": "string", "description": "Destination MFS path"},
                        "parents": {"type": "boolean", "description": "Create parent directories as needed", "default": False}
                    },
                    "required": ["source", "destination"]
                }
            },
            "ipfs_files_mv": {
                "name": "ipfs_files_mv",
                "description": "Move files within IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source MFS path"},
                        "destination": {"type": "string", "description": "Destination MFS path"}
                    },
                    "required": ["source", "destination"]
                }
            },
            "ipfs_files_flush": {
                "name": "ipfs_files_flush",
                "description": "Flush MFS changes and return the root hash",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "MFS path to flush (default: /)", "default": "/"}
                    }
                }
            }
        }
        
        logger.info(f"Registered {len(self.tools)} tools (Phase 2: 17 Phase 1 + 9 MFS tools)")
    
    def _validate_mfs_path(self, path: str) -> bool:
        """Validate MFS path format."""
        if not path:
            return False
        if not path.startswith('/'):
            return False
        return True
    
    # MCP Protocol handlers
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        logger.info("Handling initialize request")
        
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "resourceTemplates": {"listChanged": False},
                "logging": {}
            },
            "serverInfo": {
                "name": "enhanced-ipfs-kit-mcp-server-phase2",
                "version": __version__
            }
        }
    
    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        logger.info("Handling tools/list request")
        
        tools_list = list(self.tools.values())
        return {"tools": tools_list}
    
    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        logger.info("Handling resources/list request")
        return {"resources": []}
    
    async def handle_resources_templates_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/templates/list request."""
        logger.info("Handling resources/templates/list request")
        return {"resourceTemplates": []}
    
    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Handling tools/call request for: {tool_name}")
        
        if tool_name not in self.tools:
            raise Exception(f"Tool '{tool_name}' not found")
        
        # Execute the tool
        result = await self.execute_tool(tool_name, arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ],
            "isError": result.get("success", True) is False
        }
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool."""
        try:
            # Route to appropriate handler
            if tool_name.startswith("ipfs_files_"):
                return await self.execute_mfs_tool(tool_name, arguments)
            elif tool_name.startswith("ipfs_") and tool_name != "ipfs_cluster_status":
                return await self.execute_ipfs_tool(tool_name, arguments)
            elif tool_name in ["filesystem_health", "system_health", "ipfs_cluster_status"]:
                return await self.execute_system_tool(tool_name, arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    # Phase 2: MFS Tool implementations
    async def execute_mfs_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute MFS-related tools."""
        
        if tool_name == "ipfs_files_ls":
            return await self.ipfs_files_ls_tool(arguments)
        elif tool_name == "ipfs_files_mkdir":
            return await self.ipfs_files_mkdir_tool(arguments)
        elif
