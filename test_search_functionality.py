#!/usr/bin/env python3
"""
MCP Search functionality test script.

This script demonstrates how to use the search capabilities of the MCP server,
including indexing content, performing text searches, vector searches, and
hybrid searches.
"""

import os
import sys
import time
import json
import random
import argparse
import logging
import requests
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Parse arguments
parser = argparse.ArgumentParser(description='Test MCP Search functionality')
parser.add_argument('--host', type=str, default='localhost', help='MCP Server host')
parser.add_argument('--port', type=int, default=9997, help='MCP Server port')
parser.add_argument('--api-prefix', type=str, default='/api/v0', help='API prefix')
args = parser.parse_args()

# Constants
HOST = args.host
PORT = args.port
API_PREFIX = args.api_prefix
BASE_URL = f"http://{HOST}:{PORT}{API_PREFIX}"

# Example document content for testing
EXAMPLE_DOCUMENTS = [
    {
        "title": "Introduction to IPFS",
        "content": """
        IPFS (InterPlanetary File System) is a protocol and peer-to-peer network for storing and sharing data in a distributed file system.
        IPFS uses content-addressing to uniquely identify each file in a global namespace connecting all computing devices.
        IPFS allows users to host and receive content in a manner similar to BitTorrent.
        """,
        "tags": ["ipfs", "p2p", "distributed", "tutorial"],
        "content_type": "text/plain"
    },
    {
        "title": "Understanding Content Addressing",
        "content": """
        Content addressing is a way to find data in a network using its content rather than its location.
        In IPFS, files are identified by their content, not by where they're stored.
        When you add a file to IPFS, your file is split into smaller chunks, cryptographically hashed, and given a unique fingerprint called a CID (Content Identifier).
        CIDs are based on the content's cryptographic hash. That means:
        - Any change in content will change the CID
        - The same content will always have the same CID
        - Content cannot be changed without creating a new CID
        """,
        "tags": ["cid", "content-addressing", "ipfs", "technical"],
        "content_type": "text/plain"
    },
    {
        "title": "Working with MFS (Mutable File System)",
        "content": """
        The Mutable File System (MFS) is a feature in IPFS that allows you to work with files and directories as if you were using a traditional file system.
        MFS provides a way to add, remove, and move around files while maintaining the immutable, content-addressed nature of IPFS.
        MFS keeps track of changes to your files and directories over time, like a version control system.
        Key MFS commands include:
        - ipfs files write: Write to a file in MFS
        - ipfs files read: Read a file from MFS
        - ipfs files mkdir: Create a directory in MFS
        - ipfs files ls: List directory contents in MFS
        - ipfs files cp: Copy files in MFS
        - ipfs files mv: Move files in MFS
        """,
        "tags": ["mfs", "ipfs", "tutorial", "files"],
        "content_type": "text/plain"
    },
    {
        "title": "IPFS and Filecoin Integration",
        "content": """
        IPFS and Filecoin are complementary protocols for storing and sharing data in a decentralized network.
        IPFS addresses content and moves it around the network, while Filecoin is an incentive layer that puts IPFS content in long-term storage.
        Filecoin provides economic incentives to ensure files are stored reliably over time.
        The relationship between IPFS and Filecoin:
        - IPFS lets you address content by what's in it, not where it is
        - Filecoin lets you store content with miners that compete on price and reliability
        - Both use the same addressing format (CIDs)
        - Filecoin's blockchain provides cryptographic proof that your data is being stored correctly
        """,
        "tags": ["filecoin", "ipfs", "storage", "blockchain"],
        "content_type": "text/plain"
    },
    {
        "title": "Setting up a Private IPFS Network",
        "content": """
        A private IPFS network is isolated from the public IPFS network and only nodes with the correct swarm key can join.
        Steps to create a private IPFS network:
        1. Create a swarm key that will be shared by all nodes in your network
        2. Initialize IPFS with a custom profile for private networks
        3. Configure bootstrap nodes specific to your private network
        4. Start the IPFS daemon with the custom configurations
        Private networks are useful for:
        - Enterprise environments that need data privacy
        - Development and testing environments
        - Applications that require controlled content distribution
        - Networks with specific performance or security requirements
        """,
        "tags": ["ipfs", "private-network", "tutorial", "enterprise"],
        "content_type": "text/plain"
    }
]

