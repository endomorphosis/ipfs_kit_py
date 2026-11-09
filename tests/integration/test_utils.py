#!/usr/bin/env python3
"""
Utility functions for tests to handle common tasks like imports,
setup and teardown.
"""

import os
import sys
import logging
import importlib
from typing import Dict, Any, List, Optional, Tuple, Set, Callable

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_utils")

def import_or_mock(module_path: str, attributes: List[str] = None) -> Tuple[bool, Any]:
    """
    Attempt to import a module, but create a mock if it fails.
    
    Args:
        module_path: The module path to import
        attributes: Optional list of attribute names to ensure exist in the mock
        
    Returns:
        Tuple of (success, module) where success is a boolean and module is either
        the real module or a mock
    """
    try:
        module = importlib.import_module(module_path)
        return True, module
    except ImportError as e:
        logger.warning(f"Could not import {module_path}: {e}")
        # Create a mock module
        import types
        mock_module = types.ModuleType(module_path)
        
        # Add any required attributes
        if attributes:
            for attr in attributes:
                setattr(mock_module, attr, None)
        
        # Add to sys.modules
        sys.modules[module_path] = mock_module
        return False, mock_module

def pytest_safe_skip(condition: bool, reason: str):
    """
    Safely skip a test, handling both pytest and standalone execution.
    
    Args:
        condition: If True, test will be skipped
        reason: The reason for skipping
    """
    if condition:
        try:
            # Try to import pytest for proper skipping
            import pytest
            pytest.skip(reason)
        except ImportError:
            # If pytest isn't available, just log
            logger.warning(f"Test skipped: {reason}")
        except Exception as e:
            # Other exceptions in pytest environment
            logger.warning(f"Test skipped: {reason} (error: {e})")

def requires_modules(*module_paths, mock_on_fail=True):
    """
    Decorator to skip tests if required modules are not available.
    
    Args:
        *module_paths: Module paths required for the test
        mock_on_fail: If True, create mock modules on failure
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            all_available = True
            for module_path in module_paths:
                try:
                    importlib.import_module(module_path)
                except ImportError as e:
                    logger.warning(f"Required module {module_path} not available: {e}")
                    all_available = False
                    if mock_on_fail:
                        # Create a mock module
                        import types
                        mock_module = types.ModuleType(module_path)
                        sys.modules[module_path] = mock_module
            
            if not all_available:
                pytest_safe_skip(True, f"Missing required modules: {', '.join(module_paths)}")
                return None
            
            return func(*args, **kwargs)
        return wrapper
    return decorator