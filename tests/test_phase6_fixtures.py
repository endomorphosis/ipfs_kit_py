"""
Test Fixtures and Utilities for Phase 6 Tests

Reusable fixtures, factories, and utilities to support comprehensive testing.
Provides common test data, mock objects, and helper functions.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, timedelta


# ============================================================================
# Mock IPFS Client Fixtures
# ============================================================================

@pytest.fixture
def mock_ipfs_client():
    """Create a mock IPFS client with common methods."""
    mock = Mock()
    
    # Async methods
    mock.cat = AsyncMock(return_value=b"test content")
    mock.add = AsyncMock(return_value={"Hash": "QmTestHash123"})
    mock.get = AsyncMock(return_value=b"test file content")
    
    # Pin operations
    mock.pin = Mock()
    mock.pin.add = AsyncMock(return_value={"Pins": ["QmTestHash123"]})
    mock.pin.rm = AsyncMock(return_value={"Pins": ["QmTestHash123"]})
    mock.pin.ls = AsyncMock(return_value={"Keys": {}})
    
    # Files operations (MFS)
    mock.files = Mock()
    mock.files.ls = AsyncMock(return_value={"Entries": []})
    mock.files.mkdir = AsyncMock(return_value=True)
    mock.files.stat = AsyncMock(return_value={"Type": "directory", "Size": 0})
    mock.files.read = AsyncMock(return_value=b"file content")
    mock.files.write = AsyncMock(return_value=True)
    mock.files.rm = AsyncMock(return_value=True)
    
    return mock


@pytest.fixture
def mock_ipfs_client_with_errors():
    """Create a mock IPFS client that simulates errors."""
    mock = Mock()
    
    mock.cat = AsyncMock(side_effect=Exception("Connection refused"))
    mock.add = AsyncMock(side_effect=Exception("IPFS daemon not running"))
    mock.get = AsyncMock(side_effect=Exception("Timeout"))
    
    mock.pin = Mock()
    mock.pin.add = AsyncMock(side_effect=Exception("Pin failed"))
    
    return mock


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_workspace_with_files(temp_workspace):
    """Create a temporary workspace with sample files."""
    # Create some test files
    (temp_workspace / "file1.txt").write_text("content 1")
    (temp_workspace / "file2.txt").write_text("content 2")
    (temp_workspace / "subdir").mkdir()
    (temp_workspace / "subdir" / "file3.txt").write_text("content 3")
    
    yield temp_workspace


# ============================================================================
# Mock Bucket Fixtures
# ============================================================================

@pytest.fixture
def mock_bucket():
    """Create a mock bucket object."""
    bucket = Mock()
    bucket.name = "test-bucket"
    bucket.bucket_type = "standard"
    bucket.created = datetime.utcnow().isoformat()
    bucket.settings = {"public": False, "versioning": False}
    return bucket


@pytest.fixture
def mock_bucket_with_files(mock_bucket):
    """Create a mock bucket with files."""
    mock_bucket.files = {
        "file1.txt": {"cid": "QmFile1", "size": 100, "modified": datetime.utcnow().isoformat()},
        "file2.txt": {"cid": "QmFile2", "size": 200, "modified": datetime.utcnow().isoformat()},
        "dir/file3.txt": {"cid": "QmFile3", "size": 150, "modified": datetime.utcnow().isoformat()},
    }
    return mock_bucket


# ============================================================================
# Sample Data Factories
# ============================================================================

class TestDataFactory:
    """Factory for generating test data."""
    
    @staticmethod
    def create_region(
        region_id: str = "test-region",
        name: str = "Test Region",
        location: str = "test-location",
        endpoints: Optional[List[str]] = None,
        status: str = "healthy",
        priority: int = 1,
        weight: int = 100
    ) -> Dict[str, Any]:
        """Create test region data."""
        if endpoints is None:
            endpoints = [f"http://{region_id}.example.com"]
        
        return {
            "region_id": region_id,
            "name": name,
            "location": location,
            "endpoints": endpoints,
            "status": status,
            "priority": priority,
            "weight": weight,
            "avg_latency": 50.0,
            "healthy_endpoints": len(endpoints)
        }
    
    @staticmethod
    def create_wasm_module_info(
        name: str = "test-module",
        cid: str = "QmTestModule",
        version: str = "1.0.0"
    ) -> Dict[str, Any]:
        """Create WASM module info."""
        return {
            "name": name,
            "cid": cid,
            "metadata": {
                "version": version,
                "author": "test@example.com",
                "license": "MIT",
                "functions": ["process", "encode", "decode"]
            },
            "registered_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_bucket_metadata(
        bucket_name: str = "test-bucket",
        num_files: int = 5
    ) -> Dict[str, Any]:
        """Create bucket metadata for export/import testing."""
        files = {
            f"file{i}.txt": {
                "cid": f"QmFile{i}",
                "size": i * 100,
                "modified": datetime.utcnow().isoformat()
            }
            for i in range(num_files)
        }
        
        return {
            "version": "1.0",
            "exported_at": datetime.utcnow().isoformat(),
            "bucket_info": {
                "name": bucket_name,
                "type": "standard",
                "created": (datetime.utcnow() - timedelta(days=30)).isoformat()
            },
            "files": files,
            "statistics": {
                "total_files": num_files,
                "total_size": sum(f["size"] for f in files.values())
            }
        }
    
    @staticmethod
    def create_graphrag_documents(num_docs: int = 5) -> List[Dict[str, Any]]:
        """Create sample documents for GraphRAG testing."""
        topics = ["Python", "JavaScript", "Rust", "Go", "TypeScript"]
        
        return [
            {
                "cid": f"QmDoc{i}",
                "path": f"/docs/doc{i}.md",
                "content": f"This is a document about {topics[i % len(topics)]} programming language."
            }
            for i in range(num_docs)
        ]


@pytest.fixture
def test_data_factory():
    """Provide test data factory."""
    return TestDataFactory()


# ============================================================================
# Analytics Test Data
# ============================================================================

@pytest.fixture
def sample_operations():
    """Create sample operations for analytics testing."""
    operations = []
    
    for i in range(100):
        operations.append({
            "operation_type": f"operation_{i % 10}",
            "duration": 0.1 * (i % 50),
            "success": (i % 10) != 0,
            "timestamp": datetime.utcnow().isoformat(),
            "peer_id": f"peer{i % 5}"
        })
    
    return operations


# ============================================================================
# Mock FastAPI Application Fixtures
# ============================================================================

@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI application."""
    try:
        from fastapi import FastAPI
        app = FastAPI(title="Test App")
        return app
    except ImportError:
        pytest.skip("FastAPI not available")


