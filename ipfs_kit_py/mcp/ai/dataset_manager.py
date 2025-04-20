"""
Dataset Manager Module for AI/ML Components in MCP Server

This module provides dataset management capabilities for AI/ML components, including:
1. Dataset versioning
2. Dataset metadata tracking
3. Schema validation
4. Transformation pipelines

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import json
import logging
import threading
import uuid
import shutil
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Set
from pathlib import Path
import datetime
from dataclasses import dataclass, field

# Configure logger
logger = logging.getLogger(__name__)

# Import dependencies
try:
    from ipfs_kit_py.mcp.ai.config import get_instance as get_config_instance
    from ipfs_kit_py.mcp.ai.monitoring import get_metrics_collector, get_health_check, measure_time
except ImportError:
    logger.warning("AI/ML configuration or monitoring modules not available")
    
    # Fallback class for config
    class MockConfig:
        def get(self, key, default=None):
            return default
    
    # Provide fallback for config
    def get_config_instance(*args, **kwargs):
        return MockConfig()
    
    # Fallback class for metrics
    class MockMetricsCollector:
        def counter(self, name, labels=None, value=1):
            return 0
        
        def gauge(self, name, value, labels=None):
            return 0
        
        def histogram(self, name, value, labels=None):
            pass
    
    # Fallback class for health check
    class MockHealthCheck:
        def register_check(self, name, check_func):
            pass
        
        def check_health(self, name):
            return {"status": "unknown"}
        
        def check_overall_health(self):
            return {"status": "unknown"}
    
    # Provide fallback for monitoring
    def get_metrics_collector():
        return MockMetricsCollector()
    
    def get_health_check():
        return MockHealthCheck()
    
    # Simple decorator as fallback for measure_time
    def measure_time(name, labels=None):
        def decorator(func):
            return func
        return decorator


class DatasetFormat(str, Enum):
    """Dataset format types."""
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    IMAGE = "image"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    BINARY = "binary"
    CUSTOM = "custom"


class DatasetDomain(str, Enum):
    """Dataset domain types."""
    TABULAR = "tabular"
    COMPUTER_VISION = "computer_vision"
    NATURAL_LANGUAGE = "natural_language"
    AUDIO = "audio"
    TIME_SERIES = "time_series"
    GRAPH = "graph"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    CUSTOM = "custom"


class DatasetSplit(str, Enum):
    """Dataset split types."""
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    UNSPLIT = "unsplit"


@dataclass
class DatasetFile:
    """Information about a file in a dataset."""
    name: str
    path: str
    format: str = "csv"
    split: str = "train"
    size_bytes: int = 0
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_ref: Optional[str] = None


@dataclass
class DatasetVersion:
    """Dataset version information."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dataset_id: str = ""
    version: str = "1.0.0"
    description: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    files: List[DatasetFile] = field(default_factory=list)
    schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    storage_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "files": [self._file_to_dict(file) for file in self.files],
            "schema": self.schema,
            "metadata": self.metadata,
            "metrics": self.metrics,
            "storage_path": self.storage_path
        }
    
    @staticmethod
    def _file_to_dict(file: DatasetFile) -> Dict[str, Any]:
        """Convert file to dictionary."""
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
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetVersion':
        """Create from dictionary."""
        files = []
        for file_data in data.get("files", []):
            files.append(DatasetFile(
                name=file_data.get("name", ""),
                path=file_data.get("path", ""),
                format=file_data.get("format", "csv"),
                split=file_data.get("split", "train"),
                size_bytes=file_data.get("size_bytes", 0),
                checksum=file_data.get("checksum"),
                metadata=file_data.get("metadata", {}),
                storage_ref=file_data.get("storage_ref")
            ))
        
        created_at = datetime.datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.datetime.now()
        updated_at = datetime.datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else datetime.datetime.now()
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            dataset_id=data.get("dataset_id", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            created_at=created_at,
            updated_at=updated_at,
            files=files,
            schema=data.get("schema", {}),
            metadata=data.get("metadata", {}),
            metrics=data.get("metrics", {}),
            storage_path=data.get("storage_path")
        )


