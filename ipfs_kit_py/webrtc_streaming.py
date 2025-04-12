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
from typing import Dict, List, Optional, Union, Callable, Any, Tuple
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext

# Import anyio as primary async library
import anyio
from anyio.to_thread import run_sync
# Import asyncio for compatibility with aiortc
# Will be fully replaced with anyio once all migration is complete
import anyio

# Try to detect current async context
try:
    import sniffio
    HAS_SNIFFIO = True
except ImportError:
    HAS_SNIFFIO = False

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

# Global variables for WebRTC state
webrtc_connections = {}
media_players = {}
media_relays = {}
media_tracks = {}
active_streams = {}
peer_stats = {}
quality_profiles = {}
event_listeners = {}
_next_track_id = 0  # For unique track IDs

class AnyIOEventLoopHandler:
    """Helper class to manage event loop interaction with AnyIO compatibility.
    
    This class detects the current async context and provides methods to run coroutines
    appropriately, whether in asyncio, trio, or non-async contexts.
    """
    
    def __init__(self):
        """Initialize with detection of current async context."""
        self.current_async_lib = None
        self.in_async_context = False
        
        # Try to detect current async context if sniffio is available
        if HAS_SNIFFIO:
            try:
                self.current_async_lib = sniffio.current_async_library()
                self.in_async_context = True
                logger.debug(f"Detected async context: {self.current_async_lib}")
            except sniffio.AsyncLibraryNotFoundError:
                self.in_async_context = False
                logger.debug("No async context detected")
    
    async def run_coro(self, coro):
        """Run a coroutine in the appropriate way based on detected context.
        
        Args:
            coro: Asyncio coroutine to run
            
        Returns:
            Result of the coroutine
        """
        # If we're in the same async library context, we can just await the coroutine
        if self.current_async_lib in ("asyncio", "anyio"):
            return await coro
        
        # If we're in a trio or another context, we need to run it in a thread
        if self.in_async_context:
            # Use AnyIO's run_sync to execute the coroutine in thread
            return await anyio.to_thread.run_sync(
                lambda: anyio.run(coro)
            )
        
        # If we're not in an async context at all, just run it directly
        return anyio.run(coro)
    
    def run_sync(self, coro):
        """Run a coroutine synchronously.
        
        Args:
            coro: Asyncio coroutine to run
            
        Returns:
            Result of the coroutine
        """
        return anyio.run(coro)