def check_mcp_server() -> bool:
    """Check if MCP server is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("MCP server is running")
            return True
        else:
            logger.error(f"MCP server returned status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}")
        return False

def check_search_extension() -> bool:
    """Check if search extension is available."""
    try:
        response = requests.get(f"{BASE_URL}/search/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Search extension status: {data['status']}")
            return data.get('success', False)
        else:
            logger.error(f"Search extension returned status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking search extension: {e}")
        return False

def add_to_ipfs(content: str, filename: str = "example.txt") -> Optional[str]:
    """Add content to IPFS and return the CID."""
    try:
        # Create a temporary file with the content
        with open(filename, "w") as f:
            f.write(content)
        
        # Add the file to IPFS
        files = {'file': open(filename, 'rb')}
        response = requests.post(f"{BASE_URL}/ipfs/add", files=files)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('cid')
            else:
                logger.error(f"Error adding to IPFS: {data.get('error')}")
                return None
        else:
            logger.error(f"Error adding to IPFS, status code: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error adding to IPFS: {e}")
        return None
    finally:
        # Clean up temporary file
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except:
            pass

def index_content(cid: str, metadata: Dict[str, Any]) -> bool:
    """Index content in the search system."""
    try:
        # Prepare the form data
        form_data = {
            'cid': cid,
            'name': metadata.get('title', ''),
            'description': metadata.get('description', ''),
            'tags': json.dumps(metadata.get('tags', [])),
            'content_type': metadata.get('content_type', 'text/plain'),
            'size': len(metadata.get('content', '')),
            'created': time.time(),
            'extract_text': 'true',
            'create_embedding': 'true'
        }
        
        # Send the indexing request
        response = requests.post(f"{BASE_URL}/search/index", data=form_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                logger.info(f"Successfully indexed content with CID: {cid}")
                return True
            else:
                logger.error(f"Error indexing content: {data.get('error')}")
                return False
        else:
            logger.error(f"Error indexing content, status code: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error indexing content: {e}")
        return False

def perform_text_search(query: str) -> Dict[str, Any]:
    """Perform a text-based search."""
    try:
        # Prepare the search query
        search_query = {
            'query_text': query,
            'vector_search': False,
            'hybrid_search': False,
            'max_results': 10
        }
        
        # Send the search request
        response = requests.post(f"{BASE_URL}/search/query", json=search_query)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error performing text search, status code: {response.status_code}")
            return {'success': False, 'error': f"HTTP error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Error performing text search: {e}")
        return {'success': False, 'error': str(e)}

def perform_vector_search(query: str) -> Dict[str, Any]:
    """Perform a vector-based search."""
    try:
        # Prepare the search query
        search_query = {
            'text': query,
            'min_score': 0.5,
            'max_results': 10
        }
        
        # Send the search request
        response = requests.post(f"{BASE_URL}/search/vector", json=search_query)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error performing vector search, status code: {response.status_code}")
            return {'success': False, 'error': f"HTTP error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Error performing vector search: {e}")
        return {'success': False, 'error': str(e)}

def perform_hybrid_search(query: str) -> Dict[str, Any]:
    """Perform a hybrid search (combining text and vector)."""
    try:
        # Prepare the search query
        search_query = {
            'query_text': query,
            'vector_search': True,
            'hybrid_search': True,
            'min_score': 0.3,
            'max_results': 10
        }
        
        # Send the search request
        response = requests.post(f"{BASE_URL}/search/hybrid", json=search_query)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error performing hybrid search, status code: {response.status_code}")
            return {'success': False, 'error': f"HTTP error: {response.status_code}"}
    except Exception as e:
        logger.error(f"Error performing hybrid search: {e}")
        return {'success': False, 'error': str(e)}

def print_search_results(results: Dict[str, Any], search_type: str) -> None:
    """Print search results in a readable format."""
    print(f"\n===== {search_type.upper()} SEARCH RESULTS =====")
    print(f"Query: {results.get('query', 'N/A')}")
    print(f"Search type: {results.get('search_type', 'N/A')}")
    print(f"Found {results.get('count', 0)} results\n")
    
    if results.get('success') and results.get('results'):
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. {result.get('name', 'Untitled')} (CID: {result.get('cid', 'Unknown')})")
            print(f"   Score: {result.get('score', 0):.4f}")
            print(f"   Tags: {', '.join(result.get('tags', []))}")
            print(f"   Content type: {result.get('content_type', 'Unknown')}")
            print()
    elif not results.get('success'):
        print(f"ERROR: {results.get('error', 'Unknown error')}")
    else:
        print("No results found.")

def main():
    """Run the MCP search test."""
    logger.info("Starting MCP search functionality test")
    
    # Check MCP server
    if not check_mcp_server():
        logger.error("MCP server is not running. Please start it first.")
        sys.exit(1)
    
    # Check search extension
    if not check_search_extension():
        logger.error("Search extension is not available. Please check the MCP server configuration.")
        sys.exit(1)
    
    # Add and index example documents
    logger.info("Adding and indexing example documents...")
    indexed_cids = []
    
    for doc in EXAMPLE_DOCUMENTS:
        print(f"Adding document: {doc['title']}")
        cid = add_to_ipfs(doc['content'], f"{doc['title'].replace(' ', '_')}.txt")
        if cid:
            success = index_content(cid, doc)
            if success:
                indexed_cids.append(cid)
                print(f"Successfully indexed document with CID: {cid}")
            else:
                print(f"Failed to index document with CID: {cid}")
        else:
            print(f"Failed to add document to IPFS: {doc['title']}")
    
    if not indexed_cids:
        logger.error("No documents were successfully indexed. Exiting.")
        sys.exit(1)
    
    print(f"\nSuccessfully indexed {len(indexed_cids)} documents.")
    
    # Wait a moment for indexing to complete
    print("Waiting for indexing to complete...")
    time.sleep(2)
    
    # Perform text search
    text_query = "ipfs content addressing"
    print(f"\nPerforming text search for: '{text_query}'")
    text_results = perform_text_search(text_query)
    print_search_results(text_results, "text")
    
    # Perform vector search if available
    vector_query = "how does content addressing work in ipfs"
    print(f"\nPerforming vector search for: '{vector_query}'")
    vector_results = perform_vector_search(vector_query)
    if vector_results.get('success', False):
        print_search_results(vector_results, "vector")
    else:
        print("Vector search is not available or failed.")
        print(f"Error: {vector_results.get('error', 'Unknown error')}")
    
    # Perform hybrid search if available
    hybrid_query = "ipfs private network setup"
    print(f"\nPerforming hybrid search for: '{hybrid_query}'")
    hybrid_results = perform_hybrid_search(hybrid_query)
    if hybrid_results.get('success', False):
        print_search_results(hybrid_results, "hybrid")
    else:
        print("Hybrid search is not available or failed.")
        print(f"Error: {hybrid_results.get('error', 'Unknown error')}")
    
    print("\nMCP search functionality test completed.")

if __name__ == "__main__":
    main()