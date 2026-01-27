#!/usr/bin/env python3
"""
Verification script for the Search Integration.

This script verifies that the Search Integration functionality
mentioned in the roadmap is working correctly.
"""

import os
import sys
import json
import time
import logging
import tempfile
import anyio
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger("search_test")

# Add project root to Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

async def test_search_imports():
    """Test the search module imports correctly."""
    try:
        from ipfs_kit_py.mcp.search import (
            SearchEngine,
            search_text,
            search_vector,
            search_hybrid,
            index_document
        )
        
        logger.info("✅ Successfully imported search module")
        return True, SearchEngine
    except ImportError as e:
        logger.error(f"❌ Failed to import search module: {e}")
        return False, None

async def test_search_engine_initialization(SearchEngine):
    """Test search engine initialization."""
    try:
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        
        # Initialize search engine with text search only
        engine = SearchEngine(db_path=temp_db.name, enable_vector_search=False)
        logger.info("✅ Successfully initialized search engine with text search only")
        
        # Get stats
        stats = await engine.get_stats()
        logger.info(f"Search engine stats: {stats}")
        
        # Clean up
        engine.close()
        
        # Try with vector search if dependencies are available
        try:
            engine = SearchEngine(db_path=temp_db.name, enable_vector_search=True)
            logger.info("✅ Successfully initialized search engine with vector search")
            
            # Get stats
            stats = await engine.get_stats()
            logger.info(f"Search engine stats with vector search: {stats}")
            
            # Clean up
            engine.close()
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize vector search: {e}")
            logger.info("This is expected if vector search dependencies are not installed")
        
        # Clean up
        os.unlink(temp_db.name)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize search engine: {e}")
        return False

async def test_document_indexing(SearchEngine):
    """Test document indexing functionality."""
    try:
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        
        # Initialize search engine
        engine = SearchEngine(db_path=temp_db.name, enable_vector_search=False)
        
        # Create test documents
        documents = [
            {
                "cid": "QmTest1",
                "text": "This is a test document about artificial intelligence.",
                "title": "AI Test",
                "content_type": "text/plain",
                "metadata": {
                    "author": "Test Author",
                    "tags": ["ai", "test"]
                }
            },
            {
                "cid": "QmTest2",
                "text": "IPFS is a distributed file system for storing and accessing files.",
                "title": "IPFS Overview",
                "content_type": "text/plain",
                "metadata": {
                    "author": "IPFS Team",
                    "tags": ["ipfs", "distributed", "storage"]
                }
            },
            {
                "cid": "QmTest3",
                "text": "Machine learning is a subset of artificial intelligence.",
                "title": "ML Basics",
                "content_type": "text/plain",
                "metadata": {
                    "author": "ML Expert",
                    "tags": ["ml", "ai", "learning"]
                }
            }
        ]
        
        # Index documents
        for doc in documents:
            success = await engine.index_document(
                cid=doc["cid"],
                text=doc["text"],
                title=doc["title"],
                content_type=doc["content_type"],
                metadata=doc["metadata"]
            )
            if success:
                logger.info(f"✅ Successfully indexed document {doc['cid']}")
            else:
                logger.error(f"❌ Failed to index document {doc['cid']}")
                return False
        
        # Get stats to verify documents were indexed
        stats = await engine.get_stats()
        if stats.get("document_count") != len(documents):
            logger.error(f"❌ Expected {len(documents)} documents, got {stats.get('document_count')}")
            return False
        
        logger.info(f"✅ Successfully indexed {len(documents)} documents")
        
        # Clean up
        engine.close()
        os.unlink(temp_db.name)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to test document indexing: {e}")
        return False

async def test_text_search(SearchEngine):
    """Test text search functionality."""
    try:
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        
        # Initialize search engine
        engine = SearchEngine(db_path=temp_db.name, enable_vector_search=False)
        
        # Create test documents
        documents = [
            {
                "cid": "QmTest1",
                "text": "This is a test document about artificial intelligence.",
                "title": "AI Test",
                "content_type": "text/plain",
                "metadata": {
                    "author": "Test Author",
                    "tags": ["ai", "test"]
                }
            },
            {
                "cid": "QmTest2",
                "text": "IPFS is a distributed file system for storing and accessing files.",
                "title": "IPFS Overview",
                "content_type": "text/plain",
                "metadata": {
                    "author": "IPFS Team",
                    "tags": ["ipfs", "distributed", "storage"]
                }
            },
            {
                "cid": "QmTest3",
                "text": "Machine learning is a subset of artificial intelligence.",
                "title": "ML Basics",
                "content_type": "text/plain",
                "metadata": {
                    "author": "ML Expert",
                    "tags": ["ml", "ai", "learning"]
                }
            }
        ]
        
        # Index documents
        for doc in documents:
            await engine.index_document(
                cid=doc["cid"],
                text=doc["text"],
                title=doc["title"],
                content_type=doc["content_type"],
                metadata=doc["metadata"]
            )
        
        # Test simple text search
        results = await engine.search_text("artificial intelligence")
        if len(results) != 2:
            logger.error(f"❌ Expected 2 results for 'artificial intelligence', got {len(results)}")
            return False
        
        # Check that the results contain the expected documents
        cids = [result["cid"] for result in results]
        if "QmTest1" not in cids or "QmTest3" not in cids:
            logger.error(f"❌ Expected results to contain QmTest1 and QmTest3, got {cids}")
            return False
        
        logger.info("✅ Basic text search successful")
        
        # Test metadata filtering
        results = await engine.search_text(
            "artificial intelligence",
            metadata_filters={"tags": ["ai"]}
        )
        if len(results) != 2:
            logger.error(f"❌ Expected 2 results with tag 'ai', got {len(results)}")
            return False
        
        logger.info("✅ Text search with metadata filtering successful")
        
        # Test empty query with metadata filtering
        results = await engine.search_text(
            "",
            metadata_filters={"author": "IPFS Team"}
        )
        if len(results) != 1 or results[0]["cid"] != "QmTest2":
            logger.error(f"❌ Expected 1 result with author 'IPFS Team', got {len(results)}")
            return False
        
        logger.info("✅ Metadata-only filtering successful")
        
        # Clean up
        engine.close()
        os.unlink(temp_db.name)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to test text search: {e}")
        return False

