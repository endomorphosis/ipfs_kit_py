"""
High-level API helper modules for IPFS Kit
"""

import logging
import os
import sys
import importlib.util

logger = logging.getLogger(__name__)

HAVE_LIBP2P = False
try:
    from ..ipfs_fsspec import IPFSFileSystem as IPFSFileSystem

    HAVE_FSSPEC = True
except Exception:
    IPFSFileSystem = None
    HAVE_FSSPEC = False

_DEFAULT_IPFS_FILESYSTEM = IPFSFileSystem
_IPFS_SIMPLE_API_IMPL = None
_IPFS_SIMPLE_API_LOAD_ATTEMPTED = False
_IPFS_SIMPLE_API_LOAD_ERROR = None

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

# We intentionally avoid importing optional helper modules at package-import time.
# Some helpers pull in large dependency trees which can trigger circular imports.
WebRTCBenchmarkIntegration = None
WebRTCBenchmarkIntegrationAnyIO = None
HAVE_ANYIO_BENCHMARK = False

class IPFSSimpleAPI:
    """Functional stub implementation of IPFSSimpleAPI.

    This package intentionally avoids clobbering `ipfs_kit_py.high_level_api` in
    `sys.modules` (it is a package). We attempt to load the large legacy
    implementation in `../high_level_api.py` under a *different* module name.
    The load is deferred until first instantiation so importing this package
    does not pull optional runtime dependencies into unrelated callers.
    """

    def __new__(cls, *args, **kwargs):
        if cls is IPFSSimpleAPI:
            if not HAVE_FSSPEC or IPFSFileSystem is not _DEFAULT_IPFS_FILESYSTEM:
                return super().__new__(cls)
            impl = _try_load_ipfs_simple_api()
            if impl is not None and impl is not cls:
                return impl(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self, *args, **kwargs):
        self.config = kwargs.get("config", {})
        self._filesystem = None
        self.available = False

    def get_filesystem(self, **kwargs):
        if not HAVE_FSSPEC or IPFSFileSystem is None:
            return None

        fs_kwargs = {}
        if "role" in kwargs:
            fs_kwargs["role"] = kwargs["role"]
        else:
            fs_kwargs["role"] = self.config.get("role", "leecher")

        if "ipfs_path" in kwargs:
            fs_kwargs["ipfs_path"] = kwargs["ipfs_path"]
        elif "ipfs_path" in self.config:
            fs_kwargs["ipfs_path"] = self.config["ipfs_path"]

        if "socket_path" in kwargs:
            fs_kwargs["socket_path"] = kwargs["socket_path"]
        elif "socket_path" in self.config:
            fs_kwargs["socket_path"] = self.config["socket_path"]

        if "cache_config" in kwargs:
            fs_kwargs["cache_config"] = kwargs["cache_config"]
        elif "cache" in self.config:
            fs_kwargs["cache_config"] = self.config["cache"]

        fs_kwargs["use_mmap"] = kwargs.get("use_mmap", True)
        fs_kwargs["enable_metrics"] = kwargs.get("enable_metrics", True)

        try:
            self._filesystem = IPFSFileSystem(**fs_kwargs)
            return self._filesystem
        except Exception:
            return None

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


def _try_load_ipfs_simple_api():
    global _IPFS_SIMPLE_API_IMPL
    global _IPFS_SIMPLE_API_LOAD_ATTEMPTED
    global _IPFS_SIMPLE_API_LOAD_ERROR

    if _IPFS_SIMPLE_API_LOAD_ATTEMPTED:
        return _IPFS_SIMPLE_API_IMPL

    _IPFS_SIMPLE_API_LOAD_ATTEMPTED = True
    high_level_api_path = os.path.join(os.path.dirname(__file__), "..", "high_level_api.py")
    if not os.path.exists(high_level_api_path):
        return None

    module_name = "ipfs_kit_py._high_level_api_impl"
    try:
        existing = sys.modules.get(module_name)
        if existing is not None and getattr(existing, "IPFSSimpleAPI", None) is not None:
            _IPFS_SIMPLE_API_IMPL = existing.IPFSSimpleAPI
            globals()["IPFSSimpleAPI"] = existing.IPFSSimpleAPI
            return _IPFS_SIMPLE_API_IMPL

        spec = importlib.util.spec_from_file_location(module_name, high_level_api_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module from {high_level_api_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        impl = getattr(module, "IPFSSimpleAPI", None)
        if impl is not None:
            _IPFS_SIMPLE_API_IMPL = impl
            globals()["IPFSSimpleAPI"] = impl
            logger.info("Successfully loaded IPFSSimpleAPI implementation")
            return _IPFS_SIMPLE_API_IMPL
    except ModuleNotFoundError as e:
        _IPFS_SIMPLE_API_LOAD_ERROR = e
        if e.name == "fastapi":
            try:
                from ipfs_datasets_py.auto_installer import ensure_module

                fastapi_module = ensure_module("fastapi", "fastapi")
                if fastapi_module is not None:
                    _IPFS_SIMPLE_API_LOAD_ATTEMPTED = False
                    return _try_load_ipfs_simple_api()
            except Exception:
                pass
        logger.info(f"IPFSSimpleAPI implementation unavailable: {e}")
    except Exception as e:
        _IPFS_SIMPLE_API_LOAD_ERROR = e
        logger.info(f"IPFSSimpleAPI implementation unavailable: {e}")
    return None


# Import optional helpers after IPFSSimpleAPI is resolved.
try:
    from .webrtc_benchmark_helpers import WebRTCBenchmarkIntegration as _WebRTCBenchmarkIntegration

    WebRTCBenchmarkIntegration = _WebRTCBenchmarkIntegration
except Exception as e:
    logger.debug(f"WebRTCBenchmarkIntegration not available: {e}")

try:
    from .webrtc_benchmark_helpers_anyio import (
        WebRTCBenchmarkIntegrationAnyIO as _WebRTCBenchmarkIntegrationAnyIO,
    )

    WebRTCBenchmarkIntegrationAnyIO = _WebRTCBenchmarkIntegrationAnyIO
    HAVE_ANYIO_BENCHMARK = True
    logger.info("Successfully imported WebRTCBenchmarkIntegrationAnyIO")
except Exception as e:
    HAVE_ANYIO_BENCHMARK = False
    logger.debug(f"WebRTCBenchmarkIntegrationAnyIO not available: {e}")

# LibP2P integration is applied by IPFSSimpleAPI at instantiation time.
# Deferring avoids circular imports during package initialization.

# Export components
__all__ = ['IPFSSimpleAPI']

if WebRTCBenchmarkIntegration is not None:
    __all__.append('WebRTCBenchmarkIntegration')

# Add anyio components to exports if available
if HAVE_ANYIO_BENCHMARK:
    __all__.append('WebRTCBenchmarkIntegrationAnyIO')
    __all__.append('HAVE_ANYIO_BENCHMARK')
