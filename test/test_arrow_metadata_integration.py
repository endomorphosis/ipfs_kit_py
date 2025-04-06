"""
Test suite for the integration between Arrow metadata index and AI/ML components.

This module tests the integration between the Arrow metadata index and the AI/ML
components, verifying the registration of models and datasets with the metadata index
and the efficient querying capabilities provided by this integration.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.ai_ml_integration import (
    DatasetManager,
    ModelRegistry,
)

# Mock the availability of PyArrow for testing
MOCK_ARROW_AVAILABLE = True


class TestModelRegistryMetadataIndexIntegration(unittest.TestCase):
    """Test cases for the integration between ModelRegistry and Arrow metadata index."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Mock IPFS operations
        self.ipfs_client.dag_put.side_effect = lambda data: {
            "success": True,
            "cid": f"mock-cid-{data.get('name', 'test')}",
        }
        # Explicitly mock ipfs_add_path to return a dict with a string CID
        self.ipfs_client.ipfs_add_path.return_value = {"success": True, "cid": "mock-dir-cid"}
        # Also mock add_directory for consistency if it's used elsewhere
        self.ipfs_client.add_directory.return_value = {"success": True, "Hash": "mock-dir-cid"}
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Create a mock metadata index
        self.mock_metadata_index = MagicMock()
        self.mock_metadata_index.add.return_value = {"success": True, "cid": "mock-registered-cid"}

        # Attach metadata index to IPFS client
        self.ipfs_client.metadata_index = self.mock_metadata_index

        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()

        # Initialize model registry
        self.model_registry = ModelRegistry(ipfs_client=self.ipfs_client, base_path=self.temp_dir)

    def test_model_registration_with_metadata_index(self):
        """Test that models are properly registered with the metadata index."""
        # Create a dummy model
        dummy_model = {"type": "dummy_model", "params": {"layers": 2}}

        # Mock framework detection
        with patch.object(self.model_registry, "_detect_framework", return_value="sklearn"):
            # Add model to registry
            result = self.model_registry.add_model(
                model=dummy_model,
                model_name="test_model",
                version="1.0.0",
                metadata={"accuracy": 0.95, "tags": ["classification", "test"]},
            )

        # Verify the model was added successfully using attribute access
        self.assertTrue(result.success)
        self.assertEqual(result.model_name, "test_model")
        # Check that the CID returned is the mocked string CID
        self.assertEqual(result.cid, "mock-dir-cid")

        # Verify the metadata index was called with appropriate parameters
        self.mock_metadata_index.add.assert_called_once()

        # Get the call arguments
        call_args = self.mock_metadata_index.add.call_args[0][0]

        # Verify the metadata record structure
        self.assertEqual(call_args["cid"], "mock-dir-cid")
        self.assertEqual(call_args["mime_type"], "application/x-ml-model")
        self.assertEqual(call_args["filename"], "test_model_1.0.0")
        self.assertEqual(call_args["path"], "/ipfs/mock-dir-cid")

        # Verify tags
        self.assertIn("sklearn", call_args["tags"])
        self.assertIn("model", call_args["tags"])
        self.assertIn("test_model", call_args["tags"])

        # Verify properties
        self.assertEqual(call_args["properties"]["model_name"], "test_model")
        self.assertEqual(call_args["properties"]["model_version"], "1.0.0")
        self.assertEqual(call_args["properties"]["framework"], "sklearn")
        self.assertEqual(call_args["properties"]["type"], "ml_model")
        self.assertEqual(call_args["properties"]["accuracy"], "0.95")


