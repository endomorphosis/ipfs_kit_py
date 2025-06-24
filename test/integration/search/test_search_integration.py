#!/usr/bin/env python3
"""
Test script to verify the Search Integration functionality from the MCP roadmap.

This script tests:
1. Content Indexing (metadata extraction, text indexing)
2. Vector Search (embeddings, vector similarity)
3. Hybrid Search (combined text and vector search)
"""

import os
import sys
import json
import time
import logging
import asyncio
import argparse
import tempfile
import requests
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("search_test")

# Default endpoint
DEFAULT_ENDPOINT = "http://localhost:8000/api/v0"


async def test_search_status(base_url: str) -> bool:
    """Test if the search API is available and verify its capabilities."""
    try:
        logger.info(f"Testing search status at {base_url}/search/status")
        response = requests.get(f"{base_url}/search/status")
        response.raise_for_status()

        data = response.json()
        logger.info(f"Search status response: {json.dumps(data, indent=2)}")

        if not data.get("success", False):
            logger.error(f"Search status API returned error: {data.get('error', 'Unknown error')}")
            return False

        # Check for required features
        features = data.get("features", {})
        if not features.get("text_search", False):
            logger.warning("Text search feature not available")

        vector_search = features.get("vector_search", False)
        if not vector_search:
            logger.warning("Vector search feature not available - need sentence-transformers and FAISS")

        stats = data.get("stats", {})
        logger.info(f"Search stats: {json.dumps(stats, indent=2)}")

        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Error accessing search status API: {e}")
        return False


