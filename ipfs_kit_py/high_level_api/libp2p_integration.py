"""
LibP2P integration for the high-level API.

This module extends the IPFSSimpleAPI with libp2p capabilities when available.
"""

import os
import logging
import time
import uuid
import importlib.util
import sys
from typing import Any, Dict, List, Optional, Type, Union, Callable

logger = logging.getLogger(__name__)

# Try to import required modules
try:
    from ..libp2p import HAS_LIBP2P
    from ..libp2p_peer import IPFSLibp2pPeer
    
    # Import from libp2p.high_level_api_integration for the implementation
    from ..libp2p.high_level_api_integration import extend_high_level_api_class, apply_high_level_api_integration

    # Add libp2p methods to IPFSSimpleAPI
    # We'll define a method to apply the integration that can be called from outside
    if HAS_LIBP2P:
        logger.info("Adding libp2p methods to IPFSSimpleAPI")
        
        def inject_libp2p_into_high_level_api(api_class):
            """
            Inject libp2p functionality into the IPFSSimpleAPI class.
            
            This function is used for dependency injection, allowing the integration
            to be applied after both modules are fully loaded.
            
            Args:
                api_class: The IPFSSimpleAPI class to extend
                
            Returns:
                The extended api_class
            """
            try:
                # Call the function from high_level_api_integration
                return extend_high_level_api_class(api_class)
            except Exception as e:
                logger.error(f"Failed to inject libp2p into high-level API: {e}")
                return api_class
        
        # Export the function
        __all__ = ["inject_libp2p_into_high_level_api"]
    else:
        logger.warning("libp2p is not available, high-level API integration disabled")
        # Export the function as empty stub
        def inject_libp2p_into_high_level_api(api_class):
            """Stub implementation when libp2p is not available."""
            return api_class
        
        __all__ = ["inject_libp2p_into_high_level_api"]
except ImportError as e:
    logger.error(f"Error importing libp2p components: {e}")
    # Provide a stub function
    def inject_libp2p_into_high_level_api(api_class):
        """Stub implementation when imports fail."""
        return api_class
    
    __all__ = ["inject_libp2p_into_high_level_api"]