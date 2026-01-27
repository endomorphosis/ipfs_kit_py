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
import anyio
import logging
import traceback
import hashlib
import os
import time
import subprocess
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
            
            process = await anyio.open_process(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            with anyio.fail_after(timeout):
                stdout, stderr = await process.communicate()
            
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
                
        except TimeoutError:
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
        
        elif command == "stat":
            if len(cmd_args) < 2:
                return {"success": False, "error": "CID required"}
            cid = cmd_args[1]
            return {
                "success": True,
                "data": {
                    "Hash": cid,
                    "BlockSize": 1024,
                    "CumulativeSize": 2048,
                    "DataSize": 1000,
                    "LinksSize": 24,
                    "NumLinks": 2,
                    "Type": "file"
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
        self.tools = {
            # Phase 1 tools (17 tools)
            "ipfs_add": {
                "name": "ipfs_add",
                "description": "Add content to IPFS and return the CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Content to add to IPFS"
                        },
                        "file_path": {
                            "type": "string", 
                            "description": "Path to file to add to IPFS"
                        }
                    }
                }
            },
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Retrieve content from IPFS by CID",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to retrieve"
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to pin"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Pin recursively",
                            "default": True
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to retrieve content from"
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID of directory to list"
                        },
                        "headers": {
                            "type": "boolean",
                            "description": "Print table headers",
                            "default": False
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to get statistics for"
                        }
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
                        "all": {
                            "type": "boolean",
                            "description": "Show all version information",
                            "default": False
                        }
                    }
                }
            },
            "ipfs_id": {
                "name": "ipfs_id",
                "description": "Get IPFS node identity and network information",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "peer_id": {
                            "type": "string",
                            "description": "Peer ID to get info for (default: self)"
                        }
                    }
                }
            },
            "ipfs_list_pins": {
                "name": "ipfs_list_pins",
                "description": "List all pinned content in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["all", "direct", "indirect", "recursive"],
                            "description": "Type of pins to list",
                            "default": "all"
                        },
                        "quiet": {
                            "type": "boolean",
                            "description": "Write just CIDs",
                            "default": False
                        }
                    }
                }
            },
            "ipfs_unpin": {
                "name": "ipfs_unpin",
                "description": "Remove pins from IPFS content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {
                            "type": "string",
                            "description": "IPFS CID to unpin"
                        },
                        "recursive": {
                            "type": "boolean", 
                            "description": "Recursively unpin the object linked to by the specified object(s)",
                            "default": True
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "CID of block to retrieve"
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "CID of block to get stats for"
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "CID of DAG object to retrieve"
                        },
                        "output_codec": {
                            "type": "string",
                            "enum": ["dag-json", "dag-cbor", "raw"],
                            "description": "Output codec for the data",
                            "default": "dag-json"
                        }
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
                        "cid": {
                            "type": "string",
                            "description": "CID of object to get stats for"
                        }
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
                        "path": {
                            "type": "string",
                            "description": "Path to check",
                            "default": "/"
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path to list (default: /)",
                            "default": "/"
                        },
                        "long": {
                            "type": "boolean",
                            "description": "Use long listing format",
                            "default": False
                        }
                    }
                }
            },
            "ipfs_files_mkdir": {
                "name": "ipfs_files_mkdir",
                "description": "Create a directory in IPFS MFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "MFS path for the new directory"
                        },
                        "parents": {
                            "type": "boolean",
                            "description": "Create parent directories as needed",
                            "default": False
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path for the file"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        },
                        "create": {
                            "type": "boolean",
                            "description": "Create the file if it doesn't exist",
                            "default": True
                        },
                        "truncate": {
                            "type": "boolean",
                            "description": "Truncate the file before writing",
                            "default": False
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path of the file to read"
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Byte offset to start reading from",
                            "default": 0
                        },
                        "count": {
                            "type": "integer",
                            "description": "Maximum number of bytes to read"
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path to remove"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Remove directories and their contents recursively",
                            "default": False
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Ignore nonexistent files",
                            "default": False
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path to get information about"
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format",
                            "default": "default"
                        },
                        "hash": {
                            "type": "boolean",
                            "description": "Print only the hash",
                            "default": False
                        },
                        "size": {
                            "type": "boolean",
                            "description": "Print only the size",
                            "default": False
                        }
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
                        "source": {
                            "type": "string",
                            "description": "Source path (MFS path or IPFS CID)"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination MFS path"
                        },
                        "parents": {
                            "type": "boolean",
                            "description": "Create parent directories as needed",
                            "default": False
                        }
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
                        "source": {
                            "type": "string",
                            "description": "Source MFS path"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination MFS path"
                        }
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
                        "path": {
                            "type": "string",
                            "description": "MFS path to flush (default: /)",
                            "default": "/"
                        }
                    }
                }
            }
        }
        
        logger.info(f"Registered {len(self.tools)} tools (Phase 2: {len(self.tools)} total, 9 new MFS tools)")
    
    def _validate_mfs_path(self, path: str) -> bool:
        """Validate MFS path format."""
        if not path:
            return False
        if not path.startswith('/'):
            return False
        # Additional validation can be added here
        return True
    
    # MCP Protocol handlers (unchanged from Phase 1)
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
        elif tool_name == "ipfs_files_write":
            return await self.ipfs_files_write_tool(arguments)
        elif tool_name == "ipfs_files_read":
            return await self.ipfs_files_read_tool(arguments)
        elif tool_name == "ipfs_files_rm":
            return await self.ipfs_files_rm_tool(arguments)
        elif tool_name == "ipfs_files_stat":
            return await self.ipfs_files_stat_tool(arguments)
        elif tool_name == "ipfs_files_cp":
            return await self.ipfs_files_cp_tool(arguments)
        elif tool_name == "ipfs_files_mv":
            return await self.ipfs_files_mv_tool(arguments)
        elif tool_name == "ipfs_files_flush":
            return await self.ipfs_files_flush_tool(arguments)
        else:
            return {"success": False, "error": f"Unknown MFS tool: {tool_name}"}
    
    async def ipfs_files_ls_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files and directories in IPFS MFS."""
        path = args.get("path", "/")
        long_format = args.get("long", False)
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "ls"]
        if long_format:
            cmd_args.append("--long")
        cmd_args.append(path)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "entries": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_mkdir_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a directory in IPFS MFS."""
        path = args.get("path")
        parents = args.get("parents", False)
        
        if not path:
            return {"success": False, "error": "Path is required"}
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "mkdir"]
        if parents:
            cmd_args.append("--parents")
        cmd_args.append(path)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "created": True,
                "parents": parents,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_write_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write content to a file in IPFS MFS."""
        path = args.get("path")
        content = args.get("content")
        create = args.get("create", True)
        truncate = args.get("truncate", False)
        
        if not path:
            return {"success": False, "error": "Path is required"}
        if not content:
            return {"success": False, "error": "Content is required"}
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        # Create temp file for content
        import tempfile
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(content)
                temp_path = f.name
            
            cmd_args = ["files", "write"]
            if create:
                cmd_args.append("--create")
            if truncate:
                cmd_args.append("--truncate")
            cmd_args.extend([path, temp_path])
            
            result = await self.ipfs.run_ipfs_command(cmd_args)
            
            if result["success"]:
                return {
                    "success": True,
                    "path": path,
                    "bytes_written": len(content),
                    "created": create,
                    "truncated": truncate,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return result
        
        finally:
            # Clean up temp file
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    async def ipfs_files_read_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read content from a file in IPFS MFS."""
        path = args.get("path")
        offset = args.get("offset", 0)
        count = args.get("count")
        
        if not path:
            return {"success": False, "error": "Path is required"}
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "read"]
        if offset > 0:
            cmd_args.extend(["--offset", str(offset)])
        if count:
            cmd_args.extend(["--count", str(count)])
        cmd_args.append(path)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "content": result["data"],
                "offset": offset,
                "count": count,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_rm_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove files or directories from IPFS MFS."""
        path = args.get("path")
        recursive = args.get("recursive", False)
        force = args.get("force", False)
        
        if not path:
            return {"success": False, "error": "Path is required"}
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "rm"]
        if recursive:
            cmd_args.append("--recursive")
        if force:
            cmd_args.append("--force")
        cmd_args.append(path)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "removed": True,
                "recursive": recursive,
                "force": force,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_stat_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about a file or directory in IPFS MFS."""
        path = args.get("path")
        format_str = args.get("format", "default")
        hash_only = args.get("hash", False)
        size_only = args.get("size", False)
        
        if not path:
            return {"success": False, "error": "Path is required"}
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "stat"]
        if hash_only:
            cmd_args.append("--hash")
        elif size_only:
            cmd_args.append("--size")
        elif format_str != "default":
            cmd_args.extend(["--format", format_str])
        cmd_args.append(path)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "stats": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_cp_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Copy files within IPFS MFS or from IPFS to MFS."""
        source = args.get("source")
        destination = args.get("destination")
        parents = args.get("parents", False)
        
        if not source:
            return {"success": False, "error": "Source is required"}
        if not destination:
            return {"success": False, "error": "Destination is required"}
        
        if not self._validate_mfs_path(destination):
            return {"success": False, "error": "Invalid destination MFS path"}
        
        cmd_args = ["files", "cp"]
        if parents:
            cmd_args.append("--parents")
        cmd_args.extend([source, destination])
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "source": source,
                "destination": destination,
                "copied": True,
                "parents": parents,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_mv_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Move files within IPFS MFS."""
        source = args.get("source")
        destination = args.get("destination")
        
        if not source:
            return {"success": False, "error": "Source is required"}
        if not destination:
            return {"success": False, "error": "Destination is required"}
        
        if not self._validate_mfs_path(source):
            return {"success": False, "error": "Invalid source MFS path"}
        if not self._validate_mfs_path(destination):
            return {"success": False, "error": "Invalid destination MFS path"}
        
        cmd_args = ["files", "mv", source, destination]
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "source": source,
                "destination": destination,
                "moved": True,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_files_flush_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Flush MFS changes and return the root hash."""
        path = args.get("path", "/")
        
        if not self._validate_mfs_path(path):
            return {"success": False, "error": "Invalid MFS path"}
        
        cmd_args = ["files", "flush", path]
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "path": path,
                "hash": result["data"],
                "flushed": True,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    # Phase 1 IPFS Tool implementations (copied from Phase 1)
    async def execute_ipfs_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute IPFS-related tools."""
        
        if tool_name == "ipfs_add":
            return await self.ipfs_add_tool(arguments)
        elif tool_name == "ipfs_get":
            return await self.ipfs_get_tool(arguments)
        elif tool_name == "ipfs_pin":
            return await self.ipfs_pin_tool(arguments)
        elif tool_name == "ipfs_cat":
            return await self.ipfs_cat_tool(arguments)
        elif tool_name == "ipfs_ls":
            return await self.ipfs_ls_tool(arguments)
        elif tool_name == "ipfs_stat":
            return await self.ipfs_stat_tool(arguments)
        elif tool_name == "ipfs_version":
            return await self.ipfs_version_tool(arguments)
        elif tool_name == "ipfs_id":
            return await self.ipfs_id_tool(arguments)
        elif tool_name == "ipfs_list_pins":
            return await self.ipfs_list_pins_tool(arguments)
        elif tool_name == "ipfs_unpin":
            return await self.ipfs_unpin_tool(arguments)
        elif tool_name == "ipfs_block_get":
            return await self.ipfs_block_get_tool(arguments)
        elif tool_name == "ipfs_block_stat":
            return await self.ipfs_block_stat_tool(arguments)
        elif tool_name == "ipfs_dag_get":
            return await self.ipfs_dag_get_tool(arguments)
        elif tool_name == "ipfs_object_stat":
            return await self.ipfs_object_stat_tool(arguments)
        else:
            return {"success": False, "error": f"Unknown IPFS tool: {tool_name}"}
    
    # IPFS Tool implementations (from Phase 1)
    async def ipfs_add_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add content to IPFS."""
        content = args.get("content", "")
        file_path = args.get("file_path", "")
        
        if not content and not file_path:
            return {"success": False, "error": "Either content or file_path must be provided"}
        
        temp_path = None
        try:
            if file_path:
                if not os.path.exists(file_path):
                    return {"success": False, "error": f"File not found: {file_path}"}
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'rb') as f:
                        content = f.read().decode('utf-8', errors='ignore')
                except Exception as e:
                    return {"success": False, "error": f"Error reading file: {str(e)}"}
            
            # Use IPFS interface
            cmd_args = ["add", "--quiet"]
            if content:
                # Create temp file for content
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                cmd_args.append(temp_path)
            else:
                cmd_args.append(file_path)
            
            result = await self.ipfs.run_ipfs_command(cmd_args)
            
            if result["success"]:
                cid = result["data"].strip() if isinstance(result["data"], str) else result["data"].get("Hash", "")
                return {
                    "success": True,
                    "cid": cid,
                    "size": len(content) if content else os.path.getsize(file_path),
                    "timestamp": datetime.now().isoformat(),
                    "source": "file_path" if file_path else "content"
                }
            else:
                return result
        
        finally:
            # Clean up temp file if created
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
    
    async def ipfs_get_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve content from IPFS (same as ipfs_cat_tool)."""
        return await self.ipfs_cat_tool(args)
    
    async def ipfs_pin_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Pin content in IPFS."""
        cid = args.get("cid")
        recursive = args.get("recursive", True)
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ["pin", "add"]
        if not recursive:
            cmd_args.append("--recursive=false")
        cmd_args.append(cid)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "recursive": recursive,
                "pinned": True,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_cat_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve and display content from IPFS."""
        cid = args.get("cid")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(["cat", cid])
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "content": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_ls_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents in IPFS."""
        cid = args.get("cid")
        headers = args.get("headers", False)
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ["ls"]
        if headers:
            cmd_args.append("--headers")
        cmd_args.append(cid)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "contents": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_stat_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get metadata and statistics about IPFS objects."""
        cid = args.get("cid")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        # Use dag stat instead of stat for better compatibility
        result = await self.ipfs.run_ipfs_command(["dag", "stat", cid])
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "stats": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_version_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get IPFS daemon version information."""
        all_info = args.get("all", False)
        
        cmd_args = ["version"]
        if all_info:
            cmd_args.append("--all")
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "version_info": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_id_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get IPFS node identity and network information."""
        peer_id = args.get("peer_id")
        
        cmd_args = ["id"]
        if peer_id:
            cmd_args.append(peer_id)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "identity": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_list_pins_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List all pinned content in IPFS."""
        pin_type = args.get("type", "all")
        quiet = args.get("quiet", False)
        
        cmd_args = ["pin", "ls"]
        if pin_type != "all":
            cmd_args.extend(["--type", pin_type])
        if quiet:
            cmd_args.append("--quiet")
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "pins": result["data"],
                "type": pin_type,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_unpin_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Remove pins from IPFS content."""
        cid = args.get("cid")
        recursive = args.get("recursive", True)
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ["pin", "rm"]
        if not recursive:
            cmd_args.append("--recursive=false")
        cmd_args.append(cid)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "unpinned": True,
                "recursive": recursive,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_block_get_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get raw block data from IPFS."""
        cid = args.get("cid")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(["block", "get", cid])
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "block_data": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_block_stat_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about an IPFS block."""
        cid = args.get("cid")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(["block", "stat", cid])
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "block_stats": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_dag_get_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get a DAG object from IPFS."""
        cid = args.get("cid")
        output_codec = args.get("output_codec", "dag-json")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ["dag", "get", "--output-codec", output_codec, cid]
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "dag_object": result["data"],
                "output_codec": output_codec,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    async def ipfs_object_stat_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about an IPFS object."""
        cid = args.get("cid")
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        # Use dag stat instead of deprecated object stat
        result = await self.ipfs.run_ipfs_command(["dag", "stat", cid])
        
        if result["success"]:
            return {
                "success": True,
                "cid": cid,
                "object_stats": result["data"],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return result
    
    # System tools (from original server)
    async def execute_system_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system monitoring tools."""
        if tool_name == "filesystem_health":
            return await self.filesystem_health_tool(arguments)
        elif tool_name == "system_health":
            return await self.system_health_tool(arguments)
        elif tool_name == "ipfs_cluster_status":
            return await self.ipfs_cluster_status_tool(arguments)
        else:
            return {"success": False, "error": f"Unknown system tool: {tool_name}"}
    
    async def filesystem_health_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check filesystem health."""
        path = args.get("path", "/")
        
        try:
            import psutil
            
            disk_usage = psutil.disk_usage(path)
            used_percent = (disk_usage.used / disk_usage.total) * 100
            
            if used_percent > 95:
                health_status = "critical"
            elif used_percent > 90:
                health_status = "warning"
            elif used_percent > 80:
                health_status = "moderate"
            else:
                health_status = "healthy"
            
            return {
                "success": True,
                "path": path,
                "health_status": health_status,
                "total_bytes": disk_usage.total,
                "used_bytes": disk_usage.used,
                "free_bytes": disk_usage.free,
                "used_percent": round(used_percent, 2),
                "timestamp": datetime.now().isoformat()
            }
            
        except ImportError:
            return {
                "success": True,
                "path": path,
                "health_status": "unknown",
                "message": "psutil not available - install with: pip install psutil",
                "timestamp": datetime.now().isoformat()
            }
    
    async def system_health_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health status."""
        health_data = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "server_version": __version__
        }
        
        try:
            import psutil
            
            health_data.update({
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": {}
            })
            
            for path in ["/", "/tmp", os.path.expanduser("~")]:
                try:
                    usage = psutil.disk_usage(path)
                    health_data["disk_usage"][path] = {
                        "used_percent": round((usage.used / usage.total) * 100, 2),
                        "free_gb": round(usage.free / (1024**3), 2)
                    }
                except:
                    pass
                    
        except ImportError:
            health_data["system_metrics"] = "psutil not available"
        
        return health_data
    
    async def ipfs_cluster_status_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get IPFS cluster status."""
        return {
            "success": True,
            "cluster_id": "12D3KooWExample",
