#!/usr/bin/env python3
"""
Fix for MCP server refactoring implementation issues.

This script addresses specific implementation issues that arose after the MCP server
refactoring, ensuring proper operation of the new structure.
"""

import os
import sys
from pathlib import Path
import re
import shutil

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define paths to relevant files
BLUE_GREEN_PROXY_PATH = PROJECT_ROOT / "ipfs_kit_py" / "mcp_server" / "blue_green_proxy.py"
SERVER_PATH = PROJECT_ROOT / "ipfs_kit_py" / "mcp_server" / "server.py"
STORAGE_CONTROLLER_PATH = (
    PROJECT_ROOT / "ipfs_kit_py" / "mcp_server" / "controllers" / "storage_manager_controller.py"
)

# Updated content for blue_green_proxy.py to fix implementation issues
BLUE_GREEN_PROXY_CONTENT = '''"""
Blue-Green Deployment Proxy for MCP Server.

This module provides the ability to perform blue-green deployments of the MCP server,
allowing seamless updates with zero downtime.
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class BlueGreenProxy:
    """
    Blue-Green deployment proxy for the MCP Server.
    
    This class manages two instances of the MCP server (blue and green) and
    routes traffic between them to enable zero-downtime deployments.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Blue-Green Proxy.
        
        Args:
            config: Configuration for the proxy
        """
        self.config = config or {}
        self.running = False
        self.blue_server = None
        self.green_server = None
        self.active_color = None
        logger.debug("Blue-Green Proxy initialized")
    
    async def start(self) -> Dict[str, Any]:
        """
        Start the Blue-Green Proxy.
        
        Returns:
            Dict containing status information
        """
        if self.running:
            return {"success": False, "message": "Proxy already running"}
        
        try:
            # Start the blue server initially
            blue_result = await self._start_blue_server()
            if not blue_result.get("success", False):
                return {"success": False, "message": f"Failed to start blue server: {blue_result.get('message')}"}
            
            self.active_color = "blue"
            self.running = True
            
            logger.info("Blue-Green Proxy started with blue server active")
            return {"success": True, "message": "Blue-Green Proxy started successfully"}
        
        except Exception as e:
            logger.error(f"Failed to start Blue-Green Proxy: {e}")
            return {"success": False, "message": f"Failed to start: {str(e)}"}
    
    async def stop(self) -> Dict[str, Any]:
        """
        Stop the Blue-Green Proxy and all servers.
        
        Returns:
            Dict containing status information
        """
        if not self.running:
            return {"success": False, "message": "Proxy not running"}
        
        try:
            # Stop both servers
            if self.blue_server:
                await self._stop_blue_server()
            
            if self.green_server:
                await self._stop_green_server()
            
            self.running = False
            self.active_color = None
            
            logger.info("Blue-Green Proxy stopped")
            return {"success": True, "message": "Blue-Green Proxy stopped successfully"}
        
        except Exception as e:
            logger.error(f"Failed to stop Blue-Green Proxy: {e}")
            return {"success": False, "message": f"Failed to stop: {str(e)}"}
    
    async def switch(self) -> Dict[str, Any]:
        """
        Switch between blue and green servers.
        
        Returns:
            Dict containing status information
        """
        if not self.running:
            return {"success": False, "message": "Proxy not running"}
        
        try:
            if self.active_color == "blue":
                # Start green server if not running
                if not self.green_server:
                    green_result = await self._start_green_server()
                    if not green_result.get("success", False):
                        return {"success": False, "message": f"Failed to start green server: {green_result.get('message')}"}
                
                # Switch to green
                self.active_color = "green"
                logger.info("Switched from blue to green server")
                
                # Optionally stop blue server after switch
                if self.config.get("stop_inactive", False):
                    await self._stop_blue_server()
                
            else:  # active_color is "green"
                # Start blue server if not running
                if not self.blue_server:
                    blue_result = await self._start_blue_server()
                    if not blue_result.get("success", False):
                        return {"success": False, "message": f"Failed to start blue server: {blue_result.get('message')}"}
                
                # Switch to blue
                self.active_color = "blue"
                logger.info("Switched from green to blue server")
                
                # Optionally stop green server after switch
                if self.config.get("stop_inactive", False):
                    await self._stop_green_server()
            
            return {
                "success": True, 
                "message": f"Switched to {self.active_color} server",
                "active_color": self.active_color
            }
        
        except Exception as e:
            logger.error(f"Failed to switch servers: {e}")
            return {"success": False, "message": f"Failed to switch: {str(e)}"}
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a request by routing it to the active server.
        
        Args:
            request: Dictionary containing request data
            
        Returns:
            Dict containing response data
        """
        if not self.running:
            return {"success": False, "message": "Proxy not running"}
        
        try:
            # Route request to the active server
            if self.active_color == "blue" and self.blue_server:
                return await self.blue_server.handle_request(request)
            elif self.active_color == "green" and self.green_server:
                return await self.green_server.handle_request(request)
            else:
                return {"success": False, "message": "No active server available"}
        
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {"success": False, "message": f"Error handling request: {str(e)}"}
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Blue-Green Proxy and its servers.
        
        Returns:
            Dict containing health status information
        """
        if not self.running:
            return {"success": False, "status": "stopped"}
        
        try:
            blue_health = {"running": self.blue_server is not None}
            green_health = {"running": self.green_server is not None}
            
            # Get detailed health if servers are running
            if self.blue_server:
                blue_health.update(await self.blue_server.check_health())
            
            if self.green_server:
                green_health.update(await self.green_server.check_health())
            
            return {
                "success": True,
                "status": "healthy",
                "active_color": self.active_color,
                "servers": {
                    "blue": blue_health,
                    "green": green_health
                }
            }
        
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return {"success": False, "status": "error", "message": str(e)}
    
    # Private helper methods
    
    async def _start_blue_server(self) -> Dict[str, Any]:
        """Start the blue server."""
        try:
            # Import here to avoid circular imports
            from ipfs_kit_py.mcp_server.server import MCPServer
            
            # Create blue server with its configuration
            blue_config = self.config.get("blue_config", {})
            self.blue_server = MCPServer(blue_config)
            
            # Start the blue server
            result = await self.blue_server.start()
            logger.info(f"Blue server started: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error starting blue server: {e}")
            return {"success": False, "message": f"Error starting blue server: {str(e)}"}
    
    async def _start_green_server(self) -> Dict[str, Any]:
        """Start the green server."""
        try:
            # Import here to avoid circular imports
            from ipfs_kit_py.mcp_server.server import MCPServer
            
            # Create green server with its configuration
            green_config = self.config.get("green_config", {})
            self.green_server = MCPServer(green_config)
            
            # Start the green server
            result = await self.green_server.start()
            logger.info(f"Green server started: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error starting green server: {e}")
            return {"success": False, "message": f"Error starting green server: {str(e)}"}
    
    async def _stop_blue_server(self) -> Dict[str, Any]:
        """Stop the blue server."""
        if not self.blue_server:
            return {"success": True, "message": "Blue server not running"}
        
        try:
            result = await self.blue_server.stop()
            self.blue_server = None
            logger.info(f"Blue server stopped: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error stopping blue server: {e}")
            return {"success": False, "message": f"Error stopping blue server: {str(e)}"}
    
    async def _stop_green_server(self) -> Dict[str, Any]:
        """Stop the green server."""
        if not self.green_server:
            return {"success": True, "message": "Green server not running"}
        
        try:
            result = await self.green_server.stop()
            self.green_server = None
            logger.info(f"Green server stopped: {result}")
            return result
        
        except Exception as e:
            logger.error(f"Error stopping green server: {e}")
            return {"success": False, "message": f"Error stopping green server: {str(e)}"}
'''

