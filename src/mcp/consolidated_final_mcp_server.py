#!/usr/bin/env python3
"""
Consolidated MCP Server

This is the final, consolidated MCP server implementation that integrates all IPFS and
Virtual Filesystem tools into a single, reliable server. It resolves previous code debt
issues and provides a clean, organized codebase.

Features:
- Core IPFS functionality
- Virtual Filesystem (VFS) capabilities
- IPFS-VFS bridge for seamless integration
- Filesystem journal for operation logging
- Utility tools for server management
- Health endpoint for monitoring
- Initialize endpoint for VSCode integration

All tools are exposed through a consistent JSON-RPC interface that follows the
Model Context Protocol (MCP).
"""

import os
import sys
import json
import time
import uuid
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from functools import wraps

try:
    import requests
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route, Mount
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    import uvicorn
except ImportError:
    print("Required packages not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                          "starlette", "uvicorn", "requests"])
    import requests
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, PlainTextResponse
    from starlette.routing import Route, Mount
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("consolidated_mcp_server")

# ===== Constants =====
SERVER_VERSION = "1.0.0"
SERVER_NAME = "Consolidated IPFS-VFS MCP Server"
SERVER_START_TIME = time.time()

# IPFS API Configuration
# Dynamic IPFS API URL discovery
def get_ipfs_api_url():
    try:
        # Try to get the swarm port which is also used for API
        import subprocess
        result = subprocess.run(['ipfs', 'id', '-f=<addrs>'], capture_output=True, text=True)
        output = result.stdout

        # Look for the localhost address
        import re
        match = re.search(r'/ip4/127\.0\.0\.1/tcp/(\d+)', output)
        if match:
            port = match.group(1)
            # Use API port if we found the swarm port
            return f"http://127.0.0.1:{port}/api/v0"
    except Exception as e:
        logger.error(f"Failed to discover IPFS API port: {e}")

    # Fall back to default if discovery fails
    return "http://127.0.0.1:5001/api/v0"

IPFS_API_URL = get_ipfs_api_url()
logger.info(f"Using IPFS API URL: {IPFS_API_URL}")

# ===== Virtual Filesystem =====
class VirtualFileSystem:
    """In-memory virtual filesystem implementation"""

    def __init__(self):
        """Initialize the virtual filesystem with a root directory"""
        self.root = {
            "type": "directory",
            "children": {},
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        }

    def _get_path_parts(self, path: str) -> List[str]:
        """Split a path into its component parts"""
        if not path or path == "/":
            return []

        # Remove leading and trailing slashes, then split
        path = path.strip("/")
        if not path:
            return []

        return path.split("/")

    def _get_parent_dir(self, path: str) -> Tuple[Dict, str]:
        """Get the parent directory of a path and the basename"""
        parts = self._get_path_parts(path)

        if not parts:
            # Root path
            return self.root, "/"

        basename = parts.pop()

        # Navigate to the parent directory
        current = self.root
        for part in parts:
            if part not in current["children"] or current["children"][part]["type"] != "directory":
                raise FileNotFoundError(f"Path not found: /{'/'.join(parts)}")

            current = current["children"][part]

        return current, basename

    def mkdir(self, path: str) -> Dict:
        """Create a directory at the specified path"""
        if not path or path == "/":
            return {"success": True, "path": "/", "exists": True}

        parts = self._get_path_parts(path)
        current = self.root
        created_path = ""

        for i, part in enumerate(parts):
            created_path = f"{created_path}/{part}"

            if part in current["children"]:
                if current["children"][part]["type"] != "directory":
                    raise ValueError(f"Path exists but is not a directory: {created_path}")

                # Directory already exists, continue to next part
                current = current["children"][part]
                continue

            # Create the directory
            current["children"][part] = {
                "type": "directory",
                "children": {},
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
            }

            current = current["children"][part]

        return {"success": True, "path": path, "created": True}

    def write(self, path: str, content: str) -> Dict:
        """Write content to a file at the specified path"""
        if not path or path == "/":
            raise ValueError("Cannot write to root directory")

        parent, basename = self._get_parent_dir(path)

        # Update file if it exists, otherwise create it
        if basename in parent["children"] and parent["children"][basename]["type"] == "file":
            parent["children"][basename]["content"] = content
            parent["children"][basename]["modified"] = datetime.now().isoformat()
            parent["children"][basename]["size"] = len(content)
        else:
            parent["children"][basename] = {
                "type": "file",
                "content": content,
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
                "size": len(content),
            }

        return {
            "success": True,
            "path": path,
            "size": len(content),
            "updated": basename in parent["children"]
        }

    def read(self, path: str) -> Dict:
        """Read content from a file at the specified path"""
        if not path or path == "/":
            raise ValueError("Cannot read from root directory")

        parent, basename = self._get_parent_dir(path)

        if basename not in parent["children"]:
            raise FileNotFoundError(f"File not found: {path}")

        file_entry = parent["children"][basename]

        if file_entry["type"] != "file":
            raise ValueError(f"Path is not a file: {path}")

        return {
            "success": True,
            "path": path,
            "content": file_entry["content"],
            "size": file_entry["size"],
            "created": file_entry["created"],
            "modified": file_entry["modified"]
        }

    def stat(self, path: str) -> Dict:
        """Get information about a file or directory"""
        if not path or path == "/":
            return {
                "success": True,
                "path": "/",
                "type": "directory",
                "created": self.root["created"],
                "modified": self.root["modified"],
                "children_count": len(self.root["children"])
            }

        parent, basename = self._get_parent_dir(path)

        if basename not in parent["children"]:
            raise FileNotFoundError(f"Path not found: {path}")

        entry = parent["children"][basename]

        result = {
            "success": True,
            "path": path,
            "type": entry["type"],
            "created": entry["created"],
            "modified": entry["modified"]
        }

        if entry["type"] == "file":
            result["size"] = entry["size"]
        else:
            result["children_count"] = len(entry["children"])

        return result

    def list(self, path: str) -> Dict:
        """List the contents of a directory"""
        if not path or path == "/":
            entries = [{"name": name, "type": info["type"]} for name, info in self.root["children"].items()]
            return {
                "success": True,
                "path": "/",
                "entries": entries
            }

        parts = self._get_path_parts(path)

        # Navigate to the directory
        current = self.root
        for part in parts:
            if part not in current["children"] or current["children"][part]["type"] != "directory":
                raise FileNotFoundError(f"Directory not found: {path}")

            current = current["children"][part]

        entries = [{"name": name, "type": info["type"]} for name, info in current["children"].items()]

        return {
            "success": True,
            "path": path,
            "entries": entries
        }

    def rm(self, path: str) -> Dict:
        """Remove a file or directory"""
        if not path or path == "/":
            raise ValueError("Cannot remove root directory")

        parent, basename = self._get_parent_dir(path)

        if basename not in parent["children"]:
            raise FileNotFoundError(f"Path not found: {path}")

        # Check if it's a non-empty directory
        entry = parent["children"][basename]
        if entry["type"] == "directory" and entry["children"]:
            raise ValueError(f"Directory is not empty: {path}")

        # Remove the entry
        del parent["children"][basename]

        return {
            "success": True,
            "path": path,
            "removed": True
        }

# ===== Filesystem Journal =====
class FilesystemJournal:
    """Journal to record filesystem operations"""

    def __init__(self):
        """Initialize the journal"""
        self.entries = []

    def record(self, operation: str, path: str, details: Dict = None) -> Dict:
        """Record an operation in the journal"""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
            "details": details or {}
        }

        self.entries.append(entry)

        return {
            "success": True,
            "entry_id": entry["id"]
        }

    def get_history(self, limit: int = None) -> Dict:
        """Get the operation history"""
        if limit is not None:
            entries = self.entries[-limit:]
        else:
            entries = self.entries

        return {
            "success": True,
            "entries": entries
        }

    def clear(self) -> Dict:
        """Clear the journal"""
        self.entries = []

        return {
            "success": True,
            "cleared": True
        }

    def status(self) -> Dict:
        """Get the journal status"""
        return {
            "success": True,
            "enabled": True,  # The journal is always enabled in this implementation
            "count": len(self.entries),
            "oldest": self.entries[0]["timestamp"] if self.entries else None,
            "newest": self.entries[-1]["timestamp"] if self.entries else None
        }

