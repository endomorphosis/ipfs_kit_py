#!/usr/bin/env python3
"""
Test suite for WAL Telemetry AI/ML integration with AnyIO support.

This module tests the WAL Telemetry AI/ML extension which provides
specialized monitoring and tracing for AI/ML operations, using AnyIO
for backend-agnostic async operations.
"""

import unittest
import time
import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import logging
import sys
import os

# Import AnyIO
import anyio
from anyio.abc import TaskGroup

# Add parent directory to path for importing from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module to test
from ipfs_kit_py.wal_telemetry_ai_ml import (
    WALTelemetryAIMLExtension,
    extend_wal_telemetry,
    extend_high_level_api_with_aiml_telemetry
)

# Check if AnyIO version exists
try:
    from ipfs_kit_py.wal_telemetry_ai_ml_anyio import (
        WALTelemetryAIMLExtensionAnyIO,
        extend_wal_telemetry_async,
        extend_high_level_api_with_aiml_telemetry_async
    )
    HAS_WAL_TELEMETRY_AIML_ANYIO = True
except ImportError:
    HAS_WAL_TELEMETRY_AIML_ANYIO = False


class TestWALTelemetryAIMLExtensionAnyIO(unittest.TestCase):
    """Test WAL Telemetry AI/ML extension with AnyIO support."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock base extension
        self.base_extension = MagicMock()
        
        # Mock the create_span method to return a context manager
        self.mock_span = MagicMock()
        self.mock_span.__enter__ = MagicMock(return_value=self.mock_span)
        self.mock_span.__exit__ = MagicMock(return_value=None)
        self.base_extension.create_span = MagicMock(return_value=self.mock_span)
        
        # For async testing
        self.mock_span_async = MagicMock()
        self.mock_span_async.__aenter__ = AsyncMock(return_value=self.mock_span_async)
        self.mock_span_async.__aexit__ = AsyncMock(return_value=None)
        self.base_extension.create_span_async = AsyncMock(return_value=self.mock_span_async)
        
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
                
                # Create AnyIO extension if available
                if HAS_WAL_TELEMETRY_AIML_ANYIO:
                    self.extension_anyio = WALTelemetryAIMLExtensionAnyIO(self.base_extension)
    
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
    
    @pytest.mark.asyncio
    async def test_track_model_operation_async(self):
        """Test tracking model operations asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test tracking model load operation asynchronously
        async with self.extension_anyio.track_model_operation_async(
            operation_type="model_load",
            model_id="test_model",
            framework="test_framework",
            model_size=1000000
        ) as tracking:
            # Check span is created
            self.base_extension.create_span_async.assert_called_once()
            
            # Verify span attributes
            span_args = self.base_extension.create_span_async.call_args[1]
            self.assertEqual(span_args["name"], "aiml.model_load")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")
            
            # Verify tracking context
            self.assertEqual(tracking["operation_type"], "model_load")
            self.assertEqual(tracking["model_id"], "test_model")
        
        # Verify metrics increment (on success path)
        # For this we need to mock the metrics registry
        with patch.object(self.extension_anyio, 'metrics_registered', True):
            with patch.object(self.extension_anyio, 'registry', {
                "ai_operations_total": MagicMock(),
                "model_load_time": MagicMock()
            }):
                # Test tracking model init operation
                async with self.extension_anyio.track_model_operation_async(
                    operation_type="model_init",
                    model_id="test_model",
                    device="cpu"
                ):
                    pass
                
                # Verify metrics increment
                self.extension_anyio.registry["ai_operations_total"].labels.assert_called_once_with(
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
    
    @pytest.mark.asyncio
    async def test_track_inference_async(self):
        """Test tracking inference operations asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test tracking inference operation asynchronously
        async with self.extension_anyio.track_inference_async(
            model_id="test_model",
            batch_size=16,
            track_memory=True
        ) as tracking:
            # Check span is created
            self.base_extension.create_span_async.assert_called_once()
            
            # Verify span attributes
            span_args = self.base_extension.create_span_async.call_args[1]
            self.assertEqual(span_args["name"], "aiml.inference")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")
            self.assertEqual(span_args["attributes"]["batch.size"], 16)
            
            # Verify tracking context
            self.assertEqual(tracking["model_id"], "test_model")
            self.assertEqual(tracking["batch_size"], 16)
        
        # Verify metrics increment (on success path)
        # For this we need to mock the metrics registry
        with patch.object(self.extension_anyio, 'metrics_registered', True):
            with patch.object(self.extension_anyio, 'registry', {
                "ai_operations_total": MagicMock(),
                "inference_latency": MagicMock(),
                "inference_throughput": MagicMock()
            }):
                # Test tracking inference operation
                async with self.extension_anyio.track_inference_async(
                    model_id="test_model",
                    batch_size=16
                ):
                    pass
                
                # Verify metrics increment
                self.extension_anyio.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="inference",
                    status="success"
                )
                self.extension_anyio.registry["inference_latency"].labels.assert_called_once_with(
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
    
    @pytest.mark.asyncio
    async def test_track_training_epoch_async(self):
        """Test tracking training epochs asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test tracking training epoch operation asynchronously
        async with self.extension_anyio.track_training_epoch_async(
            model_id="test_model",
            epoch=1,
            num_samples=1000
        ) as tracking:
            # Check span is created
            self.base_extension.create_span_async.assert_called_once()
            
            # Verify span attributes
            span_args = self.base_extension.create_span_async.call_args[1]
            self.assertEqual(span_args["name"], "aiml.training_epoch")
            self.assertEqual(span_args["attributes"]["model.id"], "test_model")
            self.assertEqual(span_args["attributes"]["epoch"], 1)
            self.assertEqual(span_args["attributes"]["num_samples"], 1000)
            
            # Verify tracking context
            self.assertEqual(tracking["model_id"], "test_model")
            self.assertEqual(tracking["epoch"], 1)
            self.assertEqual(tracking["num_samples"], 1000)
        
        # Verify metrics increment (on success path)
        with patch.object(self.extension_anyio, 'metrics_registered', True):
            with patch.object(self.extension_anyio, 'registry', {
                "ai_operations_total": MagicMock(),
                "training_epoch_time": MagicMock(),
                "training_samples_per_second": MagicMock()
            }):
                # Test tracking training epoch operation
                async with self.extension_anyio.track_training_epoch_async(
                    model_id="test_model",
                    epoch=1,
                    num_samples=1000
                ):
                    pass
                
                # Verify metrics increment
                self.extension_anyio.registry["ai_operations_total"].labels.assert_called_once_with(
                    operation_type="training_epoch",
                    status="success"
                )
                self.extension_anyio.registry["training_epoch_time"].labels.assert_called_once_with(
                    model_id="test_model"
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
    
    @pytest.mark.asyncio
    async def test_get_ai_ml_metrics_async(self):
        """Test getting AI/ML metrics asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test getting metrics asynchronously
        result = await self.extension_anyio.get_ai_ml_metrics_async()
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertIn("metrics", result)
        
        # Verify AIMLMetrics call
        self.mock_metrics.get_comprehensive_report.assert_called()
    
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
    
    @pytest.mark.asyncio
    async def test_generate_metrics_report_async(self):
        """Test generating metrics report asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Mock the generate_formatted_report method
        self.mock_metrics.generate_formatted_report = MagicMock(return_value="# Metrics Report")
        
        # Test generating report asynchronously
        result = await self.extension_anyio.generate_metrics_report_async(format="markdown")
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertIn("report", result)
        self.assertEqual(result["report"], "# Metrics Report")
        
        # Verify AIMLMetrics call
        self.mock_metrics.generate_formatted_report.assert_called_with(format="markdown")


class TestHelperFunctionsAnyIO(unittest.TestCase):
    """Test helper functions in WAL Telemetry AI/ML module with AnyIO support."""
    
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
    
    @pytest.mark.asyncio
    async def test_extend_wal_telemetry_async(self):
        """Test extending WAL telemetry with AI/ML capabilities asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test with WAL_TELEMETRY_AVAILABLE=True
        with patch('ipfs_kit_py.wal_telemetry_ai_ml_anyio.WAL_TELEMETRY_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml_anyio.WALTelemetryAIMLExtensionAnyIO') as mock_extension_class:
                mock_extension = MagicMock()
                mock_extension_class.return_value = mock_extension
                
                # Test extending telemetry asynchronously
                base_extension = MagicMock()
                result = await extend_wal_telemetry_async(base_extension)
                
                # Verify extension creation
                mock_extension_class.assert_called_once_with(base_extension)
                self.assertEqual(result, mock_extension)
        
        # Test with WAL_TELEMETRY_AVAILABLE=False
        with patch('ipfs_kit_py.wal_telemetry_ai_ml_anyio.WAL_TELEMETRY_AVAILABLE', False):
            base_extension = MagicMock()
            result = await extend_wal_telemetry_async(base_extension)
            
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
    
    @pytest.mark.asyncio
    async def test_extend_high_level_api_with_aiml_telemetry_async(self):
        """Test extending high-level API with AI/ML telemetry asynchronously."""
        # Skip if WALTelemetryAIMLExtensionAnyIO is not available
        if not HAS_WAL_TELEMETRY_AIML_ANYIO:
            return
            
        # Test with WAL_TELEMETRY_AVAILABLE=True and initialized extension
        with patch('ipfs_kit_py.wal_telemetry_ai_ml_anyio.WAL_TELEMETRY_AVAILABLE', True):
            with patch('ipfs_kit_py.wal_telemetry_ai_ml_anyio.extend_wal_telemetry_async') as mock_extend:
                mock_extension = MagicMock()
                mock_extend.return_value = mock_extension
                
                # Create mock API with telemetry extension
                api = MagicMock()
                api._wal_telemetry_extension = MagicMock()
                
                # Test extending API asynchronously
                result = await extend_high_level_api_with_aiml_telemetry_async(api)
                
                # Verify extension creation
                mock_extend.assert_called_once_with(api._wal_telemetry_extension)
                
                # Check that async AI/ML methods were added to API
                self.assertEqual(api.wal_aiml_telemetry_async, mock_extension.initialize_async)
                self.assertEqual(api.wal_track_model_operation_async, mock_extension.track_model_operation_async)
                self.assertEqual(api.wal_track_inference_async, mock_extension.track_inference_async)
                self.assertEqual(api.wal_track_training_epoch_async, mock_extension.track_training_epoch_async)
                self.assertEqual(api.wal_record_training_stats_async, mock_extension.record_training_stats_async)
                self.assertEqual(api.wal_track_dataset_operation_async, mock_extension.track_dataset_operation_async)
                self.assertEqual(api.wal_record_worker_utilization_async, mock_extension.record_worker_utilization_async)
                self.assertEqual(api.wal_get_ai_ml_metrics_async, mock_extension.get_ai_ml_metrics_async)
                self.assertEqual(api.wal_generate_metrics_report_async, mock_extension.generate_metrics_report_async)
                
                # Verify extension reference was stored
                self.assertEqual(api._wal_aiml_telemetry_extension_anyio, mock_extension)
                
                # Verify API was returned
                self.assertEqual(result, api)


# Allow running with both unittest and pytest
if __name__ == "__main__":
    unittest.main()