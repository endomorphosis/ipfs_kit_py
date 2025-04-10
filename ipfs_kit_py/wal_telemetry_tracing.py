# ipfs_kit_py/wal_telemetry_tracing.py

"""
Distributed tracing module for the Write-Ahead Log (WAL) telemetry system.

This module provides distributed tracing capabilities for the WAL system, enabling
tracking of operations across different components and services. It includes:

1. OpenTelemetry integration for standardized tracing
2. Trace context propagation between components
3. Span creation and management for WAL operations
4. Automatic correlation with WAL telemetry metrics
5. Export capabilities to various tracing backends (Jaeger, Zipkin, etc.)

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
    from opentelemetry.context.context import Context
    from opentelemetry.trace.span import Span, SpanContext, TraceState, format_span_id, format_trace_id
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

class WALTracing:
    """
    Distributed tracing for the IPFS Kit Write-Ahead Log system.
    
    This class provides tracing capabilities for WAL operations, allowing
    for tracking and analysis of distributed operations across components
    and services.
    """
    
    def __init__(
        self,
        service_name: str = "ipfs-kit-wal",
        telemetry: Optional[Any] = None,
        exporter_type: Union[str, TracingExporterType] = TracingExporterType.CONSOLE,
        exporter_endpoint: Optional[str] = None,
        resource_attributes: Optional[Dict[str, str]] = None,
        sampling_ratio: float = 1.0,
        auto_instrument: bool = True
    ):
        """
        Initialize the WAL tracing system.
        
        Args:
            service_name: Name of the service for tracing identification
            telemetry: Optional WALTelemetry instance for metric correlation
            exporter_type: Type of tracing exporter to use
            exporter_endpoint: Endpoint URL for the tracing backend
            resource_attributes: Additional resource attributes
            sampling_ratio: Sampling ratio for traces (0.0-1.0)
            auto_instrument: Whether to automatically instrument WAL operations
        """
        self.service_name = service_name
        self.telemetry = telemetry
        
        # Convert enum to string
        if hasattr(exporter_type, 'value'):
            exporter_type = exporter_type.value
            
        self.exporter_type = exporter_type
        self.exporter_endpoint = exporter_endpoint
        self.auto_instrument = auto_instrument
        
        # Default resource attributes
        self.resource_attributes = {
            "service.name": service_name,
            "service.namespace": "ipfs_kit_py",
            "service.version": getattr(telemetry, "__version__", "unknown") if telemetry else "unknown"
        }
        
        # Add custom resource attributes
        if resource_attributes:
            self.resource_attributes.update(resource_attributes)
            
        # Initialize OpenTelemetry if available
        self.tracer = None
        self.propagator = None
        if OPENTELEMETRY_AVAILABLE:
            self._setup_opentelemetry(sampling_ratio)
        else:
            logger.warning("OpenTelemetry not available. Using minimal tracing implementation.")
            self._setup_minimal_tracing()
            
        # Track active spans
        self._active_spans = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Install hooks if auto-instrument is enabled
        if auto_instrument and telemetry is not None and WAL_AVAILABLE:
            self._install_tracing_hooks()
            
        logger.info(f"WAL tracing initialized with exporter: {self.exporter_type}")
        
    def _setup_opentelemetry(self, sampling_ratio: float):
        """Set up OpenTelemetry tracing components."""
        # Create resource
        resource = Resource.create(self.resource_attributes)
        
        # Create tracer provider with resource
        provider = TracerProvider(resource=resource)
        
        # Configure exporter based on type
        if self.exporter_type == TracingExporterType.CONSOLE.value:
            exporter = ConsoleSpanExporter()
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            
        elif self.exporter_type == TracingExporterType.OTLP.value and OTLP_AVAILABLE:
            # OTLP exporter for sending to collectors like OpenTelemetry Collector
            endpoint = self.exporter_endpoint or "http://localhost:4317"
            exporter = OTLPSpanExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            
        elif self.exporter_type == TracingExporterType.JAEGER.value and JAEGER_AVAILABLE:
            # Jaeger exporter
            endpoint = self.exporter_endpoint or "http://localhost:14268/api/traces"
            exporter = JaegerExporter(collector_endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            
        elif self.exporter_type == TracingExporterType.ZIPKIN.value and ZIPKIN_AVAILABLE:
            # Zipkin exporter
            endpoint = self.exporter_endpoint or "http://localhost:9411/api/v2/spans"
            exporter = ZipkinExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            
        elif self.exporter_type != TracingExporterType.NONE.value:
            logger.warning(f"Unsupported or unavailable exporter type: {self.exporter_type}. Using Console exporter.")
            exporter = ConsoleSpanExporter()
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Create tracer
        self.tracer = trace.get_tracer(self.service_name)
        
        # Set up propagator for distributed tracing
        self.propagator = TraceContextTextMapPropagator()
        
    def _setup_minimal_tracing(self):
        """Set up minimal tracing when OpenTelemetry is not available."""
        self.tracer = MinimalTracer(self.service_name)
        self.propagator = MinimalPropagator()
        
    def _install_tracing_hooks(self):
        """Install hooks on WAL operations to automatically create traces."""
        if not hasattr(self.telemetry.wal, 'add_operation_traced'):
            # Save the original add_operation method
            self.telemetry.wal.add_operation_traced = self.telemetry.wal.add_operation
            
            # Replace with traced version
            def add_operation_with_tracing(*args, **kwargs):
                # Extract operation type and backend if available
                operation_type = kwargs.get("operation_type", "unknown")
                backend = kwargs.get("backend", "unknown")
                
                # Create span context
                with self.create_span_context(
                    operation_type=operation_type,
                    backend=backend,
                    operation_id="pending"  # Will be updated when we get the result
                ) as span:
                    # Call original method
                    result = self.telemetry.wal.add_operation_traced(*args, **kwargs)
                    
                    # Update span with operation ID and status
                    if result.get("success") and "operation_id" in result:
                        span.set_attribute("operation.id", result["operation_id"])
                        
                        # Store active span for this operation
                        with self._lock:
                            self._active_spans[result["operation_id"]] = span
                    else:
                        # Operation failed
                        span.set_status(Status(StatusCode.ERROR))
                        if "error" in result:
                            span.set_attribute("error.message", result["error"])
                    
                    return result
                    
            self.telemetry.wal.add_operation = add_operation_with_tracing
        
        # Hook the update_operation_status method
        if not hasattr(self.telemetry.wal, 'update_operation_status_traced'):
            # Save the original method
            self.telemetry.wal.update_operation_status_traced = self.telemetry.wal.update_operation_status
            
            # Replace with traced version
            def update_operation_status_with_tracing(operation_id, new_status, updates=None):
                # Get the active span for this operation if available
                span = None
                with self._lock:
                    span = self._active_spans.get(operation_id)
                
                if span is not None:
                    # Convert enum to string if needed
                    status_str = new_status
                    if hasattr(new_status, 'value'):
                        status_str = new_status.value
                        
                    # Record status change event
                    span.add_event(
                        name="status.change",
                        attributes={
                            "operation.id": operation_id,
                            "status.new": status_str,
                        }
                    )
                    
                    # Check if operation is complete
                    if status_str in [OperationStatus.COMPLETED.value, OperationStatus.FAILED.value]:
                        # Set final status
                        if status_str == OperationStatus.COMPLETED.value:
                            span.set_status(Status(StatusCode.OK))
                        else:
                            span.set_status(Status(StatusCode.ERROR))
                            
                            # Add error details if available
                            if updates and "error" in updates:
                                span.set_attribute("error.message", updates["error"])
                            if updates and "error_type" in updates:
                                span.set_attribute("error.type", updates["error_type"])
                        
                        # End span
                        span.end()
                        
                        # Remove from active spans
                        with self._lock:
                            if operation_id in self._active_spans:
                                del self._active_spans[operation_id]
                
                # Call original method
                return self.telemetry.wal.update_operation_status_traced(operation_id, new_status, updates)
                
            self.telemetry.wal.update_operation_status = update_operation_status_with_tracing
            
        logger.info("WAL tracing hooks installed successfully")
        
    def start_span(
        self, 
        name: str, 
        context: Optional[Any] = None,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[List[Any]] = None,
        start_time: Optional[int] = None
    ) -> Span:
        """
        Start a new tracing span.
        
        Args:
            name: Name of the span
            context: Optional parent context
            kind: Span kind (server, client, producer, consumer)
            attributes: Span attributes
            links: Span links to other traces
            start_time: Optional start time (nanoseconds)
            
        Returns:
            A new span
        """
        if OPENTELEMETRY_AVAILABLE:
            # Use OpenTelemetry API
            return self.tracer.start_span(
                name=name,
                context=context,
                kind=kind,
                attributes=attributes,
                links=links,
                start_time=start_time
            )
        else:
            # Use minimal implementation
            span = MinimalSpan(name=name)
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            return span
    
    def create_span_context(
        self,
        operation_type: str,
        backend: str,
        operation_id: str,
        parent_context: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> WALTracingContext:
        """
        Create a context manager for a WAL operation span.
        
        Args:
            operation_type: Type of WAL operation
            backend: Backend system being used
            operation_id: ID of the WAL operation
            parent_context: Optional parent context for nested spans
            attributes: Additional span attributes
            
        Returns:
            A context manager that creates and manages a span
        """
        return WALTracingContext(
            tracer=self,
            operation_type=operation_type,
            operation_id=operation_id,
            backend=backend,
            parent_context=parent_context,
            attributes=attributes
        )
        
    def inject_context(self, context: Optional[Any], carrier: Dict[str, str]):
        """
        Inject trace context into a carrier for propagation.
        
        Args:
            context: The context to inject
            carrier: Dictionary to inject context into
        """
        if OPENTELEMETRY_AVAILABLE and self.propagator:
            self.propagator.inject(carrier, context=context)
        else:
            # Basic injection for minimal implementation
            if hasattr(context, "span_id") and hasattr(context, "trace_id"):
                carrier["traceparent"] = f"00-{context.trace_id}-{context.span_id}-01"
        
    def extract_context(self, carrier: Dict[str, str]) -> Optional[Any]:
        """
        Extract trace context from a carrier.
        
        Args:
            carrier: Dictionary containing the trace context
            
        Returns:
            Extracted context
        """
        if OPENTELEMETRY_AVAILABLE and self.propagator:
            return self.propagator.extract(carrier=carrier)
        else:
            # Basic extraction for minimal implementation
            if "traceparent" in carrier:
                try:
                    parts = carrier["traceparent"].split("-")
                    if len(parts) >= 3:
                        return MinimalContext(trace_id=parts[1], span_id=parts[2])
                except Exception:
                    pass
                    
            return None
            
    def trace_function(
        self, 
        name: Optional[str] = None, 
        operation_type: Optional[str] = None,
        backend: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Decorator to trace a function execution.
        
        Args:
            name: Span name (defaults to function name)
            operation_type: Type of operation
            backend: Backend system
            attributes: Additional span attributes
            
        Returns:
            Decorated function
        """
        def decorator(func):
            # Use function name as span name if not provided
            span_name = name or f"function.{func.__name__}"
            
            def wrapper(*args, **kwargs):
                # Start span
                with self.start_span(
                    name=span_name,
                    attributes={
                        "function": func.__name__,
                        "operation.type": operation_type or "function",
                        "backend": backend or "none",
                        **(attributes or {})
                    }
                ) as span:
                    try:
                        # Execute function
                        result = func(*args, **kwargs)
                        
                        # Set status as OK
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                    except Exception as e:
                        # Record exception
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        # Re-raise the exception
                        raise
                        
            return wrapper
            
        return decorator
        
    def get_current_span(self) -> Optional[Span]:
        """Get the current active span."""
        if OPENTELEMETRY_AVAILABLE:
            return trace.get_current_span()
        else:
            # Minimal implementation doesn't support this well
            return None
            
    def get_tracer(self) -> Any:
        """Get the underlying tracer."""
        return self.tracer
        
    def get_trace_id(self) -> Optional[str]:
        """Get the current trace ID if available."""
        span = self.get_current_span()
        if span and hasattr(span, "get_span_context"):
            context = span.get_span_context()
            if context and hasattr(context, "trace_id"):
                return format_trace_id(context.trace_id) if hasattr(format_trace_id, "__call__") else str(context.trace_id)
        return None
        
    def get_span_id(self) -> Optional[str]:
        """Get the current span ID if available."""
        span = self.get_current_span()
        if span and hasattr(span, "get_span_context"):
            context = span.get_span_context()
            if context and hasattr(context, "span_id"):
                return format_span_id(context.span_id) if hasattr(format_span_id, "__call__") else str(context.span_id)
        return None
        
    def generate_trace_context(self) -> Dict[str, str]:
        """Generate a trace context dictionary for the current span."""
        carrier = {}
        self.inject_context(None, carrier)  # Use current context
        return carrier
        
    def trace_request(self, request_info: Dict[str, Any], response_info: Dict[str, Any]) -> None:
        """
        Trace an HTTP request-response cycle.
        
        Args:
            request_info: Information about the request
            response_info: Information about the response
        """
        # Create a span for the request
        with self.start_span(
            name=f"http.{request_info.get('method', 'request')}",
            attributes={
                "http.method": request_info.get("method", "UNKNOWN"),
                "http.url": request_info.get("url", ""),
                "http.path": request_info.get("path", ""),
                "http.status_code": response_info.get("status_code", 0),
                "http.request_content_length": request_info.get("content_length", 0),
                "http.response_content_length": request_info.get("content_length", 0),
                "http.duration_ms": response_info.get("duration_ms", 0)
            }
        ) as span:
            # Set span status based on response
            status_code = response_info.get("status_code", 0)
            if 400 <= status_code < 600:
                span.set_status(Status(StatusCode.ERROR, f"HTTP error {status_code}"))
                
    def correlation_id(self) -> str:
        """Generate a correlation ID for the current trace."""
        trace_id = self.get_trace_id()
        if trace_id:
            return trace_id
        return str(uuid.uuid4())
        
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """
        Add an event to the current span.
        
        Args:
            name: Event name
            attributes: Event attributes
        """
        span = self.get_current_span()
        if span and hasattr(span, "add_event"):
            span.add_event(name=name, attributes=attributes)
            
    def close(self) -> None:
        """Close the tracer and clean up resources."""
        # Ensure all active spans are closed
        with self._lock:
            for span_id, span in self._active_spans.items():
                try:
                    span.end()
                except Exception as e:
                    logger.warning(f"Error closing span {span_id}: {e}")
                    
            self._active_spans.clear()
            
        logger.info("WAL tracing closed")


