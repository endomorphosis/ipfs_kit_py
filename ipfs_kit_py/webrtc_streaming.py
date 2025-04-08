"""WebRTC streaming functionality for IPFS content.

This module provides WebRTC streaming capabilities for IPFS content,
enabling real-time media streaming from IPFS to browsers or other clients.

The module includes functionality for:
- Establishing WebRTC connections with clients
- Streaming IPFS content over WebRTC
- Managing media tracks
- Handling signaling protocols
- Dynamic bitrate adaptation

This implementation properly handles optional dependencies to ensure the 
module can be imported even if WebRTC dependencies are not installed.
"""

import os
import sys
import json
import time
import uuid
import logging
import asyncio
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext

# Setup basic logging
logger = logging.getLogger(__name__)

# Check for force environment variables
FORCE_WEBRTC = os.environ.get("IPFS_KIT_FORCE_WEBRTC", "0") == "1"
FORCE_WEBRTC_TESTS = os.environ.get("FORCE_WEBRTC_TESTS", "0") == "1"
RUN_ALL_TESTS = os.environ.get("IPFS_KIT_RUN_ALL_TESTS", "0") == "1"

# Set default flags
HAVE_NUMPY = False
HAVE_CV2 = False
HAVE_AV = False
HAVE_AIORTC = False
HAVE_WEBRTC = False  # Overall flag set if all dependencies are available
HAVE_NOTIFICATIONS = False
HAVE_WEBSOCKETS = False

# Handle forced testing mode
if FORCE_WEBRTC or FORCE_WEBRTC_TESTS or RUN_ALL_TESTS:
    logger.info("WebRTC dependencies being forced available for testing")
    # Force all dependency flags to True
    HAVE_NUMPY = True
    HAVE_CV2 = True
    HAVE_AV = True
    HAVE_AIORTC = True
    HAVE_WEBRTC = True
    HAVE_NOTIFICATIONS = True
    HAVE_WEBSOCKETS = True
    
    # Create mock classes if we're in testing mode
    class MockMediaStreamTrack:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockVideoStreamTrack(MockMediaStreamTrack):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
    
    class MockAudioStreamTrack(MockMediaStreamTrack):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
    
    class MockRTCPeerConnection:
        def __init__(self, *args, **kwargs):
            pass
            
    # Create module-level mock objects for imports
    if not 'numpy' in sys.modules:
        sys.modules['numpy'] = type('MockNumpy', (), {'array': lambda x: x})
        sys.modules['numpy'].np = sys.modules['numpy']
    
    if not 'cv2' in sys.modules:
        sys.modules['cv2'] = type('MockCV2', (), {})
    
    if not 'av' in sys.modules:
        sys.modules['av'] = type('MockAV', (), {})
    
    if not 'aiortc' in sys.modules:
        sys.modules['aiortc'] = type('MockAiortc', (), {
            'RTCPeerConnection': MockRTCPeerConnection,
            'RTCSessionDescription': type('MockRTCSessionDescription', (), {}),
            'RTCConfiguration': type('MockRTCConfiguration', (), {}),
            'RTCIceServer': type('MockRTCIceServer', (), {}),
            'mediastreams': type('MockMediastreams', (), {
                'MediaStreamTrack': MockMediaStreamTrack,
                'VideoStreamTrack': MockVideoStreamTrack,
                'AudioStreamTrack': MockAudioStreamTrack
            }),
            'rtcrtpsender': type('MockRTCRTPSender', (), {
                'RTCRtpSender': type('MockRTCRtpSender', (), {})
            }),
            'contrib': type('MockContrib', (), {
                'media': type('MockMedia', (), {
                    'MediaPlayer': type('MockMediaPlayer', (), {}),
                    'MediaRelay': type('MockMediaRelay', (), {}),
                    'MediaRecorder': type('MockMediaRecorder', (), {})
                })
            })
        })
        
        # Add the module attributes to the current module
        RTCPeerConnection = MockRTCPeerConnection
        RTCSessionDescription = sys.modules['aiortc'].RTCSessionDescription
        RTCConfiguration = sys.modules['aiortc'].RTCConfiguration
        RTCIceServer = sys.modules['aiortc'].RTCIceServer
        MediaStreamTrack = MockMediaStreamTrack
        VideoStreamTrack = MockVideoStreamTrack
        AudioStreamTrack = MockAudioStreamTrack
        RTCRtpSender = sys.modules['aiortc'].rtcrtpsender.RTCRtpSender
        MediaPlayer = sys.modules['aiortc'].contrib.media.MediaPlayer
        MediaRelay = sys.modules['aiortc'].contrib.media.MediaRelay
        MediaRecorder = sys.modules['aiortc'].contrib.media.MediaRecorder
    
    if not 'websockets' in sys.modules:
        sys.modules['websockets'] = type('MockWebsockets', (), {
            'exceptions': type('MockExceptions', (), {
                'ConnectionClosed': type('MockConnectionClosed', (), {})
            })
        })
        ConnectionClosed = sys.modules['websockets'].exceptions.ConnectionClosed
    
    # No need to mock internal modules
    try:
        from .websocket_notifications import NotificationType, emit_event
    except (ImportError, ModuleNotFoundError):
        NotificationType = type('MockNotificationType', (), {'WEBRTC_OFFER': 'webrtc.offer'})
        emit_event = lambda *args, **kwargs: None

