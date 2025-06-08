#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/tests/test_metrics.py

"""
Unit tests for the metrics collectors.

This module tests the various metrics collectors used to gather
information for routing decisions.
"""

import unittest
from unittest.mock import MagicMock, patch
import time

from ipfs_kit_py.mcp.routing.router import (
    Backend, ContentType, OperationType, RouteMetrics
)
from ipfs_kit_py.mcp.routing.metrics.bandwidth import BandwidthMonitor, BandwidthSample
from ipfs_kit_py.mcp.routing.metrics.latency import LatencyTracker, LatencySample
from ipfs_kit_py.mcp.routing.metrics.cost import CostCalculator
from ipfs_kit_py.mcp.routing.metrics.geographic import GeographicOptimizer
from ipfs_kit_py.mcp.routing.metrics.content import ContentTypeAnalyzer
from ipfs_kit_py.mcp.routing.metrics.performance import PerformanceMetrics


class TestBandwidthMonitor(unittest.TestCase):
    """Test cases for the BandwidthMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = BandwidthMonitor(history_size=5)
    
    def test_record_sample(self):
        """Test recording bandwidth samples."""
        # Record a sample
        self.monitor.record_sample(
            backend="IPFS",
            bytes_sent=1024 * 1024,  # 1 MB
            bytes_received=2 * 1024 * 1024,  # 2 MB
            duration_seconds=1.0,
            operation_type="read"
        )
        
        # Check that the sample was recorded
        self.assertIn("IPFS", self.monitor.samples)
        self.assertEqual(len(self.monitor.samples["IPFS"]), 1)
        
        # Check that summary stats were updated
        self.assertIn("IPFS", self.monitor.summary_stats)
        self.assertIn("avg_throughput_mbps", self.monitor.summary_stats["IPFS"])
        
        # Check that the throughput was calculated correctly
        # (1 + 2) MB = 3 MB = 24 Mb, over 1 second = 24 Mbps
        self.assertAlmostEqual(
            self.monitor.summary_stats["IPFS"]["avg_throughput_mbps"],
            24.0,
            delta=0.1
        )
    
    def test_record_multiple_samples(self):
        """Test recording multiple bandwidth samples."""
        # Record multiple samples
        for i in range(3):
            self.monitor.record_sample(
                backend="IPFS",
                bytes_sent=1024 * 1024,  # 1 MB
                bytes_received=1024 * 1024,  # 1 MB
                duration_seconds=1.0,
                operation_type="read"
            )
        
        # Check that all samples were recorded
        self.assertEqual(len(self.monitor.samples["IPFS"]), 3)
        
        # Record more samples than history size
        for i in range(5):
            self.monitor.record_sample(
                backend="S3",
                bytes_sent=1024 * 1024,  # 1 MB
                bytes_received=1024 * 1024,  # 1 MB
                duration_seconds=1.0,
                operation_type="read"
            )
        
        # Check that only history_size samples were kept
        self.assertEqual(len(self.monitor.samples["S3"]), 5)
        
        # Record one more to trigger rotation
        self.monitor.record_sample(
            backend="S3",
            bytes_sent=2 * 1024 * 1024,  # 2 MB
            bytes_received=2 * 1024 * 1024,  # 2 MB
            duration_seconds=1.0,
            operation_type="read"
        )
        
        # Check that oldest sample was dropped but count stayed at history_size
        self.assertEqual(len(self.monitor.samples["S3"]), 5)
    
    def test_get_throughput(self):
        """Test getting throughput for a backend."""
        # Record a sample
        self.monitor.record_sample(
            backend="IPFS",
            bytes_sent=1024 * 1024,  # 1 MB
            bytes_received=1024 * 1024,  # 1 MB
            duration_seconds=0.5,
            operation_type="read"
        )
        
        # Get throughput
        throughput = self.monitor.get_throughput("IPFS")
        
        # Check that throughput is correct
        # (1 + 1) MB = 2 MB = 16 Mb, over 0.5 seconds = 32 Mbps
        self.assertAlmostEqual(throughput, 32.0, delta=0.1)
        
        # Get throughput for non-existent backend
        throughput = self.monitor.get_throughput("NON_EXISTENT")
        self.assertIsNone(throughput)
    
    def test_collect_metrics(self):
        """Test collecting metrics for routing."""
        # Record a sample
        self.monitor.record_sample(
            backend="IPFS",
            bytes_sent=1024 * 1024,  # 1 MB
            bytes_received=3 * 1024 * 1024,  # 3 MB
            duration_seconds=1.0,
            operation_type="read"
        )
        
        # Collect metrics
        metrics = self.monitor.collect_metrics("IPFS")
        
        # Check that metrics include throughput
        self.assertIn("throughput_mbps", metrics)
        
        # Check that throughput is correct
        # (1 + 3) MB = 4 MB = 32 Mb, over 1 second = 32 Mbps
        self.assertAlmostEqual(metrics["throughput_mbps"], 32.0, delta=0.1)
    
    def test_clear_history(self):
        """Test clearing bandwidth history."""
        # Record samples for multiple backends
        self.monitor.record_sample(
            backend="IPFS",
            bytes_sent=1024 * 1024,
            bytes_received=1024 * 1024,
            duration_seconds=1.0,
            operation_type="read"
        )
        
        self.monitor.record_sample(
            backend="S3",
            bytes_sent=1024 * 1024,
            bytes_received=1024 * 1024,
            duration_seconds=1.0,
            operation_type="read"
        )
        
        # Clear history for one backend
        self.monitor.clear_history("IPFS")
        
        # Check that only the specified backend was cleared
        self.assertNotIn("IPFS", self.monitor.samples)
        self.assertIn("S3", self.monitor.samples)
        
        # Clear all history
        self.monitor.clear_history()
        
        # Check that all history was cleared
        self.assertEqual(len(self.monitor.samples), 0)
        self.assertEqual(len(self.monitor.summary_stats), 0)


class TestLatencyTracker(unittest.TestCase):
    """Test cases for the LatencyTracker class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tracker = LatencyTracker(history_size=5)
    
    def test_record_sample(self):
        """Test recording latency samples."""
        # Record a sample
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        # Check that the sample was recorded
        self.assertIn("IPFS", self.tracker.samples)
        self.assertEqual(len(self.tracker.samples["IPFS"]), 1)
        
        # Check that summary stats were updated
        self.assertIn("IPFS", self.tracker.summary_stats)
        self.assertIn("avg_latency_ms", self.tracker.summary_stats["IPFS"])
        
        # Check that the latency was recorded correctly
        self.assertEqual(self.tracker.summary_stats["IPFS"]["avg_latency_ms"], 50.0)
    
    def test_start_timer_and_record_latency(self):
        """Test using start_timer and record_latency methods."""
        # Start a timer
        start_time = self.tracker.start_timer()
        
        # Wait a bit
        time.sleep(0.01)
        
        # Record latency
        latency_ms = self.tracker.record_latency(
            backend="IPFS",
            start_time=start_time,
            operation_type="read",
            success=True
        )
        
        # Check that latency was recorded and returned
        self.assertGreater(latency_ms, 0)
        self.assertIn("IPFS", self.tracker.samples)
        self.assertEqual(len(self.tracker.samples["IPFS"]), 1)
    
    def test_record_failed_operation(self):
        """Test recording a failed operation."""
        # Record a successful sample
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        # Record a failed sample
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=100.0,
            operation_type="read",
            success=False,
            error="Connection timeout"
        )
        
        # Check that both samples were recorded
        self.assertEqual(len(self.tracker.samples["IPFS"]), 2)
        
        # Check that success rate was updated correctly
        self.assertEqual(self.tracker.summary_stats["IPFS"]["success_rate"], 0.5)
        
        # Check that avg_latency only includes successful samples
        self.assertEqual(self.tracker.summary_stats["IPFS"]["avg_latency_ms"], 50.0)
    
    def test_get_latency(self):
        """Test getting latency for a backend."""
        # Record samples
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=70.0,
            operation_type="read",
            success=True
        )
        
        # Get latency
        latency = self.tracker.get_latency("IPFS")
        
        # Check that it returns the recent average latency
        self.assertEqual(latency, 60.0)
        
        # Get latency for non-existent backend
        latency = self.tracker.get_latency("NON_EXISTENT")
        self.assertIsNone(latency)
    
    def test_get_success_rate(self):
        """Test getting success rate for a backend."""
        # Record samples with mixed success
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=70.0,
            operation_type="read",
            success=False,
            error="Error"
        )
        
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=60.0,
            operation_type="read",
            success=True
        )
        
        # Get success rate
        success_rate = self.tracker.get_success_rate("IPFS")
        
        # Check that success rate is correct (2/3)
        self.assertAlmostEqual(success_rate, 2/3, places=2)
    
    def test_collect_metrics(self):
        """Test collecting metrics for routing."""
        # Record samples
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=70.0,
            operation_type="read",
            success=True
        )
        
        # Collect metrics
        metrics = self.tracker.collect_metrics("IPFS")
        
        # Check that metrics include latency and success rate
        self.assertIn("latency_ms", metrics)
        self.assertIn("success_rate", metrics)
        
        # Check values
        self.assertEqual(metrics["success_rate"], 1.0)
        # p90 should be around 70ms with two samples
        self.assertAlmostEqual(metrics["latency_ms"], 70.0, delta=5.0)
    
    def test_clear_history(self):
        """Test clearing latency history."""
        # Record samples for multiple backends
        self.tracker.record_sample(
            backend="IPFS",
            latency_ms=50.0,
            operation_type="read",
            success=True
        )
        
        self.tracker.record_sample(
            backend="S3",
            latency_ms=70.0,
            operation_type="read",
            success=True
        )
        
        # Clear history for one backend
        self.tracker.clear_history("IPFS")
        
        # Check that only the specified backend was cleared
        self.assertNotIn("IPFS", self.tracker.samples)
        self.assertIn("S3", self.tracker.samples)
        
        # Clear all history
        self.tracker.clear_history()
        
        # Check that all history was cleared
        self.assertEqual(len(self.tracker.samples), 0)
        self.assertEqual(len(self.tracker.summary_stats), 0)