# Minimal implementations for when OpenTelemetry is not available
class MinimalSpan:
    """Minimal span implementation when OpenTelemetry is not available."""
    
    def __init__(self, name: str):
        self.name = name
        self.attributes = {}
        self.events = []
        self.start_time = time.time()
        self.end_time = None
        self.status = "OK"
        self.status_description = None
        self.trace_id = f"{uuid.uuid4().hex}{'0' * 16}"
        self.span_id = uuid.uuid4().hex[:16]
        
    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value
        
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        })
        
    def record_exception(self, exception: Exception) -> None:
        """Record an exception in the span."""
        self.add_event(
            name="exception",
            attributes={
                "exception.type": type(exception).__name__,
                "exception.message": str(exception)
            }
        )
        
    def set_status(self, status: Any) -> None:
        """Set the span status."""
        if hasattr(status, "status_code"):
            self.status = status.status_code
        else:
            self.status = status
            
        if hasattr(status, "description"):
            self.status_description = status.description
            
    def end(self) -> None:
        """End the span."""
        self.end_time = time.time()
        
    def get_span_context(self) -> Any:
        """Get the span context."""
        return self


class MinimalContext:
    """Minimal context implementation when OpenTelemetry is not available."""
    
    def __init__(self, trace_id: str, span_id: str):
        self.trace_id = trace_id
        self.span_id = span_id


