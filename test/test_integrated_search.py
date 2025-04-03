"""Tests for the integrated search module.

This module tests the integration between Arrow metadata index and GraphRAG.
"""

import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

# Class under test
from ipfs_kit_py.integrated_search import MetadataEnhancedGraphRAG

# Import mock classes to avoid actual IPFS dependencies during testing
from .mock_ipfs_kit import MockIPFSKit


# Create mock versions of dependencies
class MockIPLDGraphDB:
    def __init__(self, ipfs_client):
        self.ipfs = ipfs_client
        self.entities = {}
        self.relationships = {}
        self.vectors = {}

    def add_entity(self, entity_id, properties, vector=None):
        self.entities[entity_id] = {"properties": properties, "vector": vector}
        return {"success": True, "entity_id": entity_id}

    def get_entity(self, entity_id):
        return self.entities.get(entity_id)

    def add_relationship(self, from_entity, to_entity, relationship_type, properties=None):
        rel_id = f"{from_entity}:{relationship_type}:{to_entity}"
        self.relationships[rel_id] = {
            "from": from_entity,
            "to": to_entity,
            "type": relationship_type,
            "properties": properties or {},
        }
        return rel_id

    def find_related_entities(self, entity_id, max_hops=1, include_properties=False):
        results = []
        for rel_id, rel in self.relationships.items():
            if rel["from"] == entity_id:
                related = {"entity_id": rel["to"], "relationship": rel["type"]}
                if include_properties:
                    related["properties"] = rel["properties"]
                results.append(related)
        return results

    def graph_vector_search(self, query_vector, hop_count=1, top_k=10):
        results = []
        for entity_id, entity in self.entities.items():
            if entity.get("vector") is not None:
                # Simple dot product similarity
                vector = np.array(entity["vector"])
                query = np.array(query_vector)
                similarity = np.dot(vector, query) / (
                    np.linalg.norm(vector) * np.linalg.norm(query)
                )

                results.append(
                    {
                        "entity_id": entity_id,
                        "score": float(similarity),
                        "path": [entity_id],
                        "distance": 0,
                    }
                )

        # Sort by score and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def generate_embedding(self, text):
        """Mock embedding generator that creates a simple vector from text."""
        # Simple hash-based representation for testing
        vector = []
        for i in range(10):
            # Create a repeatable but varied vector based on text
            vector.append(sum([ord(c) * (i + 1) for c in text]) % 100 / 100.0)
        return vector

    def generate_llm_prompt(self, query, results, format_type="text"):
        """Generate a mock prompt for testing."""
        if format_type == "markdown":
            return f"# Context for {query}\n\n" + "\n".join(
                [f"- {r['entity_id']}: {r['score']:.2f}" for r in results]
            )
        else:
            return f"Context for {query}:\n" + "\n".join(
                [f"{r['entity_id']}: {r['score']:.2f}" for r in results]
            )


class MockIPFSArrowIndex:
    def __init__(self, role="leecher"):
        self.role = role
        self.records = {}

    def add_record(self, record):
        self.records[record["cid"]] = record
        return {"success": True, "record_added": True, "cid": record["cid"]}

    def get_by_cid(self, cid):
        return self.records.get(cid)

    def query(self, filters):
        """Simple filtering implementation for testing."""
        results = []

        for cid, record in self.records.items():
            match = True
            for field, op, value in filters:
                if field not in record:
                    match = False
                    break

                if op == "==":
                    if record[field] != value:
                        match = False
                elif op == "!=":
                    if record[field] == value:
                        match = False
                elif op == ">":
                    if not (record[field] > value):
                        match = False
                elif op == ">=":
                    if not (record[field] >= value):
                        match = False
                elif op == "<":
                    if not (record[field] < value):
                        match = False
                elif op == "<=":
                    if not (record[field] <= value):
                        match = False
                elif op == "contains":
                    if isinstance(record[field], list):
                        if value not in record[field]:
                            match = False
                    elif isinstance(record[field], str):
                        if value not in record[field]:
                            match = False
                    else:
                        match = False

            if match:
                results.append(record)

        # Create a mock table-like object that has to_pylist method
        mock_table = MagicMock()
        mock_table.to_pylist.return_value = results
        mock_table.num_rows = len(results)

        return mock_table


