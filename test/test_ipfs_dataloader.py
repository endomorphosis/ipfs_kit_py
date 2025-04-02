# """
# Tests for the IPFSDataLoader implementation.

# This module tests the IPFSDataLoader class, which provides efficient data loading
# capabilities for machine learning workloads using IPFS content-addressed storage.
# """

# import unittest
# import json
# import tempfile
# import os
# import time
# from unittest.mock import MagicMock, patch

# # Import IPFS Kit
# from ipfs_kit_py.ipfs_kit import ipfs_kit
# from ipfs_kit_py.ai_ml_integration import IPFSDataLoader


# class TestIPFSDataLoader(unittest.TestCase):
#     """Test suite for IPFSDataLoader."""

#     def setUp(self):
#         """Set up test environment."""
#         # Mock IPFS client
#         self.ipfs_mock = MagicMock()
        
#         # Sample dataset metadata
#         self.dataset_metadata = {
#             "name": "test_dataset",
#             "description": "Test dataset for unit tests",
#             "version": "1.0.0",
#             "created_at": time.time(),
#             "samples": [
#                 "QmSample1", "QmSample2", "QmSample3", "QmSample4", 
#                 "QmSample5", "QmSample6", "QmSample7", "QmSample8"
#             ]
#         }
        
#         # Sample dataset with embedded data
#         self.embedded_dataset = {
#             "name": "embedded_dataset",
#             "description": "Test dataset with embedded data",
#             "version": "1.0.0",
#             "created_at": time.time(),
#             "data": [
#                 {"features": [1, 2, 3], "labels": 0},
#                 {"features": [4, 5, 6], "labels": 1},
#                 {"features": [7, 8, 9], "labels": 0},
#                 {"features": [10, 11, 12], "labels": 1}
#             ]
#         }
        
#         # Create mock samples
#         self.samples = [
#             {"features": [1, 2, 3], "labels": 0},
#             {"features": [4, 5, 6], "labels": 1},
#             {"features": [7, 8, 9], "labels": 0},
#             {"features": [10, 11, 12], "labels": 1},
#             {"features": [13, 14, 15], "labels": 0},
#             {"features": [16, 17, 18], "labels": 1},
#             {"features": [19, 20, 21], "labels": 0},
#             {"features": [22, 23, 24], "labels": 1}
#         ]
        
#         # Configure mocks
#         self.setup_mocks()

#     def setup_mocks(self):
#         """Set up mock responses for IPFS operations."""
#         # Mock successful dag_get for dataset metadata
#         self.ipfs_mock.dag_get.return_value = {
#             "success": True,
#             "operation": "dag_get",
#             "object": self.dataset_metadata
#         }
        
#         # Mock sample retrieval - different response for each sample CID
#         def mock_dag_get(cid, **kwargs):
#             if cid == "QmDatasetCID":
#                 return {
#                     "success": True,
#                     "operation": "dag_get",
#                     "object": self.dataset_metadata
#                 }
#             elif cid == "QmEmbeddedDatasetCID":
#                 return {
#                     "success": True, 
#                     "operation": "dag_get",
#                     "object": self.embedded_dataset
#                 }
#             elif cid.startswith("QmSample"):
#                 # Extract index from sample name
#                 idx = int(cid[8:]) - 1
#                 if 0 <= idx < len(self.samples):
#                     return {
#                         "success": True,
#                         "operation": "dag_get",
#                         "object": self.samples[idx]
#                     }
            
#             return {
#                 "success": False,
#                 "operation": "dag_get",
#                 "error": f"Content not found: {cid}"
#             }
            
#         self.ipfs_mock.dag_get.side_effect = mock_dag_get

#     def test_dataloader_init(self):
#         """Test IPFSDataLoader initialization."""
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=4, shuffle=True, prefetch=2)
        
#         self.assertEqual(loader.batch_size, 4)
#         self.assertEqual(loader.shuffle, True)
#         self.assertEqual(loader.prefetch, 2)
#         self.assertEqual(loader.total_samples, 0)

#     def test_load_dataset(self):
#         """Test loading a dataset by CID."""
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
        
#         # Load dataset
#         result = loader.load_dataset("QmDatasetCID")
        
#         # Assertions
#         self.assertTrue(result["success"])
#         self.assertEqual(loader.total_samples, 8)
#         self.assertEqual(loader.dataset_cid, "QmDatasetCID")
#         self.assertEqual(len(loader.sample_cids), 8)

#     def test_load_embedded_dataset(self):
#         """Test loading a dataset with embedded data."""
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=2)
        
#         # Update mock to return embedded dataset
#         self.ipfs_mock.dag_get.return_value = {
#             "success": True,
#             "operation": "dag_get",
#             "object": self.embedded_dataset
#         }
        
