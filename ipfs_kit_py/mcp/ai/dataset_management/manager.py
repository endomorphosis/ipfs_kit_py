"""
MCP Dataset Management

This module implements a comprehensive dataset management system with:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics
- Dataset lineage tracking

The system supports various types of datasets including:
- Tabular data (CSV, TSV, JSON)
- Image data
- Text data
- Audio data
- Video data
- Time series data
- Graph data
- Mixed data types

Datasets are stored across backend storage systems while metadata and versioning
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
logger = logging.getLogger("mcp_dataset_management")

class DatasetFormat(Enum):
    """Supported dataset formats."""
    CSV = "csv"                   # CSV tabular data
    TSV = "tsv"                   # TSV tabular data
    JSON = "json"                 # JSON data
    JSONL = "jsonl"               # JSON Lines
    PARQUET = "parquet"           # Parquet format
    ARROW = "arrow"               # Apache Arrow format
    IMAGES = "images"             # Image files
    TEXT = "text"                 # Text files
    AUDIO = "audio"               # Audio files
    VIDEO = "video"               # Video files
    MIXED = "mixed"               # Mixed data types
    HUGGINGFACE = "huggingface"   # HuggingFace dataset format
    CUSTOM = "custom"             # Custom format

class DatasetType(Enum):
    """Types of datasets."""
    TABULAR = "tabular"           # Tabular data (rows & columns)
    IMAGE = "image"               # Image data
    TEXT = "text"                 # Text data
    AUDIO = "audio"               # Audio data
    VIDEO = "video"               # Video data
    TIME_SERIES = "time_series"   # Time series data
    GRAPH = "graph"               # Graph/network data
    MIXED = "mixed"               # Mixed data types
    OTHER = "other"               # Other types

class DatasetStatus(Enum):
    """Status of a dataset version."""
    DRAFT = "draft"               # Initial state, incomplete
    UPLOADING = "uploading"       # Data is being uploaded
    VALIDATING = "validating"     # Data is being validated
    PROCESSING = "processing"     # Data is being processed
    READY = "ready"               # Ready for use
    PUBLISHED = "published"       # Officially published
    DEPRECATED = "deprecated"     # Still usable but not recommended
    ARCHIVED = "archived"         # No longer in active use
    CORRUPTED = "corrupted"       # Data integrity issues
    DELETED = "deleted"           # Marked for deletion

class DataLicense(Enum):
    """Common data licenses."""
    CC0 = "cc0"                   # Creative Commons Zero
    CC_BY = "cc-by"               # Creative Commons Attribution
    CC_BY_SA = "cc-by-sa"         # CC Attribution-ShareAlike
    CC_BY_NC = "cc-by-nc"         # CC Attribution-NonCommercial
    CC_BY_NC_SA = "cc-by-nc-sa"   # CC Attribution-NonCommercial-ShareAlike
    CC_BY_ND = "cc-by-nd"         # CC Attribution-NoDerivs
    CC_BY_NC_ND = "cc-by-nc-nd"   # CC Attribution-NonCommercial-NoDerivs
    APACHE2 = "apache-2.0"        # Apache License 2.0
    MIT = "mit"                   # MIT License
    GPL3 = "gpl-3.0"              # GNU GPL v3
    PROPRIETARY = "proprietary"   # Proprietary/Custom
    OTHER = "other"               # Other license

@dataclass
class DataQualityMetrics:
    """Dataset quality metrics."""
    completeness: Optional[float] = None          # Percentage of non-null values
    uniqueness: Optional[float] = None            # Percentage of unique values
    consistency: Optional[float] = None           # Consistency score
    accuracy: Optional[float] = None              # Accuracy score
    integrity: Optional[float] = None             # Data integrity score
    timeliness: Optional[float] = None            # Timeliness score
    num_samples: Optional[int] = None             # Number of samples
    num_features: Optional[int] = None            # Number of features
    missing_values: Optional[int] = None          # Count of missing values
    duplicate_rows: Optional[int] = None          # Count of duplicate rows
    outliers_count: Optional[int] = None          # Count of outliers
    class_distribution: Dict[str, int] = field(default_factory=dict)  # Distribution of classes
    custom_metrics: Dict[str, Any] = field(default_factory=dict)      # Custom metrics
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataQualityMetrics':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in asdict(cls())})

@dataclass
class DataSource:
    """Source information for a dataset."""
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    contact: Optional[str] = None
    citation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSource':
        """Create from dictionary."""
        return cls(**data)

@dataclass
class PreprocessingStep:
    """Dataset preprocessing step."""
    name: str
    description: str
    parameters: Dict[str, Any]
    order: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PreprocessingStep':
        """Create from dictionary."""
        return cls(**data)

@dataclass
class Schema:
    """Dataset schema information."""
    fields: List[Dict[str, Any]]
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Schema':
        """Create from dictionary."""
        return cls(**data)

@dataclass
class DatasetMetadata:
    """Additional dataset metadata."""
    date_created: Optional[str] = None
    date_modified: Optional[str] = None
    language: Optional[str] = None
    geographic_coverage: Optional[List[str]] = None
    temporal_coverage: Optional[Dict[str, Any]] = None
    subject_domain: Optional[List[str]] = None
    collection_methodology: Optional[str] = None
    processing_methodology: Optional[str] = None
    sampling_procedure: Optional[str] = None
    limitations: Optional[str] = None
    usage_notes: Optional[str] = None
    update_frequency: Optional[str] = None
    access_restrictions: Optional[str] = None
    privacy_considerations: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetMetadata':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in asdict(cls())})

@dataclass
class DataLineage:
    """Dataset lineage information."""
    parent_datasets: List[str] = field(default_factory=list)    # Parent dataset IDs
    derived_datasets: List[str] = field(default_factory=list)   # Derived dataset IDs
    source_code_repo: Optional[str] = None                      # Repository URL
    source_code_commit: Optional[str] = None                    # Commit hash
    processing_script: Optional[str] = None                     # Processing script
    transformations: List[Dict[str, Any]] = field(default_factory=list)  # Applied transformations
    creation_timestamp: Optional[float] = None                  # Creation time
    creator_id: Optional[str] = None                            # Creator ID
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataLineage':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in asdict(cls())})

@dataclass
class DatasetVersion:
    """A specific version of a dataset."""
    id: str
    dataset_id: str
    version: str
    created_at: float
    created_by: str
    storage_backend: str
    storage_location: str
    format: DatasetFormat
    size_bytes: int
    file_count: int
    description: str = ""
    commit_message: str = ""
    status: DatasetStatus = DatasetStatus.DRAFT
    license: Optional[DataLicense] = None
    quality_metrics: Optional[DataQualityMetrics] = None
    preprocessing_steps: List[PreprocessingStep] = field(default_factory=list)
    schema: Optional[Schema] = None
    metadata: Optional[DatasetMetadata] = None
    lineage: Optional[DataLineage] = None
    tags: List[str] = field(default_factory=list)
    parent_version: Optional[str] = None
    updated_at: Optional[float] = None
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {}
        for k, v in asdict(self).items():
            if k in ["format", "status", "license"] and v is not None:
                result[k] = v.value
            elif k in ["quality_metrics", "metadata", "lineage"] and v is not None:
                result[k] = v.to_dict()
            elif k == "preprocessing_steps":
                result[k] = [step.to_dict() for step in v]
            elif k == "schema" and v is not None:
                result[k] = v.to_dict()
            else:
                result[k] = v
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetVersion':
        """Create from dictionary representation."""
        # Handle enums
        if "format" in data:
            data["format"] = DatasetFormat(data["format"])
        if "status" in data:
            data["status"] = DatasetStatus(data["status"])
        if "license" in data and data["license"]:
            data["license"] = DataLicense(data["license"])
        
        # Handle complex types
        if "quality_metrics" in data and data["quality_metrics"]:
            data["quality_metrics"] = DataQualityMetrics.from_dict(data["quality_metrics"])
        if "preprocessing_steps" in data:
            data["preprocessing_steps"] = [PreprocessingStep.from_dict(step) for step in data["preprocessing_steps"]]
        if "schema" in data and data["schema"]:
            data["schema"] = Schema.from_dict(data["schema"])
        if "metadata" in data and data["metadata"]:
            data["metadata"] = DatasetMetadata.from_dict(data["metadata"])
        if "lineage" in data and data["lineage"]:
            data["lineage"] = DataLineage.from_dict(data["lineage"])
        
        return cls(**data)

@dataclass
class Dataset:
    """A dataset in the registry with multiple versions."""
    id: str
    name: str
    owner: str
    created_at: float
    description: str = ""
    dataset_type: Optional[DatasetType] = None
    source: Optional[DataSource] = None
    team: Optional[str] = None
    project: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    access_control: Dict[str, Any] = field(default_factory=dict)
    latest_version: Optional[str] = None
    latest_ready_version: Optional[str] = None
    updated_at: Optional[float] = None
    versions: Dict[str, DatasetVersion] = field(default_factory=dict)
    
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
            if k == "dataset_type" and v is not None:
                result[k] = v.value
            elif k == "source" and v is not None:
                result[k] = v.to_dict()
            elif k == "versions":
                if include_versions:
                    result[k] = {ver_id: ver.to_dict() for ver_id, ver in v.items()}
                else:
                    result[k] = list(v.keys())
            else:
                result[k] = v
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], versions: Optional[Dict[str, Dict[str, Any]]] = None) -> 'Dataset':
        """
        Create from dictionary representation.
        
        Args:
            data: Dictionary with dataset data
            versions: Optional dictionary of version data
            
        Returns:
            Dataset instance
        """
        # Make a copy to avoid modifying the input
        data_copy = data.copy()
        
        # Handle dataset_type enum
        if "dataset_type" in data_copy and data_copy["dataset_type"]:
            data_copy["dataset_type"] = DatasetType(data_copy["dataset_type"])
        
        # Handle source
        if "source" in data_copy and data_copy["source"]:
            data_copy["source"] = DataSource.from_dict(data_copy["source"])
        
        # Handle versions
        if "versions" in data_copy:
            versions_dict = data_copy.pop("versions")
            if isinstance(versions_dict, dict) and all(isinstance(v, dict) for v in versions_dict.values()):
                dataset_versions = {k: DatasetVersion.from_dict(v) for k, v in versions_dict.items()}
            else:
                dataset_versions = {}
                
                # If versions data is provided, use it
                if versions:
                    for ver_id in versions_dict:
                        if ver_id in versions:
                            dataset_versions[ver_id] = DatasetVersion.from_dict(versions[ver_id])
            
            data_copy["versions"] = dataset_versions
        else:
            data_copy["versions"] = {}
            
            # If versions data is provided, use it
            if versions:
                data_copy["versions"] = {k: DatasetVersion.from_dict(v) for k, v in versions.items()}
        
        return cls(**data_copy)

class DatasetStore:
    """Storage interface for datasets."""
    
    def __init__(self, store_path: str):
        """
        Initialize the dataset store.
        
        Args:
            store_path: Path to store registry data
        """
        self.store_path = store_path
        
        # Create directories
        self.datasets_dir = os.path.join(store_path, "datasets")
        self.versions_dir = os.path.join(store_path, "versions")
        
        os.makedirs(self.datasets_dir, exist_ok=True)
        os.makedirs(self.versions_dir, exist_ok=True)
        
        # In-memory caches
        self._datasets_cache = {}  # id -> Dataset
        self._versions_cache = {}  # id -> DatasetVersion
    
    def save_dataset(self, dataset: Dataset) -> bool:
        """
        Save a dataset to the store.
        
        Args:
            dataset: Dataset to save
            
        Returns:
            Success flag
        """
        try:
            # Save dataset without versions
            dataset_dict = dataset.to_dict(include_versions=False)
            
            # Write to file
            dataset_path = os.path.join(self.datasets_dir, f"{dataset.id}.json")
            with open(dataset_path, 'w') as f:
                json.dump(dataset_dict, f, indent=2)
            
            # Update cache
            self._datasets_cache[dataset.id] = dataset
            
            # Save versions separately
            for version_id, version in dataset.versions.items():
                self.save_version(version)
            
            return True
        except Exception as e:
            logger.error(f"Error saving dataset {dataset.id}: {e}")
            return False
    
    def save_version(self, version: DatasetVersion) -> bool:
        """
        Save a dataset version to the store.
        
        Args:
            version: Dataset version to save
            
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
    
    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Get a dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dataset or None if not found
        """
        # Check cache
        if dataset_id in self._datasets_cache:
            return self._datasets_cache[dataset_id]
        
        try:
            # Read dataset file
            dataset_path = os.path.join(self.datasets_dir, f"{dataset_id}.json")
            if not os.path.exists(dataset_path):
                logger.warning(f"Dataset {dataset_id} not found")
                return None
            
            with open(dataset_path, 'r') as f:
                dataset_dict = json.load(f)
            
            # Load versions
            versions = {}
            for version_id in dataset_dict.get("versions", []):
                version = self.get_version(version_id)
                if version:
                    versions[version_id] = version
            
            # Create dataset
            dataset = Dataset.from_dict(dataset_dict)
            dataset.versions = versions
            
            # Update cache
            self._datasets_cache[dataset_id] = dataset
            
            return dataset
        except Exception as e:
            logger.error(f"Error loading dataset {dataset_id}: {e}")
            return None
    
    def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        """
        Get a dataset version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            DatasetVersion or None if not found
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
            version = DatasetVersion.from_dict(version_dict)
            
            # Update cache
            self._versions_cache[version_id] = version
            
            return version
        except Exception as e:
            logger.error(f"Error loading version {version_id}: {e}")
            return None
    
    def list_datasets(self) -> List[Dataset]:
        """
        List all datasets in the registry.
        
        Returns:
            List of datasets
        """
        datasets = []
        
        try:
            # Get all dataset files
            for filename in os.listdir(self.datasets_dir):
                if filename.endswith(".json"):
                    dataset_id = filename[:-5]  # Remove .json extension
                    dataset = self.get_dataset(dataset_id)
                    if dataset:
                        datasets.append(dataset)
            
            return datasets
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return []
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset and all its versions.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Success flag
        """
        try:
            # Get dataset first
            dataset = self.get_dataset(dataset_id)
            if not dataset:
                logger.warning(f"Dataset {dataset_id} not found for deletion")
                return False
            
            # Delete all versions
            for version_id in dataset.versions.keys():
                self.delete_version(version_id)
            
            # Delete dataset file
            dataset_path = os.path.join(self.datasets_dir, f"{dataset_id}.json")
            if os.path.exists(dataset_path):
                os.remove(dataset_path)
            
            # Remove from cache
            if dataset_id in self._datasets_cache:
                del self._datasets_cache[dataset_id]
            
            return True
        except Exception as e:
            logger.error(f"Error deleting dataset {dataset_id}: {e}")
            return False
    
    def delete_version(self, version_id: str) -> bool:
        """
        Delete a dataset version.
        
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
            
            # Update dataset (remove version from versions list)
            dataset = self.get_dataset(version.dataset_id)
            if dataset and version_id in dataset.versions:
                del dataset.versions[version_id]
                
                # Update latest_version if needed
                if dataset.latest_version == version_id:
                    # Find new latest version
                    latest_version = None
                    latest_time = 0
                    for ver_id, ver in dataset.versions.items():
                        if ver.created_at > latest_time:
                            latest_time = ver.created_at
                            latest_version = ver_id
                    
                    dataset.latest_version = latest_version
                
                # Update latest_ready_version if needed
                if dataset.latest_ready_version == version_id:
                    # Find new latest ready version
                    latest_ready = None
                    latest_time = 0
                    for ver_id, ver in dataset.versions.items():
                        if ver.status == DatasetStatus.READY and ver.created_at > latest_time:
                            latest_time = ver.created_at
                            latest_ready = ver_id
                    
                    dataset.latest_ready_version = latest_ready
                
                # Save dataset
                self.save_dataset(dataset)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting version {version_id}: {e}")
            return False
    
    def search_datasets(
        self,
        name_filter: Optional[str] = None,
        owner_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        dataset_type_filter: Optional[DatasetType] = None,
        team_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None
    ) -> List[Dataset]:
        """
        Search for datasets matching criteria.
        
        Args:
            name_filter: Filter by name (contains)
            owner_filter: Filter by owner
            tags_filter: Filter by tags (all must match)
            dataset_type_filter: Filter by dataset type
            team_filter: Filter by team
            project_filter: Filter by project
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            
        Returns:
            List of matching datasets
        """
        # Get all datasets
        all_datasets = self.list_datasets()
        
        # Apply filters
        filtered_datasets = []
        for dataset in all_datasets:
            # Check name
            if name_filter and name_filter.lower() not in dataset.name.lower():
                continue
            
            # Check owner
            if owner_filter and dataset.owner != owner_filter:
                continue
            
            # Check tags (all must match)
            if tags_filter and not all(tag in dataset.tags for tag in tags_filter):
                continue
            
            # Check dataset type
            if dataset_type_filter and dataset.dataset_type != dataset_type_filter:
                continue
            
            # Check team
            if team_filter and dataset.team != team_filter:
                continue
            
            # Check project
            if project_filter and dataset.project != project_filter:
                continue
            
            # Check creation time
            if created_after and dataset.created_at < created_after:
                continue
            if created_before and dataset.created_at > created_before:
                continue
            
            # All filters passed
            filtered_datasets.append(dataset)
        
        return filtered_datasets
    
    def find_versions(
        self,
        dataset_id: Optional[str] = None,
        status_filter: Optional[DatasetStatus] = None,
        format_filter: Optional[DatasetFormat] = None,
        license_filter: Optional[DataLicense] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        tags_filter: Optional[List[str]] = None
    ) -> List[DatasetVersion]:
        """
        Find versions matching criteria.
        
        Args:
            dataset_id: Filter by dataset ID
            status_filter: Filter by status
            format_filter: Filter by format
            license_filter: Filter by license
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            tags_filter: Filter by tags (all must match)
            
        Returns:
            List of matching versions
        """
        versions = []
        
        # Get all versions or only for specific dataset
        if dataset_id:
            dataset = self.get_dataset(dataset_id)
            if dataset:
                versions = list(dataset.versions.values())
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
            
            # Check format
            if format_filter and version.format != format_filter:
                continue
            
            # Check license
            if license_filter and version.license != license_filter:
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


