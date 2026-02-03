#!/usr/bin/env python3
"""
Tests for improved GraphRAG and bucket metadata export/import functionality.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock


class TestImprovedGraphRAG:
    """Tests for improved GraphRAG functionality."""
    
    def test_graphrag_with_caching(self):
        """Test GraphRAG initialization with caching."""
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = GraphRAGSearchEngine(workspace_dir=tmpdir, enable_caching=True)
            assert engine.enable_caching == True
            assert engine.embedding_cache is not None
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
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
    
    @pytest.mark.asyncio
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
    
    def test_importer_initialization(self):
        """Test importer initialization."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataImporter
        
        importer = BucketMetadataImporter()
        assert importer is not None
        assert importer.ipfs_client is None
        assert importer.bucket_manager is None
    
    @pytest.mark.asyncio
    async def test_export_bucket_metadata(self):
        """Test exporting bucket metadata."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
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
        mock_bucket.storage_path = Path("/tmp/test-bucket")
        mock_bucket.dirs = {"files": Path("/tmp/test-bucket/files")}
        
        exporter = BucketMetadataExporter()
        result = await exporter.export_bucket_metadata(
            mock_bucket,
            include_files=False,
            include_knowledge_graph=False,
            include_vector_index=False
        )
        
        assert result["success"] == True
        assert "size_bytes" in result
    
    @pytest.mark.asyncio
    async def test_export_with_ipfs_client(self):
        """Test exporting with IPFS client."""
        from ipfs_kit_py.bucket_metadata_transfer import BucketMetadataExporter
        
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
        mock_bucket.storage_path = Path("/tmp/test-bucket")
        mock_bucket.dirs = {"files": Path("/tmp/test-bucket/files")}
        
        exporter = BucketMetadataExporter(ipfs_client=mock_ipfs)
        result = await exporter.export_bucket_metadata(
            mock_bucket,
            include_files=False
        )
        
        assert result["success"] == True
        assert "metadata_cid" in result
    
    @pytest.mark.asyncio
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
    
    def test_convenience_functions(self):
        """Test convenience functions for creating exporters/importers."""
        from ipfs_kit_py.bucket_metadata_transfer import create_bucket_exporter, create_bucket_importer
        
        exporter = create_bucket_exporter()
        assert exporter is not None
        
        importer = create_bucket_importer()
        assert importer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
