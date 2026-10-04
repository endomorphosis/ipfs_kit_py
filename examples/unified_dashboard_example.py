#!/usr/bin/env python3
"""
Unified Dashboard Example for IPFS Kit.

This example demonstrates a unified dashboard that combines:
1. WebRTC video streaming directly from IPFS content
2. Real-time WebSocket notifications for various system events
3. System status monitoring and visualization

This provides a comprehensive real-time view into the IPFS Kit system,
showing both content streaming and system events in one interface.

Usage:
    python unified_dashboard_example.py [--api-url API_URL] [--cid CID]

Requirements:
    - ipfs_kit_py[webrtc,ui] - Install with optional dependencies
    - A running IPFS Kit server with WebSocket notification and WebRTC support
"""

import argparse
import anyio
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Any

# Try to import UI dependencies
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    from PIL import Image, ImageTk
    import cv2
    import numpy as np
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAVE_UI = True
except ImportError:
    HAVE_UI = False

# Try to import WebRTC dependencies
try:
    import aiohttp
    import aiortc
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer, MediaRecorder
    import av
    from av.frame import Frame
    HAVE_WEBRTC = True
except ImportError:
    HAVE_WEBRTC = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("unified_dashboard")

# Notification type colors for UI
NOTIFICATION_COLORS = {
    "webrtc_connection_created": "#E1F5FE",      # Light blue
    "webrtc_connection_established": "#E8F5E9",  # Light green
    "webrtc_connection_closed": "#FFF3E0",       # Light orange
    "webrtc_stream_started": "#DCEDC8",          # Light green-yellow
    "webrtc_stream_ended": "#FFEBEE",            # Light red
    "webrtc_quality_changed": "#F3E5F5",         # Light purple
    "webrtc_error": "#FFCDD2",                   # Light red
    "content_added": "#E0F7FA",                  # Light cyan
    "content_retrieved": "#F1F8E9",              # Light green
    "peer_connected": "#E8EAF6",                 # Light indigo
    "peer_disconnected": "#FBE9E7",              # Light deep orange
    "system_metrics": "#E0F2F1",                 # Light teal
    "system_warning": "#FFF8E1",                 # Light amber
    "system_error": "#FFEBEE",                   # Light red
    "system_info": "#E8F5E9",                    # Light green
}

# Default fallback color
DEFAULT_COLOR = "#F5F5F5"  # Light grey


@dataclass
class WebRTCConnection:
    """Represents a WebRTC connection for streaming IPFS content."""
    pc_id: str
    peer_connection: RTCPeerConnection
    cid: Optional[str] = None
    kind: str = "video"
    state: str = "new"
    created_at: float = 0.0
    ice_candidates: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.ice_candidates is None:
            self.ice_candidates = []
        self.created_at = time.time()


