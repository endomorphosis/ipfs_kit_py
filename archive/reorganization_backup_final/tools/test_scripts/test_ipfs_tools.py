#!/usr/bin/env python3
"""
Test script for IPFS MCP tools with the real implementation.
"""
import anyio
import json
import aiohttp
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IPFSToolsTester:
    def __init__(self, server_url="http://localhost:8002"):
        self.server_url = server_url
        self.jsonrpc_url = f"{server_url}/jsonrpc"
        
    async def call_tool(self, tool_name, **kwargs):
        """Call an MCP tool via JSON-RPC"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": kwargs
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.jsonrpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    result = await response.json()
                    
                    if "error" in result:
                        logger.error(f"Tool {tool_name} error: {result['error']}")
                        return None
                    
                    return result.get("result")
                    
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return None
    
    async def test_ipfs_add(self):
        """Test adding content to IPFS"""
        logger.info("Testing IPFS add...")
        test_content = "Hello from MCP IPFS test!"
        
        result = await self.call_tool("ipfs_add", content=test_content)
        
        if result and "content" in result:
            logger.info(f"✅ IPFS add successful: {result['content']}")
            # Extract hash from result
            if "Hash" in result["content"]:
                return result["content"]["Hash"]
        else:
            logger.error(f"❌ IPFS add failed: {result}")
        
        return None
    
    async def test_ipfs_cat(self, ipfs_hash):
        """Test reading content from IPFS"""
        if not ipfs_hash:
            logger.warning("No hash provided for cat test")
            return False
            
        logger.info(f"Testing IPFS cat with hash: {ipfs_hash}")
        
        result = await self.call_tool("ipfs_cat", hash=ipfs_hash)
        
        if result and "content" in result:
            logger.info(f"✅ IPFS cat successful: {result['content'][:100]}...")
            return True
        else:
            logger.error(f"❌ IPFS cat failed: {result}")
            return False
    
    async def test_ipfs_pin_add(self, ipfs_hash):
        """Test pinning content in IPFS"""
        if not ipfs_hash:
            logger.warning("No hash provided for pin test")
            return False
            
        logger.info(f"Testing IPFS pin add with hash: {ipfs_hash}")
        
        result = await self.call_tool("ipfs_pin_add", hash=ipfs_hash)
        
        if result and "content" in result:
            logger.info(f"✅ IPFS pin add successful: {result['content']}")
            return True
        else:
            logger.error(f"❌ IPFS pin add failed: {result}")
            return False
    
    async def test_ipfs_pin_ls(self):
        """Test listing pinned content"""
        logger.info("Testing IPFS pin ls...")
        
        result = await self.call_tool("ipfs_pin_ls")
        
        if result and "content" in result:
            logger.info(f"✅ IPFS pin ls successful: Found {len(result['content'])} pinned items")
            return True
        else:
            logger.error(f"❌ IPFS pin ls failed: {result}")
            return False
    
    async def run_all_tests(self):
        """Run all IPFS tests"""
        logger.info("🚀 Starting IPFS MCP tools test suite...")
        
        # Test 1: Add content
        ipfs_hash = await self.test_ipfs_add()
        
        # Test 2: Read content back
        if ipfs_hash:
            await self.test_ipfs_cat(ipfs_hash)
            await self.test_ipfs_pin_add(ipfs_hash)
        
        # Test 3: List pins
        await self.test_ipfs_pin_ls()
        
        logger.info("🏁 IPFS MCP tools test suite completed!")

async def main():
    tester = IPFSToolsTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    anyio.run(main)
