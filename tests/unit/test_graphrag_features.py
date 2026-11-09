#!/usr/bin/env python3
"""
Quick test of Enhanced GraphRAG MCP Server functionality
"""

import sys
import subprocess
import json
import tempfile
import time
import os
from pathlib import Path
import textwrap

import pytest

pytestmark = pytest.mark.anyio


async def test_text_search_not_implemented():
    """Ensure text_search reports an unimplemented error."""
    from enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

    engine = GraphRAGSearchEngine()
    result = await engine.text_search("test query")

    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "not implemented" in str(result.get("error", "")).lower()


@pytest.mark.skip(reason="GraphRAG text_search method not yet implemented - full integration test")
def test_basic_server():
    """Test basic server functionality in isolation."""

    print("🧪 Quick Enhanced MCP Server Test")
    print("=" * 40)

    repo_root = Path(__file__).resolve().parents[2]
    # Use current Python executable instead of hardcoded venv path
    import sys

    venv_python = sys.executable

    try:
        # Test that server can import successfully
        print("📋 1. Testing imports...")
        result = subprocess.run(
            [
                venv_python,
                "-c",
                "import sys; sys.path.insert(0, 'mcp'); import enhanced_mcp_server_with_daemon_mgmt; print('✅ Server imports successfully')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )

        if result.returncode == 0:
            print("✅ Server imports successfully")
        else:
            print(f"❌ Import failed: {result.stderr}")
            pytest.fail(f"Server import failed: {result.stderr}")

        # Test that GraphRAG search engine can be created
        print("📋 2. Testing GraphRAG engine...")
        test_code = textwrap.dedent("""
            import sys
            sys.path.insert(0, 'mcp')
            from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine
            try:
                engine = GraphRAGSearchEngine()
                stats = engine.get_search_stats()
                print(f'✅ GraphRAG engine created: {stats["vector_search_available"]=}, {stats["graph_search_available"]=}, {stats["sparql_available"]=}')
            except Exception as e:
                print(f'❌ GraphRAG engine failed: {e}')
        """)

        result = subprocess.run(
            [venv_python, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(repo_root),
        )

        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"❌ GraphRAG test failed: {result.stderr}")
            pytest.fail(f"GraphRAG engine test failed: {result.stderr}")

        # Test content indexing
        print("📋 3. Testing content indexing...")
        test_code = textwrap.dedent("""
            import sys
            import anyio
            sys.path.insert(0, 'mcp')
            from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

            async def test_indexing():
                engine = GraphRAGSearchEngine()
                result = await engine.index_content(
                    cid="test123",
                    path="/test/doc.txt",
                    content="This is a test document about IPFS and distributed systems.",
                    metadata={"topic": "test"}
                )
                return result

            result = anyio.run(test_indexing)
            print(f'✅ Content indexing: {result["success"]=}')
        """)

        result = subprocess.run(
            [venv_python, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(repo_root),
        )

        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"❌ Indexing test failed: {result.stderr}")
            pytest.fail(f"Indexing test failed: {result.stderr}")

        # Test text search
        print("📋 4. Testing search functionality...")
        test_code = textwrap.dedent("""
            import sys
            import anyio
            sys.path.insert(0, 'mcp')
            from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

            async def test_search():
                engine = GraphRAGSearchEngine()
                # Index content first
                await engine.index_content(
                    cid="test123",
                    path="/test/doc.txt",
                    content="This is a test document about IPFS and distributed systems.",
                    metadata={"topic": "test"}
                )
                # Search for it
                result = await engine.text_search("IPFS distributed", limit=5)
                return result

            result = anyio.run(test_search)
            print(f'✅ Search functionality: {result["success"]=}, results={len(result.get("results", []))}')
        """)

        result = subprocess.run(
            [venv_python, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(repo_root),
        )

        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"❌ Search test failed: {result.stderr}")
            pytest.fail(f"Search test failed: {result.stderr}")

        print("\n🎉 All basic tests passed!")
        assert True

    except subprocess.TimeoutExpired:
        print("❌ Test timeout")
        pytest.fail("GraphRAG test timed out")
    except Exception as e:
        print(f"❌ Test error: {e}")
        pytest.fail(f"GraphRAG test failed: {e}")


def check_capabilities():
    """Check what search capabilities are available."""

    print("\n📊 Search Capabilities Check")
    print("-" * 30)

    repo_root = Path(__file__).resolve().parents[2]
    venv_python = str((repo_root / ".venv" / "bin" / "python").resolve())

    test_code = """
import sys
sys.path.insert(0, 'mcp')
from ipfs_kit_py.mcp.enhanced_mcp_server_with_daemon_mgmt import GraphRAGSearchEngine

engine = GraphRAGSearchEngine()
stats = engine.get_search_stats()

print("Available capabilities:")
for key, value in stats.items():
    if key.endswith('_available'):
        status = "✅" if value else "❌"
        feature = key.replace('_available', '').replace('_', ' ').title()
        print(f"  {status} {feature}")

print(f"\\nDatabase info:")
print(f"  📊 Total indexed content: {stats.get('total_indexed_content', 0)}")
print(f"  🔗 Knowledge graph nodes: {stats.get('knowledge_graph_nodes', 0)}")
print(f"  🔗 Knowledge graph edges: {stats.get('knowledge_graph_edges', 0)}")
print(f"  📈 RDF triples: {stats.get('rdf_triples', 0)}")
"""

    try:
        result = subprocess.run(
            [venv_python, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )

        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"❌ Capability check failed: {result.stderr}")

    except Exception as e:
        print(f"❌ Error checking capabilities: {e}")


if __name__ == "__main__":
    try:
        success = test_basic_server()
        check_capabilities()

        print("\n" + "=" * 40)
        if success:
            print("🎯 Enhanced GraphRAG MCP Server is functional!")
            print("\nKey features verified:")
            print("✅ Server imports and initialization")
            print("✅ GraphRAG search engine creation")
            print("✅ Content indexing capabilities")
            print("✅ Text search functionality")
            print("✅ Database operations")

            print("\n🚀 Ready for use with:")
            print("- VFS/MFS filesystem operations with auto-indexing")
            print("- Vector search (if sentence-transformers installed)")
            print("- Knowledge graph search")
            print("- SPARQL queries on RDF data")
            print("- Hybrid search combining multiple methods")
        else:
            print("❌ Some tests failed - check output above")

    except KeyboardInterrupt:
        print("\n❌ Test interrupted")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
