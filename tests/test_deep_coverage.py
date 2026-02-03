#!/usr/bin/env python3
"""
Deep coverage tests for all PR features.

This test file aims to achieve maximum coverage for:
- S3 Gateway (18% → 40%+)
- WASM Support (38% → 55%+)
- GraphRAG (55% → 65%+)
- Analytics Dashboard (52% → 60%+)
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import sqlite3


# ============================================================================
# S3 Gateway Deep Coverage Tests
# ============================================================================

def test_s3_gateway_xml_conversion():
    """Test XML conversion utility methods in S3Gateway."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    # Create gateway without starting server
    gateway = S3Gateway.__new__(S3Gateway)
    gateway.ipfs_api = Mock()
    
    # Test dict_to_xml conversion
    test_dict = {
        "ListBucketResult": {
            "Name": "test-bucket",
            "Contents": [
                {"Key": "file1.txt", "Size": 100},
                {"Key": "file2.txt", "Size": 200}
            ]
        }
    }
    
    xml_result = gateway._dict_to_xml(test_dict)
    assert isinstance(xml_result, str)
    assert "ListBucketResult" in xml_result
    assert "test-bucket" in xml_result


def test_s3_gateway_error_response():
    """Test S3 error response generation."""
    pytest.importorskip("fastapi")
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    gateway.ipfs_api = Mock()
    
    # Test error response generation
    response = gateway._error_response(
        code="NoSuchBucket",
        message="The specified bucket does not exist"
    )
    
    assert response is not None
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_s3_gateway_bucket_operations():
    """Test S3 bucket operation methods."""
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_ipfs = AsyncMock()
    mock_ipfs.list_buckets = AsyncMock(return_value=[
        {"name": "bucket1", "created": "2024-01-01T00:00:00Z"},
        {"name": "bucket2", "created": "2024-01-02T00:00:00Z"}
    ])
    gateway.ipfs_api = mock_ipfs
    
    # Test bucket listing
    buckets = await gateway._get_vfs_buckets()
    assert len(buckets) == 2
    assert buckets[0]["name"] == "bucket1"


@pytest.mark.asyncio  
async def test_s3_gateway_object_operations():
    """Test S3 object operation methods."""
    pytest.importorskip("fastapi")
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_ipfs = AsyncMock()
    mock_ipfs.vfs_read = AsyncMock(return_value=b"file content")
    gateway.ipfs_api = mock_ipfs
    
    # Test object retrieval
    content = await gateway._get_object("bucket", "path/to/file.txt")
    assert content == b"file content"


@pytest.mark.asyncio
async def test_s3_gateway_metadata_operations():
    """Test S3 metadata operations."""
    pytest.importorskip("fastapi")
    from ipfs_kit_py.s3_gateway import S3Gateway
    
    gateway = S3Gateway.__new__(S3Gateway)
    mock_ipfs = AsyncMock()
    mock_ipfs.vfs_stat = AsyncMock(return_value={
        "size": 100,
        "type": "file",
        "hash": "QmTest123"
    })
    gateway.ipfs_api = mock_ipfs
    
    # Test metadata retrieval
    metadata = await gateway._get_object_metadata("bucket", "path/to/file.txt")
    assert metadata is not None
    assert "size" in metadata


# ============================================================================
# WASM Support Deep Coverage Tests
# ============================================================================

@pytest.mark.asyncio
async def test_wasm_module_registry():
    """Test WASM module registry functionality."""
    from ipfs_kit_py.wasm_support import WasmModuleRegistry
    
    # Test registry with actual class
    mock_ipfs = AsyncMock()
    registry = WasmModuleRegistry(ipfs_api=mock_ipfs)
    
    # Test module registration
    test_cid = "QmTest123"
    await registry.register_module("test_module", test_cid, version="1.0.0")
    
    # Test module retrieval
    module_info = await registry.get_module("test_module")
    assert module_info is not None
    assert module_info["cid"] == test_cid


def test_wasm_ipfs_imports():
    """Test WASM IPFS import function creation."""
    from ipfs_kit_py.wasm_support import WasmIPFSBridge
    
    bridge = WasmIPFSBridge.__new__(WasmIPFSBridge)
    bridge.ipfs_api = Mock()
    bridge.runtime = "wasmtime"
    
    # Test import creation
    imports = bridge.create_ipfs_imports()
    
    assert imports is not None
    assert isinstance(imports, dict)


