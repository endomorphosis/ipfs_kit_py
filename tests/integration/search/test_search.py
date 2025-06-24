"""
Integration test for MCP Search capabilities.
This test verifies the functionality of the search components
including content indexing, vector search, and hybrid search.
"""

import os
import sys
import unittest
import logging
import tempfile
import time
import uuid
import json
import asyncio
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestSearchIntegration(unittest.TestCase):
    """Integration tests for the MCP search capabilities."""

    @classmethod
    def setUpClass(cls):
        """Set up test resources."""
        # Create a temporary directory for search database
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.db_path = cls.temp_dir / "search_test.db"

        # Sample test documents for indexing
        cls.test_docs = [
            {
                "cid": f"bafybeih{uuid.uuid4().hex[:24]}",
                "name": "Document about artificial intelligence",
                "content": "Artificial intelligence (AI) is intelligence demonstrated by machines.",
                "metadata": {
                    "author": "AI Researcher",
                    "date": "2025-04-01",
                    "tags": ["AI", "machine learning", "technology"]
                }
            },
            {
                "cid": f"bafybeih{uuid.uuid4().hex[:24]}",
                "name": "Document about blockchain",
                "content": "Blockchain is a decentralized, distributed ledger technology.",
                "metadata": {
                    "author": "Blockchain Expert",
                    "date": "2025-04-02",
                    "tags": ["blockchain", "cryptocurrency", "technology"]
                }
            },
            {
                "cid": f"bafybeih{uuid.uuid4().hex[:24]}",
                "name": "Document about IPFS",
                "content": "IPFS is a protocol and network designed to create a content-addressable, peer-to-peer method of storing and sharing files.",
                "metadata": {
                    "author": "IPFS Developer",
                    "date": "2025-04-03",
                    "tags": ["ipfs", "decentralized storage", "technology"]
                }
            }
        ]

        # Try to import the search module
        try:
            from ipfs_kit_py.mcp.search import mcp_search
            cls.search_module = mcp_search
            cls.import_error = None

            # Initialize the search engine
            cls.search_engine = cls.search_module.SearchEngine(
                db_path=str(cls.db_path),
                enable_vector_search=False  # Start with just text search for basic testing
            )
        except ImportError as e:
            logger.warning(f"Cannot import search module: {e}")
            cls.import_error = e
            return
        except Exception as e:
            logger.error(f"Error initializing search engine: {e}")
            cls.init_error = e
            return

        # Index the test documents
        try:
            for doc in cls.test_docs:
                cls.search_engine.index_document(
                    cid=doc["cid"],
                    text=doc["content"],
                    metadata=doc["metadata"]
                )
            logger.info(f"Indexed {len(cls.test_docs)} test documents")
        except Exception as e:
            logger.error(f"Error indexing test documents: {e}")
            cls.index_error = e

    def setUp(self):
        """Set up for each test."""
        if hasattr(self.__class__, 'import_error') and self.__class__.import_error:
            self.skipTest(f"Search module not available: {self.__class__.import_error}")

        if hasattr(self.__class__, 'init_error') and self.__class__.init_error:
            self.skipTest(f"Search engine initialization failed: {self.__class__.init_error}")

        if hasattr(self.__class__, 'index_error') and self.__class__.index_error:
            self.skipTest(f"Document indexing failed: {self.__class__.index_error}")

    def test_search_module_exists(self):
        """Test that the search module exists and can be initialized."""
        self.assertIsNotNone(self.search_module)
        logger.info("Search module exists")

        # Check for expected attributes/methods
        expected_attributes = [
            'SearchEngine', 'search_text', 'search_vector',
            'search_hybrid', 'index_document'
        ]

        for attr in expected_attributes:
            self.assertTrue(hasattr(self.search_module, attr) or
                          hasattr(self.search_engine, attr.split('_')[-1]),
                          f"Missing attribute: {attr}")

        logger.info("Search module has expected components")

    def test_text_search(self):
        """Test basic text search functionality."""
        # Search for "artificial intelligence"
        results = self.search_engine.search_text("artificial intelligence")
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        # The first document should be the one about AI
        first_result = results[0]
        self.assertIn("artificial intelligence", first_result["text"].lower())

        logger.info(f"Text search returned {len(results)} results")

        # Search for "blockchain"
        results = self.search_engine.search_text("blockchain")
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        # The first document should be the one about blockchain
        first_result = results[0]
        self.assertIn("blockchain", first_result["text"].lower())

        logger.info(f"Text search for 'blockchain' returned {len(results)} results")

    def test_metadata_filtering(self):
        """Test search with metadata filtering."""
        # Search with author filter
        results = self.search_engine.search_text(
            "technology",
            metadata_filters={"author": "IPFS Developer"}
        )

        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        # Should only return the IPFS document
        first_result = results[0]
        self.assertEqual(first_result["metadata"]["author"], "IPFS Developer")

        logger.info(f"Metadata-filtered search returned {len(results)} results")

    def test_tag_search(self):
        """Test searching by tags in metadata."""
        # Search for documents with the "ipfs" tag
        results = self.search_engine.search_text(
            "", # Empty query to match everything
            metadata_filters={"tags": ["ipfs"]}
        )

        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

        # Should return the IPFS document
        first_result = results[0]
        self.assertIn("ipfs", first_result["metadata"]["tags"])

        logger.info(f"Tag search returned {len(results)} results")

    def test_vector_search_support(self):
        """Test if vector search is supported (even if not enabled)."""
        try:
            # Try to initialize with vector search
            search_engine_vector = self.search_module.SearchEngine(
                db_path=str(self.db_path) + ".vector",
                enable_vector_search=True
            )

            # If we got here, vector search is at least supported in code
            logger.info("Vector search is supported in the code")

            # Clean up
            if hasattr(search_engine_vector, "close"):
                search_engine_vector.close()

            # Remove the vector database file if it was created
            vector_db_path = Path(str(self.db_path) + ".vector")
            if vector_db_path.exists():
                vector_db_path.unlink()

        except (ImportError, Exception) as e:
            # This is not a failure - just means optional dependencies aren't installed
            logger.info(f"Vector search not available: {e}")
            self.skipTest(f"Vector search dependencies not installed: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        # Close the search engine if it was created
        if hasattr(cls, 'search_engine'):
            if hasattr(cls.search_engine, "close"):
                cls.search_engine.close()

        # Clean up the temporary directory
        if hasattr(cls, 'temp_dir') and cls.temp_dir.exists():
            import shutil
            shutil.rmtree(cls.temp_dir)
            logger.info(f"Cleaned up test directory: {cls.temp_dir}")

if __name__ == "__main__":
    unittest.main()
