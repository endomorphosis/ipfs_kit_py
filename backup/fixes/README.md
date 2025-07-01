# WebRTC Event Loop Fixes and Monitoring for MCP Server

This directory contains fixes for event loop issues in the WebRTC implementation of the IPFS Kit MCP Server, as well as comprehensive monitoring capabilities. The main issue was that WebRTC methods were attempting to create new event loops when running in FastAPI context, which already has a running event loop.

## Available Solutions

We provide three implementations, with increasing levels of functionality:

1. **AnyIO Solution (Recommended for Basic Fix)**: 
   - Uses AnyIO for better compatibility across different async backends (asyncio, trio, etc.)
   - Better integration with FastAPI which uses Starlette (built on AnyIO)
   - Better context detection through sniffio
   - Files: `webrtc_anyio_fix.py`, `apply_webrtc_anyio_fixes.py`

2. **Asyncio Solution**: 
   - Uses native asyncio
   - Simpler implementation if you only need asyncio support
   - Files: `webrtc_event_loop_fix.py`, `apply_webrtc_fixes.py`

3. **AnyIO + Monitoring Integration (Enhanced Solution)**: 
   - Builds on the AnyIO solution with comprehensive monitoring 
   - Tracks WebRTC connections, operations, and async tasks
   - Provides detailed logs and metrics for debugging
   - Includes REST API endpoints for monitoring data
   - Files: `webrtc_monitor.py`, `webrtc_anyio_monitor_integration.py`

## Installation

1. Clone or copy these files to your project
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Option 1: Apply the Basic AnyIO Fixes

```python
from ipfs_kit_py.mcp.server import MCPServer
from fixes.apply_webrtc_anyio_fixes import apply_fixes

# Create the MCP server
mcp_server = MCPServer(debug_mode=True)

# Apply the fixes directly to the instance
apply_fixes(mcp_server)

# Use the patched server as normal
```

### Option 2: Apply the Enhanced AnyIO + Monitoring Solution

```python
from ipfs_kit_py.mcp.server import MCPServer
from fixes.webrtc_anyio_monitor_integration import apply_enhanced_fixes

# Create the MCP server
mcp_server = MCPServer(debug_mode=True)

# Apply the enhanced fixes with monitoring
monitor = apply_enhanced_fixes(
    mcp_server, 
    log_dir="./logs",
    debug_mode=True
)

# Use the enhanced server with monitoring
```

### Option 3: Use the Enhanced Run Script

Use the provided script to run the MCP server with the enhanced solution:

```bash
# For AnyIO + Monitoring solution (most complete)
python ../run_mcp_with_anyio_monitor.py --debug --port 9999 --log-dir ./logs --webrtc-test --run-tests

# Arguments:
# --debug: Enable debug mode
# --port: Port to run the server on (default: 9999)
# --host: Host to bind to (default: 127.0.0.1)
# --log-dir: Directory to store WebRTC logs (default: ./logs)
# --isolation: Run with isolated IPFS repository
# --webrtc-test: Include WebRTC test endpoint
# --run-tests: Run WebRTC tests after starting the server
```

## Monitoring Features

The WebRTC monitoring system provides these capabilities:

1. **Connection Tracking**:
   - Track WebRTC connection states, tracks, and data channels
   - Monitor ICE connectivity and signaling states
   - Track connection lifecycle events

2. **Operation Monitoring**:
   - Track WebRTC operations (e.g., close connections) with timing and results
   - Record operation success/failure with detailed error information
   - Generate unique operation IDs for correlation

3. **Async Task Management**:
   - Track async tasks with proper cleanup
   - Prevent resource leaks from orphaned tasks
   - Monitor background task execution

4. **Logging & Metrics**:
   - Store connection and operation logs in structured JSON format
   - Provide summary statistics and health metrics
   - Enable optional debug logging for detailed troubleshooting

5. **REST API Endpoints** (when using `run_mcp_with_anyio_monitor.py`):
   - `/webrtc/monitor/summary`: Overall monitoring summary
   - `/webrtc/monitor/connections`: List of all connections
   - `/webrtc/monitor/connections/{connection_id}`: Specific connection details
   - `/webrtc/monitor/operations`: Active operations
   - `/webrtc/monitor/tasks`: Pending async tasks

## Implementation Details

The AnyIO + Monitoring solution combines the best of both worlds:

1. **Proper Event Loop Handling**:
   - Detects whether we're in an async context using sniffio
   - In a running event loop (like FastAPI), schedules operations as background tasks
   - When not in a running event loop, executes operations normally
   - Provides both sync and async versions of methods

2. **Comprehensive Monitoring**:
   - Tracks every WebRTC connection with detailed state information
   - Records all operations with timing information
   - Manages async tasks to prevent resource leaks
   - Provides detailed logging and metrics

3. **Testing & Diagnostics**:
   - Includes test endpoints for verifying functionality
   - Provides REST API endpoints for monitoring data
   - Stores detailed logs for troubleshooting

## Files

- `webrtc_anyio_fix.py`: AnyIO implementation of the basic fixes
- `apply_webrtc_anyio_fixes.py`: Script to apply the AnyIO fixes
- `webrtc_event_loop_fix.py`: Asyncio implementation of the basic fixes
- `apply_webrtc_fixes.py`: Script to apply the asyncio fixes
- `webrtc_monitor.py`: WebRTC monitoring implementation
- `webrtc_anyio_monitor_integration.py`: Integration of AnyIO fixes with monitoring
- `requirements.txt`: Required dependencies
- `README.md`: This documentation file

## Testing

To verify that the enhanced solution works correctly:

```bash
# Start the enhanced server with test endpoint and automatic tests
python ../run_mcp_with_anyio_monitor.py --debug --port 9999 --webrtc-test --run-tests

# Check the monitoring dashboard
curl http://127.0.0.1:9999/webrtc/monitor/summary
```

## Documentation

For more detailed information about the problem and solutions, see:

- [../WEBRTC_EVENT_LOOP_FIX.md](../WEBRTC_EVENT_LOOP_FIX.md) - Details on event loop fixes
- [../run_mcp_with_anyio_monitor.py](../run_mcp_with_anyio_monitor.py) - Enhanced server implementation