@dataclass
class Dataset:
    """Dataset information."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    versions: List[str] = field(default_factory=list)
    latest_version: Optional[str] = None
    domain: str = "tabular"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    storage_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "versions": self.versions,
            "latest_version": self.latest_version,
            "domain": self.domain,
            "tags": self.tags,
            "metadata": self.metadata,
            "storage_path": self.storage_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dataset':
        """Create from dictionary."""
        created_at = datetime.datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.datetime.now()
        updated_at = datetime.datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else datetime.datetime.now()
        
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            created_at=created_at,
            updated_at=updated_at,
            versions=data.get("versions", []),
            latest_version=data.get("latest_version"),
            domain=data.get("domain", "tabular"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            storage_path=data.get("storage_path")
        )


class DatasetManager:
    """
    Manager for dataset operations.
    
    This class provides methods for managing and accessing datasets.
    """
    
    def __init__(self):
        """Initialize the dataset manager."""
        # For thread safety
        self.lock = threading.RLock()
        
        # Get configuration
        try:
            self.config = get_config_instance()
            self.storage_path = Path(self.config.get("dataset_manager.storage_path", ""))
        except Exception as e:
            logger.warning(f"Error getting configuration: {e}")
            self.config = None
            self.storage_path = Path.home() / ".ipfs_kit" / "ai_ml" / "datasets"
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Metrics
        try:
            self.metrics = get_metrics_collector()
            self.health = get_health_check()
            
            # Register health check
            self.health.register_check("dataset_manager", self._health_check)
        except Exception as e:
            logger.warning(f"Error setting up monitoring: {e}")
            self.metrics = None
            self.health = None
        
        # Initialize in-memory index
        self._index: Dict[str, Dataset] = {}
        self._version_index: Dict[str, DatasetVersion] = {}
        
        # Load index from storage
        self._load_index()
        
        logger.info(f"Dataset manager initialized with storage path: {self.storage_path}")
    
    def _health_check(self) -> Dict[str, Any]:
        """Health check function."""
        try:
            # Verify storage path exists
            if not os.path.exists(self.storage_path):
                return {
                    "status": "error",
                    "error": f"Storage path {self.storage_path} does not exist",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            
            # Count datasets and versions
            dataset_count = len(self._index)
            version_count = len(self._version_index)
            
            # Verify we can write to the storage path
            test_path = self.storage_path / ".health_check"
            try:
                with open(test_path, "w") as f:
                    f.write("test")
                os.unlink(test_path)
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"Cannot write to storage path: {e}",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            
            return {
                "status": "healthy",
                "details": {
                    "storage_path": str(self.storage_path),
                    "dataset_count": dataset_count,
                    "version_count": version_count
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
    
    def _load_index(self):
        """Load index from storage."""
        try:
            # Load datasets
            dataset_index_path = self.storage_path / "dataset_index.json"
            if os.path.exists(dataset_index_path):
                with open(dataset_index_path, "r") as f:
                    datasets_data = json.load(f)
                    
                    for dataset_data in datasets_data:
                        dataset = Dataset.from_dict(dataset_data)
                        self._index[dataset.id] = dataset
            
            # Load versions
            version_index_path = self.storage_path / "version_index.json"
            if os.path.exists(version_index_path):
                with open(version_index_path, "r") as f:
                    versions_data = json.load(f)
                    
                    for version_data in versions_data:
                        version = DatasetVersion.from_dict(version_data)
                        self._version_index[version.id] = version
            
            logger.info(f"Loaded {len(self._index)} datasets and {len(self._version_index)} versions")
        
        except Exception as e:
            logger.error(f"Error loading index: {e}")
    
    def _save_index(self):
        """Save index to storage."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(self.storage_path, exist_ok=True)
            
            # Save datasets
            dataset_index_path = self.storage_path / "dataset_index.json"
            with open(dataset_index_path, "w") as f:
                json.dump([d.to_dict() for d in self._index.values()], f, indent=2)
            
            # Save versions
            version_index_path = self.storage_path / "version_index.json"
            with open(version_index_path, "w") as f:
                json.dump([v.to_dict() for v in self._version_index.values()], f, indent=2)
            
            logger.debug("Saved index")
        
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    @measure_time("dataset_manager.create_dataset")
    def create_dataset(self, 
                      name: str, 
                      description: str = "", 
                      domain: str = "tabular",
                      tags: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Dataset:
        """
        Create a new dataset.
        
        Args:
            name: Dataset name
            description: Dataset description
            domain: Dataset domain (tabular, computer_vision, etc.)
            tags: Optional tags for the dataset
            metadata: Optional metadata
            
        Returns:
            Created dataset
        """
        with self.lock:
            # Generate ID
            dataset_id = str(uuid.uuid4())
            
            # Create dataset
            dataset = Dataset(
                id=dataset_id,
                name=name,
                description=description,
                domain=domain,
                tags=tags or [],
                metadata=metadata or {},
                storage_path=str(self.storage_path / dataset_id)
            )
            
            # Create storage directory
            os.makedirs(dataset.storage_path, exist_ok=True)
            
            # Save dataset
            self._index[dataset_id] = dataset
            self._save_index()
            
            # Log creation
            logger.info(f"Created dataset {dataset_id} ({name})")
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.datasets_created")
            
            return dataset
    
    @measure_time("dataset_manager.get_dataset")
    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Get a dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dataset or None if not found
        """
        with self.lock:
            # Get from index
            dataset = self._index.get(dataset_id)
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.datasets_retrieved")
            
            return dataset
    
    @measure_time("dataset_manager.list_datasets")
    def list_datasets(self, 
                     domain: Optional[str] = None,
                     tag: Optional[str] = None) -> List[Dataset]:
        """
        List datasets.
        
        Args:
            domain: Optional domain filter
            tag: Optional tag filter
            
        Returns:
            List of datasets
        """
        with self.lock:
            results = []
            
            for dataset in self._index.values():
                # Apply domain filter
                if domain and dataset.domain != domain:
                    continue
                
                # Apply tag filter
                if tag and tag not in dataset.tags:
                    continue
                
                results.append(dataset)
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.datasets_listed")
            
            return results
    
    @measure_time("dataset_manager.update_dataset")
    def update_dataset(self, 
                      dataset_id: str,
                      name: Optional[str] = None,
                      description: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[Dataset]:
        """
        Update a dataset.
        
        Args:
            dataset_id: Dataset ID
            name: Optional new name
            description: Optional new description
            tags: Optional new tags
            metadata: Optional new metadata
            
        Returns:
            Updated dataset or None if not found
        """
        with self.lock:
            # Get dataset
            dataset = self._index.get(dataset_id)
            if not dataset:
                return None
            
            # Update fields
            if name is not None:
                dataset.name = name
            
            if description is not None:
                dataset.description = description
            
            if tags is not None:
                dataset.tags = tags
            
            if metadata is not None:
                dataset.metadata = metadata
            
            # Update timestamp
            dataset.updated_at = datetime.datetime.now()
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.datasets_updated")
            
            return dataset
    
    @measure_time("dataset_manager.delete_dataset")
    def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            # Get dataset
            dataset = self._index.get(dataset_id)
            if not dataset:
                return False
            
            # Delete versions
            for version_id in dataset.versions:
                if version_id in self._version_index:
                    del self._version_index[version_id]
            
            # Delete storage
            if dataset.storage_path and os.path.exists(dataset.storage_path):
                shutil.rmtree(dataset.storage_path)
            
            # Delete from index
            del self._index[dataset_id]
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.datasets_deleted")
            
            return True
    
    @measure_time("dataset_manager.create_dataset_version")
    def create_dataset_version(self,
                             dataset_id: str,
                             version: str = "1.0.0",
                             description: str = "",
                             files: Optional[List[Dict[str, Any]]] = None,
                             schema: Optional[Dict[str, Any]] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> Optional[DatasetVersion]:
        """
        Create a new dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            description: Version description
            files: List of file descriptors
            schema: Schema information
            metadata: Optional metadata
            
        Returns:
            Created version or None if dataset not found
        """
        with self.lock:
            # Get dataset
            dataset = self._index.get(dataset_id)
            if not dataset:
                return None
            
            # Generate ID
            version_id = str(uuid.uuid4())
            
            # Process files
            processed_files = []
            if files:
                for file_data in files:
                    file = DatasetFile(
                        name=file_data.get("name", ""),
                        path=file_data.get("path", ""),
                        format=file_data.get("format", "csv"),
                        split=file_data.get("split", "train"),
                        size_bytes=file_data.get("size_bytes", 0),
                        checksum=file_data.get("checksum"),
                        metadata=file_data.get("metadata", {}),
                        storage_ref=file_data.get("storage_ref")
                    )
                    processed_files.append(file)
            
            # Create version
            dataset_version = DatasetVersion(
                id=version_id,
                dataset_id=dataset_id,
                version=version,
                description=description,
                files=processed_files,
                schema=schema or {},
                metadata=metadata or {},
                storage_path=str(Path(dataset.storage_path) / version_id)
            )
            
            # Create storage directory
            os.makedirs(dataset_version.storage_path, exist_ok=True)
            
            # Save version
            self._version_index[version_id] = dataset_version
            
            # Update dataset
            dataset.versions.append(version_id)
            dataset.latest_version = version_id
            dataset.updated_at = datetime.datetime.now()
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.versions_created")
            
            return dataset_version
    
    @measure_time("dataset_manager.get_dataset_version")
    def get_dataset_version(self, version_id: str) -> Optional[DatasetVersion]:
        """
        Get a dataset version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            Dataset version or None if not found
        """
        with self.lock:
            # Get from index
            version = self._version_index.get(version_id)
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.versions_retrieved")
            
            return version
    
    @measure_time("dataset_manager.list_dataset_versions")
    def list_dataset_versions(self, dataset_id: str) -> List[DatasetVersion]:
        """
        List versions for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of dataset versions
        """
        with self.lock:
            # Get dataset
            dataset = self._index.get(dataset_id)
            if not dataset:
                return []
            
            # Get versions
            versions = []
            for version_id in dataset.versions:
                version = self._version_index.get(version_id)
                if version:
                    versions.append(version)
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.versions_listed")
            
            return versions
    
    @measure_time("dataset_manager.update_dataset_version")
    def update_dataset_version(self,
                              version_id: str,
                              description: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None,
                              schema: Optional[Dict[str, Any]] = None) -> Optional[DatasetVersion]:
        """
        Update a dataset version.
        
        Args:
            version_id: Version ID
            description: Optional new description
            metadata: Optional new metadata
            schema: Optional new schema
            
        Returns:
            Updated version or None if not found
        """
        with self.lock:
            # Get version
            version = self._version_index.get(version_id)
            if not version:
                return None
            
            # Update fields
            if description is not None:
                version.description = description
            
            if metadata is not None:
                version.metadata = metadata
            
            if schema is not None:
                version.schema = schema
            
            # Update timestamp
            version.updated_at = datetime.datetime.now()
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.versions_updated")
            
            return version
    
    @measure_time("dataset_manager.delete_dataset_version")
    def delete_dataset_version(self, version_id: str) -> bool:
        """
        Delete a dataset version.
        
        Args:
            version_id: Version ID
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            # Get version
            version = self._version_index.get(version_id)
            if not version:
                return False
            
            # Get dataset
            dataset = self._index.get(version.dataset_id)
            if dataset:
                # Remove from dataset
                if version_id in dataset.versions:
                    dataset.versions.remove(version_id)
                
                # Update latest version
                if dataset.latest_version == version_id:
                    if dataset.versions:
                        dataset.latest_version = dataset.versions[-1]
                    else:
                        dataset.latest_version = None
                
                # Update timestamp
                dataset.updated_at = datetime.datetime.now()
            
            # Delete storage
            if version.storage_path and os.path.exists(version.storage_path):
                shutil.rmtree(version.storage_path)
            
            # Delete from index
            del self._version_index[version_id]
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.versions_deleted")
            
            return True
    
    @measure_time("dataset_manager.add_file_to_version")
    def add_file_to_version(self,
                           version_id: str,
                           file: Dict[str, Any]) -> Optional[DatasetVersion]:
        """
        Add a file to a dataset version.
        
        Args:
            version_id: Version ID
            file: File descriptor
            
        Returns:
            Updated version or None if not found
        """
        with self.lock:
            # Get version
            version = self._version_index.get(version_id)
            if not version:
                return None
            
            # Create file
            dataset_file = DatasetFile(
                name=file.get("name", ""),
                path=file.get("path", ""),
                format=file.get("format", "csv"),
                split=file.get("split", "train"),
                size_bytes=file.get("size_bytes", 0),
                checksum=file.get("checksum"),
                metadata=file.get("metadata", {}),
                storage_ref=file.get("storage_ref")
            )
            
            # Add to version
            version.files.append(dataset_file)
            
            # Update timestamp
            version.updated_at = datetime.datetime.now()
            
            # Save changes
            self._save_index()
            
            # Record metric
            if self.metrics:
                self.metrics.counter("dataset_manager.files_added")
            
            return version


# Singleton instance
_instance = None

def get_instance() -> DatasetManager:
    """
    Get the singleton instance.
    
    Returns:
        DatasetManager instance
    """
    global _instance
    if _instance is None:
        _instance = DatasetManager()
    return _instance
