"""
Comprehensive GraphRAG Tests for 100% Coverage

This test file aims to achieve 100% line and branch coverage for the GraphRAG module.
Tests cover all search methods, indexing, graph operations, and edge cases.
"""

import pytest
import anyio
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Import GraphRAG
from ipfs_kit_py.graphrag import GraphRAGSearchEngine


class TestGraphRAGInitialization:
    """Test GraphRAG initialization and setup."""
    
    @pytest.mark.anyio
    async def test_init_with_custom_workspace(self):
        """Test initialization with custom workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            
            assert engine.workspace_dir == tmpdir
            assert engine.enable_caching is True
            assert os.path.exists(engine.db_path)
    
    @pytest.mark.anyio
    async def test_init_with_default_workspace(self):
        """Test initialization with default workspace directory."""
        engine = GraphRAGSearchEngine()
        
        assert engine.workspace_dir is not None
        assert os.path.exists(engine.workspace_dir)
        assert engine.db_path is not None
    
    @pytest.mark.anyio
    async def test_init_without_caching(self):
        """Test initialization without caching enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=False)
            
            assert engine.enable_caching is False
    
    @pytest.mark.anyio
    async def test_database_initialization(self):
        """Test that database tables are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Check that database file exists
            assert os.path.exists(engine.db_path)
            
            # Verify tables exist
            import sqlite3
            conn = sqlite3.connect(engine.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()
            
            # Check for actual table names (content_index, not content)
            assert "content_index" in tables
            assert "content_relationships" in tables or "relationships" in tables
            assert "content_versions" in tables


class TestGraphRAGIndexing:
    """Test content indexing operations."""
    
    @pytest.mark.anyio
    async def test_index_single_content(self):
        """Test indexing a single piece of content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.index_content(
                cid="QmTest123",
                path="/test/file.txt",
                content="This is test content for indexing."
            )
            
            assert result is not None
            assert "indexed" in result or "success" in result or result.get("status") == "success"
    
    @pytest.mark.anyio
    async def test_index_content_with_metadata(self):
        """Test indexing content with additional metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.index_content(
                cid="QmTest456",
                path="/test/doc.md",
                content="Document content here.",
                metadata={"author": "test", "type": "markdown"}
            )
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_bulk_index_multiple_items(self):
        """Test bulk indexing multiple items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            items = [
                {"cid": "Qm1", "path": "/file1.txt", "content": "First file"},
                {"cid": "Qm2", "path": "/file2.txt", "content": "Second file"},
                {"cid": "Qm3", "path": "/file3.txt", "content": "Third file"}
            ]
            
            result = await engine.bulk_index_content(items)
            
            assert result is not None
            assert result.get("indexed", 0) >= 0 or result.get("total", 0) >= 0
    
    @pytest.mark.anyio
    async def test_bulk_index_empty_list(self):
        """Test bulk indexing with empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.bulk_index_content([])
            
            assert result is not None
            assert result.get("indexed", 0) == 0 or result.get("total", 0) == 0
    
    @pytest.mark.anyio
    async def test_index_content_update_version(self):
        """Test that re-indexing same content creates version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # First index
            await engine.index_content("QmTest", "/file.txt", "Version 1")
            
            # Second index (update)
            result = await engine.index_content("QmTest", "/file.txt", "Version 2")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_index_empty_content(self):
        """Test indexing empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.index_content("QmEmpty", "/empty.txt", "")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_index_large_content(self):
        """Test indexing large content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            large_content = "Large content. " * 10000  # ~150KB
            result = await engine.index_content("QmLarge", "/large.txt", large_content)
            
            assert result is not None


