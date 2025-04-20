"""
MCP Dataset Management Package

This package implements a comprehensive dataset management system with:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics
- Dataset lineage tracking

The system supports various types of datasets and integrates with
the storage backends provided by the MCP server.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

from ipfs_kit_py.mcp.ai.dataset_management.manager import (
    DatasetManager,
    Dataset,
    DatasetVersion,
    DataQualityMetrics,
    DataLineage,
    DatasetFormat,
    DatasetType,
    DatasetStatus,
    DataLicense,
    DataSource,
    PreprocessingStep,
    Schema,
    DatasetMetadata
)

from ipfs_kit_py.mcp.ai.dataset_management.router import (
    router as dataset_management_router,
    initialize_dataset_manager
)

__all__ = [
    # Core registry classes
    'DatasetManager',
    'Dataset',
    'DatasetVersion',
    'DataQualityMetrics',
    'DataLineage',
    'DataSource',
    'PreprocessingStep',
    'Schema',
    'DatasetMetadata',
    
    # Enums for dataset metadata
    'DatasetFormat',
    'DatasetType',
    'DatasetStatus',
    'DataLicense',
    
    # Router and initialization
    'dataset_management_router',
    'initialize_dataset_manager'
]