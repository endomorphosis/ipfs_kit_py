#!/usr/bin/env python3
"""
Dataset Manager Router for MCP Server

This module provides FastAPI routes for the dataset management capabilities,
exposing a RESTful API for working with datasets.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import logging
import json
import os
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends, Path, Body

from .dataset_manager import DatasetManager, Dataset, DatasetVersion

# Configure logging
logger = logging.getLogger("mcp_dataset_manager_router")

def create_dataset_manager_router(dataset_manager: DatasetManager) -> APIRouter:
    """
    Create a FastAPI router for the dataset manager.
    
    Args:
        dataset_manager: DatasetManager instance
        
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    @router.get("/datasets", response_model=Dict[str, Any])
    async def list_datasets(
        limit: Optional[int] = Query(50, description="Maximum number of datasets to return"),
        offset: int = Query(0, description="Number of datasets to skip"),
        sort_by: str = Query("updated_at", description="Field to sort by"),
        ascending: bool = Query(False, description="Sort in ascending order"),
        tags: Optional[str] = Query(None, description="Comma-separated tags"),
        domain: Optional[str] = Query(None, description="Filter by domain"),
        search: Optional[str] = Query(None, description="Search in name and description")
    ) -> Dict[str, Any]:
        """
        List datasets with filtering and pagination.
        """
        try:
            # Convert tags to list if provided
            filter_tags = tags.split(",") if tags else None
            
            # Get datasets
            datasets = dataset_manager.list_datasets(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                ascending=ascending,
                filter_tags=filter_tags,
                filter_domain=domain,
                search_term=search
            )
            
            # Convert to dict representation
            dataset_dicts = [d.to_dict() for d in datasets]
            
            return {
                "datasets": dataset_dicts,
                "count": len(dataset_dicts),
                "offset": offset,
                "limit": limit,
                "total": dataset_manager.get_dataset_count()
            }
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")
    
    @router.post("/datasets", response_model=Dict[str, Any])
    async def create_dataset(
        name: str = Form(..., description="Dataset name"),
        description: Optional[str] = Form(None, description="Dataset description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        domain: Optional[str] = Form(None, description="Dataset domain"),
        license: Optional[str] = Form(None, description="Dataset license"),
        source: Optional[str] = Form(None, description="Dataset source"),
        user_id: Optional[str] = Form(None, description="User ID"),
        metadata: Optional[str] = Form(None, description="JSON metadata")
    ) -> Dict[str, Any]:
        """
        Create a new dataset.
        """
        try:
            # Parse tags
            tag_list = tags.split(",") if tags else None
            
            # Parse metadata
            metadata_dict = json.loads(metadata) if metadata else None
            
            # Create dataset
            dataset = dataset_manager.create_dataset(
                name=name,
                description=description,
                tags=tag_list,
                domain=domain,
                license=license,
                source=source,
                user_id=user_id,
                metadata=metadata_dict
            )
            
            return dataset.to_dict()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create dataset: {str(e)}")
    
    @router.get("/datasets/{dataset_id}", response_model=Dict[str, Any])
    async def get_dataset(
        dataset_id: str = Path(..., description="Dataset ID"),
        include_versions: bool = Query(False, description="Include version data")
    ) -> Dict[str, Any]:
        """
        Get dataset by ID.
        """
        try:
            dataset = dataset_manager.get_dataset(dataset_id)
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            return dataset.to_dict(include_versions=include_versions)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting dataset: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get dataset: {str(e)}")
    
    @router.post("/datasets/{dataset_id}/versions", response_model=Dict[str, Any])
    async def create_dataset_version(
        dataset_id: str = Path(..., description="Dataset ID"),
        file: UploadFile = File(..., description="Dataset file"),
        description: Optional[str] = Form(None, description="Version description"),
        tags: Optional[str] = Form(None, description="Comma-separated tags"),
        format: Optional[str] = Form(None, description="Dataset format"),
        user_id: Optional[str] = Form(None, description="User ID"),
        metadata: Optional[str] = Form(None, description="JSON metadata"),
        parent_version_id: Optional[str] = Form(None, description="Parent version ID")
    ) -> Dict[str, Any]:
        """
        Create a new version of a dataset.
        """
        try:
            # Parse tags
            tag_list = tags.split(",") if tags else None
            
            # Parse metadata
            metadata_dict = json.loads(metadata) if metadata else None
            
            # Save uploaded file to a temporary location
            filename = file.filename or "uploaded_file"
            extension = os.path.splitext(filename)[1] if filename else ""
            temp_file = dataset_manager.storage_path / "temp" / f"{uuid.uuid4()}{extension}"
            os.makedirs(os.path.dirname(str(temp_file)), exist_ok=True)
            
            with open(temp_file, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Create version
            version = dataset_manager.create_dataset_version(
                dataset_id=dataset_id,
                file_path=temp_file,
                description=description,
                tags=tag_list,
                format=format or (os.path.splitext(filename)[1].lstrip('.') if filename else ""),
                user_id=user_id,
                metadata=metadata_dict,
                parent_version_id=parent_version_id,
                original_filename=filename
            )
            
            # Remove temporary file
            os.unlink(temp_file)
            
            if not version:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            return version.to_dict()
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Error creating dataset version: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create dataset version: {str(e)}")
    
    @router.get("/datasets/{dataset_id}/versions", response_model=Dict[str, Any])
    async def list_dataset_versions(
        dataset_id: str = Path(..., description="Dataset ID"),
        limit: Optional[int] = Query(50, description="Maximum number of versions to return"),
        offset: int = Query(0, description="Number of versions to skip")
    ) -> Dict[str, Any]:
        """
        List versions of a dataset.
        """
        try:
            dataset = dataset_manager.get_dataset(dataset_id)
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            versions = dataset.get_versions(limit=limit, offset=offset)
            version_dicts = [v.to_dict() for v in versions]
            
            return {
                "dataset_id": dataset_id,
                "versions": version_dicts,
                "count": len(version_dicts),
                "offset": offset,
                "limit": limit,
                "total": dataset.version_count
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing dataset versions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list dataset versions: {str(e)}")
    
    @router.get("/datasets/{dataset_id}/versions/{version_id}", response_model=Dict[str, Any])
    async def get_dataset_version(
        dataset_id: str = Path(..., description="Dataset ID"),
        version_id: str = Path(..., description="Version ID")
    ) -> Dict[str, Any]:
        """
        Get a specific version of a dataset.
        """
        try:
            version = dataset_manager.get_dataset_version(dataset_id, version_id)
            if not version:
                raise HTTPException(status_code=404, detail=f"Version {version_id} not found for dataset {dataset_id}")
            
            return version.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting dataset version: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get dataset version: {str(e)}")
    
    @router.get("/datasets/{dataset_id}/lineage", response_model=Dict[str, Any])
    async def get_dataset_lineage(
        dataset_id: str = Path(..., description="Dataset ID")
    ) -> Dict[str, Any]:
        """
        Get lineage graph for dataset versions.
        """
        try:
            dataset = dataset_manager.get_dataset(dataset_id)
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            lineage = dataset.get_lineage_graph()
            
            return {
                "dataset_id": dataset_id,
                "lineage": lineage
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting dataset lineage: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get dataset lineage: {str(e)}")
    
    @router.post("/datasets/{dataset_id}/versions/{version_id}/quality", response_model=Dict[str, Any])
    async def update_quality_metrics(
        dataset_id: str = Path(..., description="Dataset ID"),
        version_id: str = Path(..., description="Version ID"),
        metrics: Dict[str, Any] = Body(..., description="Quality metrics")
    ) -> Dict[str, Any]:
        """
        Update quality metrics for a dataset version.
        """
        try:
            version = dataset_manager.get_dataset_version(dataset_id, version_id)
            if not version:
                raise HTTPException(status_code=404, detail=f"Version {version_id} not found for dataset {dataset_id}")
            
            # Update metrics
            version.update_quality_metrics(metrics)
            
            # Save changes
            dataset = dataset_manager.get_dataset(dataset_id)
            if dataset:
                dataset_manager._save_dataset_metadata(dataset)
            
            return version.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating quality metrics: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update quality metrics: {str(e)}")
    
    return router
