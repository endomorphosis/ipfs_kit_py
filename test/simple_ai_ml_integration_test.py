"""
Unit tests for ai_ml_integration.py using unittest framework.
"""

import json
import os
import pickle
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

# Import the classes to test
from ipfs_kit_py.ai_ml_integration import (
    DatasetManager,
    DistributedTraining,
    IPFSDataLoader,
    LangchainIntegration,
    LlamaIndexIntegration,
    ModelRegistry,
)


class TestModelRegistry(unittest.TestCase):
    """Tests for the ModelRegistry class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Configure the mock to return expected values
        self.ipfs_client.dag_put.return_value = "QmTest123"
        self.ipfs_client.add_directory.return_value = {"success": True, "Hash": "QmTestDir123"}
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Initialize with temp directory for test isolation
        self.test_dir = tempfile.mkdtemp()
        self.registry = ModelRegistry(self.ipfs_client, base_path=self.test_dir)

    def tearDown(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test ModelRegistry initialization."""
        self.assertEqual(self.registry.ipfs, self.ipfs_client)
        self.assertEqual(self.registry.base_path, self.test_dir)

        # Check that registry file was created
        registry_file = os.path.join(self.test_dir, "model_registry.json")
        self.assertTrue(os.path.exists(registry_file))

        # Check registry structure
        with open(registry_file, "r") as f:
            registry_data = json.load(f)
            self.assertIn("models", registry_data)
            self.assertIn("updated_at", registry_data)
            self.assertIn("version", registry_data)

    def test_add_model(self):
        """Test adding a model to the registry."""
        # Create a simple model
        model = {"layers": [10, 5, 1], "weights": [0.1, 0.2, 0.3]}

        # Add the model to the registry
        result = self.registry.add_model(
            model,
            model_name="test_model",
            version="1.0.0",
            framework="test",
            metadata={"accuracy": 0.95},
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["framework"], "test")
        self.assertEqual(result["cid"], "QmTestDir123")

        # Check that IPFS client was called correctly
        self.ipfs_client.add_directory.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once_with("QmTestDir123")

        # Check registry was updated
        self.assertIn("test_model", self.registry.registry["models"])
        self.assertIn("1.0.0", self.registry.registry["models"]["test_model"])
        self.assertEqual(
            self.registry.registry["models"]["test_model"]["1.0.0"]["cid"], "QmTestDir123"
        )

    def test_add_model_error_handling(self):
        """Test error handling when adding a model."""
        # Configure mock to simulate an error
        self.ipfs_client.add_directory.return_value = {"success": False, "error": "Test error"}

        # Create a simple model
        model = {"layers": [10, 5, 1], "weights": [0.1, 0.2, 0.3]}

        # Add the model to the registry
        result = self.registry.add_model(model, model_name="test_model", version="1.0.0")

        # Check result contains error
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["error_type"], "Exception")

    def test_get_model(self):
        """Test retrieving a model from the registry."""
        # Set up mock for ipfs_client.get
        self.ipfs_client.get.return_value = True

        # Set up mock for ipfs_client.dag_get to return mock metadata
        metadata_json = {
            "name": "test_model",
            "version": "1.0.0",
            "framework": "test",
            "files": {"model": "model.pkl"},
        }

        # Mock the filesystem operations
        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(metadata_json))):
            with patch("pickle.load") as mock_pickle_load:
                # Set up mock to return a model
                mock_model = {"type": "test_model", "data": [1, 2, 3]}
                mock_pickle_load.return_value = mock_model

                # Add a model to the registry first
                self.registry.registry["models"]["test_model"] = {
                    "1.0.0": {"cid": "QmTestModelCID", "framework": "test"}
                }

                # Get the model
                model, metadata = self.registry.get_model("test_model", "1.0.0")

                # Check that the correct model was returned
                self.assertEqual(model, mock_model)
                self.assertEqual(metadata["name"], "test_model")
                self.assertEqual(metadata["version"], "1.0.0")

    def test_list_models(self):
        """Test listing models in the registry."""
        # Populate registry with test models
        self.registry.registry["models"] = {
            "model1": {
                "1.0.0": {
                    "cid": "QmModel1v1",
                    "framework": "framework1",
                    "added_at": time.time(),
                    "metadata": {"accuracy": 0.9},
                },
                "1.1.0": {
                    "cid": "QmModel1v2",
                    "framework": "framework1",
                    "added_at": time.time(),
                    "metadata": {"accuracy": 0.95},
                },
            },
            "model2": {
                "1.0.0": {
                    "cid": "QmModel2v1",
                    "framework": "framework2",
                    "added_at": time.time(),
                    "metadata": {"accuracy": 0.8},
                }
            },
        }

        # Get the model list
        result = self.registry.list_models()

        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("model1", result["models"])
        self.assertIn("model2", result["models"])
        self.assertEqual(len(result["models"]["model1"]), 2)
        self.assertEqual(len(result["models"]["model2"]), 1)

        # Check sorting of versions
        self.assertEqual(result["models"]["model1"][0]["version"], "1.0.0")
        self.assertEqual(result["models"]["model1"][1]["version"], "1.1.0")


