#!/usr/bin/env python3
"""
IPFS WebRTC Streaming Example

This example demonstrates how to use the WebRTC streaming capabilities of IPFS Kit
to stream audio/video content directly from IPFS with minimal latency. It uses
the aiortc library to create a WebRTC client that connects to the IPFS Kit server.

Features demonstrated:
1. Setting up a WebRTC signaling server
2. Client-side streaming from IPFS content
3. Adaptive bitrate handling
4. Performance metrics collection
5. Multiple stream support

Requirements:
- ipfs_kit_py[webrtc] - Install with pip
- ipfs_kit_py[api] - For the server component
- OpenCV (cv2) - For video playback/processing (optional)
- PyAudio - For audio playback (optional)

Usage:
Server mode:
    python webrtc_streaming_example.py --server

Client mode:
    python webrtc_streaming_example.py --client --signaling-url ws://localhost:8000/ws/webrtc --cid QmExample...
"""

import argparse
import anyio
import json
import logging
import os
import sys
import time
import uuid
from typing import Dict, List, Optional, Union, Any
from urllib.parse import urlparse

# Check for optional dependencies
HAVE_CV2 = False
HAVE_NUMPY = False
HAVE_AIORTC = False
HAVE_WEBRTC = False

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    pass

try:
    import cv2
    HAVE_CV2 = True
except ImportError:
    pass

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaBlackhole
    import websockets
    HAVE_AIORTC = True
except ImportError:
    pass

# Import FastAPI for server mode (with fallback for CLI-only mode)
HAVE_FASTAPI = False
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    HAVE_FASTAPI = True
except ImportError:
    pass

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('webrtc_example')

# Check if all webrtc dependencies are available
HAVE_WEBRTC = HAVE_NUMPY and HAVE_AIORTC

# Show a dependency status message
if not HAVE_WEBRTC:
    logger.warning("Some WebRTC dependencies are missing. Full functionality may not be available.")
    logger.warning(f"Dependency status: numpy={HAVE_NUMPY}, aiortc={HAVE_AIORTC}, cv2={HAVE_CV2}")
    logger.warning("Install dependencies with: pip install ipfs_kit_py[webrtc]")


