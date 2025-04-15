"""
Dataset Management Module

This module implements version-controlled dataset management:
- Dataset storage and versioning
- Metadata and statistics tracking
- Preprocessing pipelines
- Data quality metrics

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import time
import uuid
import logging
import hashlib
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dataset_management")


class DatasetType(str, Enum):
    """Types of datasets supported by the system."""
    TABULAR = "tabular"
    IMAGE = "image"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    TIME_SERIES = "time_series"
    GRAPH = "graph"
    MULTIMODAL = "multimodal"
    OTHER = "other"


class DatasetFormat(str, Enum):
    """Common file formats for datasets."""
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    AVRO = "avro"
    HDF5 = "hdf5"
    TFRECORD = "tfrecord"
    IMAGES = "images"
    TEXT_FILES = "text"
    AUDIO_FILES = "audio"
    VIDEO_FILES = "video"
    ARROW = "arrow"
    NUMPY = "numpy"
    MIXED = "mixed"
    OTHER = "other"


class DatasetStatus(str, Enum):
    """Status of a dataset in the system."""
    RAW = "raw"                 # Original unprocessed data
    PROCESSING = "processing"   # Currently being processed
    PROCESSED = "processed"     # Ready for use in training
    PUBLISHED = "published"     # Officially available for use
    DEPRECATED = "deprecated"   # No longer recommended
    ARCHIVED = "archived"       # Not active, but kept for reference


class DataQualityStatus(str, Enum):
    """Data quality assessment status."""
    NOT_ASSESSED = "not_assessed"
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


class DatasetManager:
    """
    Dataset Manager for ML datasets.
    
    Provides functionality for storing, versioning, and managing datasets
    along with their metadata, statistics, and quality metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dataset manager.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Set up storage paths
        base_dir = self.config.get("base_dir", "data/datasets")
        self.datasets_dir = os.path.join(base_dir, "datasets")
        self.metadata_dir = os.path.join(base_dir, "metadata")
        self.index_file = os.path.join(base_dir, "dataset_index.json")
        
        # Ensure directories exist
        os.makedirs(self.datasets_dir, exist_ok=True)
        os.makedirs(self.metadata_dir, exist_ok=True)
        
        # Initialize or load dataset index
        self.dataset_index = self._load_dataset_index()
        
        # Default storage backend
        self.default_backend = self.config.get("default_backend", "ipfs")
        
        # Storage backend access
        self.storage_manager = None
        
        logger.info("Dataset Manager initialized")
    
    def _load_dataset_index(self) -> Dict[str, Any]:
        """
        Load the dataset index from disk or create a new one.
        
        Returns:
            Dictionary with dataset index
        """
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading dataset index: {e}")
                return self._create_empty_index()
        else:
            return self._create_empty_index()
    
    def _create_empty_index(self) -> Dict[str, Any]:
        """
        Create an empty dataset index.
        
        Returns:
            Empty dataset index dictionary
        """
        return {
            "datasets": {},
            "tags": {},
            "types": {},
            "formats": {},
            "last_updated": time.time()
        }
    
    def _save_dataset_index(self) -> None:
        """Save the dataset index to disk."""
        self.dataset_index["last_updated"] = time.time()
        
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.dataset_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving dataset index: {e}")
    
    def _generate_dataset_id(self, name: str) -> str:
        """
        Generate a unique dataset ID based on name.
        
        Args:
            name: Dataset name
            
        Returns:
            Unique dataset ID
        """
        # Clean the name for file system use
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())
        # Add timestamp and random component for uniqueness
        timestamp = int(time.time())
        random_component = uuid.uuid4().hex[:8]
        return f"{clean_name}_{timestamp}_{random_component}"
    
    def _get_dataset_dir(self, dataset_id: str) -> str:
        """
        Get the directory for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Path to dataset directory
        """
        return os.path.join(self.datasets_dir, dataset_id)
    
    def _get_version_dir(self, dataset_id: str, version: str) -> str:
        """
        Get the directory for a specific dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Path to version directory
        """
        return os.path.join(self._get_dataset_dir(dataset_id), version)
    
    def _get_metadata_file(self, dataset_id: str) -> str:
        """
        Get the metadata file path for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Path to metadata file
        """
        return os.path.join(self.metadata_dir, f"{dataset_id}.json")
    
    def _get_version_metadata_file(self, dataset_id: str, version: str) -> str:
        """
        Get the metadata file path for a specific dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Path to version metadata file
        """
        return os.path.join(self.metadata_dir, f"{dataset_id}_{version}.json")
    
    def _load_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """
        Load metadata for a dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dictionary with dataset metadata
        """
        metadata_file = self._get_metadata_file(dataset_id)
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading dataset metadata: {e}")
                return {}
        else:
            return {}
    
    def _save_dataset_metadata(self, dataset_id: str, metadata: Dict[str, Any]) -> None:
        """
        Save metadata for a dataset.
        
        Args:
            dataset_id: Dataset ID
            metadata: Metadata dictionary
        """
        metadata_file = self._get_metadata_file(dataset_id)
        
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving dataset metadata: {e}")
    
    def _load_version_metadata(self, dataset_id: str, version: str) -> Dict[str, Any]:
        """
        Load metadata for a specific dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Dictionary with version metadata
        """
        metadata_file = self._get_version_metadata_file(dataset_id, version)
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading version metadata: {e}")
                return {}
        else:
            return {}
    
    def _save_version_metadata(self, dataset_id: str, version: str, metadata: Dict[str, Any]) -> None:
        """
        Save metadata for a specific dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            metadata: Metadata dictionary
        """
        metadata_file = self._get_version_metadata_file(dataset_id, version)
        
        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving version metadata: {e}")
    
    def _update_dataset_references(self, dataset_id: str, metadata: Dict[str, Any]) -> None:
        """
        Update dataset references in the index.
        
        Args:
            dataset_id: Dataset ID
            metadata: Dataset metadata
        """
        # Update type references
        dataset_type = metadata.get("type")
        if dataset_type:
            if dataset_type not in self.dataset_index["types"]:
                self.dataset_index["types"][dataset_type] = []
            if dataset_id not in self.dataset_index["types"][dataset_type]:
                self.dataset_index["types"][dataset_type].append(dataset_id)
        
        # Update format references
        dataset_format = metadata.get("format")
        if dataset_format:
            if dataset_format not in self.dataset_index["formats"]:
                self.dataset_index["formats"][dataset_format] = []
            if dataset_id not in self.dataset_index["formats"][dataset_format]:
                self.dataset_index["formats"][dataset_format].append(dataset_id)
        
        # Update tag references
        tags = metadata.get("tags", [])
        for tag in tags:
            if tag not in self.dataset_index["tags"]:
                self.dataset_index["tags"][tag] = []
            if dataset_id not in self.dataset_index["tags"][tag]:
                self.dataset_index["tags"][tag].append(dataset_id)
    
    def register_dataset(
        self,
        name: str,
        description: str = "",
        dataset_type: Optional[Union[DatasetType, str]] = None,
        dataset_format: Optional[Union[DatasetFormat, str]] = None,
        tags: Optional[List[str]] = None,
        owner: Optional[str] = None,
        source_url: Optional[str] = None,
        license_info: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a new dataset in the system.
        
        Args:
            name: Dataset name
            description: Dataset description
            dataset_type: Type of dataset
            dataset_format: Format of dataset
            tags: List of tags for the dataset
            owner: Owner or creator of the dataset
            source_url: URL where the dataset was sourced from
            license_info: License information for the dataset
            metadata: Additional metadata
            
        Returns:
            Dictionary with registration result
        """
        # Generate dataset ID
        dataset_id = self._generate_dataset_id(name)
        
        # Create dataset directory
        dataset_dir = self._get_dataset_dir(dataset_id)
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Normalize type and format
        if dataset_type is not None:
            dataset_type = dataset_type.value if isinstance(dataset_type, DatasetType) else dataset_type
        
        if dataset_format is not None:
            dataset_format = dataset_format.value if isinstance(dataset_format, DatasetFormat) else dataset_format
        
        # Create dataset metadata
        dataset_metadata = {
            "id": dataset_id,
            "name": name,
            "description": description,
            "type": dataset_type,
            "format": dataset_format,
            "tags": tags or [],
            "owner": owner,
            "source_url": source_url,
            "license_info": license_info,
            "created_at": time.time(),
            "updated_at": time.time(),
            "versions": [],
            "latest_version": None,
            "status": DatasetStatus.RAW.value,
            **metadata or {}
        }
        
        # Save metadata
        self._save_dataset_metadata(dataset_id, dataset_metadata)
        
        # Update dataset index
        self.dataset_index["datasets"][dataset_id] = {
            "name": name,
            "type": dataset_type,
            "format": dataset_format,
            "tags": tags or [],
            "created_at": dataset_metadata["created_at"],
            "updated_at": dataset_metadata["updated_at"],
            "latest_version": None,
            "status": DatasetStatus.RAW.value,
            "quality": DataQualityStatus.NOT_ASSESSED.value
        }
        
        # Update references
        self._update_dataset_references(dataset_id, dataset_metadata)
        
        # Save index
        self._save_dataset_index()
        
        logger.info(f"Registered dataset: {name} with ID: {dataset_id}")
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "metadata": dataset_metadata
        }
    
    def update_dataset(
        self,
        dataset_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        dataset_type: Optional[Union[DatasetType, str]] = None,
        dataset_format: Optional[Union[DatasetFormat, str]] = None,
        tags: Optional[List[str]] = None,
        owner: Optional[str] = None,
        source_url: Optional[str] = None,
        license_info: Optional[str] = None,
        status: Optional[Union[DatasetStatus, str]] = None,
        quality: Optional[Union[DataQualityStatus, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update dataset metadata.
        
        Args:
            dataset_id: Dataset ID
            name: New dataset name
            description: New dataset description
            dataset_type: New dataset type
            dataset_format: New dataset format
            tags: New tags
            owner: New owner
            source_url: New source URL
            license_info: New license information
            status: New dataset status
            quality: New data quality status
            metadata: Additional metadata to update
            
        Returns:
            Dictionary with update result
        """
        # Load existing metadata
        dataset_metadata = self._load_dataset_metadata(dataset_id)
        
        if not dataset_metadata:
            return {
                "success": False,
                "error": f"Dataset with ID {dataset_id} not found"
            }
        
        # Update fields if provided
        if name is not None:
            dataset_metadata["name"] = name
        
        if description is not None:
            dataset_metadata["description"] = description
        
        if dataset_type is not None:
            dataset_metadata["type"] = dataset_type.value if isinstance(dataset_type, DatasetType) else dataset_type
        
        if dataset_format is not None:
            dataset_metadata["format"] = dataset_format.value if isinstance(dataset_format, DatasetFormat) else dataset_format
        
        if tags is not None:
            dataset_metadata["tags"] = tags
        
        if owner is not None:
            dataset_metadata["owner"] = owner
        
        if source_url is not None:
            dataset_metadata["source_url"] = source_url
        
        if license_info is not None:
            dataset_metadata["license_info"] = license_info
        
        if status is not None:
            dataset_metadata["status"] = status.value if isinstance(status, DatasetStatus) else status
        
        # Update additional metadata
        if metadata:
            for key, value in metadata.items():
                if key not in ["id", "created_at", "versions"]:
                    dataset_metadata[key] = value
        
        # Update timestamps
        dataset_metadata["updated_at"] = time.time()
        
        # Save updated metadata
        self._save_dataset_metadata(dataset_id, dataset_metadata)
        
        # Update dataset index
        index_entry = self.dataset_index["datasets"][dataset_id]
        index_entry.update({
            "name": dataset_metadata["name"],
            "type": dataset_metadata["type"],
            "format": dataset_metadata["format"],
            "tags": dataset_metadata["tags"],
            "updated_at": dataset_metadata["updated_at"],
            "status": dataset_metadata["status"]
        })
        
        # Update quality if provided
        if quality is not None:
            quality_value = quality.value if isinstance(quality, DataQualityStatus) else quality
            index_entry["quality"] = quality_value
        
        # Update references
        self._update_dataset_references(dataset_id, dataset_metadata)
        
        # Save index
        self._save_dataset_index()
        
        logger.info(f"Updated dataset metadata for dataset ID: {dataset_id}")
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "metadata": dataset_metadata
        }
    
    def create_dataset_version(
        self,
        dataset_id: str,
        version: str,
        files: Union[str, List[str]],
        description: str = "",
        statistics: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        preprocessing: Optional[List[Dict[str, Any]]] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        backend: Optional[str] = None,
        storage_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new version of a dataset.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            files: Path to the dataset file or directory, or list of files
            description: Version description
            statistics: Dataset statistics
            schema: Dataset schema
            preprocessing: List of preprocessing steps applied
            quality_metrics: Data quality metrics
            backend: Storage backend to use
            storage_options: Additional storage options
            
        Returns:
            Dictionary with version creation result
        """
        # Load dataset metadata
        dataset_metadata = self._load_dataset_metadata(dataset_id)
        
        if not dataset_metadata:
            return {
                "success": False,
                "error": f"Dataset with ID {dataset_id} not found"
            }
        
        # Check if version already exists
        if version in dataset_metadata.get("versions", []):
            return {
                "success": False,
                "error": f"Version {version} already exists for dataset {dataset_id}"
            }
        
        # Create version directory
        version_dir = self._get_version_dir(dataset_id, version)
        os.makedirs(version_dir, exist_ok=True)
        
        # Determine file paths
        file_list = []
        if isinstance(files, str):
            if os.path.isdir(files):
                # If directory, get all files
                for root, _, filenames in os.walk(files):
                    for filename in filenames:
                        file_list.append(os.path.join(root, filename))
            else:
                # Single file
                file_list = [files]
        else:
            # List of files
            file_list = files
        
        # Calculate dataset size and file hashes
        total_size = 0
        file_hashes = {}
        
        for file_path in file_list:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            size = os.path.getsize(file_path)
            total_size += size
            
            try:
                file_hash = self._calculate_file_hash(file_path)
                file_hashes[os.path.basename(file_path)] = {
                    "hash": file_hash,
                    "size": size
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error calculating file hash: {e}"
                }
        
        # Determine storage backend
        backend = backend or self.default_backend
        storage_options = storage_options or {}
        
        # Store dataset files using the appropriate backend
        storage_result = self._store_dataset_files(
            file_list,
            dataset_id,
            version,
            backend,
            storage_options
        )
        
        if not storage_result["success"]:
            return {
                "success": False,
                "error": f"Error storing dataset files: {storage_result.get('error', 'Unknown error')}"
            }
        
        # Calculate overall dataset hash
        dataset_hash = self._calculate_dataset_hash(file_hashes)
        
        # Determine data quality status from metrics
        quality_status = DataQualityStatus.NOT_ASSESSED
        if quality_metrics:
            # Simple heuristic based on metrics
            if "completeness" in quality_metrics and "accuracy" in quality_metrics:
                avg_quality = (quality_metrics["completeness"] + quality_metrics["accuracy"]) / 2
                if avg_quality > 0.9:
                    quality_status = DataQualityStatus.EXCELLENT
                elif avg_quality > 0.8:
                    quality_status = DataQualityStatus.GOOD
                elif avg_quality > 0.6:
                    quality_status = DataQualityStatus.FAIR
                else:
                    quality_status = DataQualityStatus.POOR
        
        # Create version metadata
        version_metadata = {
            "version": version,
            "dataset_id": dataset_id,
            "description": description,
            "file_count": len(file_list),
            "total_size": total_size,
            "file_hashes": file_hashes,
            "dataset_hash": dataset_hash,
            "statistics": statistics or {},
            "schema": schema or {},
            "preprocessing": preprocessing or [],
            "quality_metrics": quality_metrics or {},
            "quality_status": quality_status.value,
            "storage": {
                "backend": backend,
                "locations": storage_result.get("locations", {}),
                "identifiers": storage_result.get("identifiers", {})
            },
            "created_at": time.time(),
            "status": DatasetStatus.PROCESSED.value
        }
        
        # Save version metadata
        self._save_version_metadata(dataset_id, version, version_metadata)
        
        # Update dataset metadata
        if "versions" not in dataset_metadata:
            dataset_metadata["versions"] = []
        
        dataset_metadata["versions"].append(version)
        dataset_metadata["latest_version"] = version
        dataset_metadata["updated_at"] = time.time()
        
        # If this is the first version, update the dataset status to PROCESSED
        if len(dataset_metadata["versions"]) == 1:
            dataset_metadata["status"] = DatasetStatus.PROCESSED.value
        
        self._save_dataset_metadata(dataset_id, dataset_metadata)
        
        # Update dataset index
        self.dataset_index["datasets"][dataset_id]["latest_version"] = version
        self.dataset_index["datasets"][dataset_id]["updated_at"] = dataset_metadata["updated_at"]
        self.dataset_index["datasets"][dataset_id]["status"] = dataset_metadata["status"]
        self.dataset_index["datasets"][dataset_id]["quality"] = quality_status.value
        
        # Save index
        self._save_dataset_index()
        
        logger.info(f"Created version {version} for dataset {dataset_id}")
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "version": version,
            "metadata": version_metadata
        }
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate the SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash of the file
        """
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # Read and update in chunks for large files
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _calculate_dataset_hash(self, file_hashes: Dict[str, Dict[str, Any]]) -> str:
        """
        Calculate a hash for the entire dataset based on individual file hashes.
        
        Args:
            file_hashes: Dictionary of file hashes
            
        Returns:
            Dataset hash
        """
        # Sort files by name for consistent hashing
        sorted_files = sorted(file_hashes.keys())
        
        # Combine all file hashes
        combined_hash = hashlib.sha256()
        for filename in sorted_files:
            combined_hash.update(file_hashes[filename]["hash"].encode())
        
        return combined_hash.hexdigest()
    
    def _store_dataset_files(
        self,
        file_paths: List[str],
        dataset_id: str,
        version: str,
        backend: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store dataset files using the specified backend.
        
        Args:
            file_paths: List of paths to dataset files
            dataset_id: Dataset ID
            version: Version string
            backend: Storage backend to use
            options: Storage options
            
        Returns:
            Dictionary with storage result
        """
        # If storage manager is not configured, use local storage
        if self.storage_manager is None:
            # Store locally in the version directory
            version_dir = self._get_version_dir(dataset_id, version)
            locations = {}
            identifiers = {}
            
            try:
                for file_path in file_paths:
                    filename = os.path.basename(file_path)
                    dest_path = os.path.join(version_dir, filename)
                    
                    # Copy file to version directory
                    shutil.copy2(file_path, dest_path)
                    
                    # Record location and identifier
                    locations[filename] = dest_path
                    identifiers[filename] = f"local:{dest_path}"
                
                return {
                    "success": True,
                    "locations": locations,
                    "identifiers": identifiers
                }
            except Exception as e:
                logger.error(f"Error storing dataset files locally: {e}")
                return {
                    "success": False,
                    "error": f"Error storing dataset files: {e}"
                }
        else:
            # Use the storage manager to store the files
            try:
                locations = {}
                identifiers = {}
                
                for file_path in file_paths:
                    filename = os.path.basename(file_path)
                    
                    with open(file_path, 'rb') as f:
                        # Create content info
                        content_info = {
                            "filename": filename,
                            "content_type": self._guess_content_type(filename),
                            "content_category": "dataset",
                            "metadata": {
                                "dataset_id": dataset_id,
                                "version": version
                            }
                        }
                        
                        # Store with specified backend
                        result = self.storage_manager.store(
                            f, 
                            backend=backend, 
                            content_info=content_info, 
                            **options
                        )
                        
                        if not result.get("success", False):
                            return {
                                "success": False,
                                "error": f"Failed to store file {filename}: {result.get('error', 'Unknown error')}"
                            }
                        
                        # Record location and identifier
                        locations[filename] = result.get("location", "")
                        identifiers[filename] = result.get("identifier", "")
                
                return {
                    "success": True,
                    "locations": locations,
                    "identifiers": identifiers
                }
            except Exception as e:
                logger.error(f"Error storing dataset files with storage manager: {e}")
                return {
                    "success": False,
                    "error": f"Error storing dataset files: {e}"
                }
    
    def _guess_content_type(self, filename: str) -> str:
        """
        Guess the content type based on file extension.
        
        Args:
            filename: Name of the file
            
        Returns:
            Content type string
        """
        import mimetypes
        
        # Ensure mimetypes are initialized
        mimetypes.init()
        
        # Guess type based on extension
        content_type, _ = mimetypes.guess_type(filename)
        
        # Default to application/octet-stream if unknown
        if content_type is None:
            content_type = "application/octet-stream"
        
        return content_type
    
    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get dataset metadata.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Dictionary with dataset metadata
        """
        dataset_metadata = self._load_dataset_metadata(dataset_id)
        
        if not dataset_metadata:
            return {
                "success": False,
                "error": f"Dataset with ID {dataset_id} not found"
            }
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "metadata": dataset_metadata
        }
    
    def get_dataset_version(self, dataset_id: str, version: str) -> Dict[str, Any]:
        """
        Get metadata for a specific dataset version.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Dictionary with version metadata
        """
        dataset_metadata = self._load_dataset_metadata(dataset_id)
        
        if not dataset_metadata:
            return {
                "success": False,
                "error": f"Dataset with ID {dataset_id} not found"
            }
        
        if version not in dataset_metadata.get("versions", []):
            return {
                "success": False,
                "error": f"Version {version} not found for dataset {dataset_id}"
            }
        
        version_metadata = self._load_version_metadata(dataset_id, version)
        
        if not version_metadata:
            return {
                "success": False,
                "error": f"Metadata for version {version} of dataset {dataset_id} not found"
            }
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "version": version,
            "metadata": version_metadata
        }
    
    def list_datasets(
        self,
        dataset_type: Optional[Union[DatasetType, str]] = None,
        dataset_format: Optional[Union[DatasetFormat, str]] = None,
        tags: Optional[List[str]] = None,
        owner: Optional[str] = None,
        status: Optional[Union[DatasetStatus, str]] = None,
        quality: Optional[Union[DataQualityStatus, str]] = None
    ) -> Dict[str, Any]:
        """
        List datasets with optional filtering.
        
        Args:
            dataset_type: Filter by dataset type
            dataset_format: Filter by dataset format
            tags: Filter by tags (datasets with any of the specified tags)
            owner: Filter by owner
            status: Filter by status
            quality: Filter by quality status
            
        Returns:
            Dictionary with list of matching datasets
        """
        # Convert enum values to strings
        if dataset_type is not None:
            dataset_type = dataset_type.value if isinstance(dataset_type, DatasetType) else dataset_type
        
        if dataset_format is not None:
            dataset_format = dataset_format.value if isinstance(dataset_format, DatasetFormat) else dataset_format
        
        if status is not None:
            status = status.value if isinstance(status, DatasetStatus) else status
        
        if quality is not None:
            quality = quality.value if isinstance(quality, DataQualityStatus) else quality
        
        # Filter datasets
        filtered_datasets = {}
        
        for dataset_id, dataset_info in self.dataset_index["datasets"].items():
            # Check type
            if dataset_type is not None and dataset_info.get("type") != dataset_type:
                continue
            
            # Check format
            if dataset_format is not None and dataset_info.get("format") != dataset_format:
                continue
            
            # Check tags (any match)
            if tags is not None:
                dataset_tags = dataset_info.get("tags", [])
                if not any(tag in dataset_tags for tag in tags):
                    continue
            
            # Check status
            if status is not None and dataset_info.get("status") != status:
                continue
            
            # Check quality
            if quality is not None and dataset_info.get("quality") != quality:
                continue
            
            # Check owner
            if owner is not None:
                # Need to load full metadata for owner
                dataset_metadata = self._load_dataset_metadata(dataset_id)
                if dataset_metadata.get("owner") != owner:
                    continue
            
            # Add to filtered results
            filtered_datasets[dataset_id] = dataset_info
        
        return {
            "success": True,
            "datasets": filtered_datasets
        }
    
    def set_storage_manager(self, storage_manager) -> None:
        """
        Set the storage manager for the dataset manager.
        
        Args:
            storage_manager: Storage manager instance
        """
        self.storage_manager = storage_manager
        logger.info("Set storage manager for dataset manager")
    
    def get_dataset_types(self) -> Dict[str, Any]:
        """
        Get list of available dataset types and their dataset counts.
        
        Returns:
            Dictionary with dataset types and counts
        """
        types = {}
        
        for dataset_type, datasets in self.dataset_index["types"].items():
            types[dataset_type] = len(datasets)
        
        return {
            "success": True,
            "types": types
        }
    
    def get_dataset_formats(self) -> Dict[str, Any]:
        """
        Get list of available dataset formats and their dataset counts.
        
        Returns:
            Dictionary with dataset formats and counts
        """
        formats = {}
        
        for dataset_format, datasets in self.dataset_index["formats"].items():
            formats[dataset_format] = len(datasets)
        
        return {
            "success": True,
            "formats": formats
        }
    
    def search_datasets(self, query: str) -> Dict[str, Any]:
        """
        Search for datasets by name, description, or tags.
        
        Args:
            query: Search query string
            
        Returns:
            Dictionary with search results
        """
        query = query.lower()
        results = {}
        
        for dataset_id, dataset_info in self.dataset_index["datasets"].items():
            # Search in name
            if query in dataset_info.get("name", "").lower():
                results[dataset_id] = dataset_info
                continue
            
            # Search in tags
            if any(query in tag.lower() for tag in dataset_info.get("tags", [])):
                results[dataset_id] = dataset_info
                continue
            
            # Need to load full metadata for description
            dataset_metadata = self._load_dataset_metadata(dataset_id)
            
            # Search in description
            if query in dataset_metadata.get("description", "").lower():
                results[dataset_id] = dataset_info
                continue
        
        return {
            "success": True,
            "query": query,
            "results": results
        }
    
    def get_download_urls(self, dataset_id: str, version: str) -> Dict[str, Any]:
        """
        Get download URLs for dataset files.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Dictionary with download URLs for all files
        """
        # Get version metadata
        version_result = self.get_dataset_version(dataset_id, version)
        
        if not version_result["success"]:
            return version_result
        
        version_metadata = version_result["metadata"]
        storage_info = version_metadata.get("storage", {})
        
        # Get file identifiers
        identifiers = storage_info.get("identifiers", {})
        backend = storage_info.get("backend")
        
        # If using a storage manager, get the download URLs
        if self.storage_manager is not None:
            try:
                urls = {}
                
                for filename, identifier in identifiers.items():
                    # Get download URL from storage manager
                    result = self.storage_manager.get_download_url(identifier, backend=backend)
                    
                    if result.get("success", False):
                        urls[filename] = result.get("url")
                    else:
                        urls[filename] = None
                
                return {
                    "success": True,
                    "dataset_id": dataset_id,
                    "version": version,
                    "download_urls": urls
                }
            except Exception as e:
                logger.error(f"Error getting download URLs: {e}")
                return {
                    "success": False,
                    "error": f"Error getting download URLs: {e}"
                }
        else:
            # Local storage
            locations = storage_info.get("locations", {})
            
            urls = {}
            for filename, location in locations.items():
                if os.path.exists(location):
                    urls[filename] = f"file://{os.path.abspath(location)}"
                else:
                    urls[filename] = None
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "version": version,
                "download_urls": urls
            }
    
    def analyze_dataset(self, dataset_id: str, version: str) -> Dict[str, Any]:
        """
        Analyze a dataset to compute statistics and quality metrics.
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Dictionary with analysis results
        """
        # Get version metadata
        version_result = self.get_dataset_version(dataset_id, version)
        
        if not version_result["success"]:
            return version_result
        
        version_metadata = version_result["metadata"]
        storage_info = version_metadata.get("storage", {})
        
        # Get file locations
        if self.storage_manager is not None:
            # Storage manager is used, we need to download files to temp location
            return {
                "success": False,
                "error": "Dataset analysis with storage manager not implemented yet"
            }
        else:
            # Local storage
            locations = storage_info.get("locations", {})
            
            # Check if we have files to analyze
            if not locations:
                return {
                    "success": False,
                    "error": "No dataset files to analyze"
                }
            
            # Simple file stats for now
            file_stats = {}
            for filename, location in locations.items():
                if os.path.exists(location):
                    size = os.path.getsize(location)
                    last_modified = os.path.getmtime(location)
                    
                    file_stats[filename] = {
                        "size": size,
                        "last_modified": last_modified
                    }
            
            # Basic quality metrics
            quality_metrics = {
                "file_count": len(locations),
                "total_size": sum(stat["size"] for stat in file_stats.values()),
                "completeness": 1.0 if all(os.path.exists(location) for location in locations.values()) else 0.0
            }
            
            # Determine quality status
            quality_status = DataQualityStatus.GOOD if quality_metrics["completeness"] == 1.0 else DataQualityStatus.POOR
            
            # Update version metadata with statistics and quality metrics
            version_metadata["statistics"] = {
                "file_stats": file_stats,
                "analyzed_at": time.time()
            }
            
            version_metadata["quality_metrics"] = quality_metrics
            version_metadata["quality_status"] = quality_status.value
            
            # Save updated version metadata
            self._save_version_metadata(dataset_id, version, version_metadata)
            
            # Update dataset index with quality status
            self.dataset_index["datasets"][dataset_id]["quality"] = quality_status.value
            self._save_dataset_index()
            
            return {
                "success": True,
                "dataset_id": dataset_id,
                "version": version,
                "statistics": version_metadata["statistics"],
                "quality_metrics": quality_metrics,
                "quality_status": quality_status.value
            }
    
    def compare_versions(self, dataset_id: str, versions: List[str]) -> Dict[str, Any]:
        """
        Compare statistics between different dataset versions.
        
        Args:
            dataset_id: Dataset ID
            versions: List of version strings to compare
            
        Returns:
            Dictionary with comparison results
        """
        # Get dataset metadata
        dataset_result = self.get_dataset(dataset_id)
        
        if not dataset_result["success"]:
            return dataset_result
        
        dataset_metadata = dataset_result["metadata"]
        
        # Check if versions exist
        for version in versions:
            if version not in dataset_metadata.get("versions", []):
                return {
                    "success": False,
                    "error": f"Version {version} not found for dataset {dataset_id}"
                }
        
        # Get version metadata and statistics
        version_data = {}
        stat_keys = set()
        quality_keys = set()
        
        for version in versions:
            version_result = self.get_dataset_version(dataset_id, version)
            
            if not version_result["success"]:
                return version_result
            
            version_metadata = version_result["metadata"]
            version_stats = version_metadata.get("statistics", {})
            version_quality = version_metadata.get("quality_metrics", {})
            
            version_data[version] = {
                "statistics": version_stats,
                "quality_metrics": version_quality,
                "file_count": version_metadata.get("file_count", 0),
                "total_size": version_metadata.get("total_size", 0),
                "created_at": version_metadata.get("created_at"),
                "quality_status": version_metadata.get("quality_status")
            }
            
            # Collect all statistics and quality metrics keys
            stat_keys.update(version_stats.keys())
            quality_keys.update(version_quality.keys())
        
        # Create comparison table
        comparison = {
            "statistics": {},
            "quality_metrics": {},
            "version_info": {}
        }
        
        # Compare statistics
        for stat in stat_keys:
            comparison["statistics"][stat] = {
                version: version_data[version]["statistics"].get(stat)
                for version in versions
            }
        
        # Compare quality metrics
        for metric in quality_keys:
            comparison["quality_metrics"][metric] = {
                version: version_data[version]["quality_metrics"].get(metric)
                for version in versions
            }
        
        # Version info
        for version in versions:
            comparison["version_info"][version] = {
                "created_at": version_data[version]["created_at"],
                "file_count": version_data[version]["file_count"],
                "total_size": version_data[version]["total_size"],
                "quality_status": version_data[version]["quality_status"]
            }
        
        return {
            "success": True,
            "dataset_id": dataset_id,
            "versions": versions,
            "comparison": comparison
        }


# Singleton instance
_instance = None

def get_instance(config=None):
    """Get or create a singleton instance of the dataset manager."""
    global _instance
    if _instance is None:
        _instance = DatasetManager(config)
    return _instance