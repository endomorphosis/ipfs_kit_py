#!/usr/bin/env python
"""
Verification test for Search Integration in MCP.

This script tests the search functionality of the MCP server by:
1. Adding sample content to IPFS
2. Indexing the content in the search system
3. Performing various types of searches
4. Validating the search results

This addresses the "Search Integration (Reassessment Needed)" section from the mcp_roadmap.md
"""

import os
import sys
import json
import time
import uuid
import anyio
import hashlib
import logging
import tempfile
import argparse
import subprocess
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("search_verification")

# Add parent directory to path if needed
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from ipfs_kit_py.mcp.extensions.search import ContentSearchService
from ipfs_kit_py.mcp.extensions.search import ContentMetadata, SearchQuery

# Test data
TEST_DOCUMENTS = [
    {
        "name": "IPFS Introduction",
        "content": """
        The InterPlanetary File System (IPFS) is a protocol and peer-to-peer network for storing and 
        sharing data in a distributed file system. IPFS uses content-addressing to uniquely identify 
        each file in a global namespace connecting all computing devices.
        
        IPFS allows users to host and receive content in a manner similar to BitTorrent. As opposed to 
        a centrally located server, IPFS is built around a decentralized system creating a resilient 
        system of file storage and sharing.
        """,
        "tags": ["ipfs", "decentralized", "file-storage", "peer-to-peer"],
        "content_type": "text/plain",
        "author": "Test Script",
        "license": "MIT"
    },
    {
        "name": "Filecoin Overview",
        "content": """
        Filecoin is an open-source, public cryptocurrency and digital payment system intended to be 
        a blockchain-based cooperative digital storage and data retrieval method. It is made by 
        Protocol Labs and builds on top of IPFS, allowing users to rent unused hard drive space.
        
        Filecoin aims to store data in a decentralized way. Unlike cloud storage companies like 
        Amazon Web Services or Cloudflare, which are prone to the problems of centralization, 
        Filecoin leverages its decentralized nature to protect the integrity of data's location.
        """,
        "tags": ["filecoin", "blockchain", "storage", "cryptocurrency"],
        "content_type": "text/plain",
        "author": "Test Script",
        "license": "Apache-2.0"
    },
    {
        "name": "MCP Server Documentation",
        "content": """
        The Model-Controller-Persistence (MCP) server is a crucial component of the IPFS Kit ecosystem, 
        providing a unified interface for interacting with various distributed storage systems.
        
        The MCP server supports multiple backend integrations including IPFS, S3, Filecoin, Storacha,
        HuggingFace, and Lassie. It provides features such as streaming operations, search integration,
        and WebSocket notifications.
        """,
        "tags": ["mcp", "documentation", "server", "ipfs-kit"],
        "content_type": "text/markdown",
        "author": "Test Script",
        "license": "MIT"
    },
    {
        "name": "JSON Configuration Example",
        "content": json.dumps({
            "server": {
                "host": "localhost",
                "port": 8000,
                "log_level": "info"
            },
            "storage": {
                "ipfs": {
                    "enabled": True,
                    "gateway": "http://localhost:8080"
                },
                "s3": {
                    "enabled": False,
                    "region": "us-east-1",
                    "bucket": "test-bucket"
                }
            },
            "features": ["streaming", "search", "websocket"]
        }, indent=2),
        "tags": ["configuration", "json", "example"],
        "content_type": "application/json",
        "author": "Test Script",
        "license": "MIT"
    }
]

