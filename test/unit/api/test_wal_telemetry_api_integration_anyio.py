#!/usr/bin/env python3
# test/test_wal_telemetry_api_integration_anyio.py

"""
Integration tests for the WAL telemetry API integration with AnyIO support.

These tests verify that the WAL telemetry API correctly integrates with
the high-level API, providing telemetry, Prometheus metrics, and distributed tracing
using AnyIO for backend-agnostic async operations.
"""

import os
import time
import unittest
import logging
import tempfile
import json
from unittest.mock import patch, MagicMock, AsyncMock
import anyio
import pytest

# Set up logging to capture events during tests
logging.basicConfig(level=logging.DEBUG)

# Default values in case imports fail
ALL_COMPONENTS_AVAILABLE = False
PROMETHEUS_AVAILABLE = False
OPENTELEMETRY_AVAILABLE = False
FASTAPI_AVAILABLE = False

# Try to import the necessary components
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.wal_telemetry_api_anyio import extend_high_level_api, WALTelemetryAPIExtension
    import anyio

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
    ALL_COMPONENTS_AVAILABLE = True
except ImportError as e:
    # Print helpful information about missing components
    logging.warning(f"Skipping WAL telemetry API tests: {str(e)}")
    # ALL_COMPONENTS_AVAILABLE remains False
    # PROMETHEUS_AVAILABLE and others retain their default False values

