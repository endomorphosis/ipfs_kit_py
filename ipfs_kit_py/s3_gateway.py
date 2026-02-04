#!/usr/bin/env python3
"""
S3-Compatible Gateway for IPFS Kit

Provides an S3-compatible HTTP API for accessing IPFS content,
allowing tools and applications that work with S3 to work with IPFS.
"""

import anyio
import hashlib
import hmac
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote

try:
    from fastapi import FastAPI, Request, Response, HTTPException
    from fastapi.responses import StreamingResponse, JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    # Provide dummy classes if FastAPI not available
    class FastAPI:
        pass
    class Request:
        pass
    class Response:
        pass
    class HTTPException:
        pass

logger = logging.getLogger(__name__)


class S3Gateway:
    """
    S3-compatible gateway for IPFS Kit.
    
    Implements a subset of the S3 API to allow S3-compatible tools
    to interact with IPFS content.
    """
    
    def __init__(self, ipfs_api=None, vfs=None, host: str = "0.0.0.0", port: int = 9000):
        """Initialize S3 gateway."""
        if not HAS_FASTAPI:
            raise ImportError("FastAPI is required for S3 gateway. Install with: pip install fastapi uvicorn")
        
        self.ipfs_api = ipfs_api
        self.vfs = vfs
        self.host = host
        self.port = port
        self.app = FastAPI(title="IPFS S3 Gateway", version="1.0.0")
        
        # S3 gateway configuration
        self.region = "us-east-1"
        self.service = "s3"
        
        # Setup routes
        self._setup_routes()
        
        logger.info(f"S3 Gateway initialized on {host}:{port}")
    
    def _setup_routes(self):
        """Setup S3-compatible API routes."""
        
        # List buckets
        @self.app.get("/")
        async def list_buckets(request: Request):
            """List all buckets (VFS buckets in IPFS)."""
            try:
                # Get VFS buckets from IPFS
                buckets = await self._get_vfs_buckets()
                
                # Format as S3 response
                response = {
                    "ListAllMyBucketsResult": {
                        "Owner": {
                            "ID": "ipfs-kit",
                            "DisplayName": "IPFS Kit"
                        },
                        "Buckets": {
                            "Bucket": [
                                {
                                    "Name": bucket["name"],
                                    "CreationDate": bucket.get("created", datetime.utcnow().isoformat() + "Z")
                                }
                                for bucket in buckets
                            ]
                        }
                    }
                }
                
                return Response(
                    content=self._dict_to_xml(response),
                    media_type="application/xml"
                )
            except Exception as e:
                logger.error(f"Error listing buckets: {e}")
                return self._error_response("InternalError", str(e))
        
        # List objects in bucket
        @self.app.get("/{bucket}")
        async def list_objects(bucket: str, request: Request):
            """List objects in a bucket."""
            try:
                prefix = request.query_params.get("prefix", "")
                max_keys = int(request.query_params.get("max-keys", 1000))
                
                # Get objects from IPFS VFS
                objects = await self._list_bucket_objects(bucket, prefix, max_keys)
                
                response = {
                    "ListBucketResult": {
                        "Name": bucket,
                        "Prefix": prefix,
                        "MaxKeys": max_keys,
                        "IsTruncated": "false",
                        "Contents": [
                            {
                                "Key": obj["key"],
                                "LastModified": obj.get("modified", datetime.utcnow().isoformat() + "Z"),
                                "ETag": f'"{obj["hash"]}"',
                                "Size": obj["size"],
                                "StorageClass": "STANDARD"
                            }
                            for obj in objects
                        ]
                    }
                }
                
                return Response(
                    content=self._dict_to_xml(response),
                    media_type="application/xml"
                )
            except Exception as e:
                logger.error(f"Error listing objects in {bucket}: {e}")
                return self._error_response("NoSuchBucket", f"Bucket {bucket} not found")
        
        # Get object
        @self.app.get("/{bucket}/{path:path}")
        async def get_object(bucket: str, path: str, request: Request):
            """Get an object from a bucket."""
            try:
                # Get object from IPFS
                content = await self._get_object(bucket, path)
                
                if content is None:
                    return self._error_response("NoSuchKey", f"Key {path} not found")
                
                # Calculate ETag
                etag = hashlib.md5(content).hexdigest()
                
                return Response(
                    content=content,
                    headers={
                        "ETag": f'"{etag}"',
                        "Content-Length": str(len(content)),
                        "Accept-Ranges": "bytes"
                    }
                )
            except Exception as e:
                logger.error(f"Error getting object {bucket}/{path}: {e}")
                return self._error_response("InternalError", str(e))
        
        # Put object
        @self.app.put("/{bucket}/{path:path}")
        async def put_object(bucket: str, path: str, request: Request):
            """Put an object into a bucket."""
            try:
                # Read request body
                content = await request.body()
                
                # Store in IPFS
                result = await self._put_object(bucket, path, content)
                
                # Calculate ETag
                etag = hashlib.md5(content).hexdigest()
                
                return Response(
                    status_code=200,
                    headers={
                        "ETag": f'"{etag}"'
                    }
                )
            except Exception as e:
                logger.error(f"Error putting object {bucket}/{path}: {e}")
                return self._error_response("InternalError", str(e))
        
        # Delete object
        @self.app.delete("/{bucket}/{path:path}")
        async def delete_object(bucket: str, path: str):
            """Delete an object from a bucket."""
            try:
                await self._delete_object(bucket, path)
                return Response(status_code=204)
            except Exception as e:
                logger.error(f"Error deleting object {bucket}/{path}: {e}")
                return self._error_response("InternalError", str(e))
        
        # Head object
        @self.app.head("/{bucket}/{path:path}")
        async def head_object(bucket: str, path: str):
            """Get object metadata."""
            try:
                metadata = await self._get_object_metadata(bucket, path)
                
                if metadata is None:
                    return Response(status_code=404)
                
                return Response(
                    status_code=200,
                    headers={
                        "ETag": f'"{metadata["hash"]}"',
                        "Content-Length": str(metadata["size"]),
                        "Last-Modified": metadata.get("modified", "")
                    }
                )
            except Exception as e:
                logger.error(f"Error getting metadata for {bucket}/{path}: {e}")
                return Response(status_code=500)
    
    async def _get_vfs_buckets(self) -> List[Dict[str, Any]]:
        """Get list of VFS buckets."""
        if self.ipfs_api is None:
            return []
        
        try:
            # Get buckets from VFS manager
            if hasattr(self.ipfs_api, 'list_buckets'):
                return await self.ipfs_api.list_buckets()
            return []
        except Exception as e:
            logger.error(f"Error getting VFS buckets: {e}")
            return []
    
    async def _list_bucket_objects(self, bucket: str, prefix: str, max_keys: int) -> List[Dict[str, Any]]:
        """List objects in a bucket."""
        if self.ipfs_api is None:
            return []
        
        try:
            # List files from VFS
            if hasattr(self.ipfs_api, 'vfs_ls'):
                path = f"/{bucket}/{prefix}" if prefix else f"/{bucket}"
                files = await self.ipfs_api.vfs_ls(path)
                
                objects = []
                for file in files[:max_keys]:
                    objects.append({
                        "key": file.get("name", ""),
                        "hash": file.get("hash", ""),
                        "size": file.get("size", 0),
                        "modified": file.get("modified", datetime.utcnow().isoformat() + "Z")
                    })
                return objects
            return []
        except Exception as e:
            logger.error(f"Error listing bucket objects: {e}")
            return []
    
    async def _get_object(self, bucket: str, path: str) -> Optional[bytes]:
        """Get object content."""
        if self.ipfs_api is None:
            return None
        
        try:
            # Get file from VFS
            if hasattr(self.ipfs_api, 'vfs_read'):
                vfs_path = f"/{bucket}/{path}"
                return await self.ipfs_api.vfs_read(vfs_path)
            return None
        except Exception as e:
            logger.error(f"Error getting object: {e}")
            return None

    async def _get_object_from_ipfs(self, cid: str) -> Optional[bytes]:
        """Fetch raw object bytes from IPFS by CID (test helper)."""
        if self.ipfs_api is None:
            return None
        try:
            if hasattr(self.ipfs_api, "cat"):
                return await self.ipfs_api.cat(cid)
        except Exception as e:
            logger.error(f"Error fetching CID {cid} from IPFS: {e}")
            return None
        return None
    
    async def _put_object(self, bucket: str, path: str, content: bytes) -> Dict[str, Any]:
        """Put object content."""
        if self.ipfs_api is None:
            raise Exception("IPFS API not initialized")
        
        try:
            # Write file to VFS
            if hasattr(self.ipfs_api, 'vfs_write'):
                vfs_path = f"/{bucket}/{path}"
                return await self.ipfs_api.vfs_write(vfs_path, content)
            raise Exception("VFS write not supported")
        except Exception as e:
            logger.error(f"Error putting object: {e}")
            raise
    
    async def _delete_object(self, bucket: str, path: str) -> bool:
        """Delete object."""
        if self.ipfs_api is None:
            return False
        
        try:
            # Delete file from VFS
            if hasattr(self.ipfs_api, 'vfs_rm'):
                vfs_path = f"/{bucket}/{path}"
                return await self.ipfs_api.vfs_rm(vfs_path)
            return False
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            return False

    async def _get_vfs_bucket_objects(self, bucket: str) -> List[Any]:
        """List objects in a bucket via the optional VFS adapter (test helper)."""
        if self.vfs is None:
            return []
        try:
            if hasattr(self.vfs, "list_bucket"):
                return await self.vfs.list_bucket(bucket)
            if hasattr(self.vfs, "list_objects"):
                return await self.vfs.list_objects(bucket)
        except Exception as e:
            logger.error(f"Error listing VFS bucket {bucket}: {e}")
            return []
        return []
    
    async def _get_object_metadata(self, bucket: str, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        if self.ipfs_api is None:
            return None
        
        try:
            # Get file stat from VFS
            if hasattr(self.ipfs_api, 'vfs_stat'):
                vfs_path = f"/{bucket}/{path}"
                return await self.ipfs_api.vfs_stat(vfs_path)
            return None
        except Exception as e:
            logger.error(f"Error getting object metadata: {e}")
            return None
    
    def _dict_to_xml(self, data: Dict[str, Any], root_name: Optional[str] = None) -> str:
        """Convert dict to XML string."""

        def dict_to_xml_recursive(d: Dict[str, Any], wrap_name: Optional[str] = None) -> str:
            xml: List[str] = []
            if wrap_name:
                xml.append(f"<{wrap_name}>")

            for key, value in d.items():
                if isinstance(value, dict):
                    xml.append(dict_to_xml_recursive(value, key))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml.append(dict_to_xml_recursive(item, key))
                        else:
                            xml.append(f"<{key}>{item}</{key}>")
                else:
                    xml.append(f"<{key}>{value}</{key}>")

            if wrap_name:
                xml.append(f"</{wrap_name}>")
            return "".join(xml)

        xml_header = '<?xml version="1.0" encoding="UTF-8"?>'
        xml_body = dict_to_xml_recursive(data, root_name)
        return xml_header + xml_body
    
    def _error_response(self, code: str, message: str) -> Response:
        """Create S3 error response."""
        error_xml = self._create_error_response(code, message)
        
        return Response(
            content=error_xml,
            status_code=400 if code != "InternalError" else 500,
            media_type="application/xml"
        )

    def _create_error_response(
        self,
        code: str,
        message: str,
        resource: str = "",
        request_id: Optional[str] = None,
    ) -> str:
        """Create an S3-style XML error document as a string."""
        req_id = request_id or str(int(time.time()))
        resource_xml = f"\n    <Resource>{resource}</Resource>" if resource else ""
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Error>\n"
            f"    <Code>{code}</Code>\n"
            f"    <Message>{message}</Message>{resource_xml}\n"
            f"    <RequestId>{req_id}</RequestId>\n"
            "</Error>"
        )
    
    def run(self):
        """Run the S3 gateway server."""
        try:
            import uvicorn
            uvicorn.run(self.app, host=self.host, port=self.port)
        except ImportError:
            raise ImportError("uvicorn is required to run S3 gateway. Install with: pip install uvicorn")
    
    async def start(self):
        """Start the S3 gateway server asynchronously."""
        try:
            import uvicorn
            config = uvicorn.Config(self.app, host=self.host, port=self.port)
            server = uvicorn.Server(config)
            await server.serve()
        except ImportError:
            raise ImportError("uvicorn is required to run S3 gateway. Install with: pip install uvicorn")


# Convenience function
def create_s3_gateway(ipfs_api=None, host: str = "0.0.0.0", port: int = 9000) -> S3Gateway:
    """Create and return an S3 gateway instance."""
    return S3Gateway(ipfs_api=ipfs_api, host=host, port=port)
