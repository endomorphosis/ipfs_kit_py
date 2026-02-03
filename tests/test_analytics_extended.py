#!/usr/bin/env python3
"""
Extended tests for Analytics Dashboard.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import tempfile
from pathlib import Path


class TestAnalyticsDashboardExtended:
    """Extended tests for Analytics Dashboard functionality."""
    
    def test_metrics_collector_initialization(self):
        """Test metrics collector initialization with custom config."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector(window_size=120, retention_period=7200)
        
        assert collector.window_size == 120
        assert collector.retention_period == 7200
        assert collector.metrics is not None
    
    def test_record_operation_types(self):
        """Test recording different operation types."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record different operations
        collector.record_operation("get", success=True, latency=0.05)
        collector.record_operation("put", success=True, latency=0.1)
        collector.record_operation("delete", success=False, latency=0.02)
        
        metrics = collector.get_metrics()
        
        assert "get" in metrics or "operations" in metrics
        assert metrics["total_operations"] >= 3
    
    def test_record_operation_with_metadata(self):
        """Test recording operations with metadata."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        collector.record_operation(
            "get",
            success=True,
            latency=0.05,
            metadata={"size": 1024, "peer": "QmPeer1"}
        )
        
        metrics = collector.get_metrics()
        assert metrics is not None
    
    def test_get_metrics_by_time_window(self):
        """Test getting metrics for specific time window."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector(window_size=60)
        
        # Record some operations
        for i in range(10):
            collector.record_operation("get", success=True, latency=0.01 * i)
        
        metrics = collector.get_metrics(window_seconds=30)
        
        assert metrics is not None
        assert "total_operations" in metrics
    
    def test_calculate_success_rate(self):
        """Test success rate calculation."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record operations with mixed success
        for i in range(10):
            collector.record_operation("get", success=(i % 2 == 0), latency=0.01)
        
        metrics = collector.get_metrics()
        success_rate = metrics.get("success_rate", 0)
        
        assert 0 <= success_rate <= 1
    
    def test_calculate_average_latency(self):
        """Test average latency calculation."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        latencies = [0.01, 0.02, 0.03, 0.04, 0.05]
        for lat in latencies:
            collector.record_operation("get", success=True, latency=lat)
        
        metrics = collector.get_metrics()
        avg_latency = metrics.get("average_latency", 0)
        
        assert avg_latency > 0
        assert avg_latency == pytest.approx(sum(latencies) / len(latencies), rel=0.1)
    
    def test_calculate_percentiles(self):
        """Test latency percentile calculations."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record operations with varying latencies
        for i in range(100):
            collector.record_operation("get", success=True, latency=i * 0.001)
        
        metrics = collector.get_metrics()
        
        # Check for percentile metrics
        assert "p50_latency" in metrics or "median_latency" in metrics
        assert "p95_latency" in metrics or "percentiles" in metrics
        assert "p99_latency" in metrics or "percentiles" in metrics
    
    def test_track_bandwidth(self):
        """Test bandwidth tracking."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Track bandwidth
        collector.record_bandwidth(bytes_sent=1024, bytes_received=2048)
        collector.record_bandwidth(bytes_sent=512, bytes_received=1024)
        
        metrics = collector.get_metrics()
        
        assert "bandwidth" in metrics or "total_bytes_sent" in metrics
    
    def test_track_errors(self):
        """Test error tracking."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record errors
        collector.record_error("timeout", "Connection timeout")
        collector.record_error("not_found", "Object not found")
        collector.record_error("timeout", "Another timeout")
        
        metrics = collector.get_metrics()
        
        assert "errors" in metrics or "total_errors" in metrics
        assert metrics.get("total_errors", 0) >= 3
    
    def test_get_error_distribution(self):
        """Test error distribution analysis."""
        from ipfs_kit_py.analytics_dashboard import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record various errors
        for _ in range(5):
            collector.record_error("timeout", "Timeout")
        for _ in range(3):
            collector.record_error("not_found", "Not found")
        
        metrics = collector.get_metrics()
        error_dist = metrics.get("error_distribution", {})
        
        if error_dist:
            assert "timeout" in error_dist or len(error_dist) > 0
    
    def test_analytics_dashboard_initialization(self):
        """Test analytics dashboard initialization."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = Mock()
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        
        assert dashboard.ipfs_api == mock_ipfs
        assert dashboard.collector is not None
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record some data
        dashboard.collector.record_operation("get", success=True, latency=0.05)
        dashboard.collector.record_operation("put", success=True, latency=0.1)
        
        data = dashboard.get_dashboard_data()
        
        assert data is not None
        assert "metrics" in data or "operations" in data
    
    def test_generate_latency_chart(self):
        """Test latency chart generation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record operations
        for i in range(20):
            dashboard.collector.record_operation("get", success=True, latency=0.01 * i)
        
        chart = dashboard.generate_latency_chart()
        
        assert chart is not None
    
    def test_generate_bandwidth_chart(self):
        """Test bandwidth chart generation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record bandwidth
        for i in range(10):
            dashboard.collector.record_bandwidth(bytes_sent=1024 * i, bytes_received=2048 * i)
        
        chart = dashboard.generate_bandwidth_chart()
        
        assert chart is not None
    
    def test_generate_error_chart(self):
        """Test error distribution chart generation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record errors
        dashboard.collector.record_error("timeout", "Timeout 1")
        dashboard.collector.record_error("timeout", "Timeout 2")
        dashboard.collector.record_error("not_found", "Not found")
        
        chart = dashboard.generate_error_chart()
        
        assert chart is not None
    
    def test_generate_success_rate_chart(self):
        """Test success rate chart generation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record mixed success operations
        for i in range(20):
            dashboard.collector.record_operation("get", success=(i % 3 != 0), latency=0.01)
        
        chart = dashboard.generate_success_rate_chart()
        
        assert chart is not None
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """Test starting real-time monitoring."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = AsyncMock()
        mock_ipfs.get_stats = AsyncMock(return_value={"peers": 10, "bandwidth": 1000})
        
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        
        # Start monitoring (should not block)
        task = asyncio.create_task(dashboard.start_monitoring(interval=1))
        
        # Let it run briefly
        await asyncio.sleep(0.1)
        
        # Stop monitoring
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_collect_peer_stats(self):
        """Test collecting peer statistics."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = AsyncMock()
        mock_ipfs.swarm_peers = AsyncMock(return_value=[
            {"peer": "QmPeer1", "addr": "/ip4/1.2.3.4"},
            {"peer": "QmPeer2", "addr": "/ip4/5.6.7.8"}
        ])
        
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        
        stats = await dashboard.collect_peer_stats()
        
        assert stats is not None
        assert stats.get("peer_count", 0) >= 0
    
    @pytest.mark.asyncio
    async def test_collect_storage_stats(self):
        """Test collecting storage statistics."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = AsyncMock()
        mock_ipfs.repo_stat = AsyncMock(return_value={
            "repo_size": 1000000,
            "num_objects": 500
        })
        
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        
        stats = await dashboard.collect_storage_stats()
        
        assert stats is not None
    
    def test_export_metrics_json(self):
        """Test exporting metrics to JSON."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        import json
        
        dashboard = AnalyticsDashboard()
        dashboard.collector.record_operation("get", success=True, latency=0.05)
        
        json_data = dashboard.export_metrics_json()
        
        assert json_data is not None
        # Should be valid JSON
        parsed = json.loads(json_data)
        assert parsed is not None
    
    def test_export_metrics_csv(self):
        """Test exporting metrics to CSV."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        dashboard.collector.record_operation("get", success=True, latency=0.05)
        dashboard.collector.record_operation("put", success=False, latency=0.1)
        
        csv_data = dashboard.export_metrics_csv()
        
        assert csv_data is not None
        assert "," in csv_data or "\n" in csv_data  # CSV format
    
    def test_get_top_operations(self):
        """Test getting top operations by count."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record various operations
        for _ in range(10):
            dashboard.collector.record_operation("get", success=True, latency=0.01)
        for _ in range(5):
            dashboard.collector.record_operation("put", success=True, latency=0.02)
        for _ in range(3):
            dashboard.collector.record_operation("delete", success=True, latency=0.01)
        
        top_ops = dashboard.get_top_operations(limit=3)
        
        assert top_ops is not None
        assert len(top_ops) <= 3
    
    def test_get_slowest_operations(self):
        """Test getting slowest operations."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record operations with different latencies
        dashboard.collector.record_operation("fast", success=True, latency=0.01)
        dashboard.collector.record_operation("medium", success=True, latency=0.05)
        dashboard.collector.record_operation("slow", success=True, latency=0.5)
        
        slowest = dashboard.get_slowest_operations(limit=2)
        
        assert slowest is not None
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test dashboard health check."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        health = await dashboard.health_check()
        
        assert health is not None
        assert "status" in health
    
    def test_reset_metrics(self):
        """Test resetting metrics."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        # Record some data
        dashboard.collector.record_operation("get", success=True, latency=0.05)
        
        # Reset
        dashboard.reset_metrics()
        
        metrics = dashboard.get_dashboard_data()
        assert metrics["metrics"]["total_operations"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
