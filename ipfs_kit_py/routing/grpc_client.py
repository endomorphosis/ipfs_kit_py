#!/usr/bin/env python3
"""
gRPC Routing Client

This module provides a client interface for the optimized data routing gRPC service.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
from pathlib import Path

# Add parent directory to path to allow imports
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    import grpc
    import grpc.experimental.aio as grpc_aio
    from google.protobuf.struct_pb2 import Struct
    from google.protobuf.timestamp_pb2 import Timestamp
    from google.protobuf.json_format import MessageToDict
    
    # Import generated code
    from ipfs_kit_py.routing.grpc.routing_pb2 import (
        SelectBackendRequest, SelectBackendResponse,
        RecordOutcomeRequest, RecordOutcomeResponse,
        GetInsightsRequest, GetInsightsResponse,
        StreamMetricsRequest, MetricsUpdate
    )
    from ipfs_kit_py.routing.grpc.routing_pb2_grpc import RoutingServiceStub
    
    # Import authentication
    from ipfs_kit_py.routing.grpc_auth import secure_channel_credentials
    
    GRPC_AVAILABLE = True
except ImportError as e:
    print(f"Error importing gRPC modules: {e}")
    GRPC_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

class RoutingClient:
    """
    Client for the optimized data routing gRPC service.
    
    This client provides methods to interact with the routing service,
    including selecting backends, recording outcomes, and getting insights.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 50051,
        use_ssl: bool = False,
        ssl_cert_path: Optional[str] = None,
        auth_token: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize the routing client.
        
        Args:
            host: Host address of the gRPC server
            port: Port of the gRPC server
            use_ssl: Whether to use SSL/TLS
            ssl_cert_path: Path to SSL certificate file
            auth_token: Optional JWT token for authentication
            api_key: Optional API key for authentication
            username: Optional username for Basic authentication
            password: Optional password for Basic authentication
        """
        if not GRPC_AVAILABLE:
            raise ImportError(
                "gRPC is not available. Install with 'pip install grpcio grpcio-tools'"
            )
        
        self.host = host
        self.port = port
        self.address = f"{host}:{port}"
        
        # Set up SSL
        self.use_ssl = use_ssl
        self.ssl_cert_path = ssl_cert_path
        self.ssl_credentials = None
        
        if use_ssl and ssl_cert_path:
            with open(ssl_cert_path, 'rb') as f:
                trusted_certs = f.read()
            self.ssl_credentials = grpc.ssl_channel_credentials(
                root_certificates=trusted_certs
            )
        
        # Set up authentication
        self.auth_token = auth_token
        self.api_key = api_key
        self.username = username
        self.password = password
        
        # Create channel and stub
        self.channel = None
        self.stub = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self) -> None:
        """Connect to the gRPC server."""
        if self.channel is not None:
            return
        
        # Create credentials
        if self.use_ssl or self.auth_token or self.api_key or (self.username and self.password):
            credentials = secure_channel_credentials(
                jwt_token=self.auth_token,
                api_key=self.api_key,
                username=self.username,
                password=self.password,
                ssl_credentials=self.ssl_credentials
            )
            self.channel = grpc_aio.secure_channel(self.address, credentials)
        else:
            self.channel = grpc_aio.insecure_channel(self.address)
        
        # Create stub
        self.stub = RoutingServiceStub(self.channel)
        
        logger.debug(f"Connected to gRPC server at {self.address}")
    
    async def close(self) -> None:
        """Close the connection to the gRPC server."""
        if self.channel is not None:
            await self.channel.close()
            self.channel = None
            self.stub = None
            logger.debug(f"Disconnected from gRPC server at {self.address}")
    
    @staticmethod
    def _dict_to_struct(data: Dict[str, Any]) -> Struct:
        """Convert a Python dictionary to a Protobuf Struct."""
        struct = Struct()
        struct.update(data)
        return struct
    
    @staticmethod
    def _create_timestamp(dt: Optional[datetime] = None) -> Timestamp:
        """Create a Protobuf timestamp from a datetime object."""
        dt = dt or datetime.now()
        ts = Timestamp()
        ts.FromDatetime(dt)
        return ts
    
    async def select_backend(
        self,
        content_type: str,
        content_size: int,
        content_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        available_backends: Optional[List[str]] = None,
        client_location: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select the optimal backend for content.
        
        Args:
            content_type: Content MIME type
            content_size: Content size in bytes
            content_hash: Optional content hash
            metadata: Additional metadata
            strategy: Routing strategy
            priority: Routing priority
            available_backends: Available backends
            client_location: Client location as dictionary with lat, lon, region
            request_id: Unique request ID
            
        Returns:
            Dictionary with selected backend and metadata
        """
        await self.connect()
        
        # Create request
        request = SelectBackendRequest(
            content_type=content_type,
            content_size=content_size
        )
        
        # Set optional fields
        if content_hash:
            request.content_hash = content_hash
        
        if metadata:
            request.metadata.update(metadata)
        
        if strategy:
            request.strategy = strategy
        
        if priority:
            request.priority = priority
        
        if available_backends:
            request.available_backends.extend(available_backends)
        
        if client_location:
            request.client_location.latitude = client_location.get("lat", 0)
            request.client_location.longitude = client_location.get("lon", 0)
            if "region" in client_location:
                request.client_location.region = client_location["region"]
        
        if request_id:
            request.request_id = request_id
        
        # Set timestamp
        request.timestamp.CopyFrom(self._create_timestamp())
        
        # Call RPC
        response = await self.stub.SelectBackend(request)
        
        # Convert to dictionary
        result = {
            "backend_id": response.backend_id,
            "score": response.score,
            "factor_scores": MessageToDict(response.factor_scores),
            "alternatives": [
                {
                    "backend_id": alt.backend_id,
                    "score": alt.score
                }
                for alt in response.alternatives
            ],
            "request_id": response.request_id,
            "timestamp": response.timestamp.ToDatetime()
        }
        
        return result
    
    async def record_outcome(
        self,
        backend_id: str,
        success: bool,
        content_hash: Optional[str] = None,
        content_type: Optional[str] = None,
        content_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record the outcome of a routing decision.
        
        Args:
            backend_id: Backend that was used
            success: Whether the operation was successful
            content_hash: Content hash
            content_type: Content MIME type
            content_size: Content size in bytes
            duration_ms: Operation duration in milliseconds
            error: Error message if not successful
            
        Returns:
            Dictionary with outcome recording result
        """
        await self.connect()
        
        # Create request
        request = RecordOutcomeRequest(
            backend_id=backend_id,
            success=success
        )
        
        # Set optional fields
        if content_hash:
            request.content_hash = content_hash
        
        if content_type:
            request.content_type = content_type
        
        if content_size is not None:
            request.content_size = content_size
        
        if duration_ms is not None:
            request.duration_ms = duration_ms
        
        if error:
            request.error = error
        
        # Set timestamp
        request.timestamp.CopyFrom(self._create_timestamp())
        
        # Call RPC
        response = await self.stub.RecordOutcome(request)
        
        # Convert to dictionary
        result = {
            "success": response.success,
            "message": response.message,
            "timestamp": response.timestamp.ToDatetime()
        }
        
        return result
    
    async def get_insights(
        self,
        backend_id: Optional[str] = None,
        content_type: Optional[str] = None,
        time_window_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get insights about routing decisions.
        
        Args:
            backend_id: Optional focus on specific backend
            content_type: Optional focus on specific content type
            time_window_hours: Optional time window in hours
            
        Returns:
            Dictionary with routing insights
        """
        await self.connect()
        
        # Create request
        request = GetInsightsRequest()
        
        # Set optional fields
        if backend_id:
            request.backend_id = backend_id
        
        if content_type:
            request.content_type = content_type
        
        if time_window_hours is not None:
            request.time_window_hours = time_window_hours
        
        # Call RPC
        response = await self.stub.GetInsights(request)
        
        # Convert to dictionary
        result = {
            "factor_weights": MessageToDict(response.factor_weights),
            "backend_scores": MessageToDict(response.backend_scores),
            "backend_success_rates": MessageToDict(response.backend_success_rates),
            "content_type_distribution": MessageToDict(response.content_type_distribution),
            "backend_usage_stats": MessageToDict(response.backend_usage_stats),
            "latency_stats": MessageToDict(response.latency_stats),
            "timestamp": response.timestamp.ToDatetime()
        }
        
        return result
    
    async def stream_metrics(
        self,
        update_interval_seconds: int = 5,
        metrics_types: Optional[List[str]] = None,
        include_backends: bool = True,
        include_content_types: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream routing metrics updates.
        
        Args:
            update_interval_seconds: Update interval in seconds
            metrics_types: Types of metrics to stream
            include_backends: Whether to include backend metrics
            include_content_types: Whether to include content type metrics
            
        Yields:
            Dictionaries with metrics updates
        """
        await self.connect()
        
        # Create request
        request = StreamMetricsRequest(
            update_interval_seconds=update_interval_seconds,
            include_backends=include_backends,
            include_content_types=include_content_types
        )
        
        # Set metrics types
        if metrics_types:
            request.metrics_types.extend(metrics_types)
        
        # Call streaming RPC
        stream = self.stub.StreamMetrics(request)
        
        try:
            async for update in stream:
                # Convert to dictionary
                result = {
                    "metrics": MessageToDict(update.metrics),
                    "status": MetricsUpdate.SystemStatus.Name(update.status),
                    "timestamp": update.timestamp.ToDatetime()
                }
                
                yield result
                
        except grpc.RpcError as e:
            logger.error(f"RPC error: {e.details()}")
        except asyncio.CancelledError:
            # Stream was cancelled
            raise
        finally:
            try:
                await stream.cancel()
            except:
                pass


async def example_usage():
    """Example usage of the routing client."""
    # Create client
    async with RoutingClient(host="localhost", port=50051) as client:
        # Select backend
        backend = await client.select_backend(
            content_type="application/json",
            content_size=1024,
            metadata={"user_id": "user123"},
            available_backends=["ipfs", "s3", "filecoin"]
        )
        print(f"Selected backend: {backend['backend_id']}")
        
        # Record outcome
        outcome = await client.record_outcome(
            backend_id=backend["backend_id"],
            success=True,
            content_type="application/json",
            content_size=1024,
            duration_ms=250
        )
        print(f"Recorded outcome: {outcome['success']}")
        
        # Get insights
        insights = await client.get_insights()
        print(f"Backend scores: {insights['backend_scores']}")
        
        # Stream metrics for 20 seconds
        print("Streaming metrics for 20 seconds...")
        start_time = datetime.now()
        async for update in client.stream_metrics():
            print(f"Metrics update: {update['status']}")
            
            # Stop after 20 seconds
            if (datetime.now() - start_time).total_seconds() > 20:
                break


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run example
    asyncio.run(example_usage())