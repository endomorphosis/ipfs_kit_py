#!/usr/bin/env python3
"""
MCP WebRTC AioRTC Client

This script implements a complete WebRTC client for the IPFS Kit MCP server using the aiortc library.
It establishes a WebRTC connection to the server, receives media streams, and provides detailed
performance metrics. This is an advanced companion to the mcp_webrtc_test.py script, focusing
specifically on real WebRTC connections rather than just API testing.

Features:
- WebSocket-based signaling with the MCP server
- Complete WebRTC session establishment
- Media stream handling (video/audio)
- Adaptive bitrate reporting
- Statistics collection and reporting
- Optional video display using OpenCV (if available)

Requirements:
- ipfs_kit_py[webrtc] - For WebRTC dependencies
- aiortc - For WebRTC client functionality
- websockets - For WebSocket signaling
- opencv-python (optional) - For video display

Usage:
    python mcp_webrtc_aiortc_client.py --server-url http://localhost:9999/mcp --cid QmExample...
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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_webrtc_client')

# Check for dependencies
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaBlackhole
    HAVE_AIORTC = True
except ImportError:
    logger.error(
        "aiortc not available. Install with: pip install aiortc\n"
        "This is required for WebRTC client functionality."
    )
    HAVE_AIORTC = False

try:
    import websockets
    HAVE_WEBSOCKETS = True
except ImportError:
    logger.error(
        "websockets not available. Install with: pip install websockets\n"
        "This is required for WebRTC signaling."
    )
    HAVE_WEBSOCKETS = False

try:
    import cv2
    import numpy as np
    HAVE_OPENCV = True
except ImportError:
    logger.warning("OpenCV not available - video display will be disabled")
    HAVE_OPENCV = False

# Check if we have minimum requirements
if not (HAVE_AIORTC and HAVE_WEBSOCKETS):
    logger.error("Missing required dependencies. Please install them and try again.")
    sys.exit(1)


class MCPWebRTCClient:
    """WebRTC client for IPFS Kit MCP server using aiortc."""

    def __init__(
        self,
        server_url: str,
        cid: str,
        use_websocket_url: Optional[str] = None,
        display_video: bool = False,
        save_video_path: Optional[str] = None,
        quality: str = "medium",
        ice_servers: Optional[List[Dict[str, Any]]] = None,
        verbose: bool = False
    ):
        """Initialize the WebRTC client.

        Args:
            server_url: Base URL for the MCP server (e.g., http://localhost:9999/mcp)
            cid: Content ID to stream
            use_websocket_url: Override WebSocket URL (otherwise derived from server_url)
            display_video: Whether to display video using OpenCV
            save_video_path: Path to save video (optional)
            quality: Streaming quality (low, medium, high, auto)
            ice_servers: ICE servers for NAT traversal
            verbose: Whether to enable verbose logging
        """
        self.server_url = server_url.rstrip('/')
        self.cid = cid
        self.display_video = display_video and HAVE_OPENCV
        self.save_video_path = save_video_path
        self.quality = quality
        self.verbose = verbose

        # Derive WebSocket URL from server URL if not specified
        if use_websocket_url:
            self.websocket_url = use_websocket_url
        else:
            # Convert http(s):// to ws(s)://
            parsed = urlparse(server_url)
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
            self.websocket_url = f"{ws_scheme}://{parsed.netloc}{parsed.path}/webrtc/ws"

        logger.info(f"WebSocket URL: {self.websocket_url}")

        # Set up ICE servers
        self.ice_servers = ice_servers or [
            {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]}
        ]

        # WebRTC objects
        self.websocket = None
        self.pc = None
        self.pc_id = None
        self.dc = None  # data channel
        self.video_track = None
        self.audio_track = None
        self.recorder = None

        # Session state
        self.session_id = str(uuid.uuid4())
        self.stream_active = False
        self.interrupted = False
        self.started_at = None
        self.connected_at = None
        self.first_frame_at = None

        # Event to signal when connection is established
        self.connection_established = anyio.Event()

        # Statistics
        self.stats = {
            "connection_attempts": 0,
            "connection_successes": 0,
            "connection_failures": 0,
            "connection_time_ms": None,
            "frames_received": 0,
            "frames_dropped": 0,
            "first_frame_time_ms": None,
            "video_bytes_received": 0,
            "audio_bytes_received": 0,
            "video_bitrate_kbps": None,
            "audio_bitrate_kbps": None,
            "avg_fps": None,
            "resolution": None,
            "quality_changes": [],
            "ice_state_changes": [],
            "connection_state_changes": [],
            "latest_stats": {}
        }

    async def connect(self):
        """Connect to the MCP server and establish WebRTC session.

        Returns:
            True if successfully connected, False otherwise
        """
        logger.info(f"Connecting to MCP WebRTC server: {self.server_url}")
        self.stats["connection_attempts"] += 1
        start_time = time.time()
        self.started_at = start_time

        try:
            # Create WebSocket connection
            logger.info(f"Establishing WebSocket connection to {self.websocket_url}")
            self.websocket = await websockets.connect(
                self.websocket_url,
                max_size=10 * 1024 * 1024  # 10MB max message size
            )

            # Create peer connection
            logger.info("Creating RTCPeerConnection")
            self.pc = RTCPeerConnection(
                {"iceServers": self.ice_servers}
            )

            # Set up event handlers
            await self._setup_event_handlers()

            # Receive welcome message
            welcome_msg = await self.websocket.recv()
            try:
                welcome_data = json.loads(welcome_msg)
                if welcome_data.get("type") == "welcome":
                    logger.info(f"Received welcome message: {welcome_data.get('message', '')}")
                else:
                    logger.warning(f"Unexpected welcome message type: {welcome_data.get('type')}")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse welcome message: {welcome_msg}")

            # Send offer request
            logger.info(f"Requesting stream for CID: {self.cid}")
            await self.websocket.send(json.dumps({
                "type": "offer_request",
                "cid": self.cid,
                "kind": "video",  # Request video streams
                "frameRate": 30,  # Request 30fps
                "quality": self.quality,
                "session_id": self.session_id
            }))

            # Wait for offer
            logger.info("Waiting for offer from server...")
            offer_message = await self.websocket.recv()
            offer_data = json.loads(offer_message)

            if offer_data.get("type") != "offer":
                error_msg = f"Expected offer message, got: {offer_data.get('type')}"
                logger.error(error_msg)
                self.stats["connection_failures"] += 1
                return False

            # Get PC ID for tracking
            self.pc_id = offer_data.get("pc_id")
            logger.info(f"Received offer with PC ID: {self.pc_id}")

            # Set remote description (server's offer)
            logger.info("Setting remote description (offer)")
            await self.pc.setRemoteDescription(
                RTCSessionDescription(
                    sdp=offer_data["sdp"],
                    type=offer_data["sdpType"]
                )
            )

            # Create answer
            logger.info("Creating answer")
            answer = await self.pc.createAnswer()

            # Set local description (our answer)
            logger.info("Setting local description (answer)")
            await self.pc.setLocalDescription(answer)

            # Send answer to server
            logger.info("Sending answer to server")
            await self.websocket.send(json.dumps({
                "type": "answer",
                "pc_id": self.pc_id,
                "sdp": self.pc.localDescription.sdp,
                "sdpType": self.pc.localDescription.type,
                "session_id": self.session_id
            }))

            # Start handling signaling messages
            anyio.create_task(self._handle_signaling())

            # Wait for connection to be established with timeout
            logger.info("Waiting for connection to be established...")
            try:
                await anyio.wait_for(
                    self.connection_established.wait(),
                    timeout=30.0
                )
                connection_time = time.time() - start_time
                self.connected_at = time.time()
                self.stats["connection_time_ms"] = connection_time * 1000
                self.stats["connection_successes"] += 1

                logger.info(f"Connection established in {connection_time:.2f} seconds")
                self.stream_active = True
                return True

            except anyio.TimeoutError:
                logger.error("Connection timed out after 30 seconds")
                self.stats["connection_failures"] += 1
                return False

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            self.stats["connection_failures"] += 1
            return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.stats["connection_failures"] += 1
            return False

    async def _setup_event_handlers(self):
        """Set up WebRTC event handlers."""
        # Handle connection state changes
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            logger.info(f"Connection state changed to: {state}")

            # Record state change
            self.stats["connection_state_changes"].append({
                "state": state,
                "time": time.time() - self.started_at
            })

            if state == "connected":
                # Mark as connected and signal the event
                self.connection_established.set()

            elif state == "failed" or state == "closed":
                logger.warning(f"Connection {state}")
                if not self.interrupted:
                    # Could implement reconnection logic here
                    pass

        # Handle ICE connection state changes
        @self.pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            state = self.pc.iceConnectionState
            logger.info(f"ICE connection state changed to: {state}")

            # Record ICE state change
            self.stats["ice_state_changes"].append({
                "state": state,
                "time": time.time() - self.started_at
            })

        # Handle incoming tracks
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"Received {track.kind} track")

            if track.kind == "video":
                self.video_track = track

                # Get video resolution if available
                if hasattr(track, "width") and hasattr(track, "height"):
                    self.stats["resolution"] = f"{track.width}x{track.height}"

                # Start handling video frames
                if self.display_video and HAVE_OPENCV:
                    anyio.create_task(self._process_video(track))
                else:
                    # Just consume the track without displaying
                    player = MediaBlackhole()
                    player.addTrack(track)
                    await player.start()

                # Set up recording if requested
                if self.save_video_path:
                    self.recorder = MediaRecorder(self.save_video_path)
                    self.recorder.addTrack(track)
                    await self.recorder.start()
                    logger.info(f"Recording video to {self.save_video_path}")

            elif track.kind == "audio":
                self.audio_track = track

                # If we have a recorder, add the audio track
                if self.recorder:
                    self.recorder.addTrack(track)

                # Start playing audio
                player = MediaBlackhole()
                player.addTrack(track)
                await player.start()

            # Handle track ending
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track ended: {track.kind}")
                if track.kind == "video":
                    self.video_track = None
                elif track.kind == "audio":
                    self.audio_track = None

                # Stop recorder if both tracks are gone
                if self.recorder and not self.video_track and not self.audio_track:
                    await self.recorder.stop()
                    self.recorder = None

    async def _handle_signaling(self):
        """Handle WebRTC signaling messages from the server."""
        while self.websocket and not self.interrupted:
            try:
                message = await self.websocket.recv()

                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(f"Received non-JSON message: {message}")
                    continue

                msg_type = data.get("type")

                if self.verbose:
                    logger.debug(f"Received message: {msg_type}")

                if msg_type == "candidate" and self.pc:
                    # Handle ICE candidate
                    candidate = data.get("candidate", "")
                    sdp_mid = data.get("sdpMid", "")
                    sdp_mline_index = data.get("sdpMLineIndex", 0)

                    await self.pc.addIceCandidate({
                        "candidate": candidate,
                        "sdpMid": sdp_mid,
                        "sdpMLineIndex": sdp_mline_index
                    })

                    if self.verbose:
                        logger.debug(f"Added ICE candidate: {candidate[:30]}...")

                elif msg_type == "connected":
                    logger.info("Server confirmed WebRTC connection established")

                elif msg_type == "notification":
                    notification_type = data.get("notification_type")

                    if notification_type == "webrtc_quality_changed":
                        # Handle quality change notification
                        notification_data = data.get("data", {})
                        quality_level = notification_data.get("quality_level")
                        network_score = notification_data.get("network_score")

                        if quality_level:
                            logger.info(f"Quality changed to {quality_level} (score: {network_score})")

                            # Record quality change
                            self.stats["quality_changes"].append({
                                "from": self.quality,
                                "to": quality_level,
                                "network_score": network_score,
                                "time": time.time() - self.started_at
                            })

                            # Update current quality
                            self.quality = quality_level

                elif msg_type == "closed":
                    logger.info("Connection closed by server")
                    break

                elif msg_type == "error":
                    logger.error(f"Error from server: {data.get('message', 'Unknown error')}")
                    # Could implement error handling logic here

                else:
                    if self.verbose:
                        logger.debug(f"Unhandled message type: {msg_type}")

            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket connection closed")
                break

            except Exception as e:
                logger.error(f"Error handling signaling message: {e}")
                # Don't break the loop for sporadic errors

    async def _process_video(self, track):
        """Process video frames from the track.

        Args:
            track: MediaStreamTrack for video
        """
        if not HAVE_OPENCV:
            logger.error("OpenCV not available for video display")
            return

        # Create window for display
        window_name = f"IPFS WebRTC: {self.cid[:16]}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)

        # Stats for display
        frame_count = 0
        start_time = time.time()
        last_fps_update = start_time
        dropped_frames = 0

        logger.info("Starting video processing")

        try:
            while not self.interrupted:
                try:
                    # Wait for next frame with timeout
                    frame = await anyio.wait_for(track.recv(), timeout=1.0)
                    frame_time = time.time()

                    # Update frame count and timing
                    frame_count += 1
                    self.stats["frames_received"] += 1

                    # Record first frame time
                    if not self.first_frame_at:
                        self.first_frame_at = frame_time
                        self.stats["first_frame_time_ms"] = (frame_time - self.started_at) * 1000
                        logger.info(f"First frame received after {self.stats['first_frame_time_ms']:.2f}ms")

                    # Estimate data size for statistics (rough estimate)
                    if hasattr(frame, 'width') and hasattr(frame, 'height'):
                        # Assuming YUV420 format (12 bits per pixel)
                        frame_size = (frame.width * frame.height * 12) // 8
                        self.stats["video_bytes_received"] += frame_size

                        # Update resolution
                        self.stats["resolution"] = f"{frame.width}x{frame.height}"

                    # Convert frame for OpenCV
                    img = frame.to_ndarray(format="bgr24")

                    # Calculate FPS and bitrate every second
                    current_time = time.time()
                    elapsed = current_time - last_fps_update

                    if elapsed >= 1.0:
                        # Calculate FPS
                        fps = (frame_count - self.stats["frames_dropped"]) / elapsed
                        bitrate = (self.stats["video_bytes_received"] * 8) / (current_time - start_time) / 1000  # kbps

                        # Update stats
                        self.stats["avg_fps"] = fps
                        self.stats["video_bitrate_kbps"] = bitrate

                        # Reset for next update
                        frame_count = 0
                        self.stats["video_bytes_received"] = 0
                        last_fps_update = current_time

                        # Log stats
                        logger.info(f"FPS: {fps:.2f}, Bitrate: {bitrate:.2f} kbps, "
                                   f"Resolution: {self.stats['resolution']}, Quality: {self.quality}")

                    # Add overlay text
                    elapsed_time = current_time - self.started_at
                    self._add_stats_overlay(img, elapsed_time)

                    # Display the frame
                    cv2.imshow(window_name, img)

                    # Check for key press (q or ESC to quit)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord('q'), 27):  # q or ESC
                        logger.info("User requested exit")
                        self.interrupted = True
                        break

                except anyio.TimeoutError:
                    logger.warning("Timeout waiting for video frame")
                    self.stats["frames_dropped"] += 1
                    dropped_frames += 1

                except Exception as e:
                    logger.error(f"Error processing video frame: {e}")
                    await anyio.sleep(0.1)  # Avoid tight loop on errors

                # Small sleep to avoid tight loop
                await anyio.sleep(0.001)

        except Exception as e:
            logger.error(f"Error in video processing loop: {e}")

        finally:
            # Clean up
            cv2.destroyAllWindows()

    def _add_stats_overlay(self, img, elapsed_time):
        """Add statistics overlay to video frame.

        Args:
            img: NumPy array containing the image
            elapsed_time: Elapsed time in seconds
        """
        # Add text at the bottom of the frame
        height, width = img.shape[:2]

        # Background rectangle for better readability
        cv2.rectangle(img, (0, height - 110), (width, height), (0, 0, 0, 128), -1)

        # Helper function to add text with shadow for better readability
        def add_text(text, pos_y):
            # Shadow
            cv2.putText(
                img, text, (11, pos_y + 1),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2
            )
            # Text
            cv2.putText(
                img, text, (10, pos_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
            )

        # Add stats text
        add_text(f"CID: {self.cid[:20]}{'...' if len(self.cid) > 20 else ''}", height - 85)
        add_text(f"Quality: {self.quality}", height - 65)
        add_text(f"Time: {int(elapsed_time // 60):02d}:{int(elapsed_time % 60):02d}", height - 45)

        # Add performance stats if available
        if self.stats["avg_fps"]:
            add_text(f"FPS: {self.stats['avg_fps']:.1f}", height - 25)

        if self.stats["resolution"]:
            resolution_text = f"Resolution: {self.stats['resolution']}"
            text_size = cv2.getTextSize(resolution_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            add_text(resolution_text, height - 25)

        if self.stats["video_bitrate_kbps"]:
            bitrate_text = f"Bitrate: {self.stats['video_bitrate_kbps']:.1f} kbps"
            add_text(bitrate_text, height - 5)

    async def collect_stats(self):
        """Collect WebRTC statistics periodically.

        This runs until the connection is closed or interrupted.
        """
        if not self.pc:
            logger.error("No peer connection available for stats collection")
            return

        logger.info("Starting stats collection")

        try:
            while self.pc and not self.interrupted:
                # Collect stats
                stats = await self.pc.getStats()

                if stats:
                    # Process stats into a more usable format
                    processed_stats = self._process_rtc_stats(stats)

                    # Store latest stats
                    self.stats["latest_stats"] = processed_stats

                    # Update derived metrics
                    self._update_derived_metrics(processed_stats)

                    if self.verbose:
                        logger.debug(f"WebRTC stats: {json.dumps(processed_stats, default=str)}")

                # Wait before next collection
                await anyio.sleep(1.0)

        except Exception as e:
            logger.error(f"Error collecting stats: {e}")

    def _process_rtc_stats(self, stats):
        """Process and filter raw WebRTC stats into a more useful format.

        Args:
            stats: Raw stats from RTCPeerConnection.getStats()

        Returns:
            Dictionary with processed stats
        """
        processed = {}

        # Extract interesting stats
        for stat in stats.values():
            stat_type = stat.type

            if stat_type == "inbound-rtp":
                # RTP statistics for incoming media
                if stat.kind == "video":
                    processed["video_bytes_received"] = stat.bytesReceived
                    processed["video_packets_received"] = stat.packetsReceived
                    processed["video_frames_received"] = stat.framesReceived if hasattr(stat, "framesReceived") else None
                    processed["video_frames_decoded"] = stat.framesDecoded if hasattr(stat, "framesDecoded") else None
                    processed["video_nack_count"] = stat.nackCount if hasattr(stat, "nackCount") else None
                    processed["video_pli_count"] = stat.pliCount if hasattr(stat, "pliCount") else None
                    processed["video_fir_count"] = stat.firCount if hasattr(stat, "firCount") else None
                    processed["video_jitter"] = stat.jitter if hasattr(stat, "jitter") else None

                elif stat.kind == "audio":
                    processed["audio_bytes_received"] = stat.bytesReceived
                    processed["audio_packets_received"] = stat.packetsReceived
                    processed["audio_jitter"] = stat.jitter if hasattr(stat, "jitter") else None

            elif stat_type == "track" and stat.kind == "video":
                # Media track stats
                processed["frame_width"] = stat.frameWidth if hasattr(stat, "frameWidth") else None
                processed["frame_height"] = stat.frameHeight if hasattr(stat, "frameHeight") else None
                processed["frames_dropped"] = stat.framesDropped if hasattr(stat, "framesDropped") else None
                processed["frames_received"] = stat.framesReceived if hasattr(stat, "framesReceived") else None
                processed["frames_decoded"] = stat.framesDecoded if hasattr(stat, "framesDecoded") else None

            elif stat_type == "candidate-pair" and stat.state == "succeeded":
                # ICE candidate pair stats
                processed["ice_round_trip_time"] = stat.currentRoundTripTime if hasattr(stat, "currentRoundTripTime") else None
                processed["ice_available_outgoing_bitrate"] = stat.availableOutgoingBitrate if hasattr(stat, "availableOutgoingBitrate") else None
                processed["ice_available_incoming_bitrate"] = stat.availableIncomingBitrate if hasattr(stat, "availableIncomingBitrate") else None

        # Add timestamp
        processed["timestamp"] = time.time()

        return processed

    def _update_derived_metrics(self, stats):
        """Update derived metrics based on collected stats.

        Args:
            stats: Processed WebRTC stats
        """
        # Update resolution
        if (stats.get("frame_width") is not None and
            stats.get("frame_height") is not None):
            self.stats["resolution"] = f"{stats['frame_width']}x{stats['frame_height']}"

        # Update dropped frames if available
        if stats.get("frames_dropped") is not None:
            self.stats["frames_dropped"] = stats["frames_dropped"]

        # Calculate video bitrate
        if self.connected_at and stats.get("video_bytes_received") is not None:
            elapsed = time.time() - self.connected_at
            if elapsed > 0:
                video_bitrate = (stats["video_bytes_received"] * 8) / elapsed / 1000  # kbps
                self.stats["video_bitrate_kbps"] = video_bitrate

        # Calculate audio bitrate
        if self.connected_at and stats.get("audio_bytes_received") is not None:
            elapsed = time.time() - self.connected_at
            if elapsed > 0:
                audio_bitrate = (stats["audio_bytes_received"] * 8) / elapsed / 1000  # kbps
                self.stats["audio_bitrate_kbps"] = audio_bitrate

    async def disconnect(self):
        """Disconnect from the WebRTC session and clean up resources."""
        logger.info("Disconnecting from WebRTC session")
        self.interrupted = True

        # Stop recording if active
        if self.recorder:
            try:
                await self.recorder.stop()
            except Exception as e:
                logger.error(f"Error stopping recorder: {e}")
            self.recorder = None

        # Close peer connection
        if self.pc:
            try:
                await self.pc.close()
            except Exception as e:
                logger.error(f"Error closing peer connection: {e}")
            self.pc = None

        # Send close message
        if self.websocket and self.pc_id:
            try:
                await self.websocket.send(json.dumps({
                    "type": "close",
                    "pc_id": self.pc_id,
                    "session_id": self.session_id
                }))
                logger.info(f"Sent close message for peer connection {self.pc_id}")
            except Exception as e:
                logger.error(f"Error sending close message: {e}")

        # Close WebSocket
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            self.websocket = None

        # Close any OpenCV windows
        if self.display_video and HAVE_OPENCV:
            cv2.destroyAllWindows()

        logger.info("Disconnected successfully")

        # Log final statistics
        self._log_final_stats()

    def _log_final_stats(self):
        """Log final statistics after disconnection."""
        logger.info("=== WebRTC Session Statistics ===")
        logger.info(f"CID: {self.cid}")
        logger.info(f"Session duration: {self._format_duration(time.time() - self.started_at)}")

        if self.connected_at:
            connection_time_ms = (self.connected_at - self.started_at) * 1000
            logger.info(f"Connection time: {connection_time_ms:.2f}ms")

        if self.first_frame_at:
            first_frame_time_ms = (self.first_frame_at - self.started_at) * 1000
            logger.info(f"Time to first frame: {first_frame_time_ms:.2f}ms")

        logger.info(f"Frames received: {self.stats['frames_received']}")
        logger.info(f"Frames dropped: {self.stats['frames_dropped']}")

        if self.stats["avg_fps"]:
            logger.info(f"Average FPS: {self.stats['avg_fps']:.2f}")

        if self.stats["resolution"]:
            logger.info(f"Resolution: {self.stats['resolution']}")

        if self.stats["video_bitrate_kbps"]:
            logger.info(f"Video bitrate: {self.stats['video_bitrate_kbps']:.2f} kbps")

        if self.stats["audio_bitrate_kbps"]:
            logger.info(f"Audio bitrate: {self.stats['audio_bitrate_kbps']:.2f} kbps")

        # Log quality changes
        if self.stats["quality_changes"]:
            logger.info(f"Quality changes: {len(self.stats['quality_changes'])}")
            for i, change in enumerate(self.stats["quality_changes"]):
                logger.info(f"  {i+1}. {change['from']} -> {change['to']} "
                           f"at {self._format_duration(change['time'])} "
                           f"(score: {change['network_score']})")

    def _format_duration(self, seconds):
        """Format seconds as MM:SS.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string
        """
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_stats_report(self):
        """Get a formatted report of all statistics.

        Returns:
            Dictionary with comprehensive statistics
        """
        return {
            "session": {
                "cid": self.cid,
                "start_time": self.started_at,
                "duration_seconds": time.time() - self.started_at if self.started_at else None,
                "connection_time_ms": self.stats["connection_time_ms"],
                "first_frame_time_ms": self.stats["first_frame_time_ms"],
                "quality_changes": self.stats["quality_changes"],
                "final_quality": self.quality
            },
            "performance": {
                "frames_received": self.stats["frames_received"],
                "frames_dropped": self.stats["frames_dropped"],
                "avg_fps": self.stats["avg_fps"],
                "resolution": self.stats["resolution"],
                "video_bitrate_kbps": self.stats["video_bitrate_kbps"],
                "audio_bitrate_kbps": self.stats["audio_bitrate_kbps"]
            },
            "connection": {
                "pc_id": self.pc_id,
                "ice_state_changes": self.stats["ice_state_changes"],
                "connection_state_changes": self.stats["connection_state_changes"],
                "connection_attempts": self.stats["connection_attempts"],
                "connection_successes": self.stats["connection_successes"],
                "connection_failures": self.stats["connection_failures"]
            },
            "raw_stats": self.stats["latest_stats"]
        }


async def run_client(args):
    """Run the WebRTC client with command line arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        0 for success, 1 for failure
    """
    # Create client
    client = MCPWebRTCClient(
        server_url=args.server_url,
        cid=args.cid,
        use_websocket_url=args.websocket_url,
        display_video=args.display,
        save_video_path=args.save_video,
        quality=args.quality,
        verbose=args.verbose
    )

    try:
        # Connect to server
        if not await client.connect():
            logger.error("Failed to connect to server")
            return 1

        # Start stats collection in background
        stats_task = anyio.create_task(client.collect_stats())

        # Run for the specified duration
        if args.duration > 0:
            logger.info(f"Streaming for {args.duration} seconds...")
            try:
                await anyio.sleep(args.duration)
            except anyio.CancelledError:
                logger.info("Streaming interrupted by user")
        else:
            # Run until user interrupts with Ctrl+C
            logger.info("Streaming until interrupted (Ctrl+C to stop)...")
            try:
                # Keep running until interrupted
                while not client.interrupted:
                    await anyio.sleep(1)
            except anyio.CancelledError:
                logger.info("Streaming interrupted by user")

        # Clean up
        stats_task.cancel()
        await client.disconnect()

        # Write stats report if requested
        if args.stats_output:
            try:
                report = client.get_stats_report()
                with open(args.stats_output, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
                logger.info(f"Statistics report written to {args.stats_output}")
            except Exception as e:
                logger.error(f"Failed to write statistics report: {e}")

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except Exception as e:
        logger.error(f"Error during streaming: {e}")
        return 1

    finally:
        # Make sure client disconnects
        if hasattr(client, 'disconnect'):
            await client.disconnect()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="WebRTC client for IPFS Kit MCP server")

    parser.add_argument("--server-url", required=True,
                       help="MCP server URL (e.g., http://localhost:9999/mcp)")

    parser.add_argument("--cid", required=True,
                       help="Content ID to stream")

    parser.add_argument("--websocket-url",
                       help="WebSocket URL for signaling (derived from server-url if not specified)")

    parser.add_argument("--quality", default="medium",
                       choices=["low", "medium", "high", "auto"],
                       help="Streaming quality (default: medium)")

    parser.add_argument("--duration", type=int, default=0,
                       help="Streaming duration in seconds (0 for unlimited)")

    parser.add_argument("--display", action="store_true",
                       help="Display video using OpenCV")

    parser.add_argument("--save-video",
                       help="Path to save video (e.g., output.mp4)")

    parser.add_argument("--stats-output",
                       help="Path to save statistics report as JSON")

    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    # Print dependency status
    logger.info("=== WebRTC Client Dependency Status ===")
    logger.info(f"aiortc: {'Available' if HAVE_AIORTC else 'Not Available'}")
    logger.info(f"websockets: {'Available' if HAVE_WEBSOCKETS else 'Not Available'}")
    logger.info(f"OpenCV: {'Available' if HAVE_OPENCV else 'Not Available'}")

    # Run client
    exit_code = await run_client(args)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(anyio.run(main()))
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
