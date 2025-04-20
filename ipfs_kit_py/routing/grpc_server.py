"""
gRPC Server for Optimized Data Routing

This module implements a gRPC server for the optimized data routing system,
providing a high-performance, language-independent interface.
"""

import os
import time
import json
import logging
import asyncio
import threading
from concurrent import futures
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Generator, AsyncGenerator

try:
    import grpc
    import grpc.experimental.aio as grpc_aio
    from google.protobuf.struct_pb2 import Struct
    from google.protobuf.timestamp_pb2 import Timestamp
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    # Create placeholder for type hints
    class grpc:
        class ServicerContext: pass
        class Server: pass
    class grpc_aio:
        class ServicerContext: pass
        class Server: pass

# Configure logging
logger = logging.getLogger(__name__)

# Import routing components
from ipfs_kit_py.routing import RoutingManager, RoutingManagerSettings
from ipfs_kit_py.routing.metrics_collector import RoutingMetricsDatabase

# Import gRPC generated code (will be available after generation)
# These imports will work after running the generate_grpc_code.py script
try:
    from ipfs_kit_py.routing.grpc.routing_pb2 import (
        SelectBackendRequest, SelectBackendResponse,
        RecordOutcomeRequest, RecordOutcomeResponse,
        GetInsightsRequest, GetInsightsResponse,
        StreamMetricsRequest, MetricsUpdate
    )
    from ipfs_kit_py.routing.grpc.routing_pb2_grpc import (
        RoutingServiceServicer, 
        add_RoutingServiceServicer_to_server
    )
    GRPC_GENERATED_CODE_AVAILABLE = True
except ImportError:
    # Placeholder for missing generated code
    SelectBackendRequest = RecordOutcomeRequest = GetInsightsRequest = StreamMetricsRequest = None
    SelectBackendResponse = RecordOutcomeResponse = GetInsightsResponse = MetricsUpdate = None
    RoutingServiceServicer = None
    add_RoutingServiceServicer_to_server = None
    GRPC_GENERATED_CODE_AVAILABLE = False


