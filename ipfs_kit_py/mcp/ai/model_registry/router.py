"""
Model Registry API Router

This module provides FastAPI routes for the Model Registry, enabling:
- Model management (CRUD operations)
- Version management
- Model data storage and retrieval
- Performance metrics tracking
- Deployment configuration management

These endpoints integrate with the MCP server to provide a comprehensive
model registry as part of the AI/ML integration features.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import io
import json
import time
from typing import Dict, List, Optional, Any, Union, Set
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# Import the Model Registry components
from ipfs_kit_py.mcp.ai.model_registry.registry import (
    ModelRegistry, Model, ModelVersion, ModelMetrics, ModelDependency,
    ModelDeploymentConfig, ModelFormat, ModelFramework, ModelType, ModelStatus
)

# Import auth components for permission checking
try:
    from ipfs_kit_py.mcp.auth.models import User
    from ipfs_kit_py.mcp.auth.router import get_current_user, get_admin_user
    AUTH_AVAILABLE = True
except ImportError:
    # Fallback: define a User class and dummy dependency
    class User:
        id: str
        username: str
        
    async def get_current_user():
        return User(id="mock_user", username="mock_user")
    
    async def get_admin_user():
        return User(id="mock_admin", username="mock_admin")
    
    AUTH_AVAILABLE = False

# Create router
router = APIRouter(prefix="/api/v0/ai/models", tags=["Model Registry"])

# Global model registry instance
_model_registry = None

# Pydantic models for request/response validation

class ModelCreate(BaseModel):
    """Model creation request."""
    name: str = Field(..., description="Model name")
    description: str = Field("", description="Model description")
    model_type: Optional[str] = Field(None, description="Model type")
    team: Optional[str] = Field(None, description="Team name")
    project: Optional[str] = Field(None, description="Project name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Model metadata")
    tags: List[str] = Field(default_factory=list, description="Model tags")

class ModelUpdate(BaseModel):
    """Model update request."""
    name: Optional[str] = Field(None, description="Model name")
    description: Optional[str] = Field(None, description="Model description")
    model_type: Optional[str] = Field(None, description="Model type")
    team: Optional[str] = Field(None, description="Team name")
    project: Optional[str] = Field(None, description="Project name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Model metadata to merge")
    tags: Optional[List[str]] = Field(None, description="Model tags (replaces existing)")

class VersionUpdate(BaseModel):
    """Version update request."""
    description: Optional[str] = Field(None, description="Version description")
    status: Optional[str] = Field(None, description="Version status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Version metadata to merge")
    tags: Optional[List[str]] = Field(None, description="Version tags (replaces existing)")

class MetricsUpdate(BaseModel):
    """Metrics update request."""
    accuracy: Optional[float] = Field(None, description="Classification accuracy")
    precision: Optional[float] = Field(None, description="Classification precision")
    recall: Optional[float] = Field(None, description="Classification recall")
    f1_score: Optional[float] = Field(None, description="F1 score")
    auc: Optional[float] = Field(None, description="Area under ROC curve")
    mse: Optional[float] = Field(None, description="Mean squared error")
    mae: Optional[float] = Field(None, description="Mean absolute error")
    r2: Optional[float] = Field(None, description="R-squared score")
    latency_ms: Optional[float] = Field(None, description="Inference latency in milliseconds")
    throughput_qps: Optional[float] = Field(None, description="Queries per second")
    memory_mb: Optional[float] = Field(None, description="Memory usage in MB")
    custom_metrics: Dict[str, float] = Field(default_factory=dict, description="Custom metrics")

class DeploymentConfigUpdate(BaseModel):
    """Deployment configuration update request."""
    min_resources: Dict[str, Any] = Field(default_factory=dict, description="Minimum resources")
    max_resources: Dict[str, Any] = Field(default_factory=dict, description="Maximum resources")
    scaling_policy: Dict[str, Any] = Field(default_factory=dict, description="Scaling policy")
    environment_variables: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    serving_config: Dict[str, Any] = Field(default_factory=dict, description="Serving configuration")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="Custom configuration")

class DependencyCreate(BaseModel):
    """Dependency create request."""
    name: str = Field(..., description="Dependency name")
    version: str = Field(..., description="Dependency version")
    constraint: Optional[str] = Field(None, description="Version constraint")


# Dependency to get the model registry instance
async def get_model_registry() -> ModelRegistry:
    """Get the model registry instance."""
    global _model_registry
    if _model_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model registry not initialized"
        )
    return _model_registry


# Model management endpoints

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_model(
    model: ModelCreate,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Create a new model in the registry.
    
    Returns the created model information.
    """
    # Convert model_type string to enum if provided
    model_type = None
    if model.model_type:
        try:
            model_type = ModelType(model.model_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model type: {model.model_type}"
            )
    
    # Create model
    created_model = await registry.create_model(
        name=model.name,
        owner=current_user.id,
        description=model.description,
        model_type=model_type,
        team=model.team,
        project=model.project,
        metadata=model.metadata,
        tags=model.tags
    )
    
    if not created_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model"
        )
    
    # Return model details
    return {
        "success": True,
        "model": created_model.to_dict()
    }


