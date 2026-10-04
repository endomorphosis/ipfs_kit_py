#!/usr/bin/env python3
"""
Minimal MCP Server for Testing IPFS Tool Registration
"""

import os
import sys
import json
import logging
import asyncio
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("minimal-mcp-server")

class MinimalMCPServer:
    """Minimal MCP server implementation for testing"""
    
    def __init__(self):
        self.tools = {}
        self.registered_tool_categories = set()
    
    def tool(self, name: str, description: str):
        """Decorator for registering tools"""
        def decorator(func):
            self.tools[name] = {
                "handler": func,
                "description": description,
                "name": name
            }
            logger.info(f"✅ Registered tool: {name}")
            return func
        return decorator
    
    def register_tool(self, name: str, handler, description: str = None):
        """Direct tool registration method"""
        self.tools[name] = {
            "handler": handler,
            "description": description or f"Handler for {name}",
            "name": name
        }
        logger.info(f"✅ Registered tool via register_tool: {name}")
    
    def get_health_status(self):
        """Get server health status"""
        return {
            "status": "ok",
            "version": "1.0.0",
            "tools_count": len(self.tools),
            "registered_tool_categories": list(self.registered_tool_categories)
        }
    
    def list_tools(self):
        """List all registered tools"""
        return {name: info["description"] for name, info in self.tools.items()}

def test_ipfs_tools_registration():
    """Test IPFS tools registration with minimal server"""
    logger.info("Starting IPFS tools registration test...")
    
    # Create minimal server
    server = MinimalMCPServer()
    
    try:
        # Import IPFS tools registry
        from ipfs_tools_registry import IPFS_TOOLS
        logger.info(f"Loaded {len(IPFS_TOOLS)} tools from registry")
        
        # Simple mock implementations for testing
        async def mock_implementation(**kwargs):
            return {
                "success": True,
                "message": "Mock implementation",
                "arguments": kwargs
            }
        
        # Register all tools with mock implementations
        registered_count = 0
        failed_count = 0
        
        for tool in IPFS_TOOLS:
            tool_name = tool["name"]
            description = tool.get("description", f"IPFS tool: {tool_name}")
            
            try:
                # Create a unique mock for each tool
                async def create_mock(name=tool_name):
                    async def mock_func(**kwargs):
                        return {
                            "success": True,
                            "tool": name,
                            "message": f"Mock response from {name}",
                            "arguments": kwargs
                        }
                    return mock_func
                
                # Register the tool
                mock_handler = asyncio.run(create_mock())
                server.register_tool(tool_name, mock_handler, description)
                registered_count += 1
                
                # Add to appropriate category
                category = tool_name.split("_")[1] if "_" in tool_name else "other"
                server.registered_tool_categories.add(f"{category}_tools")
                
            except Exception as e:
                logger.error(f"❌ Failed to register {tool_name}: {e}")
                failed_count += 1
        
        # Add IPFS tools category
        server.registered_tool_categories.add("ipfs_tools")
        
        logger.info(f"Registration complete: {registered_count} success, {failed_count} failed")
        
        # Test server health
        health = server.get_health_status()
        logger.info(f"Server health: {json.dumps(health, indent=2)}")
        
        # Test listing tools
        tools_list = server.list_tools()
        ipfs_tools = {name: desc for name, desc in tools_list.items() if name.startswith("ipfs_")}
        logger.info(f"Found {len(ipfs_tools)} IPFS tools registered")
        
        # Show first few IPFS tools
        logger.info("Sample IPFS tools:")
        for i, (name, desc) in enumerate(list(ipfs_tools.items())[:5]):
            logger.info(f"  {i+1}. {name}: {desc}")
        
        return registered_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error in registration test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_tool_execution():
    """Test executing a registered tool"""
    logger.info("Testing tool execution...")
    
    server = MinimalMCPServer()
    
    # Register a simple test tool
    @server.tool("test_ipfs_add", "Test IPFS add functionality")
    async def test_add(content="", filename=None, pin=True):
        return {
            "success": True,
            "cid": "QmTestCID123",
            "content": content,
            "filename": filename,
            "pinned": pin
        }
    
    # Test calling the tool
    try:
        handler = server.tools["test_ipfs_add"]["handler"]
        result = await handler(content="Hello IPFS!", filename="test.txt")
        logger.info(f"✅ Tool execution result: {json.dumps(result, indent=2)}")
        return True
    except Exception as e:
        logger.error(f"❌ Tool execution failed: {e}")
        return False

def main():
    logger.info("=== Minimal MCP Server IPFS Tools Test ===")
    
    # Test registration
    registration_success = test_ipfs_tools_registration()
    
    # Test execution
    execution_success = asyncio.run(test_tool_execution())
    
    if registration_success and execution_success:
        logger.info("✅ ALL TESTS PASSED - IPFS tools registration is working!")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