else:
    # Normal dependency checking mode
    # Try to import numpy (required for image processing)
    try:
        import numpy as np
        HAVE_NUMPY = True
    except ImportError:
        logger.info("Numpy not found, some WebRTC features will be unavailable")

    # Try to import OpenCV (for video processing)
    if HAVE_NUMPY:
        try:
            import cv2
            HAVE_CV2 = True
        except ImportError:
            # Try alternative opencv modules
            try:
                import cv2.cv2 as cv2
                HAVE_CV2 = True
            except ImportError:
                try:
                    # Check for headless version
                    import cv2
                    HAVE_CV2 = True
                except ImportError:
                    logger.info("OpenCV not found, some video processing features will be unavailable")

    # Try to import AV (for media handling)
    try:
        import av
        HAVE_AV = True
    except ImportError:
        try:
            # Sometimes the import is case-sensitive
            import av.pyav as av
            HAVE_AV = True
        except ImportError:
            logger.info("PyAV not found, media handling features will be unavailable")

    # Try to import aiortc (for WebRTC)
    try:
        import aiortc
        from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
        from aiortc.mediastreams import MediaStreamTrack, VideoStreamTrack, AudioStreamTrack
        from aiortc.rtcrtpsender import RTCRtpSender
        from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaRecorder
        HAVE_AIORTC = True
    except ImportError:
        # Second attempt with explicit import paths
        try:
            import aiortc
            # Sometimes the internal modules need to be imported individually
            try:
                from aiortc import RTCPeerConnection
                from aiortc import RTCSessionDescription
                from aiortc import RTCConfiguration
                from aiortc import RTCIceServer
                from aiortc.mediastreams import MediaStreamTrack, VideoStreamTrack, AudioStreamTrack
                from aiortc.rtcrtpsender import RTCRtpSender
                from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaRecorder
                HAVE_AIORTC = True
            except ImportError as e:
                logger.info(f"aiortc module found but submodules missing: {e}")
                HAVE_AIORTC = False
        except ImportError:
            logger.info("aiortc not found, WebRTC features will be unavailable")

    # Check for WebSocket implementation (for signaling)
    try:
        from websockets.exceptions import ConnectionClosed
        HAVE_WEBSOCKETS = True
    except ImportError:
        HAVE_WEBSOCKETS = False
        logger.info("websockets not found, WebRTC signaling will be unavailable")

    # Check for notification system
    try:
        from .websocket_notifications import NotificationType, emit_event
        HAVE_NOTIFICATIONS = True
    except (ImportError, ModuleNotFoundError):
        logger.info("Notification system not available")

    # Set overall WebRTC availability flag
    HAVE_WEBRTC = all([HAVE_NUMPY, HAVE_CV2, HAVE_AV, HAVE_AIORTC])
    
    # Log detected dependencies
    logger.info(f"WebRTC dependencies status: NUMPY={HAVE_NUMPY}, CV2={HAVE_CV2}, AV={HAVE_AV}, AIORTC={HAVE_AIORTC}")
    logger.info(f"WebRTC availability: {HAVE_WEBRTC}")

# Constants for WebRTC
DEFAULT_ICE_SERVERS = [
    {"urls": ["stun:stun.l.google.com:19302"]}
]
DEFAULT_BITRATE = 1_000_000  # 1 Mbps
MIN_BITRATE = 100_000  # 100 Kbps
MAX_BITRATE = 5_000_000  # 5 Mbps
DEFAULT_FRAMERATE = 30
QUALITY_PRESETS = {
    "low": {"bitrate": 500_000, "width": 640, "height": 360, "framerate": 15},
    "medium": {"bitrate": 1_000_000, "width": 1280, "height": 720, "framerate": 30},
    "high": {"bitrate": 2_500_000, "width": 1920, "height": 1080, "framerate": 30}
}

