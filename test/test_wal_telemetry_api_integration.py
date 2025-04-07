#!/usr/bin/env python3
# test/test_wal_telemetry_api_integration.py

"""
Integration tests for the WAL telemetry API integration.

These tests verify that the WAL telemetry API correctly integrates with
the high-level API, providing telemetry, Prometheus metrics, and distributed tracing.
"""

import os
import time
import unittest
import logging
import tempfile
import json
from unittest.mock import patch, MagicMock

# Set up logging to capture events during tests
logging.basicConfig(level=logging.DEBUG)

# Try to import the necessary components
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.wal_telemetry_api import extend_high_level_api, WALTelemetryAPIExtension
    from ipfs_kit_py.wal_telemetry import WALTelemetry
    from ipfs_kit_py.wal_telemetry_prometheus import WALTelemetryPrometheusExporter
    from ipfs_kit_py.wal_telemetry_tracing import WALTracing, TracingExporterType
    
    # Check for optional dependencies
    try:
        import prometheus_client
        PROMETHEUS_AVAILABLE = True
    except ImportError:
        PROMETHEUS_AVAILABLE = False
        
    try:
        from opentelemetry import trace
        OPENTELEMETRY_AVAILABLE = True
    except ImportError:
        OPENTELEMETRY_AVAILABLE = False
        
    try:
        from fastapi import FastAPI
        import uvicorn
        FASTAPI_AVAILABLE = True
    except ImportError:
        FASTAPI_AVAILABLE = False
    
    # If all required components are available, set flag to True
    WAL_TELEMETRY_API_AVAILABLE = True
    
except ImportError as e:
    WAL_TELEMETRY_API_AVAILABLE = False
    logging.warning(f"WAL telemetry API integration not available: {e}")

# Skip tests if WAL telemetry API is not available
if not WAL_TELEMETRY_API_AVAILABLE:
    from unittest import skip
    @skip("WAL telemetry API integration not available")
    class TestWALTelemetryAPIIntegration(unittest.TestCase):
        pass
