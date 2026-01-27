#!/usr/bin/env python3
"""
WebRTC Streaming Optimized Example

This example demonstrates how to use the optimized WebRTC streaming capabilities
of ipfs_kit_py with advanced buffer management, progressive loading, and network adaptation.

Features demonstrated:
- Creating and configuring a WebRTC stream with optimized buffer parameters
- Setting up a simple web server to serve the streaming client
- Monitoring buffer metrics during streaming
- Adjusting buffer parameters based on network conditions
"""

import anyio
import json
import logging
import os
import time
from threading import Thread
from aiohttp import web
from pathlib import Path

from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# HTML template for the streaming client
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS WebRTC Streaming with Buffer Optimization</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
        }
        .video-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 20px;
        }
        video {
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: #000;
        }
        .controls {
            width: 100%;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
        }
        button {
            padding: 10px 15px;
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #2980b9;
        }
        button:disabled {
            background-color: #95a5a6;
            cursor: not-allowed;
        }
        .metrics {
            width: 100%;
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background-color: white;
        }
        .metric-container {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .metric {
            flex: 1;
            min-width: 200px;
            padding: 10px;
            border-radius: 4px;
            background-color: #f9f9f9;
        }
        .metric h3 {
            margin-top: 0;
            font-size: 16px;
            color: #2c3e50;
        }
        .metric p {
            margin: 5px 0;
            font-size: 14px;
        }
        .dropdown {
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ddd;
            min-width: 150px;
        }
        label {
            font-weight: bold;
            margin-right: 5px;
        }
        .form-group {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <h1>IPFS WebRTC Streaming with Buffer Optimization</h1>
    
    <div class="controls">
        <div class="form-group">
            <label for="buffer-size">Buffer Size:</label>
            <select id="buffer-size" class="dropdown">
                <option value="10">10 frames</option>
                <option value="30" selected>30 frames</option>
                <option value="60">60 frames</option>
                <option value="120">120 frames</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="prefetch-threshold">Prefetch Threshold:</label>
            <select id="prefetch-threshold" class="dropdown">
                <option value="0.3">30%</option>
                <option value="0.5" selected>50%</option>
                <option value="0.7">70%</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="progressive-loading">Progressive Loading:</label>
            <select id="progressive-loading" class="dropdown">
                <option value="true" selected>Enabled</option>
                <option value="false">Disabled</option>
            </select>
        </div>
    </div>
    
    <div class="controls">
        <button id="start-btn">Start Streaming</button>
        <button id="stop-btn" disabled>Stop Streaming</button>
    </div>
    
    <div class="video-container">
        <video id="video" autoplay playsinline></video>
    </div>
    
    <div class="metrics">
        <h2>Streaming Metrics</h2>
        <div class="metric-container">
            <div class="metric">
                <h3>Buffer Statistics</h3>
                <p>Buffer Size: <span id="current-buffer-size">-</span></p>
                <p>Fill Level: <span id="buffer-fill-level">-</span>%</p>
                <p>Underflow Events: <span id="buffer-underflows">-</span></p>
                <p>Overflow Events: <span id="buffer-overflows">-</span></p>
            </div>
            <div class="metric">
                <h3>Performance</h3>
                <p>Frame Rate: <span id="framerate">-</span> fps</p>
                <p>Frame Processing Time: <span id="processing-time">-</span> ms</p>
                <p>Total Frames: <span id="total-frames">-</span></p>
            </div>
            <div class="metric">
                <h3>Network</h3>
                <p>Bandwidth: <span id="bandwidth">-</span> Kbps</p>
                <p>Latency: <span id="latency">-</span> ms</p>
                <p>Packets Lost: <span id="packets-lost">-</span></p>
            </div>
        </div>
    </div>

    <script>
        let pc = null;
        let metricsInterval = null;
        
        const videoElement = document.getElementById('video');
        const startButton = document.getElementById('start-btn');
        const stopButton = document.getElementById('stop-btn');
        
        // Metrics elements
        const bufferSizeElement = document.getElementById('current-buffer-size');
        const fillLevelElement = document.getElementById('buffer-fill-level');
        const underflowsElement = document.getElementById('buffer-underflows');
        const overflowsElement = document.getElementById('buffer-overflows');
        const framerateElement = document.getElementById('framerate');
        const processingTimeElement = document.getElementById('processing-time');
        const totalFramesElement = document.getElementById('total-frames');
        const bandwidthElement = document.getElementById('bandwidth');
        const latencyElement = document.getElementById('latency');
        const packetsLostElement = document.getElementById('packets-lost');
        
        function getSelectedBufferParams() {
            return {
                buffer_size: parseInt(document.getElementById('buffer-size').value),
                prefetch_threshold: parseFloat(document.getElementById('prefetch-threshold').value),
                use_progressive_loading: document.getElementById('progressive-loading').value === 'true'
            };
        }
        
        async function start() {
            const bufferParams = getSelectedBufferParams();
            
            startButton.disabled = true;
            stopButton.disabled = false;
            
            // Create peer connection
            pc = new RTCPeerConnection({
                sdpSemantics: 'unified-plan',
                iceServers: [
                    {
                        urls: 'stun:stun.l.google.com:19302'
                    }
                ]
            });
            
            // Handle incoming tracks
            pc.addEventListener('track', (event) => {
                if (event.track.kind === 'video') {
                    videoElement.srcObject = new MediaStream([event.track]);
                }
            });
            
            // Create offer
            const offer = await pc.createOffer({
                offerToReceiveVideo: true
            });
            await pc.setLocalDescription(offer);
            
            // Send offer to server and get answer
            const response = await fetch('/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sdp: pc.localDescription.sdp,
                    type: pc.localDescription.type,
                    buffer_size: bufferParams.buffer_size,
                    prefetch_threshold: bufferParams.prefetch_threshold,
                    use_progressive_loading: bufferParams.use_progressive_loading
                })
            });
            
            const answer = await response.json();
            await pc.setRemoteDescription(answer);
            
            // Start metrics polling
            startMetricsPolling();
        }
        
        async function stop() {
            stopButton.disabled = true;
            
            // Stop metrics polling
            if (metricsInterval) {
                clearInterval(metricsInterval);
                metricsInterval = null;
            }
            
            // Close connection
            if (pc) {
                pc.close();
                pc = null;
            }
            
            // Stop video
            if (videoElement.srcObject) {
                videoElement.srcObject.getTracks().forEach(track => track.stop());
                videoElement.srcObject = null;
            }
            
            startButton.disabled = false;
        }
        
        async function pollMetrics() {
            try {
                const response = await fetch('/metrics');
                const metrics = await response.json();
                
                // Update buffer metrics
                bufferSizeElement.textContent = metrics.buffer.size;
                fillLevelElement.textContent = (metrics.buffer.fill_level * 100).toFixed(1);
                underflowsElement.textContent = metrics.buffer.underflows;
                overflowsElement.textContent = metrics.buffer.overflows;
                
                // Update performance metrics
                framerateElement.textContent = metrics.performance.framerate.toFixed(2);
                processingTimeElement.textContent = metrics.performance.processing_time.toFixed(2);
                totalFramesElement.textContent = metrics.performance.total_frames;
                
                // Update network metrics
                bandwidthElement.textContent = metrics.network.bandwidth.toFixed(2);
                latencyElement.textContent = metrics.network.latency.toFixed(2);
                packetsLostElement.textContent = metrics.network.packets_lost;
            } catch (error) {
                console.error('Error fetching metrics:', error);
            }
        }
        
        function startMetricsPolling() {
            // Poll every second
            metricsInterval = setInterval(pollMetrics, 1000);
        }
        
        // Event listeners
        startButton.addEventListener('click', start);
        stopButton.addEventListener('click', stop);
    </script>
