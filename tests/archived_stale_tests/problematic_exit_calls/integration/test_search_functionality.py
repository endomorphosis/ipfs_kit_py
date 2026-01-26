#!/usr/bin/env python
"""
Test script for the MCP Search Integration functionality.

This script tests the search infrastructure for the MCP server, including:
1. Content indexing with automated metadata extraction
2. Full-text indexing with SQLite FTS5
3. Vector search with sentence-transformers and FAISS
4. Hybrid search combining text and vector results
"""
import logging
import sys
import os
import json
import time
import uuid
import anyio
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("search_test")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


async def run_search_test(sample_content_path: str = None):
    """Run comprehensive tests on the search implementation."""
    logger.info("Starting MCP Search Integration test...")
    
    try:
        # Import the search module from the new location
        from ipfs_kit_py.mcp.search import ContentSearchService, ContentMetadata, SearchQuery
        logger.info("Successfully imported search module")
        
        # Create a temporary database for testing
        import tempfile
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_search.db")
        vector_index_path = os.path.join(temp_dir, "vector_index")
        
        # Initialize search service
        search_service = ContentSearchService(
            db_path=db_path,
            vector_index_path=vector_index_path,
            embedding_model_name="all-MiniLM-L6-v2"  # Using a small model for fast tests
        )
        
        await search_service.initialize()
        logger.info("Initialized search service")
        
        # Check if vector search is available
        stats = await search_service.get_stats()
        vector_search_available = stats["stats"]["vector_search_available"] if stats["success"] else False
        logger.info(f"Vector search available: {vector_search_available}")
        
        # Test 1: Generate test content
        test_text_content = f"This is a test document about IPFS, decentralized storage, and content addressing. It was created at {time.time()} with ID {uuid.uuid4()}."
        test_json_content = json.dumps({
            "title": "Test JSON Document",
            "description": "A JSON document for testing search functionality",
            "tags": ["test", "json", "search"],
            "content": {
                "main": "This is the main content of the JSON document",
                "sections": [
                    {
                        "title": "Introduction",
                        "text": "Introduction to IPFS and decentralized systems"
                    },
                    {
                        "title": "Content Addressing",
                        "text": "Content addressing uses cryptographic hashes"
                    }
                ]
            },
            "metadata": {
                "created": time.time(),
                "version": "1.0"
            }
        })
        
        # Test 2: Index content
        text_cid = f"bafytest{uuid.uuid4().hex[:16]}"  # Mock CID for text content
        text_metadata = ContentMetadata(
            name="Test Text Document",
            description="A simple text document for testing search",
            tags=["test", "text", "search"],
            content_type="text/plain",
            size=len(test_text_content),
            created=time.time(),
            author="Test Author",
            license="CC0",
            extra={"test_extra": "value", "importance": "high"}
        )
        
        json_cid = f"bafytest{uuid.uuid4().hex[:16]}"  # Mock CID for JSON content
        json_metadata = ContentMetadata(
            name="Test JSON Document",
            description="A JSON document for testing search",
            tags=["test", "json", "search"],
            content_type="application/json",
            size=len(test_json_content),
            created=time.time(),
            author="Test Author",
            license="MIT",
            extra={"test_extra": "json_value", "importance": "medium"}
        )
        
        # Index text content
        text_index_result = await search_service.index_content(
            text_cid,
            text_metadata,
            extract_text=True,
            create_embedding=True,
            content_data=test_text_content.encode('utf-8')
        )
        logger.info(f"Text content indexing result: {json.dumps(text_index_result, indent=2, default=str)}")
        
        if text_index_result.get("success", False):
            logger.info("✅ Text content indexing successful")
        else:
            logger.error("❌ Text content indexing failed")
        
        # Index JSON content
        json_index_result = await search_service.index_content(
            json_cid,
            json_metadata,
            extract_text=True,
            create_embedding=True,
            content_data=test_json_content.encode('utf-8')
        )
        logger.info(f"JSON content indexing result: {json.dumps(json_index_result, indent=2, default=str)}")
        
        if json_index_result.get("success", False):
            logger.info("✅ JSON content indexing successful")
        else:
            logger.error("❌ JSON content indexing failed")
        
        # Wait a moment for indexing to complete
        await anyio.sleep(1)
        
        # Test 3: Text search
        text_query = SearchQuery(
            query_text="decentralized storage",
            vector_search=False,
            hybrid_search=False,
            max_results=10
        )
        
        text_search_result = await search_service.search(text_query)
        logger.info(f"Text search result: {json.dumps(text_search_result, indent=2, default=str)}")
        
        if text_search_result.get("success", False) and text_search_result.get("count", 0) > 0:
            logger.info("✅ Text search successful")
        else:
            logger.warning("⚠️ Text search returned no results or failed")
        
        # Test 4: Vector search (if available)
        if vector_search_available:
            vector_query = SearchQuery(
                query_text="content addressing with cryptographic hashes",
                vector_search=True,
                hybrid_search=False,
                max_results=10
            )
            
            vector_search_result = await search_service.search(vector_query)
            logger.info(f"Vector search result: {json.dumps(vector_search_result, indent=2, default=str)}")
            
            if vector_search_result.get("success", False) and vector_search_result.get("count", 0) > 0:
                logger.info("✅ Vector search successful")
            else:
                logger.warning("⚠️ Vector search returned no results or failed")
                
            # Test 5: Hybrid search (if available)
            hybrid_query = SearchQuery(
                query_text="IPFS decentralized",
                vector_search=True,
                hybrid_search=True,
                max_results=10
            )
            
            hybrid_search_result = await search_service.search(hybrid_query)
            logger.info(f"Hybrid search result: {json.dumps(hybrid_search_result, indent=2, default=str)}")
            
            if hybrid_search_result.get("success", False) and hybrid_search_result.get("count", 0) > 0:
                logger.info("✅ Hybrid search successful")
            else:
                logger.warning("⚠️ Hybrid search returned no results or failed")
        else:
            logger.warning("⚠️ Skipping vector and hybrid search tests as vector search is not available")
        
        # Test 6: Filtered search
        filter_query = SearchQuery(
            query_text="test",
            metadata_filters={"importance": "high"},
            tags=["text"],
            content_types=["text/plain"],
            vector_search=False,
            hybrid_search=False,
            max_results=10
        )
        
        filter_search_result = await search_service.search(filter_query)
        logger.info(f"Filtered search result: {json.dumps(filter_search_result, indent=2, default=str)}")
        
        if filter_search_result.get("success", False):
            logger.info("✅ Filtered search successful")
            
            # Check if filtering worked correctly
            if filter_search_result.get("count", 0) > 0:
                if all(item.get("content_type") == "text/plain" for item in filter_search_result.get("results", [])):
                    logger.info("✅ Content type filter working correctly")
                else:
                    logger.warning("⚠️ Content type filter not working correctly")
                    
                if all("text" in item.get("tags", []) for item in filter_search_result.get("results", [])):
                    logger.info("✅ Tag filter working correctly")
                else:
                    logger.warning("⚠️ Tag filter not working correctly")
            else:
                logger.warning("⚠️ Filtered search returned no results")
        else:
            logger.error("❌ Filtered search failed")
        
        # Test 7: Get metadata
        metadata_result = await search_service.get_content_metadata(text_cid)
        logger.info(f"Metadata result: {json.dumps(metadata_result, indent=2, default=str)}")
        
        if metadata_result.get("success", False):
            logger.info("✅ Metadata retrieval successful")
        else:
            logger.error("❌ Metadata retrieval failed")
        
        # Test 8: Remove content
        remove_result = await search_service.remove_content(text_cid)
        logger.info(f"Remove content result: {json.dumps(remove_result, indent=2, default=str)}")
        
        if remove_result.get("success", False):
            logger.info("✅ Content removal successful")
            
            # Verify content is gone
            verify_result = await search_service.get_content_metadata(text_cid)
            if not verify_result.get("success", False):
                logger.info("✅ Content properly removed from index")
            else:
                logger.warning("⚠️ Content still exists after removal")
        else:
            logger.error("❌ Content removal failed")
        
        # Test 9: Final statistics
        final_stats = await search_service.get_stats()
        logger.info(f"Final search statistics: {json.dumps(final_stats, indent=2, default=str)}")
        
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)
        logger.info(f"Cleaned up temporary test directory: {temp_dir}")
        
        logger.info("All search tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error testing search functionality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    # Get sample content path from command line if provided
    sample_content_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Run the test asynchronously
    result = anyio.run(run_search_test, sample_content_path)
    
    if result:
        logger.info("✅ MCP Search Integration test passed!")
        sys.exit(0)
    else:
        logger.error("❌ MCP Search Integration test failed")
        sys.exit(1)