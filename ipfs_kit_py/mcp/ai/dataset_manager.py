#!/usr/bin/env python3
"""
Dataset Manager for MCP Server

This module provides version-controlled dataset storage and management capabilities
for machine learning datasets within the IPFS Kit ecosystem.

Key features:
- Version-controlled dataset storage
- Dataset preprocessing pipelines
- Data quality metrics
- Dataset lineage tracking

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import os
import json
import logging
import shutil
import uuid
import hashlib
from typing import Dict, List, Optional, Union, Any, Tuple, Set, Iterator
from pathlib import Path
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import csv
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_dataset_manager")


class DatasetQualityMetrics:
    """Class to track and compute dataset quality metrics."""
    
    def __init__(self):
        """Initialize dataset quality metrics."""
        self.metrics: Dict[str, Any] = {
            "completeness": {},
            "uniqueness": {},
            "consistency": {},
            "accuracy": {},
            "timeliness": {},
            "statistical": {}
        }
    
    def update_completeness(self, field_name: str, missing_ratio: float) -> None:
        """
        Update completeness metrics for a field.
        
        Args:
            field_name: Name of the field
            missing_ratio: Ratio of missing values (0.0-1.0)
        """
        self.metrics["completeness"][field_name] = 1.0 - missing_ratio
    
    def update_uniqueness(self, field_name: str, unique_ratio: float) -> None:
        """
        Update uniqueness metrics for a field.
        
        Args:
            field_name: Name of the field
            unique_ratio: Ratio of unique values (0.0-1.0)
        """
        self.metrics["uniqueness"][field_name] = unique_ratio
    
    def update_consistency(self, field_name: str, consistency_score: float) -> None:
        """
        Update consistency metrics for a field.
        
        Args:
            field_name: Name of the field
            consistency_score: Consistency score (0.0-1.0)
        """
        self.metrics["consistency"][field_name] = consistency_score
    
    def update_accuracy(self, field_name: str, accuracy_score: float) -> None:
        """
        Update accuracy metrics for a field.
        
        Args:
            field_name: Name of the field
            accuracy_score: Accuracy score (0.0-1.0)
        """
        self.metrics["accuracy"][field_name] = accuracy_score
    
    def update_timeliness(self, dataset_age_days: float) -> None:
        """
        Update timeliness metrics for the dataset.
        
        Args:
            dataset_age_days: Age of the dataset in days
        """
        # Convert to a score where newer is better (exponential decay)
        if dataset_age_days <= 0:
            score = 1.0
        else:
            # Arbitrary decay factor - 0.9 score at 30 days
            score = min(1.0, max(0.0, pow(0.9, dataset_age_days / 30.0)))
            
        self.metrics["timeliness"]["dataset_age_days"] = dataset_age_days
        self.metrics["timeliness"]["score"] = score
    
    def update_statistical(self, metrics: Dict[str, Any]) -> None:
        """
        Update statistical metrics for the dataset.
        
        Args:
            metrics: Dictionary of statistical metrics
        """
        self.metrics["statistical"].update(metrics)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all quality metrics.
        
        Returns:
            Dictionary of all quality metrics
        """
        return self.metrics
    
    def get_overall_quality_score(self) -> float:
        """
        Calculate an overall quality score based on all metrics.
        
        Returns:
            Overall quality score (0.0-1.0)
        """
        scores = []
        
        # Completeness score (average across fields)
        if self.metrics["completeness"]:
            scores.append(sum(self.metrics["completeness"].values()) / len(self.metrics["completeness"]))
        
        # Uniqueness score (average across fields)
        if self.metrics["uniqueness"]:
            scores.append(sum(self.metrics["uniqueness"].values()) / len(self.metrics["uniqueness"]))
        
        # Consistency score (average across fields)
        if self.metrics["consistency"]:
            scores.append(sum(self.metrics["consistency"].values()) / len(self.metrics["consistency"]))
        
        # Accuracy score (average across fields)
        if self.metrics["accuracy"]:
            scores.append(sum(self.metrics["accuracy"].values()) / len(self.metrics["accuracy"]))
        
        # Timeliness score
        if "score" in self.metrics["timeliness"]:
            scores.append(self.metrics["timeliness"]["score"])
        
        # If no scores are available, return a neutral score
        if not scores:
            return 0.5
        
        # Average of all scores
        return sum(scores) / len(scores)


