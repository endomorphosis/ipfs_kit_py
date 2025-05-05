#!/usr/bin/env python3
"""
Script to create mock modules needed by the MCP server
"""

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('mock-modules')

# Paths to create
PATHS = [
    'ipfs_kit_py/mcp',
    'ipfs_kit_py/mcp/server',
    'mcp',
    'mcp/server',
]

# Files to create
FILES = {
    'ipfs_kit_py/mcp/__init__.py': '',
    'ipfs_kit_py/mcp/server/__init__.py': '',
    'ipfs_kit_py/mcp/server_bridge.py': '''
# Mock implementation of ipfs_kit_py.mcp.server_bridge
import logging

logger = logging.getLogger(__name__)

class ServerBridge:
    def __init__(self, *args, **kwargs):
        logger.info("Initialized mock ServerBridge")
        self.connected = False
        
    async def connect(self, *args, **kwargs):
        logger.info("Mock ServerBridge.connect called")
        self.connected = True
        return True
        
    async def disconnect(self):
        logger.info("Mock ServerBridge.disconnect called")
        self.connected = False
        return True
        
    async def send_request(self, *args, **kwargs):
        logger.info(f"Mock ServerBridge.send_request called with args={args}, kwargs={kwargs}")
        return {"result": "mock_result"}
''',
    'mcp/__init__.py': '',
    'mcp/server/__init__.py': '',
    'mcp/server/fastmcp.py': '''
# Mock implementation of mcp.server.fastmcp
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable

logger = logging.getLogger(__name__)

class FastMCPServer:
    def __init__(self, host="127.0.0.1", port=8765, **kwargs):
        logger.info(f"Initialized mock FastMCPServer on {host}:{port}")
        self.host = host
        self.port = port
        self.tools = {}
        self.running = False
        
    def register_tool(self, name, func, **kwargs):
        logger.info(f"Registered mock tool: {name}")
        self.tools[name] = func
        return True
        
    def register_tools(self, tools_dict):
        for name, func in tools_dict.items():
            self.register_tool(name, func)
        return True
    
    async def start(self):
        logger.info("Starting mock FastMCPServer")
        self.running = True
        while self.running:
            await asyncio.sleep(1)
        
    def stop(self):
        logger.info("Stopping mock FastMCPServer")
        self.running = False
        return True
'''
}

def create_mock_modules():
    """Create mock module files in the current directory"""
    base_dir = os.getcwd()
    
    # Create directories
    for path in PATHS:
        full_path = os.path.join(base_dir, path)
        if not os.path.exists(full_path):
            logger.info(f"Creating directory: {full_path}")
            os.makedirs(full_path, exist_ok=True)
    
    # Create files
    for file_path, content in FILES.items():
        full_path = os.path.join(base_dir, file_path)
        if not os.path.exists(full_path):
            logger.info(f"Creating file: {full_path}")
            with open(full_path, 'w') as f:
                f.write(content.strip())
        else:
            logger.info(f"File already exists: {full_path}")
    
    logger.info("Mock modules created successfully")

if __name__ == "__main__":
    create_mock_modules()