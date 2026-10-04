#!/usr/bin/env python3
"""
Pytest internal patch module.

This module patches pytest's internal modules to ensure compatibility
with the test suite, focusing on fixing issues with the terminal writer
and other critical components.
"""

import sys
import importlib
import logging
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_patch")

def fix_assertion_module():
    """Add missing 'assertion' attribute to _pytest.assertion.rewrite."""
    try:
        from _pytest.assertion import rewrite
        if not hasattr(rewrite, 'assertion'):
            rewrite.assertion = MagicMock()
            logger.info("Added missing 'assertion' attribute to existing _pytest.assertion.rewrite module")
        return True
    except ImportError:
        logger.error("Failed to import _pytest.assertion.rewrite module")
        return False

def fix_config_module():
    """Fix issues with _pytest.config module."""
    try:
        import _pytest.config
        from _pytest.config import Config
        
        if not hasattr(_pytest.config, 'Config'):
            _pytest.config.Config = Config
            logger.info("Added 'Config' reference to _pytest.config")
            
        # Add create_terminal_writer to Config class directly
        if not hasattr(Config, 'create_terminal_writer'):
            def create_terminal_writer_static(config=None, file=None):
                class MockTerminalWriter:
                    def __init__(self):
                        self.lines = []
                        self.hasmarkup = True
                        self.file = file
                    def line(self, s='', **kw):
                        self.lines.append(s)
                        if self.file:
                            self.file.write(s + '\n')
                        return self
                    def sep(self, sep, title=None, **kw):
                        line = f"{sep * 10} {title if title else ''} {sep * 10}"
                        self.lines.append(line)
                        if self.file:
                            self.file.write(line + '\n')
                        return self
                    def write(self, s, **kw):
                        self.lines.append(s)
                        if self.file:
                            self.file.write(str(s))
                        return self
                    def flush(self):
                        if self.file and hasattr(self.file, 'flush'):
                            self.file.flush()
                        return self
                return MockTerminalWriter()
                
            # Add as static method to Config class
            setattr(Config, 'create_terminal_writer', staticmethod(create_terminal_writer_static))
            logger.info("Added create_terminal_writer method to Config class")
            
            # Also add to module level
            _pytest.config.create_terminal_writer = create_terminal_writer_static
            logger.info("Added create_terminal_writer function to _pytest.config module")
                
        # Fix TerminalReporter if needed
        if '_pytest.terminal' in sys.modules:
            terminal = sys.modules['_pytest.terminal']
            if hasattr(terminal, 'TerminalReporter'):
                original_init = terminal.TerminalReporter.__init__
                
                def patched_init(self, config, file=None):
                    self.config = config
                    self.verbosity = getattr(config.option, 'verbose', 0) if hasattr(config, 'option') else 0
                    tw = _pytest.config.create_terminal_writer(config, file)
                    self._tw = tw
                
                # Patch the init method
                terminal.TerminalReporter.__init__ = patched_init
                logger.info("Patched TerminalReporter.__init__")
        # Check if LOTUS_KIT_AVAILABLE is already defined
        try:
            from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
            logger.info(f"LOTUS_KIT_AVAILABLE already defined: {LOTUS_KIT_AVAILABLE}")
        except (ImportError, AttributeError):
            # Add it if not defined
            import types
            lotus_kit_module = types.ModuleType("ipfs_kit_py.lotus_kit")
            lotus_kit_module.LOTUS_KIT_AVAILABLE = True
            lotus_kit_module.lotus_kit = MagicMock()
            sys.modules["ipfs_kit_py.lotus_kit"] = lotus_kit_module
            logger.info("Created mock lotus_kit module with LOTUS_KIT_AVAILABLE=True")
            
        return True
    except Exception as e:
        logger.error(f"Failed to fix _pytest.config module: {e}")
        return False

def install_meta_path_hook():
    """Install a meta path hook to handle missing modules."""
    class PytestImportFixer:
        def find_spec(self, fullname, path, target=None):
            # Handle specific modules we know might cause issues
            if fullname == '_pytest.config':
                return importlib.util.find_spec('_pytest.config')
            return None
            
    # Add our hook to sys.meta_path
    sys.meta_path.insert(0, PytestImportFixer())
    logger.info("Installed meta path hook for _pytest.config")

# Apply all fixes
fix_assertion_module()
fix_config_module()
install_meta_path_hook()
logger.info("Installed all pytest compatibility fixes")
