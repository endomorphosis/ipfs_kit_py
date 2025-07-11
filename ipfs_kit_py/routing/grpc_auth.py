"""
gRPC Routing Service - DEPRECATED

This module has been deprecated due to protobuf version conflicts.
Use the HTTP API server instead: ipfs_kit_py.routing.http_server

For migration information, see: GRPC_DEPRECATION_NOTICE.md
"""

import warnings

def __getattr__(name):
    """Deprecated gRPC component access."""
    warnings.warn(
        f"gRPC component '{name}' is deprecated due to protobuf conflicts. "
        "Use ipfs_kit_py.routing.http_server.HTTPRoutingServer instead. "
        "See GRPC_DEPRECATION_NOTICE.md for migration guide.",
        DeprecationWarning,
        stacklevel=2
    )
    
    class DeprecatedGRPCComponent:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"gRPC component '{name}' deprecated. "
                "Use HTTP API: ipfs_kit_py.routing.http_server"
            )
    
    return DeprecatedGRPCComponent

# Legacy compatibility
class GRPCServer:
    def __init__(self, *args, **kwargs):
        raise ImportError(
            "GRPCServer deprecated due to protobuf conflicts. "
            "Use HTTPRoutingServer: "
            "from ipfs_kit_py.routing.http_server import HTTPRoutingServer"
        )

class RoutingServiceServicer:
    def __init__(self, *args, **kwargs):
        raise ImportError("gRPC servicer deprecated - use HTTP API")

# Export deprecated symbols for backwards compatibility
__all__ = ["GRPCServer", "RoutingServiceServicer"]
