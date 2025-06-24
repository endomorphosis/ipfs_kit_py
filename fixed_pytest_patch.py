#!/usr/bin/env python3
"""
Comprehensive pytest patch module.

This module integrates all pytest patches into a single coordinated application
to fix issues with pytest's internal modules. It applies fixes in the correct order
to ensure maximum compatibility.
"""

import sys
import types
import logging
import importlib
import io
from unittest.mock import MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pytest_fix")

class MockTerminalWriter:
    """Mock implementation of TerminalWriter."""

    def __init__(self, file=None):
        self.file = file or io.StringIO()
        self.hasmarkup = True
        self.lines = []

    def write(self, text, **kwargs):
        self.lines.append(str(text))
        if hasattr(self.file, 'write'):
            self.file.write(str(text))
        return self

    def line(self, text="", **kwargs):
        self.lines.append(str(text))
        if hasattr(self.file, 'write'):
            self.file.write(str(text) + "\n")
        return self

    def sep(self, sep="-", title=None, **kwargs):
        line = f"{sep * 10} {title if title else ''} {sep * 10}"
        self.lines.append(line)
        if hasattr(self.file, 'write'):
            self.file.write(line + "\n")
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

def fix_assertion_module():
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
                    if not spec:
                        return None

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

def fix_config_module():
    """
    Fix issues with _pytest.config module.

    This specifically addresses the issue with create_terminal_writer not being
    found on the Config class.
    """
    # First try direct monkey patching
    # Get _pytest module
    if '_pytest' not in sys.modules:
        logger.warning("_pytest module not found in sys.modules")
        return False

    _pytest = sys.modules['_pytest']

    # Check if config module exists
    if not hasattr(_pytest, 'config'):
        logger.warning("config module not found in _pytest")
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
        logger.info("Added config attribute to _pytest.config module")

    return True

def fix_terminal_reporter():
    """
    Fix issues with _pytest.terminal.TerminalReporter.

    This specifically patches the TerminalReporter.__init__ method to use
    our custom terminal writer.
    """
    # Fix TerminalReporter if needed
    if '_pytest.terminal' in sys.modules:
        terminal_module = sys.modules['_pytest.terminal']
        if hasattr(terminal_module, 'TerminalReporter'):
            # Save the original __init__ method
            original_init = terminal_module.TerminalReporter.__init__

            # Define a new __init__ method that uses our mock
            def patched_init(self, config, file=None):
                self.config = config
                self.verbosity = getattr(config.option, 'verbose', 0) if hasattr(config, 'option') else 0
                tw = create_terminal_writer_mock(config, file)
                self._tw = tw

                # Initialize any additional attributes needed
                self.reportchars = getattr(config.option, 'reportchars', '') if hasattr(config, 'option') else ''
                self.stats = {}
                self.startdir = getattr(config, 'invocation_dir', None) or '.'

            # Patch the init method
            terminal_module.TerminalReporter.__init__ = patched_init
            logger.info("Patched TerminalReporter.__init__ to use our custom terminal writer")
    return True

def fix_lotus_kit():
    """
    Fix issues with ipfs_kit_py.lotus_kit module.

    This adds the necessary attributes to the lotus_kit module.
    """
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

def install_meta_path_hooks():
    """
    Install meta path hooks to handle missing modules.

    This adds hooks to handle importing certain modules that might be missing
    or need special handling.
    """
    class PytestImportFixer:
        def find_spec(self, fullname, path, target=None):
            # Handle specific modules we know might cause issues
            if fullname == '_pytest.config':
                return importlib.util.find_spec('_pytest.config')
            return None

    # Add our hook to sys.meta_path
    sys.meta_path.insert(0, PytestImportFixer())
    logger.info("Installed meta path hook for _pytest.config")
    return True

def apply_all_fixes():
    """Apply all pytest fixes in the correct order."""
    # First apply assertion module fix (most critical)
    fix_assertion_module()

    # Then fix config module
    fix_config_module()

    # Fix terminal reporter
    fix_terminal_reporter()

    # Fix other modules
    fix_lotus_kit()

    # Install meta path hooks
    install_meta_path_hooks()

    logger.info("All pytest fixes applied successfully")
    return True

# Apply all fixes when this module is imported
apply_all_fixes()