class TestCostCalculator(unittest.TestCase):
    """Test cases for the CostCalculator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use custom backend costs for testing
        backend_costs = {
            "IPFS": {
                "storage_cost": 0.02,
                "retrieval_cost": 0.01,
                "operation_cost": 0.0001
            },
            "S3": {
                "storage_cost": 0.023,
                "retrieval_cost": 0.09,
                "operation_cost": 0.0005
            }
        }
        self.calculator = CostCalculator(backend_costs=backend_costs)
    
    def test_estimate_storage_cost(self):
        """Test estimating storage costs."""
        # Estimate cost for 1 GB for 1 month
        cost = self.calculator.estimate_storage_cost(
            backend="IPFS",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            months=1.0
        )
        
        # Check that cost is correct
        # 1 GB * $0.02/GB/month * 1 month = $0.02
        self.assertEqual(cost, 0.02)
        
        # Estimate cost for 10 GB for 6 months
        cost = self.calculator.estimate_storage_cost(
            backend="IPFS",
            size_bytes=10 * 1024 * 1024 * 1024,  # 10 GB
            months=6.0
        )
        
        # Check that cost is correct
        # 10 GB * $0.02/GB/month * 6 months = $1.20
        self.assertEqual(cost, 1.20)
    
    def test_estimate_retrieval_cost(self):
        """Test estimating retrieval costs."""
        # Estimate cost for retrieving 1 GB
        cost = self.calculator.estimate_retrieval_cost(
            backend="IPFS",
            size_bytes=1024 * 1024 * 1024  # 1 GB
        )
        
        # Check that cost is correct
        # 1 GB * $0.01/GB = $0.01
        self.assertEqual(cost, 0.01)
        
        # Estimate cost for retrieving 5 GB
        cost = self.calculator.estimate_retrieval_cost(
            backend="S3",
            size_bytes=5 * 1024 * 1024 * 1024  # 5 GB
        )
        
        # Check that cost is correct
        # 5 GB * $0.09/GB = $0.45
        self.assertEqual(cost, 0.45)
    
    def test_estimate_operation_cost(self):
        """Test estimating operation costs."""
        # Estimate cost for a read operation
        cost = self.calculator.estimate_operation_cost(
            backend="IPFS",
            operation_type=OperationType.READ
        )
        
        # Check that cost is correct
        self.assertEqual(cost, 0.0001)
    
    def test_estimate_total_cost(self):
        """Test estimating total costs for operations."""
        # Estimate cost for a write operation (storing 1 GB for 1 month)
        total_cost = self.calculator.estimate_total_cost(
            backend="IPFS",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            operation_type=OperationType.WRITE,
            months=1.0
        )
        
        # Check that costs are correct
        self.assertEqual(total_cost["storage_cost"], 0.02)
        self.assertEqual(total_cost["operation_cost"], 0.0001)
        self.assertEqual(total_cost["retrieval_cost"], 0.0)
        self.assertAlmostEqual(total_cost["total_cost"], 0.0201, places=4)
        
        # Estimate cost for a read operation (retrieving 1 GB)
        total_cost = self.calculator.estimate_total_cost(
            backend="S3",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            operation_type=OperationType.READ
        )
        
        # Check that costs are correct
        self.assertEqual(total_cost["storage_cost"], 0.0)
        self.assertEqual(total_cost["operation_cost"], 0.0005)
        self.assertEqual(total_cost["retrieval_cost"], 0.09)
        self.assertEqual(total_cost["total_cost"], 0.0905)
    
    def test_record_operation(self):
        """Test recording an operation for cost tracking."""
        # Record a write operation
        costs = self.calculator.record_operation(
            backend="IPFS",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            operation_type=OperationType.WRITE,
            months=1.0
        )
        
        # Check that costs were calculated correctly
        self.assertEqual(costs["storage_cost"], 0.02)
        self.assertEqual(costs["operation_cost"], 0.0001)
        
        # Check that the operation was recorded in history
        self.assertIn("IPFS", self.calculator.cost_history)
        self.assertEqual(len(self.calculator.cost_history["IPFS"]), 1)
        
        # Check that monthly totals were updated
        current_month = time.strftime('%Y-%m')
        self.assertIn(current_month, self.calculator.monthly_totals)
        self.assertIn("IPFS", self.calculator.monthly_totals[current_month])
        self.assertAlmostEqual(
            self.calculator.monthly_totals[current_month]["IPFS"],
            0.0201,
            places=4
        )
    
    def test_get_cost_model(self):
        """Test getting the cost model for a backend."""
        # Get cost model for IPFS
        model = self.calculator.get_cost_model("IPFS")
        
        # Check that model is correct
        self.assertEqual(model["storage_cost"], 0.02)
        self.assertEqual(model["retrieval_cost"], 0.01)
        self.assertEqual(model["operation_cost"], 0.0001)
        
        # Get cost model for non-existent backend (should fall back to S3)
        model = self.calculator.get_cost_model("NON_EXISTENT")
        self.assertEqual(model["storage_cost"], 0.023)  # S3 cost
    
    def test_get_monthly_cost(self):
        """Test getting monthly costs."""
        # Record operations in current month
        self.calculator.record_operation(
            backend="IPFS",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            operation_type=OperationType.WRITE
        )
        
        self.calculator.record_operation(
            backend="IPFS",
            size_bytes=2 * 1024 * 1024 * 1024,  # 2 GB
            operation_type=OperationType.READ
        )
        
        # Get monthly cost
        current_month = time.strftime('%Y-%m')
        monthly_cost = self.calculator.get_monthly_cost("IPFS", current_month)
        
        # Should be sum of the two operations
        # Write: 0.02 (storage) + 0.0001 (operation) = 0.0201
        # Read: 0.02 (retrieval) + 0.0001 (operation) = 0.0201
        # Total: 0.0402
        self.assertAlmostEqual(monthly_cost, 0.0402, places=4)
    
    def test_collect_metrics(self):
        """Test collecting metrics for routing."""
        # Collect metrics
        metrics = self.calculator.collect_metrics("IPFS")
        
        # Check that metrics include cost parameters
        self.assertIn("storage_cost", metrics)
        self.assertIn("retrieval_cost", metrics)
        self.assertIn("operation_cost", metrics)
        
        # Check values
        self.assertEqual(metrics["storage_cost"], 0.02)
        self.assertEqual(metrics["retrieval_cost"], 0.01)
        self.assertEqual(metrics["operation_cost"], 0.0001)
    
    def test_update_cost_model(self):
        """Test updating the cost model for a backend."""
        # Update the cost model
        self.calculator.update_cost_model("IPFS", {
            "storage_cost": 0.03,
            "retrieval_cost": 0.015
        })
        
        # Check that the model was updated
        model = self.calculator.get_cost_model("IPFS")
        self.assertEqual(model["storage_cost"], 0.03)
        self.assertEqual(model["retrieval_cost"], 0.015)
        self.assertEqual(model["operation_cost"], 0.0001)  # Unchanged
        
        # Update a non-existent backend
        self.calculator.update_cost_model("NEW", {
            "storage_cost": 0.01,
            "retrieval_cost": 0.01,
            "operation_cost": 0.0001
        })
        
        # Check that the new backend was added
        self.assertIn("NEW", self.calculator.cost_models)
        model = self.calculator.get_cost_model("NEW")
        self.assertEqual(model["storage_cost"], 0.01)


class TestContentTypeAnalyzer(unittest.TestCase):
    """Test cases for the ContentTypeAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ContentTypeAnalyzer()
    
    def test_analyze_content_type_from_extension(self):
        """Test analyzing content type from file extension."""
        # Test with various file extensions
        self.assertEqual(
            self.analyzer.analyze_content_type(None, filename="image.jpg"),
            ContentType.IMAGE
        )
        
        self.assertEqual(
            self.analyzer.analyze_content_type(None, filename="document.pdf"),
            ContentType.DOCUMENT
        )
        
        self.assertEqual(
            self.analyzer.analyze_content_type(None, filename="data.csv"),
            ContentType.DATASET
        )
        
        self.assertEqual(
            self.analyzer.analyze_content_type(None, filename="model.pt"),
            ContentType.MODEL
        )
        
        # Test with unknown extension
        self.assertEqual(
            self.analyzer.analyze_content_type(None, filename="file.xyz"),
            ContentType.UNKNOWN
        )
    
    def test_analyze_content_type_from_mime_type(self):
        """Test analyzing content type from MIME type."""
        # Test with MIME type provided
        self.assertEqual(
            self.analyzer.analyze_content_type(None, mime_type="image/jpeg"),
            ContentType.IMAGE
        )
        
        self.assertEqual(
            self.analyzer.analyze_content_type(None, mime_type="application/pdf"),
            ContentType.DOCUMENT
        )
        
        self.assertEqual(
            self.analyzer.analyze_content_type(None, mime_type="text/csv"),
            ContentType.DATASET
        )
        
        # Test with unknown MIME type
        self.assertEqual(
            self.analyzer.analyze_content_type(None, mime_type="application/x-custom"),
            ContentType.UNKNOWN
        )
    
    def test_analyze_content_type_from_metadata(self):
        """Test analyzing content type from metadata dictionary."""
        # Test with content_type in metadata
        self.assertEqual(
            self.analyzer.analyze_content_type({"content_type": "image"}),
            ContentType.IMAGE
        )
        
        # Test with mime_type in metadata
        self.assertEqual(
            self.analyzer.analyze_content_type({"mime_type": "video/mp4"}),
            ContentType.VIDEO
        )
        
        # Test with empty metadata
        self.assertEqual(
            self.analyzer.analyze_content_type({}),
            ContentType.UNKNOWN
        )
    
    def test_get_preferred_backends(self):
        """Test getting preferred backends for a content type."""
        # Get preferred backends for images
        preferred = self.analyzer.get_preferred_backends(ContentType.IMAGE)
        
        # Should be sorted by preference (higher score first)
        self.assertGreater(len(preferred), 0)
        
        # First item should be a tuple of (backend, score)
        self.assertEqual(len(preferred[0]), 2)
        
        # First backend should have highest preference score
        self.assertEqual(preferred[0][0], "IPFS")  # Based on default prefs
        
        # Scores should be in descending order
        scores = [score for _, score in preferred]
        self.assertEqual(scores, sorted(scores, reverse=True))
    
    def test_calculate_backend_score(self):
        """Test calculating backend score for a content type."""
        # Calculate score for IPFS with images
        score = self.analyzer.calculate_backend_score("IPFS", ContentType.IMAGE)
        
        # Should be the value from BACKEND_CONTENT_PREFERENCES
        self.assertEqual(score, 0.9)
        
        # Calculate score for non-existent backend
        score = self.analyzer.calculate_backend_score("NON_EXISTENT", ContentType.IMAGE)
        self.assertEqual(score, 0.5)  # Default score
    
    def test_collect_metrics(self):
        """Test collecting metrics for routing."""
        # Collect metrics
        metrics = self.analyzer.collect_metrics("IPFS")
        
        # Check that metrics include content type scores
        self.assertIn("image_score", metrics)
        self.assertIn("video_score", metrics)
        self.assertIn("document_score", metrics)
        self.assertIn("content_versatility_score", metrics)
        
        # Check values based on default preferences
        self.assertEqual(metrics["image_score"], 0.9)
        self.assertEqual(metrics["video_score"], 0.7)
        self.assertEqual(metrics["document_score"], 0.9)


