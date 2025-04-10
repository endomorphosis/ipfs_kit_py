# IPFS Kit WebRTC Testing Tools

This directory contains various tools for testing the WebRTC streaming capabilities of the IPFS Kit MCP server. These tools are designed for different use cases and environments, from simple API testing to full WebRTC client implementations.

## Available Testing Tools

### 1. MCP WebRTC Test (Python - API Test)
**File:** `mcp_webrtc_test.py`

A basic Python-based test script that exercises the MCP server's WebRTC API endpoints without establishing actual WebRTC connections. Useful for basic API validation and smoke testing.

```bash
python mcp_webrtc_test.py --server-url http://localhost:9999/api/v0/mcp
python mcp_webrtc_test.py --server-url http://localhost:9999/api/v0/mcp --cid QmYourCidHere
```

### 2. WebRTC MCP Test (HTML - Browser Client)
**File:** `webrtc_mcp_test.html`

A browser-based test page that provides a UI for interacting with the MCP server's WebRTC capabilities. Supports testing streams in the browser with visualization and control features.

To use, serve the HTML file and access it in a WebRTC-capable browser:
```bash
# Using Python's built-in HTTP server
python -m http.server 8000
# Then open http://localhost:8000/webrtc_mcp_test.html in your browser
```

### 3. MCP WebRTC AioRTC Client (Python - Full WebRTC Client)
**File:** `mcp_webrtc_aiortc_client.py`

A comprehensive Python-based WebRTC client using the `aiortc` library. This tool establishes a complete WebRTC connection, receives media streams, and provides detailed performance metrics. It can optionally display the video stream using OpenCV.

```bash
# Basic usage
python mcp_webrtc_aiortc_client.py --server-url http://localhost:9999/mcp --cid QmYourCidHere

# With video display (requires OpenCV)
python mcp_webrtc_aiortc_client.py --server-url http://localhost:9999/mcp --cid QmYourCidHere --display

# With statistics collection
python mcp_webrtc_aiortc_client.py --server-url http://localhost:9999/mcp --cid QmYourCidHere --stats-output stats.json

# With limited duration
python mcp_webrtc_aiortc_client.py --server-url http://localhost:9999/mcp --cid QmYourCidHere --duration 30
```

### 4. Node WebRTC Client (Node.js - Full WebRTC Client)
**File:** `node_webrtc_client.js`

A Node.js-based WebRTC client that can be used in environments without a display or browser. Useful for automated testing and CI/CD pipelines.

```bash
# Install dependencies
npm install

# Basic usage
node node_webrtc_client.js --server-url http://localhost:9999/mcp --cid QmYourCidHere

# With statistics collection
node node_webrtc_client.js --server-url http://localhost:9999/mcp --cid QmYourCidHere --stats-output stats.json

# With limited duration
node node_webrtc_client.js --server-url http://localhost:9999/mcp --cid QmYourCidHere --duration 30
```

### 5. WebRTC Streaming Example (General WebRTC Demo)
**File:** `webrtc_streaming_example.py`

A general-purpose WebRTC streaming example that demonstrates the functionality of the IPFS Kit WebRTC module. It can operate in both server and client modes, showing the complete WebRTC streaming workflow.

```bash
# Server mode
python webrtc_streaming_example.py --server

# Client mode
python webrtc_streaming_example.py --client --signaling-url ws://localhost:8000/ws/webrtc --cid QmYourCidHere
```

## Installation Requirements

### Python Tools
The Python-based tools require various dependencies:

```bash
# For basic API testing
pip install requests

# For aiortc-based client
pip install aiohttp aiortc opencv-python websockets

# For WebRTC streaming example
pip install ipfs_kit_py[webrtc]
```

### Node.js Tool
The Node.js client requires:

```bash
# Install from package.json
npm install

# Or install dependencies directly
npm install wrtc ws node-fetch commander
```

## Best Practices for WebRTC Testing

1. **Start with API Tests:** Begin with the `mcp_webrtc_test.py` script to verify that the MCP server's WebRTC API endpoints are functional.

2. **Browser Testing:** Use the HTML client (`webrtc_mcp_test.html`) to visually confirm streaming quality and behavior.

3. **Programmatic Testing:** Use the Python or Node.js clients for automated testing and performance benchmarking.

4. **Test Different Content Types:** Test with different types of content (video, audio, etc.) and different quality settings.

5. **Network Condition Testing:** Test under various network conditions to verify adaptive bitrate behavior.

6. **Metrics Collection:** Use the `--stats-output` option to collect performance metrics for analysis.

7. **CI/CD Integration:** The Node.js client is particularly well-suited for integration into continuous integration pipelines.

## Troubleshooting

### Common Issues

1. **WebRTC Dependencies Not Available**
   
   The aiortc library requires native components that might need additional system dependencies. If you see this error, install the required packages:
   
   ```bash
   # Ubuntu/Debian
   apt-get install libavdevice-dev libavfilter-dev libopus-dev libvpx-dev pkg-config
   
   # macOS
   brew install ffmpeg opus libvpx pkg-config
   ```

2. **Connection Failures**
   
   If connections fail, check:
   - That the MCP server is running and accessible
   - That the server has WebRTC capabilities enabled
   - That your network allows WebRTC connections (some firewalls block them)

3. **Node.js wrtc Installation Issues**
   
   The wrtc package can be challenging to install on some platforms. It requires Python 2.7 and node-gyp:
   
   ```bash
   npm install -g node-gyp
   ```

## Extending the Testing Tools

These tools can be extended to support additional testing scenarios:

1. **Adding More Metrics:** Modify the statistics collection to capture additional metrics relevant to your use case.

2. **Custom Media Processing:** Extend the media handling to perform custom processing or analysis on the received streams.

3. **Integration with Testing Frameworks:** Integrate these tools with testing frameworks like pytest or mocha for more structured testing.

4. **Load Testing:** Modify the tools to create multiple simultaneous connections to test server capacity and performance under load.

## Contact & Support

For issues with these testing tools, please open an issue in the IPFS Kit repository or contact the development team.