class SearchVerificationTest:
    """Test harness for verifying MCP search functionality."""
    
    def __init__(self, cleanup: bool = True):
        """
        Initialize the test harness.
        
        Args:
            cleanup: Whether to clean up test data after running
        """
        self.cleanup = cleanup
        self.test_dir = tempfile.mkdtemp(prefix="mcp_search_test_")
        
        # Create test-specific paths
        self.db_path = os.path.join(self.test_dir, "search.db")
        self.index_path = os.path.join(self.test_dir, "vector_index")
        
        # Initialize search service
        self.search_service = ContentSearchService(
            db_path=self.db_path,
            vector_index_path=self.index_path
        )
        
        # Track test content
        self.test_cids = []
    
    async def setup(self):
        """Set up test environment and data."""
        logger.info("Setting up test environment")
        
        # Create test content files
        content_files = []
        for doc in TEST_DOCUMENTS:
            file_path = os.path.join(self.test_dir, f"{doc['name'].replace(' ', '_')}.txt")
            with open(file_path, "w") as f:
                f.write(doc["content"])
            content_files.append((file_path, doc))
        
        # Add content to IPFS
        for file_path, doc in content_files:
            # Add to IPFS
            result = await anyio.run_process(
                ["ipfs", "add", "-q", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if result.returncode != 0:
                logger.error(f"Error adding file to IPFS: {result.stderr.decode()}")
                continue
            
            cid = result.stdout.decode().strip()
            logger.info(f"Added content to IPFS: {cid} ({doc['name']})")
            
            # Index in search service
            metadata = ContentMetadata(
                name=doc["name"],
                description=doc.get("description", "Test document"),
                tags=doc["tags"],
                content_type=doc["content_type"],
                size=len(doc["content"]),
                created=time.time(),
                author=doc["author"],
                license=doc["license"],
                extra={"source": "search_verification_test"}
            )
            
            result = await self.search_service.index_content(
                cid,
                metadata,
                extract_text=True,
                create_embedding=True,
                content_data=doc["content"].encode("utf-8")
            )
            
            if result["success"]:
                logger.info(f"Indexed content: {cid}")
                self.test_cids.append(cid)
            else:
                logger.error(f"Failed to index content: {result.get('error', 'Unknown error')}")
    
    async def run_tests(self):
        """Run the verification tests."""
        logger.info("Running search verification tests")
        
        # Wait for indexing to complete
        logger.info("Waiting for indexing to complete...")
        await anyio.sleep(2)
        
        # Test 1: Basic text search
        logger.info("Test 1: Basic text search")
        query = SearchQuery(
            query_text="IPFS decentralized",
            vector_search=False
        )
        
        result = await self.search_service.search(query)
        
        if result["success"] and len(result["results"]) > 0:
            logger.info(f"✅ Basic text search found {len(result['results'])} results")
            
            # Verify the first result is about IPFS
            first_result = result["results"][0]
            if "ipfs" in first_result["name"].lower() or "ipfs" in first_result.get("description", "").lower():
                logger.info("✅ First result is correctly about IPFS")
            else:
                logger.warning("⚠️ First result doesn't seem to be about IPFS")
        else:
            logger.error(f"❌ Basic text search failed: {result.get('error', 'No results')}")
        
        # Test 2: Tag filtering
        logger.info("Test 2: Tag filtering")
        query = SearchQuery(
            query_text="storage",
            tags=["blockchain"],
            vector_search=False
        )
        
        result = await self.search_service.search(query)
        
        if result["success"]:
            logger.info(f"✅ Tag filtering search found {len(result['results'])} results")
            
            if len(result["results"]) > 0:
                # Verify results contain the tag
                first_result = result["results"][0]
                if "blockchain" in first_result["tags"]:
                    logger.info("✅ Results correctly filtered by tag")
                else:
                    logger.warning("⚠️ Results don't contain the filtered tag")
        else:
            logger.error(f"❌ Tag filtering search failed: {result.get('error', 'Unknown error')}")
        
        # Test 3: Vector search (if available)
        logger.info("Test 3: Vector search")
        vector_query = SearchQuery(
            query_text="What is MCP server?",
            vector_search=True,
            hybrid_search=False
        )
        
        result = await self.search_service.search(vector_query)
        
        if result["success"]:
            if result["search_type"] == "vector" and len(result["results"]) > 0:
                logger.info(f"✅ Vector search found {len(result['results'])} results")
                
                # Verify the results contain MCP info
                found_mcp = False
                for r in result["results"]:
                    if "mcp" in r["name"].lower() or "mcp" in r.get("description", "").lower():
                        found_mcp = True
                        break
                
                if found_mcp:
                    logger.info("✅ Vector search found relevant MCP content")
                else:
                    logger.warning("⚠️ Vector search didn't find relevant MCP content")
            else:
                logger.warning(f"⚠️ Vector search not available or no results (type: {result['search_type']})")
        else:
            logger.error(f"❌ Vector search failed: {result.get('error', 'Unknown error')}")
        
        # Test 4: Hybrid search
        logger.info("Test 4: Hybrid search")
        hybrid_query = SearchQuery(
            query_text="configuration settings JSON",
            vector_search=True,
            hybrid_search=True
        )
        
        result = await self.search_service.search(hybrid_query)
        
        if result["success"]:
            if result["search_type"] == "hybrid" and len(result["results"]) > 0:
                logger.info(f"✅ Hybrid search found {len(result['results'])} results")
                
                # Verify the results contain JSON configuration
                found_json = False
                for r in result["results"]:
                    if "json" in r["tags"] or "configuration" in r["tags"]:
                        found_json = True
                        break
                
                if found_json:
                    logger.info("✅ Hybrid search found JSON configuration content")
                else:
                    logger.warning("⚠️ Hybrid search didn't find JSON configuration content")
            else:
                logger.warning(f"⚠️ Hybrid search not available or no results (type: {result['search_type']})")
        else:
            logger.error(f"❌ Hybrid search failed: {result.get('error', 'Unknown error')}")
        
        # Test 5: Get metadata
        logger.info("Test 5: Get metadata")
        
        if self.test_cids:
            test_cid = self.test_cids[0]
            metadata_result = await self.search_service.get_content_metadata(test_cid)
            
            if metadata_result["success"]:
                logger.info(f"✅ Get metadata successful for {test_cid}")
                
                # Verify metadata matches
                metadata = metadata_result["metadata"]
                if metadata["cid"] == test_cid:
                    logger.info("✅ Metadata CID matches")
                else:
                    logger.warning("⚠️ Metadata CID doesn't match")
            else:
                logger.error(f"❌ Get metadata failed: {metadata_result.get('error', 'Unknown error')}")
    
    async def cleanup_test_data(self):
        """Clean up test data."""
        logger.info("Cleaning up test data")
        
        # Remove indexed content
        for cid in self.test_cids:
            await self.search_service.remove_content(cid)
            logger.info(f"Removed indexed content: {cid}")
        
        # Remove test files
        try:
            import shutil
            shutil.rmtree(self.test_dir)
            logger.info(f"Removed test directory: {self.test_dir}")
        except Exception as e:
            logger.error(f"Error removing test directory: {e}")
    
    async def run(self):
        """Run the full verification test."""
        try:
            await self.setup()
            await self.run_tests()
            
            # Get search service stats
            stats_result = await self.search_service.get_stats()
            if stats_result["success"]:
                logger.info("Search service statistics:")
                for key, value in stats_result["stats"].items():
                    if key not in ["content_types", "tags"]:
                        logger.info(f"  {key}: {value}")
            
            if self.cleanup:
                await self.cleanup_test_data()
                
            return True
        except Exception as e:
            logger.error(f"Error running verification test: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

async def main():
    parser = argparse.ArgumentParser(description='MCP Search Verification Test')
    parser.add_argument('--no-cleanup', action='store_true', help='Do not clean up test data')
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    test = SearchVerificationTest(cleanup=not args.no_cleanup)
    success = await test.run()
    
    if success:
        logger.info("✅ Search verification test completed successfully")
        return 0
    else:
        logger.error("❌ Search verification test failed")
        return 1

if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)