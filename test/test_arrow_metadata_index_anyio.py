"""
Test suite for the ArrowMetadataIndexAnyIO class.

This module tests the AnyIO-compatible version of the Arrow metadata index.
"""

import os
import pytest
import tempfile
import time
from typing import Any, Dict, List, Optional

import anyio

# Import the AnyIO implementation
from ipfs_kit_py.arrow_metadata_index_anyio import (
    ArrowMetadataIndexAnyIO,
    create_metadata_from_ipfs_file_async,
    find_ai_ml_resources_async,
    find_similar_models_async,
    find_datasets_for_task_async,
)

# Skip tests if PyArrow is not available
try:
    import pyarrow as pa
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

# Skip tests if PyArrow Plasma is not available
try:
    import pyarrow.plasma as plasma
    PLASMA_AVAILABLE = True
except ImportError:
    PLASMA_AVAILABLE = False


# Fixture for temporary index directory
@pytest.fixture
def temp_index_dir():
    """Create a temporary directory for the index."""
    temp_dir = tempfile.mkdtemp(prefix="test_arrow_index_anyio_")
    yield temp_dir
    # Clean up
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Error cleaning up {temp_dir}: {e}")


@pytest.mark.skipif(not ARROW_AVAILABLE, reason="PyArrow not available")
class TestArrowMetadataIndexAnyIO:
    """Test the AnyIO-compatible Arrow metadata index."""
    
    @pytest.mark.anyio
    async def test_initialization(self, temp_index_dir):
        """Test initialization of the AnyIO index."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        # Basic assertions
        assert index.index_dir == temp_index_dir
        assert index.role == "leecher"
        assert index.sync_interval == 1
        assert index.enable_c_interface is False
        
        # Clean up
        await index.close_async()
    
    @pytest.mark.anyio
    async def test_add_and_get_async(self, temp_index_dir):
        """Test adding and retrieving a record asynchronously."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        try:
            # Test record
            test_cid = "QmTest123"
            test_record = {
                "cid": test_cid,
                "cid_version": 0,
                "multihash_type": "sha2-256",
                "size_bytes": 1024,
                "blocks": 1,
                "links": 0,
                "mime_type": "text/plain",
                "local": True,
                "pinned": True,
                "pin_types": ["recursive"],
                "replication": 1,
                "path": "/test/path",
                "filename": "test.txt",
                "extension": "txt",
            }
            
            # Add record asynchronously
            result = await index.add_async(test_record)
            
            # Verify result
            assert result["success"] is True
            assert result["cid"] == test_cid
            
            # Get record asynchronously
            retrieved = await index.get_by_cid_async(test_cid)
            
            # Verify retrieved record
            assert retrieved is not None
            assert retrieved["cid"] == test_cid
            assert retrieved["size_bytes"] == 1024
            assert retrieved["mime_type"] == "text/plain"
            
        finally:
            # Clean up
            await index.close_async()
    
    @pytest.mark.anyio
    async def test_query_async(self, temp_index_dir):
        """Test querying records asynchronously."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        try:
            # Add some test records
            for i in range(5):
                test_record = {
                    "cid": f"QmTest{i}",
                    "size_bytes": 1000 + i * 100,
                    "mime_type": "text/plain" if i % 2 == 0 else "application/json",
                    "local": True,
                    "pinned": i % 2 == 0,
                }
                await index.add_async(test_record)
            
            # Query with filters
            filters = [("mime_type", "==", "text/plain")]
            results = await index.query_async(filters)
            
            # Verify results
            assert results.num_rows == 3  # Records with i=0, 2, 4
            
            # Query with limit
            limited_results = await index.query_async(limit=2)
            assert limited_results.num_rows == 2
            
            # Query with count
            count = await index.count_async(filters)
            assert count == 3
            
        finally:
            # Clean up
            await index.close_async()
    
    @pytest.mark.anyio
    async def test_update_stats_async(self, temp_index_dir):
        """Test updating record statistics asynchronously."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        try:
            # Add test record
            test_cid = "QmTest456"
            test_record = {
                "cid": test_cid,
                "access_count": 0,
            }
            await index.add_async(test_record)
            
            # Update stats asynchronously
            success = await index.update_stats_async(test_cid)
            assert success is True
            
            # Verify stats were updated
            updated = await index.get_by_cid_async(test_cid)
            assert updated is not None
            assert updated["access_count"] == 1
            
        finally:
            # Clean up
            await index.close_async()
    
    @pytest.mark.anyio
    async def test_delete_by_cid_async(self, temp_index_dir):
        """Test deleting a record asynchronously."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        try:
            # Add test record
            test_cid = "QmTestDelete"
            test_record = {
                "cid": test_cid,
                "size_bytes": 2048,
            }
            await index.add_async(test_record)
            
            # Verify record exists
            assert await index.get_by_cid_async(test_cid) is not None
            
            # Delete record asynchronously
            success = await index.delete_by_cid_async(test_cid)
            assert success is True
            
            # Verify record was deleted
            assert await index.get_by_cid_async(test_cid) is None
            
        finally:
            # Clean up
            await index.close_async()
    
    @pytest.mark.anyio
    async def test_utility_functions_async(self, temp_index_dir, mocker):
        """Test the async utility functions."""
        # Initialize the index
        index = ArrowMetadataIndexAnyIO(
            index_dir=temp_index_dir,
            role="leecher",
            sync_interval=1,
            enable_c_interface=False,
        )
        
        try:
            # Mock IPFS client for create_metadata_from_ipfs_file_async
            mock_ipfs_client = mocker.MagicMock()
            mock_ipfs_client.ipfs_object_stat.return_value = {
                "success": True,
                "Stats": {"CumulativeSize": 1024, "NumBlocks": 1, "NumLinks": 0}
            }
            
            # Test create_metadata_from_ipfs_file_async
            test_cid = "QmTestUtility"
            metadata = await create_metadata_from_ipfs_file_async(mock_ipfs_client, test_cid, False)
            assert "cid" in metadata
            assert metadata["cid"] == test_cid
            
            # For the other utility functions, we'll just test they don't throw exceptions
            # since they depend on actual index data
            
            # Add some records for AI/ML functions
            ai_record = {
                "cid": "QmTestModel",
                "properties": {"type": "ml_model", "model_name": "TestModel", "framework": "pytorch"}
            }
            await index.add_async(ai_record)
            
            # Test find_ai_ml_resources_async
            resources = await find_ai_ml_resources_async(index, {"resource_type": "ml_model"})
            assert "success" in resources
            
            # Test find_similar_models_async (may not find actual similar models in our test)
            models = await find_similar_models_async(index, "QmTestModel")
            assert "success" in models
            
            # Test find_datasets_for_task_async
            datasets = await find_datasets_for_task_async(index, "classification")
            assert "success" in datasets
            
        finally:
            # Clean up
            await index.close_async()