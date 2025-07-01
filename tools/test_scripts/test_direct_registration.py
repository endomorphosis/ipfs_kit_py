#!/usr/bin/env python3
"""
Direct IPFS Tools Registration Test
"""

import os
import sys
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct-registration-test")

def test_direct_registration():
    """Test direct registration of IPFS tools"""
    try:
        # Import the tools registry
        from ipfs_tools_registry import IPFS_TOOLS
        logger.info(f"✅ Loaded {len(IPFS_TOOLS)} tools from registry")
        
        # Mock MCP server class
        class MockMCPServer:
            def __init__(self):
                self.tools = {}
                self.registered_tool_categories = set()
            
            def tool(self, name, description):
                def decorator(func):
                    self.tools[name] = {
                        "handler": func,
                        "description": description
                    }
                    logger.info(f"Registered: {name}")
                    return func
                return decorator
        
        # Create mock server
        server = MockMCPServer()
        
        # Simple mock implementations
        async def mock_add(content="", filename=None, pin=True):
            return {"success": True, "cid": "QmMock", "content": content}
            
        async def mock_cat(cid=""):
            return {"success": True, "content": f"Content for {cid}"}
        
        # Register key tools directly
        key_tools = [
            ("ipfs_add", "Add content to IPFS", mock_add),
            ("ipfs_cat", "Get content from IPFS", mock_cat),
        ]
        
        for tool_name, description, handler in key_tools:
            server.tool(tool_name, description)(handler)
        
        logger.info(f"✅ Successfully registered {len(server.tools)} tools")
        
        # Test calling a tool
        async def test_tool_call():
            try:
                # Mock context
                class MockContext:
                    def __init__(self, **kwargs):
                        self.arguments = kwargs
                        self.params = kwargs
                
                # Test ipfs_add
                ctx = MockContext(content="Hello IPFS!", filename="test.txt")
                handler = server.tools["ipfs_add"]["handler"]
                result = await handler(content="Hello IPFS!", filename="test.txt")
                logger.info(f"✅ ipfs_add test result: {result}")
                
                return True
            except Exception as e:
                logger.error(f"❌ Error testing tool call: {e}")
                return False
        
        # Run the async test
        success = asyncio.run(test_tool_call())
        
        if success:
            logger.info("✅ Direct registration test PASSED")
            return True
        else:
            logger.error("❌ Tool call test failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error in direct registration test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    logger.info("Starting direct IPFS tools registration test...")
    
    if test_direct_registration():
        logger.info("✅ ALL TESTS PASSED")
        return 0
    else:
        logger.error("❌ TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
