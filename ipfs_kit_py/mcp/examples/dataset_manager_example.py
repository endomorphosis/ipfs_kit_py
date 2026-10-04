#!/usr/bin/env python3
"""
Dataset Management Example for MCP Server

This example demonstrates how to use the Dataset Management module to create, 
version, and preprocess datasets for machine learning workflows. It shows:

1. Creating and managing datasets
2. Adding files with different formats
3. Versioning and tracking lineage
4. Dataset quality metrics
5. Preprocessing pipelines
6. Integration with different storage backends

Usage:
  python dataset_manager_example.py [--ipfs] [--s3]
"""

import os
import sys
import tempfile
import argparse
import logging
import json
import shutil
import csv
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dataset-manager-example")

# Try to import optional dependencies
try:
    import numpy as np
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("Pandas not available. Some examples will be limited.")

# Import dataset manager components
try:
    from ipfs_kit_py.mcp.ai.dataset_manager import (
        Dataset,
        DatasetVersion,
        DatasetFile,
        DataQualityMetrics,
        PreprocessingStep,
        DatasetFormat,
        DatasetSplit,
        DatasetStatus,
        PreprocessingStage,
        FileSystemDatasetStorage,
        IPFSDatasetStorage,
        S3DatasetStorage,
        BaseMetadataStore,  # Abstract base class
    )
except ImportError:
    logger.error("Failed to import dataset manager modules. Make sure ipfs_kit_py is installed")
    sys.exit(1)

# ------------------------------------------------------------
# Helper Functions for Creating Sample Datasets
# ------------------------------------------------------------

def create_sample_csv_file(base_dir: str, rows: int = 100) -> str:
    """Create a sample CSV file for the example."""
    file_path = os.path.join(base_dir, "sample_data.csv")
    
    # Generate some random data
    data = []
    header = ["id", "name", "value", "timestamp", "category"]
    
    categories = ["A", "B", "C", "D"]
    
    for i in range(rows):
        row = [
            i,  # id
            f"Item {i}",  # name
            np.random.uniform(0, 100),  # value
            datetime.now().isoformat(),  # timestamp
            categories[np.random.randint(0, len(categories))]  # category
        ]
        data.append(row)
    
    # Write to file
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)
    
    logger.info(f"Created sample CSV file with {rows} rows at {file_path}")
    return file_path

def create_sample_json_file(base_dir: str, items: int = 50) -> str:
    """Create a sample JSON file for the example."""
    file_path = os.path.join(base_dir, "sample_data.json")
    
    # Generate some random data
    data = []
    
    for i in range(items):
        item = {
            "id": i,
            "name": f"Item {i}",
            "attributes": {
                "color": ["red", "green", "blue", "yellow"][np.random.randint(0, 4)],
                "size": ["small", "medium", "large"][np.random.randint(0, 3)],
                "rating": np.random.uniform(1, 5)
            },
            "tags": ["sample", "test", "example"][:np.random.randint(1, 4)],
            "created": datetime.now().isoformat()
        }
        data.append(item)
    
    # Write to file
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Created sample JSON file with {items} items at {file_path}")
    return file_path

def create_sample_text_files(base_dir: str, num_files: int = 5) -> List[str]:
    """Create sample text files for the example."""
    file_paths = []
    
    # Sample texts
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Natural language processing is a field of artificial intelligence.",
        "Machine learning models require high-quality training data.",
        "Dataset management is critical for reproducible AI research.",
        "IPFS provides content-addressed storage for decentralized systems.",
        "MCP Server integrates multiple storage backends with a unified API.",
        "Preprocessing data is often the most time-consuming part of ML workflows.",
        "Data quality metrics help identify issues before training models.",
        "Version control for datasets ensures reproducibility of experiments."
    ]
    
    # Create files
    os.makedirs(os.path.join(base_dir, "texts"), exist_ok=True)
    for i in range(num_files):
        file_path = os.path.join(base_dir, "texts", f"sample_text_{i}.txt")
        
        # Write a longer text by combining random samples
        indices = np.random.choice(len(texts), size=np.random.randint(3, 8), replace=True)
        content = "\n\n".join([texts[j] for j in indices])
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        file_paths.append(file_path)
    
    logger.info(f"Created {num_files} sample text files in {os.path.join(base_dir, 'texts')}")
    return file_paths

