#!/usr/bin/env python3
"""
Monkey patch for pytest's terminal writer in Python 3.12.

This module specifically addresses the issue with pytest's terminal writer in Python 3.12
by monkey patching the relevant components directly in the pytest modules.
"""

import sys
import types
import logging
from unittest.mock import MagicMock

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_terminal_fix")

def fix_terminal_reporter():
    """Fix TerminalReporter's __init__ method to avoid attribute errors."""
    try:
        import _pytest.terminal
        
        # Store the original __init__ method
        original_init = _pytest.terminal.TerminalReporter.__init__
        
        # Create a new __init__ that handles problematic attributes
        def safe_init(self, config, file=None):
            try:
                # Try the original init first
                original_init(self, config, file)
            except AttributeError as e:
                # If we get an attribute error, fallback to a minimal initialization
                logger.warning(f"Using fallback initialization for TerminalReporter: {e}")
                
                # Initialize basic attributes directly
                self.config = config
                self.startdir = getattr(config, 'startdir', None)
                self._tw = file or sys.stdout
                self.stats = {}
                self.currentfspath = None
                self._session = None
                self._showfspath = None
                
                # Add missing attributes that are common sources of errors
                self._tested_count_width = 5  # Reasonable default
                self._collect_report_last_write = None
                
                # Initialize properties safely
                try:
                    self.verbosity = getattr(config.option, 'verbose', 0)
                except (AttributeError, TypeError):
                    logger.debug("Could not access config.option.verbose, using default")
                    self._verbosity = 0
                    
                try:
                    self.showheader = getattr(config.option, 'verbose', 0) > 0
                except (AttributeError, TypeError):
                    logger.debug("Could not access config.option.verbose for showheader, using default")
                    self._showheader = True
                    
                try:
                    self.showfspath = getattr(config.option, 'showlocals', False)
                except (AttributeError, TypeError):
                    logger.debug("Could not access config.option.showlocals, using default")
                    self._showfspath = True
                    
                # Add other properties with default values
                self._tw.hasmarkup = getattr(self._tw, 'hasmarkup', True)
                
        # Replace the __init__ method
        _pytest.terminal.TerminalReporter.__init__ = safe_init
        logger.info("Successfully patched TerminalReporter.__init__")
        return True
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to patch TerminalReporter: {e}")
        return False

def fix_config_create_terminal_writer():
    """Fix create_terminal_writer in _pytest.config."""
    try:
        import _pytest.config
        
        # Define our patched create_terminal_writer function
        def patched_create_terminal_writer(config, file=None):
            try:
                # Try to get the terminal writer from compat module
                try:
                    from _pytest.config.compat import create_terminal_writer as original
                    return original(config, file)
                except (ImportError, AttributeError):
                    pass
                    
                # If we cannot access the original function, create a minimal terminal writer
                from _pytest.terminal import TerminalWriter
                return TerminalWriter(file)
            except Exception as e:
                logger.warning(f"Failed to create terminal writer: {e}")
                # Last resort: return a minimal object with the most common methods
                mock_tw = MagicMock()
                mock_tw.line = lambda text="", **kw: None
                mock_tw.sep = lambda char="-", title=None, **kw: None
                mock_tw.write = lambda text, **kw: None
                return mock_tw
                
        # Add the function to the module
        _pytest.config.create_terminal_writer = patched_create_terminal_writer
        
        # Also add it to Config class for good measure
        if hasattr(_pytest.config, 'Config'):
            if not hasattr(_pytest.config.Config, 'create_terminal_writer'):
                _pytest.config.Config.create_terminal_writer = staticmethod(patched_create_terminal_writer)
                
        logger.info("Successfully patched create_terminal_writer")
        return True
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to patch create_terminal_writer: {e}")
        return False

def fix_assertion_rewrite():
    """Fix missing 'assertion' attribute in _pytest.assertion.rewrite."""
    try:
        import _pytest.assertion.rewrite
        
        if not hasattr(_pytest.assertion.rewrite, 'assertion'):
            _pytest.assertion.rewrite.assertion = MagicMock()
            logger.info("Added missing 'assertion' attribute to _pytest.assertion.rewrite")
            
        return True
    except ImportError as e:
        logger.error(f"Failed to fix _pytest.assertion.rewrite: {e}")
        return False

def apply_all_fixes():
    """Apply all pytest fixes."""
    results = []
    
    # Fix terminal reporter
    results.append(fix_terminal_reporter())
    
    # Fix config.create_terminal_writer
    results.append(fix_config_create_terminal_writer())
    
    # Fix assertion rewrite
    results.append(fix_assertion_rewrite())
    
    # Report results
    success_count = sum(1 for result in results if result)
    logger.info(f"Applied {success_count}/{len(results)} pytest fixes successfully")
    
    return all(results)

# Apply the patches when imported
apply_all_fixes()