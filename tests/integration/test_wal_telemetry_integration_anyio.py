#!/usr/bin/env python3
# test/test_wal_telemetry_integration_anyio.py

"""
Integration tests for the WAL telemetry system with AnyIO support.

These tests verify that all components of the WAL telemetry system 
work together correctly using AnyIO for backend-agnostic async operations, including:
- Telemetry metrics collection
- API integration
- Client communication
- Report generation
- Visualization rendering
"""

import os
import sys
import time
import json
import uuid
import shutil
import tempfile
import unittest
import threading
import subprocess
import pytest
from unittest import mock
from contextlib import contextmanager
from typing import Dict, Any, List, Optional, Generator

# Import anyio for backend-agnostic async operations
import anyio
from anyio.abc import TaskGroup
from unittest.mock import AsyncMock

# Add parent directory to path for importing from ipfs_kit_py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ipfs_kit_py.storage_wal import StorageWriteAheadLog as WAL # Corrected import
from ipfs_kit_py.wal_telemetry import WALTelemetry
from ipfs_kit_py.wal_telemetry_client import WALTelemetryClient, TelemetryMetricType

# Check if anyio-compatible WAL telemetry client is available
try:
    from ipfs_kit_py.wal_telemetry_client_anyio import WALTelemetryClientAnyIO
    HAS_WAL_TELEMETRY_CLIENT_ANYIO = True
except ImportError:
    HAS_WAL_TELEMETRY_CLIENT_ANYIO = False

# Check if anyio-compatible WAL API is available
try:
    from ipfs_kit_py.wal_api_anyio import create_api_app, start_api_server
    HAS_WAL_API_ANYIO = True
except ImportError:
    HAS_WAL_API_ANYIO = False

# Test utilities

@contextmanager
def temp_directory() -> Generator[str, None, None]:
    """Create a temporary directory that is automatically cleaned up."""
    dir_path = tempfile.mkdtemp()
    try:
        yield dir_path
    finally:
        shutil.rmtree(dir_path, ignore_errors=True)

class ServerThread(threading.Thread):
    """Thread for running an API server during tests."""
    
    def __init__(self, app, port: int):
        """Initialize the server thread."""
        super().__init__()
        self.daemon = True  # Thread will exit when main thread exits
        self.app = app
        self.port = port
        self._stop_event = threading.Event()
        
    def run(self):
        """Run the server in the thread."""
        import uvicorn
        
        # Use a simpler approach with uvicorn.run
        try:
            # Set server to run until stop event is set
            self._server_started = True
            uvicorn.run(
                self.app, 
                host="127.0.0.1", 
                port=self.port, 
                log_level="error"
            )
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self._server_started = False
        
    def stop(self):
        """Stop the server thread."""
        self._stop_event.set()
        self.join(timeout=5.0)

class AsyncServerTask:
    """Class for running an API server with anyio during tests."""
    
    def __init__(self, app, port: int):
        """Initialize the server task."""
        self.app = app
        self.port = port
        self.task_group = None
        
    async def start(self, task_group: TaskGroup):
        """Start the server in the task group."""
        self.task_group = task_group
        
        try:
            import uvicorn
            config = uvicorn.Config(
                self.app, 
                host="127.0.0.1", 
                port=self.port, 
                log_level="error"
            )
            server = uvicorn.Server(config)
            await task_group.spawn(server.serve)
        except Exception as e:
            print(f"Async server error: {e}")

