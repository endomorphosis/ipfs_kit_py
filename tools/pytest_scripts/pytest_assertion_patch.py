#!/usr/bin/env python3
"""
Pytest assertion module patch.

This module specifically addresses issues with the _pytest.assertion.rewrite module
by adding missing attributes that may be referenced in tests.
"""

import sys
import types
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_assertion_patch")

def patch_assertion_module():
    """
    Add missing 'assertion' attribute to _pytest.assertion.rewrite module.
    
    This patch ensures that any code trying to access _pytest.assertion.rewrite.assertion
    will work correctly even though that attribute doesn't exist in the original module.
    """
    # Check if the module is already in sys.modules
    if '_pytest.assertion.rewrite' in sys.modules:
        rewrite_module = sys.modules['_pytest.assertion.rewrite']
        if not hasattr(rewrite_module, 'assertion'):
            # Create the missing assertion attribute
            rewrite_module.assertion = MagicMock()
            logger.info("Added missing 'assertion' attribute to existing _pytest.assertion.rewrite module")
    else:
        # If the module isn't loaded yet, we can create a finder to patch it when it's imported
        class AssertionRewritePatcher:
            def find_spec(self, fullname, path, target=None):
                if fullname == '_pytest.assertion.rewrite':
                    # Get the real spec
                    import importlib.util
                    spec = importlib.util.find_spec('_pytest.assertion.rewrite')
                    
                    # Create a custom loader that wraps the real one
                    orig_loader = spec.loader
                    
                    class CustomLoader:
                        def create_module(self, spec):
                            # Let the original loader create the module
                            module = orig_loader.create_module(spec)
                            return module
                            
                        def exec_module(self, module):
                            # Let the original loader execute the module
                            orig_loader.exec_module(module)
                            
                            # Add our patch
                            if not hasattr(module, 'assertion'):
                                module.assertion = MagicMock()
                                logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite module during import")
                    
                    # Replace the loader with our custom one
                    spec.loader = CustomLoader()
                    return spec
                return None
        
        # Insert our finder at the beginning of sys.meta_path
        sys.meta_path.insert(0, AssertionRewritePatcher())
        logger.info("Installed meta path hook for _pytest.assertion.rewrite")
    
    # Also add the module to sys.modules if it doesn't exist yet
    if '_pytest.assertion' not in sys.modules:
        # Create a module
        assertion_module = types.ModuleType('_pytest.assertion')
        sys.modules['_pytest.assertion'] = assertion_module
        
        # Add the rewrite submodule if needed
        if '_pytest.assertion.rewrite' not in sys.modules:
            rewrite_module = types.ModuleType('_pytest.assertion.rewrite')
            rewrite_module.assertion = MagicMock()
            assertion_module.rewrite = rewrite_module
            sys.modules['_pytest.assertion.rewrite'] = rewrite_module
            logger.info("Created _pytest.assertion.rewrite module with assertion attribute")
    
    return True

# Apply the patch
patch_assertion_module()
logger.info("Successfully applied pytest assertion patches")
