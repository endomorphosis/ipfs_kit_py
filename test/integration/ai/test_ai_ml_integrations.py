#!/usr/bin/env python3
"""
AI/ML Component Integration Test Utility

This script provides automated testing and verification of the AI/ML components in the MCP server.
It tests the integration between the model registry, dataset manager, distributed training,
and framework integration components to ensure they work together properly.

Usage:
  python test_ai_ml_integrations.py [--local-only] [--skip-training] [--ipfs] [--s3]
"""

import os
import sys
import argparse
import logging
import tempfile
import uuid
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ai-ml-integration-test")

# Try to import optional dependencies
try:
    import numpy as np
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("Pandas not available. Some tests will be limited.")

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available. Model training tests will be limited.")

# Test result tracking
class TestResults:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.start_time = time.time()
    
    def record_pass(self, test_name: str):
        self.tests_run += 1
        self.tests_passed += 1
        logger.info(f"✅ PASS: {test_name}")
    
    def record_fail(self, test_name: str, error: str):
        self.tests_run += 1
        self.tests_failed += 1
        self.failures.append((test_name, error))
        logger.error(f"❌ FAIL: {test_name} - {error}")
    
    def summary(self) -> str:
        duration = time.time() - self.start_time
        result = f"\n{'=' * 60}\n"
        result += f"TEST SUMMARY:\n"
        result += f"  Total tests: {self.tests_run}\n"
        result += f"  Passed: {self.tests_passed}\n"
        result += f"  Failed: {self.tests_failed}\n"
        result += f"  Duration: {duration:.2f} seconds\n"
        
        if self.failures:
            result += f"\nFAILURES:\n"
            for i, (test, error) in enumerate(self.failures):
                result += f"  {i+1}. {test}: {error}\n"
        
        result += f"{'=' * 60}\n"
        return result

# Test resources management
class TestResources:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory for test resources: {self.temp_dir}")
        
        # Tracking resources
        self.created_files = []
        self.dataset_ids = []
        self.model_ids = []
        self.job_ids = []
    
    def create_sample_data(self, rows: int = 100) -> str:
        """Create a sample CSV file for testing."""
        file_path = os.path.join(self.temp_dir, f"sample_data_{uuid.uuid4()}.csv")
        
        if not HAS_PANDAS:
            # Create a simple CSV manually
            with open(file_path, 'w') as f:
                f.write("id,feature1,feature2,target\n")
                for i in range(rows):
                    f.write(f"{i},{i*2},{i*3},{1 if i % 2 == 0 else 0}\n")
        else:
            # Create with pandas for more features
            df = pd.DataFrame({
                'id': range(rows),
                'feature1': np.random.normal(0, 1, rows),
                'feature2': np.random.normal(0, 1, rows),
                'feature3': np.random.normal(0, 1, rows),
                'feature4': np.random.normal(0, 1, rows),
                'target': np.random.randint(0, 2, rows)
            })
            df.to_csv(file_path, index=False)
        
        self.created_files.append(file_path)
        return file_path
    
    def create_simple_model(self) -> str:
        """Create a simple PyTorch model for testing."""
        if not HAS_TORCH:
            dummy_path = os.path.join(self.temp_dir, "dummy_model.txt")
            with open(dummy_path, 'w') as f:
                f.write("This is a dummy model file since PyTorch is not available.")
            self.created_files.append(dummy_path)
            return dummy_path
        
        model_path = os.path.join(self.temp_dir, "simple_model.pt")
        
        # Define a simple model
        class SimpleModel(torch.nn.Module):
            def __init__(self, input_size=10, hidden_size=50, output_size=1):
                super(SimpleModel, self).__init__()
                self.fc1 = torch.nn.Linear(input_size, hidden_size)
                self.relu = torch.nn.ReLU()
                self.fc2 = torch.nn.Linear(hidden_size, output_size)
                self.sigmoid = torch.nn.Sigmoid()
            
            def forward(self, x):
                x = self.fc1(x)
                x = self.relu(x)
                x = self.fc2(x)
                x = self.sigmoid(x)
                return x
        
        # Create and save the model
        model = SimpleModel()
        torch.save(model.state_dict(), model_path)
        
        self.created_files.append(model_path)
        return model_path
    
    def cleanup(self):
        """Clean up test resources."""
        for file_path in self.created_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")
        
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Removed temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove directory {self.temp_dir}: {e}")