# ============================================================================
# Helper Functions
# ============================================================================

def create_mock_async_function(return_value=None, side_effect=None):
    """Create a mock async function."""
    mock = AsyncMock()
    if return_value is not None:
        mock.return_value = return_value
    if side_effect is not None:
        mock.side_effect = side_effect
    return mock


def assert_valid_cid(cid: str):
    """Assert that a string is a valid CID format."""
    assert cid.startswith("Qm") or cid.startswith("bafy"), f"Invalid CID format: {cid}"
    assert len(cid) > 10, f"CID too short: {cid}"


def assert_valid_timestamp(timestamp: str):
    """Assert that a string is a valid ISO timestamp."""
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pytest.fail(f"Invalid timestamp format: {timestamp}")


def create_test_content(size_kb: int = 1) -> bytes:
    """Create test content of specified size."""
    return b"x" * (size_kb * 1024)


# ============================================================================
# Parametrized Test Data
# ============================================================================

# Region configurations for parameterized tests
REGION_CONFIGS = [
    {"region_id": "us-east-1", "location": "us-east", "priority": 1},
    {"region_id": "us-west-1", "location": "us-west", "priority": 1},
    {"region_id": "eu-west-1", "location": "eu-west", "priority": 2},
    {"region_id": "ap-south-1", "location": "ap-south", "priority": 3},
]

# Routing strategies for parameterized tests
ROUTING_STRATEGIES = ["latency", "geographic", "cost", "round-robin", "weighted"]

# Search types for GraphRAG
SEARCH_TYPES = ["vector", "text", "graph", "hybrid"]

# File formats for testing
FILE_FORMATS = ["json", "cbor"]

# Error scenarios for testing
ERROR_SCENARIOS = [
    {"error": "ConnectionError", "message": "Connection refused"},
    {"error": "TimeoutError", "message": "Request timeout"},
    {"error": "PermissionError", "message": "Access denied"},
    {"error": "IOError", "message": "Disk full"},
]


# ============================================================================
# Performance Test Fixtures
# ============================================================================

@pytest.fixture
def performance_timer():
    """Provide a performance timer for testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Cleanup code here if needed


# ============================================================================
# Module-Specific Fixtures
# ============================================================================

@pytest.fixture
def mock_graphrag_engine():
    """Create a mock GraphRAG engine."""
    from unittest.mock import Mock
    
    engine = Mock()
    engine.index_content = AsyncMock(return_value=True)
    engine.search = AsyncMock(return_value=[])
    engine.add_relationship = Mock()
    engine.get_statistics = Mock(return_value={
        "indexed_items": 0,
        "relationships": 0
    })
    
    return engine


@pytest.fixture
def mock_analytics_collector():
    """Create a mock analytics collector."""
    collector = Mock()
    collector.record_operation = Mock()
    collector.get_metrics = Mock(return_value={
        "total_operations": 0,
        "avg_duration": 0.0
    })
    collector.get_latency_stats = Mock(return_value={
        "min": 0.0,
        "max": 0.0,
        "avg": 0.0,
        "p50": 0.0,
        "p95": 0.0,
        "p99": 0.0
    })
    
    return collector


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_metadata_valid(metadata: Dict[str, Any]):
    """Assert that metadata structure is valid."""
    assert "version" in metadata, "Metadata missing version"
    assert "bucket_info" in metadata, "Metadata missing bucket_info"
    assert isinstance(metadata["bucket_info"], dict), "bucket_info must be dict"


def assert_region_valid(region: Dict[str, Any]):
    """Assert that region data is valid."""
    required_fields = ["region_id", "name", "location", "endpoints"]
    for field in required_fields:
        assert field in region, f"Region missing required field: {field}"
    
    assert isinstance(region["endpoints"], list), "endpoints must be a list"
    assert len(region["endpoints"]) > 0, "Region must have at least one endpoint"


# Export commonly used items
__all__ = [
    # Fixtures
    "mock_ipfs_client",
    "mock_ipfs_client_with_errors",
    "temp_workspace",
    "temp_workspace_with_files",
    "mock_bucket",
    "mock_bucket_with_files",
    "test_data_factory",
    "sample_operations",
    "mock_fastapi_app",
    "performance_timer",
    "mock_graphrag_engine",
    "mock_analytics_collector",
    
    # Helper functions
    "create_mock_async_function",
    "assert_valid_cid",
    "assert_valid_timestamp",
    "create_test_content",
    "assert_metadata_valid",
    "assert_region_valid",
    
    # Test data
    "REGION_CONFIGS",
    "ROUTING_STRATEGIES",
    "SEARCH_TYPES",
    "FILE_FORMATS",
    "ERROR_SCENARIOS",
    
    # Factories
    "TestDataFactory",
]