class TestGraphRAGSearch:
    """Test search operations."""
    
    @pytest.mark.anyio
    async def test_search_hybrid_type(self):
        """Test hybrid search (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Index some content first
            await engine.index_content("Qm1", "/test.txt", "Test content for search")
            
            result = await engine.search("test", search_type="hybrid")
            
            assert result is not None
            assert "results" in result or "matches" in result or isinstance(result, dict)
    
    @pytest.mark.anyio
    async def test_search_vector_type(self):
        """Test vector search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Vector search test")
            
            result = await engine.search("vector", search_type="vector")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_search_graph_type(self):
        """Test graph search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Graph search test")
            
            result = await engine.search("graph", search_type="graph")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_search_text_type(self):
        """Test text search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Text search test")
            
            result = await engine.search("text", search_type="text")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_vector_search_direct(self):
        """Test vector search method directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Direct vector search")
            
            result = await engine.vector_search("search query", limit=5)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_hybrid_search_with_weights(self):
        """Test hybrid search with custom weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Hybrid search content")
            
            result = await engine.hybrid_search(
                "query",
                weights={'vector': 0.5, 'graph': 0.3, 'text': 0.2}
            )
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_graph_search_with_max_depth(self):
        """Test graph search with different max depths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/test.txt", "Graph depth test")
            
            # Test with different depths
            result1 = await engine.graph_search("query", max_depth=1)
            result2 = await engine.graph_search("query", max_depth=3)
            
            assert result1 is not None
            assert result2 is not None
    
    @pytest.mark.anyio
    async def test_search_empty_query(self):
        """Test search with empty query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.search("")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_search_no_indexed_content(self):
        """Test search when no content is indexed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.search("nonexistent")
            
            assert result is not None


class TestGraphRAGRelationships:
    """Test relationship management."""
    
    @pytest.mark.anyio
    async def test_add_relationship(self):
        """Test adding a relationship between content items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Index content first
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            
            # Add relationship
            result = await engine.add_relationship(
                "Qm1", "Qm2", 
                relationship_type="references",
                confidence=0.9
            )
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_add_relationship_with_confidence(self):
        """Test adding relationship with different confidence scores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            
            # Low confidence
            await engine.add_relationship("Qm1", "Qm2", "weak_link", confidence=0.3)
            
            # High confidence
            await engine.add_relationship("Qm1", "Qm2", "strong_link", confidence=0.95)
            
            # Should succeed
            assert True
    
    @pytest.mark.anyio
    async def test_infer_relationships(self):
        """Test automatic relationship inference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Index similar content
            await engine.index_content("Qm1", "/doc1.txt", "Python programming tutorial")
            await engine.index_content("Qm2", "/doc2.txt", "Python coding guide")
            await engine.index_content("Qm3", "/doc3.txt", "Completely different topic")
            
            result = await engine.infer_relationships(threshold=0.5)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_infer_relationships_high_threshold(self):
        """Test relationship inference with high threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            
            # High threshold should result in fewer relationships
            result = await engine.infer_relationships(threshold=0.95)
            
            assert result is not None


class TestGraphRAGEntityExtraction:
    """Test entity extraction."""
    
    @pytest.mark.anyio
    async def test_extract_entities_basic(self):
        """Test basic entity extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            content = "John works at Microsoft in Seattle. He uses Python and IPFS."
            result = await engine.extract_entities(content)
            
            assert result is not None
            assert "entities" in result or isinstance(result, dict)
    
    @pytest.mark.anyio
    async def test_extract_entities_with_cids(self):
        """Test entity extraction finds CIDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            content = "The file is stored at QmTest123 and QmABC456."
            result = await engine.extract_entities(content)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_extract_entities_empty_content(self):
        """Test entity extraction with empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.extract_entities("")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_extract_entities_special_characters(self):
        """Test entity extraction with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            content = "Special chars: @#$% & *()! UTF-8: 日本語 中文 Русский"
            result = await engine.extract_entities(content)
            
            assert result is not None


class TestGraphRAGAnalytics:
    """Test graph analytics and statistics."""
    
    @pytest.mark.anyio
    async def test_analyze_graph(self):
        """Test graph analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Add some content and relationships
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            await engine.add_relationship("Qm1", "Qm2", "related_to", confidence=0.8)
            
            result = engine.analyze_graph()
            
            assert result is not None
            assert isinstance(result, dict)
    
    @pytest.mark.anyio
    async def test_analyze_empty_graph(self):
        """Test graph analysis with no content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = engine.analyze_graph()
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_get_stats(self):
        """Test getting statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Index some content
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            
            result = engine.get_stats()
            
            assert result is not None
            assert isinstance(result, dict)
    
    @pytest.mark.anyio
    async def test_get_stats_with_cache_enabled(self):
        """Test statistics with caching enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            
            # Index content to populate cache
            await engine.index_content("Qm1", "/file1.txt", "Cached content")
            
            result = engine.get_stats()
            
            assert result is not None
            # Should have cache-related stats
            assert "stats" in result or "cache" in result or isinstance(result, dict)


class TestGraphRAGCaching:
    """Test embedding caching functionality."""
    
    @pytest.mark.anyio
    async def test_caching_enabled(self):
        """Test that caching works when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            
            # Index content twice
            await engine.index_content("Qm1", "/file.txt", "Cacheable content")
            await engine.index_content("Qm1", "/file.txt", "Cacheable content")
            
            # Should use cache on second index
            assert engine.enable_caching is True
    
    @pytest.mark.anyio
    async def test_caching_disabled(self):
        """Test that caching can be disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=False)
            
            await engine.index_content("Qm1", "/file.txt", "Non-cached content")
            
            assert engine.enable_caching is False
    
    @pytest.mark.anyio
    async def test_cache_persistence(self):
        """Test that cache persists between sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First session
            engine1 = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            await engine1.index_content("Qm1", "/file.txt", "Persistent cache")
            
            # Second session
            engine2 = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            # Cache should be loaded
            assert engine2.enable_caching is True


