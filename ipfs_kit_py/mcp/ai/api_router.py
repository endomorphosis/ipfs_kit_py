"""
AI/ML API Router for MCP Server

This module provides API endpoints for AI/ML integration capabilities:
- Model Registry operations
- Dataset management
- Model deployment
- Inference services

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, File, UploadFile, Form
from pydantic import BaseModel, Field

# Import the model registry module
try:
    from ..ai.model_registry import (
        ModelRegistry, ModelMetadata, ModelDeployment,
        ModelFramework, ModelTask, ModelStatus, get_instance as get_model_registry
    )
except ImportError:
    # For development/testing without the full module
    ModelRegistry = object
    ModelMetadata = object
    ModelDeployment = object
    ModelFramework = object
    ModelTask = object
    ModelStatus = object
    get_model_registry = lambda: None

from ..models.responses import StandardResponse, ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_ai_api")

# Pydantic models for API requests/responses

class ModelInfo(BaseModel):
    """Basic model information."""
    id: str
    name: str
    version: str
    framework: str
    task: Optional[str] = None
    description: Optional[str] = None
    status: str
    created_at: float
    updated_at: float

class ModelDetail(ModelInfo):
    """Detailed model information."""
    tags: List[str] = []
    metrics: Dict[str, float] = {}
    params: Dict[str, Any] = {}
    dependencies: Dict[str, str] = {}
    storage_uri: Optional[str] = None
    storage_backend: Optional[str] = None
    size_bytes: int = 0
    checksum: Optional[str] = None
    parent_models: List[str] = []

class DeploymentInfo(BaseModel):
    """Basic deployment information."""
    id: str
    model_id: str
    name: str
    environment: str
    status: str
    is_active: bool
    created_at: float
    updated_at: float
    deployed_at: Optional[float] = None
    endpoint: Optional[str] = None

class DeploymentDetail(DeploymentInfo):
    """Detailed deployment information."""
    description: Optional[str] = None
    config: Dict[str, Any] = {}
    scaling: Dict[str, Any] = {}
    resources: Dict[str, Any] = {}
    monitoring: Dict[str, Any] = {}
    performance: Dict[str, Any] = {}
    health: Dict[str, Any] = {}

class ModelCreateRequest(BaseModel):
    """Request to create a new model."""
    name: str
    version: Optional[str] = None
    framework: str
    description: Optional[str] = None
    task: Optional[str] = None
    tags: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None
    params: Optional[Dict[str, Any]] = None
    dependencies: Optional[Dict[str, str]] = None
    parent_models: Optional[List[str]] = None

class ModelUpdateRequest(BaseModel):
    """Request to update a model."""
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None
    status: Optional[str] = None

class DeploymentCreateRequest(BaseModel):
    """Request to create a model deployment."""
    name: str
    environment: str
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    scaling: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None

class DeploymentUpdateRequest(BaseModel):
    """Request to update a deployment."""
    description: Optional[str] = None
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    scaling: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None

# API Router

def create_ai_api_router(
    model_registry: Optional[ModelRegistry] = None,
    get_current_user = None  # Optional dependency for authenticated endpoints
) -> APIRouter:
    """
    Create an API router for AI/ML integration.
    
    Args:
        model_registry: ModelRegistry instance
        get_current_user: Optional dependency for authenticated endpoints
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter(tags=["AI/ML Integration"])
    
    # Use provided model registry or get singleton instance
    registry = model_registry or get_model_registry()
    
    if registry is None:
        logger.warning("Model registry not available - AI/ML endpoints will return errors")
    
    # Model Registry endpoints
    
    @router.get(
        "/models",
        response_model=StandardResponse,
        summary="List Models",
        description="List models in the registry, with optional filtering."
    )
    async def list_models(
        name: Optional[str] = Query(None, description="Filter by name"),
        framework: Optional[str] = Query(None, description="Filter by framework"),
        task: Optional[str] = Query(None, description="Filter by task"),
        status: Optional[str] = Query(None, description="Filter by status"),
        tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """List models in the registry."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Parse tags if provided
            tag_list = None
            if tags:
                tag_list = [tag.strip() for tag in tags.split(",")]
            
            # Get models from registry
            models = registry.list_models(
                name=name,
                framework=framework,
                task=task,
                status=status,
                tags=tag_list
            )
            
            # Convert to response format
            model_info = [
                ModelInfo(
                    id=model.id,
                    name=model.name,
                    version=model.version,
                    framework=model.framework.value,
                    task=model.task.value if model.task else None,
                    description=model.description,
                    status=model.status.value,
                    created_at=model.created_at,
                    updated_at=model.updated_at
                )
                for model in models
            ]
            
            return StandardResponse(
                success=True,
                message=f"Found {len(model_info)} models",
                data={"models": model_info}
            )
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to list models: {str(e)}",
                error_code="model_list_error"
            )
    
    @router.get(
        "/models/{model_id}",
        response_model=StandardResponse,
        summary="Get Model",
        description="Get detailed information about a specific model."
    )
    async def get_model(
        model_id: str = Path(..., description="Model ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Get a specific model by ID."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get model from registry
            model = registry.get_model(model_id)
            
            if not model:
                return ErrorResponse(
                    success=False,
                    message=f"Model {model_id} not found",
                    error_code="model_not_found"
                )
            
            # Convert to response format
            model_detail = ModelDetail(
                id=model.id,
                name=model.name,
                version=model.version,
                framework=model.framework.value,
                task=model.task.value if model.task else None,
                description=model.description,
                tags=model.tags,
                metrics=model.metrics,
                params=model.params,
                dependencies=model.dependencies,
                storage_uri=model.storage_uri,
                storage_backend=model.storage_backend,
                size_bytes=model.size_bytes,
                checksum=model.checksum,
                status=model.status.value,
                created_at=model.created_at,
                updated_at=model.updated_at,
                parent_models=model.parent_models
            )
            
            return StandardResponse(
                success=True,
                message=f"Found model {model_id}",
                data={"model": model_detail}
            )
        except Exception as e:
            logger.error(f"Error getting model {model_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to get model: {str(e)}",
                error_code="model_get_error"
            )
    
    @router.post(
        "/models",
        response_model=StandardResponse,
        summary="Create Model",
        description="Register a new model in the registry."
    )
    async def create_model(
        request: ModelCreateRequest,
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Create a new model."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Register model in registry
            model = registry.register_model(
                name=request.name,
                version=request.version,
                framework=request.framework,
                description=request.description,
                task=request.task,
                tags=request.tags,
                metrics=request.metrics,
                params=request.params,
                dependencies=request.dependencies,
                parent_models=request.parent_models
            )
            
            # Convert to response format
            model_detail = ModelDetail(
                id=model.id,
                name=model.name,
                version=model.version,
                framework=model.framework.value,
                task=model.task.value if model.task else None,
                description=model.description,
                tags=model.tags,
                metrics=model.metrics,
                params=model.params,
                dependencies=model.dependencies,
                storage_uri=model.storage_uri,
                storage_backend=model.storage_backend,
                size_bytes=model.size_bytes,
                checksum=model.checksum,
                status=model.status.value,
                created_at=model.created_at,
                updated_at=model.updated_at,
                parent_models=model.parent_models
            )
            
            return StandardResponse(
                success=True,
                message=f"Created model {model.id}",
                data={"model": model_detail}
            )
        except Exception as e:
            logger.error(f"Error creating model: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to create model: {str(e)}",
                error_code="model_create_error"
            )
    
    @router.post(
        "/models/{model_id}/upload",
        response_model=StandardResponse,
        summary="Upload Model Files",
        description="Upload model files to the registry."
    )
    async def upload_model(
        model_id: str = Path(..., description="Model ID"),
        file: UploadFile = File(..., description="Model file to upload"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Upload model files."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Check if model exists
            model = registry.get_model(model_id)
            if not model:
                return ErrorResponse(
                    success=False,
                    message=f"Model {model_id} not found",
                    error_code="model_not_found"
                )
            
            # Save uploaded file to temporary location
            import tempfile
            import os
            import shutil
            
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                shutil.copyfileobj(file.file, temp_file)
            
            try:
                # Process model file
                # (In a real implementation, this would use the actual model registry's upload method)
                import hashlib
                import os
                
                # Calculate file size and checksum
                size_bytes = os.path.getsize(temp_path)
                
                # Calculate checksum
                sha256_hash = hashlib.sha256()
                with open(temp_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                checksum = sha256_hash.hexdigest()
                
                # Update model storage info
                # (This is a simplified simulation of the storage process)
                storage_path = os.path.join(registry.storage_path, "models", model.name, model.version)
                os.makedirs(storage_path, exist_ok=True)
                
                dest_path = os.path.join(storage_path, file.filename)
                shutil.copy2(temp_path, dest_path)
                
                # Update storage info in model metadata
                model.update_storage_info(
                    uri=f"local://{dest_path}",
                    backend="local",
                    size_bytes=size_bytes,
                    checksum=checksum
                )
                
                return StandardResponse(
                    success=True,
                    message=f"Uploaded model file for {model_id}",
                    data={
                        "filename": file.filename,
                        "size_bytes": size_bytes,
                        "checksum": checksum
                    }
                )
            finally:
                # Clean up temporary file
                os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Error uploading model file for {model_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to upload model file: {str(e)}",
                error_code="model_upload_error"
            )
    
    @router.put(
        "/models/{model_id}",
        response_model=StandardResponse,
        summary="Update Model",
        description="Update model information in the registry."
    )
    async def update_model(
        model_id: str = Path(..., description="Model ID"),
        request: ModelUpdateRequest = None,
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Update a model."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Convert request to kwargs
            kwargs = {}
            if request:
                if request.description is not None:
                    kwargs["description"] = request.description
                if request.tags is not None:
                    kwargs["tags"] = request.tags
                if request.metrics is not None:
                    kwargs["metrics"] = request.metrics
                if request.status is not None:
                    kwargs["status"] = ModelStatus(request.status)
            
            # Update model in registry
            model = registry.update_model(model_id, **kwargs)
            
            if not model:
                return ErrorResponse(
                    success=False,
                    message=f"Model {model_id} not found",
                    error_code="model_not_found"
                )
            
            # Convert to response format
            model_detail = ModelDetail(
                id=model.id,
                name=model.name,
                version=model.version,
                framework=model.framework.value,
                task=model.task.value if model.task else None,
                description=model.description,
                tags=model.tags,
                metrics=model.metrics,
                params=model.params,
                dependencies=model.dependencies,
                storage_uri=model.storage_uri,
                storage_backend=model.storage_backend,
                size_bytes=model.size_bytes,
                checksum=model.checksum,
                status=model.status.value,
                created_at=model.created_at,
                updated_at=model.updated_at,
                parent_models=model.parent_models
            )
            
            return StandardResponse(
                success=True,
                message=f"Updated model {model_id}",
                data={"model": model_detail}
            )
        except Exception as e:
            logger.error(f"Error updating model {model_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to update model: {str(e)}",
                error_code="model_update_error"
            )
    
    @router.delete(
        "/models/{model_id}",
        response_model=StandardResponse,
        summary="Delete Model",
        description="Delete a model from the registry."
    )
    async def delete_model(
        model_id: str = Path(..., description="Model ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Delete a model."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Delete model from registry
            success = registry.delete_model(model_id)
            
            if not success:
                return ErrorResponse(
                    success=False,
                    message=f"Model {model_id} not found",
                    error_code="model_not_found"
                )
            
            return StandardResponse(
                success=True,
                message=f"Deleted model {model_id}",
                data={"model_id": model_id}
            )
        except Exception as e:
            logger.error(f"Error deleting model {model_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to delete model: {str(e)}",
                error_code="model_delete_error"
            )
    
    # Model Deployment endpoints
    
    @router.get(
        "/deployments",
        response_model=StandardResponse,
        summary="List Deployments",
        description="List model deployments, with optional filtering."
    )
    async def list_deployments(
        model_id: Optional[str] = Query(None, description="Filter by model ID"),
        environment: Optional[str] = Query(None, description="Filter by environment"),
        active_only: bool = Query(False, description="Only show active deployments"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """List model deployments."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get deployments from registry
            deployments = registry.list_deployments(
                model_id=model_id,
                environment=environment,
                active_only=active_only
            )
            
            # Convert to response format
            deployment_info = [
                DeploymentInfo(
                    id=deployment.id,
                    model_id=deployment.model_id,
                    name=deployment.name,
                    environment=deployment.environment,
                    status=deployment.status,
                    is_active=deployment.is_active,
                    created_at=deployment.created_at,
                    updated_at=deployment.updated_at,
                    deployed_at=deployment.deployed_at,
                    endpoint=deployment.endpoint
                )
                for deployment in deployments
            ]
            
            return StandardResponse(
                success=True,
                message=f"Found {len(deployment_info)} deployments",
                data={"deployments": deployment_info}
            )
        except Exception as e:
            logger.error(f"Error listing deployments: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to list deployments: {str(e)}",
                error_code="deployment_list_error"
            )
    
    @router.get(
        "/deployments/{deployment_id}",
        response_model=StandardResponse,
        summary="Get Deployment",
        description="Get detailed information about a specific deployment."
    )
    async def get_deployment(
        deployment_id: str = Path(..., description="Deployment ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Get a specific deployment by ID."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get deployment from registry
            deployment = registry.get_deployment(deployment_id)
            
            if not deployment:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            # Convert to response format
            deployment_detail = DeploymentDetail(
                id=deployment.id,
                model_id=deployment.model_id,
                name=deployment.name,
                environment=deployment.environment,
                description=deployment.description,
                config=deployment.config,
                scaling=deployment.scaling,
                resources=deployment.resources,
                monitoring=deployment.monitoring,
                status=deployment.status,
                is_active=deployment.is_active,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
                deployed_at=deployment.deployed_at,
                endpoint=deployment.endpoint,
                performance=deployment.performance,
                health=deployment.health
            )
            
            return StandardResponse(
                success=True,
                message=f"Found deployment {deployment_id}",
                data={"deployment": deployment_detail}
            )
        except Exception as e:
            logger.error(f"Error getting deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to get deployment: {str(e)}",
                error_code="deployment_get_error"
            )
    
    @router.post(
        "/models/{model_id}/deployments",
        response_model=StandardResponse,
        summary="Create Deployment",
        description="Create a new deployment for a model."
    )
    async def create_deployment(
        model_id: str = Path(..., description="Model ID"),
        request: DeploymentCreateRequest = None,
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Create a new deployment for a model."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Check if model exists
            model = registry.get_model(model_id)
            if not model:
                return ErrorResponse(
                    success=False,
                    message=f"Model {model_id} not found",
                    error_code="model_not_found"
                )
            
            # Create deployment
            deployment = registry.create_deployment(
                model_id=model_id,
                name=request.name,
                environment=request.environment,
                description=request.description,
                config=request.config,
                scaling=request.scaling,
                resources=request.resources,
                monitoring=request.monitoring
            )
            
            # Convert to response format
            deployment_detail = DeploymentDetail(
                id=deployment.id,
                model_id=deployment.model_id,
                name=deployment.name,
                environment=deployment.environment,
                description=deployment.description,
                config=deployment.config,
                scaling=deployment.scaling,
                resources=deployment.resources,
                monitoring=deployment.monitoring,
                status=deployment.status,
                is_active=deployment.is_active,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
                deployed_at=deployment.deployed_at,
                endpoint=deployment.endpoint,
                performance=deployment.performance,
                health=deployment.health
            )
            
            return StandardResponse(
                success=True,
                message=f"Created deployment {deployment.id} for model {model_id}",
                data={"deployment": deployment_detail}
            )
        except Exception as e:
            logger.error(f"Error creating deployment for model {model_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to create deployment: {str(e)}",
                error_code="deployment_create_error"
            )
    
    @router.put(
        "/deployments/{deployment_id}",
        response_model=StandardResponse,
        summary="Update Deployment",
        description="Update deployment information."
    )
    async def update_deployment(
        deployment_id: str = Path(..., description="Deployment ID"),
        request: DeploymentUpdateRequest = None,
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Update a deployment."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Convert request to kwargs
            kwargs = {}
            if request:
                if request.description is not None:
                    kwargs["description"] = request.description
                if request.config is not None:
                    kwargs["config"] = request.config
                if request.scaling is not None:
                    kwargs["scaling"] = request.scaling
                if request.resources is not None:
                    kwargs["resources"] = request.resources
                if request.monitoring is not None:
                    kwargs["monitoring"] = request.monitoring
                if request.status is not None:
                    kwargs["status"] = request.status
            
            # Update deployment in registry
            deployment = registry.update_deployment(deployment_id, **kwargs)
            
            if not deployment:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            # Convert to response format
            deployment_detail = DeploymentDetail(
                id=deployment.id,
                model_id=deployment.model_id,
                name=deployment.name,
                environment=deployment.environment,
                description=deployment.description,
                config=deployment.config,
                scaling=deployment.scaling,
                resources=deployment.resources,
                monitoring=deployment.monitoring,
                status=deployment.status,
                is_active=deployment.is_active,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
                deployed_at=deployment.deployed_at,
                endpoint=deployment.endpoint,
                performance=deployment.performance,
                health=deployment.health
            )
            
            return StandardResponse(
                success=True,
                message=f"Updated deployment {deployment_id}",
                data={"deployment": deployment_detail}
            )
        except Exception as e:
            logger.error(f"Error updating deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to update deployment: {str(e)}",
                error_code="deployment_update_error"
            )
    
    @router.delete(
        "/deployments/{deployment_id}",
        response_model=StandardResponse,
        summary="Delete Deployment",
        description="Delete a deployment."
    )
    async def delete_deployment(
        deployment_id: str = Path(..., description="Deployment ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Delete a deployment."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Delete deployment from registry
            success = registry.delete_deployment(deployment_id)
            
            if not success:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            return StandardResponse(
                success=True,
                message=f"Deleted deployment {deployment_id}",
                data={"deployment_id": deployment_id}
            )
        except Exception as e:
            logger.error(f"Error deleting deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to delete deployment: {str(e)}",
                error_code="deployment_delete_error"
            )
    
    @router.post(
        "/deployments/{deployment_id}/activate",
        response_model=StandardResponse,
        summary="Activate Deployment",
        description="Activate a deployment."
    )
    async def activate_deployment(
        deployment_id: str = Path(..., description="Deployment ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Activate a deployment."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get deployment
            deployment = registry.get_deployment(deployment_id)
            
            if not deployment:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            # Update deployment status
            deployment.update_status("deployed", {"activated_by": getattr(current_user, "username", "unknown")})
            deployment.is_active = True
            deployment.deployed_at = time.time()
            
            # In a real implementation, this would include actual deployment logic
            # For now, we'll just simulate endpoint creation
            deployment.endpoint = f"/api/v0/inference/{deployment_id}"
            
            # Save updated deployment
            registry.update_deployment(deployment_id, 
                                       status=deployment.status,
                                       is_active=deployment.is_active,
                                       deployed_at=deployment.deployed_at,
                                       endpoint=deployment.endpoint)
            
            return StandardResponse(
                success=True,
                message=f"Activated deployment {deployment_id}",
                data={
                    "deployment_id": deployment_id,
                    "status": deployment.status,
                    "endpoint": deployment.endpoint
                }
            )
        except Exception as e:
            logger.error(f"Error activating deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to activate deployment: {str(e)}",
                error_code="deployment_activation_error"
            )
    
    @router.post(
        "/deployments/{deployment_id}/deactivate",
        response_model=StandardResponse,
        summary="Deactivate Deployment",
        description="Deactivate a deployment."
    )
    async def deactivate_deployment(
        deployment_id: str = Path(..., description="Deployment ID"),
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Deactivate a deployment."""
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get deployment
            deployment = registry.get_deployment(deployment_id)
            
            if not deployment:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            # Update deployment status
            deployment.update_status("stopped", {"deactivated_by": getattr(current_user, "username", "unknown")})
            deployment.is_active = False
            
            # Save updated deployment
            registry.update_deployment(deployment_id, 
                                       status=deployment.status,
                                       is_active=deployment.is_active)
            
            return StandardResponse(
                success=True,
                message=f"Deactivated deployment {deployment_id}",
                data={
                    "deployment_id": deployment_id,
                    "status": deployment.status
                }
            )
        except Exception as e:
            logger.error(f"Error deactivating deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to deactivate deployment: {str(e)}",
                error_code="deployment_deactivation_error"
            )
    
    # Inference endpoints (placeholder for future implementation)
    
    @router.post(
        "/inference/{deployment_id}",
        response_model=StandardResponse,
        summary="Run Inference",
        description="Run inference using a deployed model. This is a placeholder endpoint."
    )
    async def run_inference(
        deployment_id: str = Path(..., description="Deployment ID"),
        input_data: Dict[str, Any] = None,
        current_user = Depends(get_current_user) if get_current_user else None
    ):
        """Run inference using a deployed model."""
        # This is a placeholder endpoint that would be implemented
        # with actual model serving capabilities in a real system
        
        if registry is None:
            return ErrorResponse(
                success=False,
                message="Model registry not available",
                error_code="registry_unavailable"
            )
        
        try:
            # Get deployment
            deployment = registry.get_deployment(deployment_id)
            
            if not deployment:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} not found",
                    error_code="deployment_not_found"
                )
            
            if not deployment.is_active:
                return ErrorResponse(
                    success=False,
                    message=f"Deployment {deployment_id} is not active",
                    error_code="deployment_inactive"
                )
            
            # Get model
            model = registry.get_model(deployment.model_id)
            if not model:
                return ErrorResponse(
                    success=False,
                    message=f"Model {deployment.model_id} not found",
                    error_code="model_not_found"
                )
            
            # In a real implementation, this would load and run the model
            # For now, we'll just return a placeholder response
            
            # Simulate inference latency
            import time
            import random
            time.sleep(random.uniform(0.1, 0.5))
            
            # Return mock result
            return StandardResponse(
                success=True,
                message=f"Inference completed for deployment {deployment_id}",
                data={
                    "deployment_id": deployment_id,
                    "model_id": deployment.model_id,
                    "model_name": model.name,
                    "model_version": model.version,
                    "input_shape": {"inputs": len(input_data) if input_data else 0},
                    "results": {
                        "predictions": [random.random() for _ in range(5)],
                        "processing_time_ms": random.randint(50, 500)
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error running inference with deployment {deployment_id}: {e}")
            return ErrorResponse(
                success=False,
                message=f"Failed to run inference: {str(e)}",
                error_code="inference_error"
            )
    
    return router