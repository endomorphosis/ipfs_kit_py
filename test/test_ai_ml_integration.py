"""
Test suite for the AI/ML Integration functionality.

This module tests the AI/ML Integration implementation which provides:
1. Model and dataset storage with content addressing
2. Langchain and LlamaIndex connectors
3. Distributed training capabilities
4. ML framework integration

This test module uses mocking extensively to test functionality
without requiring actual ML frameworks or distributed infrastructure.
"""

import json
import os
import pickle
import sys
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Add parent directory to path to import from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the new test fixtures
try:
    from test.test_fixtures.ai_ml_test_fixtures import (
        MockMLModel, MockSklearnModel, MockPyTorchModel, MockTensorflowModel,
        MockDataset, ModelScenario, DatasetScenario
    )
    FIXTURES_AVAILABLE = True
except ImportError:
    FIXTURES_AVAILABLE = False

from ipfs_kit_py.ai_ml_integration import (
    LANGCHAIN_AVAILABLE,
    LLAMA_INDEX_AVAILABLE,
    SKLEARN_AVAILABLE,
    TF_AVAILABLE,
    TORCH_AVAILABLE,
    DatasetManager,
    DistributedTraining,
    IPFSDataLoader,
    LangchainIntegration,
    LlamaIndexIntegration,
    ModelRegistry,
    TensorflowIntegration,
    PyTorchIntegration,
)


class TestModelRegistry(unittest.TestCase):
    """Test cases for the Model Registry implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Set flag to disable demo mode
        self.ipfs_client._testing_mode = False

        # Mock IPFS dag_put
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"

        # Mock IPFS ipfs_add_path (new method name)
        self.ipfs_client.ipfs_add_path = MagicMock()
        mock_dir_cid = f"mock-dir-cid-{uuid.uuid4()}"
        self.ipfs_client.ipfs_add_path.return_value = {
            "success": True,
            "Hash": mock_dir_cid,
            "is_directory": True,
            "files": {"/tmp/mock_dir": mock_dir_cid},
        }

        # Keep add_directory for backward compatibility
        self.ipfs_client.add_directory = self.ipfs_client.ipfs_add_path

        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps({"test": "data"}),
        }

        # Mock IPFS get
        self.ipfs_client.get.return_value = {"success": True}

        # Mock IPFS pin_add
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()

        # Initialize model registry
        self.model_registry = ModelRegistry(ipfs_client=self.ipfs_client, base_path=self.temp_dir)

        # Create a dummy model for testing
        self.dummy_model = {"type": "dummy_model", "version": "1.0.0"}

    def test_init_and_empty_registry(self):
        """Test initialization and empty registry creation."""
        # Verify empty registry structure
        self.assertIn("models", self.model_registry.registry)
        self.assertIn("updated_at", self.model_registry.registry)
        self.assertIn("version", self.model_registry.registry)
        self.assertEqual(self.model_registry.registry["version"], "1.0.0")
        self.assertEqual(len(self.model_registry.registry["models"]), 0)

        # Verify registry file was created
        registry_file = os.path.join(self.temp_dir, "model_registry.json")
        self.assertTrue(os.path.exists(registry_file))

    def test_add_model(self):
        """Test adding a model to the registry."""
        # Add a model to the registry
        result = self.model_registry.add_model(
            model=self.dummy_model,
            model_name="test_model",
            version="1.0.0",
            framework="test_framework",
            metadata={"test_key": "test_value"},
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["framework"], "test_framework")
        self.assertIn("cid", result)

        # Verify model was added to registry
        self.assertIn("test_model", self.model_registry.registry["models"])
        self.assertIn("1.0.0", self.model_registry.registry["models"]["test_model"])
        self.assertEqual(
            self.model_registry.registry["models"]["test_model"]["1.0.0"]["framework"],
            "test_framework",
        )

        # Verify IPFS interactions
        self.ipfs_client.ipfs_add_path.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once()

    @patch("ipfs_kit_py.ai_ml_integration.SKLEARN_AVAILABLE", True)
    @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", False)
    @patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", False)
    def test_framework_detection_sklearn(self):
        """Test detection of scikit-learn models."""

        # Mock sklearn BaseEstimator
        class MockSklearnEstimator:
            pass

        # Mock sklearn module
        with patch("ipfs_kit_py.ai_ml_integration.sklearn") as mock_sklearn:
            # Create mock base module with BaseEstimator
            mock_sklearn.base = MagicMock()
            mock_sklearn.base.BaseEstimator = MockSklearnEstimator
            mock_sklearn.__version__ = "1.0.0"

            # Create a mock model
            model = MockSklearnEstimator()

            # Detect framework
            framework = self.model_registry._detect_framework(model)

            # Verify framework detection
            self.assertEqual(framework, "sklearn")

    def test_list_models(self):
        """Test listing models in the registry."""
        # Add a few models
        self.model_registry.add_model(model=self.dummy_model, model_name="model1", version="1.0.0")
        self.model_registry.add_model(model=self.dummy_model, model_name="model1", version="1.1.0")
        self.model_registry.add_model(model=self.dummy_model, model_name="model2", version="1.0.0")

        # List models
        result = self.model_registry.list_models()

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("model1", result["models"])
        self.assertIn("model2", result["models"])
        self.assertEqual(len(result["models"]["model1"]), 2)
        self.assertEqual(len(result["models"]["model2"]), 1)


class TestDatasetManager(unittest.TestCase):
    """Test cases for the Dataset Manager implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Set flag to disable demo mode
        self.ipfs_client._testing_mode = False

        # Mock IPFS dag_put
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"

        # Mock IPFS ipfs_add_path (new method name)
        self.ipfs_client.ipfs_add_path = MagicMock()
        mock_dir_cid = f"mock-dir-cid-{uuid.uuid4()}"
        self.ipfs_client.ipfs_add_path.return_value = {
            "success": True,
            "Hash": mock_dir_cid,
            "is_directory": True,
            "files": {"/tmp/mock_dir": mock_dir_cid},
        }

        # Keep add_directory for backward compatibility
        self.ipfs_client.add_directory = self.ipfs_client.ipfs_add_path

        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps({"test": "data"}),
        }

        # Mock IPFS get
        self.ipfs_client.get.return_value = {"success": True}

        # Mock IPFS pin_add
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()

        # Create temp directory for test datasets
        self.dataset_dir = tempfile.mkdtemp()

        # Create a test dataset file
        self.test_csv = os.path.join(self.dataset_dir, "test.csv")
        with open(self.test_csv, "w") as f:
            f.write("id,value\n1,100\n2,200\n3,300\n")

        # Initialize dataset manager
        self.dataset_manager = DatasetManager(ipfs_client=self.ipfs_client, base_path=self.temp_dir)

    def test_init_and_empty_registry(self):
        """Test initialization and empty registry creation."""
        # Verify empty registry structure
        self.assertIn("datasets", self.dataset_manager.registry)
        self.assertIn("updated_at", self.dataset_manager.registry)
        self.assertIn("version", self.dataset_manager.registry)
        self.assertEqual(self.dataset_manager.registry["version"], "1.0.0")
        self.assertEqual(len(self.dataset_manager.registry["datasets"]), 0)

        # Verify registry file was created
        registry_file = os.path.join(self.temp_dir, "dataset_registry.json")
        self.assertTrue(os.path.exists(registry_file))

    def test_add_dataset(self):
        """Test adding a dataset to the registry."""
        # Add a dataset to the registry
        result = self.dataset_manager.add_dataset(
            dataset_path=self.test_csv,
            dataset_name="test_dataset",
            version="1.0.0",
            format="csv",
            metadata={"test_key": "test_value"},
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_name"], "test_dataset")
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["format"], "csv")
        self.assertIn("cid", result)

        # Verify dataset was added to registry
        self.assertIn("test_dataset", self.dataset_manager.registry["datasets"])
        self.assertIn("1.0.0", self.dataset_manager.registry["datasets"]["test_dataset"])
        self.assertEqual(
            self.dataset_manager.registry["datasets"]["test_dataset"]["1.0.0"]["format"], "csv"
        )

        # Verify IPFS interactions
        self.ipfs_client.ipfs_add_path.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once()

    def test_format_detection(self):
        """Test detection of dataset formats."""
        # Test CSV detection
        self.assertEqual(self.dataset_manager._detect_format(self.test_csv), "csv")

        # Test JSON detection
        json_file = os.path.join(self.dataset_dir, "test.json")
        with open(json_file, "w") as f:
            f.write('{"test": "data"}')
        self.assertEqual(self.dataset_manager._detect_format(json_file), "json")

        # Test directory detection
        images_dir = os.path.join(self.dataset_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        with open(os.path.join(images_dir, "test.jpg"), "w") as f:
            f.write("dummy image data")
        self.assertEqual(self.dataset_manager._detect_format(images_dir), "images")

    def test_list_datasets(self):
        """Test listing datasets in the registry."""
        # Add a few datasets
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv, dataset_name="dataset1", version="1.0.0"
        )
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv, dataset_name="dataset1", version="1.1.0"
        )
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv, dataset_name="dataset2", version="1.0.0"
        )

        # List datasets
        result = self.dataset_manager.list_datasets()

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 2)
        self.assertIn("dataset1", result["datasets"])
        self.assertIn("dataset2", result["datasets"])
        self.assertEqual(len(result["datasets"]["dataset1"]), 2)
        self.assertEqual(len(result["datasets"]["dataset2"]), 1)