# Create a global instance for use throughout the module
event_loop_handler = AnyIOEventLoopHandler()

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
        """Media stream track that sources content from IPFS with optimized streaming."""
        
        def __init__(self, 
                    source_cid=None, 
                    source_path=None,
                    width=1280, 
                    height=720, 
                    framerate=30,
                    ipfs_client=None,
                    track_id=None,
                    buffer_size=30,  # Buffer size in frames
                    prefetch_threshold=0.5,  # Prefetch when buffer is 50% full
                    use_progressive_loading=True):  # Enable progressive loading
            """Initialize the IPFS media stream track with optimized buffering."""
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
            
            # Advanced buffering and streaming optimization
            self.buffer_size = buffer_size
            self.initial_buffer_size = buffer_size  # Store initial size for adaptation metrics
            self.prefetch_threshold = prefetch_threshold
            self.use_progressive_loading = use_progressive_loading
            self.frame_buffer = anyio.Queue(maxsize=buffer_size)
            self.buffer_task = None
            self.buffer_stats = {
                "buffer_size": buffer_size,
                "current_fill_level": 0,
                "underflows": 0,
                "overflows": 0,
                "prefetches": 0,
                "avg_fill_level": 0,
                "fill_level_samples": []
            }
            
            # Network adaption metrics
            self.network_metrics = {
                "last_frame_delay": 0,
                "avg_frame_delay": 0,
                "frame_delays": [],
                "jitter": 0,
                "last_adaptation": time.time()
            }
            
            # Initialize video source
            self._initialize_source()
            
            # Start buffer filling
            if self.source_track:
                self.buffer_task = anyio.create_task(self._fill_buffer())
        
        def _initialize_source(self):
            """Initialize the video source from IPFS content with progressive loading."""
            if self.source_cid:
                # Load content from IPFS
                if self.ipfs_client:
                    logger.info(f"Loading IPFS content: {self.source_cid}")
                    try:
                        # Create temporary directory
                        import tempfile
                        self.temp_dir = tempfile.TemporaryDirectory()
                        temp_path = Path(self.temp_dir.name) / "media.mp4"
                        
                        if self.use_progressive_loading:
                            # Progressive loading - create empty file first
                            with open(temp_path, "wb") as f:
                                f.write(b"")  # Create empty file
                            
                            # Start fetching in the background
                            self.fetch_task = anyio.create_task(
                                self._progressive_fetch(self.source_cid, temp_path)
                            )
                            
                            # Wait a short time for initial data
                            time.sleep(0.1)
                        else:
                            # Traditional loading - fetch entire content
                            content = self.ipfs_client.cat(self.source_cid)
                            with open(temp_path, "wb") as f:
                                f.write(content)
                            
                        # Create media source with appropriate options
                        import av
                        self.container = av.open(
                            str(temp_path), 
                            mode='r',
                            timeout=60,  # Increased timeout for progressive loading
                            options={
                                'analyzeduration': '10000000',  # 10 seconds in microseconds
                                'probesize': '5000000',  # 5MB probe size for progressive loading
                                'fflags': 'nobuffer',   # Less buffering for real-time playback
                            }
                        )
                        
                        # Create player with an overridden socket read timeout
                        self.player = MediaPlayer(
                            str(temp_path),
                            options={
                                'rtbufsize': '15M',  # Larger real-time buffer
                                'fflags': 'nobuffer+discardcorrupt',  # Discard corrupt frames
                            }
                        )
                        
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
                    self.player = MediaPlayer(
                        self.source_path,
                        options={
                            'rtbufsize': '15M',  # Larger real-time buffer
                            'fflags': 'nobuffer+discardcorrupt',  # Discard corrupt frames
                        }
                    )
                    self.source_track = self.player.video
                    logger.info(f"Successfully loaded media from local path: {self.source_path}")
                except Exception as e:
                    logger.error(f"Error loading local media: {e}")
                    self.source_track = None
            
            else:
                # Generate test pattern if no source provided
                logger.info("No source provided, using test pattern")
                self.source_track = None
        
        async def _progressive_fetch(self, cid, file_path):
            """Progressively fetch IPFS content and write to file."""
            try:
                # Fetch content chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                
                # Get file size if possible
                size_result = self.ipfs_client.size(cid)
                total_size = size_result.get("Size", 0) if isinstance(size_result, dict) else 0
                
                # Open file for progressive writing
                with open(file_path, "wb") as f:
                    # If supported, get a chunk-based reader
                    if hasattr(self.ipfs_client, "cat_stream"):
                        async for chunk in self.ipfs_client.cat_stream(cid, chunk_size=chunk_size):
                            f.write(chunk)
                            await anyio.sleep(0.01)  # Small yield to prevent blocking
                    else:
                        # Fallback to single request
                        content = self.ipfs_client.cat(cid)
                        f.write(content)
                        
                logger.info(f"Completed progressive fetch of {cid} to {file_path}")
                
            except Exception as e:
                logger.error(f"Error in progressive fetch: {e}")
        
        async def _fill_buffer(self):
            """Fill the frame buffer from the source track."""
            frame_interval = 1.0 / self.framerate
            last_prefetch_time = time.time()
            
            try:
                while self.active and self.source_track:
                    # Check if buffer needs filling
                    current_fill = self.frame_buffer.qsize()
                    fill_percentage = current_fill / self.buffer_size
                    
                    # Update buffer statistics
                    self.buffer_stats["current_fill_level"] = current_fill
                    self.buffer_stats["fill_level_samples"].append(current_fill)
                    if len(self.buffer_stats["fill_level_samples"]) > 100:
                        self.buffer_stats["fill_level_samples"].pop(0)
                    self.buffer_stats["avg_fill_level"] = sum(self.buffer_stats["fill_level_samples"]) / len(self.buffer_stats["fill_level_samples"])
                    
                    # Check if we need to prefetch more frames
                    should_prefetch = fill_percentage <= self.prefetch_threshold
                    
                    if should_prefetch:
                        # Prefetch frames until buffer is full
                        prefetch_count = self.buffer_size - current_fill
                        prefetch_start = time.time()
                        
                        for _ in range(prefetch_count):
                            if not self.active:
                                break
                                
                            try:
                                # Get frame from source
                                frame = await self.source_track.recv()
                                
                                # Try to put in buffer (non-blocking)
                                try:
                                    self.frame_buffer.put_nowait(frame)
                                except anyio.WouldBlock:
                                    # Buffer is full
                                    self.buffer_stats["overflows"] += 1
                                    break
                                    
                            except Exception as e:
                                logger.error(f"Error prefetching frame: {e}")
                                break
                                
                        # Record prefetch stats
                        self.buffer_stats["prefetches"] += 1
                        last_prefetch_time = time.time()
                        prefetch_duration = time.time() - prefetch_start
                        logger.debug(f"Prefetched {prefetch_count} frames in {prefetch_duration:.3f}s")
                        
                    # Wait before checking buffer again
                    await anyio.sleep(frame_interval)
                    
            except anyio.get_cancelled_exc_class():
                logger.debug("Buffer filling task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in buffer filling task: {e}")
        
        async def recv(self):
            """Receive the next frame from the buffer with adaptive timing."""
            frame_start_time = time.time()
            
            if not self.active:
                # Track has been stopped
                frame = None
                pts, time_base = await self._next_timestamp()
            
            elif self.source_track and self.frame_buffer and self.frame_buffer.qsize() > 0:
                # Get frame from buffer
                try:
                    # Get from buffer with timeout
                    with anyio.fail_after(1.0/self.framerate):
                        frame = await self.frame_buffer.get()
                except TimeoutError:
                    # Buffer underflow
                    self.buffer_stats["underflows"] += 1
                    logger.debug("Buffer underflow, generating fallback frame")
                    frame = self._create_test_frame()
                except Exception as e:
                    logger.error(f"Error getting frame from buffer: {e}")
                    frame = self._create_test_frame()
                    
            elif self.source_track:
                # Direct from source if buffer not available
                try:
                    frame = await self.source_track.recv()
                except Exception as e:
                    logger.error(f"Error receiving frame from source: {e}")
                    frame = self._create_test_frame()
                    
            else:
                # Generate test pattern
                frame = self._create_test_frame()
            
            # Update network adaptation metrics
            frame_delay = time.time() - frame_start_time
            self.network_metrics["last_frame_delay"] = frame_delay
            self.network_metrics["frame_delays"].append(frame_delay)
            
            # Keep a rolling window of 30 frames for metrics
            if len(self.network_metrics["frame_delays"]) > 30:
                self.network_metrics["frame_delays"].pop(0)
                
            # Calculate average and jitter
            if len(self.network_metrics["frame_delays"]) > 1:
                self.network_metrics["avg_frame_delay"] = sum(self.network_metrics["frame_delays"]) / len(self.network_metrics["frame_delays"])
                
                # Calculate jitter as standard deviation of delays
                mean_delay = self.network_metrics["avg_frame_delay"]
                sum_squared_diff = sum((d - mean_delay) ** 2 for d in self.network_metrics["frame_delays"])
                self.network_metrics["jitter"] = (sum_squared_diff / len(self.network_metrics["frame_delays"])) ** 0.5
            
            # Consider adaptation if needed (high jitter or delays)
            now = time.time()
            if (now - self.network_metrics["last_adaptation"] > 5.0 and  # At least 5 seconds between adaptations
                (self.network_metrics["jitter"] > 0.05 or  # High jitter (>50ms std dev)
                 self.network_metrics["avg_frame_delay"] > 0.1)):  # High delay (>100ms)
                
                # Perform adaptation - adjust buffer size or prefetch threshold
                if self.network_metrics["jitter"] > 0.05:
                    # High jitter - increase buffer size to absorb jitter
                    self.buffer_size = min(60, self.buffer_size + 5)  # Increase but cap at 60 frames
                    logger.info(f"Increasing buffer size to {self.buffer_size} due to high jitter")
                
                if self.network_metrics["avg_frame_delay"] > 0.1:
                    # High delay - increase prefetch threshold for earlier prefetching
                    self.prefetch_threshold = min(0.8, self.prefetch_threshold + 0.1)
                    logger.info(f"Increasing prefetch threshold to {self.prefetch_threshold} due to high delay")
                
                # Record adaptation time
                self.network_metrics["last_adaptation"] = now
            
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
                await anyio.sleep(delay)
            
            return pts, time_base
        
        def stop(self):
            """Stop the track and clean up resources including buffer tasks."""
            self.active = False
            
            # Cancel buffer filling task if running
            if hasattr(self, 'buffer_task') and self.buffer_task:
                self.buffer_task.cancel()
                self.buffer_task = None
                
            # Cancel progressive fetch task if running
            if hasattr(self, 'fetch_task') and self.fetch_task:
                self.fetch_task.cancel()
                self.fetch_task = None
                
            # Clear frame buffer
            if hasattr(self, 'frame_buffer') and self.frame_buffer:
                while not self.frame_buffer.empty():
                    try:
                        self.frame_buffer.get_nowait()
                    except:
                        break
            
            # Clean up media player if needed
            if hasattr(self, 'player') and self.player and hasattr(self.player, 'video') and self.player.video:
                self.player.video.stop()
                
            # Close container if opened directly
            if hasattr(self, 'container') and self.container:
                try:
                    self.container.close()
                except:
                    pass
                
            # Clean up temporary directory if needed
            if hasattr(self, 'temp_dir') and self.temp_dir:
                try:
                    self.temp_dir.cleanup()
                except:
                    logger.debug("Error cleaning up temporary directory")
                
            logger.info(f"Track {self.track_id} stopped and resources cleaned up")
        
        def get_stats(self):
            """Get statistics about this track including buffer metrics."""
            now = time.time()
            elapsed = now - self.start_time
            
            # Basic stats
            stats = {
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
            
            # Add buffer statistics if available
            if hasattr(self, 'buffer_stats'):
                current_fill = self.frame_buffer.qsize() if hasattr(self, 'frame_buffer') else 0
                self.buffer_stats["current_fill_level"] = current_fill
                
                stats["buffer"] = {
                    "size": self.buffer_size,
                    "current_fill": current_fill,
                    "fill_percentage": (current_fill / self.buffer_size) * 100 if self.buffer_size > 0 else 0,
                    "underflows": self.buffer_stats.get("underflows", 0),
                    "overflows": self.buffer_stats.get("overflows", 0),
                    "prefetches": self.buffer_stats.get("prefetches", 0),
                    "avg_fill_level": self.buffer_stats.get("avg_fill_level", 0),
                    "prefetch_threshold": self.prefetch_threshold
                }
            
            # Add network adaptation metrics if available
            if hasattr(self, 'network_metrics'):
                stats["network"] = {
                    "avg_frame_delay_ms": self.network_metrics.get("avg_frame_delay", 0) * 1000,
                    "jitter_ms": self.network_metrics.get("jitter", 0) * 1000,
                    "buffer_adaptations": self.buffer_size != getattr(self, 'initial_buffer_size', 30)
                }
                
            # Add progressive loading statistics if available
            if hasattr(self, 'use_progressive_loading') and self.use_progressive_loading:
                stats["progressive_loading"] = True
                
            return stats
            
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

# AnyIO compatibility layer for WebRTC functions

async def create_offer_anyio(track_ids=None, ice_servers=None):
    """AnyIO-compatible version of WebRTC offer creation.
    
    This function handles the execution of the aiortc code
    in any async context using AnyIO.
    
    Args:
        track_ids: IDs of tracks to include in the offer
        ice_servers: ICE servers to use (defaults to standard STUN servers)
        
    Returns:
        Dictionary with the offer details
    """
    if not HAVE_WEBRTC:
        return {
            "success": False,
            "error": "WebRTC dependencies not available",
            "error_type": "dependency_missing",
            "installation_command": "pip install ipfs_kit_py[webrtc]"
        }
    
    # Create a manager instance
    manager = WebRTCStreamingManager(ice_servers=ice_servers)
    
    # Execute the aiortc coroutine using our handler
    try:
        result = await event_loop_handler.run_coro(
            manager.create_offer(track_ids=track_ids)
        )
        return result
    except Exception as e:
        logger.error(f"Error creating WebRTC offer: {e}")
        return {
            "success": False,
            "error": f"Error creating WebRTC offer: {str(e)}",
            "error_type": "webrtc_error"
        }

async def process_answer_anyio(pc_id, answer_sdp):
    """AnyIO-compatible version of WebRTC answer processing.
    
    Args:
        pc_id: Peer connection ID
        answer_sdp: SDP answer from the client
        
    Returns:
        Dictionary with the result of processing the answer
    """
    if not HAVE_WEBRTC:
        return {
            "success": False,
            "error": "WebRTC dependencies not available",
            "error_type": "dependency_missing",
            "installation_command": "pip install ipfs_kit_py[webrtc]"
        }
    
    # Execute the aiortc coroutine using our handler
    try:
        # We need to check if the connection exists
        if pc_id not in webrtc_connections:
            return {
                "success": False,
                "error": f"Unknown peer connection ID: {pc_id}",
                "error_type": "invalid_connection"
            }
            
        # Use the WebRTC connection directly since we don't have a manager
        pc = webrtc_connections[pc_id]
        
        # Create the session description
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        
        # Process the answer
        result = await event_loop_handler.run_coro(
            pc.setRemoteDescription(answer)
        )
        
        return {
            "success": True,
            "pc_id": pc_id
        }
    except Exception as e:
        logger.error(f"Error processing WebRTC answer: {e}")
        return {
            "success": False,
            "error": f"Error processing WebRTC answer: {str(e)}",
            "error_type": "webrtc_error"
        }