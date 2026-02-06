"""
High-level API helper modules for IPFS Kit
"""

import logging
import os
import sys
import importlib.util

logger = logging.getLogger(__name__)

HAVE_LIBP2P = False

def _init_libp2p_integration() -> None:
    global HAVE_LIBP2P
    try:
        # First check if libp2p is available
        from ..libp2p import HAS_LIBP2P as _HAS_LIBP2P

        HAVE_LIBP2P = bool(_HAS_LIBP2P)

        # Only attempt to import integration if libp2p is available
        if HAVE_LIBP2P:
            from . import libp2p_integration
            logger.info("LibP2P integration module imported")
        else:
            logger.warning("LibP2P integration module not loaded: libp2p dependencies not available")
    except ImportError as e:
        logger.warning(f"LibP2P integration module not available: {e}")

# Import WebRTC benchmark helpers (both async-io and anyio versions)
from .webrtc_benchmark_helpers import WebRTCBenchmarkIntegration
try:
    from .webrtc_benchmark_helpers_anyio import WebRTCBenchmarkIntegrationAnyIO
    HAVE_ANYIO_BENCHMARK = True
    logger.info("Successfully imported WebRTCBenchmarkIntegrationAnyIO")
except ImportError:
    logger.warning("WebRTCBenchmarkIntegrationAnyIO not available")
    HAVE_ANYIO_BENCHMARK = False

class IPFSSimpleAPI:
    """Functional stub implementation of IPFSSimpleAPI.

    This package intentionally avoids clobbering `ipfs_kit_py.high_level_api` in
    `sys.modules` (it is a package). We attempt to load the large legacy
    implementation in `../high_level_api.py` under a *different* module name.
    """

    def __init__(self, *args, **kwargs):
        logger.warning("Using stub implementation of IPFSSimpleAPI")
        self.available = False

    def __getattr__(self, name):
        def dummy_method(*args, **kwargs):
            logger.warning(
                f"IPFSSimpleAPI.{name} called but not available (using stub implementation)"
            )
            return {
                "success": False,
                "warning": f"IPFSSimpleAPI.{name} not available (using stub implementation)",
            }

        return dummy_method


def _try_load_ipfs_simple_api() -> None:
    high_level_api_path = os.path.join(os.path.dirname(__file__), "..", "high_level_api.py")
    if not os.path.exists(high_level_api_path):
        return

    module_name = "ipfs_kit_py._high_level_api_impl"
    try:
        existing = sys.modules.get(module_name)
        if existing is not None and getattr(existing, "IPFSSimpleAPI", None) is not None:
            globals()["IPFSSimpleAPI"] = existing.IPFSSimpleAPI
            return

        spec = importlib.util.spec_from_file_location(module_name, high_level_api_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module from {high_level_api_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        impl = getattr(module, "IPFSSimpleAPI", None)
        if impl is not None:
            globals()["IPFSSimpleAPI"] = impl
            logger.info("Successfully loaded IPFSSimpleAPI implementation")
    except Exception as e:
        logger.warning(f"Error importing IPFSSimpleAPI implementation: {e}")


_try_load_ipfs_simple_api()
_init_libp2p_integration()

# Export components
__all__ = ['WebRTCBenchmarkIntegration', 'IPFSSimpleAPI']

# Add anyio components to exports if available
if HAVE_ANYIO_BENCHMARK:
    __all__.append('WebRTCBenchmarkIntegrationAnyIO')
    __all__.append('HAVE_ANYIO_BENCHMARK')