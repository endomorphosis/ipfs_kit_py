"""
Dataset Management API Router

This module implements FastAPI routes for the Dataset Management:
- Dataset registration and version management
- File upload and download
- Dataset analysis and quality assessment
- Search and filtering capabilities

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import tempfile
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Form, Query, Path
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ipfs_kit_py.mcp.ai.dataset_manager import (
    get_instance as get_dataset_manager,
    DatasetType, DatasetFormat, DatasetStatus, DataQualityStatus
)

# Create API router
router = APIRouter(prefix="/api/v0/ai/datasets", tags=["dataset-management"])

# --- Helper Functions ---

async def save_upload_files_temp(upload_files: List[UploadFile]) -> List[str]:
    """
    Save uploaded files to temporary locations.
    
    Args:
        upload_files: List of uploaded file objects
        
    Returns:
        List of paths to temporary files
    """
    try:
        temp_paths = []
        for upload_file in upload_files:
            suffix = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ""
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                content = await upload_file.read()
                temp.write(content)
                temp_paths.append(temp.name)
        return temp_paths
    except Exception as e:
        # Clean up any created temp files
        for path in temp_paths:
            if os.path.exists(path):
                os.unlink(path)
        raise HTTPException(status_code=500, detail=f"Error saving uploaded files: {str(e)}")

# --- API Routes ---

@router.post("/", summary="Register a new dataset")
async def register_dataset(
    name: str = Form(..., description="Dataset name"),
    description: str = Form("", description="Dataset description"),
    dataset_type: Optional[str] = Form(None, description="Type of dataset"),
    dataset_format: Optional[str] = Form(None, description="Format of dataset"),
    tags: str = Form("", description="Comma-separated list of tags"),
    owner: Optional[str] = Form(None, description="Owner or creator of the dataset"),
    source_url: Optional[str] = Form(None, description="URL where the dataset was sourced from"),
    license_info: Optional[str] = Form(None, description="License information for the dataset"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string")
):
    """
    Register a new dataset in the system.
    
    Returns dataset ID and metadata for the registered dataset.
    """
    # Convert tags string to list
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
    
    # Parse metadata JSON if provided
    meta_dict = None
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    
    # Register dataset
    dataset_manager = get_dataset_manager()
    result = dataset_manager.register_dataset(
        name=name,
        description=description,
        dataset_type=dataset_type,
        dataset_format=dataset_format,
        tags=tag_list,
        owner=owner,
        source_url=source_url,
        license_info=license_info,
        metadata=meta_dict
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to register dataset"))
    
    return result

@router.get("/", summary="List datasets")
async def list_datasets(
    dataset_type: Optional[str] = Query(None, description="Filter by dataset type"),
    dataset_format: Optional[str] = Query(None, description="Filter by dataset format"),
    tags: Optional[str] = Query(None, description="Filter by comma-separated tags"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    status: Optional[str] = Query(None, description="Filter by status"),
    quality: Optional[str] = Query(None, description="Filter by quality status")
):
    """
    List datasets with optional filtering.
    
    Returns a list of datasets matching the specified filters.
    """
    # Convert tags string to list if provided
    tag_list = None
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
    
    # List datasets with filters
    dataset_manager = get_dataset_manager()
    result = dataset_manager.list_datasets(
        dataset_type=dataset_type,
        dataset_format=dataset_format,
        tags=tag_list,
        owner=owner,
        status=status,
        quality=quality
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to list datasets"))
    
    return result

@router.get("/{dataset_id}", summary="Get dataset details")
async def get_dataset(
    dataset_id: str = Path(..., description="Dataset ID")
):
    """
    Get detailed information about a specific dataset.
    
    Returns dataset metadata including available versions.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.get_dataset(dataset_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Dataset not found"))
    
    return result

@router.put("/{dataset_id}", summary="Update dataset metadata")
async def update_dataset(
    dataset_id: str = Path(..., description="Dataset ID"),
    name: Optional[str] = Form(None, description="New dataset name"),
    description: Optional[str] = Form(None, description="New dataset description"),
    dataset_type: Optional[str] = Form(None, description="New dataset type"),
    dataset_format: Optional[str] = Form(None, description="New dataset format"),
    tags: Optional[str] = Form(None, description="New comma-separated list of tags"),
    owner: Optional[str] = Form(None, description="New owner"),
    source_url: Optional[str] = Form(None, description="New source URL"),
    license_info: Optional[str] = Form(None, description="New license information"),
    status: Optional[str] = Form(None, description="New dataset status"),
    quality: Optional[str] = Form(None, description="New data quality status"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string")
):
    """
    Update dataset metadata.
    
    Returns updated dataset metadata.
    """
    # Convert tags string to list if provided
    tag_list = None
    if tags is not None:
        tag_list = [tag.strip() for tag in tags.split(",")]
    
    # Parse metadata JSON if provided
    meta_dict = None
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    
    # Update dataset
    dataset_manager = get_dataset_manager()
    result = dataset_manager.update_dataset(
        dataset_id=dataset_id,
        name=name,
        description=description,
        dataset_type=dataset_type,
        dataset_format=dataset_format,
        tags=tag_list,
        owner=owner,
        source_url=source_url,
        license_info=license_info,
        status=status,
        quality=quality,
        metadata=meta_dict
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update dataset"))
    
    return result

@router.post("/{dataset_id}/versions", summary="Create a new dataset version")
async def create_dataset_version(
    dataset_id: str = Path(..., description="Dataset ID"),
    files: List[UploadFile] = File(..., description="Dataset files to upload"),
    version: str = Form(..., description="Version string"),
    description: str = Form("", description="Version description"),
    statistics: Optional[str] = Form(None, description="Dataset statistics as JSON string"),
    schema: Optional[str] = Form(None, description="Dataset schema as JSON string"),
    preprocessing: Optional[str] = Form(None, description="Preprocessing steps as JSON string"),
    quality_metrics: Optional[str] = Form(None, description="Quality metrics as JSON string"),
    backend: Optional[str] = Form(None, description="Storage backend to use")
):
    """
    Create a new version of a dataset by uploading dataset files.
    
    Returns version metadata and storage information.
    """
    # Save uploaded files to temporary locations
    temp_file_paths = await save_upload_files_temp(files)
    
    try:
        # Parse JSON inputs if provided
        statistics_dict = None
        if statistics:
            try:
                statistics_dict = json.loads(statistics)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid statistics JSON")
        
        schema_dict = None
        if schema:
            try:
                schema_dict = json.loads(schema)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid schema JSON")
        
        preprocessing_list = None
        if preprocessing:
            try:
                preprocessing_list = json.loads(preprocessing)
                if not isinstance(preprocessing_list, list):
                    raise HTTPException(status_code=400, detail="Preprocessing must be a JSON array")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid preprocessing JSON")
        
        quality_metrics_dict = None
        if quality_metrics:
            try:
                quality_metrics_dict = json.loads(quality_metrics)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid quality metrics JSON")
        
        # Create dataset version
        dataset_manager = get_dataset_manager()
        result = dataset_manager.create_dataset_version(
            dataset_id=dataset_id,
            version=version,
            files=temp_file_paths,
            description=description,
            statistics=statistics_dict,
            schema=schema_dict,
            preprocessing=preprocessing_list,
            quality_metrics=quality_metrics_dict,
            backend=backend
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create dataset version"))
        
        return result
    finally:
        # Clean up temporary files
        for path in temp_file_paths:
            if os.path.exists(path):
                os.unlink(path)

@router.get("/{dataset_id}/versions/{version}", summary="Get dataset version details")
async def get_dataset_version(
    dataset_id: str = Path(..., description="Dataset ID"),
    version: str = Path(..., description="Version string")
):
    """
    Get detailed information about a specific dataset version.
    
    Returns version metadata including statistics and storage information.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.get_dataset_version(dataset_id, version)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Dataset version not found"))
    
    return result

@router.get("/{dataset_id}/versions/{version}/download", summary="Get dataset download URLs")
async def get_dataset_download_urls(
    dataset_id: str = Path(..., description="Dataset ID"),
    version: str = Path(..., description="Version string")
):
    """
    Get download URLs for all files in a dataset version.
    
    Returns URLs that can be used to download the dataset files.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.get_download_urls(dataset_id, version)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Failed to get download URLs"))
    
    return result

@router.post("/{dataset_id}/versions/{version}/analyze", summary="Analyze dataset")
async def analyze_dataset(
    dataset_id: str = Path(..., description="Dataset ID"),
    version: str = Path(..., description="Version string")
):
    """
    Analyze a dataset to compute statistics and quality metrics.
    
    Returns computed statistics and quality assessment results.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.analyze_dataset(dataset_id, version)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to analyze dataset"))
    
    return result

@router.post("/{dataset_id}/versions/compare", summary="Compare dataset versions")
async def compare_dataset_versions(
    dataset_id: str = Path(..., description="Dataset ID"),
    versions: List[str] = Body(..., description="List of version strings to compare")
):
    """
    Compare statistics and quality metrics between different dataset versions.
    
    Returns a comparison of statistics and metrics for the specified versions.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.compare_versions(dataset_id, versions)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to compare versions"))
    
    return result

@router.get("/search", summary="Search datasets")
async def search_datasets(
    query: str = Query(..., description="Search query string")
):
    """
    Search for datasets by name, description, or tags.
    
    Returns datasets matching the search query.
    """
    dataset_manager = get_dataset_manager()
    result = dataset_manager.search_datasets(query)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Search failed"))
    
    return result

@router.get("/types", summary="Get available dataset types")
async def get_dataset_types():
    """
    Get a list of available dataset types and their dataset counts.
    
    Returns a dictionary of dataset types with the count of datasets for each.
    """
    dataset_manager = get_dataset_manager()
    return dataset_manager.get_dataset_types()

@router.get("/formats", summary="Get available dataset formats")
async def get_dataset_formats():
    """
    Get a list of available dataset formats and their dataset counts.
    
    Returns a dictionary of dataset formats with the count of datasets for each.
    """
    dataset_manager = get_dataset_manager()
    return dataset_manager.get_dataset_formats()

@router.get("/enum/types", summary="Get supported dataset types")
async def get_supported_dataset_types():
    """
    Get a list of supported dataset types.
    
    Returns the enum values for supported dataset types.
    """
    return {
        "types": [dataset_type.value for dataset_type in DatasetType]
    }

@router.get("/enum/formats", summary="Get supported dataset formats")
async def get_supported_dataset_formats():
    """
    Get a list of supported dataset formats.
    
    Returns the enum values for supported dataset formats.
    """
    return {
        "formats": [dataset_format.value for dataset_format in DatasetFormat]
    }

@router.get("/enum/statuses", summary="Get supported dataset statuses")
async def get_supported_dataset_statuses():
    """
    Get a list of supported dataset statuses.
    
    Returns the enum values for supported dataset statuses.
    """
    return {
        "statuses": [status.value for status in DatasetStatus]
    }

@router.get("/enum/quality", summary="Get supported data quality statuses")
async def get_supported_quality_statuses():
    """
    Get a list of supported data quality statuses.
    
    Returns the enum values for supported data quality statuses.
    """
    return {
        "quality_statuses": [quality.value for quality in DataQualityStatus]
    }