# Integration test classes
class ModelRegistryTests:
    """Tests for the model registry component."""
    
    def __init__(self, results: TestResults, resources: TestResources, use_ipfs: bool = False, use_s3: bool = False):
        self.results = results
        self.resources = resources
        self.use_ipfs = use_ipfs
        self.use_s3 = use_s3
        self.model_registry = None
        self.initialized = False
    
    def setup(self) -> bool:
        """Set up the model registry for testing."""
        try:
            from ipfs_kit_py.mcp.ai.model_registry import (
                ModelRegistry, JSONFileMetadataStore, FileSystemModelStorage,
                IPFSModelStorage, S3ModelStorage
            )
            
            # Create directories
            registry_dir = os.path.join(self.resources.temp_dir, "model_registry")
            os.makedirs(registry_dir, exist_ok=True)
            
            # Create metadata store
            metadata_store = JSONFileMetadataStore(os.path.join(registry_dir, "metadata"))
            
            # Create appropriate storage backend
            if self.use_ipfs:
                try:
                    from ipfs_kit_py.ipfs_client import IPFSClient
                    ipfs_client = IPFSClient()
                    storage = IPFSModelStorage(ipfs_client)
                    logger.info("Using IPFS storage for model registry tests")
                except Exception as e:
                    logger.warning(f"Failed to initialize IPFS storage: {e}. Falling back to file system storage.")
                    storage = FileSystemModelStorage(os.path.join(registry_dir, "storage"))
            elif self.use_s3:
                try:
                    # For testing purposes, you would use actual credentials here
                    storage = S3ModelStorage("test-bucket", "models/")
                    logger.info("Using S3 storage for model registry tests")
                except Exception as e:
                    logger.warning(f"Failed to initialize S3 storage: {e}. Falling back to file system storage.")
                    storage = FileSystemModelStorage(os.path.join(registry_dir, "storage"))
            else:
                storage = FileSystemModelStorage(os.path.join(registry_dir, "storage"))
                logger.info("Using file system storage for model registry tests")
            
            # Initialize model registry
            self.model_registry = ModelRegistry(metadata_store, storage)
            self.initialized = True
            return True
        except Exception as e:
            self.results.record_fail("ModelRegistry_Setup", f"Failed to set up model registry: {e}")
            return False
    
    def run_tests(self):
        """Run all tests for the model registry component."""
        if not self.setup():
            return
        
        self.test_create_model()
        self.test_create_version()
        self.test_add_artifact()
        self.test_update_model()
        self.test_list_models()
    
    def test_create_model(self):
        """Test creating a model in the registry."""
        try:
            model = self.model_registry.create_model(
                name="Test Model",
                description="A model for testing purposes",
                owner="Test User",
                team="Test Team",
                project="Integration Tests",
                task_type="classification",
                tags=["test", "integration"]
            )
            
            # Verify model was created correctly
            assert model.id is not None, "Model ID should not be None"
            assert model.name == "Test Model", "Model name does not match"
            
            # Store the model ID for other tests
            self.resources.model_ids.append(model.id)
            
            # Get the model from the registry to make sure it was saved
            retrieved_model = self.model_registry.get_model(model.id)
            assert retrieved_model is not None, "Failed to retrieve model"
            assert retrieved_model.name == model.name, "Retrieved model name does not match"
            
            self.results.record_pass("ModelRegistry_CreateModel")
        except Exception as e:
            self.results.record_fail("ModelRegistry_CreateModel", f"Failed to create model: {e}")
    
    def test_create_version(self):
        """Test creating a model version in the registry."""
        if not self.resources.model_ids:
            self.results.record_fail("ModelRegistry_CreateVersion", "No model IDs available, skipping test")
            return
        
        try:
            from ipfs_kit_py.mcp.ai.model_registry import ModelFramework
            
            model_id = self.resources.model_ids[0]
            version = self.model_registry.create_model_version(
                model_id=model_id,
                version="1.0.0",
                name="Initial version",
                description="First version of the test model",
                framework=ModelFramework.PYTORCH
            )
            
            # Verify version was created correctly
            assert version.id is not None, "Version ID should not be None"
            assert version.version == "1.0.0", "Version string does not match"
            assert version.model_id == model_id, "Model ID does not match"
            
            # Get the version from the registry to make sure it was saved
            retrieved_version = self.model_registry.get_model_version(model_id, version.id)
            assert retrieved_version is not None, "Failed to retrieve version"
            assert retrieved_version.version == version.version, "Retrieved version string does not match"
            
            self.results.record_pass("ModelRegistry_CreateVersion")
        except Exception as e:
            self.results.record_fail("ModelRegistry_CreateVersion", f"Failed to create model version: {e}")
    
    def test_add_artifact(self):
        """Test adding an artifact to a model version."""
        if not self.resources.model_ids:
            self.results.record_fail("ModelRegistry_AddArtifact", "No model IDs available, skipping test")
            return
        
        try:
            from ipfs_kit_py.mcp.ai.model_registry import ArtifactType
            
            model_id = self.resources.model_ids[0]
            model_versions = self.model_registry.list_model_versions(model_id)
            
            if not model_versions:
                self.results.record_fail("ModelRegistry_AddArtifact", "No model versions available, skipping test")
                return
            
            version_id = model_versions[0].id
            model_file = self.resources.create_simple_model()
            
            artifact = self.model_registry.add_model_artifact(
                model_id=model_id,
                version_id=version_id,
                file_path=model_file,
                artifact_type=ArtifactType.MODEL_WEIGHTS,
                name="Model Weights",
                description="Weights for the test model"
            )
            
            # Verify artifact was added correctly
            assert artifact.id is not None, "Artifact ID should not be None"
            assert artifact.name == "Model Weights", "Artifact name does not match"
            
            # Get the version to make sure the artifact was added
            version = self.model_registry.get_model_version(model_id, version_id)
            assert len(version.artifacts) > 0, "No artifacts found in the model version"
            assert version.artifacts[0].id == artifact.id, "Artifact ID does not match"
            
            self.results.record_pass("ModelRegistry_AddArtifact")
        except Exception as e:
            self.results.record_fail("ModelRegistry_AddArtifact", f"Failed to add artifact: {e}")
    
    def test_update_model(self):
        """Test updating a model in the registry."""
        if not self.resources.model_ids:
            self.results.record_fail("ModelRegistry_UpdateModel", "No model IDs available, skipping test")
            return
        
        try:
            model_id = self.resources.model_ids[0]
            updated_model = self.model_registry.update_model(
                model_id=model_id,
                description="Updated description for testing",
                tags=["test", "integration", "updated"]
            )
            
            # Verify model was updated correctly
            assert updated_model is not None, "Failed to update model"
            assert updated_model.description == "Updated description for testing", "Description was not updated"
            assert "updated" in updated_model.tags, "Tags were not updated"
            
            # Get the model to verify the update was saved
            retrieved_model = self.model_registry.get_model(model_id)
            assert retrieved_model.description == updated_model.description, "Retrieved model description does not match"
            
            self.results.record_pass("ModelRegistry_UpdateModel")
        except Exception as e:
            self.results.record_fail("ModelRegistry_UpdateModel", f"Failed to update model: {e}")
    
    def test_list_models(self):
        """Test listing models in the registry."""
        try:
            models = self.model_registry.list_models()
            
            # Verify we can list models
            assert isinstance(models, list), "list_models should return a list"
            assert len(models) >= len(self.resources.model_ids), f"Expected at least {len(self.resources.model_ids)} models"
            
            # Try filtering by tags
            filtered_models = self.model_registry.list_models(
                filters={"tags": "test"}
            )
            
            assert len(filtered_models) > 0, "No models found with tag 'test'"
            
            self.results.record_pass("ModelRegistry_ListModels")
        except Exception as e:
            self.results.record_fail("ModelRegistry_ListModels", f"Failed to list models: {e}")

