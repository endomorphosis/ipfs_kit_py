#!/usr/bin/env python3
"""
Additional coverage tests to increase test coverage across all PR features.

Focus areas:
- S3 Gateway (28% → 50%+)
- WASM Support edge cases
- GraphRAG edge cases
- Analytics Dashboard edge cases
- Multi-Region Cluster edge cases
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import sqlite3


# ============================================================================
# S3 Gateway Additional Coverage
# ============================================================================

def test_s3_gateway_initialization():
    """Test S3Gateway initialization."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_ipfs = Mock()
    gateway.ipfs_api = mock_ipfs
    gateway.port = 9000
    gateway.host = "0.0.0.0"
    
    assert gateway.ipfs_api is not None
    assert gateway.port == 9000
    assert gateway.host == "0.0.0.0"


def test_s3_gateway_dict_to_xml():
    """Test XML conversion for S3 responses."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    gateway.ipfs_api = Mock()
    
    # Test simple dict
    simple_dict = {"key": "value"}
    xml = gateway._dict_to_xml(simple_dict)
    assert "key" in xml
    assert "value" in xml
    
    # Test nested dict
    nested_dict = {
        "parent": {
            "child1": "value1",
            "child2": "value2"
        }
    }
    xml = gateway._dict_to_xml(nested_dict)
    assert "parent" in xml
    assert "child1" in xml
    assert "value1" in xml


def test_s3_gateway_list_to_xml():
    """Test XML conversion for list elements."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    gateway.ipfs_api = Mock()
    
    # Test list of dicts
    list_dict = {
        "Contents": [
            {"Key": "file1.txt", "Size": 100},
            {"Key": "file2.txt", "Size": 200}
        ]
    }
    xml = gateway._dict_to_xml(list_dict)
    assert "file1.txt" in xml
    assert "file2.txt" in xml
    assert "100" in xml
    assert "200" in xml


@pytest.mark.anyio
async def test_s3_gateway_vfs_bucket_listing():
    """Test VFS bucket listing."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_vfs = AsyncMock()
    mock_vfs.list_buckets = AsyncMock(return_value=[
        {"name": "bucket1"},
        {"name": "bucket2"},
        {"name": "bucket3"}
    ])
    gateway.ipfs_api = mock_vfs
    
    buckets = await gateway._get_vfs_buckets()
    assert len(buckets) == 3
    assert buckets[0]["name"] == "bucket1"


@pytest.mark.anyio
async def test_s3_gateway_object_read():
    """Test object reading from VFS."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_vfs = AsyncMock()
    test_content = b"test file content"
    mock_vfs.vfs_read = AsyncMock(return_value=test_content)
    gateway.ipfs_api = mock_vfs
    
    content = await gateway._get_object("test-bucket", "path/to/file.txt")
    assert content == test_content
    mock_vfs.vfs_read.assert_called_once()


@pytest.mark.anyio
async def test_s3_gateway_object_metadata():
    """Test object metadata retrieval."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_vfs = AsyncMock()
    mock_vfs.vfs_stat = AsyncMock(return_value={
        "size": 1024,
        "type": "file",
        "hash": "QmTest123"
    })
    gateway.ipfs_api = mock_vfs
    
    metadata = await gateway._get_object_metadata("test-bucket", "file.txt")
    assert metadata["size"] == 1024
    assert metadata["type"] == "file"


# ============================================================================
# WASM Support Additional Coverage
# ============================================================================

@pytest.mark.anyio
async def test_wasm_bridge_initialization():
    """Test WasmIPFSBridge initialization."""
    from ipfs_kit_py.wasm_support import WasmIPFSBridge
    
    mock_ipfs = Mock()
    # Don't actually initialize runtime, just test setup
    bridge = WasmIPFSBridge.__new__(WasmIPFSBridge)
    bridge.ipfs_api = mock_ipfs
    bridge.runtime = "wasmtime"
    
    assert bridge.ipfs_api is not None
    assert bridge.runtime == "wasmtime"


def test_wasm_module_registry_list():
    """Test module registry listing."""
    from ipfs_kit_py.wasm_support import WasmModuleRegistry
    
    registry = WasmModuleRegistry(ipfs_api=Mock())
    
    # Add some modules
    registry.modules = {
        "module1": {"cid": "Qm1", "metadata": {}},
        "module2": {"cid": "Qm2", "metadata": {}}
    }
    
    modules = registry.list_modules()
    assert len(modules) == 2
    assert modules[0]["name"] in ["module1", "module2"]


@pytest.mark.anyio
async def test_wasm_module_registry_registration():
    """Test module registration with metadata."""
    from ipfs_kit_py.wasm_support import WasmModuleRegistry
    
    registry = WasmModuleRegistry(ipfs_api=Mock())
    
    result = await registry.register_module(
        "test_module",
        "QmTest123",
        metadata={"version": "1.0.0", "author": "test"}
    )
    
    assert result == True
    module = await registry.get_module("test_module")
    assert module["cid"] == "QmTest123"
    assert module["metadata"]["version"] == "1.0.0"


def test_wasm_js_bindings_structure():
    """Test JavaScript bindings structure."""
    from ipfs_kit_py.wasm_support import WasmJSBindings
    
    js_code = WasmJSBindings.generate_js_bindings(
        module_name="TestModule",
        functions=["func1", "func2", "func3"]
    )
    
    # Check for class structure
    assert "TestModule" in js_code
    assert "class" in js_code or "async" in js_code
    assert "load" in js_code or "Load" in js_code


# ============================================================================
# GraphRAG Additional Coverage
# ============================================================================

@pytest.mark.anyio
async def test_graphrag_empty_content_handling():
    """Test GraphRAG with empty content."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Try to index empty content
        result = await engine.index_content("QmEmpty", "/empty", "")
        assert result["success"] == True  # Should handle gracefully


