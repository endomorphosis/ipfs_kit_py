"""
Model Registry Module for MCP Server

This module provides a comprehensive model registry for machine learning models.
It allows storing, versioning, and retrieving ML models along with their metadata,
performance metrics, and related artifacts.

Key features:
1. Version control for models and related artifacts
2. Rich metadata and tagging system
3. Performance metrics tracking
4. Integrations with popular ML frameworks
5. Storage backend abstraction layer

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import json
import time
import logging
import uuid
import hashlib
import threading
import re
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple, BinaryIO
from datetime import datetime
from dataclasses import dataclass, field, asdict

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy not available. Some features will be limited.")

try:
    from huggingface_hub import HfApi, hf_hub_download, upload_file
    HAS_HUGGINGFACE = True
except ImportError:
    HAS_HUGGINGFACE = False
    logger.warning("Hugging Face Hub not available. HF integration will be disabled.")


class ModelFramework(str, Enum):
    """Enum for supported ML frameworks."""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    SCIKIT_LEARN = "scikit-learn"
    XGBOOST = "xgboost"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"
    OTHER = "other"


class ModelStatus(str, Enum):
    """Enum for model lifecycle status."""
    DRAFT = "draft"
    TRAINING = "training"
    EVALUATING = "evaluating"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ArtifactType(str, Enum):
    """Enum for types of model artifacts."""
    MODEL_WEIGHTS = "model_weights"
    CONFIG = "config"
    TOKENIZER = "tokenizer"
    PREPROCESSOR = "preprocessor"
    METADATA = "metadata"
    EVALUATION = "evaluation"
    VISUALIZATION = "visualization"
    DOCUMENTATION = "documentation"
    SAMPLE_DATA = "sample_data"
    TRAINING_CODE = "training_code"
    OTHER = "other"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    # Common metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    
    # Regression metrics
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    r2: Optional[float] = None
    
    # NLP metrics
    perplexity: Optional[float] = None
    bleu_score: Optional[float] = None
    rouge_score: Optional[float] = None
    
    # Custom metrics
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Inference performance
    inference_time_ms: Optional[float] = None
    throughput_qps: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    
    # Evaluation dataset info
    evaluation_dataset: Optional[str] = None
    evaluation_dataset_version: Optional[str] = None
    evaluation_split: Optional[str] = None
    evaluation_timestamp: Optional[str] = None


@dataclass
class ModelArtifact:
    """A model artifact (file associated with a model version)."""
    # Basic info
    id: str
    name: str
    type: ArtifactType
    description: Optional[str] = None
    
    # Storage info
    path: str  # Path in the storage backend
    size_bytes: int = 0
    content_hash: Optional[str] = None
    content_type: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    
    def compute_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash as hex string
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


@dataclass
class ModelVersion:
    """A specific version of a model."""
    # Version info
    id: str
    version: str
    model_id: str
    
    # Basic info
    name: str
    description: Optional[str] = None
    framework: ModelFramework = ModelFramework.CUSTOM
    framework_version: Optional[str] = None
    
    # Status
    status: ModelStatus = ModelStatus.DRAFT
    is_latest: bool = False
    
    # Performance metrics
    metrics: Optional[ModelMetrics] = None
    
    # Artifacts
    artifacts: List[ModelArtifact] = field(default_factory=list)
    
    # Lineage
    parent_version: Optional[str] = None
    dataset_ids: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_by: Optional[str] = None


@dataclass
class Model:
    """A model in the registry (with multiple versions)."""
    # Basic info
    id: str
    name: str
    description: Optional[str] = None
    
    # Organization
    owner: Optional[str] = None
    team: Optional[str] = None
    project: Optional[str] = None
    
    # Categorization
    task_type: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    # Versions
    latest_version: Optional[str] = None
    production_version: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_by: Optional[str] = None


class BaseModelStorage:
    """Base class for model storage backends."""
    
    def __init__(self):
        """Initialize the storage backend."""
        pass
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        raise NotImplementedError("Subclasses must implement this method")


class FileSystemModelStorage(BaseModelStorage):
    """File system implementation of model storage."""
    
    def __init__(self, base_dir: str):
        """
        Initialize the file system storage.
        
        Args:
            base_dir: Base directory for storing model artifacts
        """
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized file system model storage at {self.base_dir}")
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to the file system.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Create the directory structure
        model_dir = os.path.join(self.base_dir, model_id, version_id)
        os.makedirs(model_dir, exist_ok=True)
        
        # Define the file path
        file_path = os.path.join(model_dir, artifact_path)
        
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write the file
        with open(file_path, 'wb') as f:
            f.write(file_obj.read())
        
        # Return the storage path (relative to base_dir)
        return os.path.join(model_id, version_id, artifact_path)
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from the file system.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        file_path = os.path.join(self.base_dir, storage_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Model artifact not found: {file_path}")
        
        return open(file_path, 'rb')
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from the file system.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        file_path = os.path.join(self.base_dir, storage_path)
        if not os.path.exists(file_path):
            return False
        
        os.remove(file_path)
        return True
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in the file system.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        model_dir = os.path.join(self.base_dir, model_id)
        if not os.path.exists(model_dir):
            return []
        
        if version_id:
            version_dir = os.path.join(model_dir, version_id)
            if not os.path.exists(version_dir):
                return []
            
            # List all files recursively
            result = []
            for root, _, files in os.walk(version_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.base_dir)
                    result.append(rel_path)
            
            return result
        else:
            # List all files for all versions
            result = []
            for root, _, files in os.walk(model_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.base_dir)
                    result.append(rel_path)
            
            return result


class S3ModelStorage(BaseModelStorage):
    """Amazon S3 implementation of model storage."""
    
    def __init__(self, bucket_name: str, base_prefix: str = "models/", 
               region_name: Optional[str] = None):
        """
        Initialize the S3 storage.
        
        Args:
            bucket_name: S3 bucket name
            base_prefix: Base prefix for S3 objects
            region_name: AWS region name
        """
        super().__init__()
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix.rstrip("/") + "/"
        self.region_name = region_name
        
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=region_name)
            logger.info(f"Initialized S3 model storage in bucket {bucket_name}")
        except ImportError:
            logger.error("boto3 is required for S3 storage. Please install it: pip install boto3")
            raise
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to S3.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{model_id}/{version_id}/{artifact_path}"
        
        # Upload to S3
        self.s3_client.upload_fileobj(file_obj, self.bucket_name, s3_key)
        
        # Return the storage path (relative to base_prefix)
        return f"{model_id}/{version_id}/{artifact_path}"
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from S3.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        import io
        
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{storage_path}"
        
        # Create a file-like object to write the download to
        file_obj = io.BytesIO()
        
        try:
            # Download from S3
            self.s3_client.download_fileobj(self.bucket_name, s3_key, file_obj)
            
            # Reset file position to beginning
            file_obj.seek(0)
            
            return file_obj
        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            raise
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from S3.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{storage_path}"
        
        try:
            # Delete from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in S3.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        # Generate the S3 prefix
        if version_id:
            prefix = f"{self.base_prefix}{model_id}/{version_id}/"
        else:
            prefix = f"{self.base_prefix}{model_id}/"
        
        try:
            # List objects with the specified prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            result = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Convert S3 key to storage path
                        s3_key = obj['Key']
                        if s3_key.startswith(self.base_prefix):
                            storage_path = s3_key[len(self.base_prefix):]
                            result.append(storage_path)
            
            return result
        except Exception as e:
            logger.error(f"Error listing objects in S3: {e}")
            return []


class IPFSModelStorage(BaseModelStorage):
    """IPFS implementation of model storage."""
    
    def __init__(self, ipfs_client=None, pin: bool = True):
        """
        Initialize the IPFS storage.
        
        Args:
            ipfs_client: IPFS client to use
            pin: Whether to pin files to the IPFS node
        """
        super().__init__()
        self.ipfs_client = ipfs_client
        self.pin = pin
        
        # Mapping from storage paths to IPFS CIDs
        self.path_to_cid: Dict[str, str] = {}
        self.cid_to_path: Dict[str, str] = {}
        
        try:
            if self.ipfs_client is None:
                # Try to import ipfshttpclient
                try:
                    import ipfshttpclient
                    self.ipfs_client = ipfshttpclient.connect()
                except ImportError:
                    # Try to import ipfs_client from our MCP server
                    try:
                        from ipfs_kit_py.ipfs_client import IPFSClient
                        self.ipfs_client = IPFSClient()
                    except ImportError:
                        logger.error("No IPFS client available. Please provide an IPFS client.")
                        raise
            
            logger.info("Initialized IPFS model storage")
        except Exception as e:
            logger.error(f"Error initializing IPFS client: {e}")
            raise
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to IPFS.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Generate the storage path
        storage_path = f"{model_id}/{version_id}/{artifact_path}"
        
        # Add to IPFS
        try:
            result = self.ipfs_client.add(file_obj, pin=self.pin)
            if isinstance(result, list):
                # Some clients return a list of results
                cid = result[0]['Hash']
            elif isinstance(result, dict):
                # Some clients return a single dict
                cid = result['Hash']
            else:
                cid = str(result)
            
            # Store the mapping
            self.path_to_cid[storage_path] = cid
            self.cid_to_path[cid] = storage_path
            
            logger.debug(f"Added to IPFS: {storage_path} -> {cid}")
            
            return storage_path
        except Exception as e:
            logger.error(f"Error adding to IPFS: {e}")
            raise
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from IPFS.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        import io
        
        # Get the CID
        cid = self.path_to_cid.get(storage_path)
        if not cid:
            raise FileNotFoundError(f"Model artifact not found: {storage_path}")
        
        # Create a file-like object to write the download to
        file_obj = io.BytesIO()
        
        try:
            # Get from IPFS
            content = self.ipfs_client.cat(cid)
            file_obj.write(content)
            file_obj.seek(0)
            
            return file_obj
        except Exception as e:
            logger.error(f"Error getting from IPFS: {e}")
            raise
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from IPFS.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        # Get the CID
        cid = self.path_to_cid.get(storage_path)
        if not cid:
            return False
        
        try:
            # Unpin from IPFS
            if self.pin:
                self.ipfs_client.pin.rm(cid)
            
            # Remove from mappings
            del self.path_to_cid[storage_path]
            del self.cid_to_path[cid]
            
            return True
        except Exception as e:
            logger.error(f"Error unpinning from IPFS: {e}")
            return False
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in IPFS.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        # Generate the prefix
        if version_id:
            prefix = f"{model_id}/{version_id}/"
        else:
            prefix = f"{model_id}/"
        
        # Filter paths by prefix
        result = []
        for path in self.path_to_cid.keys():
            if path.startswith(prefix):
                result.append(path)
        
        return result


class BaseMetadataStore:
    """Base class for model metadata storage."""
    
    def __init__(self):
        """Initialize the metadata store."""
        pass
    
    def save_model(self, model: Model) -> None:
        """
        Save a model's metadata.
        
        Args:
            model: Model to save
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model's metadata.
        
        Args:
            model_id: ID of the model
            
        Returns:
            Model object or None if not found
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_models(self, filters: Optional[Dict[str, Any]] = None, 
                  sort_by: Optional[str] = None, 
                  limit: Optional[int] = None) -> List[Model]:
        """
        List models' metadata.
        
        Args:
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of Model objects
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model(self, model_id: str) -> bool:
        """
        Delete a model's metadata.
        
        Args:
            model_id: ID of the model
            
        Returns:
            True if the model was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def save_model_version(self, version: ModelVersion) -> None:
        """
        Save a model version's metadata.
        
        Args:
            version: ModelVersion to save
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model_version(self, model_id: str, version_id: str) -> Optional[ModelVersion]:
        """
        Get a model version's metadata.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            ModelVersion object or None if not found
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_model_versions(self, model_id: str, 
                          filters: Optional[Dict[str, Any]] = None,
                          sort_by: Optional[str] = None, 
                          limit: Optional[int] = None) -> List[ModelVersion]:
        """
        List a model's versions.
        
        Args:
            model_id: ID of the model
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of ModelVersion objects
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model_version(self, model_id: str, version_id: str) -> bool:
        """
        Delete a model version's metadata.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            True if the version was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")


