# Streaming Metrics Integration Guide

This document provides guidelines for implementing the integration between streaming functionality and the performance metrics system in the `ipfs_kit_py` project.

## Background

The performance metrics system in `performance_metrics.py` includes a comprehensive `track_streaming_operation` method that records detailed metrics for streaming operations, including throughput calculations, bandwidth usage, and other streaming metadata. 

## Implementation Status

- ✅ Added metrics initialization to `__init__` method in `IPFSSimpleAPI`
- ✅ Added `track_streaming_operation` method to `IPFSSimpleAPI` as a wrapper for `performance_metrics.track_streaming_operation`
- 🟡 Streaming functions in `high_level_api.py` still need to be updated to use the metrics system

The foundation for metrics integration has been implemented. The IPFSSimpleAPI class now initializes metrics tracking in its constructor and provides a `track_streaming_operation` method that acts as a wrapper for the metrics system. The next step is to update each streaming method to use this infrastructure.

## Integration Approach

### 1. Enable Metrics in the `IPFSSimpleAPI` Class

First, ensure that the `IPFSSimpleAPI` class initializes a metrics tracker:

```python
def __init__(self, ipfs_path=None, enable_metrics=True, **kwargs):
    # Existing initialization code...
    
    # Initialize metrics
    self.enable_metrics = enable_metrics
    if self.enable_metrics:
        from ipfs_kit_py.performance_metrics import PerformanceMetrics
        self.metrics = PerformanceMetrics()
    else:
        self.metrics = None
```

### 2. Add `track_streaming_operation` Method

For convenience, add a wrapper method for streaming metrics tracking:

```python
def track_streaming_operation(self, stream_type, direction, size_bytes, duration_seconds, path=None, 
                             chunk_count=None, chunk_size=None, correlation_id=None):
    """Track streaming operation metrics if metrics are enabled."""
    if not self.enable_metrics or not self.metrics:
        return None
        
    return self.metrics.track_streaming_operation(
        stream_type=stream_type,
        direction=direction,
        size_bytes=size_bytes,
        duration_seconds=duration_seconds,
        path=path,
        chunk_count=chunk_count,
        chunk_size=chunk_size,
        correlation_id=correlation_id
    )
```

### 3. Integrate with HTTP Streaming Functions

Modify the `stream_media` method to track metrics:

```python
def stream_media(self, path: str, *, chunk_size: int = 1024 * 1024, mime_type: Optional[str] = None, 
                start_byte: Optional[int] = None, end_byte: Optional[int] = None, 
                cache: bool = True, timeout: Optional[int] = None, **kwargs) -> Iterator[bytes]:
    """Stream media content from IPFS with chunked access."""
    # Start tracking metrics
    start_time = time.time()
    total_bytes = 0
    chunk_count = 0
    
    try:
        # Get content (existing implementation)
        # ...
        
        # Stream content in chunks (existing implementation)
        for chunk in chunks:
            total_bytes += len(chunk)
            chunk_count += 1
            yield chunk
            
    finally:
        # Track streaming metrics when completed
        duration = time.time() - start_time
        if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
            self.track_streaming_operation(
                stream_type="http",
                direction="outbound",
                size_bytes=total_bytes,
                duration_seconds=duration,
                path=path,
                chunk_count=chunk_count,
                chunk_size=chunk_size
            )
```

### 4. Integrate with WebSocket Streaming Functions

Modify the `handle_websocket_media_stream` method:

```python
async def handle_websocket_media_stream(self, websocket, path: str, *, chunk_size: int = 1024 * 1024, 
                                      mime_type: Optional[str] = None, cache: bool = True, 
                                      timeout: Optional[int] = None, **kwargs) -> None:
    """Stream media content through a WebSocket connection."""
    # Start metrics tracking
    start_time = time.time()
    total_bytes = 0
    chunk_count = 0
    
    try:
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Get content (existing implementation)
        # ...
        
        # Send content metadata (existing implementation)
        # ...
        
        # Stream the content in chunks (existing implementation)
        async for chunk in content_stream:
            await websocket.send_bytes(chunk)
            total_bytes += len(chunk)
            chunk_count += 1
            
    except Exception as e:
        # Error handling (existing implementation)
        # ...
        
    finally:
        # Track streaming metrics when completed
        duration = time.time() - start_time
        if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
            self.track_streaming_operation(
                stream_type="websocket",
                direction="outbound",
                size_bytes=total_bytes,
                duration_seconds=duration,
                path=path,
                chunk_count=chunk_count,
                chunk_size=chunk_size
            )
```

### 5. Integrate with Upload Streaming Functions

Modify the `handle_websocket_upload_stream` method:

```python
async def handle_websocket_upload_stream(self, websocket, *, chunk_size: int = 1024 * 1024, 
                                       timeout: Optional[int] = None, test_cid=None, **kwargs) -> None:
    """Receive content upload through a WebSocket connection."""
    # Start metrics tracking
    start_time = time.time()
    total_bytes = 0
    chunk_count = 0
    
    try:
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Process metadata message (existing implementation)
        # ...
        
        # Process content chunks (existing implementation)
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), 
                    timeout=timeout or 30
                )
                
                # If it's a binary message, process the chunk
                if "bytes" in message:
                    chunk = message["bytes"]
                    content_chunks.append(chunk)
                    total_bytes += len(chunk)
                    chunk_count += 1
                    
                # Remaining implementation
                # ...
                
        # Add to IPFS (existing implementation)
        # ...
        
    except Exception as e:
        # Error handling (existing implementation)
        # ...
        
    finally:
        # Track streaming metrics when completed
        duration = time.time() - start_time
        if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
            self.track_streaming_operation(
                stream_type="websocket",
                direction="inbound",
                size_bytes=total_bytes,
                duration_seconds=duration,
                path=filename if 'filename' in locals() else None,
                chunk_count=chunk_count,
                chunk_size=chunk_size
            )
```

### 6. Integrate with Bidirectional Streaming

Modify the `handle_websocket_bidirectional_stream` method to track both inbound and outbound metrics separately:

```python
async def handle_websocket_bidirectional_stream(self, websocket, *, chunk_size: int = 1024 * 1024, 
                                              timeout: Optional[int] = None, **kwargs) -> None:
    """Handle bidirectional content streaming through a WebSocket connection."""
    # Initialize metrics tracking for both directions
    inbound_start_time = time.time()
    outbound_start_time = time.time()
    inbound_bytes = 0
    outbound_bytes = 0
    inbound_chunks = 0
    outbound_chunks = 0
    
    try:
        # Accept the WebSocket connection
        await websocket.accept()
        
        # Process commands (existing implementation)
        while True:
            # Receive command
            # ...
            
            if command == "get":
                # Reset outbound tracking for this operation
                outbound_start_time = time.time()
                outbound_bytes = 0
                outbound_chunks = 0
                
                # Process get command to stream content to client
                # ...
                
                # During streaming
                async for chunk in content_stream:
                    await websocket.send_bytes(chunk)
                    outbound_bytes += len(chunk)
                    outbound_chunks += 1
                    
                # Track metrics for this get operation
                outbound_duration = time.time() - outbound_start_time
                if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
                    self.track_streaming_operation(
                        stream_type="websocket_bidirectional",
                        direction="outbound",
                        size_bytes=outbound_bytes,
                        duration_seconds=outbound_duration,
                        path=path,
                        chunk_count=outbound_chunks,
                        chunk_size=chunk_size
                    )
                    
            elif command == "add":
                # Reset inbound tracking for this operation
                inbound_start_time = time.time()
                inbound_bytes = 0
                inbound_chunks = 0
                
                # Process add command to receive content from client
                # ...
                
                # During upload
                while waiting_for_chunks:
                    chunk = await websocket.receive_bytes()
                    content_chunks.append(chunk)
                    inbound_bytes += len(chunk)
                    inbound_chunks += 1
                    
                # Track metrics for this add operation
                inbound_duration = time.time() - inbound_start_time
                if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
                    self.track_streaming_operation(
                        stream_type="websocket_bidirectional",
                        direction="inbound",
                        size_bytes=inbound_bytes,
                        duration_seconds=inbound_duration,
                        path=filename if 'filename' in locals() else None,
                        chunk_count=inbound_chunks,
                        chunk_size=chunk_size
                    )
                    
    except Exception as e:
        # Error handling (existing implementation)
        # ...
```

### 7. Add Metrics to WebRTC Streaming

If WebRTC streaming is implemented, add similar metrics tracking:

```python
async def handle_webrtc_streaming(self, websocket, **kwargs):
    """Provide WebRTC-based streaming for IPFS content."""
    # Initialize metrics tracking
    start_time = time.time()
    total_bytes = 0
    frame_count = 0
    
    try:
        # Existing implementation
        # ...
        
        # During frame sending
        for frame in frames:
            # Send frame
            # ...
            
            total_bytes += len(frame)
            frame_count += 1
            
    finally:
        # Track streaming metrics when completed
        duration = time.time() - start_time
        if self.enable_metrics and hasattr(self, 'metrics') and self.metrics:
            self.track_streaming_operation(
                stream_type="webrtc",
                direction="outbound",
                size_bytes=total_bytes,
                duration_seconds=duration,
                path=path if 'path' in locals() else None,
                chunk_count=frame_count,
                chunk_size=None  # Variable frame sizes
            )
```

## Testing the Implementation

The tests in `test_streaming.py` have been updated to verify the integration between streaming functions and the metrics system:

1. `test_streaming_metrics_integration` tests HTTP streaming metrics
2. `test_websocket_streaming_metrics` tests WebSocket streaming metrics

These tests should pass after implementing the integration as described in this guide.

## Benefits of Implementation

Implementing this integration will provide several benefits:

1. **Performance Monitoring**: Track streaming performance metrics like throughput, latency, and bandwidth usage
2. **Debugging Aid**: Identify performance bottlenecks and streaming issues
3. **Resource Optimization**: Understand resource usage patterns during streaming operations
4. **User Experience Insights**: Gather data about streaming quality and reliability for different content types

## Conclusion

This integration enhances the ipfs_kit_py project by connecting the existing streaming functionality with the robust performance metrics system. The changes are minimally invasive while providing significant observability benefits.