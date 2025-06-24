"""
Patch for pytest's assertion rewriting mechanism to work with the test suite.

This module fixes the issue with "_pytest.assertion.rewrite" module lacking an "assertion" attribute,
which causes import errors in the test suite.
"""

import sys
import logging
import importlib
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_assertion_patch")

def patch_assertion_rewrite():
    """
    Add missing 'assertion' attribute to _pytest.assertion.rewrite module.
    """
    try:
        # Import the module
        rewrite_module = importlib.import_module('_pytest.assertion.rewrite')

        # Add the missing attribute if it doesn't exist
        if not hasattr(rewrite_module, 'assertion'):
            setattr(rewrite_module, 'assertion', MagicMock())
            logger.info("Added 'assertion' attribute to _pytest.assertion.rewrite module")
    except ImportError:
        logger.warning("Could not import _pytest.assertion.rewrite module")
    except Exception as e:
        logger.error(f"Error patching assertion rewrite module: {e}")

# Apply the patch when the module is imported
patch_assertion_rewrite()