class MinimalPropagator:
    """Minimal propagator implementation when OpenTelemetry is not available."""
    
    def inject(self, carrier: Dict[str, str], context: Optional[Any] = None) -> None:
        """Inject context into carrier."""
        if context is None:
            # Generate a new trace and span ID
            trace_id = f"{uuid.uuid4().hex}{'0' * 16}"
            span_id = uuid.uuid4().hex[:16]
            carrier["traceparent"] = f"00-{trace_id}-{span_id}-01"
        elif hasattr(context, "trace_id") and hasattr(context, "span_id"):
            carrier["traceparent"] = f"00-{context.trace_id}-{context.span_id}-01"
            
    def extract(self, carrier: Dict[str, str]) -> Optional[Any]:
        """Extract context from carrier."""
        if "traceparent" in carrier:
            try:
                parts = carrier["traceparent"].split("-")
                if len(parts) >= 3:
                    return MinimalContext(trace_id=parts[1], span_id=parts[2])
            except Exception:
                pass
                
        return None


class MinimalTracer:
    """Minimal tracer implementation when OpenTelemetry is not available."""
    
    def __init__(self, name: str):
        self.name = name
        
    def start_span(
        self, 
        name: str, 
        context: Optional[Any] = None,
        kind: Optional[Any] = None,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[List[Any]] = None,
        start_time: Optional[int] = None
    ) -> MinimalSpan:
        """Start a new span."""
        span = MinimalSpan(name=name)
        
        # Set attributes if provided
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
                
        return span