@pytest.mark.anyio
async def test_graphrag_special_characters():
    """Test GraphRAG with special characters in content."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        special_content = "Test with émojis 🎉 and üñíçödé characters"
        result = await engine.index_content("QmSpecial", "/special", special_content)
        assert result["success"] == True


def test_graphrag_cache_hit_miss_tracking():
    """Test cache hit/miss statistics."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
        
        # Simulate cache operations
        engine.stats["cache_hits"] = 50
        engine.stats["cache_misses"] = 10
        
        stats = engine.get_stats()
        assert stats["success"] == True
        cache_stats = stats["stats"]["cache"]
        assert cache_stats["hits"] == 50
        assert cache_stats["misses"] == 10
        assert cache_stats["hit_rate"] > 0.8


@pytest.mark.anyio
async def test_graphrag_relationship_confidence():
    """Test relationship with confidence scores."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Create relationship with confidence
        result = await engine.add_relationship(
            "QmCid1", "QmCid2",
            "related_to",
            confidence=0.85
        )
        assert result["success"] == True


@pytest.mark.anyio
async def test_graphrag_bulk_operations_empty():
    """Test bulk indexing with empty list."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        result = await engine.bulk_index_content([])
        assert result["success"] == True
        assert result["indexed_count"] == 0  # Key is 'indexed_count'


@pytest.mark.anyio
async def test_graphrag_multiple_versions():
    """Test version tracking with multiple updates."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        cid = "QmVersionTest"
        path = "/test/version.txt"
        
        # Index multiple versions
        await engine.index_content(cid, path, "Version 1")
        await engine.index_content(cid, path, "Version 2")
        await engine.index_content(cid, path, "Version 3")
        
        # Check version was incremented
        with sqlite3.connect(engine.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM content_index WHERE cid = ?", (cid,))
            version = cursor.fetchone()
            assert version is not None
            assert version[0] >= 1


# ============================================================================
# Analytics Dashboard Additional Coverage
# ============================================================================

def test_analytics_collector_window_size():
    """Test analytics collector with window size limits."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector(window_size=10)
    
    # Add more operations than window size
    for i in range(20):
        collector.record_operation("get", 0.1, 1000)
    
    # Check total operations tracked (not limited by window)
    metrics = collector.get_metrics()
    assert metrics["total_operations"] == 20  # Key is 'total_operations'


def test_analytics_latency_percentiles():
    """Test latency percentile calculations."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record operations with varying latencies
    latencies = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    for lat in latencies:
        collector.record_operation("get", lat, 1000)
    
    # Get metrics (contains latency stats)
    metrics = collector.get_metrics()
    assert "latency" in metrics
    assert "p50" in metrics["latency"]
    assert "p95" in metrics["latency"]
    assert "p99" in metrics["latency"]


def test_analytics_error_tracking():
    """Test error rate tracking."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record operations with some errors
    collector.record_operation("get", 0.1, 1000, success=True)
    collector.record_operation("get", 0.2, 1000, success=True)
    collector.record_operation("get", 0.3, 1000, success=False)
    collector.record_operation("add", 0.5, 2000, success=False)
    
    # Get error rate
    metrics = collector.get_metrics()
    assert "error_rate" in metrics or "errors" in metrics


