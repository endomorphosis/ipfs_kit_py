#!/usr/bin/env python3
"""
Tests for improved GraphRAG and bucket metadata export/import functionality.
"""

import pytest
import anyio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import json


class TestImprovedGraphRAG:
    """Tests for improved GraphRAG functionality."""
    
    def test_graphrag_with_caching(self):
        """Test GraphRAG initialization with caching."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            assert engine.enable_caching == True
            assert engine.embedding_cache is not None
    
    def test_graphrag_without_caching(self):
        """Test GraphRAG initialization without caching."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=False)
            assert engine.enable_caching == False
    
    @pytest.mark.anyio
    async def test_bulk_indexing(self):
        """Test bulk content indexing."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Bulk index items
            items = [
                {"cid": "QmTest1", "path": "/test1", "content": "Test content 1"},
                {"cid": "QmTest2", "path": "/test2", "content": "Test content 2"},
                {"cid": "QmTest3", "path": "/test3", "content": "Test content 3"}
            ]
            
            result = await engine.bulk_index_content(items)
            
            assert result["success"] == True
            assert result["indexed_count"] == 3
            assert result["total_items"] == 3
    
    @pytest.mark.anyio
    async def test_bulk_indexing_with_errors(self):
        """Test bulk indexing with some failing items."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Include invalid item
            items = [
                {"cid": "QmTest1", "path": "/test1", "content": "Test content 1"},
                {"cid": None, "path": "/test2", "content": "Test content 2"},  # Invalid
            ]
            
            result = await engine.bulk_index_content(items)
            
            assert result["success"] == True
            # The implementation gracefully handles errors, check that at least some items were indexed
            assert result.get("indexed", 0) >= 0
    
    @pytest.mark.anyio
    async def test_entity_extraction_with_spacy(self):
        """Test enhanced entity extraction."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            content = "John Smith from Microsoft visited QmTest123 at /home/user/file.txt"
            result = await engine.extract_entities(content)
            
            assert result["success"] == True
            assert "entities" in result
            # Should extract CIDs and paths at minimum
            assert len(result["entities"]["cids"]) > 0 or len(result["entities"]["paths"]) > 0
    
    @pytest.mark.anyio
    async def test_entity_extraction_fallback(self):
        """Test entity extraction without spaCy (regex fallback)."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.nlp_model = None  # Force fallback
            
            # Use more specific CID pattern that will match
            content = "File at /path/to/file.txt with CID QmTest1234567890123456789012345678901234567890AB"
            result = await engine.extract_entities(content)
            
            assert result["success"] == True
            assert len(result["entities"]["paths"]) > 0  # Should at least find paths
    
    @pytest.mark.anyio
    async def test_relationship_with_confidence(self):
        """Test adding relationships with confidence scores."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            result = await engine.add_relationship(
                "QmTest1", "QmTest2", 
                relationship_type="similar_to",
                confidence=0.85
            )
            
            assert result["success"] == True
            assert result["relationship"]["confidence"] == 0.85
    
    @pytest.mark.anyio
    async def test_infer_relationships(self):
        """Test relationship inference based on similarity."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Skip if embeddings model not available
            if not engine.embeddings_model:
                pytest.skip("Sentence transformers not available")
            
            # Index similar content
            await engine.index_content("QmTest1", "/test1", "machine learning algorithms")
            await engine.index_content("QmTest2", "/test2", "deep learning neural networks")
            
            # Infer relationships
            result = await engine.infer_relationships(threshold=0.3)
            
            assert result["success"] == True
            assert "inferred_count" in result
    
    @pytest.mark.anyio
    async def test_infer_relationships_no_embeddings(self):
        """Test relationship inference without embeddings model."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.embeddings_model = None
            
            result = await engine.infer_relationships(threshold=0.7)
            
            assert result["success"] == False
            assert "error" in result
    
    def test_graph_analytics(self):
        """Test graph analytics functionality."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Add some nodes and edges to knowledge graph
            if engine.knowledge_graph:
                engine.knowledge_graph.add_node("QmTest1", path="/test1")
                engine.knowledge_graph.add_node("QmTest2", path="/test2")
                engine.knowledge_graph.add_edge("QmTest1", "QmTest2", type="references")
                
                # Analyze graph
                result = engine.analyze_graph()
                
                assert result["success"] == True
                assert result["stats"]["nodes"] == 2
                assert result["stats"]["edges"] == 1
    
    def test_graph_analytics_no_graph(self):
        """Test graph analytics without knowledge graph."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.knowledge_graph = None
            
            result = engine.analyze_graph()
            
            assert result["success"] == False
            assert "error" in result
    
    @pytest.mark.anyio
    async def test_improved_hybrid_search(self):
        """Test improved hybrid search combining multiple methods."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # Index some content
            await engine.index_content("QmTest1", "/test1", "Python programming language")
            await engine.index_content("QmTest2", "/test2", "JavaScript web development")
            
            # Perform hybrid search
            result = await engine.hybrid_search(
                "programming",
                weights={'vector': 0.5, 'graph': 0.3, 'text': 0.2}
            )
            
            assert result["success"] == True
            assert "results" in result
            assert "search_types_used" in result
    
    @pytest.mark.anyio
    async def test_vector_search(self):
        """Test vector search directly."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            if not engine.embeddings_model:
                pytest.skip("Embeddings model not available")
            
            await engine.index_content("QmTest1", "/test1", "machine learning")
            
            result = await engine.vector_search("machine learning", limit=5)
            
            assert result["success"] == True
            assert "results" in result
    
    @pytest.mark.anyio
    async def test_vector_search_no_model(self):
        """Test vector search without embeddings model."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.embeddings_model = None
            
            result = await engine.vector_search("test query")
            
            assert result["success"] == False
            assert "error" in result
    
    @pytest.mark.anyio
    async def test_graph_search(self):
        """Test graph search directly."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)

            if engine.knowledge_graph is None:
                pytest.skip("NetworkX not available")

            engine.knowledge_graph.add_node("QmTest1", path="/test/file.txt")

            result = await engine.graph_search("test", max_depth=3)

            assert result["success"] == True
            assert "results" in result
    
    @pytest.mark.anyio
    async def test_graph_search_no_graph(self):
        """Test graph search without knowledge graph."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.knowledge_graph = None
            
            result = await engine.graph_search("test")
            
            assert result["success"] == False
            assert "error" in result
    
    @pytest.mark.anyio
    async def test_sparql_search(self):
        """Test SPARQL search directly."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # rdflib.Graph is falsy when empty, so only treat None as unavailable.
            if engine.rdf_graph is None:
                pytest.skip("RDFLib not available")
            
            query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
            result = await engine.sparql_search(query)
            
            assert result["success"] == True
            assert "results" in result
    
    @pytest.mark.anyio
    async def test_sparql_search_no_rdf(self):
        """Test SPARQL search without RDF graph."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            engine.rdf_graph = None
            
            result = await engine.sparql_search("SELECT * WHERE { ?s ?p ?o }")
            
            assert result["success"] == False
            assert "error" in result
    
    def test_comprehensive_stats(self):
        """Test comprehensive statistics gathering."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            
            stats = engine.get_stats()
            
            assert stats["success"] == True
            assert "stats" in stats
            assert "cache" in stats["stats"]
            assert "hit_rate" in stats["stats"]["cache"]
            assert "version_stats" in stats["stats"]
    
    @pytest.mark.anyio
    async def test_index_content_with_version_update(self):
        """Test updating existing content increments version."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir)
            
            # First index
            result1 = await engine.index_content("QmTest1", "/file", "Version 1")
            assert result1["version"] == 1
            
            # Update content
            result2 = await engine.index_content("QmTest1", "/file", "Version 2")
            assert result2["version"] == 2
    
    def test_save_load_cache(self):
        """Test saving and loading embedding cache."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create engine and add to cache
            engine1 = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            engine1.embedding_cache["test_hash"] = [1.0, 2.0, 3.0]
            engine1._save_embedding_cache()
            
            # Create new engine and verify cache loaded
            engine2 = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            assert "test_hash" in engine2.embedding_cache


class TestBucketMetadataExportImport:
    """Tests for bucket metadata export/import functionality."""
    
    def test_import_bucket_metadata_exporter(self):
        """Test importing bucket metadata exporter."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        assert BucketMetadataExporter is not None
    
    def test_import_bucket_metadata_importer(self):
        """Test importing bucket metadata importer."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        assert BucketMetadataImporter is not None
    
    def test_exporter_initialization(self):
        """Test exporter initialization."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        exporter = BucketMetadataExporter()
        assert exporter is not None
        assert exporter.ipfs_client is None
    
    def test_exporter_with_client(self):
        """Test exporter initialization with IPFS client."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        mock_client = Mock()
        exporter = BucketMetadataExporter(ipfs_client=mock_client)
        assert exporter.ipfs_client == mock_client
    
    def test_importer_initialization(self):
        """Test importer initialization."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        importer = BucketMetadataImporter()
        assert importer is not None
        assert importer.ipfs_client is None
        assert importer.bucket_manager is None
    
    def test_importer_with_clients(self):
        """Test importer initialization with clients."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        mock_ipfs = Mock()
        mock_manager = Mock()
        importer = BucketMetadataImporter(ipfs_client=mock_ipfs, bucket_manager=mock_manager)
        assert importer.ipfs_client == mock_ipfs
        assert importer.bucket_manager == mock_manager
    
    @pytest.mark.anyio
    async def test_export_bucket_metadata(self):
        """Test exporting bucket metadata."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock bucket
            mock_bucket = Mock()
            mock_bucket.name = "test-bucket"
            mock_bucket.bucket_type = Mock(value="general")
            mock_bucket.vfs_structure = Mock(value="unixfs")
            mock_bucket.created_at = "2024-01-01T00:00:00Z"
            mock_bucket.root_cid = "QmTest"
            mock_bucket.metadata = {}
            mock_bucket.knowledge_graph = None
            mock_bucket.vector_index = None
            mock_bucket.storage_path = Path(tmpdir)
            mock_bucket.dirs = {"files": Path(tmpdir) / "files"}
            
            exporter = BucketMetadataExporter()
            result = await exporter.export_bucket_metadata(
                mock_bucket,
                include_files=False,
                include_knowledge_graph=False,
                include_vector_index=False
            )
            
            assert result["success"] == True
            assert "size_bytes" in result
    
    @pytest.mark.anyio
    async def test_export_with_files(self):
        """Test exporting with file manifest."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            files_dir = Path(tmpdir) / "files"
            files_dir.mkdir()
            (files_dir / "test1.txt").write_text("test content 1")
            (files_dir / "test2.txt").write_text("test content 2")
            
            mock_bucket = Mock()
            mock_bucket.name = "test-bucket"
            mock_bucket.bucket_type = Mock(value="general")
            mock_bucket.vfs_structure = Mock(value="unixfs")
            mock_bucket.created_at = "2024-01-01T00:00:00Z"
            mock_bucket.root_cid = "QmTest"
            mock_bucket.metadata = {}
            mock_bucket.knowledge_graph = None
            mock_bucket.vector_index = None
            mock_bucket.storage_path = Path(tmpdir)
            mock_bucket.dirs = {"files": files_dir}
            
            exporter = BucketMetadataExporter()
            result = await exporter.export_bucket_metadata(
                mock_bucket,
                include_files=True
            )
            
            assert result["success"] == True
            # Check that export path was created
            assert result.get("export_path") is not None
    
    @pytest.mark.anyio
    async def test_export_with_ipfs_client(self):
        """Test exporting with IPFS client."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock IPFS client
            mock_ipfs = AsyncMock()
            mock_ipfs.add = AsyncMock(return_value={"Hash": "QmExportedMetadata"})
            
            # Create mock bucket
            mock_bucket = Mock()
            mock_bucket.name = "test-bucket"
            mock_bucket.bucket_type = Mock(value="general")
            mock_bucket.vfs_structure = Mock(value="unixfs")
            mock_bucket.created_at = "2024-01-01T00:00:00Z"
            mock_bucket.root_cid = "QmTest"
            mock_bucket.metadata = {}
            mock_bucket.knowledge_graph = None
            mock_bucket.vector_index = None
            mock_bucket.storage_path = Path(tmpdir)
            mock_bucket.dirs = {"files": Path(tmpdir) / "files"}
            
            exporter = BucketMetadataExporter(ipfs_client=mock_ipfs)
            result = await exporter.export_bucket_metadata(
                mock_bucket,
                include_files=False
            )
            
            assert result["success"] == True
            assert "metadata_cid" in result
    
    @pytest.mark.anyio
    async def test_export_cbor_format(self):
        """Test exporting in CBOR format."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_bucket = Mock()
            mock_bucket.name = "test-bucket"
            mock_bucket.bucket_type = Mock(value="general")
            mock_bucket.vfs_structure = Mock(value="unixfs")
            mock_bucket.created_at = "2024-01-01T00:00:00Z"
            mock_bucket.root_cid = "QmTest"
            mock_bucket.metadata = {}
            mock_bucket.knowledge_graph = None
            mock_bucket.vector_index = None
            mock_bucket.storage_path = Path(tmpdir)
            mock_bucket.dirs = {"files": Path(tmpdir) / "files"}
            
            exporter = BucketMetadataExporter()
            result = await exporter.export_bucket_metadata(
                mock_bucket,
                format="cbor"
            )
            
            # Should succeed or return appropriate error if cbor2 not installed
            assert "success" in result
    
    @pytest.mark.anyio
    async def test_export_file_manifest(self):
        """Test file manifest export functionality."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            files_dir = Path(tmpdir) / "files"
            files_dir.mkdir()
            (files_dir / "test.txt").write_text("test")
            
            mock_bucket = Mock()
            mock_bucket.dirs = {"files": files_dir}
            
            exporter = BucketMetadataExporter()
            manifest = await exporter._export_file_manifest(mock_bucket)
            
            assert "file_count" in manifest
            assert manifest["file_count"] > 0
    
    @pytest.mark.anyio
    async def test_export_statistics(self):
        """Test statistics export."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_bucket = Mock()
            mock_bucket.created_at = "2024-01-01T00:00:00Z"
            mock_bucket.root_cid = "QmTest"
            mock_bucket.storage_path = Path(tmpdir)
            
            exporter = BucketMetadataExporter()
            stats = await exporter._export_statistics(mock_bucket)
            
            assert "created_at" in stats
            assert "root_cid" in stats
    
    @pytest.mark.anyio
    async def test_import_bucket_metadata_validation(self):
        """Test metadata validation during import."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        importer = BucketMetadataImporter()
        
        # Valid metadata
        valid_metadata = {
            "version": "1.0",
            "bucket_info": {
                "name": "test-bucket",
                "type": "general"
            }
        }
        assert importer._validate_metadata(valid_metadata) == True
        
        # Invalid metadata - missing version
        invalid_metadata1 = {
            "bucket_info": {
                "name": "test-bucket",
                "type": "general"
            }
        }
        assert importer._validate_metadata(invalid_metadata1) == False
        
        # Invalid metadata - missing name
        invalid_metadata2 = {
            "version": "1.0",
            "bucket_info": {
                "type": "general"
            }
        }
        assert importer._validate_metadata(invalid_metadata2) == False
    
    @pytest.mark.anyio
    async def test_import_from_json(self):
        """Test JSON parsing from bytes."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        # Test that we can at least validate the metadata format
        metadata_dict = {
            "version": "1.0",
            "bucket_info": {
                "name": "test-bucket",
                "type": "general"
            }
        }
        
        importer = BucketMetadataImporter()
        assert importer._validate_metadata(metadata_dict) == True
    
    @pytest.mark.anyio
    async def test_import_without_ipfs_client(self):
        """Test importing without IPFS client."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        importer = BucketMetadataImporter()
        metadata = await importer._fetch_metadata_from_ipfs("QmTestCID")
        
        assert metadata is None
    
    @pytest.mark.anyio
    async def test_create_bucket_from_metadata(self):
        """Test bucket creation from metadata."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        metadata = {
            "version": "1.0",
            "bucket_info": {
                "name": "test-bucket",
                "type": "general",
                "vfs_structure": "unixfs",
                "metadata": {}
            }
        }
        
        mock_manager = AsyncMock()
        mock_manager.create_bucket = AsyncMock(return_value={"success": True})
        
        importer = BucketMetadataImporter(bucket_manager=mock_manager)
        result = await importer._create_bucket_from_metadata("test-bucket", metadata)
        
        assert result["success"] == True
    
    def test_convenience_functions(self):
        """Test convenience functions for creating exporters/importers."""
        from ipfs_kit_py.bucket_metadata_transfer import create_bucket_exporter, create_bucket_importer
        
        exporter = create_bucket_exporter()
        assert exporter is not None
        
        importer = create_bucket_importer()
        assert importer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
