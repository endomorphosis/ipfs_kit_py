#!/usr/bin/env python3
"""
Standalone gRPC Server for Routing Service

This module provides a standalone implementation of the gRPC routing service
that can work independently without complex dependencies.
"""

import os
import time
import json
import logging
import asyncio
import random
import threading
from concurrent import futures
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, AsyncGenerator

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
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import gRPC generated code
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
    logger.error("gRPC generated code not available. Run generate_grpc_code.py first.")
    GRPC_GENERATED_CODE_AVAILABLE = False


class SimpleRoutingDatabase:
    """
    Simple in-memory database for storing routing data.
    
    This is a simplified implementation for demonstration purposes.
    """
    
    def __init__(self):
        """Initialize the database."""
        self.backend_metrics = {}
        self.backend_scores = {}
        self.routing_history = []
        self.outcome_history = []
        self.lock = threading.RLock()
    
    def update_backend_metrics(self, backend_id: str, metrics: Dict[str, Any]) -> None:
        """Update metrics for a backend."""
        with self.lock:
            if backend_id not in self.backend_metrics:
                self.backend_metrics[backend_id] = {}
            self.backend_metrics[backend_id].update(metrics)
            self.backend_metrics[backend_id]["updated_at"] = time.time()
    
    def update_backend_score(self, backend_id: str, score: float) -> None:
        """Update score for a backend."""
        with self.lock:
            self.backend_scores[backend_id] = score
    
    def add_routing_decision(self, decision: Dict[str, Any]) -> None:
        """Add a routing decision to history."""
        with self.lock:
            decision["timestamp"] = time.time()
            self.routing_history.append(decision)
            
            # Limit history size
            if len(self.routing_history) > 1000:
                self.routing_history = self.routing_history[-1000:]
    
    def add_routing_outcome(self, outcome: Dict[str, Any]) -> None:
        """Add a routing outcome to history."""
        with self.lock:
            outcome["timestamp"] = time.time()
            self.outcome_history.append(outcome)
            
            # Limit history size
            if len(self.outcome_history) > 1000:
                self.outcome_history = self.outcome_history[-1000:]
            
            # Update success rates
            self._update_success_rates(outcome)
    
    def _update_success_rates(self, outcome: Dict[str, Any]) -> None:
        """Update success rates based on a new outcome."""
        backend_id = outcome["backend_id"]
        success = outcome["success"]
        
        if backend_id not in self.backend_metrics:
            self.backend_metrics[backend_id] = {}
        
        metrics = self.backend_metrics[backend_id]
        
        # Update success count
        if "success_count" not in metrics:
            metrics["success_count"] = 0
        if "total_count" not in metrics:
            metrics["total_count"] = 0
        
        if success:
            metrics["success_count"] += 1
        metrics["total_count"] += 1
        
        # Calculate success rate
        metrics["success_rate"] = metrics["success_count"] / metrics["total_count"]
    
    def get_backend_metrics(self, backend_id: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a backend or all backends."""
        with self.lock:
            if backend_id is not None:
                return self.backend_metrics.get(backend_id, {})
            return self.backend_metrics
    
    def get_backend_scores(self) -> Dict[str, float]:
        """Get scores for all backends."""
        with self.lock:
            return self.backend_scores
    
    def get_backend_success_rates(self, time_window_hours: int = 24) -> Dict[str, float]:
        """Get success rates for all backends within a time window."""
        with self.lock:
            result = {}
            cutoff_time = time.time() - (time_window_hours * 3600)
            
            # Filter outcomes within time window
            recent_outcomes = [
                outcome for outcome in self.outcome_history
                if outcome["timestamp"] > cutoff_time
            ]
            
            # Calculate success rates
            for backend_id in set(outcome["backend_id"] for outcome in recent_outcomes):
                backend_outcomes = [o for o in recent_outcomes if o["backend_id"] == backend_id]
                if backend_outcomes:
                    success_count = sum(1 for o in backend_outcomes if o["success"])
                    result[backend_id] = success_count / len(backend_outcomes)
                else:
                    result[backend_id] = 0.0
            
            return result
    
    def get_content_type_distribution(self, time_window_hours: int = 24) -> Dict[str, Dict[str, int]]:
        """Get content type distribution within a time window."""
        with self.lock:
            result = {}
            cutoff_time = time.time() - (time_window_hours * 3600)
            
            # Filter decisions within time window
            recent_decisions = [
                decision for decision in self.routing_history
                if decision["timestamp"] > cutoff_time
            ]
            
            # Calculate distribution
            for decision in recent_decisions:
                content_type = decision.get("content_type", "unknown")
                backend_id = decision["backend_id"]
                
                if content_type not in result:
                    result[content_type] = {}
                
                if backend_id not in result[content_type]:
                    result[content_type][backend_id] = 0
                
                result[content_type][backend_id] += 1
            
            return result
    
    def get_usage_stats(self, time_window_hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics within a time window."""
        with self.lock:
            result = {}
            cutoff_time = time.time() - (time_window_hours * 3600)
            
            # Filter decisions within time window
            recent_decisions = [
                decision for decision in self.routing_history
                if decision["timestamp"] > cutoff_time
            ]
            
            # Calculate usage stats
            for backend_id in set(decision["backend_id"] for decision in recent_decisions):
                backend_decisions = [d for d in recent_decisions if d["backend_id"] == backend_id]
                
                result[backend_id] = {
                    "request_count": len(backend_decisions),
                    "avg_content_size": sum(d.get("content_size", 0) for d in backend_decisions) / len(backend_decisions) if backend_decisions else 0,
                    "total_size": sum(d.get("content_size", 0) for d in backend_decisions)
                }
            
            return result
    
    def get_latency_stats(self, time_window_hours: int = 24) -> Dict[str, Dict[str, float]]:
        """Get latency statistics within a time window."""
        with self.lock:
            result = {}
            cutoff_time = time.time() - (time_window_hours * 3600)
            
            # Filter outcomes within time window
            recent_outcomes = [
                outcome for outcome in self.outcome_history
                if outcome["timestamp"] > cutoff_time and "duration_ms" in outcome
            ]
            
            # Calculate latency stats
            for backend_id in set(outcome["backend_id"] for outcome in recent_outcomes):
                backend_outcomes = [o for o in recent_outcomes if o["backend_id"] == backend_id]
                
                if backend_outcomes:
                    durations = [o["duration_ms"] for o in backend_outcomes]
                    result[backend_id] = {
                        "min_ms": min(durations),
                        "max_ms": max(durations),
                        "avg_ms": sum(durations) / len(durations),
                        "count": len(durations)
                    }
            
            return result


class SimpleRoutingManager:
    """
    Simple routing manager for demonstration purposes.
    
    This is a simplified implementation that doesn't rely on the complex
    dependencies of the full routing manager.
    """
    
    def __init__(self):
        """Initialize the routing manager."""
        self.db = SimpleRoutingDatabase()
        self.available_backends = ["ipfs", "filecoin", "s3"]
        self.factor_weights = {
            "performance": 0.4,
            "cost": 0.3,
            "reliability": 0.2,
            "geo_proximity": 0.1
        }
        
        # Initialize with some default metrics
        for backend_id in self.available_backends:
            self.db.update_backend_metrics(backend_id, {
                "status": "active",
                "latency_ms": random.uniform(50, 200),
                "throughput_mbps": random.uniform(10, 100),
                "cost_per_gb": random.uniform(0.01, 0.1),
                "success_rate": random.uniform(0.9, 0.99),
            })
            self.db.update_backend_score(backend_id, random.uniform(0.7, 0.95))
    
    async def select_backend(
        self,
        content_type: str,
        content_size: int,
        metadata: Optional[Dict[str, Any]] = None,
        available_backends: Optional[List[str]] = None,
        strategy: Optional[str] = None,
        priority: Optional[str] = None,
        client_location: Optional[Dict[str, Any]] = None
    ) -> str:
        """Select the optimal backend for content."""
        # Use defaults if not provided
        if available_backends is None or not available_backends:
            available_backends = self.available_backends
        
        # Get scores for each backend
        scores = {}
        for backend_id in available_backends:
            metrics = self.db.get_backend_metrics(backend_id)
            
            # Calculate score components
            performance_score = 1.0 - min(1.0, metrics.get("latency_ms", 100) / 200)
            cost_score = 1.0 - min(1.0, metrics.get("cost_per_gb", 0.05) / 0.1)
            reliability_score = metrics.get("success_rate", 0.9)
            geo_score = 0.8  # Default if no location info
            
            # Adjust geo score if client location is provided
            if client_location:
                # Simplified geo score calculation
                geo_score = random.uniform(0.7, 0.95)
            
            # Calculate weighted score
            score = (
                performance_score * self.factor_weights["performance"] +
                cost_score * self.factor_weights["cost"] +
                reliability_score * self.factor_weights["reliability"] +
                geo_score * self.factor_weights["geo_proximity"]
            )
            
            scores[backend_id] = score
        
        # Select backend with highest score
        if not scores:
            backend_id = self.available_backends[0]  # Fallback
        else:
            backend_id = max(scores.items(), key=lambda x: x[1])[0]
        
        # Record decision in database
        self.db.add_routing_decision({
            "backend_id": backend_id,
            "content_type": content_type,
            "content_size": content_size,
            "strategy": strategy or "optimal",
            "priority": priority or "balanced",
            "score": scores.get(backend_id, 0.0),
            "client_location": client_location
        })
        
        return backend_id
    
    async def record_routing_outcome(
        self,
        backend_id: str,
        content_info: Dict[str, Any],
        success: bool,
        duration_ms: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """Record the outcome of a routing decision."""
        # Record outcome in database
        self.db.add_routing_outcome({
            "backend_id": backend_id,
            "content_type": content_info.get("content_type"),
            "content_size": content_info.get("size_bytes", 0),
            "success": success,
            "duration_ms": duration_ms,
            "error": error
        })
    
    async def get_routing_insights(self) -> Dict[str, Any]:
        """Get insights about routing decisions."""
        return {
            "factor_weights": self.factor_weights,
            "backend_scores": self.db.get_backend_scores(),
            "backend_metrics": self.db.get_backend_metrics(),
            "backend_success_rates": self.db.get_backend_success_rates(),
            "content_type_distribution": self.db.get_content_type_distribution(),
            "usage_stats": self.db.get_usage_stats(),
            "latency_stats": self.db.get_latency_stats()
        }


class RoutingServicer(RoutingServiceServicer):
    """Implementation of the RoutingService gRPC service."""
    
    def __init__(self):
        """Initialize the RoutingServicer."""
        self.routing_manager = SimpleRoutingManager()
        self._metrics_streams = set()
        self._shutdown_event = threading.Event()
    
    async def shutdown(self) -> None:
        """Shutdown the servicer."""
        self._shutdown_event.set()
        
        # Close all streaming connections
        for stream in self._metrics_streams:
            try:
                await stream.cancel()
            except Exception:
                pass
        
        logger.info("Shutdown routing servicer")
    
    def _create_timestamp(self, dt: Optional[datetime] = None) -> Timestamp:
        """Create a Protobuf timestamp from a datetime object."""
        dt = dt or datetime.now()
        ts = Timestamp()
        ts.FromDatetime(dt)
        return ts
    
    def _dict_to_struct(self, data: Dict[str, Any]) -> Struct:
        """Convert a Python dictionary to a Protobuf Struct."""
        struct = Struct()
        struct.update(data)
        return struct
    
    def _struct_to_dict(self, struct: Struct) -> Dict[str, Any]:
        """Convert a Protobuf Struct to a Python dictionary."""
        return dict(struct)
    
    async def SelectBackend(
        self, 
        request: SelectBackendRequest, 
        context: grpc_aio.ServicerContext
    ) -> SelectBackendResponse:
        """Select the optimal backend for content."""
        try:
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
        """Record the outcome of a routing decision."""
        try:
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
        """Get insights about routing decisions."""
        try:
            # Get time window
            time_window_hours = request.time_window_hours if request.time_window_hours > 0 else 24
            
            # Get insights from routing manager
            insights = await self.routing_manager.get_routing_insights()
            
            # Build response
            response = GetInsightsResponse()
            
            # Set factor weights
            response.factor_weights.update(insights.get("factor_weights", {}))
            
            # Set backend scores
            response.backend_scores.update(insights.get("backend_scores", {}))
            
            # Set success rates
            response.backend_success_rates.update(insights.get("backend_success_rates", {}))
            
            # Set content type distribution
            content_type_dist = insights.get("content_type_distribution", {})
            # Convert to serializable format
            serializable_dist = {}
            for content_type, backends in content_type_dist.items():
                serializable_dist[content_type] = {str(k): v for k, v in backends.items()}
            response.content_type_distribution.update(serializable_dist)
            
            # Set backend usage stats
            usage_stats = insights.get("usage_stats", {})
            # Convert to serializable format
            serializable_stats = {k: dict(v) for k, v in usage_stats.items()}
            response.backend_usage_stats.update(serializable_stats)
            
            # Set latency stats
            latency_stats = insights.get("latency_stats", {})
            # Convert to serializable format
            serializable_latency = {k: dict(v) for k, v in latency_stats.items()}
            response.latency_stats.update(serializable_latency)
            
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
        """Stream routing metrics updates."""
        # Register this stream
        self._metrics_streams.add(context)
        
        try:
            # Set update interval
            interval = max(1, request.update_interval_seconds)
            
            # Determine metrics to include
            include_backends = request.include_backends
            include_content_types = request.include_content_types
            metrics_types = list(request.metrics_types) if request.metrics_types else None
            
            # Keep streaming until context is cancelled
            while not context.done() and not self._shutdown_event.is_set():
                try:
                    # Get insights
                    insights = await self.routing_manager.get_routing_insights()
                    
                    # Create metrics dictionary
                    metrics = {}
                    
                    # Add relevant metrics based on request
                    if not metrics_types or "factor_weights" in metrics_types:
                        metrics["factor_weights"] = insights.get("factor_weights", {})
                    
                    if not metrics_types or "backend_scores" in metrics_types:
                        metrics["backend_scores"] = insights.get("backend_scores", {})
                    
                    if not metrics_types or "success_rates" in metrics_types:
                        metrics["success_rates"] = insights.get("backend_success_rates", {})
                    
                    if not metrics_types or "latency_stats" in metrics_types:
                        metrics["latency_stats"] = insights.get("latency_stats", {})
                    
                    if include_content_types and (not metrics_types or "content_distribution" in metrics_types):
                        metrics["content_distribution"] = insights.get("content_type_distribution", {})
                    
                    # Create update message
                    update = MetricsUpdate()
                    update.metrics.update(metrics)
                    
                    # Determine system status based on success rates
                    success_rates = insights.get("backend_success_rates", {})
                    
                    update.status = MetricsUpdate.NORMAL
                    # Check for warning conditions
                    if any(rate < 0.9 for rate in success_rates.values()):
                        update.status = MetricsUpdate.WARNING
                    # Check for critical conditions
                    if any(rate < 0.7 for rate in success_rates.values()):
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


class StandaloneGRPCServer:
    """
    Standalone gRPC server for the optimized data routing system.
    
    This server provides a high-performance, language-independent
    interface to the optimized data routing functionality without
    complex dependencies.
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50051,
        max_workers: int = 10,
        use_ssl: bool = False,
        ssl_cert_path: Optional[str] = None,
        ssl_key_path: Optional[str] = None
    ):
        """
        Initialize the gRPC server.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
            max_workers: Maximum number of worker threads
            use_ssl: Whether to use SSL/TLS
            ssl_cert_path: Path to SSL certificate file (required if use_ssl is True)
            ssl_key_path: Path to SSL key file (required if use_ssl is True)
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
        self.max_workers = max_workers
        self.use_ssl = use_ssl
        self.ssl_cert_path = ssl_cert_path
        self.ssl_key_path = ssl_key_path
        
        # Validate SSL settings
        if use_ssl and (not ssl_cert_path or not ssl_key_path):
            raise ValueError("SSL certificate and key paths are required when use_ssl is True")
        
        # Initialize server and servicer
        self.server = None
        self.servicer = None
        
        logger.info(f"Initialized standalone gRPC server on {host}:{port}")
    
    async def start(self) -> None:
        """Start the gRPC server."""
        try:
            # Create servicer
            self.servicer = RoutingServicer()
            
            # Create server
            self.server = grpc_aio.server(
                futures.ThreadPoolExecutor(max_workers=self.max_workers)
            )
            
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
    max_workers: int = 10,
    use_ssl: bool = False,
    ssl_cert_path: Optional[str] = None,
    ssl_key_path: Optional[str] = None
) -> StandaloneGRPCServer:
    """
    Run the standalone gRPC server.
    
    Args:
        host: Host address to bind to
        port: Port to listen on
        max_workers: Maximum number of worker threads
        use_ssl: Whether to use SSL/TLS
        ssl_cert_path: Path to SSL certificate file (required if use_ssl is True)
        ssl_key_path: Path to SSL key file (required if use_ssl is True)
    
    Returns:
        StandaloneGRPCServer instance
    """
    server = StandaloneGRPCServer(
        host=host,
        port=port,
        max_workers=max_workers,
        use_ssl=use_ssl,
        ssl_cert_path=ssl_cert_path,
        ssl_key_path=ssl_key_path
    )
    
    await server.start()
    return server


if __name__ == "__main__":
    import argparse
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Run the standalone gRPC server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind to")
    parser.add_argument("--port", type=int, default=50051, help="Port to listen on")
    parser.add_argument("--workers", type=int, default=10, help="Maximum number of worker threads")
    parser.add_argument("--use-ssl", action="store_true", help="Use SSL/TLS")
    parser.add_argument("--ssl-cert", type=str, help="Path to SSL certificate file")
    parser.add_argument("--ssl-key", type=str, help="Path to SSL key file")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run server
    asyncio.run(
        run_server(
            host=args.host,
            port=args.port,
            max_workers=args.workers,
            use_ssl=args.use_ssl,
            ssl_cert_path=args.ssl_cert,
            ssl_key_path=args.ssl_key
        ).wait_for_termination()
    )