@router.get("", response_model=Dict[str, Any])
async def list_models(
    name: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[str] = None,
    model_type: Optional[str] = None,
    team: Optional[str] = None,
    project: Optional[str] = None,
    created_after: Optional[float] = None,
    created_before: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    List models in the registry with optional filtering.
    
    Returns a list of models matching the filter criteria.
    """
    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",")]
    
    # Convert model_type string to enum if provided
    model_type_enum = None
    if model_type:
        try:
            model_type_enum = ModelType(model_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model type: {model_type}"
            )
    
    # Get models
    models = await registry.list_models(
        name_filter=name,
        owner_filter=owner,
        tags_filter=tags_list,
        model_type_filter=model_type_enum,
        team_filter=team,
        project_filter=project,
        created_after=created_after,
        created_before=created_before
    )
    
    # Return model list
    return {
        "success": True,
        "count": len(models),
        "models": [model.to_dict() for model in models]
    }


@router.get("/{model_id}", response_model=Dict[str, Any])
async def get_model(
    model_id: str,
    include_versions: bool = False,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Get a model by ID.
    
    Returns the model information.
    """
    model = await registry.get_model(model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Return model details
    return {
        "success": True,
        "model": model.to_dict(include_versions=include_versions)
    }


@router.patch("/{model_id}", response_model=Dict[str, Any])
async def update_model(
    model_id: str,
    model_update: ModelUpdate,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Update a model's metadata.
    
    Returns the updated model information.
    """
    # Check if model exists
    model = await registry.get_model(model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Check owner or admin permission
    if model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        # Here we're just doing a basic check
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this model"
            )
    
    # Convert model_type string to enum if provided
    model_type = None
    if model_update.model_type:
        try:
            model_type = ModelType(model_update.model_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model type: {model_update.model_type}"
            )
    
    # Update model
    updated_model = await registry.update_model(
        model_id=model_id,
        name=model_update.name,
        description=model_update.description,
        model_type=model_type,
        team=model_update.team,
        project=model_update.project,
        metadata=model_update.metadata,
        tags=model_update.tags
    )
    
    if not updated_model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model"
        )
    
    # Return updated model
    return {
        "success": True,
        "model": updated_model.to_dict()
    }


@router.delete("/{model_id}", response_model=Dict[str, Any])
async def delete_model(
    model_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Delete a model and all its versions.
    
    Returns success status.
    """
    # Check if model exists
    model = await registry.get_model(model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Check owner or admin permission
    if model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this model"
            )
    
    # Delete model
    success = await registry.delete_model(model_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Model {model_id} deleted"
    }


# Version management endpoints

@router.post("/{model_id}/versions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_model_version(
    model_id: str,
    version: str = Form(...),
    model_file: UploadFile = File(...),
    description: str = Form(""),
    commit_message: str = Form(""),
    format: str = Form(...),
    framework: Optional[str] = Form(None),
    framework_version: Optional[str] = Form(None),
    metadata: Optional[str] = Form("{}"),
    tags: Optional[str] = Form("[]"),
    parent_version: Optional[str] = Form(None),
    dataset_refs: Optional[str] = Form("[]"),
    experiment_id: Optional[str] = Form(None),
    storage_backend: str = Form("ipfs"),
    status: str = Form("draft"),
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Create a new version of a model.
    
    Uploads the model file and creates a new version in the registry.
    """
    # Check if model exists
    model = await registry.get_model(model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Check owner or admin permission
    if model.owner != current_user.id:
        # In a real implementation, check if user is admin or has write permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create versions for this model"
            )
    
    # Parse format
    try:
        model_format = ModelFormat(format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model format: {format}"
        )
    
    # Parse framework if provided
    model_framework = None
    if framework:
        try:
            model_framework = ModelFramework(framework)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model framework: {framework}"
            )
    
    # Parse status
    try:
        model_status = ModelStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model status: {status}"
        )
    
    # Parse metadata
    try:
        metadata_dict = json.loads(metadata)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid metadata JSON"
        )
    
    # Parse tags
    try:
        tags_list = json.loads(tags)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tags JSON"
        )
    
    # Parse dataset_refs
    try:
        dataset_refs_list = json.loads(dataset_refs)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid dataset_refs JSON"
        )
    
    # Read model file
    model_data = await model_file.read()
    
    # Create model version
    model_version = await registry.create_model_version(
        model_id=model_id,
        version=version,
        created_by=current_user.id,
        model_data=model_data,
        format=model_format,
        storage_backend=storage_backend,
        description=description,
        commit_message=commit_message,
        framework=model_framework,
        framework_version=framework_version,
        metadata=metadata_dict,
        tags=tags_list,
        parent_version=parent_version,
        dataset_refs=dataset_refs_list,
        experiment_id=experiment_id,
        status=model_status
    )
    
    if not model_version:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model version"
        )
    
    # Return model version details
    return {
        "success": True,
        "model_id": model_id,
        "version": model_version.to_dict()
    }


@router.get("/{model_id}/versions", response_model=Dict[str, Any])
async def list_model_versions(
    model_id: str,
    status: Optional[str] = None,
    framework: Optional[str] = None,
    format: Optional[str] = None,
    created_after: Optional[float] = None,
    created_before: Optional[float] = None,
    tags: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    List versions of a model with optional filtering.
    
    Returns a list of versions matching the filter criteria.
    """
    # Check if model exists
    model = await registry.get_model(model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Parse status if provided
    status_filter = None
    if status:
        try:
            status_filter = ModelStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid version status: {status}"
            )
    
    # Parse framework if provided
    framework_filter = None
    if framework:
        try:
            framework_filter = ModelFramework(framework)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model framework: {framework}"
            )
    
    # Parse format if provided
    format_filter = None
    if format:
        try:
            format_filter = ModelFormat(format)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model format: {format}"
            )
    
    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",")]
    
    # Get versions
    versions = await registry.list_versions(
        model_id=model_id,
        status_filter=status_filter,
        framework_filter=framework_filter,
        format_filter=format_filter,
        created_after=created_after,
        created_before=created_before,
        tags_filter=tags_list
    )
    
    # Return version list
    return {
        "success": True,
        "count": len(versions),
        "versions": [version.to_dict() for version in versions]
    }


