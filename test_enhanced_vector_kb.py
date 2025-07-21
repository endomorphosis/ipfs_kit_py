#!/usr/bin/env python3
"""
Test script for the enhanced Vector & KB dashboard functionality.
"""

import asyncio
import sys
import os
import logging

# Add the project root to the path
sys.path.insert(0, '/home/devel/ipfs_kit_py')

from mcp.ipfs_kit.api.vector_kb_endpoints import VectorKBEndpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_vector_kb_endpoints():
    """Test the vector and knowledge base endpoints."""
    print("Testing Enhanced Vector & KB Endpoints...")
    
    # Initialize endpoints
    endpoints = VectorKBEndpoints()
    
    print("\n1. Testing Vector Index Status...")
    try:
        result = await endpoints.get_enhanced_vector_index_status()
        print(f"   Success: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"   Index Health: {data['index_health']}")
            print(f"   Total Vectors: {data['total_vectors']}")
            print(f"   Index Type: {data['index_type']}")
            print(f"   Dimension: {data['dimension']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Testing Knowledge Base Status...")
    try:
        result = await endpoints.get_enhanced_knowledge_base_status()
        print(f"   Success: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"   Graph Health: {data['graph_health']}")
            print(f"   Total Nodes: {data['nodes']['total']}")
            print(f"   Total Edges: {data['edges']['total']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n3. Testing Vector Collections List...")
    try:
        result = await endpoints.list_vector_collections()
        print(f"   Success: {result['success']}")
        if result['success']:
            print(f"   Total Collections: {result['total_collections']}")
            for collection in result.get('collections', []):
                print(f"   - {collection['name']}: {collection['document_count']} docs")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n4. Testing Vector Search...")
    try:
        result = await endpoints.search_vector_database("test query", limit=5)
        print(f"   Success: {result['success']}")
        if result['success']:
            print(f"   Query: {result['query']}")
            print(f"   Results Found: {result['total_found']}")
            print(f"   Search Time: {result['search_time_ms']}ms")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n5. Testing Knowledge Graph Entity Search...")
    try:
        result = await endpoints.search_knowledge_graph_by_entity("test_entity_123")
        print(f"   Success: {result['success']}")
        if not result['success']:
            print(f"   Expected error (entity not found): {result['error']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\nTest completed!")


async def test_search_engine_availability():
    """Test if search engines are available."""
    print("Testing Search Engine Availability...")
    
    try:
        from ipfs_kit_py.mcp.search.mcp_search import SearchEngine
        print("✅ SearchEngine available")
        
        # Try to initialize
        search_engine = SearchEngine(enable_vector_search=True)
        print("✅ SearchEngine initialized successfully")
        
        # Check vector search capability
        if hasattr(search_engine, 'vector_model') and search_engine.vector_model:
            print("✅ Vector search model loaded")
        else:
            print("⚠️ Vector search model not available")
            
    except ImportError as e:
        print(f"❌ SearchEngine import failed: {e}")
    except Exception as e:
        print(f"❌ SearchEngine initialization failed: {e}")
    
    try:
        from ipfs_kit_py.ipld_knowledge_graph import IPLDGraphDB
        print("✅ IPLDGraphDB available")
    except ImportError as e:
        print(f"❌ IPLDGraphDB import failed: {e}")
    
    # Check optional dependencies
    try:
        import faiss
        print("✅ FAISS available for vector indexing")
    except ImportError:
        print("⚠️ FAISS not available - vector search will be limited")
    
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ SentenceTransformers available for embeddings")
    except ImportError:
        print("⚠️ SentenceTransformers not available - no text embeddings")
    
    try:
        import numpy as np
        print("✅ NumPy available for vector operations")
    except ImportError:
        print("❌ NumPy not available - vector operations will fail")


if __name__ == "__main__":
    print("Enhanced Vector & KB Dashboard Test")
    print("=" * 50)
    
    # Run availability tests
    asyncio.run(test_search_engine_availability())
    
    print("\n" + "=" * 50)
    
    # Run endpoint tests
    asyncio.run(test_vector_kb_endpoints())