class RoutingServicer(RoutingServiceServicer):
    """Implementation of the RoutingService gRPC service."""
    
    def __init__(self, routing_manager: Optional["RoutingManager"] = None):
        """
        Initialize the RoutingServicer.
        
        Args:
            routing_manager: Optional RoutingManager instance
        """
        self.routing_manager = routing_manager
        self._metrics_streams = set()
        self._shutdown_event = threading.Event()
    
    async def initialize(self) -> None:
        """Initialize the routing manager if not provided."""
        if self.routing_manager is None:
            settings = RoutingManagerSettings(
                enabled=True,
                auto_start_background_tasks=True,
                collect_metrics_on_startup=True
            )
            self.routing_manager = await RoutingManager.create(settings)
            logger.info("Initialized routing manager for gRPC service")
    
    async def shutdown(self) -> None:
        """Shutdown the servicer."""
        self._shutdown_event.set()
        
        # Close all streaming connections
        for stream in self._metrics_streams:
            try:
                await stream.cancel()
            except Exception:
                pass
        
        # Shutdown routing manager
        if self.routing_manager and hasattr(self.routing_manager, "stop"):
            await self.routing_manager.stop()
        
        logger.info("Shutdown routing servicer")
    
    def _create_timestamp(self, dt: Optional[datetime] = None) -> Timestamp:
        """
        Create a Protobuf timestamp from a datetime object.
        
        Args:
            dt: Optional datetime object (default: current time)
            
        Returns:
            Protobuf Timestamp
        """
        dt = dt or datetime.now()
        ts = Timestamp()
        ts.FromDatetime(dt)
        return ts
    
    def _dict_to_struct(self, data: Dict[str, Any]) -> Struct:
        """
        Convert a Python dictionary to a Protobuf Struct.
        
        Args:
            data: Python dictionary
            
        Returns:
            Protobuf Struct
        """
        struct = Struct()
        struct.update(data)
        return struct
    
    def _struct_to_dict(self, struct: Struct) -> Dict[str, Any]:
        """
        Convert a Protobuf Struct to a Python dictionary.
        
        Args:
            struct: Protobuf Struct
            
        Returns:
            Python dictionary
        """
        return dict(struct)
    
    async def SelectBackend(
        self, 
        request: SelectBackendRequest, 
        context: grpc_aio.ServicerContext
    ) -> SelectBackendResponse:
        """
        Select the optimal backend for content.
        
        Args:
            request: SelectBackendRequest
            context: gRPC context
            
        Returns:
            SelectBackendResponse
        """
        try:
            # Ensure routing manager is initialized
            if self.routing_manager is None:
                await self.initialize()
            
            # Extract request parameters
            content_hash = request.content_hash if request.content_hash else None
            content_type = request.content_type
            content_size = request.content_size
            
            # Convert metadata struct to dict
            metadata = self._struct_to_dict(request.metadata) if request.HasField("metadata") else {}
            if content_hash:
                metadata["content_hash"] = content_hash
            
            # Extract other parameters
            strategy = request.strategy if request.strategy else None
            priority = request.priority if request.priority else None
            available_backends = list(request.available_backends) if request.available_backends else None
            
            # Extract client location
            client_location = None
            if request.HasField("client_location"):
                client_location = {
                    "lat": request.client_location.latitude,
                    "lon": request.client_location.longitude,
                    "region": request.client_location.region if request.client_location.region else None
                }
            
            # Select backend
            backend_id = await self.routing_manager.select_backend(
                content_type=content_type,
                content_size=content_size,
                metadata=metadata,
                available_backends=available_backends,
                strategy=strategy,
                priority=priority,
                client_location=client_location
            )
            
            # Get insights for additional information
            insights = await self.routing_manager.get_routing_insights()
            factor_weights = insights.get("factor_weights", {})
            backend_scores = insights.get("backend_scores", {})
            
            # Build response
            response = SelectBackendResponse()
            response.backend_id = backend_id
            response.score = backend_scores.get(backend_id, 0.9)
            response.factor_scores.update(factor_weights)
            
            # Add alternatives
            for alt_backend, alt_score in backend_scores.items():
                if alt_backend != backend_id:
                    alt = response.alternatives.add()
                    alt.backend_id = alt_backend
                    alt.score = alt_score
            
            # Set metadata
            response.request_id = request.request_id if request.HasField("request_id") else ""
            response.timestamp.CopyFrom(self._create_timestamp())
            
            return response
            
        except Exception as e:
            logger.error(f"Error selecting backend: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to select backend: {str(e)}")
            return SelectBackendResponse()
    
    async def RecordOutcome(
        self, 
        request: RecordOutcomeRequest, 
        context: grpc_aio.ServicerContext
    ) -> RecordOutcomeResponse:
        """
        Record the outcome of a routing decision.
        
        Args:
            request: RecordOutcomeRequest
            context: gRPC context
            
        Returns:
            RecordOutcomeResponse
        """
        try:
            # Ensure routing manager is initialized
            if self.routing_manager is None:
                await self.initialize()
            
            # Extract request parameters
            backend_id = request.backend_id
            success = request.success
            content_hash = request.content_hash if request.content_hash else None
            content_type = request.content_type if request.content_type else None
            content_size = request.content_size
            
            # Build content info
            content_info = {
                "content_hash": content_hash,
                "content_type": content_type,
                "size_bytes": content_size
            }
            
            # Record outcome
            await self.routing_manager.record_routing_outcome(
                backend_id=backend_id,
                content_info=content_info,
                success=success,
                duration_ms=request.duration_ms if request.duration_ms else None,
                error=request.error if request.error else None
            )
            
            # Build response
            response = RecordOutcomeResponse()
            response.success = True
            response.message = "Outcome recorded successfully"
            response.timestamp.CopyFrom(self._create_timestamp())
            
            return response
            
        except Exception as e:
            logger.error(f"Error recording outcome: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to record outcome: {str(e)}")
            
            response = RecordOutcomeResponse()
            response.success = False
            response.message = f"Error: {str(e)}"
            response.timestamp.CopyFrom(self._create_timestamp())
            return response
    
    async def GetInsights(
        self, 
        request: GetInsightsRequest, 
        context: grpc_aio.ServicerContext
    ) -> GetInsightsResponse:
        """
        Get insights about routing decisions.
        
        Args:
            request: GetInsightsRequest
            context: gRPC context
            
        Returns:
            GetInsightsResponse
        """
        try:
            # Ensure routing manager is initialized
            if self.routing_manager is None:
                await self.initialize()
            
            # Get insights from routing manager
            insights = await self.routing_manager.get_routing_insights()
            
            # Build response
            response = GetInsightsResponse()
            
            # Set factor weights
            response.factor_weights.update(insights.get("factor_weights", {}))
            
            # Set backend scores
            response.backend_scores.update(insights.get("backend_scores", {}))
            
            # Get success rates if metrics DB is available
            try:
                if hasattr(self.routing_manager, "metrics_db") and self.routing_manager.metrics_db:
                    # Set default time window if not provided
                    time_window_hours = request.time_window_hours if request.time_window_hours > 0 else 24
                    
                    # Get success rates
                    success_rates = self.routing_manager.metrics_db.get_backend_success_rates(
                        time_window_hours=time_window_hours,
                        content_type=request.content_type if request.content_type else None
                    )
                    response.backend_success_rates.update(success_rates)
                    
                    # Get content type distribution
                    content_type_dist = self.routing_manager.metrics_db.get_content_type_backend_distribution(
                        time_window_hours=time_window_hours
                    )
                    # Convert to serializable format (keys must be strings)
                    serializable_dist = {}
                    for content_type, backends in content_type_dist.items():
                        serializable_dist[content_type] = {str(k): v for k, v in backends.items()}
                    response.content_type_distribution.update(serializable_dist)
                    
                    # Get backend usage stats
                    usage_stats = self.routing_manager.metrics_db.get_backend_usage_stats(
                        time_window_hours=time_window_hours
                    )
                    # Convert to serializable format
                    serializable_stats = {k: dict(v) for k, v in usage_stats.items()}
                    response.backend_usage_stats.update(serializable_stats)
                    
                    # Get latency stats
                    latency_stats = self.routing_manager.metrics_db.get_backend_latency_stats(
                        time_window_hours=time_window_hours
                    )
                    # Convert to serializable format
                    serializable_latency = {k: dict(v) for k, v in latency_stats.items()}
                    response.latency_stats.update(serializable_latency)
            except Exception as metrics_err:
                logger.warning(f"Error getting metrics: {metrics_err}")
            
            # Set timestamp
            response.timestamp.CopyFrom(self._create_timestamp())
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting insights: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to get insights: {str(e)}")
            return GetInsightsResponse()
    
    async def StreamMetrics(
        self, 
        request: StreamMetricsRequest, 
        context: grpc_aio.ServicerContext
    ) -> AsyncGenerator[MetricsUpdate, None]:
        """
        Stream routing metrics updates.
        
        Args:
            request: StreamMetricsRequest
            context: gRPC context
            
        Yields:
            MetricsUpdate messages
        """
        # Register this stream
        self._metrics_streams.add(context)
        
        try:
            # Ensure routing manager is initialized
            if self.routing_manager is None:
                await self.initialize()
            
            # Set update interval
            interval = max(1, request.update_interval_seconds)
            
            # Determine metrics to include
            include_backends = request.include_backends
            include_content_types = request.include_content_types
            metrics_types = list(request.metrics_types) if request.metrics_types else None
            
            # Keep streaming until context is cancelled
            while not context.done() and not self._shutdown_event.is_set():
                try:
                    # Collect metrics
                    metrics = {}
                    
                    # Get insights from routing manager
                    insights = await self.routing_manager.get_routing_insights()
                    metrics["factor_weights"] = insights.get("factor_weights", {})
                    metrics["backend_scores"] = insights.get("backend_scores", {})
                    
                    # Get metrics from metrics DB if available
                    if hasattr(self.routing_manager, "metrics_db") and self.routing_manager.metrics_db:
                        metrics_db = self.routing_manager.metrics_db
                        
                        # Get success rates
                        if not metrics_types or "success_rates" in metrics_types:
                            success_rates = metrics_db.get_backend_success_rates(time_window_hours=1)
                            metrics["success_rates"] = success_rates
                        
                        # Get backend usage stats
                        if not metrics_types or "usage_stats" in metrics_types:
                            usage_stats = metrics_db.get_backend_usage_stats(time_window_hours=1)
                            # Convert to serializable format
                            metrics["usage_stats"] = {k: dict(v) for k, v in usage_stats.items()}
                        
                        # Get latency stats
                        if not metrics_types or "latency_stats" in metrics_types:
                            latency_stats = metrics_db.get_backend_latency_stats(time_window_hours=1)
                            # Convert to serializable format
                            metrics["latency_stats"] = {k: dict(v) for k, v in latency_stats.items()}
                        
                        # Get content type distribution
                        if include_content_types and (not metrics_types or "content_distribution" in metrics_types):
                            content_type_dist = metrics_db.get_content_type_backend_distribution(time_window_hours=1)
                            # Convert to serializable format
                            serializable_dist = {}
                            for content_type, backends in content_type_dist.items():
                                serializable_dist[content_type] = {str(k): v for k, v in backends.items()}
                            metrics["content_distribution"] = serializable_dist
                    
                    # Create update message
                    update = MetricsUpdate()
                    update.metrics.update(metrics)
                    
                    # Set status based on metrics
                    update.status = MetricsUpdate.NORMAL
                    # Check for warning conditions
                    if any(rate < 0.9 for rate in metrics.get("success_rates", {}).values()):
                        update.status = MetricsUpdate.WARNING
                    # Check for critical conditions
                    if any(rate < 0.7 for rate in metrics.get("success_rates", {}).values()):
                        update.status = MetricsUpdate.CRITICAL
                    
                    # Set timestamp
                    update.timestamp.CopyFrom(self._create_timestamp())
                    
                    # Send update
                    yield update
                    
                    # Wait for next update
                    await asyncio.sleep(interval)
                    
                except asyncio.CancelledError:
                    # Stream was cancelled
                    break
                except Exception as update_err:
                    logger.error(f"Error generating metrics update: {update_err}", exc_info=True)
                    
                    # Create error update
                    error_update = MetricsUpdate()
                    error_update.metrics.update({"error": str(update_err)})
                    error_update.status = MetricsUpdate.WARNING
                    error_update.timestamp.CopyFrom(self._create_timestamp())
                    
                    # Send error update
                    yield error_update
                    
                    # Wait before retrying
                    await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            # Stream was cancelled
            pass
        except Exception as e:
            logger.error(f"Error streaming metrics: {e}", exc_info=True)
        finally:
            # Unregister this stream
            self._metrics_streams.discard(context)