class DatasetVersion:
    """Represents a single version of a dataset with its metadata and metrics."""
    
    def __init__(
        self,
        version_id: str,
        dataset_id: str,
        created_at: Union[str, datetime],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        quality_metrics: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        path: Optional[str] = None,
        storage_backend: Optional[str] = None,
        storage_uri: Optional[str] = None,
        format: Optional[str] = None,
        size_bytes: Optional[int] = None,
        row_count: Optional[int] = None,
        column_count: Optional[int] = None,
        user_id: Optional[str] = None,
        status: str = "created",
        parent_version_id: Optional[str] = None,
        transformations: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Initialize a dataset version.
        
        Args:
            version_id: Unique identifier for this version
            dataset_id: ID of the parent dataset
            created_at: Creation timestamp
            description: Human-readable description
            metadata: Additional metadata
            schema: Dataset schema information
            quality_metrics: Data quality metrics
            tags: Tags for categorization and filtering
            path: Local filesystem path (if stored locally)
            storage_backend: Storage backend identifier (ipfs, filecoin, s3, etc.)
            storage_uri: URI for retrieving the dataset from storage
            format: Dataset format (csv, json, parquet, etc.)
            size_bytes: Size of the dataset in bytes
            row_count: Number of rows in the dataset
            column_count: Number of columns in the dataset
            user_id: ID of the user who created this version
            status: Current status (created, processing, ready, failed, etc.)
            parent_version_id: ID of the parent version (for derived datasets)
            transformations: List of transformations applied to create this version
        """
        self.version_id = version_id
        self.dataset_id = dataset_id
        
        # Convert string timestamps to datetime objects
        if isinstance(created_at, str):
            self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            self.created_at = created_at
            
        self.description = description
        self.metadata = metadata or {}
        self.schema = schema or {}
        self.quality_metrics = quality_metrics or {}
        self.tags = tags or []
        self.path = path
        self.storage_backend = storage_backend
        self.storage_uri = storage_uri
        self.format = format
        self.size_bytes = size_bytes
        self.row_count = row_count
        self.column_count = column_count
        self.user_id = user_id
        self.status = status
        self.updated_at = self.created_at
        self.parent_version_id = parent_version_id
        self.transformations = transformations or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dataset version to a dictionary."""
        return {
            "version_id": self.version_id,
            "dataset_id": self.dataset_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
            "schema": self.schema,
            "quality_metrics": self.quality_metrics,
            "tags": self.tags,
            "path": self.path,
            "storage_backend": self.storage_backend,
            "storage_uri": self.storage_uri,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "user_id": self.user_id,
            "status": self.status,
            "parent_version_id": self.parent_version_id,
            "transformations": self.transformations
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DatasetVersion':
        """Create a DatasetVersion from a dictionary."""
        return cls(
            version_id=data["version_id"],
            dataset_id=data["dataset_id"],
            created_at=data["created_at"],
            description=data.get("description"),
            metadata=data.get("metadata"),
            schema=data.get("schema"),
            quality_metrics=data.get("quality_metrics"),
            tags=data.get("tags"),
            path=data.get("path"),
            storage_backend=data.get("storage_backend"),
            storage_uri=data.get("storage_uri"),
            format=data.get("format"),
            size_bytes=data.get("size_bytes"),
            row_count=data.get("row_count"),
            column_count=data.get("column_count"),
            user_id=data.get("user_id"),
            status=data.get("status", "created"),
            parent_version_id=data.get("parent_version_id"),
            transformations=data.get("transformations")
        )
    
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Update metadata.
        
        Args:
            metadata: New or updated metadata
        """
        self.metadata.update(metadata)
        self.updated_at = datetime.now()
    
    def update_quality_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Update quality metrics.
        
        Args:
            metrics: New or updated quality metrics
        """
        self.quality_metrics.update(metrics)
        self.updated_at = datetime.now()
    
    def update_schema(self, schema: Dict[str, Any]) -> None:
        """
        Update schema information.
        
        Args:
            schema: New or updated schema information
        """
        self.schema.update(schema)
        self.updated_at = datetime.now()
    
    def add_tags(self, tags: List[str]) -> None:
        """
        Add tags to the dataset version.
        
        Args:
            tags: Tags to add
        """
        for tag in tags:
            if tag not in self.tags:
                self.tags.append(tag)
        self.updated_at = datetime.now()
    
    def remove_tags(self, tags: List[str]) -> None:
        """
        Remove tags from the dataset version.
        
        Args:
            tags: Tags to remove
        """
        self.tags = [t for t in self.tags if t not in tags]
        self.updated_at = datetime.now()
    
    def update_status(self, status: str) -> None:
        """
        Update the status of the dataset version.
        
        Args:
            status: New status
        """
        self.status = status
        self.updated_at = datetime.now()
    
    def add_transformation(self, transformation: Dict[str, Any]) -> None:
        """
        Add a transformation to the dataset version lineage.
        
        Args:
            transformation: Transformation information
        """
        if "timestamp" not in transformation:
            transformation["timestamp"] = datetime.now().isoformat()
        
        self.transformations.append(transformation)
        self.updated_at = datetime.now()


class Dataset:
    """
    Represents a dataset with its versions and metadata.
    
    This is the main class for interacting with dataset data, including
    creating new versions, tracking quality metrics, and managing metadata.
    """
    
    def __init__(
        self,
        dataset_id: str,
        name: str,
        created_at: Union[str, datetime],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        versions: Optional[Dict[str, DatasetVersion]] = None,
        license: Optional[str] = None,
        source: Optional[str] = None
    ):
        """
        Initialize a dataset.
        
        Args:
            dataset_id: Unique identifier for the dataset
            name: Human-readable name
            created_at: Creation timestamp
            description: Human-readable description
            tags: Tags for categorization and filtering
            domain: Domain or category of the dataset
            user_id: ID of the user who created the dataset
            metadata: Additional metadata
            versions: Dictionary of version_id -> DatasetVersion
            license: Dataset license information
            source: Original source of the dataset
        """
        self.dataset_id = dataset_id
        self.name = name
        
        # Convert string timestamps to datetime objects
        if isinstance(created_at, str):
            self.created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            self.created_at = created_at
            
        self.description = description
        self.tags = tags or []
        self.domain = domain
        self.user_id = user_id
        self.metadata = metadata or {}
        self.versions = versions or {}
        self.license = license
        self.source = source
        self.updated_at = self.created_at
        self.version_count = len(self.versions)
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    def to_dict(self, include_versions: bool = False) -> Dict[str, Any]:
        """
        Convert dataset to a dictionary.
        
        Args:
            include_versions: Whether to include version data
            
        Returns:
            Dataset as a dictionary
        """
        with self._lock:
            result = {
                "dataset_id": self.dataset_id,
                "name": self.name,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
                "description": self.description,
                "tags": self.tags,
                "domain": self.domain,
                "user_id": self.user_id,
                "metadata": self.metadata,
                "version_count": self.version_count,
                "license": self.license,
                "source": self.source
            }
            
            if include_versions:
                result["versions"] = {
                    v_id: version.to_dict() 
                    for v_id, version in self.versions.items()
                }
            
            return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dataset':
        """Create a Dataset from a dictionary."""
        versions = {}
        if "versions" in data:
            versions = {
                v_id: DatasetVersion.from_dict(v_data)
                for v_id, v_data in data["versions"].items()
            }
        
        return cls(
            dataset_id=data["dataset_id"],
            name=data["name"],
            created_at=data["created_at"],
            description=data.get("description"),
            tags=data.get("tags"),
            domain=data.get("domain"),
            user_id=data.get("user_id"),
            metadata=data.get("metadata"),
            versions=versions,
            license=data.get("license"),
            source=data.get("source")
        )
    
    def add_version(self, version: DatasetVersion) -> None:
        """
        Add a version to the dataset.
        
        Args:
            version: DatasetVersion to add
        """
        with self._lock:
            self.versions[version.version_id] = version
            self.version_count = len(self.versions)
            self.updated_at = datetime.now()
    
    def get_version(self, version_id: str) -> Optional[DatasetVersion]:
        """
        Get a specific version of the dataset.
        
        Args:
            version_id: Version ID to retrieve
            
        Returns:
            DatasetVersion if found, None otherwise
        """
        with self._lock:
            return self.versions.get(version_id)
    
    def get_latest_version(self) -> Optional[DatasetVersion]:
        """
        Get the latest version of the dataset.
        
        Returns:
            Most recent DatasetVersion if any exist, None otherwise
        """
        with self._lock:
            if not self.versions:
                return None
            
            # Find version with latest created_at timestamp
            return max(self.versions.values(), key=lambda v: v.created_at)
    
    def get_versions(self, limit: Optional[int] = None, offset: int = 0) -> List[DatasetVersion]:
        """
        Get versions of the dataset.
        
        Args:
            limit: Maximum number of versions to return
            offset: Number of versions to skip
            
        Returns:
            List of DatasetVersion objects sorted by created_at (newest first)
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
        Remove a version from the dataset.
        
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
        Add tags to the dataset.
        
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
        Remove tags from the dataset.
        
        Args:
            tags: Tags to remove
        """
        with self._lock:
            self.tags = [t for t in self.tags if t not in tags]
            self.updated_at = datetime.now()
    
    def get_lineage_graph(self) -> Dict[str, Any]:
        """
        Get a lineage graph for the dataset versions.
        
        Returns:
            Lineage graph data structure
        """
        with self._lock:
            # Initialize lineage graph
            nodes = []
            edges = []
            
            # Add all versions as nodes
            for version_id, version in self.versions.items():
                nodes.append({
                    "id": version_id,
                    "label": version_id,
                    "created_at": version.created_at.isoformat(),
                    "status": version.status
                })
                
                # Add edge for parent-child relationship
                if version.parent_version_id:
                    edges.append({
                        "source": version.parent_version_id,
                        "target": version_id,
                        "type": "derivation"
                    })
            
            return {
                "nodes": nodes,
                "edges": edges
            }


class DatasetManager:
    """
    Manager for versioned datasets.
    
    This class provides functionality for storing, retrieving, and managing
    datasets and their versions, metadata, and quality metrics.
    """
    
    def __init__(self, storage_path: Union[str, Path], config: Optional[Dict[str, Any]] = None):
        """
        Initialize the dataset manager.
        
        Args:
            storage_path: Path to store datasets and metadata
            config: Configuration options
        """
        self.storage_path = Path(storage_path)
        self.config = config or {}
        
        # Ensure storage directories exist
        self.datasets_path = self.storage_path / "datasets"
        self.data_path = self.storage_path / "data"
        self.index_path = self.storage_path / "index"
        
        self.datasets_path.mkdir(parents=True, exist_ok=True)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # In-memory cache of datasets
        self._datasets: Dict[str, Dataset] = {}
        
        # Initialize executors
        self._executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 4),
            thread_name_prefix="dataset_manager_"
        )
        
        # Load existing datasets
        self._load_datasets()
        
        logger.info(f"Dataset Manager initialized at {self.storage_path} with {len(self._datasets)} datasets")
    
    def _load_datasets(self) -> None:
        """Load existing datasets from storage."""
        try:
            # Load dataset metadata
            dataset_files = list(self.index_path.glob("*.json"))
            for dataset_file in dataset_files:
                try:
                    with open(dataset_file, 'r') as f:
                        dataset_data = json.load(f)
                    
                    dataset = Dataset.from_dict(dataset_data)
                    self._datasets[dataset.dataset_id] = dataset
                    
                except Exception as e:
                    logger.error(f"Error loading dataset from {dataset_file}: {e}")
            
            logger.info(f"Loaded {len(self._datasets)} datasets from storage")
            
        except Exception as e:
            logger.error(f"Error during dataset loading: {e}")
    
    def _save_dataset_metadata(self, dataset: Dataset) -> bool:
        """
        Save dataset metadata to storage.
        
        Args:
            dataset: Dataset to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            dataset_file = self.index_path / f"{dataset.dataset_id}.json"
            dataset_data = dataset.to_dict(include_versions=True)
            
            # Write to a temporary file first, then rename to ensure atomic operation
            temp_file = dataset_file.with_suffix(".tmp")
            with open(temp_file, 'w') as f:
                json.dump(dataset_data, f, indent=2)
            
            temp_file.rename(dataset_file)
            return True
            
        except Exception as e:
            logger.error(f"Error saving dataset metadata for {dataset.dataset_id}: {e}")
            return False
    
    def _analyze_file_for_schema(self, file_path: Union[str, Path]) -> Tuple[Dict[str, Any], Dict[str, Any], int, int]:
        """
        Analyze a file to determine its schema and quality metrics.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (schema, quality_metrics, row_count, column_count)
        """
        file_path = Path(file_path)
        file_ext = file_path.suffix.lower()
        
        schema = {}
        quality_metrics = {}
        row_count = 0
        column_count = 0
        
        try:
            # Handle different file types
            if file_ext == '.csv':
                # Read the file to determine schema and basics stats
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    # Sample first few rows to determine schema
                    sample_rows = []
                    csv_reader = csv.reader(f)
                    
                    # Get header
                    header = next(csv_reader)
                    column_count = len(header)
                    
                    # Sample rows
                    for _ in range(min(1000, self.config.get("schema_sample_size", 1000))):
                        try:
                            row = next(csv_reader)
                            sample_rows.append(row)
                            row_count += 1
                        except StopIteration:
                            break
                    
                    # Continue counting rows
                    for _ in csv_reader:
                        row_count += 1
                
                # Infer schema from the sample
                for i, col_name in enumerate(header):
                    col_values = [row[i] if i < len(row) else None for row in sample_rows]
                    non_empty_values = [v for v in col_values if v and v.strip()]
                    
                    # Determine data type
                    data_type = "string"  # Default type
                    if non_empty_values:
                        # Try to infer numeric types
                        try:
                            # Try integer
                            all(int(v) for v in non_empty_values)
                            data_type = "integer"
                        except ValueError:
                            try:
                                # Try float
                                all(float(v) for v in non_empty_values)
                                data_type = "float"
                            except ValueError:
                                # Check if boolean
                                if all(v.lower() in ('true', 'false', '0', '1', 'yes', 'no') for v in non_empty_values):
                                    data_type = "boolean"
                                else:
                                    # Check if date
                                    try:
                                        from dateutil.parser import parse
                                        all(parse(v) for v in non_empty_values)
                                        data_type = "datetime"
                                    except (ImportError, ValueError):
                                        data_type = "string"
                    
                    # Add to schema
                    schema[col_name] = {
                        "type": data_type,
                        "nullable": any(not v for v in col_values)
                    }
                    
                    # Add quality metrics for this column
                    if col_values:
                        missing_ratio = len([v for v in col_values if not v]) / len(col_values)
                        quality_metrics.setdefault("completeness", {})[col_name] = 1.0 - missing_ratio
                        
                        if non_empty_values:
                            unique_ratio = len(set(non_empty_values)) / len(non_empty_values)
                            quality_metrics.setdefault("uniqueness", {})[col_name] = unique_ratio
            
            elif file_ext == '.json':
                # For JSON files, we'll just count records and determine top-level fields
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Check first character to determine if it's a JSON array or object
                    first_char = f.read(1)
                    f.seek(0)
                    
                    if first_char == '[':
                        # JSON array
                        data = json.load(f)
                        row_count = len(data)
                        
                        # Sample some records to determine schema
                        sample_size = min(100, row_count)
                        sample = data[:sample_size]
                        
                        if sample:
                            # Get all keys from the first record
                            first_record = sample[0]
                            if isinstance(first_record, dict):
                                column_count = len(first_record)
                                
                                # Build schema from all sampled records
                                for record in sample:
                                    for key, value in record.items():
                                        if key not in schema:
                                            schema[key] = {"type": "unknown", "nullable": False}
                                        
                                        # Update type info
                                        current_type = schema[key]["type"]
                                        if value is None:
                                            schema[key]["nullable"] = True
                                        elif isinstance(value, int) and current_type in ("unknown", "integer"):
                                            schema[key]["type"] = "integer"
                                        elif isinstance(value, float) and current_type in ("unknown", "integer", "float"):
                                            schema[key]["type"] = "float"
                                        elif isinstance(value, bool) and current_type in ("unknown", "boolean"):
                                            schema[key]["type"] = "boolean"
                                        elif isinstance(value, str) and current_type in ("unknown", "string"):
                                            schema[key]["type"] = "string"
                                        elif isinstance(value, (list, dict)):
                                            schema[key]["type"] = "object"
                                        else:
                                            schema[key]["type"] = "mixed"
                    else:
                        # Single JSON object
                        data = json.load(f)
                        row_count = 1
                        column_count = len(data) if isinstance(data, dict) else 0
                        
                        # Build schema
                        if isinstance(data, dict):
                            for key, value in data.items():
                                schema[key] = {
                                    "type": type(value).__name__ if value is not None else "null",
                                    "nullable": value is None
                                }
            
            return schema, quality_metrics, row_count, column_count
        except Exception as e:
            logger.error(f"Error analyzing file: {e}")
            return {}, {}, 0, 0
    
    def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        domain: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        license: Optional[str] = None,
        source: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> Dataset:
        """
        Create a new dataset.
        
        Args:
            name: Human-readable name
            description: Human-readable description
            tags: Tags for categorization and filtering
            domain: Domain or category of the dataset
            user_id: ID of the user creating the dataset
            metadata: Additional metadata
            license: Dataset license information
            source: Original source of the dataset
            dataset_id: Optional custom dataset ID (generated if not provided)
            
        Returns:
            The created Dataset object
        """
        with self._lock:
            # Generate dataset_id if not provided
            if dataset_id is None:
                dataset_id = f"dataset_{uuid.uuid4().hex[:12]}"
            
            # Ensure dataset_id is unique
            if dataset_id in self._datasets:
                raise ValueError(f"Dataset with ID '{dataset_id}' already exists")
            
            # Create dataset
            dataset = Dataset(
                dataset_id=dataset_id,
                name=name,
                created_at=datetime.now(),
                description=description,
                tags=tags,
                domain=domain,
                user_id=user_id,
                metadata=metadata,
                license=license,
                source=source
            )
            
            # Add to registry
            self._datasets[dataset_id] = dataset
            
            # Save metadata
            self._save_dataset_metadata(dataset)
            
            logger.info(f"Created dataset '{name}' with ID {dataset_id}")
            
            return dataset
    
    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        Get a dataset by ID.
        
        Args:
            dataset_id: ID of the dataset to retrieve
            
        Returns:
            Dataset if found, None otherwise
        """
        return self._datasets.get(dataset_id)
    
    def list_datasets(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        sort_by: str = "updated_at",
        ascending: bool = False,
        filter_tags: Optional[List[str]] = None,
        filter_domain: Optional[str] = None,
        search_term: Optional[str] = None
    ) -> List[Dataset]:
        """
        List datasets with filtering and sorting.
        
        Args:
            limit: Maximum number of datasets to return
            offset: Number of datasets to skip
            sort_by: Attribute to sort by
            ascending: Whether to sort in ascending order
            filter_tags: Filter by tags (datasets must have all specified tags)
            filter_domain: Filter by domain
            search_term: Search in name and description
            
        Returns:
            List of matching datasets
        """
        with self._lock:
            # Start with all datasets
            datasets = list(self._datasets.values())
            
            # Apply filters
            if filter_tags:
                datasets = [
                    d for d in datasets 
                    if all(tag in d.tags for tag in filter_tags)
                ]
            
            if filter_domain:
                datasets = [
                    d for d in datasets 
                    if d.domain == filter_domain
                ]
            
            if search_term:
                search_term = search_term.lower()
                datasets = [
                    d for d in datasets 
                    if (
                        search_term in d.name.lower() or 
                        (d.description and search_term in d.description.lower())
                    )
                ]
            
            # Sort datasets
            if sort_by == "name":
                datasets.sort(key=lambda d: d.name, reverse=not ascending)
            elif sort_by == "created_at":
                datasets.sort(key=lambda d: d.created_at, reverse=not ascending)
            elif sort_by == "version_count":
                datasets.sort(key=lambda d: d.version_count, reverse=not ascending)
            else:  # Default to updated_at
                datasets.sort(key=lambda d: d.updated_at, reverse=not ascending)
            
            # Apply pagination
            if offset:
                datasets = datasets[offset:]
            
            if limit is not None:
                datasets = datasets[:limit]
            
            return datasets
    
    def get_dataset_count(self) -> int:
        """
        Get the total number of datasets.
        
        Returns:
            Number of datasets
        """
        return len(self._datasets)
    
    def delete_dataset(self, dataset_id: str, delete_files: bool = True) -> bool:
        """
        Delete a dataset and optionally its files.
        
        Args:
            dataset_id: ID of the dataset to delete
            delete_files: Whether to delete dataset files
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            dataset = self._datasets.get(dataset_id)
            if not dataset:
                return False
            
            # Delete dataset files if requested
            if delete_files:
                dataset_dir = self.datasets_path / dataset_id
                if dataset_dir.exists():
                    try:
                        shutil.rmtree(dataset_dir)
                    except Exception as e:
                        logger.error(f"Error deleting dataset files for {dataset_id}: {e}")
            
            # Delete dataset metadata file
            dataset_file = self.index_path / f"{dataset_id}.json"
            if dataset_file.exists():
                try:
                    dataset_file.unlink()
                except Exception as e:
                    logger.error(f"Error deleting dataset metadata file for {dataset_id}: {e}")
            
            # Remove from registry
            del self._datasets[dataset_id]
            
            logger.info(f"Deleted dataset {dataset_id}")
            
            return True
    
    def create_dataset_version(
        self, 
        dataset_id: str,
        file_path: Union[str, Path],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        format: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_version_id: Optional[str] = None,
        original_filename: Optional[str] = None,
        version_id: Optional[str] = None
    ) -> Optional[DatasetVersion]:
        """
        Create a new version of a dataset.
        
        Args:
            dataset_id: ID of the dataset
            file_path: Path to dataset file
            description: Human-readable description
            tags: Tags for categorization and filtering
            format: Dataset format (csv, json, parquet, etc.)
            user_id: ID of the user creating the version
            metadata: Additional metadata
            parent_version_id: ID of the parent version (for derived datasets)
            original_filename: Original filename (for display purposes)
            version_id: Optional custom version ID (generated if not provided)
            
        Returns:
            The created DatasetVersion, or None if dataset not found
        """
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            logger.error(f"Cannot create version: Dataset {dataset_id} not found")
            return None
        
        # Generate version_id if not provided
        if version_id is None:
            version_id = f"v_{uuid.uuid4().hex[:8]}"
        
        # Ensure version directory exists
        dataset_dir = self.datasets_path / dataset_id
        version_dir = dataset_dir / version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine format from file extension if not provided
        if not format and isinstance(file_path, (str, Path)):
            format = os.path.splitext(str(file_path))[1].lstrip('.')
        
        # Copy file to version directory
        file_path = Path(file_path)
        if not file_path.exists():
            raise ValueError(f"File {file_path} does not exist")
        
        target_filename = original_filename or file_path.name
        target_path = version_dir / target_filename
        try:
            shutil.copy2(file_path, target_path)
        except Exception as e:
            logger.error(f"Error copying dataset file: {e}")
            shutil.rmtree(version_dir)
            raise
        
        # Analyze file to determine schema and quality metrics
        try:
            schema, quality_metrics, row_count, column_count = self._analyze_file_for_schema(target_path)
        except Exception as e:
            logger.error(f"Error analyzing dataset file: {e}")
            schema, quality_metrics, row_count, column_count = {}, {}, 0, 0
        
        # Create version
        version = DatasetVersion(
            version_id=version_id,
            dataset_id=dataset_id,
            created_at=datetime.now(),
            description=description,
            tags=tags,
            path=str(target_path),
            format=format,
            size_bytes=target_path.stat().st_size if target_path.exists() else None,
            row_count=row_count,
            column_count=column_count,
            user_id=user_id or dataset.user_id,
            schema=schema,
            quality_metrics=quality_metrics,
            metadata=metadata,
            parent_version_id=parent_version_id,
            status="ready"
        )
        
        # Add to dataset
        dataset.add_version(version)
        
        # Save dataset metadata
        self._save_dataset_metadata(dataset)
        
        logger.info(f"Created version {version_id} for dataset {dataset_id}")
        
        return version
    
    def get_dataset_version(self, dataset_id: str, version_id: str) -> Optional[DatasetVersion]:
        """
        Get a specific version of a dataset.
        
        Args:
            dataset_id: ID of the dataset
            version_id: ID of the version
            
        Returns:
            DatasetVersion if found, None otherwise
        """
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            return None
        
        return dataset.get_version(version_id)

# Singleton instance
_instance = None

def get_instance(
    storage_path: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None
) -> DatasetManager:
    """
    Get or create the singleton instance of the DatasetManager.
    
    Args:
        storage_path: Path to store datasets and metadata
        config: Configuration options
        
    Returns:
        DatasetManager instance
    """
    global _instance
    if _instance is None:
        # Set default storage path if none provided
        default_path = Path.home() / ".ipfs_kit" / "dataset_manager"
        actual_storage_path = default_path if storage_path is None else storage_path
        _instance = DatasetManager(actual_storage_path, config)
    return _instance