def create_sample_numpy_arrays(base_dir: str, num_files: int = 3) -> List[str]:
    """Create sample NumPy array files for the example."""
    if not HAS_PANDAS:
        logger.warning("NumPy not available. Skipping NumPy array creation.")
        return []
        
    file_paths = []
    
    # Create files
    os.makedirs(os.path.join(base_dir, "arrays"), exist_ok=True)
    for i in range(num_files):
        file_path = os.path.join(base_dir, "arrays", f"sample_array_{i}.npy")
        
        # Create a random array
        shape = tuple(np.random.randint(10, 100) for _ in range(2))  # 2D array
        array = np.random.random(shape)
        
        # Save the array
        np.save(file_path, array)
        
        file_paths.append(file_path)
    
    logger.info(f"Created {num_files} sample NumPy arrays in {os.path.join(base_dir, 'arrays')}")
    return file_paths

def create_dataset_archive(base_dir: str) -> str:
    """Create a ZIP archive containing a complete sample dataset."""
    # Create a temporary directory for the dataset files
    dataset_dir = os.path.join(base_dir, "complete_dataset")
    os.makedirs(dataset_dir, exist_ok=True)
    
    # Create subdirectories for train/val/test splits
    for split in ["train", "validation", "test"]:
        os.makedirs(os.path.join(dataset_dir, split), exist_ok=True)
    
    # Create CSV files for each split
    train_csv = create_sample_csv_file(os.path.join(dataset_dir, "train"), rows=500)
    val_csv = create_sample_csv_file(os.path.join(dataset_dir, "validation"), rows=100)
    test_csv = create_sample_csv_file(os.path.join(dataset_dir, "test"), rows=100)
    
    # Create a metadata.json file
    metadata = {
        "name": "Example Dataset",
        "description": "A sample dataset for demonstration purposes",
        "version": "1.0.0",
        "created": datetime.utcnow().isoformat(),
        "schema": {
            "id": "integer",
            "name": "string",
            "value": "float",
            "timestamp": "datetime",
            "category": "string"
        },
        "splits": {
            "train": {"file": "train/sample_data.csv", "rows": 500},
            "validation": {"file": "validation/sample_data.csv", "rows": 100},
            "test": {"file": "test/sample_data.csv", "rows": 100}
        }
    }
    
    with open(os.path.join(dataset_dir, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Create a ZIP archive
    zip_path = os.path.join(base_dir, "example_dataset.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, _, files in os.walk(dataset_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), base_dir)
                )
    
    logger.info(f"Created dataset archive at {zip_path}")
    return zip_path

# ------------------------------------------------------------
# Simple In-Memory Metadata Store Implementation
# ------------------------------------------------------------

class InMemoryMetadataStore(BaseMetadataStore):
    """Simple in-memory implementation of metadata storage for examples."""
    
    def __init__(self):
        """Initialize the in-memory store."""
        super().__init__()
        self.datasets: Dict[str, Dataset] = {}
        self.versions: Dict[str, Dict[str, DatasetVersion]] = {}
        self._lock = threading.RLock()
    
    def save_dataset(self, dataset: Dataset) -> None:
        """Save a dataset."""
        with self._lock:
            self.datasets[dataset.id] = dataset
    
    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        with self._lock:
            return self.datasets.get(dataset_id)
    
    def list_datasets(self, filters: Optional[Dict[str, Any]] = None, 
                    sort_by: Optional[str] = None, 
                    limit: Optional[int] = None) -> List[Dataset]:
        """List datasets with optional filtering and sorting."""
        with self._lock:
            datasets = list(self.datasets.values())
            
            # Apply filters
            if filters:
                filtered_datasets = []
                for dataset in datasets:
                    include = True
                    for key, value in filters.items():
                        if not hasattr(dataset, key) or getattr(dataset, key) != value:
                            include = False
                            break
                    if include:
                        filtered_datasets.append(dataset)
                datasets = filtered_datasets
            
            # Sort if requested
            if sort_by and hasattr(Dataset, sort_by):
                datasets.sort(key=lambda d: getattr(d, sort_by))
            
            # Apply limit
            if limit is not None and limit > 0:
                datasets = datasets[:limit]
            
            return datasets
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        with self._lock:
            if dataset_id in self.datasets:
                del self.datasets[dataset_id]
                
                # Also delete any versions
                if dataset_id in self.versions:
                    del self.versions[dataset_id]
                
                return True
            return False
    
    def save_dataset_version(self, version: DatasetVersion) -> None:
        """Save a dataset version."""
        with self._lock:
            if version.dataset_id not in self.versions:
                self.versions[version.dataset_id] = {}
            
            self.versions[version.dataset_id][version.id] = version
            
            # Update the latest version in the dataset if needed
            if version.is_latest and version.dataset_id in self.datasets:
                dataset = self.datasets[version.dataset_id]
                dataset.latest_version = version.id
                dataset.updated_at = datetime.utcnow().isoformat()
                self.save_dataset(dataset)
    
    def get_dataset_version(self, dataset_id: str, version_id: str) -> Optional[DatasetVersion]:
        """Get a dataset version."""
        with self._lock:
            if dataset_id in self.versions and version_id in self.versions[dataset_id]:
                return self.versions[dataset_id][version_id]
            return None
    
    def list_dataset_versions(self, dataset_id: str, 
                            filters: Optional[Dict[str, Any]] = None,
                            sort_by: Optional[str] = None, 
                            limit: Optional[int] = None) -> List[DatasetVersion]:
        """List versions of a dataset."""
        with self._lock:
            if dataset_id not in self.versions:
                return []
            
            versions = list(self.versions[dataset_id].values())
            
            # Apply filters
            if filters:
                filtered_versions = []
                for version in versions:
                    include = True
                    for key, value in filters.items():
                        if not hasattr(version, key) or getattr(version, key) != value:
                            include = False
                            break
                    if include:
                        filtered_versions.append(version)
                versions = filtered_versions
            
            # Sort if requested
            if sort_by and hasattr(DatasetVersion, sort_by):
                versions.sort(key=lambda v: getattr(v, sort_by))
            
            # Apply limit
            if limit is not None and limit > 0:
                versions = versions[:limit]
            
            return versions
    
    def delete_dataset_version(self, dataset_id: str, version_id: str) -> bool:
        """Delete a dataset version."""
        with self._lock:
            if dataset_id in self.versions and version_id in self.versions[dataset_id]:
                # Get the version to check if it's the latest
                version = self.versions[dataset_id][version_id]
                is_latest = version.is_latest
                
                # Delete the version
                del self.versions[dataset_id][version_id]
                
                # If this was the latest version, update the dataset
                if is_latest and dataset_id in self.datasets:
                    dataset = self.datasets[dataset_id]
                    # Find the newest version by created_at
                    all_versions = self.list_dataset_versions(dataset_id, sort_by="created_at")
                    
                    if all_versions:
                        newest_version = all_versions[-1]
                        newest_version.is_latest = True
                        dataset.latest_version = newest_version.id
                        self.save_dataset_version(newest_version)
                    else:
                        dataset.latest_version = None
                    
                    dataset.updated_at = datetime.utcnow().isoformat()
                    self.save_dataset(dataset)
                
                return True
            return False

# ------------------------------------------------------------
# Example Preprocessing Functions
# ------------------------------------------------------------

def clean_missing_values(df: 'pd.DataFrame') -> 'pd.DataFrame':
    """Example preprocessing function: Clean missing values."""
    if not HAS_PANDAS:
        return df
    
    # Fill numeric columns with mean
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].mean())
    
    # Fill string columns with "Unknown"
    string_cols = df.select_dtypes(include=['object']).columns
    for col in string_cols:
        df[col] = df[col].fillna("Unknown")
    
    return df

