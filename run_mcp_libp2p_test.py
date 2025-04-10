#!/usr/bin/env python3
"""
Script to run the MCP communication tests with libp2p mocks applied.

This script will:
1. Apply the libp2p mocks from fix_libp2p_mocks.py
2. Run the test_libp2p_protocol test from test_mcp_communication.py
3. Report the test results

Usage:
    python run_mcp_libp2p_test.py
"""

import os
import sys
import importlib.util
import logging
import pytest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_and_apply_fixes():
    """Load and apply the libp2p mocks."""
    # Load the fix module
    fix_path = os.path.join(os.path.dirname(__file__), "fix_libp2p_mocks.py")
    if not os.path.exists(fix_path):
        logger.error(f"Fix script not found at {fix_path}")
        return False
    
    try:
        # Import the module
        spec = importlib.util.spec_from_file_location("fix_libp2p_mocks", fix_path)
        fix_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fix_module)
        
        # Apply the fixes
        libp2p_success = fix_module.apply_libp2p_mocks()
        mcp_success = fix_module.patch_mcp_command_handlers()
        
        if libp2p_success and mcp_success:
            logger.info("Successfully applied all fixes")
            return True
        else:
            logger.error(f"Failed to apply fixes: libp2p={libp2p_success}, mcp={mcp_success}")
            return False
    except Exception as e:
        logger.error(f"Error loading or applying fixes: {e}")
        return False

def run_test():
    """Run the test_libp2p_protocol test."""
    # Set environment variables to force mock usage
    os.environ['FORCE_MOCK_IPFS_LIBP2P_PEER'] = '1'
    os.environ['SKIP_LIBP2P'] = '0'  # Don't skip libp2p tests
    
    # Set global variables to ensure HAS_LIBP2P is true
    import ipfs_kit_py.libp2p_peer
    ipfs_kit_py.libp2p_peer.HAS_LIBP2P = True
    sys.modules['ipfs_kit_py.libp2p_peer'].HAS_LIBP2P = True
    
    # Import test module
    test_file = "test.test_mcp_communication"
    test_path = f"TestMCPServerCommunication::test_libp2p_communication"
    
    # Run the test with pytest
    result = pytest.main(["-xvs", f"{test_file}::{test_path}"])
    
    return result == 0  # 0 means success in pytest

if __name__ == "__main__":
    print("=== Running MCP libp2p Communication Test ===")
    
    # Apply fixes
    if not load_and_apply_fixes():
        print("Failed to apply necessary fixes. Exiting.")
        sys.exit(1)
    
    # Run test
    if run_test():
        print("Test passed successfully!")
        sys.exit(0)
    else:
        print("Test failed. See output for details.")
        sys.exit(1)