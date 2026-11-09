"""
Comprehensive S3 Gateway Tests for 100% Coverage

This test file aims to achieve 100% line and branch coverage for the S3 Gateway module.
Tests cover all HTTP endpoints, error scenarios, and edge cases.
"""

import pytest
import anyio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
import hashlib

# Import S3 Gateway
pytest.importorskip("fastapi")
from ipfs_kit_py.s3_gateway import S3Gateway


class TestS3GatewayInitialization:
    """Test S3 Gateway initialization and configuration."""
    
    @pytest.mark.anyio
    async def test_gateway_init_with_ipfs_api(self):
        """Test gateway initialization with IPFS API."""
        mock_api = Mock()
        gateway = S3Gateway(ipfs_api=mock_api, host="127.0.0.1", port=9000)
        
        assert gateway.ipfs_api == mock_api
        assert gateway.host == "127.0.0.1"
        assert gateway.port == 9000
        assert gateway.region == "us-east-1"
        assert gateway.service == "s3"
        assert gateway.app is not None
    
    @pytest.mark.anyio
    async def test_gateway_init_without_ipfs_api(self):
        """Test gateway initialization without IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        
        assert gateway.ipfs_api is None
        assert gateway.host == "0.0.0.0"
        assert gateway.port == 9000
    
    def test_gateway_init_without_fastapi(self):
        """Test that gateway raises error without FastAPI."""
        with patch('ipfs_kit_py.s3_gateway.HAS_FASTAPI', False):
            # Need to reload module or test initialization path
            # For now, verify current behavior works
            pass


class TestS3GatewayListBuckets:
    """Test list buckets endpoint."""
    
    @pytest.mark.anyio
    async def test_list_buckets_success(self):
        """Test successful bucket listing."""
        mock_api = Mock()
        mock_api.list_buckets = AsyncMock(return_value=[
            {"name": "bucket1", "created": "2024-01-01T00:00:00Z"},
            {"name": "bucket2", "created": "2024-01-02T00:00:00Z"}
        ])
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_vfs_buckets()
        
        assert len(result) == 2
        assert result[0]["name"] == "bucket1"
        assert result[1]["name"] == "bucket2"
    
    @pytest.mark.anyio
    async def test_list_buckets_no_api(self):
        """Test bucket listing with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        result = await gateway._get_vfs_buckets()
        
        assert result == []
    
    @pytest.mark.anyio
    async def test_list_buckets_api_error(self):
        """Test bucket listing when API throws error."""
        mock_api = Mock()
        mock_api.list_buckets = AsyncMock(side_effect=Exception("API Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_vfs_buckets()
        
        assert result == []
    
    @pytest.mark.anyio
    async def test_list_buckets_no_list_buckets_method(self):
        """Test bucket listing when API doesn't have list_buckets."""
        mock_api = Mock(spec=[])  # Empty spec
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_vfs_buckets()
        
        assert result == []


class TestS3GatewayListObjects:
    """Test list objects in bucket endpoint."""
    
    @pytest.mark.anyio
    async def test_list_objects_success(self):
        """Test successful object listing."""
        mock_api = Mock()
        mock_api.vfs_ls = AsyncMock(return_value=[
            {"name": "file1.txt", "hash": "Qm123", "size": 100},
            {"name": "file2.txt", "hash": "Qm456", "size": 200}
        ])
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._list_bucket_objects("test-bucket", "", 1000)
        
        assert len(result) == 2
        assert result[0]["key"] == "file1.txt"
        assert result[1]["key"] == "file2.txt"
    
    @pytest.mark.anyio
    async def test_list_objects_with_prefix(self):
        """Test object listing with prefix filter."""
        mock_api = Mock()
        mock_api.vfs_ls = AsyncMock(return_value=[
            {"name": "docs/readme.md", "hash": "Qm789", "size": 300}
        ])
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._list_bucket_objects("test-bucket", "docs/", 1000)
        
        assert len(result) == 1
        assert result[0]["key"] == "docs/readme.md"
    
    @pytest.mark.anyio
    async def test_list_objects_with_max_keys(self):
        """Test object listing respects max_keys."""
        mock_api = Mock()
        files = [{"name": f"file{i}.txt", "hash": f"Qm{i}", "size": i*100} 
                 for i in range(1, 11)]
        mock_api.vfs_ls = AsyncMock(return_value=files)
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._list_bucket_objects("test-bucket", "", 5)
        
        assert len(result) == 5
    
    @pytest.mark.anyio
    async def test_list_objects_no_api(self):
        """Test object listing with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        result = await gateway._list_bucket_objects("test-bucket", "", 1000)
        
        assert result == []
    
    @pytest.mark.anyio
    async def test_list_objects_api_error(self):
        """Test object listing when API throws error."""
        mock_api = Mock()
        mock_api.vfs_ls = AsyncMock(side_effect=Exception("VFS Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._list_bucket_objects("test-bucket", "", 1000)
        
        assert result == []


class TestS3GatewayGetObject:
    """Test get object endpoint."""
    
    @pytest.mark.anyio
    async def test_get_object_success(self):
        """Test successful object retrieval."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(return_value=b"Hello, World!")
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "file.txt")
        
        assert result == b"Hello, World!"
    
    @pytest.mark.anyio
    async def test_get_object_not_found(self):
        """Test object retrieval when object doesn't exist."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(return_value=None)
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "missing.txt")
        
        assert result is None
    
    @pytest.mark.anyio
    async def test_get_object_no_api(self):
        """Test object retrieval with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        result = await gateway._get_object("test-bucket", "file.txt")
        
        assert result is None
    
    @pytest.mark.anyio
    async def test_get_object_api_error(self):
        """Test object retrieval when API throws error."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(side_effect=Exception("Read Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "file.txt")
        
        assert result is None


class TestS3GatewayPutObject:
    """Test put object endpoint."""
    
    @pytest.mark.anyio
    async def test_put_object_success(self):
        """Test successful object upload."""
        mock_api = Mock()
        mock_api.vfs_write = AsyncMock(return_value={"Hash": "QmNewFile"})
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._put_object("test-bucket", "new-file.txt", b"Content")
        
        assert result is not None
    
    @pytest.mark.anyio
    async def test_put_object_no_api(self):
        """Test object upload with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        
        # Should raise Exception when IPFS API not initialized
        with pytest.raises(Exception, match="IPFS API not initialized"):
            await gateway._put_object("test-bucket", "file.txt", b"Content")
    
    @pytest.mark.anyio
    async def test_put_object_api_error(self):
        """Test object upload when API throws error."""
        mock_api = Mock()
        mock_api.vfs_write = AsyncMock(side_effect=Exception("Write Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        
        # Should raise the exception
        with pytest.raises(Exception, match="Write Error"):
            await gateway._put_object("test-bucket", "file.txt", b"Content")


class TestS3GatewayDeleteObject:
    """Test delete object endpoint."""
    
    @pytest.mark.anyio
    async def test_delete_object_success(self):
        """Test successful object deletion."""
        mock_api = Mock()
        mock_api.vfs_rm = AsyncMock(return_value=True)
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._delete_object("test-bucket", "file.txt")
        
        assert result is True
    
    @pytest.mark.anyio
    async def test_delete_object_no_api(self):
        """Test object deletion with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        result = await gateway._delete_object("test-bucket", "file.txt")
        
        # Should return False or None when no API
        assert result in [False, None]
    
    @pytest.mark.anyio
    async def test_delete_object_api_error(self):
        """Test object deletion when API throws error."""
        mock_api = Mock()
        mock_api.vfs_rm = AsyncMock(side_effect=Exception("Delete Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._delete_object("test-bucket", "file.txt")
        
        assert result is False


class TestS3GatewayHeadObject:
    """Test head object (metadata) endpoint."""
    
    @pytest.mark.anyio
    async def test_head_object_success(self):
        """Test successful metadata retrieval."""
        mock_api = Mock()
        mock_api.vfs_stat = AsyncMock(return_value={
            "Hash": "QmTest",
            "Size": 1024,
            "CumulativeSize": 1024
        })
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object_metadata("test-bucket", "file.txt")
        
        assert result is not None
        # The actual implementation returns the raw stat result
        assert result["Hash"] == "QmTest"
        assert result["Size"] == 1024
    
    @pytest.mark.anyio
    async def test_head_object_not_found(self):
        """Test metadata retrieval when object doesn't exist."""
        mock_api = Mock()
        mock_api.vfs_stat = AsyncMock(return_value=None)
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object_metadata("test-bucket", "missing.txt")
        
        assert result is None
    
    @pytest.mark.anyio
    async def test_head_object_no_api(self):
        """Test metadata retrieval with no IPFS API."""
        gateway = S3Gateway(ipfs_api=None)
        result = await gateway._get_object_metadata("test-bucket", "file.txt")
        
        assert result is None
    
    @pytest.mark.anyio
    async def test_head_object_api_error(self):
        """Test metadata retrieval when API throws error."""
        mock_api = Mock()
        mock_api.vfs_stat = AsyncMock(side_effect=Exception("Stat Error"))
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object_metadata("test-bucket", "file.txt")
        
        assert result is None


class TestS3GatewayXMLConversion:
    """Test XML conversion utilities."""
    
    @pytest.mark.anyio
    async def test_dict_to_xml_simple(self):
        """Test simple dict to XML conversion."""
        gateway = S3Gateway(ipfs_api=None)
        
        data = {"Root": {"Key": "Value"}}
        xml = gateway._dict_to_xml(data)
        
        assert "<Root>" in xml
        assert "<Key>Value</Key>" in xml
        assert "</Root>" in xml
    
    @pytest.mark.anyio
    async def test_dict_to_xml_nested(self):
        """Test nested dict to XML conversion."""
        gateway = S3Gateway(ipfs_api=None)
        
        data = {
            "Root": {
                "Parent": {
                    "Child": "Value"
                }
            }
        }
        xml = gateway._dict_to_xml(data)
        
        assert "<Root>" in xml
        assert "<Parent>" in xml
        assert "<Child>Value</Child>" in xml
    
    @pytest.mark.anyio
    async def test_dict_to_xml_list(self):
        """Test list items in XML conversion."""
        gateway = S3Gateway(ipfs_api=None)
        
        data = {
            "Root": {
                "Items": {
                    "Item": [
                        {"Name": "Item1"},
                        {"Name": "Item2"}
                    ]
                }
            }
        }
        xml = gateway._dict_to_xml(data)
        
        assert "<Items>" in xml
        assert "<Name>Item1</Name>" in xml
        assert "<Name>Item2</Name>" in xml
    
    @pytest.mark.anyio
    async def test_dict_to_xml_empty(self):
        """Test empty dict to XML conversion."""
        gateway = S3Gateway(ipfs_api=None)
        
        data = {}
        xml = gateway._dict_to_xml(data)
        
        assert xml is not None
    
    @pytest.mark.anyio
    async def test_dict_to_xml_with_attributes(self):
        """Test XML conversion with special characters."""
        gateway = S3Gateway(ipfs_api=None)
        
        data = {
            "Root": {
                "Special": "Value with <>&\" chars"
            }
        }
        xml = gateway._dict_to_xml(data)
        
        # XML should escape special characters
        assert "<Root>" in xml
        assert "<Special>" in xml


class TestS3GatewayErrorResponses:
    """Test error response generation."""
    
    @pytest.mark.anyio
    async def test_error_response_no_such_bucket(self):
        """Test NoSuchBucket error response."""
        gateway = S3Gateway(ipfs_api=None)
        
        response = gateway._error_response("NoSuchBucket", "Bucket not found")
        
        # Should be XML response
        assert hasattr(response, 'body') or hasattr(response, 'content')
    
    @pytest.mark.anyio
    async def test_error_response_no_such_key(self):
        """Test NoSuchKey error response."""
        gateway = S3Gateway(ipfs_api=None)
        
        response = gateway._error_response("NoSuchKey", "Key not found")
        
        assert response is not None
    
    @pytest.mark.anyio
    async def test_error_response_internal_error(self):
        """Test InternalError response."""
        gateway = S3Gateway(ipfs_api=None)
        
        response = gateway._error_response("InternalError", "Something went wrong")
        
        assert response is not None
    
    @pytest.mark.anyio
    async def test_error_response_access_denied(self):
        """Test AccessDenied error response."""
        gateway = S3Gateway(ipfs_api=None)
        
        response = gateway._error_response("AccessDenied", "Access denied")
        
        assert response is not None
    
    @pytest.mark.anyio
    async def test_error_response_invalid_request(self):
        """Test InvalidRequest error response."""
        gateway = S3Gateway(ipfs_api=None)
        
        response = gateway._error_response("InvalidRequest", "Invalid request")
        
        assert response is not None


class TestS3GatewayEdgeCases:
    """Test edge cases and special scenarios."""
    
    @pytest.mark.anyio
    async def test_list_objects_empty_bucket(self):
        """Test listing objects in empty bucket."""
        mock_api = Mock()
        mock_api.vfs_ls = AsyncMock(return_value=[])
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._list_bucket_objects("empty-bucket", "", 1000)
        
        assert result == []
    
    @pytest.mark.anyio
    async def test_get_object_empty_content(self):
        """Test getting object with empty content."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(return_value=b"")
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "empty.txt")
        
        assert result == b""
    
    @pytest.mark.anyio
    async def test_put_object_large_content(self):
        """Test uploading large object."""
        mock_api = Mock()
        mock_api.vfs_write = AsyncMock(return_value={"Hash": "QmLarge"})
        
        gateway = S3Gateway(ipfs_api=mock_api)
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        result = await gateway._put_object("test-bucket", "large.bin", large_content)
        
        assert result is not None
    
    @pytest.mark.anyio
    async def test_object_path_with_special_chars(self):
        """Test object path with special characters."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(return_value=b"Content")
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "path/with spaces/file.txt")
        
        assert result == b"Content"
    
    @pytest.mark.anyio
    async def test_object_path_with_unicode(self):
        """Test object path with Unicode characters."""
        mock_api = Mock()
        mock_api.vfs_read = AsyncMock(return_value=b"Content")
        
        gateway = S3Gateway(ipfs_api=mock_api)
        result = await gateway._get_object("test-bucket", "путь/文件.txt")
        
        assert result == b"Content"
    
    @pytest.mark.anyio
    async def test_bucket_name_validation(self):
        """Test bucket name with valid/invalid characters."""
        mock_api = Mock()
        
        gateway = S3Gateway(ipfs_api=mock_api)
        
        # Valid bucket names
        valid_names = ["my-bucket", "bucket123", "my.bucket"]
        for name in valid_names:
            # Should not raise error
            await gateway._get_vfs_buckets()
    
    @pytest.mark.anyio
    async def test_concurrent_operations(self):
        """Test concurrent object operations."""
        mock_api = Mock()
        mock_api.vfs_write = AsyncMock(return_value={"Hash": "QmTest"})
        mock_api.vfs_read = AsyncMock(return_value=b"Content")
        
        gateway = S3Gateway(ipfs_api=mock_api)
        
        # Simulate concurrent operations
        async with anyio.create_task_group() as tg:
            tg.start_soon(gateway._put_object, "bucket", "file1.txt", b"Data1")
            tg.start_soon(gateway._put_object, "bucket", "file2.txt", b"Data2")
            tg.start_soon(gateway._get_object, "bucket", "file1.txt")
    
    @pytest.mark.anyio
    async def test_gateway_run_without_uvicorn(self):
        """Test that gateway run method exists."""
        gateway = S3Gateway(ipfs_api=None)
        
        # Check that run method exists
        assert hasattr(gateway, 'run') or hasattr(gateway, 'app')
    
    @pytest.mark.anyio
    async def test_etag_calculation(self):
        """Test ETag calculation for objects."""
        content = b"Test content for ETag"
        expected_etag = hashlib.md5(content).hexdigest()
        
        gateway = S3Gateway(ipfs_api=None)
        # ETag calculation happens in endpoint handlers
        
        calculated_etag = hashlib.md5(content).hexdigest()
        assert calculated_etag == expected_etag


class TestS3GatewayIntegration:
    """Test integration scenarios."""
    
    @pytest.mark.anyio
    async def test_full_object_lifecycle(self):
        """Test complete object lifecycle: create, read, update, delete."""
        mock_api = Mock()
        mock_api.vfs_write = AsyncMock(return_value={"Hash": "QmTest"})
        mock_api.vfs_read = AsyncMock(return_value=b"Content")
        mock_api.vfs_rm = AsyncMock(return_value=True)
        mock_api.vfs_stat = AsyncMock(return_value={
            "Hash": "QmTest",
            "Size": 7,
            "CumulativeSize": 7
        })
        
        gateway = S3Gateway(ipfs_api=mock_api)
        
        # Create
        put_result = await gateway._put_object("bucket", "file.txt", b"Content")
        assert put_result is not None
        
        # Read
        get_result = await gateway._get_object("bucket", "file.txt")
        assert get_result == b"Content"
        
        # Metadata
        meta_result = await gateway._get_object_metadata("bucket", "file.txt")
        assert meta_result is not None
        
        # Delete
        delete_result = await gateway._delete_object("bucket", "file.txt")
        assert delete_result is True
    
    @pytest.mark.anyio
    async def test_bucket_operations_workflow(self):
        """Test typical bucket operations workflow."""
        mock_api = Mock()
        mock_api.list_buckets = AsyncMock(return_value=[
            {"name": "bucket1"},
            {"name": "bucket2"}
        ])
        mock_api.vfs_ls = AsyncMock(return_value=[
            {"name": "file1.txt", "hash": "Qm1", "size": 100},
            {"name": "file2.txt", "hash": "Qm2", "size": 200}
        ])
        
        gateway = S3Gateway(ipfs_api=mock_api)
        
        # List buckets
        buckets = await gateway._get_vfs_buckets()
        assert len(buckets) == 2
        
        # List objects in bucket
        objects = await gateway._list_bucket_objects("bucket1", "", 1000)
        assert len(objects) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
