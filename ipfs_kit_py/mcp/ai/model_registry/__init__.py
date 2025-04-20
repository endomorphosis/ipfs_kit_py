"""
MCP Model Registry Package

This package implements a comprehensive model registry for machine learning models with:
- Version-controlled model storage
- Model metadata management
- Model performance tracking
- Deployment configuration management

The registry supports various model formats and frameworks and integrates with
the storage backends provided by the MCP server.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

from ipfs_kit_py.mcp.ai.model_registry.registry import (
    ModelRegistry,
    Model,
    ModelVersion,
    ModelMetrics,
    ModelDependency,
    ModelDeploymentConfig,
    ModelFormat,
    ModelFramework,
    ModelType,
    ModelStatus
)

from ipfs_kit_py.mcp.ai.model_registry.router import (
    router as model_registry_router,
    initialize_model_registry
)

__all__ = [
    # Core registry classes
    'ModelRegistry',
    'Model',
    'ModelVersion',
    'ModelMetrics',
    'ModelDependency',
    'ModelDeploymentConfig',
    
    # Enums for model metadata
    'ModelFormat',
    'ModelFramework',
    'ModelType',
    'ModelStatus',
    
    # Router and initialization
    'model_registry_router',
    'initialize_model_registry'
]