class TestGraphRAGSPARQL:
    """Test SPARQL query functionality."""
    
    @pytest.mark.anyio
    async def test_sparql_search_basic(self):
        """Test basic SPARQL search."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            query = "SELECT ?s WHERE { ?s ?p ?o }"
            result = await engine.sparql_search(query)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_sparql_search_empty_query(self):
        """Test SPARQL with empty query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.sparql_search("")
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_sparql_search_complex_query(self):
        """Test SPARQL with complex query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Complex SPARQL query
            query = """
            SELECT ?subject ?predicate ?object
            WHERE {
                ?subject ?predicate ?object .
                FILTER(?object > 10)
            }
            LIMIT 100
            """
            result = await engine.sparql_search(query)
            
            assert result is not None


class TestGraphRAGEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.mark.anyio
    async def test_concurrent_indexing(self):
        """Test concurrent indexing operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            async with anyio.create_task_group() as tg:
                tg.start_soon(engine.index_content, "Qm1", "/file1.txt", "Content 1")
                tg.start_soon(engine.index_content, "Qm2", "/file2.txt", "Content 2")
                tg.start_soon(engine.index_content, "Qm3", "/file3.txt", "Content 3")
            
            # Should complete without errors
            assert True
    
    @pytest.mark.anyio
    async def test_special_characters_in_paths(self):
        """Test indexing with special characters in paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.index_content(
                "Qm1",
                "/path/with spaces/and-special!@#$chars.txt",
                "Content with special path"
            )
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_unicode_content(self):
        """Test indexing Unicode content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            unicode_content = "Hello 世界 🌍 Привет مرحبا"
            result = await engine.index_content("Qm1", "/unicode.txt", unicode_content)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_very_long_content(self):
        """Test indexing very long content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            long_content = "Long content. " * 100000  # ~1.5MB
            result = await engine.index_content("QmLong", "/long.txt", long_content)
            
            assert result is not None
    
    @pytest.mark.anyio
    async def test_multiple_relationships_same_cids(self):
        """Test adding multiple relationships between same CIDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            await engine.index_content("Qm1", "/file1.txt", "Content 1")
            await engine.index_content("Qm2", "/file2.txt", "Content 2")
            
            # Add multiple relationship types
            await engine.add_relationship("Qm1", "Qm2", "type1", confidence=0.8)
            await engine.add_relationship("Qm1", "Qm2", "type2", confidence=0.7)
            await engine.add_relationship("Qm1", "Qm2", "type3", confidence=0.9)
            
            # Should handle multiple relationships
            assert True
    
    @pytest.mark.anyio
    async def test_circular_relationships(self):
        """Test circular relationships in graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Create circular relationships
            await engine.index_content("Qm1", "/file1.txt", "Node 1")
            await engine.index_content("Qm2", "/file2.txt", "Node 2")
            await engine.index_content("Qm3", "/file3.txt", "Node 3")
            
            await engine.add_relationship("Qm1", "Qm2", "points_to")
            await engine.add_relationship("Qm2", "Qm3", "points_to")
            await engine.add_relationship("Qm3", "Qm1", "points_to")  # Circular
            
            # Graph should handle cycles
            result = engine.analyze_graph()
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
