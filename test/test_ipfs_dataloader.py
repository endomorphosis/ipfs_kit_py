"""
Tests for the IPFSDataLoader implementation.

This module tests the IPFSDataLoader class, which provides efficient data loading
capabilities for machine learning workloads using IPFS content-addressed storage.
"""

import unittest
import json
import tempfile
import os
import time
import sys
import queue
from unittest.mock import MagicMock, patch

# Import IPFS Kit components
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.ai_ml_integration import IPFSDataLoader, ipfs_data_loader_context


class TestIPFSDataLoader(unittest.TestCase):
    """Test suite for IPFSDataLoader."""

    def setUp(self):
        """Set up test environment."""
        # Mock IPFS client
        self.ipfs_mock = MagicMock()

        # Sample dataset metadata
        self.dataset_metadata = {
            "name": "test_dataset",
            "description": "Test dataset for unit tests",
            "version": "1.0.0",
            "created_at": time.time(),
            "samples": [
                "QmSample1", "QmSample2", "QmSample3", "QmSample4",
                "QmSample5", "QmSample6", "QmSample7", "QmSample8"
            ]
        }

        # Sample dataset with embedded data
        self.embedded_dataset = {
            "name": "embedded_dataset",
            "description": "Test dataset with embedded data",
            "version": "1.0.0",
            "created_at": time.time(),
            "data": [
                {"features": [1, 2, 3], "labels": 0},
                {"features": [4, 5, 6], "labels": 1},
                {"features": [7, 8, 9], "labels": 0},
                {"features": [10, 11, 12], "labels": 1}
            ]
        }
        
        # Sample multimodal dataset
        self.multimodal_dataset = {
            "name": "multimodal_dataset",
            "description": "Test dataset with multimodal data",
            "version": "1.0.0",
            "created_at": time.time(),
            "samples": [
                {
                    "id": "sample001",
                    "image_cid": "QmImageCID1",
                    "text": "Sample text description for image 1",
                    "tabular_features": [0.1, 0.2, 0.3],
                    "label": 1
                },
                {
                    "id": "sample002",
                    "image_cid": "QmImageCID2",
                    "text": "Sample text description for image 2",
                    "tabular_features": [0.4, 0.5, 0.6],
                    "label": 0
                }
            ]
        }

        # Create mock samples
        self.samples = [
            {"features": [1, 2, 3], "labels": 0},
            {"features": [4, 5, 6], "labels": 1},
            {"features": [7, 8, 9], "labels": 0},
            {"features": [10, 11, 12], "labels": 1},
            {"features": [13, 14, 15], "labels": 0},
            {"features": [16, 17, 18], "labels": 1},
            {"features": [19, 20, 21], "labels": 0},
            {"features": [22, 23, 24], "labels": 1}
        ]

        # Configure mocks
        self.setup_mocks()

    def setup_mocks(self):
        """Set up mock responses for IPFS operations."""
        # Mock successful dag_get for dataset metadata
        self.ipfs_mock.dag_get.return_value = {
            "success": True,
            "operation": "dag_get",
            "object": self.dataset_metadata
        }
        
        # Mock IPFS cat for image loading
        self.ipfs_mock.cat.return_value = b"mock_image_data"

        # Mock sample retrieval - different response for each sample CID
        def mock_dag_get(cid, **kwargs):
            if cid == "QmDatasetCID":
                return {
                    "success": True,
                    "operation": "dag_get",
                    "object": self.dataset_metadata
                }
            elif cid == "QmEmbeddedDatasetCID":
                return {
                    "success": True,
                    "operation": "dag_get",
                    "object": self.embedded_dataset
                }
            elif cid == "QmMultimodalDatasetCID":
                return {
                    "success": True,
                    "operation": "dag_get",
                    "object": self.multimodal_dataset
                }
            elif cid.startswith("QmSample"):
                # Extract index from sample name
                idx = int(cid[8:]) - 1
                if 0 <= idx < len(self.samples):
                    return {
                        "success": True,
                        "operation": "dag_get",
                        "object": self.samples[idx]
                    }
            elif cid.startswith("QmImageCID"):
                return {
                    "success": True,
                    "operation": "dag_get",
                    "object": {
                        "data": "mock_image_data_base64"
                    }
                }

            return {
                "success": False,
                "operation": "dag_get",
                "error": f"Content not found: {cid}"
            }

        self.ipfs_mock.dag_get.side_effect = mock_dag_get
        
        # Add a logger to the mock IPFS client
        self.ipfs_mock.logger = MagicMock()

    def test_dataloader_init(self):
        """Test IPFSDataLoader initialization."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4, shuffle=True, prefetch=2)

        self.assertEqual(loader.batch_size, 4)
        self.assertEqual(loader.shuffle, True)
        self.assertEqual(loader.prefetch, 2)
        self.assertEqual(loader.total_samples, 0)
        
        # Test metrics initialization
        self.assertIn("batch_times", loader.performance_metrics)
        self.assertIn("cache_hits", loader.performance_metrics)
        self.assertIn("cache_misses", loader.performance_metrics)

    def test_load_dataset(self):
        """Test loading a dataset by CID."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)

        # Load dataset
        result = loader.load_dataset("QmDatasetCID")

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(loader.total_samples, 8)
        self.assertEqual(loader.dataset_cid, "QmDatasetCID")
        self.assertEqual(len(loader.sample_cids), 8)
        
        # Verify dataset metadata was loaded
        self.assertEqual(loader.dataset_metadata["name"], "test_dataset")
        self.assertEqual(loader.dataset_metadata["version"], "1.0.0")

    def test_load_embedded_dataset(self):
        """Test loading a dataset with embedded data."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=2)

        # Load embedded dataset
        result = loader.load_dataset("QmEmbeddedDatasetCID")

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(loader.total_samples, 4)
        self.assertIsNone(loader.sample_cids)
        self.assertEqual(len(loader.embedded_samples), 4)
        
        # Verify embedded samples were loaded correctly
        self.assertEqual(loader.embedded_samples[0]["features"], [1, 2, 3])
        self.assertEqual(loader.embedded_samples[0]["labels"], 0)

    def test_load_multimodal_dataset(self):
        """Test loading a multimodal dataset."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=1)

        # Load multimodal dataset
        result = loader.load_dataset("QmMultimodalDatasetCID")

        # Assertions
        self.assertTrue(result["success"])
        self.assertEqual(loader.total_samples, 2)
        self.assertIsNone(loader.sample_cids)
        self.assertEqual(len(loader.embedded_samples), 2)
        
        # Verify multimodal samples were loaded correctly
        self.assertEqual(loader.embedded_samples[0]["image_cid"], "QmImageCID1")
        self.assertEqual(loader.embedded_samples[0]["label"], 1)
        self.assertEqual(loader.embedded_samples[0]["text"], "Sample text description for image 1")

    def test_batch_iteration(self):
        """Test iterating through dataset batches."""
        # Create loader with batch size 3
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=3, shuffle=False)

        # Load dataset
        loader.load_dataset("QmDatasetCID")

        # Check iteration - should get 3 batches (3 + 3 + 2 samples)
        batches = list(loader)

        # Assertions
        self.assertEqual(len(batches), 3)  # ceil(8/3) = 3 batches
        self.assertEqual(len(batches[0]), 3)  # First batch has 3 samples
        self.assertEqual(len(batches[1]), 3)  # Second batch has 3 samples
        self.assertEqual(len(batches[2]), 2)  # Third batch has 2 samples
        
        # Verify sample content
        self.assertEqual(batches[0][0]["features"], [1, 2, 3])
        self.assertEqual(batches[0][0]["labels"], 0)

    def test_shuffled_batch_iteration(self):
        """Test iterating through dataset with shuffling enabled."""
        # Create separate loader with shuffling enabled
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=2, shuffle=True)
        
        # Load dataset
        loader.load_dataset("QmDatasetCID")
        
        # Set a fixed seed for reproducible testing
        loader.rng.seed(42)
        
        # Get batches from first iteration
        first_batches = list(loader)
        
        # Reset and re-seed for second iteration
        loader.rng.seed(99)  # Different seed should produce different order
        second_batches = list(loader)
        
        # Verify we got the expected number of batches
        self.assertEqual(len(first_batches), 4)  # ceil(8/2) = 4 batches
        
        # Check that the order is different with different seeds
        # This just checks if any sample is in a different position
        all_same = True
        for i in range(len(first_batches)):
            for j in range(len(first_batches[i])):
                if i < len(second_batches) and j < len(second_batches[i]):
                    if first_batches[i][j]["features"] != second_batches[i][j]["features"]:
                        all_same = False
                        break
            if not all_same:
                break
                
        # Shuffling should give a different order with a different seed
        self.assertFalse(all_same)

    def test_dataloader_length(self):
        """Test the __len__ method."""
        # Create loader with different batch sizes
        loader1 = IPFSDataLoader(self.ipfs_mock, batch_size=3)
        loader2 = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        loader3 = IPFSDataLoader(self.ipfs_mock, batch_size=5)

        # Load dataset with 8 samples
        loader1.load_dataset("QmDatasetCID")
        loader2.load_dataset("QmDatasetCID")
        loader3.load_dataset("QmDatasetCID")

        # Assertions
        self.assertEqual(len(loader1), 3)  # ceil(8/3) = 3 batches
        self.assertEqual(len(loader2), 2)  # ceil(8/4) = 2 batches
        self.assertEqual(len(loader3), 2)  # ceil(8/5) = 2 batches

    @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True)
    @patch("ipfs_kit_py.ai_ml_integration.torch")
    def test_to_pytorch(self, mock_torch):
        """Test conversion to PyTorch DataLoader."""
        # Configure mocks
        mock_dataloader = MagicMock()
        mock_torch.utils.data.DataLoader.return_value = mock_dataloader

        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        loader.load_dataset("QmDatasetCID")

        # Convert to PyTorch
        pytorch_loader = loader.to_pytorch()

        # Assertions
        self.assertIsNotNone(pytorch_loader)
        mock_torch.utils.data.DataLoader.assert_called_once()

    @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", False)
    def test_to_pytorch_unavailable(self):
        """Test conversion to PyTorch DataLoader when PyTorch is not available."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        loader.load_dataset("QmDatasetCID")

        # Try to convert to PyTorch
        result = loader.to_pytorch()

        # Assertions
        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("PyTorch is not available", result["error"])

    @patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True)
    @patch("ipfs_kit_py.ai_ml_integration.tf")
    def test_to_tensorflow(self, mock_tf):
        """Test conversion to TensorFlow Dataset."""
        # Configure mocks
        mock_dataset = MagicMock()
        mock_tf.data.Dataset.from_generator.return_value = mock_dataset
        mock_dataset.batch.return_value = mock_dataset
        mock_dataset.prefetch.return_value = mock_dataset

        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        loader.load_dataset("QmDatasetCID")

        # Convert to TensorFlow
        tf_dataset = loader.to_tensorflow()

        # Assertions
        self.assertIsNotNone(tf_dataset)
        mock_tf.data.Dataset.from_generator.assert_called_once()
        mock_dataset.batch.assert_called_once_with(4)
        mock_dataset.prefetch.assert_called_once()

    @patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", False)
    def test_to_tensorflow_unavailable(self):
        """Test conversion to TensorFlow Dataset when TensorFlow is not available."""
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        loader.load_dataset("QmDatasetCID")

        # Try to convert to TensorFlow
        result = loader.to_tensorflow()

        # Assertions
        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("TensorFlow is not available", result["error"])

    def test_fetch_image(self):
        """Test fetching images from IPFS."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Test fetch_image method
        with patch("ipfs_kit_py.ai_ml_integration.Image") as mock_image:
            mock_pil_image = MagicMock()
            mock_image.open.return_value = mock_pil_image
            
            # Call fetch_image without transform
            result = loader.fetch_image("QmImageCID1")
            
            # Assertions
            self.assertEqual(result, mock_pil_image)
            mock_image.open.assert_called_once()
            self.ipfs_mock.cat.assert_called_once_with("QmImageCID1")

    @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True)
    def test_fetch_image_with_transform(self):
        """Test fetching images with PyTorch transformation."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Test fetch_image method with transform
        with patch("ipfs_kit_py.ai_ml_integration.Image") as mock_image:
            with patch("ipfs_kit_py.ai_ml_integration.torch") as mock_torch:
                mock_pil_image = MagicMock()
                mock_image.open.return_value = mock_pil_image
                
                mock_tensor = MagicMock()
                mock_transform = MagicMock()
                mock_transform.return_value = mock_tensor
                
                # Call fetch_image with transform
                result = loader.fetch_image("QmImageCID1", transform_to_tensor=True, image_transforms=mock_transform)
                
                # Assertions
                self.assertEqual(result, mock_tensor)
                mock_transform.assert_called_once_with(mock_pil_image)

    def test_process_text(self):
        """Test text processing."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Test with plain text (no tokenizer)
        text = "This is a test sentence."
        result = loader.process_text(text)
        
        # Assertions
        self.assertEqual(result, text)
        
        # Test with mock tokenizer
        mock_tokenizer = MagicMock()
        mock_tokenized = MagicMock()
        mock_tokenizer.return_value = mock_tokenized
        
        result = loader.process_text(text, tokenizer=mock_tokenizer, max_length=128)
        
        # Assertions
        self.assertEqual(result, mock_tokenized)
        mock_tokenizer.assert_called_once_with(text, return_tensors="pt", max_length=128, truncation=True)

    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Set up some mock metrics
        loader.performance_metrics["batch_times"] = [10, 20, 30]
        loader.performance_metrics["cache_hits"] = 15
        loader.performance_metrics["cache_misses"] = 5
        loader.performance_metrics["load_times"] = [100, 200]
        
        # Get metrics
        metrics = loader.get_performance_metrics()
        
        # Assertions
        self.assertEqual(metrics["cache_hit_rate"], 0.75)  # 15 / (15 + 5)
        self.assertEqual(metrics["avg_batch_time_ms"], 20)  # (10 + 20 + 30) / 3
        self.assertEqual(metrics["min_batch_time_ms"], 10)
        self.assertEqual(metrics["max_batch_time_ms"], 30)
        self.assertEqual(metrics["avg_load_time_ms"], 150)  # (100 + 200) / 2

    def test_clear(self):
        """Test clearing the data loader."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Load dataset
        loader.load_dataset("QmDatasetCID")
        
        # Verify data is loaded
        self.assertEqual(loader.total_samples, 8)
        self.assertIsNotNone(loader.sample_cids)
        
        # Clear the loader
        loader.clear()
        
        # Verify data is cleared
        self.assertEqual(loader.total_samples, 0)
        self.assertIsNone(loader.sample_cids)
        self.assertIsNone(loader.embedded_samples)

    def test_close(self):
        """Test closing the data loader."""
        # Create loader
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
        # Load dataset
        loader.load_dataset("QmDatasetCID")
        
        # Mock the prefetch queue and threads
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        loader.prefetch_threads = [mock_thread]
        
        # Close the loader
        loader.close()
        
        # Assertions
        self.assertTrue(loader.stop_prefetch.is_set())
        mock_thread.join.assert_called_once()
        self.assertEqual(len(loader.prefetch_threads), 0)

    def test_context_manager(self):
        """Test the context manager functionality."""
        # Test context manager
        with patch("ipfs_kit_py.ai_ml_integration.IPFSDataLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader_class.return_value = mock_loader
            
            # Use context manager
            with ipfs_data_loader_context(self.ipfs_mock, batch_size=16) as loader:
                pass
                
            # Verify loader was created and closed
            mock_loader_class.assert_called_once()
            mock_loader.close.assert_called_once()

    def test_handle_missing_samples(self):
        """Test how the dataloader handles missing samples."""
        # Modified mock dag_get that will return error for one sample
        def mock_dag_get_with_error(cid, **kwargs):
            if cid == "QmDatasetCID":
                return {
                    "success": True,
                    "operation": "dag_get",
                    "object": self.dataset_metadata
                }
            elif cid == "QmSample3":  # Make this sample fail
                return {
                    "success": False,
                    "operation": "dag_get",
                    "error": "Sample not found"
                }
            elif cid.startswith("QmSample"):
                # Extract index from sample name
                idx = int(cid[8:]) - 1
                if 0 <= idx < len(self.samples):
                    return {
                        "success": True,
                        "operation": "dag_get",
                        "object": self.samples[idx]
                    }
            return {
                "success": False,
                "operation": "dag_get",
                "error": f"Content not found: {cid}"
            }
            
        # Create loader with our modified mock
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4, shuffle=False)
        self.ipfs_mock.dag_get.side_effect = mock_dag_get_with_error
        
        # Load dataset
        loader.load_dataset("QmDatasetCID")
        
        # Should still work even with a missing sample
        batches = list(loader)
        
        # Assertions - we should have 2 batches with 7 total samples (one missing)
        self.assertEqual(len(batches), 2)
        total_samples = sum(len(batch) for batch in batches)
        self.assertEqual(total_samples, 7)  # 8 original - 1 missing

    @patch("ipfs_kit_py.ai_ml_integration.queue.Queue")
    def test_prefetch_mechanism(self, mock_queue):
        """Test the prefetch mechanism."""
        # Configure mock queue
        mock_q = MagicMock()
        mock_queue.return_value = mock_q
        
        # Create loader with prefetch
        loader = IPFSDataLoader(self.ipfs_mock, batch_size=4, prefetch=3)
        
        # Load dataset
        loader.load_dataset("QmDatasetCID")
        
        # Verify prefetch queue was created with correct size
        mock_queue.assert_called_with(maxsize=3)
        
        # Verify prefetch threads were started
        self.assertEqual(len(loader.prefetch_threads), 1)


if __name__ == "__main__":
    unittest.main()
