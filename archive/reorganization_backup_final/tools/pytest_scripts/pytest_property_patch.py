#!/usr/bin/env python3
"""
Pytest property patch for Python 3.12.

This module specifically targets the verbosity property issue in pytest's TerminalReporter.
"""

import sys
import types
import logging
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_property_patch")

def fix_terminal_reporter_properties():
    """Fix TerminalReporter properties by monkey patching relevant methods."""
    try:
        import _pytest.terminal
        
        # First, let's check if the TerminalReporter class exists
        if not hasattr(_pytest.terminal, "TerminalReporter"):
            logger.warning("TerminalReporter class not found in _pytest.terminal")
            return False
            
        # Get the class for patching
        TerminalReporter = _pytest.terminal.TerminalReporter
        
        # Store the original __init__ method
        original_init = TerminalReporter.__init__
        
        # Create a patched __init__ that avoids setting properties directly
        def patched_init(self, config, file=None):
            """Patched __init__ that avoids property access issues."""
            # Set some basic attributes directly
            self.config = config
            self._tw = None  # Will be set safely later
            
            # Set other essential attributes that don't use properties
            self.stats = {}
            self.currentfspath = None
            self.reportchars = None
            
            # Store verbosity as _verbosity instead of using the property
            try:
                self._verbosity = getattr(config.option, 'verbose', 0)
            except (AttributeError, TypeError):
                self._verbosity = 0
                
            # Now set the terminal writer safely
            if file is not None:
                self._tw = file
            else:
                try:
                    self._tw = config.get_terminal_writer()
                except (AttributeError, TypeError):
                    import sys
                    self._tw = sys.stdout
                    
            # Finish initialization safely
            try:
                self._collect_report_last_write = None
                self._session = None
            except Exception as e:
                logger.warning(f"Error during terminal reporter initialization: {e}")
                
        # Replace the __init__ method
        TerminalReporter.__init__ = patched_init
        
        # Add a true getter for verbosity if it doesn't exist
        if not hasattr(TerminalReporter, "_get_verbosity"):
            TerminalReporter._get_verbosity = lambda self: getattr(self, "_verbosity", 0)
            
        # Check if verbosity is a property and patch it if needed
        if isinstance(getattr(TerminalReporter, "verbosity", None), property):
            # Store the original property
            original_property = TerminalReporter.verbosity
            
            # Create a new property with a safe getter
            TerminalReporter.verbosity = property(
                lambda self: getattr(self, "_verbosity", 0)
            )
            
            logger.info("Successfully patched TerminalReporter.verbosity property")
            
        logger.info("Successfully patched TerminalReporter initialization")
        return True
    except Exception as e:
        logger.error(f"Failed to patch TerminalReporter: {e}")
        return False

def fix_assertion_rewrite():
    """Fix missing 'assertion' attribute in _pytest.assertion.rewrite."""
    try:
        from _pytest.assertion import rewrite
        if not hasattr(rewrite, 'assertion'):
            rewrite.assertion = MagicMock()
            logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
        return True
    except ImportError:
        logger.error("Failed to import _pytest.assertion.rewrite")
        return False

def fix_all():
    """Apply all fixes."""
    fix_terminal_reporter_properties()
    fix_assertion_rewrite()
    logger.info("Applied all pytest property fixes")

# Apply fixes when this module is imported
fix_all()