async def test_vector_search(SearchEngine):
    """Test vector search functionality if available."""
    try:
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        
        # Try to initialize search engine with vector search
        try:
            engine = SearchEngine(db_path=temp_db.name, enable_vector_search=True)
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize vector search: {e}")
            logger.info("Skipping vector search test (this is expected if dependencies are not installed)")
            os.unlink(temp_db.name)
            return True
        
        if not engine.enable_vector_search:
            logger.info("Vector search is disabled, skipping test")
            engine.close()
            os.unlink(temp_db.name)
            return True
        
        # Create test documents
        documents = [
            {
                "cid": "QmTest1",
                "text": "This is a test document about artificial intelligence.",
                "title": "AI Test",
                "content_type": "text/plain",
                "metadata": {
                    "author": "Test Author",
                    "tags": ["ai", "test"]
                }
            },
            {
                "cid": "QmTest2",
                "text": "IPFS is a distributed file system for storing and accessing files.",
                "title": "IPFS Overview",
                "content_type": "text/plain",
                "metadata": {
                    "author": "IPFS Team",
                    "tags": ["ipfs", "distributed", "storage"]
                }
            },
            {
                "cid": "QmTest3",
                "text": "Machine learning is a subset of artificial intelligence.",
                "title": "ML Basics",
                "content_type": "text/plain",
                "metadata": {
                    "author": "ML Expert",
                    "tags": ["ml", "ai", "learning"]
                }
            }
        ]
        
        # Index documents
        for doc in documents:
            await engine.index_document(
                cid=doc["cid"],
                text=doc["text"],
                title=doc["title"],
                content_type=doc["content_type"],
                metadata=doc["metadata"]
            )
        
        # Test vector search
        results = await engine.search_vector("AI and machine learning")
        if len(results) < 1:
            logger.error(f"❌ Expected at least 1 result for vector search, got {len(results)}")
            return False
        
        logger.info(f"✅ Vector search returned {len(results)} results")
        logger.info(f"Top result: {results[0]['cid']} - Score: {results[0]['score']}")
        
        # Test hybrid search
        results = await engine.search_hybrid("artificial intelligence")
        if len(results) < 1:
            logger.error(f"❌ Expected at least 1 result for hybrid search, got {len(results)}")
            return False
        
        logger.info(f"✅ Hybrid search returned {len(results)} results")
        logger.info(f"Top result: {results[0]['cid']} - Score: {results[0]['score']}")
        
        # Clean up
        engine.close()
        os.unlink(temp_db.name)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to test vector search: {e}")
        return False

async def main():
    """Run all search verification tests."""
    logger.info("\n=== SEARCH INTEGRATION VERIFICATION ===\n")
    
    # Test 1: Import the search module
    import_success, SearchEngine = await test_search_imports()
    if not import_success:
        logger.error("❌ Search module import test failed")
        return False
    
    # Test 2: Search engine initialization
    if not await test_search_engine_initialization(SearchEngine):
        logger.error("❌ Search engine initialization test failed")
        return False
    
    # Test 3: Document indexing
    if not await test_document_indexing(SearchEngine):
        logger.error("❌ Document indexing test failed")
        return False
    
    # Test 4: Text search
    if not await test_text_search(SearchEngine):
        logger.error("❌ Text search test failed")
        return False
    
    # Test 5: Vector search
    if not await test_vector_search(SearchEngine):
        logger.error("❌ Vector search test failed")
        return False
    
    logger.info("\n=== TEST RESULT ===")
    logger.info("✅ All Search Integration tests passed!")
    logger.info("The search functionality has been successfully verified.")
    
    return True

if __name__ == "__main__":
    anyio.run(main)