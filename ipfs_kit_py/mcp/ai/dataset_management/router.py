"""
Dataset Management API Router

This module provides FastAPI routes for the Dataset Management system, enabling:
- Dataset creation and versioning
- Metadata management
- Quality metrics tracking
- Schema management
- Lineage tracking
- Dataset file storage and retrieval

These endpoints integrate with the MCP server to provide comprehensive
dataset management capabilities as part of the AI/ML integration features.

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

# Import the Dataset Management components
from ipfs_kit_py.mcp.ai.dataset_management.manager import (
    DatasetManager, Dataset, DatasetVersion, DataQualityMetrics, DataLineage,
    DatasetFormat, DatasetType, DatasetStatus, DataLicense, 
    DataSource, PreprocessingStep, Schema, DatasetMetadata
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
router = APIRouter(prefix="/api/v0/ai/datasets", tags=["Dataset Management"])

# Global dataset manager instance
_dataset_manager = None

# Pydantic models for request/response validation

class DataSourceCreate(BaseModel):
    """Data source creation request."""
    name: str = Field(..., description="Source name")
    description: Optional[str] = Field(None, description="Source description")
    url: Optional[str] = Field(None, description="Source URL")
    contact: Optional[str] = Field(None, description="Contact information")
    citation: Optional[str] = Field(None, description="Citation information")

class DatasetCreate(BaseModel):
    """Dataset creation request."""
    name: str = Field(..., description="Dataset name")
    description: str = Field("", description="Dataset description")
    dataset_type: Optional[str] = Field(None, description="Dataset type")
    source: Optional[DataSourceCreate] = Field(None, description="Data source")
    team: Optional[str] = Field(None, description="Team name")
    project: Optional[str] = Field(None, description="Project name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Dataset metadata")
    tags: List[str] = Field(default_factory=list, description="Dataset tags")
    access_control: Dict[str, Any] = Field(default_factory=dict, description="Access control rules")

class DatasetUpdate(BaseModel):
    """Dataset update request."""
    name: Optional[str] = Field(None, description="Dataset name")
    description: Optional[str] = Field(None, description="Dataset description")
    dataset_type: Optional[str] = Field(None, description="Dataset type")
    source: Optional[DataSourceCreate] = Field(None, description="Data source")
    team: Optional[str] = Field(None, description="Team name")
    project: Optional[str] = Field(None, description="Project name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dataset metadata to merge")
    tags: Optional[List[str]] = Field(None, description="Dataset tags (replaces existing)")
    access_control: Optional[Dict[str, Any]] = Field(None, description="Access control rules to merge")

class VersionUpdate(BaseModel):
    """Version update request."""
    description: Optional[str] = Field(None, description="Version description")
    status: Optional[str] = Field(None, description="Version status")
    license: Optional[str] = Field(None, description="Data license")
    tags: Optional[List[str]] = Field(None, description="Version tags (replaces existing)")

class QualityMetricsUpdate(BaseModel):
    """Quality metrics update request."""
    completeness: Optional[float] = Field(None, description="Percentage of non-null values")
    uniqueness: Optional[float] = Field(None, description="Percentage of unique values")
    consistency: Optional[float] = Field(None, description="Consistency score")
    accuracy: Optional[float] = Field(None, description="Accuracy score")
    integrity: Optional[float] = Field(None, description="Data integrity score")
    timeliness: Optional[float] = Field(None, description="Timeliness score")
    num_samples: Optional[int] = Field(None, description="Number of samples")
    num_features: Optional[int] = Field(None, description="Number of features")
    missing_values: Optional[int] = Field(None, description="Count of missing values")
    duplicate_rows: Optional[int] = Field(None, description="Count of duplicate rows")
    outliers_count: Optional[int] = Field(None, description="Count of outliers")
    class_distribution: Dict[str, int] = Field(default_factory=dict, description="Distribution of classes")
    custom_metrics: Dict[str, Any] = Field(default_factory=dict, description="Custom metrics")

class SchemaUpdate(BaseModel):
    """Schema update request."""
    fields: List[Dict[str, Any]] = Field(..., description="Schema fields")
    description: Optional[str] = Field(None, description="Schema description")

class LineageUpdate(BaseModel):
    """Lineage update request."""
    parent_datasets: List[str] = Field(default_factory=list, description="Parent dataset IDs")
    derived_datasets: List[str] = Field(default_factory=list, description="Derived dataset IDs")
    source_code_repo: Optional[str] = Field(None, description="Repository URL")
    source_code_commit: Optional[str] = Field(None, description="Commit hash")
    processing_script: Optional[str] = Field(None, description="Processing script")
    transformations: List[Dict[str, Any]] = Field(default_factory=list, description="Applied transformations")
    creation_timestamp: Optional[float] = Field(None, description="Creation timestamp")
    creator_id: Optional[str] = Field(None, description="Creator ID")

class PreprocessingStepCreate(BaseModel):
    """Preprocessing step creation request."""
    name: str = Field(..., description="Step name")
    description: str = Field(..., description="Step description")
    parameters: Dict[str, Any] = Field(..., description="Step parameters")
    order: int = Field(..., description="Step order")


# Dependency to get the dataset manager instance
async def get_dataset_manager() -> DatasetManager:
    """Get the dataset manager instance."""
    global _dataset_manager
    if _dataset_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dataset manager not initialized"
        )
    return _dataset_manager


# Dataset management endpoints

@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset: DatasetCreate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Create a new dataset in the registry.
    
    Returns the created dataset information.
    """
    # Convert dataset_type string to enum if provided
    dataset_type = None
    if dataset.dataset_type:
        try:
            dataset_type = DatasetType(dataset.dataset_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dataset type: {dataset.dataset_type}"
            )
    
    # Convert source dict to DataSource if provided
    source = None
    if dataset.source:
        source = DataSource(
            name=dataset.source.name,
            description=dataset.source.description,
            url=dataset.source.url,
            contact=dataset.source.contact,
            citation=dataset.source.citation
        )
    
    # Create dataset
    created_dataset = await manager.create_dataset(
        name=dataset.name,
        owner=current_user.id,
        description=dataset.description,
        dataset_type=dataset_type,
        source=source,
        team=dataset.team,
        project=dataset.project,
        metadata=dataset.metadata,
        tags=dataset.tags,
        access_control=dataset.access_control
    )
    
    if not created_dataset:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dataset"
        )
    
    # Return dataset details
    return {
        "success": True,
        "dataset": created_dataset.to_dict()
    }


