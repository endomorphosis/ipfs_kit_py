"""
MCP tool manager for IPFS Kit.
"""

from typing import List, Dict, Any, Optional
import logging
import traceback
import time
import os

from .backend_tools import BackendTools
from .system_tools import SystemTools
from .vfs_tools import VFSTools

logger = logging.getLogger(__name__)

# Auto-healing integration
_AUTO_HEAL_ENABLED = os.environ.get('IPFS_KIT_AUTO_HEAL', '').lower() in ('true', '1', 'yes')


class SimplifiedMCPTool:
    """Simplified MCP tool representation."""
    
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPToolManager:
    """Manages MCP tools for the IPFS Kit server."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        
        # Initialize tool handlers
        self.backend_tools = BackendTools(backend_monitor)
        self.system_tools = SystemTools(backend_monitor)
        self.vfs_tools = VFSTools(backend_monitor)
        
        # Initialize auto-healing wrapper if enabled
        self.auto_heal_enabled = _AUTO_HEAL_ENABLED
        if self.auto_heal_enabled:
            try:
                from ipfs_kit_py.auto_heal.mcp_tool_wrapper import get_mcp_error_capture
                self.error_capture = get_mcp_error_capture(enable_auto_heal=True)
                logger.info("MCP tool auto-healing enabled")
            except Exception as e:
                logger.warning(f"Could not enable MCP tool auto-healing: {e}")
                self.error_capture = None
                self.auto_heal_enabled = False
        else:
            self.error_capture = None
        
        # Create tool registry
        self.tools = self._create_tools()
    
    def _create_tools(self) -> List[SimplifiedMCPTool]:
        """Create the MCP tools registry."""
        
        tools = []
        
        # System tools
        tools.extend([
            SimplifiedMCPTool(
                name="system_health",
                description="Get comprehensive system health status including all backend monitoring",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_development_insights",
                description="Get insights and recommendations for development based on backend status",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            )
        ])
        
        # Backend tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_backend_status",
                description="Get comprehensive backend status and monitoring data for all filesystem backends",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Specific backend to check (optional)",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    }
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_detailed",
                description="Get detailed information about a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get detailed info for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="restart_backend",
                description="Attempt to restart a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend to restart",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="get_backend_config",
                description="Get configuration for a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get config for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        }
                    },
                    "required": ["backend"]
                }
            ),
            SimplifiedMCPTool(
                name="set_backend_config",
                description="Set configuration for a specific backend",
                input_schema={
                    "type": "object",
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to set config for",
                            "enum": ["ipfs", "ipfs_cluster", "ipfs_cluster_follow", "lotus", "storacha", "synapse", "s3", "huggingface", "parquet"]
                        },
                        "config": {
                            "type": "object",
                            "description": "Configuration object to set"
                        }
                    },
                    "required": ["backend", "config"]
                }
            )
        ])
        
        # VFS tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_vfs_statistics",
                description="Get VFS statistics and metrics",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_cache",
                description="Get VFS cache information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_vector_index",
                description="Get VFS vector index information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="get_vfs_knowledge_base",
                description="Get VFS knowledge base information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            )
        ])
        
        # IPFS tools
        tools.extend([
            SimplifiedMCPTool(
                name="ipfs_add",
                description="Add content to IPFS",
                input_schema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to add to IPFS"},
                        "name": {"type": "string", "description": "Name for the file", "default": "file.txt"}
                    },
                    "required": ["content"]
                }
            ),
            SimplifiedMCPTool(
                name="ipfs_cat",
                description="Retrieve content from IPFS",
                input_schema={
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash to retrieve"}
                    },
                    "required": ["hash"]
                }
            ),
            SimplifiedMCPTool(
                name="ipfs_pin_add",
                description="Pin content to local IPFS node",
                input_schema={
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash to pin"}
                    },
                    "required": ["hash"]
                }
            ),
            SimplifiedMCPTool(
                name="ipfs_pin_ls",
                description="List pinned content",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            ),
            SimplifiedMCPTool(
                name="ipfs_pin_rm",
                description="Unpin content from local IPFS node",
                input_schema={
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash to unpin"}
                    },
                    "required": ["hash"]
                }
            )
        ])
        
        # VFS file operations
        tools.extend([
            SimplifiedMCPTool(
                name="vfs_mkdir",
                description="Create a directory in the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to create"}
                    },
                    "required": ["path"]
                }
            ),
            SimplifiedMCPTool(
                name="vfs_write",
                description="Write content to a file in the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to write to"},
                        "content": {"type": "string", "description": "Content to write"}
                    },
                    "required": ["path", "content"]
                }
            ),
            SimplifiedMCPTool(
                name="vfs_read",
                description="Read content from a file in the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read from"}
                    },
                    "required": ["path"]
                }
            ),
            SimplifiedMCPTool(
                name="vfs_stat",
                description="Get information about a file or directory in the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to get information about"}
                    },
                    "required": ["path"]
                }
            ),
            SimplifiedMCPTool(
                name="vfs_list",
                description="List the contents of a directory in the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path to list"}
                    },
                    "required": ["path"]
                }
            ),
            SimplifiedMCPTool(
                name="vfs_rm",
                description="Remove a file or directory from the virtual filesystem",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to remove"}
                    },
                    "required": ["path"]
                }
            )
        ])
        
        # Utility tools
        tools.extend([
            SimplifiedMCPTool(
                name="utility_ping",
                description="Test server connectivity",
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to ping", "default": "hello"}
                    }
                }
            ),
            SimplifiedMCPTool(
                name="utility_server_info",
                description="Get server information",
                input_schema={
                    "type": "object",
                    "properties": {},
                }
            )
        ])
        
        # Metrics and monitoring tools
        tools.extend([
            SimplifiedMCPTool(
                name="get_metrics_history",
                description="Get historical metrics for backends",
                input_schema={
                    "type": "object", 
                    "properties": {
                        "backend": {
                            "type": "string",
                            "description": "Backend name to get metrics for"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of recent metrics to return",
                            "default": 10
                        }
                    }
                }
            )
        ])
        
        return tools
    
    async def handle_tool_request(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tool requests with auto-healing error capture."""
        
        # If auto-healing is enabled, wrap the execution
        if self.auto_heal_enabled and self.error_capture:
            try:
                return await self._execute_tool(tool_name, arguments)
            except Exception as e:
                # Capture error for auto-healing
                error_info = self.error_capture._capture_tool_error(tool_name, arguments, e)
                logger.error(f"MCP tool '{tool_name}' failed: {e}", exc_info=True)
                
                # Trigger auto-healing in background
                import asyncio
                asyncio.create_task(self.error_capture._trigger_auto_heal(error_info))
                
                # Re-raise the exception
                raise
        else:
            # No auto-healing, execute directly
            return await self._execute_tool(tool_name, arguments)
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual tool logic."""
        
        try:
            # System tools
            if tool_name == "system_health":
                return await self.system_tools.get_system_health()
            
            elif tool_name == "get_development_insights":
                return await self.system_tools.get_development_insights()
            
            # Backend tools
            elif tool_name == "get_backend_status":
                backend = arguments.get("backend")
                return await self.backend_tools.get_backend_status(backend)
            
            elif tool_name == "get_backend_detailed":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.get_backend_detailed(backend)
            
            elif tool_name == "restart_backend":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.restart_backend(backend)
            
            elif tool_name == "get_backend_config":
                backend = arguments.get("backend")
                if not backend:
                    return {"error": "Backend name is required"}
                return await self.backend_tools.get_backend_config(backend)
            
            elif tool_name == "set_backend_config":
                backend = arguments.get("backend")
                config = arguments.get("config")
                if not backend or not config:
                    return {"error": "Backend name and config are required"}
                return await self.backend_tools.set_backend_config(backend, config)
            
            # VFS tools
            elif tool_name == "get_vfs_statistics":
                return await self.vfs_tools.get_vfs_statistics()
            
            elif tool_name == "get_vfs_cache":
                return await self.vfs_tools.get_vfs_cache()
            
            elif tool_name == "get_vfs_vector_index":
                return await self.vfs_tools.get_vfs_vector_index()
            
            elif tool_name == "get_vfs_knowledge_base":
                return await self.vfs_tools.get_vfs_knowledge_base()
            
            # IPFS tools
            elif tool_name == "ipfs_add":
                content = arguments.get("content")
                name = arguments.get("name", "file.txt")
                if not content:
                    return {"error": "Content is required"}
                return await self._handle_ipfs_add(content, name)
            
            elif tool_name == "ipfs_cat":
                hash_val = arguments.get("hash")
                if not hash_val:
                    return {"error": "IPFS hash is required"}
                return await self._handle_ipfs_cat(hash_val)
            
            elif tool_name == "ipfs_pin_add":
                hash_val = arguments.get("hash")
                if not hash_val:
                    return {"error": "IPFS hash is required"}
                return await self._handle_ipfs_pin_add(hash_val)
            
            elif tool_name == "ipfs_pin_ls":
                return await self._handle_ipfs_pin_ls()
            
            elif tool_name == "ipfs_pin_rm":
                hash_val = arguments.get("hash")
                if not hash_val:
                    return {"error": "IPFS hash is required"}
                return await self._handle_ipfs_pin_rm(hash_val)
            
            # VFS file operations
            elif tool_name == "vfs_mkdir":
                path = arguments.get("path")
                if not path:
                    return {"error": "Path is required"}
                return await self._handle_vfs_mkdir(path)
            
            elif tool_name == "vfs_write":
                path = arguments.get("path")
                content = arguments.get("content")
                if not path or not content:
                    return {"error": "Path and content are required"}
                return await self._handle_vfs_write(path, content)
            
            elif tool_name == "vfs_read":
                path = arguments.get("path")
                if not path:
                    return {"error": "Path is required"}
                return await self._handle_vfs_read(path)
            
            elif tool_name == "vfs_stat":
                path = arguments.get("path")
                if not path:
                    return {"error": "Path is required"}
                return await self._handle_vfs_stat(path)
            
            elif tool_name == "vfs_list":
                path = arguments.get("path")
                if not path:
                    return {"error": "Path is required"}
                return await self._handle_vfs_list(path)
            
            elif tool_name == "vfs_rm":
                path = arguments.get("path")
                if not path:
                    return {"error": "Path is required"}
                return await self._handle_vfs_rm(path)
            
            # Utility tools
            elif tool_name == "utility_ping":
                message = arguments.get("message", "hello")
                return await self._handle_utility_ping(message)
            
            elif tool_name == "utility_server_info":
                return await self._handle_utility_server_info()
            
            # Metrics tools
            elif tool_name == "get_metrics_history":
                backend = arguments.get("backend")
                limit = arguments.get("limit", 10)
                return await self.backend_tools.get_metrics_history(backend, limit)
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception:
            # Don't log here - let handle_tool_request handle it with auto-heal
            # This avoids redundant error logging
            raise
    
    def get_tools(self) -> List[SimplifiedMCPTool]:
        """Get all available MCP tools."""
        return self.tools

    # IPFS tool implementations
    async def _handle_ipfs_add(self, content: str, name: str) -> Dict[str, Any]:
        """Handle IPFS add operation."""
        try:
            # Import here to avoid circular imports
            import subprocess
            import json
            
            # Create a temporary file with the content
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{name}', delete=False) as f:
                f.write(content)
                temp_path = f.name
            
            # Add to IPFS
            result = subprocess.run(
                ['ipfs', 'add', '--json', temp_path],
                capture_output=True,
                text=True
            )
            
            # Clean up temp file
            import os
            os.unlink(temp_path)
            
            if result.returncode == 0:
                data = json.loads(result.stdout.strip())
                return {
                    "status": "success",
                    "hash": data.get("Hash"),
                    "size": data.get("Size"),
                    "name": name
                }
            else:
                return {
                    "status": "error",
                    "message": f"IPFS add failed: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to add to IPFS: {str(e)}"
            }

    async def _handle_ipfs_cat(self, hash_val: str) -> Dict[str, Any]:
        """Handle IPFS cat operation."""
        try:
            import subprocess
            
            result = subprocess.run(
                ['ipfs', 'cat', hash_val],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "content": result.stdout,
                    "hash": hash_val
                }
            else:
                return {
                    "status": "error",
                    "message": f"IPFS cat failed: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to retrieve from IPFS: {str(e)}"
            }

    async def _handle_ipfs_pin_add(self, hash_val: str) -> Dict[str, Any]:
        """Handle IPFS pin add operation."""
        try:
            import subprocess
            
            result = subprocess.run(
                ['ipfs', 'pin', 'add', hash_val],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": f"Pinned {hash_val}",
                    "hash": hash_val
                }
            else:
                return {
                    "status": "error",
                    "message": f"IPFS pin add failed: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to pin to IPFS: {str(e)}"
            }

    async def _handle_ipfs_pin_ls(self) -> Dict[str, Any]:
        """Handle IPFS pin list operation."""
        try:
            import subprocess
            
            result = subprocess.run(
                ['ipfs', 'pin', 'ls'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pins = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            pins.append({
                                "hash": parts[0],
                                "type": parts[1]
                            })
                
                return {
                    "status": "success",
                    "pins": pins
                }
            else:
                return {
                    "status": "error",
                    "message": f"IPFS pin ls failed: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to list pins: {str(e)}"
            }

    async def _handle_ipfs_pin_rm(self, hash_val: str) -> Dict[str, Any]:
        """Handle IPFS pin remove operation."""
        try:
            import subprocess
            
            result = subprocess.run(
                ['ipfs', 'pin', 'rm', hash_val],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": f"Unpinned {hash_val}",
                    "hash": hash_val
                }
            else:
                return {
                    "status": "error",
                    "message": f"IPFS pin rm failed: {result.stderr}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to unpin from IPFS: {str(e)}"
            }

    # VFS file operation implementations
    async def _handle_vfs_mkdir(self, path: str) -> Dict[str, Any]:
        """Handle VFS mkdir operation."""
        try:
            import os
            
            # Ensure the VFS directory exists
            vfs_root = "/tmp/vfs"
            if not os.path.exists(vfs_root):
                os.makedirs(vfs_root)
            
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            os.makedirs(full_path, exist_ok=True)
            
            return {
                "status": "success",
                "path": path,
                "full_path": full_path,
                "message": f"Directory created: {path}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create directory: {str(e)}"
            }

    async def _handle_vfs_write(self, path: str, content: str) -> Dict[str, Any]:
        """Handle VFS write operation."""
        try:
            import os
            
            # Ensure the VFS directory exists
            vfs_root = "/tmp/vfs"
            if not os.path.exists(vfs_root):
                os.makedirs(vfs_root)
            
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            
            # Create parent directories if needed
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            # Write content
            with open(full_path, 'w') as f:
                f.write(content)
            
            return {
                "status": "success",
                "path": path,
                "full_path": full_path,
                "size": len(content),
                "message": f"File written: {path}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to write file: {str(e)}"
            }

    async def _handle_vfs_read(self, path: str) -> Dict[str, Any]:
        """Handle VFS read operation."""
        try:
            import os
            
            vfs_root = "/tmp/vfs"
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            
            if not os.path.exists(full_path):
                return {
                    "status": "error",
                    "message": f"File not found: {path}"
                }
            
            with open(full_path, 'r') as f:
                content = f.read()
            
            return {
                "status": "success",
                "path": path,
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read file: {str(e)}"
            }

    async def _handle_vfs_stat(self, path: str) -> Dict[str, Any]:
        """Handle VFS stat operation."""
        try:
            import os
            
            vfs_root = "/tmp/vfs"
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            
            if not os.path.exists(full_path):
                return {
                    "status": "error",
                    "message": f"Path not found: {path}"
                }
            
            stat = os.stat(full_path)
            
            return {
                "status": "success",
                "path": path,
                "size": stat.st_size,
                "is_file": os.path.isfile(full_path),
                "is_dir": os.path.isdir(full_path),
                "modified": stat.st_mtime,
                "created": stat.st_ctime
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to stat path: {str(e)}"
            }

    async def _handle_vfs_list(self, path: str) -> Dict[str, Any]:
        """Handle VFS list operation."""
        try:
            import os
            
            vfs_root = "/tmp/vfs"
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            
            if not os.path.exists(full_path):
                return {
                    "status": "error",
                    "message": f"Directory not found: {path}"
                }
            
            if not os.path.isdir(full_path):
                return {
                    "status": "error",
                    "message": f"Path is not a directory: {path}"
                }
            
            items = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                stat = os.stat(item_path)
                items.append({
                    "name": item,
                    "is_file": os.path.isfile(item_path),
                    "is_dir": os.path.isdir(item_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
            
            return {
                "status": "success",
                "path": path,
                "items": items
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to list directory: {str(e)}"
            }

    async def _handle_vfs_rm(self, path: str) -> Dict[str, Any]:
        """Handle VFS remove operation."""
        try:
            import os
            import shutil
            
            vfs_root = "/tmp/vfs"
            full_path = os.path.join(vfs_root, path.lstrip('/'))
            
            if not os.path.exists(full_path):
                return {
                    "status": "error",
                    "message": f"Path not found: {path}"
                }
            
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
                message = f"Directory removed: {path}"
            else:
                os.remove(full_path)
                message = f"File removed: {path}"
            
            return {
                "status": "success",
                "path": path,
                "message": message
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to remove path: {str(e)}"
            }

    # Utility tool implementations
    async def _handle_utility_ping(self, message: str) -> Dict[str, Any]:
        """Handle utility ping operation."""
        return {
            "status": "success",
            "message": f"Pong: {message}",
            "timestamp": time.time()
        }

    async def _handle_utility_server_info(self) -> Dict[str, Any]:
        """Handle utility server info operation."""
        try:
            import platform
            import psutil
            
            return {
                "status": "success",
                "server_info": {
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "cpu_count": psutil.cpu_count(),
                    "memory_total": psutil.virtual_memory().total,
                    "memory_available": psutil.virtual_memory().available,
                    "disk_usage": {
                        "total": psutil.disk_usage('/').total,
                        "used": psutil.disk_usage('/').used,
                        "free": psutil.disk_usage('/').free
                    },
                    "timestamp": time.time()
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get server info: {str(e)}"
            }
