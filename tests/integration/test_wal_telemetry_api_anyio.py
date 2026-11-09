#!/usr/bin/env python3
# test/test_wal_telemetry_api_anyio.py

"""
Unit tests for the WAL Telemetry API with AnyIO support.

These tests validate the telemetry-related API endpoints in the Write-Ahead Log system:
1. Metrics retrieval and aggregation
2. Real-time telemetry data
3. Report generation
4. Visualization endpoints
5. Concurrent operations using AnyIO task groups
"""

import os
import json
import time
import tempfile
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

import anyio
import pytest
from fastapi.testclient import TestClient

from ipfs_kit_py.storage_wal import (
    StorageWriteAheadLog,
    BackendHealthMonitor,
    OperationType,
    OperationStatus,
    BackendType
)

# Only import telemetry components if available
try:
    from ipfs_kit_py.wal_telemetry import (
        WALTelemetry,
        TelemetryMetricType,
        TelemetryAggregation
    )
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    TelemetryMetricType = None
    TelemetryAggregation = None

# Only import FastAPI components if available
try:
    from ipfs_kit_py.api import app
    from ipfs_kit_py.wal_api_anyio import (
        wal_router,
        register_wal_api,
        get_telemetry_instance
    )
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

@unittest.skipIf(not FASTAPI_AVAILABLE or not TELEMETRY_AVAILABLE, 
                 "FastAPI or WAL Telemetry not available")
