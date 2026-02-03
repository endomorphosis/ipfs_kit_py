#!/usr/bin/env python3
"""
Extended tests for S3-compatible gateway.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path


class TestS3GatewayExtended:
    """Extended tests for S3 Gateway functionality."""
    
    def test_s3_gateway_without_fastapi(self):
        """Test error when FastAPI not available."""
        with patch('ipfs_kit_py.s3_gateway.HAS_FASTAPI', False):
            from ipfs_kit_py.s3_gateway import S3Gateway
            
            with pytest.raises(ImportError, match="FastAPI is required"):
                gateway = S3Gateway()
    
    def test_s3_gateway_configuration(self):
        """Test S3 gateway configuration options."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        mock_ipfs = Mock()
        gateway = S3Gateway(ipfs_api=mock_ipfs, host="192.168.1.1", port=8080)
        
        assert gateway.ipfs_api == mock_ipfs
        assert gateway.host == "192.168.1.1"
        assert gateway.port == 8080
        assert gateway.region == "us-east-1"
        assert gateway.service == "s3"
    
    @pytest.mark.asyncio
    async def test_get_vfs_buckets(self):
        """Test getting VFS buckets."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        mock_ipfs = AsyncMock()
        gateway = S3Gateway(ipfs_api=mock_ipfs)
        
        # Test with no IPFS API
        gateway.ipfs_api = None
        buckets = await gateway._get_vfs_buckets()
        assert buckets == []
        
        # Test with mock bucket manager
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.list_buckets = AsyncMock(return_value=[
            {"name": "bucket1", "created": "2024-01-01T00:00:00Z"},
            {"name": "bucket2", "created": "2024-01-02T00:00:00Z"}
        ])
        gateway.ipfs_api = mock_ipfs
        
        buckets = await gateway._get_vfs_buckets()
        assert len(buckets) == 2
        assert buckets[0]["name"] == "bucket1"
    
    @pytest.mark.asyncio
    async def test_get_bucket_objects(self):
        """Test getting objects from a bucket."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test with no IPFS API
        objects = await gateway._get_bucket_objects("test-bucket")
        assert objects == []
        
        # Test with mock bucket
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.list_files = AsyncMock(return_value=[
            {"path": "file1.txt", "size": 100, "modified": 1234567890},
            {"path": "file2.txt", "size": 200, "modified": 1234567900}
        ])
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        gateway.ipfs_api = mock_ipfs
        
        objects = await gateway._get_bucket_objects("test-bucket")
        assert len(objects) == 2
        assert objects[0]["path"] == "file1.txt"
    
    @pytest.mark.asyncio
    async def test_get_object_content(self):
        """Test retrieving object content."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test with no IPFS API
        content = await gateway._get_object_content("bucket", "key")
        assert content is None
        
        # Test with mock content
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.get_file = AsyncMock(return_value=b"test content")
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        gateway.ipfs_api = mock_ipfs
        
        content = await gateway._get_object_content("bucket", "key")
        assert content == b"test content"
    
    @pytest.mark.asyncio
    async def test_put_object_content(self):
        """Test uploading object content."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test with no IPFS API
        result = await gateway._put_object_content("bucket", "key", b"content")
        assert result is False
        
        # Test with mock upload
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.put_file = AsyncMock(return_value={"success": True})
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        gateway.ipfs_api = mock_ipfs
        
        result = await gateway._put_object_content("bucket", "key", b"content")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_object(self):
        """Test deleting an object."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test with no IPFS API
        result = await gateway._delete_object("bucket", "key")
        assert result is False
        
        # Test with mock delete
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.delete_file = AsyncMock(return_value={"success": True})
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        gateway.ipfs_api = mock_ipfs
        
        result = await gateway._delete_object("bucket", "key")
        assert result is True
    
    def test_dict_to_xml_nested(self):
        """Test XML conversion with nested structures."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        test_dict = {
            "Root": {
                "Child1": "value1",
                "Child2": {
                    "GrandChild": "value2"
                },
                "Child3": ["item1", "item2", "item3"]
            }
        }
        
        xml = gateway._dict_to_xml(test_dict)
        assert "<?xml version" in xml
        assert "<Root>" in xml
        assert "<Child1>value1</Child1>" in xml
        assert "<GrandChild>value2</GrandChild>" in xml
    
    def test_dict_to_xml_with_attributes(self):
        """Test XML conversion with XML attributes."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        test_dict = {
            "Element": {
                "@attr": "value",
                "content": "text"
            }
        }
        
        xml = gateway._dict_to_xml(test_dict)
        assert "<Element" in xml
    
    def test_dict_to_xml_with_lists(self):
        """Test XML conversion with lists."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        test_dict = {
            "Items": {
                "Item": [
                    {"Name": "item1"},
                    {"Name": "item2"},
                    {"Name": "item3"}
                ]
            }
        }
        
        xml = gateway._dict_to_xml(test_dict)
        assert xml.count("<Item>") == 3
        assert "<Name>item1</Name>" in xml
    
    def test_parse_s3_auth_header(self):
        """Test parsing S3 authentication headers."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test AWS4-HMAC-SHA256 signature
        auth_header = "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20240101/us-east-1/s3/aws4_request, SignedHeaders=host;x-amz-date, Signature=abc123"
        
        result = gateway._parse_auth_header(auth_header)
        
        assert result["algorithm"] == "AWS4-HMAC-SHA256"
        assert "Credential" in result
    
    def test_generate_etag(self):
        """Test ETag generation for objects."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        content = b"test content"
        etag = gateway._generate_etag(content)
        
        assert etag is not None
        assert len(etag) > 0
        assert etag == gateway._generate_etag(content)  # Should be consistent
    
    def test_format_list_bucket_response(self):
        """Test formatting list bucket response."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        objects = [
            {"path": "file1.txt", "size": 100, "modified": 1234567890, "etag": "abc123"},
            {"path": "dir/file2.txt", "size": 200, "modified": 1234567900, "etag": "def456"}
        ]
        
        response = gateway._format_list_bucket_response("test-bucket", objects)
        
        assert "ListBucketResult" in response
        assert response["ListBucketResult"]["Name"] == "test-bucket"
        assert "Contents" in response["ListBucketResult"]
    
    def test_format_error_response(self):
        """Test formatting S3 error responses."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        error_response = gateway._format_error_response("NoSuchBucket", "Bucket not found", "test-bucket")
        
        assert "Error" in error_response
        assert error_response["Error"]["Code"] == "NoSuchBucket"
        assert error_response["Error"]["Message"] == "Bucket not found"
    
    @pytest.mark.asyncio
    async def test_head_object(self):
        """Test HEAD request for object metadata."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.get_file_metadata = AsyncMock(return_value={
            "size": 100,
            "modified": 1234567890,
            "content_type": "text/plain"
        })
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        
        gateway = S3Gateway(ipfs_api=mock_ipfs)
        
        metadata = await gateway._head_object("bucket", "key")
        
        assert metadata is not None
        assert metadata["size"] == 100
    
    def test_url_encoding(self):
        """Test URL encoding/decoding for object keys."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        # Test special characters in keys
        key_with_spaces = "file with spaces.txt"
        key_with_special = "file+name&special=chars.txt"
        
        # These should handle encoding properly
        encoded1 = gateway._encode_key(key_with_spaces)
        assert " " not in encoded1 or "%20" in encoded1
        
        decoded1 = gateway._decode_key(encoded1)
        assert decoded1 == key_with_spaces or decoded1.replace("%20", " ") == key_with_spaces
    
    @pytest.mark.asyncio
    async def test_multipart_upload_init(self):
        """Test initiating multipart upload."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        gateway = S3Gateway()
        
        upload_id = await gateway._init_multipart_upload("bucket", "key")
        
        assert upload_id is not None
        assert len(upload_id) > 0
    
    @pytest.mark.asyncio
    async def test_copy_object(self):
        """Test copying an object."""
        pytest.importorskip("fastapi", reason="FastAPI not installed")
        from ipfs_kit_py.s3_gateway import S3Gateway
        
        mock_ipfs = AsyncMock()
        mock_bucket = Mock()
        mock_bucket.copy_file = AsyncMock(return_value={"success": True})
        mock_ipfs.bucket_manager = Mock()
        mock_ipfs.bucket_manager.get_bucket = AsyncMock(return_value=mock_bucket)
        
        gateway = S3Gateway(ipfs_api=mock_ipfs)
        
        result = await gateway._copy_object("src_bucket", "src_key", "dst_bucket", "dst_key")
        
        # Should succeed or gracefully handle
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
