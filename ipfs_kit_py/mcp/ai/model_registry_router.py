#!/usr/bin/env python3
"""
Model Registry Router for MCP Server

This module provides FastAPI routes for the model registry capabilities,
exposing a RESTful API for working with machine learning models.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import logging
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends, Path, Body

from .model_registry import ModelRegistry, Model, ModelVersion

# Configure logging
logger = logging.getLogger("mcp_model_registry_router")

def create_model_registry_router(model_registry: ModelRegistry) -> APIRouter:
    """
    Create a FastAPI router for the model registry.
    
    Args:
        model_registry: ModelRegistry instance
        
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.get("/models", response_model=Dict[str, Any])
    async def list_models(
        limit: Optional[int] = Query(50, description="Maximum number of models to return"),
        offset: int = Query(0, description="Number of models to skip"),
        sort_by: str = Query("updated_at", description="Field to sort by"),
        ascending: bool = Query(False, description="Sort in ascending order"),
        tags: Optional[str] = Query(None, description="Comma-separated tags"),
        framework: Optional[str] = Query(None, description="Filter by framework"),
        search: Optional[str] = Query(None, description="Search in name and description")
    ) -> Dict[str, Any]:
        """
        List models with filtering and pagination.
        """
        try:
            # Convert tags to list if provided
            filter_tags = tags.split(",") if tags else None
            
            # Get models with correct parameter names
            models = model_registry.list_models(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                ascending=ascending,
                filter_tags=filter_tags,
                filter_framework=framework,
                search_term=search
            )
            
            # Convert to dict representation
            model_dicts = [m.to_dict() for m in models]
            
            return {
                "models": model_dicts,
                "count": len(model_dicts),
                "offset": offset,
                "limit": limit
            }
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")
    
    @router.post("/models", response_model=Dict[str, Any])
    async def create_model(
        name: str = Form(..., description="Model name"),
        description: Optional[str] = Form(None, description="Model description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        framework: Optional[str] = Form(None, description="Model framework"),
        user_id: Optional[str] = Form(None, description="User ID"),
        metadata: Optional[str] = Form(None, description="JSON metadata")
    ) -> Dict[str, Any]:
        """
        Create a new model.
        """
        try:
            # Parse tags
            tag_list = tags.split(",") if tags else None
            
            # Parse metadata
            metadata_dict = json.loads(metadata) if metadata else None
            
            # Create model
            model = model_registry.create_model(
                name=name,
                description=description,
                tags=tag_list,
                framework=framework,
                user_id=user_id,
                metadata=metadata_dict
            )
            
            return model.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating model: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create model: {str(e)}")
    
    @router.get("/models/{model_id}", response_model=Dict[str, Any])
    async def get_model(
        model_id: str = Path(..., description="Model ID"),
        include_versions: bool = Query(False, description="Include version data")
    ) -> Dict[str, Any]:
        """
        Get model by ID.
        """
        try:
            model = model_registry.get_model(model_id)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
            
            return model.to_dict(include_versions=include_versions)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get model: {str(e)}")
    
    @router.post("/models/{model_id}/versions", response_model=Dict[str, Any])
    async def create_model_version(
        model_id: str = Path(..., description="Model ID"),
        file: Optional[UploadFile] = File(None, description="Model file"),
        description: Optional[str] = Form(None, description="Version description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        framework: Optional[str] = Form(None, description="Model framework"),
        user_id: Optional[str] = Form(None, description="User ID"),
        metrics: Optional[str] = Form(None, description="Performance metrics as JSON"),
        metadata: Optional[str] = Form(None, description="JSON metadata"),
        storage_backend: Optional[str] = Form(None, description="Storage backend identifier"),
        storage_uri: Optional[str] = Form(None, description="Storage URI")
    ) -> Dict[str, Any]:
        """
        Create a new version of a model.
        """
        try:
            # Parse tags
            tag_list = tags.split(",") if tags else None
            
            # Parse metadata
            metadata_dict = json.loads(metadata) if metadata else None
            
            # Parse metrics
            metrics_dict = json.loads(metrics) if metrics else None
            
            # Handle file upload
            temp_file = None
            if file:
                # Save uploaded file to a temporary location
                filename = file.filename or "uploaded_model"
                extension = os.path.splitext(filename)[1] if filename else ""
                temp_file = os.path.join(model_registry.storage_path, "temp", f"{uuid.uuid4()}{extension}")
                os.makedirs(os.path.dirname(temp_file), exist_ok=True)
                
                try:
                    with open(temp_file, "wb") as f:
                        content = await file.read()
                        f.write(content)
                except Exception as e:
                    logger.error(f"Error saving uploaded file: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
            
            # Create version with parameters that match the expected signature
            version = model_registry.create_model_version(
                model_id=model_id,
                model_data_path=temp_file if temp_file else None,
                metadata=metadata_dict,
                metrics=metrics_dict,
                tags=tag_list,
                framework=framework,
                description=description,
                user_id=user_id,
                storage_backend=storage_backend,
                storage_uri=storage_uri
            )
            
            # Remove temporary file if created
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            
            if not version:
                raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
            
            return version.to_dict()
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating model version: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create model version: {str(e)}")
    
    @router.get("/models/{model_id}/versions", response_model=Dict[str, Any])
    async def list_model_versions(
        model_id: str = Path(..., description="Model ID"),
        limit: Optional[int] = Query(50, description="Maximum number of versions to return"),
        offset: int = Query(0, description="Number of versions to skip")
    ) -> Dict[str, Any]:
        """
        List versions of a model.
        """
        try:
            model = model_registry.get_model(model_id)
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
            
            versions = model.get_versions(limit=limit, offset=offset)
            version_dicts = [v.to_dict() for v in versions]
            
            return {
                "model_id": model_id,
                "versions": version_dicts,
                "count": len(version_dicts),
                "offset": offset,
                "limit": limit,
                "total": model.version_count
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing model versions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list model versions: {str(e)}")
    
    @router.get("/models/{model_id}/versions/{version_id}", response_model=Dict[str, Any])
    async def get_model_version(
        model_id: str = Path(..., description="Model ID"),
        version_id: str = Path(..., description="Version ID")
    ) -> Dict[str, Any]:
        """
        Get a specific version of a model.
        """
        try:
            version = model_registry.get_model_version(model_id, version_id)
            if not version:
                raise HTTPException(status_code=404, detail=f"Version {version_id} not found for model {model_id}")
            
            return version.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting model version: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get model version: {str(e)}")
    
    @router.post("/models/{model_id}/versions/{version_id}/metrics", response_model=Dict[str, Any])
    async def update_metrics(
        model_id: str = Path(..., description="Model ID"),
        version_id: str = Path(..., description="Version ID"),
        metrics: Dict[str, float] = Body(..., description="Performance metrics")
    ) -> Dict[str, Any]:
        """
        Update metrics for a model version.
        """
        try:
            version = model_registry.get_model_version(model_id, version_id)
            if not version:
                raise HTTPException(status_code=404, detail=f"Version {version_id} not found for model {model_id}")
            
            # Update metrics
            version.update_metrics(metrics)
            
            # Save changes
            model = model_registry.get_model(model_id)
            if model:
                model_registry._save_model_metadata(model)
            else:
                logger.error(f"Model {model_id} not found when saving metrics")
            
            return version.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update metrics: {str(e)}")
    
    @router.post("/models/upload", response_model=Dict[str, Any])
    async def upload_model(
        name: str = Form(..., description="Model name"),
        file: UploadFile = File(..., description="Model file"),
        description: Optional[str] = Form(None, description="Model description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        framework: Optional[str] = Form(None, description="Model framework"),
        user_id: Optional[str] = Form(None, description="User ID"),
        metadata: Optional[str] = Form(None, description="JSON metadata"),
        metrics: Optional[str] = Form(None, description="Performance metrics as JSON"),
        version_description: Optional[str] = Form(None, description="Description for the first version")
    ) -> Dict[str, Any]:
        """
        Create a new model and upload its first version in one operation.
        """
        try:
            # Parse tags
            tag_list = tags.split(",") if tags else None
            
            # Parse metadata
            metadata_dict = json.loads(metadata) if metadata else None
            
            # Parse metrics
            metrics_dict = json.loads(metrics) if metrics else None
            
            # Save uploaded file to a temporary location
            filename = file.filename or "uploaded_model"
            extension = os.path.splitext(filename)[1] if filename else ""
            temp_file = os.path.join(model_registry.storage_path, "temp", f"{uuid.uuid4()}{extension}")
            os.makedirs(os.path.dirname(temp_file), exist_ok=True)
            
            try:
                with open(temp_file, "wb") as f:
                    content = await file.read()
                    f.write(content)
            except Exception as e:
                logger.error(f"Error saving uploaded file: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
            
            # Upload model with parameters that match the expected signature
            model, version = model_registry.upload_model(
                name=name,
                model_data_path=temp_file,
                description=description,
                tags=tag_list,
                framework=framework,
                user_id=user_id,
                metadata=metadata_dict,
                metrics=metrics_dict,
                version_description=version_description
            )
            
            # Remove temporary file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            
            if not model or not version:
                raise HTTPException(status_code=500, detail="Failed to upload model")
            
            return {
                "model": model.to_dict(),
                "version": version.to_dict()
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error uploading model: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload model: {str(e)}")
    
    return router