class IPFSWebRTCClient:
    """Client for streaming media content from IPFS using WebRTC."""
    
    def __init__(self, server_url, cid=None, kind="video", frame_rate=30, quality="auto", stun_servers=None):
        """
        Initialize the WebRTC client.
        
        Args:
            server_url: WebSocket URL for the signaling server
            cid: IPFS Content ID to stream
            kind: Media type ("video" or "audio")
            frame_rate: Target frame rate for video
            quality: Initial quality level ("very_low", "low", "medium", "high", "very_high", "auto")
            stun_servers: List of STUN servers for NAT traversal
        """
        if not HAVE_WEBRTC:
            logger.error("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
            raise ImportError("Required WebRTC dependencies not available")
            
        self.server_url = server_url
        self.cid = cid
        self.kind = kind
        self.frame_rate = frame_rate
        self.quality = quality
        
        self.websocket = None
        self.pc = None
        self.pc_id = None
        self.track = None
        self.recorder = None
        
        # Use provided STUN servers or default to Google's
        self.ice_servers = []
        if stun_servers:
            for server in stun_servers:
                self.ice_servers.append({"urls": [server]})
        else:
            self.ice_servers = [
                {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}
            ]
            
        # Track statistics
        self.stats = {
            "connection_attempts": 0,
            "successful_connections": 0,
            "frames_received": 0,
            "bytes_received": 0,
            "stream_duration": 0,
            "quality_changes": [],
            "connection_state_changes": [],
            "current_quality": quality,
            "start_time": None,
            "connected_time": None
        }
        
        # Event for signaling when the connection is established
        self.connection_established = anyio.Event()
        
        # Flag for detecting if the process was interrupted
        self.interrupted = False
    
    async def connect(self):
        """Connect to the signaling server."""
        logger.info(f"Connecting to server: {self.server_url}")
        
        self.stats["connection_attempts"] += 1
        
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info("Connected to signaling server")
            
            # Wait for welcome message
            welcome = await self.websocket.recv()
            welcome_data = json.loads(welcome)
            
            if welcome_data.get("type") == "welcome":
                logger.info(f"Server says: {welcome_data.get('message')}")
                
                # Check if the server supports our desired media kind
                capabilities = welcome_data.get("capabilities", [])
                if capabilities and self.kind not in capabilities:
                    logger.warning(f"Server does not support {self.kind}. Available: {capabilities}")
                    return False
                    
                return True
            else:
                logger.error(f"Unexpected welcome message: {welcome_data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the server and clean up resources."""
        logger.info("Disconnecting...")
        
        self.interrupted = True
        
        # Calculate stream duration if we had a successful connection
        if self.stats["start_time"] and self.stats["connected_time"]:
            self.stats["stream_duration"] = time.time() - self.stats["connected_time"]
        
        # Close peer connection
        if self.pc:
            await self.pc.close()
            self.pc = None
        
        # Close recorder
        if self.recorder:
            await self.recorder.stop()
            self.recorder = None
        
        # Send close message
        if self.websocket and self.pc_id:
            try:
                await self.websocket.send(json.dumps({
                    "type": "close", 
                    "pc_id": self.pc_id
                }))
                logger.info(f"Sent close message for peer connection {self.pc_id}")
            except Exception as e:
                logger.warning(f"Error sending close message: {e}")
        
        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        logger.info("Disconnected from server")
        
        # Log final statistics
        self._log_statistics()
    
    def _log_statistics(self):
        """Log streaming statistics."""
        if self.stats["connected_time"]:
            duration = time.time() - self.stats["connected_time"]
            logger.info(f"Stream Statistics:")
            logger.info(f"  Duration: {duration:.2f} seconds")
            logger.info(f"  Frames received: {self.stats['frames_received']}")
            
            if duration > 0:
                fps = self.stats["frames_received"] / duration
                logger.info(f"  Average FPS: {fps:.2f}")
                
            if self.stats["bytes_received"] > 0:
                mb_received = self.stats["bytes_received"] / (1024 * 1024)
                bitrate = (self.stats["bytes_received"] * 8) / duration / 1000  # kbps
                logger.info(f"  Data received: {mb_received:.2f} MB")
                logger.info(f"  Average bitrate: {bitrate:.2f} kbps")
                
            if self.stats["quality_changes"]:
                logger.info(f"  Quality changes: {len(self.stats['quality_changes'])}")
                for change in self.stats["quality_changes"][-5:]:  # Show last 5 changes
                    logger.info(f"    {change['time']:.2f}s: {change['from']} -> {change['to']}")
    
    async def start_streaming(self):
        """Start streaming content from IPFS via WebRTC."""
        if not self.websocket:
            logger.error("Not connected to server")
            return False
        
        if not self.cid:
            logger.error("No CID specified")
            return False
            
        self.stats["start_time"] = time.time()
        
        # Request an offer
        await self.websocket.send(json.dumps({
            "type": "offer_request",
            "cid": self.cid,
            "kind": self.kind,
            "frameRate": self.frame_rate,
            "quality": self.quality
        }))
        
        logger.info(f"Requested stream for CID: {self.cid}")
        
        # Create a new peer connection
        self.pc = RTCPeerConnection({"iceServers": self.ice_servers})
        
        # Set up event handlers for connection monitoring
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            logger.info(f"Connection state: {state}")
            
            # Record state change
            self.stats["connection_state_changes"].append({
                "time": time.time() - self.stats["start_time"],
                "state": state
            })
            
            if state == "connected":
                # Mark connection time for statistics
                if not self.stats["connected_time"]:
                    self.stats["connected_time"] = time.time()
                    self.stats["successful_connections"] += 1
                
                # Signal that the connection is established
                self.connection_established.set()
                
            elif state == "failed" or state == "closed":
                if not self.interrupted:
                    logger.error(f"Connection {state}, attempting to restart...")
                    # This would be a good place to implement automatic reconnection
                    # For now, we just disconnect
                    await self.disconnect()
        
        # Handle incoming tracks from the server
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"Received track: {track.kind}")
            self.track = track
            
            # Set up appropriate handling based on track kind
            if track.kind == "audio":
                # Set up audio playback if possible
                try:
                    self.recorder = MediaRecorder("audio.wav")
                    self.recorder.addTrack(track)
                    await self.recorder.start()
                    logger.info("Started audio recorder")
                except Exception as e:
                    logger.error(f"Failed to set up audio recording: {e}")
            
            elif track.kind == "video":
                # Handle video tracks
                if HAVE_CV2:
                    # Start video display in a separate task
                    anyio.create_task(self.display_video(track))
                else:
                    logger.warning("OpenCV not available, falling back to recording")
                    # Fallback to just recording
                    try:
                        self.recorder = MediaRecorder("ipfs_video.mp4")
                        self.recorder.addTrack(track)
                        await self.recorder.start()
                        logger.info("Started video recorder (OpenCV not available)")
                    except Exception as e:
                        logger.error(f"Failed to set up video recording: {e}")
            
            # Handle track ending
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track ended: {track.kind}")
                if self.recorder:
                    await self.recorder.stop()
                    self.recorder = None
        
        # Wait for offer from server
        offer_msg = await self.websocket.recv()
        try:
            offer_data = json.loads(offer_msg)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse offer message: {offer_msg}")
            return False
        
        if offer_data.get("type") != "offer":
            logger.error(f"Expected offer, got: {offer_data}")
            return False
        
        # Get PC ID for this connection
        self.pc_id = offer_data.get("pc_id")
        
        try:
            # Set remote description (the offer)
            await self.pc.setRemoteDescription(
                RTCSessionDescription(sdp=offer_data["sdp"], type=offer_data["sdpType"])
            )
            
            # Create and set local description (answer)
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            # Send answer to server
            await self.websocket.send(json.dumps({
                "type": "answer",
                "pc_id": self.pc_id,
                "sdp": self.pc.localDescription.sdp,
                "sdpType": self.pc.localDescription.type
            }))
            
            logger.info("Sent answer to server")
            
            # Start handling signaling messages in a separate task
            anyio.create_task(self.handle_signaling())
            
            # Wait for connection to be established with timeout
            try:
                await anyio.wait_for(self.connection_established.wait(), timeout=30)
                logger.info("WebRTC connection established successfully")
                return True
            except anyio.TimeoutError:
                logger.error("Connection establishment timed out")
                return False
                
        except Exception as e:
            logger.error(f"Error establishing connection: {e}")
            return False
    
    async def handle_signaling(self):
        """Handle ongoing signaling messages."""
        while self.websocket and not self.interrupted:
            try:
                message = await self.websocket.recv()
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message: {message}")
                    continue
                
                if data.get("type") == "candidate" and self.pc:
                    # Add ICE candidate
                    await self.pc.addIceCandidate({
                        "candidate": data["candidate"],
                        "sdpMid": data["sdpMid"],
                        "sdpMLineIndex": data["sdpMLineIndex"]
                    })
                
                elif data.get("type") == "connected":
                    logger.info("Server confirmed WebRTC connection established")
                
                elif data.get("type") == "closed":
                    logger.info("Connection closed by server")
                    await self.disconnect()
                    break
                
                elif data.get("type") == "notification" and data.get("notification_type") == "webrtc_quality_changed":
                    # Quality change notification from server
                    notification_data = data.get("data", {})
                    if "quality_level" in notification_data and notification_data["quality_level"] != self.stats["current_quality"]:
                        quality_change = {
                            "time": time.time() - self.stats["start_time"],
                            "from": self.stats["current_quality"],
                            "to": notification_data["quality_level"],
                            "network_score": notification_data.get("network_score", 0),
                            "buffer_level": notification_data.get("buffer_level", 0)
                        }
                        self.stats["quality_changes"].append(quality_change)
                        self.stats["current_quality"] = notification_data["quality_level"]
                        
                        logger.info(f"Stream quality changed to {notification_data['quality_level']} "
                                   f"(score: {notification_data.get('network_score', 'N/A')})")
                
                elif data.get("type") == "error":
                    logger.error(f"Server error: {data.get('message')}")
                
                else:
                    logger.debug(f"Received signaling message: {data.get('type', 'unknown')}")
                
            except websockets.ConnectionClosed:
                logger.info("WebSocket connection closed")
                break
            except Exception as e:
                logger.error(f"Error handling signaling message: {e}")
                # Don't break the loop for sporadic errors
    
    async def display_video(self, track):
        """Display video using OpenCV."""
        if not HAVE_CV2:
            logger.error("OpenCV not available, can't display video")
            return
            
        logger.info("Starting video display")
        
        # Create OpenCV window
        window_name = f"IPFS WebRTC Stream: {self.cid[:10]}..."
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)
        
        # Frame counting for statistics
        frame_count = 0
        last_stats_time = time.time()
        start_time = time.time()
        
        try:
            # Create media player to receive frames
            player = MediaBlackhole()
            player.addTrack(track)
            await player.start()
            
            # Process frames from the track
            while not self.interrupted:
                try:
                    # Get next frame with timeout
                    frame = await anyio.wait_for(track.recv(), timeout=5.0)
                    
                    # Update statistics
                    frame_count += 1
                    self.stats["frames_received"] += 1
                    
                    # Estimate data size for statistics (very rough)
                    if hasattr(frame, 'width') and hasattr(frame, 'height'):
                        # Assuming YUV420 format (12 bits per pixel)
                        frame_size = (frame.width * frame.height * 12) // 8
                        self.stats["bytes_received"] += frame_size
                    
                    # Convert to numpy array for OpenCV
                    img = frame.to_ndarray(format="bgr24")
                    
                    # Add quality and statistics overlay
                    current_time = time.time()
                    seconds_elapsed = int(current_time - start_time)
                    
                    # Log statistics every 5 seconds
                    if current_time - last_stats_time >= 5.0:
                        fps = frame_count / (current_time - last_stats_time)
                        logger.info(f"Video playback stats - FPS: {fps:.1f}, "
                                   f"Quality: {self.stats['current_quality']}, "
                                   f"Duration: {seconds_elapsed}s, "
                                   f"Frames: {self.stats['frames_received']}")
                        frame_count = 0
                        last_stats_time = current_time
                    
                    # Add info text to the frame
                    cv2.putText(img, f"CID: {self.cid[:16]}...", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.6, (0, 255, 0), 2)
                    cv2.putText(img, f"Quality: {self.stats['current_quality']}", (10, 55), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(img, f"Time: {seconds_elapsed}s", (10, 85), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    cv2.putText(img, f"Press 'Q' to quit", (10, 115), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    # Display the frame
                    cv2.imshow(window_name, img)
                    
                    # Check for key press (q or ESC to quit)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord('q'), 27):  # q or ESC
                        logger.info("User pressed quit key")
                        self.interrupted = True
                        break
                    
                    # Small sleep to give the UI a chance to update
                    await anyio.sleep(0.01)
                    
                except anyio.TimeoutError:
                    logger.warning("Timeout waiting for video frame")
                    continue
                except Exception as e:
                    logger.error(f"Error receiving/displaying frame: {e}")
                    await anyio.sleep(0.1)  # Avoid tight loop on errors
                
        except Exception as e:
            logger.error(f"Error in video display loop: {e}")
            
        finally:
            # Clean up
            cv2.destroyAllWindows()
            logger.info("Video display stopped")


async def run_client(args):
    """Run the WebRTC client with the given arguments."""
    # Create client instance
    client = IPFSWebRTCClient(
        server_url=args.signaling_url,
        cid=args.cid,
        kind=args.kind,
        frame_rate=args.frame_rate,
        quality=args.quality,
        stun_servers=args.stun_server
    )
    
    try:
        # Connect to server
        if not await client.connect():
            logger.error("Failed to connect to signaling server")
            return 1
        
        # Start streaming
        if not await client.start_streaming():
            logger.error("Failed to start streaming")
            await client.disconnect()
            return 1
        
        # Keep running until user interrupts or connection fails
        while not client.interrupted:
            await anyio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        return 1
    finally:
        # Clean up
        await client.disconnect()
    
    return 0


async def run_server(args):
    """Run a WebRTC streaming server."""
    if not HAVE_FASTAPI:
        logger.error("FastAPI not installed. Cannot run server mode.")
        logger.error("Install with: pip install fastapi uvicorn")
        return 1
        
    # Import ipfs_kit_py here to avoid issues when only the client is needed
    try:
        from ipfs_kit_py import ipfs_kit
        from ipfs_kit_py.webrtc_streaming import handle_webrtc_signaling
    except ImportError:
        logger.error("Failed to import ipfs_kit_py. Make sure it's installed.")
        logger.error("Install with: pip install ipfs_kit_py[api]")
        return 1
    
    # Create an IPFS client
    logger.info("Initializing IPFS client...")
    kit = ipfs_kit()
    
    # Create FastAPI app
    app = FastAPI(title="IPFS WebRTC Streaming Server")
    
    # Serve the HTML client if requested
    if args.serve_client:
        # Determine the path to the example HTML file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        client_path = os.path.join(script_dir, "webrtc_streaming_example.html")
        
        if os.path.exists(client_path):
            # Create a temporary directory to serve the file
            import tempfile
            static_dir = tempfile.mkdtemp(prefix="ipfs_webrtc_")
            
            # Copy the HTML file to the temp directory
            import shutil
            shutil.copy(client_path, os.path.join(static_dir, "index.html"))
            
            # Mount static files
            app.mount("/", StaticFiles(directory=static_dir, html=True), name="webrtc_client")
            logger.info(f"Serving WebRTC client at http://{args.host}:{args.port}/")
    
    # WebSocket endpoint for WebRTC signaling
    @app.websocket("/ws/webrtc")
    async def websocket_endpoint(websocket: WebSocket):
        await handle_webrtc_signaling(websocket, kit.ipfs)
    
    # Start the server
    logger.info(f"Starting WebRTC signaling server on {args.host}:{args.port}")
    try:
        config = uvicorn.Config(
            app=app, 
            host=args.host, 
            port=args.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1
    
    return 0


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="IPFS WebRTC Streaming Example")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--client", action="store_true", help="Run in client mode")
    mode_group.add_argument("--server", action="store_true", help="Run in server mode")
    
    # Client options
    client_group = parser.add_argument_group("Client options")
    client_group.add_argument("--signaling-url", 
                            type=str, 
                            default="ws://localhost:8000/ws/webrtc",
                            help="WebSocket URL for the signaling server")
    
    client_group.add_argument("--cid", 
                            type=str, 
                            help="IPFS Content ID to stream")
    
    client_group.add_argument("--kind", 
                            type=str, 
                            default="video",
                            choices=["video", "audio"],
                            help="Media type (video or audio)")
    
    client_group.add_argument("--frame-rate", 
                            type=int, 
                            default=30,
                            help="Target frame rate for video")
    
    client_group.add_argument("--quality", 
                            type=str, 
                            default="auto",
                            choices=["very_low", "low", "medium", "high", "very_high", "auto"],
                            help="Initial quality level")
    
    client_group.add_argument("--stun-server", 
                           action="append",
                           help="STUN server(s) for NAT traversal (can be specified multiple times)")
    
    # Server options
    server_group = parser.add_argument_group("Server options")
    server_group.add_argument("--host", 
                             type=str, 
                             default="127.0.0.1",
                             help="Host address to bind the server")
    
    server_group.add_argument("--port", 
                             type=int, 
                             default=8000,
                             help="Port to run the server on")
    
    server_group.add_argument("--serve-client", 
                             action="store_true",
                             help="Serve the WebRTC HTML client")
    
    return parser.parse_args()


async def main():
    """Main entry point for the application."""
    args = parse_arguments()
    
    if args.client:
        if not args.cid:
            print("Error: Please specify a CID with --cid")
            return 1
            
        return await run_client(args)
        
    elif args.server:
        return await run_server(args)
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = anyio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
