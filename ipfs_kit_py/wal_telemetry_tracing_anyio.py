# ipfs_kit_py/wal_telemetry_tracing_anyio.py

"""
AnyIO-compatible distributed tracing module for the Write-Ahead Log (WAL) telemetry system.

This module provides distributed tracing capabilities for the WAL system, enabling
tracking of operations across different components and services, with support for 
both asyncio and trio backends through AnyIO. It includes:

1. OpenTelemetry integration for standardized tracing
2. Trace context propagation between components
3. Span creation and management for WAL operations
4. Automatic correlation with WAL telemetry metrics
5. Export capabilities to various tracing backends (Jaeger, Zipkin, etc.)
6. AnyIO compatibility for backend-agnostic async operations

The tracing system integrates with the WAL telemetry to provide a comprehensive
view of system performance and behavior across distributed components.
"""

import os
import time
import logging
import json
import uuid
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable, Tuple

# Import AnyIO for backend-agnostic async operations
import anyio

# Import WAL components if available
try:
    from .wal_telemetry import WALTelemetry
    from .storage_wal import (
        StorageWriteAheadLog,
        OperationType,
        OperationStatus,
        BackendType
    )
    WAL_AVAILABLE = True
except ImportError:
    WAL_AVAILABLE = False
    
    # Define placeholder enums for documentation
    class OperationType(str, Enum):
        ADD = "add"
        GET = "get"
        PIN = "pin"
        
    class OperationStatus(str, Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"
        
    class BackendType(str, Enum):
        IPFS = "ipfs"
        S3 = "s3"
        STORACHA = "storacha"

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    # from opentelemetry.context.context import Context # This line was causing the NameError, Context is imported below
    from opentelemetry.context import Context # Correct import location
    from opentelemetry.trace.span import Span, SpanContext, TraceState, format_span_id, format_trace_id
    from ipfs_kit_py import __version__

    from opentelemetry.trace.status import Status, StatusCode

    # Optional exporters
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        OTLP_AVAILABLE = True
    except ImportError:
        OTLP_AVAILABLE = False

    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter

        JAEGER_AVAILABLE = True
    except ImportError:
        JAEGER_AVAILABLE = False

    try:
        from opentelemetry.exporter.zipkin.json import ZipkinExporter

        ZIPKIN_AVAILABLE = True
    except ImportError:
        ZIPKIN_AVAILABLE = False

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    # Define basic placeholder classes for when OpenTelemetry is not available
    class Span:
        def __init__(self):
            pass
        
        def set_attribute(self, key, value):
            pass
            
        def record_exception(self, exception):
            pass
            
        def set_status(self, status):
            pass
            
        def end(self):
            pass
    
    class StatusCode:
        ERROR = "ERROR"
        OK = "OK"
        
    class Status:
        @classmethod
        def ok(cls):
            return "OK"
            
        @classmethod
        def error(cls):
            return "ERROR"

# Configure logging
logger = logging.getLogger(__name__)

class TracingExporterType(str, Enum):
    """Types of tracing exporters supported."""
    CONSOLE = "console"
    OTLP = "otlp"
    JAEGER = "jaeger"
    ZIPKIN = "zipkin"
    NONE = "none"

class WALTracingContext:
    """
    Context manager for WAL operation tracing spans.
    
    This class provides a context manager that creates and manages a tracing span
    for a WAL operation, automatically recording its timing and status.
    """
    
    def __init__(
        self, 
        tracer: 'WALTracing', 
        operation_type: str, 
        operation_id: str, 
        backend: str,
        parent_context: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a new tracing context.
        
        Args:
            tracer: WALTracing instance
            operation_type: Type of WAL operation
            operation_id: ID of the WAL operation
            backend: Backend system being used
            parent_context: Optional parent context for nested spans
            attributes: Additional span attributes
        """
        self.tracer = tracer
        self.operation_type = operation_type
        self.operation_id = operation_id
        self.backend = backend
        self.parent_context = parent_context
        self.attributes = attributes or {}
        self.span = None
        
    def __enter__(self):
        """Start the span when entering the context."""
        self.span = self.tracer.start_span(
            name=f"wal.operation.{self.operation_type}",
            context=self.parent_context,
            attributes={
                "operation.id": self.operation_id,
                "operation.type": self.operation_type,
                "backend": self.backend,
                **self.attributes
            }
        )
        return self.span
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the span when exiting the context."""
        if exc_type is not None:
            if self.span:
                self.span.record_exception(exc_val)
                self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
        
        if self.span:
            self.span.end()

class WALTracingAnyIO:
    """
    AnyIO-compatible distributed tracing for the IPFS Kit Write-Ahead Log system.
    
    This class provides tracing capabilities for WAL operations, allowing
    for tracking and analysis of distributed operations across components
    and services. It supports both asyncio and trio backends through AnyIO.
    """
    
    def __init__(
        self,
        service_name: str = "ipfs-kit-wal",
        telemetry: Optional[WALTelemetry] = None,
        exporter_type: TracingExporterType = TracingExporterType.CONSOLE,
        endpoint: Optional[str] = None
    ):
        """
        Initialize the WAL tracing system.
        
        Args:
            service_name: Name of the service for tracing identification
            telemetry: Optional WALTelemetry instance for correlation
            exporter_type: Type of tracing exporter to use
            endpoint: Optional endpoint for the tracing exporter
        """
        self.service_name = service_name
        self.telemetry = telemetry
        self.exporter_type = exporter_type
        self.endpoint = endpoint
        
        # OpenTelemetry components
        self.tracer_provider = None
        self.tracer = None
        self.propagator = None
        
        # Initialize OpenTelemetry if available
        if OPENTELEMETRY_AVAILABLE:
            self._init_tracing()
            
    def _init_tracing(self):
        """Initialize the OpenTelemetry tracing components."""
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": self.service_name,
                "service.namespace": "ipfs.kit",
                "service.version": __version__,  # Pull from version module
                "service.instance.id": str(uuid.uuid4())
            })
            
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Create and add appropriate span processor based on exporter type
            processor = self._create_span_processor()
            if processor:
                self.tracer_provider.add_span_processor(processor)
                
            # Set as global tracer provider
            trace.set_tracer_provider(self.tracer_provider)
            
            # Create tracer
            self.tracer = trace.get_tracer(self.service_name)
            
            # Create propagator for context extraction/injection
            self.propagator = TraceContextTextMapPropagator()
            
            logger.info(f"WAL tracing initialized with {self.exporter_type.value} exporter")
            
        except Exception as e:
            logger.error(f"Failed to initialize WAL tracing: {e}")
            # Fall back to placeholder implementation
            self.tracer_provider = None
            self.tracer = None
            self.propagator = None
            
    def _create_span_processor(self):
        """Create the appropriate span processor based on exporter type."""
        if not OPENTELEMETRY_AVAILABLE:
            return None
            
        try:
            if self.exporter_type == TracingExporterType.CONSOLE:
                # Simple console exporter for development/debugging
                exporter = ConsoleSpanExporter()
                return BatchSpanProcessor(exporter)
                
            elif self.exporter_type == TracingExporterType.OTLP and OTLP_AVAILABLE:
                # OTLP exporter for OpenTelemetry Collector
                endpoint = self.endpoint or "http://localhost:4317"
                exporter = OTLPSpanExporter(endpoint=endpoint)
                return BatchSpanProcessor(exporter)
                
            elif self.exporter_type == TracingExporterType.JAEGER and JAEGER_AVAILABLE:
                # Jaeger exporter
                endpoint = self.endpoint or "http://localhost:14268/api/traces"
                exporter = JaegerExporter(collector_endpoint=endpoint)
                return BatchSpanProcessor(exporter)
                
            elif self.exporter_type == TracingExporterType.ZIPKIN and ZIPKIN_AVAILABLE:
                # Zipkin exporter
                endpoint = self.endpoint or "http://localhost:9411/api/v2/spans"
                exporter = ZipkinExporter(endpoint=endpoint)
                return BatchSpanProcessor(exporter)
                
            elif self.exporter_type == TracingExporterType.NONE:
                # No exporter - useful for tests or when tracing is functionally disabled
                return None
                
            else:
                # Fall back to console exporter
                logger.warning(f"Unsupported exporter type {self.exporter_type}. Using Console exporter.")
                exporter = ConsoleSpanExporter()
                return BatchSpanProcessor(exporter)
                
        except Exception as e:
            logger.error(f"Failed to create span processor: {e}")
            return None
            
    def start_span(self, name: str, context: Optional[Any] = None, attributes: Optional[Dict[str, Any]] = None) -> Span:
        """
        Start a new tracing span.
        
        Args:
            name: Name of the span
            context: Optional parent context
            attributes: Additional span attributes
            
        Returns:
            A new span object
        """
        if not OPENTELEMETRY_AVAILABLE or not self.tracer:
            # Return placeholder span
            return Span()
            
        try:
            # Start a new span with the given parent context
            span = self.tracer.start_span(name, context=context)
            
            # Add attributes
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
                    
            return span
        except Exception as e:
            logger.error(f"Failed to start span: {e}")
            return Span()
            
    def trace_operation(
        self, 
        operation_type: str, 
        operation_id: str, 
        backend: str,
        parent_context: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> WALTracingContext:
        """
        Create a context manager for tracing a WAL operation.
        
        Args:
            operation_type: Type of WAL operation
            operation_id: ID of the WAL operation
            backend: Backend system being used
            parent_context: Optional parent context for nested spans
            attributes: Additional span attributes
            
        Returns:
            A context manager for the operation span
        """
        return WALTracingContext(
            tracer=self,
            operation_type=operation_type,
            operation_id=operation_id,
            backend=backend,
            parent_context=parent_context,
            attributes=attributes
        )
        
    def extract_context(self, carrier: Dict[str, str]) -> Optional['Context']: # Use string literal
        """
        Extract trace context from a carrier (e.g., HTTP headers).
        
        Args:
            carrier: Dictionary containing trace context information
            
        Returns:
            Extracted context or None if extraction fails
        """
        if not OPENTELEMETRY_AVAILABLE or not self.propagator:
            return None
            
        try:
            return self.propagator.extract(carrier=carrier)
        except Exception as e:
            logger.error(f"Failed to extract context: {e}")
            return None
            
    def inject_context(self, context: Any, carrier: Dict[str, str]) -> Dict[str, str]:
        """
        Inject trace context into a carrier (e.g., HTTP headers).
        
        Args:
            context: Trace context to inject
            carrier: Dictionary to inject context into
            
        Returns:
            Carrier with injected context
        """
        if not OPENTELEMETRY_AVAILABLE or not self.propagator:
            return carrier
            
        try:
            self.propagator.inject(carrier=carrier, context=context)
        except Exception as e:
            logger.error(f"Failed to inject context: {e}")
            
        return carrier
    
    async def tracing_middleware(self, request, call_next):
        """
        AnyIO-compatible ASGI middleware for tracing HTTP requests.
        
        This middleware adds tracing for incoming HTTP requests, creating
        spans with request information and propagating trace context.
        
        Args:
            request: The incoming request
            call_next: The next middleware in the chain
            
        Returns:
            The response from subsequent middleware
        """
        # Extract trace context from headers
        context = self.extract_context(dict(request.headers))
        
        # Start a new span
        with self.start_span(
            name=f"http.{request.method}",
            context=context,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.host": request.url.netloc,
                "http.target": request.url.path,
                "http.flavor": str(request.scope.get("http_version", "1.1")),
                "http.user_agent": request.headers.get("user-agent", ""),
            }
        ) as span:
            try:
                # Process the request
                response = await call_next(request)
                
                # Add response attributes to span
                span.set_attribute("http.status_code", response.status_code)
                
                # Categorize by status code
                if 400 <= response.status_code < 600:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                
                return response
            except Exception as e:
                # Record exception and set error status
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise  # Re-raise the exception
                
    def create_trace_headers(self, operation_id: str) -> Dict[str, str]:
        """
        Create trace headers for a new operation.
        
        This is useful for propagating trace context to downstream services
        or for integrating with other systems.
        
        Args:
            operation_id: ID of the operation to create headers for
            
        Returns:
            Dictionary of headers containing trace context
        """
        if not OPENTELEMETRY_AVAILABLE or not self.tracer:
            return {}
            
        try:
            # Create a new span for the operation
            with self.start_span(
                name=f"wal.operation.{operation_id}",
                attributes={"operation.id": operation_id}
            ) as span:
                # Create carrier for context injection
                carrier = {}
                
                # Inject the current context
                self.inject_context(trace.get_current_span().get_span_context(), carrier)
                
                return carrier
        except Exception as e:
            logger.error(f"Failed to create trace headers: {e}")
            return {}
            
    def shutdown(self):
        """
        Shut down the tracing system and clean up resources.
        """
        if OPENTELEMETRY_AVAILABLE and self.tracer_provider:
            try:
                self.tracer_provider.shutdown()
                logger.info("WAL tracing system shut down")
            except Exception as e:
                logger.error(f"Error shutting down WAL tracing: {e}")