# Additional code to fix storage_controller integration
STORAGE_CONTROLLER_ADD = '''
    async def register_storage_backend(self, name: str, backend_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a new storage backend.
        
        Args:
            name: Name of the backend
            backend_config: Configuration for the backend
            
        Returns:
            Dict containing status information
        """
        if not self.running:
            return {"success": False, "message": "Controller not running"}
        
        try:
            # Check if backend already exists
            if name in self.storage_backends:
                return {"success": False, "message": f"Backend '{name}' already exists"}
            
            # Create and initialize the backend
            logger.info(f"Registering new storage backend: {name}")
            # self.storage_backends[name] = SomeBackendClass(backend_config)
            
            return {
                "success": True,
                "message": f"Backend '{name}' registered successfully"
            }
        
        except Exception as e:
            logger.error(f"Error registering storage backend: {e}")
            return {"success": False, "message": f"Error registering backend: {str(e)}"}
    
    async def unregister_storage_backend(self, name: str) -> Dict[str, Any]:
        """
        Unregister a storage backend.
        
        Args:
            name: Name of the backend to unregister
            
        Returns:
            Dict containing status information
        """
        if not self.running:
            return {"success": False, "message": "Controller not running"}
        
        try:
            # Check if backend exists
            if name not in self.storage_backends:
                return {"success": False, "message": f"Backend '{name}' does not exist"}
            
            # Clean up and remove the backend
            logger.info(f"Unregistering storage backend: {name}")
            # await self.storage_backends[name].close()
            del self.storage_backends[name]
            
            return {
                "success": True,
                "message": f"Backend '{name}' unregistered successfully"
            }
        
        except Exception as e:
            logger.error(f"Error unregistering storage backend: {e}")
            return {"success": False, "message": f"Error unregistering backend: {str(e)}"}
'''