class AdaptiveBitrateController:
    """Adaptive bitrate controller for WebRTC streams."""
    
    def __init__(self, initial_bitrate=DEFAULT_BITRATE, 
                 min_bitrate=MIN_BITRATE, 
                 max_bitrate=MAX_BITRATE):
        """Initialize the bitrate controller with initial settings."""
        self.target_bitrate = initial_bitrate
        self.min_bitrate = min_bitrate
        self.max_bitrate = max_bitrate
        self.current_bitrate = initial_bitrate
        self.quality_level = "auto"
        
        # Track adaptation state
        self.last_adaptation = time.time()
        self.adaptation_history = []
        self.network_conditions = "stable"
    
    def set_quality(self, quality_level):
        """Set the quality level for the stream."""
        if quality_level not in QUALITY_PRESETS and quality_level != "auto":
            logger.warning(f"Unknown quality level: {quality_level}")
            return None
            
        self.quality_level = quality_level
        
        if quality_level == "auto":
            # Auto mode - no fixed preset, just enable adaptation
            return {
                "mode": "auto",
                "bitrate": self.current_bitrate,
                "adaptable": True
            }
        else:
            # Fixed quality preset
            preset = QUALITY_PRESETS[quality_level]
            self.target_bitrate = preset["bitrate"]
            self.current_bitrate = preset["bitrate"]
            
            return {
                "mode": "fixed",
                "preset": quality_level,
                "bitrate": preset["bitrate"],
                "width": preset["width"],
                "height": preset["height"],
                "framerate": preset["framerate"],
                "adaptable": False
            }
    
    def adapt(self, stats):
        """Adapt bitrate based on network statistics."""
        # Only adapt in auto mode
        if self.quality_level != "auto":
            return {"adapted": False, "reason": "fixed_quality_mode"}
        
        # Check if enough time has passed since last adaptation
        now = time.time()
        if now - self.last_adaptation < 5:  # Minimum 5 seconds between adaptations
            return {"adapted": False, "reason": "too_soon"}
            
        # Extract relevant stats
        packet_loss = stats.get("packet_loss", 0)
        rtt = stats.get("rtt", 0)
        available_bandwidth = stats.get("available_bandwidth", self.current_bitrate)
        
        # Determine network condition
        if packet_loss > 0.1:  # >10% packet loss
            self.network_conditions = "poor"
        elif packet_loss > 0.03:  # 3-10% packet loss
            self.network_conditions = "fair"
        else:  # <3% packet loss
            self.network_conditions = "good"
        
        old_bitrate = self.current_bitrate
        
        # Adapt bitrate based on conditions
        if self.network_conditions == "poor":
            # Reduce bitrate by 30%
            self.current_bitrate = max(self.min_bitrate, int(self.current_bitrate * 0.7))
        elif self.network_conditions == "fair":
            # Reduce bitrate by 10%
            self.current_bitrate = max(self.min_bitrate, int(self.current_bitrate * 0.9))
        elif self.network_conditions == "good" and available_bandwidth > self.current_bitrate * 1.2:
            # Increase bitrate by 10% if bandwidth allows
            self.current_bitrate = min(self.max_bitrate, int(self.current_bitrate * 1.1))
        
        # Record adaptation
        adaptation = {
            "timestamp": now,
            "old_bitrate": old_bitrate,
            "new_bitrate": self.current_bitrate,
            "packet_loss": packet_loss,
            "rtt": rtt,
            "network_condition": self.network_conditions
        }
        self.adaptation_history.append(adaptation)
        self.last_adaptation = now
        
        # Check if adaptation happened
        if old_bitrate != self.current_bitrate:
            logger.info(f"Adapted bitrate: {old_bitrate/1000:.0f}kbps -> {self.current_bitrate/1000:.0f}kbps")
            return {
                "adapted": True,
                "reason": f"network_{self.network_conditions}",
                "details": adaptation
            }
        else:
            return {"adapted": False, "reason": "no_change_needed"}