@router.get("", response_model=Dict[str, Any])
async def list_datasets(
    name: Optional[str] = None,
    owner: Optional[str] = None,
    tags: Optional[str] = None,
    dataset_type: Optional[str] = None,
    team: Optional[str] = None,
    project: Optional[str] = None,
    created_after: Optional[float] = None,
    created_before: Optional[float] = None,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    List datasets in the registry with optional filtering.
    
    Returns a list of datasets matching the filter criteria.
    """
    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",")]
    
    # Convert dataset_type string to enum if provided
    dataset_type_enum = None
    if dataset_type:
        try:
            dataset_type_enum = DatasetType(dataset_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dataset type: {dataset_type}"
            )
    
    # Get datasets
    datasets = await manager.list_datasets(
        name_filter=name,
        owner_filter=owner,
        tags_filter=tags_list,
        dataset_type_filter=dataset_type_enum,
        team_filter=team,
        project_filter=project,
        created_after=created_after,
        created_before=created_before
    )
    
    # Return dataset list
    return {
        "success": True,
        "count": len(datasets),
        "datasets": [dataset.to_dict() for dataset in datasets]
    }


@router.get("/{dataset_id}", response_model=Dict[str, Any])
async def get_dataset(
    dataset_id: str,
    include_versions: bool = False,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Get a dataset by ID.
    
    Returns the dataset information.
    """
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Return dataset details
    return {
        "success": True,
        "dataset": dataset.to_dict(include_versions=include_versions)
    }


@router.patch("/{dataset_id}", response_model=Dict[str, Any])
async def update_dataset(
    dataset_id: str,
    dataset_update: DatasetUpdate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Update a dataset's metadata.
    
    Returns the updated dataset information.
    """
    # Check if dataset exists
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Check owner or admin permission
    if dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        # Here we're just doing a basic check
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this dataset"
            )
    
    # Convert dataset_type string to enum if provided
    dataset_type = None
    if dataset_update.dataset_type:
        try:
            dataset_type = DatasetType(dataset_update.dataset_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dataset type: {dataset_update.dataset_type}"
            )
    
    # Convert source dict to DataSource if provided
    source = None
    if dataset_update.source:
        source = DataSource(
            name=dataset_update.source.name,
            description=dataset_update.source.description,
            url=dataset_update.source.url,
            contact=dataset_update.source.contact,
            citation=dataset_update.source.citation
        )
    
    # Update dataset
    updated_dataset = await manager.update_dataset(
        dataset_id=dataset_id,
        name=dataset_update.name,
        description=dataset_update.description,
        dataset_type=dataset_type,
        source=source,
        team=dataset_update.team,
        project=dataset_update.project,
        metadata=dataset_update.metadata,
        tags=dataset_update.tags,
        access_control=dataset_update.access_control
    )
    
    if not updated_dataset:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dataset"
        )
    
    # Return updated dataset
    return {
        "success": True,
        "dataset": updated_dataset.to_dict()
    }


@router.delete("/{dataset_id}", response_model=Dict[str, Any])
async def delete_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Delete a dataset and all its versions.
    
    Returns success status.
    """
    # Check if dataset exists
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Check owner or admin permission
    if dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this dataset"
            )
    
    # Delete dataset
    success = await manager.delete_dataset(dataset_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dataset"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Dataset {dataset_id} deleted"
    }


# Version management endpoints

@router.post("/{dataset_id}/versions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_dataset_version(
    dataset_id: str,
    version: str = Form(...),
    files: List[UploadFile] = File(...),
    description: str = Form(""),
    commit_message: str = Form(""),
    format: str = Form(...),
    license: Optional[str] = Form(None),
    tags: Optional[str] = Form("[]"),
    parent_version: Optional[str] = Form(None),
    storage_backend: str = Form("ipfs"),
    status: str = Form("draft"),
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Create a new version of a dataset.
    
    Uploads dataset files and creates a new version in the registry.
    """
    # Check if dataset exists
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Check owner or admin permission
    if dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has write permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to create versions for this dataset"
            )
    
    # Parse format
    try:
        dataset_format = DatasetFormat(format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid dataset format: {format}"
        )
    
    # Parse license if provided
    dataset_license = None
    if license:
        try:
            dataset_license = DataLicense(license)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid license: {license}"
            )
    
    # Parse status
    try:
        dataset_status = DatasetStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {status}"
        )
    
    # Parse tags
    try:
        tags_list = json.loads(tags)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tags JSON"
        )
    
    # Read and process all files
    data_files = {}
    for file in files:
        file_content = await file.read()
        data_files[file.filename] = file_content
    
    # Create dataset version
    dataset_version = await manager.create_dataset_version(
        dataset_id=dataset_id,
        version=version,
        created_by=current_user.id,
        data_files=data_files,
        format=dataset_format,
        storage_backend=storage_backend,
        description=description,
        commit_message=commit_message,
        license=dataset_license,
        tags=tags_list,
        parent_version=parent_version,
        status=dataset_status
    )
    
    if not dataset_version:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create dataset version"
        )
    
    # Return dataset version details
    return {
        "success": True,
        "dataset_id": dataset_id,
        "version": dataset_version.to_dict()
    }


@router.get("/{dataset_id}/versions", response_model=Dict[str, Any])
async def list_dataset_versions(
    dataset_id: str,
    status: Optional[str] = None,
    format: Optional[str] = None,
    license: Optional[str] = None,
    created_after: Optional[float] = None,
    created_before: Optional[float] = None,
    tags: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    List versions of a dataset with optional filtering.
    
    Returns a list of versions matching the filter criteria.
    """
    # Check if dataset exists
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Parse status if provided
    status_filter = None
    if status:
        try:
            status_filter = DatasetStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid version status: {status}"
            )
    
    # Parse format if provided
    format_filter = None
    if format:
        try:
            format_filter = DatasetFormat(format)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid dataset format: {format}"
            )
    
    # Parse license if provided
    license_filter = None
    if license:
        try:
            license_filter = DataLicense(license)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid license: {license}"
            )
    
    # Parse tags if provided
    tags_list = None
    if tags:
        tags_list = [tag.strip() for tag in tags.split(",")]
    
    # Get versions
    versions = await manager.list_versions(
        dataset_id=dataset_id,
        status_filter=status_filter,
        format_filter=format_filter,
        license_filter=license_filter,
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


@router.get("/{dataset_id}/versions/{version_id}", response_model=Dict[str, Any])
async def get_dataset_version(
    dataset_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Get a specific version of a dataset.
    
    Returns the version information.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


@router.patch("/{dataset_id}/versions/{version_id}", response_model=Dict[str, Any])
async def update_dataset_version(
    dataset_id: str,
    version_id: str,
    version_update: VersionUpdate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Update a dataset version's metadata.
    
    Returns the updated version information.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this dataset version"
            )
    
    # Parse status if provided
    update_status = None
    if version_update.status:
        try:
            update_status = DatasetStatus(version_update.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid version status: {version_update.status}"
            )
    
    # Parse license if provided
    update_license = None
    if version_update.license:
        try:
            update_license = DataLicense(version_update.license)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid license: {version_update.license}"
            )
    
    # Update version
    updated_version = await manager.update_version(
        version_id=version_id,
        description=version_update.description,
        status=update_status,
        license=update_license,
        tags=version_update.tags
    )
    
    if not updated_version:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dataset version"
        )
    
    # Return updated version
    return {
        "success": True,
        "version": updated_version.to_dict()
    }