#         # Load dataset
#         result = loader.load_dataset("QmEmbeddedDatasetCID")
        
#         # Assertions
#         self.assertTrue(result["success"])
#         self.assertEqual(loader.total_samples, 4)
#         self.assertIsNone(loader.sample_cids)
#         self.assertEqual(len(loader.embedded_samples), 4)

#     def test_batch_iteration(self):
#         """Test iterating through dataset batches."""
#         # Create loader with batch size 3
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=3, shuffle=False)
        
#         # Load dataset
#         loader.load_dataset("QmDatasetCID")
        
#         # Check iteration - should get 3 batches (3 + 3 + 2 samples)
#         batches = list(loader)
        
#         # Assertions
#         self.assertEqual(len(batches), 3)  # ceil(8/3) = 3 batches
#         self.assertEqual(len(batches[0]), 3)  # First batch has 3 samples
#         self.assertEqual(len(batches[1]), 3)  # Second batch has 3 samples
#         self.assertEqual(len(batches[2]), 2)  # Third batch has 2 samples

#     def test_dataloader_length(self):
#         """Test the __len__ method."""
#         # Create loader with different batch sizes
#         loader1 = IPFSDataLoader(self.ipfs_mock, batch_size=3)
#         loader2 = IPFSDataLoader(self.ipfs_mock, batch_size=4)
#         loader3 = IPFSDataLoader(self.ipfs_mock, batch_size=5)
        
#         # Load dataset with 8 samples
#         loader1.load_dataset("QmDatasetCID")
#         loader2.load_dataset("QmDatasetCID")
#         loader3.load_dataset("QmDatasetCID")
        
#         # Assertions
#         self.assertEqual(len(loader1), 3)  # ceil(8/3) = 3 batches
#         self.assertEqual(len(loader2), 2)  # ceil(8/4) = 2 batches
#         self.assertEqual(len(loader3), 2)  # ceil(8/5) = 2 batches

#     @patch("ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE", True)
#     @patch("ipfs_kit_py.ai_ml_integration.torch")
#     def test_to_pytorch(self, mock_torch):
#         """Test conversion to PyTorch DataLoader."""
#         # Configure mocks
#         mock_dataloader = MagicMock()
#         mock_torch.utils.data.DataLoader.return_value = mock_dataloader
        
#         # Create loader
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
#         loader.load_dataset("QmDatasetCID")
        
#         # Convert to PyTorch
#         pytorch_loader = loader.to_pytorch()
        
#         # Assertions
#         self.assertIsNotNone(pytorch_loader)
#         mock_torch.utils.data.DataLoader.assert_called_once()

#     @patch("ipfs_kit_py.ai_ml_integration.TF_AVAILABLE", True)
#     @patch("ipfs_kit_py.ai_ml_integration.tf")
#     def test_to_tensorflow(self, mock_tf):
#         """Test conversion to TensorFlow Dataset."""
#         # Configure mocks
#         mock_dataset = MagicMock()
#         mock_tf.data.Dataset.from_generator.return_value = mock_dataset
#         mock_dataset.batch.return_value = mock_dataset
#         mock_dataset.prefetch.return_value = mock_dataset
        
#         # Create loader
#         loader = IPFSDataLoader(self.ipfs_mock, batch_size=4)
#         loader.load_dataset("QmDatasetCID")
        
#         # Convert to TensorFlow
#         tf_dataset = loader.to_tensorflow()
        
#         # Assertions
#         self.assertIsNotNone(tf_dataset)
#         mock_tf.data.Dataset.from_generator.assert_called_once()
#         mock_dataset.batch.assert_called_once_with(4)
#         mock_dataset.prefetch.assert_called_once()

#     @patch("ipfs_kit_py.ai_ml_integration.HAS_AI_ML_INTEGRATION", True)
#     @patch("ipfs_kit_py.ai_ml_integration.IPFSDataLoader")
#     def test_get_data_loader_from_ipfs_kit(self, mock_dataloader_class):
#         """Test getting a data loader from the IPFS Kit interface."""
#         # Configure mocks
#         mock_dataloader = MagicMock()
#         mock_dataloader_class.return_value = mock_dataloader
        
#         # Create IPFS Kit with mocked components
#         with patch("ipfs_kit_py.ipfs_kit.ipfs") as mock_ipfs_module:
#             kit = ipfs_kit()
#             kit.ipfs = MagicMock()
            
#             # Test getting data loader
#             loader = kit.get_data_loader(batch_size=16, shuffle=False)
            
#             # Assertions
#             self.assertEqual(loader, mock_dataloader)
#             mock_dataloader_class.assert_called_once_with(
#                 ipfs_client=kit.ipfs,
#                 batch_size=16,
#                 shuffle=False,
#                 prefetch=2
#             )


# if __name__ == "__main__":
#     unittest.main()