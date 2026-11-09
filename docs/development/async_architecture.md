# Async Architecture Guide

## Overview

This document outlines the async architecture of the ipfs_kit_py project, which uses anyio to provide a flexible async runtime that works with multiple backends (async-io, trio, curio) while simplifying the async code.

## Why Anyio?

[Anyio](https://anyio.readthedocs.io/) is a high-level asynchronous concurrency library that:

1. **Provides Backend Flexibility**: Allows code to run on multiple async backends (async-io, trio, curio)
2. **Offers Simpler APIs**: Provides more intuitive APIs for common async patterns
3. **Improves Cancellation**: Uses more reliable cancellation mechanisms compared to async-io
4. **Standardizes Timeouts**: Provides consistent timeout handling across all operations
5. **Better Resource Management**: Simplifies context management and resource cleanup
6. **Concurrent Task Management**: Simplified task groups for running concurrent tasks

By adopting anyio, we enhance the flexibility of ipfs_kit_py while making the async code more robust and maintainable.

## AnyIO Architecture Components

IPFS Kit uses AnyIO throughout its codebase to enable flexible async backends. The key architectural components include:

### Core Async Utilities

- Base async utilities and helper functions
- Common patterns for cancellation, timeout handling, and resource management
- Backend-agnostic task creation and management

### Networking Components

- WebSocket-based peer discovery using AnyIO
- Async HTTP clients with proper cancelation and timeout handling
- Event handling systems for async notifications
- Connection management with proper cleanup

### Feature Implementation

- Streaming components for efficient content transfer
- Async filesystem operations with proper resource handling
- Resource management with structured cleanup
- Task scheduling with cancellation support

### Testing Infrastructure

- AnyIO-compatible testing utilities
- Support for both async-io and trio backends in tests
- Performance benchmarking across different backends

## Implementation Guidelines

### Direct Replacements

| async-io                          | anyio                          |
|-----------------------------------|--------------------------------|
| `async_io.sleep()`                | `anyio.sleep()`                |
| `async_io.gather()`               | `anyio.gather()`               |
| `async_io.create_task()`          | `anyio.create_task()`          |
| `async_io.wait_for()`             | `anyio.fail_after()`           |
| `async_io.TimeoutError`           | `anyio.TimeoutError`           |
| `async_io.run()`                  | `anyio.run()`                  |
| `async_io.current_task()`         | `anyio.get_current_task()`     |
| `async_io.create_task_group()`    | `anyio.create_task_group()`    |
| `async_io.to_thread()`            | `anyio.to_thread.run_sync()`   |

### Task Groups

Anyio provides a more structured way to handle groups of tasks:

```python
# async-io
async def main():
    task1 = async_io.create_task(some_function())
    task2 = async_io.create_task(another_function())
    await async_io.gather(task1, task2)

# anyio
async def main():
    async with anyio.create_task_group() as tg:
        tg.start_soon(some_function)
        tg.start_soon(another_function)
```

### Timeouts

Anyio offers a more intuitive timeout API:

```python
# async-io
try:
    await async_io.wait_for(operation(), timeout=5.0)
except async_io.TimeoutError:
    print("Operation timed out")

# anyio
try:
    async with anyio.fail_after(5.0):
        await operation()
except anyio.TimeoutError:
    print("Operation timed out")
```

### Streams and Sockets

Anyio provides a unified API for streams and sockets:

```python
# async-io
reader, writer = await async_io.open_connection(host, port)
data = await reader.read(1024)
writer.write(response)
await writer.drain()
writer.close()
await writer.wait_closed()

# anyio
async with await anyio.connect_tcp(host, port) as client:
    data = await client.receive(1024)
    await client.send(response)
```

### WebSockets

For WebSockets, anyio provides integrations with common libraries:

```python
# Using websockets with async-io
async with websockets.connect(url) as websocket:
    await websocket.send(data)
    response = await websocket.recv()

# Using websockets with anyio backend
async with websockets.connect(url) as websocket:
    await anyio.to_thread.run_sync(websocket.send, data)
    response = await anyio.to_thread.run_sync(websocket.recv)
```

Better yet, use a native anyio-compatible WebSocket library like `trio-websocket` or `wsproto` with anyio.

## Best Practices

1. **Use Task Groups**: Prefer task groups over individual task creation for better error propagation and cleanup
2. **Be Explicit with Timeouts**: Always specify timeouts for I/O operations
3. **Avoid Backend-Specific Features**: Stay within anyio's API to maintain backend independence
4. **Cancellation Handling**: Always handle cancellation properly in long-running tasks
5. **Resource Management**: Use `async with` for managing async resources
6. **Threading**: Use `anyio.to_thread.run_sync()` for CPU-bound operations
7. **Blocking Operations**: Move blocking operations to threads using `anyio.to_thread.run_sync()`

## Testing with Anyio

For testing async code with anyio, use the built-in testing utilities:

```python
import anyio
import pytest

@pytest.mark.anyio
async def test_async_function():
    # This test will run on all available backends
    result = await some_async_function()
    assert result == expected_value
```

## FAQs

### Can I mix async-io and anyio in the same project?

Yes, but it's recommended to use anyio consistently for new code and migrate existing code when possible.

### Will using anyio affect performance?

No, anyio is designed to be a thin wrapper around the underlying backends with minimal overhead.

### How do I specify which backend to use?

By default, anyio uses the async-io backend. To specify a different backend:

```python
import anyio

anyio.run(main, backend="trio")  # Use trio backend
```

### Can I use async-io-specific libraries with anyio?

Yes, most async-io libraries will work with anyio's async-io backend. For trio-specific features, you may need to use anyio's adapter utilities.

## Implementation Examples

### API Server Migration

The API server (`api.py`) was successfully migrated to an anyio-based implementation (`api_anyio.py`). This migration involved:

1. **Direct Replacements**: Replacing async-io imports with anyio, and async-io-specific functions with their anyio equivalents

```python
# Before (async-io-based)
import async_io

try:
    await async_io.wait_for(operation(), timeout=5.0)
except async_io.TimeoutError:
    # Handle timeout
    
# After (anyio-based)
import anyio

try:
    with anyio.fail_after(5.0):
        await operation()
except anyio.TimeoutError:
    # Handle timeout
```

2. **Timeout Handling**: Using anyio's context manager-based timeout handling for streaming operations

```python
# Before (with async-io)
async def stream_content():
    try:
        # Use async-io wait_for for timeout
        result = await async_io.wait_for(
            api.stream_media_async(path=path, chunk_size=chunk_size),
            timeout=timeout
        )
        return result
    except async_io.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout streaming content")

# After (with anyio)
async def stream_content():
    try:
        # Use anyio.move_on_after context manager
        with anyio.move_on_after(timeout):
            async for chunk in api.stream_media_async(
                path=path,
                chunk_size=chunk_size
            ):
                yield chunk
    except Exception as e:
        logger.error(f"Error during content streaming: {str(e)}")
        return
```

3. **Server Startup**: Using anyio.run to start the server to support different async backends

```python
# Before (async-io-based)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
    
# After (anyio-based)
if __name__ == "__main__":
    async def run_server():
        config = uvicorn.Config(
            "api_anyio:app", 
            host=host, 
            port=port,
            log_level=log_level,
            reload=False
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    # Run with anyio to support multiple backends
    import anyio
    backend = os.environ.get("IPFS_KIT_ASYNC_BACKEND", "async-io")
    anyio.run(run_server, backend=backend)
```

4. **Testing Integration**: Using pytest-anyio for testing the anyio components

```python
# Mark tests with pytest.mark.anyio
@pytest.mark.anyio
async def test_async_function():
    # Test implementation
    ...

# Use anyio.run for test execution
if __name__ == "__main__":
    anyio.run(
        pytest.main,
        ["-v", __file__]
    )
```

The migrated API server (`api_anyio.py`) preserves all the functionality of the original server while gaining the benefits of anyio - backend agnosticism, improved cancellation handling, and more intuitive concurrency patterns.

### WebSocket Notifications Migration

The WebSocket notifications system was migrated from async-io to anyio in `websocket_notifications_anyio.py`, demonstrating these key patterns:

1. **Task Group for Connection Management**: 
   - Replacing individual task creation and manual tracking with task groups for better error propagation and cleanup.
   - Task groups automatically cancel all tasks when exiting the context.

2. **Memory Streams for Inter-Task Communication**:
    - Using anyio's memory object streams instead of async-io queues.
   - Streams provide more consistent behavior across backends and better backpressure handling.

3. **Structured Cancellation**:
   - Properly handling cancellation to ensure resources are cleaned up.
   - Using anyio's cancel scopes for fine-grained control over cancellation.

### WAL WebSocket Migration

Similar patterns were applied when migrating the Write-Ahead Log WebSocket implementation:

1. **Converting Timeouts**:
    - Replacing `async_io.wait_for()` with `anyio.fail_after()` context managers.
   - This provides more intuitive timeout handling with proper cleanup.

2. **Thread-to-Async Bridge**:
    - Using `anyio.from_thread.run()` instead of async-io's thread functions.
   - This ensures compatibility across different backends.

3. **Proper Task Cancellation**:
   - Implementing proper cancellation handling with task groups.
   - Using `task_group.__aenter__()` and `task_group.__aexit__()` for explicit control when needed.

These implementation examples demonstrate how using anyio improves code readability, robustness, and maintainability while enabling backend flexibility.

## AnyIO Implementation Examples

The WebRTC controller demonstrates effective use of AnyIO primitives throughout its implementation.

### Key Implementation Patterns:

1. **Full AnyIO Implementation**: The WebRTC controller (`ipfs_kit_py/mcp/controllers/webrtc_controller.py`) exclusively uses AnyIO for asynchronous operations instead of async-io.

2. **Thread Safety**: All synchronous operations use `anyio.to_thread.run_sync()` for proper thread handling, which works in both async-io and trio contexts.

3. **Simplified Task Management**: Task creation and cancellation use straightforward AnyIO patterns that work across backends.

4. **Structured Error Handling**: AnyIO's cancellation handling provides cleaner error recovery.

5. **Controller-Level Async Methods**: All controller methods natively support async/await patterns for better integration with FastAPI.

6. **Backward Compatibility**: Where needed, compatibility layers ensure integration with existing code works correctly.

These patterns are replicated across controllers for a consistent implementation.

## References

- [Anyio Documentation](https://anyio.readthedocs.io/)
- [Trio Documentation](https://trio.readthedocs.io/)
- Async-IO documentation (Python standard library)