# Example FastAPI integration
def add_tracing_middleware(app, tracer: WALTracing, service_name: str = "ipfs-kit-api"):
    """
    Add tracing middleware to a FastAPI application.
    
    Args:
        app: FastAPI application
        tracer: WALTracing instance
        service_name: Name of the service
    """
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry not available. Minimal middleware installed.")
        
    @app.middleware("http")
    async def tracing_middleware(request, call_next):
        # Extract trace context from headers
        context = tracer.extract_context(dict(request.headers))
        
        # Start a new span
        with tracer.start_span(
            name=f"http.{request.method}",
            context=context,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.path": request.url.path,
                "http.scheme": request.url.scheme,
                "http.host": request.url.hostname,
                "service.name": service_name
            }
        ) as span:
            start_time = time.time()
            
            try:
                # Call next middleware
                response = await call_next(request)
                
                # Record response information
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.duration_ms", duration_ms)
                
                # Set span status based on response
                if 400 <= response.status_code < 600:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP error {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))
                    
                return response
                
            except Exception as e:
                # Record exception
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                # Re-raise the exception
                raise
                
    logger.info(f"Tracing middleware added to {service_name}")


# Example async HTTP client tracing (anyio compatible)
def trace_http_request(tracer: WALTracing, method: str, url: str, **kwargs):
    """
    Trace an HTTP request with OpenTelemetry.
    This function works with any async HTTP client (aiohttp, httpx, etc.)
    and is compatible with both asyncio and trio backends through anyio.
    
    Args:
        tracer: WALTracing instance
        method: HTTP method
        url: Request URL
        **kwargs: Additional request kwargs
        
    Returns:
        Trace context carrier and async trace context manager
    """
    # Create trace context
    carrier = {}
    tracer.inject_context(None, carrier)  # Use current context
    
    # Create attributes
    attributes = {
        "http.method": method.upper(),
        "http.url": url,
        "http.scheme": url.split("://")[0] if "://" in url else "",
        "http.host": url.split("://")[1].split("/")[0] if "://" in url else ""
    }
    
    # Create a span for the request
    return carrier, tracer.start_span(
        name=f"http.client.{method.lower()}",
        attributes=attributes
    )

