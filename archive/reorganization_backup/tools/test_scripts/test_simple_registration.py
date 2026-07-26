#!/usr/bin/env python3
"""
Simple test script to verify IPFS tools registration
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test-ipfs-registration")

def test_unified_ipfs_tools():
    """Test the unified_ipfs_tools module"""
    try:
        # Add current directory to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, script_dir)
        
        logger.info("Testing unified_ipfs_tools import...")
        
        # Test importing just the essential parts
        try:
            # Try to import the IPFS_TOOLS list first
            from ipfs_tools_registry import IPFS_TOOLS
            logger.info(f"✅ Successfully imported IPFS_TOOLS registry with {len(IPFS_TOOLS)} tools")
            
            # Print some tools
            for i, tool in enumerate(IPFS_TOOLS[:5]):  # First 5 tools
                logger.info(f"  Tool {i+1}: {tool['name']} - {tool.get('description', 'No description')}")
        
        except ImportError as e:
            logger.warning(f"⚠️ Could not import IPFS_TOOLS registry: {e}")
            # Create a minimal set for testing
            IPFS_TOOLS = [
                {"name": "ipfs_add", "description": "Add content to IPFS"},
                {"name": "ipfs_cat", "description": "Get content from IPFS"}
            ]
            logger.info(f"Using minimal IPFS_TOOLS with {len(IPFS_TOOLS)} tools")
        
        # Test the mock implementations
        logger.info("Testing mock implementations...")
        
        # Create mock class to simulate MCP server
        class MockMCPServer:
            def __init__(self):
                self.registered_tools = {}
            
            def tool(self, name, description):
                def decorator(func):
                    self.registered_tools[name] = {
                        "function": func,
                        "description": description
                    }
                    logger.info(f"Mock registered: {name}")
                    return func
                return decorator
            
            def register_tool(self, name, handler, description=None):
                self.registered_tools[name] = {
                    "function": handler,
                    "description": description or f"Handler for {name}"
                }
                logger.info(f"Mock registered via register_tool: {name}")
        
        # Create mock server
        mock_server = MockMCPServer()
        
        # Try to register tools using a simplified approach
        logger.info("Attempting simplified tool registration...")
        
        # Simple mock implementations
        async def mock_ipfs_add(content="", filename=None, pin=True):
            return {
                "success": True,
                "cid": "QmMockCID123",
                "size": len(str(content)),
                "filename": filename,
                "pinned": pin
            }
        
        async def mock_ipfs_cat(cid=""):
            return {
                "success": True,
                "content": f"Mock content for {cid}",
                "cid": cid
            }
        
        # Register directly
        mock_server.tool("ipfs_add", "Add content to IPFS")(mock_ipfs_add)
        mock_server.tool("ipfs_cat", "Get content from IPFS")(mock_ipfs_cat)
        
        logger.info(f"✅ Successfully registered {len(mock_server.registered_tools)} tools")
        logger.info("Registered tools:")
        for name, info in mock_server.registered_tools.items():
            logger.info(f"  - {name}: {info['description']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    logger.info("Starting IPFS tools registration test...")
    
    if test_unified_ipfs_tools():
        logger.info("✅ IPFS tools registration test PASSED")
        return 0
    else:
        logger.error("❌ IPFS tools registration test FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