class JSONFileMetadataStore(BaseMetadataStore):
    """JSON file implementation of model metadata storage."""
    
    def __init__(self, base_dir: str):
        """
        Initialize the JSON file storage.
        
        Args:
            base_dir: Base directory for storing JSON files
        """
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        self.models_dir = os.path.join(self.base_dir, "models")
        self.versions_dir = os.path.join(self.base_dir, "versions")
        
        # Create directories
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
        
        # Cache for models and versions
        self._models_cache: Dict[str, Model] = {}
        self._versions_cache: Dict[str, Dict[str, ModelVersion]] = {}
        
        # For thread safety
        self._lock = threading.RLock()
        
        logger.info(f"Initialized JSON file metadata store at {self.base_dir}")
    
    def _model_to_dict(self, model: Model) -> Dict[str, Any]:
        """Convert a Model object to a dictionary."""
        return asdict(model)
    
    def _dict_to_model(self, data: Dict[str, Any]) -> Model:
        """Convert a dictionary to a Model object."""
        return Model(**data)
    
    def _version_to_dict(self, version: ModelVersion) -> Dict[str, Any]:
        """Convert a ModelVersion object to a dictionary."""
        return asdict(version)
    
    def _dict_to_version(self, data: Dict[str, Any]) -> ModelVersion:
        """Convert a dictionary to a ModelVersion object."""
        # Handle enum fields
        if 'framework' in data and isinstance(data['framework'], str):
            data['framework'] = ModelFramework(data['framework'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ModelStatus(data['status'])
        
        # Handle artifact enum fields
        if 'artifacts' in data:
            for artifact in data['artifacts']:
                if 'type' in artifact and isinstance(artifact['type'], str):
                    artifact['type'] = ArtifactType(artifact['type'])
        
        return ModelVersion(**data)
    
    def save_model(self, model: Model) -> None:
        """
        Save a model's metadata to a JSON file.
        
        Args:
            model: Model to save
        """
        with self._lock:
            # Convert to dict
            model_dict = self._model_to_dict(model)
            
            # Define file path
            file_path = os.path.join(self.models_dir, f"{model.id}.json")
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(model_dict, f, indent=2)
            
            # Update cache
            self._models_cache[model.id] = model
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model's metadata from a JSON file.
        
        Args:
            model_id: ID of the model
            
        Returns:
            Model object or None if not found
        """
        with self._lock:
            # Check cache first
            if model_id in self._models_cache:
                return self._models_cache[model_id]
            
            # Define file path
            file_path = os.path.join(self.models_dir, f"{model_id}.json")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return None
            
            # Read from file
            try:
                with open(file_path, 'r') as f:
                    model_dict = json.load(f)
                
                # Convert to Model object
                model = self._dict_to_model(model_dict)
                
                # Update cache
                self._models_cache[model_id] = model
                
                return model
            except Exception as e:
                logger.error(f"Error reading model from {file_path}: {e}")
                return None
    
    def list_models(self, filters: Optional[Dict[str, Any]] = None, 
                  sort_by: Optional[str] = None, 
                  limit: Optional[int] = None) -> List[Model]:
        """
        List models' metadata from JSON files.
        
        Args:
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of Model objects
        """
        with self._lock:
            # Get all model files
            model_files = [f for f in os.listdir(self.models_dir) if f.endswith('.json')]
            
            # Load all models
            models = []
            for file_name in model_files:
                try:
                    file_path = os.path.join(self.models_dir, file_name)
                    with open(file_path, 'r') as f:
                        model_dict = json.load(f)
                    
                    # Convert to Model object
                    model = self._dict_to_model(model_dict)
                    
                    # Update cache
                    self._models_cache[model.id] = model
                    
                    # Apply filters
                    if filters:
                        include = True
                        for key, value in filters.items():
                            if not hasattr(model, key) or getattr(model, key) != value:
                                include = False
                                break
                        
                        if not include:
                            continue
                    
                    models.append(model)
                except Exception as e:
                    logger.error(f"Error reading model from {file_name}: {e}")
            
            # Sort if requested
            if sort_by and hasattr(Model, sort_by):
                models.sort(key=lambda m: getattr(m, sort_by))
            
            # Limit if requested
            if limit is not None and limit > 0:
                models = models[:limit]
            
            return models
    
    def delete_model(self, model_id: str) -> bool:
        """
        Delete a model's metadata from a JSON file.
        
        Args:
            model_id: ID of the model
            
        Returns:
            True if the model was deleted, False otherwise
        """
        with self._lock:
            # Define file path
            file_path = os.path.join(self.models_dir, f"{model_id}.json")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return False
            
            # Delete file
            os.remove(file_path)
            
            # Remove from cache
            if model_id in self._models_cache:
                del self._models_cache[model_id]
            
            # Also remove any versions
            version_dir = os.path.join(self.versions_dir, model_id)
            if os.path.exists(version_dir):
                for file_name in os.listdir(version_dir):
                    os.remove(os.path.join(version_dir, file_name))
                os.rmdir(version_dir)
            
            # Remove from versions cache
            if model_id in self._versions_cache:
                del self._versions_cache[model_id]
            
            return True
    
    def save_model_version(self, version: ModelVersion) -> None:
        """
        Save a model version's metadata to a JSON file.
        
        Args:
            version: ModelVersion to save
        """
        with self._lock:
            # Convert to dict
            version_dict = self._version_to_dict(version)
            
            # Create version directory for model if it doesn't exist
            model_version_dir = os.path.join(self.versions_dir, version.model_id)
            os.makedirs(model_version_dir, exist_ok=True)
            
            # Define file path
            file_path = os.path.join(model_version_dir, f"{version.id}.json")
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(version_dict, f, indent=2)
            
            # Update cache
            if version.model_id not in self._versions_cache:
                self._versions_cache[version.model_id] = {}
            
            self._versions_cache[version.model_id][version.id] = version
            
            # If this is the latest version, update the model
            model = self.get_model(version.model_id)
            if model and version.is_latest:
                model.latest_version = version.id
                model.updated_at = datetime.utcnow().isoformat()
                self.save_model(model)
    
    def get_model_version(self, model_id: str, version_id: str) -> Optional[ModelVersion]:
        """
        Get a model version's metadata from a JSON file.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            ModelVersion object or None if not found
        """
        with self._lock:
            # Check cache first
            if (model_id in self._versions_cache and 
                version_id in self._versions_cache[model_id]):
                return self._versions_cache[model_id][version_id]
            
            # Define file path
            file_path = os.path.join(self.versions_dir, model_id, f"{version_id}.json")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return None
            
            # Read from file
            try:
                with open(file_path, 'r') as f:
                    version_dict = json.load(f)
                
                # Convert to ModelVersion object
                version = self._dict_to_version(version_dict)
                
                # Update cache
                if model_id not in self._versions_cache:
                    self._versions_cache[model_id] = {}
                
                self._versions_cache[model_id][version_id] = version
                
                return version
            except Exception as e:
                logger.error(f"Error reading model version from {file_path}: {e}")
                return None
    
    def list_model_versions(self, model_id: str, 
                          filters: Optional[Dict[str, Any]] = None,
                          sort_by: Optional[str] = None, 
                          limit: Optional[int] = None) -> List[ModelVersion]:
        """
        List a model's versions from JSON files.
        
        Args:
            model_id: ID of the model
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of ModelVersion objects
        """
        with self._lock:
            # Check if model exists
            model_version_dir = os.path.join(self.versions_dir, model_id)
            if not os.path.exists(model_version_dir):
                return []
            
            # Get all version files
            version_files = [f for f in os.listdir(model_version_dir) if f.endswith('.json')]
            
            # Load all versions
            versions = []
            for file_name in version_files:
                try:
                    file_path = os.path.join(model_version_dir, file_name)
                    with open(file_path, 'r') as f:
                        version_dict = json.load(f)
                    
                    # Convert to ModelVersion object
                    version = self._dict_to_version(version_dict)
                    
                    # Update cache
                    if model_id not in self._versions_cache:
                        self._versions_cache[model_id] = {}
                    
                    self._versions_cache[model_id][version.id] = version
                    
                    # Apply filters
                    if filters:
                        include = True
                        for key, value in filters.items():
                            if not hasattr(version, key) or getattr(version, key) != value:
                                include = False
                                break
                        
                        if not include:
                            continue
                    
                    versions.append(version)
                except Exception as e:
                    logger.error(f"Error reading model version from {file_name}: {e}")
            
            # Sort if requested
            if sort_by and hasattr(ModelVersion, sort_by):
                versions.sort(key=lambda v: getattr(v, sort_by))
            
            # Limit if requested
            if limit is not None and limit > 0:
                versions = versions[:limit]
            
            return versions
    
    def delete_model_version(self, model_id: str, version_id: str) -> bool:
        """
        Delete a model version's metadata from a JSON file.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            True if the version was deleted, False otherwise
        """
        with self._lock:
            # Define file path
            file_path = os.path.join(self.versions_dir, model_id, f"{version_id}.json")
            
            # Check if file exists
            if not os.path.exists(file_path):
                return False
            
            # Get version data (to check if it's the latest)
            version = self.get_model_version(model_id, version_id)
            is_latest = version and version.is_latest
            
            # Delete file
            os.remove(file_path)
            
            # Remove from cache
            if (model_id in self._versions_cache and 
                version_id in self._versions_cache[model_id]):
                del self._versions_cache[model_id][version_id]
            
            # If this was the latest version, update the model
            if is_latest:
                model = self.get_model(model_id)
                if model:
                    model.latest_version = None
                    
                    # Find the newest version
                    versions = self.list_model_versions(model_id, sort_by="created_at")
                    if versions:
                        newest_version = versions[-1]
                        newest_version.is_latest = True
                        model.latest_version = newest_version.id
                        self.save_model_version(newest_version)
                    
                    self.save_model(model)
            
            return True


class ModelRegistry:
    """
    Model Registry for ML models and their versions.
    
    This class provides a centralized registry for storing, versioning, and
    retrieving machine learning models and their related artifacts.
    """
    
    def __init__(self, 
               metadata_store: Optional[BaseMetadataStore] = None,
               model_storage: Optional[BaseModelStorage] = None,
               base_dir: Optional[str] = None):
        """
        Initialize the model registry.
        
        Args:
            metadata_store: Store for model metadata
            model_storage: Storage for model files
            base_dir: Base directory for default file-based stores
        """
        # If base_dir is provided but not the stores, create file-based stores
        if base_dir:
            if not metadata_store:
                metadata_dir = os.path.join(base_dir, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                metadata_store = JSONFileMetadataStore(metadata_dir)
            
            if not model_storage:
                storage_dir = os.path.join(base_dir, "storage")
                os.makedirs(storage_dir, exist_ok=True)
                model_storage = FileSystemModelStorage(storage_dir)
        
        # Ensure we have storage backends
        if not metadata_store:
            raise ValueError("metadata_store must be provided if base_dir is not provided")
        
        if not model_storage:
            raise ValueError("model_storage must be provided if base_dir is not provided")
        
        self.metadata_store = metadata_store
        self.model_storage = model_storage
        
        logger.info("Initialized model registry")
    
    def create_model(self, 
                   name: str, 
                   description: Optional[str] = None,
                   owner: Optional[str] = None,
                   team: Optional[str] = None,
                   project: Optional[str] = None,
                   task_type: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Model:
        """
        Create a new model in the registry.
        
        Args:
            name: Name of the model
            description: Optional description
            owner: Optional owner (user or organization)
            team: Optional team
            project: Optional project
            task_type: Optional task type (e.g., "classification", "segmentation")
            tags: Optional list of tags
            metadata: Optional additional metadata
            
        Returns:
            The created Model object
        """
        # Generate a unique ID
        model_id = str(uuid.uuid4())
        
        # Create the model
        model = Model(
            id=model_id,
            name=name,
            description=description,
            owner=owner,
            team=team,
            project=project,
            task_type=task_type,
            tags=tags or [],
            metadata=metadata or {},
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        # Save the model
        self.metadata_store.save_model(model)
        
        logger.info(f"Created model: {model_id} - {name}")
        
        return model
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model from the registry.
        
        Args:
            model_id: ID of the model
            
        Returns:
            Model object or None if not found
        """
        return self.metadata_store.get_model(model_id)
    
    def list_models(self, 
                  filters: Optional[Dict[str, Any]] = None,
                  sort_by: Optional[str] = None,
                  limit: Optional[int] = None) -> List[Model]:
        """
        List models in the registry.
        
        Args:
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of Model objects
        """
        return self.metadata_store.list_models(filters, sort_by, limit)
    
    def update_model(self, 
                   model_id: str,
                   name: Optional[str] = None,
                   description: Optional[str] = None,
                   owner: Optional[str] = None,
                   team: Optional[str] = None,
                   project: Optional[str] = None,
                   task_type: Optional[str] = None,
                   tags: Optional[List[str]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Optional[Model]:
        """
        Update a model in the registry.
        
        Args:
            model_id: ID of the model to update
            name: Optional new name
            description: Optional new description
            owner: Optional new owner
            team: Optional new team
            project: Optional new project
            task_type: Optional new task type
            tags: Optional new tags
            metadata: Optional new metadata
            
        Returns:
            Updated Model object or None if not found
        """
        # Get the model
        model = self.metadata_store.get_model(model_id)
        if not model:
            return None
        
        # Update fields
        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if owner is not None:
            model.owner = owner
        if team is not None:
            model.team = team
        if project is not None:
            model.project = project
        if task_type is not None:
            model.task_type = task_type
        if tags is not None:
            model.tags = tags
        if metadata is not None:
            # Merge with existing metadata
            model.metadata.update(metadata)
        
        # Update timestamp
        model.updated_at = datetime.utcnow().isoformat()
        
        # Save the model
        self.metadata_store.save_model(model)
        
        return model
    
    def delete_model(self, model_id: str) -> bool:
        """
        Delete a model from the registry.
        
        Args:
            model_id: ID of the model to delete
            
        Returns:
            True if the model was deleted, False otherwise
        """
        # Delete model files from storage
        files = self.model_storage.list_model_files(model_id)
        for file_path in files:
            self.model_storage.delete_model_file(file_path)
        
        # Delete model metadata
        return self.metadata_store.delete_model(model_id)
    
    def create_model_version(self,
                           model_id: str,
                           version: Optional[str] = None,
                           name: Optional[str] = None,
                           description: Optional[str] = None,
                           framework: Optional[Union[ModelFramework, str]] = None,
                           framework_version: Optional[str] = None,
                           parent_version: Optional[str] = None,
                           tags: Optional[List[str]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Optional[ModelVersion]:
        """
        Create a new version of a model.
        
        Args:
            model_id: ID of the model
            version: Optional version string (if not provided, a sequential version will be generated)
            name: Optional name for this version
            description: Optional description
            framework: Optional ML framework used
            framework_version: Optional framework version
            parent_version: Optional ID of the parent version
            tags: Optional list of tags
            metadata: Optional additional metadata
            
        Returns:
            The created ModelVersion object or None if model not found
        """
        # Get the model
        model = self.metadata_store.get_model(model_id)
        if not model:
            return None
        
        # Generate a unique ID for the version
        version_id = str(uuid.uuid4())
        
        # Generate a version string if not provided
        if version is None:
            # List existing versions
            versions = self.metadata_store.list_model_versions(model_id)
            
            # Find the latest version number
            latest_num = 0
            for v in versions:
                try:
                    # Try to extract a number from the version
                    num = int(re.search(r'\d+', v.version).group())
                    latest_num = max(latest_num, num)
                except (AttributeError, ValueError):
                    pass
            
            # Create new version string
            version = f"v{latest_num + 1}"
        
        # Use model name as default version name
        version_name = name or f"{model.name} {version}"
        
        # Convert framework to enum if it's a string
        if isinstance(framework, str):
            try:
                framework = ModelFramework(framework)
            except ValueError:
                framework = ModelFramework.CUSTOM
        
        # Create the model version
        model_version = ModelVersion(
            id=version_id,
            version=version,
            model_id=model_id,
            name=version_name,
            description=description,
            framework=framework or ModelFramework.CUSTOM,
            framework_version=framework_version,
            status=ModelStatus.DRAFT,
            is_latest=True,  # This will be the latest version
            parent_version=parent_version,
            tags=tags or [],
            metadata=metadata or {},
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        # If there was a previous 'latest' version, update it
        if model.latest_version:
            prev_latest = self.metadata_store.get_model_version(model_id, model.latest_version)
            if prev_latest:
                prev_latest.is_latest = False
                self.metadata_store.save_model_version(prev_latest)
        
        # Save the version
        self.metadata_store.save_model_version(model_version)
        
        # Update the model with the new latest version
        model.latest_version = version_id
        model.updated_at = datetime.utcnow().isoformat()
        self.metadata_store.save_model(model)
        
        logger.info(f"Created model version: {model_id} - {version_id} ({version})")
        
        return model_version
    
    def get_model_version(self, model_id: str, version_id: str) -> Optional[ModelVersion]:
        """
        Get a specific version of a model.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version
            
        Returns:
            ModelVersion object or None if not found
        """
        return self.metadata_store.get_model_version(model_id, version_id)
    
    def list_model_versions(self, 
                          model_id: str,
                          filters: Optional[Dict[str, Any]] = None,
                          sort_by: Optional[str] = None,
                          limit: Optional[int] = None) -> List[ModelVersion]:
        """
        List versions of a model.
        
        Args:
            model_id: ID of the model
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of ModelVersion objects
        """
        return self.metadata_store.list_model_versions(model_id, filters, sort_by, limit)
    
    def update_model_version(self,
                           model_id: str,
                           version_id: str,
                           name: Optional[str] = None,
                           description: Optional[str] = None,
                           status: Optional[Union[ModelStatus, str]] = None,
                           metrics: Optional[ModelMetrics] = None,
                           tags: Optional[List[str]] = None,
                           metadata: Optional[Dict[str, Any]] = None) -> Optional[ModelVersion]:
        """
        Update a model version.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version to update
            name: Optional new name
            description: Optional new description
            status: Optional new status
            metrics: Optional performance metrics
            tags: Optional new tags
            metadata: Optional new metadata
            
        Returns:
            Updated ModelVersion object or None if not found
        """
        # Get the version
        version = self.metadata_store.get_model_version(model_id, version_id)
        if not version:
            return None
        
        # Update fields
        if name is not None:
            version.name = name
        if description is not None:
            version.description = description
        if status is not None:
            if isinstance(status, str):
                version.status = ModelStatus(status)
            else:
                version.status = status
        if metrics is not None:
            version.metrics = metrics
        if tags is not None:
            version.tags = tags
        if metadata is not None:
            # Merge with existing metadata
            version.metadata.update(metadata)
        
        # Update timestamp
        version.updated_at = datetime.utcnow().isoformat()
        
        # Save the version
        self.metadata_store.save_model_version(version)
        
        # If this is the production version, update the model
        if version.status == ModelStatus.PRODUCTION:
            model = self.metadata_store.get_model(model_id)
            if model:
                model.production_version = version_id
                model.updated_at = datetime.utcnow().isoformat()
                self.metadata_store.save_model(model)
        
        return version
    
    def delete_model_version(self, model_id: str, version_id: str) -> bool:
        """
        Delete a model version.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version to delete
            
        Returns:
            True if the version was deleted, False otherwise
        """
        # Delete version files from storage
        files = self.model_storage.list_model_files(model_id, version_id)
        for file_path in files:
            self.model_storage.delete_model_file(file_path)
        
        # Delete version metadata
        return self.metadata_store.delete_model_version(model_id, version_id)
    
    def add_model_artifact(self,
                         model_id: str,
                         version_id: str,
                         file_path: str,
                         artifact_type: Union[ArtifactType, str],
                         name: Optional[str] = None,
                         description: Optional[str] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> Optional[ModelArtifact]:
        """
        Add an artifact to a model version.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version
            file_path: Path to the file to add
            artifact_type: Type of artifact
            name: Optional name for the artifact
            description: Optional description
            metadata: Optional additional metadata
            
        Returns:
            The created ModelArtifact object or None if version not found
        """
        # Get the version
        version = self.metadata_store.get_model_version(model_id, version_id)
        if not version:
            return None
        
        # Generate artifact ID
        artifact_id = str(uuid.uuid4())
        
        # Determine artifact name if not provided
        if name is None:
            name = os.path.basename(file_path)
        
        # Convert artifact type to enum if it's a string
        if isinstance(artifact_type, str):
            try:
                artifact_type = ArtifactType(artifact_type)
            except ValueError:
                artifact_type = ArtifactType.OTHER
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Compute content hash
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        content_hash = sha256.hexdigest()
        
        # Determine content type
        content_type = None
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == '.json':
            content_type = 'application/json'
        elif file_ext in ['.pt', '.pth']:
            content_type = 'application/octet-stream'
        elif file_ext == '.onnx':
            content_type = 'application/onnx'
        elif file_ext in ['.h5', '.hdf5']:
            content_type = 'application/x-hdf5'
        elif file_ext == '.pb':
            content_type = 'application/x-protobuf'
        elif file_ext in ['.yaml', '.yml']:
            content_type = 'application/yaml'
        elif file_ext == '.md':
            content_type = 'text/markdown'
        elif file_ext == '.txt':
            content_type = 'text/plain'
        
        # Define artifact path in storage
        artifact_storage_path = f"{artifact_type.value}/{name}"
        
        # Create the artifact object
        artifact = ModelArtifact(
            id=artifact_id,
            name=name,
            type=artifact_type,
            description=description,
            path=artifact_storage_path,
            size_bytes=file_size,
            content_hash=content_hash,
            content_type=content_type,
            metadata=metadata or {},
            created_at=datetime.utcnow().isoformat()
        )
        
        # Upload to storage
        with open(file_path, 'rb') as f:
            storage_path = self.model_storage.save_model_file(
                model_id=model_id,
                version_id=version_id,
                artifact_path=artifact_storage_path,
                file_obj=f
            )
        
        # Update the path if it was changed
        if storage_path != artifact_storage_path:
            artifact.path = storage_path
        
        # Add to version artifacts
        version.artifacts.append(artifact)
        version.updated_at = datetime.utcnow().isoformat()
        
        # Save the version
        self.metadata_store.save_model_version(version)
        
        logger.info(f"Added artifact {artifact_id} to model {model_id} version {version_id}")
        
        return artifact
    
    def get_model_artifact(self, 
                         model_id: str, 
                         version_id: str, 
                         artifact_id: str) -> Optional[ModelArtifact]:
        """
        Get an artifact from a model version.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version
            artifact_id: ID of the artifact
            
        Returns:
            ModelArtifact object or None if not found
        """
        # Get the version
        version = self.metadata_store.get_model_version(model_id, version_id)
        if not version:
            return None
        
        # Find the artifact
        for artifact in version.artifacts:
            if artifact.id == artifact_id:
                return artifact
        
        return None
    
    def get_artifact_content(self, 
                           model_id: str, 
                           version_id: str, 
                           artifact_id: str) -> Optional[BinaryIO]:
        """
        Get the content of an artifact.
        
        Args:
            model_id: ID of the model
            version_id: ID of the version
            artifact_id: ID of the artifact
            
        Returns:
            File-like object containing the artifact data or None if not found
        """
        # Get the artifact
        artifact = self.get_model_artifact(model_id, version_id, artifact_id)
        if not artifact:
            return None
        
        # Get the file from storage
        return self.model_storage.get_model_file(artifact.path)
    
    def delete_model_artifact(self, 
                            model_id: str, 
                            version_id: str, 
                            artifact_id: str) -> bool
"""
Model Registry Module for MCP Server

This module provides a comprehensive model registry for machine learning models.
It allows storing, versioning, and retrieving ML models along with their metadata,
performance metrics, and related artifacts.

Key features:
1. Version control for models and related artifacts
2. Rich metadata and tagging system
3. Performance metrics tracking
4. Integrations with popular ML frameworks
5. Storage backend abstraction layer

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import json
import time
import logging
import uuid
import hashlib
import threading
import re
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple, BinaryIO
from datetime import datetime
from dataclasses import dataclass, field, asdict

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("NumPy not available. Some features will be limited.")

try:
    from huggingface_hub import HfApi, hf_hub_download, upload_file
    HAS_HUGGINGFACE = True
except ImportError:
    HAS_HUGGINGFACE = False
    logger.warning("Hugging Face Hub not available. HF integration will be disabled.")


class ModelFramework(str, Enum):
    """Enum for supported ML frameworks."""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    SCIKIT_LEARN = "scikit-learn"
    XGBOOST = "xgboost"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"
    OTHER = "other"


class ModelStatus(str, Enum):
    """Enum for model lifecycle status."""
    DRAFT = "draft"
    TRAINING = "training"
    EVALUATING = "evaluating"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ArtifactType(str, Enum):
    """Enum for types of model artifacts."""
    MODEL_WEIGHTS = "model_weights"
    CONFIG = "config"
    TOKENIZER = "tokenizer"
    PREPROCESSOR = "preprocessor"
    METADATA = "metadata"
    EVALUATION = "evaluation"
    VISUALIZATION = "visualization"
    DOCUMENTATION = "documentation"
    SAMPLE_DATA = "sample_data"
    TRAINING_CODE = "training_code"
    OTHER = "other"


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    # Common metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    auc_roc: Optional[float] = None
    
    # Regression metrics
    mse: Optional[float] = None
    rmse: Optional[float] = None
    mae: Optional[float] = None
    r2: Optional[float] = None
    
    # NLP metrics
    perplexity: Optional[float] = None
    bleu_score: Optional[float] = None
    rouge_score: Optional[float] = None
    
    # Custom metrics
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Inference performance
    inference_time_ms: Optional[float] = None
    throughput_qps: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    
    # Evaluation dataset info
    evaluation_dataset: Optional[str] = None
    evaluation_dataset_version: Optional[str] = None
    evaluation_split: Optional[str] = None
    evaluation_timestamp: Optional[str] = None


@dataclass
class ModelArtifact:
    """A model artifact (file associated with a model version)."""
    # Basic info
    id: str
    name: str
    type: ArtifactType
    description: Optional[str] = None
    
    # Storage info
    path: str  # Path in the storage backend
    size_bytes: int = 0
    content_hash: Optional[str] = None
    content_type: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    
    def compute_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash as hex string
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


@dataclass
class ModelVersion:
    """A specific version of a model."""
    # Version info
    id: str
    version: str
    model_id: str
    
    # Basic info
    name: str
    description: Optional[str] = None
    framework: ModelFramework = ModelFramework.CUSTOM
    framework_version: Optional[str] = None
    
    # Status
    status: ModelStatus = ModelStatus.DRAFT
    is_latest: bool = False
    
    # Performance metrics
    metrics: Optional[ModelMetrics] = None
    
    # Artifacts
    artifacts: List[ModelArtifact] = field(default_factory=list)
    
    # Lineage
    parent_version: Optional[str] = None
    dataset_ids: List[str] = field(default_factory=list)
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_by: Optional[str] = None


@dataclass
class Model:
    """A model in the registry (with multiple versions)."""
    # Basic info
    id: str
    name: str
    description: Optional[str] = None
    
    # Organization
    owner: Optional[str] = None
    team: Optional[str] = None
    project: Optional[str] = None
    
    # Categorization
    task_type: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    # Versions
    latest_version: Optional[str] = None
    production_version: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_by: Optional[str] = None


class BaseModelStorage:
    """Base class for model storage backends."""
    
    def __init__(self):
        """Initialize the storage backend."""
        pass
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        raise NotImplementedError("Subclasses must implement this method")


class FileSystemModelStorage(BaseModelStorage):
    """File system implementation of model storage."""
    
    def __init__(self, base_dir: str):
        """
        Initialize the file system storage.
        
        Args:
            base_dir: Base directory for storing model artifacts
        """
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)
        logger.info(f"Initialized file system model storage at {self.base_dir}")
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to the file system.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Create the directory structure
        model_dir = os.path.join(self.base_dir, model_id, version_id)
        os.makedirs(model_dir, exist_ok=True)
        
        # Define the file path
        file_path = os.path.join(model_dir, artifact_path)
        
        # Ensure the parent directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write the file
        with open(file_path, 'wb') as f:
            f.write(file_obj.read())
        
        # Return the storage path (relative to base_dir)
        return os.path.join(model_id, version_id, artifact_path)
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from the file system.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        file_path = os.path.join(self.base_dir, storage_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Model artifact not found: {file_path}")
        
        return open(file_path, 'rb')
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from the file system.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        file_path = os.path.join(self.base_dir, storage_path)
        if not os.path.exists(file_path):
            return False
        
        os.remove(file_path)
        return True
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in the file system.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        model_dir = os.path.join(self.base_dir, model_id)
        if not os.path.exists(model_dir):
            return []
        
        if version_id:
            version_dir = os.path.join(model_dir, version_id)
            if not os.path.exists(version_dir):
                return []
            
            # List all files recursively
            result = []
            for root, _, files in os.walk(version_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.base_dir)
                    result.append(rel_path)
            
            return result
        else:
            # List all files for all versions
            result = []
            for root, _, files in os.walk(model_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.base_dir)
                    result.append(rel_path)
            
            return result


class S3ModelStorage(BaseModelStorage):
    """Amazon S3 implementation of model storage."""
    
    def __init__(self, bucket_name: str, base_prefix: str = "models/", 
               region_name: Optional[str] = None):
        """
        Initialize the S3 storage.
        
        Args:
            bucket_name: S3 bucket name
            base_prefix: Base prefix for S3 objects
            region_name: AWS region name
        """
        super().__init__()
        self.bucket_name = bucket_name
        self.base_prefix = base_prefix.rstrip("/") + "/"
        self.region_name = region_name
        
        try:
            import boto3
            self.s3_client = boto3.client('s3', region_name=region_name)
            logger.info(f"Initialized S3 model storage in bucket {bucket_name}")
        except ImportError:
            logger.error("boto3 is required for S3 storage. Please install it: pip install boto3")
            raise
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to S3.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{model_id}/{version_id}/{artifact_path}"
        
        # Upload to S3
        self.s3_client.upload_fileobj(file_obj, self.bucket_name, s3_key)
        
        # Return the storage path (relative to base_prefix)
        return f"{model_id}/{version_id}/{artifact_path}"
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from S3.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        import io
        
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{storage_path}"
        
        # Create a file-like object to write the download to
        file_obj = io.BytesIO()
        
        try:
            # Download from S3
            self.s3_client.download_fileobj(self.bucket_name, s3_key, file_obj)
            
            # Reset file position to beginning
            file_obj.seek(0)
            
            return file_obj
        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            raise
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from S3.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        # Generate the S3 key
        s3_key = f"{self.base_prefix}{storage_path}"
        
        try:
            # Delete from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in S3.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        # Generate the S3 prefix
        if version_id:
            prefix = f"{self.base_prefix}{model_id}/{version_id}/"
        else:
            prefix = f"{self.base_prefix}{model_id}/"
        
        try:
            # List objects with the specified prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            result = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Convert S3 key to storage path
                        s3_key = obj['Key']
                        if s3_key.startswith(self.base_prefix):
                            storage_path = s3_key[len(self.base_prefix):]
                            result.append(storage_path)
            
            return result
        except Exception as e:
            logger.error(f"Error listing objects in S3: {e}")
            return []


class IPFSModelStorage(BaseModelStorage):
    """IPFS implementation of model storage."""
    
    def __init__(self, ipfs_client=None, pin: bool = True):
        """
        Initialize the IPFS storage.
        
        Args:
            ipfs_client: IPFS client to use
            pin: Whether to pin files to the IPFS node
        """
        super().__init__()
        self.ipfs_client = ipfs_client
        self.pin = pin
        
        # Mapping from storage paths to IPFS CIDs
        self.path_to_cid: Dict[str, str] = {}
        self.cid_to_path: Dict[str, str] = {}
        
        try:
            if self.ipfs_client is None:
                # Try to import ipfshttpclient
                try:
                    import ipfshttpclient
                    self.ipfs_client = ipfshttpclient.connect()
                except ImportError:
                    # Try to import ipfs_client from our MCP server
                    try:
                        from ipfs_kit_py.ipfs_client import IPFSClient
                        self.ipfs_client = IPFSClient()
                    except ImportError:
                        logger.error("No IPFS client available. Please provide an IPFS client.")
                        raise
            
            logger.info("Initialized IPFS model storage")
        except Exception as e:
            logger.error(f"Error initializing IPFS client: {e}")
            raise
    
    def save_model_file(self, model_id: str, version_id: str, 
                      artifact_path: str, file_obj: BinaryIO) -> str:
        """
        Save a model artifact file to IPFS.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            artifact_path: Path where the artifact should be stored
            file_obj: File-like object containing the artifact data
            
        Returns:
            Storage path where the file was saved
        """
        # Generate the storage path
        storage_path = f"{model_id}/{version_id}/{artifact_path}"
        
        # Add to IPFS
        try:
            result = self.ipfs_client.add(file_obj, pin=self.pin)
            if isinstance(result, list):
                # Some clients return a list of results
                cid = result[0]['Hash']
            elif isinstance(result, dict):
                # Some clients return a single dict
                cid = result['Hash']
            else:
                cid = str(result)
            
            # Store the mapping
            self.path_to_cid[storage_path] = cid
            self.cid_to_path[cid] = storage_path
            
            logger.debug(f"Added to IPFS: {storage_path} -> {cid}")
            
            return storage_path
        except Exception as e:
            logger.error(f"Error adding to IPFS: {e}")
            raise
    
    def get_model_file(self, storage_path: str) -> BinaryIO:
        """
        Get a model artifact file from IPFS.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            File-like object containing the artifact data
        """
        import io
        
        # Get the CID
        cid = self.path_to_cid.get(storage_path)
        if not cid:
            raise FileNotFoundError(f"Model artifact not found: {storage_path}")
        
        # Create a file-like object to write the download to
        file_obj = io.BytesIO()
        
        try:
            # Get from IPFS
            content = self.ipfs_client.cat(cid)
            file_obj.write(content)
            file_obj.seek(0)
            
            return file_obj
        except Exception as e:
            logger.error(f"Error getting from IPFS: {e}")
            raise
    
    def delete_model_file(self, storage_path: str) -> bool:
        """
        Delete a model artifact file from IPFS.
        
        Args:
            storage_path: Storage path of the artifact
            
        Returns:
            True if the file was deleted, False otherwise
        """
        # Get the CID
        cid = self.path_to_cid.get(storage_path)
        if not cid:
            return False
        
        try:
            # Unpin from IPFS
            if self.pin:
                self.ipfs_client.pin.rm(cid)
            
            # Remove from mappings
            del self.path_to_cid[storage_path]
            del self.cid_to_path[cid]
            
            return True
        except Exception as e:
            logger.error(f"Error unpinning from IPFS: {e}")
            return False
    
    def list_model_files(self, model_id: str, version_id: Optional[str] = None) -> List[str]:
        """
        List model artifact files in IPFS.
        
        Args:
            model_id: ID of the model
            version_id: Optional ID of the model version
            
        Returns:
            List of storage paths for the model's artifacts
        """
        # Generate the prefix
        if version_id:
            prefix = f"{model_id}/{version_id}/"
        else:
            prefix = f"{model_id}/"
        
        # Filter paths by prefix
        result = []
        for path in self.path_to_cid.keys():
            if path.startswith(prefix):
                result.append(path)
        
        return result


class BaseMetadataStore:
    """Base class for model metadata storage."""
    
    def __init__(self):
        """Initialize the metadata store."""
        pass
    
    def save_model(self, model: Model) -> None:
        """
        Save a model's metadata.
        
        Args:
            model: Model to save
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model's metadata.
        
        Args:
            model_id: ID of the model
            
        Returns:
            Model object or None if not found
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_models(self, filters: Optional[Dict[str, Any]] = None, 
                  sort_by: Optional[str] = None, 
                  limit: Optional[int] = None) -> List[Model]:
        """
        List models' metadata.
        
        Args:
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of Model objects
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model(self, model_id: str) -> bool:
        """
        Delete a model's metadata.
        
        Args:
            model_id: ID of the model
            
        Returns:
            True if the model was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def save_model_version(self, version: ModelVersion) -> None:
        """
        Save a model version's metadata.
        
        Args:
            version: ModelVersion to save
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def get_model_version(self, model_id: str, version_id: str) -> Optional[ModelVersion]:
        """
        Get a model version's metadata.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            ModelVersion object or None if not found
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def list_model_versions(self, model_id: str, 
                          filters: Optional[Dict[str, Any]] = None,
                          sort_by: Optional[str] = None, 
                          limit: Optional[int] = None) -> List[ModelVersion]:
        """
        List a model's versions.
        
        Args:
            model_id: ID of the model
            filters: Optional filters to apply
            sort_by: Optional field to sort by
            limit: Optional limit on the number of results
            
        Returns:
            List of ModelVersion objects
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def delete_model_version(self, model_id: str, version_id: str) -> bool:
        """
        Delete a model version's metadata.
        
        Args:
            model_id: ID of the model
            version_id: ID of the model version
            
        Returns:
            True if the version was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")


class JSONFileMetadataStore(BaseMetadataStore):
    """JSON file implementation of model metadata storage."""
    
    def __init__(self, base_dir: str):
        """
        Initialize the JSON file storage.
        
        Args:
            base_dir: Base directory for storing JSON files
        """
        super().__init__()
        self.base_dir = os.path.abspath(base_dir)
        self.models_dir = os.path.join(self.base_dir, "models")
        self.versions_dir = os.path.join(self.base_dir, "versions")
        
        # Create directories
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
        
        # Cache for models and versions
        self._models_cache: Dict[str, Model] = {}
        self._versions_cache: Dict[str, Dict[str, ModelVersion]] = {}
        
        # For thread safety
        self._lock = threading.RLock()
        
        logger.info(f"Initialized JSON file metadata store at {self.base_dir}")
    
    def _model_to_dict(self, model: Model) -> Dict[str, Any]:
        """Convert a Model object to a dictionary."""
        return asdict(model)
    
    def _dict_to_model(self, data: Dict[str, Any]) -> Model:
        """Convert a dictionary to a Model object."""
        return Model(**data)
    
    def _version_to_dict(self, version: ModelVersion) -> Dict[str, Any]:
        """Convert a ModelVersion object to a dictionary."""
        return asdict(version)
    
    def _dict_to_version(self, data: Dict[str, Any]) -> ModelVersion:
        """Convert a dictionary to a ModelVersion object."""
        # Handle enum fields
        if 'framework' in data and isinstance(data['framework'], str):
            data['framework'] = ModelFramework(data['framework'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ModelStatus(data['status'])
        
        # Handle artifact enum fields
        if 'artifacts' in data:
            for artifact in data['artifacts']:
                if 'type' in artifact and isinstance(artifact['type'], str):
                    artifact['type'] = ArtifactType(artifact['type'])
        
        return ModelVersion(**data)
    
    def save_model(self, model: Model) -> None:
        """
        Save a model's metadata to a JSON file.
        
        Args:
            model: Model to save
        """
        with self._lock:
            # Convert to dict
            model_dict = self._model_to_dict(model)
            
            # Define file path
            file_path = os.path.join(self.models_dir, f"{model.id}.json")
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(model_dict, f, indent=2)
            
            # Update cache
            self._models_cache[model.id] = model
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """
        Get a model's metadata from a JSON file.
        
        Args:
            model_id: ID of the model