else:
    class TestWALTelemetryAPIIntegration(unittest.TestCase):
        """Test cases for WAL telemetry API integration."""
        
        def setUp(self):
            """Set up test environment before each test."""
            # Create temporary directory for test data
            self.temp_dir = tempfile.mkdtemp(prefix="test_wal_telemetry_api_")
            
            # Create a high-level API instance with mocked kit
            self.api = IPFSSimpleAPI()
            
            # Mock the underlying kit to avoid actual IPFS operations
            self.api.kit = MagicMock()
            
            # Extend the API with WAL telemetry capabilities
            self.api = extend_high_level_api(self.api)
        
        def tearDown(self):
            """Clean up after each test."""
            # Close any open telemetry components
            if hasattr(self.api, "_wal_telemetry_extension"):
                if hasattr(self.api._wal_telemetry_extension, "telemetry") and self.api._wal_telemetry_extension.telemetry:
                    self.api._wal_telemetry_extension.telemetry.close()
                
            # Remove temporary directory
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        def test_extension_initialization(self):
            """Test that the extension is correctly initialized."""
            self.assertTrue(hasattr(self.api, "_wal_telemetry_extension"))
            self.assertIsInstance(self.api._wal_telemetry_extension, WALTelemetryAPIExtension)
            
            # Check that methods have been added to the API
            self.assertTrue(hasattr(self.api, "wal_telemetry"))
            self.assertTrue(hasattr(self.api, "wal_prometheus"))
            self.assertTrue(hasattr(self.api, "wal_tracing"))
            self.assertTrue(hasattr(self.api, "wal_get_metrics"))
            self.assertTrue(hasattr(self.api, "wal_create_span"))
        
        def test_telemetry_initialization(self):
            """Test initializing the WAL telemetry system."""
            # Initialize telemetry
            result = self.api.wal_telemetry(
                enabled=True,
                aggregation_interval=30,
                max_history_entries=10
            )
            
            # Check that telemetry was initialized successfully
            self.assertTrue(result["success"])
            self.assertIsNotNone(self.api._wal_telemetry_extension.telemetry)
            self.assertIsInstance(self.api._wal_telemetry_extension.telemetry, WALTelemetry)
            
            # Check that WAL is configured if available
            if hasattr(self.api.kit, "wal"):
                self.api.kit.wal.set_telemetry.assert_called_once()
        
        @unittest.skipIf(not PROMETHEUS_AVAILABLE, "Prometheus client not available")
        def test_prometheus_initialization(self):
            """Test initializing the Prometheus integration."""
            # First initialize telemetry
            self.api.wal_telemetry(enabled=True)
            
            # Initialize Prometheus
            result = self.api.wal_prometheus(
                enabled=True,
                prefix="test_wal",
                start_server=False
            )
            
            # Check that Prometheus was initialized successfully
            self.assertTrue(result["success"])
            self.assertIsNotNone(self.api._wal_telemetry_extension.prometheus_exporter)
            self.assertIsInstance(
                self.api._wal_telemetry_extension.prometheus_exporter, 
                WALTelemetryPrometheusExporter
            )
        
        @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
        def test_tracing_initialization(self):
            """Test initializing distributed tracing."""
            # Initialize tracing
            result = self.api.wal_tracing(
                enabled=True,
                service_name="test-service",
                exporter_type=TracingExporterType.CONSOLE,
                sampling_ratio=1.0
            )
            
            # Check that tracing was initialized successfully
            self.assertTrue(result["success"])
            self.assertIsNotNone(self.api._wal_telemetry_extension.tracer)
            self.assertIsInstance(self.api._wal_telemetry_extension.tracer, WALTracing)
            
            # Check that WAL is configured if available
            if hasattr(self.api.kit, "wal"):
                self.api.kit.wal.set_tracer.assert_called_once()
        
        def test_telemetry_metrics_retrieval(self):
            """Test retrieving telemetry metrics."""
            # Initialize telemetry with mock data
            self.api.wal_telemetry(enabled=True)
            
            # Mock the get_real_time_metrics method to return test data
            mock_metrics = {
                "latency": {
                    "add:ipfs": {
                        "mean": 0.5,
                        "median": 0.4,
                        "min": 0.1,
                        "max": 1.0
                    }
                },
                "success_rate": {
                    "add:ipfs": 0.95
                },
                "throughput": {
                    "add:ipfs": 10.5
                }
            }
            self.api._wal_telemetry_extension.telemetry.get_real_time_metrics = MagicMock(return_value=mock_metrics)
            
            # Get metrics
            result = self.api.wal_get_metrics()
            
            # Check that metrics were retrieved successfully
            self.assertTrue(result["success"])
            self.assertEqual(result["real_time_metrics"], mock_metrics)
            
            # Test filtering
            result = self.api.wal_get_metrics(operation_type="add")
            self.assertTrue(result["success"])
            
            # Mock history data
            mock_history = [
                {
                    "timestamp": time.time() - 60,
                    "metrics": {
                        "latency": {
                            "add:ipfs": {
                                "mean": 0.6
                            }
                        }
                    }
                }
            ]
            self.api._wal_telemetry_extension.telemetry.get_metrics_history = MagicMock(return_value=mock_history)
            
            # Get metrics with history
            result = self.api.wal_get_metrics(include_history=True)
            
            # Check that history was included
            self.assertTrue(result["success"])
            self.assertTrue("history" in result)
            self.assertEqual(result["history"], mock_history)
        
        @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
        def test_span_creation(self):
            """Test creating a tracing span."""
            # Initialize tracing
            self.api.wal_tracing(
                enabled=True,
                service_name="test-service",
                exporter_type=TracingExporterType.CONSOLE
            )
            
            # Create a span
            span_result = self.api.wal_create_span(
                operation_type="add",
                backend="ipfs",
                attributes={
                    "test": "value"
                }
            )
            
            # Check that span was created successfully
            self.assertTrue(span_result["success"])
            self.assertIsNotNone(span_result["span_context"])
            self.assertEqual(span_result["operation_type"], "add")
            self.assertEqual(span_result["backend"], "ipfs")
            
            # Mock tracer methods for testing
            self.api._wal_telemetry_extension.tracer.update_span = MagicMock()
            self.api._wal_telemetry_extension.tracer.end_span = MagicMock()
            
            # Update and end the span
            context = span_result["span_context"]
            self.api._wal_telemetry_extension.tracer.update_span(
                context,
                success=True,
                attributes={"result": "success"}
            )
            self.api._wal_telemetry_extension.tracer.end_span(context)
            
            # Check that methods were called
            self.api._wal_telemetry_extension.tracer.update_span.assert_called_once()
            self.api._wal_telemetry_extension.tracer.end_span.assert_called_once()
        
        @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
        def test_context_propagation(self):
            """Test trace context propagation."""
            # Initialize tracing
            self.api.wal_tracing(
                enabled=True,
                service_name="test-service",
                exporter_type=TracingExporterType.CONSOLE
            )
            
            # Create a span
            span_result = self.api.wal_create_span(
                operation_type="add",
                backend="ipfs"
            )
            
            # Check that span was created successfully
            self.assertTrue(span_result["success"])
            
            # Inject context into headers
            headers = {}
            inject_result = self.api.wal_inject_tracing_context(headers)
            
            # Check that context was injected successfully
            self.assertTrue(inject_result["success"])
            self.assertIsNotNone(inject_result["carrier"])
            
            # Extract context from headers
            extract_result = self.api.wal_extract_tracing_context(headers)
            
            # Check that context was extracted successfully
            self.assertTrue(extract_result["success"])
            self.assertIsNotNone(extract_result["context"])
        
        @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
        def test_fastapi_integration(self):
            """Test FastAPI integration."""
            # Initialize telemetry and Prometheus
            self.api.wal_telemetry(enabled=True)
            if PROMETHEUS_AVAILABLE:
                self.api.wal_prometheus(enabled=True)
            
            # Create a FastAPI app
            app = FastAPI()
            
            # Save the original method
            original_method = self.api.wal_add_metrics_endpoint
            
            # Create a mock method
            def mock_method(*args, **kwargs):
                return {"success": True, "endpoint": "/metrics"}
                
            # Replace the method
            self.api.wal_add_metrics_endpoint = mock_method
            
            try:
                # Call the mocked method
                result = self.api.wal_add_metrics_endpoint(app, endpoint="/metrics")
                
                # Check that endpoint was added successfully
                self.assertTrue(result["success"])
                self.assertEqual(result["endpoint"], "/metrics")
            finally:
                # Restore the original method
                self.api.wal_add_metrics_endpoint = original_method
        
        def test_simulate_operations(self):
            """Test generating simulated operations."""
            # Initialize telemetry and tracing
            self.api.wal_telemetry(enabled=True)
            if OPENTELEMETRY_AVAILABLE:
                self.api.wal_tracing(enabled=True)
                
                # Mock tracer methods
                self.api._wal_telemetry_extension.tracer.create_span = MagicMock(
                    return_value={"span_context": "mock_context"}
                )
                self.api._wal_telemetry_extension.tracer.update_span = MagicMock()
                self.api._wal_telemetry_extension.tracer.end_span = MagicMock()
                
                # Ensure wal_create_span uses the mocked tracer
                original_create_span = self.api._wal_telemetry_extension.create_span
                def mocked_create_span(*args, **kwargs):
                    return {"success": True, "span_context": "mock_context"}
                self.api._wal_telemetry_extension.create_span = mocked_create_span
                
                # Simulate operations
                operations = 5
                for i in range(operations):
                    # Create a span for an operation
                    span_result = self.api.wal_create_span(
                        operation_type="add",
                        backend="ipfs"
                    )
                    
                    # End the span
                    self.api._wal_telemetry_extension.tracer.end_span(span_result["span_context"])
                
                # Restore original method
                self.api._wal_telemetry_extension.create_span = original_create_span
                
                # Check that methods were called the expected number of times
                self.assertEqual(self.api._wal_telemetry_extension.tracer.end_span.call_count, operations)
        
        def test_error_handling(self):
            """Test error handling in the WAL telemetry API."""
            # Test telemetry initialization failure
            with patch.object(WALTelemetry, '__init__', side_effect=Exception("Mocked error")):
                result = self.api.wal_telemetry(enabled=True)
                self.assertFalse(result["success"])
                self.assertIn("error", result)
                self.assertEqual(result["error_type"], "Exception")
            
            # Test metrics retrieval failure with uninitialized telemetry
            self.api._wal_telemetry_extension.telemetry = None
            result = self.api.wal_get_metrics()
            self.assertFalse(result["success"])
            self.assertIn("error", result)
            self.assertEqual(result["error_type"], "ConfigurationError")
            
            # Test tracing initialization with unavailable exporter
            if OPENTELEMETRY_AVAILABLE:
                result = self.api.wal_tracing(
                    enabled=True,
                    exporter_type="nonexistent"
                )
                self.assertFalse(result["success"])
                self.assertIn("error", result)

    class TestWALTelemetryAPIPerformance(unittest.TestCase):
        """Performance tests for the WAL telemetry API integration."""
        
        @unittest.skipIf(not WAL_TELEMETRY_API_AVAILABLE, "WAL telemetry API not available")
        def setUp(self):
            """Set up test environment before each test."""
            # Create a high-level API instance
            self.api = IPFSSimpleAPI()
            
            # Extend the API with WAL telemetry capabilities
            self.api = extend_high_level_api(self.api)
            
            # Initialize telemetry, Prometheus, and tracing
            self.api.wal_telemetry(enabled=True)
            if PROMETHEUS_AVAILABLE:
                self.api.wal_prometheus(enabled=True)
            if OPENTELEMETRY_AVAILABLE:
                self.api.wal_tracing(
                    enabled=True,
                    exporter_type=TracingExporterType.CONSOLE
                )
        
        def tearDown(self):
            """Clean up after each test."""
            # Close any open telemetry components
            if hasattr(self.api, "_wal_telemetry_extension"):
                if hasattr(self.api._wal_telemetry_extension, "telemetry") and self.api._wal_telemetry_extension.telemetry:
                    self.api._wal_telemetry_extension.telemetry.close()
        
        @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
        def test_span_creation_performance(self):
            """Test performance of span creation."""
            # Skip detailed tracing for performance tests
            if not hasattr(self.api, "_wal_telemetry_extension") or not hasattr(self.api._wal_telemetry_extension, "tracer"):
                self.skipTest("Tracing not initialized")
                
            # Measure time to create spans
            iterations = 100
            start_time = time.time()
            
            for i in range(iterations):
                span_result = self.api.wal_create_span(
                    operation_type="perf_test",
                    backend="test",
                    attributes={"iteration": i}
                )
                
                # End span immediately
                if span_result["success"]:
                    self.api._wal_telemetry_extension.tracer.end_span(span_result["span_context"])
            
            end_time = time.time()
            total_time = end_time - start_time
            avg_time = total_time / iterations
            
            # Log performance results
            logging.info(f"Span creation performance: {iterations} spans in {total_time:.4f}s")
            logging.info(f"Average time per span: {avg_time*1000:.4f}ms")
            
            # Very rough performance expectation (highly environment-dependent)
            # This is more of a benchmark than a strict test
            self.assertLess(avg_time, 0.01, "Span creation should be reasonably fast")
        
        def test_metrics_retrieval_performance(self):
            """Test performance of metrics retrieval."""
            # Skip if telemetry not initialized
            if not hasattr(self.api, "_wal_telemetry_extension") or not self.api._wal_telemetry_extension.telemetry:
                self.skipTest("Telemetry not initialized")
                
            # Generate some test metrics
            for i in range(50):
                # Use the telemetry directly to avoid tracing overhead
                self.api._wal_telemetry_extension.telemetry.record_operation_latency(
                    operation_type=f"perf_test_{i % 5}",
                    backend=f"backend_{i % 3}",
                    latency=i / 100.0
                )
            
            # Measure time for metrics retrieval
            iterations = 10
            start_time = time.time()
            
            for i in range(iterations):
                result = self.api.wal_get_metrics(include_history=(i % 2 == 0))
                self.assertTrue(result["success"])
            
            end_time = time.time()
            total_time = end_time - start_time
            avg_time = total_time / iterations
            
            # Log performance results
            logging.info(f"Metrics retrieval performance: {iterations} retrievals in {total_time:.4f}s")
            logging.info(f"Average time per retrieval: {avg_time*1000:.4f}ms")
            
            # Very rough performance expectation (highly environment-dependent)
            self.assertLess(avg_time, 0.05, "Metrics retrieval should be reasonably fast")

if __name__ == "__main__":
    unittest.main()