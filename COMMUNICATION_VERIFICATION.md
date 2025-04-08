# MCP Communication Verification

This document describes how to verify communication between the MCP server and ipfs_kit_py components using three communication methods:

1. **WebRTC** for media streaming
2. **WebSockets** for notifications
3. **libp2p** for direct peer-to-peer communication

## Overview

The verification tests ensure that the MCP server and ipfs_kit_py client components can properly communicate with each other. These tests validate:

- WebRTC dependency detection functions correctly
- WebRTC streaming connections can be established
- WebSocket notifications work properly
- libp2p peer-to-peer connections function as expected
- Fallback mechanisms work when a communication method is unavailable

## Running the Tests

The tests can be run using the provided script:

```bash
# Run all tests
./run_mcp_communication_test.py

# Run only WebRTC tests
./run_mcp_communication_test.py --test-only webrtc

# Run only WebSocket tests
./run_mcp_communication_test.py --test-only websocket

# Run only libp2p tests
./run_mcp_communication_test.py --test-only libp2p

# Run integrated tests with all protocols
./run_mcp_communication_test.py --test-only integrated

# Force WebRTC tests even if dependencies are missing
./run_mcp_communication_test.py --force-webrtc

# Verbose output
./run_mcp_communication_test.py --verbose
```

## Test Details

### WebRTC Communication Test

This test verifies that:

1. The MCP server can properly initialize its WebRTC streaming manager
2. A WebRTC peer connection can be created
3. SDP offers can be generated for WebRTC signaling
4. The client and server can establish a WebRTC connection

The test uses mocks to simulate the WebRTC dependencies when necessary, and is skipped if the WebRTC dependencies are not available (unless forced).

### WebSocket Communication Test

This test verifies that:

1. The MCP server can send notifications to connected clients
2. Clients receive the correct notification messages
3. Various notification types are handled correctly
4. The notification subscription system works as expected

This test does not require any optional dependencies and should always run.

### libp2p Communication Test

This test verifies that:

1. The MCP server and client can create libp2p peers
2. Peers can connect directly to each other
3. Content can be announced and discovered
4. Data can be transferred directly between peers

The test is skipped if the libp2p dependencies are not available (unless forced).

### Integrated Communication Test

This test verifies the fallback mechanism between different communication protocols:

1. First attempts to use WebRTC (if available)
2. Falls back to WebSockets if WebRTC is unavailable
3. Falls back to libp2p if WebSockets fail
4. Finally falls back to direct API calls if all else fails

This test ensures that communication is always possible even when some protocols are unavailable.

## Dependencies

These tests rely on the following dependencies:

- **WebRTC**: Requires `aiortc` and `PyAV`
- **WebSockets**: Built into the core functionality
- **libp2p**: Requires `libp2p-py`

The tests can be run without these dependencies by using the appropriate command-line flags, which will use mocked implementations.

## Troubleshooting

### Missing Dependencies

If the WebRTC or libp2p tests are being skipped due to missing dependencies:

1. Install the required dependencies:
   ```bash
   pip install aiortc PyAV libp2p-py
   ```

2. Alternatively, force the tests to run with mocked dependencies:
   ```bash
   ./run_mcp_communication_test.py --force-webrtc --force-libp2p
   ```

### Test Failures

- **WebRTC test failures**: Check that the WebRTC dependencies are correctly installed and that the environment variable detection works correctly in `webrtc_streaming.py`.
- **WebSocket test failures**: Examine the WebSocket notification manager in `websocket_notifications.py` for issues.
- **libp2p test failures**: Verify the libp2p implementation in `libp2p_peer.py` and check that all dependencies are installed.

## Implementation Details

The verification tests use a combination of real components and mocks:

1. A real MCP server is initialized in isolation mode
2. A real ipfs_kit_py client is created to communicate with the server
3. External dependencies (WebRTC, libp2p) are mocked when necessary
4. Communication is verified by checking that messages are correctly exchanged

The tests are designed to be robust against missing dependencies, making them suitable for continuous integration environments where all dependencies may not be available.