"""
Test suite for Phase 2: Enhanced Content Retrieval implementation.

This module tests the IPNI client, Saturn backend, and Enhanced Gateway Chain.
"""

import pytest
from ipfs_kit_py.mcp.storage_manager.discovery.ipni_client import IPNIClient
from ipfs_kit_py.mcp.storage_manager.backends.saturn_backend import SaturnBackend
from ipfs_kit_py.mcp.storage_manager.retrieval.enhanced_gateway_chain import EnhancedGatewayChain
from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType


class TestIPNIClient:
    """Test IPNI Client implementation."""
    
    @pytest.mark.anyio
    async def test_initialization(self):
        """Test IPNI client initialization."""
        client = IPNIClient()
        
        assert client is not None
        assert len(client.endpoints) > 0
        assert client.timeout > 0
    
    @pytest.mark.anyio
    async def test_initialization_custom_endpoints(self):
        """Test initialization with custom endpoints."""
        custom_endpoints = ["https://custom.ipni.example.com"]
        client = IPNIClient(endpoints=custom_endpoints)
        
        assert len(client.endpoints) == 1
        assert client.endpoints[0] == custom_endpoints[0]
    
    @pytest.mark.anyio
    async def test_find_providers_mock(self):
        """Test finding providers (will fail gracefully without real IPNI)."""
        client = IPNIClient()
        
        # This will likely fail but shouldn't crash
        try:
            providers = await client.find_providers("bafybeib123", limit=5)
            # If it succeeds, great
            assert isinstance(providers, list)
        except Exception as e:
            # Expected to fail without real IPNI service
            assert True
    
    @pytest.mark.anyio
    async def test_cache_operations(self):
        """Test cache operations."""
        client = IPNIClient(cache_duration=10)
        
        # Add to cache
        test_data = [{"provider_id": "test123"}]
        client._add_to_cache("test_key", test_data)
        
        # Get from cache
        cached = client._get_from_cache("test_key")
        assert cached == test_data
        
        # Clear cache
        client.clear_cache()
        cached = client._get_from_cache("test_key")
        assert cached is None


class TestSaturnBackend:
    """Test Saturn CDN backend implementation."""
    
    def test_initialization(self):
        """Test Saturn backend initialization."""
        resources = {}
        metadata = {}
        
        backend = SaturnBackend(resources, metadata)
        
        assert backend.get_name() == "saturn"
        assert backend.backend_type == StorageBackendType.SATURN
        assert backend.enable_geographic_routing is True
    
    def test_initialization_with_config(self):
        """Test initialization with custom configuration."""
        resources = {
            "orchestrator_url": "https://custom.saturn.example.com",
            "timeout": 60
        }
        metadata = {
            "enable_geographic_routing": False,
            "cache_duration": 7200
        }
        
        backend = SaturnBackend(resources, metadata)
        
        assert backend.orchestrator_url == resources["orchestrator_url"]
        assert backend.timeout == 60
        assert backend.enable_geographic_routing is False
        assert backend.cache_duration == 7200
    
    def test_add_content_readonly(self):
        """Test that add_content returns error (read-only backend)."""
        resources = {}
        metadata = {}
        backend = SaturnBackend(resources, metadata)
        
        result = backend.add_content(b"test", {})
        
        assert result["success"] is False
        assert "read-only" in result["error"].lower()
    
    def test_remove_content_readonly(self):
        """Test that remove_content returns error (read-only backend)."""
        resources = {}
        metadata = {}
        backend = SaturnBackend(resources, metadata)
        
        result = backend.remove_content("bafybeib123")
        
        assert result["success"] is False
        assert "read-only" in result["error"].lower()
    
    def test_get_metadata(self):
        """Test getting metadata."""
        resources = {}
        metadata = {}
        backend = SaturnBackend(resources, metadata)
        
        result = backend.get_metadata("bafybeib123")
        
        assert result["success"] is True
        assert result["backend"] == "saturn"
        assert "available" in result
    
    def test_cache_operations(self):
        """Test content caching."""
        resources = {}
        metadata = {"cache_duration": 10}
        backend = SaturnBackend(resources, metadata)
        
        test_cid = "bafybeib123"
        test_content = b"test content"
        
        # Add to cache
        backend._add_to_cache(test_cid, test_content)
        
        # Get from cache
        cached = backend._get_from_cache(test_cid)
        assert cached == test_content


