#!/usr/bin/env python3
"""
Unified Parameter Handling Test Suite

This script tests the enhanced parameter handling for both IPFS and
multi-backend tools. It ensures that tools can handle different parameter
naming conventions consistently.
"""

import os
import sys
import json
import anyio
import logging
import argparse
import importlib
from pathlib import Path
from datetime import datetime

# Configure logging
log_file = f"parameter_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger("parameter-test")

async def test_ipfs_parameters():
    """Run IPFS parameter tests"""
    logger.info("====== Testing IPFS Parameter Handling ======")
    
    try:
        # Try to import the test module
        if os.path.exists('test_ipfs_mcp_tools.py'):
            # Import the module
            spec = importlib.util.spec_from_file_location("test_ipfs_tools", "test_ipfs_mcp_tools.py")
            test_ipfs_tools = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_ipfs_tools)
            
            # Run tests
            if hasattr(test_ipfs_tools, 'run_all_tests'):
                logger.info("Running IPFS parameter tests...")
                result = await test_ipfs_tools.run_all_tests()
                logger.info(f"IPFS parameter tests completed with result: {'✅ PASSED' if result else '❌ FAILED'}")
                return result
            else:
                logger.error("IPFS test module does not have run_all_tests function")
                return False
        else:
            logger.error("IPFS test module not found")
            return False
    except Exception as e:
        logger.error(f"Error running IPFS parameter tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def test_multi_backend_parameters():
    """Run multi-backend parameter tests"""
    logger.info("====== Testing Multi-Backend Parameter Handling ======")
    
    try:
        # Try to import the test module
        if os.path.exists('test_multi_backend_params.py'):
            # Import the module
            spec = importlib.util.spec_from_file_location("test_multi_backend", "test_multi_backend_params.py")
            test_multi_backend = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_multi_backend)
            
            # Run tests
            if hasattr(test_multi_backend, 'run_all_tests'):
                logger.info("Running multi-backend parameter tests...")
                result = await test_multi_backend.run_all_tests()
                logger.info(f"Multi-backend parameter tests completed with result: {'✅ PASSED' if result else '❌ FAILED'}")
                return result
            else:
                logger.error("Multi-backend test module does not have run_all_tests function")
                return False
        else:
            logger.error("Multi-backend test module not found")
            return False
    except Exception as e:
        logger.error(f"Error running multi-backend parameter tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def run_specific_tool_test(tool_name, parameter_variants):
    """
    Test a specific tool with different parameter naming variants
    
    Args:
        tool_name: The name of the tool to test
        parameter_variants: List of parameter dictionaries with different naming conventions
    """
    logger.info(f"====== Testing {tool_name} with Parameter Variants ======")
    
    try:
        from enhanced_parameter_adapter import ToolContext
        
        # Try to get the direct handler
        handler = None
        
        # Try IPFS handlers
        try:
            from ipfs_tool_adapters import get_tool_handler
            handler = get_tool_handler(tool_name)
        except ImportError:
            pass
        
        # Try multi-backend handlers if not found
        if not handler:
            try:
                from enhanced.multi_backend_tool_adapters import get_tool_handler as get_mbfs_handler
                handler = get_mbfs_handler(tool_name)
            except ImportError:
                pass
        
        if not handler:
            logger.error(f"No handler found for tool: {tool_name}")
            return False
        
        # Test each parameter variant
        results = []
        
        for variant_index, params in enumerate(parameter_variants):
            logger.info(f"Testing variant {variant_index + 1}: {json.dumps(params, indent=2)}")
            
            # Create context with the parameters
            ctx = ToolContext(params)
            
            # Call the handler
            try:
                result = await handler(ctx)
                logger.info(f"Result: {json.dumps(result, indent=2)}")
                results.append({
                    "variant": variant_index + 1,
                    "params": params,
                    "result": result,
                    "success": result.get("success", False)
                })
            except Exception as e:
                logger.error(f"Error calling handler: {e}")
                results.append({
                    "variant": variant_index + 1,
                    "params": params,
                    "error": str(e),
                    "success": False
                })
        
        # Check if all tests were successful
        all_success = all(r["success"] for r in results)
        
        logger.info(f"Tool {tool_name} test completed with result: {'✅ PASSED' if all_success else '❌ FAILED'}")
        logger.info(f"Tested {len(results)} parameter variants, {sum(1 for r in results if r['success'])} succeeded")
        
        return all_success
    
    except Exception as e:
        logger.error(f"Error testing tool {tool_name}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def run_all_tests():
    """Run all parameter tests"""
    logger.info("====== Starting Enhanced Parameter Handling Tests ======")
    
    ipfs_result = await test_ipfs_parameters()
    multi_backend_result = await test_multi_backend_parameters()
    
    # Generate overall report
    logger.info("====== Test Summary ======")
    logger.info(f"IPFS Parameter Tests: {'✅ PASSED' if ipfs_result else '❌ FAILED'}")
    logger.info(f"Multi-Backend Parameter Tests: {'✅ PASSED' if multi_backend_result else '❌ FAILED'}")
    
    all_passed = ipfs_result and multi_backend_result
    logger.info(f"Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    # Create test report file
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": {
            "ipfs_tests": ipfs_result,
            "multi_backend_tests": multi_backend_result,
            "overall": all_passed
        },
        "log_file": log_file
    }
    
    with open("parameter_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Test report saved to parameter_test_report.json")
    
    return all_passed

def main():
    """Main function to parse arguments and run tests"""
    parser = argparse.ArgumentParser(description="Enhanced Parameter Handling Test Suite")
    parser.add_argument('--tool', help='Test a specific tool')
    parser.add_argument('--ipfs-only', action='store_true', help='Only test IPFS tools')
    parser.add_argument('--multi-backend-only', action='store_true', help='Only test multi-backend tools')
    
    args = parser.parse_args()
    
    if args.tool:
        # Test a specific tool
        print(f"Testing specific tool: {args.tool}")
        # TODO: Implement specific tool testing
        anyio.run(run_specific_tool_test, args.tool, [])
    elif args.ipfs_only:
        # Test only IPFS tools
        anyio.run(test_ipfs_parameters)
    elif args.multi_backend_only:
        # Test only multi-backend tools
        anyio.run(test_multi_backend_parameters)
    else:
        # Run all tests
        anyio.run(run_all_tests)

if __name__ == "__main__":
    main()