class DatasetManager:
    """
    Dataset Manager for handling datasets and their versions.
    
    This manager provides:
    - Dataset and version creation/management
    - Dataset preprocessing pipelines
    - Quality metrics tracking
    - Lineage tracking
    """
    
    def __init__(
        self,
        store_path: str,
        backend_manager: Any
    ):
        """
        Initialize the dataset manager.
        
        Args:
            store_path: Path to store registry data
            backend_manager: Backend manager for storage operations
        """
        self.store = DatasetStore(store_path)
        self.backend_manager = backend_manager
        
        # Ensure the store path exists
        os.makedirs(store_path, exist_ok=True)
        
        logger.info(f"Initialized Dataset Manager at {store_path}")
    
    async def create_dataset(
        self,
        name: str,
        owner: str,
        description: str = "",
        dataset_type: Optional[DatasetType] = None,
        source: Optional[DataSource] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        access_control: Optional[Dict[str, Any]] = None
    ) -> Optional[Dataset]:
        """
        Create a new dataset.
        
        Args:
            name: Dataset name
            owner: Dataset owner (user ID)
            description: Optional dataset description
            dataset_type: Optional dataset type
            source: Optional data source
            team: Optional team name
            project: Optional project name
            metadata: Optional metadata
            tags: Optional tags
            access_control: Optional access control rules
            
        Returns:
            Created dataset or None if failed
        """
        # Generate unique ID
        dataset_id = str(uuid.uuid4())
        
        # Create dataset
        dataset = Dataset(
            id=dataset_id,
            name=name,
            owner=owner,
            created_at=time.time(),
            description=description,
            dataset_type=dataset_type,
            source=source,
            team=team,
            project=project,
            metadata=metadata or {},
            tags=tags or [],
            access_control=access_control or {}
        )
        
        # Save dataset
        if self.store.save_dataset(dataset):
            logger.info(f"Created dataset {dataset_id}: {name}")
            return dataset
        else:
            logger.error(f"Failed to create dataset: {name}")
            return None
    
    async def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Get a dataset by ID.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dataset or None if not found
        """
        return self.store.get_dataset(dataset_id)
    
    async def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        dataset_type: Optional[DatasetType] = None,
        source: Optional[DataSource] = None,
        team: Optional[str] = None,
        project: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        access_control: Optional[Dict[str, Any]] = None
    ) -> Optional[Dataset]:
        """
        Update a dataset's metadata.
        
        Args:
            dataset_id: Dataset ID
            name: Optional new name
            description: Optional new description
            dataset_type: Optional new dataset type
            source: Optional new data source
            team: Optional new team
            project: Optional new project
            metadata: Optional new metadata (merged with existing)
            tags: Optional new tags (replaces existing)
            access_control: Optional new access control rules (merged with existing)
            
        Returns:
            Updated dataset or None if failed
        """
        # Get dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            logger.warning(f"Dataset {dataset_id} not found for update")
            return None
        
        # Update fields
        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        if dataset_type is not None:
            dataset.dataset_type = dataset_type
        if source is not None:
            dataset.source = source
        if team is not None:
            dataset.team = team
        if project is not None:
            dataset.project = project
        if metadata is not None:
            dataset.metadata.update(metadata)
        if tags is not None:
            dataset.tags = tags
        if access_control is not None:
            dataset.access_control.update(access_control)
        
        # Update timestamp
        dataset.updated_at = time.time()
        
        # Save dataset
        if self.store.save_dataset(dataset):
            logger.info(f"Updated dataset {dataset_id}")
            return dataset
        else:
            logger.error(f"Failed to update dataset {dataset_id}")
            return None
    
    async def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset and all its versions.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Success flag
        """
        # Get dataset to check storage locations
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            logger.warning(f"Dataset {dataset_id} not found for deletion")
            return False
        
        # Delete storage artifacts (TODO: Implement storage backend cleanup)
        # This would delete actual dataset files from storage
        
        # Delete dataset from registry
        success = self.store.delete_dataset(dataset_id)
        if success:
            logger.info(f"Deleted dataset {dataset_id}")
        else:
            logger.error(f"Failed to delete dataset {dataset_id}")
        
        return success
    
    async def create_dataset_version(
        self,
        dataset_id: str,
        version: str,
        created_by: str,
        data_files: Dict[str, Any],
        format: DatasetFormat,
        storage_backend: str = "ipfs",
        description: str = "",
        commit_message: str = "",
        file_count: Optional[int] = None,
        license: Optional[DataLicense] = None,
        preprocessing_steps: Optional[List[PreprocessingStep]] = None,
        schema: Optional[Schema] = None,
        metadata: Optional[DatasetMetadata] = None,
        lineage: Optional[DataLineage] = None,
        tags: Optional[List[str]] = None,
        parent_version: Optional[str] = None,
        status: DatasetStatus = DatasetStatus.DRAFT
    ) -> Optional[DatasetVersion]:
        """
        Create a new dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string (e.g., "1.0.0")
            created_by: User ID who created the version
            data_files: Dictionary of data files (name -> content)
            format: Dataset format
            storage_backend: Storage backend name
            description: Optional description
            commit_message: Optional commit message
            file_count: Optional file count (calculated if not provided)
            license: Optional data license
            preprocessing_steps: Optional preprocessing steps
            schema: Optional dataset schema
            metadata: Optional dataset metadata
            lineage: Optional lineage information
            tags: Optional tags
            parent_version: Optional parent version ID
            status: Initial status
            
        Returns:
            Created dataset version or None if failed
        """
        # Get dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            logger.warning(f"Dataset {dataset_id} not found for version creation")
            return None
        
        # Generate unique ID
        version_id = str(uuid.uuid4())
        
        # Prepare data for storage
        storage_location = ""
        total_size = 0
        
        try:
            # Get backend
            backend = self.backend_manager.get_backend(storage_backend)
            if not backend:
                logger.error(f"Storage backend {storage_backend} not found")
                return None
            
            # Create a directory structure for the dataset
            timestamp = int(time.time())
            base_dir = f"{dataset_id}_{version}_{timestamp}"
            
            # Process each file
            checksums = []
            for filename, file_data in data_files.items():
                # Calculate size
                file_size = len(file_data)
                total_size += file_size
                
                # Calculate checksum
                file_checksum = hashlib.sha256(file_data).hexdigest()
                checksums.append(file_checksum)
                
                # Store file
                file_result = await backend.add_content(
                    file_data,
                    {
                        "filename": filename,
                        "dataset_id": dataset_id,
                        "version": version,
                        "base_dir": base_dir
                    }
                )
                
                if not file_result.get("success", False):
                    logger.error(f"Failed to store file {filename}: {file_result.get('error', 'Unknown error')}")
                    return None
                
                logger.debug(f"Stored file {filename} at {storage_backend}:{file_result.get('identifier', '')}")
            
            # Create a metadata file with file listing
            metadata_content = json.dumps({
                "dataset_id": dataset_id,
                "version": version,
                "files": list(data_files.keys()),
                "checksums": checksums,
                "count": len(data_files),
                "total_size": total_size,
                "created_at": timestamp
            }).encode('utf-8')
            
            meta_result = await backend.add_content(
                metadata_content,
                {
                    "filename": f"{base_dir}/_metadata.json",
                    "dataset_id": dataset_id,
                    "version": version,
                    "base_dir": base_dir
                }
            )
            
            if not meta_result.get("success", False):
                logger.error(f"Failed to store metadata: {meta_result.get('error', 'Unknown error')}")
                return None
            
            # Use the metadata file's location as the version's storage location
            storage_location = meta_result.get("identifier", "")
            logger.info(f"Stored dataset version at {storage_backend}:{storage_location}")
            
        except Exception as e:
            logger.error(f"Error storing dataset files: {e}")
            return None
        
        # Set file count
        if file_count is None:
            file_count = len(data_files)
        
        # Calculate overall checksum
        checksum = hashlib.sha256((dataset_id + version + str(timestamp)).encode()).hexdigest()
        
        # Create version
        dataset_version = DatasetVersion(
            id=version_id,
            dataset_id=dataset_id,
            version=version,
            created_at=time.time(),
            created_by=created_by,
            storage_backend=storage_backend,
            storage_location=storage_location,
            format=format,
            size_bytes=total_size,
            file_count=file_count,
            description=description,
            commit_message=commit_message,
            status=status,
            license=license,
            preprocessing_steps=preprocessing_steps or [],
            schema=schema,
            metadata=metadata,
            lineage=lineage,
            tags=tags or [],
            parent_version=parent_version,
            checksum=checksum
        )
        
        # Save version
        if not self.store.save_version(dataset_version):
            logger.error(f"Failed to save version {version_id}")
            return None
        
        # Update dataset
        dataset.versions[version_id] = dataset_version
        dataset.latest_version = version_id
        dataset.updated_at = time.time()
        
        # Update latest_ready_version if applicable
        if status == DatasetStatus.READY:
            dataset.latest_ready_version = version_id
        
        if not self.store.save_dataset(dataset):
            logger.error(f"Failed to update dataset {dataset_id} with new version")
            return None
        
        logger.info(f"Created dataset version {dataset_id}:{version} ({version_id})")
        return dataset_version
    
    async def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        """
        Get a dataset version by ID.
        
        Args:
            version_id: Version ID
            
        Returns:
            DatasetVersion or None if not found
        """
        return self.store.get_version(version_id)
    
    async def update_version(
        self,
        version_id: str,
        description: Optional[str] = None,
        status: Optional[DatasetStatus] = None,
        license: Optional[DataLicense] = None,
        quality_metrics: Optional[DataQualityMetrics] = None,
        preprocessing_steps: Optional[List[PreprocessingStep]] = None,
        schema: Optional[Schema] = None,
        metadata: Optional[DatasetMetadata] = None,
        lineage: Optional[DataLineage] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[DatasetVersion]:
        """
        Update a dataset version's metadata.
        
        Args:
            version_id: Version ID
            description: Optional new description
            status: Optional new status
            license: Optional new license
            quality_metrics: Optional new quality metrics
            preprocessing_steps: Optional new preprocessing steps
            schema: Optional new schema
            metadata: Optional new metadata
            lineage: Optional new lineage information
            tags: Optional new tags
            
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
        if license is not None:
            version.license = license
        if quality_metrics is not None:
            version.quality_metrics = quality_metrics
        if preprocessing_steps is not None:
            version.preprocessing_steps = preprocessing_steps
        if schema is not None:
            version.schema = schema
        if metadata is not None:
            version.metadata = metadata
        if lineage is not None:
            version.lineage = lineage
        if tags is not None:
            version.tags = tags
        
        # Update timestamp
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Updated version {version_id}")
            
            # Also update the dataset to ensure consistency
            dataset = await self.get_dataset(version.dataset_id)
            if dataset:
                dataset.versions[version_id] = version
                dataset.updated_at = time.time()
                
                # Update latest_ready_version if applicable
                if status == DatasetStatus.READY and (
                    dataset.latest_ready_version is None or 
                    version.created_at > dataset.versions.get(dataset.latest_ready_version, DatasetVersion(
                        id="", dataset_id="", version="", created_at=0, created_by="",
                        storage_backend="", storage_location="", format=DatasetFormat.CUSTOM,
                        size_bytes=0, file_count=0
                    )).created_at
                ):
                    dataset.latest_ready_version = version_id
                
                self.store.save_dataset(dataset)
            
            return version
        else:
            logger.error(f"Failed to update version {version_id}")
            return None
    
    async def delete_version(self, version_id: str) -> bool:
        """
        Delete a dataset version.
        
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
        # This would delete the actual dataset files from storage
        
        # Delete version from registry
        success = self.store.delete_version(version_id)
        if success:
            logger.info(f"Deleted version {version_id}")
        else:
            logger.error(f"Failed to delete version {version_id}")
        
        return success
    
    async def set_ready_version(self, dataset_id: str, version_id: str) -> bool:
        """
        Set a version as the ready version for a dataset.
        
        Args:
            dataset_id: Dataset ID
            version_id: Version ID to set as ready
            
        Returns:
            Success flag
        """
        # Get dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            logger.warning(f"Dataset {dataset_id} not found for setting ready version")
            return False
        
        # Verify version exists for this dataset
        if version_id not in dataset.versions:
            logger.warning(f"Version {version_id} not found in dataset {dataset_id}")
            return False
        
        # Update version status
        version = dataset.versions[version_id]
        version.status = DatasetStatus.READY
        version.updated_at = time.time()
        
        # Update dataset
        dataset.latest_ready_version = version_id
        dataset.updated_at = time.time()
        
        # Save version and dataset
        if self.store.save_version(version) and self.store.save_dataset(dataset):
            logger.info(f"Set ready version for {dataset_id} to {version_id}")
            return True
        else:
            logger.error(f"Failed to set ready version for {dataset_id}")
            return False
    
    async def get_dataset_files(
        self,
        version_id: str,
        file_patterns: Optional[List[str]] = None
    ) -> Optional[Dict[str, bytes]]:
        """
        Get the files for a dataset version.
        
        Args:
            version_id: Version ID
            file_patterns: Optional list of file patterns to match
            
        Returns:
            Dictionary of filename -> content or None if failed
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
            
            # Get metadata file
            meta_result = await backend.get_content(version.storage_location)
            
            if not meta_result.get("success", False):
                logger.error(f"Failed to get metadata: {meta_result.get('error', 'Unknown error')}")
                return None
            
            meta_content = meta_result.get("data")
            if not meta_content:
                logger.error("Empty metadata content")
                return None
            
            # Parse metadata
            if isinstance(meta_content, bytes):
                meta_json = json.loads(meta_content.decode('utf-8'))
            else:
                meta_json = meta_content
            
            files = meta_json.get("files", [])
            
            # Filter files by pattern if provided
            if file_patterns:
                import fnmatch
                matched_files = []
                for file in files:
                    if any(fnmatch.fnmatch(file, pattern) for pattern in file_patterns):
                        matched_files.append(file)
                files = matched_files
            
            # Get file contents
            file_contents = {}
            base_dir = meta_json.get("base_dir", None)
            
            for file in files:
                # Construct file path
                if base_dir:
                    file_path = f"{base_dir}/{file}"
                else:
                    file_path = file
                
                # Get file content
                file_result = await backend.get_content(file_path)
                
                if not file_result.get("success", False):
                    logger.warning(f"Failed to get file {file}: {file_result.get('error', 'Unknown error')}")
                    continue
                
                file_content = file_result.get("data")
                if file_content:
                    file_contents[file] = file_content
            
            return file_contents
        
        except Exception as e:
            logger.error(f"Error getting dataset files: {e}")
            return None
    
    async def list_datasets(
        self,
        name_filter: Optional[str] = None,
        owner_filter: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        dataset_type_filter: Optional[DatasetType] = None,
        team_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None
    ) -> List[Dataset]:
        """
        List datasets matching criteria.
        
        Args:
            name_filter: Filter by name (contains)
            owner_filter: Filter by owner
            tags_filter: Filter by tags (all must match)
            dataset_type_filter: Filter by dataset type
            team_filter: Filter by team
            project_filter: Filter by project
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            
        Returns:
            List of matching datasets
        """
        return self.store.search_datasets(
            name_filter=name_filter,
            owner_filter=owner_filter,
            tags_filter=tags_filter,
            dataset_type_filter=dataset_type_filter,
            team_filter=team_filter,
            project_filter=project_filter,
            created_after=created_after,
            created_before=created_before
        )
    
    async def list_versions(
        self,
        dataset_id: Optional[str] = None,
        status_filter: Optional[DatasetStatus] = None,
        format_filter: Optional[DatasetFormat] = None,
        license_filter: Optional[DataLicense] = None,
        created_after: Optional[float] = None,
        created_before: Optional[float] = None,
        tags_filter: Optional[List[str]] = None
    ) -> List[DatasetVersion]:
        """
        List versions matching criteria.
        
        Args:
            dataset_id: Filter by dataset ID
            status_filter: Filter by status
            format_filter: Filter by format
            license_filter: Filter by license
            created_after: Filter by creation time (after)
            created_before: Filter by creation time (before)
            tags_filter: Filter by tags (all must match)
            
        Returns:
            List of matching versions
        """
        return self.store.find_versions(
            dataset_id=dataset_id,
            status_filter=status_filter,
            format_filter=format_filter,
            license_filter=license_filter,
            created_after=created_after,
            created_before=created_before,
            tags_filter=tags_filter
        )
    
    async def record_quality_metrics(
        self,
        version_id: str,
        metrics: DataQualityMetrics
    ) -> bool:
        """
        Record quality metrics for a dataset version.
        
        Args:
            version_id: Version ID
            metrics: Quality metrics
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for recording metrics")
            return False
        
        # Update metrics
        version.quality_metrics = metrics
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Recorded quality metrics for version {version_id}")
            return True
        else:
            logger.error(f"Failed to record quality metrics for version {version_id}")
            return False
    
    async def add_preprocessing_step(
        self,
        version_id: str,
        step: PreprocessingStep
    ) -> bool:
        """
        Add a preprocessing step to a dataset version.
        
        Args:
            version_id: Version ID
            step: Preprocessing step
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for adding preprocessing step")
            return False
        
        # Add step
        version.preprocessing_steps.append(step)
        
        # Sort steps by order
        version.preprocessing_steps.sort(key=lambda s: s.order)
        
        # Update timestamp
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Added preprocessing step to version {version_id}")
            return True
        else:
            logger.error(f"Failed to add preprocessing step to version {version_id}")
            return False
    
    async def update_schema(
        self,
        version_id: str,
        schema: Schema
    ) -> bool:
        """
        Update the schema for a dataset version.
        
        Args:
            version_id: Version ID
            schema: Schema
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for updating schema")
            return False
        
        # Update schema
        version.schema = schema
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Updated schema for version {version_id}")
            return True
        else:
            logger.error(f"Failed to update schema for version {version_id}")
            return False
    
    async def update_lineage(
        self,
        version_id: str,
        lineage: DataLineage
    ) -> bool:
        """
        Update the lineage for a dataset version.
        
        Args:
            version_id: Version ID
            lineage: Lineage information
            
        Returns:
            Success flag
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for updating lineage")
            return False
        
        # Update lineage
        version.lineage = lineage
        version.updated_at = time.time()
        
        # Save version
        if self.store.save_version(version):
            logger.info(f"Updated lineage for version {version_id}")
            return True
        else:
            logger.error(f"Failed to update lineage for version {version_id}")
            return False
    
    async def get_derived_datasets(self, dataset_id: str) -> List[Dataset]:
        """
        Get all datasets derived from a given dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of derived datasets
        """
        derived_datasets = []
        
        # Get all datasets
        all_datasets = self.store.list_datasets()
        
        # Check each dataset's versions for lineage
        for dataset in all_datasets:
            if dataset.id == dataset_id:
                continue
            
            # Check each version
            for version in dataset.versions.values():
                if version.lineage and dataset_id in version.lineage.parent_datasets:
                    derived_datasets.append(dataset)
                    break
        
        return derived_datasets
    
    async def get_ready_version(self, dataset_id: str) -> Optional[DatasetVersion]:
        """
        Get the ready version of a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Ready version or None if not found
        """
        # Get dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset or not dataset.latest_ready_version:
            return None
        
        # Get ready version
        return dataset.versions.get(dataset.latest_ready_version)
    
    async def get_latest_version(self, dataset_id: str) -> Optional[DatasetVersion]:
        """
        Get the latest version of a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Latest version or None if not found
        """
        # Get dataset
        dataset = await self.get_dataset(dataset_id)
        if not dataset or not dataset.latest_version:
            return None
        
        # Get latest version
        return dataset.versions.get(dataset.latest_version)
    
    async def calculate_quality_metrics(
        self,
        version_id: str,
        custom_metrics: Optional[Dict[str, Any]] = None
    ) -> Optional[DataQualityMetrics]:
        """
        Calculate quality metrics for a dataset version.
        
        Args:
            version_id: Version ID
            custom_metrics: Optional custom metrics to include
            
        Returns:
            Calculated metrics or None if failed
        """
        # Get version
        version = await self.get_version(version_id)
        if not version:
            logger.warning(f"Version {version_id} not found for calculating metrics")
            return None
        
        try:
            # Get dataset files
            files = await self.get_dataset_files(version_id)
            if not files:
                logger.error(f"Failed to get dataset files for version {version_id}")
                return None
            
            # Initialize metrics
            metrics = DataQualityMetrics(
                num_samples=0,
                num_features=0,
                missing_values=0,
                duplicate_rows=0,
                outliers_count=0,
                custom_metrics=custom_metrics or {}
            )
            
            # For tabular data, perform more detailed analysis
            if version.format in [DatasetFormat.CSV, DatasetFormat.TSV, DatasetFormat.PARQUET, DatasetFormat.ARROW]:
                # TODO: Implement detailed quality metrics calculation
                # This would typically use pandas, numpy, etc. to analyze the data
                # For now, we just set some placeholder values
                metrics.num_samples = 1000
                metrics.num_features = 10
                metrics.completeness = 0.95
                metrics.uniqueness = 0.8
                metrics.consistency = 0.9
                metrics.integrity = 0.95
            else:
                # For non-tabular data, just set basic metrics
                metrics.num_samples = len(files)
            
            # Record the metrics
            await self.record_quality_metrics(version_id, metrics)
            
            return metrics
        
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            return None