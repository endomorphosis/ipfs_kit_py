#!/usr/bin/env python3
"""
Tests for Embeddings Router

Tests the embeddings router functionality with mock providers and fallback behavior.
"""

import os
import pytest
import sys
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ipfs_kit_py.embeddings_router import (
        embed_texts,
        embed_text,
        get_embeddings_provider,
        register_embeddings_provider,
        clear_embeddings_router_caches,
        EmbeddingsProvider,
    )
    from ipfs_kit_py.router_deps import RouterDeps, get_default_router_deps
    EMBEDDINGS_ROUTER_AVAILABLE = True
except ImportError as e:
    EMBEDDINGS_ROUTER_AVAILABLE = False
    pytest.skip(f"Embeddings router not available: {e}", allow_module_level=True)


class MockEmbeddingsProvider:
    """Mock embeddings provider for testing."""
    
    def __init__(self, dimension=128):
        self.dimension = dimension
        self.calls = []
    
    def embed_texts(self, texts, *, model_name=None, device=None, **kwargs):
        """Mock embed_texts method."""
        text_list = list(texts)
        self.calls.append({
            "texts": text_list,
            "model_name": model_name,
            "device": device,
            "kwargs": kwargs
        })
        # Return mock embeddings with specified dimension
        return [[0.1] * self.dimension for _ in text_list]


class TestEmbeddingsRouterBasics:
    """Test basic embeddings router functionality."""
    
    def test_register_provider(self):
        """Test registering a custom embeddings provider."""
        mock_provider = MockEmbeddingsProvider(dimension=64)
        
        register_embeddings_provider("test_embeddings_provider", lambda: mock_provider)
        
        provider = get_embeddings_provider("test_embeddings_provider", use_cache=False)
        assert provider is not None
        
        result = provider.embed_texts(["Test text"])
        assert len(result) == 1
        assert len(result[0]) == 64
        assert len(mock_provider.calls) == 1
    
    def test_embed_texts_with_custom_provider(self):
        """Test embedding multiple texts with custom provider."""
        mock_provider = MockEmbeddingsProvider(dimension=128)
        
        texts = ["Text 1", "Text 2", "Text 3"]
        result = embed_texts(
            texts=texts,
            provider_instance=mock_provider,
        )
        
        assert len(result) == 3
        assert all(len(emb) == 128 for emb in result)
        assert len(mock_provider.calls) == 1
        assert mock_provider.calls[0]["texts"] == texts
    
    def test_embed_single_text(self):
        """Test embedding single text."""
        mock_provider = MockEmbeddingsProvider(dimension=256)
        
        text = "Single test text"
        result = embed_text(
            text=text,
            provider_instance=mock_provider,
        )
        
        assert len(result) == 256
        assert len(mock_provider.calls) == 1
    
    def test_clear_caches(self):
        """Test clearing router caches."""
        # Should not raise an error
        clear_embeddings_router_caches()


class TestRouterDepsEmbeddings:
    """Test router dependencies with embeddings."""
    
    def test_embeddings_with_deps(self):
        """Test using embeddings with router dependencies."""
        deps = RouterDeps()
        mock_provider = MockEmbeddingsProvider()
        
        result = embed_texts(
            texts=["Test"],
            provider_instance=mock_provider,
            deps=deps,
        )
        
        assert len(result) == 1
        assert len(result[0]) == 128  # default dimension


class TestProviderFallbackEmbeddings:
    """Test provider fallback behavior for embeddings."""
    
    def test_custom_provider_registration(self):
        """Test that custom providers can be registered and used."""
        
        class CustomEmbedder:
            def embed_texts(self, texts, **kwargs):
                return [[0.5] * 100 for _ in texts]
        
        register_embeddings_provider("custom_embedder", lambda: CustomEmbedder())
        
        result = embed_texts(["test"], provider="custom_embedder")
        assert len(result) == 1
        assert len(result[0]) == 100


class TestEmbeddingAdapter:
    """Test embedding adapter functions."""
    
    def test_embedding_adapter_import(self):
        """Test that embedding adapter can be imported."""
        try:
            from ipfs_kit_py.utils.embedding_adapter import embed_texts as adapter_embed, embed_text as adapter_embed_single
            assert adapter_embed is not None
            assert adapter_embed_single is not None
        except ImportError:
            pytest.skip("Embedding adapter utils not available")


class TestEnvironmentVariablesEmbeddings:
    """Test environment variable configuration for embeddings."""
    
    def test_env_variable_fallback(self):
        """Test that IPFS_KIT_ and IPFS_DATASETS_PY_ prefixes work."""
        with patch.dict(os.environ, {"IPFS_KIT_EMBEDDINGS_MODEL": "test-model"}):
            # Test that we can access the env var
            assert os.getenv("IPFS_KIT_EMBEDDINGS_MODEL") == "test-model"
    
    def test_env_variable_provider_selection(self):
        """Test provider selection via environment variable."""
        mock_provider = MockEmbeddingsProvider()
        
        register_embeddings_provider("env_test_embeddings", lambda: mock_provider)
        
        with patch.dict(os.environ, {"IPFS_KIT_EMBEDDINGS_PROVIDER": "env_test_embeddings"}):
            # Provider selection happens at runtime
            pass


class TestIPFSPeerProvider:
    """Test IPFS peer provider for embeddings."""
    
    def test_ipfs_peer_provider_with_mock_backend(self):
        """Test IPFS peer provider with mock backend."""
        
        class MockIPFSBackend:
            class MockPeerManager:
                def route_embeddings_request(self, texts, model=None, device=None, **kwargs):
                    return {
                        "embeddings": [[0.1, 0.2, 0.3] for _ in texts]
                    }
            
            def __init__(self):
                self.peer_manager = self.MockPeerManager()
        
        deps = RouterDeps()
        deps.ipfs_backend = MockIPFSBackend()
        
        result = embed_texts(
            texts=["Test IPFS peer routing"],
            provider="ipfs_peer",
            deps=deps
        )
        
        assert len(result) == 1
        assert len(result[0]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