def test_wasm_js_bindings_generation():
    """Test JavaScript bindings generation."""
    from ipfs_kit_py.wasm_support import WasmModuleRegistry
    
    # Test JS code generation
    js_code = WasmModuleRegistry.generate_js_bindings(
        module_name="test_module",
        functions=["add", "get", "cat"]
    )
    
    assert "test_module" in js_code
    assert "add" in js_code
    assert "get" in js_code
    assert "cat" in js_code
    assert "export" in js_code


@pytest.mark.asyncio
async def test_wasm_error_handling():
    """Test WASM error handling."""
    from ipfs_kit_py.wasm_support import WasmIPFSBridge
    
    bridge = WasmIPFSBridge.__new__(WasmIPFSBridge)
    bridge.ipfs_api = None
    bridge.runtime = "wasmtime"
    
    # Test error when IPFS API not initialized
    with pytest.raises(Exception):
        await bridge.load_wasm_module("QmTest123")


@pytest.mark.asyncio
async def test_wasm_module_storage():
    """Test WASM module storage to IPFS."""
    from ipfs_kit_py.wasm_support import WasmIPFSBridge
    
    bridge = WasmIPFSBridge.__new__(WasmIPFSBridge)
    mock_ipfs = AsyncMock()
    mock_ipfs.add = AsyncMock(return_value={"Hash": "QmTest123"})
    bridge.ipfs_api = mock_ipfs
    bridge.runtime = "wasmtime"
    
    # Test module storage
    test_wasm = b"\x00asm\x01\x00\x00\x00"  # Minimal WASM header
    cid = await bridge.store_wasm_module(test_wasm, metadata={"name": "test"})
    assert cid == "QmTest123"


# ============================================================================
# GraphRAG Deep Coverage Tests  
# ============================================================================

def test_graphrag_cache_operations():
    """Test GraphRAG embedding cache operations."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
        
        # Test cache save
        test_embeddings = {
            "test_content_hash": [0.1, 0.2, 0.3, 0.4, 0.5]
        }
        engine.embedding_cache = test_embeddings
        engine._save_embedding_cache()
        
        # Verify cache file exists
        assert os.path.exists(engine.embedding_cache_path)
        
        # Test cache load
        engine.embedding_cache = {}
        loaded_cache = engine._load_embedding_cache()
        assert "test_content_hash" in loaded_cache
        assert loaded_cache["test_content_hash"] == [0.1, 0.2, 0.3, 0.4, 0.5]


@pytest.mark.asyncio
async def test_graphrag_entity_extraction_variations():
    """Test entity extraction with different content types."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Test with various content patterns
        contents = [
            "Visit https://example.com for more info",
            "Contact user@example.com for details",
            "File located at /path/to/file.txt",
            "CID: QmTest123ABC456DEF789",
            "Python keywords: async await class def import"
        ]
        
        for content in contents:
            entities = await engine.extract_entities(content)
            assert isinstance(entities, dict)
            assert len(entities) > 0


@pytest.mark.asyncio
async def test_graphrag_relationship_operations():
    """Test relationship operations."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Add test relationships
        await engine.add_relationship("node1", "node2", "depends_on", confidence=0.9)
        await engine.add_relationship("node2", "node3", "similar_to", confidence=0.8)
        await engine.add_relationship("node3", "node4", "depends_on", confidence=0.7)
        
        # Verify relationships were added to knowledge graph
        if engine.knowledge_graph:
            assert engine.knowledge_graph.number_of_edges() > 0


def test_graphrag_graph_analysis():
    """Test graph analytics methods."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Only test if NetworkX is available
        if engine.knowledge_graph:
            # Build a small graph
            import asyncio
            asyncio.run(engine.add_relationship("A", "B", "connects_to"))
            asyncio.run(engine.add_relationship("B", "C", "connects_to"))
            asyncio.run(engine.add_relationship("C", "D", "connects_to"))
            asyncio.run(engine.add_relationship("A", "D", "connects_to"))
            
            # Test analytics
            analysis = engine.analyze_graph()
            assert "node_count" in analysis
            assert "edge_count" in analysis