class TestDatasetManager(unittest.TestCase):
    """Tests for the DatasetManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Configure the mock to return expected values
        self.ipfs_client.dag_put.return_value = "QmTest123"
        self.ipfs_client.add_directory.return_value = {"success": True, "Hash": "QmTestDir123"}
        self.ipfs_client.pin_add.return_value = {"success": True}
        self.ipfs_client.get.return_value = {"success": True}

        # Initialize with temp directory for test isolation
        self.test_dir = tempfile.mkdtemp()
        self.manager = DatasetManager(self.ipfs_client, base_path=self.test_dir)

        # Create a test dataset file
        self.dataset_path = os.path.join(self.test_dir, "test_dataset.csv")
        with open(self.dataset_path, "w") as f:
            f.write("col1,col2,col3\n1,2,3\n4,5,6\n")

    def tearDown(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test DatasetManager initialization."""
        self.assertEqual(self.manager.ipfs, self.ipfs_client)
        self.assertEqual(self.manager.base_path, self.test_dir)

        # Check that registry file was created
        registry_file = os.path.join(self.test_dir, "dataset_registry.json")
        self.assertTrue(os.path.exists(registry_file))

        # Check registry structure
        with open(registry_file, "r") as f:
            registry_data = json.load(f)
            self.assertIn("datasets", registry_data)
            self.assertIn("updated_at", registry_data)
            self.assertIn("version", registry_data)

    def test_add_dataset(self):
        """Test adding a dataset to the registry."""
        # Add the dataset to the registry
        result = self.manager.add_dataset(
            self.dataset_path,
            dataset_name="test_dataset",
            version="1.0.0",
            format="csv",
            metadata={"source": "test"},
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_name"], "test_dataset")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["format"], "csv")
        self.assertEqual(result["cid"], "QmTestDir123")

        # Check that IPFS client was called correctly
        self.ipfs_client.add_directory.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once_with("QmTestDir123")

        # Check registry was updated
        self.assertIn("test_dataset", self.manager.registry["datasets"])
        self.assertIn("1.0.0", self.manager.registry["datasets"]["test_dataset"])
        self.assertEqual(
            self.manager.registry["datasets"]["test_dataset"]["1.0.0"]["cid"], "QmTestDir123"
        )

    def test_add_dataset_with_format_detection(self):
        """Test format detection when adding a dataset."""
        # Add the dataset without specifying the format
        result = self.manager.add_dataset(
            self.dataset_path, dataset_name="test_dataset", version="1.0.0"
        )

        # Check that format was detected correctly
        self.assertEqual(result["format"], "csv")

    def test_get_dataset(self):
        """Test retrieving a dataset from the registry."""
        # Set up mock response
        mock_metadata = {"name": "test_dataset", "version": "1.0.0", "format": "csv"}

        with patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(mock_metadata))):
            # Add dataset to registry
            self.manager.registry["datasets"]["test_dataset"] = {
                "1.0.0": {"cid": "QmTestDatasetCID", "format": "csv"}
            }

            # Get the dataset
            result = self.manager.get_dataset("test_dataset", "1.0.0")

            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["dataset_name"], "test_dataset")
            self.assertEqual(result["version"], "1.0.0")
            self.assertEqual(result["format"], "csv")
            self.assertEqual(result["cid"], "QmTestDatasetCID")

            # Check that IPFS client was called correctly
            self.ipfs_client.get.assert_called_once()

    def test_list_datasets(self):
        """Test listing datasets in the registry."""
        # Populate registry with test datasets
        self.manager.registry["datasets"] = {
            "dataset1": {
                "1.0.0": {
                    "cid": "QmDataset1v1",
                    "format": "csv",
                    "added_at": time.time(),
                    "metadata": {"source": "test1"},
                },
                "1.1.0": {
                    "cid": "QmDataset1v2",
                    "format": "csv",
                    "added_at": time.time(),
                    "metadata": {"source": "test1"},
                },
            },
            "dataset2": {
                "1.0.0": {
                    "cid": "QmDataset2v1",
                    "format": "parquet",
                    "added_at": time.time(),
                    "metadata": {"source": "test2"},
                }
            },
        }

        # Get the dataset list
        result = self.manager.list_datasets()

        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("dataset1", result["datasets"])
        self.assertIn("dataset2", result["datasets"])
        self.assertEqual(len(result["datasets"]["dataset1"]), 2)
        self.assertEqual(len(result["datasets"]["dataset2"]), 1)

        # Check sorting of versions
        self.assertEqual(result["datasets"]["dataset1"][0]["version"], "1.0.0")
        self.assertEqual(result["datasets"]["dataset1"][1]["version"], "1.1.0")