@router.get("/{model_id}/versions/{version_id}", response_model=Dict[str, Any])
async def get_model_version(
    model_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Get a specific version of a model.
    
    Returns the version information.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


@router.patch("/{model_id}/versions/{version_id}", response_model=Dict[str, Any])
async def update_model_version(
    model_id: str,
    version_id: str,
    version_update: VersionUpdate,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Update a model version's metadata.
    
    Returns the updated version information.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Check owner or admin permission
    model = await registry.get_model(model_id)
    if model and model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this model version"
            )
    
    # Parse status if provided
    update_status = None
    if version_update.status:
        try:
            update_status = ModelStatus(version_update.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid version status: {version_update.status}"
            )
    
    # Update version
    updated_version = await registry.update_version(
        version_id=version_id,
        description=version_update.description,
        status=update_status,
        metadata=version_update.metadata,
        tags=version_update.tags
    )
    
    if not updated_version:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model version"
        )
    
    # Return updated version
    return {
        "success": True,
        "version": updated_version.to_dict()
    }


@router.delete("/{model_id}/versions/{version_id}", response_model=Dict[str, Any])
async def delete_model_version(
    model_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Delete a model version.
    
    Returns success status.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Check owner or admin permission
    model = await registry.get_model(model_id)
    if model and model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this model version"
            )
    
    # Delete version
    success = await registry.delete_version(version_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete model version"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Version {version_id} deleted"
    }