# Define implementations only if dependencies are available
if HAVE_WEBRTC:
    class IPFSMediaStreamTrack(VideoStreamTrack):
        """Media stream track that sources content from IPFS."""
        
        def __init__(self, 
                    source_cid=None, 
                    source_path=None,
                    width=1280, 
                    height=720, 
                    framerate=30,
                    ipfs_client=None,
                    track_id=None):
            """Initialize the IPFS media stream track."""
            super().__init__()
            self.source_cid = source_cid
            self.source_path = source_path
            self.width = width
            self.height = height
            self.framerate = framerate
            self.ipfs_client = ipfs_client
            self.track_id = track_id or str(uuid.uuid4())
            
            # Initialize state
            self.active = True
            self.frame_count = 0
            self.start_time = time.time()
            self.last_frame_time = self.start_time
            
            # Set up adaptive bitrate control
            self._bitrate_controller = AdaptiveBitrateController()
            
            # Initialize video source
            self._initialize_source()
        
        def _initialize_source(self):
            """Initialize the video source from IPFS content."""
            if self.source_cid:
                # Load content from IPFS
                if self.ipfs_client:
                    logger.info(f"Loading IPFS content: {self.source_cid}")
                    try:
                        # Fetch content from IPFS
                        content = self.ipfs_client.cat(self.source_cid)
                        
                        # Save to temporary file for processing
                        import tempfile
                        self.temp_dir = tempfile.TemporaryDirectory()
                        temp_path = Path(self.temp_dir.name) / "media.mp4"
                        
                        with open(temp_path, "wb") as f:
                            f.write(content)
                            
                        # Create media source
                        self.player = MediaPlayer(str(temp_path))
                        
                        # Get video track
                        self.source_track = self.player.video
                        
                        logger.info(f"Successfully loaded media from IPFS: {self.source_cid}")
                    
                    except Exception as e:
                        logger.error(f"Error loading IPFS content: {e}")
                        self.source_track = None
                else:
                    logger.error("No IPFS client provided")
                    self.source_track = None
            
            elif self.source_path:
                # Load from local file
                try:
                    self.player = MediaPlayer(self.source_path)
                    self.source_track = self.player.video
                    logger.info(f"Successfully loaded media from local path: {self.source_path}")
                except Exception as e:
                    logger.error(f"Error loading local media: {e}")
                    self.source_track = None
            
            else:
                # Generate test pattern if no source provided
                logger.info("No source provided, using test pattern")
                self.source_track = None
        
        async def recv(self):
            """Receive the next frame from the source."""
            if not self.active:
                # Track has been stopped
                frame = None
                pts, time_base = await self._next_timestamp()
            
            elif self.source_track:
                # Use source track if available
                try:
                    frame = await self.source_track.recv()
                except Exception as e:
                    logger.error(f"Error receiving frame from source: {e}")
                    frame = self._create_test_frame()
                    pts, time_base = await self._next_timestamp()
                    
            else:
                # Generate test pattern
                frame = self._create_test_frame()
                pts, time_base = await self._next_timestamp()
            
            # Update stats
            self.frame_count += 1
            self.last_frame_time = time.time()
            
            return frame
        
        def _create_test_frame(self):
            """Create a test pattern frame."""
            import fractions
            
            # Create a simple test pattern
            width, height = self.width, self.height
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Draw a gradient background
            for y in range(height):
                for x in range(width):
                    frame[y, x, 0] = int(255 * x / width)  # Blue gradient
                    frame[y, x, 1] = int(255 * y / height)  # Green gradient
                    frame[y, x, 2] = 128  # Constant red
            
            # Add frame number and timestamp
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = f"Frame: {self.frame_count} - Time: {time.time():.2f}"
            cv2.putText(frame, text, (50, 50), font, 1, (255, 255, 255), 2)
            
            # Add IPFS info
            if self.source_cid:
                cv2.putText(frame, f"IPFS CID: {self.source_cid[:20]}...", 
                          (50, 100), font, 0.8, (255, 255, 255), 2)
            
            # Create VideoFrame
            frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
            frame.pts = int(self.frame_count * 1000 / self.framerate)
            frame.time_base = fractions.Fraction(1, 1000)
            
            return frame
        
        async def _next_timestamp(self):
            """Calculate the next frame timestamp."""
            import fractions
            
            # Calculate timing based on framerate
            elapsed = time.time() - self.start_time
            pts = int(self.frame_count * 1000 / self.framerate)
            time_base = fractions.Fraction(1, 1000)
            
            # If we're ahead of schedule, add a small delay
            target_time = self.start_time + (pts / 1000)
            delay = max(0, target_time - time.time())
            if delay > 0:
                await asyncio.sleep(delay)
            
            return pts, time_base
        
        def stop(self):
            """Stop the track and clean up resources."""
            self.active = False
            
            # Clean up media player if needed
            if hasattr(self, 'player') and self.player and hasattr(self.player, 'video') and self.player.video:
                self.player.video.stop()
                
            # Clean up temporary directory if needed
            if hasattr(self, 'temp_dir') and self.temp_dir:
                self.temp_dir.cleanup()
        
        def get_stats(self):
            """Get statistics about this track."""
            now = time.time()
            elapsed = now - self.start_time
            
            return {
                "track_id": self.track_id,
                "resolution": f"{self.width}x{self.height}",
                "framerate": self.framerate,
                "frames_sent": self.frame_count,
                "uptime": elapsed,
                "fps": self.frame_count / max(1, elapsed),
                "bitrate": self._bitrate_controller.current_bitrate,
                "quality_level": self._bitrate_controller.quality_level,
                "last_frame_time": self.last_frame_time,
                "active": self.active
            }
            
    class WebRTCStreamingManager:
        """Manager for WebRTC streaming connections."""
        
        def __init__(self, ipfs_api=None, ice_servers=None):
            """Initialize the WebRTC streaming manager."""
            if not HAVE_WEBRTC:
                raise ImportError(
                    "WebRTC dependencies not available. Install them with: "
                    "pip install ipfs_kit_py[webrtc]"
                )
                
            self.ipfs = ipfs_api
            self.ice_servers = ice_servers or DEFAULT_ICE_SERVERS
            
            # Connection state
            self.peer_connections = {}
            self.connection_stats = {}
            self.tracks = {}
            
            # Media relay for track sharing
            self.relay = MediaRelay()
            
            # Time tracking
            self.start_time = time.time()
        
        async def create_offer(self, pc_id=None, track_ids=None):
            """Create an offer for a new peer connection."""
            pc_id = pc_id or str(uuid.uuid4())
            
            # Create a new peer connection
            pc = RTCPeerConnection(RTCConfiguration(
                iceServers=self.ice_servers
            ))
            
            # Store the connection
            self.peer_connections[pc_id] = pc
            
            # Initialize stats for this connection
            self.connection_stats[pc_id] = {
                "created_at": time.time(),
                "ice_state": "new",
                "signaling_state": "new",
                "connection_state": "new",
                "tracks": [],
                "last_activity": time.time()
            }
            
            # Helper function to track state changes
            def track_state_change(name, state):
                self.connection_stats[pc_id][name] = state
                self.connection_stats[pc_id]["last_activity"] = time.time()
                logger.info(f"[{pc_id}] {name} -> {state}")
            
            # Add connection state change listener
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                track_state_change("connection_state", pc.connectionState)
                
                # Log more details for failed connections
                if pc.connectionState == "failed":
                    logger.warning(f"[{pc_id}] Connection failed")
                
                # Notify on completed connections
                if pc.connectionState == "connected":
                    logger.info(f"[{pc_id}] Connection established")
                    
                    # Emit connected notification
                    if HAVE_NOTIFICATIONS:
                        await emit_event(
                            NotificationType.WEBRTC_CONNECTED,
                            {
                                "pc_id": pc_id,
                                "client_id": pc_id,
                                "tracks": len(pc.getTransceivers())
                            },
                            source="webrtc_manager"
                        )
                
                # Clean up closed connections
                if pc.connectionState in ["closed", "failed"]:
                    await self.close_connection(pc_id)
            
            # Track ICE connection state
            @pc.on("iceconnectionstatechange")
            async def on_iceconnectionstatechange():
                track_state_change("ice_state", pc.iceConnectionState)
            
            # Track signaling state
            @pc.on("signalingstatechange")
            async def on_signalingstatechange():
                track_state_change("signaling_state", pc.signalingState)
            
            # Add tracks if requested
            if track_ids:
                for track_id in track_ids:
                    if track_id in self.tracks:
                        # Reuse existing track through relay
                        track = self.relay.subscribe(self.tracks[track_id])
                        pc.addTrack(track)
                        
                        # Update stats
                        self.connection_stats[pc_id]["tracks"].append(track_id)
                        logger.info(f"[{pc_id}] Added existing track {track_id}")
                    else:
                        logger.warning(f"[{pc_id}] Requested track {track_id} not found")
            
            # Create default track if none specified
            if not track_ids or len(track_ids) == 0:
                # Create a default test pattern track
                track_id = f"default-{pc_id}"
                track = IPFSMediaStreamTrack(track_id=track_id, ipfs_client=self.ipfs)
                
                # Store the track for potential reuse
                self.tracks[track_id] = track
                
                # Add to the connection
                pc.addTrack(track)
                self.connection_stats[pc_id]["tracks"].append(track_id)
                logger.info(f"[{pc_id}] Created default track {track_id}")
            
            # Create and return offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            return {
                "pc_id": pc_id,
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
                "ice_servers": self.ice_servers,
                "tracks": self.connection_stats[pc_id]["tracks"]
            }
        
        async def handle_answer(self, pc_id, sdp, type="answer"):
            """Handle a WebRTC answer from a client."""
            # Check if the connection exists
            if pc_id not in self.peer_connections:
                logger.warning(f"Received answer for unknown connection: {pc_id}")
                return {
                    "success": False,
                    "error": "Connection not found"
                }
            
            pc = self.peer_connections[pc_id]
            
            # Set the remote description
            try:
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=sdp, type=type)
                )
                
                # Update stats
                self.connection_stats[pc_id]["remote_sdp_set"] = True
                self.connection_stats[pc_id]["last_activity"] = time.time()
                
                return {
                    "success": True,
                    "pc_id": pc_id
                }
                
            except Exception as e:
                logger.error(f"[{pc_id}] Error setting remote description: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        async def add_ipfs_track(self, cid, track_id=None, pc_id=None):
            """Add a track from IPFS content to a connection."""
            track_id = track_id or f"ipfs-{cid[:8]}-{str(uuid.uuid4())[:6]}"
            
            try:
                # Create new track from IPFS content
                track = IPFSMediaStreamTrack(
                    source_cid=cid,
                    ipfs_client=self.ipfs,
                    track_id=track_id
                )
                
                # Store for reuse
                self.tracks[track_id] = track
                
                # If pc_id provided, add to that connection
                if pc_id and pc_id in self.peer_connections:
                    pc = self.peer_connections[pc_id]
                    pc.addTrack(track)
                    
                    # Update stats
                    self.connection_stats[pc_id]["tracks"].append(track_id)
                    self.connection_stats[pc_id]["last_activity"] = time.time()
                
                return {
                    "success": True,
                    "track_id": track_id,
                    "cid": cid
                }
                
            except Exception as e:
                logger.error(f"Error adding IPFS track from {cid}: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        async def close_connection(self, pc_id):
            """Close and clean up a peer connection."""
            if pc_id in self.peer_connections:
                pc = self.peer_connections[pc_id]
                
                # Close the connection
                await pc.close()
                
                # Clean up tracks specific to this connection
                track_ids = self.connection_stats[pc_id]["tracks"]
                for track_id in track_ids:
                    # Check if track is used by other connections
                    track_in_use = False
                    for other_id, stats in self.connection_stats.items():
                        if other_id != pc_id and track_id in stats["tracks"]:
                            track_in_use = True
                            break
                    
                    # If not used elsewhere, clean it up
                    if not track_in_use and track_id in self.tracks:
                        track = self.tracks[track_id]
                        if hasattr(track, 'stop'):
                            track.stop()
                        del self.tracks[track_id]
                
                # Remove from dictionaries
                del self.peer_connections[pc_id]
                del self.connection_stats[pc_id]
                
                # Log the cleanup
                logger.info(f"Closed connection {pc_id}")
                
                return {"success": True, "pc_id": pc_id}
            else:
                return {"success": False, "error": "Connection not found"}
        
        async def close_all_connections(self):
            """Close all peer connections."""
            # Cancel metrics task if it exists
            if hasattr(self, 'metrics_task') and self.metrics_task:
                self.metrics_task.cancel()
                
            pcs = list(self.peer_connections.keys())
            for pc_id in pcs:
                await self.close_connection(pc_id)
            
            logger.info(f"Closed all {len(pcs)} connections")
        
        def get_stats(self):
            """Get overall statistics."""
            return {
                "active_connections": len(self.peer_connections),
                "active_tracks": len(self.tracks),
                "uptime": time.time() - self.start_time,
                "connections": self.connection_stats
            }

# Stub implementations for when dependencies are missing
else:
    # Stubs that raise ImportError when used
    class IPFSMediaStreamTrack:
        """Stub implementation of IPFSMediaStreamTrack."""
        
        def __init__(self, *args, **kwargs):
            """Raise an informative import error."""
            raise ImportError(
                "WebRTC dependencies not available. Install them with: "
                "pip install ipfs_kit_py[webrtc]"
            )

    class WebRTCStreamingManager:
        """Stub implementation of WebRTCStreamingManager."""
        
        def __init__(self, *args, **kwargs):
            """Raise an informative import error."""
            raise ImportError(
                "WebRTC dependencies not available. Install them with: "
                "pip install ipfs_kit_py[webrtc]"
            )

# WebRTC signaling handler (implemented regardless of dependencies)
async def handle_webrtc_signaling(websocket, path, manager=None):
    """Handle WebRTC signaling over WebSocket.
    
    This function processes WebRTC signaling messages between
    the client and server, establishing connections and managing
    media streams.
    
    Args:
        websocket: The WebSocket connection
        path: The connection path
        manager: Optional WebRTCStreamingManager instance
    
    Note:
        This stub implementation is always defined but will raise
        an error if WebRTC dependencies are missing.
    """
    if not HAVE_WEBRTC:
        if HAVE_WEBSOCKETS:
            await websocket.send_json({
                "type": "error",
                "message": "WebRTC dependencies not available. Install them with: pip install ipfs_kit_py[webrtc]"
            })
        return
        
    # Make sure we have a manager
    if manager is None:
        # Attempt to create a manager
        try:
            manager = WebRTCStreamingManager()
        except ImportError as e:
            if HAVE_WEBSOCKETS:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            return
    
    client_id = str(uuid.uuid4())
    logger.info(f"New WebRTC signaling connection: {client_id}")
    
    try:
        # Notify about signaling connection
        if HAVE_NOTIFICATIONS:
            await emit_event(
                NotificationType.SYSTEM_INFO,
                {
                    "message": "New WebRTC signaling connection",
                    "client_id": client_id
                },
                source="webrtc_signaling"
            )
        
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "server_info": {
                "version": "ipfs_kit_py WebRTC",
                "features": ["streaming", "signaling", "adaptive-bitrate"]
            }
        })
        
        # Process messages
        async for message in websocket:
            try:
                msg = json.loads(message)
                msg_type = msg.get("type")
                
                # Process based on message type
                if msg_type == "offer_request":
                    # Client wants an offer - create a connection
                    pc_id = msg.get("pc_id")
                    track_ids = msg.get("track_ids")
                    
                    offer = await manager.create_offer(pc_id, track_ids)
                    
                    await websocket.send_json({
                        "type": "offer",
                        **offer
                    })
                
                elif msg_type == "answer":
                    # Client has sent an answer to our offer
                    pc_id = msg.get("pc_id")
                    sdp = msg.get("sdp")
                    
                    result = await manager.handle_answer(pc_id, sdp)
                    
                    await websocket.send_json({
                        "type": "answer_result",
                        **result
                    })
                
                elif msg_type == "add_ipfs_track":
                    # Client wants to add a track from IPFS content
                    cid = msg.get("cid")
                    pc_id = msg.get("pc_id")
                    track_id = msg.get("track_id")
                    
                    if not cid:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing CID for IPFS track"
                        })
                        continue
                    
                    result = await manager.add_ipfs_track(cid, track_id, pc_id)
                    
                    await websocket.send_json({
                        "type": "add_track_result",
                        **result
                    })
                
                elif msg_type == "close":
                    # Client wants to close a connection
                    pc_id = msg.get("pc_id")
                    
                    if not pc_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing pc_id for close"
                        })
                        continue
                    
                    result = await manager.close_connection(pc_id)
                    
                    await websocket.send_json({
                        "type": "close_result",
                        **result
                    })
                
                elif msg_type == "stats_request":
                    # Client wants connection statistics
                    pc_id = msg.get("pc_id")
                    
                    if pc_id and pc_id in manager.connection_stats:
                        # Get stats for specific connection
                        stats = manager.connection_stats[pc_id]
                        
                        # Add track-specific stats if available
                        track_stats = {}
                        for track_id in stats.get("tracks", []):
                            if track_id in manager.tracks:
                                track = manager.tracks[track_id]
                                if hasattr(track, "get_stats"):
                                    track_stats[track_id] = track.get_stats()
                        
                        await websocket.send_json({
                            "type": "stats",
                            "pc_id": pc_id,
                            "stats": stats,
                            "track_stats": track_stats,
                            "timestamp": time.time()
                        })
                    else:
                        # Get overall stats
                        stats = manager.get_stats()
                        
                        await websocket.send_json({
                            "type": "stats",
                            "stats": stats,
                            "timestamp": time.time()
                        })
                
                elif msg_type == "quality_change":
                    # Client wants to change stream quality
                    pc_id = msg.get("pc_id")
                    track_id = msg.get("track_id")
                    quality = msg.get("quality", "medium")
                    
                    if not pc_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing pc_id for quality change"
                        })
                        continue
                    
                    # Find the appropriate track
                    success = False
                    if pc_id in manager.connection_stats:
                        # Get the track(s) for this connection
                        track_ids = manager.connection_stats[pc_id].get("tracks", [])
                        
                        # If track_id specified, use that one, otherwise use first track
                        track = None
                        if track_id and track_id in track_ids and track_id in manager.tracks:
                            track = manager.tracks[track_id]
                        elif track_ids and track_ids[0] in manager.tracks:
                            track = manager.tracks[track_ids[0]]
                        
                        # Handle both single track and multiple tracks
                        tracks_to_update = [track] if not isinstance(track, list) else track
                        
                        for idx, current_track in enumerate(tracks_to_update):
                            if hasattr(current_track, '_bitrate_controller') and \
                               hasattr(current_track._bitrate_controller, 'set_quality'):
                                # Set quality on the track
                                settings = current_track._bitrate_controller.set_quality(quality)
                                success = True
                                
                                # Update connection stats
                                if pc_id in manager.connection_stats:
                                    manager.connection_stats[pc_id]["quality"] = quality
                                    manager.connection_stats[pc_id]["quality_settings"] = settings
                                    manager.connection_stats[pc_id]["adaptation_changes"] = \
                                        manager.connection_stats[pc_id].get("adaptation_changes", 0) + 1
                                
                                # Emit quality changed notification
                                if HAVE_NOTIFICATIONS:
                                    await emit_event(
                                        NotificationType.WEBRTC_QUALITY_CHANGED,
                                        {
                                            "pc_id": pc_id,
                                            "quality_level": quality,
                                            "settings": settings,
                                            "track_index": idx,
                                            "client_initiated": True
                                        },
                                        source="webrtc_signaling"
                                    )
                    
                    await websocket.send_json({
                        "type": "quality_result",
                        "pc_id": pc_id,
                        "quality": quality,
                        "success": success
                    })
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })
            
            except json.JSONDecodeError:
                error_msg = "Invalid JSON message"
                logger.error(error_msg)
                
                # Emit error notification
                if HAVE_NOTIFICATIONS:
                    await emit_event(
                        NotificationType.WEBRTC_ERROR,
                        {
                            "error": error_msg,
                            "client_id": client_id
                        },
                        source="webrtc_signaling"
                    )
                
                await websocket.send_json({
                    "type": "error",
                    "message": error_msg
                })
    
    except Exception as e:
        error_msg = f"WebRTC signaling error: {e}"
        logger.error(error_msg)
        
        # Emit error notification
        if HAVE_NOTIFICATIONS:
            await emit_event(
                NotificationType.WEBRTC_ERROR,
                {
                    "error": error_msg,
                    "client_id": client_id,
                    "stack_trace": str(e)
                },
                source="webrtc_signaling"
            )
        
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
    
    finally:
        # Clean up all connections
        if manager:
            await manager.close_all_connections()
        
        # Notify about signaling connection closing
        if HAVE_NOTIFICATIONS:
            await emit_event(
                NotificationType.SYSTEM_INFO,
                {
                    "message": "WebRTC signaling connection closed",
                    "client_id": client_id
                },
                source="webrtc_signaling"
            )
        
        logger.info(f"WebRTC signaling connection closed: {client_id}")

# Module-level test function
def check_webrtc_dependencies():
    """Check the status of WebRTC dependencies and return a detailed report."""
    return {
        "webrtc_available": HAVE_WEBRTC,
        "dependencies": {
            "numpy": HAVE_NUMPY,
            "opencv": HAVE_CV2,
            "av": HAVE_AV,
            "aiortc": HAVE_AIORTC,
            "websockets": HAVE_WEBSOCKETS,
            "notifications": HAVE_NOTIFICATIONS
        },
        "installation_command": "pip install ipfs_kit_py[webrtc]"
    }