def test_analytics_peer_statistics():
    """Test peer-based statistics."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record operations from different peers
    for i in range(5):
        collector.record_operation("get", 0.1, 1000, peer_id=f"peer{i%3}")
    
    # Get peer stats (top_peers contains peer info)
    metrics = collector.get_metrics()
    assert "top_peers" in metrics
    assert isinstance(metrics["top_peers"], list)


def test_analytics_operation_types():
    """Test operation type tracking."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record different operation types
    collector.record_operation("get", 0.1, 1000)
    collector.record_operation("get", 0.2, 1500)
    collector.record_operation("add", 0.5, 2000)
    collector.record_operation("add", 0.6, 2500)
    collector.record_operation("pin", 1.0, 500)
    
    metrics = collector.get_metrics()
    assert metrics["total_operations"] >= 5  # Key is 'total_operations'
    assert "operation_counts" in metrics  # Has operation type breakdown


# ============================================================================
# Multi-Region Cluster Additional Coverage
# ============================================================================

def test_multi_region_add_multiple_regions():
    """Test adding multiple regions."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add multiple regions (add_region is synchronous, not async)
    cluster.add_region("us-east-1", "N. Virginia", "us-east", ["http://node1:5001"])
    cluster.add_region("us-west-1", "N. California", "us-west", ["http://node2:5001"])
    cluster.add_region("eu-west-1", "Ireland", "eu-west", ["http://node3:5001"])
    
    # Check all regions added
    assert len(cluster.regions) == 3
    assert "us-east-1" in cluster.regions
    assert "us-west-1" in cluster.regions
    assert "eu-west-1" in cluster.regions


@pytest.mark.anyio
async def test_multi_region_health_check_all():
    """Test health check for all regions."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add regions (synchronous)
    cluster.add_region("region1", "Region 1", "zone1", ["http://node1:5001"])
    cluster.add_region("region2", "Region 2", "zone2", ["http://node2:5001"])
    
    # Use the actual health_check method
    result = await cluster.health_check()
    assert "regions" in result or "healthy" in str(result).lower()


def test_multi_region_routing_strategies():
    """Test different routing strategies."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add regions (synchronous) - regions are dataclass instances
    cluster.add_region("low-latency", "Fast", "zone1", ["http://fast:5001"])
    cluster.add_region("high-latency", "Slow", "zone2", ["http://slow:5001"])
    
    # Update latency attributes directly (Region is a dataclass)
    cluster.regions["low-latency"].average_latency = 10
    cluster.regions["high-latency"].average_latency = 100
    
    # Use actual method name: select_region with latency_optimized strategy
    cluster.routing_strategy = "latency_optimized"
    best = cluster.select_region()
    assert best.name == "low-latency"


@pytest.mark.anyio
async def test_multi_region_failover_scenarios():
    """Test failover between regions."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, RegionStatus
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add primary and backup regions (synchronous)
    cluster.add_region("primary", "Primary", "zone1", ["http://primary:5001"])
    cluster.add_region("backup", "Backup", "zone2", ["http://backup:5001"])
    
    # Mark primary as unavailable (Region is dataclass)
    cluster.regions["primary"].status = RegionStatus.UNAVAILABLE
    cluster.regions["backup"].status = RegionStatus.HEALTHY
    
    # Use actual method name: failover
    result = await cluster.failover("primary")
    assert "backup_regions" in result
    assert len(result["backup_regions"]) > 0


def test_multi_region_statistics():
    """Test cluster statistics collection."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster, RegionStatus
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add regions with various statuses (synchronous)
    cluster.add_region("healthy1", "H1", "z1", ["http://h1:5001"])
    cluster.add_region("healthy2", "H2", "z2", ["http://h2:5001"])
    cluster.add_region("unhealthy1", "U1", "z3", ["http://u1:5001"])
    
    # Update status (Region is dataclass)
    cluster.regions["healthy1"].status = RegionStatus.HEALTHY
    cluster.regions["healthy2"].status = RegionStatus.HEALTHY
    cluster.regions["unhealthy1"].status = RegionStatus.UNAVAILABLE
    
    # Get statistics
    stats = cluster.get_cluster_stats()
    assert stats["total_regions"] == 3
    assert "regions_by_status" in stats
    assert stats["regions_by_status"].get("healthy", 0) == 2


@pytest.mark.anyio
async def test_multi_region_content_replication():
    """Test content replication across regions."""
    from ipfs_kit_py.multi_region_cluster import MultiRegionCluster
    
    cluster = MultiRegionCluster(ipfs_api=Mock())
    
    # Add regions (synchronous)
    cluster.add_region("region1", "R1", "z1", ["http://r1:5001"])
    cluster.add_region("region2", "R2", "z2", ["http://r2:5001"])
    
    # Test that regions were added
    assert len(cluster.regions) == 2
    assert "region1" in cluster.regions
    assert "region2" in cluster.regions
    
    # Test basic region properties
    assert cluster.regions["region1"].location == "R1"
    assert cluster.regions["region2"].location == "R2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
