#!/usr/bin/env python3
"""
Direct test of IPFS functionality without MCP server.
"""
import anyio
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_fixed_ipfs_model():
    """Test the fixed IPFS model directly"""
    try:
        # Add current directory to Python path
        sys.path.insert(0, os.getcwd())
        
        # Import the fixed IPFS model
        from fixed_ipfs_model import IPFSModel
        
        logger.info("✅ Successfully imported IPFSModel")
        
        # Initialize the model
        ipfs_model = IPFSModel()
        logger.info("✅ Successfully initialized IPFSModel")
        
        # Test add_content
        test_content = "Hello from direct IPFS test!"
        logger.info(f"Testing add_content with: {test_content}")
        
        result = await ipfs_model.add_content(test_content)
        logger.info(f"add_content result: {result}")
        
        if result.get("success", False):
            cid = result.get("cid")
            logger.info(f"✅ Content added successfully with CID: {cid}")
            
            # Test cat
            if cid:
                logger.info(f"Testing cat with CID: {cid}")
                cat_result = await ipfs_model.cat(cid)
                logger.info(f"cat result: {cat_result}")
                
                if cat_result.get("success", False):
                    logger.info("✅ Cat operation successful")
                    return True
                else:
                    logger.error("❌ Cat operation failed")
            else:
                logger.error("❌ No CID returned from add_content")
        else:
            logger.error("❌ add_content failed")
            
    except Exception as e:
        logger.error(f"❌ Error testing IPFS model: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    return False

async def test_unified_ipfs_tools():
    """Test the unified IPFS tools"""
    try:
        # Import unified tools
        import unified_ipfs_tools
        
        logger.info("✅ Successfully imported unified_ipfs_tools")
        
        # Check tool status
        logger.info(f"Tool status: {unified_ipfs_tools.TOOL_STATUS}")
        
        # Try to get some tools
        if hasattr(unified_ipfs_tools, 'TOOL_REGISTRY'):
            logger.info(f"Found {len(unified_ipfs_tools.TOOL_REGISTRY)} tools in registry")
            
            # List some tools
            for i, (name, tool) in enumerate(unified_ipfs_tools.TOOL_REGISTRY.items()):
                if i < 5:  # Show first 5 tools
                    logger.info(f"  - {name}: {tool.get('description', 'No description')}")
                    
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing unified IPFS tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    return False

async def test_direct_ipfs_tools():
    """Test the direct IPFS tools registration"""
    try:
        # Import direct tools
        import fixed_direct_ipfs_tools
        
        logger.info("✅ Successfully imported fixed_direct_ipfs_tools")
        
        # Check if real implementations are available
        if hasattr(fixed_direct_ipfs_tools, 'REAL_IMPLEMENTATIONS_AVAILABLE'):
            status = fixed_direct_ipfs_tools.REAL_IMPLEMENTATIONS_AVAILABLE
            logger.info(f"Real implementations available: {status}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Error testing direct IPFS tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting direct IPFS functionality tests...")
    
    results = []
    
    logger.info("\n" + "="*50)
    logger.info("1. Testing Fixed IPFS Model")
    logger.info("="*50)
    results.append(await test_fixed_ipfs_model())
    
    logger.info("\n" + "="*50)
    logger.info("2. Testing Unified IPFS Tools")
    logger.info("="*50)
    results.append(await test_unified_ipfs_tools())
    
    logger.info("\n" + "="*50)
    logger.info("3. Testing Direct IPFS Tools")
    logger.info("="*50)
    results.append(await test_direct_ipfs_tools())
    
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    
    test_names = ["Fixed IPFS Model", "Unified IPFS Tools", "Direct IPFS Tools"]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{i+1}. {name}: {status}")
    
    overall_success = all(results)
    if overall_success:
        logger.info("🎉 All tests passed!")
    else:
        logger.info("⚠️ Some tests failed.")
    
    return overall_success

if __name__ == "__main__":
    success = anyio.run(main)
    sys.exit(0 if success else 1)
