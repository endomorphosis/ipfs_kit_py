#!/usr/bin/env python3
"""
Test Phase 1 Components

Quick test script to verify Phase 1 components are working correctly.
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_phase1_components():
    """Test all Phase 1 components"""
    print("Testing Phase 1 Components")
    print("=" * 40)
    
    # Test 1: Tool Registry
    print("1. Testing Tool Registry...")
    try:
        from mcp.ipfs_kit.core.tool_registry import ToolRegistry, ToolCategory, ToolSchema
        
        registry = ToolRegistry()
        
        # Create a test tool
        test_tool = ToolSchema(
            name="test_tool",
            category=ToolCategory.SYSTEM,
            description="Test tool",
            parameters={},
            returns={},
            version="1.0.0",
            dependencies=[]
        )
        
        success = registry.register_tool(test_tool)
        assert success, "Failed to register test tool"
        assert "test_tool" in registry.tools, "Test tool not found in registry"
        
        print("   ✓ Tool Registry working correctly")
        
    except Exception as e:
        print(f"   ✗ Tool Registry failed: {e}")
        return False
    
    # Test 2: Service Manager
    print("2. Testing Service Manager...")
    try:
        from mcp.ipfs_kit.core.service_manager import ServiceManager
        
        manager = ServiceManager()
        port = manager.find_available_port(9000, 10)
        assert port is not None, "Failed to find available port"
        
        print(f"   ✓ Service Manager working correctly (found port {port})")
        
    except Exception as e:
        print(f"   ✗ Service Manager failed: {e}")
        return False
    
    # Test 3: Error Handler
    print("3. Testing Error Handler...")
    try:
        from mcp.ipfs_kit.core.error_handler import ErrorHandler, ErrorCode, create_success_response
        
        handler = ErrorHandler()
        
        # Test error creation
        error = handler.create_error(ErrorCode.INVALID_PARAMETER, "Test error")
        assert error.status == "error", "Error creation failed"
        assert error.error_code == ErrorCode.INVALID_PARAMETER.value, "Error code mismatch"
        
        # Test success response
        success_resp = create_success_response("test data")
        assert success_resp["status"] == "success", "Success response failed"
        
        print("   ✓ Error Handler working correctly")
        
    except Exception as e:
        print(f"   ✗ Error Handler failed: {e}")
        return False
    
    # Test 4: Test Framework
    print("4. Testing Test Framework...")
    try:
        from mcp.ipfs_kit.core.test_framework import TestFramework, TestSuite, TestCategory
        
        framework = TestFramework()
        
        # Create a simple test
        def simple_test():
            assert True, "This should pass"
        
        test_suite = TestSuite(
            name="simple_test_suite",
            tests=[simple_test],
            category=TestCategory.UNIT
        )
        
        framework.register_test_suite(test_suite)
        results = framework.run_test_suite("simple_test_suite")
        
        assert len(results) == 1, "Test suite should have 1 result"
        assert results[0].status.value == "passed", "Test should pass"
        
        print("   ✓ Test Framework working correctly")
        
    except Exception as e:
        print(f"   ✗ Test Framework failed: {e}")
        return False
    
    print()
    print("=" * 40)
    print("All Phase 1 components working correctly! ✓")
    print("=" * 40)
    return True

if __name__ == "__main__":
    success = test_phase1_components()
    sys.exit(0 if success else 1)