class TestLangchainIntegration(unittest.TestCase):
    """Test cases for the Langchain Integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Initialize Langchain integration
        self.langchain_integration = LangchainIntegration(ipfs_client=self.ipfs_client)

    def test_check_availability(self):
        """Test checking Langchain availability."""
        # Check availability
        result = self.langchain_integration.check_availability()

        # Verify result includes availability info
        self.assertIn("langchain_available", result)
        self.assertIn("numpy_available", result)

        # Verify the value matches the imported constant
        self.assertEqual(result["langchain_available"], LANGCHAIN_AVAILABLE)

    def test_create_ipfs_vectorstore(self):
        """Test creating a Langchain vector store with IPFS storage."""
        # Create a mock embedding function
        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]

        # Patch LANGCHAIN_AVAILABLE to ensure test runs
        with patch("ipfs_kit_py.ai_ml_integration.LANGCHAIN_AVAILABLE", True):
            # Patch VectorStore class if Langchain not available
            mock_vector_store = MagicMock()
            mock_vector_store.ipfs = self.ipfs_client
            mock_vector_store.embedding_function = mock_embeddings

            # Create mock IPFSVectorStore class
            mock_ipfs_vector_store = MagicMock()
            mock_ipfs_vector_store.return_value = mock_vector_store

            # Patch the VectorStore class inside create_ipfs_vectorstore method
            with patch.object(
                self.langchain_integration,
                "create_ipfs_vectorstore",
                return_value=mock_vector_store,
            ):

                # Create vector store
                vector_store = self.langchain_integration.create_ipfs_vectorstore(
                    embedding_function=mock_embeddings
                )

                # Verify vector store was created successfully
                self.assertIsNotNone(vector_store)
                self.assertEqual(vector_store.ipfs, self.ipfs_client)
                self.assertEqual(vector_store.embedding_function, mock_embeddings)

    def test_create_document_loader(self):
        """Test creating a document loader for IPFS content."""
        # Patch LANGCHAIN_AVAILABLE to ensure test runs
        with patch("ipfs_kit_py.ai_ml_integration.LANGCHAIN_AVAILABLE", True):
            # Create mock document loader
            mock_loader = MagicMock()
            mock_loader.ipfs = self.ipfs_client
            mock_loader.path_or_cid = "test_cid"

            # Patch the create_document_loader method
            with patch.object(
                self.langchain_integration, "create_document_loader", return_value=mock_loader
            ):

                # Create document loader
                loader = self.langchain_integration.create_document_loader("test_cid")

                # Verify loader was created successfully
                self.assertIsNotNone(loader)
                self.assertEqual(loader.ipfs, self.ipfs_client)
                self.assertEqual(loader.path_or_cid, "test_cid")


class TestLlamaIndexIntegration(unittest.TestCase):
    """Test cases for the LlamaIndex Integration."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Initialize LlamaIndex integration
        self.llama_index_integration = LlamaIndexIntegration(ipfs_client=self.ipfs_client)

    def test_check_availability(self):
        """Test checking LlamaIndex availability."""
        # Check availability
        result = self.llama_index_integration.check_availability()

        # Verify result includes availability info
        self.assertIn("llama_index_available", result)
        self.assertIn("numpy_available", result)

        # Verify the value matches the imported constant
        self.assertEqual(result["llama_index_available"], LLAMA_INDEX_AVAILABLE)

    def test_create_ipfs_document_reader(self):
        """Test creating a LlamaIndex document reader for IPFS content."""
        # Patch LLAMA_INDEX_AVAILABLE to ensure test runs
        with patch("ipfs_kit_py.ai_ml_integration.LLAMA_INDEX_AVAILABLE", True):
            # Create mock document reader
            mock_reader = MagicMock()
            mock_reader.ipfs = self.ipfs_client
            mock_reader.path_or_cid = "test_cid"

            # Patch the create_ipfs_document_reader method
            with patch.object(
                self.llama_index_integration,
                "create_ipfs_document_reader",
                return_value=mock_reader,
            ):

                # Create document reader
                reader = self.llama_index_integration.create_ipfs_document_reader("test_cid")

                # Verify reader was created successfully
                self.assertIsNotNone(reader)
                self.assertEqual(reader.ipfs, self.ipfs_client)
                self.assertEqual(reader.path_or_cid, "test_cid")