class DatasetManagerTests:
    """Tests for the dataset manager component."""
    
    def __init__(self, results: TestResults, resources: TestResources, use_ipfs: bool = False, use_s3: bool = False):
        self.results = results
        self.resources = resources
        self.use_ipfs = use_ipfs
        self.use_s3 = use_s3
        self.dataset_manager = None
        self.initialized = False
    
    def setup(self) -> bool:
        """Set up the dataset manager for testing."""
        try:
            from ipfs_kit_py.mcp.ai.dataset_manager import (
                DatasetManager, JSONFileMetadataStore, FileSystemDatasetStorage,
                IPFSDatasetStorage, S3DatasetStorage
            )
            
            # Create directories
            dataset_dir = os.path.join(self.resources.temp_dir, "dataset_manager")
            os.makedirs(dataset_dir, exist_ok=True)
            
            # Create metadata store
            metadata_store = JSONFileMetadataStore(os.path.join(dataset_dir, "metadata"))
            
            # Create appropriate storage backend
            if self.use_ipfs:
                try:
                    from ipfs_kit_py.ipfs_client import IPFSClient
                    ipfs_client = IPFSClient()
                    storage = IPFSDatasetStorage(ipfs_client)
                    logger.info("Using IPFS storage for dataset manager tests")
                except Exception as e:
                    logger.warning(f"Failed to initialize IPFS storage: {e}. Falling back to file system storage.")
                    storage = FileSystemDatasetStorage(os.path.join(dataset_dir, "storage"))
            elif self.use_s3:
                try:
                    # For testing purposes, you would use actual credentials here
                    storage = S3DatasetStorage("test-bucket", "datasets/")
                    logger.info("Using S3 storage for dataset manager tests")
                except Exception as e:
                    logger.warning(f"Failed to initialize S3 storage: {e}. Falling back to file system storage.")
                    storage = FileSystemDatasetStorage(os.path.join(dataset_dir, "storage"))
            else:
                storage = FileSystemDatasetStorage(os.path.join(dataset_dir, "storage"))
                logger.info("Using file system storage for dataset manager tests")
            
            # Initialize dataset manager
            self.dataset_manager = DatasetManager(metadata_store, storage)
            self.initialized = True
            return True
        except Exception as e:
            self.results.record_fail("DatasetManager_Setup", f"Failed to set up dataset manager: {e}")
            return False
    
    def run_tests(self):
        """Run all tests for the dataset manager component."""
        if not self.setup():
            return
        
        self.test_create_dataset()
        self.test_create_version()
        self.test_add_file()
        self.test_update_dataset()
        self.test_list_datasets()
    
    def test_create_dataset(self):
        """Test creating a dataset in the manager."""
        try:
            dataset = self.dataset_manager.create_dataset(
                name="Test Dataset",
                description="A dataset for testing purposes",
                owner="Test User",
                team="Test Team",
                project="Integration Tests",
                task_type="classification",
                domain="testing",
                tags=["test", "integration"]
            )
            
            # Verify dataset was created correctly
            assert dataset.id is not None, "Dataset ID should not be None"
            assert dataset.name == "Test Dataset", "Dataset name does not match"
            
            # Store the dataset ID for other tests
            self.resources.dataset_ids.append(dataset.id)
            
            # Get the dataset from the manager to make sure it was saved
            retrieved_dataset = self.dataset_manager.get_dataset(dataset.id)
            assert retrieved_dataset is not None, "Failed to retrieve dataset"
            assert retrieved_dataset.name == dataset.name, "Retrieved dataset name does not match"
            
            self.results.record_pass("DatasetManager_CreateDataset")
        except Exception as e:
            self.results.record_fail("DatasetManager_CreateDataset", f"Failed to create dataset: {e}")
    
    def test_create_version(self):
        """Test creating a dataset version."""
        if not self.resources.dataset_ids:
            self.results.record_fail("DatasetManager_CreateVersion", "No dataset IDs available, skipping test")
            return
        
        try:
            from ipfs_kit_py.mcp.ai.dataset_manager import DatasetFormat
            
            dataset_id = self.resources.dataset_ids[0]
            version = self.dataset_manager.create_dataset_version(
                dataset_id=dataset_id,
                version="1.0.0",
                name="Initial version",
                description="First version of the test dataset",
                format=DatasetFormat.CSV
            )
            
            # Verify version was created correctly
            assert version.id is not None, "Version ID should not be None"
            assert version.version == "1.0.0", "Version string does not match"
            assert version.dataset_id == dataset_id, "Dataset ID does not match"
            
            # Get the version from the manager to make sure it was saved
            retrieved_version = self.dataset_manager.get_dataset_version(dataset_id, version.id)
            assert retrieved_version is not None, "Failed to retrieve version"
            assert retrieved_version.version == version.version, "Retrieved version string does not match"
            
            self.results.record_pass("DatasetManager_CreateVersion")
        except Exception as e:
            self.results.record_fail("DatasetManager_CreateVersion", f"Failed to create dataset version: {e}")
    
    def test_add_file(self):
        """Test adding a file to a dataset version."""
        if not self.resources.dataset_ids:
            self.results.record_fail("DatasetManager_AddFile", "No dataset IDs available, skipping test")
            return
        
        try:
            from ipfs_kit_py.mcp.ai.dataset_manager import DatasetSplit
            
            dataset_id = self.resources.dataset_ids[0]
            dataset_versions = self.dataset_manager.list_dataset_versions(dataset_id)
            
            if not dataset_versions:
                self.results.record_fail("DatasetManager_AddFile", "No dataset versions available, skipping test")
                return
            
            version_id = dataset_versions[0].id
            data_file = self.resources.create_sample_data()
            
            # Add the file to the dataset version
            file = self.dataset_manager.add_dataset_file(
                dataset_id=dataset_id,
                version_id=version_id,
                file_path=data_file,
                split=DatasetSplit.TRAIN,
                name="Training Data",
                description="Sample training data for testing"
            )
            
            # Verify file was added correctly
            assert file.id is not None, "File ID should not be None"
            assert file.name == "Training Data", "File name does not match"
            
            # Get the version to make sure the file was added
            version = self.dataset_manager.get_dataset_version(dataset_id, version_id)
            assert len(version.files) > 0, "No files found in the dataset version"
            assert version.files[0].id == file.id, "File ID does not match"
            
            self.results.record_pass("DatasetManager_AddFile")
        except Exception as e:
            self.results.record_fail("DatasetManager_AddFile", f"Failed to add file: {e}")
    
    def test_update_dataset(self):
        """Test updating a dataset."""
        if not self.resources.dataset_ids:
            self.results.record_fail("DatasetManager_UpdateDataset", "No dataset IDs available, skipping test")
            return
        
        try:
            dataset_id = self.resources.dataset_ids[0]
            updated_dataset = self.dataset_manager.update_dataset(
                dataset_id=dataset_id,
                description="Updated description for testing",
                tags=["test", "integration", "updated"]
            )
            
            # Verify dataset was updated correctly
            assert updated_dataset is not None, "Failed to update dataset"
            assert updated_dataset.description == "Updated description for testing", "Description was not updated"
            assert "updated" in updated_dataset.tags, "Tags were not updated"
            
            # Get the dataset to verify the update was saved
            retrieved_dataset = self.dataset_manager.get_dataset(dataset_id)
            assert retrieved_dataset.description == updated_dataset.description, "Retrieved dataset description does not match"
            
            self.results.record_pass("DatasetManager_UpdateDataset")
        except Exception as e:
            self.results.record_fail("DatasetManager_UpdateDataset", f"Failed to update dataset: {e}")
    
    def test_list_datasets(self):
        """Test listing datasets."""
        try:
            datasets = self.dataset_manager.list_datasets()
            
            # Verify we can list datasets
            assert isinstance(datasets, list), "list_datasets should return a list"
            assert len(datasets) >= len(self.resources.dataset_ids), f"Expected at least {len(self.resources.dataset_ids)} datasets"
            
            # Try filtering by tags
            filtered_datasets = self.dataset_manager.list_datasets(
                filters={"tags": "test"}
            )
            
            assert len(filtered_datasets) > 0, "No datasets found with tag 'test'"
            
            self.results.record_pass("DatasetManager_ListDatasets")
        except Exception as e:
            self.results.record_fail("DatasetManager_ListDatasets", f"Failed to list datasets: {e}")

