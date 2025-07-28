#!/usr/bin/env python3
"""
Resource Tracking Decorators and Context Managers

This module provides decorators and context managers to automatically track
resource consumption for backend operations without modifying existing code.
"""

import time
import functools
from typing import Dict, Any, Optional, Union, Callable
from contextlib import contextmanager

from .resource_tracker import (
    get_resource_tracker, 
    ResourceMetric, 
    ResourceType, 
    BackendType,
    track_bandwidth_upload,
    track_bandwidth_download,
    track_storage_usage,
    track_api_call
)

class ResourceTrackingDecorator:
    """Decorator for automatic resource tracking in backend methods."""
    
    def __init__(self, 
                 backend_name: str,
                 backend_type: BackendType,
                 resource_type: ResourceType,
                 extract_amount: Optional[Callable] = None,
                 extract_metadata: Optional[Callable] = None):
        """
        Initialize resource tracking decorator.
        
        Args:
            backend_name: Name of the backend
            backend_type: Type of backend
            resource_type: Type of resource being tracked
            extract_amount: Function to extract amount from result/args
            extract_metadata: Function to extract metadata from result/args
        """
        self.backend_name = backend_name
        self.backend_type = backend_type
        self.resource_type = resource_type
        self.extract_amount = extract_amount
        self.extract_metadata = extract_metadata
    
    def __call__(self, func: Callable) -> Callable:
        """Apply the decorator to a function."""
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Wrapper for async functions."""
            start_time = time.time()
            operation_id = kwargs.get('operation_id') or f"{func.__name__}_{int(start_time)}"
            
            try:
                result = await func(*args, **kwargs)
                
                # Extract amount and metadata
                amount = self._extract_amount(args, kwargs, result)
                metadata = self._extract_metadata(args, kwargs, result)
                metadata = metadata or {}
                metadata.update({
                    'function_name': func.__name__,
                    'duration_ms': int((time.time() - start_time) * 1000),
                    'success': True
                })
                
                # Track the resource usage
                tracker = get_resource_tracker()
                metric = ResourceMetric(
                    backend_name=self.backend_name,
                    backend_type=self.backend_type,
                    resource_type=self.resource_type,
                    amount=amount,
                    operation_id=operation_id,
                    metadata=metadata
                )
                tracker.track_resource_usage(metric)
                
                return result
                
            except Exception as e:
                # Track failed operation
                metadata = self._extract_metadata(args, kwargs, None) or {}
                metadata.update({
                    'function_name': func.__name__,
                    'duration_ms': int((time.time() - start_time) * 1000),
                    'success': False,
                    'error': str(e)
                })
                
                tracker = get_resource_tracker()
                metric = ResourceMetric(
                    backend_name=self.backend_name,
                    backend_type=self.backend_type,
                    resource_type=self.resource_type,
                    amount=0,
                    operation_id=operation_id,
                    metadata=metadata
                )
                tracker.track_resource_usage(metric)
                
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            """Wrapper for sync functions."""
            start_time = time.time()
            operation_id = kwargs.get('operation_id') or f"{func.__name__}_{int(start_time)}"
            
            try:
                result = func(*args, **kwargs)
                
                # Extract amount and metadata
                amount = self._extract_amount(args, kwargs, result)
                metadata = self._extract_metadata(args, kwargs, result)
                metadata = metadata or {}
                metadata.update({
                    'function_name': func.__name__,
                    'duration_ms': int((time.time() - start_time) * 1000),
                    'success': True
                })
                
                # Track the resource usage
                tracker = get_resource_tracker()
                metric = ResourceMetric(
                    backend_name=self.backend_name,
                    backend_type=self.backend_type,
                    resource_type=self.resource_type,
                    amount=amount,
                    operation_id=operation_id,
                    metadata=metadata
                )
                tracker.track_resource_usage(metric)
                
                return result
                
            except Exception as e:
                # Track failed operation
                metadata = self._extract_metadata(args, kwargs, None) or {}
                metadata.update({
                    'function_name': func.__name__,
                    'duration_ms': int((time.time() - start_time) * 1000),
                    'success': False,
                    'error': str(e)
                })
                
                tracker = get_resource_tracker()
                metric = ResourceMetric(
                    backend_name=self.backend_name,
                    backend_type=self.backend_type,
                    resource_type=self.resource_type,
                    amount=0,
                    operation_id=operation_id,
                    metadata=metadata
                )
                tracker.track_resource_usage(metric)
                
                raise
        
        # Return appropriate wrapper based on function type
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    def _extract_amount(self, args: tuple, kwargs: dict, result: Any) -> int:
        """Extract the resource amount from function arguments or result."""
        if self.extract_amount:
            return self.extract_amount(args, kwargs, result)
        
        # Default extraction logic based on resource type
        if self.resource_type == ResourceType.API_CALLS:
            return 1
        
        # Try to find size information in various places
        for source in [kwargs, result]:
            if isinstance(source, dict):
                for key in ['size', 'bytes', 'length', 'content_length']:
                    if key in source:
                        return source[key]
        
        # Check if result has size information
        if hasattr(result, '__len__'):
            try:
                return len(result)
            except:
                pass
        
        return 0
    
    def _extract_metadata(self, args: tuple, kwargs: dict, result: Any) -> Optional[Dict[str, Any]]:
        """Extract metadata from function arguments or result."""
        if self.extract_metadata:
            return self.extract_metadata(args, kwargs, result)
        
        metadata = {}
        
        # Extract common metadata
        for key in ['file_path', 'path', 'key', 'cid']:
            if key in kwargs:
                metadata[key] = kwargs[key]
        
        # Extract from positional args (common patterns)
        if args:
            if len(args) > 0 and isinstance(args[0], str):
                metadata['first_arg'] = args[0]
        
        return metadata if metadata else None

@contextmanager
def track_operation(backend_name: str, 
                   backend_type: BackendType,
                   operation_name: str,
                   file_path: Optional[str] = None):
    """
    Context manager for tracking complex operations.
    
    Usage:
        with track_operation('s3_primary', BackendType.S3, 'bulk_upload') as tracker:
            # Perform operations
            tracker.add_bandwidth_upload(1024 * 1024)  # 1MB uploaded
            tracker.add_storage_usage(2048 * 1024)     # 2MB stored
    """
    
    class OperationTracker:
        """Helper class for tracking resources within an operation."""
        
        def __init__(self, backend_name: str, backend_type: BackendType, operation_id: str):
            self.backend_name = backend_name
            self.backend_type = backend_type
            self.operation_id = operation_id
            self.start_time = time.time()
            self.resources_tracked = []
        
        def add_bandwidth_upload(self, bytes_uploaded: int, metadata: Optional[Dict[str, Any]] = None):
            """Track bandwidth upload within this operation."""
            track_bandwidth_upload(
                self.backend_name, self.backend_type, bytes_uploaded,
                self.operation_id, file_path
            )
            self.resources_tracked.append(('bandwidth_upload', bytes_uploaded))
        
        def add_bandwidth_download(self, bytes_downloaded: int, metadata: Optional[Dict[str, Any]] = None):
            """Track bandwidth download within this operation."""
            track_bandwidth_download(
                self.backend_name, self.backend_type, bytes_downloaded,
                self.operation_id, file_path
            )
            self.resources_tracked.append(('bandwidth_download', bytes_downloaded))
        
        def add_storage_usage(self, bytes_stored: int, metadata: Optional[Dict[str, Any]] = None):
            """Track storage usage within this operation."""
            track_storage_usage(
                self.backend_name, self.backend_type, bytes_stored,
                self.operation_id, file_path
            )
            self.resources_tracked.append(('storage_usage', bytes_stored))
        
        def add_api_call(self, metadata: Optional[Dict[str, Any]] = None):
            """Track API call within this operation."""
            track_api_call(
                self.backend_name, self.backend_type,
                self.operation_id, metadata
            )
            self.resources_tracked.append(('api_call', 1))
        
        def get_summary(self) -> Dict[str, Any]:
            """Get summary of resources tracked in this operation."""
            summary = {
                'operation_id': self.operation_id,
                'backend_name': self.backend_name,
                'backend_type': self.backend_type.value,
                'duration_ms': int((time.time() - self.start_time) * 1000),
                'resources': {}
            }
            
            for resource_type, amount in self.resources_tracked:
                if resource_type not in summary['resources']:
                    summary['resources'][resource_type] = 0
                summary['resources'][resource_type] += amount
            
            return summary
    
    operation_id = f"{operation_name}_{int(time.time())}"
    tracker = OperationTracker(backend_name, backend_type, operation_id)
    
    try:
        yield tracker
    except Exception as e:
        # Track the failed operation
        metadata = {
            'operation_name': operation_name,
            'file_path': file_path,
            'error': str(e),
            'success': False
        }
        
        resource_tracker = get_resource_tracker()
        metric = ResourceMetric(
            backend_name=backend_name,
            backend_type=backend_type,
            resource_type=ResourceType.API_CALLS,
            amount=1,
            operation_id=operation_id,
            file_path=file_path,
            metadata=metadata
        )
        resource_tracker.track_resource_usage(metric)
        
        raise

# Predefined decorators for common backend operations
def track_upload(backend_name: str, backend_type: BackendType):
    """Decorator for tracking upload operations."""
    def extract_upload_size(args, kwargs, result):
        # Try to get size from various sources
        if 'data' in kwargs and hasattr(kwargs['data'], '__len__'):
            return len(kwargs['data'])
        if 'content' in kwargs and hasattr(kwargs['content'], '__len__'):
            return len(kwargs['content'])
        if isinstance(result, dict) and 'size' in result:
            return result['size']
        return 0
    
    return ResourceTrackingDecorator(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.BANDWIDTH_UPLOAD,
        extract_amount=extract_upload_size
    )

def track_download(backend_name: str, backend_type: BackendType):
    """Decorator for tracking download operations."""
    def extract_download_size(args, kwargs, result):
        if hasattr(result, '__len__'):
            return len(result)
        if isinstance(result, dict) and 'size' in result:
            return result['size']
        return 0
    
    return ResourceTrackingDecorator(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.BANDWIDTH_DOWNLOAD,
        extract_amount=extract_download_size
    )

def track_api(backend_name: str, backend_type: BackendType):
    """Decorator for tracking API calls."""
    return ResourceTrackingDecorator(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.API_CALLS
    )

def track_storage(backend_name: str, backend_type: BackendType):
    """Decorator for tracking storage operations."""
    def extract_storage_size(args, kwargs, result):
        # Storage operations typically involve the size of data being stored
        if 'data' in kwargs and hasattr(kwargs['data'], '__len__'):
            return len(kwargs['data'])
        if 'content' in kwargs and hasattr(kwargs['content'], '__len__'):
            return len(kwargs['content'])
        if isinstance(result, dict) and 'size' in result:
            return result['size']
        return 0
    
    return ResourceTrackingDecorator(
        backend_name=backend_name,
        backend_type=backend_type,
        resource_type=ResourceType.STORAGE_USED,
        extract_amount=extract_storage_size
    )