def test_graphrag_statistics_methods():
    """Test GraphRAG statistics collection."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
        
        # Simulate some operations
        engine.stats["total_indexed"] = 100
        engine.stats["cache_hits"] = 75
        engine.stats["cache_misses"] = 25
        
        # Get statistics
        stats = engine.get_stats()
        
        assert stats["total_indexed"] == 100
        assert stats["cache_hits"] == 75
        assert stats["cache_misses"] == 25
        assert "cache_hit_rate" in stats
        assert stats["cache_hit_rate"] == 0.75


@pytest.mark.asyncio
async def test_graphrag_version_tracking():
    """Test content version history tracking."""
    from ipfs_kit_py.graphrag import GraphRAGSearchEngine
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
        
        # Index same CID multiple times (simulating updates)
        cid = "QmTest123"
        await engine.index_content(cid, "/test/file.txt", "Version 1 content")
        await engine.index_content(cid, "/test/file.txt", "Version 2 content")
        await engine.index_content(cid, "/test/file.txt", "Version 3 content")
        
        # Verify content was indexed
        with sqlite3.connect(engine.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM content_versions WHERE cid = ?", (cid,))
            count = cursor.fetchone()[0]
            assert count >= 1  # At least one version tracked


# ============================================================================
# Analytics Dashboard Deep Coverage Tests
# ============================================================================

def test_analytics_bandwidth_calculations():
    """Test bandwidth metrics."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector(window_size=100)
    
    # Record some bandwidth events
    import time
    now = time.time()
    
    for i in range(10):
        collector.bandwidth.append({
            "timestamp": now + i,
            "bytes": 1000 * (i + 1)
        })
    
    # Get bandwidth metrics
    metrics = collector.get_metrics()
    assert "total_bytes" in metrics


def test_analytics_top_peers():
    """Test top peers analysis."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record operations from different peers
    collector.record_operation("get", 0.1, 1000, peer_id="peer1")
    collector.record_operation("get", 0.2, 2000, peer_id="peer2")
    collector.record_operation("add", 0.3, 3000, peer_id="peer1")
    collector.record_operation("add", 0.4, 500, peer_id="peer3")
    
    # Get top peers
    top_peers = collector._get_top_peers(limit=2)
    assert len(top_peers) <= 2


def test_analytics_error_rate_tracking():
    """Test error rate calculation."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record mix of successful and failed operations
    for i in range(7):
        collector.record_operation("get", 0.1, success=True)
    
    for i in range(3):
        collector.record_operation("get", 0.1, success=False)
    
    # Get metrics which includes error rate
    metrics = collector.get_metrics()
    assert "total_errors" in metrics
    assert metrics["total_errors"] == 3


def test_analytics_metrics_aggregation():
    """Test metrics aggregation."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record various operations
    for i in range(20):
        op_type = "get" if i % 2 == 0 else "add"
        collector.record_operation(op_type, 0.1 + (i * 0.01), 1000)
    
    # Get aggregated metrics
    metrics = collector.get_metrics()
    
    assert metrics["total_operations"] == 20
    assert metrics["operation_counts"]["get"] == 10
    assert metrics["operation_counts"]["add"] == 10


def test_analytics_latency_percentiles():
    """Test latency percentile calculations."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    
    collector = AnalyticsCollector()
    
    # Record operations with varying latencies
    latencies = [0.01, 0.02, 0.03, 0.05, 0.08, 0.13, 0.21, 0.34, 0.55, 0.89]
    for lat in latencies:
        collector.record_operation("get", lat, 1000)
    
    # Calculate percentiles using internal method
    p50 = collector._percentile(latencies, 50)
    p95 = collector._percentile(latencies, 95)
    p99 = collector._percentile(latencies, 99)
    
    assert p50 < p95 <= p99


def test_analytics_operation_recording():
    """Test operation recording."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsCollector
    import time
    
    collector = AnalyticsCollector()
    
    # Record operations over time
    base_time = time.time()
    for i in range(50):
        collector.record_operation("get", 0.1, 1000)
    
    # Get metrics
    metrics = collector.get_metrics()
    
    assert len(collector.operations) > 0
    assert metrics["total_operations"] == 50


def test_analytics_dashboard_data():
    """Test dashboard data structure."""
    from ipfs_kit_py.analytics_dashboard import AnalyticsDashboard
    
    mock_ipfs = Mock()
    dashboard = AnalyticsDashboard(ipfs_api=mock_ipfs)
    
    # Record some operations
    dashboard.collector.record_operation("get", 0.1, 1000)
    dashboard.collector.record_operation("add", 0.2, 2000)
    
    # Get dashboard data
    data = dashboard.get_dashboard_data()
    
    assert "metrics" in data
    assert "storage" in data
    assert "network" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