def normalize_numeric_features(df: 'pd.DataFrame') -> 'pd.DataFrame':
    """Example preprocessing function: Normalize numeric features to [0,1]."""
    if not HAS_PANDAS:
        return df
    
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        min_val = df[col].min()
        max_val = df[col].max()
        if max_val > min_val:  # Avoid division by zero
            df[col] = (df[col] - min_val) / (max_val - min_val)
    
    return df

def encode_categorical_features(df: 'pd.DataFrame') -> 'pd.DataFrame':
    """Example preprocessing function: One-hot encode categorical features."""
    if not HAS_PANDAS:
        return df
    
    categorical_cols = df.select_dtypes(include=['object']).columns
    
    for col in categorical_cols:
        # Skip if too many unique values (would create too many columns)
        if df[col].nunique() < 10:
            # Create one-hot encoded columns
            dummies = pd.get_dummies(df[col], prefix=col)
            # Add to dataframe
            df = pd.concat([df, dummies], axis=1)
            # Remove original column
            df = df.drop(col, axis=1)
    
    return df

def create_train_test_split(df: 'pd.DataFrame', test_size: float = 0.2) -> Dict[str, 'pd.DataFrame']:
    """Example preprocessing function: Create train/test split."""
    if not HAS_PANDAS:
        return {"train": df, "test": df.iloc[0:0]}  # Empty dataframe for test
    
    # Shuffle the dataframe
    df = df.sample(frac=1.0, random_state=42)
    
    # Split into train and test
    split_idx = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    return {"train": train_df, "test": test_df}

