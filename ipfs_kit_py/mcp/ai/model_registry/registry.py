"""
MCP Model Registry

This module implements a model registry for machine learning models with:
- Version-controlled model storage
- Comprehensive metadata management
- Model performance tracking
- Deployment configuration management

The registry supports various model formats and frameworks including:
- PyTorch
- TensorFlow
- ONNX
- HuggingFace Transformers
- Custom models

Models are stored across backend storage systems while metadata and versioning
information is managed in a database for efficient querying and retrieval.

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import time
import logging
import hashlib
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_model_registry")

class ModelFormat(Enum):
    """Supported model formats in the registry."""
    PYTORCH = "pytorch"           # PyTorch models (.pt, .pth)
    TENSORFLOW = "tensorflow"     # TensorFlow models (.h5, SavedModel)
    ONNX = "onnx"                 # ONNX format (.onnx)
    HUGGINGFACE = "huggingface"   # HuggingFace model format
    CUSTOM = "custom"             # Custom model format
    
class ModelFramework(Enum):
    """Common ML frameworks supported by the registry."""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    KERAS = "keras"
    HUGGINGFACE = "huggingface"
    SCIKIT_LEARN = "scikit-learn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    ONNX = "onnx"
    FASTAI = "fastai"
    JAX = "jax"
    CUSTOM = "custom"

class ModelType(Enum):
    """Types of machine learning models supported."""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    OBJECT_DETECTION = "object_detection"
    SEGMENTATION = "segmentation"
    NLP = "nlp"
    LANGUAGE_MODEL = "language_model"
    VISION = "vision"
    MULTIMODAL = "multimodal"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    TIME_SERIES = "time_series"
    GENERATIVE = "generative"
    GRAPH = "graph"
    OTHER = "other"

class ModelStatus(Enum):
    """Status of a model version in the registry."""
    DRAFT = "draft"               # Initial state, incomplete
    PENDING = "pending"           # Waiting for validation
    VALIDATED = "validated"       # Validated but not yet approved
    APPROVED = "approved"         # Approved for use
    STAGED = "staged"             # Staged for deployment
    PRODUCTION = "production"     # Currently in production
    DEPRECATED = "deprecated"     # Still usable but not recommended
    ARCHIVED = "archived"         # No longer in active use
    FAILED = "failed"             # Failed validation

@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc: Optional[float] = None
    mse: Optional[float] = None
    mae: Optional[float] = None
    r2: Optional[float] = None
    latency_ms: Optional[float] = None
    throughput_qps: Optional[float] = None
    memory_mb: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetrics':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in asdict(cls())})

@dataclass
class ModelDependency:
    """Model dependency information."""
    name: str
    version: str
    constraint: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelDependency':
        """Create from dictionary."""
        return cls(**data)

@dataclass
class ModelDeploymentConfig:
    """Model deployment configuration."""
    min_resources: Dict[str, Any] = field(default_factory=dict)
    max_resources: Dict[str, Any] = field(default_factory=dict)
    scaling_policy: Dict[str, Any] = field(default_factory=dict)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    serving_config: Dict[str, Any] = field(default_factory=dict)
    custom_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelDeploymentConfig':
        """Create from dictionary."""
        return cls(**data)

@dataclass
class ModelVersion:
    """A specific version of a model in the registry."""
    id: str
    model_id: str
    version: str
    created_at: float
    created_by: str
    storage_backend: str
    storage_location: str
    format: ModelFormat
    size_bytes: int
    description: str = ""
    commit_message: str = ""
    status: ModelStatus = ModelStatus.DRAFT
    framework: Optional[ModelFramework] = None
    framework_version: Optional[str] = None
    dependencies: List[ModelDependency] = field(default_factory=list)
    metrics: Optional[ModelMetrics] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    deployment_config: Optional[ModelDeploymentConfig] = None
    parent_version: Optional[str] = None
    dataset_refs: List[str] = field(default_factory=list)
    experiment_id: Optional[str] = None
    updated_at: Optional[float] = None
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {}
        for k, v in asdict(self).items():
            if k in ["format", "status", "framework"] and v is not None:
                result[k] = v.value
            elif k in ["metrics", "deployment_config"] and v is not None:
                result[k] = v.to_dict()
            elif k == "dependencies":
                result[k] = [d.to_dict() for d in v]
            else:
                result[k] = v
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelVersion':
        """Create from dictionary representation."""
        # Handle enums
        if "format" in data:
            data["format"] = ModelFormat(data["format"])
        if "status" in data:
            data["status"] = ModelStatus(data["status"])
        if "framework" in data and data["framework"]:
            data["framework"] = ModelFramework(data["framework"])
        
        # Handle complex types
        if "metrics" in data and data["metrics"]:
            data["metrics"] = ModelMetrics.from_dict(data["metrics"])
        if "deployment_config" in data and data["deployment_config"]:
            data["deployment_config"] = ModelDeploymentConfig.from_dict(data["deployment_config"])
        if "dependencies" in data:
            data["dependencies"] = [ModelDependency.from_dict(d) for d in data["dependencies"]]
        
        return cls(**data)

@dataclass
class Model:
    """A model in the registry with multiple versions."""
    id: str
    name: str
    owner: str
    created_at: float
    description: str = ""
    model_type: Optional[ModelType] = None
    team: Optional[str] = None
    project: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    latest_version: Optional[str] = None
    production_version: Optional[str] = None
    updated_at: Optional[float] = None
    versions: Dict[str, ModelVersion] = field(default_factory=dict)
    
    def to_dict(self, include_versions: bool = False) -> Dict[str, Any]:
        """
        Convert to dictionary representation.
        
        Args:
            include_versions: Whether to include version details
            
        Returns:
            Dictionary representation
        """
        result = {}
        for k, v in asdict(self).items():
            if k == "model_type" and v is not None:
                result[k] = v.value
            elif k == "versions":
                if include_versions:
                    result[k] = {ver_id: ver.to_dict() for ver_id, ver in v.items()}
                else:
                    result[k] = list(v.keys())
            else:
                result[k] = v
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], versions: Optional[Dict[str, Dict[str, Any]]] = None) -> 'Model':
        """
        Create from dictionary representation.
        
        Args:
            data: Dictionary with model data
            versions: Optional dictionary of version data
            
        Returns:
            Model instance
        """
        # Make a copy to avoid modifying the input
        data_copy = data.copy()
        
        # Handle model_type enum
        if "model_type" in data_copy and data_copy["model_type"]:
            data_copy["model_type"] = ModelType(data_copy["model_type"])
        
        # Handle versions
        if "versions" in data_copy:
            versions_dict = data_copy.pop("versions")
            if isinstance(versions_dict, dict) and all(isinstance(v, dict) for v in versions_dict.values()):
                model_versions = {k: ModelVersion.from_dict(v) for k, v in versions_dict.items()}
            else:
                model_versions = {}
                
                # If versions data is provided, use it
                if versions:
                    for ver_id in versions_dict:
                        if ver_id in versions:
                            model_versions[ver_id] = ModelVersion.from_dict(versions[ver_id])
            
            data_copy["versions"] = model_versions
        else:
            data_copy["versions"] = {}
            
            # If versions data is provided, use it
            if versions:
                data_copy["versions"] = {k: ModelVersion.from_dict(v) for k, v in versions.items()}
        
        return cls(**data_copy)

class ModelRegistryStore:
    """Storage interface for the model registry."""
    
    def __init__(self, store_path: str):
        """
        Initialize the model registry store.
        
        Args:
            store_path: Path to store registry data
        """
        self.store_path = store_path
        
        # Create directories
        self.models_dir = os.path.join(store_path, "models")
        self.versions_dir = os.path.join(store_path, "versions")
        
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
        
        # In-memory caches
        self._models_cache = {}  # id -> Model
        self._versions_cache = {}  # id -> ModelVersion
    
    def save_model(self, model: Model) -> bool:
        """
        Save a model to the store.
        
        Args:
            model: Model to save
            
        Returns:
            Success flag
        """
        try:
            # Save model without versions
            model_dict = model.to_dict(include_versions=False)
            
            # Write to file
            model_path = os.path.join(self.models_dir, f"{model.id}.json")
            with open(model_path, 'w') as f:
                json.dump(model_dict, f, indent=2)
            
            # Update cache
            self._models_cache[model.id] = model
            
            # Save versions separately
            for version_id, version in model.versions.items():
                self.save_version(version)
            
            return True
        except Exception as e:
            logger.error(f"Error saving model {model.id}: {e}")
            return False
    
    def save_version(self, version: ModelVersion) -> bool:
        """
        Save a model version to the store.
        
        Args:
            version: Model version to save
            
        Returns:
            Success flag
        """
        try:
            # Convert to dict
            version_dict = version.to_dict()
            
            # Write to file
            version_path = os.path.join(self.versions_dir, f"{version.id}.json")
            with open(version_path, 'w') as f:
                json.dump(version_dict, f, indent=2)
            
            # Update cache
            self._versions_cache[version.id] = version
            
            return True
        except Exception as e:
            logger.error(f"Error saving version {version.id}: {e}")
            return False
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model or None if not found
        """
        # Check cache
        if model_id in self._models_cache:
            return self._models_cache[model_id]
        
        try:
            # Read model file
            model_path = os.path.join(self.models_dir, f"{model_id}.json")
            if not os.path.exists(model_path):
                logger.warning(f"Model {model_id} not found")
                return None
            
            with open(model_path, 'r') as f:
                model_dict = json.load(f)
            
            # Load versions
            versions = {}
            for version_id in model_dict.get("versions", []):
                version = self.get_version(version_id)
                if version:
                    versions[version_id] = version
            
            # Create model
            model = Model.from_dict(model_dict)
            model.versions = versions
            
            # Update cache
            self._models_cache[model_id] = model
            
            return model
        except Exception as e:
            logger.error(f"Error loading model {model_id}: {e}")
            return None
    
    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """
        Get a model version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            ModelVersion or None if not found
        """
        # Check cache
        if version_id in self._versions_cache:
            return self._versions_cache[version_id]
        
        try:
            # Read version file
            version_path = os.path.join(self.versions_dir, f"{version_id}.json")
            if not os.path.exists(version_path):
                logger.warning(f"Version {version_id} not found")
                return None
            
            with open(version_path, 'r') as f:
                version_dict = json.load(f)
            
            # Create version
            version = ModelVersion.from_dict(version_dict)
            
            # Update cache
            self._versions_cache[version_id] = version
            
            return version
        except Exception as e:
            logger.error(f"Error loading version {version_id}: {e}")
            return None
    
    def list_models(self) -> List[Model]:
        """
        List all models in the registry.
        
        Returns:
            List of models
        """
        models = []
        
        try:
            # Get all model files
            for filename in os.listdir(self.models_dir):
                if filename.endswith(".json"):
                    model_id = filename[:-5]  # Remove .json extension
                    model = self.get_model(model_id)
                    if model:
                        models.append(model)
            
            return models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    def delete_model(self, model_id: str) -> bool:
        """
        Delete a model and all its versions.
        
        Args:
            model_id: Model ID
            
        Returns:
            Success flag
        """
        try:
            # Get model first
            model = self.get_model(model_id)
            if not model:
                logger.warning(f"Model {model_id} not found for deletion")
                return False
            
            # Delete all versions
            for version_id in model.versions.keys():
                self.delete_version(version_id)
            
            # Delete model file
            model_path = os.path.join(self.models_dir, f"{model_id}.json")
            if os.path.exists(model_path):
                os.remove(model_path)
            
            # Remove from cache
            if model_id in self._models_cache:
                del self._models_cache[model_id]
            
            return True
        except Exception as e:
            logger.error(f"Error deleting model {model_id}: {e}")
            return False
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a model version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Success flag
        """
        try:
            # Get version
            version = self.get_version(version_id)
            if not version:
                logger.warning(f"Version {version_id} not found for deletion")
                return False
            
            # Delete version file
            version_path = os.path.join(self.versions_dir, f"{version_id}.json")
            if os.path.exists(version_path):
                os.remove(version_path)
            
            # Remove from cache
            if version_id in self._versions_cache:
                del self._versions_cache[version_id]
            
            # Update model (remove version from versions list)
            model = self.get_model(version.model_id)
            if model and version_id in model.versions:
                del model.versions[version_id]
                
                # Update latest_version if needed
                if model.latest_version == version_id:
                    # Find new latest version
                    latest_version = None
                    latest_time = 0
                    for ver_id, ver in model.versions.items():
                        if ver.created_at > latest_time:
                            latest_time = ver.created_at
                            latest_version = ver_id
                    
                    model.latest_version = latest_version
                
                # Update production_version if needed
                if model.production_version == version_id:
                    model.production_version = None
                
                # Save model
                self.save_model(model)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting version {version_id}: {e}")
            return False
    
    def search_models(
        self,
        name_filter: Optional[str] = None,
        owner_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        model_type_filter: Optional[ModelType] = None,
        team_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None
    ) -> List[Model]:
        """
        Search for models matching criteria.
        
        Args:
            name_filter: Filter by name (contains)
            owner_filter: Filter by owner
            tags_filter: Filter by tags (all must match)
            model_type_filter: Filter by model type
            team_filter: Filter by team
            project_filter: Filter by project
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            
        Returns:
            List of matching models
        """
        # Get all models
        all_models = self.list_models()
        
        # Apply filters
        filtered_models = []
        for model in all_models:
            # Check name
            if name_filter and name_filter.lower() not in model.name.lower():
                continue
            
            # Check owner
            if owner_filter and model.owner != owner_filter:
                continue
            
            # Check tags (all must match)
            if tags_filter and not all(tag in model.tags for tag in tags_filter):
                continue
            
            # Check model type
            if model_type_filter and model.model_type != model_type_filter:
                continue
            
            # Check team
            if team_filter and model.team != team_filter:
                continue
            
            # Check project
            if project_filter and model.project != project_filter:
                continue
            
            # Check creation time
            if created_after and model.created_at < created_after:
                continue
            if created_before and model.created_at > created_before:
                continue
            
            # All filters passed
            filtered_models.append(model)
        
        return filtered_models
    
    def find_versions(
        self,
        model_id: Optional[str] = None,
        status_filter: Optional[ModelStatus] = None,
        framework_filter: Optional[ModelFramework] = None,
        format_filter: Optional[ModelFormat] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        tags_filter: Optional[List[str]] = None
    ) -> List[ModelVersion]:
        """
        Find versions matching criteria.
        
        Args:
            model_id: Filter by model ID
            status_filter: Filter by status
            framework_filter: Filter by framework
            format_filter: Filter by format
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            tags_filter: Filter by tags (all must match)
            
        Returns:
            List of matching versions
        """
        versions = []
        
        # Get all versions or only for specific model
        if model_id:
            model = self.get_model(model_id)
            if model:
                versions = list(model.versions.values())
        else:
            # Scan all version files
            for filename in os.listdir(self.versions_dir):
                if filename.endswith(".json"):
                    version_id = filename[:-5]  # Remove .json extension
                    version = self.get_version(version_id)
                    if version:
                        versions.append(version)
        
        # Apply filters
        filtered_versions = []
        for version in versions:
            # Check status
            if status_filter and version.status != status_filter:
                continue
            
            # Check framework
            if framework_filter and version.framework != framework_filter:
                continue
            
            # Check format
            if format_filter and version.format != format_filter:
                continue
            
            # Check creation time
            if created_after and version.created_at < created_after:
                continue
            if created_before and version.created_at > created_before:
                continue
            
            # Check tags (all must match)
            if tags_filter and not all(tag in version.tags for tag in tags_filter):
                continue
            
            # All filters passed
            filtered_versions.append(version)
        
        return filtered_versions


class ModelRegistry:
    """
    Model Registry for managing ML models and their versions.
    
    The registry provides:
    - Version-controlled model storage
    - Comprehensive metadata management
    - Model performance tracking
    - Deployment configuration management
    """
    
    def __init__(
        self,
        store_path: str,
        backend_manager: Any
    ):
        """
        Initialize the model registry.
        
        Args:
            store_path: Path to store registry data
            backend_manager: Backend manager for storage operations
        """
        self.store = ModelRegistryStore(store_path)
        self.backend_manager = backend_manager
        
        # Ensure the store path exists
        os.makedirs(store_path, exist_ok=True)
        
        logger.info(f"Initialized Model Registry at {store_path}")
    
    async def create_model(
        self,
        name: str,
        owner: str,
        description: str = "",
        model_type: Optional[ModelType] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Model]:
        """
        Create a new model in the registry.
        
        Args:
            name: Model name
            owner: Model owner (user ID)
            description: Optional model description
            model_type: Optional model type
            team: Optional team name
            project: Optional project name
            metadata: Optional metadata
            tags: Optional tags
            
        Returns:
            Created model or None if failed
        """
        # Generate unique ID
        model_id = str(uuid.uuid4())
        
        # Create model
        model = Model(
            id=model_id,
            name=name,
            owner=owner,
            created_at=time.time(),
            description=description,
            model_type=model_type,
            team=team,
            project=project,
            metadata=metadata or {},
            tags=tags or []
        )
        
        # Save model
        if self.store.save_model(model):
            logger.info(f"Created model {model_id}: {name}")
            return model
        else:
            logger.error(f"Failed to create model: {name}")
            return None
    
    async def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model by ID.
        
        Args:
            model_id: Model ID
            
        Returns:
            Model or None if not found
        """
        return self.store.get_model(model_id)
    
    async def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Model]:
        """
        Update a model's metadata.
        
        Args:
            model_id: Model ID
            name: Optional new name
            description: Optional new description
            model_type: Optional new model type
            team: Optional new team
            project: Optional new project
            metadata: Optional new metadata (merged with existing)
            tags: Optional new tags (replaces existing)
            
        Returns:
            Updated model or None if failed
        """
        # Get model
        model = await self.get_model(model_id)
        if not model:
            logger.warning(f"Model {model_id} not found for update")
            return None
        
        # Update fields
        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if model_type is not None:
            model.model_type = model_type
        if team is not None:
            model.team = team
        if project is not None:
            model.project = project
        if metadata is not None:
            model.metadata.update(metadata)
        if tags is not None:
            model.tags = tags
        
        # Update timestamp
        model.updated_at = time.time()
        
        # Save model
        if self.store.save_model(model):
            logger.info(f"Updated model {model_id}")
            return model
        else:
            logger.error(f"Failed to update model {model_id}")
            return None
    
    async def delete_model(self, model_id: str) -> bool:
        """
        Delete a model and all its versions.
        
        Args:
            model_id: Model ID
            
        Returns:
            Success flag
        """
        # Get model to check storage locations
        model = await self.get_model(model_id)
        if not model:
            logger.warning(f"Model {model_id} not found for deletion")
            return False
        
        # Delete storage artifacts (TODO: Implement storage backend cleanup)
        # This would delete actual model files from storage
        
        # Delete model from registry
        success = self.store.delete_model(model_id)
        if success:
            logger.info(f"Deleted model {model_id}")
        else:
            logger.error(f"Failed to delete model {model_id}")
        
        return success
    
    async def create_model_version(
        self,
        model_id: str,
        version: str,
        created_by: str,
        model_data: bytes,
        format: ModelFormat,
        storage_backend: str = "ipfs",
        description: str = "",
        commit_message: str = "",
        framework: Optional[ModelFramework] = None,
        framework_version: Optional[str] = None,
        dependencies: Optional[List[ModelDependency]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        deployment_config: Optional[ModelDeploymentConfig] = None,
        parent_version: Optional[str] = None,
        dataset_refs: Optional[List[str]] = None,
        experiment_id: Optional[str] = None,
        status: ModelStatus = ModelStatus.DRAFT
    ) -> Optional[ModelVersion]:
        """
        Create a new model version.
        
        Args:
            model_id: Model ID
            version: Version string (e.g., "1.0.0")
            created_by: User ID who created the version
            model_data: Model binary data
            format: Model format
            storage_backend: Storage backend name
            description: Optional description
            commit_message: Optional commit message
            framework: Optional model framework
            framework_version: Optional framework version
            dependencies: Optional list of dependencies
            metadata: Optional metadata
            tags: Optional tags
            deployment_config: Optional deployment configuration
            parent_version: Optional parent version ID
            dataset_refs: Optional list of dataset references
            experiment_id: Optional experiment ID
            status: Initial status
            
        Returns:
            Created model version or None if failed
        """
        # Get model
        model = await self.get_model(model_id)
        if not model:
            logger.warning(f"Model {model_id} not found for version creation")
            return None
        
        # Generate unique ID
        version_id = str(uuid.uuid4())
        
        # Calculate checksum
        checksum = hashlib.sha256(model_data).hexdigest()
        
        # Store model data in the storage backend
        storage_location = ""
        try:
            # Get backend
            backend = self.backend_manager.get_backend(storage_backend)
            if not backend:
                logger.error(f"Storage backend {storage_backend} not found")
                return None
            
            # Add content
            timestamp = int(time.time())
            filename = f"{model_id}_{version}_{timestamp}.model"
            
            result = await backend.add_content(
                model_data,
                {"filename": filename, "model_id": model_id, "version": version}
            )
            
            if not result.get("success", False):
                logger.error(f"Failed to store model data: {result.get('error', 'Unknown error')}")
                return None
            
            storage_location = result.get("identifier", "")
            logger.info(f"Stored model data at {storage_backend}:{storage_location}")
        except Exception as e:
            logger.error(f"Error storing model data: {e}")
            return None
        
        # Create version
        model_version = ModelVersion(
            id=version_id,
            model_id=model_id,
            version=version,
            created_at=time.time(),
            created_by=created_by,
            storage_backend=storage_backend,
            storage_location=storage_location,
            format=format,
            size_bytes=len(model_data),
            description=description,
            commit_message=commit_message,
            status=status,
            framework=framework,
            framework_version=framework_version,
            dependencies=dependencies or [],
            metadata=metadata or {},
            tags=tags or [],
            deployment_config=deployment_config,
            parent_version=parent_version,
            dataset_refs=dataset_refs or [],
            experiment_id=experiment_id,
            checksum=checksum
        )
        
        # Save version
        if not self.store.save_version(model_version):
            logger.error(f"Failed to save version {version_id}")
            return None
        
        # Update model
        model.versions[version_id] = model_version
        model.latest_version = version_id
        model.updated_at = time.time()
        
        if not self.store.save_model(model):
            logger.error(f"Failed to update model {model_id} with new version")
            return None
        
        logger.info(f"Created model version {model_id}:{version} ({version_id})")
        return model_version
    
    async def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """
        Get a model version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            ModelVersion or None if not found
        """
        return self.store.get_version(version_id)
    
    async def update_version(
        self,
        version_id: str,
        description: Optional[str] = None,
        status: Optional[ModelStatus] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metrics: Optional[ModelMetrics] = None,
        deployment_config: Optional[ModelDeploymentConfig] = None
    ) -> Optional[ModelVersion]:
        """
        Update a model version's metadata.
        
        Args:
            version_id: Version ID
            description: Optional new description
            status: Optional new status
            metadata: Optional new metadata (merged with existing)
            tags: Optional new tags (replaces existing)
            metrics: Optional performance metrics
            deployment_config: Optional deployment configuration
            
        Returns:
            Updated version or None if failed
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for update")
            return None
        
        # Update fields
        if description is not None:
            version.description = description
        if status is not None:
            version.status = status
        if metadata is not None:
            version.metadata.update(metadata)
        if tags is not None:
            version.tags = tags
        if metrics is not None:
            version.metrics = metrics
        if deployment_config is not None:
            version.deployment_config = deployment_config
        
        # Update timestamp
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Updated version {version_id}")
            
            # Also update the model to ensure consistency
            model = await self.get_model(version.model_id)
            if model:
                model.versions[version_id] = version
                model.updated_at = time.time()
                self.store.save_model(model)
            
            return version
        else:
            logger.error(f"Failed to update version {version_id}")
            return None
    
    async def delete_version(self, version_id: str) -> bool:
        """
        Delete a model version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Success flag
        """
        # Get version to check storage location
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for deletion")
            return False
        
        # Delete storage artifact (TODO: Implement storage backend cleanup)
        # This would delete the actual model file from storage
        
        # Delete version from registry
        success = self.store.delete_version(version_id)
        if success:
            logger.info(f"Deleted version {version_id}")
        else:
            logger.error(f"Failed to delete version {version_id}")
        
        return success
    
    async def set_production_version(self, model_id: str, version_id: str) -> bool:
        """
        Set a version as the production version for a model.
        
        Args:
            model_id: Model ID
            version_id: Version ID to set as production
            
        Returns:
            Success flag
        """
        # Get model
        model = await self.get_model(model_id)
        if not model:
            logger.warning(f"Model {model_id} not found for setting production version")
            return False
        
        # Verify version exists for this model
        if version_id not in model.versions:
            logger.warning(f"Version {version_id} not found in model {model_id}")
            return False
        
        # Check if version is in an appropriate state
        version = model.versions[version_id]
        if version.status not in [ModelStatus.VALIDATED, ModelStatus.APPROVED, ModelStatus.STAGED]:
            logger.warning(f"Version {version_id} has inappropriate status {version.status.value} for production")
            return False
        
        # Update model
        model.production_version = version_id
        model.updated_at = time.time()
        
        # Update version status
        version.status = ModelStatus.PRODUCTION
        version.updated_at = time.time()
        
        # Save model and version
        if self.store.save_model(model) and self.store.save_version(version):
            logger.info(f"Set production version for {model_id} to {version_id}")
            return True
        else:
            logger.error(f"Failed to set production version for {model_id}")
            return False
    
    async def get_model_data(self, version_id: str) -> Optional[bytes]:
        """
        Get the binary data for a model version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Model binary data or None if not found
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found")
            return None
        
        try:
            # Get backend
            backend = self.backend_manager.get_backend(version.storage_backend)
            if not backend:
                logger.error(f"Storage backend {version.storage_backend} not found")
                return None
            
            # Get content
            result = await backend.get_content(version.storage_location)
            
            if not result.get("success", False):
                logger.error(f"Failed to get model data: {result.get('error', 'Unknown error')}")
                return None
            
            data = result.get("data")
            
            # Verify checksum if available
            if version.checksum and isinstance(data, bytes):
                checksum = hashlib.sha256(data).hexdigest()
                if checksum != version.checksum:
                    logger.error(f"Checksum mismatch for {version_id}: expected {version.checksum}, got {checksum}")
                    return None
            
            return data
        except Exception as e:
            logger.error(f"Error getting model data: {e}")
            return None
    
    async def list_models(
        self,
        name_filter: Optional[str] = None,
        owner_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        model_type_filter: Optional[ModelType] = None,
        team_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None
    ) -> List[Model]:
        """
        List models matching criteria.
        
        Args:
            name_filter: Filter by name (contains)
            owner_filter: Filter by owner
            tags_filter: Filter by tags (all must match)
            model_type_filter: Filter by model type
            team_filter: Filter by team
            project_filter: Filter by project
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            
        Returns:
            List of matching models
        """
        return self.store.search_models(
            name_filter=name_filter,
            owner_filter=owner_filter,
            tags_filter=tags_filter,
            model_type_filter=model_type_filter,
            team_filter=team_filter,
            project_filter=project_filter,
            created_after=created_after,
            created_before=created_before
        )
    
    async def list_versions(
        self,
        model_id: Optional[str] = None,
        status_filter: Optional[ModelStatus] = None,
        framework_filter: Optional[ModelFramework] = None,
        format_filter: Optional[ModelFormat] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        tags_filter: Optional[List[str]] = None
    ) -> List[ModelVersion]:
        """
        List versions matching criteria.
        
        Args:
            model_id: Filter by model ID
            status_filter: Filter by status
            framework_filter: Filter by framework
            format_filter: Filter by format
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            tags_filter: Filter by tags (all must match)
            
        Returns:
            List of matching versions
        """
        return self.store.find_versions(
            model_id=model_id,
            status_filter=status_filter,
            framework_filter=framework_filter,
            format_filter=format_filter,
            created_after=created_after,
            created_before=created_before,
            tags_filter=tags_filter
        )
    
    async def record_metrics(
        self,
        version_id: str,
        metrics: ModelMetrics
    ) -> bool:
        """
        Record performance metrics for a model version.
        
        Args:
            version_id: Version ID
            metrics: Performance metrics
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for recording metrics")
            return False
        
        # Update metrics
        version.metrics = metrics
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Recorded metrics for version {version_id}")
            return True
        else:
            logger.error(f"Failed to record metrics for version {version_id}")
            return False
    
    async def update_deployment_config(
        self,
        version_id: str,
        deployment_config: ModelDeploymentConfig
    ) -> bool:
        """
        Update deployment configuration for a model version.
        
        Args:
            version_id: Version ID
            deployment_config: Deployment configuration
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for updating deployment config")
            return False
        
        # Update deployment config
        version.deployment_config = deployment_config
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Updated deployment config for version {version_id}")
            return True
        else:
            logger.error(f"Failed to update deployment config for version {version_id}")
            return False
    
    async def get_production_version(self, model_id: str) -> Optional[ModelVersion]:
        """
        Get the production version for a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Production version or None if not found
        """
        # Get model
        model = await self.get_model(model_id)
        if not model or not model.production_version:
            return None
        
        # Get production version
        return model.versions.get(model.production_version)
    
    async def get_latest_version(self, model_id: str) -> Optional[ModelVersion]:
        """
        Get the latest version for a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Latest version or None if not found
        """
        # Get model
        model = await self.get_model(model_id)
        if not model or not model.latest_version:
            return None
        
        # Get latest version
        return model.versions.get(model.latest_version)
    
    async def compare_versions(
        self,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """
        Compare two model versions.
        
        Args:
            version_id_1: First version ID
            version_id_2: Second version ID
            
        Returns:
            Comparison results
        """
        # Get versions
        v1 = await self.get_version(version_id_1)
        v2 = await self.get_version(version_id_2)
        
        if not v1 or not v2:
            missing = []
            if not v1:
                missing.append(version_id_1)
            if not v2:
                missing.append(version_id_2)
            return {
                "success": False,
                "error": f"Versions not found: {', '.join(missing)}"
            }
        
        # Compare metrics if available
        metrics_comparison = None
        if v1.metrics and v2.metrics:
            m1 = v1.metrics.to_dict()
            m2 = v2.metrics.to_dict()
            
            metrics_comparison = {}
            all_keys = set(m1.keys()) | set(m2.keys())
            
            for key in all_keys:
                val1 = m1.get(key)
                val2 = m2.get(key)
                
                if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                    diff = val2 - val1
                    pct_change = (diff / val1) * 100 if val1 != 0 else float('inf')
                    metrics_comparison[key] = {
                        "v1": val1,
                        "v2": val2,
                        "diff": diff,
                        "pct_change": pct_change
                    }
                else:
                    metrics_comparison[key] = {
                        "v1": val1,
                        "v2": val2,
                        "diff": "N/A"
                    }
        
        # Compare metadata
        metadata_diff = {
            "added": {k: v for k, v in v2.metadata.items() if k not in v1.metadata},
            "removed": {k: v for k, v in v1.metadata.items() if k not in v2.metadata},
            "changed": {
                k: {"v1": v1.metadata[k], "v2": v2.metadata[k]}
                for k in v1.metadata
                if k in v2.metadata and v1.metadata[k] != v2.metadata[k]
            }
        }
        
        # Compare tags
        tags1 = set(v1.tags)
        tags2 = set(v2.tags)
        tags_diff = {
            "added": list(tags2 - tags1),
            "removed": list(tags1 - tags2)
        }
        
        # Compare dependencies
        deps1 = {d.name: d.version for d in v1.dependencies}
        deps2 = {d.name: d.version for d in v2.dependencies}
        deps_diff = {
            "added": {k: v for k, v in deps2.items() if k not in deps1},
            "removed": {k: v for k, v in deps1.items() if k not in deps2},
            "changed": {
                k: {"v1": deps1[k], "v2": deps2[k]}
                for k in deps1
                if k in deps2 and deps1[k] != deps2[k]
            }
        }
        
        return {
            "success": True,
            "v1": {
                "id": v1.id,
                "version": v1.version,
                "created_at": v1.created_at,
                "status": v1.status.value
            },
            "v2": {
                "id": v2.id,
                "version": v2.version,
                "created_at": v2.created_at,
                "status": v2.status.value
            },
            "size_diff_bytes": v2.size_bytes - v1.size_bytes,
            "size_diff_percent": ((v2.size_bytes - v1.size_bytes) / v1.size_bytes) * 100 if v1.size_bytes > 0 else float('inf'),
            "metrics_comparison": metrics_comparison,
            "metadata_diff": metadata_diff,
            "tags_diff": tags_diff,
            "dependencies_diff": deps_diff,
            "basic_info_diff": {
                field: {
                    "v1": getattr(v1, field),
                    "v2": getattr(v2, field)
                }
                for field in ["format", "framework", "framework_version"]
                if getattr(v1, field) != getattr(v2, field)
            }
        }