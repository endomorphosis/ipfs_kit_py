#!/usr/bin/env python3
"""
Enhanced GraphRAG MCP Server Usage Examples
==========================================

This script demonstrates practical usage of the enhanced MCP server
with VFS operations and advanced search capabilities.
"""

import json
import subprocess
import sys
import os
import tempfile
from datetime import datetime

def run_mcp_tool(tool_name, arguments=None):
    """Helper function to call MCP tools."""
    if arguments is None:
        arguments = {}
    
    venv_python = "/home/barberb/ipfs_kit_py/.venv/bin/python"
    
    # Create the MCP request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    
    # Initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "demo-client", "version": "1.0.0"}
        }
    }
    
    # Notification
    notify_request = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    }
    
    try:
        # Start server
        server_process = subprocess.Popen([
            venv_python, "mcp/enhanced_mcp_server_with_daemon_mgmt.py"
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd="/home/barberb/ipfs_kit_py")
        
        # Send requests
        requests = [
            json.dumps(init_request),
            json.dumps(notify_request),
            json.dumps(request)
        ]
        
        input_data = "\n".join(requests) + "\n"
        stdout, stderr = server_process.communicate(input=input_data, timeout=20)
        
        # Parse response
        for line in reversed(stdout.strip().split('\n')):
            if line.strip():
                try:
                    response = json.loads(line)
                    if response.get("id") == 1:
                        result = response.get("result", {})
                        if not result.get("isError"):
                            content = result.get("content", [{}])[0].get("text", "{}")
                            return json.loads(content)
                        else:
                            return {"error": f"Tool error: {result}"}
                except json.JSONDecodeError:
                    continue
        
        return {"error": "No valid response", "stderr": stderr}
        
    except subprocess.TimeoutExpired:
        server_process.kill()
        return {"error": "Timeout"}
    except Exception as e:
        return {"error": str(e)}

def demo_content_indexing():
    """Demo content indexing and search."""
    
    print("🔍 Demo: Content Indexing and Search")
    print("=" * 40)
    
    # Sample documents to index
    documents = [
        {
            "cid": "bafybeig1234ipfswhitepaper",
            "content": """IPFS Whitepaper Summary

IPFS (InterPlanetary File System) is a distributed web protocol designed to create a permanent and decentralized method of storing and sharing files. It uses content-addressing to uniquely identify each file in a global namespace connecting all computing devices.

Key features:
- Content-addressed storage
- Distributed hash table (DHT)
- Merkle DAG structure
- Peer-to-peer networking""",
            "metadata": {"type": "documentation", "topic": "ipfs", "category": "protocol"}
        },
        {
            "cid": "bafybeig5678graphragpaper",
            "content": """GraphRAG: Knowledge Graph Enhanced Retrieval

GraphRAG combines traditional retrieval-augmented generation with knowledge graphs to provide more accurate and contextual information retrieval. By leveraging structured relationships between entities, GraphRAG can traverse semantic connections to find relevant information.

Applications:
- Question answering systems
- Document analysis
- Semantic search
- Knowledge discovery""",
            "metadata": {"type": "research", "topic": "ai", "category": "machine-learning"}
        },
        {
            "cid": "bafybeig9999vectorsearch",
            "content": """Vector Search and Embeddings

Vector search uses high-dimensional numerical representations (embeddings) to find semantically similar content. Unlike keyword search, vector search understands context and meaning, enabling more accurate retrieval of relevant information.

Benefits:
- Semantic understanding
- Multilingual support  
- Fuzzy matching
- Context awareness""",
            "metadata": {"type": "tutorial", "topic": "search", "category": "technology"}
        }
    ]
    
    print("📚 1. Indexing sample documents...")
    
    # Index each document
    indexed_count = 0
    for doc in documents:
        print(f"  Indexing: {doc['cid'][:16]}...")
        
        result = run_mcp_tool("search_index_content", {
            "cid": doc["cid"],
            "path": f"/docs/{doc['cid']}.md",
            "content": doc["content"],
            "content_type": "markdown",
            "metadata": doc["metadata"]
        })
        
        if result.get("success"):
            indexed_count += 1
            print(f"    ✅ Indexed: {result.get('title', 'Untitled')}")
        else:
            print(f"    ❌ Failed: {result.get('error', 'Unknown error')}")
    
    print(f"\n📊 Indexed {indexed_count}/{len(documents)} documents")
    
    # Test searches
    search_queries = [
        ("distributed file system", "Should find IPFS content"),
        ("knowledge graphs AI", "Should find GraphRAG content"), 
        ("semantic search embeddings", "Should find vector search content"),
        ("protocol networking", "Should find IPFS and related content")
    ]
    
    print("\n🔍 2. Testing search functionality...")
    
    for query, description in search_queries:
        print(f"\n  Query: '{query}' ({description})")
        
        # Text search
        result = run_mcp_tool("search_text", {
            "query": query,
            "limit": 3
        })
        
        if result.get("success"):
            results = result.get("results", [])
            print(f"    📝 Text search: {len(results)} results")
            for r in results[:2]:
                title = r.get("title", "Untitled")
                score = r.get("relevance_score", 0)
                print(f"      - {title} (score: {score})")
        else:
            print(f"    ❌ Text search failed: {result.get('error')}")
        
        # Graph search  
        result = run_mcp_tool("search_graph", {
            "query": query,
            "max_depth": 2
        })
        
        if result.get("success"):
            results = result.get("results", [])
            print(f"    🕸️ Graph search: {len(results)} results")
            for r in results[:2]:
                title = r.get("title", "Untitled")
                score = r.get("importance_score", 0)
                print(f"      - {title} (score: {score:.3f})")
        else:
            print(f"    ❌ Graph search failed: {result.get('error')}")
    
    print("\n✅ Content indexing and search demo complete!")

def demo_vfs_integration():
    """Demo VFS operations with auto-indexing."""
    
    print("\n📁 Demo: VFS Operations with Auto-Indexing")
    print("=" * 40)
    
    # Test MFS operations (which auto-index content)
    print("📚 1. Testing MFS operations with auto-indexing...")
    
    # Create MFS directory
    result = run_mcp_tool("ipfs_files_mkdir", {
        "path": "/demo",
        "parents": True
    })
    
    if result.get("success"):
        print("  ✅ Created MFS directory: /demo")
    else:
        print(f"  ❌ Failed to create directory: {result.get('error')}")
    
    # Write content to MFS (should auto-index)
    sample_content = """# Demo Document

This is a sample document created in MFS (Mutable File System).
It demonstrates auto-indexing capabilities where content written 
to MFS is automatically indexed for search.

Topics covered:
- IPFS MFS operations
- Auto-indexing functionality
- Search integration
- Content management"""
    
    result = run_mcp_tool("ipfs_files_write", {
        "path": "/demo/auto_indexed_doc.md",
        "content": sample_content,
        "create": True
    })
    
    if result.get("success"):
        print("  ✅ Written content to MFS: /demo/auto_indexed_doc.md")
        print(f"      Bytes written: {result.get('bytes_written', 0)}")
    else:
        print(f"  ❌ Failed to write to MFS: {result.get('error')}")
    
    # Read content from MFS (should also auto-index)
    result = run_mcp_tool("ipfs_files_read", {
        "path": "/demo/auto_indexed_doc.md"
    })
    
    if result.get("success"):
        content = result.get("content", "")
        print("  ✅ Read content from MFS")
        print(f"      Content preview: {content[:50]}...")
    else:
        print(f"  ❌ Failed to read from MFS: {result.get('error')}")
    
    print("\n🔍 2. Testing search on auto-indexed content...")
    
    # Search for the auto-indexed content
    result = run_mcp_tool("search_text", {
        "query": "MFS auto-indexing",
        "limit": 5
    })
    
    if result.get("success"):
        results = result.get("results", [])
        print(f"  ✅ Search found {len(results)} results for auto-indexed content")
        for r in results:
            title = r.get("title", "Untitled")
            path = r.get("path", "Unknown")
            score = r.get("relevance_score", 0)
            print(f"    - {title} at {path} (score: {score})")
    else:
        print(f"  ❌ Search failed: {result.get('error')}")
    
    print("\n✅ VFS integration demo complete!")

def demo_search_stats():
    """Demo search statistics and capabilities."""
    
    print("\n📊 Demo: Search Statistics and Capabilities")
    print("=" * 40)
    
    result = run_mcp_tool("search_stats", {})
    
    if result.get("success", True):  # search_stats sets success=True internally
        print("📈 Current search index statistics:")
        
        # Core stats
        total_content = result.get("total_indexed_content", 0)
        print(f"  📚 Total indexed content: {total_content}")
        
        # Capabilities
        vector_available = result.get("vector_search_available", False)
        graph_available = result.get("graph_search_available", False)
        sparql_available = result.get("sparql_available", False)
        
        print(f"  🔍 Vector search: {'✅ Available' if vector_available else '❌ Unavailable'}")
        print(f"  🕸️ Graph search: {'✅ Available' if graph_available else '❌ Unavailable'}")
        print(f"  📊 SPARQL queries: {'✅ Available' if sparql_available else '❌ Unavailable'}")
        
        # Content types
        content_types = result.get("content_types", {})
        if content_types:
            print(f"  📄 Content types:")
            for ctype, count in content_types.items():
                print(f"    - {ctype}: {count}")
        
        # Graph stats
        graph_nodes = result.get("knowledge_graph_nodes", 0)
        graph_edges = result.get("knowledge_graph_edges", 0)
        rdf_triples = result.get("rdf_triples", 0)
        
        print(f"  🕸️ Knowledge graph: {graph_nodes} nodes, {graph_edges} edges")
        print(f"  📊 RDF triples: {rdf_triples}")
        
        # Entity stats
        entity_types = result.get("entity_types", {})
        if entity_types:
            print(f"  🏷️ Extracted entities:")
            for etype, count in entity_types.items():
                print(f"    - {etype}: {count}")
    
    else:
        print(f"❌ Failed to get search stats: {result.get('error')}")
    
    print("\n✅ Search statistics demo complete!")

def demo_hybrid_search():
    """Demo hybrid search combining multiple methods."""
    
    print("\n🎯 Demo: Hybrid Search")
    print("=" * 40)
    
    query = "distributed systems networking"
    print(f"🔍 Testing hybrid search for: '{query}'")
    
    result = run_mcp_tool("search_hybrid", {
        "query": query,
        "search_types": ["text", "graph"],
        "limit": 5
    })
    
    if result.get("success"):
        print("✅ Hybrid search completed successfully!")
        
        # Show individual search results
        search_results = result.get("results", {})
        for search_type, type_results in search_results.items():
            if isinstance(type_results, dict) and type_results.get("success"):
                results = type_results.get("results", [])
                print(f"\n  📋 {search_type.title()} search: {len(results)} results")
                for r in results[:2]:
                    title = r.get("title", "Untitled")
                    score_keys = ["similarity", "importance_score", "relevance_score"]
                    score = next((r.get(k, 0) for k in score_keys if k in r), 0)
                    print(f"    - {title} (score: {score:.3f})")
        
        # Show combined results
        combined = result.get("combined", {})
        if combined:
            total = combined.get("total_unique_results", 0)
            print(f"\n  🎯 Combined unique results: {total}")
            
            combined_results = combined.get("results", [])
            for r in combined_results[:3]:
                title = r.get("title", "Untitled")
                methods = ", ".join(r.get("search_methods", []))
                score = r.get("combined_score", 0)
                print(f"    - {title}")
                print(f"      Methods: {methods}, Score: {score:.3f}")
    
    else:
        print(f"❌ Hybrid search failed: {result.get('error')}")
    
    print("\n✅ Hybrid search demo complete!")

def main():
    """Run all demos."""
    
    print("🚀 Enhanced GraphRAG MCP Server Usage Examples")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Run demos
        demo_content_indexing()
        demo_vfs_integration()
        demo_search_stats()
        demo_hybrid_search()
        
        print("\n" + "=" * 60)
        print("🎉 All demos completed successfully!")
        print("\n🌟 Key Features Demonstrated:")
        print("✅ Content indexing with metadata")
        print("✅ Multiple search methods (text, graph, hybrid)")
        print("✅ VFS/MFS operations with auto-indexing")
        print("✅ Search statistics and capability reporting")
        print("✅ Knowledge graph and RDF integration")
        
        print("\n🔧 Usage Tips:")
        print("- Content is automatically indexed when accessed via VFS/MFS")
        print("- Use hybrid search for best results")
        print("- Check search_stats for current index status")
        print("- SPARQL queries work on RDF-formatted metadata")
        print("- Vector search requires sentence-transformers package")
        
    except KeyboardInterrupt:
        print("\n❌ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
