"""
IPFS Kit Compatibility Layer for gRPC Deprecation

This module provides backwards compatibility during the gRPC deprecation transition.
"""

import warnings
import logging

logger = logging.getLogger(__name__)

class DeprecationWarning(UserWarning):
    """Custom deprecation warning for gRPC components."""
    pass

def grpc_deprecation_warning(component_name: str, alternative: str = None):
    """Issue deprecation warning for gRPC components."""
    message = f"gRPC component '{component_name}' is deprecated due to protobuf conflicts."
    
    if alternative:
        message += f" Use {alternative} instead."
    else:
        message += " Use HTTP API alternatives."
    
    message += " See GRPC_DEPRECATION_NOTICE.md for migration guide."
    
    warnings.warn(message, DeprecationWarning, stacklevel=3)
    logger.warning(message)

# Routing API compatibility
def get_routing_client():
    """Get routing client with deprecation warning."""
    grpc_deprecation_warning(
        "routing client", 
        "HTTP requests to ipfs_kit_py.routing.http_server"
    )
    raise ImportError("gRPC routing client deprecated - use HTTP API")

def get_routing_server():
    """Get routing server with deprecation warning."""
    grpc_deprecation_warning(
        "routing server",
        "ipfs_kit_py.routing.http_server.HTTPRoutingServer"
    )
    raise ImportError("gRPC routing server deprecated - use HTTP API")

# Module-level compatibility
def __getattr__(name: str):
    """Handle deprecated attribute access."""
    
    grpc_components = [
        "GRPCServer", "GRPCClient", "RoutingServiceServicer",
        "grpc_server", "grpc_client", "grpc_auth"
    ]
    
    if name in grpc_components or "grpc" in name.lower():
        grpc_deprecation_warning(name)
        raise AttributeError(f"gRPC component '{name}' deprecated")
    
    raise AttributeError(f"module 'ipfs_kit_py.compat' has no attribute '{name}'")

# Export compatibility symbols
__all__ = ["grpc_deprecation_warning", "get_routing_client", "get_routing_server"]