@router.delete("/{dataset_id}/versions/{version_id}", response_model=Dict[str, Any])
async def delete_dataset_version(
    dataset_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Delete a dataset version.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this dataset version"
            )
    
    # Delete version
    success = await manager.delete_version(version_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete dataset version"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Version {version_id} deleted"
    }


@router.get("/{dataset_id}/versions/{version_id}/files", response_model=Dict[str, Any])
async def list_dataset_files(
    dataset_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    List files in a dataset version.
    
    Returns a list of filenames.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Get files
    files = await manager.get_dataset_files(version_id)
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Failed to retrieve dataset files or no files found"
        )
    
    # Return file list
    return {
        "success": True,
        "count": len(files),
        "files": list(files.keys())
    }


@router.get("/{dataset_id}/versions/{version_id}/files/{file_name:path}", response_class=StreamingResponse)
async def download_dataset_file(
    dataset_id: str,
    version_id: str,
    file_name: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Download a specific file from a dataset version.
    
    Returns the file content as a streaming response.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Get file
    files = await manager.get_dataset_files(version_id, file_patterns=[file_name])
    
    if not files or file_name not in files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_name} not found in dataset version"
        )
    
    file_content = files[file_name]
    
    # Determine content type (simplified version)
    content_type = "application/octet-stream"
    if file_name.endswith(".csv"):
        content_type = "text/csv"
    elif file_name.endswith(".json"):
        content_type = "application/json"
    elif file_name.endswith(".txt"):
        content_type = "text/plain"
    elif file_name.endswith((".jpg", ".jpeg")):
        content_type = "image/jpeg"
    elif file_name.endswith(".png"):
        content_type = "image/png"
    
    # Return file as streaming response
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={os.path.basename(file_name)}"
        }
    )


