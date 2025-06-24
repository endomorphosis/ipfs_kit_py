"""
Patch for Uvicorn's websockets implementation to fix deprecation warnings.

This module provides a function to patch the Uvicorn websockets implementation
to use the newer import path instead of the deprecated one.
"""

import importlib
import logging
import sys
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def apply_uvicorn_websockets_patch():
    """
    Apply patch to fix the deprecation warning in Uvicorn's websockets implementation.

    Specifically replaces 'from websockets.server import WebSocketServerProtocol'
    with 'from websockets.legacy.server import WebSocketServerProtocol'
    to fix the "websockets.server.WebSocketServerProtocol is deprecated" warning.
    """
    try:
        # Check if the module is imported
        if "uvicorn.protocols.websockets.websockets_impl" in sys.modules:
            module = sys.modules["uvicorn.protocols.websockets.websockets_impl"]

            # Check if patching is needed
            if hasattr(module, "WebSocketServerProtocol") and hasattr(module.WebSocketServerProtocol, "__module__"):
                if module.WebSocketServerProtocol.__module__ == "websockets.server":
                    # The module is using the deprecated import, patch it
                    logger.info("Patching Uvicorn's WebSocketServerProtocol import")

                    # Import the class from the correct location
                    try:
                        from websockets.legacy.server import WebSocketServerProtocol as NewWebSocketServerProtocol

                        # Replace the imported class
                        module.WebSocketServerProtocol = NewWebSocketServerProtocol
                        return True
                    except ImportError as e:
                        logger.debug(f"Failed to import WebSocketServerProtocol from websockets.legacy.server: {e}")
                        return False
                else:
                    # Already using the correct import
                    logger.debug("Uvicorn WebSocketServerProtocol import is already using the correct path")
                    return False
            else:
                logger.debug("Could not access WebSocketServerProtocol in uvicorn module")
                return False
        else:
            # Load the module and then apply the patch
            try:
                import uvicorn.protocols.websockets.websockets_impl
                return apply_uvicorn_websockets_patch()
            except ImportError as e:
                logger.debug(f"Failed to import uvicorn.protocols.websockets.websockets_impl: {e}")
                return False
    except Exception as e:
        logger.error(f"Error patching Uvicorn's WebSocketServerProtocol: {e}")
        return False


# Patch loader that modifies the module source code during import
class UvicornWebsocketsImplLoader(Loader):
    """
    Custom loader that modifies the source code of the uvicorn.protocols.websockets.websockets_impl
    module during import to fix the deprecation warning.
    """

    def create_module(self, spec: ModuleSpec) -> Optional[ModuleType]:
        """Create the module, delegating to the default loader."""
        return None  # Use default module creation

    def exec_module(self, module: ModuleType) -> None:
        """Execute the module, patching the imports."""
        # Load the original module
        original_loader = self.get_original_loader()
        if original_loader:
            original_loader.exec_module(module)

            # Patch the WebSocketServerProtocol import
            try:
                from websockets.legacy.server import WebSocketServerProtocol as NewWebSocketServerProtocol
                module.WebSocketServerProtocol = NewWebSocketServerProtocol

                # Update the import line for better code inspection
                import re
                module.__doc__ = re.sub(
                    r"from websockets\.server import WebSocketServerProtocol",
                    "from websockets.legacy.server import WebSocketServerProtocol  # Patched by uvicorn_websockets_patch.py",
                    module.__doc__ or ""
                )

                logger.info("Successfully patched websockets import in uvicorn module during load")
            except ImportError as e:
                logger.debug(f"Failed to patch WebSocketServerProtocol import: {e}")

    def get_original_loader(self) -> Optional[Loader]:
        """Get the original loader for the module."""
        try:
            # Find the original spec without our hook
            name = "uvicorn.protocols.websockets.websockets_impl"
            original_spec = importlib.util.find_spec(name)
            if original_spec and original_spec.loader and original_spec.loader != self:
                return original_spec.loader
        except Exception as e:
            logger.debug(f"Failed to get original loader: {e}")
        return None


def install_import_hook():
    """
    Install an import hook to patch the Uvicorn websockets implementation during import.
    """
    try:
        import sys
        from importlib.machinery import PathFinder

        # Create a hook that intercepts imports of the specific module
        class UvicornWebsocketsImplFinder(PathFinder):
            @classmethod
            def find_spec(cls, fullname, path=None, target=None):
                if fullname == "uvicorn.protocols.websockets.websockets_impl":
                    # Get the original spec
                    spec = super().find_spec(fullname, path, target)
                    if spec:
                        # Replace the loader with our custom one
                        spec.loader = UvicornWebsocketsImplLoader()
                    return spec
                return None

        # Insert our finder at the beginning of the list
        sys.meta_path.insert(0, UvicornWebsocketsImplFinder)
        logger.info("Installed import hook for uvicorn.protocols.websockets.websockets_impl")
        return True
    except Exception as e:
        logger.error(f"Failed to install import hook: {e}")
        return False
