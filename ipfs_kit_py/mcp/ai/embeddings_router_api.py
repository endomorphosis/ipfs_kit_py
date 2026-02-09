#!/usr/bin/env python3
"""
Embeddings Router API for MCP Server

This module provides FastAPI endpoints for the embeddings router,
enabling embedding generation across multiple providers and
IPFS peer endpoints.

Part of the MCP Roadmap Phase 2: AI/ML Integration - Embeddings Support.
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ipfs_kit_py.embeddings_router import (
    embed_texts,
    embed_text,
    get_embeddings_provider,
    register_embeddings_provider,
    EmbeddingsProvider,
    clear_embeddings_router_caches,
)
from ipfs_kit_py.router_deps import RouterDeps, get_default_router_deps

# Configure logging
logger = logging.getLogger("mcp_embeddings_router_api")


class EmbeddingRequest(BaseModel):
    """Request model for embedding generation."""
    
    texts: List[str] = Field(..., description="List of texts to embed", min_items=1)
    model_name: Optional[str] = Field(None, description="Specific model to use")
    device: Optional[str] = Field(None, description="Device to use (cpu/cuda)")
    provider: Optional[str] = Field(None, description="Embeddings provider to use")
    timeout: Optional[float] = Field(120.0, description="Request timeout in seconds")


class SingleEmbeddingRequest(BaseModel):
    """Request model for single text embedding."""
    
    text: str = Field(..., description="Text to embed")
    model_name: Optional[str] = Field(None, description="Specific model to use")
    device: Optional[str] = Field(None, description="Device to use (cpu/cuda)")
    provider: Optional[str] = Field(None, description="Embeddings provider to use")
    timeout: Optional[float] = Field(120.0, description="Request timeout in seconds")


class EmbeddingResponse(BaseModel):
    """Response model for embeddings."""
    
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    provider: Optional[str] = Field(None, description="Provider used")
    model: Optional[str] = Field(None, description="Model used")
    device: Optional[str] = Field(None, description="Device used")
    cached: bool = Field(False, description="Whether results were cached")


class SingleEmbeddingResponse(BaseModel):
    """Response model for single embedding."""
    
    embedding: List[float] = Field(..., description="Generated embedding")
    provider: Optional[str] = Field(None, description="Provider used")
    model: Optional[str] = Field(None, description="Model used")
    device: Optional[str] = Field(None, description="Device used")
    cached: bool = Field(False, description="Whether result was cached")


class ProviderListResponse(BaseModel):
    """Response model for listing providers."""
    
    providers: List[str] = Field(..., description="Available embeddings providers")
    default_provider: Optional[str] = Field(None, description="Default provider if configured")


def create_embeddings_router(
    deps: Optional[RouterDeps] = None,
    enable_caching: bool = True
) -> APIRouter:
    """
    Create the embeddings router API.
    
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
    async def get_embeddings_router_info() -> Dict[str, Any]:
        """Get information about the embeddings router."""
        return {
            "name": "Embeddings Router",
            "version": "1.0.0",
            "description": "Multi-provider embeddings generation with IPFS peer support",
            "features": [
                "Multiple embeddings providers (OpenRouter, Gemini CLI, HuggingFace)",
                "Local HuggingFace transformers fallback",
                "Gemini CLI integration",
                "IPFS peer endpoint multiplexing",
                "Response caching for performance",
                "Configurable via environment variables"
            ],
            "endpoints": {
                "/embed": "Generate embeddings for texts",
                "/embed-single": "Generate embedding for single text",
                "/providers": "List available providers",
                "/health": "Health check"
            }
        }
    
    @router.post("/embed", response_model=EmbeddingResponse)
    async def generate_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Generate embeddings for multiple texts.
        
        The router will automatically select the best available provider
        or use the specified provider if requested.
        """
        try:
            # Generate embeddings using the router
            result = embed_texts(
                texts=request.texts,
                model_name=request.model_name,
                device=request.device,
                provider=request.provider,
                deps=router_deps,
                timeout=request.timeout,
            )
            
            return EmbeddingResponse(
                embeddings=result,
                provider=request.provider or "auto",
                model=request.model_name,
                device=request.device,
                cached=False  # TODO: Track if results were cached
            )
        except Exception as e:
            logger.error(f"Embeddings generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Embeddings generation failed: {str(e)}"
            )
    
    @router.post("/embed-single", response_model=SingleEmbeddingResponse)
    async def generate_single_embedding(request: SingleEmbeddingRequest) -> SingleEmbeddingResponse:
        """Generate embedding for a single text."""
        try:
            # Generate embedding using the router
            result = embed_text(
                text=request.text,
                model_name=request.model_name,
                device=request.device,
                provider=request.provider,
                deps=router_deps,
                timeout=request.timeout,
            )
            
            return SingleEmbeddingResponse(
                embedding=result,
                provider=request.provider or "auto",
                model=request.model_name,
                device=request.device,
                cached=False
            )
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Embedding generation failed: {str(e)}"
            )
    
    @router.get("/providers", response_model=ProviderListResponse)
    async def list_providers() -> ProviderListResponse:
        """List available embeddings providers."""
        # Try to detect available providers
        available_providers = []
        
        # Check for common providers
        provider_checks = [
            ("openrouter", "OpenRouter embeddings API"),
            ("gemini_cli", "Gemini CLI"),
            ("local_adapter", "Local HuggingFace adapter"),
            ("ipfs_peer", "IPFS peer endpoints"),
        ]
        
        for provider_name, description in provider_checks:
            try:
                # Try to get provider - if it works, it's available
                provider = get_embeddings_provider(provider_name, deps=router_deps, use_cache=False)
                if provider is not None:
                    available_providers.append(provider_name)
            except Exception:
                # Provider not available
                pass
        
        import os
        default_provider = (
            os.getenv("IPFS_KIT_EMBEDDINGS_PROVIDER") or 
            os.getenv("IPFS_DATASETS_PY_EMBEDDINGS_PROVIDER") or 
            None
        )
        
        return ProviderListResponse(
            providers=available_providers,
            default_provider=default_provider
        )
    
    @router.get("/health", response_model=Dict[str, Any])
    async def health_check() -> Dict[str, Any]:
        """Check health of embeddings router."""
        try:
            # Try to get a provider
            provider = get_embeddings_provider(deps=router_deps, use_cache=False)
            
            return {
                "status": "healthy",
                "message": "Embeddings router is operational",
                "provider_available": provider is not None
            }
        except Exception as e:
            logger.error(f"Embeddings router health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Embeddings router error: {str(e)}",
                "provider_available": False
            }
    
    @router.post("/cache/clear", response_model=Dict[str, str])
    async def clear_cache() -> Dict[str, str]:
        """Clear the embeddings router caches."""
        try:
            clear_embeddings_router_caches()
            return {
                "status": "success",
                "message": "Embeddings router caches cleared"
            }
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Cache clear failed: {str(e)}"
            )
    
    return router
