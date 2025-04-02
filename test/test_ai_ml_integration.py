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

import unittest
import os
import sys
import json
import tempfile
import uuid
import pickle
from unittest.mock import patch, MagicMock

# Add parent directory to path to import from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.ai_ml_integration import (
    ModelRegistry,
    DatasetManager,
    LangchainIntegration,
    LlamaIndexIntegration,
    DistributedTraining,
    LANGCHAIN_AVAILABLE,
    LLAMA_INDEX_AVAILABLE,
    SKLEARN_AVAILABLE,
    TORCH_AVAILABLE,
    TF_AVAILABLE
)


class TestModelRegistry(unittest.TestCase):
    """Test cases for the Model Registry implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()
        
        # Mock IPFS dag_put
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"
        
        # Mock IPFS add_directory
        self.ipfs_client.add_directory.return_value = {
            "success": True,
            "Hash": f"mock-dir-cid-{uuid.uuid4()}"
        }
        
        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps({"test": "data"})
        }
        
        # Mock IPFS get
        self.ipfs_client.get.return_value = {
            "success": True
        }
        
        # Mock IPFS pin_add
        self.ipfs_client.pin_add.return_value = {
            "success": True
        }
        
        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize model registry
        self.model_registry = ModelRegistry(
            ipfs_client=self.ipfs_client,
            base_path=self.temp_dir
        )
        
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
            metadata={"test_key": "test_value"}
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
            "test_framework"
        )
        
        # Verify IPFS interactions
        self.ipfs_client.add_directory.assert_called_once()
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
        self.model_registry.add_model(
            model=self.dummy_model,
            model_name="model1",
            version="1.0.0"
        )
        self.model_registry.add_model(
            model=self.dummy_model,
            model_name="model1",
            version="1.1.0"
        )
        self.model_registry.add_model(
            model=self.dummy_model,
            model_name="model2",
            version="1.0.0"
        )
        
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
        
        # Mock IPFS dag_put
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"
        
        # Mock IPFS add_directory
        self.ipfs_client.add_directory.return_value = {
            "success": True,
            "Hash": f"mock-dir-cid-{uuid.uuid4()}"
        }
        
        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps({"test": "data"})
        }
        
        # Mock IPFS get
        self.ipfs_client.get.return_value = {
            "success": True
        }
        
        # Mock IPFS pin_add
        self.ipfs_client.pin_add.return_value = {
            "success": True
        }
        
        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()
        
        # Create temp directory for test datasets
        self.dataset_dir = tempfile.mkdtemp()
        
        # Create a test dataset file
        self.test_csv = os.path.join(self.dataset_dir, "test.csv")
        with open(self.test_csv, 'w') as f:
            f.write("id,value\n1,100\n2,200\n3,300\n")
        
        # Initialize dataset manager
        self.dataset_manager = DatasetManager(
            ipfs_client=self.ipfs_client,
            base_path=self.temp_dir
        )
    
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
            metadata={"test_key": "test_value"}
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
            self.dataset_manager.registry["datasets"]["test_dataset"]["1.0.0"]["format"],
            "csv"
        )
        
        # Verify IPFS interactions
        self.ipfs_client.add_directory.assert_called_once()
        self.ipfs_client.pin_add.assert_called_once()
    
    def test_format_detection(self):
        """Test detection of dataset formats."""
        # Test CSV detection
        self.assertEqual(self.dataset_manager._detect_format(self.test_csv), "csv")
        
        # Test JSON detection
        json_file = os.path.join(self.dataset_dir, "test.json")
        with open(json_file, 'w') as f:
            f.write('{"test": "data"}')
        self.assertEqual(self.dataset_manager._detect_format(json_file), "json")
        
        # Test directory detection
        images_dir = os.path.join(self.dataset_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        with open(os.path.join(images_dir, "test.jpg"), 'w') as f:
            f.write("dummy image data")
        self.assertEqual(self.dataset_manager._detect_format(images_dir), "images")
    
    def test_list_datasets(self):
        """Test listing datasets in the registry."""
        # Add a few datasets
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv,
            dataset_name="dataset1",
            version="1.0.0"
        )
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv,
            dataset_name="dataset1",
            version="1.1.0"
        )
        self.dataset_manager.add_dataset(
            dataset_path=self.test_csv,
            dataset_name="dataset2",
            version="1.0.0"
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
        self.langchain_integration = LangchainIntegration(
            ipfs_client=self.ipfs_client
        )
    
    def test_check_availability(self):
        """Test checking Langchain availability."""
        # Check availability
        result = self.langchain_integration.check_availability()
        
        # Verify result includes availability info
        self.assertIn("langchain_available", result)
        self.assertIn("numpy_available", result)
        
        # Verify the value matches the imported constant
        self.assertEqual(result["langchain_available"], LANGCHAIN_AVAILABLE)
    
    @unittest.skipIf(not LANGCHAIN_AVAILABLE, "Langchain not available")
    def test_create_ipfs_vectorstore(self):
        """Test creating a Langchain vector store with IPFS storage."""
        # Create a mock embedding function
        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.return_value = [[0.1, 0.2, 0.3]]
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        
        # Create vector store
        vector_store = self.langchain_integration.create_ipfs_vectorstore(
            embedding_function=mock_embeddings
        )
        
        # Verify vector store was created successfully if Langchain is available
        self.assertIsNotNone(vector_store)
        self.assertEqual(vector_store.ipfs, self.ipfs_client)
        self.assertEqual(vector_store.embedding_function, mock_embeddings)
    
    @unittest.skipIf(not LANGCHAIN_AVAILABLE, "Langchain not available")
    def test_create_document_loader(self):
        """Test creating a document loader for IPFS content."""
        # Create document loader
        loader = self.langchain_integration.create_document_loader("test_cid")
        
        # Verify loader was created successfully if Langchain is available
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
        self.llama_index_integration = LlamaIndexIntegration(
            ipfs_client=self.ipfs_client
        )
    
    def test_check_availability(self):
        """Test checking LlamaIndex availability."""
        # Check availability
        result = self.llama_index_integration.check_availability()
        
        # Verify result includes availability info
        self.assertIn("llama_index_available", result)
        self.assertIn("numpy_available", result)
        
        # Verify the value matches the imported constant
        self.assertEqual(result["llama_index_available"], LLAMA_INDEX_AVAILABLE)
    
    @unittest.skipIf(not LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_create_ipfs_document_reader(self):
        """Test creating a LlamaIndex document reader for IPFS content."""
        # Create document reader
        reader = self.llama_index_integration.create_ipfs_document_reader("test_cid")
        
        # Verify reader was created successfully if LlamaIndex is available
        self.assertIsNotNone(reader)
        self.assertEqual(reader.ipfs, self.ipfs_client)
        self.assertEqual(reader.path_or_cid, "test_cid")


class TestDistributedTraining(unittest.TestCase):
    """Test cases for the Distributed Training infrastructure."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()
        
        # Mock IPFS cat
        self.ipfs_client.cat.return_value = {
            "success": True,
            "content": json.dumps({
                "operation": "distributed_training",
                "model_name": "test_model",
                "dataset_name": "test_dataset",
                "dataset_cid": "test_dataset_cid",
                "model_cid": None,
                "training_config": {"epochs": 10},
                "created_at": 1234567890,
                "task_id": "test_task_id"
            })
        }
        
        # Mock IPFS add_json
        self.ipfs_client.add_json.return_value = {
            "success": True,
            "Hash": "test_config_cid"
        }
        
        # Mock IPFS add_directory
        self.ipfs_client.add_directory.return_value = {
            "success": True,
            "Hash": "test_model_cid"
        }
        
        # Mock IPFS get
        self.ipfs_client.get.return_value = {
            "success": True
        }
        
        # Create mock cluster manager
        self.cluster_manager = MagicMock()
        self.cluster_manager.get_active_workers.return_value = [
            {"id": "worker1"},
            {"id": "worker2"}
        ]
        self.cluster_manager.create_task.return_value = {
            "success": True,
            "task_id": "test_task_id"
        }
        self.cluster_manager.get_task_results.return_value = {
            "success": True,
            "task_id": "test_task_id",
            "results": [
                {
                    "success": True,
                    "model_name": "test_model",
                    "model_cid": "worker1_model_cid",
                    "metrics": {"accuracy": 0.9}
                },
                {
                    "success": True,
                    "model_name": "test_model",
                    "model_cid": "worker2_model_cid",
                    "metrics": {"accuracy": 0.95}
                }
            ]
        }
        
        # Initialize distributed training
        self.distributed_training = DistributedTraining(
            ipfs_client=self.ipfs_client,
            cluster_manager=self.cluster_manager
        )

        # Manually add the test dataset to the mocked registry for testing prepare_distributed_task
        # This simulates the dataset having been added previously
        import time # Ensure time is imported if not already
        self.distributed_training.dataset_manager.registry["datasets"]["test_dataset"] = {
            "1.0.0": {
                "cid": "test_dataset_cid",
                "format": "csv",
                "added_at": time.time(),
                "stats": {"size_bytes": 100, "num_files": 1, "num_rows": 3},
                "metadata": {"description": "Mock dataset for testing"}
            }
        }
    
    def test_prepare_distributed_task(self):
        """Test preparing a distributed training task."""
        # Prepare distributed task
        result = self.distributed_training.prepare_distributed_task(
            model_name="test_model",
            dataset_name="test_dataset",
            training_config={"epochs": 10},
            num_workers=2
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
            task_config_cid="test_config_cid",
            worker_id="test_worker"
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
        self.ipfs_client.add_directory.assert_called_once()
    
    def test_aggregate_training_results(self):
        """Test aggregating results from multiple workers."""
        # Aggregate training results
        result = self.distributed_training.aggregate_training_results(
            task_id="test_task_id"
        )
        
        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["model_name"], "test_model")
        self.assertEqual(result["best_model_cid"], "worker2_model_cid")  # Higher accuracy
        self.assertEqual(result["num_workers"], 2)
        self.assertIn("worker_metrics", result)
        self.assertIn("registry_result", result)
        
        # Verify cluster manager interactions
        self.cluster_manager.get_task_results.assert_called_once_with("test_task_id")


if __name__ == '__main__':
    unittest.main()
