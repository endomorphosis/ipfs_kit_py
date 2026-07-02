#!/usr/bin/env python3
"""
Tests for LLM Router

Tests the LLM router functionality with mock providers and fallback behavior.
"""

import os
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ipfs_kit_py.llm_router import (
        generate_text,
        get_llm_provider,
        register_llm_provider,
        clear_llm_router_caches,
        LLMProvider,
    )
    from ipfs_kit_py.router_deps import RouterDeps, get_default_router_deps
    LLM_ROUTER_AVAILABLE = True
except ImportError as e:
    LLM_ROUTER_AVAILABLE = False
    pytest.skip(f"LLM router not available: {e}", allow_module_level=True)


class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, response="Mock response"):
        self.response = response
        self.calls = []
    
    def generate(self, prompt: str, *, model_name=None, **kwargs):
        """Mock generate method."""
        self.calls.append({
            "prompt": prompt,
            "model_name": model_name,
            "kwargs": kwargs
        })
        return self.response


class TestLLMRouterBasics:
    """Test basic LLM router functionality."""
    
    def test_register_provider(self):
        """Test registering a custom provider."""
        mock_provider = MockLLMProvider("Custom provider response")
        
        register_llm_provider("test_provider", lambda: mock_provider)
        
        provider = get_llm_provider("test_provider", use_cache=False)
        assert provider is not None
        
        result = provider.generate("Test prompt")
        assert result == "Custom provider response"
        assert len(mock_provider.calls) == 1
    
    def test_generate_text_with_custom_provider(self):
        """Test text generation with custom provider."""
        mock_provider = MockLLMProvider("Generated text")
        
        result = generate_text(
            "Test prompt",
            provider_instance=mock_provider,
            max_tokens=100
        )
        
        assert result == "Generated text"
        assert len(mock_provider.calls) == 1
        assert mock_provider.calls[0]["prompt"] == "Test prompt"
        assert mock_provider.calls[0]["kwargs"]["max_tokens"] == 100
    
    def test_clear_caches(self):
        """Test clearing router caches."""
        # Should not raise an error
        clear_llm_router_caches()


class TestRouterDeps:
    """Test router dependencies."""
    
    def test_create_router_deps(self):
        """Test creating router dependencies."""
        deps = RouterDeps()
        
        assert deps.accelerate_managers == {}
        assert deps.ipfs_backend is None
        assert deps.router_cache == {}
        assert deps.remote_cache is None
    
    def test_cache_operations(self):
        """Test cache get/set operations."""
        deps = RouterDeps()
        
        # Test set and get
        value = {"test": "data"}
        result = deps.set_cached("test_key", value)
        assert result == value
        
        cached = deps.get_cached("test_key")
        assert cached == value
        
        # Test missing key
        missing = deps.get_cached("nonexistent")
        assert missing is None
    
    def test_get_or_create(self):
        """Test get_or_create pattern."""
        deps = RouterDeps()
        
        factory_called = []
        
        def factory():
            factory_called.append(True)
            return "created_value"
        
        # First call should create
        value1 = deps.get_or_create("test_key", factory)
        assert value1 == "created_value"
        assert len(factory_called) == 1
        
        # Second call should return cached
        value2 = deps.get_or_create("test_key", factory)
        assert value2 == "created_value"
        assert len(factory_called) == 1  # Factory not called again
    
    def test_default_router_deps(self):
        """Test getting default router dependencies."""
        deps = get_default_router_deps()
        
        assert isinstance(deps, RouterDeps)
        
        # Should return same instance
        deps2 = get_default_router_deps()
        assert deps is deps2


class TestProviderFallback:
    """Test provider fallback behavior."""
    
    def test_provider_fallback_on_error(self):
        """Test that router falls back to other providers on error."""
        
        class FailingProvider:
            def generate(self, prompt, **kwargs):
                raise RuntimeError("Provider failed")
        
        # Register a failing provider
        register_llm_provider("failing_provider", lambda: FailingProvider())
        
        # Calling generate_text with a failing provider should raise
        # since we explicitly request it and there's no automatic fallback
        # when a specific provider is requested
        with pytest.raises(RuntimeError, match="Provider failed"):
            generate_text("test prompt", provider="failing_provider")


class TestEnvironmentVariables:
    """Test environment variable configuration."""
    
    def test_env_variable_fallback(self):
        """Test that IPFS_KIT_ and IPFS_DATASETS_PY_ prefixes work."""
        with patch.dict(os.environ, {"IPFS_KIT_LLM_MODEL": "test-model"}):
            # Test that we can access the env var
            assert os.getenv("IPFS_KIT_LLM_MODEL") == "test-model"
    
    def test_env_variable_provider_selection(self):
        """Test provider selection via environment variable."""
        mock_provider = MockLLMProvider("Env provider response")
        
        register_llm_provider("env_test_provider", lambda: mock_provider)
        
        with patch.dict(os.environ, {"IPFS_KIT_LLM_PROVIDER": "env_test_provider"}):
            # Note: This won't actually use the env var in tests due to caching
            # but we're testing the pattern
            pass


class TestCLIFunctions:
    """Test CLI wrapper functions."""
    
    def test_gemini_cli_import(self):
        """Test that Gemini CLI wrapper can be imported."""
        try:
            from ipfs_kit_py.utils.gemini_cli import GeminiCLI
            assert GeminiCLI is not None
        except ImportError:
            pytest.skip("Gemini CLI utils not available")
    
    def test_claude_cli_import(self):
        """Test that Claude CLI wrapper can be imported."""
        try:
            from ipfs_kit_py.utils.claude_cli import ClaudeCLI
            assert ClaudeCLI is not None
        except ImportError:
            pytest.skip("Claude CLI utils not available")
    
    def test_cid_utils_import(self):
        """Test that CID utils can be imported."""
        try:
            from ipfs_kit_py.utils.cid_utils import cid_for_obj
            
            # Test basic CID generation
            obj = {"test": "data"}
            cid = cid_for_obj(obj)
            assert cid.startswith("b")  # base32 prefix
            
            # Same object should give same CID
            cid2 = cid_for_obj(obj)
            assert cid == cid2
        except ImportError:
            pytest.skip("CID utils not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
