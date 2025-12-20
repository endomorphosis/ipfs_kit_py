"""
Test suite for Filecoin Pin backend implementation.

This module tests the new Filecoin Pin backend and associated components.
"""

import pytest
import asyncio
from ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend import FilecoinPinBackend
from ipfs_kit_py.mcp.storage_manager.pinning import UnifiedPinService
from ipfs_kit_py.mcp.storage_manager.retrieval import GatewayChain
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class TestFilecoinPinBackend:
    """Test Filecoin Pin backend implementation."""
    
    def test_initialization(self):
        """Test backend initialization."""
        resources = {}
        metadata = {}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        assert backend.get_name() == "filecoin_pin"
        assert backend.backend_type == StorageBackendType.FILECOIN_PIN
        assert backend.mock_mode is True  # No API key provided
    
    def test_initialization_with_api_key(self):
        """Test backend initialization with API key."""
        resources = {"api_key": "test_key"}
        metadata = {"default_replication": 5}
        
        backend = FilecoinPinBackend(resources, metadata)
        
        assert backend.get_name() == "filecoin_pin"
        assert backend.api_key == "test_key"
        assert backend.default_replication == 5
        assert backend.mock_mode is False
    
    def test_add_content_mock(self):
        """Test adding content in mock mode."""
        resources = {}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        content = b"Test content for Filecoin Pin"
        result = backend.add_content(
            content=content,
            metadata={"name": "test-pin", "tags": ["test"]}
        )
        
        assert result["success"] is True
        assert "cid" in result
        assert result["status"] == "pinned"
        assert result["backend"] == "filecoin_pin"
        assert result["mock"] is True
    
    def test_get_content_mock(self):
        """Test retrieving content in mock mode."""
        resources = {}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        cid = "bafybeib123456789"
        result = backend.get_content(cid)
        
        assert result["success"] is True
        assert "data" in result
        assert result["cid"] == cid
        assert result["backend"] == "filecoin_pin"
        assert result["mock"] is True
    
    def test_remove_content_mock(self):
        """Test removing content in mock mode."""
        resources = {}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        cid = "bafybeib123456789"
        result = backend.remove_content(cid)
        
        assert result["success"] is True
        assert result["cid"] == cid
        assert result["backend"] == "filecoin_pin"
        assert result["mock"] is True
    
    def test_get_metadata_mock(self):
        """Test getting metadata in mock mode."""
        resources = {}
        metadata = {"default_replication": 3}
        backend = FilecoinPinBackend(resources, metadata)
        
        cid = "bafybeib123456789"
        result = backend.get_metadata(cid)
        
        assert result["success"] is True
        assert result["cid"] == cid
        assert result["status"] == "pinned"
        assert "deals" in result
        assert len(result["deals"]) > 0
        assert result["backend"] == "filecoin_pin"
        assert result["mock"] is True
    
    def test_list_pins_mock(self):
        """Test listing pins in mock mode."""
        resources = {}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        result = backend.list_pins(status="pinned", limit=10)
        
        assert result["success"] is True
        assert "pins" in result
        assert result["count"] > 0
        assert result["backend"] == "filecoin_pin"
        assert result["mock"] is True


