#!/usr/bin/env python3
"""
Test Phase 2 Progress - IPFS Kit MCP Server Tool Coverage

This script tests the current implementation of Phase 2 tool coverage
to validate all 37 tools are properly registered and functional.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the enhanced MCP server
from mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Phase2Tester:
    """Test Phase 2 implementation"""
    
    def __init__(self):
        self.server = EnhancedMCPServerWithDaemonMgmt()
        self.test_results = {}
        
    async def test_tool_registration(self):
        """Test that all expected tools are registered"""
        logger.info("Testing tool registration...")
        
        # Get tools list
        result = await self.server.handle_tools_list({})
        tools = result.get("tools", [])
        tool_names = [tool["name"] for tool in tools]
        
        # Expected tools by category
        expected_tools = {
            "IPFS Core Operations": [
                "ipfs_add", "ipfs_cat", "ipfs_get", "ipfs_ls",
                "ipfs_pin_add", "ipfs_pin_rm", "ipfs_list_pins", "ipfs_pin_update",
                "ipfs_id", "ipfs_version", "ipfs_stats", "ipfs_swarm_peers",
                "ipfs_refs", "ipfs_refs_local", "ipfs_block_stat", "ipfs_block_get",
                "ipfs_dag_get", "ipfs_dag_put"
            ],
            "IPFS Advanced Operations": [
                "ipfs_dht_findpeer", "ipfs_dht_findprovs", "ipfs_dht_query",
                "ipfs_name_publish", "ipfs_name_resolve",
                "ipfs_pubsub_publish", "ipfs_pubsub_subscribe", "ipfs_pubsub_peers"
            ],
            "IPFS MFS Tools": [
                "ipfs_files_mkdir", "ipfs_files_ls", "ipfs_files_stat",
                "ipfs_files_read", "ipfs_files_write", "ipfs_files_cp", "ipfs_files_mv",
                "ipfs_files_rm", "ipfs_files_flush", "ipfs_files_chcid"
            ],
            "Virtual Filesystem Tools": [
                "vfs_mount", "vfs_unmount", "vfs_list_mounts",
                "vfs_read", "vfs_write", "vfs_copy", "vfs_move",
                "vfs_mkdir", "vfs_rmdir", "vfs_ls", "vfs_stat",
                "vfs_sync_to_ipfs", "vfs_sync_from_ipfs"
            ],
            "System Tools": [
                "system_health"
            ]
        }
        
        # Check registration
        registration_results = {}
        total_expected = 0
        total_found = 0
        
        for category, expected in expected_tools.items():
            found = [tool for tool in expected if tool in tool_names]
            missing = [tool for tool in expected if tool not in tool_names]
            
            registration_results[category] = {
                "expected": len(expected),
                "found": len(found),
                "missing": missing
            }
            
            total_expected += len(expected)
            total_found += len(found)
            
            logger.info(f"{category}: {len(found)}/{len(expected)} tools registered")
            if missing:
                logger.warning(f"  Missing: {missing}")
        
        self.test_results["tool_registration"] = {
            "total_expected": total_expected,
            "total_found": total_found,
            "categories": registration_results,
            "success": total_found == total_expected
        }
        
        logger.info(f"Tool Registration: {total_found}/{total_expected} tools found")
        return total_found == total_expected
    
    async def test_sample_tools(self):
        """Test execution of sample tools from each category"""
        logger.info("Testing sample tool execution...")
        
        sample_tests = [
            # IPFS Core
            ("ipfs_version", {}),
            ("ipfs_id", {}),
            ("ipfs_add", {"content": "Hello Phase 2 with VFS!"}),
            ("ipfs_stats", {"stat_type": "repo"}),
            
            # IPFS Advanced
            ("ipfs_dht_findpeer", {"peer_id": "12D3KooWTestPeer"}),
            ("ipfs_name_resolve", {"name": "test.example.com"}),
            ("ipfs_pubsub_peers", {}),
            
            # IPFS MFS
            ("ipfs_files_ls", {"path": "/"}),
            ("ipfs_files_mkdir", {"path": "/test_phase2"}),
            ("ipfs_files_write", {"path": "/test_file.txt", "content": "Test content"}),
            
            # VFS Tools
            ("vfs_list_mounts", {}),
            ("vfs_mkdir", {"path": "/vfs_test"}),
            ("vfs_write", {"path": "/vfs_test/file.txt", "content": "VFS test content"}),
            ("vfs_ls", {"path": "/"}),
            
            # System
            ("system_health", {})
        ]
        
        execution_results = {}
        
        for tool_name, args in sample_tests:
            try:
                logger.info(f"Testing {tool_name}...")
                result = await self.server.execute_tool(tool_name, args)
                success = result.get("success", False)
                
                execution_results[tool_name] = {
                    "success": success,
                    "result": result
                }
                
                if success:
                    logger.info(f"  ✓ {tool_name} executed successfully")
                else:
                    logger.warning(f"  ✗ {tool_name} failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                execution_results[tool_name] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"  ✗ {tool_name} exception: {e}")
        
        self.test_results["tool_execution"] = execution_results
        
        successful_executions = sum(1 for result in execution_results.values() if result.get("success", False))
        total_tests = len(sample_tests)
        
        logger.info(f"Tool Execution: {successful_executions}/{total_tests} sample tools executed successfully")
        return successful_executions == total_tests
    
    async def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("Generating Phase 2 test report...")
        
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "phase": "Phase 2 - Comprehensive Tool Coverage",
            "test_results": self.test_results,
            "summary": {
                "tools_registered": self.test_results.get("tool_registration", {}).get("total_found", 0),
                "tools_expected": self.test_results.get("tool_registration", {}).get("total_expected", 0),
                "registration_success": self.test_results.get("tool_registration", {}).get("success", False),
                "sample_execution_count": len(self.test_results.get("tool_execution", {})),
                "successful_executions": sum(1 for result in self.test_results.get("tool_execution", {}).values() if result.get("success", False))
            }
        }
        
        # Save report
        report_file = f"phase2_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Test report saved to: {report_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("PHASE 2 TEST SUMMARY")
        print("="*60)
        print(f"Tool Registration: {report['summary']['tools_registered']}/{report['summary']['tools_expected']} tools")
        print(f"Sample Execution: {report['summary']['successful_executions']}/{report['summary']['sample_execution_count']} tools")
        print(f"Overall Success: {report['summary']['registration_success']}")
        print("="*60)
        
        return report
    
    async def run_all_tests(self):
        """Run all Phase 2 tests"""
        logger.info("Starting Phase 2 comprehensive test suite...")
        
        try:
            # Test tool registration
            registration_ok = await self.test_tool_registration()
            
            # Test sample tool execution
            execution_ok = await self.test_sample_tools()
            
            # Generate report
            report = await self.generate_report()
            
            return registration_ok and execution_ok
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            return False
        finally:
            # Cleanup
            self.server.cleanup()

async def main():
    """Main test function"""
    tester = Phase2Tester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 Phase 2 tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Phase 2 tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