# ===== IPFS-VFS Bridge =====
class IPFSVFSBridge:
    """Bridge between IPFS and the virtual filesystem"""

    def __init__(self, vfs: VirtualFileSystem):
        """Initialize the bridge"""
        self.vfs = vfs
        self.mappings = {}  # Maps VFS paths to IPFS CIDs

    def export_to_ipfs(self, path: str) -> Dict:
        """Export a file from VFS to IPFS"""
        try:
            # Read the file from VFS
            file_data = self.vfs.read(path)

            # Add the content to IPFS
            response = requests.post(
                f"{IPFS_API_URL}/add",
                files={"file": file_data["content"]}
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            ipfs_data = response.json()
            cid = ipfs_data["Hash"]

            # Store the mapping
            self.mappings[path] = cid

            return {
                "success": True,
                "path": path,
                "cid": cid,
                "size": file_data["size"]
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def import_from_ipfs(self, cid: str, path: str) -> Dict:
        """Import content from IPFS to VFS"""
        try:
            # Get the content from IPFS
            response = requests.post(
                f"{IPFS_API_URL}/cat",
                params={"arg": cid}
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            content = response.text

            # Create parent directories if needed
            parent_path = os.path.dirname(path)
            if parent_path:
                self.vfs.mkdir(parent_path)

            # Write the content to VFS
            result = self.vfs.write(path, content)

            # Store the mapping
            self.mappings[path] = cid

            return {
                "success": True,
                "path": path,
                "cid": cid,
                "size": result["size"]
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def status(self) -> Dict:
        """Get the bridge status"""
        return {
            "success": True,
            "mappings_count": len(self.mappings)
        }

    def list_mappings(self) -> Dict:
        """List all VFS-IPFS mappings"""
        return {
            "success": True,
            "mappings": self.mappings
        }

# ===== IPFS Tools =====
class IPFSTools:
    """Tools for interacting with IPFS"""

    @staticmethod
    def add(content: str, name: str = "file.txt") -> Dict:
        """Add content to IPFS"""
        try:
            response = requests.post(
                f"{IPFS_API_URL}/add",
                files={"file": (name, content)}
            )

            if response.status_code != 200:
                return {
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            return response.json()

        except Exception as e:
            return {
                "error": str(e)
            }

    @staticmethod
    def cat(hash: str) -> Dict:
        """Retrieve content from IPFS"""
        try:
            response = requests.post(
                f"{IPFS_API_URL}/cat",
                params={"arg": hash}
            )

            if response.status_code != 200:
                return {
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            return {
                "data": response.text
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    @staticmethod
    def pin_add(hash: str) -> Dict:
        """Pin content to local IPFS node"""
        try:
            response = requests.post(
                f"{IPFS_API_URL}/pin/add",
                params={"arg": hash}
            )

            if response.status_code != 200:
                return {
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            return {
                "success": True,
                "hash": hash
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    @staticmethod
    def pin_ls() -> Dict:
        """List pinned content"""
        try:
            response = requests.post(
                f"{IPFS_API_URL}/pin/ls"
            )

            if response.status_code != 200:
                return {
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            data = response.json()

            return {
                "pins": list(data.get("Keys", {}).keys())
            }

        except Exception as e:
            return {
                "error": str(e)
            }

    @staticmethod
    def pin_rm(hash: str) -> Dict:
        """Unpin content from local IPFS node"""
        try:
            response = requests.post(
                f"{IPFS_API_URL}/pin/rm",
                params={"arg": hash}
            )

            if response.status_code != 200:
                return {
                    "error": f"IPFS API error: {response.status_code}",
                    "details": response.text
                }

            return {
                "success": True,
                "hash": hash
            }

        except Exception as e:
            return {
                "error": str(e)
            }

# ===== MCP Server =====
class MCPServer:
    """Consolidated MCP Server implementation"""

    def __init__(self):
        """Initialize the server components"""
        self.start_time = time.time()
        self.vfs = VirtualFileSystem()
        self.journal = FilesystemJournal()
        self.bridge = IPFSVFSBridge(self.vfs)
        self.ipfs = IPFSTools()
        self.tools = {}

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register all available tools"""
        # Utility tools
        self.register_tool("utility_ping", self.utility_ping,
                          {"message": {"type": "string", "description": "Message to ping"}},
                          "Test server connectivity")

        self.register_tool("utility_server_info", self.utility_server_info,
                          {},
                          "Get server information")

        # IPFS tools
        self.register_tool("ipfs_add", self.ipfs_add,
                          {"content": {"type": "string", "description": "Content to add to IPFS"},
                           "name": {"type": "string", "description": "Name for the file", "default": "file.txt"}},
                          "Add content to IPFS")

        self.register_tool("ipfs_cat", self.ipfs_cat,
                          {"cid": {"type": "string", "description": "IPFS CID to retrieve"}},
                          "Retrieve content from IPFS")

        self.register_tool("ipfs_pin_add", self.ipfs_pin_add,
                          {"cid": {"type": "string", "description": "IPFS CID to pin"}},
                          "Pin content to local IPFS node")

        self.register_tool("ipfs_pin_ls", self.ipfs_pin_ls,
                          {},
                          "List pinned content")

        self.register_tool("ipfs_pin_rm", self.ipfs_pin_rm,
                          {"cid": {"type": "string", "description": "IPFS CID to unpin"}},
                          "Unpin content from local IPFS node")

        # VFS tools
        self.register_tool("vfs_mkdir", self.vfs_mkdir,
                          {"path": {"type": "string", "description": "Directory path to create"}},
                          "Create a directory in the virtual filesystem")

        self.register_tool("vfs_write", self.vfs_write,
                          {"path": {"type": "string", "description": "File path to write to"},
                           "content": {"type": "string", "description": "Content to write"}},
                          "Write content to a file in the virtual filesystem")

        self.register_tool("vfs_read", self.vfs_read,
                          {"path": {"type": "string", "description": "File path to read from"}},
                          "Read content from a file in the virtual filesystem")

        self.register_tool("vfs_stat", self.vfs_stat,
                          {"path": {"type": "string", "description": "Path to get information about"}},
                          "Get information about a file or directory in the virtual filesystem")

        self.register_tool("vfs_list", self.vfs_list,
                          {"path": {"type": "string", "description": "Directory path to list"}},
                          "List the contents of a directory in the virtual filesystem")

        self.register_tool("vfs_rm", self.vfs_rm,
                          {"path": {"type": "string", "description": "Path to remove"}},
                          "Remove a file or directory from the virtual filesystem")

        # IPFS-VFS bridge tools
        self.register_tool("ipfs_fs_export_to_ipfs", self.ipfs_fs_export_to_ipfs,
                          {"path": {"type": "string", "description": "VFS file path to export to IPFS"}},
                          "Export a file from the virtual filesystem to IPFS")

        self.register_tool("ipfs_fs_import_from_ipfs", self.ipfs_fs_import_from_ipfs,
                          {"cid": {"type": "string", "description": "IPFS CID to import"},
                           "path": {"type": "string", "description": "VFS file path to import to"}},
                          "Import content from IPFS to the virtual filesystem")

        self.register_tool("ipfs_fs_bridge_status", self.ipfs_fs_bridge_status,
                          {},
                          "Get the status of the IPFS-VFS bridge")

        self.register_tool("ipfs_fs_bridge_list_mappings", self.ipfs_fs_bridge_list_mappings,
                          {},
                          "List all mappings between VFS paths and IPFS CIDs")

        # Filesystem journal tools
        self.register_tool("fs_journal_record", self.fs_journal_record,
                          {"operation": {"type": "string", "description": "Operation to record"},
                           "path": {"type": "string", "description": "Path the operation was performed on"},
                           "details": {"type": "object", "description": "Additional details about the operation"}},
                          "Record an operation in the filesystem journal")

        self.register_tool("fs_journal_get_history", self.fs_journal_get_history,
                          {"limit": {"type": "integer", "description": "Maximum number of entries to return"}},
                          "Get the operation history from the filesystem journal")

        self.register_tool("fs_journal_status", self.fs_journal_status,
                          {},
                          "Get the status of the filesystem journal")

        self.register_tool("fs_journal_clear", self.fs_journal_clear,
                          {},
                          "Clear the filesystem journal")

    def register_tool(self, name: str, func: Callable, parameters: Dict, description: str):
        """Register a tool with the server"""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func
        }
        logger.info(f"Registered tool: {name}")

    def use_tool(self, params: Dict) -> Dict:
        """Use a registered tool"""
        tool_name = params.get("tool_name")

        if not tool_name:
            return {"error": "tool_name is required"}

        if tool_name not in self.tools:
            return {"error": f"Tool not found: {tool_name}"}

        tool = self.tools[tool_name]

        # Extract parameters for the tool
        tool_params = {}
        for param_name, param_info in tool["parameters"].items():
            if param_name in params:
                tool_params[param_name] = params[param_name]
            elif "default" in param_info:
                tool_params[param_name] = param_info["default"]
            elif param_info.get("required", True):
                return {"error": f"Missing required parameter: {param_name}"}

        try:
            # Call the tool function with the parameters
            result = tool["function"](**tool_params)
            return result
        except Exception as e:
            logger.error(f"Error using tool {tool_name}: {str(e)}")
            return {"error": str(e)}

    def get_server_info(self) -> Dict:
        """Get information about the server"""
        return {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "uptime": time.time() - SERVER_START_TIME,
            "tools_count": len(self.tools),
            "tools": list(self.tools.keys())
        }

    def get_tools_info(self) -> List[Dict]:
        """Get information about all registered tools"""
        tools_info = []

        for name, tool in self.tools.items():
            tools_info.append({
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            })

        return tools_info

    # ===== Tool Implementations =====

    # Utility tools
    def utility_ping(self, message: str = "hello") -> Dict:
        """Test server connectivity"""
        return {
            "pong": True,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    def utility_server_info(self) -> Dict:
        """Get server information"""
        return {
            "version": SERVER_VERSION,
            "uptime": time.time() - SERVER_START_TIME,
            "tools_count": len(self.tools)
        }

    # IPFS tools
    def ipfs_add(self, content: str, name: str = "file.txt") -> Dict:
        """Add content to IPFS"""
        return self.ipfs.add(content, name)

    def ipfs_cat(self, cid: str) -> Dict:
        """Retrieve content from IPFS"""
        return self.ipfs.cat(cid)

    def ipfs_pin_add(self, cid: str) -> Dict:
        """Pin content to local IPFS node"""
        return self.ipfs.pin_add(cid)

    def ipfs_pin_ls(self) -> Dict:
        """List pinned content"""
        return self.ipfs.pin_ls()

    def ipfs_pin_rm(self, cid: str) -> Dict:
        """Unpin content from local IPFS node"""
        return self.ipfs.pin_rm(cid)

    # VFS tools
    def vfs_mkdir(self, path: str) -> Dict:
        """Create a directory in the virtual filesystem"""
        try:
            result = self.vfs.mkdir(path)
            # Record in journal
            self.journal.record("mkdir", path, {"success": True})
            return result
        except Exception as e:
            self.journal.record("mkdir", path, {"success": False, "error": str(e)})
            raise

    def vfs_write(self, path: str, content: str) -> Dict:
        """Write content to a file in the virtual filesystem"""
        try:
            result = self.vfs.write(path, content)
            # Record in journal
            self.journal.record("write", path, {"success": True, "size": len(content)})
            return result
        except Exception as e:
            self.journal.record("write", path, {"success": False, "error": str(e)})
            raise

    def vfs_read(self, path: str) -> Dict:
        """Read content from a file in the virtual filesystem"""
        try:
            result = self.vfs.read(path)
            # Record in journal
            self.journal.record("read", path, {"success": True})
            return result
        except Exception as e:
            self.journal.record("read", path, {"success": False, "error": str(e)})
            raise

    def vfs_stat(self, path: str) -> Dict:
        """Get information about a file or directory in the virtual filesystem"""
        try:
            result = self.vfs.stat(path)
            # Record in journal
            self.journal.record("stat", path, {"success": True})
            return result
        except Exception as e:
            self.journal.record("stat", path, {"success": False, "error": str(e)})
            raise

    def vfs_list(self, path: str) -> Dict:
        """List the contents of a directory in the virtual filesystem"""
        try:
            result = self.vfs.list(path)
            # Record in journal
            self.journal.record("list", path, {"success": True})
            return result
        except Exception as e:
            self.journal.record("list", path, {"success": False, "error": str(e)})
            raise

    def vfs_rm(self, path: str) -> Dict:
        """Remove a file or directory from the virtual filesystem"""
        try:
            result = self.vfs.rm(path)
            # Record in journal
            self.journal.record("rm", path, {"success": True})
            return result
        except Exception as e:
            self.journal.record("rm", path, {"success": False, "error": str(e)})
            raise

    # IPFS-VFS bridge tools
    def ipfs_fs_export_to_ipfs(self, path: str) -> Dict:
        """Export a file from the virtual filesystem to IPFS"""
        result = self.bridge.export_to_ipfs(path)
        # Record in journal
        self.journal.record("export_to_ipfs", path, {
            "success": result["success"],
            "cid": result.get("cid")
        })
        return result

    def ipfs_fs_import_from_ipfs(self, cid: str, path: str) -> Dict:
        """Import content from IPFS to the virtual filesystem"""
        result = self.bridge.import_from_ipfs(cid, path)
        # Record in journal
        self.journal.record("import_from_ipfs", path, {
            "success": result["success"],
            "cid": cid
        })
        return result

    def ipfs_fs_bridge_status(self) -> Dict:
        """Get the status of the IPFS-VFS bridge"""
        return self.bridge.status()

    def ipfs_fs_bridge_list_mappings(self) -> Dict:
        """List all mappings between VFS paths and IPFS CIDs"""
        return self.bridge.list_mappings()

    # Filesystem journal tools
    def fs_journal_record(self, operation: str, path: str, details: Dict = None) -> Dict:
        """Record an operation in the filesystem journal"""
        return self.journal.record(operation, path, details)

    def fs_journal_get_history(self, limit: int = None) -> Dict:
        """Get the operation history from the filesystem journal"""
        return self.journal.get_history(limit)

    def fs_journal_status(self) -> Dict:
        """Get the status of the filesystem journal"""
        return self.journal.status()

    def fs_journal_clear(self) -> Dict:
        """Clear the filesystem journal"""
        return self.journal.clear()

# ===== JSON-RPC Handler =====
async def jsonrpc_handler(request):
    """Handle JSON-RPC requests"""
    try:
        # Parse the JSON-RPC request
        data = await request.json()

        # Validate the request
        if "jsonrpc" not in data or data["jsonrpc"] != "2.0" or "method" not in data:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": data.get("id", None)
            })

        # Extract the request parameters
        method = data["method"]
        params = data.get("params", {})
        request_id = data.get("id", None)

        # Handle the request
        if method == "use_tool":
            result = server.use_tool(params)

            # Check for error
            if "error" in result:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": result["error"]},
                    "id": request_id
                })

            return JSONResponse({
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            })
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            })

    except Exception as e:
        logger.error(f"JSON-RPC handler error: {str(e)}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            "id": None
        })

# ===== HTTP Routes =====
async def health_handler(request):
    """Health endpoint"""
    return JSONResponse({
        "status": "ok",
        "name": SERVER_NAME,
        "version": SERVER_VERSION,
        "uptime": time.time() - SERVER_START_TIME
    })

async def initialize_handler(request):
    """Initialize endpoint for VSCode integration"""
    return JSONResponse({
        "mcp_server_info": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "url": str(request.url).replace("initialize", "jsonrpc")
        },
        "tools": server.get_tools_info()
    })

async def tools_handler(request):
    """List available tools"""
    return JSONResponse(server.get_tools_info())

# ===== Server Initialization =====
# Create the server instance
server = MCPServer()

# Create the Starlette application
app = Starlette(
    debug=False,
    routes=[
        Route("/jsonrpc", jsonrpc_handler, methods=["POST"]),
        Route("/health", health_handler, methods=["GET"]),
        Route("/initialize", initialize_handler, methods=["GET"]),
        Route("/tools", tools_handler, methods=["GET"])
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )
    ]
)

# ===== Main Function =====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Start the {SERVER_NAME}")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")

    args = parser.parse_args()

    logger.info(f"Starting {SERVER_NAME} v{SERVER_VERSION}")
    logger.info(f"Server URL: http://{args.host}:{args.port}/")
    logger.info(f"JSON-RPC URL: http://{args.host}:{args.port}/jsonrpc")
    logger.info(f"Health URL: http://{args.host}:{args.port}/health")
    logger.info(f"Initialize URL: http://{args.host}:{args.port}/initialize")
    logger.info(f"Available tools: {len(server.tools)}")

    # Start the server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info" if not args.debug else "debug",
        reload=args.reload
    )