@router.get("/{model_id}/versions/{version_id}/download", response_class=StreamingResponse)
async def download_model_version(
    model_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Download the binary data for a model version.
    
    Returns the model file as a streaming response.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Get model data
    model_data = await registry.get_model_data(version_id)
    
    if not model_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model data not found"
        )
    
    # Create content disposition filename
    filename = f"{model_id}_{version.version}.model"
    
    # Return streaming response
    return StreamingResponse(
        io.BytesIO(model_data),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/{model_id}/versions/{version_id}/metrics", response_model=Dict[str, Any])
async def update_version_metrics(
    model_id: str,
    version_id: str,
    metrics: MetricsUpdate,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Update performance metrics for a model version.
    
    Returns success status.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Check owner or admin permission
    model = await registry.get_model(model_id)
    if model and model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update metrics for this model version"
            )
    
    # Create ModelMetrics from the provided data
    model_metrics = ModelMetrics(
        accuracy=metrics.accuracy,
        precision=metrics.precision,
        recall=metrics.recall,
        f1_score=metrics.f1_score,
        auc=metrics.auc,
        mse=metrics.mse,
        mae=metrics.mae,
        r2=metrics.r2,
        latency_ms=metrics.latency_ms,
        throughput_qps=metrics.throughput_qps,
        memory_mb=metrics.memory_mb,
        custom_metrics=metrics.custom_metrics
    )
    
    # Update metrics
    success = await registry.record_metrics(version_id, model_metrics)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update metrics"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Metrics updated for version {version_id}"
    }


@router.post("/{model_id}/versions/{version_id}/deployment", response_model=Dict[str, Any])
async def update_deployment_config(
    model_id: str,
    version_id: str,
    config: DeploymentConfigUpdate,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Update deployment configuration for a model version.
    
    Returns success status.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Check owner or admin permission
    model = await registry.get_model(model_id)
    if model and model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update deployment config for this model version"
            )
    
    # Create ModelDeploymentConfig from the provided data
    deployment_config = ModelDeploymentConfig(
        min_resources=config.min_resources,
        max_resources=config.max_resources,
        scaling_policy=config.scaling_policy,
        environment_variables=config.environment_variables,
        serving_config=config.serving_config,
        custom_config=config.custom_config
    )
    
    # Update deployment config
    success = await registry.update_deployment_config(version_id, deployment_config)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update deployment configuration"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Deployment configuration updated for version {version_id}"
    }


@router.post("/{model_id}/production/{version_id}", response_model=Dict[str, Any])
async def set_production_version(
    model_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Set a version as the production version for a model.
    
    Returns success status.
    """
    # Get version
    version = await registry.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify model ID matches
    if version.model_id != model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to model {model_id}"
        )
    
    # Check owner or admin permission
    model = await registry.get_model(model_id)
    if model and model.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to set the production version for this model"
            )
    
    # Set production version
    success = await registry.set_production_version(model_id, version_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set production version"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Version {version_id} set as production for model {model_id}"
    }


@router.get("/{model_id}/production", response_model=Dict[str, Any])
async def get_production_version(
    model_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Get the production version for a model.
    
    Returns the production version information.
    """
    # Get production version
    version = await registry.get_production_version(model_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No production version found for model {model_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


@router.get("/{model_id}/latest", response_model=Dict[str, Any])
async def get_latest_version(
    model_id: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Get the latest version for a model.
    
    Returns the latest version information.
    """
    # Get latest version
    version = await registry.get_latest_version(model_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for model {model_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


@router.get("/versions/compare", response_model=Dict[str, Any])
async def compare_versions(
    version1: str,
    version2: str,
    current_user: User = Depends(get_current_user),
    registry: ModelRegistry = Depends(get_model_registry)
):
    """
    Compare two model versions.
    
    Returns a comparison of the two versions.
    """
    # Compare versions
    comparison = await registry.compare_versions(version1, version2)
    
    if not comparison.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=comparison.get("error", "Failed to compare versions")
        )
    
    # Return comparison
    return comparison


def initialize_model_registry(backend_manager: Any) -> ModelRegistry:
    """
    Initialize the model registry.
    
    Args:
        backend_manager: Backend manager instance
        
    Returns:
        Initialized model registry
    """
    global _model_registry
    
    # Create data directory
    data_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "model_registry")
    os.makedirs(data_dir, exist_ok=True)
    
    # Create registry
    _model_registry = ModelRegistry(data_dir, backend_manager)
    
    return _model_registry