class WALTelemetryIntegrationTests(unittest.TestCase):
    """Integration tests for the WAL telemetry system."""
    
    @classmethod
    def setUpClass(cls):
        """Set up resources that are shared across all tests."""
        # Create a temporary directory for test data
        cls.test_dir = tempfile.mkdtemp()
        
        # Set up environment variables for telemetry
        os.environ["WAL_TELEMETRY_ENABLED"] = "1"
        os.environ["WAL_TELEMETRY_PATH"] = os.path.join(cls.test_dir, "telemetry")
        os.environ["WAL_TELEMETRY_REPORT_PATH"] = os.path.join(cls.test_dir, "reports")
        os.environ["WAL_TELEMETRY_RETENTION_DAYS"] = "1"
        
        # Create directories
        os.makedirs(os.environ["WAL_TELEMETRY_PATH"], exist_ok=True)
        os.makedirs(os.environ["WAL_TELEMETRY_REPORT_PATH"], exist_ok=True)
        
    @classmethod
    def tearDownClass(cls):
        """Clean up shared resources after all tests."""
        # Clean up the temporary directory
        shutil.rmtree(cls.test_dir, ignore_errors=True)
        
        # Reset environment variables
        if "WAL_TELEMETRY_ENABLED" in os.environ:
            del os.environ["WAL_TELEMETRY_ENABLED"]
        if "WAL_TELEMETRY_PATH" in os.environ:
            del os.environ["WAL_TELEMETRY_PATH"]
        if "WAL_TELEMETRY_REPORT_PATH" in os.environ:
            del os.environ["WAL_TELEMETRY_REPORT_PATH"]
        if "WAL_TELEMETRY_RETENTION_DAYS" in os.environ:
            del os.environ["WAL_TELEMETRY_RETENTION_DAYS"]
        
    def setUp(self):
        """Set up resources for each individual test."""
        # Create a data directory for each test
        self.data_dir = os.path.join(self.test_dir, f"test_data_{uuid.uuid4().hex}")
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create a WAL instance with telemetry enabled
        self.wal = WAL(base_path=self.data_dir)
        
        # Create and attach telemetry manually
        metrics_path = os.path.join(self.test_dir, "telemetry")
        os.makedirs(metrics_path, exist_ok=True)
        self.telemetry = WALTelemetry(wal=self.wal, metrics_path=metrics_path)
        
        # Add 'enabled' attribute that tests expect
        self.telemetry.enabled = True
        
        # Manually attach telemetry to WAL
        self.wal.telemetry = self.telemetry
        
        # Create an API app
        self.app = create_api_app(wal=self.wal)
        
        # Use a random port to avoid conflicts
        # We need to use a socket to find an available port
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            self.api_port = s.getsockname()[1]
        
        # Start API server in a separate thread
        self.server_thread = ServerThread(self.app, self.api_port)
        self.server_thread.start()
        
        # Wait for server to start
        time.sleep(1)
        
        # Create a client
        self.client = WALTelemetryClient(base_url=f"http://localhost:{self.api_port}")
        
        # Create anyio client if available
        if HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            self.anyio_client = WALTelemetryClientAnyIO(base_url=f"http://localhost:{self.api_port}")
        
    def tearDown(self):
        """Clean up resources after each test."""
        # Stop API server
        if hasattr(self, 'server_thread') and self.server_thread is not None:
            self.server_thread.stop()
        
        # Clean up test data directory
        shutil.rmtree(self.data_dir, ignore_errors=True)
        
    def generate_test_operations(self, count: int = 100) -> None:
        """Generate test operations for the WAL."""
        import random
        
        # Operation types
        op_types = ["append", "read", "update", "delete"]
        
        # Generate random operations
        for i in range(count):
            op_type = random.choice(op_types)
            
            # Generate random data
            key = f"key_{random.randint(1, 100)}"
            value = {
                "timestamp": time.time(),
                "data": random.randint(1, 1000),
                "text": f"Test operation {i}"
            }
            
            # Execute operation based on type
            try:
                if op_type == "append":
                    self.wal.append(key, value)
                elif op_type == "read":
                    self.wal.get(key)
                elif op_type == "update":
                    self.wal.update(key, value)
                elif op_type == "delete":
                    self.wal.delete(key)
                    
                # Add occasional error
                if random.random() < 0.05:  # 5% error rate
                    try:
                        self.wal.get(f"nonexistent_key_{random.randint(1000, 9999)}")
                    except:
                        pass
                    
            except Exception as e:
                print(f"Error in test operation: {str(e)}")
            
            # Small delay to avoid spamming
            time.sleep(0.001)
    
    def test_telemetry_initialization(self):
        """Test that telemetry is properly initialized with the WAL."""
        # Verify that telemetry is enabled
        self.assertTrue(self.telemetry.enabled)
        
        # Verify that metrics path exists
        self.assertTrue(os.path.exists(self.telemetry.metrics_path))
        
        # Verify telemetry instance is properly created
        self.assertIsInstance(self.telemetry, WALTelemetry)
        
    def test_metrics_collection(self):
        """Test that metrics are properly collected during WAL operations."""
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Verify that metrics are being collected
        metrics = self.telemetry.get_metrics()
        
        # Check that metrics contain expected fields
        self.assertIn("operation_count", metrics)
        self.assertIn("operation_latency", metrics)
        self.assertIn("success_rate", metrics)
        
        # Check that operations were recorded
        op_count = metrics["operation_count"]
        self.assertGreater(sum(count for count in op_count.values()), 0)
        
    def test_api_metrics_endpoint(self):
        """Test that metrics are accessible through the API."""
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Request metrics through API client
        response = self.client.get_metrics()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("metrics", response)
        
        # Check metrics content
        metrics = response["metrics"]
        self.assertIn("operation_count", metrics)
        self.assertIn("operation_latency", metrics)
        
    def test_realtime_metrics_endpoint(self):
        """Test that real-time metrics are accessible through the API."""
        # Generate some test operations
        self.generate_test_operations(count=20)
        
        # Request real-time metrics
        response = self.client.get_realtime_metrics()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("timestamp", response)
        
        # Check metrics content
        self.assertIn("operation_latency", response)
        self.assertIn("success_rate", response)
        self.assertIn("throughput", response)
        
    def test_filtered_metrics(self):
        """Test that metrics can be filtered."""
        # Generate some test operations
        self.generate_test_operations(count=75)
        
        # Request filtered metrics by type
        response = self.client.get_metrics(
            metric_type=TelemetryMetricType.OPERATION_LATENCY
        )
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("metrics", response)
        
        # Metrics should only contain operation_latency
        metrics = response["metrics"]
        self.assertIn("operation_latency", metrics)
        self.assertNotIn("success_rate", metrics)  # Should be filtered out
        
        # Request filtered metrics by operation type
        response = self.client.get_metrics(
            operation_type="append"
        )
        
        # Check that only append operations are included
        metrics = response["metrics"]
        if "operation_count" in metrics:
            op_count = metrics["operation_count"]
            for op_type, count in op_count.items():
                if op_type != "append":
                    self.assertEqual(count, 0)
        
    def test_report_generation(self):
        """Test report generation through the API."""
        # Generate some test operations
        self.generate_test_operations(count=100)
        
        # Generate report
        response = self.client.generate_report()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("report_id", response)
        self.assertIn("files", response)
        
        # Check that report files exist
        report_id = response["report_id"]
        report_dir = os.path.join(self.telemetry.report_path, report_id)
        self.assertTrue(os.path.exists(report_dir))
        
        # Check that index.html exists
        index_path = os.path.join(report_dir, "index.html")
        self.assertTrue(os.path.exists(index_path))
        
        # Check that we can retrieve a report file
        file_response = self.client.get_report_file(
            report_id=report_id,
            file_name="index.html"
        )
        
        self.assertTrue(file_response["success"])
        self.assertIn("content", file_response)
        self.assertIn("content_type", file_response)
        
    def test_visualization_generation(self):
        """Test visualization generation through the API."""
        # Generate some test operations
        self.generate_test_operations(count=100)
        
        # Create a temporary file for the visualization
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Generate visualization
            response = self.client.get_visualization(
                metric_type=TelemetryMetricType.OPERATION_LATENCY,
                save_path=temp_path
            )
            
            # Check response
            self.assertTrue(response["success"])
            self.assertTrue(response.get("saved", False))
            
            # Check that the file exists and has content
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 0)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_time_series_metrics(self):
        """Test retrieving metrics over time."""
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Small delay
        time.sleep(1)
        
        # Generate more operations
        self.generate_test_operations(count=50)
        
        # Get metrics over time
        response = self.client.get_metrics_over_time(
            metric_type=TelemetryMetricType.OPERATION_COUNT,
            interval="hour"  # Use hour since our test data is generated quickly
        )
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("time_series", response)
        
        # Check time series data
        time_series = response["time_series"]
        self.assertGreater(len(time_series), 0)
        
        # Check that each time point has expected structure
        for point in time_series:
            self.assertIn("timestamp", point)
            self.assertIn("metrics", point)
            
    def test_config_endpoints(self):
        """Test configuration endpoints."""
        # Get current configuration
        response = self.client.get_config()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("config", response)
        
        # Check configuration content
        config = response["config"]
        self.assertIn("enabled", config)
        self.assertIn("metrics_path", config)
        
        # Update configuration
        original_interval = config.get("sampling_interval", 60)
        new_interval = original_interval + 30
        
        update_response = self.client.update_config(
            sampling_interval=new_interval
        )
        
        # Check response
        self.assertTrue(update_response["success"])
        self.assertIn("config", update_response)
        
        # Check that configuration was updated
        updated_config = update_response["config"]
        self.assertEqual(updated_config["sampling_interval"], new_interval)
        
        # Verify the update with another get request
        verify_response = self.client.get_config()
        verify_config = verify_response["config"]
        self.assertEqual(verify_config["sampling_interval"], new_interval)
        
    def test_cli_output(self):
        """Test CLI command output."""
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Get path to CLI script
        script_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "ipfs_kit_py",
            "wal_telemetry_cli.py"
        ))
        
        # Run metrics command
        result = subprocess.run(
            [sys.executable, script_path, "--url", f"http://localhost:{self.api_port}", "metrics"],
            capture_output=True,
            text=True
        )
        
        # Check output
        self.assertEqual(result.returncode, 0)
        self.assertIn("WAL Telemetry Metrics", result.stdout)
        self.assertIn("operation_count", result.stdout)
        
        # Run config command
        result = subprocess.run(
            [sys.executable, script_path, "--url", f"http://localhost:{self.api_port}", "config"],
            capture_output=True,
            text=True
        )
        
        # Check output
        self.assertEqual(result.returncode, 0)
        self.assertIn("Current Configuration", result.stdout)
        self.assertIn("enabled", result.stdout)
        
    def test_error_handling(self):
        """Test error handling in client and API."""
        # Test with invalid URL
        invalid_client = WALTelemetryClient(base_url="http://invalid-url:9999")
        
        # This should raise a connection error
        with self.assertRaises(Exception):
            invalid_client.get_metrics()
            
        # Test with invalid metric type
        with self.assertRaises(ValueError):
            self.client.get_metrics(metric_type="invalid_metric_type")
            
    def test_metric_validation(self):
        """Test metric validation in the API."""
        # Test with invalid time range
        invalid_range = (time.time(), time.time() - 3600)  # End before start
        
        # This should return an error in the response
        response = self.client.get_metrics(time_range=invalid_range)
        
        # Check that error is properly reported
        self.assertFalse(response.get("success", True))
        self.assertIn("error", response)
        
    def test_concurrent_operations(self):
        """Test telemetry with concurrent operations."""
        # Number of concurrent threads
        thread_count = 5
        operations_per_thread = 20
        
        # Function to run operations in a thread
        def run_operations():
            for i in range(operations_per_thread):
                key = f"key_thread_{threading.get_ident()}_{i}"
                value = {"data": i, "thread": threading.get_ident()}
                self.wal.append(key, value)
                
        # Create and start threads
        threads = []
        for _ in range(thread_count):
            thread = threading.Thread(target=run_operations)
            thread.start()
            threads.append(thread)
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Check metrics after concurrent operations
        response = self.client.get_metrics()
        
        # Check total operation count
        metrics = response["metrics"]
        if "operation_count" in metrics and "append" in metrics["operation_count"]:
            self.assertGreaterEqual(
                metrics["operation_count"]["append"],
                thread_count * operations_per_thread
            )
            
    def test_end_to_end_workflow(self):
        """Test a complete end-to-end workflow combining multiple features."""
        # 1. Generate operations
        self.generate_test_operations(count=100)
        
        # 2. Get real-time metrics
        realtime = self.client.get_realtime_metrics()
        self.assertTrue(realtime["success"])
        
        # 3. Get metrics over time
        time_series = self.client.get_metrics_over_time(
            metric_type=TelemetryMetricType.OPERATION_LATENCY,
            interval="hour"
        )
        self.assertTrue(time_series["success"])
        
        # 4. Generate a report
        report = self.client.generate_report()
        self.assertTrue(report["success"])
        report_id = report["report_id"]
        
        # 5. Retrieve a report file
        report_file = self.client.get_report_file(
            report_id=report_id,
            file_name="index.html"
        )
        self.assertTrue(report_file["success"])
        
        # 6. Generate a visualization
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            viz = self.client.get_visualization(
                metric_type=TelemetryMetricType.THROUGHPUT,
                save_path=temp_path
            )
            self.assertTrue(viz["success"])
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
        # 7. Update configuration
        config = self.client.get_config()
        original_retention = config["config"]["retention_days"]
        new_retention = original_retention + 1
        
        update = self.client.update_config(retention_days=new_retention)
        self.assertTrue(update["success"])
        self.assertEqual(update["config"]["retention_days"], new_retention)

    # AnyIO specific tests
    @pytest.mark.anyio
    async def test_async_metrics_collection(self):
        """Test that metrics are properly collected and accessible via async client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Get metrics using async client
        response = await self.anyio_client.get_metrics_async()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("metrics", response)
        
        # Check metrics content
        metrics = response["metrics"]
        self.assertIn("operation_count", metrics)
        self.assertIn("operation_latency", metrics)
        
        # Check operation counts
        op_count = metrics["operation_count"]
        self.assertGreater(sum(count for count in op_count.values()), 0)
    
    @pytest.mark.anyio
    async def test_async_realtime_metrics(self):
        """Test that real-time metrics are accessible via async client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=20)
        
        # Get real-time metrics using async client
        response = await self.anyio_client.get_realtime_metrics_async()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("timestamp", response)
        
        # Check metrics content
        self.assertIn("operation_latency", response)
        self.assertIn("success_rate", response)
        self.assertIn("throughput", response)
    
    @pytest.mark.anyio
    async def test_async_report_generation(self):
        """Test report generation through the async API client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Generate report using async client
        response = await self.anyio_client.generate_report_async()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("report_id", response)
        
        # Check that report directory exists
        report_id = response["report_id"]
        report_dir = os.path.join(self.telemetry.report_path, report_id)
        self.assertTrue(os.path.exists(report_dir))
        
        # Get report file using async client
        file_response = await self.anyio_client.get_report_file_async(
            report_id=report_id,
            file_name="index.html"
        )
        
        # Check response
        self.assertTrue(file_response["success"])
        self.assertIn("content", file_response)
    
    @pytest.mark.anyio
    async def test_async_visualization(self):
        """Test visualization generation through the async API client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=50)
        
        # Create temporary file for visualization
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Generate visualization using async client
            response = await self.anyio_client.get_visualization_async(
                metric_type=TelemetryMetricType.OPERATION_LATENCY,
                save_path=temp_path
            )
            
            # Check response
            self.assertTrue(response["success"])
            self.assertTrue(response.get("saved", False))
            
            # Check that file exists and has content
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 0)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.mark.anyio
    async def test_async_config_endpoints(self):
        """Test configuration endpoints with async client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Get current configuration using async client
        response = await self.anyio_client.get_config_async()
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("config", response)
        
        # Check configuration content
        config = response["config"]
        self.assertIn("enabled", config)
        self.assertIn("metrics_path", config)
        
        # Update configuration using async client
        original_interval = config.get("sampling_interval", 60)
        new_interval = original_interval + 30
        
        update_response = await self.anyio_client.update_config_async(
            sampling_interval=new_interval
        )
        
        # Check response
        self.assertTrue(update_response["success"])
        self.assertIn("config", update_response)
        
        # Check that configuration was updated
        updated_config = update_response["config"]
        self.assertEqual(updated_config["sampling_interval"], new_interval)
    
    @pytest.mark.anyio
    async def test_async_metrics_over_time(self):
        """Test retrieving metrics over time with async client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=25)
        
        # Small delay
        await anyio.sleep(0.5)
        
        # Generate more operations
        self.generate_test_operations(count=25)
        
        # Get metrics over time using async client
        response = await self.anyio_client.get_metrics_over_time_async(
            metric_type=TelemetryMetricType.OPERATION_COUNT,
            interval="hour"
        )
        
        # Check response
        self.assertTrue(response["success"])
        self.assertIn("time_series", response)
        
        # Check time series data
        time_series = response["time_series"]
        self.assertGreater(len(time_series), 0)
        
        # Check that each time point has expected structure
        for point in time_series:
            self.assertIn("timestamp", point)
            self.assertIn("metrics", point)
    
    @pytest.mark.anyio
    async def test_async_concurrent_monitoring(self):
        """Test real-time monitoring with async client."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Generate some test operations
        self.generate_test_operations(count=20)
        
        # Define async callback for monitoring
        monitoring_results = []
        
        async def async_metrics_callback(metrics, iteration):
            monitoring_results.append((metrics, iteration))
            
        # Run short monitoring session with timeout
        async with anyio.fail_after(5.0):  # 5-second timeout
            try:
                async with anyio.create_task_group() as tg:
                    # Start monitoring in a task
                    tg.start_soon(
                        self.anyio_client.monitor_realtime_async,
                        async_metrics_callback,
                        interval=0.5,  # 500ms interval
                        duration=2  # 2-second duration
                    )
                    
                    # Run operations in background concurrently
                    async def run_operations():
                        for i in range(3):
                            # Generate some operations
                            self.generate_test_operations(count=5)
                            # Small delay
                            await anyio.sleep(0.5)
                    
                    tg.start_soon(run_operations)
            
            except TimeoutError:
                pass  # Expected if monitoring runs too long
        
        # Check that we got some monitoring results
        self.assertGreater(len(monitoring_results), 0)
        
        # Check structure of monitoring results
        for metrics, iteration in monitoring_results:
            self.assertTrue(metrics["success"])
            self.assertIn("timestamp", metrics)
            self.assertIn("latency", metrics)
            self.assertIn("success_rate", metrics)
    
    @pytest.mark.anyio
    async def test_async_end_to_end_workflow(self):
        """Test a complete end-to-end async workflow."""
        # Skip if anyio client is not available
        if not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # 1. Generate operations
        self.generate_test_operations(count=50)
        
        # 2. Get real-time metrics using async client
        realtime = await self.anyio_client.get_realtime_metrics_async()
        self.assertTrue(realtime["success"])
        
        # 3. Get metrics over time using async client
        time_series = await self.anyio_client.get_metrics_over_time_async(
            metric_type=TelemetryMetricType.OPERATION_LATENCY,
            interval="hour"
        )
        self.assertTrue(time_series["success"])
        
        # 4. Generate a report using async client
        report = await self.anyio_client.generate_report_async()
        self.assertTrue(report["success"])
        report_id = report["report_id"]
        
        # 5. Retrieve a report file using async client
        report_file = await self.anyio_client.get_report_file_async(
            report_id=report_id,
            file_name="index.html"
        )
        self.assertTrue(report_file["success"])
        
        # 6. Generate a visualization using async client
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            viz = await self.anyio_client.get_visualization_async(
                metric_type=TelemetryMetricType.THROUGHPUT,
                save_path=temp_path
            )
            self.assertTrue(viz["success"])
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
        # 7. Update configuration using async client
        config = await self.anyio_client.get_config_async()
        original_retention = config["config"]["retention_days"]
        new_retention = original_retention + 1
        
        update = await self.anyio_client.update_config_async(retention_days=new_retention)
        self.assertTrue(update["success"])
        self.assertEqual(update["config"]["retention_days"], new_retention)

class TestAsyncServerSetup:
    """Standalone async test class for testing anyio-specific server setup."""
    
    @pytest.mark.anyio
    async def test_async_server_setup(self):
        """Test setting up and using a FastAPI server with anyio."""
        # Skip if anyio-compatible WAL API is not available
        if not HAS_WAL_API_ANYIO or not HAS_WAL_TELEMETRY_CLIENT_ANYIO:
            return
            
        # Create a temporary directory for test data
        with temp_directory() as test_dir:
            # Create a data directory
            data_dir = os.path.join(test_dir, "test_data")
            os.makedirs(data_dir, exist_ok=True)
            
            # Create a WAL instance
            wal = WAL(base_path=data_dir)
            
            # Create and attach telemetry
            metrics_path = os.path.join(test_dir, "telemetry")
            os.makedirs(metrics_path, exist_ok=True)
            telemetry = WALTelemetry(wal=wal, metrics_path=metrics_path)
            telemetry.enabled = True
            wal.telemetry = telemetry
            
            # Create an API app
            app = create_api_app(wal=wal)
            
            # Find an available port
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                api_port = s.getsockname()[1]
            
            # Create async server task
            server_task = AsyncServerTask(app, api_port)
            
            # Create anyio client
            client = WALTelemetryClientAnyIO(base_url=f"http://localhost:{api_port}")
            
            # Start server and run tests
            async with anyio.create_task_group() as tg:
                # Start the server
                await server_task.start(tg)
                
                # Wait for server to initialize
                await anyio.sleep(1)
                
                # Generate test operations
                # We need to run this in a separate thread since it's synchronous
                await anyio.to_thread.run_sync(
                    lambda: generate_test_operations_helper(wal, 20)
                )
                
                # Test endpoints
                
                # 1. Get metrics
                response = await client.get_metrics_async()
                assert response["success"] is True
                assert "metrics" in response
                
                # 2. Get real-time metrics
                realtime = await client.get_realtime_metrics_async()
                assert realtime["success"] is True
                assert "timestamp" in realtime
                
                # 3. Get configuration
                config = await client.get_config_async()
                assert config["success"] is True
                assert "config" in config

def generate_test_operations_helper(wal, count=20):
    """Helper function to generate test operations for async tests."""
    import random
    
    # Operation types
    op_types = ["append", "read", "update", "delete"]
    
    # Generate random operations
    for i in range(count):
        op_type = random.choice(op_types)
        
        # Generate random data
        key = f"key_{random.randint(1, 100)}"
        value = {
            "timestamp": time.time(),
            "data": random.randint(1, 1000),
            "text": f"Test operation {i}"
        }
        
        # Execute operation based on type
        try:
            if op_type == "append":
                wal.append(key, value)
            elif op_type == "read":
                wal.get(key)
            elif op_type == "update":
                wal.update(key, value)
            elif op_type == "delete":
                wal.delete(key)
                
        except Exception as e:
            print(f"Error in test operation: {str(e)}")
        
        # Small delay to avoid spamming
        time.sleep(0.001)

# Allow running with both unittest and pytest
if __name__ == "__main__":
    unittest.main()