@unittest.skipIf(not ALL_COMPONENTS_AVAILABLE, "Required components not available")
class TestWALTelemetryAPIIntegrationAnyIO(unittest.TestCase):
    """Test WAL telemetry API integration with AnyIO support."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock IPFSSimpleAPI
        self.mock_api = MagicMock(spec=IPFSSimpleAPI)

        # Create a mock WAL object with telemetry capability
        self.mock_wal = MagicMock()
        self.mock_telemetry = MagicMock()
        self.mock_wal.telemetry = self.mock_telemetry

        # Set up basic mock return values
        self.mock_api.wal = self.mock_wal

        # Set up run_async method for AnyIO compatibility
        def run_async_func(async_func, *args, **kwargs):
            """Run async function in a loop"""
            loop = anyio.new_event_loop()
            try:
                return loop.run_until_complete(async_func(*args, **kwargs))
            finally:
                loop.close()

        self.mock_api.run_async = MagicMock(side_effect=run_async_func)

        # Default metrics data
        self.default_metrics = {
            "total_operations": 42,
            "successful_operations": 38,
            "failed_operations": 4,
            "average_latency_ms": 120.5,
            "operation_counts": {
                "add": 20,
                "get": 15,
                "remove": 7
            },
            "backend_performance": {
                "ipfs": {
                    "operations": 30,
                    "success_rate": 0.93,
                    "average_latency_ms": 110.2
                },
                "s3": {
                    "operations": 12,
                    "success_rate": 0.91,
                    "average_latency_ms": 145.8
                }
            }
        }

        # Mock the telemetry methods
        self.mock_telemetry.get_metrics.return_value = self.default_metrics
        self.mock_telemetry.get_metrics_async = AsyncMock(return_value=self.default_metrics)

        # Create a temporary file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = os.path.join(self.temp_dir, "test_report.json")

        # Mock the generate_report method
        report_content = {"timestamp": time.time(), "metrics": self.default_metrics}
        self.mock_telemetry.generate_report.return_value = {
            "success": True,
            "report_path": self.temp_file,
            "report": report_content
        }
        self.mock_telemetry.generate_report_async = AsyncMock(return_value={
            "success": True,
            "report_path": self.temp_file,
            "report": report_content
        })

        # Create the report file
        with open(self.temp_file, 'w') as f:
            json.dump(report_content, f)

        # Extend the API with WAL telemetry
        self.api_extension = WALTelemetryAPIExtension(self.mock_api)
        extend_high_level_api(self.mock_api)

    def tearDown(self):
        """Clean up resources after tests."""
        # Clean up temporary files
        try:
            os.remove(self.temp_file)
            os.rmdir(self.temp_dir)
        except (OSError, IOError):
            # Ignore errors during cleanup
            pass

    def test_api_extension(self):
        """Test that the API extension is properly registered."""
        self.assertEqual(self.api_extension.api, self.mock_api)
        self.assertTrue(hasattr(self.mock_api, "get_telemetry_metrics"))
        self.assertTrue(hasattr(self.mock_api, "get_telemetry_metrics_async"))
        self.assertTrue(hasattr(self.mock_api, "generate_telemetry_report"))
        self.assertTrue(hasattr(self.mock_api, "generate_telemetry_report_async"))
        self.assertTrue(hasattr(self.mock_api, "visualize_telemetry_metrics"))
        self.assertTrue(hasattr(self.mock_api, "visualize_telemetry_metrics_async"))

    def test_get_telemetry_metrics_sync(self):
        """Test getting telemetry metrics synchronously."""
        # Set up the mock
        self.mock_telemetry.get_metrics.return_value = self.default_metrics

        # Call the method
        result = self.mock_api.get_telemetry_metrics()

        # Verify the result
        self.mock_telemetry.get_metrics.assert_called_once()
        self.assertEqual(result, self.default_metrics)

    @pytest.mark.asyncio
    async def test_get_telemetry_metrics_async(self):
        """Test getting telemetry metrics asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()
        mock_api.wal.telemetry.get_metrics_async = AsyncMock(return_value=self.default_metrics)

        # Create the extension
        api_extension = WALTelemetryAPIExtension(mock_api)

        # Call the async method directly
        result = await api_extension.get_telemetry_metrics_async()

        # Verify the result
        mock_api.wal.telemetry.get_metrics_async.assert_called_once()
        self.assertEqual(result, self.default_metrics)

    def test_generate_telemetry_report_sync(self):
        """Test generating a telemetry report synchronously."""
        # Call the method
        result = self.mock_api.generate_telemetry_report(output_format="json")

        # Verify the result
        self.mock_telemetry.generate_report.assert_called_once_with(output_format="json")
        self.assertTrue(result["success"])
        self.assertEqual(result["report_path"], self.temp_file)
        self.assertIn("report", result)

    @pytest.mark.asyncio
    async def test_generate_telemetry_report_async(self):
        """Test generating a telemetry report asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        # Setup the mock return value
        report_content = {"timestamp": time.time(), "metrics": self.default_metrics}
        expected_return = {
            "success": True,
            "report_path": self.temp_file,
            "report": report_content
        }
        mock_api.wal.telemetry.generate_report_async = AsyncMock(return_value=expected_return)

        # Create the extension
        api_extension = WALTelemetryAPIExtension(mock_api)

        # Call the async method directly
        result = await api_extension.generate_telemetry_report_async(output_format="json")

        # Verify the result
        mock_api.wal.telemetry.generate_report_async.assert_called_once_with(output_format="json")
        self.assertTrue(result["success"])
        self.assertEqual(result["report_path"], self.temp_file)
        self.assertIn("report", result)

    @patch('anyio.to_thread.run_sync')
    def test_visualize_telemetry_metrics_sync(self, mock_run_sync):
        """Test visualizing telemetry metrics synchronously using AnyIO thread offloading."""
        # Setup mock
        viz_path = os.path.join(self.temp_dir, "metrics_viz.png")
        mock_run_sync.return_value = {
            "success": True,
            "visualization_path": viz_path
        }

        # Call the method
        with patch.object(self.api_extension, 'run_async', side_effect=lambda f, *args, **kwargs: f(*args, **kwargs)):
            result = self.mock_api.visualize_telemetry_metrics(metric_type="operations", time_range="1d")

        # Verify the result uses AnyIO's to_thread.run_sync
        self.assertTrue(mock_run_sync.called)
        self.assertTrue(result["success"])
        self.assertEqual(result["visualization_path"], viz_path)

    @pytest.mark.asyncio
    async def test_visualize_telemetry_metrics_async(self):
        """Test visualizing telemetry metrics asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        # Setup the mock visualization function
        viz_path = os.path.join(self.temp_dir, "metrics_viz.png")

        with patch('anyio.to_thread.run_sync') as mock_run_sync:
            # Setup the mock return
            mock_run_sync.return_value = {
                "success": True,
                "visualization_path": viz_path
            }

            # Create the extension
            api_extension = WALTelemetryAPIExtension(mock_api)

            # Call the async method directly
            result = await api_extension.visualize_telemetry_metrics_async(
                metric_type="operations",
                time_range="1d"
            )

            # Verify the result
            self.assertTrue(mock_run_sync.called)
            self.assertTrue(result["success"])
            self.assertEqual(result["visualization_path"], viz_path)

    @unittest.skipIf(not PROMETHEUS_AVAILABLE, "Prometheus client not available")
    def test_prometheus_integration(self):
        """Test integration with Prometheus metrics."""
        # Mock the Prometheus exporter
        with patch('ipfs_kit_py.wal_telemetry_prometheus_anyio.WALTelemetryPrometheusExporter') as mock_exporter_class:
            mock_exporter = MagicMock()
            mock_exporter_class.return_value = mock_exporter
            mock_exporter.start = MagicMock(return_value={"success": True, "port": 9090})
            mock_exporter.start_async = AsyncMock(return_value={"success": True, "port": 9090})

            # Call the setup method
            result = self.mock_api.setup_telemetry_prometheus_exporter(
                port=9090,
                metrics_path="/metrics"
            )

            # Verify the result
            self.assertTrue(result["success"])
            self.assertEqual(result["port"], 9090)
            mock_exporter.start.assert_called_once()

    @pytest.mark.asyncio
    @unittest.skipIf(not PROMETHEUS_AVAILABLE, "Prometheus client not available")
    async def test_prometheus_integration_async(self):
        """Test integration with Prometheus metrics asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        # Mock the Prometheus exporter
        with patch('ipfs_kit_py.wal_telemetry_prometheus_anyio.WALTelemetryPrometheusExporter') as mock_exporter_class:
            mock_exporter = MagicMock()
            mock_exporter_class.return_value = mock_exporter
            mock_exporter.start_async = AsyncMock(return_value={"success": True, "port": 9090})

            # Create the extension
            api_extension = WALTelemetryAPIExtension(mock_api)

            # Call the async method directly
            result = await api_extension.setup_telemetry_prometheus_exporter_async(
                port=9090,
                metrics_path="/metrics"
            )

            # Verify the result
            self.assertTrue(result["success"])
            self.assertEqual(result["port"], 9090)
            mock_exporter.start_async.assert_called_once()

    @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
    def test_tracing_integration(self):
        """Test integration with distributed tracing."""
        # Mock the tracing setup
        with patch('ipfs_kit_py.wal_telemetry_tracing_anyio.WALTracing') as mock_tracing_class:
            mock_tracing = MagicMock()
            mock_tracing_class.return_value = mock_tracing
            mock_tracing.setup_tracing = MagicMock(return_value={"success": True})
            mock_tracing.setup_tracing_async = AsyncMock(return_value={"success": True})

            # Call the setup method
            result = self.mock_api.setup_telemetry_tracing(
                service_name="ipfs-kit-test",
                exporter_type="console"
            )

            # Verify the result
            self.assertTrue(result["success"])
            mock_tracing.setup_tracing.assert_called_once()

    @pytest.mark.asyncio
    @unittest.skipIf(not OPENTELEMETRY_AVAILABLE, "OpenTelemetry not available")
    async def test_tracing_integration_async(self):
        """Test integration with distributed tracing asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        # Mock the tracing setup
        with patch('ipfs_kit_py.wal_telemetry_tracing_anyio.WALTracing') as mock_tracing_class:
            mock_tracing = MagicMock()
            mock_tracing_class.return_value = mock_tracing
            mock_tracing.setup_tracing_async = AsyncMock(return_value={"success": True})

            # Create the extension
            api_extension = WALTelemetryAPIExtension(mock_api)

            # Call the async method directly
            result = await api_extension.setup_telemetry_tracing_async(
                service_name="ipfs-kit-test",
                exporter_type="console"
            )

            # Verify the result
            self.assertTrue(result["success"])
            mock_tracing.setup_tracing_async.assert_called_once()

    def test_get_telemetry_configuration(self):
        """Test getting telemetry configuration."""
        # Set up the mock
        self.mock_telemetry.get_config.return_value = {
            "metrics_enabled": True,
            "log_level": "INFO",
            "collection_interval": 60,
            "metrics_retention_days": 7
        }

        # Call the method
        result = self.mock_api.get_telemetry_configuration()

        # Verify the result
        self.mock_telemetry.get_config.assert_called_once()
        self.assertEqual(result["metrics_enabled"], True)
        self.assertEqual(result["log_level"], "INFO")

    @pytest.mark.asyncio
    async def test_get_telemetry_configuration_async(self):
        """Test getting telemetry configuration asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        config = {
            "metrics_enabled": True,
            "log_level": "INFO",
            "collection_interval": 60,
            "metrics_retention_days": 7
        }
        mock_api.wal.telemetry.get_config_async = AsyncMock(return_value=config)

        # Create the extension
        api_extension = WALTelemetryAPIExtension(mock_api)

        # Call the async method directly
        result = await api_extension.get_telemetry_configuration_async()

        # Verify the result
        mock_api.wal.telemetry.get_config_async.assert_called_once()
        self.assertEqual(result["metrics_enabled"], True)
        self.assertEqual(result["log_level"], "INFO")

    def test_update_telemetry_configuration(self):
        """Test updating telemetry configuration."""
        # Set up the mock
        new_config = {
            "metrics_enabled": False,
            "log_level": "DEBUG",
            "collection_interval": 30
        }
        self.mock_telemetry.update_config.return_value = {
            "success": True,
            "config": new_config
        }

        # Call the method
        result = self.mock_api.update_telemetry_configuration(new_config)

        # Verify the result
        self.mock_telemetry.update_config.assert_called_once_with(new_config)
        self.assertTrue(result["success"])
        self.assertEqual(result["config"]["metrics_enabled"], False)
        self.assertEqual(result["config"]["log_level"], "DEBUG")

    @pytest.mark.asyncio
    async def test_update_telemetry_configuration_async(self):
        """Test updating telemetry configuration asynchronously."""
        # Create a new mock API for direct async testing
        mock_api = MagicMock(spec=IPFSSimpleAPI)
        mock_api.wal = MagicMock()
        mock_api.wal.telemetry = MagicMock()

        new_config = {
            "metrics_enabled": False,
            "log_level": "DEBUG",
            "collection_interval": 30
        }

        expected_result = {
            "success": True,
            "config": new_config
        }

        mock_api.wal.telemetry.update_config_async = AsyncMock(return_value=expected_result)

        # Create the extension
        api_extension = WALTelemetryAPIExtension(mock_api)

        # Call the async method directly
        result = await api_extension.update_telemetry_configuration_async(new_config)

        # Verify the result
        mock_api.wal.telemetry.update_config_async.assert_called_once_with(new_config)
        self.assertTrue(result["success"])
        self.assertEqual(result["config"]["metrics_enabled"], False)
        self.assertEqual(result["config"]["log_level"], "DEBUG")

if __name__ == "__main__":
    unittest.main()
