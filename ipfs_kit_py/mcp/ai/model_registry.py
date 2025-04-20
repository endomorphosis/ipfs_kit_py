#!/usr/bin/env python3
"""
Model Registry for MCP Server

This module provides version-controlled model storage and management capabilities
for machine learning models within the IPFS Kit ecosystem.

Key features:
- Version-controlled model storage
- Model metadata management
- Model performance tracking
- Deployment configuration management

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import logging
import time
import hashlib
import shutil
from typing import Dict, List, Optional, Union, Any, Tuple, Iterator
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_model_registry")

class ModelVersion:
    """Represents a single version of a model with its metadata and metrics."""
    
    def __init__(
        self,
        version_id: str,
        model_id: str,
        created_at: Union[str, datetime],
        metadata: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
        tags: Optional[List[str]] = None,
        path: Optional[str] = None,
        storage_backend: Optional[str] = None,
        storage_uri: Optional[str] = None,
        framework: Optional[str] = None,
        size_bytes: Optional[int] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        status: str = "created"
    ):
        """
        Initialize a model version.
        
        Args:
            version_id: Unique identifier for this version
            model_id: ID of the parent model
            created_at: Creation timestamp
            metadata: Additional metadata
            metrics: Performance metrics
            tags: Tags for categorization and filtering
            path: Local filesystem path (if stored locally)
            storage_backend: Storage backend identifier (ipfs, filecoin, s3, etc.)
            storage_uri: URI for retrieving the model from storage
            framework: ML framework (tensorflow, pytorch, etc.)
            size_bytes: Size of the model in bytes
            description: Human-readable description
            user_id: ID of the user who created this version
            status: Current status (created, training, ready, failed, etc.)
        """
        self.version_id = version_id
        self.model_id = model_id
        
        # Convert string timestamps to datetime objects
        if isinstance(created_at, str):
            self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            self.created_at = created_at
            
        self.metadata = metadata or {}
        self.metrics = metrics or {}
        self.tags = tags or []
        self.path = path
        self.storage_backend = storage_backend
        self.storage_uri = storage_uri
        self.framework = framework
        self.size_bytes = size_bytes
        self.description = description
        self.user_id = user_id
        self.status = status
        self.updated_at = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model version to a dictionary."""
        return {
            "version_id": self.version_id,
            "model_id": self.model_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "metrics": self.metrics,
            "tags": self.tags,
            "path": self.path,
            "storage_backend": self.storage_backend,
            "storage_uri": self.storage_uri,
            "framework": self.framework,
            "size_bytes": self.size_bytes,
            "description": self.description,
            "user_id": self.user_id,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelVersion':
        """Create a ModelVersion from a dictionary."""
        return cls(
            version_id=data["version_id"],
            model_id=data["model_id"],
            created_at=data["created_at"],
            metadata=data.get("metadata"),
            metrics=data.get("metrics"),
            tags=data.get("tags"),
            path=data.get("path"),
            storage_backend=data.get("storage_backend"),
            storage_uri=data.get("storage_uri"),
            framework=data.get("framework"),
            size_bytes=data.get("size_bytes"),
            description=data.get("description"),
            user_id=data.get("user_id"),
            status=data.get("status", "created")
        )
    
    def update_metrics(self, metrics: Dict[str, float]) -> None:
        """
        Update performance metrics.
        
        Args:
            metrics: New or updated metrics
        """
        self.metrics.update(metrics)
        self.updated_at = datetime.now()
    
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Update metadata.
        
        Args:
            metadata: New or updated metadata
        """
        self.metadata.update(metadata)
        self.updated_at = datetime.now()
    
    def add_tags(self, tags: List[str]) -> None:
        """
        Add tags to the model version.
        
        Args:
            tags: Tags to add
        """
        for tag in tags:
            if tag not in self.tags:
                self.tags.append(tag)
        self.updated_at = datetime.now()
    
    def remove_tags(self, tags: List[str]) -> None:
        """
        Remove tags from the model version.
        
        Args:
            tags: Tags to remove
        """
        self.tags = [t for t in self.tags if t not in tags]
        self.updated_at = datetime.now()
    
    def update_status(self, status: str) -> None:
        """
        Update the status of the model version.
        
        Args:
            status: New status
        """
        self.status = status
        self.updated_at = datetime.now()

class Model:
    """
    Represents a machine learning model with its versions and metadata.
    
    This is the main class for interacting with model data, including
    creating new versions, tracking metrics, and managing metadata.
    """
    
    def __init__(
        self,
        model_id: str,
        name: str,
        created_at: Union[str, datetime],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        versions: Optional[Dict[str, ModelVersion]] = None
    ):
        """
        Initialize a model.
        
        Args:
            model_id: Unique identifier for the model
            name: Human-readable name
            created_at: Creation timestamp
            description: Human-readable description
            tags: Tags for categorization and filtering
            framework: ML framework (tensorflow, pytorch, etc.)
            user_id: ID of the user who created the model
            metadata: Additional metadata
            versions: Dictionary of version_id -> ModelVersion
        """
        self.model_id = model_id
        self.name = name
        
        # Convert string timestamps to datetime objects
        if isinstance(created_at, str):
            self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            self.created_at = created_at
            
        self.description = description
        self.tags = tags or []
        self.framework = framework
        self.user_id = user_id
        self.metadata = metadata or {}
        self.versions = versions or {}
        self.updated_at = self.created_at
        self.version_count = len(self.versions)
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def to_dict(self, include_versions: bool = False) -> Dict[str, Any]:
        """
        Convert model to a dictionary.
        
        Args:
            include_versions: Whether to include version data
            
        Returns:
            Model as a dictionary
        """
        with self._lock:
            result = {
                "model_id": self.model_id,
                "name": self.name,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
                "description": self.description,
                "tags": self.tags,
                "framework": self.framework,
                "user_id": self.user_id,
                "metadata": self.metadata,
                "version_count": self.version_count
            }
            
            if include_versions:
                result["versions"] = {
                    v_id: version.to_dict() 
                    for v_id, version in self.versions.items()
                }
            
            return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Model':
        """Create a Model from a dictionary."""
        versions = {}
        if "versions" in data:
            versions = {
                v_id: ModelVersion.from_dict(v_data)
                for v_id, v_data in data["versions"].items()
            }
        
        return cls(
            model_id=data["model_id"],
            name=data["name"],
            created_at=data["created_at"],
            description=data.get("description"),
            tags=data.get("tags"),
            framework=data.get("framework"),
            user_id=data.get("user_id"),
            metadata=data.get("metadata"),
            versions=versions
        )
    
    def add_version(self, version: ModelVersion) -> None:
        """
        Add a version to the model.
        
        Args:
            version: ModelVersion to add
        """
        with self._lock:
            self.versions[version.version_id] = version
            self.version_count = len(self.versions)
            self.updated_at = datetime.now()
    
    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """
        Get a specific version of the model.
        
        Args:
            version_id: Version ID to retrieve
            
        Returns:
            ModelVersion if found, None otherwise
        """
        with self._lock:
            return self.versions.get(version_id)
    
    def get_latest_version(self) -> Optional[ModelVersion]:
        """
        Get the latest version of the model.
        
        Returns:
            Most recent ModelVersion if any exist, None otherwise
        """
        with self._lock:
            if not self.versions:
                return None
            
            # Find version with latest created_at timestamp
            return max(self.versions.values(), key=lambda v: v.created_at)
    
    def get_versions(self, limit: Optional[int] = None, offset: int = 0) -> List[ModelVersion]:
        """
        Get versions of the model.
        
        Args:
            limit: Maximum number of versions to return
            offset: Number of versions to skip
            
        Returns:
            List of ModelVersion objects sorted by created_at (newest first)
        """
        with self._lock:
            sorted_versions = sorted(
                self.versions.values(),
                key=lambda v: v.created_at,
                reverse=True
            )
            
            if offset:
                sorted_versions = sorted_versions[offset:]
            
            if limit is not None:
                sorted_versions = sorted_versions[:limit]
            
            return sorted_versions
    
    def remove_version(self, version_id: str) -> bool:
        """
        Remove a version from the model.
        
        Args:
            version_id: Version ID to remove
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if version_id in self.versions:
                del self.versions[version_id]
                self.version_count = len(self.versions)
                self.updated_at = datetime.now()
                return True
            return False
    
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Update metadata.
        
        Args:
            metadata: New or updated metadata
        """
        with self._lock:
            self.metadata.update(metadata)
            self.updated_at = datetime.now()
    
    def add_tags(self, tags: List[str]) -> None:
        """
        Add tags to the model.
        
        Args:
            tags: Tags to add
        """
        with self._lock:
            for tag in tags:
                if tag not in self.tags:
                    self.tags.append(tag)
            self.updated_at = datetime.now()
    
    def remove_tags(self, tags: List[str]) -> None:
        """
        Remove tags from the model.
        
        Args:
            tags: Tags to remove
        """
        with self._lock:
            self.tags = [t for t in self.tags if t not in tags]
            self.updated_at = datetime.now()
    
    def update_version_status(self, version_id: str, status: str) -> bool:
        """
        Update the status of a specific version.
        
        Args:
            version_id: Version ID to update
            status: New status
            
        Returns:
            True if updated, False if version not found
        """
        with self._lock:
            version = self.versions.get(version_id)
            if version:
                version.update_status(status)
                return True
            return False
    
    def get_best_version(self, metric_name: str, higher_is_better: bool = True) -> Optional[ModelVersion]:
        """
        Get the best version according to a specific metric.
        
        Args:
            metric_name: Name of the metric to optimize
            higher_is_better: Whether higher values are better
            
        Returns:
            Best ModelVersion according to the metric, or None if no versions have the metric
        """
        with self._lock:
            valid_versions = [
                v for v in self.versions.values()
                if metric_name in v.metrics
            ]
            
            if not valid_versions:
                return None
            
            # Choose optimal direction based on whether higher is better
            key_func = lambda v: v.metrics[metric_name]
            if not higher_is_better:
                key_func = lambda v: -v.metrics[metric_name]
            
            return max(valid_versions, key=key_func)

class ModelRegistry:
    """
    Registry for managing machine learning models.
    
    This class provides functionality for storing, retrieving, and managing
    machine learning models and their versions, metadata, and metrics.
    """
    
    def __init__(self, storage_path: Union[str, Path], config: Optional[Dict[str, Any]] = None):
        """
        Initialize the model registry.
        
        Args:
            storage_path: Path to store models and metadata
            config: Configuration options
        """
        self.storage_path = Path(storage_path)
        self.config = config or {}
        
        # Ensure storage directories exist
        self.models_path = self.storage_path / "models"
        self.data_path = self.storage_path / "data"
        self.index_path = self.storage_path / "index"
        
        self.models_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # In-memory cache of models
        self._models: Dict[str, Model] = {}
        
        # Initialize executors
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 4),
            thread_name_prefix="model_registry_"
        )
        
        # Load existing models
        self._load_models()
        
        logger.info(f"Model Registry initialized at {self.storage_path} with {len(self._models)} models")
    
    def _load_models(self) -> None:
        """Load existing models from storage."""
        try:
            # Load model metadata
            model_files = list(self.index_path.glob("*.json"))
            for model_file in model_files:
                try:
                    with open(model_file, 'r') as f:
                        model_data = json.load(f)
                    
                    model = Model.from_dict(model_data)
                    self._models[model.model_id] = model
                    
                except Exception as e:
                    logger.error(f"Error loading model from {model_file}: {e}")
            
            logger.info(f"Loaded {len(self._models)} models from storage")
            
        except Exception as e:
            logger.error(f"Error during model loading: {e}")
    
    def _save_model_metadata(self, model: Model) -> bool:
        """
        Save model metadata to storage.
        
        Args:
            model: Model to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            model_file = self.index_path / f"{model.model_id}.json"
            model_data = model.to_dict(include_versions=True)
            
            # Write to a temporary file first, then rename to ensure atomic operation
            temp_file = model_file.with_suffix(".tmp")
            with open(temp_file, 'w') as f:
                json.dump(model_data, f, indent=2)
            
            temp_file.rename(model_file)
            return True
            
        except Exception as e:
            logger.error(f"Error saving model metadata for {model.model_id}: {e}")
            return False
    
    def create_model(
        self,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        model_id: Optional[str] = None
    ) -> Model:
        """
        Create a new model.
        
        Args:
            name: Human-readable name
            description: Human-readable description
            tags: Tags for categorization and filtering
            framework: ML framework (tensorflow, pytorch, etc.)
            user_id: ID of the user creating the model
            metadata: Additional metadata
            model_id: Optional custom model ID (generated if not provided)
            
        Returns:
            The created Model object
        """
        with self._lock:
            # Generate model_id if not provided
            if model_id is None:
                model_id = f"model_{uuid.uuid4().hex[:12]}"
            
            # Ensure model_id is unique
            if model_id in self._models:
                raise ValueError(f"Model with ID '{model_id}' already exists")
            
            # Create model
            model = Model(
                model_id=model_id,
                name=name,
                created_at=datetime.now(),
                description=description,
                tags=tags,
                framework=framework,
                user_id=user_id,
                metadata=metadata
            )
            
            # Add to registry
            self._models[model_id] = model
            
            # Save metadata
            self._save_model_metadata(model)
            
            logger.info(f"Created model '{name}' with ID {model_id}")
            
            return model
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model by ID.
        
        Args:
            model_id: ID of the model to retrieve
            
        Returns:
            Model if found, None otherwise
        """
        return self._models.get(model_id)
    
    def list_models(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        ascending: bool = False,
        filter_tags: Optional[List[str]] = None,
        filter_framework: Optional[str] = None,
        search_term: Optional[str] = None
    ) -> List[Model]:
        """
        List models with filtering and sorting.
        
        Args:
            limit: Maximum number of models to return
            offset: Number of models to skip
            sort_by: Attribute to sort by
            ascending: Whether to sort in ascending order
            filter_tags: Filter by tags (models must have all specified tags)
            filter_framework: Filter by framework
            search_term: Search in name and description
            
        Returns:
            List of matching models
        """
        with self._lock:
            # Start with all models
            models = list(self._models.values())
            
            # Apply filters
            if filter_tags:
                models = [
                    m for m in models 
                    if all(tag in m.tags for tag in filter_tags)
                ]
            
            if filter_framework:
                models = [
                    m for m in models 
                    if m.framework == filter_framework
                ]
            
            if search_term:
                search_term = search_term.lower()
                models = [
                    m for m in models 
                    if (
                        search_term in m.name.lower() or 
                        (m.description and search_term in m.description.lower())
                    )
                ]
            
            # Sort models
            if sort_by == "name":
                models.sort(key=lambda m: m.name, reverse=not ascending)
            elif sort_by == "created_at":
                models.sort(key=lambda m: m.created_at, reverse=not ascending)
            elif sort_by == "version_count":
                models.sort(key=lambda m: m.version_count, reverse=not ascending)
            else:  # Default to updated_at
                models.sort(key=lambda m: m.updated_at, reverse=not ascending)
            
            # Apply pagination
            if offset:
                models = models[offset:]
            
            if limit is not None:
                models = models[:limit]
            
            return models
    
    def delete_model(self, model_id: str, delete_files: bool = True) -> bool:
        """
        Delete a model and optionally its files.
        
        Args:
            model_id: ID of the model to delete
            delete_files: Whether to delete model files
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            model = self._models.get(model_id)
            if not model:
                return False
            
            # Delete model files if requested
            if delete_files:
                model_dir = self.models_path / model_id
                if model_dir.exists():
                    try:
                        shutil.rmtree(model_dir)
                    except Exception as e:
                        logger.error(f"Error deleting model files for {model_id}: {e}")
            
            # Delete model metadata file
            model_file = self.index_path / f"{model_id}.json"
            if model_file.exists():
                try:
                    model_file.unlink()
                except Exception as e:
                    logger.error(f"Error deleting model metadata file for {model_id}: {e}")
            
            # Remove from registry
            del self._models[model_id]
            
            logger.info(f"Deleted model {model_id}")
            
            return True
    
    def create_model_version(
        self,
        model_id: str,
        model_data_path: Optional[Union[str, Path]] = None,
        model_data: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        version_id: Optional[str] = None,
        storage_backend: Optional[str] = None,
        storage_uri: Optional[str] = None
    ) -> Optional[ModelVersion]:
        """
        Create a new version of a model.
        
        Args:
            model_id: ID of the model
            model_data_path: Path to model data (ignored if model_data is provided)
            model_data: Model data as bytes (ignored if model_data_path is provided)
            metadata: Additional metadata
            metrics: Performance metrics
            tags: Tags for categorization and filtering
            framework: ML framework (tensorflow, pytorch, etc.)
            description: Human-readable description
            user_id: ID of the user creating the version
            version_id: Optional custom version ID (generated if not provided)
            storage_backend: Storage backend identifier (ipfs, filecoin, s3, etc.)
            storage_uri: URI for retrieving the model from storage
            
        Returns:
            The created ModelVersion, or None if model not found
        """
        model = self.get_model(model_id)
        if not model:
            logger.error(f"Cannot create version: Model {model_id} not found")
            return None
        
        # Generate version_id if not provided
        if version_id is None:
            version_id = f"v_{uuid.uuid4().hex[:8]}"
        
        # Ensure version directory exists
        model_dir = self.models_path / model_id
        version_dir = model_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine storage path and size
        path = None
        size_bytes = None
        
        if model_data_path:
            # Copy model data from path
            model_data_path = Path(model_data_path)
            if model_data_path.is_file():
                target_path = version_dir / model_data_path.name
                try:
                    shutil.copy2(model_data_path, target_path)
                    path = str(target_path)
                    size_bytes = target_path.stat().st_size
                except Exception as e:
                    logger.error(f"Error copying model data: {e}")
            elif model_data_path.is_dir():
                target_dir = version_dir / model_data_path.name
                try:
                    shutil.copytree(model_data_path, target_dir)
                    path = str(target_dir)
                    size_bytes = sum(f.stat().st_size for f in target_dir.glob('**/*') if f.is_file())
                except Exception as e:
                    logger.error(f"Error copying model directory: {e}")
        
        elif model_data:
            # Save model data bytes
            target_path = version_dir / "model.bin"
            try:
                with open(target_path, 'wb') as f:
                    f.write(model_data)
                path = str(target_path)
                size_bytes = len(model_data)
            except Exception as e:
                logger.error(f"Error saving model data: {e}")
        
        # Create version
        version = ModelVersion(
            version_id=version_id,
            model_id=model_id,
            created_at=datetime.now(),
            metadata=metadata,
            metrics=metrics,
            tags=tags,
            path=path,
            storage_backend=storage_backend,
            storage_uri=storage_uri,
            framework=framework or model.framework,
            size_bytes=size_bytes,
            description=description,
            user_id=user_id or model.user_id,
            status="ready" if (path or storage_uri) else "created"
        )
        
        # Add to model
        model.add_version(version)
        
        # Save model metadata
        self._save_model_metadata(model)
        
        logger.info(f"Created version {version_id} for model {model_id}")
        
        return version
    
    def get_model_version(self, model_id: str, version_id: str) -> Optional[ModelVersion]:
        """
        Get a specific version of a model.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version
            
        Returns:
            ModelVersion if found, None otherwise
        """
        model = self.get_model(model_id)
        if not model:
            return None
        
        return model.get_version(version_id)
    
    def upload_model(
        self,
        name: str,
        model_data_path: Union[str, Path],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        framework: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None,
        version_description: Optional[str] = None,
        storage_backend: Optional[str] = None
    ) -> Tuple[Optional[Model], Optional[ModelVersion]]:
        """
        Create a new model and upload its first version in one operation.
        
        Args:
            name: Human-readable name
            model_data_path: Path to model data
            description: Human-readable description
            tags: Tags for categorization and filtering
            framework: ML framework (tensorflow, pytorch, etc.)
            user_id: ID of the user creating the model
            metadata: Additional metadata
            metrics: Initial performance metrics
            version_description: Description for the first version
            storage_backend: Storage backend identifier
            
        Returns:
            Tuple of (Model, ModelVersion), or (None, None) if failed
        """
        try:
            # Create model
            model = self.create_model(
                name=name,
                description=description,
                tags=tags,
                framework=framework,
                user_id=user_id,
                metadata=metadata
            )
            
            # Create version
            version = self.create_model_version(
                model_id=model.model_id,
                model_data_path=model_data_path,
                metadata=metadata,
                metrics=metrics,
                tags=tags,
                framework=framework,
                description=version_description,
                user_id=user_id,
                storage_backend=storage_backend
            )
            
            if not version:
                logger.error(f"Failed to create version for newly created model {model.model_id}")
                # Consider deleting the model if version creation failed
                self.delete_model(model.model_id)
                return None, None
                
            return model, version
            
        except Exception as e:
            logger.error(f"Error uploading model: {e}")
            return None, None
        
# Singleton instance
_instance = None

def get_instance(
    storage_path: Union[str, Path] = None,
    config: Optional[Dict[str, Any]] = None
) -> ModelRegistry:
    """
    Get or create the singleton instance of the ModelRegistry.
    
    Args:
        storage_path: Path to store models and metadata
        config: Configuration options
        
    Returns:
        ModelRegistry instance
    """
    global _instance
    if _instance is None:
        if storage_path is None:
            storage_path = Path.home() / ".ipfs_kit" / "model_registry"
        _instance = ModelRegistry(storage_path, config)
    return _instance
