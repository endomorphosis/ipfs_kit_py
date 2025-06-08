#!/usr/bin/env python3
"""
Complete pytest assertion and meta path hook fixer.

This patches pytest's assertion rewrite and meta path hook mechanisms 
to ensure proper operation during testing.
"""

import sys
import types
import logging
import importlib.abc
import importlib.util
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_fix")

def create_assertion_module():
    """Create and patch the pytest assertion module structure."""
    # Create _pytest.assertion module if it doesn't exist
    if '_pytest.assertion' not in sys.modules:
        assertion_module = types.ModuleType('_pytest.assertion')
        sys.modules['_pytest.assertion'] = assertion_module
        logger.info("Created _pytest.assertion module")
    else:
        assertion_module = sys.modules['_pytest.assertion']
    
    # Create _pytest.assertion.rewrite module if it doesn't exist
    if '_pytest.assertion.rewrite' not in sys.modules:
        rewrite_module = types.ModuleType('_pytest.assertion.rewrite')
        sys.modules['_pytest.assertion.rewrite'] = rewrite_module
        assertion_module.rewrite = rewrite_module
        logger.info("Created _pytest.assertion.rewrite module")
    else:
        rewrite_module = sys.modules['_pytest.assertion.rewrite']
        assertion_module.rewrite = rewrite_module
    
    # Add the missing 'assertion' attribute to rewrite module
    if not hasattr(rewrite_module, 'assertion'):
        class AssertionHelper:
            def __init__(self):
                self.rewrite = MagicMock()
        
        rewrite_helper = AssertionHelper()
        rewrite_module.assertion = rewrite_helper
        assertion_module.assertion = rewrite_helper
        logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
    
    # Create a dummy AssertionRewriter class if needed
    if not hasattr(rewrite_module, 'AssertionRewriter'):
        class MockAssertionRewriter:
            def __init__(self, *args, **kwargs):
                pass
            
            def rewrite(self, *args, **kwargs):
                return None
        
        rewrite_module.AssertionRewriter = MockAssertionRewriter
        logger.info("Added AssertionRewriter class to _pytest.assertion.rewrite")
    
    return assertion_module

def add_meta_path_hook():
    """Add a meta path hook for pytest modules to ensure proper loading."""
    
    class PytestModuleFinder(importlib.abc.MetaPathFinder):
        """Meta path finder for pytest modules."""
        
        def find_spec(self, fullname, path, target=None):
            """Find the module spec for pytest modules."""
            if fullname.startswith('_pytest'):
                # Check if module already exists
                if fullname in sys.modules:
                    # Module exists, return a spec pointing to the existing module
                    return importlib.util.spec_from_loader(
                        fullname, 
                        importlib.abc.Loader()
                    )
                
                if fullname == '_pytest.assertion':
                    # Make sure we have the assertion module
                    create_assertion_module()
                    return importlib.util.spec_from_loader(
                        fullname, 
                        importlib.abc.Loader()
                    )
                
                if fullname == '_pytest.assertion.rewrite':
                    # Make sure we have the rewrite module
                    assertion_module = create_assertion_module()
                    return importlib.util.spec_from_loader(
                        fullname, 
                        importlib.abc.Loader()
                    )
            
            # Not a pytest module, let other finders handle it
            return None
    
    # Add our finder to sys.meta_path
    sys.meta_path.insert(0, PytestModuleFinder())
    logger.info("Added meta path hook for pytest modules")

def apply_all_fixes():
    """Apply all fixes for pytest assertion and meta path hooks."""
    create_assertion_module()
    add_meta_path_hook()
    logger.info("All pytest fixes applied successfully")

# Apply fixes when this module is imported
apply_all_fixes()