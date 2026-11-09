#!/usr/bin/env python3
"""
Custom test runner that bypasses pytest's internal configuration.

This script directly imports and runs the test files, avoiding the issues
with pytest's config and terminal modules.
"""

import os
import sys
import unittest
import importlib.util
import logging
import types
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger("test_runner")

def patch_pytest_modules():
    """Apply critical patches to pytest modules."""
    # Patch assertion module
    if '_pytest.assertion.rewrite' in sys.modules:
        rewrite_module = sys.modules['_pytest.assertion.rewrite']
        if not hasattr(rewrite_module, 'assertion'):
            rewrite_module.assertion = MagicMock()
            logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
    
    # Add the modules to sys.modules if they don't exist yet
    if '_pytest.assertion' not in sys.modules:
        assertion_module = types.ModuleType('_pytest.assertion')
        sys.modules['_pytest.assertion'] = assertion_module
        
        if '_pytest.assertion.rewrite' not in sys.modules:
            rewrite_module = types.ModuleType('_pytest.assertion.rewrite')
            rewrite_module.assertion = MagicMock()
            assertion_module.rewrite = rewrite_module
            sys.modules['_pytest.assertion.rewrite'] = rewrite_module
    
    # Add import hook to ensure future imports work
    class PytestImportHook:
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith('_pytest'):
                # For any _pytest module that's imported, ensure it has basic functionality
                if fullname == '_pytest.assertion.rewrite':
                    # Handle this module specially
                    return None  # Let the regular import machinery handle it, we'll patch after
            return None
    
    # Insert our hook
    sys.meta_path.insert(0, PytestImportHook())
    logger.info("Added meta path hook for pytest modules")
    return True

def import_test_module(file_path):
    """Import a test module from a file path."""
    # Get the module name from the file path
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not find module spec for {file_path}")
    
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    
    # Now execute the module
    spec.loader.exec_module(module)
    
    return module

def discover_test_classes(module):
    """Discover all unittest.TestCase classes in a module."""
    test_cases = []
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj != unittest.TestCase:
            test_cases.append(obj)
    return test_cases

def run_test_file(file_path):
    """Run all tests in a test file."""
    logger.info(f"Running tests from: {file_path}")
    
    # First apply patches
    patch_pytest_modules()
    
    try:
        # Import the test module
        module = import_test_module(file_path)
        
        # Discover test cases
        test_cases = discover_test_classes(module)
        
        if not test_cases:
            logger.warning(f"No test cases found in {file_path}")
            return False
        
        # Create test suite
        suite = unittest.TestSuite()
        for test_case in test_cases:
            suite.addTest(unittest.defaultTestLoader.loadTestsFromTestCase(test_case))
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Return success/failure
        return result.wasSuccessful()
    except Exception as e:
        logger.error(f"Error running tests: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Get the test file from command line arguments
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <test_file_path>")
        sys.exit(1)
    
    test_file = sys.argv[1]
    success = run_test_file(test_file)
    
    sys.exit(0 if success else 1)