def calculate_quality_metrics(df: 'pd.DataFrame') -> DataQualityMetrics:
    """Calculate quality metrics for a pandas DataFrame."""
    if not HAS_PANDAS:
        return DataQualityMetrics()
    
    # Basic statistics
    row_count = len(df)
    column_count = len(df.columns)
    
    # Missing values
    missing_values = {col: int(df[col].isna().sum()) for col in df.columns}
    missing_values_percent = {col: float(df[col].isna().mean() * 100) for col in df.columns}
    
    # Data types
    data_types = {col: str(df[col].dtype) for col in df.columns}
    
    # Statistical metrics for numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns
    min_values = {col: float(df[col].min()) for col in numeric_cols}
    max_values = {col: float(df[col].max()) for col in numeric_cols}
    mean_values = {col: float(df[col].mean()) for col in numeric_cols}
    median_values = {col: float(df[col].median()) for col in numeric_cols}
    std_values = {col: float(df[col].std()) for col in numeric_cols}
    
    # Categorical distributions
    categorical_cols = df.select_dtypes(include=['object']).columns
    categorical_distributions = {}
    for col in categorical_cols:
        value_counts = df[col].value_counts(normalize=True)
        categorical_distributions[col] = {str(k): float(v) for k, v in value_counts.items()}
    
    # Cardinality
    unique_values = {col: int(df[col].nunique()) for col in df.columns}
    
    # Correlations for numeric columns
    correlations = {}
    if len(numeric_cols) > 1:
        corr_matrix = df[numeric_cols].corr()
        for col1 in numeric_cols:
            correlations[col1] = {col2: float(corr_matrix.loc[col1, col2]) 
                                for col2 in numeric_cols}
    
    return DataQualityMetrics(
        row_count=row_count,
        column_count=column_count,
        missing_values=missing_values,
        missing_values_percent=missing_values_percent,
        min_values=min_values,
        max_values=max_values,
        mean_values=mean_values,
        median_values=median_values,
        std_values=std_values,
        unique_values=unique_values,
        categorical_distributions=categorical_distributions,
        data_types=data_types,
        correlations=correlations
    )

# ------------------------------------------------------------
# Example Functions
# ------------------------------------------------------------