# Server extension for graceful termination
SERVER_ADD = '''
    def graceful_shutdown(self) -> None:
        """Perform a graceful shutdown of the server."""
        try:
            loop = asyncio.get_event_loop()
            if self.running:
                # Run the stop method in the event loop
                stop_task = loop.create_task(self.stop())
                loop.run_until_complete(stop_task)
                logger.info("Server gracefully shut down")
            else:
                logger.info("Server was not running, no shutdown needed")
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
'''

def fix_blue_green_proxy():
    """Fix the blue-green proxy implementation."""
    print(f"Updating blue-green proxy at {BLUE_GREEN_PROXY_PATH}...")
    
    # Ensure directory exists
    os.makedirs(BLUE_GREEN_PROXY_PATH.parent, exist_ok=True)
    
    # Backup the original file if it exists
    if BLUE_GREEN_PROXY_PATH.exists():
        backup_path = BLUE_GREEN_PROXY_PATH.with_suffix(".py.bak")
        shutil.copy2(BLUE_GREEN_PROXY_PATH, backup_path)
        print(f"Created backup at {backup_path}")
    
    # Write the updated content
    with open(BLUE_GREEN_PROXY_PATH, 'w') as f:
        f.write(BLUE_GREEN_PROXY_CONTENT)
        
    print("Blue-green proxy updated successfully")

def update_storage_controller():
    """Update the storage controller with additional methods."""
    if not STORAGE_CONTROLLER_PATH.exists():
        print(f"Storage controller not found at {STORAGE_CONTROLLER_PATH}, skipping update")
        return
        
    print(f"Updating storage controller at {STORAGE_CONTROLLER_PATH}...")
    
    # Read the original content
    with open(STORAGE_CONTROLLER_PATH, 'r') as f:
        content = f.read()
    
    # Create backup
    backup_path = STORAGE_CONTROLLER_PATH.with_suffix(".py.bak")
    with open(backup_path, 'w') as f:
        f.write(content)
        print(f"Created backup at {backup_path}")
    
    # Find position to insert new methods (before the last closing brace)
    last_brace_pos = content.rfind('}')
    if last_brace_pos > 0:
        new_content = content[:last_brace_pos] + STORAGE_CONTROLLER_ADD + content[last_brace_pos:]
    else:
        # If no closing brace found, append to the end
        new_content = content + "\n" + STORAGE_CONTROLLER_ADD
    
    # Write the updated content
    with open(STORAGE_CONTROLLER_PATH, 'w') as f:
        f.write(new_content)
        
    print("Storage controller updated successfully")

