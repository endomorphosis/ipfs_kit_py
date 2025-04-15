"""
Model Registry API Router

This module implements FastAPI routes for the Model Registry:
- Model registration and management
- Version creation and tracking
- Model deployment
- Search and filtering capabilities

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import tempfile
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Form, Query, Path
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ipfs_kit_py.mcp.ai.model_registry import (
    get_instance as get_model_registry,
    ModelFramework, ModelType, ModelStatus
)

# Create API router
router = APIRouter(prefix="/api/v0/ai/models", tags=["model-registry"])

# --- Helper Functions ---

async def save_upload_file_temp(upload_file: UploadFile) -> str:
    """
    Save an uploaded file to a temporary location.
    
    Args:
        upload_file: Uploaded file object
        
    Returns:
        Path to temporary file
    """
    try:
        suffix = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            content = await upload_file.read()
            temp.write(content)
            return temp.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving uploaded file: {str(e)}")

# --- API Routes ---

@router.post("/", summary="Register a new model")
async def register_model(
    name: str = Form(..., description="Model name"),
    description: str = Form("", description="Model description"),
    framework: Optional[str] = Form(None, description="ML framework used"),
    model_type: Optional[str] = Form(None, description="Type of model"),
    tags: str = Form("", description="Comma-separated list of tags"),
    owner: Optional[str] = Form(None, description="Owner or creator of the model"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string")
):
    """
    Register a new model in the registry.
    
    Returns model ID and metadata for the registered model.
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
    
    # Register model
    model_registry = get_model_registry()
    result = model_registry.register_model(
        name=name,
        description=description,
        framework=framework,
        model_type=model_type,
        tags=tag_list,
        owner=owner,
        metadata=meta_dict
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to register model"))
    
    return result

@router.get("/", summary="List models")
async def list_models(
    framework: Optional[str] = Query(None, description="Filter by framework"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    tags: Optional[str] = Query(None, description="Filter by comma-separated tags"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    List models with optional filtering.
    
    Returns a list of models matching the specified filters.
    """
    # Convert tags string to list if provided
    tag_list = None
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",")]
    
    # List models with filters
    model_registry = get_model_registry()
    result = model_registry.list_models(
        framework=framework,
        model_type=model_type,
        tags=tag_list,
        owner=owner,
        status=status
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to list models"))
    
    return result

@router.get("/{model_id}", summary="Get model details")
async def get_model(
    model_id: str = Path(..., description="Model ID")
):
    """
    Get detailed information about a specific model.
    
    Returns model metadata including available versions.
    """
    model_registry = get_model_registry()
    result = model_registry.get_model(model_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Model not found"))
    
    return result

@router.put("/{model_id}", summary="Update model metadata")
async def update_model(
    model_id: str = Path(..., description="Model ID"),
    name: Optional[str] = Form(None, description="New model name"),
    description: Optional[str] = Form(None, description="New model description"),
    framework: Optional[str] = Form(None, description="New ML framework"),
    model_type: Optional[str] = Form(None, description="New model type"),
    tags: Optional[str] = Form(None, description="New comma-separated list of tags"),
    owner: Optional[str] = Form(None, description="New owner"),
    status: Optional[str] = Form(None, description="New model status"),
    metadata: Optional[str] = Form(None, description="Additional metadata as JSON string")
):
    """
    Update model metadata.
    
    Returns updated model metadata.
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
    
    # Update model
    model_registry = get_model_registry()
    result = model_registry.update_model(
        model_id=model_id,
        name=name,
        description=description,
        framework=framework,
        model_type=model_type,
        tags=tag_list,
        owner=owner,
        status=status,
        metadata=meta_dict
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update model"))
    
    return result

@router.post("/{model_id}/versions", summary="Create a new model version")
async def create_model_version(
    model_id: str = Path(..., description="Model ID"),
    model_file: UploadFile = File(..., description="Model file to upload"),
    version: str = Form(..., description="Version string"),
    description: str = Form("", description="Version description"),
    metrics: Optional[str] = Form(None, description="Performance metrics as JSON string"),
    dataset_id: Optional[str] = Form(None, description="ID of the dataset used for training"),
    params: Optional[str] = Form(None, description="Model hyperparameters as JSON string"),
    backend: Optional[str] = Form(None, description="Storage backend to use")
):
    """
    Create a new version of a model by uploading a model file.
    
    Returns version metadata and storage information.
    """
    # Save uploaded file to temporary location
    temp_file_path = await save_upload_file_temp(model_file)
    
    try:
        # Parse metrics JSON if provided
        metrics_dict = None
        if metrics:
            try:
                metrics_dict = json.loads(metrics)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metrics JSON")
        
        # Parse params JSON if provided
        params_dict = None
        if params:
            try:
                params_dict = json.loads(params)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid params JSON")
        
        # Create model version
        model_registry = get_model_registry()
        result = model_registry.create_model_version(
            model_id=model_id,
            version=version,
            model_file=temp_file_path,
            description=description,
            metrics=metrics_dict,
            dataset_id=dataset_id,
            params=params_dict,
            backend=backend
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to create model version"))
        
        return result
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

@router.get("/{model_id}/versions/{version}", summary="Get model version details")
async def get_model_version(
    model_id: str = Path(..., description="Model ID"),
    version: str = Path(..., description="Version string")
):
    """
    Get detailed information about a specific model version.
    
    Returns version metadata including metrics and storage information.
    """
    model_registry = get_model_registry()
    result = model_registry.get_model_version(model_id, version)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Model version not found"))
    
    return result

@router.get("/{model_id}/versions/{version}/download", summary="Get model download URL")
async def get_model_download_url(
    model_id: str = Path(..., description="Model ID"),
    version: str = Path(..., description="Version string")
):
    """
    Get a download URL for a specific model version.
    
    Returns a URL that can be used to download the model file.
    """
    model_registry = get_model_registry()
    result = model_registry.get_download_url(model_id, version)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Failed to get download URL"))
    
    return result

@router.post("/{model_id}/versions/compare", summary="Compare model versions")
async def compare_model_versions(
    model_id: str = Path(..., description="Model ID"),
    versions: List[str] = Body(..., description="List of version strings to compare")
):
    """
    Compare metrics and parameters between different model versions.
    
    Returns a comparison of metrics and parameters for the specified versions.
    """
    model_registry = get_model_registry()
    result = model_registry.compare_versions(model_id, versions)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to compare versions"))
    
    return result

@router.get("/search", summary="Search models")
async def search_models(
    query: str = Query(..., description="Search query string")
):
    """
    Search for models by name, description, or tags.
    
    Returns models matching the search query.
    """
    model_registry = get_model_registry()
    result = model_registry.search_models(query)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Search failed"))
    
    return result

@router.get("/frameworks", summary="Get available frameworks")
async def get_frameworks():
    """
    Get a list of available ML frameworks and their model counts.
    
    Returns a dictionary of frameworks with the count of models for each.
    """
    model_registry = get_model_registry()
    return model_registry.get_frameworks()

@router.get("/types", summary="Get available model types")
async def get_model_types():
    """
    Get a list of available model types and their model counts.
    
    Returns a dictionary of model types with the count of models for each.
    """
    model_registry = get_model_registry()
    return model_registry.get_model_types()

@router.get("/enum/frameworks", summary="Get supported ML frameworks")
async def get_supported_frameworks():
    """
    Get a list of supported ML frameworks.
    
    Returns the enum values for supported frameworks.
    """
    return {
        "frameworks": [framework.value for framework in ModelFramework]
    }

@router.get("/enum/types", summary="Get supported model types")
async def get_supported_model_types():
    """
    Get a list of supported model types.
    
    Returns the enum values for supported model types.
    """
    return {
        "types": [model_type.value for model_type in ModelType]
    }

@router.get("/enum/statuses", summary="Get supported model statuses")
async def get_supported_model_statuses():
    """
    Get a list of supported model statuses.
    
    Returns the enum values for supported model statuses.
    """
    return {
        "statuses": [status.value for status in ModelStatus]
    }