class NotificationClient:
    """Client for WebSocket notifications from IPFS Kit."""
    
    def __init__(self, api_url="http://localhost:8000", on_notification=None):
        """
        Initialize notification client.
        
        Args:
            api_url: Base URL for the IPFS Kit API
            on_notification: Callback function for notifications
        """
        self.api_url = api_url.rstrip("/")
        self.ws_url = self.api_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{self.ws_url}/ws/notifications"
        self.ws = None
        self.session = None
        self.connected = False
        self.subscriptions = set()
        self.on_notification = on_notification
        self.stats = {
            "notifications_received": 0,
            "notifications_by_type": {},
            "connection_established": None,
            "last_activity": None
        }
    
    async def connect(self):
        """Connect to the notification WebSocket endpoint."""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.ws_url)
            self.connected = True
            self.stats["connection_established"] = time.time()
            logger.info(f"Connected to notification endpoint: {self.ws_url}")
            
            # Start listening for messages
            anyio.create_task(self._listen())
            return True
        except Exception as e:
            logger.error(f"Failed to connect to notification endpoint: {e}")
            return False
    
    async def _listen(self):
        """Listen for incoming notification messages."""
        if not self.ws:
            return
        
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        self._handle_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket connection closed")
                    self.connected = False
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket connection error: {self.ws.exception()}")
                    self.connected = False
                    break
        except Exception as e:
            logger.error(f"Error in notification listener: {e}")
            self.connected = False
        finally:
            if self.ws and not self.ws.closed:
                await self.ws.close()
            self.connected = False
    
    def _handle_message(self, data):
        """
        Handle incoming WebSocket messages.
        
        Args:
            data: Parsed JSON message
        """
        msg_type = data.get("type")
        self.stats["last_activity"] = time.time()
        
        if msg_type == "welcome":
            # Handle welcome message
            logger.info(f"Received welcome message: {data.get('message')}")
            # Subscribe to all notification types
            anyio.create_task(self.subscribe(["all_events"]))
            
        elif msg_type == "notification":
            # Handle notification
            notification_type = data.get("notification_type")
            
            # Update stats
            self.stats["notifications_received"] += 1
            self.stats["notifications_by_type"].setdefault(notification_type, 0)
            self.stats["notifications_by_type"][notification_type] += 1
            
            # Call notification handler if set
            if self.on_notification:
                self.on_notification(data)
                
            logger.debug(f"Received notification: {notification_type}")
            
        elif msg_type in ["subscription_confirmed", "unsubscription_confirmed"]:
            # Handle subscription changes
            subs = data.get("notification_types", [])
            logger.info(f"Subscription updated: {subs}")
            self.subscriptions = set(subs)
            
        elif msg_type == "pong":
            # Handle pong response
            pass
            
        elif msg_type == "error":
            # Handle error message
            logger.error(f"Notification error: {data.get('message')}")
    
    async def subscribe(self, notification_types):
        """
        Subscribe to specific notification types.
        
        Args:
            notification_types: List of notification types to subscribe to
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to notification server")
            return False
        
        try:
            await self.ws.send_json({
                "action": "subscribe",
                "notification_types": notification_types
            })
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to notifications: {e}")
            return False
    
    async def unsubscribe(self, notification_types):
        """
        Unsubscribe from specific notification types.
        
        Args:
            notification_types: List of notification types to unsubscribe from
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to notification server")
            return False
        
        try:
            await self.ws.send_json({
                "action": "unsubscribe",
                "notification_types": notification_types
            })
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe from notifications: {e}")
            return False
    
    async def get_history(self, limit=50, notification_type=None):
        """
        Get notification history.
        
        Args:
            limit: Maximum number of history items to retrieve
            notification_type: Optional type to filter history
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to notification server")
            return []
        
        try:
            message = {
                "action": "get_history",
                "limit": limit
            }
            if notification_type:
                message["notification_type"] = notification_type
                
            await self.ws.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to get notification history: {e}")
            return False
    
    async def ping(self):
        """Send a ping to keep the connection alive."""
        if not self.connected or not self.ws:
            logger.warning("Not connected to notification server")
            return False
        
        try:
            await self.ws.send_json({"action": "ping"})
            return True
        except Exception as e:
            logger.error(f"Failed to send ping: {e}")
            return False
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.ws and not self.ws.closed:
            await self.ws.close()
        
        if self.session:
            await self.session.close()
            
        self.connected = False
        logger.info("Notification client disconnected")


class WebRTCClient:
    """Client for WebRTC streaming from IPFS content."""
    
    def __init__(self, api_url="http://localhost:8000", on_frame=None, on_connection_change=None):
        """
        Initialize WebRTC client.
        
        Args:
            api_url: Base URL for the IPFS Kit API
            on_frame: Callback function for received video frames
            on_connection_change: Callback function for connection state changes
        """
        if not HAVE_WEBRTC:
            raise ImportError("WebRTC dependencies not available")
            
        self.api_url = api_url.rstrip("/")
        self.ws_url = self.api_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_url = f"{self.ws_url}/ws/webrtc"
        
        self.ws = None
        self.session = None
        self.connected = False
        self.client_id = None
        
        self.connections = {}  # pc_id -> WebRTCConnection
        self.on_frame = on_frame
        self.on_connection_change = on_connection_change
        
        # Set up frame processing
        self.frame_processor = FrameProcessor(on_frame=self.on_frame)
    
    async def connect(self):
        """Connect to the WebRTC signaling endpoint."""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.ws_url)
            self.connected = True
            logger.info(f"Connected to WebRTC signaling endpoint: {self.ws_url}")
            
            # Start listening for messages
            anyio.create_task(self._listen())
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebRTC signaling endpoint: {e}")
            return False
    
    async def _listen(self):
        """Listen for incoming WebRTC signaling messages."""
        if not self.ws:
            return
        
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._handle_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebRTC signaling connection closed")
                    self.connected = False
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebRTC signaling connection error: {self.ws.exception()}")
                    self.connected = False
                    break
        except Exception as e:
            logger.error(f"Error in WebRTC signaling listener: {e}")
            self.connected = False
        finally:
            # Close all peer connections
            await self.close_all_connections()
            
            if self.ws and not self.ws.closed:
                await self.ws.close()
            self.connected = False
    
    async def _handle_message(self, data):
        """
        Handle incoming WebRTC signaling messages.
        
        Args:
            data: Parsed JSON message
        """
        msg_type = data.get("type")
        
        if msg_type == "welcome":
            # Handle welcome message
            self.client_id = data.get("client_id")
            logger.info(f"Received welcome message from WebRTC server, client ID: {self.client_id}")
            
        elif msg_type == "offer":
            # Handle offer from server
            pc_id = data.get("pc_id")
            sdp = data.get("sdp")
            sdp_type = data.get("sdpType")
            
            if pc_id in self.connections:
                # Set remote description on the peer connection
                pc = self.connections[pc_id].peer_connection
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=sdp, type=sdp_type)
                )
                
                # Create and send answer
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                
                await self.ws.send_json({
                    "type": "answer",
                    "pc_id": pc_id,
                    "sdp": pc.localDescription.sdp,
                    "sdpType": pc.localDescription.type
                })
                
                logger.info(f"Sent answer for connection: {pc_id}")
            else:
                logger.warning(f"Received offer for unknown connection: {pc_id}")
        
        elif msg_type == "track_offer":
            # Handle track offer from server (for existing connection)
            pc_id = data.get("pc_id")
            sdp = data.get("sdp")
            sdp_type = data.get("sdpType")
            
            if pc_id in self.connections:
                # Update remote description on the peer connection
                pc = self.connections[pc_id].peer_connection
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=sdp, type=sdp_type)
                )
                
                # Create and send answer
                answer = await pc.createAnswer()
                await pc.setLocalDescription(answer)
                
                await self.ws.send_json({
                    "type": "answer",
                    "pc_id": pc_id,
                    "sdp": pc.localDescription.sdp,
                    "sdpType": pc.localDescription.type
                })
                
                logger.info(f"Sent answer for track offer on connection: {pc_id}")
            else:
                logger.warning(f"Received track offer for unknown connection: {pc_id}")
        
        elif msg_type == "connected":
            # Connection established successfully
            pc_id = data.get("pc_id")
            if pc_id in self.connections:
                conn = self.connections[pc_id]
                conn.state = "connected"
                logger.info(f"WebRTC connection established: {pc_id}")
                
                # Notify about connection change
                if self.on_connection_change:
                    self.on_connection_change(pc_id, "connected", conn)
            
        elif msg_type == "error":
            # Handle error message
            logger.error(f"WebRTC signaling error: {data.get('message')}")
            
        elif msg_type == "closed":
            # Handle connection closed
            pc_id = data.get("pc_id")
            if pc_id in self.connections:
                await self._close_connection(pc_id)
                
        elif msg_type == "closed_all":
            # All connections closed by server
            await self.close_all_connections()
            
        elif msg_type == "stats":
            # Handle stats response
            logger.debug(f"Received WebRTC stats: {data.get('stats')}")
            
        elif msg_type == "pong":
            # Handle pong response
            pass
    
    async def request_stream(self, cid, kind="video", frame_rate=30):
        """
        Request a stream from an IPFS content.
        
        Args:
            cid: Content identifier for the media in IPFS
            kind: Track kind ("video" or "audio")
            frame_rate: Target frame rate for video tracks
            
        Returns:
            str: Peer connection ID if successful, None otherwise
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to WebRTC signaling server")
            return None
        
        try:
            # Create a new RTCPeerConnection
            pc = RTCPeerConnection()
            
            # Set up event handlers
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track received: {track.kind}")
                
                if track.kind == "video":
                    self.frame_processor.add_track(track)
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state changed: {pc.connectionState}")
                
                if pc_id in self.connections:
                    conn = self.connections[pc_id]
                    conn.state = pc.connectionState
                    
                    # Notify about connection change
                    if self.on_connection_change:
                        self.on_connection_change(pc_id, pc.connectionState, conn)
                    
                    if pc.connectionState == "failed" or pc.connectionState == "closed":
                        await self._close_connection(pc_id)
            
            # Create a temporary connection ID for local tracking
            pc_id = f"temp_{time.time()}"
            
            # Add connection to our dictionary
            self.connections[pc_id] = WebRTCConnection(
                pc_id=pc_id,
                peer_connection=pc,
                cid=cid,
                kind=kind
            )
            
            # Send offer request
            await self.ws.send_json({
                "type": "offer_request",
                "cid": cid,
                "kind": kind,
                "frameRate": frame_rate
            })
            
            logger.info(f"Sent stream request for CID: {cid}")
            return pc_id
            
        except Exception as e:
            logger.error(f"Failed to request stream: {e}")
            return None
    
    async def add_ice_candidate(self, pc_id, candidate, sdp_mid, sdp_mline_index):
        """
        Add an ICE candidate to a peer connection.
        
        Args:
            pc_id: Peer connection ID
            candidate: ICE candidate string
            sdp_mid: Media stream identifier
            sdp_mline_index: Media line index
        """
        if pc_id not in self.connections:
            logger.warning(f"Cannot add ICE candidate: unknown connection {pc_id}")
            return False
        
        conn = self.connections[pc_id]
        pc = conn.peer_connection
        
        try:
            await pc.addIceCandidate({
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index
            })
            
            # Store candidate for reference
            conn.ice_candidates.append({
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index
            })
            
            return True
        except Exception as e:
            logger.error(f"Failed to add ICE candidate: {e}")
            return False
    
    async def get_stats(self, pc_id=None):
        """
        Get statistics for WebRTC connections.
        
        Args:
            pc_id: Optional peer connection ID to get stats for a specific connection
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to WebRTC signaling server")
            return None
        
        try:
            message = {"type": "get_stats"}
            if pc_id:
                message["pc_id"] = pc_id
                
            await self.ws.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to get WebRTC stats: {e}")
            return False
    
    async def _close_connection(self, pc_id):
        """
        Close a specific WebRTC connection.
        
        Args:
            pc_id: Peer connection ID
        """
        if pc_id not in self.connections:
            return
        
        conn = self.connections[pc_id]
        pc = conn.peer_connection
        
        try:
            # Stop all tracks
            for transceiver in pc.getTransceivers():
                if transceiver.receiver and transceiver.receiver.track:
                    transceiver.receiver.track.stop()
            
            # Close the peer connection
            await pc.close()
            
            # Remove from our dictionary
            del self.connections[pc_id]
            
            # Notify about connection change
            if self.on_connection_change:
                self.on_connection_change(pc_id, "closed", conn)
                
            logger.info(f"Closed WebRTC connection: {pc_id}")
            
        except Exception as e:
            logger.error(f"Error closing WebRTC connection {pc_id}: {e}")
    
    async def close_connection(self, pc_id):
        """
        Close a WebRTC connection and notify the server.
        
        Args:
            pc_id: Peer connection ID
        """
        if not self.connected or not self.ws:
            logger.warning("Not connected to WebRTC signaling server")
            return False
        
        try:
            # Send close message to server
            await self.ws.send_json({
                "type": "close",
                "pc_id": pc_id
            })
            
            # Close the connection locally
            await self._close_connection(pc_id)
            return True
        except Exception as e:
            logger.error(f"Failed to close WebRTC connection: {e}")
            return False
    
    async def close_all_connections(self):
        """Close all active WebRTC connections."""
        if not self.connected or not self.ws:
            # Close local connections anyway
            for pc_id in list(self.connections.keys()):
                await self._close_connection(pc_id)
            return
        
        try:
            # Send close all message to server
            await self.ws.send_json({
                "type": "close"  # No pc_id means close all
            })
            
            # Close all connections locally
            for pc_id in list(self.connections.keys()):
                await self._close_connection(pc_id)
                
        except Exception as e:
            logger.error(f"Failed to close all WebRTC connections: {e}")
            
            # Still try to close locally
            for pc_id in list(self.connections.keys()):
                await self._close_connection(pc_id)
    
    async def close(self):
        """Close the WebRTC client and all connections."""
        # Close all connections
        await self.close_all_connections()
        
        # Close the WebSocket connection
        if self.ws and not self.ws.closed:
            await self.ws.close()
        
        # Close the session
        if self.session:
            await self.session.close()
            
        self.connected = False
        logger.info("WebRTC client disconnected")
        
        # Stop frame processor
        self.frame_processor.stop()


class FrameProcessor:
    """Process video frames from WebRTC tracks."""
    
    def __init__(self, on_frame=None):
        """
        Initialize frame processor.
        
        Args:
            on_frame: Callback function for processed frames
        """
        self.on_frame = on_frame
        self.tracks = set()
        self.running = True
        self.frame_count = 0
        self.last_frames = {}  # track -> last frame
        
        # Start processing loop in a separate task
        self.task = anyio.create_task(self._process_frames())
    
    def add_track(self, track):
        """
        Add a track to process frames from.
        
        Args:
            track: MediaStreamTrack to process
        """
        self.tracks.add(track)
        logger.info(f"Added track to frame processor: {track.kind}")
    
    def remove_track(self, track):
        """
        Remove a track from processing.
        
        Args:
            track: MediaStreamTrack to remove
        """
        if track in self.tracks:
            self.tracks.remove(track)
            if track in self.last_frames:
                del self.last_frames[track]
            logger.info(f"Removed track from frame processor: {track.kind}")
    
    async def _process_frames(self):
        """Process frames from all tracks in a loop."""
        try:
            while self.running:
                if not self.tracks:
                    # No tracks to process, wait a bit
                    await anyio.sleep(0.1)
                    continue
                
                # Process frames from all tracks
                for track in list(self.tracks):
                    try:
                        frame = await track.recv()
                        self.last_frames[track] = frame
                        
                        # Convert to RGB for display if it's a video frame
                        if hasattr(frame, 'to_rgb') and self.on_frame:
                            # Convert to RGB numpy array
                            img = frame.to_rgb().to_ndarray()
                            
                            # Call frame handler
                            self.on_frame(img, track)
                            
                            self.frame_count += 1
                            
                    except Exception as e:
                        # Remove track if there was an error (might be ended)
                        logger.error(f"Error processing frame from track: {e}")
                        self.tracks.remove(track)
                        if track in self.last_frames:
                            del self.last_frames[track]
                
                # Give other tasks a chance to run
                await anyio.sleep(0.001)
                
        except anyio.CancelledError:
            logger.info("Frame processor task cancelled")
        except Exception as e:
            logger.error(f"Error in frame processor: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """Stop the frame processor."""
        self.running = False
        if hasattr(self, "task") and self.task:
            self.task.cancel()
        self.tracks.clear()
        self.last_frames.clear()


class UnifiedDashboard:
    """Unified dashboard for WebRTC streaming and WebSocket notifications."""
    
    def __init__(self, api_url="http://localhost:8000", cid=None):
        """
        Initialize unified dashboard.
        
        Args:
            api_url: Base URL for the IPFS Kit API
            cid: Optional CID to stream immediately
        """
        if not HAVE_UI:
            raise ImportError("UI dependencies not available")
            
        self.api_url = api_url
        self.initial_cid = cid
        self.root = None
        self.frame = None
        self.notification_client = None
        self.webrtc_client = None
        self.notifications = []
        self.max_notifications = 100
        self.current_connection = None
        self.webrtc_task = None
        self.notification_task = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Frame update lock
        self.frame_lock = anyio.Lock()
        
        # Initialize UI
        self._init_ui()
        
        # Set up event loop
        self.loop = anyio.new_event_loop()
        anyio.set_event_loop(self.loop)
        
        # Start clients
        self.loop.run_until_complete(self._start_clients())
        
        # Stream initial CID if provided
        if self.initial_cid:
            self.loop.run_until_complete(self._stream_cid(self.initial_cid))
        
        # Start background tasks
        self._schedule_tasks()
    
    def _init_ui(self):
        """Initialize the UI components."""
        self.root = tk.Tk()
        self.root.title("IPFS Kit Unified Dashboard")
        self.root.geometry("1280x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Create main frame
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left and right panels
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Left panel - Video stream
        video_frame = ttk.LabelFrame(left_panel, text="IPFS Content Stream")
        video_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video canvas
        self.video_canvas = tk.Canvas(video_frame, bg="black", width=640, height=480)
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Video controls
        controls_frame = ttk.Frame(video_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(controls_frame, text="CID:").pack(side=tk.LEFT, padx=5)
        self.cid_entry = ttk.Entry(controls_frame, width=50)
        self.cid_entry.pack(side=tk.LEFT, padx=5)
        if self.initial_cid:
            self.cid_entry.insert(0, self.initial_cid)
        
        self.stream_button = ttk.Button(controls_frame, text="Stream", command=self._on_stream_button)
        self.stream_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self._on_stop_button, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Video status
        status_frame = ttk.Frame(video_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, text="Not connected")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Right panel - Notifications
        notebook = ttk.Notebook(right_panel)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Notifications tab
        notifications_frame = ttk.Frame(notebook)
        notebook.add(notifications_frame, text="Notifications")
        
        # Notifications list
        self.notification_list = tk.Listbox(notifications_frame, height=20, width=80)
        self.notification_list.pack(fill=tk.BOTH, expand=True, pady=5)
        self.notification_list.bind("<<ListboxSelect>>", self._on_notification_select)
        
        # Notification details
        details_frame = ttk.LabelFrame(notifications_frame, text="Notification Details")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.notification_details = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD, height=10)
        self.notification_details.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Stats tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        
        # Create stats widgets
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=stats_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Connection stats frame
        conn_stats_frame = ttk.LabelFrame(stats_frame, text="Connection Statistics")
        conn_stats_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.conn_stats_text = scrolledtext.ScrolledText(conn_stats_frame, wrap=tk.WORD, height=8)
        self.conn_stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        
        ttk.Label(status_bar, text="API:").pack(side=tk.LEFT, padx=5)
        self.api_label = ttk.Label(status_bar, text=self.api_url)
        self.api_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(status_bar, text="WebRTC:").pack(side=tk.LEFT, padx=15)
        self.webrtc_status = ttk.Label(status_bar, text="Disconnected")
        self.webrtc_status.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(status_bar, text="Notifications:").pack(side=tk.LEFT, padx=15)
        self.notification_status = ttk.Label(status_bar, text="Disconnected")
        self.notification_status.pack(side=tk.LEFT, padx=5)
    
    async def _start_clients(self):
        """Start WebRTC and notification clients."""
        # Create notification client
        self.notification_client = NotificationClient(
            api_url=self.api_url,
            on_notification=self._handle_notification
        )
        
        # Create WebRTC client
        if HAVE_WEBRTC:
            self.webrtc_client = WebRTCClient(
                api_url=self.api_url,
                on_frame=self._handle_frame,
                on_connection_change=self._handle_connection_change
            )
        
        # Connect notification client
        notification_connected = await self.notification_client.connect()
        if notification_connected:
            self.root.after(0, lambda: self.notification_status.config(text="Connected"))
        
        # Connect WebRTC client if available
        if HAVE_WEBRTC:
            webrtc_connected = await self.webrtc_client.connect()
            if webrtc_connected:
                self.root.after(0, lambda: self.webrtc_status.config(text="Connected"))
    
    def _schedule_tasks(self):
        """Schedule periodic tasks."""
        # Update UI task
        def update_ui():
            if self.root.winfo_exists():
                self._update_stats()
                self.root.after(1000, update_ui)
        
        # Schedule update task
        update_ui()
        
        # Schedule ping task to keep connections alive
        async def ping_task():
            while True:
                try:
                    if self.notification_client and self.notification_client.connected:
                        await self.notification_client.ping()
                    
                    await anyio.sleep(30)
                except anyio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in ping task: {e}")
                    await anyio.sleep(5)
        
        # Start ping task
        self.notification_task = self.loop.create_task(ping_task())
        
        # Start event loop in a thread
        def run_event_loop():
            anyio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                logger.error(f"Error in event loop: {e}")
            finally:
                logger.info("Event loop stopped")
        
        self.executor.submit(run_event_loop)
    
    def _on_stream_button(self):
        """Handle stream button click."""
        cid = self.cid_entry.get().strip()
        if not cid:
            self._update_status("Please enter a valid CID")
            return
        
        # Submit task to event loop
        anyio.run_coroutine_threadsafe(self._stream_cid(cid), self.loop)
    
    async def _stream_cid(self, cid):
        """
        Stream content from a CID.
        
        Args:
            cid: Content identifier for the media in IPFS
        """
        if not HAVE_WEBRTC or not self.webrtc_client or not self.webrtc_client.connected:
            self._update_status("WebRTC client not available or not connected")
            return
        
        try:
            # Request stream from server
            pc_id = await self.webrtc_client.request_stream(cid)
            if pc_id:
                self.current_connection = pc_id
                self._update_status(f"Streaming CID: {cid}")
                
                # Update UI
                self.root.after(0, lambda: self.stream_button.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.stop_button.config(state=tk.NORMAL))
            else:
                self._update_status(f"Failed to start stream for CID: {cid}")
        except Exception as e:
            self._update_status(f"Error: {str(e)}")
    
    def _on_stop_button(self):
        """Handle stop button click."""
        if self.current_connection:
            # Submit task to event loop
            anyio.run_coroutine_threadsafe(self._stop_stream(), self.loop)
    
    async def _stop_stream(self):
        """Stop the current stream."""
        if self.current_connection and self.webrtc_client:
            await self.webrtc_client.close_connection(self.current_connection)
            self.current_connection = None
            
            # Update UI
            self._update_status("Stream stopped")
            self.root.after(0, lambda: self.stream_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            
            # Clear video display
            self.root.after(0, lambda: self.video_canvas.delete("all"))
    
    def _handle_frame(self, img_array, track):
        """
        Handle received video frame.
        
        Args:
            img_array: NumPy array with RGB image data
            track: Source track
        """
        # Convert to PIL Image
        try:
            img = Image.fromarray(img_array)
            
            # Resize to fit canvas if needed
            canvas_width = self.video_canvas.winfo_width()
            canvas_height = self.video_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                img = img.resize((canvas_width, canvas_height), Image.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image=img)
            
            # Update canvas in main thread
            self.root.after(0, lambda: self._update_canvas(photo))
            
        except Exception as e:
            logger.error(f"Error handling frame: {e}")
    
    def _update_canvas(self, photo):
        """
        Update video canvas with new frame.
        
        Args:
            photo: PhotoImage to display
        """
        if not self.root.winfo_exists():
            return
            
        # Store reference to prevent garbage collection
        self.frame = photo
        
        # Clear canvas and add image
        self.video_canvas.delete("all")
        self.video_canvas.create_image(
            self.video_canvas.winfo_width() // 2,
            self.video_canvas.winfo_height() // 2,
            image=self.frame
        )
    
    def _handle_connection_change(self, pc_id, state, connection):
        """
        Handle WebRTC connection state change.
        
        Args:
            pc_id: Peer connection ID
            state: New connection state
            connection: WebRTCConnection object
        """
        if pc_id == self.current_connection:
            self._update_status(f"Connection state: {state}")
            
            if state in ["failed", "closed"]:
                self.current_connection = None
                self.root.after(0, lambda: self.stream_button.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
    
    def _handle_notification(self, notification):
        """
        Handle incoming notification.
        
        Args:
            notification: Notification data
        """
        # Add to notifications list
        self.notifications.append(notification)
        
        # Limit the number of stored notifications
        if len(self.notifications) > self.max_notifications:
            self.notifications = self.notifications[-self.max_notifications:]
        
        # Update UI in main thread
        self.root.after(0, self._update_notification_list)
    
    def _update_notification_list(self):
        """Update the notification list in the UI."""
        if not self.root.winfo_exists():
            return
            
        self.notification_list.delete(0, tk.END)
        
        for i, notification in enumerate(reversed(self.notifications)):
            notif_type = notification.get("notification_type", "unknown")
            timestamp = notification.get("timestamp", 0)
            time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
            
            # Notification summary for display
            display_text = f"{time_str} - {notif_type}"
            
            # Add to list with color based on type
            self.notification_list.insert(tk.END, display_text)
            
            # Set background color based on notification type
            bg_color = NOTIFICATION_COLORS.get(notif_type, DEFAULT_COLOR)
            self.notification_list.itemconfig(i, {'bg': bg_color})
    
    def _on_notification_select(self, event):
        """Handle notification selection in listbox."""
        selection = self.notification_list.curselection()
        if not selection:
            return
        
        # Get selected notification (reversed order in display)
        index = len(self.notifications) - 1 - selection[0]
        if 0 <= index < len(self.notifications):
            notification = self.notifications[index]
            
            # Format JSON for display
            json_str = json.dumps(notification, indent=2)
            
            # Update details text
            self.notification_details.delete(1.0, tk.END)
            self.notification_details.insert(tk.END, json_str)
    
    def _update_status(self, status):
        """Update status label."""
        self.root.after(0, lambda: self.status_label.config(text=status))
    
    def _update_stats(self):
        """Update statistics display."""
        if not self.root.winfo_exists():
            return
            
        try:
            # Get notification stats
            notification_stats = None
            if self.notification_client:
                notification_stats = self.notification_client.stats
            
            # Update chart
            self._update_chart(notification_stats)
            
            # Update connection stats
            self._update_connection_stats()
            
        except Exception as e:
            logger.error(f"Error updating stats: {e}")
    
    def _update_chart(self, notification_stats):
        """Update statistics chart."""
        if not notification_stats:
            return
            
        # Clear figure
        self.ax.clear()
        
        # Get notification counts by type
        notif_types = notification_stats.get("notifications_by_type", {})
        
        if notif_types:
            # Sort by count
            sorted_types = sorted(
                notif_types.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Extract labels and values
            labels = [t[0] for t in sorted_types]
            values = [t[1] for t in sorted_types]
            
            # Plot bar chart
            bars = self.ax.bar(labels, values)
            
            # Add counts on top of bars
            for bar in bars:
                height = bar.get_height()
                self.ax.text(
                    bar.get_x() + bar.get_width()/2.,
                    height + 0.1,
                    str(int(height)),
                    ha='center', va='bottom', rotation=0
                )
            
            # Customize chart
            self.ax.set_title('Notifications by Type')
            self.ax.set_xlabel('Notification Type')
            self.ax.set_ylabel('Count')
            
            # Rotate labels for better readability
            self.ax.set_xticklabels(labels, rotation=45, ha='right')
            
            # Adjust layout
            self.fig.tight_layout()
            
            # Redraw
            self.canvas.draw()
    
    def _update_connection_stats(self):
        """Update connection statistics text."""
        stats_text = ""
        
        # Add WebRTC connection stats
        if self.webrtc_client and self.current_connection:
            conn = self.webrtc_client.connections.get(self.current_connection)
            if conn:
                stats_text += f"WebRTC Connection: {self.current_connection}\n"
                stats_text += f"State: {conn.state}\n"
                stats_text += f"CID: {conn.cid}\n"
                stats_text += f"Kind: {conn.kind}\n"
                stats_text += f"Duration: {time.time() - conn.created_at:.1f} seconds\n"
                stats_text += f"ICE Candidates: {len(conn.ice_candidates)}\n"
        
        # Add notification stats
        if self.notification_client:
            stats = self.notification_client.stats
            stats_text += "\nNotification Statistics:\n"
            stats_text += f"Total Notifications: {stats.get('notifications_received', 0)}\n"
            
            if stats.get('connection_established'):
                duration = time.time() - stats['connection_established']
                stats_text += f"Connection Duration: {duration:.1f} seconds\n"
            
            stats_text += f"Subscriptions: {', '.join(self.notification_client.subscriptions)}\n"
        
        # Update text widget
        self.conn_stats_text.delete(1.0, tk.END)
        self.conn_stats_text.insert(tk.END, stats_text)
    
    def _on_close(self):
        """Handle window close event."""
        logger.info("Closing dashboard")
        
        # Stop tasks
        if hasattr(self, "notification_task") and self.notification_task:
            self.notification_task.cancel()
        
        if hasattr(self, "webrtc_task") and self.webrtc_task:
            self.webrtc_task.cancel()
        
        # Schedule cleanup in event loop
        anyio.run_coroutine_threadsafe(self._cleanup(), self.loop)
        
        # Stop event loop after a short delay
        self.loop.call_later(1, self._stop_loop)
        
        # Destroy window
        self.root.destroy()
    
    async def _cleanup(self):
        """Clean up resources before closing."""
        # Close WebRTC client
        if self.webrtc_client:
            await self.webrtc_client.close()
        
        # Close notification client
        if self.notification_client:
            await self.notification_client.close()
    
    def _stop_loop(self):
        """Stop the event loop."""
        self.loop.stop()
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
    
    def run(self):
        """Run the dashboard."""
        try:
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            logger.info("Dashboard closed")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="IPFS Kit Unified Dashboard")
    parser.add_argument(
        "--api-url", 
        default="http://localhost:8000", 
        help="IPFS Kit API URL"
    )
    parser.add_argument(
        "--cid", 
        help="Initial CID to stream"
    )
    args = parser.parse_args()
    
    if not HAVE_UI:
        print("UI dependencies not available. Please install them with:")
        print("pip install ipfs_kit_py[ui]")
        return
    
    try:
        # Run dashboard
        dashboard = UnifiedDashboard(api_url=args.api_url, cid=args.cid)
        dashboard.run()
    except Exception as e:
        logger.error(f"Error running dashboard: {e}")


if __name__ == "__main__":
    main()
