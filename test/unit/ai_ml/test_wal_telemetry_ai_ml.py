#!/usr/bin/env python3
"""
Test suite for WAL Telemetry AI/ML integration.

This module tests the WAL Telemetry AI/ML extension which provides
specialized monitoring and tracing for AI/ML operations.
"""

import unittest
import time
import json
import anyio
from unittest.mock import patch, MagicMock, AsyncMock
import logging
import sys
import os

# Add parent directory to path for importing from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module to test
from ipfs_kit_py.wal_telemetry_ai_ml import (
    WALTelemetryAIMLExtension,
    extend_wal_telemetry,
    extend_high_level_api_with_aiml_telemetry
)


class TestWALTelemetryAIMLExtension(unittest.TestCase):
    """Test WAL Telemetry AI/ML extension."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock base extension
        self.base_extension = MagicMock()

        # Mock the create_span method to return a context manager
        self.mock_span = MagicMock()
        self.mock_span.__enter__ = MagicMock(return_value=self.mock_span)
        self.mock_span.__exit__ = MagicMock(return_value=None)
        self.base_extension.create_span = MagicMock(return_value=self.mock_span)

        # Mock telemetry attribute
        self.base_extension.telemetry = MagicMock()

        # Create extension
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.AIML_METRICS_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml.AIMLMetrics') as self.mock_metrics_class:
                self.mock_metrics = MagicMock()
                self.mock_metrics.track_model_load = MagicMock(return_value=MagicMock())
                self.mock_metrics.track_inference = MagicMock(return_value=MagicMock())
                self.mock_metrics.track_training_epoch = MagicMock(return_value=MagicMock())
                self.mock_metrics.get_comprehensive_report = MagicMock(return_value={
                    "models": {"stats": {}},
                    "inference": {"stats": {}},
                    "training": {"stats": {}}
                })
                self.mock_metrics_class.return_value = self.mock_metrics

                self.extension = WALTelemetryAIMLExtension(self.base_extension)

    def test_initialize(self):
        """Test initialization of AI/ML telemetry extension."""
        # Test initialization without prometheus exporter
        result = self.extension.initialize()

        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "AI/ML telemetry initialized successfully")

        # Test with prometheus exporter
        self.base_extension.prometheus_exporter = MagicMock()

        # Create a mock prometheus_client module with required components
        mock_prom = MagicMock()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()
        mock_histogram = MagicMock()
        mock_summary = MagicMock()

        # Patch the import inside the _register_prometheus_metrics method
        with patch.dict('sys.modules', {'prometheus_client': mock_prom}):
            # Also make Counter, Gauge, etc. available
            mock_prom.Counter = mock_counter
            mock_prom.Gauge = mock_gauge
            mock_prom.Histogram = mock_histogram
            mock_prom.Summary = mock_summary

            result = self.extension.initialize()

            self.assertTrue(result["success"])

            # Verify metrics registration
            self.assertTrue(self.extension.metrics_registered)
            self.assertGreater(len(self.extension.registry), 0)

    def test_track_model_operation(self):
        """Test tracking model operations."""
        # Test tracking model load operation
        with self.extension.track_model_operation(
            operation_type="model_load",
            model_id="test_model",
            framework="test_framework",
            model_size=1000000
        ) as tracking:
            # Check span is created
            self.base_extension.create_span.assert_called_once()

            # Verify span attributes
            span_args = self.base_extension.create_span.call_args[1]
            self.assertEqual(span_args["name"], "aiml.model_load")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")

            # Verify AIMLMetrics tracking
            self.mock_metrics.track_model_load.assert_called_once_with(
                model_id="test_model",
                framework="test_framework",
                model_size=1000000
            )

            # Verify tracking context
            self.assertEqual(tracking["operation_type"], "model_load")
            self.assertEqual(tracking["model_id"], "test_model")

        # Verify metrics increment (on success path)
        # For this we need to mock the metrics registry
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "ai_operations_total": MagicMock(),
                "model_load_time": MagicMock()
            }):
                # Test tracking model init operation
                with self.extension.track_model_operation(
                    operation_type="model_init",
                    model_id="test_model",
                    device="cpu"
                ):
                    pass

                # Verify metrics increment
                self.extension.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="model_init",
                    status="success"
                )

    def test_track_inference(self):
        """Test tracking inference operations."""
        # Test tracking inference operation
        with self.extension.track_inference(
            model_id="test_model",
            batch_size=16,
            track_memory=True
        ) as tracking:
            # Check span is created
            self.base_extension.create_span.assert_called_once()

            # Verify span attributes
            span_args = self.base_extension.create_span.call_args[1]
            self.assertEqual(span_args["name"], "aiml.inference")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")
            self.assertEqual(span_args["attributes"]["batch.size"], 16)

            # Verify AIMLMetrics tracking
            self.mock_metrics.track_inference.assert_called_once_with(
                model_id="test_model",
                batch_size=16,
                track_memory=True
            )

            # Verify tracking context
            self.assertEqual(tracking["model_id"], "test_model")
            self.assertEqual(tracking["batch_size"], 16)

        # Verify metrics increment (on success path)
        # For this we need to mock the metrics registry
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "ai_operations_total": MagicMock(),
                "inference_latency": MagicMock(),
                "inference_throughput": MagicMock()
            }):
                # Test tracking inference operation
                with self.extension.track_inference(
                    model_id="test_model",
                    batch_size=16
                ):
                    pass

                # Verify metrics increment
                self.extension.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="inference",
                    status="success"
                )
                self.extension.registry["inference_latency"].labels.assert_called_once_with(
                    model_id="test_model",
                    batch_size="16"
                )

    def test_track_training_epoch(self):
        """Test tracking training epochs."""
        # Test tracking training epoch operation
        with self.extension.track_training_epoch(
            model_id="test_model",
            epoch=1,
            num_samples=1000
        ) as tracking:
            # Check span is created
            self.base_extension.create_span.assert_called_once()

            # Verify span attributes
            span_args = self.base_extension.create_span.call_args[1]
            self.assertEqual(span_args["name"], "aiml.training_epoch")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")
            self.assertEqual(span_args["attributes"]["epoch"], 1)
            self.assertEqual(span_args["attributes"]["num_samples"], 1000)

            # Verify AIMLMetrics tracking
            self.mock_metrics.track_training_epoch.assert_called_once_with(
                model_id="test_model",
                epoch=1,
                num_samples=1000
            )

            # Verify tracking context
            self.assertEqual(tracking["model_id"], "test_model")
            self.assertEqual(tracking["epoch"], 1)
            self.assertEqual(tracking["num_samples"], 1000)

        # Verify metrics increment (on success path)
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "ai_operations_total": MagicMock(),
                "training_epoch_time": MagicMock(),
                "training_samples_per_second": MagicMock()
            }):
                # Test tracking training epoch operation
                with self.extension.track_training_epoch(
                    model_id="test_model",
                    epoch=1,
                    num_samples=1000
                ):
                    pass

                # Verify metrics increment
                self.extension.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="training_epoch",
                    status="success"
                )
                self.extension.registry["training_epoch_time"].labels.assert_called_once_with(
                    model_id="test_model"
                )

    def test_track_dataset_operation(self):
        """Test tracking dataset operations."""
        # Test tracking dataset load operation
        with self.extension.track_dataset_operation(
            operation_type="dataset_load",
            dataset_id="test_dataset",
            format="csv",
            dataset_size=10000000
        ) as tracking:
            # Check span is created
            self.base_extension.create_span.assert_called_once()

            # Verify span attributes
            span_args = self.base_extension.create_span.call_args[1]
            self.assertEqual(span_args["name"], "aiml.dataset_load")
            self.assertEqual(span_args["attributes"]["dataset.id"], "test_dataset")
            self.assertEqual(span_args["attributes"]["format"], "csv")

            # Verify tracking context
            self.assertEqual(tracking["operation_type"], "dataset_load")
            self.assertEqual(tracking["dataset_id"], "test_dataset")

        # Verify metrics increment (on success path)
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "ai_operations_total": MagicMock(),
                "dataset_load_time": MagicMock(),
                "dataset_size": MagicMock()
            }):
                # Test tracking dataset load operation
                with self.extension.track_dataset_operation(
                    operation_type="dataset_load",
                    dataset_id="test_dataset",
                    format="csv",
                    dataset_size=10000000
                ):
                    pass

                # Verify metrics increment
                self.extension.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="dataset_load",
                    status="success"
                )
                self.extension.registry["dataset_load_time"].labels.assert_called_once_with(
                    dataset_id="test_dataset",
                    format="csv"
                )
                self.extension.registry["dataset_size"].labels.assert_called_once_with(
                    dataset_id="test_dataset"
                )

    def test_track_distributed_operation(self):
        """Test tracking distributed operations."""
        # Test tracking worker coordination operation
        with self.extension.track_distributed_operation(
            operation_type="worker_coordination",
            task_id="test_task",
            num_workers=4
        ) as tracking:
            # Check span is created
            self.base_extension.create_span.assert_called_once()

            # Verify span attributes
            span_args = self.base_extension.create_span.call_args[1]
            self.assertEqual(span_args["name"], "aiml.worker_coordination")
            self.assertEqual(span_args["attributes"]["task.id"], "test_task")
            self.assertEqual(span_args["attributes"]["num_workers"], 4)

            # Verify tracking context
            self.assertEqual(tracking["operation_type"], "worker_coordination")
            self.assertEqual(tracking["task_id"], "test_task")
            self.assertEqual(tracking["num_workers"], 4)

        # Verify metrics increment (on success path)
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "ai_operations_total": MagicMock(),
                "coordination_overhead": MagicMock()
            }):
                # Test tracking distributed operation
                with self.extension.track_distributed_operation(
                    operation_type="worker_coordination",
                    task_id="test_task",
                    num_workers=4
                ):
                    pass

                # Verify metrics increment
                self.extension.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="worker_coordination",
                    status="success"
                )
                self.extension.registry["coordination_overhead"].labels.assert_called_once_with(
                    operation="worker_coordination"
                )

    def test_record_training_stats(self):
        """Test recording training statistics."""
        # Test recording training stats
        result = self.extension.record_training_stats(
            model_id="test_model",
            epoch=1,
            loss=0.1,
            learning_rate=0.01,
            gradient_norm=0.5
        )

        # Verify result
        self.assertTrue(result["success"])

        # Verify AIMLMetrics call
        self.mock_metrics.record_training_stats.assert_called_once_with(
            model_id="test_model",
            epoch=1,
            loss=0.1,
            learning_rate=0.01,
            gradient_norm=0.5
        )

        # Verify span creation
        self.base_extension.create_span.assert_called_once()

        # Verify Prometheus metrics update (if registered)
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "training_loss": MagicMock()
            }):
                # Test recording training stats
                self.extension.record_training_stats(
                    model_id="test_model",
                    epoch=1,
                    loss=0.1
                )

                # Verify metrics update
                self.extension.registry["training_loss"].labels.assert_called_once_with(
                    model_id="test_model",
                    epoch="1"
                )

    def test_record_worker_utilization(self):
        """Test recording worker utilization."""
        # Test recording worker utilization
        result = self.extension.record_worker_utilization(
            worker_id="worker1",
            utilization=0.75
        )

        # Verify result
        self.assertTrue(result["success"])

        # Verify AIMLMetrics call
        self.mock_metrics.record_worker_utilization.assert_called_once_with(
            worker_id="worker1",
            utilization=0.75
        )

        # Verify span creation
        self.base_extension.create_span.assert_called_once()

        # Verify Prometheus metrics update (if registered)
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "worker_utilization": MagicMock()
            }):
                # Test recording worker utilization
                self.extension.record_worker_utilization(
                    worker_id="worker1",
                    utilization=0.75
                )

                # Verify metrics update
                self.extension.registry["worker_utilization"].labels.assert_called_once_with(
                    worker_id="worker1"
                )

    def test_get_ai_ml_metrics(self):
        """Test getting AI/ML metrics."""
        # Test getting metrics
        result = self.extension.get_ai_ml_metrics()

        # Verify result
        self.assertTrue(result["success"])
        self.assertIn("metrics", result)

        # Verify AIMLMetrics call
        self.mock_metrics.get_comprehensive_report.assert_called_once()

    def test_generate_metrics_report(self):
        """Test generating metrics report."""
        # Mock the generate_formatted_report method
        self.mock_metrics.generate_formatted_report = MagicMock(return_value="# Metrics Report")

        # Test generating report
        result = self.extension.generate_metrics_report(format="markdown")

        # Verify result
        self.assertTrue(result["success"])
        self.assertIn("report", result)
        self.assertEqual(result["report"], "# Metrics Report")

        # Verify AIMLMetrics call
        self.mock_metrics.generate_formatted_report.assert_called_once_with(format="markdown")

    def test_update_prometheus_metrics(self):
        """Test updating Prometheus metrics."""
        # Create test metrics data
        metrics_data = {
            "models": {
                "models": {
                    "model1": {
                        "size_bytes": 1000000,
                        "framework": "test_framework",
                        "load_time_stats": {
                            "count": 10,
                            "mean": 0.1,
                            "min": 0.05,
                            "max": 0.2
                        }
                    }
                }
            },
            "inference": {
                "models": {
                    "model1": {
                        "throughput_stats": {
                            "mean": 100,
                            "min": 50,
                            "max": 150
                        }
                    }
                }
            },
            "training": {
                "models": {
                    "model1": {
                        "samples_per_second_stats": {
                            "mean": 1000,
                            "min": 500,
                            "max": 1500
                        },
                        "loss_progress": {
                            "initial": 1.0,
                            "final": 0.1
                        },
                        "num_epochs": 10
                    }
                }
            },
            "distributed": {
                "average_worker_utilization": {
                    "worker1": 0.8,
                    "worker2": 0.9
                }
            }
        }

        # Mock registry
        with patch.object(self.extension, 'metrics_registered', True):
            with patch.object(self.extension, 'registry', {
                "model_size": MagicMock(),
                "inference_throughput": MagicMock(),
                "training_samples_per_second": MagicMock(),
                "training_loss": MagicMock(),
                "worker_utilization": MagicMock()
            }):
                # Test updating metrics
                result = self.extension.update_prometheus_metrics(metrics_data)

                # Verify result
                self.assertTrue(result["success"])
                self.assertGreater(result["metrics_updated"], 0)

                # Verify model size metric update
                self.extension.registry["model_size"].labels.assert_called_once_with(
                    model_id="model1",
                    framework="test_framework"
                )

                # Verify inference throughput metric update
                self.extension.registry["inference_throughput"].labels.assert_called_once_with(
                    model_id="model1"
                )

                # Verify training samples per second metric update
                self.extension.registry["training_samples_per_second"].labels.assert_called_once_with(
                    model_id="model1"
                )

                # Verify training loss metric update
                self.extension.registry["training_loss"].labels.assert_called_once_with(
                    model_id="model1",
                    epoch="10"
                )

                # Verify worker utilization metric update (should be called twice)
                self.assertEqual(self.extension.registry["worker_utilization"].labels.call_count, 2)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions in WAL Telemetry AI/ML module."""

    def test_extend_wal_telemetry(self):
        """Test extending WAL telemetry with AI/ML capabilities."""
        # Test with WAL_TELEMETRY_AVAILABLE=True
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml.WALTelemetryAIMLExtension') as mock_extension_class:
                mock_extension = MagicMock()
                mock_extension_class.return_value = mock_extension

                # Test extending telemetry
                base_extension = MagicMock()
                result = extend_wal_telemetry(base_extension)

                # Verify extension creation
                mock_extension_class.assert_called_once_with(base_extension)
                self.assertEqual(result, mock_extension)

        # Test with WAL_TELEMETRY_AVAILABLE=False
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', False):
            base_extension = MagicMock()
            result = extend_wal_telemetry(base_extension)

            # Should return None
            self.assertIsNone(result)

    def test_extend_high_level_api_with_aiml_telemetry(self):
        """Test extending high-level API with AI/ML telemetry."""
        # Test with WAL_TELEMETRY_AVAILABLE=True and initialized extension
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml.extend_wal_telemetry') as mock_extend:
                mock_extension = MagicMock()
                mock_extend.return_value = mock_extension

                # Create mock API with telemetry extension
                api = MagicMock()
                api._wal_telemetry_extension = MagicMock()

                # Test extending API
                result = extend_high_level_api_with_aiml_telemetry(api)

                # Verify extension creation
                mock_extend.assert_called_once_with(api._wal_telemetry_extension)

                # Check that AI/ML methods were added to API
                self.assertEqual(api.wal_aiml_telemetry, mock_extension.initialize)
                self.assertEqual(api.wal_track_model_operation, mock_extension.track_model_operation)
                self.assertEqual(api.wal_track_inference, mock_extension.track_inference)
                self.assertEqual(api.wal_track_training_epoch, mock_extension.track_training_epoch)
                self.assertEqual(api.wal_record_training_stats, mock_extension.record_training_stats)
                self.assertEqual(api.wal_track_dataset_operation, mock_extension.track_dataset_operation)
                self.assertEqual(api.wal_track_distributed_operation, mock_extension.track_distributed_operation)
                self.assertEqual(api.wal_record_worker_utilization, mock_extension.record_worker_utilization)
                self.assertEqual(api.wal_get_ai_ml_metrics, mock_extension.get_ai_ml_metrics)
                self.assertEqual(api.wal_generate_metrics_report, mock_extension.generate_metrics_report)

                # Verify extension reference was stored
                self.assertEqual(api._wal_aiml_telemetry_extension, mock_extension)

                # Verify API was returned
                self.assertEqual(result, api)

        # Test with WAL_TELEMETRY_AVAILABLE=False
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', False):
            api = MagicMock()
            result = extend_high_level_api_with_aiml_telemetry(api)

            # Should return API unchanged
            self.assertEqual(result, api)

        # Test with no existing telemetry extension
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', True):
            api = MagicMock()
            api._wal_telemetry_extension = None
            result = extend_high_level_api_with_aiml_telemetry(api)

            # Should return API unchanged
            self.assertEqual(result, api)

        # Test with telemetry available but extension creation fails
        with patch('ipfs_kit_py.wal_telemetry_ai_ml.WAL_TELEMETRY_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml.extend_wal_telemetry') as mock_extend:
                mock_extend.return_value = None

                # Create mock API with telemetry extension
                api = MagicMock()
                api._wal_telemetry_extension = MagicMock()

                # Test extending API
                result = extend_high_level_api_with_aiml_telemetry(api)

                # Verify extension creation was attempted
                mock_extend.assert_called_once_with(api._wal_telemetry_extension)

                # Should return API unchanged
                self.assertEqual(result, api)


if __name__ == "__main__":
    unittest.main()