class GRPCServer:
    """
    gRPC server for the optimized data routing system.
    
    This server provides a high-performance, language-independent
    interface to the optimized data routing functionality.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        routing_manager: Optional["RoutingManager"] = None,
        max_workers: int = 10,
        use_ssl: bool = False,
        ssl_cert_path: Optional[str] = None,
        ssl_key_path: Optional[str] = None,
        enable_auth: bool = False,
        auth_manager: Optional["AuthenticationManager"] = None,
        jwt_secret: Optional[str] = None,
        users_file: Optional[str] = None
    ):
        """
        Initialize the gRPC server.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
            routing_manager: Optional routing manager instance
            max_workers: Maximum number of worker threads
            use_ssl: Whether to use SSL/TLS
            ssl_cert_path: Path to SSL certificate file (required if use_ssl is True)
            ssl_key_path: Path to SSL key file (required if use_ssl is True)
            enable_auth: Whether to enable authentication and authorization
            auth_manager: Optional authentication manager instance
            jwt_secret: Optional JWT secret for auth manager
            users_file: Optional path to users configuration file
        """
        if not GRPC_AVAILABLE:
            raise ImportError(
                "gRPC is not available. Install with 'pip install grpcio grpcio-tools'"
            )
        
        if not GRPC_GENERATED_CODE_AVAILABLE:
            raise ImportError(
                "gRPC generated code is not available. Run 'bin/generate_grpc_code.py' first"
            )
        
        self.host = host
        self.port = port
        self.routing_manager = routing_manager
        self.max_workers = max_workers
        self.use_ssl = use_ssl
        self.ssl_cert_path = ssl_cert_path
        self.ssl_key_path = ssl_key_path
        self.enable_auth = enable_auth
        
        # Validate SSL settings
        if use_ssl and (not ssl_cert_path or not ssl_key_path):
            raise ValueError("SSL certificate and key paths are required when use_ssl is True")
        
        # Initialize authentication manager if enabled
        self.auth_manager = None
        if enable_auth:
            try:
                from ipfs_kit_py.routing.grpc_auth import AuthenticationManager
                self.auth_manager = auth_manager or AuthenticationManager(
                    jwt_secret=jwt_secret,
                    users_file=users_file
                )
            except ImportError:
                logger.warning("Authentication libraries not available, disabling authentication")
                self.enable_auth = False
        
        # Initialize server and servicer
        self.server = None
        self.servicer = None
        
        logger.info(f"Initialized gRPC server for routing on {host}:{port}")
    
    async def start(self) -> None:
        """Start the gRPC server."""
        try:
            # Create servicer
            self.servicer = RoutingServicer(self.routing_manager)
            
            # Initialize servicer
            await self.servicer.initialize()
            
            # Create server
            self.server = grpc_aio.server(
                futures.ThreadPoolExecutor(max_workers=self.max_workers)
            )
            
            # Add authentication interceptor if enabled
            if self.enable_auth and self.auth_manager:
                try:
                    from ipfs_kit_py.routing.grpc_auth import AsyncAuthInterceptor
                    auth_interceptor = AsyncAuthInterceptor(self.auth_manager)
                    self.server.add_interceptor(auth_interceptor)
                    logger.info("Added authentication interceptor to gRPC server")
                except ImportError:
                    logger.warning("Could not import auth interceptor, authentication disabled")
            
            # Add servicer to server
            add_RoutingServiceServicer_to_server(self.servicer, self.server)
            
            # Set up SSL if enabled
            if self.use_ssl:
                with open(self.ssl_key_path, 'rb') as key_file:
                    private_key = key_file.read()
                with open(self.ssl_cert_path, 'rb') as cert_file:
                    certificate_chain = cert_file.read()
                
                server_credentials = grpc.ssl_server_credentials(
                    [(private_key, certificate_chain)]
                )
                address = f"{self.host}:{self.port}"
                port = self.server.add_secure_port(address, server_credentials)
            else:
                address = f"{self.host}:{self.port}"
                port = self.server.add_insecure_port(address)
            
            # Start server
            await self.server.start()
            
            logger.info(f"gRPC server started on {address}")
            
        except Exception as e:
            logger.error(f"Error starting gRPC server: {e}", exc_info=True)
            # Clean up if server was created
            if self.server:
                await self.server.stop(0)
                self.server = None
            raise
    
    async def stop(self) -> None:
        """Stop the gRPC server."""
        if self.server:
            # Stop servicer
            if self.servicer:
                await self.servicer.shutdown()
                self.servicer = None
            
            # Stop server
            await self.server.stop(0)
            self.server = None
            
            logger.info("gRPC server stopped")
    
    async def wait_for_termination(self) -> None:
        """Wait for the server to terminate."""
        if self.server:
            await self.server.wait_for_termination()


async def run_server(
    host: str = "127.0.0.1",
    port: int = 50051,
    routing_manager: Optional["RoutingManager"] = None,
    max_workers: int = 10,
    use_ssl: bool = False,
    ssl_cert_path: Optional[str] = None,
    ssl_key_path: Optional[str] = None
) -> GRPCServer:
    """
    Run the gRPC server.
    
    Args:
        host: Host address to bind to
        port: Port to listen on
        routing_manager: Optional routing manager instance
        max_workers: Maximum number of worker threads
        use_ssl: Whether to use SSL/TLS
        ssl_cert_path: Path to SSL certificate file (required if use_ssl is True)
        ssl_key_path: Path to SSL key file (required if use_ssl is True)
    
    Returns:
        GRPCServer instance
    """
    server = GRPCServer(
        host=host,
        port=port,
        routing_manager=routing_manager,
        max_workers=max_workers,
        use_ssl=use_ssl,
        ssl_cert_path=ssl_cert_path,
        ssl_key_path=ssl_key_path
    )
    
    await server.start()
    return server