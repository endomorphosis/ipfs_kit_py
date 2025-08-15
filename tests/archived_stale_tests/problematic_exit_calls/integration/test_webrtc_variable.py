#!/usr/bin/env python3
"""
This script tests how pytest is handling the _can_test_webrtc flag.
"""

import importlib
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_regular_import():
    """Test importing the module directly."""
    logger.info("Testing direct import:")
    
    # Import the test module
    from test.test_webrtc_streaming import _can_test_webrtc
    
    logger.info(f"Direct import _can_test_webrtc = {_can_test_webrtc}")

def test_import_reload():
    """Test importing the module with importlib.reload."""
    logger.info("Testing import with reload:")
    
    # First, import the module
    import test.test_webrtc_streaming
    
    # Check initial value
    logger.info(f"Before reload _can_test_webrtc = {test.test_webrtc_streaming._can_test_webrtc}")
    
    # Now reload the module
    importlib.reload(test.test_webrtc_streaming)
    
    # Check value after reload
    logger.info(f"After reload _can_test_webrtc = {test.test_webrtc_streaming._can_test_webrtc}")

def test_import_with_flags():
    """Test importing the module in different ways."""
    logger.info("Testing different import approaches:")
    
    # Direct assignment after import
    import test.test_webrtc_streaming
    test.test_webrtc_streaming._can_test_webrtc = True
    logger.info(f"After direct assignment _can_test_webrtc = {test.test_webrtc_streaming._can_test_webrtc}")
    
    # Check if module is already in sys.modules and its value
    if "test.test_webrtc_streaming" in sys.modules:
        logger.info(f"Module in sys.modules, _can_test_webrtc = {sys.modules['test.test_webrtc_streaming']._can_test_webrtc}")
    
    # Simulate pytest's collection behavior (clean import)
    if "test.test_webrtc_streaming" in sys.modules:
        del sys.modules["test.test_webrtc_streaming"]
    
    import test.test_webrtc_streaming
    logger.info(f"After clean import _can_test_webrtc = {test.test_webrtc_streaming._can_test_webrtc}")
    
    # Check actual HAVE_WEBRTC status
    from ipfs_kit_py.webrtc_streaming import HAVE_WEBRTC
    logger.info(f"Actual HAVE_WEBRTC from source module = {HAVE_WEBRTC}")
    
    # Modify skipif condition directly
    import pytest
    from test.test_webrtc_streaming import TestWebRTCStreaming
    
    # Get the original skipif mark
    skipif_mark = [m for m in TestWebRTCStreaming.__dict__.get('__pytest_skipped__', []) 
                  if hasattr(m, 'condition')]
    
    if skipif_mark:
        logger.info(f"Original skipif condition: {skipif_mark[0].condition}")
        
        # Try to force the condition to False
        skipif_mark[0].condition = False
        logger.info(f"Modified skipif condition: {skipif_mark[0].condition}")

if __name__ == "__main__":
    try:
        test_regular_import()
        test_import_reload()
        test_import_with_flags()
    except Exception as e:
        logger.error(f"Error during testing: {e}")
        sys.exit(1)