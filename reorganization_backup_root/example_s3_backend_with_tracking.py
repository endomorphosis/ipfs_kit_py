#!/usr/bin/env python3
"""
Example: S3 Backend with Resource Tracking Integration

This shows how to modify an existing backend to automatically track
bandwidth and storage consumption using the resource tracking system.
"""

import logging
import time
import os
from typing import Dict, Any, Optional, Union, BinaryIO

# Import resource tracking components
from ipfs_kit_py.resource_tracker import BackendType, track_bandwidth_upload, track_bandwidth_download, track_storage_usage, track_api_call
from ipfs_kit_py.resource_tracking_decorators import track_operation, track_upload, track_download, track_api

logger = logging.getLogger(__name__)

class S3BackendWithResourceTracking:
    """
    Example S3 Backend with integrated resource tracking.
    
    This demonstrates how to add resource tracking to existing backend operations
    without significantly modifying the original code structure.
    """
    
    def __init__(self, backend_name: str = "s3_primary", **config):
        self.backend_name = backend_name
        self.backend_type = BackendType.S3
        self.config = config
        
        # Initialize original S3 backend components here
        # (AWS credentials, boto3 client, etc.)
        
        logger.info(f"S3 backend '{backend_name}' initialized with resource tracking")
    
    @track_upload('s3_backend', BackendType.S3)
    async def upload_file(self, file_path: str, data: bytes, **kwargs) -> Dict[str, Any]:
        """
        Upload file to S3 with automatic resource tracking.
        
        The @track_upload decorator automatically tracks:
        - Bandwidth upload (bytes uploaded)
        - Operation timing
        - Success/failure status
        """
        operation_id = f"upload_{int(time.time())}"
        
        try:
            # Simulate S3 upload operation
            logger.info(f"Uploading {len(data)} bytes to {file_path}")
            
            # Original S3 upload logic would go here
            # client.put_object(Bucket=bucket, Key=file_path, Body=data)
            
            # Simulate upload time based on size
            upload_time = len(data) / (10 * 1024 * 1024)  # 10MB/s simulated speed
            await asyncio.sleep(min(upload_time, 2.0))  # Cap at 2 seconds for demo
            
            # Track storage usage in addition to bandwidth (handled by decorator)
            track_storage_usage(
                self.backend_name, 
                self.backend_type, 
                len(data), 
                operation_id, 
                file_path
            )
            
            # Track API call
            track_api_call(
                self.backend_name,
                self.backend_type,
                operation_id,
                {"operation": "put_object", "bucket": kwargs.get('bucket', 'default')}
            )
            
            return {
                "success": True,
                "file_path": file_path,
                "size": len(data),
                "operation_id": operation_id
            }
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": operation_id
            }
    
    @track_download('s3_backend', BackendType.S3)
    async def download_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Download file from S3 with automatic resource tracking.
        
        The @track_download decorator automatically tracks:
        - Bandwidth download (bytes downloaded)
        - Operation timing
        - Success/failure status
        """
        operation_id = f"download_{int(time.time())}"
        
        try:
            # Simulate S3 download operation
            logger.info(f"Downloading {file_path}")
            
            # Original S3 download logic would go here
            # response = client.get_object(Bucket=bucket, Key=file_path)
            # data = response['Body'].read()
            
            # Simulate download - create fake data for demo
            simulated_size = kwargs.get('expected_size', 1024 * 1024)  # Default 1MB
            data = b"X" * simulated_size
            
            # Simulate download time
            download_time = len(data) / (20 * 1024 * 1024)  # 20MB/s simulated speed
            await asyncio.sleep(min(download_time, 1.0))  # Cap at 1 second for demo
            
            # Track API call
            track_api_call(
                self.backend_name,
                self.backend_type,
                operation_id,
                {"operation": "get_object", "bucket": kwargs.get('bucket', 'default')}
            )
            
            return {
                "success": True,
                "data": data,
                "size": len(data),
                "operation_id": operation_id
            }
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": operation_id
            }
    
    @track_api('s3_backend', BackendType.S3)
    async def list_objects(self, prefix: str = "", **kwargs) -> Dict[str, Any]:
        """
        List objects in S3 bucket with automatic API call tracking.
        
        The @track_api decorator automatically tracks:
        - API calls (count)
        - Operation timing
        - Success/failure status
        """
        operation_id = f"list_{int(time.time())}"
        
        try:
            logger.info(f"Listing objects with prefix: {prefix}")
            
            # Original S3 list logic would go here
            # response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            # Simulate API response
            await asyncio.sleep(0.1)  # Simulate API call time
            
            # Create fake object list for demo
            objects = [
                {"key": f"{prefix}file_{i}.dat", "size": 1024 * (i + 1)}
                for i in range(5)
            ]
            
            return {
                "success": True,
                "objects": objects,
                "count": len(objects),
                "operation_id": operation_id
            }
            
        except Exception as e:
            logger.error(f"List objects failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": operation_id
            }
    
    async def bulk_upload(self, files: Dict[str, bytes]) -> Dict[str, Any]:
        """
        Bulk upload operation using context manager for detailed tracking.
        
        This demonstrates how to track complex operations that involve
        multiple resource types.
        """
        with track_operation(self.backend_name, self.backend_type, 'bulk_upload') as tracker:
            results = []
            total_uploaded = 0
            
            for file_path, data in files.items():
                try:
                    # Perform the upload
                    result = await self.upload_file(file_path, data)
                    results.append(result)
                    
                    if result['success']:
                        total_uploaded += len(data)
                        
                        # The individual upload is already tracked by the decorator,
                        # but we can add additional tracking for the bulk operation
                        tracker.add_api_call({
                            "bulk_operation": "upload",
                            "file": file_path,
                            "size": len(data)
                        })
                    
                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")
                    results.append({
                        "success": False,
                        "file_path": file_path,
                        "error": str(e)
                    })
            
            # Get operation summary
            operation_summary = tracker.get_summary()
            
            return {
                "success": True,
                "files_processed": len(files),
                "total_uploaded_bytes": total_uploaded,
                "results": results,
                "operation_summary": operation_summary
            }
    
    async def get_resource_metrics(self) -> Dict[str, Any]:
        """
        Get resource usage metrics for this backend.
        
        This method provides easy access to resource tracking data
        specific to this backend instance.
        """
        try:
            from ipfs_kit_py.resource_tracker import get_resource_tracker
            
            tracker = get_resource_tracker()
            
            # Get usage summary for this backend
            summary = tracker.get_resource_summary(
                backend_name=self.backend_name,
                period='day'
            )
            
            # Get backend status
            status = tracker.get_backend_status(backend_name=self.backend_name)
            
            # Get recent usage details
            recent_usage = tracker.get_resource_usage(
                backend_name=self.backend_name,
                hours_back=1,
                limit=50
            )
            
            return {
                "backend_name": self.backend_name,
                "summary": summary,
                "status": status.get(self.backend_name, {}),
                "recent_activity": recent_usage,
                "metrics_available": True
            }
            
        except ImportError:
            return {
                "backend_name": self.backend_name,
                "metrics_available": False,
                "error": "Resource tracking not available"
            }
        except Exception as e:
            return {
                "backend_name": self.backend_name,
                "metrics_available": False,
                "error": str(e)
            }
    
    async def update_health_status(self, health_status: str = "healthy"):
        """Update the health status of this backend."""
        try:
            from ipfs_kit_py.resource_tracker import get_resource_tracker
            tracker = get_resource_tracker()
            
            # Calculate current usage metrics
            recent_usage = tracker.get_resource_usage(
                backend_name=self.backend_name,
                hours_back=1,
                limit=100
            )
            
            # Calculate bandwidth usage (simplified)
            bandwidth_usage = 0
            storage_usage = 0
            
            for record in recent_usage:
                if record['resource_type'] in ['bandwidth_upload', 'bandwidth_download']:
                    bandwidth_usage += record['amount']
                elif record['resource_type'] == 'storage_used':
                    storage_usage += record['amount']
            
            # Convert to appropriate units
            bandwidth_mbps = (bandwidth_usage / (1024 * 1024)) / 3600  # Rough conversion
            storage_gb = storage_usage / (1024 * 1024 * 1024)
            
            success = tracker.update_backend_status(
                backend_name=self.backend_name,
                backend_type=self.backend_type,
                is_active=True,
                bandwidth_usage_mbps=bandwidth_mbps,
                storage_usage_gb=storage_gb,
                health_status=health_status,
                metadata={
                    "last_health_update": time.time(),
                    "config": self.config
                }
            )
            
            return {"success": success, "health_status": health_status}
            
        except Exception as e:
            logger.error(f"Failed to update health status: {e}")
            return {"success": False, "error": str(e)}

# Example usage demonstration
async def demo_s3_with_tracking():
    """Demonstrate S3 backend with resource tracking."""
    import asyncio
    
    print("🚀 S3 Backend Resource Tracking Demo")
    print("=" * 50)
    
    # Initialize backend
    backend = S3BackendWithResourceTracking(
        backend_name="demo_s3_backend",
        bucket="test-bucket",
        region="us-west-2"
    )
    
    # Update health status
    await backend.update_health_status("healthy")
    print("✅ Backend health status updated")
    
    # Perform some operations
    test_data = b"Hello, World! " * 1000  # ~13KB of test data
    
    print("\n📤 Testing upload operation...")
    upload_result = await backend.upload_file("test/demo.txt", test_data)
    print(f"Upload result: {upload_result['success']}")
    
    print("\n📥 Testing download operation...")
    download_result = await backend.download_file("test/demo.txt", expected_size=len(test_data))
    print(f"Download result: {download_result['success']}")
    
    print("\n📋 Testing list operation...")
    list_result = await backend.list_objects("test/")
    print(f"List result: {list_result['success']}, found {list_result['count']} objects")
    
    print("\n📦 Testing bulk upload...")
    bulk_files = {
        f"bulk/file_{i}.dat": b"X" * (1024 * (i + 1))  # 1KB, 2KB, 3KB files
        for i in range(3)
    }
    bulk_result = await backend.bulk_upload(bulk_files)
    print(f"Bulk upload: {bulk_result['files_processed']} files, {bulk_result['total_uploaded_bytes']} bytes")
    
    print("\n📊 Getting resource metrics...")
    metrics = await backend.get_resource_metrics()
    if metrics['metrics_available']:
        print("Resource tracking is working!")
        if 'recent_activity' in metrics:
            print(f"Recent activity: {len(metrics['recent_activity'])} operations")
    else:
        print(f"Resource tracking not available: {metrics.get('error', 'Unknown error')}")
    
    print("\n✅ Demo completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_s3_with_tracking())
