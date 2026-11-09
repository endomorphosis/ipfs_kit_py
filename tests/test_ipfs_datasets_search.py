"""
Test suite for ipfs_datasets search and indexing integration.

This test validates the integration between ipfs_datasets_py and the
search/indexing capabilities (GraphRAG, knowledge graphs, Arrow index).
"""

import os
import sys
import tempfile
import shutil
import json
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ipfs_kit_py.ipfs_datasets_search import (
    DatasetSearchIndexer,
    get_dataset_search_indexer,
    integrate_with_dataset_manager,
    reset_indexer
)


class TestDatasetSearchIndexer(unittest.TestCase):
    """Test the dataset search and indexing integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.index_dir = os.path.join(self.test_dir, "index")
        self.test_dataset = os.path.join(self.test_dir, "test_dataset.csv")
        
        # Create a simple test dataset
        with open(self.test_dataset, 'w') as f:
            f.write("id,value\n1,100\n2,200\n")
        
        # Reset singleton
        reset_indexer()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        reset_indexer()
    
    def test_indexer_initialization(self):
        """Test DatasetSearchIndexer initialization."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Check that indexer was created
        self.assertIsNotNone(indexer)
        self.assertTrue(os.path.exists(indexer.base_path))
    
    def test_is_available_without_components(self):
        """Test availability check when no components are enabled."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Should still report as available if dataset manager is present
        # (depends on whether ipfs_datasets_py is installed)
        result = indexer.is_available()
        self.assertIsInstance(result, bool)
    
    def test_index_dataset_basic(self):
        """Test basic dataset indexing."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        result = indexer.index_dataset(
            dataset_id="test-dataset",
            dataset_path=self.test_dataset,
            metadata={"description": "Test dataset", "tags": ["test"]}
        )
        
        # Should succeed
        self.assertTrue(result["success"])
        self.assertEqual(result["dataset_id"], "test-dataset")
        
        # Check that dataset is in index
        self.assertIn("test-dataset", indexer.dataset_index)
    
    def test_index_dataset_with_cid(self):
        """Test indexing with IPFS CID."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        cid = "QmTest123"
        result = indexer.index_dataset(
            dataset_id="test-dataset",
            dataset_path=self.test_dataset,
            metadata={"version": "1.0"},
            cid=cid
        )
        
        self.assertTrue(result["success"])
        
        # Check CID mapping
        self.assertEqual(indexer.cid_to_dataset[cid], "test-dataset")
    
    def test_extract_dataset_info(self):
        """Test dataset information extraction."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        info = indexer._extract_dataset_info(self.test_dataset)
        
        # Check extracted info
        self.assertEqual(info["filename"], "test_dataset.csv")
        self.assertEqual(info["extension"], ".csv")
        self.assertEqual(info["content_type"], "tabular")
        self.assertTrue(info["is_file"])
        self.assertFalse(info["is_directory"])
    
    def test_search_datasets_simple(self):
        """Test simple dataset search."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Index a dataset
        indexer.index_dataset(
            dataset_id="test-dataset",
            dataset_path=self.test_dataset,
            metadata={"description": "Machine learning training data"}
        )
        
        # Search for it
        results = indexer.search_datasets("machine learning")
        
        # Should find the dataset
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["dataset_id"], "test-dataset")
    
    def test_search_with_filters(self):
        """Test search with filters."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Index multiple datasets
        indexer.index_dataset(
            dataset_id="csv-dataset",
            dataset_path=self.test_dataset,
            metadata={"content_type": "tabular"}
        )
        
        json_dataset = os.path.join(self.test_dir, "data.json")
        with open(json_dataset, 'w') as f:
            json.dump({"data": [1, 2, 3]}, f)
        
        indexer.index_dataset(
            dataset_id="json-dataset",
            dataset_path=json_dataset,
            metadata={"content_type": "json"}
        )
        
        # Search with filter
        results = indexer.search_datasets(
            query="dataset",
            filters={"content_type": "tabular"}
        )
        
        # Should only find the CSV dataset
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["dataset_id"], "csv-dataset")
    
    def test_get_dataset_lineage(self):
        """Test dataset lineage tracking."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Index parent dataset
        indexer.index_dataset(
            dataset_id="dataset-v1",
            dataset_path=self.test_dataset,
            metadata={"version": "1.0"}
        )
        
        # Index child dataset
        indexer.index_dataset(
            dataset_id="dataset-v2",
            dataset_path=self.test_dataset,
            metadata={
                "version": "2.0",
                "provenance": {
                    "parent_version": "dataset-v1",
                    "transformations": ["normalize", "filter"]
                }
            }
        )
        
        # Get lineage
        lineage = indexer.get_dataset_lineage("dataset-v2")
        
        # Check lineage info
        self.assertEqual(lineage["dataset_id"], "dataset-v2")
        self.assertEqual(lineage["parents"], ["dataset-v1"])
        self.assertEqual(len(lineage["transformations"]), 2)
        
        # Check parent's children
        parent_lineage = indexer.get_dataset_lineage("dataset-v1")
        self.assertEqual(parent_lineage["children"], ["dataset-v2"])
    
    def test_list_indexed_datasets(self):
        """Test listing all indexed datasets."""
        indexer = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Index multiple datasets
        indexer.index_dataset("ds1", self.test_dataset, {"type": "training"})
        indexer.index_dataset("ds2", self.test_dataset, {"type": "validation"})
        indexer.index_dataset("ds3", self.test_dataset, {"type": "training"})
        
        # List all
        all_datasets = indexer.list_indexed_datasets()
        self.assertEqual(len(all_datasets), 3)
        
        # List with filter
        training_datasets = indexer.list_indexed_datasets({"type": "training"})
        self.assertEqual(len(training_datasets), 2)
    
    def test_index_persistence(self):
        """Test that index persists across instances."""
        # Create indexer and index a dataset
        indexer1 = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        indexer1.index_dataset("persistent-ds", self.test_dataset, {"test": "value"})
        
        # Create new indexer with same base_path
        indexer2 = DatasetSearchIndexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False,
            enable_arrow_index=False,
            base_path=self.index_dir
        )
        
        # Should have loaded the previous index
        self.assertIn("persistent-ds", indexer2.dataset_index)
        self.assertEqual(indexer2.dataset_index["persistent-ds"]["test"], "value")
    
    def test_singleton_indexer(self):
        """Test singleton pattern for indexer."""
        indexer1 = get_dataset_search_indexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False
        )
        
        indexer2 = get_dataset_search_indexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False
        )
        
        # Should be the same instance
        self.assertIs(indexer1, indexer2)
        
        # Reset and get new instance
        reset_indexer()
        indexer3 = get_dataset_search_indexer(
            ipfs_client=None,
            enable_graphrag=False,
            enable_knowledge_graph=False
        )
        
        # Should be a different instance
        self.assertIsNot(indexer1, indexer3)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDatasetSearchIndexer))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
