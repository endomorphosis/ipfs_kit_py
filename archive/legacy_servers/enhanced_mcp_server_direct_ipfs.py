#!/usr/bin/env python3
"""
Enhanced MCP Server for IPFS Kit - Direct IPFS Integration
==========================================================

This server bypasses the protobuf issues by directly using IPFS commands
and handling daemon management internally.

Key features:
1. Direct IPFS binary execution (no complex dependencies)
2. Automatic daemon startup and management
3. Real IPFS operations instead of mocks
4. Comprehensive error handling
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
import signal
import psutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("enhanced-mcp-ipfs-direct")

# Server metadata
__version__ = "2.3.0"


class DirectIPFSInterface:
    """Direct IPFS interface with daemon management."""
    
    def __init__(self, auto_start_daemon=True):
        self.auto_start_daemon = auto_start_daemon
        self.daemon_process = None
        self.ipfs_available = False
        self.daemon_running = False
        self._check_ipfs_binary()
        
        if self.ipfs_available and self.auto_start_daemon:
            self._ensure_daemon_running()
    
    def _check_ipfs_binary(self):
        """Check if IPFS binary is available."""
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info(f"IPFS binary available: {result.stdout.strip()}")
                self.ipfs_available = True
            else:
                logger.error("IPFS binary not working")
                self.ipfs_available = False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.error(f"IPFS binary not found: {e}")
            self.ipfs_available = False
    
    def _test_daemon_connection(self) -> bool:
        """Test if IPFS daemon is running and accessible."""
        if not self.ipfs_available:
            return False
            
        try:
            result = subprocess.run(['ipfs', 'id'], 
                                  capture_output=True, text=True, timeout=5)
            success = result.returncode == 0
            if success:
                logger.debug("IPFS daemon connection test successful")
            else:
                logger.debug(f"IPFS daemon connection test failed: {result.stderr}")
            return success
        except Exception as e:
            logger.debug(f"IPFS daemon connection test failed: {e}")
            return False
    
    def _init_ipfs_if_needed(self):
        """Initialize IPFS repository if it doesn't exist."""
        try:
            # Check if IPFS is initialized
            result = subprocess.run(['ipfs', 'config', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.info("Initializing IPFS repository...")
                init_result = subprocess.run(['ipfs', 'init'], 
                                           capture_output=True, text=True, timeout=30)
                if init_result.returncode == 0:
                    logger.info("IPFS repository initialized successfully")
                else:
                    logger.error(f"IPFS initialization failed: {init_result.stderr}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Failed to initialize IPFS: {e}")
            return False
    
    def _ensure_daemon_running(self) -> bool:
        """Ensure IPFS daemon is running."""
        logger.info("Ensuring IPFS daemon is running...")
        
        # Check if already running
        if self._test_daemon_connection():
            logger.info("IPFS daemon already running")
            self.daemon_running = True
            return True
        
        if not self.ipfs_available:
            logger.error("IPFS binary not available, cannot start daemon")
            return False
        
        # Initialize IPFS if needed
        if not self._init_ipfs_if_needed():
            logger.error("Failed to initialize IPFS repository")
            return False
        
        # Kill any existing daemon processes
        self._kill_existing_daemons()
        
        # Start daemon
        try:
            logger.info("Starting IPFS daemon...")
            self.daemon_process = subprocess.Popen(
                ['ipfs', 'daemon', '--enable-pubsub-experiment'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait for daemon to start
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(2)
                if self._test_daemon_connection():
                    logger.info(f"IPFS daemon started successfully (attempt {attempt + 1})")
                    self.daemon_running = True
                    return True
                logger.debug(f"Daemon not ready yet, attempt {attempt + 1}/{max_attempts}")
            
            logger.error("IPFS daemon failed to become ready")
            if self.daemon_process:
                self.daemon_process.terminate()
            return False
            
        except Exception as e:
            logger.error(f"Failed to start IPFS daemon: {e}")
            return False
    
    def _kill_existing_daemons(self):
        """Kill any existing IPFS daemon processes."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'ipfs' and proc.info['cmdline'] and 'daemon' in proc.info['cmdline']:
                        logger.info(f"Killing existing IPFS daemon process {proc.info['pid']}")
                        proc.terminate()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
        except Exception as e:
            logger.warning(f"Error killing existing daemons: {e}")
    
    async def run_ipfs_command(self, cmd_args: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run an IPFS command and return the result."""
        if not self.ipfs_available:
            return {"success": False, "error": "IPFS binary not available"}
        
        # Ensure daemon is running for commands that need it
        daemon_commands = ['cat', 'pin', 'ls', 'stat', 'id', 'swarm', 'dht', 'pubsub', 'files']
        needs_daemon = any(cmd in cmd_args for cmd in daemon_commands)
        
        if needs_daemon and not self.daemon_running:
            if not self._ensure_daemon_running():
                return {"success": False, "error": "IPFS daemon not available"}
        
        try:
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
                logger.warning(f"IPFS command failed: {error_text}")
                return {"success": False, "error": error_text}
                
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            logger.error(f"Error running IPFS command: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        """Clean up resources."""
        if self.daemon_process:
            try:
                logger.info("Shutting down IPFS daemon...")
                self.daemon_process.terminate()
                self.daemon_process.wait(timeout=10)
                logger.info("IPFS daemon shut down successfully")
            except Exception as e:
                logger.warning(f"Error shutting down daemon: {e}")
                try:
                    self.daemon_process.kill()
                except:
                    pass


class EnhancedMCPServerDirect:
    """Enhanced MCP Server with direct IPFS integration."""
    
    def __init__(self):
        self.ipfs = DirectIPFSInterface()
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
            "ipfs_unpin": {
                "name": "ipfs_unpin",
                "description": "Remove pins from IPFS content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "cid": {"type": "string", "description": "IPFS CID to unpin"},
                        "recursive": {"type": "boolean", "description": "Recursively unpin", "default": True}
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
                    "properties": {}
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
            "daemon_status": {
                "name": "daemon_status",
                "description": "Check IPFS daemon status and connection",
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
        
        logger.info(f"Registered {len(self.tools)} tools with direct IPFS integration")
    
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
                "name": "enhanced-ipfs-kit-mcp-server-direct",
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
                return await self.ipfs_add_tool(arguments)
            elif tool_name == "ipfs_cat":
                return await self.ipfs_cat_tool(arguments)
            elif tool_name == "ipfs_pin":
                return await self.ipfs_pin_tool(arguments)
            elif tool_name == "ipfs_list_pins":
                return await self.ipfs_list_pins_tool(arguments)
            elif tool_name == "ipfs_unpin":
                return await self.ipfs_unpin_tool(arguments)
            elif tool_name == "ipfs_ls":
                return await self.ipfs_ls_tool(arguments)
            elif tool_name == "ipfs_stat":
                return await self.ipfs_stat_tool(arguments)
            elif tool_name == "ipfs_version":
                return await self.ipfs_version_tool(arguments)
            elif tool_name == "ipfs_id":
                return await self.ipfs_id_tool(arguments)
            elif tool_name == "daemon_status":
                return await self.daemon_status_tool(arguments)
            elif tool_name == "system_health":
                return await self.system_health_tool(arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def ipfs_add_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Add content to IPFS."""
        content = arguments.get("content")
        file_path = arguments.get("file_path")
        
        if content:
            # Create temporary file with content
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(content)
                temp_path = f.name
            
            try:
                result = await self.ipfs.run_ipfs_command(['add', '-Q', temp_path])
                if result["success"]:
                    return {
                        "success": True,
                        "operation": "ipfs_add",
                        "cid": result["data"],
                        "size": len(content)
                    }
                else:
                    return result
            finally:
                os.unlink(temp_path)
        
        elif file_path:
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}
            
            result = await self.ipfs.run_ipfs_command(['add', '-Q', file_path])
            if result["success"]:
                return {
                    "success": True,
                    "operation": "ipfs_add",
                    "cid": result["data"],
                    "file_path": file_path
                }
            else:
                return result
        
        else:
            return {"success": False, "error": "Either content or file_path is required"}
    
    async def ipfs_cat_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve content from IPFS."""
        cid = arguments.get("cid")
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(['cat', cid])
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_cat",
                "cid": cid,
                "data": result["data"]
            }
        else:
            return result
    
    async def ipfs_pin_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Pin content in IPFS."""
        cid = arguments.get("cid")
        recursive = arguments.get("recursive", True)
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ['pin', 'add']
        if recursive:
            cmd_args.append('--recursive')
        cmd_args.append(cid)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_pin",
                "cid": cid,
                "recursive": recursive,
                "pinned": result["data"]
            }
        else:
            return result
    
    async def ipfs_list_pins_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List pinned content."""
        pin_type = arguments.get("type", "all")
        
        cmd_args = ['pin', 'ls']
        if pin_type != "all":
            cmd_args.extend(['--type', pin_type])
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_list_pins",
                "type": pin_type,
                "pins": result["data"]
            }
        else:
            return result
    
    async def ipfs_unpin_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Unpin content from IPFS."""
        cid = arguments.get("cid")
        recursive = arguments.get("recursive", True)
        
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        cmd_args = ['pin', 'rm']
        if recursive:
            cmd_args.append('--recursive')
        cmd_args.append(cid)
        
        result = await self.ipfs.run_ipfs_command(cmd_args)
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_unpin",
                "cid": cid,
                "recursive": recursive,
                "unpinned": result["data"]
            }
        else:
            return result
    
    async def ipfs_ls_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents in IPFS."""
        cid = arguments.get("cid")
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(['ls', cid])
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_ls",
                "cid": cid,
                "contents": result["data"]
            }
        else:
            return result
    
    async def ipfs_stat_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about IPFS objects."""
        cid = arguments.get("cid")
        if not cid:
            return {"success": False, "error": "CID is required"}
        
        result = await self.ipfs.run_ipfs_command(['object', 'stat', cid])
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_stat",
                "cid": cid,
                "stats": result["data"]
            }
        else:
            return result
    
    async def ipfs_version_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get IPFS version information."""
        result = await self.ipfs.run_ipfs_command(['version', '--all'])
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_version",
                "version_info": result["data"]
            }
        else:
            return result
    
    async def ipfs_id_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get IPFS node identity."""
        result = await self.ipfs.run_ipfs_command(['id'])
        if result["success"]:
            return {
                "success": True,
                "operation": "ipfs_id",
                "node_info": result["data"]
            }
        else:
            return result
    
    async def daemon_status_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Check daemon status."""
        connection_test = self.ipfs._test_daemon_connection()
        
        return {
            "success": True,
            "operation": "daemon_status",
            "daemon_running": connection_test,
            "ipfs_available": self.ipfs.ipfs_available,
            "daemon_process_active": self.ipfs.daemon_process is not None and self.ipfs.daemon_process.poll() is None
        }
    
    async def system_health_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get system health including IPFS daemon status."""
        # Get basic system info
        health_info = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "system": {},
            "ipfs": {
                "binary_available": self.ipfs.ipfs_available,
                "daemon_running": self.ipfs._test_daemon_connection(),
                "daemon_process_active": self.ipfs.daemon_process is not None and self.ipfs.daemon_process.poll() is None
            }
        }
        
        # Add system info if psutil is available
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            health_info["system"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": {
                    "total": disk_usage.total,
                    "used": disk_usage.used,
                    "free": disk_usage.free
                }
            }
        except ImportError:
            health_info["system"]["note"] = "psutil not available for detailed system info"
        
        return health_info
    
    def cleanup(self):
        """Clean up resources."""
        if self.ipfs:
            self.ipfs.cleanup()


# MCP Server main loop
async def main():
    """Main MCP server loop."""
    server = EnhancedMCPServerDirect()
    
    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        server.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        message = None
        while True:
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
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
                
                # Send error response if we have a message ID
                msg_id = None
                if message and isinstance(message, dict):
                    msg_id = message.get("id")
                
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


async def handle_message(server: EnhancedMCPServerDirect, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