class TestLangchainIntegration(unittest.TestCase):
    """Tests for the LangchainIntegration class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Initialize LangchainIntegration
        self.langchain = LangchainIntegration(self.ipfs_client)

    def test_check_availability(self):
        """Test checking Langchain availability."""
        # Run the availability check
        result = self.langchain.check_availability()

        # There should always be a result regardless of whether Langchain is installed
        self.assertIn("langchain_available", result)
        self.assertIn("numpy_available", result)


class TestLlamaIndexIntegration(unittest.TestCase):
    """Tests for the LlamaIndexIntegration class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Initialize LlamaIndexIntegration
        self.llama_index = LlamaIndexIntegration(self.ipfs_client)

    def test_check_availability(self):
        """Test checking LlamaIndex availability."""
        # Run the availability check
        result = self.llama_index.check_availability()

        # There should always be a result regardless of whether LlamaIndex is installed
        self.assertIn("llama_index_available", result)
        self.assertIn("numpy_available", result)


class TestIPFSDataLoader(unittest.TestCase):
    """Tests for the IPFSDataLoader class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Mock the dag_get method to return dataset metadata
        self.ipfs_client.dag_get.return_value = {
            "success": True,
            "object": {"samples": ["QmSample1", "QmSample2", "QmSample3"]},
        }

        # Initialize data loader
        self.loader = IPFSDataLoader(self.ipfs_client, batch_size=2, shuffle=True, prefetch=1)

    def tearDown(self):
        """Clean up after tests."""
        self.loader.close()

    def test_initialization(self):
        """Test IPFSDataLoader initialization."""
        self.assertEqual(self.loader.ipfs, self.ipfs_client)
        self.assertEqual(self.loader.batch_size, 2)
        self.assertTrue(self.loader.shuffle)
        self.assertEqual(self.loader.prefetch, 1)
        self.assertEqual(self.loader.total_samples, 0)

    def test_load_dataset(self):
        """Test loading a dataset."""
        # Load dataset
        result = self.loader.load_dataset("QmTestDataset")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_cid"], "QmTestDataset")
        self.assertEqual(result["total_samples"], 3)

        # Check that the samples were loaded
        self.assertEqual(self.loader.sample_cids, ["QmSample1", "QmSample2", "QmSample3"])
        self.assertEqual(self.loader.total_samples, 3)

        # Check IPFS client was called correctly
        self.ipfs_client.dag_get.assert_called_once()

    def test_length(self):
        """Test the __len__ method."""
        # Set up samples
        self.loader.sample_cids = ["QmSample1", "QmSample2", "QmSample3", "QmSample4", "QmSample5"]
        self.loader.total_samples = 5

        # Check length calculation with batch_size=2
        self.assertEqual(len(self.loader), 3)  # Ceil(5/2) = 3

        # Change batch size and check again
        self.loader.batch_size = 3
        self.assertEqual(len(self.loader), 2)  # Ceil(5/3) = 2


class TestDistributedTraining(unittest.TestCase):
    """Tests for the DistributedTraining class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock IPFS client
        self.ipfs_client = MagicMock()

        # Create a mock cluster manager
        self.cluster_manager = MagicMock()

        # Initialize DistributedTraining
        self.training = DistributedTraining(self.ipfs_client, self.cluster_manager)

    def test_initialization(self):
        """Test DistributedTraining initialization."""
        self.assertEqual(self.training.ipfs, self.ipfs_client)
        self.assertEqual(self.training.cluster_manager, self.cluster_manager)

        # Check that internal components were initialized
        self.assertIsInstance(self.training.model_registry, ModelRegistry)
        self.assertIsInstance(self.training.dataset_manager, DatasetManager)

    def test_prepare_distributed_task(self):
        """Test preparing a distributed training task."""
        # Mock the dataset_manager registry
        self.training.dataset_manager.registry = {
            "datasets": {"test_dataset": {"1.0.0": {"cid": "QmTestDataset"}}}
        }

        # Mock cluster manager's get_active_workers and create_task methods
        self.cluster_manager.get_active_workers.return_value = [
            {"id": "worker1"},
            {"id": "worker2"},
        ]
        self.cluster_manager.create_task.return_value = {"success": True, "task_id": "test_task_id"}

        # Prepare a distributed task
        result = self.training.prepare_distributed_task(
            model_name="test_model",
            dataset_name="test_dataset",
            training_config={"epochs": 10, "batch_size": 32},
            num_workers=2,
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["dataset_name"], "test_dataset")
        self.assertEqual(result["num_workers"], 2)

        # Check that cluster manager was called correctly
        self.cluster_manager.get_active_workers.assert_called_once()
        self.cluster_manager.create_task.assert_called_once()

    def test_execute_training_task(self):
        """Test executing a training task."""
        # Mock IPFS cat to return task config
        task_config = {
            "operation": "distributed_training",
            "model_name": "test_model",
            "dataset_name": "test_dataset",
            "dataset_cid": "QmTestDataset",
            "model_cid": None,
            "training_config": {"epochs": 10, "batch_size": 32},
            "created_at": time.time(),
            "task_id": "test_task_id",
        }
        self.ipfs_client.cat.return_value = {"success": True, "content": json.dumps(task_config)}

        # Mock IPFS get for dataset and model
        self.ipfs_client.get.return_value = {"success": True}

        # Execute the training task
        result = self.training.execute_training_task(
            task_config_cid="QmTestConfig", worker_id="worker1"
        )

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["task_id"], "test_task_id")
        self.assertEqual(result["dataset_cid"], "QmTestDataset")

    def test_aggregate_training_results(self):
        """Test aggregating training results."""
        # Mock cluster manager's get_task_results method
        self.cluster_manager.get_task_results.return_value = {
            "results": [
                {"model_name": "test_model", "model_cid": "QmModel1", "metrics": {"accuracy": 0.9}},
                {
                    "model_name": "test_model",
                    "model_cid": "QmModel2",
                    "metrics": {"accuracy": 0.95},
                },
            ]
        }

        # Mock _register_aggregate_model method
        self.training._register_aggregate_model = MagicMock(
            return_value={
                "success": True,
                "model_name": "test_model",
                "version": "1.0.0",
                "cid": "QmBestModel",
            }
        )

        # Aggregate training results
        result = self.training.aggregate_training_results("test_task_id")

        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["best_model_cid"], "QmModel2")  # Higher accuracy
        self.assertEqual(result["num_workers"], 2)

        # Check that cluster manager was called correctly
        self.cluster_manager.get_task_results.assert_called_once_with("test_task_id")

        # Check that _register_aggregate_model was called correctly
        self.training._register_aggregate_model.assert_called_once()


if __name__ == "__main__":
    unittest.main()