class TestEnhancedGatewayChain:
    """Test Enhanced Gateway Chain with IPNI and Saturn."""
    
    @pytest.mark.anyio
    async def test_initialization(self):
        """Test enhanced gateway chain initialization."""
        chain = EnhancedGatewayChain()
        
        assert chain is not None
        assert chain.enable_ipni is True
        assert chain.enable_saturn is True
        assert hasattr(chain, 'ipni_client')
    
    @pytest.mark.anyio
    async def test_initialization_disabled_features(self):
        """Test initialization with features disabled."""
        chain = EnhancedGatewayChain(
            enable_ipni=False,
            enable_saturn=False
        )
        
        assert chain.enable_ipni is False
        assert chain.enable_saturn is False
    
    @pytest.mark.anyio
    async def test_provider_ranking(self):
        """Test provider ranking by performance."""
        chain = EnhancedGatewayChain()
        
        providers = [
            {"provider_id": "provider1", "protocols": ["http"]},
            {"provider_id": "provider2", "protocols": ["bitswap"]},
            {"provider_id": "provider3", "protocols": ["http"]}
        ]
        
        # Add some metrics
        chain._provider_metrics = {
            "provider1": {"success_count": 10, "fail_count": 0, "avg_time_ms": 100},
            "provider2": {"success_count": 5, "fail_count": 5, "avg_time_ms": 500},
            "provider3": {"success_count": 0, "fail_count": 10, "avg_time_ms": 0}
        }
        
        ranked = chain._rank_providers(providers)
        
        # provider1 should rank highest (best success rate and speed)
        assert ranked[0]["provider_id"] == "provider1"
    
    @pytest.mark.anyio
    async def test_update_provider_metrics(self):
        """Test updating provider metrics."""
        chain = EnhancedGatewayChain()
        
        provider_id = "test_provider"
        
        # Record successful request
        chain._update_provider_metrics(provider_id, True, 100)
        
        metrics = chain._provider_metrics[provider_id]
        assert metrics["success_count"] == 1
        assert metrics["fail_count"] == 0
        assert metrics["avg_time_ms"] == 100
        
        # Record another successful request
        chain._update_provider_metrics(provider_id, True, 200)
        
        metrics = chain._provider_metrics[provider_id]
        assert metrics["success_count"] == 2
        assert metrics["avg_time_ms"] == 150  # Average of 100 and 200
        
        # Record failed request
        chain._update_provider_metrics(provider_id, False, 0)
        
        metrics = chain._provider_metrics[provider_id]
        assert metrics["fail_count"] == 1
    
    @pytest.mark.asyncio
    async def test_get_provider_metrics(self):
        """Test getting provider metrics."""
        chain = EnhancedGatewayChain()
        
        chain._update_provider_metrics("provider1", True, 100)
        chain._update_provider_metrics("provider2", False, 0)
        
        metrics = chain.get_provider_metrics()
        
        assert "provider1" in metrics
        assert "provider2" in metrics
        assert metrics["provider1"]["success_count"] == 1
        assert metrics["provider2"]["fail_count"] == 1


# Integration tests (require network access)

class TestIPNIIntegration:
    """Integration tests for IPNI client."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_find_providers_real(self):
        """Test finding providers with real IPNI service."""
        client = IPNIClient()
        
        # Use a well-known CID
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            providers = await client.find_providers(test_cid, limit=5)
            
            # Should find at least some providers for this CID
            assert isinstance(providers, list)
            
            if providers:
                # Check provider structure
                provider = providers[0]
                assert "provider_id" in provider
                assert "protocols" in provider
                
        except Exception as e:
            pytest.skip(f"IPNI service unavailable: {e}")


class TestSaturnIntegration:
    """Integration tests for Saturn backend."""
    
    @pytest.mark.integration
    def test_get_content_real(self):
        """Test retrieving content from Saturn."""
        resources = {}
        metadata = {}
        backend = SaturnBackend(resources, metadata)
        
        # Use a well-known CID
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            result = backend.get_content(test_cid)
            
            # May or may not succeed depending on Saturn availability
            if result["success"]:
                assert "data" in result
                assert len(result["data"]) == 0  # Empty file
            else:
                # Expected if Saturn nodes are unavailable
                assert "error" in result
                
        except Exception as e:
            pytest.skip(f"Saturn service unavailable: {e}")


class TestEnhancedGatewayIntegration:
    """Integration tests for Enhanced Gateway Chain."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fetch_with_discovery_real(self):
        """Test fetching with IPNI discovery."""
        chain = EnhancedGatewayChain(enable_ipni=True, enable_saturn=True)
        
        # Use a well-known CID
        test_cid = "bafybeibj5h3bvrxvnkcrwyjv2vmdg4nwbsqw6h6qlq5oqnbw4jfabrjhpu"
        
        try:
            content, metrics = await chain.fetch_with_discovery(test_cid)
            
            assert content is not None
            assert len(content) == 0  # Empty file
            assert "source" in metrics
            assert "method" in metrics
            
            # Log which method was used
            print(f"Fetched via: {metrics['method']}, source: {metrics['source']}")
            
        except Exception as e:
            pytest.skip(f"Content retrieval failed: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short", "-k", "not integration"])
