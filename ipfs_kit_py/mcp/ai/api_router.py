#!/usr/bin/env python3
"""
AI/ML API Router for MCP Server

This module provides the main FastAPI router for all AI/ML components,
integrating various sub-components like model registry and dataset manager.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException

# Configure logging
logger = logging.getLogger("mcp_ai_api_router")

def create_ai_api_router(
    model_registry=None,
    dataset_manager=None,
    distributed_training=None,
    framework_integration=None
) -> APIRouter:
    """
    Create the main AI/ML API router.
    
    Args:
        model_registry: Model registry instance
        dataset_manager: Dataset manager instance
        distributed_training: Distributed training instance
        framework_integration: Framework integration instance
        
    Returns:
        FastAPI router
    """
    # Create main router
    main_router = APIRouter()
    
    # Define root endpoint for AI API
    @main_router.get("/", response_model=Dict[str, Any])
    async def get_ai_info() -> Dict[str, Any]:
        """Get information about available AI/ML features."""
        components = []
        
        if model_registry:
            components.append({
                "name": "model_registry",
                "status": "available",
                "description": "Manages machine learning models with version control"
            })
            
        if dataset_manager:
            components.append({
                "name": "dataset_manager",
                "status": "available",
                "description": "Manages datasets with version control and quality metrics"
            })
            
        if distributed_training:
            components.append({
                "name": "distributed_training",
                "status": "available",
                "description": "Distributed training infrastructure for machine learning models"
            })
            
        if framework_integration:
            components.append({
                "name": "framework_integration",
                "status": "available",
                "description": "Integration with popular ML frameworks"
            })
            
        return {
            "name": "AI/ML API",
            "version": "1.0.0",
            "components": components
        }
    
    # Include sub-routers if available
    
    # Add model registry router
    if model_registry:
        try:
            from .model_registry_router import create_model_registry_router
            model_registry_router = create_model_registry_router(model_registry)
            main_router.include_router(
                model_registry_router,
                prefix="/registry",
                tags=["model-registry"]
            )
            logger.info("Included model registry router")
        except ImportError as e:
            logger.warning(f"Could not include model registry router: {e}")
    
    # Add dataset manager router
    if dataset_manager:
        try:
            from .dataset_manager_router import create_dataset_manager_router
            dataset_manager_router = create_dataset_manager_router(dataset_manager)
            main_router.include_router(
                dataset_manager_router,
                prefix="/datasets",
                tags=["dataset-manager"]
            )
            logger.info("Included dataset manager router")
        except ImportError as e:
            logger.warning(f"Could not include dataset manager router: {e}")
    
    # Add health check endpoint
    @main_router.get("/health", response_model=Dict[str, Any])
    async def health_check() -> Dict[str, Any]:
        """Check health of AI/ML subsystems."""
        statuses = {}
        
        if model_registry:
            try:
                # Check if model registry is functional by listing models
                _ = model_registry.list_models(limit=1)
                statuses["model_registry"] = "healthy"
            except Exception as e:
                logger.error(f"Model registry health check failed: {e}")
                statuses["model_registry"] = f"unhealthy: {str(e)}"
                
        if dataset_manager:
            try:
                # Attempt a basic operation to check health
                if hasattr(dataset_manager, "list_datasets"):
                    _ = dataset_manager.list_datasets(limit=1)
                    statuses["dataset_manager"] = "healthy"
                else:
                    # Alternative health check
                    statuses["dataset_manager"] = "unknown"
            except Exception as e:
                logger.error(f"Dataset manager health check failed: {e}")
                statuses["dataset_manager"] = f"unhealthy: {str(e)}"
        
        if distributed_training:
            statuses["distributed_training"] = "not_implemented"
            
        if framework_integration:
            statuses["framework_integration"] = "not_implemented"
            
        return {
            "status": "ok" if all(s == "healthy" for s in statuses.values() if s != "not_implemented") else "degraded",
            "components": statuses,
            "message": "AI/ML subsystems health check"
        }
    
    return main_router