# Path the imports in the integrated_search module
@patch("ipfs_kit_py.integrated_search.IPLDGraphDB", MockIPLDGraphDB)
@patch("ipfs_kit_py.integrated_search.IPFSArrowIndex", MockIPFSArrowIndex)
class TestIntegratedSearch(unittest.TestCase):
    """Test the integration between Arrow metadata index and GraphRAG."""

    def setUp(self):
        """Set up test environment before each test."""
        self.ipfs = MockIPFSKit()
        self.integrated_search = MetadataEnhancedGraphRAG(ipfs_client=self.ipfs)

        # Add some test data
        self._add_test_data()

    def _add_test_data(self):
        """Add test entities to both systems."""
        # ML model entities
        self.integrated_search.index_entity(
            entity_id="QmModelA",
            properties={
                "type": "model",
                "name": "ResNet50",
                "task": "image-classification",
                "framework": "pytorch",
                "description": "Deep residual network for image classification",
            },
            vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            metadata={
                "mime_type": "application/x-pytorch",
                "size_bytes": 97865432,
                "tags": ["computer-vision", "classification", "resnet"],
            },
        )

        self.integrated_search.index_entity(
            entity_id="QmModelB",
            properties={
                "type": "model",
                "name": "BERT-base",
                "task": "text-embedding",
                "framework": "tensorflow",
                "description": "Bidirectional encoder for text representation",
            },
            vector=[0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0],
            metadata={
                "mime_type": "application/x-tensorflow",
                "size_bytes": 438765432,
                "tags": ["nlp", "transformer", "embedding"],
            },
        )

        # Dataset entities
        self.integrated_search.index_entity(
            entity_id="QmDatasetA",
            properties={
                "type": "dataset",
                "name": "CIFAR-10",
                "domain": "computer-vision",
                "samples": 60000,
                "description": "Small images dataset with 10 classes",
            },
            vector=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            metadata={
                "mime_type": "application/x-hdf5",
                "size_bytes": 162353434,
                "tags": ["computer-vision", "classification", "small-images"],
            },
        )

        # Add relationships
        self.integrated_search.graph_db.add_relationship(
            from_entity="QmModelA",
            to_entity="QmDatasetA",
            relationship_type="trained_on",
            properties={"epochs": 100, "accuracy": 0.94},
        )

    def test_metadata_only_search(self):
        """Test search with only metadata filters."""
        # Search for PyTorch models
        results = self.integrated_search.hybrid_search(
            metadata_filters=[("mime_type", "==", "application/x-pytorch")]
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "QmModelA")
        self.assertEqual(results[0]["source"], "metadata")

        # Search by tag
        results = self.integrated_search.hybrid_search(
            metadata_filters=[("tags", "contains", "nlp")]
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "QmModelB")

    def test_vector_only_search(self):
        """Test search with only vector similarity."""
        # Search using a vector that should be closer to ModelA
        query_vector = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0]
        results = self.integrated_search.hybrid_search(query_vector=query_vector)

        self.assertEqual(len(results), 3)  # All entities with vectors
        self.assertEqual(results[0]["id"], "QmModelA")  # Should be most similar
        self.assertEqual(results[0]["source"], "vector")

        # Filter by entity type
        results = self.integrated_search.hybrid_search(
            query_vector=query_vector, entity_types=["dataset"]
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "QmDatasetA")

    def test_combined_search(self):
        """Test combined metadata and vector search."""
        # Search for computer vision models with vector similarity
        query_vector = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0]
        results = self.integrated_search.hybrid_search(
            query_vector=query_vector, metadata_filters=[("tags", "contains", "computer-vision")]
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "QmModelA")
        self.assertEqual(results[0]["source"], "combined")

    def test_text_query_conversion(self):
        """Test that text queries are properly converted to vectors."""
        # Should convert text to a vector internally
        results = self.integrated_search.hybrid_search(query_text="image classification model")

        self.assertEqual(len(results), 3)  # All entities with vectors
        # The exact order depends on the embedding function, but we can check basic properties
        self.assertTrue(all(r["source"] == "vector" for r in results))

    def test_llm_context_generation(self):
        """Test generating LLM context from search results."""
        # Get some search results
        results = self.integrated_search.hybrid_search(query_text="image classification")

        # Generate context
        context = self.integrated_search.generate_llm_context(
            query="image classification", search_results=results, format_type="markdown"
        )

        # Verify context contains the query
        self.assertIn("image classification", context)
        # Verify it contains the most relevant entity
        self.assertIn("QmModelA", context)

    def test_error_handling(self):
        """Test the error handling in the implementation."""
        # Mock failure in graph vector search
        original_method = self.integrated_search.graph_db.graph_vector_search

        def mock_failure(*args, **kwargs):
            raise Exception("Simulated failure")

        self.integrated_search.graph_db.graph_vector_search = mock_failure

        # Should handle error and return empty results
        results = self.integrated_search.hybrid_search(query_text="image classification")

        # Reset the method
        self.integrated_search.graph_db.graph_vector_search = original_method

        # Should have gracefully handled the error
        self.assertEqual(len(results), 0)

    def test_index_entity(self):
        """Test indexing an entity in both systems."""
        # Index a new entity
        result = self.integrated_search.index_entity(
            entity_id="QmNewEntity",
            properties={"type": "model", "name": "NewModel", "framework": "custom"},
            vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # Should have succeeded
        self.assertTrue(result["success"])

        # Entity should be in the graph DB
        self.assertIsNotNone(self.integrated_search.graph_db.get_entity("QmNewEntity"))

        # Entity should be in the metadata index
        self.assertIsNotNone(self.integrated_search.metadata_index.get_by_cid("QmNewEntity"))


if __name__ == "__main__":
    unittest.main()