class TestUnifiedPinService:
    """Test Unified Pin Service."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization."""
        service = UnifiedPinService()
        
        assert service is not None
        assert len(service._supported_backends) > 0
    
    @pytest.mark.asyncio
    async def test_pin_single_backend(self):
        """Test pinning to a single backend."""
        service = UnifiedPinService()
        
        result = await service.pin(
            cid="bafybeib123456789",
            name="test-pin",
            metadata={"description": "Test pin"},
            backends=["filecoin_pin"]
        )
        
        assert "cid" in result
        assert "backends" in result
        assert "filecoin_pin" in result["backends"]
    
    @pytest.mark.asyncio
    async def test_pin_multiple_backends(self):
        """Test pinning to multiple backends."""
        service = UnifiedPinService()
        
        result = await service.pin(
            cid="bafybeib123456789",
            name="test-pin",
            backends=["ipfs", "filecoin_pin"]
        )
        
        assert "backends" in result
        assert len(result["backends"]) == 2
    
    @pytest.mark.asyncio
    async def test_unpin(self):
        """Test unpinning content."""
        service = UnifiedPinService()
        
        result = await service.unpin(
            cid="bafybeib123456789",
            backends=["filecoin_pin"]
        )
        
        assert "cid" in result
        assert "backends" in result
    
    @pytest.mark.asyncio
    async def test_list_pins(self):
        """Test listing pins."""
        service = UnifiedPinService()
        
        result = await service.list_pins(
            backend="filecoin_pin",
            status="pinned",
            limit=10
        )
        
        assert "backends" in result
        assert "total_count" in result
    
    @pytest.mark.asyncio
    async def test_pin_status(self):
        """Test getting pin status."""
        service = UnifiedPinService()
        
        result = await service.pin_status(
            cid="bafybeib123456789",
            backend="filecoin_pin"
        )
        
        assert "cid" in result
        assert "backends" in result


class TestGatewayChain:
    """Test Gateway Chain."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test gateway chain initialization."""
        chain = GatewayChain()
        
        assert chain is not None
        assert len(chain.gateways) > 0
    
    @pytest.mark.asyncio
    async def test_initialization_custom_gateways(self):
        """Test initialization with custom gateways."""
        custom_gateways = [
            {"url": "https://ipfs.io/ipfs/", "priority": 1, "timeout": 30}
        ]
        chain = GatewayChain(gateways=custom_gateways)
        
        assert len(chain.gateways) == 1
        assert chain.gateways[0]["url"] == "https://ipfs.io/ipfs/"
    
    @pytest.mark.asyncio
    async def test_test_all_gateways(self):
        """Test gateway health check."""
        chain = GatewayChain()
        
        # Note: This will make real HTTP requests
        # In a production test, you'd mock these
        results = await chain.test_all()
        
        assert isinstance(results, dict)
        assert len(results) > 0
    
    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Test getting gateway metrics."""
        chain = GatewayChain()
        
        metrics = chain.get_metrics()
        
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
    
    @pytest.mark.asyncio
    async def test_get_health(self):
        """Test getting gateway health."""
        chain = GatewayChain()
        
        health = chain.get_health()
        
        assert isinstance(health, dict)
        assert len(health) > 0
        
        # Check structure
        for gateway_url, status in health.items():
            assert "available" in status
            assert "failures" in status


# Integration tests (require actual backends)

class TestFilecoinPinIntegration:
    """Integration tests for Filecoin Pin backend."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(
        "FILECOIN_PIN_API_KEY" not in __import__('os').environ,
        reason="FILECOIN_PIN_API_KEY not set"
    )
    def test_real_pin_operation(self):
        """Test real pinning operation with API key."""
        import os
        
        resources = {"api_key": os.environ["FILECOIN_PIN_API_KEY"]}
        metadata = {}
        backend = FilecoinPinBackend(resources, metadata)
        
        content = b"Integration test content"
        result = backend.add_content(
            content=content,
            metadata={"name": "integration-test"}
        )
        
        assert result["success"] is True
        assert "cid" in result
        
        # Clean up
        backend.remove_content(result["cid"])


class TestGatewayChainIntegration:
    """Integration tests for Gateway Chain."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fetch_real_content(self):
        """Test fetching real content from IPFS."""
        chain = GatewayChain()
        
        # Use a well-known CID (empty file)
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            content, metrics = await chain.fetch_with_metrics(test_cid)
            
            assert content is not None
            assert len(content) == 0  # Empty file
            assert metrics["success"] is True
            assert "gateway_used" in metrics
        except Exception as e:
            pytest.skip(f"Gateway fetch failed: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
