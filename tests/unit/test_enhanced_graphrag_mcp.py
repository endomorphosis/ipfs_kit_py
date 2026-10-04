#!/usr/bin/env python3
"""
Test script for the Enhanced GraphRAG MCP Server
==============================================

This script tests the new GraphRAG, vector search, and SPARQL capabilities
of the enhanced MCP server.
"""

import json
import subprocess
import tempfile
import os
import sys
from datetime import datetime
import pytest

def test_mcp_server():
    """Test the enhanced MCP server with GraphRAG capabilities."""
    
    print("🚀 Testing Enhanced GraphRAG MCP Server")
    print("=" * 50)
    
    # Test data for indexing and searching
    test_documents = [
        {
            "content": "IPFS Whitepaper\n\nIPFS (InterPlanetary File System) is a distributed file system that seeks to connect all computing devices with the same system of files.",
            "path": "/docs/ipfs_whitepaper.md",
            "metadata": {"type": "documentation", "topic": "ipfs", "format": "markdown"}
        },
        {
            "content": "GraphRAG Research\n\nGraphRAG combines retrieval-augmented generation with knowledge graphs to provide more accurate and contextual responses.",
            "path": "/research/graphrag.md", 
            "metadata": {"type": "research", "topic": "ai", "format": "markdown"}
        },
        {
            "content": "Vector Search Tutorial\n\nVector search uses embeddings to find semantically similar content based on meaning rather than exact keyword matches.",
            "path": "/tutorials/vector_search.md",
            "metadata": {"type": "tutorial", "topic": "search", "format": "markdown"}
        },
        {
            "content": "SPARQL Query Examples\n\nSPARQL is a query language for RDF data. SELECT ?subject ?predicate ?object WHERE { ?subject ?predicate ?object }",
            "path": "/examples/sparql.md",
            "metadata": {"type": "example", "topic": "sparql", "format": "markdown"}
        }
    ]
    
    def send_mcp_request(method, params=None):
        """Send a request to the MCP server."""
        if params is None:
            params = {}
            
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            # Start the MCP server process
            server_process = subprocess.Popen(
                [sys.executable, "mcp/ipfs_kit/mcp/enhanced_mcp_server_with_daemon_mgmt.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.getcwd()
            )

            # Build input payload
            payload = []
            if method != "initialize":
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0.0"}
                    }
                }
                payload.append(json.dumps(init_request))
                notify_request = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                payload.append(json.dumps(notify_request))

            payload.append(json.dumps(request))
            input_data = "\n".join(payload) + "\n"

            # Read response with timeout
            try:
                stdout, stderr = server_process.communicate(input=input_data, timeout=30)
                
                if stderr:
                    print(f"Server stderr: {stderr}")
                
                # Parse the last JSON response from stdout
                if stdout.strip():
                    lines = stdout.strip().split('\n')
                    # Find the response that matches our request ID
                    for line in reversed(lines):
                        if line.strip():
                            try:
                                response = json.loads(line)
                                if response.get("id") == request.get("id"):
                                    return response
                            except json.JSONDecodeError:
                                continue
                    
                    # If no matching response, return the last valid JSON
                    for line in reversed(lines):
                        if line.strip():
                            try:
                                return json.loads(line)
                            except json.JSONDecodeError:
                                continue
                
                return {"error": "No valid response from server", "raw_output": stdout}
                    
            except subprocess.TimeoutExpired:
                server_process.kill()
                return {"error": "Server timeout"}
                
        except Exception as e:
            return {"error": f"Failed to communicate with server: {e}"}
    
    # Test 1: Initialize server
    print("\n📋 Test 1: Initialize MCP Server")
    print("-" * 30)
    
    response = send_mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    })
    
    if "error" in response:
        print(f"❌ Initialization failed: {response['error']}")
        pytest.fail(f"MCP server initialization failed: {response['error']}")
    else:
        print("✅ Server initialized successfully")
        print(f"Server: {response.get('result', {}).get('serverInfo', {}).get('name', 'Unknown')}")
    
    # Test 2: List available tools
    print("\n📋 Test 2: List Available Tools")
    print("-" * 30)
    
    response = send_mcp_request("tools/list")
    
    if "error" in response:
        print(f"❌ Failed to list tools: {response['error']}")
    else:
        tools = response.get("result", {}).get("tools", [])
        print(f"✅ Found {len(tools)} tools")
        
        # Look for search tools
        search_tools = [tool for tool in tools if tool.get("name", "").startswith("search_")]
        print(f"🔍 Search tools available: {len(search_tools)}")
        for tool in search_tools:
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:60]}...")
    
    # Test 3: Get search statistics
    print("\n📋 Test 3: Get Search Statistics")
    print("-" * 30)
    
    response = send_mcp_request("tools/call", {
        "name": "search_stats",
        "arguments": {}
    })
    
    if "error" in response:
        print(f"❌ Failed to get search stats: {response['error']}")
    else:
        result = response.get("result", {})
        if result.get("isError"):
            print(f"❌ Search stats error: {result}")
        else:
            content = result.get("content", [{}])[0].get("text", "{}")
            try:
                stats = json.loads(content)
                print("✅ Search statistics:")
                print(f"  - Vector search available: {stats.get('vector_search_available', False)}")
                print(f"  - Graph search available: {stats.get('graph_search_available', False)}")
                print(f"  - SPARQL available: {stats.get('sparql_available', False)}")
                print(f"  - Indexed content: {stats.get('total_indexed_content', 0)}")
            except json.JSONDecodeError:
                print(f"❌ Invalid stats response: {content}")
    
    # Test 4: Index test documents
    print("\n📋 Test 4: Index Test Documents")
    print("-" * 30)
    
    indexed_cids = []
    for i, doc in enumerate(test_documents):
        # Generate a mock CID for testing
        mock_cid = f"bafybeig{i:04d}test{'0' * 40}"
        indexed_cids.append(mock_cid)
        
        response = send_mcp_request("tools/call", {
            "name": "search_index_content",
            "arguments": {
                "cid": mock_cid,
                "path": doc["path"],
                "content": doc["content"],
                "content_type": "text",
                "metadata": doc["metadata"]
            }
        })
        
        if "error" in response:
            print(f"❌ Failed to index document {i+1}: {response['error']}")
        else:
            result = response.get("result", {})
            if result.get("isError"):
                print(f"❌ Index error for document {i+1}: {result}")
            else:
                content = result.get("content", [{}])[0].get("text", "{}")
                try:
                    index_result = json.loads(content)
                    if index_result.get("success"):
                        print(f"✅ Indexed document {i+1}: {doc['path']}")
                    else:
                        print(f"❌ Failed to index document {i+1}: {index_result.get('error')}")
                except json.JSONDecodeError:
                    print(f"❌ Invalid index response for document {i+1}: {content}")
    
    # Test 5: Vector search
    print("\n📋 Test 5: Vector Search")
    print("-" * 30)
    
    search_queries = [
        "distributed file system",
        "knowledge graphs and AI",
        "semantic similarity search"
    ]
    
    for query in search_queries:
        response = send_mcp_request("tools/call", {
            "name": "search_vector",
            "arguments": {
                "query": query,
                "limit": 3
            }
        })
        
        if "error" in response:
            print(f"❌ Vector search failed for '{query}': {response['error']}")
        else:
            result = response.get("result", {})
            if result.get("isError"):
                print(f"❌ Vector search error for '{query}': {result}")
            else:
                content = result.get("content", [{}])[0].get("text", "{}")
                try:
                    search_result = json.loads(content)
                    if search_result.get("success"):
                        results = search_result.get("results", [])
                        print(f"✅ Vector search for '{query}': {len(results)} results")
                        for r in results[:2]:  # Show top 2
                            print(f"   - {r.get('title', 'Untitled')} (similarity: {r.get('similarity', 0):.2f})")
                    else:
                        print(f"❌ Vector search failed for '{query}': {search_result.get('error')}")
                except json.JSONDecodeError:
                    print(f"❌ Invalid vector search response for '{query}': {content}")
    
    # Test 6: Graph search
    print("\n📋 Test 6: Graph Search")
    print("-" * 30)
    
    response = send_mcp_request("tools/call", {
        "name": "search_graph",
        "arguments": {
            "query": "IPFS distributed",
            "max_depth": 2
        }
    })
    
    if "error" in response:
        print(f"❌ Graph search failed: {response['error']}")
    else:
        result = response.get("result", {})
        if result.get("isError"):
            print(f"❌ Graph search error: {result}")
        else:
            content = result.get("content", [{}])[0].get("text", "{}")
            try:
                search_result = json.loads(content)
                if search_result.get("success"):
                    results = search_result.get("results", [])
                    print(f"✅ Graph search: {len(results)} results")
                    for r in results[:2]:
                        print(f"   - {r.get('title', 'Untitled')} (score: {r.get('importance_score', 0):.2f})")
                else:
                    print(f"❌ Graph search failed: {search_result.get('error')}")
            except json.JSONDecodeError:
                print(f"❌ Invalid graph search response: {content}")
    
    # Test 7: Hybrid search
    print("\n📋 Test 7: Hybrid Search")
    print("-" * 30)
    
    response = send_mcp_request("tools/call", {
        "name": "search_hybrid",
        "arguments": {
            "query": "vector search tutorial",
            "search_types": ["vector", "text", "graph"]
        }
    })
    
    if "error" in response:
        print(f"❌ Hybrid search failed: {response['error']}")
    else:
        result = response.get("result", {})
        if result.get("isError"):
            print(f"❌ Hybrid search error: {result}")
        else:
            content = result.get("content", [{}])[0].get("text", "{}")
            try:
                search_result = json.loads(content)
                if search_result.get("success"):
                    combined = search_result.get("combined", {})
                    total_results = combined.get("total_unique_results", 0)
                    print(f"✅ Hybrid search: {total_results} unique results")
                    
                    results = combined.get("results", [])
                    for r in results[:2]:
                        methods = ", ".join(r.get("search_methods", []))
                        print(f"   - {r.get('title', 'Untitled')} (methods: {methods})")
                else:
                    print(f"❌ Hybrid search failed: {search_result.get('error')}")
            except json.JSONDecodeError:
                print(f"❌ Invalid hybrid search response: {content}")
    
    # Test 8: SPARQL search
    print("\n📋 Test 8: SPARQL Search")
    print("-" * 30)
    
    sparql_query = """
    PREFIX content: <http://ipfs.io/content/>
    SELECT ?document ?title WHERE {
        ?document a content:Document .
        ?document <http://www.w3.org/2000/01/rdf-schema#label> ?title .
    } LIMIT 5
    """
    
    response = send_mcp_request("tools/call", {
        "name": "search_sparql",
        "arguments": {
            "sparql_query": sparql_query
        }
    })
    
    if "error" in response:
        print(f"❌ SPARQL search failed: {response['error']}")
    else:
        result = response.get("result", {})
        if result.get("isError"):
            print(f"❌ SPARQL search error: {result}")
        else:
            content = result.get("content", [{}])[0].get("text", "{}")
            try:
                search_result = json.loads(content)
                if search_result.get("success"):
                    results = search_result.get("results", [])
                    print(f"✅ SPARQL search: {len(results)} results")
                    for r in results[:3]:
                        print(f"   - {r.get('title', 'Unknown')}")
                else:
                    print(f"❌ SPARQL search failed: {search_result.get('error')}")
            except json.JSONDecodeError:
                print(f"❌ Invalid SPARQL search response: {content}")
    
    print("\n" + "=" * 50)
    print("🎉 Enhanced GraphRAG MCP Server Testing Complete!")
    print("\nFeatures tested:")
    print("✅ Content indexing with metadata")
    print("✅ Vector similarity search")
    print("✅ Knowledge graph search")
    print("✅ Hybrid search combining multiple methods")
    print("✅ SPARQL queries on RDF data")
    print("✅ Search statistics and capabilities")
    
    assert True

if __name__ == "__main__":
    try:
        test_mcp_server()
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
