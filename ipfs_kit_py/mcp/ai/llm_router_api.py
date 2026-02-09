#!/usr/bin/env python3
"""
LLM Router API for MCP Server

This module provides FastAPI endpoints for the LLM router,
enabling text generation across multiple LLM providers and
IPFS peer endpoints.

Part of the MCP Roadmap Phase 2: AI/ML Integration - LLM Support.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ipfs_kit_py.llm_router import (
    generate_text,
    get_llm_provider,
    register_llm_provider,
    LLMProvider,
    clear_llm_router_caches,
)
from ipfs_kit_py.router_deps import RouterDeps, get_default_router_deps

# Configure logging
logger = logging.getLogger("mcp_llm_router_api")


class TextGenerationRequest(BaseModel):
    """Request model for text generation."""
    
    prompt: str = Field(..., description="The input prompt for text generation")
    model_name: Optional[str] = Field(None, description="Specific model to use")
    provider: Optional[str] = Field(None, description="LLM provider to use")
    max_tokens: Optional[int] = Field(256, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature")
    timeout: Optional[float] = Field(120.0, description="Request timeout in seconds")


class TextGenerationResponse(BaseModel):
    """Response model for text generation."""
    
    text: str = Field(..., description="Generated text")
    provider: Optional[str] = Field(None, description="Provider used")
    model: Optional[str] = Field(None, description="Model used")
    cached: bool = Field(False, description="Whether result was cached")


class ProviderListResponse(BaseModel):
    """Response model for listing providers."""
    
    providers: List[str] = Field(..., description="Available LLM providers")
    default_provider: Optional[str] = Field(None, description="Default provider if configured")


def create_llm_router(
    deps: Optional[RouterDeps] = None,
    enable_caching: bool = True
) -> APIRouter:
    """
    Create the LLM router API.
    
    Args:
        deps: Router dependencies for shared state
        enable_caching: Whether to enable response caching
        
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    # Use provided deps or default
    router_deps = deps or get_default_router_deps()
    
    @router.get("/", response_model=Dict[str, Any])
    async def get_llm_router_info() -> Dict[str, Any]:
        """Get information about the LLM router."""
        return {
            "name": "LLM Router",
            "version": "1.0.0",
            "description": "Multi-provider LLM text generation with IPFS peer support",
            "features": [
                "Multiple LLM providers (OpenRouter, Copilot, Codex, Gemini, Claude)",
                "Local HuggingFace transformers fallback",
                "IPFS peer endpoint multiplexing",
                "Response caching for performance",
                "Configurable via environment variables"
            ],
            "endpoints": {
                "/generate": "Generate text from a prompt",
                "/providers": "List available providers",
                "/health": "Health check"
            }
        }
    
    @router.post("/generate", response_model=TextGenerationResponse)
    async def generate(request: TextGenerationRequest) -> TextGenerationResponse:
        """
        Generate text using the LLM router.
        
        The router will automatically select the best available provider
        or use the specified provider if requested.
        """
        try:
            # Generate text using the router
            result = generate_text(
                prompt=request.prompt,
                model_name=request.model_name,
                provider=request.provider,
                deps=router_deps,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                timeout=request.timeout,
            )
            
            return TextGenerationResponse(
                text=result,
                provider=request.provider or "auto",
                model=request.model_name,
                cached=False  # TODO: Track if result was cached
            )
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Text generation failed: {str(e)}"
            )
    
    @router.get("/providers", response_model=ProviderListResponse)
    async def list_providers() -> ProviderListResponse:
        """List available LLM providers."""
        # Try to detect available providers
        available_providers = []
        
        # Check for common providers
        provider_checks = [
            ("openrouter", "OPENROUTER_API_KEY"),
            ("codex_cli", "codex CLI"),
            ("copilot_cli", "GitHub Copilot CLI"),
            ("copilot_sdk", "copilot SDK"),
            ("gemini_cli", "Gemini CLI"),
            ("gemini_py", "Gemini Python wrapper"),
            ("claude_code", "Claude CLI"),
            ("claude_py", "Claude Python wrapper"),
            ("local_hf", "HuggingFace transformers"),
            ("ipfs_peer", "IPFS peer endpoints"),
        ]
        
        for provider_name, description in provider_checks:
            try:
                # Try to get provider - if it works, it's available
                provider = get_llm_provider(provider_name, deps=router_deps, use_cache=False)
                if provider is not None:
                    available_providers.append(provider_name)
            except Exception:
                # Provider not available
                pass
        
        import os
        default_provider = (
            os.getenv("IPFS_KIT_LLM_PROVIDER") or 
            os.getenv("IPFS_DATASETS_PY_LLM_PROVIDER") or 
            None
        )
        
        return ProviderListResponse(
            providers=available_providers,
            default_provider=default_provider
        )
    
    @router.get("/health", response_model=Dict[str, Any])
    async def health_check() -> Dict[str, Any]:
        """Check health of LLM router."""
        try:
            # Try to get a provider
            provider = get_llm_provider(deps=router_deps, use_cache=False)
            
            return {
                "status": "healthy",
                "message": "LLM router is operational",
                "provider_available": provider is not None
            }
        except Exception as e:
            logger.error(f"LLM router health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"LLM router error: {str(e)}",
                "provider_available": False
            }
    
    @router.post("/cache/clear", response_model=Dict[str, str])
    async def clear_cache() -> Dict[str, str]:
        """Clear the LLM router caches."""
        try:
            clear_llm_router_caches()
            return {
                "status": "success",
                "message": "LLM router caches cleared"
            }
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Cache clear failed: {str(e)}"
            )
    
    return router