</body>
</html>
"""

class OptimizedStreamingExample:
    """Example class for demonstrating optimized WebRTC streaming from IPFS."""
    
    def __init__(self, cid=None, http_port=8080, webrtc_port=8081):
        """Initialize the streaming example.
        
        Args:
            cid: Content identifier to stream. If None, a sample video will be added
            http_port: Port for the HTTP server serving the client page
            webrtc_port: Port for the WebRTC signaling server
        """
        self.cid = cid
        self.http_port = http_port
        self.webrtc_port = webrtc_port
        self.app = None
        self.stream_info = None
        self.metrics = {
            "buffer": {
                "size": 0,
                "fill_level": 0,
                "underflows": 0,
                "overflows": 0
            },
            "performance": {
                "framerate": 0,
                "processing_time": 0,
                "total_frames": 0
            },
            "network": {
                "bandwidth": 0,
                "latency": 0,
                "packets_lost": 0
            }
        }
        
        # Create MCP server instance
        self.mcp_server = MCPServer(debug_mode=True)
        self.ipfs_model = self.mcp_server.models["ipfs"]
        
        # Ensure we have a CID to stream
        if self.cid is None:
            self._add_sample_content()
    
    def _add_sample_content(self):
        """Add a sample video file to IPFS if no CID is provided."""
        # Check if we have a sample video in the examples directory
        sample_path = os.path.join(os.path.dirname(__file__), "sample_video.mp4")
        
        if not os.path.exists(sample_path):
            # Create a temporary file with simple content if sample doesn't exist
            logger.info("Sample video not found, creating a placeholder")
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            kit = ipfs_kit()
            
            # Use a small test pattern if available
            result = kit.ipfs_add("<test pattern content - in a real example this would be video data>")
            self.cid = result["Hash"]
            logger.info(f"Added test content with CID: {self.cid}")
        else:
            # Add the existing sample video
            logger.info(f"Adding sample video from {sample_path}")
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            kit = ipfs_kit()
            result = kit.ipfs_add_file(sample_path)
            self.cid = result["Hash"]
            logger.info(f"Added sample video with CID: {self.cid}")
    
    async def _start_stream(self, request):
        """Handle WebRTC signaling and start the stream."""
        params = await request.json()
        
        # Extract SDP offer
        offer = {
            "sdp": params["sdp"],
            "type": params["type"]
        }
        
        # Extract buffer parameters
        buffer_size = params.get("buffer_size", 30)
        prefetch_threshold = params.get("prefetch_threshold", 0.5)
        use_progressive_loading = params.get("use_progressive_loading", True)
        
        logger.info(f"Starting stream with buffer_size={buffer_size}, "
                   f"prefetch_threshold={prefetch_threshold}, "
                   f"progressive_loading={use_progressive_loading}")
                   
        # Start WebRTC stream with optimized buffer settings
        stream_result = self.ipfs_model.stream_content_webrtc(
            cid=self.cid,
            listen_address="127.0.0.1",
            port=self.webrtc_port,
            ice_servers=[{"urls": ["stun:stun.l.google.com:19302"]}],
            buffer_size=buffer_size,
            prefetch_threshold=prefetch_threshold,
            use_progressive_loading=use_progressive_loading,
            enable_benchmark=True
        )
        
        # Store stream info for later reference
        self.stream_info = stream_result
        
        if not stream_result.get("success", False):
            return web.json_response({"error": stream_result.get("error", "Unknown error")}, status=500)
        
        # Get the PC and track for metrics tracking
        pc = stream_result.get("pc")
        track = stream_result.get("track")
        
        if track and hasattr(track, "buffer_metrics"):
            # Update initial buffer metrics
            self.metrics["buffer"]["size"] = track.buffer_size
            
        # Process the offer and generate answer
        answer = await stream_result.get("handle_offer")(offer)
        
        # Start metrics collection thread
        self._start_metrics_collection(track)
        
        return web.json_response(answer)
    
    def _start_metrics_collection(self, track):
        """Start collecting metrics from the media track in a background thread."""
        if not track:
            logger.warning("Cannot start metrics collection: No track provided")
            return
            
        def collect_metrics():
            while self.stream_info and self.stream_info.get("active", False):
                try:
                    # Update buffer metrics
                    if hasattr(track, "buffer_metrics"):
                        buffer_metrics = track.buffer_metrics
                        self.metrics["buffer"]["fill_level"] = buffer_metrics.get("fill_level", 0)
                        self.metrics["buffer"]["underflows"] = buffer_metrics.get("underflows", 0)
                        self.metrics["buffer"]["overflows"] = buffer_metrics.get("overflows", 0)
                    
                    # Update performance metrics
                    if hasattr(track, "performance_metrics"):
                        perf_metrics = track.performance_metrics
                        self.metrics["performance"]["framerate"] = perf_metrics.get("framerate", 0)
                        self.metrics["performance"]["processing_time"] = perf_metrics.get("processing_time", 0)
                        self.metrics["performance"]["total_frames"] = perf_metrics.get("frames_processed", 0)
                    
                    # Update network metrics if available
                    # Note: These would typically come from WebRTC stats in a real application
                    # For this example, we're using simulated values
                    self.metrics["network"]["bandwidth"] = 1500 + (time.time() % 200)  # simulate fluctuation
                    self.metrics["network"]["latency"] = 20 + (time.time() % 15)
                    self.metrics["network"]["packets_lost"] = int(time.time() % 5)
                    
                except Exception as e:
                    logger.error(f"Error collecting metrics: {e}")
                
                time.sleep(1)
        
        # Start metrics collection in a background thread
        Thread(target=collect_metrics, daemon=True).start()
    
    async def _get_metrics(self, request):
        """Return current streaming metrics."""
        return web.json_response(self.metrics)
    
    async def _index(self, request):
        """Serve the HTML client page."""
        return web.Response(text=HTML_TEMPLATE, content_type='text/html')
    
    async def setup_routes(self, app):
        """Set up the HTTP server routes."""
        app.router.add_get('/', self._index)
        app.router.add_post('/stream', self._start_stream)
        app.router.add_get('/metrics', self._get_metrics)
    
    async def start(self):
        """Start the HTTP server."""
        self.app = web.Application()
        await self.setup_routes(self.app)
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.http_port)
        
        logger.info(f"Starting HTTP server on http://localhost:{self.http_port}")
        await site.start()
        
        # Keep the server running
        try:
            while True:
                await anyio.sleep(3600)  # Sleep for an hour (or until interrupted)
        finally:
            logger.info("Shutting down server")
            await runner.cleanup()
            
            # Clean up any active streams
            if self.stream_info and self.stream_info.get("active", False):
                cleanup_func = self.stream_info.get("cleanup")
                if cleanup_func:
                    cleanup_func()

def main():
    """Main entry point for the example."""
    # Create and start the streaming example
    example = OptimizedStreamingExample()
    
    try:
        # Run the async-io event loop
        anyio.run(example.start())
    except KeyboardInterrupt:
        logger.info("Example stopped by user")

if __name__ == "__main__":
    main()