class TestDatasetManagerMetadataIndexIntegration(unittest.TestCase):
    """Test cases for the integration between DatasetManager and Arrow metadata index."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()

        # Mock IPFS operations
        self.ipfs_client.dag_put.side_effect = lambda data: {
            "success": True,
            "cid": f"mock-cid-{data.get('name', 'test')}",
        }
        # Explicitly mock ipfs_add_path for dataset manager
        self.ipfs_client.ipfs_add_path.return_value = {"success": True, "cid": "mock-dataset-cid"}
        self.ipfs_client.add_directory.return_value = {"success": True, "Hash": "mock-dataset-cid"}
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Create a mock metadata index
        self.mock_metadata_index = MagicMock()
        self.mock_metadata_index.add.return_value = {"success": True, "cid": "mock-registered-cid"}

        # Attach metadata index to IPFS client
        self.ipfs_client.metadata_index = self.mock_metadata_index

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

    def test_dataset_registration_with_metadata_index(self):
        """Test that datasets are properly registered with the metadata index."""
        # Mock format detection
        with patch.object(self.dataset_manager, "_detect_format", return_value="csv"):
            # Mock dataset stats generation
            with patch.object(
                self.dataset_manager,
                "_generate_dataset_stats",
                return_value={"size_bytes": 1024, "num_files": 1, "num_rows": 3},
            ):
                # Add dataset to registry
                result = self.dataset_manager.add_dataset(
                    dataset_path=self.test_csv,
                    dataset_name="test_dataset",
                    version="1.0.0",
                    metadata={"description": "Test dataset", "tags": ["tabular", "test"]},
                )

        # Verify the dataset was added successfully using attribute access
        self.assertTrue(result.success)
        self.assertEqual(result.dataset_name, "test_dataset")
        # Check that the CID returned is the mocked string CID
        self.assertEqual(result.cid, "mock-dataset-cid")

        # Verify the metadata index was called with appropriate parameters
        self.mock_metadata_index.add.assert_called_once()

        # Get the call arguments
        call_args = self.mock_metadata_index.add.call_args[0][0]

        # Verify the metadata record structure
        self.assertEqual(call_args["cid"], "mock-dataset-cid")
        self.assertEqual(call_args["mime_type"], "text/csv")
        self.assertEqual(call_args["filename"], "test_dataset_1.0.0")
        self.assertEqual(call_args["path"], "/ipfs/mock-dataset-cid")
        self.assertEqual(call_args["size_bytes"], 1024)

        # Verify tags
        self.assertIn("csv", call_args["tags"])
        self.assertIn("dataset", call_args["tags"])
        self.assertIn("test_dataset", call_args["tags"])

        # Verify properties
        self.assertEqual(call_args["properties"]["dataset_name"], "test_dataset")
        self.assertEqual(call_args["properties"]["dataset_version"], "1.0.0")
        self.assertEqual(call_args["properties"]["format"], "csv")
        self.assertEqual(call_args["properties"]["type"], "dataset")
        self.assertEqual(call_args["properties"]["num_rows"], "3")
        self.assertEqual(call_args["properties"]["num_files"], "1")
        self.assertEqual(call_args["properties"]["description"], "Test dataset")


class TestMetadataIndexFallbackBehavior(unittest.TestCase):
    """Test that components gracefully handle missing metadata index."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client with no metadata index
        self.ipfs_client = MagicMock()

        # Ensure metadata_index is None
        self.ipfs_client.metadata_index = None

        # Mock IPFS operations
        self.ipfs_client.dag_put.side_effect = lambda data: {
            "success": True,
            "cid": f"mock-cid-{data.get('name', 'test')}",
        }
        # Mock ipfs_add_path to return a string CID even without metadata index
        self.ipfs_client.ipfs_add_path.return_value = {"success": True, "cid": "mock-dir-cid-fallback"}
        self.ipfs_client.add_directory.return_value = {"success": True, "Hash": "mock-dir-cid-fallback"}
        self.ipfs_client.pin_add.return_value = {"success": True}

        # Create temp directory for registry storage
        self.temp_dir = tempfile.mkdtemp()

        # Initialize model registry and dataset manager
        self.model_registry = ModelRegistry(ipfs_client=self.ipfs_client, base_path=self.temp_dir)
        self.dataset_manager = DatasetManager(ipfs_client=self.ipfs_client, base_path=self.temp_dir)

    def test_model_registry_functions_without_metadata_index(self):
        """Test that ModelRegistry works correctly when metadata_index is not available."""
        # Create a dummy model
        dummy_model = {"type": "dummy_model", "params": {"layers": 2}}

        # Add model to registry
        result = self.model_registry.add_model(
            model=dummy_model, model_name="test_model", version="1.0.0"
        )

        # Verify model was added successfully using attribute access
        self.assertTrue(result.success)
        self.assertEqual(result.model_name, "test_model")
        # Check CID is the fallback string CID
        self.assertEqual(result.cid, "mock-dir-cid-fallback")

        # Create a test dataset file
        test_csv = os.path.join(self.temp_dir, "test.csv")
        with open(test_csv, "w") as f:
            f.write("id,value\n1,100\n2,200\n3,300\n")

    def test_dataset_manager_functions_without_metadata_index(self):
        """Test that DatasetManager works correctly when metadata_index is not available."""
        # Create a test dataset file
        test_csv = os.path.join(self.temp_dir, "test.csv")
        with open(test_csv, "w") as f:
            f.write("id,value\n1,100\n2,200\n3,300\n")

        # Mock dataset stats generation to avoid real file operations
        with patch.object(
            self.dataset_manager,
            "_generate_dataset_stats",
            return_value={"size_bytes": 1024, "num_files": 1, "num_rows": 3},
        ):
            # Add dataset to registry
            result = self.dataset_manager.add_dataset(
                dataset_path=test_csv, dataset_name="test_dataset", version="1.0.0"
            )

        # Verify dataset was added successfully using attribute access
        self.assertTrue(result.success)
        self.assertEqual(result.dataset_name, "test_dataset")
        # Check CID is the fallback string CID
        self.assertEqual(result.cid, "mock-dir-cid-fallback") # Assuming dataset manager also uses ipfs_add_path


if __name__ == "__main__":
    unittest.main()
