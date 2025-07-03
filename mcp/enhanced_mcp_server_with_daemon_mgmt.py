#!/usr/bin/env python3
"""
Enhanced MCP Server for IPFS Kit - With Daemon Management
=========================================================

This server integrates directly with the IPFS Kit Python library,
ensuring proper daemon setup and using real IPFS operations instead of mocks.

Key improvements:
1. Uses the actual IPFSKit class from the project
2. Automatically handles daemon startup and initialization
3. Falls back to mocks only when absolutely necessary
4. Comprehensive error handling and daemon management
"""

import sys
import json
import asyncio
import logging
import traceback
import os
import time
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("enhanced-mcp-ipfs-kit-daemon-mgmt")

# Server metadata
__version__ = "2.2.0"

# Add the project root to Python path to import ipfs_kit_py
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class IPFSKitIntegration:
    """Integration layer for the IPFS Kit with daemon management."""
    
    def __init__(self, auto_start_daemon=True):
        self.auto_start_daemon = auto_start_daemon
        self.ipfs_kit = None
        self.daemon_process = None
        self.use_mock_fallback = False
        self._initialize_ipfs_kit()
    
    def _initialize_ipfs_kit(self):
        """Initialize the IPFS Kit, handling import issues gracefully."""
        try:
            # Try to import and initialize IPFS Kit
            from ipfs_kit_py.ipfs_kit import IPFSKit
            
            # Initialize with auto daemon startup enabled
            self.ipfs_kit = IPFSKit(metadata={
                "role": "master",
                "auto_start_daemons": True,
                "ipfs_path": os.path.expanduser("~/.ipfs")
            })
            
            logger.info("Successfully initialized IPFS Kit")
            
            # Test basic functionality
            if self._test_ipfs_connection():
                logger.info("IPFS daemon is accessible")
                self.use_mock_fallback = False
            else:
                logger.warning("IPFS daemon not accessible, attempting to start")
                if self.auto_start_daemon:
                    self._ensure_daemon_running()
                else:
                    self.use_mock_fallback = True
                    
        except Exception as e:
            error_msg = str(e)
            if "Protobuf" in error_msg and "version" in error_msg:
                logger.error(f"Protobuf version mismatch detected: {e}")
                logger.info("This is a known issue that doesn't affect core IPFS functionality")
                logger.info("Attempting to use direct IPFS commands instead...")
                
                # Try direct IPFS approach without IPFSKit
                if self._test_direct_ipfs():
                    logger.info("Direct IPFS commands working, using fallback implementation")
                    self.use_mock_fallback = False
                    self.ipfs_kit = None  # Use direct commands
                else:
                    logger.warning("Direct IPFS also unavailable, falling back to mock implementations")
                    self.use_mock_fallback = True
                    self.ipfs_kit = None
            else:
                logger.error(f"Failed to initialize IPFS Kit: {e}")
                logger.warning("Falling back to mock implementations")
                self.use_mock_fallback = True
                self.ipfs_kit = None
    
    def _test_direct_ipfs(self) -> bool:
        """Test if IPFS commands work directly."""
        try:
            result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Direct IPFS test failed: {e}")
            return False
    
    def _test_ipfs_connection(self) -> bool:
        """Test if IPFS daemon is accessible."""
        try:
            if self.ipfs_kit:
                result = self.ipfs_kit.ipfs_id()
                return result.get("success", False)
            return False
        except Exception as e:
            logger.debug(f"IPFS connection test failed: {e}")
            return False
    
    def _ensure_daemon_running(self) -> bool:
        """Ensure IPFS daemon is running."""
        logger.info("Ensuring IPFS daemon is running...")
        
        # First check if daemon is already running
        if self._test_ipfs_connection():
            logger.info("IPFS daemon already running")
            return True
        
        # Try to start daemon using ipfs_kit if available
        if self.ipfs_kit and hasattr(self.ipfs_kit, '_ensure_daemon_running'):
            try:
                result = self.ipfs_kit._ensure_daemon_running("ipfs")
                if result.get("success", False):
                    logger.info("Successfully started IPFS daemon via IPFS Kit")
                    return True
            except Exception as e:
                logger.warning(f"Failed to start daemon via IPFS Kit: {e}")
        
        # Try to start daemon directly
        try:
            # Initialize IPFS if not already done
            self._init_ipfs_if_needed()
            
            # Start daemon in background
            logger.info("Starting IPFS daemon...")
            self.daemon_process = subprocess.Popen(
                ['ipfs', 'daemon', '--enable-pubsub-experiment'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait a bit for daemon to start
            time.sleep(3)
            
            # Test connection
            if self._test_ipfs_connection():
                logger.info("Successfully started IPFS daemon")
                return True
            else:
                logger.error("IPFS daemon started but not accessible")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start IPFS daemon: {e}")
            return False
    
    def _init_ipfs_if_needed(self):
        """Initialize IPFS repository if it doesn't exist."""
        try:
            # Check if IPFS is initialized
            result = subprocess.run(['ipfs', 'config', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.info("Initializing IPFS repository...")
                subprocess.run(['ipfs', 'init'], check=True, timeout=30)
                logger.info("IPFS repository initialized")
        except subprocess.TimeoutExpired:
            logger.warning("IPFS initialization timed out")
        except Exception as e:
            logger.warning(f"Failed to initialize IPFS: {e}")
    
    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute an IPFS operation using the real IPFS Kit, direct commands, or mock fallback."""
        
        if not self.use_mock_fallback:
            if self.ipfs_kit:
                # Use real IPFS Kit
                try:
                    method = getattr(self.ipfs_kit, operation, None)
                    if method:
                        result = method(**kwargs)
                        return result
                    else:
                        return {"success": False, "error": f"Method {operation} not found in IPFS Kit"}
                except Exception as e:
                    logger.error(f"IPFS Kit operation {operation} failed: {e}")
                    # Fall back to direct commands or mock
                    return await self._try_direct_ipfs_operation(operation, **kwargs)
            else:
                # Try direct IPFS commands
                return await self._try_direct_ipfs_operation(operation, **kwargs)
        else:
            # Use mock implementation
            return await self._mock_operation(operation, **kwargs)
    
    async def _try_direct_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Try to execute IPFS operation using direct commands."""
        try:
            if operation == "ipfs_add":
                content = kwargs.get("content")
                file_path = kwargs.get("file_path")
                
                if file_path and os.path.exists(file_path):
                    # Add file directly
                    result = subprocess.run(['ipfs', 'add', file_path], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        # Parse output: "added <hash> <filename>"
                        lines = result.stdout.strip().split('\n')
                        last_line = lines[-1]
                        parts = last_line.split()
                        if len(parts) >= 2 and parts[0] == "added":
                            cid = parts[1]
                            return {
                                "success": True,
                                "operation": operation,
                                "cid": cid,
                                "name": os.path.basename(file_path)
                            }
                elif content:
                    # Add content via stdin
                    result = subprocess.run(['ipfs', 'add', '-Q'], 
                                          input=content, text=True,
                                          capture_output=True, timeout=30)
                    if result.returncode == 0:
                        cid = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "size": len(content)
                        }
                        
            elif operation == "ipfs_cat":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'cat', cid], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result.stdout.decode('utf-8'), # Decode bytes to string
                            "cid": cid
                        }
                        
            elif operation == "ipfs_get":
                cid = kwargs.get("cid")
                output_path = kwargs.get("output_path")
                if cid and output_path:
                    result = subprocess.run(['ipfs', 'get', cid, '-o', output_path],
                                          capture_output=True, text=False, timeout=60) # text=False to get bytes
                    if result.returncode == 0:
                        # Read the content from the output_path to return it as a string
                        try:
                            with open(output_path, 'rb') as f:
                                content_bytes = f.read()
                            content_str = content_bytes.decode('utf-8', errors='ignore') # Decode bytes to string
                        except Exception as e:
                            logger.error(f"Failed to read content from {output_path}: {e}")
                            return {
                                "success": False,
                                "operation": operation,
                                "error": f"Failed to read downloaded content: {str(e)}"
                            }
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "output_path": output_path,
                            "message": f"Content {cid} downloaded to {output_path}",
                            "content": content_str # Add content to result
                        }
                    else:
                        logger.error(f"ipfs get failed: {result.stderr.decode('utf-8')}")
                        return {
                            "success": False,
                            "operation": operation,
                            "error": result.stderr.decode('utf-8').strip()
                        }

            elif operation == "ipfs_ls":
                path = kwargs.get("path")
                if path:
                    result = subprocess.run(['ipfs', 'ls', path, '--json'],
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        try:
                            ls_data = json.loads(result.stdout)
                            return {
                                "success": True,
                                "operation": operation,
                                "path": path,
                                "entries": ls_data.get("Objects", [])[0].get("Links", [])
                            }
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse ipfs ls JSON output: {result.stdout}")
                            return {
                                "success": False,
                                "operation": operation,
                                "error": "Failed to parse ipfs ls output"
                            }
                    else:
                        logger.error(f"ipfs ls failed: {result.stderr}")
                        return {
                            "success": False,
                            "operation": operation,
                            "error": result.stderr.strip()
                        }

            elif operation == "ipfs_pin_add":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'pin', 'add', cid], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        return {
                            "success": True,
                            "operation": operation,
                            "pins": [cid]
                        }
                        
            elif operation == "ipfs_pin_ls":
                result = subprocess.run(['ipfs', 'pin', 'ls'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    pins = {}
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                pins[parts[0]] = {"Type": parts[1]}
                    return {
                        "success": True,
                        "operation": operation,
                        "pins": pins
                    }
                    
            elif operation == "ipfs_version":
                result = subprocess.run(['ipfs', 'version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    version_line = result.stdout.strip()
                    # Parse "ipfs version 0.33.1"
                    parts = version_line.split()
                    if len(parts) >= 3:
                        return {
                            "success": True,
                            "operation": operation,
                            "Version": parts[2],
                            "System": "direct-ipfs",
                            "source": "direct_command"
                        }
                        
            elif operation == "ipfs_id":
                result = subprocess.run(['ipfs', 'id'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    id_data = json.loads(result.stdout)
                    id_data["success"] = True
                    id_data["operation"] = operation
                    return id_data
                    
            # If direct command failed, fall back to mock
            logger.warning(f"Direct IPFS command for {operation} failed, using mock")
            return await self._mock_operation(operation, **kwargs)
            
        except Exception as e:
            logger.error(f"Direct IPFS operation {operation} failed: {e}")
            return await self._mock_operation(operation, **kwargs)
    
    async def _mock_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Mock IPFS operations for fallback."""
        logger.debug(f"Using mock implementation for {operation}")
        
        if operation == "ipfs_add":
            content = kwargs.get("content", "mock content")
            file_path = kwargs.get("file_path")
            
            if file_path and os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    content = f.read()
            
            import hashlib
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            cid = f"bafkreie{content_hash[:48]}"
            
            return {
                "success": True,
                "operation": "ipfs_add",
                "cid": cid,
                "size": len(content),
                "name": os.path.basename(file_path) if file_path else "mock_content"
            }
        
        elif operation == "ipfs_cat":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": "ipfs_cat",
                "data": f"Mock content for CID: {cid}\nRetrieved at: {datetime.now().isoformat()}",
                "cid": cid
            }
        
        elif operation == "ipfs_get":
            cid = kwargs.get("cid", "unknown")
            output_path = kwargs.get("output_path", "/tmp/mock_ipfs_get_output.txt")
            
            try:
                mock_content = f"Mock content for CID: {cid}\nDownloaded at: {datetime.now().isoformat()}"
                with open(output_path, "w") as f:
                    f.write(mock_content)
                return {
                    "success": True,
                    "operation": "ipfs_get",
                    "cid": cid,
                    "output_path": output_path,
                    "message": f"Mock content {cid} downloaded to {output_path}",
                    "content": mock_content # Add content to result
                }
            except Exception as e:
                return {
                    "success": False,
                    "operation": "ipfs_get",
                    "error": f"Mock ipfs_get failed: {str(e)}"
                }
        
        elif operation == "ipfs_pin_add":
            cid = kwargs.get("cid", "unknown")
            return {
                "success": True,
                "operation": "ipfs_pin_add",
                "pins": [cid],
                "count": 1
            }
        
        elif operation == "ipfs_pin_ls":
            return {
                "success": True,
                "operation": "ipfs_pin_ls",
                "pins": {
                    "bafkreie1": {"Type": "recursive"},
                    "bafkreie2": {"Type": "direct"}
                }
            }
        
        elif operation == "ipfs_version":
            return {
                "success": True,
                "operation": "ipfs_version",
                "Version": "0.24.0-mock",
                "Commit": "mock-commit",
                "Repo": "15",
                "System": "mock/mock",
                "Golang": "go1.21.0"
            }
        
        elif operation == "ipfs_id":
            return {
                "success": True,
                "operation": "ipfs_id",
                "ID": "12D3KooWMockPeerID",
                "PublicKey": "CAASpmock",
                "Addresses": ["/ip4/127.0.0.1/tcp/4001"],
                "AgentVersion": "go-ipfs/0.24.0/mock",
                "ProtocolVersion": "ipfs/0.1.0"
            }
        
        elif operation == "ipfs_ls_path": # Changed from ipfs_ls to ipfs_ls_path
            path = kwargs.get("path", "/ipfs/mock_cid")
            return {
                "success": True,
                "operation": "ipfs_ls_path",
                "path": path,
                "entries": [
                    {"Name": "file1.txt", "Hash": "bafkreie_mock_file1", "Size": 100},
                    {"Name": "dir1", "Hash": "bafkreie_mock_dir1", "Size": 0}
                ]
            }
        
        else:
            return {
                "success": False,
                "error": f"Mock operation {operation} not implemented",
                "operation": operation
            }
    
    def cleanup(self):
        """Clean up resources."""
        if self.daemon_process:
            try:
                logger.info("Shutting down IPFS daemon...")
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=10)
            except Exception as e:
                logger.warning(f"Error shutting down daemon: {e}")
                try:
                    self.daemon_process.kill()
                except:
                    pass


class EnhancedMCPServerWithDaemonMgmt:
    """Enhanced MCP Server with integrated daemon management."""
    
    def __init__(self):
        self.ipfs_integration = IPFSKitIntegration()
        self.tools = {}
        self.register_tools()
        
    def register_tools(self):
        """Register all available tools."""
        self.tools = {
            # Core IPFS operations
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
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Download IPFS content to a specified path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to retrieve"},
                        "output_path": {"type": "string", "description": "Local path to save the content"}
                    },
                    "required": ["cid", "output_path"]
                }
            },
            "ipfs_ls": {
                "name": "ipfs_ls",
                "description": "List directory contents for an IPFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "IPFS path to list (e.g., /ipfs/<cid>)"}
                    },
                    "required": ["path"]
                }
            },
            "ipfs_pin": {
                "name": "ipfs_pin",
                "description": "Pin content in IPFS to prevent garbage garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to pin"},
                        "recursive": {"type": "boolean", "description": "Pin recursively", "default": True}
                    },
                    "required": ["cid"]
                }
            },
            "ipfs_list_pins": {
                "name": "ipfs_list_pins",
                "description": "List all pinned content in IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["all", "direct", "indirect", "recursive"], "default": "all"}
                    }
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
                    "properties": {}
                }
            },
            "system_health": {
                "name": "system_health",
                "description": "Get comprehensive system health status including IPFS daemon status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
        
        logger.info(f"Registered {len(self.tools)} tools with daemon management")
    
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
                "name": "enhanced-ipfs-kit-mcp-server-daemon-mgmt",
                "version": __version__
            }
        }
    
    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        logger.info("Handling tools/list request")
        return {"tools": list(self.tools.values())}
    
    async def handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/list request."""
        return {"resources": []}
    
    async def handle_resources_templates_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle resources/templates/list request."""
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
            if tool_name == "ipfs_add":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_add", **arguments)
            elif tool_name == "ipfs_cat":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_cat", **arguments)
            elif tool_name == "ipfs_get":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_get", **arguments)
            elif tool_name == "ipfs_ls":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_ls", **arguments)
            elif tool_name == "ipfs_pin":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_add", **arguments)
            elif tool_name == "ipfs_list_pins":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_pin_ls", **arguments)
            elif tool_name == "ipfs_version":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_version", **arguments)
            elif tool_name == "ipfs_id":
                return await self.ipfs_integration.execute_ipfs_operation("ipfs_id", **arguments)
            elif tool_name == "system_health":
                return await self.system_health_tool(arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def system_health_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health including IPFS daemon status."""
        import psutil
        
        # Get basic system info
        health_info = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/')._asdict()
            },
            "ipfs": {
                "daemon_running": False,
                "mock_fallback": self.ipfs_integration.use_mock_fallback,
                "connection_test": False
            }
        }
        
        # Test IPFS connection
        try:
            connection_test = self.ipfs_integration._test_ipfs_connection()
            health_info["ipfs"]["connection_test"] = connection_test
            health_info["ipfs"]["daemon_running"] = connection_test
        except Exception as e:
            health_info["ipfs"]["connection_error"] = str(e)
        
        return health_info
    
    def cleanup(self):
        """Clean up resources."""
        if self.ipfs_integration:
            self.ipfs_integration.cleanup()


# MCP Server main loop
async def main():
    """Main MCP server loop."""
    server = EnhancedMCPServerWithDaemonMgmt()
    
    try:
        while True:
            message = None  # Initialize message to None
            try:
                # Read JSON-RPC message from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                # Parse the message
                try:
                    message = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue
                
                # Handle the message
                response = await handle_message(server, message)
                
                # Send response
                if response is not None:
                    print(json.dumps(response), flush=True)
                    sys.stdout.flush() # Ensure output is flushed immediately
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
                
                # Send error response if we have a message ID
                msg_id = None
                if message and hasattr(message, 'get'): # Check if message is not None before accessing 'get'
                    try:
                        msg_id = message.get("id")
                    except:
                        pass
                    
                error_response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }
                print(json.dumps(error_response), flush=True)
    
    finally:
        server.cleanup()


async def handle_message(server: EnhancedMCPServerWithDaemonMgmt, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle a single MCP message."""
    
    method = message.get("method")
    params = message.get("params", {})
    msg_id = message.get("id")
    
    try:
        # Route to appropriate handler
        if method == "initialize":
            result = await server.handle_initialize(params)
        elif method == "tools/list":
            result = await server.handle_tools_list(params)
        elif method == "resources/list":
            result = await server.handle_resources_list(params)
        elif method == "resources/templates/list":
            result = await server.handle_resources_templates_list(params)
        elif method == "tools/call":
            result = await server.handle_tools_call(params)
        else:
            raise Exception(f"Unknown method: {method}")
        
        # Return success response
        if msg_id is not None:
            return {
                "jsonrpc": "2.0", 
                "id": msg_id,
                "result": result
            }
        else:
            return None
    
    except Exception as e:
        logger.error(f"Error handling {method}: {e}")
        
        # Return error response
        if msg_id is not None:
            return {
                "jsonrpc": "2.0", 
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": str(e),
                    "data": traceback.format_exc()
                }
            }
        else:
            return None


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

</file_content>

Now that you have the latest state of the file, try the operation again with fewer, more precise SEARCH blocks. For large files especially, it may be prudent to try to limit yourself to <5 SEARCH/REPLACE blocks at a time, then wait for the user to respond with the result of the operation before following up with another replace_in_file call to make additional edits.
(If you run into this error 3 times in a row, you may use the write_to_file tool as a fallback.)
</error><environment_details>
# VSCode Visible Files
ipfs_kit_py/install_ipfs.py
ipfs_kit_py/install_ipfs.py
../../../response_1a1cc75c-6040-4dc0-a18a-b544777fddae/tools-12
../../../response_1a1cc75c-6040-4dc0-a18a-b544777fddae/14
../../../response_3276598e-6a8e-424a-b96a-9a6c5c9bd869/tools-0
../../../response_3276598e-6a8e-424a-b96a-9a6c5c9bd869/tools-3
../../../response_3276598e-6a8e-424a-b96a-9a6c5c9bd869/tools-4
../../../response_3276598e-6a8e-424a-b96a-9a6c5c9bd869/tools-5
mcp/enhanced_mcp_server_with_daemon_mgmt.py

# VSCode Open Tabs
../.config/Code/User/settings.json
mcp/enhanced_mcp_server_with_daemon_mgmt.py

# Recently Modified Files
These files have been modified since you last accessed them (file was just edited so you may need to re-read it before editing):
mcp/enhanced_mcp_server_with_daemon_mgmt.py

# Current Time
7/2/2025, 9:47:19 PM (America/Los_Angeles, UTC-7:00)

# Context Window Usage
513,090 / 1,048.576K tokens used (49%)

# Current Mode
ACT MODE
</environment_details>
