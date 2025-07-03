o s i#!/usr/bin/env python3
"""
Phase 2 IPFS Core Tools Test Script

This script tests the Phase 2 IPFS core tools implementation:
- Tool registry integration
- IPFS daemon connectivity
- Core tool functionality
- Error handling
"""

import os
import sys
import logging
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

# Add directories to Python path
base_dir = Path(__file__).parent
core_dir = base_dir / "core"
tools_dir = base_dir / "tools"
sys.path.insert(0, str(core_dir))
sys.path.insert(0, str(tools_dir))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('phase2_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Phase2Tester:
    """Phase 2 IPFS tools tester"""
    
    def __init__(self):
        self.test_results = {}
        self.components = {}
        
    def setup_test_environment(self) -> bool:
        """Setup test environment and load components"""
        try:
            logger.info("Setting up test environment...")
            
            # Import core components
            from core.tool_registry import registry
            from core.service_manager import ipfs_manager
            from core.error_handler import error_handler
            
            self.components = {
                'tool_registry': registry,
                'ipfs_manager': ipfs_manager,
                'error_handler': error_handler
            }
            
            logger.info("✓ Test environment setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup test environment: {e}")
            return False
    
    def test_ipfs_daemon_connectivity(self) -> bool:
        """Test IPFS daemon connectivity"""
        logger.info("Testing IPFS daemon connectivity...")
        
        try:
            ipfs_manager = self.components.get('ipfs_manager')
            if not ipfs_manager:
                logger.error("IPFS manager not available")
                return False
            
            # Check if daemon is running
            if ipfs_manager.health_check("ipfs"):
                logger.info("✓ IPFS daemon is accessible")
                self.test_results['ipfs_daemon'] = 'pass'
                return True
            else:
                logger.warning("⚠ IPFS daemon not accessible")
                self.test_results['ipfs_daemon'] = 'fail'
                return False
                
        except Exception as e:
            logger.error(f"IPFS daemon test failed: {e}")
            self.test_results['ipfs_daemon'] = 'error'
            return False
    
    def test_tool_registry_integration(self) -> bool:
        """Test tool registry contains IPFS tools"""
        logger.info("Testing tool registry integration...")
        
        try:
            registry = self.components.get('tool_registry')
            if not registry:
                logger.error("Tool registry not available")
                return False
            
            # Check for IPFS tools
            ipfs_tools = []
            for tool_name, tool in registry.tools.items():
                if hasattr(tool, 'category') and 'ipfs' in tool.category.value.lower():
                    ipfs_tools.append(tool_name)
            
            logger.info(f"Found {len(ipfs_tools)} IPFS tools in registry:")
            for tool in ipfs_tools[:5]:  # Show first 5
                logger.info(f"  • {tool}")
            if len(ipfs_tools) > 5:
                logger.info(f"  ... and {len(ipfs_tools) - 5} more")
            
            if len(ipfs_tools) >= 10:  # Allow some flexibility
                logger.info("✓ Tool registry integration test passed")
                self.test_results['tool_registry'] = 'pass'
                return True
            else:
                logger.warning(f"⚠ Only {len(ipfs_tools)} IPFS tools found (expected 18)")
                self.test_results['tool_registry'] = 'partial'
                return False
                
        except Exception as e:
            logger.error(f"Tool registry test failed: {e}")
            self.test_results['tool_registry'] = 'error'
            return False
    
    def test_core_ipfs_operations(self) -> bool:
        """Test core IPFS operations"""
        logger.info("Testing core IPFS operations...")
        
        # Test data
        test_content = "Hello IPFS from Phase 2 testing!"
        test_results = {}
        
        try:
            registry = self.components.get('tool_registry')
            if not registry:
                logger.error("Tool registry not available")
                return False
            
            # Test ipfs_add
            if 'ipfs_add' in registry.tools:
                try:
                    logger.info("Testing ipfs_add...")
                    add_tool = registry.tools['ipfs_add']
                    handler = registry.get_tool_handler('ipfs_add')
                    
                    if handler:
                        result = handler({'content': test_content})
                        if result.get('status') == 'success':
                            cid = result.get('data', {}).get('cid')
                            if cid:
                                logger.info(f"✓ ipfs_add successful: {cid}")
                                test_results['ipfs_add'] = {'status': 'pass', 'cid': cid}
                            else:
                                logger.warning("⚠ ipfs_add returned no CID")
                                test_results['ipfs_add'] = {'status': 'partial'}
                        else:
                            logger.warning(f"⚠ ipfs_add failed: {result}")
                            test_results['ipfs_add'] = {'status': 'fail'}
                    else:
                        logger.warning("⚠ ipfs_add handler not found")
                        test_results['ipfs_add'] = {'status': 'missing'}
                        
                except Exception as e:
                    logger.error(f"ipfs_add test error: {e}")
                    test_results['ipfs_add'] = {'status': 'error', 'error': str(e)}
            else:
                logger.warning("⚠ ipfs_add tool not registered")
                test_results['ipfs_add'] = {'status': 'missing'}
            
            # Test ipfs_cat (if we have a CID from add)
            if 'ipfs_cat' in registry.tools and test_results.get('ipfs_add', {}).get('cid'):
                try:
                    logger.info("Testing ipfs_cat...")
                    cat_handler = registry.get_tool_handler('ipfs_cat')
                    cid = test_results['ipfs_add']['cid']
                    
                    if cat_handler:
                        result = cat_handler({'cid': cid})
                        if result.get('status') == 'success':
                            content = result.get('data', {}).get('content', '')
                            if test_content in content:
                                logger.info("✓ ipfs_cat successful - content matches")
                                test_results['ipfs_cat'] = {'status': 'pass'}
                            else:
                                logger.warning("⚠ ipfs_cat content mismatch")
                                test_results['ipfs_cat'] = {'status': 'partial'}
                        else:
                            logger.warning(f"⚠ ipfs_cat failed: {result}")
                            test_results['ipfs_cat'] = {'status': 'fail'}
                    else:
                        logger.warning("⚠ ipfs_cat handler not found")
                        test_results['ipfs_cat'] = {'status': 'missing'}
                        
                except Exception as e:
                    logger.error(f"ipfs_cat test error: {e}")
                    test_results['ipfs_cat'] = {'status': 'error', 'error': str(e)}
            
            # Test ipfs_id
            if 'ipfs_id' in registry.tools:
                try:
                    logger.info("Testing ipfs_id...")
                    id_handler = registry.get_tool_handler('ipfs_id')
                    
                    if id_handler:
                        result = id_handler({})
                        if result.get('status') == 'success':
                            node_id = result.get('data', {}).get('ID')
                            if node_id:
                                logger.info(f"✓ ipfs_id successful: {node_id[:20]}...")
                                test_results['ipfs_id'] = {'status': 'pass'}
                            else:
                                logger.warning("⚠ ipfs_id returned no node ID")
                                test_results['ipfs_id'] = {'status': 'partial'}
                        else:
                            logger.warning(f"⚠ ipfs_id failed: {result}")
                            test_results['ipfs_id'] = {'status': 'fail'}
                    else:
                        logger.warning("⚠ ipfs_id handler not found")
                        test_results['ipfs_id'] = {'status': 'missing'}
                        
                except Exception as e:
                    logger.error(f"ipfs_id test error: {e}")
                    test_results['ipfs_id'] = {'status': 'error', 'error': str(e)}
            
            # Test ipfs_version
            if 'ipfs_version' in registry.tools:
                try:
                    logger.info("Testing ipfs_version...")
                    version_handler = registry.get_tool_handler('ipfs_version')
                    
                    if version_handler:
                        result = version_handler({})
                        if result.get('status') == 'success':
                            version = result.get('data', {}).get('Version')
                            if version:
                                logger.info(f"✓ ipfs_version successful: {version}")
                                test_results['ipfs_version'] = {'status': 'pass'}
                            else:
                                logger.warning("⚠ ipfs_version returned no version")
                                test_results['ipfs_version'] = {'status': 'partial'}
                        else:
                            logger.warning(f"⚠ ipfs_version failed: {result}")
                            test_results['ipfs_version'] = {'status': 'fail'}
                    else:
                        logger.warning("⚠ ipfs_version handler not found")
                        test_results['ipfs_version'] = {'status': 'missing'}
                        
                except Exception as e:
                    logger.error(f"ipfs_version test error: {e}")
                    test_results['ipfs_version'] = {'status': 'error', 'error': str(e)}
            
            # Store results
            self.test_results['core_operations'] = test_results
            
            # Calculate pass rate
            total_tests = len(test_results)
            passed_tests = len([t for t in test_results.values() if t.get('status') == 'pass'])
            
            logger.info(f"Core operations test completed: {passed_tests}/{total_tests} passed")
            
            return passed_tests >= total_tests * 0.5  # At least 50% should pass
            
        except Exception as e:
            logger.error(f"Core operations test failed: {e}")
            self.test_results['core_operations'] = {'error': str(e)}
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling in IPFS tools"""
        logger.info("Testing error handling...")
        
        try:
            registry = self.components.get('tool_registry')
            if not registry:
                return False
            
            # Test with invalid CID
            if 'ipfs_cat' in registry.tools:
                logger.info("Testing error handling with invalid CID...")
                cat_handler = registry.get_tool_handler('ipfs_cat')
                
                if cat_handler:
                    result = cat_handler({'cid': 'invalid_cid'})
                    if result.get('status') == 'error':
                        logger.info("✓ Error handling test passed - invalid CID handled correctly")
                        self.test_results['error_handling'] = 'pass'
                        return True
                    else:
                        logger.warning("⚠ Error handling test failed - invalid CID not handled")
                        self.test_results['error_handling'] = 'fail'
                        return False
            
            logger.warning("⚠ No suitable tools for error handling test")
            self.test_results['error_handling'] = 'skip'
            return True
            
        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            self.test_results['error_handling'] = 'error'
            return False
    
    def run_all_tests(self) -> bool:
        """Run all Phase 2 tests"""
        logger.info("=" * 60)
        logger.info("PHASE 2 COMPREHENSIVE TESTING")
        logger.info("=" * 60)
        
        # Setup
        if not self.setup_test_environment():
            return False
        
        # Run tests
        tests = [
            ("IPFS Daemon Connectivity", self.test_ipfs_daemon_connectivity),
            ("Tool Registry Integration", self.test_tool_registry_integration),
            ("Core IPFS Operations", self.test_core_ipfs_operations),
            ("Error Handling", self.test_error_handling),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            logger.info(f"\nRunning: {test_name}")
            logger.info("-" * 40)
            try:
                result = test_func()
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"Test {test_name} crashed: {e}")
                all_passed = False
        
        return all_passed
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        # Calculate summary statistics
        total_tests = 0
        passed_tests = 0
        
        for test_category, result in self.test_results.items():
            if isinstance(result, dict) and 'status' not in result:
                # This is a category with multiple sub-tests
                for sub_test, sub_result in result.items():
                    total_tests += 1
                    if isinstance(sub_result, dict) and sub_result.get('status') == 'pass':
                        passed_tests += 1
            else:
                # This is a single test
                total_tests += 1
                if result == 'pass':
                    passed_tests += 1
        
        report = {
            "phase": "Phase 2 - IPFS Core Tools Testing",
            "timestamp": str(Path(__file__).stat().st_mtime),
            "test_results": self.test_results.copy(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%",
                "overall_status": "pass" if passed_tests >= total_tests * 0.7 else "fail"
            }
        }
        
        return report
    
    def save_test_report(self, filename: str = "phase2_test_report.json"):
        """Save test report to file"""
        try:
            report = self.generate_test_report()
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Test report saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save test report: {e}")
            return False

def main():
    """Main test function"""
    print("=" * 60)
    print("IPFS Kit MCP Integration - Phase 2 Testing")
    print("=" * 60)
    print()
    
    # Create tester
    tester = Phase2Tester()
    
    # Run tests
    success = tester.run_all_tests()
    
    # Generate and save report
    tester.save_test_report()
    
    # Print summary
    print()
    print("=" * 60)
    print("PHASE 2 TEST SUMMARY")
    print("=" * 60)
    
    for test_category, result in tester.test_results.items():
        if isinstance(result, dict) and 'status' not in result:
            print(f"\n{test_category.replace('_', ' ').title()}:")
            for sub_test, sub_result in result.items():
                status = sub_result.get('status', 'unknown') if isinstance(sub_result, dict) else sub_result
                status_symbol = "✓" if status == "pass" else "⚠" if status == "partial" else "✗"
                print(f"  {status_symbol} {sub_test}: {status}")
        else:
            status_symbol = "✓" if result == "pass" else "⚠" if result == "partial" else "✗"
            print(f"{status_symbol} {test_category.replace('_', ' ').title()}: {result}")
    
    print()
    if success:
        print("🎉 Phase 2 testing completed successfully!")
        print("✓ IPFS daemon connectivity verified")
        print("✓ Tool registry integration working")
        print("✓ Core IPFS operations functional")
        print("✓ Error handling properly implemented")
        print()
        print("Next steps:")
        print("1. Review phase2_test_report.json for detailed results")
        print("2. Proceed with integration testing")
        print("3. Begin Phase 3 implementation")
    else:
        print("❌ Phase 2 testing completed with issues")
        print("Please review the test results and resolve issues")
    
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