class DistributedTrainingTests:
    """Tests for the distributed training component."""
    
    def __init__(self, results: TestResults, resources: TestResources, skip_training: bool = False):
        self.results = results
        self.resources = resources
        self.skip_training = skip_training
        self.job_store = None
        self.job_runner = None
        self.initialized = False
    
    def setup(self) -> bool:
        """Set up the distributed training components for testing."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import (
                TrainingJobStore, TrainingJobRunner
            )
            
            # Initialize the job store and runner
            self.job_store = TrainingJobStore()
            self.job_runner = TrainingJobRunner(self.job_store)
            
            self.initialized = True
            return True
        except Exception as e:
            self.results.record_fail("DistributedTraining_Setup", f"Failed to set up distributed training: {e}")
            return False
    
    def run_tests(self):
        """Run all tests for the distributed training component."""
        if not self.setup():
            return
        
        self.test_job_creation()
        self.test_job_submission()
        
        if not self.skip_training:
            self.test_hyperparameter_tuning()
            self.test_model_integration()
    
    def test_job_creation(self):
        """Test creating a training job."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import (
                TrainingJob, TrainingJobConfig, TrainingJobType, FrameworkType,
                ResourceRequirements
            )
            
            # Create a simple job configuration
            job_config = TrainingJobConfig(
                name="Test Training Job",
                description="A training job for testing purposes",
                job_type=TrainingJobType.SINGLE_NODE,
                framework=FrameworkType.PYTORCH,
                script_path="/path/to/script.py",  # This is just for testing
                hyperparameters={
                    "batch_size": 32,
                    "epochs": 5,
                    "learning_rate": 0.001
                },
                resources=ResourceRequirements(
                    cpu_cores=2,
                    cpu_memory_gb=4.0,
                    gpu_count=0
                )
            )
            
            # Create the job
            job = TrainingJob(
                id=str(uuid.uuid4()),
                user_id="test_user",
                config=job_config
            )
            
            # Verify job was created correctly
            assert job.id is not None, "Job ID should not be None"
            assert job.config.name == "Test Training Job", "Job name does not match"
            
            # Store the job for other tests
            self.resources.job_ids.append(job.id)
            
            self.results.record_pass("DistributedTraining_JobCreation")
        except Exception as e:
            self.results.record_fail("DistributedTraining_JobCreation", f"Failed to create training job: {e}")
    
    def test_job_submission(self):
        """Test submitting a job to the job runner."""
        if not self.resources.job_ids:
            # Create a job if none exists
            self.test_job_creation()
            if not self.resources.job_ids:
                self.results.record_fail("DistributedTraining_JobSubmission", "No job IDs available, skipping test")
                return
        
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import TrainingStatus
            
            # Get the job from the previous test
            job_id = self.resources.job_ids[0]
            job = self.job_store.get_job(job_id)
            
            if job is None:
                # If the job isn't in the store, add it
                from ipfs_kit_py.mcp.ai.distributed_training import (
                    TrainingJob, TrainingJobConfig, TrainingJobType, FrameworkType,
                    ResourceRequirements
                )
                
                # Create a simple job configuration
                job_config = TrainingJobConfig(
                    name="Test Training Job",
                    description="A training job for testing purposes",
                    job_type=TrainingJobType.SINGLE_NODE,
                    framework=FrameworkType.PYTORCH,
                    script_path="/path/to/script.py",  # This is just for testing
                    hyperparameters={
                        "batch_size": 32,
                        "epochs": 5,
                        "learning_rate": 0.001
                    },
                    resources=ResourceRequirements(
                        cpu_cores=2,
                        cpu_memory_gb=4.0,
                        gpu_count=0
                    )
                )
                
                # Create the job
                job = TrainingJob(
                    id=job_id,
                    user_id="test_user",
                    config=job_config
                )
                
                # Add to job store
                self.job_store.save_job(job)
            
            # Submit the job
            submitted_job = self.job_runner.submit_job(job)
            
            # Verify job was submitted correctly
            assert submitted_job.id == job.id, "Job ID does not match"
            assert submitted_job.status == TrainingStatus.PENDING, "Job status should be PENDING"
            
            # Update job status for testing
            updated_job = self.job_store.update_job_status(
                job_id=job.id, 
                status=TrainingStatus.RUNNING,
                status_message="Running for test"
            )
            
            # Verify job status was updated
            assert updated_job.status == TrainingStatus.RUNNING, "Job status should be RUNNING"
            
            self.results.record_pass("DistributedTraining_JobSubmission")
        except Exception as e:
            self.results.record_fail("DistributedTraining_JobSubmission", f"Failed to submit job: {e}")
    
    def test_hyperparameter_tuning(self):
        """Test hyperparameter tuning job."""
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import (
                TrainingJob, TrainingJobConfig, TrainingJobType, FrameworkType,
                ResourceRequirements, HyperparameterConfig, OptimizationStrategy
            )
            
            # Create a hyperparameter tuning job configuration
            hp_config = HyperparameterConfig(
                param_space={
                    "batch_size": [16, 32, 64],
                    "learning_rate": [0.0001, 0.001, 0.01],
                    "dropout": [0.1, 0.3, 0.5]
                },
                strategy=OptimizationStrategy.GRID_SEARCH,
                metric_name="validation_loss",
                mode="min",
                num_trials=9
            )
            
            job_config = TrainingJobConfig(
                name="Test HP Tuning Job",
                description="A hyperparameter tuning job for testing purposes",
                job_type=TrainingJobType.HYPERPARAMETER_TUNING,
                framework=FrameworkType.PYTORCH,
                script_path="/path/to/script.py",  # This is just for testing
                resources=ResourceRequirements(
                    cpu_cores=2,
                    cpu_memory_gb=4.0,
                    gpu_count=0
                ),
                hyperparameter_tuning=hp_config
            )
            
            # Create the job
            job_id = str(uuid.uuid4())
            job = TrainingJob(
                id=job_id,
                user_id="test_user",
                config=job_config
            )
            
            # Submit the job
            submitted_job = self.job_runner.submit_job(job)
            
            # Verify job was created correctly
            assert submitted_job.id is not None, "Job ID should not be None"
            assert submitted_job.config.job_type == TrainingJobType.HYPERPARAMETER_TUNING, "Job type does not match"
            
            # Store the job for other tests
            self.resources.job_ids.append(job_id)
            
            self.results.record_pass("DistributedTraining_HyperparameterTuning")
        except Exception as e:
            self.results.record_fail("DistributedTraining_HyperparameterTuning", f"Failed to create HP tuning job: {e}")
    
    def test_model_integration(self):
        """Test integration with model registry."""
        # This test depends on model registry and dataset manager
        if not self.resources.model_ids or not self.resources.dataset_ids:
            self.results.record_fail("DistributedTraining_ModelIntegration", "No model or dataset IDs available, skipping test")
            return
        
        try:
            from ipfs_kit_py.mcp.ai.distributed_training import (
                TrainingJob, TrainingJobConfig, TrainingJobType, FrameworkType,
                ResourceRequirements
            )
            
            # Get a model and dataset ID
            model_id = self.resources.model_ids[0]
            dataset_id = self.resources.dataset_ids[0]
            
            # Create a job configuration with model registry integration
            job_config = TrainingJobConfig(
                name="Model Registry Integration Job",
                description="A job integrated with the model registry",
                job_type=TrainingJobType.SINGLE_NODE,
                framework=FrameworkType.PYTORCH,
                script_path="/path/to/script.py",  # This is just for testing
                hyperparameters={
                    "batch_size": 32,
                    "epochs": 5,
                    "learning_rate": 0.001
                },
                resources=ResourceRequirements(
                    cpu_cores=2,
                    cpu_memory_gb=4.0,
                    gpu_count=0
                ),
                model_registry_id=model_id,
                dataset_id=dataset_id
            )
            
            # Create the job
            job_id = str(uuid.uuid4())
            job = TrainingJob(
                id=job_id,
                user_id="test_user",
                config=job_config
            )
            
            # Submit the job
            submitted_job = self.job_runner.submit_job(job)
            
            # Verify job was created correctly
            assert submitted_job.id is not None, "Job ID should not be None"
            assert submitted_job.config.model_registry_id == model_id, "Model registry ID does not match"
            assert submitted_job.config.dataset_id == dataset_id, "Dataset ID does not match"
            
            self.results.record_pass("DistributedTraining_ModelIntegration")
        except Exception as e:
            self.results.record_fail("DistributedTraining_ModelIntegration", f"Failed to create integrated job: {e}")


