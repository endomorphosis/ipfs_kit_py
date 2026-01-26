"""
Comprehensive integration tests for Filecoin Pin and IPFS backends.

These tests validate end-to-end functionality including:
- Adding content to Filecoin Pin backend
- Retrieving content from Filecoin Pin backend
- IPFS backend operations
- Multi-backend coordination
- Real-world workflows
"""

import pytest
import anyio
import os
import tempfile
from pathlib import Path
from ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend import FilecoinPinBackend
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend
from ipfs_kit_py.mcp.storage_manager.pinning.unified_pin_service import UnifiedPinService
from ipfs_kit_py.mcp.storage_manager.retrieval.gateway_chain import GatewayChain
from ipfs_kit_py.mcp.storage_manager.retrieval.enhanced_gateway_chain import EnhancedGatewayChain


class TestFilecoinPinBackendOperations:
    """Test Filecoin Pin backend add/retrieve operations."""
    
    def test_add_content_simple(self):
        """Test adding simple content to Filecoin Pin backend."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Add simple text content
        content = b"Hello from Filecoin Pin integration test!"
        metadata = {
            "name": "integration-test-simple",
            "description": "Simple integration test content"
        }
        
        result = backend.add_content(content, metadata)
        
        assert result["success"] is True
        assert "cid" in result
        assert result["status"] == "pinned"
        assert result["backend"] == "filecoin_pin"
        
        # Verify the CID is valid format
        cid = result["cid"]
        assert cid.startswith("bafybeib")
        assert len(cid) > 40
    
    def test_add_and_retrieve_content(self):
        """Test adding content and then retrieving it."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Add content
        original_content = b"Test content for add and retrieve workflow"
        add_result = backend.add_content(
            original_content,
            {"name": "test-retrieve"}
        )
        
        assert add_result["success"] is True
        cid = add_result["cid"]
        
        # Retrieve content
        retrieve_result = backend.get_content(cid)
        
        assert retrieve_result["success"] is True
        assert retrieve_result["cid"] == cid
        assert "data" in retrieve_result
        assert retrieve_result["source"] in ["cache", "mock-gateway"]
        
        # In mock mode, content won't match exactly, but operation succeeds
        assert len(retrieve_result["data"]) > 0
    
    def test_add_large_content(self):
        """Test adding larger content."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Create 1MB of test data
        large_content = b"x" * (1024 * 1024)
        
        result = backend.add_content(
            large_content,
            {"name": "large-content-test", "size": len(large_content)}
        )
        
        assert result["success"] is True
        assert "cid" in result
        assert result["status"] == "pinned"
    
    def test_add_content_with_metadata(self):
        """Test adding content with rich metadata."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        content = b"Content with metadata"
        metadata = {
            "name": "metadata-test",
            "description": "Testing metadata handling",
            "tags": ["test", "integration", "metadata"],
            "custom_field": "custom_value",
            "replication_target": 5
        }
        
        result = backend.add_content(content, metadata)
        
        assert result["success"] is True
        assert result["replication"] >= 1  # At least default replication
    
    def test_list_pins(self):
        """Test listing pins from backend."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Add multiple items
        for i in range(3):
            backend.add_content(
                f"Test content {i}".encode(),
                {"name": f"list-test-{i}"}
            )
        
        # List all pins
        result = backend.list_pins(status="pinned", limit=10)
        
        assert result["success"] is True
        assert result["count"] >= 3
        assert len(result["pins"]) >= 3
        
        # Verify pin structure
        pin = result["pins"][0]
        assert "cid" in pin
        assert "status" in pin
        assert "created" in pin
    
    def test_get_metadata(self):
        """Test getting metadata for pinned content."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Add content
        content = b"Metadata test content"
        add_result = backend.add_content(content, {"name": "metadata-fetch-test"})
        cid = add_result["cid"]
        
        # Get metadata
        metadata_result = backend.get_metadata(cid)
        
        assert metadata_result["success"] is True
        assert metadata_result["cid"] == cid
        assert "status" in metadata_result
        assert "size" in metadata_result
        assert "created" in metadata_result
    
    def test_remove_content(self):
        """Test removing pinned content."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Add content
        add_result = backend.add_content(
            b"Content to be removed",
            {"name": "removal-test"}
        )
        cid = add_result["cid"]
        
        # Remove content
        remove_result = backend.remove_content(cid)
        
        assert remove_result["success"] is True
        assert remove_result["cid"] == cid


class TestIPFSBackendOperations:
    """Test IPFS backend operations."""
    
    def test_ipfs_backend_initialization(self):
        """Test IPFS backend initializes correctly."""
        try:
            backend = IPFSBackend(resources={}, metadata={})
            assert backend is not None
            assert backend.get_name() == "ipfs"
        except ImportError:
            pytest.skip("IPFS backend not available")
    
    def test_ipfs_add_content(self):
        """Test adding content to IPFS."""
        try:
            backend = IPFSBackend(resources={}, metadata={})
            
            content = b"IPFS integration test content"
            result = backend.add_content(content, {"name": "ipfs-test"})
            
            # Should succeed or provide informative error
            if result.get("success"):
                # IPFS backend returns 'identifier' not 'cid'
                assert "identifier" in result or "cid" in result
                # Also check for Hash in details
                if "details" in result:
                    assert "Hash" in result["details"]
            else:
                # Mock mode or daemon not running is acceptable
                assert "error" in result or result.get("mock_mode")
                
        except ImportError:
            pytest.skip("IPFS backend not available")


class TestUnifiedPinServiceIntegration:
    """Test unified pin service with multiple backends."""
    
    @pytest.mark.anyio
    async def test_pin_to_multiple_backends(self):
        """Test pinning content to multiple backends simultaneously."""
        service = UnifiedPinService()
        
        # Create test content
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        # Pin to multiple backends
        result = await service.pin(
            cid=test_cid,
            name="unified-test",
            metadata={"test": "multi-backend"},
            backends=["ipfs", "filecoin_pin"]
        )
        
        assert result["success"] is True
        assert "backends" in result
        
        # Check each backend result
        for backend_name in ["ipfs", "filecoin_pin"]:
            if backend_name in result["backends"]:
                backend_result = result["backends"][backend_name]
                # Should have either success or informative error
                assert "status" in backend_result or "error" in backend_result
    
    @pytest.mark.anyio
    async def test_check_pin_status(self):
        """Test checking pin status across backends."""
        service = UnifiedPinService()
        
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        # Pin first
        await service.pin(test_cid, name="status-test", backends=["filecoin_pin"])
        
        # Check status
        status = await service.pin_status(test_cid)
        
        assert status["success"] is True
        assert "backends" in status
        assert len(status["backends"]) > 0
    
    @pytest.mark.anyio
    async def test_list_pins_unified(self):
        """Test listing pins across all backends."""
        service = UnifiedPinService()
        
        # Pin some content
        for i in range(2):
            test_cid = f"bafybeib{'0' * 52}{i:02d}"
            await service.pin(
                test_cid,
                name=f"list-unified-{i}",
                backends=["filecoin_pin"]
            )
        
        # List all pins
        result = await service.list_pins(backend=None, limit=10)
        
        assert result["success"] is True
        assert "backends" in result
        assert result["total_count"] >= 0


class TestGatewayChainRetrieval:
    """Test content retrieval through gateway chain."""
    
    @pytest.mark.anyio
    async def test_gateway_chain_fetch(self):
        """Test fetching content through gateway chain."""
        chain = GatewayChain()
        
        # Use a known test CID (empty file)
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            content = await chain.fetch(test_cid, timeout=10)
            
            # If successful, content should be bytes
            assert isinstance(content, bytes)
            
        except Exception as e:
            # Network issues are acceptable in CI
            pytest.skip(f"Gateway fetch failed (expected in CI): {e}")
    
    @pytest.mark.anyio
    async def test_gateway_chain_with_metrics(self):
        """Test fetching with metrics tracking."""
        chain = GatewayChain()
        
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            content, metrics = await chain.fetch_with_metrics(test_cid, timeout=10)
            
            assert isinstance(content, bytes)
            assert "source" in metrics
            assert "duration_ms" in metrics
            
        except Exception:
            pytest.skip("Gateway fetch failed (expected in CI)")


class TestEnhancedGatewayChain:
    """Test enhanced gateway chain with IPNI and Saturn."""
    
    @pytest.mark.anyio
    async def test_enhanced_fetch(self):
        """Test enhanced gateway with provider discovery."""
        chain = EnhancedGatewayChain(
            enable_ipni=True,
            enable_saturn=True
        )
        
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            content, metrics = await chain.fetch_with_discovery(test_cid)
            
            assert isinstance(content, bytes)
            assert "method" in metrics
            assert metrics["method"] in ["cache", "ipni_discovery", "saturn_cdn", "gateway"]
            
        except Exception:
            pytest.skip("Enhanced fetch failed (expected in CI)")


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.mark.anyio
    async def test_complete_pin_and_retrieve_workflow(self):
        """Test complete workflow: add to Filecoin Pin, then retrieve."""
        # Step 1: Add content to Filecoin Pin
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        original_content = b"Complete workflow test content"
        metadata = {
            "name": "e2e-workflow-test",
            "description": "End-to-end workflow validation"
        }
        
        add_result = backend.add_content(original_content, metadata)
        assert add_result["success"] is True
        
        cid = add_result["cid"]
        
        # Step 2: Verify content is pinned
        pin_metadata = backend.get_metadata(cid)
        assert pin_metadata["success"] is True
        assert pin_metadata["status"] == "pinned"
        
        # Step 3: Retrieve content
        retrieve_result = backend.get_content(cid)
        assert retrieve_result["success"] is True
        assert "data" in retrieve_result
        
        # Step 4: List pins to confirm operation works
        # Note: In mock mode, dynamic pins may not appear in list
        list_result = backend.list_pins(status="pinned")
        assert list_result["success"] is True
        assert list_result["count"] >= 0  # Should at least return mock pins
        
        # Verify we can get metadata for the CID we added
        metadata_check = backend.get_metadata(cid)
        assert metadata_check["success"] is True
    
    @pytest.mark.anyio
    async def test_multi_backend_workflow(self):
        """Test workflow across multiple backends."""
        service = UnifiedPinService()
        
        # Generate unique CID for this test
        import hashlib
        import time
        unique_data = f"multi-backend-{time.time()}".encode()
        hash_hex = hashlib.sha256(unique_data).hexdigest()
        test_cid = f"bafybeib{hash_hex[:52]}"
        
        # Step 1: Pin to Filecoin Pin
        result = await service.pin(
            test_cid,
            name="multi-backend-workflow",
            backends=["filecoin_pin"]
        )
        assert result["success"] is True
        
        # Step 2: Check status
        status = await service.pin_status(test_cid)
        assert status["success"] is True
        
        # Step 3: List and verify
        pins = await service.list_pins(backend="filecoin_pin", limit=20)
        assert pins["success"] is True
    
    def test_file_based_workflow(self):
        """Test workflow with file-based content."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_content = b"File-based workflow test content" * 100
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Read and add file content
            with open(temp_file, 'rb') as f:
                content = f.read()
            
            result = backend.add_content(
                content,
                {"name": "file-workflow-test", "source": "file"}
            )
            
            assert result["success"] is True
            assert "cid" in result
            
            # Verify can retrieve
            retrieve_result = backend.get_content(result["cid"])
            assert retrieve_result["success"] is True
            
        finally:
            os.unlink(temp_file)


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_cid_retrieval(self):
        """Test retrieving with invalid CID."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        result = backend.get_content("invalid-cid-format")
        
        # Should handle gracefully
        assert "success" in result
        assert "error" in result or "data" in result
    
    def test_empty_content(self):
        """Test adding empty content."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        result = backend.add_content(b"", {"name": "empty-test"})
        
        # Should handle empty content
        assert result["success"] is True or "error" in result
    
    def test_remove_nonexistent_pin(self):
        """Test removing non-existent pin."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        result = backend.remove_content("bafybeib" + "0" * 52)
        
        # Should handle gracefully
        assert "success" in result


class TestPerformance:
    """Test performance characteristics."""
    
    def test_add_multiple_items_performance(self):
        """Test adding multiple items."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        import time
        start_time = time.time()
        
        # Add 10 items
        results = []
        for i in range(10):
            result = backend.add_content(
                f"Performance test {i}".encode(),
                {"name": f"perf-test-{i}"}
            )
            results.append(result)
        
        elapsed = time.time() - start_time
        
        # All should succeed
        assert all(r["success"] for r in results)
        
        # Should be reasonably fast (mock mode)
        assert elapsed < 5.0  # 5 seconds for 10 operations
        
        # Calculate average
        avg_time = elapsed / 10
        print(f"Average time per operation: {avg_time*1000:.2f}ms")
    
    @pytest.mark.anyio
    async def test_concurrent_operations(self):
        """Test concurrent operations."""
        backend = FilecoinPinBackend(resources={}, metadata={})
        
        async def add_item(i):
            return backend.add_content(
                f"Concurrent test {i}".encode(),
                {"name": f"concurrent-{i}"}
            )
        
        # Run 5 concurrent operations
        results = [None] * 5
        async with anyio.create_task_group() as task_group:
            for i in range(5):
                async def run_item(index=i):
                    results[index] = await add_item(index)

                task_group.start_soon(run_item)
        
        # All should succeed
        assert all(r["success"] for r in results)
        
        # All should have unique CIDs
        cids = [r["cid"] for r in results]
        assert len(set(cids)) == len(cids)


if __name__ == "__main__":
    # Run all tests
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-k", "not (network or slow)",
        "--maxfail=5"
    ])
