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
    # Keep this best-effort: the package should import cleanly even when the
    # optional acceleration layer is absent.
    import sys
    from pathlib import Path as AcceleratePath

    accelerate_path = AcceleratePath(__file__).resolve().parents[3] / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))

    from ipfs_accelerate_py import AccelerateCompute  # noqa: F401

    HAS_ACCELERATE = True
except ImportError:
    pass

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

# Optional ipfs_accelerate_py availability flag
HAS_ACCELERATE = False
try:
    import sys
    from pathlib import Path as AcceleratePath

    accelerate_path = AcceleratePath(__file__).resolve().parents[2] / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))

    from ipfs_accelerate_py import AccelerateCompute  # noqa: F401
    HAS_ACCELERATE = True
except Exception:
    HAS_ACCELERATE = False

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