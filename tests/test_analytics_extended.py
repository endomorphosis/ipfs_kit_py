#!/usr/bin/env python3
"""
Extended tests for Analytics Dashboard - Fixed to match actual API.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import tempfile
from pathlib import Path

from ipfs_kit_py.analytics_dashboard import HAS_MATPLOTLIB, HAS_NUMPY


class TestAnalyticsDashboardExtended:
    """Extended tests for Analytics Dashboard functionality."""
    
    def test_analytics_collector_initialization(self):
        """Test analytics collector initialization."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector(window_size=120)
        
        assert collector.window_size == 120
        assert collector.operations is not None
        assert collector.total_operations == 0
    
    def test_record_operation_basic(self):
        """Test recording basic operations."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        collector.record_operation("get", duration=0.05, success=True)
        collector.record_operation("put", duration=0.1, success=True)
        collector.record_operation("delete", duration=0.02, success=False)
        
        assert collector.total_operations == 3
        assert collector.total_errors == 1
        assert collector.operation_counts["get"] == 1
    
    def test_record_operation_with_bytes(self):
        """Test recording operations with bytes transferred."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        collector.record_operation(
            "get",
            duration=0.05,
            bytes_transferred=1024,
            success=True
        )
        
        assert collector.total_bytes == 1024
    
    def test_record_operation_with_peer(self):
        """Test recording operations with peer ID."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        collector.record_operation(
            "get",
            duration=0.05,
            bytes_transferred=1024,
            success=True,
            peer_id="QmPeer1"
        )
        
        assert "QmPeer1" in collector.peer_stats
        assert collector.peer_stats["QmPeer1"]["requests"] == 1
        assert collector.peer_stats["QmPeer1"]["bytes"] == 1024
    
    def test_get_metrics_structure(self):
        """Test metrics structure."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        for i in range(10):
            collector.record_operation("get", duration=0.01 * (i + 1), success=True)
        
        metrics = collector.get_metrics()
        
        assert "total_operations" in metrics
        assert "total_bytes" in metrics
        assert "total_errors" in metrics
        assert "ops_per_second" in metrics
        assert "error_rate" in metrics
        assert "latency" in metrics
        assert "operation_counts" in metrics
    
    def test_latency_statistics(self):
        """Test latency statistics calculation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        for i in range(100):
            collector.record_operation("get", duration=i * 0.001, success=True)
        
        metrics = collector.get_metrics()
        latency = metrics["latency"]
        
        assert "min" in latency
        assert "max" in latency
        assert "mean" in latency
        assert "p50" in latency
        assert "p95" in latency
        assert "p99" in latency
    
    def test_error_tracking(self):
        """Test error tracking."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        collector.record_operation("get", duration=0.01, success=False)
        collector.record_operation("put", duration=0.01, success=False)
        collector.record_operation("get", duration=0.01, success=False)
        
        metrics = collector.get_metrics()
        
        assert metrics["total_errors"] == 3
        assert metrics["error_counts"]["get"] == 2
        assert metrics["error_counts"]["put"] == 1
    
    def test_top_peers(self):
        """Test top peers tracking."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        collector.record_operation("get", duration=0.01, peer_id="Peer1", bytes_transferred=100)
        collector.record_operation("get", duration=0.01, peer_id="Peer2", bytes_transferred=200)
        collector.record_operation("get", duration=0.01, peer_id="Peer1", bytes_transferred=150)
        
        metrics = collector.get_metrics()
        top_peers = metrics["top_peers"]
        
        assert len(top_peers) == 2
        assert top_peers[0]["peer_id"] == "Peer1"  # Most requests
        assert top_peers[0]["requests"] == 2
    
    def test_analytics_dashboard_initialization(self):
        """Test analytics dashboard initialization."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard, AnalyticsCollector
        
        mock_ipfs = Mock()
        collector = AnalyticsCollector()
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs, collector=collector)
        
        assert dashboard.ipfs_api == mock_ipfs
        assert dashboard.collector == collector
    
    def test_get_dashboard_data_basic(self):
        """Test getting dashboard data."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        dashboard.collector.record_operation("get", duration=0.05, success=True)
        dashboard.collector.record_operation("put", duration=0.1, success=True)
        
        data = dashboard.get_dashboard_data()
        
        assert "metrics" in data
        assert "cluster" in data
        assert "storage" in data
        assert "network" in data
        assert "timestamp" in data
    
    def test_storage_metrics(self):
        """Test storage metrics collection."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = Mock()
        mock_ipfs.get_pin_stats = Mock(return_value={"count": 10, "total_size": 10240})
        mock_ipfs.get_cache_stats = Mock(return_value={"hit_rate": 0.85, "size": 5120})
        
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        data = dashboard.get_dashboard_data()
        
        storage = data["storage"]
        assert storage["pinned_items"] == 10
        assert storage["total_size"] == 10240
        assert storage["cache_hit_rate"] == 0.85
    
    def test_network_metrics(self):
        """Test network metrics collection."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        mock_ipfs = Mock()
        mock_ipfs.get_swarm_peers = Mock(return_value=["Peer1", "Peer2", "Peer3"])
        mock_ipfs.get_bandwidth_stats = Mock(return_value={"rate_in": 1024, "rate_out": 2048})
        
        dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
        data = dashboard.get_dashboard_data()
        
        network = data["network"]
        assert network["peer_count"] == 3
        assert network["bandwidth_in"] == 1024
        assert network["bandwidth_out"] == 2048
    
    @pytest.mark.skipif(not (HAS_MATPLOTLIB and HAS_NUMPY), reason="Matplotlib optional")
    def test_generate_charts(self):
        """Test chart generation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
        
        dashboard = AnalyticsDashboard()
        
        for i in range(50):
            dashboard.collector.record_operation("get", duration=0.01 * i, success=True)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            charts = dashboard.generate_charts(output_dir=tmpdir)
            assert charts is not None
    
    def test_window_size_limit(self):
        """Test that window size is respected."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector(window_size=10)
        
        # Record more than window size
        for i in range(20):
            collector.record_operation("get", duration=0.01, success=True)
        
        # Should only keep last 10
        assert len(collector.operations) == 10
        assert len(collector.latencies) == 10
    
    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        
        collector = AnalyticsCollector()
        
        # 3 successes, 1 failure = 25% error rate
        collector.record_operation("get", duration=0.01, success=True)
        collector.record_operation("get", duration=0.01, success=True)
        collector.record_operation("get", duration=0.01, success=True)
        collector.record_operation("get", duration=0.01, success=False)
        
        metrics = collector.get_metrics()
        assert metrics["error_rate"] == pytest.approx(0.25)
    
    def test_operations_per_second(self):
        """Test operations per second calculation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        import time
        
        collector = AnalyticsCollector()
        
        # Record operations
        for i in range(10):
            collector.record_operation("get", duration=0.01, success=True)
        
        time.sleep(0.1)  # Wait a bit for time to pass
        
        metrics = collector.get_metrics()
        assert metrics["ops_per_second"] > 0
    
    def test_bytes_per_second(self):
        """Test bytes per second calculation."""
        from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
        import time
        
        collector = AnalyticsCollector()
        
        # Record operations with bytes
        for i in range(10):
            collector.record_operation("get", duration=0.01, bytes_transferred=1024, success=True)
        
        time.sleep(0.1)
        
        metrics = collector.get_metrics()
        assert metrics["bytes_per_second"] > 0
        assert metrics["total_bytes"] == 10240