class TestWALTelemetryAPIAnyIO(unittest.TestCase):
    """Test cases for the WAL Telemetry API with AnyIO support."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock WAL
        self.mock_wal = MagicMock(spec=StorageWriteAheadLog)
        
        # Mock telemetry
        self.mock_telemetry = MagicMock(spec=WALTelemetry)
        
        # Setup mock metrics response
        self.mock_metrics = {
            "success": True,
            "metrics": {
                "operation_count": {
                    "total": 100,
                    "by_type": {
                        "add": 30,
                        "pin": 20,
                        "get": 50
                    },
                    "by_status": {
                        "completed": 80,
                        "failed": 10,
                        "pending": 10
                    }
                },
                "operation_latency": {
                    "average": 0.5,
                    "by_type": {
                        "add": 0.8,
                        "pin": 0.2,
                        "get": 0.3
                    }
                },
                "success_rate": {
                    "overall": 0.8,
                    "by_type": {
                        "add": 0.9,
                        "pin": 0.7,
                        "get": 0.8
                    }
                }
            }
        }
        
        # Setup mock real-time metrics
        self.mock_realtime_metrics = {
            "success": True,
            "latency": {
                "add": {"avg": 0.5, "p95": 0.9, "p99": 1.2},
                "pin": {"avg": 0.2, "p95": 0.4, "p99": 0.6},
                "get": {"avg": 0.3, "p95": 0.5, "p99": 0.8}
            },
            "success_rate": {
                "add": 0.9,
                "pin": 0.7,
                "get": 0.8,
                "overall": 0.8
            },
            "error_rate": {
                "add": 0.1,
                "pin": 0.3,
                "get": 0.2,
                "overall": 0.2
            },
            "throughput": {
                "add": 10.5,
                "pin": 5.2,
                "get": 15.8,
                "overall": 31.5
            },
            "status_distribution": {
                "add": {"completed": 27, "failed": 3, "pending": 0},
                "pin": {"completed": 14, "failed": 6, "pending": 0},
                "get": {"completed": 40, "failed": 0, "pending": 10}
            }
        }
        
        # Mock get_metrics to return our mock metrics
        self.mock_telemetry.get_metrics.return_value = self.mock_metrics
        
        # Mock get_real_time_metrics to return our mock real-time metrics
        self.mock_telemetry.get_real_time_metrics.return_value = self.mock_realtime_metrics
        
        # Mock create_performance_report to return success
        self.mock_telemetry.create_performance_report.return_value = {
            "success": True,
            "report_path": "/tmp/mock_report"
        }
        
        # Mock visualize_metrics to return success
        self.mock_telemetry.visualize_metrics.return_value = {
            "success": True,
            "path": "/tmp/mock_visualization.png"
        }
        
        # Configure app state
        app.state.wal = self.mock_wal
        app.state.wal_telemetry = self.mock_telemetry
        app.state.telemetry_config = {
            "metrics_path": "/tmp/test_telemetry",
            "retention_days": 30,
            "sampling_interval": 60,
            "enable_detailed_timing": True,
            "operation_hooks": True
        }
        
        # Create test client
        self.client = TestClient(app)
    
    def test_get_telemetry_metrics(self):
        """Test getting telemetry metrics."""
        response = self.client.get("/api/v0/wal/telemetry/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_telemetry")
        self.assertIn("metrics", data)
        self.assertIn("operation_count", data["metrics"])
        
        # Verify telemetry.get_metrics was called
        self.mock_telemetry.get_metrics.assert_called_once()
        
        # Test with metric type filter
        self.mock_telemetry.get_metrics.reset_mock()
        response = self.client.get("/api/v0/wal/telemetry/metrics?metric_type=operation_latency")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["metric_type"], "operation_latency")
        
        # Verify telemetry.get_metrics was called with metric_type parameter
        call_args = self.mock_telemetry.get_metrics.call_args[1]
        self.assertIn("metric_type", call_args)
        
        # Test with other filters
        self.mock_telemetry.get_metrics.reset_mock()
        query_params = {
            "metric_type": "operation_count",
            "operation_type": "add",
            "backend": "ipfs",
            "status": "completed",
            "start_time": str(time.time() - 3600),
            "end_time": str(time.time()),
            "aggregation": "average"
        }
        response = self.client.get("/api/v0/wal/telemetry/metrics", params=query_params)
        self.assertEqual(response.status_code, 200)
        
        # Verify telemetry.get_metrics was called with all parameters
        call_args = self.mock_telemetry.get_metrics.call_args[1]
        self.assertIn("metric_type", call_args)
        self.assertIn("operation_type", call_args)
        self.assertIn("backend", call_args)
        self.assertIn("status", call_args)
        self.assertIn("time_range", call_args)
        self.assertIn("aggregation", call_args)
    
    def test_get_realtime_telemetry(self):
        """Test getting real-time telemetry data."""
        response = self.client.get("/api/v0/wal/telemetry/realtime")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_realtime_telemetry")
        
        # Verify the real-time metrics data
        self.assertIn("latency", data)
        self.assertIn("success_rate", data)
        self.assertIn("error_rate", data)
        self.assertIn("throughput", data)
        self.assertIn("status_distribution", data)
        
        # Verify telemetry.get_real_time_metrics was called
        self.mock_telemetry.get_real_time_metrics.assert_called_once()
    
    @patch('anyio.to_thread.run_sync')
    @patch('os.makedirs')
    def test_generate_telemetry_report(self, mock_makedirs, mock_run_sync):
        """Test generating a telemetry report."""
        # Setup anyio.to_thread.run_sync mock
        mock_run_sync.return_value = None
        
        # Create temporary directory for reports
        report_dir = tempfile.mkdtemp()
        
        # Make test report directory
        os.makedirs(os.path.join(report_dir, "report_test"), exist_ok=True)
        
        # Test endpoint
        response = self.client.post(
            "/api/v0/wal/telemetry/report",
            data={
                "start_time": str(time.time() - 3600),
                "end_time": str(time.time())
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "generate_telemetry_report")
        self.assertIn("report_path", data)
        self.assertIn("report_url", data)
        
        # Verify anyio.to_thread.run_sync was called
        mock_run_sync.assert_called_once()
    
    @patch('anyio.to_thread.run_sync')
    @patch('tempfile.mkstemp')
    @patch('os.close')
    def test_visualize_metrics(self, mock_close, mock_mkstemp, mock_run_sync):
        """Test generating a visualization of telemetry metrics."""
        # Setup tempfile.mkstemp mock
        mock_mkstemp.return_value = (1, "/tmp/mock_viz.png")
        
        # Setup anyio.to_thread.run_sync mock
        mock_run_sync.return_value = {"success": True, "path": "/tmp/mock_viz.png"}
        
        # Test endpoint
        response = self.client.get(
            "/api/v0/wal/telemetry/visualization/operation_count",
            params={
                "operation_type": "add",
                "width": "12",
                "height": "8"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        
        # Verify anyio.to_thread.run_sync was called
        mock_run_sync.assert_called_once()
        
        # Verify tempfile.mkstemp was called
        mock_mkstemp.assert_called_once()
        
        # Verify os.close was called
        mock_close.assert_called_once()
    
    def test_get_telemetry_config(self):
        """Test getting telemetry configuration."""
        response = self.client.get("/api/v0/wal/telemetry/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "get_telemetry_config")
        
        # Verify config values
        config = data["config"]
        self.assertEqual(config["metrics_path"], "/tmp/test_telemetry")
        self.assertEqual(config["retention_days"], 30)
        self.assertEqual(config["sampling_interval"], 60)
        self.assertTrue(config["enable_detailed_timing"])
        self.assertTrue(config["operation_hooks"])
    
    def test_update_telemetry_config(self):
        """Test updating telemetry configuration."""
        new_config = {
            "retention_days": 60,
            "sampling_interval": 30,
            "enable_detailed_timing": False
        }
        
        response = self.client.post("/api/v0/wal/telemetry/config", json=new_config)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["operation"], "update_telemetry_config")
        
        # Verify config was updated
        config = data["config"]
        self.assertEqual(config["retention_days"], 60)
        self.assertEqual(config["sampling_interval"], 30)
        self.assertFalse(config["enable_detailed_timing"])
        
        # Verify telemetry attributes were updated
        self.assertEqual(self.mock_telemetry.retention_days, 60)
        self.assertEqual(self.mock_telemetry.sampling_interval, 30)
        self.assertEqual(self.mock_telemetry.enable_detailed_timing, False)

if __name__ == "__main__":
    unittest.main()