@router.post("/{dataset_id}/versions/{version_id}/ready", response_model=Dict[str, Any])
async def set_version_ready(
    dataset_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Set a version as the ready version for a dataset.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to set the ready version for this dataset"
            )
    
    # Set ready version
    success = await manager.set_ready_version(dataset_id, version_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set ready version"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Version {version_id} set as ready for dataset {dataset_id}"
    }


@router.get("/{dataset_id}/ready", response_model=Dict[str, Any])
async def get_ready_version(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Get the ready version for a dataset.
    
    Returns the ready version information.
    """
    # Get ready version
    version = await manager.get_ready_version(dataset_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ready version found for dataset {dataset_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


@router.get("/{dataset_id}/latest", response_model=Dict[str, Any])
async def get_latest_version(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Get the latest version for a dataset.
    
    Returns the latest version information.
    """
    # Get latest version
    version = await manager.get_latest_version(dataset_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for dataset {dataset_id}"
        )
    
    # Return version details
    return {
        "success": True,
        "version": version.to_dict()
    }


# Quality metrics and metadata endpoints

@router.post("/{dataset_id}/versions/{version_id}/quality", response_model=Dict[str, Any])
async def update_quality_metrics(
    dataset_id: str,
    version_id: str,
    metrics: QualityMetricsUpdate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Update quality metrics for a dataset version.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update metrics for this dataset version"
            )
    
    # Create DataQualityMetrics from the provided data
    quality_metrics = DataQualityMetrics(
        completeness=metrics.completeness,
        uniqueness=metrics.uniqueness,
        consistency=metrics.consistency,
        accuracy=metrics.accuracy,
        integrity=metrics.integrity,
        timeliness=metrics.timeliness,
        num_samples=metrics.num_samples,
        num_features=metrics.num_features,
        missing_values=metrics.missing_values,
        duplicate_rows=metrics.duplicate_rows,
        outliers_count=metrics.outliers_count,
        class_distribution=metrics.class_distribution,
        custom_metrics=metrics.custom_metrics
    )
    
    # Update metrics
    success = await manager.record_quality_metrics(version_id, quality_metrics)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update quality metrics"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Quality metrics updated for version {version_id}"
    }


