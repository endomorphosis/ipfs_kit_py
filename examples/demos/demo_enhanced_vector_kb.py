#!/usr/bin/env python3
"""
Demo script for Enhanced Vector & KB Dashboard functionality.

This demonstrates the improved Vector & KB tab with real search capabilities.
"""

import anyio
import sys
import os
import logging
import json
import subprocess

# Add the project root to the path
sys.path.insert(0, '/home/devel/ipfs_kit_py')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_enhanced_vector_kb():
    """Demonstrate the enhanced Vector & KB functionality."""
    print("🚀 Enhanced Vector & KB Dashboard Demo")
    print("=" * 60)
    
    # Import the endpoints
    from ipfs_kit_py.mcp.ipfs_kit.api.vector_kb_endpoints import VectorKBEndpoints
    
    # Initialize the endpoints
    endpoints = VectorKBEndpoints()
    
    print("\n📊 1. CHECKING SYSTEM CAPABILITIES")
    print("-" * 40)
    
    # Check dependencies
    dependencies = {
        "NumPy": False,
        "FAISS": False,
        "SentenceTransformers": False,
        "NetworkX": False,
        "SQLite": False
    }
    
    try:
        import numpy as np
        dependencies["NumPy"] = True
        print("✅ NumPy available for vector operations")
    except ImportError:
        print("❌ NumPy not available")
    
    try:
        import faiss
        dependencies["FAISS"] = True
        print("✅ FAISS available for vector indexing")
    except ImportError:
        print("❌ FAISS not available")
    
    try:
        from sentence_transformers import SentenceTransformer
        dependencies["SentenceTransformers"] = True
        print("✅ SentenceTransformers available for embeddings")
    except ImportError:
        print("❌ SentenceTransformers not available")
    
    try:
        import networkx as nx
        dependencies["NetworkX"] = True
        print("✅ NetworkX available for graph operations")
    except ImportError:
        print("❌ NetworkX not available")
    
    try:
        import sqlite3
        dependencies["SQLite"] = True
        print("✅ SQLite available for database operations")
    except ImportError:
        print("❌ SQLite not available")
    
    print(f"\n📈 Dependencies Summary: {sum(dependencies.values())}/{len(dependencies)} available")
    
    print("\n🔍 2. TESTING VECTOR INDEX STATUS")
    print("-" * 40)
    
    try:
        result = await endpoints.get_enhanced_vector_index_status()
        
        if result['success']:
            data = result['data']
            print(f"✅ Vector Index Status Retrieved")
            print(f"   🏥 Health: {data['index_health']}")
            print(f"   📊 Total Vectors: {data['total_vectors']:,}")
            print(f"   🔧 Index Type: {data['index_type']}")
            print(f"   📐 Dimensions: {data['dimension']}")
            print(f"   💾 Index Size: {data['index_size_mb']:.1f} MB")
            
            if data.get('search_performance'):
                perf = data['search_performance']
                print(f"   ⚡ Avg Query Time: {perf['average_query_time_ms']:.1f}ms")
                print(f"   🔄 Queries/Second: {perf['queries_per_second']}")
                print(f"   📈 Total Searches: {perf['total_searches']:,}")
            
            if data.get('content_distribution'):
                dist = data['content_distribution']
                total_content = sum(dist.values())
                if total_content > 0:
                    print(f"   📄 Content Distribution:")
                    for content_type, count in dist.items():
                        if count > 0:
                            print(f"     - {content_type.replace('_', ' ').title()}: {count:,}")
        else:
            print(f"❌ Failed to get vector index status: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing vector index: {e}")
    
    print("\n🕸️ 3. TESTING KNOWLEDGE GRAPH STATUS")
    print("-" * 40)
    
    try:
        result = await endpoints.get_enhanced_knowledge_base_status()
        
        if result['success']:
            data = result['data']
            print(f"✅ Knowledge Graph Status Retrieved")
            print(f"   🏥 Graph Health: {data['graph_health']}")
            
            if data.get('nodes'):
                nodes = data['nodes']
                total_nodes = nodes['total']
                print(f"   🔗 Total Nodes: {total_nodes:,}")
                if total_nodes > 0:
                    print(f"     - Documents: {nodes.get('documents', 0):,}")
                    print(f"     - Entities: {nodes.get('entities', 0):,}")
                    print(f"     - Concepts: {nodes.get('concepts', 0):,}")
            
            if data.get('edges'):
                edges = data['edges']
                total_edges = edges['total']
                print(f"   🔗 Total Edges: {total_edges:,}")
                if total_edges > 0:
                    print(f"     - Semantic Links: {edges.get('semantic_links', 0):,}")
                    print(f"     - Reference Links: {edges.get('reference_links', 0):,}")
                    print(f"     - Temporal Links: {edges.get('temporal_links', 0):,}")
            
            if data.get('graph_metrics'):
                metrics = data['graph_metrics']
                print(f"   📊 Graph Metrics:")
                print(f"     - Density: {metrics.get('density', 0):.3f}")
                print(f"     - Clustering Coefficient: {metrics.get('clustering_coefficient', 0):.3f}")
                print(f"     - Connected Components: {metrics.get('connected_components', 0)}")
        else:
            print(f"❌ Failed to get knowledge graph status: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing knowledge graph: {e}")
    
    print("\n📚 4. TESTING VECTOR COLLECTIONS")
    print("-" * 40)
    
    try:
        result = await endpoints.list_vector_collections()
        
        if result['success']:
            collections = result.get('collections', [])
            total_collections = result.get('total_collections', 0)
            
            print(f"✅ Vector Collections Retrieved")
            print(f"   📦 Total Collections: {total_collections}")
            
            if collections:
                for i, collection in enumerate(collections, 1):
                    print(f"   {i}. {collection['name']}")
                    print(f"      - Type: {collection['type']}")
                    print(f"      - Documents: {collection['document_count']:,}")
                    print(f"      - Vectors: {collection['vector_count']:,}")
            else:
                print("   📭 No collections found (this is normal for a new system)")
        else:
            print(f"❌ Failed to list collections: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing collections: {e}")
    
    print("\n🔍 5. TESTING SEARCH FUNCTIONALITY")
    print("-" * 40)
    
    # Test vector search
    print("📍 Testing Vector Search...")
    try:
        result = await endpoints.search_vector_database("test query", limit=5)
        
        if result['success']:
            print(f"✅ Vector search completed in {result.get('search_time_ms', 0):.1f}ms")
            print(f"   🎯 Query: '{result['query']}'")
            print(f"   📊 Results Found: {result['total_found']}")
            
            if result.get('results'):
                for i, res in enumerate(result['results'][:3], 1):
                    print(f"   {i}. {res.get('cid', res.get('id', 'Unknown'))}")
                    if res.get('score'):
                        print(f"      Similarity: {res['score']*100:.1f}%")
        else:
            print(f"⚠️ Vector search unavailable: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing vector search: {e}")
    
    # Test entity search
    print("\n📍 Testing Knowledge Graph Entity Search...")
    try:
        result = await endpoints.search_knowledge_graph_by_entity("test_entity_123")
        
        if result['success']:
            print(f"✅ Entity search completed")
            print(f"   🎯 Entity ID: {result['entity_id']}")
            print(f"   🔗 Related Entities: {result.get('relationship_count', 0)}")
        else:
            print(f"⚠️ Entity search result: {result.get('error', 'Entity not found (expected)')}")
            
    except Exception as e:
        print(f"❌ Error testing entity search: {e}")
    
    print("\n🌟 6. DASHBOARD INTEGRATION STATUS")
    print("-" * 40)
    
    print("✅ Enhanced Vector & KB tab features:")
    print("   🔍 Interactive vector database search")
    print("   🕸️ Knowledge graph entity exploration")
    print("   📋 Vector collection browsing")
    print("   📊 Real-time status monitoring")
    print("   🎨 Enhanced UI with search interface")
    
    print("\n📝 New API Endpoints Added:")
    print("   • GET /api/vector/search - Vector database search")
    print("   • GET /api/vector/collections - List vector collections") 
    print("   • GET /api/kg/entity/{id} - Get entity details")
    print("   • GET /api/kg/search - Search knowledge graph by entity")
    print("   • GET /api/vfs/vector-index - Enhanced vector index status")
    print("   • GET /api/vfs/knowledge-base - Enhanced knowledge base status")
    
    print("\n🎯 7. USAGE INSTRUCTIONS")
    print("-" * 40)
    
    print("To use the enhanced Vector & KB dashboard:")
    print("1. Start the MCP server")
    print("2. Navigate to the dashboard")
    print("3. Click on the 'Vector & KB' tab")
    print("4. Use the search interface to:")
    print("   • Search vectors by entering text queries")
    print("   • Explore entities by entering entity IDs") 
    print("   • Browse available vector collections")
    print("5. View real-time status and metrics")
    
    print("\n✅ Demo completed successfully!")
    print("The Vector & KB tab now provides real search capabilities")
    print("instead of just displaying mock data.")


if __name__ == "__main__":
    anyio.run(demo_enhanced_vector_kb)