def demonstrate_basic_usage(registry_dir: str, storage_type: str = "fs"):
    """
    Demonstrate basic dataset management functionality.
    """
    logger.info("=== Basic Dataset Management Demonstration ===")
    
    # Create temporary directory for datasets
    temp_dir = tempfile.mkdtemp()
    try:
        # Set up dataset storage
        if storage_type == "ipfs":
            try:
                # Try to import ipfs_client
                from ipfs_kit_py.ipfs_client import IPFSClient
                ipfs_client = IPFSClient()
                storage = IPFSDatasetStorage(ipfs_client)
                logger.info("Using IPFS storage backend")
            except ImportError:
                logger.warning("IPFS client not available, falling back to file system storage")
                storage_type = "fs"
        
        if storage_type == "s3":
            try:
                # This is just for demonstration - in a real app, you would use actual credentials
                bucket_name = "example-datasets"
                storage = S3DatasetStorage(bucket_name)
                logger.info(f"Using S3 storage backend with bucket: {bucket_name}")
            except Exception as e:
                logger.warning(f"S3 storage setup failed: {e}, falling back to file system storage")
                storage_type = "fs"
        
        if storage_type == "fs":
            storage_dir = os.path.join(registry_dir, "storage")
            storage = FileSystemDatasetStorage(storage_dir)
            logger.info(f"Using file system storage backend at: {storage_dir}")
        
        # Set up metadata store
        metadata_store = InMemoryMetadataStore()
        
        # --------------------------
        # Create sample data files
        # --------------------------
        csv_file = create_sample_csv_file(temp_dir)
        json_file = create_sample_json_file(temp_dir)
        text_files = create_sample_text_files(temp_dir)
        numpy_files = create_sample_numpy_arrays(temp_dir)
        
        # --------------------------
        # Step 1: Create a dataset
        # --------------------------
        dataset_id = str(uuid.uuid4())
        dataset = Dataset(
            id=dataset_id,
            name="Example Dataset",
            description="A dataset for demonstration purposes",
            owner="MCP Team",
            task_type="classification",
            tags=["demo", "example", "classification"],
            domain="general",
            license="MIT"
        )
        
        # Save the dataset
        metadata_store.save_dataset(dataset)
        logger.info(f"Created dataset: {dataset.id} - {dataset.name}")
        
        # --------------------------
        # Step 2: Create a version
        # --------------------------
        version_id = str(uuid.uuid4())
        version = DatasetVersion(
            id=version_id,
            version="v1",
            dataset_id=dataset.id,
            name="Initial version",
            description="First version of the example dataset",
            format=DatasetFormat.CSV,
            status=DatasetStatus.DRAFT
        )
        
        # Save the version
        metadata_store.save_dataset_version(version)
        logger.info(f"Created dataset version: {version.id} - {version.version}")
        
        # --------------------------
        # Step 3: Add files to the version
        # --------------------------
        # Add the CSV file
        with open(csv_file, 'rb') as f:
            # Create a DatasetFile object
            file_id = str(uuid.uuid4())
            file_name = os.path.basename(csv_file)
            storage_path = storage.save_dataset_file(
                dataset_id=dataset.id,
                version_id=version.id,
                file_path=file_name,
                file_obj=f
            )
            
            # Get file size
            file_size = os.path.getsize(csv_file)
            
            # Create file metadata
            file = DatasetFile(
                id=file_id,
                name=file_name,
                path=storage_path,
                split=DatasetSplit.TRAIN,
                format=DatasetFormat.CSV,
                size_bytes=file_size,
                content_type="text/csv"
            )
            
            # If pandas is available, get column information
            if HAS_PANDAS:
                df = pd.read_csv(csv_file)
                file.columns = list(df.columns)
                file.row_count = len(df)
            
            # Add to version
            version.add_file(file)
        
        # Add the JSON file
        with open(json_file, 'rb') as f:
            # Create a DatasetFile object
            file_id = str(uuid.uuid4())
            file_name = os.path.basename(json_file)
            storage_path = storage.save_dataset_file(
                dataset_id=dataset.id,
                version_id=version.id,
                file_path=file_name,
                file_obj=f
            )
            
            # Get file size
            file_size = os.path.getsize(json_file)
            
            # Create file metadata
            file = DatasetFile(
                id=file_id,
                name=file_name,
                path=storage_path,
                format=DatasetFormat.JSON,
                size_bytes=file_size,
                content_type="application/json"
            )
            
            # Add to version
            version.add_file(file)
        
        # Save the updated version
        metadata_store.save_dataset_version(version)
        logger.info(f"Added files to version. Total files: {version.file_count}")
        
        # --------------------------
        # Step 4: Calculate quality metrics
        # --------------------------
        if HAS_PANDAS:
            # Read the CSV file
            df = pd.read_csv(csv_file)
            
            # Calculate quality metrics
            quality_metrics = calculate_quality_metrics(df)
            
            # Update the version with quality metrics
            version.quality_metrics = quality_metrics
            metadata_store.save_dataset_version(version)
            
            # Log some metrics
            logger.info(f"Calculated quality metrics:")
            logger.info(f"  Rows: {quality_metrics.row_count}")
            logger.info(f"  Columns: {quality_metrics.column_count}")
            
            # Show missing values if any
            if quality_metrics.missing_values:
                missing_count = sum(quality_metrics.missing_values.values())
                if missing_count > 0:
                    logger.info(f"  Missing values: {missing_count}")
                    for col, count in quality_metrics.missing_values.items():
                        if count > 0:
                            logger.info(f"    {col}: {count} ({quality_metrics.missing_values_percent[col]:.1f}%)")
        
        # --------------------------
        # Step 5: Set up preprocessing pipeline
        # --------------------------
        if HAS_PANDAS:
            # Define preprocessing steps
            steps = [
                PreprocessingStep(
                    id=str(uuid.uuid4()),
                    name="Clean Missing Values",
                    stage=PreprocessingStage.CLEANING,
                    function_name="clean_missing_values",
                    order=1
                ),
                PreprocessingStep(
                    id=str(uuid.uuid4()),
                    name="Normalize Features",
                    stage=PreprocessingStage.NORMALIZATION,
                    function_name="normalize_numeric_features",
                    order=2
                ),
                PreprocessingStep(
                    id=str(uuid.uuid4()),
                    name="Encode Categories",
                    stage=PreprocessingStage.FEATURE_ENGINEERING,
                    function_name="encode_categorical_features",
                    order=3
                ),
                PreprocessingStep(
                    id=str(uuid.uuid4()),
                    name="Train-Test Split",
                    stage=PreprocessingStage.SPLITTING,
                    function_name="create_train_test_split",
                    parameters={"test_size": 0.2},
                    order=4
                )
            ]
            
            # Add steps to version
            for step in steps:
                version.add_preprocessing_step(step)
            
            metadata_store.save_dataset_version(version)
            logger.info(f"Added {len(steps)} preprocessing steps to version")
        
        # --------------------------
        # Step 6: Create a second version
        # --------------------------
        # First set the first version as the latest
        version.is_latest = True
        metadata_store.save_dataset_version(version)
        
        # Now create a second version
        version2_id = str(uuid.uuid4())
        version2 = DatasetVersion(
            id=version2_id,
            version="v2",
            dataset_id=dataset.id,
            name="Improved version",
            description="Second version with additional files",
            format=DatasetFormat.CUSTOM,
            parent_version=version.id,  # Track lineage
            is_latest=True  # This will be the latest version
        )
        
        # Add text files
        for text_file in text_files:
            with open(text_file, 'rb') as f:
                # Create a DatasetFile object
                file_id = str(uuid.uuid4())
                file_name = os.path.basename(text_file)
                storage_path = storage.save_dataset_file(
                    dataset_id=dataset.id,
                    version_id=version2.id,
                    file_path=f"texts/{file_name}",
                    file_obj=f
                )
                
                # Get file size
                file_size = os.path.getsize(text_file)
                
                # Create file metadata
                file = DatasetFile(
                    id=file_id,
                    name=file_name,
                    path=storage_path,
                    format=DatasetFormat.TEXT,
                    size_bytes=file_size,
                    content_type="text/plain"
                )
                
                # Add to version
                version2.add_file(file)
        
        # Also add the original CSV file for consistency
        with open(csv_file, 'rb') as f:
            # Create a DatasetFile object
            file_id = str(uuid.uuid4())
            file_name = os.path.basename(csv_file)
            storage_path = storage.save_dataset_file