class FrameworkIntegrationTests:
    """Tests for the framework integration component."""
    
    def __init__(self, results: TestResults, resources: TestResources):
        self.results = results
        self.resources = resources
        self.framework_integration = None
        self.initialized = False
    
    def setup(self) -> bool:
        """Set up the framework integration for testing."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import (
                LangChainConfig, HuggingFaceConfig, LangChainIntegration, HuggingFaceIntegration
            )
            
            # Just test setup - we don't need to create actual integrations for testing
            self.initialized = True
            return True
        except Exception as e:
            self.results.record_fail("FrameworkIntegration_Setup", f"Failed to set up framework integration: {e}")
            return False
    
    def run_tests(self):
        """Run all tests for the framework integration component."""
        if not self.setup():
            return
        
        self.test_config_creation()
        self.test_huggingface_integration()
        self.test_model_endpoint()
    
    def test_config_creation(self):
        """Test creating framework configurations."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import (
                LangChainConfig, HuggingFaceConfig, FrameworkType
            )
            
            # Create a LangChain config
            lc_config = LangChainConfig(
                name="Test LangChain Integration",
                llm_type="openai",
                llm_model="gpt-3.5-turbo",
                prompt_templates={
                    "simple": "Answer the following question: {query}"
                }
            )
            
            # Create a HuggingFace config
            hf_config = HuggingFaceConfig(
                name="Test HuggingFace Integration",
                model_id="gpt2",
                use_local=False
            )
            
            # Verify configs were created correctly
            assert lc_config.framework_type == FrameworkType.LANGCHAIN, "LangChain config type does not match"
            assert hf_config.framework_type == FrameworkType.HUGGINGFACE, "HuggingFace config type does not match"
            assert lc_config.llm_model == "gpt-3.5-turbo", "LLM model does not match"
            assert hf_config.model_id == "gpt2", "Model ID does not match"
            
            self.results.record_pass("FrameworkIntegration_ConfigCreation")
        except Exception as e:
            self.results.record_fail("FrameworkIntegration_ConfigCreation", f"Failed to create framework configs: {e}")
    
    def test_huggingface_integration(self):
        """Test HuggingFace integration functionality."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import (
                HuggingFaceConfig, HuggingFaceIntegration
            )
            
            # For testing, we'll just check if the integration can be created
            # without actually making API calls
            
            # Create a HuggingFace config
            hf_config = HuggingFaceConfig(
                name="Test HuggingFace Integration",
                model_id="gpt2",
                use_local=False
            )
            
            # Create integration
            integration = HuggingFaceIntegration(hf_config)
            
            # Verify the integration was created correctly
            assert integration.config.name == "Test HuggingFace Integration", "Integration name does not match"
            assert integration.config.model_id == "gpt2", "Model ID does not match"
            
            self.results.record_pass("FrameworkIntegration_HuggingFace")
        except Exception as e:
            self.results.record_fail("FrameworkIntegration_HuggingFace", f"Failed to create HuggingFace integration: {e}")
    
    def test_model_endpoint(self):
        """Test creating a model endpoint."""
        try:
            from ipfs_kit_py.mcp.ai.framework_integration import (
                ModelEndpoint, EndpointType, InferenceType, FrameworkType
            )
            
            # Create a model endpoint
            endpoint = ModelEndpoint(
                id=str(uuid.uuid4()),
                name="Test Endpoint",
                description="A test model endpoint",
                model_id=self.resources.model_ids[0] if self.resources.model_ids else None,
                endpoint_type=EndpointType.REST,
                endpoint_url="https://example.com/api/models/endpoint",
                inference_type=InferenceType.TEXT_GENERATION,
                framework_type=FrameworkType.HUGGINGFACE
            )
            
            # Verify endpoint was created correctly
            assert endpoint.id is not None, "Endpoint ID should not be None"
            assert endpoint.name == "Test Endpoint", "Endpoint name does not match"
            assert endpoint.inference_type == InferenceType.TEXT_GENERATION, "Inference type does not match"
            
            self.results.record_pass("FrameworkIntegration_ModelEndpoint")
        except Exception as e:
            self.results.record_fail("FrameworkIntegration_ModelEndpoint", f"Failed to create model endpoint: {e}")


def run_integration_tests(args):
    """Run all integration tests."""
    # Set up test results and resources
    results = TestResults()
    resources = TestResources()
    
    try:
        # Run tests for each component
        logger.info("Starting AI/ML Component Integration Tests")
        
        # Model Registry Tests
        logger.info("\n==== Running Model Registry Tests ====")
        model_tests = ModelRegistryTests(results, resources, use_ipfs=args.ipfs, use_s3=args.s3)
        model_tests.run_tests()
        
        # Dataset Manager Tests
        logger.info("\n==== Running Dataset Manager Tests ====")
        dataset_tests = DatasetManagerTests(results, resources, use_ipfs=args.ipfs, use_s3=args.s3)
        dataset_tests.run_tests()
        
        # Distributed Training Tests
        logger.info("\n==== Running Distributed Training Tests ====")
        training_tests = DistributedTrainingTests(results, resources, skip_training=args.skip_training)
        training_tests.run_tests()
        
        # Framework Integration Tests
        logger.info("\n==== Running Framework Integration Tests ====")
        framework_tests = FrameworkIntegrationTests(results, resources)
        framework_tests.run_tests()
        
        # Integration between components
        if not args.local_only:
            logger.info("\n==== Running Cross-Component Integration Tests ====")
            # TODO: Implement cross-component integration tests
            
        # Print test summary
        logger.info(results.summary())
        
        return results.tests_failed == 0
    finally:
        # Clean up resources
        resources.cleanup()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AI/ML Component Integration Test Utility")
    parser.add_argument("--local-only", action="store_true", help="Only test local component functionality, not integration between components")
    parser.add_argument("--skip-training", action="store_true", help="Skip distributed training tests")
    parser.add_argument("--ipfs", action="store_true", help="Use IPFS storage backend for tests")
    parser.add_argument("--s3", action="store_true", help="Use S3 storage backend for tests")
    args = parser.parse_args()
    
    # Run tests
    success = run_integration_tests(args)
    
    # Exit with appropriate status code
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
