#!/usr/bin/env python3
"""
MCP Server VFS Test
===================

Test VFS functionality through the MCP server with a direct server call.
"""

import os
import sys
import json
import asyncio
import logging

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-vfs-test")

async def test_mcp_vfs_operations():
    """Test VFS operations through the MCP server."""
    logger.info("🧪 Testing VFS operations through MCP server")
    
    try:
        # Import the MCP server
        from mcp.enhanced_mcp_server_with_daemon_mgmt import IPFSKitIntegration
        
        # Create integration instance
        integration = IPFSKitIntegration()
        logger.info("✅ IPFSKitIntegration created successfully")
        
        # Test basic VFS operations
        test_operations = [
            {
                "name": "list_mounts",
                "operation": "vfs_list_mounts",
                "kwargs": {}
            },
            {
                "name": "mount_test",
                "operation": "vfs_mount",
                "kwargs": {
                    "ipfs_path": "/ipfs/QmTest",
                    "mount_point": "/tmp/vfs_test_mount",
                    "read_only": True
                }
            },
            {
                "name": "list_directory",
                "operation": "vfs_ls",
                "kwargs": {
                    "path": "/",
                    "detailed": True
                }
            }
        ]
        
        results = []
        
        for test in test_operations:
            try:
                logger.info(f"Testing {test['name']}...")
                
                # Execute operation
                result = await integration.execute_ipfs_operation(
                    test["operation"],
                    **test["kwargs"]
                )
                
                logger.info(f"✅ {test['name']} succeeded: {result}")
                results.append({
                    "test": test["name"],
                    "success": True,
                    "result": result
                })
                
            except Exception as e:
                logger.warning(f"⚠️  {test['name']} failed: {e}")
                results.append({
                    "test": test["name"],
                    "success": False,
                    "error": str(e)
                })
        
        # Report results
        successful_tests = [r for r in results if r["success"]]
        failed_tests = [r for r in results if not r["success"]]
        
        logger.info(f"\n📊 Test Results:")
        logger.info(f"Total tests: {len(results)}")
        logger.info(f"Successful: {len(successful_tests)}")
        logger.info(f"Failed: {len(failed_tests)}")
        
        if successful_tests:
            logger.info("✅ Successful tests:")
            for test in successful_tests:
                logger.info(f"  - {test['test']}")
        
        if failed_tests:
            logger.info("❌ Failed tests:")
            for test in failed_tests:
                logger.info(f"  - {test['test']}: {test['error']}")
        
        # Summary
        if len(successful_tests) > 0:
            logger.info("🎉 VFS operations through MCP server are working!")
            return True
        else:
            logger.error("❌ No VFS operations succeeded through MCP server")
            return False
            
    except Exception as e:
        logger.error(f"❌ MCP VFS test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_direct_vfs():
    """Test VFS operations directly."""
    logger.info("🧪 Testing direct VFS operations")
    
    try:
        # Test direct VFS functions
        import ipfs_fsspec
        
        # Test vfs functions directly
        vfs_functions = [
            "get_vfs",
            "vfs_mount", 
            "vfs_unmount",
            "vfs_list_mounts",
            "vfs_read",
            "vfs_write",
            "vfs_ls"
        ]
        
        available_functions = []
        missing_functions = []
        
        for func_name in vfs_functions:
            if hasattr(ipfs_fsspec, func_name):
                available_functions.append(func_name)
                logger.info(f"✅ {func_name} is available")
            else:
                missing_functions.append(func_name)
                logger.warning(f"❌ {func_name} is missing")
        
        if available_functions:
            logger.info(f"✅ {len(available_functions)} VFS functions are available")
            
            # Test getting VFS instance
            if hasattr(ipfs_fsspec, 'get_vfs'):
                vfs = ipfs_fsspec.get_vfs()
                logger.info(f"✅ VFS instance created: {type(vfs)}")
                
                # Test basic VFS operations
                backends = vfs.registry.list_backends()
                logger.info(f"✅ Available backends: {backends}")
                
                mounts = vfs.list_mounts()
                logger.info(f"✅ Current mounts: {mounts}")
                
                return True
        else:
            logger.error("❌ No VFS functions are available")
            return False
            
    except Exception as e:
        logger.error(f"❌ Direct VFS test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run MCP VFS tests."""
    logger.info("🚀 Starting MCP VFS Integration Tests")
    
    # Test direct VFS
    logger.info("\n" + "="*50)
    direct_result = await test_direct_vfs()
    
    # Test MCP VFS
    logger.info("\n" + "="*50)
    mcp_result = await test_mcp_vfs_operations()
    
    # Final report
    logger.info("\n" + "="*50)
    logger.info("📋 Final Results:")
    logger.info(f"Direct VFS test: {'PASS' if direct_result else 'FAIL'}")
    logger.info(f"MCP VFS test: {'PASS' if mcp_result else 'FAIL'}")
    
    if direct_result and mcp_result:
        logger.info("🎉 All tests passed! VFS is working through MCP server!")
        return 0
    elif direct_result:
        logger.info("✅ VFS is working directly, but MCP integration has issues")
        return 1
    else:
        logger.error("❌ VFS is not working")
        return 2

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
