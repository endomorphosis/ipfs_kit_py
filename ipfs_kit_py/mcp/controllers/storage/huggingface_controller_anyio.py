"""HuggingFace Controller AnyIO Module

This module provides AnyIO-compatible HuggingFace controller functionality.
"""

import anyio
import logging
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HuggingFaceAuthRequest(BaseModel):
    """Request model for HuggingFace authentication."""
    api_key: str = Field(..., description="HuggingFace API key/token")
    username: Optional[str] = Field(None, description="HuggingFace username")
    remember: bool = Field(True, description="Remember credentials for future use")


class HuggingFaceListModelsRequest:
    """Request model for listing HuggingFace models."""
    
    def __init__(
        self,
        filter_by: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ):
        self.filter_by = filter_by or {}
        self.sort_by = sort_by
        self.limit = limit
        self.offset = offset


class HuggingFaceControllerAnyIO:
    """AnyIO-compatible controller for HuggingFace operations."""
    
    def __init__(self, huggingface_model):
        """Initialize with a HuggingFace model."""
        self.huggingface_model = huggingface_model
        self.logger = logging.getLogger(__name__)
    
    async def list_models(self, request: HuggingFaceListModelsRequest) -> Dict[str, Any]:
        """List HuggingFace models based on filters."""
        self.logger.info(f"Listing HuggingFace models with filters: {request.filter_by}")
        try:
            models = await self.huggingface_model.list_models_async(
                filter_by=request.filter_by,
                sort_by=request.sort_by,
                limit=request.limit,
                offset=request.offset
            )
            return {
                "models": models,
                "count": len(models),
                "success": True,
                "message": "Models retrieved successfully"
            }
        except Exception as e:
            self.logger.error(f"Error listing models: {str(e)}")
            return {
                "models": [],
                "count": 0,
                "success": False,
                "message": f"Error listing models: {str(e)}"
            }
    
    async def get_model_info(self, request) -> Dict[str, Any]:
        """Get information about a specific HuggingFace model."""
        model_id = request.model_id
        self.logger.info(f"Getting info for model: {model_id}")
        try:
            model_info = await self.huggingface_model.get_model_info_async(model_id)
            return {
                "model_info": model_info,
                "success": True,
                "message": f"Model info retrieved for {model_id}"
            }
        except Exception as e:
            self.logger.error(f"Error getting model info: {str(e)}")
            return {
                "model_info": {},
                "success": False,
                "message": f"Error getting model info: {str(e)}"
            }
    
    async def download_model(self, request) -> Dict[str, Any]:
        """Download a HuggingFace model."""
        model_id = request.model_id
        self.logger.info(f"Downloading model: {model_id}")
        try:
            result = await self.huggingface_model.download_model_async(
                model_id=model_id,
                revision=request.revision,
                subfolder=request.subfolder,
                local_dir=request.local_dir
            )
            return {
                "local_path": result.get("local_path", ""),
                "success": True,
                "message": f"Model {model_id} downloaded successfully"
            }
        except Exception as e:
            self.logger.error(f"Error downloading model: {str(e)}")
            return {
                "local_path": "",
                "success": False,
                "message": f"Error downloading model: {str(e)}"
            }
    
    async def upload_model(self, request) -> Dict[str, Any]:
        """Upload a model to HuggingFace."""
        model_id = request.model_id
        self.logger.info(f"Uploading model: {model_id}")
        try:
            result = await self.huggingface_model.upload_model_async(
                local_path=request.local_path,
                model_id=model_id,
                private=request.private,
                commit_message=request.commit_message
            )
            return {
                "model_id": model_id,
                "url": result.get("url", ""),
                "success": True,
                "message": f"Model uploaded successfully as {model_id}"
            }
        except Exception as e:
            self.logger.error(f"Error uploading model: {str(e)}")
            return {
                "model_id": model_id,
                "url": "",
                "success": False,
                "message": f"Error uploading model: {str(e)}"
            }
            
    async def authenticate(self, request: HuggingFaceAuthRequest) -> Dict[str, Any]:
        """Authenticate with HuggingFace using API key."""
        self.logger.info(f"Authenticating with HuggingFace for user: {request.username or 'unknown'}")
        try:
            result = await self.huggingface_model.login_async(
                api_key=request.api_key,
                username=request.username,
                remember=request.remember
            )
            return {
                "authenticated": True,
                "username": result.get("username", request.username),
                "success": True,
                "message": "Successfully authenticated with HuggingFace"
            }
        except Exception as e:
            self.logger.error(f"Error authenticating with HuggingFace: {str(e)}")
            return {
                "authenticated": False,
                "username": request.username,
                "success": False,
                "message": f"Error authenticating with HuggingFace: {str(e)}"
            }