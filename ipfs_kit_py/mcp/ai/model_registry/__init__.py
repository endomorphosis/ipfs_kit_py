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

import logging

logger = logging.getLogger(__name__)

# Optional integration flags (tests expect these at the package level)
HAS_DATASETS = False
try:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager  # noqa: F401

    HAS_DATASETS = True
except ImportError:
    pass

HAS_ACCELERATE = False
try:
    import importlib.util

    # Only *detect* availability here. Importing ipfs_accelerate_py can print to
    # stdout as a side effect, which breaks JSON-producing CLIs.
    HAS_ACCELERATE = importlib.util.find_spec("ipfs_accelerate_py") is not None
except Exception:
    HAS_ACCELERATE = False

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
    'initialize_model_registry',
    'HAS_ACCELERATE'
]