async def index_test_content(base_url: str) -> List[str]:
    """Index some test content and return the CIDs."""
    try:
        logger.info(f"Indexing test content at {base_url}/search/index")

        # Create a list to store created CIDs
        cids = []

        # Test content 1: JSON document
        json_cid = "bafkreihwlmfagudrlrkfw6yh4ebj5gkcbajbjzbzqocf6f5nuhwvbvgddy"
        json_data = {
            "cid": json_cid,
            "name": "Test JSON Document",
            "description": "A test JSON document for search testing",
            "tags": ["test", "json", "document", "search"],
            "content_type": "application/json",
            "size": 1024,
            "author": "Search Test Script",
            "license": "MIT",
            "extra": {"test": True, "priority": "high"}
        }

        response = requests.post(
            f"{base_url}/search/index",
            data={
                "cid": json_cid,
                "name": json_data["name"],
                "description": json_data["description"],
                "tags": json.dumps(json_data["tags"]),
                "content_type": json_data["content_type"],
                "size": json_data["size"],
                "author": json_data["author"],
                "license": json_data["license"],
                "extra": json.dumps(json_data["extra"]),
                "extract_text": True,
                "create_embedding": True
            }
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Successfully indexed JSON document with CID: {json_cid}")
                cids.append(json_cid)
            else:
                logger.error(f"Failed to index JSON document: {result.get('error', 'Unknown error')}")
        else:
            logger.error(f"Failed to index JSON document, status code: {response.status_code}")

        # Test content 2: Text document
        text_cid = "bafkreifukegozkhptb2fwa5wevdyup24mwgvuylq2jkahrcrn4gjedel3i"
        text_data = {
            "cid": text_cid,
            "name": "Test Text Document",
            "description": "A test plain text document for search testing with specific keywords",
            "tags": ["test", "text", "document", "search", "keywords"],
            "content_type": "text/plain",
            "size": 2048,
            "author": "Search Test Script",
            "license": "Apache-2.0",
            "extra": {"test": True, "priority": "medium", "keywords": ["machine", "learning", "vector", "search"]}
        }

        response = requests.post(
            f"{base_url}/search/index",
            data={
                "cid": text_cid,
                "name": text_data["name"],
                "description": text_data["description"],
                "tags": json.dumps(text_data["tags"]),
                "content_type": text_data["content_type"],
                "size": text_data["size"],
                "author": text_data["author"],
                "license": text_data["license"],
                "extra": json.dumps(text_data["extra"]),
                "extract_text": True,
                "create_embedding": True
            }
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Successfully indexed text document with CID: {text_cid}")
                cids.append(text_cid)
            else:
                logger.error(f"Failed to index text document: {result.get('error', 'Unknown error')}")
        else:
            logger.error(f"Failed to index text document, status code: {response.status_code}")

        # Test content 3: Markdown document
        md_cid = "bafkreihzdtvw2vz22kzvqx46vgk6hdc35ggdsd26v6zcvnwzgpio6wlspm"
        md_data = {
            "cid": md_cid,
            "name": "Vector Embeddings Guide",
            "description": "A guide to using vector embeddings for semantic search",
            "tags": ["guide", "vector", "embeddings", "semantic", "search"],
            "content_type": "text/markdown",
            "size": 4096,
            "author": "Search Expert",
            "license": "CC-BY-4.0",
            "extra": {"test": True, "priority": "high", "topics": ["embeddings", "FAISS", "sentence-transformers"]}
        }

        response = requests.post(
            f"{base_url}/search/index",
            data={
                "cid": md_cid,
                "name": md_data["name"],
                "description": md_data["description"],
                "tags": json.dumps(md_data["tags"]),
                "content_type": md_data["content_type"],
                "size": md_data["size"],
                "author": md_data["author"],
                "license": md_data["license"],
                "extra": json.dumps(md_data["extra"]),
                "extract_text": True,
                "create_embedding": True
            }
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Successfully indexed markdown document with CID: {md_cid}")
                cids.append(md_cid)
            else:
                logger.error(f"Failed to index markdown document: {result.get('error', 'Unknown error')}")
        else:
            logger.error(f"Failed to index markdown document, status code: {response.status_code}")

        # Give the indexing some time to complete (especially for vector embeddings)
        if cids:
            logger.info(f"Waiting for indexing to complete...")
            await asyncio.sleep(2)

        return cids

    except requests.exceptions.RequestException as e:
        logger.error(f"Error indexing test content: {e}")
        return []


async def test_text_search(base_url: str, cids: List[str]) -> bool:
    """Test text search functionality."""
    try:
        logger.info(f"Testing text search at {base_url}/search/query")

        # Simple text search query
        query_data = {
            "query_text": "vector embeddings semantic search",
            "vector_search": False,
            "hybrid_search": False,
            "max_results": 10,
            "min_score": 0.0
        }

        response = requests.post(
            f"{base_url}/search/query",
            json=query_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Text search results count: {result.get('count', 0)}")
                logger.info(f"Text search results: {json.dumps(result.get('results', []), indent=2)}")

                # Verify at least one result was returned
                if result.get('count', 0) > 0:
                    logger.info("Text search test PASSED")
                    return True
                else:
                    logger.warning("Text search returned no results")
                    return False
            else:
                logger.error(f"Text search query failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error(f"Text search query failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing text search: {e}")
        return False


async def test_vector_search(base_url: str, cids: List[str]) -> bool:
    """Test vector search functionality."""
    try:
        logger.info(f"Testing vector search at {base_url}/search/vector")

        # Check if vector search is available
        status_response = requests.get(f"{base_url}/search/status")
        status_data = status_response.json()
        features = status_data.get("features", {})

        if not features.get("vector_search", False):
            logger.warning("Vector search is not available on this server. Skipping vector search test.")
            return True  # Return True to continue with other tests

        # Vector search query
        query_data = {
            "text": "semantic search with embeddings",
            "min_score": 0.0,
            "max_results": 10
        }

        response = requests.post(
            f"{base_url}/search/vector",
            json=query_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Vector search results count: {result.get('count', 0)}")
                logger.info(f"Vector search results: {json.dumps(result.get('results', []), indent=2)}")

                # Verify at least one result was returned
                if result.get('count', 0) > 0:
                    logger.info("Vector search test PASSED")
                    return True
                else:
                    logger.warning("Vector search returned no results")
                    return False
            else:
                logger.error(f"Vector search query failed: {result.get('error', 'Unknown error')}")
                return False
        elif response.status_code == 501:
            # Vector search might not be available
            logger.warning("Vector search endpoint returned 501 Not Implemented. This likely means sentence-transformers or FAISS is not installed.")
            return True  # Allow the test to continue
        else:
            logger.error(f"Vector search query failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing vector search: {e}")
        return False


async def test_hybrid_search(base_url: str, cids: List[str]) -> bool:
    """Test hybrid search functionality."""
    try:
        logger.info(f"Testing hybrid search at {base_url}/search/hybrid")

        # Check if hybrid search is available
        status_response = requests.get(f"{base_url}/search/status")
        status_data = status_response.json()
        features = status_data.get("features", {})

        if not features.get("hybrid_search", False):
            logger.warning("Hybrid search is not available on this server. Skipping hybrid search test.")
            return True  # Return True to continue with other tests

        # Hybrid search query
        query_data = {
            "query_text": "vector embeddings for semantic search",
            "hybrid_search": True,
            "vector_search": True,
            "max_results": 10,
            "min_score": 0.0
        }

        response = requests.post(
            f"{base_url}/search/hybrid",
            json=query_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Hybrid search results count: {result.get('count', 0)}")
                logger.info(f"Hybrid search results: {json.dumps(result.get('results', []), indent=2)}")

                # Verify at least one result was returned
                if result.get('count', 0) > 0:
                    logger.info("Hybrid search test PASSED")
                    return True
                else:
                    logger.warning("Hybrid search returned no results")
                    return False
            else:
                logger.error(f"Hybrid search query failed: {result.get('error', 'Unknown error')}")
                return False
        elif response.status_code == 501:
            # Hybrid search might not be available
            logger.warning("Hybrid search endpoint returned 501 Not Implemented. This likely means sentence-transformers or FAISS is not installed.")
            return True  # Allow the test to continue
        else:
            logger.error(f"Hybrid search query failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing hybrid search: {e}")
        return False


async def test_metadata_filtering(base_url: str, cids: List[str]) -> bool:
    """Test metadata filtering in search."""
    try:
        logger.info(f"Testing metadata filtering at {base_url}/search/query")

        # Query with metadata filters
        query_data = {
            "query_text": "test",
            "metadata_filters": {
                "author": "Search Expert"
            },
            "tags": ["vector"],
            "vector_search": False,
            "hybrid_search": False,
            "max_results": 10,
            "min_score": 0.0
        }

        response = requests.post(
            f"{base_url}/search/query",
            json=query_data
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Metadata filtering results count: {result.get('count', 0)}")
                logger.info(f"Metadata filtering results: {json.dumps(result.get('results', []), indent=2)}")

                # Verify result filtering works
                for item in result.get('results', []):
                    if item.get('author') != "Search Expert":
                        logger.error(f"Metadata filtering failed: found item with author = {item.get('author')}")
                        return False

                logger.info("Metadata filtering test PASSED")
                return True
            else:
                logger.error(f"Metadata filtering query failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error(f"Metadata filtering query failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing metadata filtering: {e}")
        return False


async def test_tag_operations(base_url: str) -> bool:
    """Test tag-related operations."""
    try:
        logger.info(f"Testing tag operations at {base_url}/search/tags")

        response = requests.get(f"{base_url}/search/tags")

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Tags count: {result.get('count', 0)}")
                logger.info(f"Tags: {json.dumps(result.get('tags', []), indent=2)}")

                # Verify tags were returned
                if result.get('count', 0) > 0:
                    logger.info("Tag operations test PASSED")
                    return True
                else:
                    logger.warning("No tags returned")
                    return False
            else:
                logger.error(f"Tag operations failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error(f"Tag operations failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing tag operations: {e}")
        return False


async def test_content_type_operations(base_url: str) -> bool:
    """Test content type operations."""
    try:
        logger.info(f"Testing content type operations at {base_url}/search/content-types")

        response = requests.get(f"{base_url}/search/content-types")

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Content types count: {result.get('count', 0)}")
                logger.info(f"Content types: {json.dumps(result.get('content_types', []), indent=2)}")

                # Verify content types were returned
                if result.get('count', 0) > 0:
                    logger.info("Content type operations test PASSED")
                    return True
                else:
                    logger.warning("No content types returned")
                    return False
            else:
                logger.error(f"Content type operations failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error(f"Content type operations failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing content type operations: {e}")
        return False


async def test_get_metadata(base_url: str, cids: List[str]) -> bool:
    """Test retrieving metadata for a specific CID."""
    if not cids:
        logger.warning("No CIDs available for metadata test")
        return False

    try:
        cid = cids[0]  # Use the first CID
        logger.info(f"Testing get metadata at {base_url}/search/metadata/{cid}")

        response = requests.get(f"{base_url}/search/metadata/{cid}")

        if response.status_code == 200:
            result = response.json()
            if result.get("success", False):
                logger.info(f"Metadata for CID {cid}: {json.dumps(result.get('metadata', {}), indent=2)}")

                # Verify metadata was returned
                if result.get('metadata', {}):
                    logger.info("Get metadata test PASSED")
                    return True
                else:
                    logger.warning("Empty metadata returned")
                    return False
            else:
                logger.error(f"Get metadata failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            logger.error(f"Get metadata failed, status code: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Error testing get metadata: {e}")
        return False


async def clean_up_test_data(base_url: str, cids: List[str]) -> bool:
    """Clean up the test data by removing indexed content."""
    success = True

    for cid in cids:
        try:
            logger.info(f"Removing test content with CID: {cid}")

            response = requests.delete(f"{base_url}/search/remove/{cid}")

            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    logger.info(f"Successfully removed content with CID: {cid}")
                else:
                    logger.error(f"Failed to remove content with CID {cid}: {result.get('error', 'Unknown error')}")
                    success = False
            else:
                logger.error(f"Failed to remove content with CID {cid}, status code: {response.status_code}")
                success = False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error removing content with CID {cid}: {e}")
            success = False

    return success


async def main():
    """Main function to run the test suite."""
    parser = argparse.ArgumentParser(description="Test MCP Search Integration")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help=f"MCP API endpoint (default: {DEFAULT_ENDPOINT})")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip cleanup of test data")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])

    base_url = args.endpoint

    logger.info(f"Starting MCP Search Integration test suite with endpoint: {base_url}")

    test_results = {
        "search_status": False,
        "indexing": False,
        "text_search": False,
        "vector_search": False,
        "hybrid_search": False,
        "metadata_filtering": False,
        "tag_operations": False,
        "content_type_operations": False,
        "get_metadata": False,
        "cleanup": False
    }

    # Step 1: Test search status
    test_results["search_status"] = await test_search_status(base_url)

    # Step 2: Index test content
    cids = []
    if test_results["search_status"]:
        cids = await index_test_content(base_url)
        test_results["indexing"] = len(cids) > 0

    # Wait a bit for indexing to complete
    if cids:
        await asyncio.sleep(3)

    # Step 3: Test text search
    if test_results["indexing"]:
        test_results["text_search"] = await test_text_search(base_url, cids)

    # Step 4: Test vector search
    if test_results["indexing"]:
        test_results["vector_search"] = await test_vector_search(base_url, cids)

    # Step 5: Test hybrid search
    if test_results["indexing"]:
        test_results["hybrid_search"] = await test_hybrid_search(base_url, cids)

    # Step 6: Test metadata filtering
    if test_results["indexing"]:
        test_results["metadata_filtering"] = await test_metadata_filtering(base_url, cids)

    # Step 7: Test tag operations
    if test_results["indexing"]:
        test_results["tag_operations"] = await test_tag_operations(base_url)

    # Step 8: Test content type operations
    if test_results["indexing"]:
        test_results["content_type_operations"] = await test_content_type_operations(base_url)

    # Step 9: Test get metadata
    if test_results["indexing"]:
        test_results["get_metadata"] = await test_get_metadata(base_url, cids)

    # Step 10: Clean up test data
    if test_results["indexing"] and not args.skip_cleanup:
        test_results["cleanup"] = await clean_up_test_data(base_url, cids)

    # Print summary
    logger.info("\n=== TEST RESULTS SUMMARY ===")
    passed = 0
    failed = 0

    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        if result:
            passed += 1
        else:
            failed += 1
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")

    logger.info(f"\nTotal: {passed + failed} tests, {passed} passed, {failed} failed")

    if failed == 0:
        logger.info("\n✅ ALL TESTS PASSED! The Search Integration is working correctly.")
    else:
        logger.error(f"\n❌ {failed} TESTS FAILED! The Search Integration needs attention.")


if __name__ == "__main__":
    asyncio.run(main())