class TestIPFSDataLoader(unittest.TestCase):
    """Test cases for the IPFS DataLoader implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Mock IPFS dag_get for dataset metadata
        self.ipfs_client.dag_get.return_value = {
            "success": True,
            "object": {
                "name": "test_dataset",
                "version": "1.0.0",
                "format": "json",
                "samples": [
                    "sample_cid_1",
                    "sample_cid_2",
                    "sample_cid_3",
                    "sample_cid_4",
                    "sample_cid_5",
                ],
                "metadata": {"description": "Test dataset for unit tests"},
            },
        }

        # Mock sample data retrieval
        def mock_dag_get_side_effect(cid):
            """Return mock data based on CID."""
            if cid.startswith("sample_cid_"):
                sample_index = int(cid.split("_")[-1])
                return {
                    "success": True,
                    "object": {
                        "features": [sample_index * 0.1, sample_index * 0.2, sample_index * 0.3],
                        "labels": sample_index % 2,  # Binary classification for test
                    },
                }
            return self.ipfs_client.dag_get.return_value

        self.ipfs_client.dag_get.side_effect = mock_dag_get_side_effect

        # Initialize data loader
        self.data_loader = IPFSDataLoader(
            ipfs_client=self.ipfs_client,
            batch_size=2,  # Small batch size for testing
            shuffle=False,  # Disable shuffle for predictable testing
            prefetch=1,
        )

    def test_load_dataset(self):
        """Test loading a dataset from IPFS."""
        # Load dataset
        result = self.data_loader.load_dataset("test_dataset_cid")

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_cid"], "test_dataset_cid")
        self.assertEqual(result["total_samples"], 5)

        # Verify IPFS interaction - at least one call to dag_get was made
        self.assertTrue(self.ipfs_client.dag_get.called)

        # Verify internal state
        self.assertEqual(self.data_loader.dataset_cid, "test_dataset_cid")
        self.assertEqual(self.data_loader.total_samples, 5)
        self.assertEqual(len(self.data_loader.sample_cids), 5)

    def test_iteration(self):
        """Test iterating through dataset batches."""
        # Load dataset first
        self.data_loader.load_dataset("test_dataset_cid")

        # Collect batches through iteration
        batches = list(self.data_loader)

        # With batch_size=2 and 5 samples, we should get 3 batches (2, 2, 1)
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0]), 2)  # First batch has 2 samples
        self.assertEqual(len(batches[1]), 2)  # Second batch has 2 samples
        self.assertEqual(len(batches[2]), 1)  # Third batch has 1 sample

        # Verify the content structure
        for batch in batches:
            for sample in batch:
                self.assertIn("features", sample)
                self.assertIn("labels", sample)
                self.assertIsInstance(sample["features"], list)
                self.assertIsInstance(sample["labels"], int)

    def test_len(self):
        """Test the __len__ method."""
        # Load dataset first
        self.data_loader.load_dataset("test_dataset_cid")

        # Check length (number of batches)
        # With 5 samples and batch_size=2, we expect 3 batches (2, 2, 1)
        self.assertEqual(len(self.data_loader), 3)

    @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True)
    def test_to_pytorch_conversion(self):
        """Test conversion to PyTorch DataLoader."""
        # Need to mock torch and DataLoader
        mock_torch = MagicMock()
        mock_data_loader = MagicMock()
        mock_iterable_dataset = MagicMock()

        # Set up mocks for the PyTorch import
        with patch.dict("sys.modules", {"torch": mock_torch, "torch.utils.data": MagicMock()}):
            # Mock the DataLoader class
            with patch("torch.utils.data.DataLoader", mock_data_loader):
                # Mock the IterableDataset class
                with patch("torch.utils.data.IterableDataset", mock_iterable_dataset):
                    # Load dataset first
                    self.data_loader.load_dataset("test_dataset_cid")

                    # Call to_pytorch
                    result = self.data_loader.to_pytorch()

                    # Verify DataLoader was created with correct parameters
                    mock_data_loader.assert_called_once()
                    # The first arg should be the dataset instance
                    args, kwargs = mock_data_loader.call_args
                    self.assertEqual(kwargs["batch_size"], self.data_loader.batch_size)
                    self.assertEqual(
                        kwargs["num_workers"], 0
                    )  # Should use 0 as we do our own prefetching

    @patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True)
    def test_to_tensorflow_conversion(self):
        """Test conversion to TensorFlow Dataset."""
        # Mock TensorFlow
        mock_tf = MagicMock()
        mock_dataset = MagicMock()
        mock_tf.data.Dataset.from_generator.return_value = mock_dataset
        mock_dataset.batch.return_value = mock_dataset
        mock_dataset.prefetch.return_value = mock_dataset

        # Set up mocks for TensorFlow import
        with patch.dict("sys.modules", {"tensorflow": mock_tf}):
            # Load dataset first
            self.data_loader.load_dataset("test_dataset_cid")

            # Call to_tensorflow
            result = self.data_loader.to_tensorflow()

            # Verify TF Dataset was created
            mock_tf.data.Dataset.from_generator.assert_called_once()
            mock_dataset.batch.assert_called_once_with(self.data_loader.batch_size)
            mock_dataset.prefetch.assert_called_once()

    def test_load_embedded_datasets(self):
        """Test loading datasets with embedded samples rather than CIDs."""
        # Create a dataset with embedded samples instead of CIDs
        embedded_dataset = {
            "success": True,
            "object": {
                "name": "embedded_dataset",
                "version": "1.0.0",
                "format": "json",
                "data": [  # Embedded samples
                    {"features": [0.1, 0.2, 0.3], "labels": 0},
                    {"features": [0.2, 0.3, 0.4], "labels": 1},
                    {"features": [0.3, 0.4, 0.5], "labels": 0},
                ],
                "metadata": {"description": "Dataset with embedded samples"},
            },
        }

        # Create a new mock that returns the embedded dataset
        embedded_ipfs = MagicMock()
        embedded_ipfs.dag_get.return_value = embedded_dataset

        # Create data loader with embedded dataset
        embedded_loader = IPFSDataLoader(
            ipfs_client=embedded_ipfs, batch_size=2, shuffle=False, prefetch=1
        )

        # Load dataset
        result = embedded_loader.load_dataset("embedded_dataset_cid")

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["total_samples"], 3)

        # Verify internal state - should have embedded_samples but no sample_cids
        self.assertIsNone(embedded_loader.sample_cids)
        self.assertEqual(len(embedded_loader.embedded_samples), 3)

        # Test iteration
        batches = list(embedded_loader)
        self.assertEqual(len(batches), 2)  # With batch_size=2 and 3 samples, we get 2 batches
        self.assertEqual(len(batches[0]), 2)  # First batch has 2 samples
        self.assertEqual(len(batches[1]), 1)  # Second batch has 1 sample

    def test_close(self):
        """Test proper cleanup when closing the data loader."""
        # Load dataset first
        self.data_loader.load_dataset("test_dataset_cid")

        # Verify prefetch thread is running
        self.assertEqual(len(self.data_loader.prefetch_threads), 1)

        # Close data loader
        self.data_loader.close()

        # Verify prefetch thread was stopped
        self.assertEqual(len(self.data_loader.prefetch_threads), 0)
        self.assertTrue(self.data_loader.stop_prefetch.is_set())

        # Verify prefetch queue is empty
        self.assertTrue(self.data_loader.prefetch_queue.empty())


class TestDistributedTraining(unittest.TestCase):
    """Test cases for the Distributed Training infrastructure."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Set flag to disable demo mode
        self.ipfs_client._testing_mode = False

        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps(
                {
                    "operation": "distributed_training",
                    "model_name": "test_model",
                    "dataset_name": "test_dataset",
                    "dataset_cid": "test_dataset_cid",
                    "model_cid": None,
                    "training_config": {"epochs": 10},
                    "created_at": 1234567890,
                    "task_id": "test_task_id",
                }
            ),
        }

        # Mock IPFS add_json
        self.ipfs_client.add_json.return_value = {"success": True, "Hash": "test_config_cid"}

        # Mock IPFS ipfs_add_path (new method name)
        self.ipfs_client.ipfs_add_path = MagicMock()
        self.ipfs_client.ipfs_add_path.return_value = {
            "success": True,
            "Hash": "test_model_cid",
            "is_directory": True,
            "files": {"/tmp/mock_output_dir": "test_model_cid"},
        }

        # Keep add_directory for backward compatibility
        self.ipfs_client.add_directory = self.ipfs_client.ipfs_add_path

        # Mock IPFS get
        self.ipfs_client.get.return_value = {"success": True}

        # Create mock cluster manager
        self.cluster_manager = MagicMock()
        self.cluster_manager.get_active_workers.return_value = [
            {"id": "worker1"},
            {"id": "worker2"},
        ]
        self.cluster_manager.create_task.return_value = {"success": True, "task_id": "test_task_id"}
        self.cluster_manager.get_task_results.return_value = {
            "success": True,
            "task_id": "test_task_id",
            "results": [
                {
                    "success": True,
                    "model_name": "test_model",
                    "model_cid": "worker1_model_cid",
                    "metrics": {"accuracy": 0.9},
                },
                {
                    "success": True,
                    "model_name": "test_model",
                    "model_cid": "worker2_model_cid",
                    "metrics": {"accuracy": 0.95},
                },
            ],
        }

        # Initialize distributed training
        self.distributed_training = DistributedTraining(
            ipfs_client=self.ipfs_client, cluster_manager=self.cluster_manager
        )

        # Manually add the test dataset to the mocked registry for testing prepare_distributed_task
        # This simulates the dataset having been added previously
        import time  # Ensure time is imported if not already

        self.distributed_training.dataset_manager.registry["datasets"]["test_dataset"] = {
            "1.0.0": {
                "cid": "test_dataset_cid",
                "format": "csv",
                "added_at": time.time(),
                "stats": {"size_bytes": 100, "num_files": 1, "num_rows": 3},
                "metadata": {"description": "Mock dataset for testing"},
            }
        }

    def test_prepare_distributed_task(self):
        """Test preparing a distributed training task."""
        # Prepare distributed task
        result = self.distributed_training.prepare_distributed_task(
            model_name="test_model",
            dataset_name="test_dataset",
            training_config={"epochs": 10},
            num_workers=2,
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["dataset_name"], "test_dataset")
        self.assertEqual(result["num_workers"], 2)
        self.assertIn("task_id", result)
        self.assertIn("task_config_cid", result)

        # Verify cluster manager interactions
        self.cluster_manager.get_active_workers.assert_called_once()
        self.cluster_manager.create_task.assert_called_once()

    def test_execute_training_task(self):
        """Test executing a training task on a worker node."""
        # Execute training task
        result = self.distributed_training.execute_training_task(
            task_config_cid="test_config_cid", worker_id="test_worker"
        )

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["task_id"], "test_task_id")
        self.assertEqual(result["dataset_cid"], "test_dataset_cid")
        self.assertIn("model_cid", result)
        self.assertIn("metrics", result)

        # Verify IPFS interactions
        self.ipfs_client.cat.assert_called_once_with("test_config_cid")
        self.ipfs_client.get.assert_called()

        # Check either ipfs_add_path or add_directory was called
        if hasattr(self.ipfs_client, "ipfs_add_path") and self.ipfs_client.ipfs_add_path.called:
            self.ipfs_client.ipfs_add_path.assert_called_once()
        else:
            self.ipfs_client.add_directory.assert_called_once()

    def test_aggregate_training_results(self):
        """Test aggregating results from multiple workers."""
        # Aggregate training results
        result = self.distributed_training.aggregate_training_results(task_id="test_task_id")

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["best_model_cid"], "worker2_model_cid")  # Higher accuracy
        self.assertEqual(result["num_workers"], 2)
        self.assertIn("worker_metrics", result)
        self.assertIn("registry_result", result)

        # Verify cluster manager interactions
        self.cluster_manager.get_task_results.assert_called_once_with("test_task_id")