@router.post("/{dataset_id}/versions/{version_id}/schema", response_model=Dict[str, Any])
async def update_schema(
    dataset_id: str,
    version_id: str,
    schema: SchemaUpdate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Update schema for a dataset version.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update schema for this dataset version"
            )
    
    # Create Schema from the provided data
    schema_obj = Schema(
        fields=schema.fields,
        description=schema.description
    )
    
    # Update schema
    success = await manager.update_schema(version_id, schema_obj)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update schema"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Schema updated for version {version_id}"
    }


@router.post("/{dataset_id}/versions/{version_id}/lineage", response_model=Dict[str, Any])
async def update_lineage(
    dataset_id: str,
    version_id: str,
    lineage: LineageUpdate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Update lineage for a dataset version.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update lineage for this dataset version"
            )
    
    # Create DataLineage from the provided data
    lineage_obj = DataLineage(
        parent_datasets=lineage.parent_datasets,
        derived_datasets=lineage.derived_datasets,
        source_code_repo=lineage.source_code_repo,
        source_code_commit=lineage.source_code_commit,
        processing_script=lineage.processing_script,
        transformations=lineage.transformations,
        creation_timestamp=lineage.creation_timestamp,
        creator_id=lineage.creator_id or current_user.id
    )
    
    # Update lineage
    success = await manager.update_lineage(version_id, lineage_obj)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update lineage"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Lineage updated for version {version_id}"
    }


@router.post("/{dataset_id}/versions/{version_id}/preprocessing", response_model=Dict[str, Any])
async def add_preprocessing_step(
    dataset_id: str,
    version_id: str,
    step: PreprocessingStepCreate,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Add a preprocessing step to a dataset version.
    
    Returns success status.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to add preprocessing steps for this dataset version"
            )
    
    # Create PreprocessingStep from the provided data
    preprocessing_step = PreprocessingStep(
        name=step.name,
        description=step.description,
        parameters=step.parameters,
        order=step.order
    )
    
    # Add preprocessing step
    success = await manager.add_preprocessing_step(version_id, preprocessing_step)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add preprocessing step"
        )
    
    # Return success
    return {
        "success": True,
        "message": f"Preprocessing step added to version {version_id}"
    }


@router.post("/{dataset_id}/versions/{version_id}/calculate-quality", response_model=Dict[str, Any])
async def calculate_dataset_quality(
    dataset_id: str,
    version_id: str,
    custom_metrics: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Calculate quality metrics for a dataset version.
    
    Returns the calculated metrics.
    """
    # Get version
    version = await manager.get_version(version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found"
        )
    
    # Verify dataset ID matches
    if version.dataset_id != dataset_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Version {version_id} does not belong to dataset {dataset_id}"
        )
    
    # Check owner or admin permission
    dataset = await manager.get_dataset(dataset_id)
    if dataset and dataset.owner != current_user.id:
        # In a real implementation, check if user is admin or has permission
        if AUTH_AVAILABLE and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to calculate metrics for this dataset version"
            )
    
    # Calculate metrics
    metrics = await manager.calculate_quality_metrics(version_id, custom_metrics)
    
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate quality metrics"
        )
    
    # Return metrics
    return {
        "success": True,
        "metrics": metrics.to_dict()
    }


@router.get("/{dataset_id}/derived", response_model=Dict[str, Any])
async def get_derived_datasets(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    manager: DatasetManager = Depends(get_dataset_manager)
):
    """
    Get datasets derived from a dataset.
    
    Returns a list of derived datasets.
    """
    # Check if dataset exists
    dataset = await manager.get_dataset(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found"
        )
    
    # Get derived datasets
    derived_datasets = await manager.get_derived_datasets(dataset_id)
    
    # Return derived datasets
    return {
        "success": True,
        "count": len(derived_datasets),
        "datasets": [dataset.to_dict() for dataset in derived_datasets]
    }


def initialize_dataset_manager(backend_manager: Any) -> DatasetManager:
    """
    Initialize the dataset manager.
    
    Args:
        backend_manager: Backend manager instance
        
    Returns:
        Initialized dataset manager
    """
    global _dataset_manager
    
    # Create data directory
    data_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "dataset_management")
    os.makedirs(data_dir, exist_ok=True)
    
    # Create manager
    _dataset_manager = DatasetManager(data_dir, backend_manager)
    
    return _dataset_manager