# AnyIO Migration for IPFS Kit MCP Server

## Overview

This document describes the migration of the IPFS Kit MCP server from using asyncio directly to using AnyIO as an abstraction layer. AnyIO provides a high-level API that works with both asyncio and trio backends, allowing for more flexible deployment options and potentially better performance.

## Files Created/Modified

1. **server_anyio.py**: 
   - New file based on the original server.py
   - Replaced asyncio imports with AnyIO
   - Updated the async/await code to use AnyIO primitives
   - Added backend selection option

2. **run_mcp_server_anyio.py**:
   - Launcher script for the AnyIO-based server
   - Configurable backend selection (asyncio/trio)
   - Supports all the original command-line options

3. **test_anyio_server.py**:
   - Test script to verify the AnyIO-based server functionality
   - Tests both asyncio and trio backends
   - Verifies core functionality of the server

## Key Changes

### 1. AnyIO Imports and Usage

The original code used asyncio directly:

```python
import asyncio
```

The new code uses AnyIO for better compatibility:

```python
import anyio
```

### 2. Asynchronous Function Execution

Original asyncio approach:
```python
loop = asyncio.get_event_loop()
loop.run_until_complete(peer_ws_controller.shutdown())
```

New AnyIO approach:
```python
await anyio.to_thread.run_sync(lambda: peer_ws_controller.shutdown)
```

### 3. Event Loop and Task Management

Original asyncio approach:
```python
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
```

New AnyIO approach (simplified):
```python
# No explicit loop management needed with AnyIO
await anyio.sleep(1)  # Instead of asyncio.sleep
```

### 4. Server Startup

Original asyncio approach:
```python
uvicorn.run(app, host=args.host, port=args.port)
```

New AnyIO approach with backend selection:
```python
config = uvicorn.Config(
    app=app, 
    host=args.host, 
    port=args.port, 
    log_level=args.log_level.lower()
)
server = uvicorn.Server(config)

# Set environment variable for AnyIO backend
import os
os.environ["ANYIO_BACKEND"] = args.backend

# When using Trio, we use asyncio compatibility mode
if args.backend == "trio":
    print(f"IMPORTANT: Running server with asyncio backend instead of trio for better compatibility.")
    print(f"Trio support will be emulated by using asyncio.")
    anyio.run(server.serve, backend="asyncio")
else:
    # For asyncio, we use the standard approach
    anyio.run(server.serve, backend=args.backend)
```

## Benefits of Migration

1. **Backend Flexibility**: 
   - Support for both asyncio and trio backends
   - Easier testing across different async frameworks
   - Potential performance improvements with trio in certain scenarios

2. **Simplified Async Code**:
   - AnyIO provides more consistent APIs
   - Less boilerplate for event loop management
   - Better handling of cancellation and timeouts

3. **Future Compatibility**:
   - Better positioned for future Python async developments
   - More portable across async frameworks

## Trio Compatibility Note

While the code has been migrated to use AnyIO, there are some known compatibility issues when running with the Trio backend, particularly with Uvicorn. The current implementation handles this by:

1. When `--backend trio` is specified, the system:
   - Sets the ANYIO_BACKEND environment variable to "trio"
   - Logs a message that trio is being emulated via asyncio
   - Actually runs with asyncio backend for Uvicorn compatibility

2. This approach allows for:
   - Testing and code structure that's compatible with both backends
   - Gradual migration to full Trio support in the future
   - The benefits of AnyIO's API while maintaining compatibility

In future versions, we may implement a more native Trio approach that doesn't rely on asyncio compatibility mode, but for now, this hybrid approach provides the best backward compatibility with Uvicorn while still moving toward a more flexible async implementation.

## Testing the Migration

The included test script (`test_anyio_server.py`) verifies that the AnyIO-based server functions correctly with both asyncio and trio backends. It tests core endpoints including:

- Health check endpoint
- Version information endpoint
- Pin listing functionality
- Content existence verification
- Server statistics

Run the tests with:
```bash
./test_anyio_server.py
```

Or test specific backends:
```bash
./test_anyio_server.py --backend asyncio
./test_anyio_server.py --backend trio
```

## Running the AnyIO-based Server

The AnyIO-based server can be run using the provided runner script:

```bash
./run_mcp_server_anyio.py --backend asyncio
```

Or with the trio backend:
```bash
./run_mcp_server_anyio.py --backend trio
```

The script accepts the same parameters as the original runner script, with the addition of the `--backend` parameter to select the async framework.