# Alias for backwards compatibility
trace_aiohttp_request = trace_http_request


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("WAL tracing module - example usage")
    
    if not WAL_AVAILABLE:
        logger.info("WAL system not available. This module provides tracing for the WAL system.")
        exit(1)
        
    # Create dependencies
    from .storage_wal import StorageWriteAheadLog, BackendHealthMonitor
    from .wal_telemetry import WALTelemetry
    
    # Create WAL with health monitor
    health_monitor = BackendHealthMonitor(
        check_interval=5,
        history_size=10
    )
    
    wal = StorageWriteAheadLog(
        base_path="~/.ipfs_kit/wal",
        partition_size=100,
        health_monitor=health_monitor
    )
    
    # Create telemetry
    telemetry = WALTelemetry(
        wal=wal,
        metrics_path="~/.ipfs_kit/telemetry",
        sampling_interval=10,
        enable_detailed_timing=True,
        operation_hooks=True
    )
    
    # Create tracer
    tracer = WALTracing(
        service_name="ipfs-kit-wal-example",
        telemetry=telemetry,
        exporter_type=TracingExporterType.CONSOLE,
        auto_instrument=True
    )
    
    # Example: Manual tracing
    with tracer.create_span_context(
        operation_type="add",
        backend="ipfs",
        operation_id="manual-1",
        attributes={"test": "manual-tracing"}
    ) as span:
        logger.info("Processing with manual tracing")
        span.set_attribute("custom.attribute", "some-value")
        
        # Simulate work
        time.sleep(0.1)
        
        # Add an event
        span.add_event(
            name="processing.step",
            attributes={"step": "validation"}
        )
        
        # Simulate more work
        time.sleep(0.1)
        
    # Example: Function decorator
    @tracer.trace_function(
        name="example.function",
        operation_type="processing",
        backend="memory",
        attributes={"test": "decorator-tracing"}
    )
    def example_function(x, y):
        logger.info(f"Processing {x} + {y}")
        return x + y
        
    result = example_function(3, 4)
    logger.info(f"Result: {result}")
    
    # Example: Auto-instrumented WAL operation
    operation = wal.add_operation(
        operation_type="add",
        backend="ipfs",
        parameters={"path": "/tmp/example.txt"}
    )
    
    logger.info(f"Added operation: {operation}")
    
    # Example: Propagation
    ctx = {}
    tracer.inject_context(None, ctx)
    logger.info(f"Propagation context: {ctx}")
    
    # Clean up
    tracer.close()
    telemetry.close()
    wal.close()
    health_monitor.close()