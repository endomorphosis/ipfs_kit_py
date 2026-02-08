"""
Test suite for the IPLD Knowledge Graph functionality.

This module tests the IPLD Knowledge Graph implementation which provides
graph-based knowledge representation with content-addressing and vector search.

Note: Advanced vector database operations and specialized embedding functionality
are provided by `ipfs_datasets_py.vector_stores` and `ipfs_datasets_py.embeddings_router`.
This test suite covers the basic vector operations used for knowledge graph integration.
"""

import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Add parent directory to path to import from ipfs_kit_py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.ipld_knowledge_graph import GraphRAG, IPLDGraphDB, KnowledgeGraphQuery


class TestIPLDKnowledgeGraph(unittest.TestCase):
    """Test cases for the IPLD Knowledge Graph implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock IPFS client
        self.ipfs_client = MagicMock()
        self.ipfs_client.dag_put.side_effect = lambda data: f"mock-cid-{uuid.uuid4()}"
        self.ipfs_client.dag_get.side_effect = lambda cid: {"data": f"mock-data-for-{cid}"}

        # Create temp directory for graph storage
        self.temp_dir = tempfile.mkdtemp()

        # Initialize graph components
        self.graph_db = IPLDGraphDB(ipfs_client=self.ipfs_client, base_path=self.temp_dir)
        self.query = KnowledgeGraphQuery(self.graph_db)
        self.rag = GraphRAG(self.graph_db)

        # Add some test entities and relationships
        self._create_test_data()

    def tearDown(self):
        """Clean up resources."""
        # Remove temp directory - use ignore_errors=True to handle non-empty directories
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_data(self):
        """Create test entities and relationships."""
        # Patch the actual calls to IPFS
        with patch.object(self.graph_db, "_persist_indexes", return_value=True):
            # Add test entities
            self.person1 = self.graph_db.add_entity(
                entity_id="person1",
                entity_type="person",
                properties={"name": "Alice Smith", "age": 32, "occupation": "Data Scientist"},
                vector=[0.1, 0.2, 0.3, 0.4],
            )

            self.person2 = self.graph_db.add_entity(
                entity_id="person2",
                entity_type="person",
                properties={"name": "Bob Johnson", "age": 45, "occupation": "Software Engineer"},
                vector=[0.2, 0.3, 0.4, 0.5],
            )

            self.document1 = self.graph_db.add_entity(
                entity_id="doc1",
                entity_type="document",
                properties={
                    "title": "Introduction to Knowledge Graphs",
                    "content": "Knowledge graphs represent information as entities and relationships...",
                },
                vector=[0.5, 0.5, 0.5, 0.5],
            )

            # Add relationships
            self.rel1 = self.graph_db.add_relationship(
                from_entity="person1",
                to_entity="doc1",
                relationship_type="authored",
                properties={"date": "2023-01-15"},
            )

            self.rel2 = self.graph_db.add_relationship(
                from_entity="person2",
                to_entity="doc1",
                relationship_type="reviewed",
                properties={"date": "2023-01-20"},
            )

    def test_add_entity(self):
        """Test adding an entity to the graph."""
        result = self.graph_db.add_entity(
            entity_id="concept1",
            entity_type="concept",
            properties={"name": "IPFS", "description": "InterPlanetary File System"},
            vector=[0.1, 0.1, 0.2, 0.2],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["entity_id"], "concept1")
        self.assertTrue("cid" in result)

        # Check that entity exists in graph
        entity = self.graph_db.get_entity("concept1")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["type"], "concept")
        self.assertEqual(entity["properties"]["name"], "IPFS")

    def test_add_relationship(self):
        """Test adding a relationship between entities."""
        result = self.graph_db.add_relationship(
            from_entity="person1",
            to_entity="person2",
            relationship_type="knows",
            properties={"since": "2020-05-15"},
        )

        self.assertTrue(result["success"])
        self.assertTrue("relationship_id" in result)
        self.assertEqual(result["relationship_id"], "person1:knows:person2")

        # Check that relationship exists in graph
        rel = self.graph_db.get_relationship("person1:knows:person2")
        self.assertIsNotNone(rel)
        self.assertEqual(rel["type"], "knows")
        self.assertEqual(rel["properties"]["since"], "2020-05-15")

    def test_query_related(self):
        """Test querying related entities."""
        # Query outgoing relationships
        results = self.graph_db.query_related("person1", direction="outgoing")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["entity_id"], "doc1")
        self.assertEqual(results[0]["relationship_type"], "authored")

        # Query incoming relationships
        results = self.graph_db.query_related("doc1", direction="incoming")
        self.assertEqual(len(results), 2)
        relationship_types = [r["relationship_type"] for r in results]
        self.assertIn("authored", relationship_types)
        self.assertIn("reviewed", relationship_types)

        # Query with relationship type filter
        results = self.graph_db.query_related(
            "doc1", relationship_type="authored", direction="incoming"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["relationship_type"], "authored")

    def test_vector_search(self):
        """Test vector similarity search."""
        query_vector = [0.1, 0.2, 0.3, 0.4]  # Close to person1
        results = self.graph_db.vector_search(query_vector, top_k=2)

        self.assertEqual(len(results), 2)
        # First result should be person1 (exact match to query)
        self.assertEqual(results[0]["entity_id"], "person1")

    def test_graph_vector_search(self):
        """Test combined graph and vector search (GraphRAG)."""
        query_vector = [0.1, 0.2, 0.3, 0.4]  # Close to person1
        results = self.graph_db.graph_vector_search(query_vector, hop_count=1, top_k=3)

        self.assertGreaterEqual(len(results), 2)
        # Should include person1 and entities connected to person1
        entity_ids = [r["entity_id"] for r in results]
        self.assertIn("person1", entity_ids)
        self.assertIn("doc1", entity_ids)

    def test_text_search(self):
        """Test searching by text content."""
        results = self.graph_db.text_search("Knowledge Graphs", top_k=2)

        self.assertGreaterEqual(len(results), 1)
        entity_ids = [r["entity_id"] for r in results]
        self.assertIn("doc1", entity_ids)

    def test_path_between(self):
        """Test finding paths between entities."""
        paths = self.graph_db.path_between("person1", "person2")

        self.assertGreaterEqual(len(paths), 1)
        # Should have a path via doc1
        path_entities = [p[0] for p in paths[0]]
        self.assertEqual(len(path_entities), 3)
        self.assertIn("person1", path_entities)
        self.assertIn("doc1", path_entities)
        self.assertIn("person2", path_entities)

    def test_export_import_subgraph(self):
        """Test exporting and importing a subgraph."""
        # Export subgraph
        subgraph = self.graph_db.export_subgraph(["person1", "doc1"], include_relationships=True)

        self.assertEqual(len(subgraph["entities"]), 2)
        self.assertGreaterEqual(len(subgraph["relationships"]), 1)

        # Import to a new graph
        new_graph = IPLDGraphDB(ipfs_client=self.ipfs_client, base_path=tempfile.mkdtemp())

        result = new_graph.import_subgraph(subgraph)
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["entities_added"], 2)
        self.assertGreaterEqual(result["relationships_added"], 1)

        # Verify imported data
        entity = new_graph.get_entity("person1")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["properties"]["name"], "Alice Smith")

    def test_query_interface(self):
        """Test the KnowledgeGraphQuery interface."""
        # Find entities by type
        results = self.query.find_entities(entity_type="person")
        self.assertEqual(len(results), 2)

        # Find related entities
        results = self.query.find_related("doc1", direction="incoming")
        self.assertEqual(len(results), 2)

        # Get knowledge cards
        cards = self.query.get_knowledge_cards(["person1", "doc1"])
        self.assertEqual(len(cards), 2)
        self.assertTrue("properties" in cards["person1"])
        self.assertTrue("outgoing_relationships" in cards["person1"])

    def test_graphrag_retrieve(self):
        """Test the GraphRAG retrieval functionality."""
        # Mock embedding model
        embedding_model = MagicMock()
        embedding_model.encode.return_value = [0.1, 0.2, 0.3, 0.4]

        # Mock embeddings stack availability to test logging
        with patch("ipfs_kit_py.ipld_knowledge_graph.EMBEDDINGS_AVAILABLE", False):
            rag = GraphRAG(graph_db=self.graph_db, embedding_model=embedding_model)

            # Retrieve with text query
            context = rag.retrieve(query_text="Knowledge graph information", top_k=2)

            self.assertTrue("entities" in context)
            self.assertGreaterEqual(len(context["entities"]), 1)

            # Format context for LLM
            formatted = rag.format_context_for_llm(context, format_type="text")
            self.assertIsInstance(formatted, str)
            self.assertIn("Knowledge Graph Context", formatted)

            # Generate LLM prompt
            prompt = rag.generate_llm_prompt(
                user_query="Tell me about knowledge graphs", context=context
            )
            self.assertIsInstance(prompt, str)
            self.assertIn("Tell me about knowledge graphs", prompt)
            self.assertIn("Context", prompt)

        # Test with mocked embeddings stack available (should log recommendation)
        with patch("ipfs_kit_py.ipld_knowledge_graph.EMBEDDINGS_AVAILABLE", True), patch(
            "ipfs_kit_py.ipld_knowledge_graph.logger"
        ) as mock_logger:
            rag = GraphRAG(graph_db=self.graph_db, embedding_model=embedding_model)
            embedding = rag.generate_embedding("test text")
            self.assertIsNotNone(embedding)
            mock_logger.info.assert_called_with(
                "Consider using ipfs_datasets_py.embeddings_router.embed_texts for production embedding generation"
            )


if __name__ == "__main__":
    unittest.main()
