"""
AI/ML Integrator Module for MCP Server

This module provides integration of AI/ML capabilities with the MCP server, including:
1. API Registration and routing
2. Component coordination
3. Authentication and authorization
4. Monitoring and diagnostics

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import logging
import json
from typing import Dict, List, Any, Optional, Union, Set, Callable
from pathlib import Path
import threading
import datetime
import uuid

# Configure logger
logger = logging.getLogger(__name__)

# Import dependencies
try:
    from fastapi import APIRouter, Depends, HTTPException, FastAPI, Request, Response
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
except ImportError:
    logger.warning("FastAPI not installed. API endpoints will not be available.")

# Import internal modules
try:
    from ipfs_kit_py.mcp.ai.config import get_instance as get_config_instance
    from ipfs_kit_py.mcp.ai.monitoring import get_metrics_collector, get_health_check
    from ipfs_kit_py.mcp.ai.dataset_manager import get_instance as get_dataset_manager
except ImportError:
    logger.warning("AI/ML modules not available. Some functionality may not work.")
    
    # Mock implementations for testing
    class MockConfig:
        def get(self, key, default=None):
            return default
    
    def get_config_instance(*args, **kwargs):
        return MockConfig()
    
    class MockMetricsCollector:
        def counter(self, name, labels=None, value=1):
            return 0
        
        def gauge(self, name, value, labels=None):
            return 0
        
        def histogram(self, name, value, labels=None):
            pass
    
    def get_metrics_collector():
        return MockMetricsCollector()
    
    class MockHealthCheck:
        def register_check(self, name, check_func):
            pass
        
        def check_health(self, name):
            return {"status": "unknown"}
        
        def check_overall_health(self):
            return {"status": "unknown"}
    
    def get_health_check():
        return MockHealthCheck()
    
    class MockDatasetManager:
        def list_datasets(self, domain=None, tag=None):
            return []
        
        def get_dataset(self, dataset_id):
            return None
        
        def create_dataset(self, name, description="", domain="tabular", tags=None, metadata=None):
            return None
        
        def list_dataset_versions(self, dataset_id):
            return []
    
    def get_dataset_manager():
        return MockDatasetManager()


# Model classes for API
class Dataset(BaseModel):
    """Dataset information for API."""
    id: str
    name: str
    description: str
    domain: str
    tags: List[str]
    versions: List[str]
    latest_version: Optional[str] = None
    created_at: str
    updated_at: str


class DatasetVersion(BaseModel):
    """Dataset version information for API."""
    id: str
    dataset_id: str
    version: str
    description: str
    files: List[Dict[str, Any]]
    schema: Dict[str, Any]
    created_at: str
    updated_at: str


class CreateDatasetRequest(BaseModel):
    """Request to create a dataset."""
    name: str
    description: Optional[str] = ""
    domain: Optional[str] = "tabular"
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateDatasetVersionRequest(BaseModel):
    """Request to create a dataset version."""
    version: str
    description: Optional[str] = ""
    files: Optional[List[Dict[str, Any]]] = None
    schema: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """API error response."""
    error: str
    details: Optional[str] = None
    status_code: int = 500


class AIML_Integrator:
    """
    AI/ML Integration Manager
    
    This class coordinates AI/ML components and provides API integration with the MCP server.
    """
    
    def __init__(self):
        """Initialize the AI/ML integrator."""
        # For thread safety
        self.lock = threading.RLock()
        
        # Initialize components
        try:
            self.config = get_config_instance()
            self.metrics = get_metrics_collector()
            self.health = get_health_check()
            
            # Register health check
            self.health.register_check("ai_ml_integrator", self._health_check)
        except Exception as e:
            logger.warning(f"Error initializing components: {e}")
            self.config = None
            self.metrics = None
            self.health = None
        
        # Component references
        self.dataset_manager = None
        self.model_registry = None
        
        # Router for FastAPI
        self.router = None
        self.prefix = "/ai"
        
        logger.info("AI/ML integrator initialized")
    
    def _health_check(self) -> Dict[str, Any]:
        """Health check function."""
        try:
            # Check if components are available
            components_status = {
                "dataset_manager": self.dataset_manager is not None,
                "model_registry": self.model_registry is not None,
                "config": self.config is not None,
                "metrics": self.metrics is not None
            }
            
            # Overall status
            status = "healthy"
            if not components_status["dataset_manager"] or not components_status["config"]:
                status = "degraded"
            
            return {
                "status": status,
                "components": components_status,
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def initialize(self) -> bool:
        """
        Initialize the integrator.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize dataset manager
            self.dataset_manager = get_dataset_manager()
            
            # Create router
            try:
                self.router = APIRouter(
                    prefix=self.prefix,
                    tags=["ai"]
                )
                
                # Register routes
                self._register_routes()
                
                logger.info("Initialized AI/ML integrator with API endpoints")
                return True
            
            except NameError:
                logger.warning("FastAPI not available, skipping router setup")
                return False
            
        except Exception as e:
            logger.error(f"Error initializing AI/ML integrator: {e}")
            return False
    
    def _register_routes(self) -> None:
        """Register API routes."""
        if not self.router:
            logger.warning("Router not initialized, skipping route registration")
            return
        
        # Dataset endpoints
        self.router.get("/datasets", response_model=List[Dataset])(self.list_datasets)
        self.router.get("/datasets/{dataset_id}", response_model=Dataset)(self.get_dataset)
        self.router.post("/datasets", response_model=Dataset)(self.create_dataset)
        self.router.get("/datasets/{dataset_id}/versions", response_model=List[DatasetVersion])(self.list_dataset_versions)
        self.router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersion)(self.create_dataset_version)
        
        # Health check endpoint
        self.router.get("/health")(self.get_health)
        
        # Version endpoint
        self.router.get("/version")(self.get_version)
    
    def register_with_server(self, app, prefix: str = "/api/v0/ai") -> bool:
        """
        Register with MCP server.
        
        Args:
            app: FastAPI application
            prefix: URL prefix
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update prefix
            self.prefix = prefix
            
            # Create router if needed
            if not self.router:
                self.router = APIRouter(
                    prefix=prefix,
                    tags=["ai"]
                )
                self._register_routes()
            
            # Include router in app
            app.include_router(self.router)
            
            # Log registration
            logger.info(f"Registered AI/ML integrator with server at {prefix}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering with server: {e}")
            return False
    
    # API Endpoint handlers
    
    async def get_health(self):
        """Get health status."""
        if self.health:
            health = self.health.check_overall_health()
            return health
        else:
            return {"status": "unknown", "timestamp": datetime.datetime.now().isoformat()}
    
    async def get_version(self):
        """Get version information."""
        return {
            "version": "0.1.0",
            "name": "AI/ML Integration",
            "components": {
                "dataset_manager": self.dataset_manager is not None,
                "model_registry": self.model_registry is not None
            }
        }
    
    async def list_datasets(self, domain: Optional[str] = None, tag: Optional[str] = None):
        """
        List datasets.
        
        Args:
            domain: Optional domain filter
            tag: Optional tag filter
            
        Returns:
            List of datasets
        """
        if not self.dataset_manager:
            raise HTTPException(status_code=503, detail="Dataset manager not available")
        
        try:
            datasets = self.dataset_manager.list_datasets(domain=domain, tag=tag)
            
            # Convert to API models
            result = []
            for dataset in datasets:
                result.append({
                    "id": dataset.id,
                    "name": dataset.name,
                    "description": dataset.description,
                    "domain": dataset.domain,
                    "tags": dataset.tags,
                    "versions": dataset.versions,
                    "latest_version": dataset.latest_version,
                    "created_at": dataset.created_at.isoformat(),
                    "updated_at": dataset.updated_at.isoformat()
                })
            
            # Record metric
            if self.metrics:
                self.metrics.counter("ai_ml_integrator.list_datasets")
            
            return result
        
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_dataset(self, dataset_id: str):
        """
        Get a dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dataset information
        """
        if not self.dataset_manager:
            raise HTTPException(status_code=503, detail="Dataset manager not available")
        
        try:
            dataset = self.dataset_manager.get_dataset(dataset_id)
            
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            # Convert to API model
            result = {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "domain": dataset.domain,
                "tags": dataset.tags,
                "versions": dataset.versions,
                "latest_version": dataset.latest_version,
                "created_at": dataset.created_at.isoformat(),
                "updated_at": dataset.updated_at.isoformat()
            }
            
            # Record metric
            if self.metrics:
                self.metrics.counter("ai_ml_integrator.get_dataset")
            
            return result
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.error(f"Error getting dataset: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def create_dataset(self, request: CreateDatasetRequest):
        """
        Create a new dataset.
        
        Args:
            request: Create dataset request
            
        Returns:
            Created dataset
        """
        if not self.dataset_manager:
            raise HTTPException(status_code=503, detail="Dataset manager not available")
        
        try:
            # Create dataset
            dataset = self.dataset_manager.create_dataset(
                name=request.name,
                description=request.description,
                domain=request.domain,
                tags=request.tags,
                metadata=request.metadata
            )
            
            # Convert to API model
            result = {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "domain": dataset.domain,
                "tags": dataset.tags,
                "versions": dataset.versions,
                "latest_version": dataset.latest_version,
                "created_at": dataset.created_at.isoformat(),
                "updated_at": dataset.updated_at.isoformat()
            }
            
            # Record metric
            if self.metrics:
                self.metrics.counter("ai_ml_integrator.create_dataset")
            
            return result
        
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def list_dataset_versions(self, dataset_id: str):
        """
        List versions for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of dataset versions
        """
        if not self.dataset_manager:
            raise HTTPException(status_code=503, detail="Dataset manager not available")
        
        try:
            # Get dataset first to check if it exists
            dataset = self.dataset_manager.get_dataset(dataset_id)
            
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            # Get versions
            versions = self.dataset_manager.list_dataset_versions(dataset_id)
            
            # Convert to API models
            result = []
            for version in versions:
                result.append({
                    "id": version.id,
                    "dataset_id": version.dataset_id,
                    "version": version.version,
                    "description": version.description,
                    "files": [self._convert_file(file) for file in version.files],
                    "schema": version.schema,
                    "created_at": version.created_at.isoformat(),
                    "updated_at": version.updated_at.isoformat()
                })
            
            # Record metric
            if self.metrics:
                self.metrics.counter("ai_ml_integrator.list_dataset_versions")
            
            return result
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.error(f"Error listing dataset versions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def _convert_file(self, file) -> Dict[str, Any]:
        """Convert file object to dictionary."""
        return {
            "name": file.name,
            "path": file.path,
            "format": file.format,
            "split": file.split,
            "size_bytes": file.size_bytes,
            "checksum": file.checksum,
            "metadata": file.metadata,
            "storage_ref": file.storage_ref
        }
    
    async def create_dataset_version(self, dataset_id: str, request: CreateDatasetVersionRequest):
        """
        Create a new dataset version.
        
        Args:
            dataset_id: Dataset ID
            request: Create version request
            
        Returns:
            Created version
        """
        if not self.dataset_manager:
            raise HTTPException(status_code=503, detail="Dataset manager not available")
        
        try:
            # Get dataset first to check if it exists
            dataset = self.dataset_manager.get_dataset(dataset_id)
            
            if not dataset:
                raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
            
            # Create version
            version = self.dataset_manager.create_dataset_version(
                dataset_id=dataset_id,
                version=request.version,
                description=request.description,
                files=request.files,
                schema=request.schema,
                metadata=request.metadata
            )
            
            # Convert to API model
            result = {
                "id": version.id,
                "dataset_id": version.dataset_id,
                "version": version.version,
                "description": version.description,
                "files": [self._convert_file(file) for file in version.files],
                "schema": version.schema,
                "created_at": version.created_at.isoformat(),
                "updated_at": version.updated_at.isoformat()
            }
            
            # Record metric
            if self.metrics:
                self.metrics.counter("ai_ml_integrator.create_dataset_version")
            
            return result
        
        except HTTPException:
            raise
        
        except Exception as e:
            logger.error(f"Error creating dataset version: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Placeholder methods for model registry
    
    async def list_models(self):
        """
        List models.
        
        Returns:
            List of models
        """
        # Return empty list for now
        return []
    
    async def get_model(self, model_id: str):
        """
        Get a model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model information
        """
        # Return 404 for now
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    async def create_model(self, request: Dict[str, Any]):
        """
        Create a new model.
        
        Args:
            request: Create model request
            
        Returns:
            Created model
        """
        # Return not implemented for now
        raise HTTPException(status_code=501, detail="Model creation not implemented yet")


# Singleton instance
_instance = None

def get_instance() -> AIML_Integrator:
    """
    Get the singleton instance.
    
    Returns:
        AIML_Integrator instance
    """
    global _instance
    if _instance is None:
        _instance = AIML_Integrator()
    return _instance