class TestPerformanceMetrics(unittest.TestCase):
    """Test cases for the PerformanceMetrics class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bandwidth_monitor = MagicMock()
        self.latency_tracker = MagicMock()
        
        # Configure mocks to return metrics
        self.bandwidth_monitor.collect_metrics.return_value = {
            "throughput_mbps": 100.0,
            "max_throughput_mbps": 120.0
        }
        
        self.latency_tracker.collect_metrics.return_value = {
            "latency_ms": 50.0,
            "success_rate": 0.99
        }
        
        self.perf_metrics = PerformanceMetrics(
            bandwidth_monitor=self.bandwidth_monitor,
            latency_tracker=self.latency_tracker
        )
    
    def test_record_operation_performance(self):
        """Test recording operation performance."""
        # Record an operation
        start_time = time.time() - 0.1  # 100ms ago
        metrics = self.perf_metrics.record_operation_performance(
            backend="IPFS",
            start_time=start_time,
            bytes_sent=1024 * 1024,
            bytes_received=2 * 1024 * 1024,
            operation_type="read",
            success=True
        )
        
        # Check that both bandwidth and latency were recorded
        self.bandwidth_monitor.record_sample.assert_called_once()
        self.latency_tracker.record_sample.assert_called_once()
        
        # Check that metrics were returned
        self.assertIn("duration_seconds", metrics)
        self.assertIn("latency_ms", metrics)
        self.assertIn("throughput_mbps", metrics)
        
        # Check that values are reasonable
        self.assertAlmostEqual(metrics["duration_seconds"], 0.1, delta=0.05)
        self.assertAlmostEqual(metrics["latency_ms"], 100.0, delta=50.0)
        self.assertGreater(metrics["throughput_mbps"], 0)
    
    def test_combine_metrics(self):
        """Test combining metrics from different collectors."""
        # Combine metrics
        combined = self.perf_metrics.combine_metrics("IPFS")
        
        # Check that both bandwidth and latency metrics were included
        self.assertIn("throughput_mbps", combined)
        self.assertIn("latency_ms", combined)
        self.assertIn("success_rate", combined)
        self.assertIn("performance_score", combined)
        
        # Check values from mocks
        self.assertEqual(combined["throughput_mbps"], 100.0)
        self.assertEqual(combined["latency_ms"], 50.0)
        self.assertEqual(combined["success_rate"], 0.99)
        
        # Check that performance score was calculated
        self.assertGreater(combined["performance_score"], 0)
        self.assertLessEqual(combined["performance_score"], 1.0)
    
    def test_collect_metrics(self):
        """Test collecting metrics for routing."""
        # Collect metrics
        metrics = self.perf_metrics.collect_metrics("IPFS")
        
        # Check that metrics were collected and combined
        self.bandwidth_monitor.collect_metrics.assert_called_once_with("IPFS")
        self.latency_tracker.collect_metrics.assert_called_once_with("IPFS")
        
        # Check that metrics include performance indicators
        self.assertIn("throughput_mbps", metrics)
        self.assertIn("latency_ms", metrics)
        self.assertIn("success_rate", metrics)
        self.assertIn("performance_score", metrics)
    
    def test_get_fastest_backend(self):
        """Test getting the fastest backend."""
        # Configure latency_tracker to return different latencies
        def collect_metrics_side_effect(backend):
            latencies = {
                "IPFS": {"latency_ms": 50.0, "success_rate": 0.99},
                "S3": {"latency_ms": 70.0, "success_rate": 0.999},
                "FILECOIN": {"latency_ms": 200.0, "success_rate": 0.95}
            }
            return latencies.get(backend, {})
        
        self.latency_tracker.collect_metrics.side_effect = collect_metrics_side_effect
        
        # Mock the combine_metrics method to use our latency data
        self.perf_metrics.combine_metrics = MagicMock(side_effect=lambda backend: {
            "backend": backend,
            "latency_ms": collect_metrics_side_effect(backend).get("latency_ms"),
            "success_rate": collect_metrics_side_effect(backend).get("success_rate"),
            "performance_score": 0.8
        })
        
        # Get fastest backend
        result = self.perf_metrics.get_fastest_backend(["IPFS", "S3", "FILECOIN"])
        
        # Should return IPFS (lowest latency) and its latency
        self.assertEqual(result, ("IPFS", 50.0))
    
    def test_get_highest_throughput_backend(self):
        """Test getting the backend with highest throughput."""
        # Configure bandwidth_monitor to return different throughputs
        def collect_metrics_side_effect(backend):
            throughputs = {
                "IPFS": {"throughput_mbps": 100.0},
                "S3": {"throughput_mbps": 80.0},
                "FILECOIN": {"throughput_mbps": 50.0}
            }
            return throughputs.get(backend, {})
        
        self.bandwidth_monitor.collect_metrics.side_effect = collect_metrics_side_effect
        
        # Mock the combine_metrics method to use our throughput data
        self.perf_metrics.combine_metrics = MagicMock(side_effect=lambda backend: {
            "backend": backend,
            "throughput_mbps": collect_metrics_side_effect(backend).get("throughput_mbps"),
            "performance_score": 0.8
        })
        
        # Get highest throughput backend
        result = self.perf_metrics.get_highest_throughput_backend(["IPFS", "S3", "FILECOIN"])
        
        # Should return IPFS (highest throughput) and its throughput
        self.assertEqual(result, ("IPFS", 100.0))


if __name__ == "__main__":
    unittest.main()