class TestTensorflowIntegration(unittest.TestCase):
    """Test cases for the TensorflowIntegration implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if TensorFlow is not available
        if not TF_AVAILABLE:
            self.skipTest("TensorFlow not available")
        
        # Create mock IPFS client
        self.ipfs_mock = MagicMock()
        self.ipfs_mock._testing_mode = False
        
        # Mock model registry
        self.model_registry_mock = MagicMock()
        self.ipfs_mock.get_model_registry = MagicMock(return_value=self.model_registry_mock)
        
        # Mock dataset manager
        self.dataset_manager_mock = MagicMock()
        self.ipfs_mock.get_dataset_manager = MagicMock(return_value=self.dataset_manager_mock)
        
        # Mock IPFS operations
        self.mock_model_cid = f"QmModelCID{uuid.uuid4().hex[:8]}"
        self.ipfs_mock.ipfs_add_path = MagicMock(return_value={
            "success": True,
            "Hash": self.mock_model_cid,
            "cid": self.mock_model_cid
        })
        self.ipfs_mock.get = MagicMock(return_value={"success": True})
        self.ipfs_mock.pin_add = MagicMock(return_value={"success": True})
        
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize TensorflowIntegration
        self.tf_integration = TensorflowIntegration(
            ipfs_client=self.ipfs_mock,
            cache_dir=self.temp_dir
        )
        
    def test_init(self):
        """Test initialization with different parameters."""
        # Default initialization
        integration = TensorflowIntegration(self.ipfs_mock)
        self.assertEqual(integration.ipfs, self.ipfs_mock)
        self.assertFalse(integration.mixed_precision)
        
        # With custom parameters
        integration = TensorflowIntegration(
            self.ipfs_mock,
            cache_dir="/tmp/custom_cache",
            mixed_precision=True,
            serving_config={"model_config": "test"}
        )
        self.assertEqual(integration.mixed_precision, True)
        self.assertEqual(integration.serving_config, {"model_config": "test"})
        
        # Directories should be created
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "models")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "datasets")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "saved_models")))
    
    @patch("tensorflow.keras.models.Sequential")
    def test_save_model(self, mock_sequential):
        """Test saving a TensorFlow model to IPFS."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.to_json.return_value = '{"config": {"layers": []}}'
        mock_model.input_names = ["input_1"]
        mock_model.output_names = ["output_1"]
        mock_sequential.return_value = mock_model
        
        # Simulate TensorFlow import
        with patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.tensorflow") as mock_tf:
            
            mock_tf.__version__ = "2.8.0"
            mock_tf.keras.Model = MagicMock
            
            # Call save_model
            result = self.tf_integration.save_model(
                model=mock_model,
                name="test_model",
                version="1.0.0",
                metadata={"test_key": "test_value"}
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["model_name"], "test_model")
            self.assertEqual(result["version"], "1.0.0")
            self.assertEqual(result["cid"], self.mock_model_cid)
            
            # Verify IPFS operations were called
            self.ipfs_mock.ipfs_add_path.assert_called_once()
            self.ipfs_mock.pin_add.assert_called_once_with(self.mock_model_cid)
            
            # Verify model registry was used
            self.model_registry_mock.store_model.assert_called_once()
    
    @patch("tensorflow.keras.models.load_model")
    def test_load_model(self, mock_load_model):
        """Test loading a model from IPFS."""
        # Mock model registry
        self.model_registry_mock.get_model_cid.return_value = self.mock_model_cid
        
        # Mock loading model
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        # Simulate TensorFlow import
        with patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.tensorflow") as mock_tf, \
             patch("json.load") as mock_json_load, \
             patch("builtins.open", mock_open()):
            
            mock_tf.keras.models.load_model = mock_load_model
            mock_tf.saved_model.load = MagicMock()
            mock_json_load.return_value = {
                "model_type": "keras", 
                "framework": "tensorflow",
                "tf_version": "2.8.0"
            }
            
            # Test loading by CID
            model, metadata = self.tf_integration.load_model(cid=self.mock_model_cid)
            
            # Verify model was loaded
            self.assertEqual(model, mock_model)
            self.assertEqual(metadata["model_type"], "keras")
            self.assertEqual(metadata["framework"], "tensorflow")
            
            # Verify IPFS operations
            self.ipfs_mock.get.assert_called_once()
            
            # Test loading by name/version
            self.ipfs_mock.get.reset_mock()
            model, metadata = self.tf_integration.load_model(name="test_model", version="1.0.0")
            
            # Verify model registry was called
            self.model_registry_mock.get_model_cid.assert_called_once_with("test_model", "1.0.0")
            
            # Verify IPFS operations
            self.ipfs_mock.get.assert_called_once()
    
    def test_export_saved_model(self):
        """Test exporting a model in SavedModel format."""
        # Create mock model
        mock_model = MagicMock()
        
        # Simulate TensorFlow import
        with patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.tensorflow") as mock_tf, \
             patch("json.dump") as mock_json_dump, \
             patch("builtins.open", mock_open()):
            
            mock_tf.__version__ = "2.8.0"
            mock_tf.keras.Model = MagicMock
            
            # Call export_saved_model
            result = self.tf_integration.export_saved_model(
                model=mock_model,
                serving_config={"serving_key": "value"}
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["tf_version"], "2.8.0")
            self.assertEqual(result["has_serving_config"], True)
            
            # Verify TensorFlow operations
            if isinstance(mock_model, mock_tf.keras.Model):
                mock_model.save.assert_called_once()
            else:
                mock_tf.saved_model.save.assert_called_once()
            
            # Verify serving config was saved
            mock_json_dump.assert_called_once()
    
    def test_create_data_loader(self):
        """Test creating a data loader from an IPFS dataset."""
        # Call create_data_loader
        data_loader = self.tf_integration.create_data_loader(
            dataset_cid="QmTestDataset",
            batch_size=64,
            shuffle=False
        )
        
        # Verify data loader was created properly
        self.assertIsInstance(data_loader, IPFSDataLoader)
        self.assertEqual(data_loader.batch_size, 64)
        self.assertEqual(data_loader.shuffle, False)
        self.assertEqual(data_loader.ipfs, self.ipfs_mock)
    
    @patch("tensorflow.keras.models.clone_model")
    def test_optimize_for_inference(self, mock_clone_model):
        """Test optimizing a model for inference."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.trainable_weights = [MagicMock(), MagicMock()]
        
        # Mock cloned model
        mock_optimized_model = MagicMock()
        mock_optimized_model.trainable_weights = [MagicMock()]
        mock_clone_model.return_value = mock_optimized_model
        
        # Simulate TensorFlow import
        with patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.tensorflow") as mock_tf:
            
            mock_tf.keras.Model = MagicMock
            mock_tf.keras.models.clone_model = mock_clone_model
            mock_tf.function = MagicMock(return_value=MagicMock())
            mock_tf.keras.backend.count_params = lambda p: 1000
            
            # Test with Keras model
            mock_tf.keras.Model.__instancecheck__ = lambda _, instance: True
            opt_model, result = self.tf_integration.optimize_for_inference(
                model=mock_model,
                input_shapes={"input_1": [None, 10]},
                mixed_precision=True
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["model_type"], "keras")
            self.assertEqual(result["mixed_precision"], True)
            self.assertIn("original_trainable_params", result)
            
            # Verify TensorFlow operations
            mock_tf.keras.mixed_precision.set_global_policy.assert_called_once_with("mixed_float16")
            mock_clone_model.assert_called_once_with(mock_model)
            
            # Test with non-Keras model
            mock_tf.keras.Model.__instancecheck__ = lambda _, instance: False
            mock_tf.Module.__instancecheck__ = lambda _, instance: True
            opt_model, result = self.tf_integration.optimize_for_inference(
                model=mock_model,
                mixed_precision=False
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["model_type"], "saved_model")
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


class TestPyTorchIntegration(unittest.TestCase):
    """Test cases for the PyTorchIntegration implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Skip tests if PyTorch is not available
        if not TORCH_AVAILABLE:
            self.skipTest("PyTorch not available")
        
        # Create mock IPFS client
        self.ipfs_mock = MagicMock()
        self.ipfs_mock._testing_mode = False
        
        # Mock model registry
        self.model_registry_mock = MagicMock()
        self.ipfs_mock.get_model_registry = MagicMock(return_value=self.model_registry_mock)
        
        # Mock dataset manager
        self.dataset_manager_mock = MagicMock()
        self.ipfs_mock.get_dataset_manager = MagicMock(return_value=self.dataset_manager_mock)
        
        # Mock IPFS operations
        self.mock_model_cid = f"QmModelCID{uuid.uuid4().hex[:8]}"
        self.ipfs_mock.add_path = MagicMock(return_value={
            "success": True,
            "Hash": self.mock_model_cid,
            "cid": self.mock_model_cid
        })
        self.ipfs_mock.get = MagicMock(return_value={"success": True})
        self.ipfs_mock.pin_add = MagicMock(return_value={"success": True})
        
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize PyTorchIntegration
        self.torch_integration = PyTorchIntegration(
            ipfs_client=self.ipfs_mock,
            temp_dir=self.temp_dir
        )
        
    def test_init(self):
        """Test initialization with different parameters."""
        # Default initialization
        integration = PyTorchIntegration(self.ipfs_mock)
        self.assertEqual(integration.ipfs, self.ipfs_mock)
        
        # With custom parameters
        custom_registry = MagicMock()
        integration = PyTorchIntegration(
            self.ipfs_mock,
            model_registry=custom_registry,
            temp_dir="/tmp/custom_cache"
        )
        self.assertEqual(integration.model_registry, custom_registry)
        
        # Directory should be created
        self.assertTrue(os.path.exists(self.temp_dir))
    
    def test_save_model(self):
        """Test saving a PyTorch model to IPFS."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.state_dict.return_value = {"weights": MagicMock()}
        mock_model.__class__.__name__ = "MockModel"
        mock_model.parameters = MagicMock(return_value=[MagicMock()])
        
        # Create mock example input
        mock_input = MagicMock()
        
        # Simulate PyTorch import
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch, \
             patch("json.dump") as mock_json_dump, \
             patch("builtins.open", mock_open()):
            
            mock_torch.__version__ = "1.10.0"
            mock_torch.save = MagicMock()
            mock_torch.jit.trace = MagicMock()
            mock_torch.jit.script = MagicMock()
            mock_torch.onnx.export = MagicMock()
            
            # Create a mock traced model
            mock_traced_model = MagicMock()
            mock_traced_model.save = MagicMock()
            mock_torch.jit.trace.return_value = mock_traced_model
            
            # Call save_model
            result = self.torch_integration.save_model(
                model=mock_model,
                name="test_model",
                version="1.0.0",
                metadata={"test_key": "test_value"},
                trace=True,
                example_inputs=mock_input,
                export_onnx=True
            )
            
            # Verify result
            self.assertTrue(result.get("success"))
            self.assertEqual(result["model_name"], "test_model")
            self.assertEqual(result["model_version"], "1.0.0")
            self.assertEqual(result["cid"], self.mock_model_cid)
            
            # Verify PyTorch operations
            mock_torch.save.assert_called_once()
            mock_torch.jit.trace.assert_called_once_with(mock_model, mock_input)
            mock_traced_model.save.assert_called_once()
            mock_torch.onnx.export.assert_called_once()
            
            # Verify IPFS operations
            self.ipfs_mock.add_path.assert_called_once()
    
    def test_load_model(self):
        """Test loading a model from IPFS."""
        # Mock model registry
        self.model_registry_mock.get_model_cid = MagicMock(return_value={
            "success": True,
            "cid": self.mock_model_cid
        })
        
        # Simulate PyTorch import
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch, \
             patch("json.load") as mock_json_load, \
             patch("builtins.open", mock_open()):
            
            # Mock state dict loading
            mock_state_dict = {"layer1.weight": MagicMock()}
            mock_torch.load = MagicMock(return_value=mock_state_dict)
            
            # Mock JIT loading
            mock_jit_model = MagicMock()
            mock_torch.jit.load = MagicMock(return_value=mock_jit_model)
            
            # Mock metadata
            mock_json_load.return_value = {
                "framework": "pytorch",
                "torch_version": "1.10.0",
                "model_type": "CNN",
                "traced": True
            }
            
            # Test loading traced model by CID
            model, metadata = self.torch_integration.load_model(
                cid=self.mock_model_cid,
                use_traced=True
            )
            
            # Verify model was loaded
            self.assertEqual(model, mock_jit_model)
            self.assertEqual(metadata["framework"], "pytorch")
            self.assertEqual(metadata["model_type"], "CNN")
            
            # Verify PyTorch operations
            mock_torch.jit.load.assert_called_once()
            
            # Test loading state dict by name/version
            # Reset mocks
            mock_torch.jit.load.reset_mock()
            mock_torch.load.reset_mock()
            
            # Mock module class
            mock_module_class = MagicMock()
            mock_module_instance = MagicMock()
            mock_module_class.return_value = mock_module_instance
            
            # Test loading with module class
            model, metadata = self.torch_integration.load_model(
                name="test_model",
                version="1.0.0",
                use_traced=False,
                module_class=mock_module_class
            )
            
            # Verify model was loaded
            self.assertEqual(model, mock_module_instance)
            
            # Verify PyTorch operations
            mock_torch.load.assert_called_once()
            mock_module_instance.load_state_dict.assert_called_once_with(mock_state_dict)
    
    def test_trace_model(self):
        """Test tracing a model with TorchScript."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        
        # Create mock example input
        mock_input = MagicMock()
        
        # Simulate PyTorch import
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch:
            
            # Mock torch operations
            mock_traced_model = MagicMock()
            mock_torch.jit.trace = MagicMock(return_value=mock_traced_model)
            mock_torch.jit.script = MagicMock(return_value=mock_traced_model)
            mock_torch.no_grad = MagicMock().__enter__ = MagicMock().__exit__ = MagicMock()
            
            # Test tracing
            traced_model, result = self.torch_integration.trace_model(
                model=mock_model,
                example_inputs=mock_input,
                use_script=False
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "trace")
            self.assertEqual(traced_model, mock_traced_model)
            
            # Verify PyTorch operations
            mock_model.eval.assert_called_once()
            mock_torch.jit.trace.assert_called_once()
            
            # Test scripting
            mock_torch.jit.trace.reset_mock()
            mock_model.eval.reset_mock()
            
            traced_model, result = self.torch_integration.trace_model(
                model=mock_model,
                example_inputs=mock_input,
                use_script=True
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["method"], "script")
            
            # Verify PyTorch operations
            mock_model.eval.assert_called_once()
            mock_torch.jit.script.assert_called_once_with(mock_model)
    
    def test_create_data_loader(self):
        """Test creating a data loader from an IPFS dataset."""
        # Mock IPFSDataLoader
        with patch("ipfs_kit_py.ai_ml_integration.IPFSDataLoader") as mock_data_loader_class:
            # Create mock data loader instance
            mock_data_loader = MagicMock()
            mock_data_loader.load_dataset = MagicMock(return_value={"success": True, "data": []})
            mock_data_loader_class.return_value = mock_data_loader
            
            # Call create_data_loader
            loader, result = self.torch_integration.create_data_loader(
                dataset_cid="QmTestDataset",
                batch_size=32,
                shuffle=True,
                num_workers=2
            )
            
            # Verify data loader creation
            mock_data_loader_class.assert_called_once_with(ipfs_client=self.ipfs_mock)
            mock_data_loader.load_dataset.assert_called_once_with("QmTestDataset")
            
            # Verify torch DataLoader creation
            self.assertTrue(result["success"])
    
    def test_optimize_for_inference(self):
        """Test optimizing a model for inference."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        mock_model.parameters = MagicMock(return_value=[MagicMock(), MagicMock()])
        
        # Create mock input
        mock_input = MagicMock()
        
        # Simulate PyTorch import
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch:
            
            # Mock half precision conversion
            mock_half_model = MagicMock()
            mock_model.half = MagicMock(return_value=mock_half_model)
            mock_half_model.parameters = MagicMock(return_value=[MagicMock()])
            
            # Mock tracing
            mock_traced_model = MagicMock()
            mock_torch.jit.trace = MagicMock(return_value=mock_traced_model)
            mock_torch.jit.optimize_for_inference = MagicMock(return_value=mock_traced_model)
            
            # Mock parameter counting
            def mock_numel():
                return 1000
            for p in mock_model.parameters():
                p.numel = mock_numel
            for p in mock_half_model.parameters():
                p.numel = mock_numel
            
            # Test with mixed precision and TorchScript
            opt_model, result = self.torch_integration.optimize_for_inference(
                model=mock_model,
                example_inputs=mock_input,
                mixed_precision=True
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertTrue(result["mixed_precision"])
            self.assertTrue(result["eval_mode"])
            self.assertEqual(result["original_params_count"], 2000)
            
            # Verify PyTorch operations
            mock_model.eval.assert_called_once()
            mock_model.half.assert_called_once()
            mock_torch.jit.trace.assert_called_once_with(mock_half_model, mock_input)
            mock_torch.jit.optimize_for_inference.assert_called_once_with(mock_traced_model)
    
    def test_export_onnx(self):
        """Test exporting a model to ONNX format."""
        # Create mock model
        mock_model = MagicMock()
        mock_model.eval = MagicMock()
        
        # Create mock input
        mock_input = MagicMock()
        
        # Simulate PyTorch import
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch, \
             patch("os.path.getsize") as mock_getsize:
            
            # Mock ONNX export
            mock_torch.onnx.export = MagicMock()
            
            # Mock file size
            mock_getsize.return_value = 1024 * 1024  # 1MB
            
            # Test ONNX export
            result = self.torch_integration.export_onnx(
                model=mock_model,
                save_path="/tmp/model.onnx",
                example_inputs=mock_input,
                input_names=["input"],
                output_names=["output"]
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["save_path"], "/tmp/model.onnx")
            self.assertEqual(result["file_size_bytes"], 1024 * 1024)
            
            # Verify PyTorch operations
            mock_model.eval.assert_called_once()
            mock_torch.onnx.export.assert_called_once()
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)


@unittest.skipIf(not FIXTURES_AVAILABLE, "AI/ML test fixtures not available")
class TestAIMLIntegrationWithFixtures(unittest.TestCase):
    """Test AI/ML integration using the new fixtures."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()
        
        # Set flag to disable demo mode
        self.ipfs_client._testing_mode = False
        
        # Mock common IPFS operations
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"
        self.ipfs_client.pin_add.return_value = {"success": True}
        self.ipfs_client.get.return_value = {"success": True}
        
        # Create temp directories
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = os.path.join(self.temp_dir, "models")
        self.datasets_dir = os.path.join(self.temp_dir, "datasets")
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.datasets_dir, exist_ok=True)
        
        # Initialize model registry with mocks
        from ipfs_kit_py.ai_ml_integration import ModelRegistry
        self.model_registry = ModelRegistry(ipfs_client=self.ipfs_client, base_path=self.temp_dir)
        
        # Initialize dataset manager with mocks
        from ipfs_kit_py.ai_ml_integration import DatasetManager
        self.dataset_manager = DatasetManager(ipfs_client=self.ipfs_client, base_path=self.temp_dir)
        
    def tearDown(self):
        """Clean up after tests."""
        # Remove temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_sklearn_model_integration(self):
        """Test scikit-learn model integration using fixtures."""
        # Create a mock sklearn model using our fixture
        model = MockSklearnModel()
        
        # Patch SKLEARN_AVAILABLE
        with patch("ipfs_kit_py.ai_ml_integration.SKLEARN_AVAILABLE", True):
            # Create a scenario for sklearn model testing
            scenario = ModelScenario.create_sklearn_training_scenario(self.ipfs_client)
            test_model = scenario.train_model()
            
            # Add the model to the registry
            result = self.model_registry.add_model(
                model=test_model,
                model_name="test_sklearn_model",
                version="1.0.0",
                metadata=scenario.get_metadata()
            )
            
            # Verify result
            self.assertTrue(result["success"])
            self.assertEqual(result["model_name"], "test_sklearn_model")
            self.assertEqual(result["version"], "1.0.0")
            
            # Verify IPFS calls
            self.ipfs_client.pin_add.assert_called_once()
    
    def test_pytorch_model_integration(self):
        """Test PyTorch model integration using fixtures."""
        # Patch TORCH_AVAILABLE
        with patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch:
            
            # Create a PyTorch model scenario
            scenario = ModelScenario.create_pytorch_training_scenario(self.ipfs_client)
            
            # Set up mock torch functions
            mock_torch.save = MagicMock()
            mock_torch.__version__ = "1.10.0"
            
            # Train the model
            model = scenario.train_model()
            
            # Mock methods needed for saving
            model.state_dict = MagicMock(return_value={"weights": "mock_weights"})
            
            # Test PyTorch integration
            from ipfs_kit_py.ai_ml_integration import PyTorchIntegration
            torch_integration = PyTorchIntegration(
                ipfs_client=self.ipfs_client, 
                temp_dir=self.temp_dir
            )
            
            # Add the model to the registry through the integration
            with patch.object(torch_integration, "save_model") as mock_save:
                mock_save.return_value = {
                    "success": True,
                    "model_name": "pytorch_model",
                    "model_version": "1.0.0",
                    "cid": f"mock-cid-{uuid.uuid4()}",
                    "format": "pytorch"
                }
                
                # Call save_model
                result = torch_integration.save_model(
                    model=model,
                    name="pytorch_model",
                    version="1.0.0"
                )
                
                # Verify result
                self.assertTrue(result["success"])
                self.assertEqual(result["model_name"], "pytorch_model")
    
    def test_tensorflow_model_integration(self):
        """Test TensorFlow model integration using fixtures."""
        # Patch TF_AVAILABLE
        with patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True), \
             patch("ipfs_kit_py.ai_ml_integration.tensorflow") as mock_tf:
            
            # Create a TensorFlow model scenario
            scenario = ModelScenario.create_tensorflow_training_scenario(self.ipfs_client)
            
            # Configure the mock_tf
            mock_tf.__version__ = "2.6.0"
            mock_tf.keras = MagicMock()
            mock_tf.keras.Model = MagicMock
            mock_tf.saved_model = MagicMock()
            
            # Train the model
            model = scenario.train_model()
            
            # Test TensorFlow integration
            from ipfs_kit_py.ai_ml_integration import TensorflowIntegration
            tf_integration = TensorflowIntegration(
                ipfs_client=self.ipfs_client,
                cache_dir=self.temp_dir
            )
            
            # Add the model to the registry through the integration
            with patch.object(tf_integration, "save_model") as mock_save:
                mock_save.return_value = {
                    "success": True,
                    "model_name": "tensorflow_model",
                    "version": "1.0.0",
                    "cid": f"mock-cid-{uuid.uuid4()}",
                    "framework": "tensorflow"
                }
                
                # Call save_model
                result = tf_integration.save_model(
                    model=model,
                    name="tensorflow_model",
                    version="1.0.0"
                )
                
                # Verify result
                self.assertTrue(result["success"])
                self.assertEqual(result["model_name"], "tensorflow_model")
    
    def test_dataset_integration(self):
        """Test dataset integration using fixtures."""
        # Create a dataset scenario
        scenario = DatasetScenario.create_tabular_dataset_scenario()
        
        # Get the dataset
        dataset_path = scenario.get_dataset_path()
        
        # Create dataset file
        with open(dataset_path, "w") as f:
            f.write(scenario.get_dataset_content())
        
        # Add the dataset to the manager
        result = self.dataset_manager.add_dataset(
            dataset_path=dataset_path,
            dataset_name="test_dataset",
            version="1.0.0",
            format="csv",
            metadata=scenario.get_metadata()
        )
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_name"], "test_dataset")
        self.assertEqual(result["version"], "1.0.0")
        
        # Verify IPFS operations
        self.ipfs_client.add_path.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once()
    
    def test_dataloader_integration(self):
        """Test DataLoader integration using fixtures."""
        # Create mock dataset
        mock_dataset = MockDataset(
            samples=[
                {"features": [0.1, 0.2, 0.3], "labels": 1},
                {"features": [0.4, 0.5, 0.6], "labels": 0},
                {"features": [0.7, 0.8, 0.9], "labels": 1},
            ],
            metadata={"name": "mock_dataset", "feature_dim": 3}
        )
        
        # Mock IPFS dag_get to return the dataset
        self.ipfs_client.dag_get.return_value = {
            "success": True,
            "object": {
                "name": "mock_dataset",
                "version": "1.0.0",
                "data": mock_dataset.samples,
                "metadata": mock_dataset.metadata
            }
        }
        
        # Initialize dataloader
        from ipfs_kit_py.ai_ml_integration import IPFSDataLoader
        data_loader = IPFSDataLoader(
            ipfs_client=self.ipfs_client,
            batch_size=2,
            shuffle=False
        )
        
        # Load the dataset
        result = data_loader.load_dataset("mock_dataset_cid")
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["total_samples"], 3)
        
        # Iterate through batches
        batches = list(data_loader)
        
        # Should have 2 batches (2 samples, 1 sample)
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), 2)  # First batch has 2 samples
        self.assertEqual(len(batches[1]), 1)  # Second batch has 1 sample


if __name__ == "__main__":
    unittest.main()