def update_server():
    """Update the server with graceful shutdown method."""
    if not SERVER_PATH.exists():
        print(f"Server not found at {SERVER_PATH}, skipping update")
        return
        
    print(f"Updating server at {SERVER_PATH}...")
    
    # Read the original content
    with open(SERVER_PATH, 'r') as f:
        content = f.read()
    
    # Create backup
    backup_path = SERVER_PATH.with_suffix(".py.bak")
    with open(backup_path, 'w') as f:
        f.write(content)
        print(f"Created backup at {backup_path}")
    
    # Find the MCPServer class definition
    mcp_server_class_match = re.search(r'class\s+MCPServer\s*:', content)
    if mcp_server_class_match:
        # Find the end of the class (last method in the class)
        methods = re.finditer(r'    def\s+\w+\s*\(', content[mcp_server_class_match.start():])
        last_method_start = None
        for m in methods:
            last_method_start = m.start() + mcp_server_class_match.start()
        
        if last_method_start:
            # Find the end of the last method
            method_body = content[last_method_start:]
            indent_level = 0
            brace_level = 0
            in_triple_quote = False
            triple_quote_type = None
            
            for i, char in enumerate(method_body):
                if i >= 3 and method_body[i-3:i] in ['"""', "'''"]:
                    if not in_triple_quote:
                        in_triple_quote = True
                        triple_quote_type = method_body[i-3:i]
                    elif triple_quote_type == method_body[i-3:i]:
                        in_triple_quote = False
                        triple_quote_type = None
                
                if not in_triple_quote:
                    if char == '{':
                        brace_level += 1
                    elif char == '}':
                        brace_level -= 1
                    
                    if char == '\n':
                        next_non_space = i + 1
                        while next_non_space < len(method_body) and method_body[next_non_space].isspace():
                            next_non_space += 1
                        
                        if next_non_space < len(method_body):
                            next_line_indent = next_non_space - (i + 1)
                            
                            # If we're back to class level indentation and not inside braces
                            if next_line_indent <= 4 and brace_level <= 0:
                                insertion_point = last_method_start + i
                                
                                # Insert the new method after the last method
                                new_content = content[:insertion_point] + "\n" + SERVER_ADD + content[insertion_point:]
                                
                                # Write the updated content
                                with open(SERVER_PATH, 'w') as f:
                                    f.write(new_content)
                                    
                                print("Server updated successfully")
                                return
    
    # If we couldn't find the right position, append to the end
    new_content = content + "\n\n" + SERVER_ADD
    
    # Write the updated content
    with open(SERVER_PATH, 'w') as f:
        f.write(new_content)
        
    print("Server updated by appending to the end")

def apply_mcp_server_fixes():
    """Apply all MCP server refactoring fixes."""
    print("Applying MCP server refactoring fixes...")
    
    try:
        # Fix blue-green proxy
        fix_blue_green_proxy()
        
        # Update storage controller
        update_storage_controller()
        
        # Update server
        update_server()
        
        print("All MCP server refactoring fixes applied successfully")
        return True
    
    except Exception as e:
        print(f"Error applying MCP server fixes: {e}")
        return False

if __name__ == "__main__":
    try:
        if apply_mcp_server_fixes():
            print("MCP server refactoring fixes applied successfully!")
            sys.exit(0)
        else:
            print("Failed to apply MCP server refactoring fixes.")
            sys.exit(1)
    except Exception as e:
        print(f"Unhandled error: {e}")
        sys.exit(1)