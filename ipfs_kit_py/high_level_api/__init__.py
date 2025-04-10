"""
High-level API helper modules for IPFS Kit
"""

import logging
logger = logging.getLogger(__name__)

# Import LibP2P integration if available
try:
    # First check if libp2p is available
    from ..libp2p import HAS_LIBP2P
    
    # Only attempt to import integration if libp2p is available
    if HAS_LIBP2P:
        from . import libp2p_integration
        logger.info("LibP2P integration module imported")
    else:
        logger.warning("LibP2P integration module not loaded: libp2p dependencies not available")
except ImportError as e:
    logger.warning(f"LibP2P integration module not available: {e}")

# Import WebRTC benchmark helpers (both asyncio and anyio versions)
from .webrtc_benchmark_helpers import WebRTCBenchmarkIntegration
try:
    from .webrtc_benchmark_helpers_anyio import WebRTCBenchmarkIntegrationAnyIO
    HAVE_ANYIO_BENCHMARK = True
    logger.info("Successfully imported WebRTCBenchmarkIntegrationAnyIO")
except ImportError:
    logger.warning("WebRTCBenchmarkIntegrationAnyIO not available")
    HAVE_ANYIO_BENCHMARK = False

# Import IPFSSimpleAPI from parent module to make it available here
# This solves the import issue with MCP server
try:
    # Try absolute import path first with full module path
    import importlib.util
    import sys
    import os

    # Get the path to the high_level_api.py file (parent module)
    high_level_api_path = os.path.join(os.path.dirname(__file__), "..", "high_level_api.py")
    
    if os.path.exists(high_level_api_path):
        # Load the module directly using importlib
        spec = importlib.util.spec_from_file_location("ipfs_kit_py.high_level_api", high_level_api_path)
        high_level_api_module = importlib.util.module_from_spec(spec)
        sys.modules["ipfs_kit_py.high_level_api"] = high_level_api_module
        spec.loader.exec_module(high_level_api_module)

        # Import the IPFSSimpleAPI class from the module
        IPFSSimpleAPI = high_level_api_module.IPFSSimpleAPI
        logger.info("Successfully imported IPFSSimpleAPI from high_level_api.py")
    else:
        # Create a functional stub that won't raise exceptions
        class IPFSSimpleAPI:
            """Functional stub implementation of IPFSSimpleAPI."""
            def __init__(self, *args, **kwargs):
                logger.warning("Using stub implementation of IPFSSimpleAPI")
                self.available = False
                
            def __getattr__(self, name):
                """Return a dummy function that logs a warning and returns a default result."""
                def dummy_method(*args, **kwargs):
                    logger.warning(f"IPFSSimpleAPI.{name} called but not available (using stub implementation)")
                    return {"success": False, "warning": f"IPFSSimpleAPI.{name} not available (using stub implementation)"}
                return dummy_method
except Exception as e:
    # Create a functional stub that won't raise exceptions
    logger.warning(f"Error importing IPFSSimpleAPI: {e}")
    
    class IPFSSimpleAPI:
        """Functional stub implementation of IPFSSimpleAPI."""
        def __init__(self, *args, **kwargs):
            logger.warning("Using stub implementation of IPFSSimpleAPI")
            self.available = False
            
        def __getattr__(self, name):
            """Return a dummy function that logs a warning and returns a default result."""
            def dummy_method(*args, **kwargs):
                logger.warning(f"IPFSSimpleAPI.{name} called but not available (using stub implementation)")
                return {"success": False, "warning": f"IPFSSimpleAPI.{name} not available (using stub implementation)"}
            return dummy_method

# Export components
__all__ = ['WebRTCBenchmarkIntegration', 'IPFSSimpleAPI']

# Add anyio components to exports if available
if HAVE_ANYIO_BENCHMARK:
    __all__.append('WebRTCBenchmarkIntegrationAnyIO')
    __all__.append('HAVE_ANYIO_BENCHMARK')