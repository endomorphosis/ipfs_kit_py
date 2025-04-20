"""
Model Registry Client Handler

This module provides a high-level client interface for interacting with the Model Registry.
It simplifies common operations and provides a more Pythonic interface compared to
directly calling API endpoints.

Usage example:
```python
from ipfs_kit_py.mcp.ai.model_registry.handler import ModelRegistryClient

# Create client
client = ModelRegistryClient(api_url="http://localhost:5000")

# Authenticate (if using authentication)
client.authenticate(token="your_token")

# Create a model
model = await client.create_model(
    name="My Model",
    description="My model description",
    model_type="classification"
)

# Upload a version
version = await client.upload_model_version(
    model_id=model["id"],
    version="1.0.0",
    model_path="path/to/model.pt",
    format="pytorch",
    framework="pytorch"
)

print(f"Model {model['name']} version {version['version']} uploaded!")
```

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import aiohttp
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, BinaryIO
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("model_registry_client")

class ModelRegistryClient:
    """
    Client for interacting with the Model Registry API.
    
    This class provides a high-level interface for common operations
    such as creating models, uploading versions, and managing metadata.
    """
    
    def __init__(self, api_url: str = "http://localhost:5000"):
        """
        Initialize the client.
        
        Args:
            api_url: Base URL for the API
        """
        self.api_url = api_url.rstrip("/")
        self.base_url = f"{self.api_url}/api/v0/ai/models"
        self.token = None
        self.session = None
    
    async def __aenter__(self):
        """Context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None
    
    def authenticate(self, token: str):
        """
        Set authentication token.
        
        Args:
            token: JWT token for authentication
        """
        self.token = token
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers.
        
        Returns:
            Dictionary of headers
        """
        headers = {
            "Accept": "application/json"
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    async def _ensure_session(self):
        """Ensure an HTTP session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the API.
        
        Args:
            method: HTTP method
            path: API path
            params: Optional query parameters
            json_data: Optional JSON data
            data: Optional form data
            files: Optional files
            
        Returns:
            Response data
        
        Raises:
            ValueError: If the request fails
        """
        await self._ensure_session()
        
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        
        # Handle file uploads
        if files:
            form_data = aiohttp.FormData()
            
            # Add form fields
            if data:
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        form_data.add_field(key, json.dumps(value))
                    else:
                        form_data.add_field(key, str(value))
            
            # Add files
            for key, file_info in files.items():
                file_path = file_info.get("path")
                file_name = file_info.get("filename", os.path.basename(file_path))
                file_content = file_info.get("content")
                
                if file_content:
                    form_data.add_field(
                        key,
                        file_content,
                        filename=file_name
                    )
                elif file_path:
                    with open(file_path, "rb") as f:
                        form_data.add_field(
                            key,
                            f.read(),
                            filename=file_name
                        )
            
            # Make request
            async with self.session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=form_data
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise ValueError(f"Request failed with status {response.status}: {error_text}")
                
                return await response.json()
        
        # Regular request (no files)
        async with self.session.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_data,
            data=data
        ) as response:
            if response.status >= 400:
                error_text = await response.text()
                raise ValueError(f"Request failed with status {response.status}: {error_text}")
            
            return await response.json()
    
    # Model management
    
    async def create_model(
        self,
        name: str,
        description: str = "",
        model_type: Optional[str] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new model.
        
        Args:
            name: Model name
            description: Optional model description
            model_type: Optional model type
            team: Optional team name
            project: Optional project name
            metadata: Optional metadata
            tags: Optional tags
            
        Returns:
            Created model information
        """
        data = {
            "name": name,
            "description": description
        }
        
        if model_type:
            data["model_type"] = model_type
        if team:
            data["team"] = team
        if project:
            data["project"] = project
        if metadata:
            data["metadata"] = metadata
        if tags:
            data["tags"] = tags
        
        response = await self._request("POST", "", json_data=data)
        return response.get("model", {})
    
    async def get_model(self, model_id: str, include_versions: bool = False) -> Dict[str, Any]:
        """
        Get a model by ID.
        
        Args:
            model_id: Model ID
            include_versions: Whether to include version details
            
        Returns:
            Model information
        """
        params = {"include_versions": "true" if include_versions else "false"}
        response = await self._request("GET", f"/{model_id}", params=params)
        return response.get("model", {})
    
    async def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model_type: Optional[str] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update a model's metadata.
        
        Args:
            model_id: Model ID
            name: Optional new name
            description: Optional new description
            model_type: Optional new model type
            team: Optional new team
            project: Optional new project
            metadata: Optional new metadata
            tags: Optional new tags
            
        Returns:
            Updated model information
        """
        data = {}
        
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if model_type is not None:
            data["model_type"] = model_type
        if team is not None:
            data["team"] = team
        if project is not None:
            data["project"] = project
        if metadata is not None:
            data["metadata"] = metadata
        if tags is not None:
            data["tags"] = tags
        
        response = await self._request("PATCH", f"/{model_id}", json_data=data)
        return response.get("model", {})
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Delete a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Success flag
        """
        response = await self._request("DELETE", f"/{model_id}")
        return response.get("success", False)
    
    async def list_models(
        self,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_type: Optional[str] = None,
        team: Optional[str] = None,
        project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List models with optional filtering.
        
        Args:
            name: Filter by name (substring match)
            owner: Filter by owner
            tags: Filter by tags (comma-separated)
            model_type: Filter by model type
            team: Filter by team
            project: Filter by project
            
        Returns:
            List of models
        """
        params = {}
        
        if name:
            params["name"] = name
        if owner:
            params["owner"] = owner
        if tags:
            params["tags"] = ",".join(tags)
        if model_type:
            params["model_type"] = model_type
        if team:
            params["team"] = team
        if project:
            params["project"] = project
        
        response = await self._request("GET", "", params=params)
        return response.get("models", [])
    
    # Version management
    
    async def upload_model_version(
        self,
        model_id: str,
        version: str,
        model_path: str,
        format: str,
        description: str = "",
        commit_message: str = "",
        framework: Optional[str] = None,
        framework_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        parent_version: Optional[str] = None,
        dataset_refs: Optional[List[str]] = None,
        experiment_id: Optional[str] = None,
        storage_backend: str = "ipfs",
        status: str = "draft"
    ) -> Dict[str, Any]:
        """
        Upload a new model version.
        
        Args:
            model_id: Model ID
            version: Version string (e.g. "1.0.0")
            model_path: Path to model file
            format: Model format
            description: Optional description
            commit_message: Optional commit message
            framework: Optional model framework
            framework_version: Optional framework version
            metadata: Optional metadata
            tags: Optional tags
            parent_version: Optional parent version ID
            dataset_refs: Optional dataset references
            experiment_id: Optional experiment ID
            storage_backend: Storage backend (default: ipfs)
            status: Initial status (default: draft)
            
        Returns:
            Created version information
        """
        data = {
            "version": version,
            "description": description,
            "commit_message": commit_message,
            "format": format,
            "storage_backend": storage_backend,
            "status": status
        }
        
        if framework:
            data["framework"] = framework
        if framework_version:
            data["framework_version"] = framework_version
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if tags:
            data["tags"] = json.dumps(tags)
        if parent_version:
            data["parent_version"] = parent_version
        if dataset_refs:
            data["dataset_refs"] = json.dumps(dataset_refs)
        if experiment_id:
            data["experiment_id"] = experiment_id
        
        files = {
            "model_file": {"path": model_path}
        }
        
        response = await self._request(
            "POST",
            f"/{model_id}/versions",
            data=data,
            files=files
        )
        
        return response.get("version", {})
    
    async def upload_model_bytes(
        self,
        model_id: str,
        version: str,
        model_bytes: bytes,
        model_filename: str,
        format: str,
        description: str = "",
        commit_message: str = "",
        framework: Optional[str] = None,
        framework_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        parent_version: Optional[str] = None,
        dataset_refs: Optional[List[str]] = None,
        experiment_id: Optional[str] = None,
        storage_backend: str = "ipfs",
        status: str = "draft"
    ) -> Dict[str, Any]:
        """
        Upload a new model version from bytes.
        
        Args:
            model_id: Model ID
            version: Version string (e.g. "1.0.0")
            model_bytes: Model file content as bytes
            model_filename: Model filename
            format: Model format
            description: Optional description
            commit_message: Optional commit message
            framework: Optional model framework
            framework_version: Optional framework version
            metadata: Optional metadata
            tags: Optional tags
            parent_version: Optional parent version ID
            dataset_refs: Optional dataset references
            experiment_id: Optional experiment ID
            storage_backend: Storage backend (default: ipfs)
            status: Initial status (default: draft)
            
        Returns:
            Created version information
        """
        data = {
            "version": version,
            "description": description,
            "commit_message": commit_message,
            "format": format,
            "storage_backend": storage_backend,
            "status": status
        }
        
        if framework:
            data["framework"] = framework
        if framework_version:
            data["framework_version"] = framework_version
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if tags:
            data["tags"] = json.dumps(tags)
        if parent_version:
            data["parent_version"] = parent_version
        if dataset_refs:
            data["dataset_refs"] = json.dumps(dataset_refs)
        if experiment_id:
            data["experiment_id"] = experiment_id
        
        files = {
            "model_file": {
                "filename": model_filename,
                "content": model_bytes
            }
        }
        
        response = await self._request(
            "POST",
            f"/{model_id}/versions",
            data=data,
            files=files
        )
        
        return response.get("version", {})
    
    async def get_version(self, model_id: str, version_id: str) -> Dict[str, Any]:
        """
        Get a model version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            
        Returns:
            Version information
        """
        response = await self._request("GET", f"/{model_id}/versions/{version_id}")
        return response.get("version", {})
    
    async def download_version(self, model_id: str, version_id: str, output_path: str) -> bool:
        """
        Download a model version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            output_path: Path to save the model file
            
        Returns:
            Success flag
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/{model_id}/versions/{version_id}/download"
        headers = self._get_headers()
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise ValueError(f"Download failed with status {response.status}: {error_text}")
                
                # Save to file
                with open(output_path, "wb") as f:
                    f.write(await response.read())
                
                return True
        except Exception as e:
            logger.error(f"Error downloading model version: {e}")
            return False
    
    async def get_version_bytes(self, model_id: str, version_id: str) -> Optional[bytes]:
        """
        Get a model version as bytes.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            
        Returns:
            Model bytes or None if failed
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/{model_id}/versions/{version_id}/download"
        headers = self._get_headers()
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise ValueError(f"Download failed with status {response.status}: {error_text}")
                
                return await response.read()
        except Exception as e:
            logger.error(f"Error downloading model version: {e}")
            return None
    
    async def update_version(
        self,
        model_id: str,
        version_id: str,
        description: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update a model version's metadata.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            description: Optional new description
            status: Optional new status
            metadata: Optional new metadata
            tags: Optional new tags
            
        Returns:
            Updated version information
        """
        data = {}
        
        if description is not None:
            data["description"] = description
        if status is not None:
            data["status"] = status
        if metadata is not None:
            data["metadata"] = metadata
        if tags is not None:
            data["tags"] = tags
        
        response = await self._request("PATCH", f"/{model_id}/versions/{version_id}", json_data=data)
        return response.get("version", {})
    
    async def delete_version(self, model_id: str, version_id: str) -> bool:
        """
        Delete a model version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            
        Returns:
            Success flag
        """
        response = await self._request("DELETE", f"/{model_id}/versions/{version_id}")
        return response.get("success", False)
    
    async def list_versions(
        self,
        model_id: str,
        status: Optional[str] = None,
        framework: Optional[str] = None,
        format: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        List versions of a model with optional filtering.
        
        Args:
            model_id: Model ID
            status: Filter by status
            framework: Filter by framework
            format: Filter by format
            tags: Filter by tags (comma-separated)
            
        Returns:
            List of versions
        """
        params = {}
        
        if status:
            params["status"] = status
        if framework:
            params["framework"] = framework
        if format:
            params["format"] = format
        if tags:
            params["tags"] = ",".join(tags)
        
        response = await self._request("GET", f"/{model_id}/versions", params=params)
        return response.get("versions", [])
    
    # Production and latest versions
    
    async def set_production_version(self, model_id: str, version_id: str) -> bool:
        """
        Set a version as the production version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            
        Returns:
            Success flag
        """
        response = await self._request("POST", f"/{model_id}/production/{version_id}")
        return response.get("success", False)
    
    async def get_production_version(self, model_id: str) -> Dict[str, Any]:
        """
        Get the production version of a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Production version information
        """
        response = await self._request("GET", f"/{model_id}/production")
        return response.get("version", {})
    
    async def get_latest_version(self, model_id: str) -> Dict[str, Any]:
        """
        Get the latest version of a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Latest version information
        """
        response = await self._request("GET", f"/{model_id}/latest")
        return response.get("version", {})
    
    # Metrics and deployment
    
    async def update_metrics(
        self,
        model_id: str,
        version_id: str,
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Update metrics for a model version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            metrics: Metrics dictionary
            
        Returns:
            Success flag
        """
        response = await self._request("POST", f"/{model_id}/versions/{version_id}/metrics", json_data=metrics)
        return response.get("success", False)
    
    async def update_deployment_config(
        self,
        model_id: str,
        version_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """
        Update deployment configuration for a model version.
        
        Args:
            model_id: Model ID
            version_id: Version ID
            config: Deployment configuration
            
        Returns:
            Success flag
        """
        response = await self._request("POST", f"/{model_id}/versions/{version_id}/deployment", json_data=config)
        return response.get("success", False)
    
    # Version comparison
    
    async def compare_versions(self, version1_id: str, version2_id: str) -> Dict[str, Any]:
        """
        Compare two model versions.
        
        Args:
            version1_id: First version ID
            version2_id: Second version ID
            
        Returns:
            Comparison results
        """
        params = {
            "version1": version1_id,
            "version2": version2_id
        }
        
        response = await self._request("GET", "/versions/compare", params=params)
        return response