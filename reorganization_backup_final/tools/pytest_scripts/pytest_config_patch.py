#!/usr/bin/env python3
"""
Pytest config module patch.

This module patches pytest's config module to ensure test compatibility.
"""

import sys
import io
import types
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_config_patch")

class MockTerminalWriter:
    """Mock implementation of TerminalWriter."""
    
    def __init__(self, file=None):
        self.file = file or io.StringIO()
        self.hasmarkup = False
        
    def write(self, text, **kwargs):
        if hasattr(self.file, 'write'):
            self.file.write(str(text))
        return self
        
    def line(self, text="", **kwargs):
        if hasattr(self.file, 'write'):
            self.file.write(str(text) + "\n")
        return self
        
    def sep(self, sep="-", **kwargs):
        if hasattr(self.file, 'write'):
            self.file.write(sep * 80 + "\n")
        return self
        
    def flush(self):
        if hasattr(self.file, 'flush'):
            self.file.flush()
        return self

def create_terminal_writer_mock(config=None, file=None):
    """Mock implementation of create_terminal_writer."""
    tw = MockTerminalWriter(file)
    if config is not None and hasattr(config, 'option') and hasattr(config.option, 'color'):
        tw.hasmarkup = config.option.color != 'no'
    return tw

def monkey_patch_pytest_config():
    """
    Direct monkey patch _pytest.config module.
    
    This approach directly modifies the _pytest.config module to add the necessary
    terminal writer functionality.
    """
    # Get _pytest module
    if '_pytest' not in sys.modules:
        logger.error("_pytest module not found in sys.modules")
        return False
    
    _pytest = sys.modules['_pytest']
    
    # Check if config module exists
    if not hasattr(_pytest, 'config'):
        logger.error("config module not found in _pytest")
        return False
    
    # Add create_terminal_writer function to the module
    _pytest.config.create_terminal_writer = create_terminal_writer_mock
    logger.info("Added create_terminal_writer function to _pytest.config")
    
    # Also add the function to the Config class itself
    if hasattr(_pytest.config, 'Config'):
        # Add create_terminal_writer method to the Config class
        setattr(_pytest.config.Config, 'create_terminal_writer', staticmethod(create_terminal_writer_mock))
        logger.info("Added create_terminal_writer staticmethod to Config class")
        
        # If Config has get_terminal_writer, also set up an alias
        if hasattr(_pytest.config.Config, 'get_terminal_writer'):
            # Define a method that calls get_terminal_writer
            def config_create_terminal_writer(cls, config=None, file=None):
                if hasattr(config, 'get_terminal_writer'):
                    return config.get_terminal_writer()
                return create_terminal_writer_mock(config, file)
                
            setattr(_pytest.config.Config, 'create_terminal_writer', 
                    classmethod(config_create_terminal_writer))
            logger.info("Added create_terminal_writer alias to Config.get_terminal_writer")
    
    # Also add config attribute (making it point to Config class)
    if hasattr(_pytest.config, 'Config') and not hasattr(_pytest.config, 'config'):
        _pytest.config.config = _pytest.config.Config
        logger.info("Added config attribute to _pytest.config")
    
    return True

def patch_pytest_config():
    """
    Add missing functions to pytest config module.
    
    This specifically addresses the issue with create_terminal_writer not being
    found on the Config class.
    """
    # Also try to monkey patch the TerminalReporter class directly
    if '_pytest.terminal' in sys.modules:
        terminal_module = sys.modules['_pytest.terminal']
        if hasattr(terminal_module, 'TerminalReporter'):
            # Save the original __init__ method
            original_init = terminal_module.TerminalReporter.__init__
            
            # Define a new __init__ method that uses our mock
            def patched_init(self, config, file=None):
                self.config = config
                self.verbosity = getattr(config.option, 'verbose', 0)
                self._tw = create_terminal_writer_mock(config, file)
                # Call other initialization if needed but skip the original method
                
            # Apply the monkey patch
            terminal_module.TerminalReporter.__init__ = patched_init
            logger.info("Patched TerminalReporter.__init__ to use our custom terminal writer")
    
    # First try direct monkey patching
    if monkey_patch_pytest_config():
        return True
    
    # Fallback to module-level patch
    if '_pytest.config' in sys.modules:
        config_module = sys.modules['_pytest.config']
        
        # Check if create is already in the module path
        try:
            from _pytest.config import create
            if hasattr(create, 'create_terminal_writer'):
                # Function exists in create module, add it to config
                config_module.create_terminal_writer = create.create_terminal_writer
                logger.info("Added create_terminal_writer from create module to config")
                return True
        except (ImportError, AttributeError):
            pass
            
        # Try with create submodule
        try:
            from _pytest.config import create as create_module
            if hasattr(create_module, 'create_terminal_writer'):
                # Function exists in create module, add it to config
                config_module.create_terminal_writer = create_module.create_terminal_writer
                logger.info("Added create_terminal_writer from create submodule to config")
                return True
        except (ImportError, AttributeError):
            pass
            
        # The function wasn't found or there was an error, so let's create a mock
        try:
            from _pytest.config.create import TerminalWriter
            
            # Define our own implementation
            def create_terminal_writer(config=None, file=None):
                """Create a TerminalWriter instance."""
                tw = TerminalWriter(file)
                if config is not None:
                    tw.hasmarkup = config.option.color != 'no'
                return tw
                
            config_module.create_terminal_writer = create_terminal_writer
            logger.info("Created and added mock create_terminal_writer function")
        except ImportError:
            # If we can't import TerminalWriter, use our MockTerminalWriter
            config_module.create_terminal_writer = create_terminal_writer_mock
            logger.info("Added mock create_terminal_writer function to config")
        
        # Add config attribute if needed
        if hasattr(config_module, 'Config') and not hasattr(config_module, 'config'):
            config_module.config = config_module.Config
            logger.info("Added config attribute to _pytest.config module")
            
    return True

# Apply the patch
patch_pytest_config()
logger.info("Successfully applied pytest config patches")
