"""
WebRTC Streaming for IPFS Kit.

This module provides WebRTC-based streaming capabilities for IPFS content,
enabling real-time peer-to-peer audio and video streaming directly from
IPFS content with minimal latency.

Key features:
1. Media Streaming: Stream audio/video directly from IPFS
2. Bidirectional Communication: Both sending and receiving media streams
3. Peer-to-Peer: Direct WebRTC connections without requiring a media server
4. Low Latency: Optimized for real-time streaming
5. Adaptive Bitrate: Automatically adjusts to network conditions
6. ICE/STUN/TURN Support: Works across NATs and firewalls
7. Progressive Loading: Stream content while it's being loaded from IPFS

This module integrates with the high-level API and leverages aiortc
for WebRTC implementation.
"""

import asyncio
import json
import logging
import os
import time
import uuid
import math
import socket
import platform
import hashlib
import traceback
import threading
import statistics
from typing import Dict, List, Optional, Union, Callable, Any, Set, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

# Define what we have available
HAVE_AV = False
HAVE_CV2 = False
HAVE_NUMPY = False
HAVE_AIORTC = False
HAVE_WEBRTC = False

# Try to import each dependency separately for finer-grained fallbacks
try:
    import av
    HAVE_AV = True
except ImportError:
    av = None

try:
    import cv2
    HAVE_CV2 = True
except ImportError:
    cv2 = None

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    np = None

# Import aiortc components with careful error handling
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    # For MediaStreamTrack, we'll add a special try/except
    try:
        from aiortc import MediaStreamTrack
        from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
        HAVE_AIORTC = True
    except ImportError:
        # Create minimal stub for MediaStreamTrack to prevent import errors
        class MediaStreamTrack:
            """Stub implementation when real MediaStreamTrack is not available."""
            kind = "unknown"
            
            def __init__(self, *args, **kwargs):
                self.ended = Exception
                raise ImportError("MediaStreamTrack not available. Install with 'pip install aiortc'")
                
            async def recv(self):
                raise NotImplementedError("MediaStreamTrack not available")
                
            def stop(self):
                pass
    
    # Only set HAVE_WEBRTC to True if we have all required dependencies
    HAVE_WEBRTC = HAVE_AV and HAVE_CV2 and HAVE_NUMPY and HAVE_AIORTC
except ImportError:
    RTCPeerConnection = None
    RTCSessionDescription = None
    MediaStreamTrack = None
    MediaBlackhole = None
    MediaPlayer = None
    MediaRecorder = None
    MediaRelay = None

# Import notification system (with try-except for testing environments)
try:
    from .websocket_notifications import emit_event, NotificationType
    HAVE_NOTIFICATIONS = True
except ImportError:
    HAVE_NOTIFICATIONS = False
    # Create dummy emit_event function for environments without notifications
    async def emit_event(*args, **kwargs):
        pass

# Configure logging
logger = logging.getLogger(__name__)

# Track active peer connections to manage their lifecycle
active_peer_connections = {}

# Last error tracking for observability
last_webrtc_errors = []
MAX_ERROR_HISTORY = 10  # Keep track of last 10 errors


class WebRTCConfig:
    """Configuration for WebRTC streaming with optimized defaults and enhanced resilience."""
    
    def __init__(self, 
                ice_servers=None, 
                ice_transport_policy="all", 
                bundle_policy="max-bundle", 
                rtcp_mux_policy="require",
                sdp_semantics="unified-plan",
                reconnect_attempts=5,
                reconnect_delay=2.0,
                timeout=30,
                enable_metrics=True,
                enable_security=True,
                enable_auto_quality=True,
                enable_resilience=True,
                preferred_codecs=None,
                log_level=logging.INFO,
                ice_candidate_timeout=5000,
                ice_gathering_timeout=5000,
                ice_connectivity_timeout=10000,
                use_ice_tcp=True,
                backup_servers=True):
        """
        Initialize WebRTC configuration with sane defaults and enhanced resilience.
        
        Args:
            ice_servers: List of STUN/TURN servers for NAT traversal
            ice_transport_policy: ICE transport policy ("all" or "relay")
            bundle_policy: Media bundling policy
            rtcp_mux_policy: RTCP multiplexing policy
            sdp_semantics: SDP semantics mode
            reconnect_attempts: Number of reconnection attempts on failure
            reconnect_delay: Delay between reconnection attempts (seconds)
            timeout: Connection timeout (seconds)
            enable_metrics: Enable detailed metrics collection
            enable_security: Enable enhanced security features
            enable_auto_quality: Enable automatic quality adaptation
            enable_resilience: Enable connection resilience features
            preferred_codecs: List of preferred video/audio codecs
            log_level: Logging level for WebRTC components
            ice_candidate_timeout: Timeout for ICE candidate gathering (ms)
            ice_gathering_timeout: Timeout for ICE gathering phase (ms)
            ice_connectivity_timeout: Timeout for ICE connectivity checks (ms)
            use_ice_tcp: Whether to allow TCP candidates for NAT traversal
            backup_servers: Whether to include backup STUN/TURN servers for resilience
        """
        # Set up primary STUN servers
        primary_stun_servers = [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]}
        ]
        
        # Free fallback STUN servers for enhanced reliability
        fallback_stun_servers = [
            {"urls": ["stun:stun.stunprotocol.org:3478"]},
            {"urls": ["stun:openrelay.metered.ca:80"]},
            {"urls": ["stun:stun.voip.blackberry.com:3478"]},
            {"urls": ["stun:stun.sip.us:3478"]}
        ]
        
        # Geographic diversity for better global coverage
        geographic_stun_servers = [
            {"urls": ["stun:stun.services.mozilla.com:3478"]},  # US
            {"urls": ["stun:stun.sipgate.net:3478"]},          # Europe
            {"urls": ["stun:stun.cloudflare.com:3478"]}        # Global CDN
        ]
        
        # Backup TURN servers with credentials for NAT traversal
        # Note: These are free public servers with limited capacity
        # For production, you should use your own TURN servers
        backup_turn_servers = []
        
        if enable_resilience:
            # Add metered.ca free TURN with ephemeral credentials
            # This will work for example purposes, but for production
            # you should use your own TURN service
            try:
                import requests
                try:
                    # Attempt to get ephemeral credentials from metered.ca
                    # This is a free service with limitations
                    turn_url = "https://metered.ca/api/v1/turn/credentials?apiKey=ccafe87gcaac89vofpfk"
                    response = requests.get(turn_url)
                    if response.status_code == 200:
                        turn_data = response.json()
                        if "username" in turn_data and "credential" in turn_data:
                            backup_turn_servers = [{
                                "urls": turn_data.get("urls", ["turn:a.relay.metered.ca:80"]),
                                "username": turn_data["username"],
                                "credential": turn_data["credential"]
                            }]
                            logger.info("Successfully obtained ephemeral TURN credentials")
                except Exception as e:
                    logger.warning(f"Failed to get TURN credentials: {e}")
            except ImportError:
                logger.warning("Requests library not available, skipping TURN server setup")
        
        # Combine all servers based on configuration
        if ice_servers:
            # Use user-provided servers
            self.ice_servers = ice_servers
        else:
            # Start with primary servers
            self.ice_servers = primary_stun_servers.copy()
            
            # Add backup servers if enabled
            if backup_servers:
                self.ice_servers.extend(fallback_stun_servers)
                self.ice_servers.extend(geographic_stun_servers)
                
                # Add TURN servers if we have them (and resilience is enabled)
                if enable_resilience and backup_turn_servers:
                    self.ice_servers.extend(backup_turn_servers)
        
        # Store WebRTC configuration 
        self.ice_transport_policy = ice_transport_policy
        self.bundle_policy = bundle_policy
        self.rtcp_mux_policy = rtcp_mux_policy
        self.sdp_semantics = sdp_semantics
        
        # Connection behavior configuration
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.timeout = timeout
        
        # Feature flags
        self.enable_metrics = enable_metrics
        self.enable_security = enable_security
        self.enable_auto_quality = enable_auto_quality
        self.enable_resilience = enable_resilience
        
        # Enhanced ICE configuration
        self.ice_candidate_timeout = ice_candidate_timeout
        self.ice_gathering_timeout = ice_gathering_timeout  
        self.ice_connectivity_timeout = ice_connectivity_timeout
        self.use_ice_tcp = use_ice_tcp
        
        # Codec preferences
        self.preferred_codecs = preferred_codecs or {
            "video": ["VP8", "H264", "VP9", "AV1"],
            "audio": ["OPUS", "G722", "PCMU", "PCMA"]
        }
        
        # Logging configuration
        self.log_level = log_level
        
        # Configure resilience features
        if enable_resilience:
            # Increase reconnection attempts for better resilience
            self.reconnect_attempts = max(self.reconnect_attempts, 5)
            
            # Use exponential backoff for reconnection
            self.reconnect_backoff_factor = 1.5
            self.reconnect_max_delay = 15.0  # Maximum delay in seconds
            
            # Enable keep-alive pings
            self.enable_keepalive = True
            self.keepalive_interval = 15  # seconds
            
            # Set failure detection thresholds
            self.max_consecutive_failures = 3
            self.recovery_threshold = 2
            
            # Circuit breaker pattern to avoid overwhelming the network
            self.circuit_breaker_failures = 5
            self.circuit_breaker_reset_time = 30  # seconds
        else:
            # Default values for non-resilience mode
            self.reconnect_backoff_factor = 1.0
            self.reconnect_max_delay = self.reconnect_delay
            self.enable_keepalive = False
            self.keepalive_interval = 0
            self.max_consecutive_failures = 0
            self.recovery_threshold = 0
            self.circuit_breaker_failures = 0
            self.circuit_breaker_reset_time = 0
        
    def get_rtc_configuration(self):
        """Get RTCConfiguration object for aiortc."""
        config = {
            "iceServers": self.ice_servers,
            "iceTransportPolicy": self.ice_transport_policy,
            "bundlePolicy": self.bundle_policy,
            "rtcpMuxPolicy": self.rtcp_mux_policy,
            "sdpSemantics": self.sdp_semantics
        }
        
        # Add advanced ICE configuration
        if hasattr(self, 'ice_candidate_timeout'):
            config["iceCandidatePoolSize"] = 5  # Pre-gather ICE candidates
            
            # Add experimental properties if supported by the browser
            # Note: These are not standard WebRTC properties but are used by some implementations
            config["gatherPolicy"] = "all"
            config["iceConnectionTimeout"] = self.ice_connectivity_timeout
            
            # Enable TCP candidates if requested
            if self.use_ice_tcp:
                config["enableTcpCandidates"] = True
        
        return config
        
    def get_preferred_codecs(self, kind):
        """Get preferred codecs for a specific media kind."""
        if kind in self.preferred_codecs:
            return self.preferred_codecs[kind]
        return []
        
    def generate_connection_id(self):
        """Generate a unique connection ID with timestamp for better tracking."""
        timestamp = int(time.time())
        random_part = uuid.uuid4().hex[:8]
        return f"conn-{timestamp}-{random_part}"
    
    def calculate_reconnect_delay(self, attempt):
        """Calculate reconnection delay with exponential backoff."""
        if not self.enable_resilience:
            return self.reconnect_delay
            
        # Exponential backoff with jitter
        delay = min(
            self.reconnect_delay * (self.reconnect_backoff_factor ** (attempt - 1)),
            self.reconnect_max_delay
        )
        
        # Add jitter (±10%) to avoid thundering herd problem
        jitter = delay * 0.1
        delay = delay + random.uniform(-jitter, jitter)
        
        return max(0.5, delay)  # Ensure minimum delay of 0.5 seconds
        
    @classmethod
    def get_optimal_config(cls):
        """Get an optimized configuration based on system capabilities and network conditions."""
        config = cls(enable_resilience=True)
        
        # Detect system capabilities and optimize accordingly
        system = platform.system().lower()
        
        # Optimize for different platforms
        if system == "linux":
            # Linux typically has better UDP support
            config.ice_transport_policy = "all"
        elif system == "windows":
            # Windows may need more STUN servers for reliable connectivity
            config.ice_servers.append({"urls": ["stun:stun2.l.google.com:19302"]})
            config.ice_servers.append({"urls": ["stun:stun3.l.google.com:19302"]})
            # Some Windows networks may have issues with UDP
            config.use_ice_tcp = True
        elif system == "darwin":  # macOS
            # macOS may benefit from TCP candidates in some network configurations
            config.use_ice_tcp = True
        
        # Check for IPv6 support and add IPv6 STUN servers if available
        if socket.has_ipv6:
            config.ice_servers.append({"urls": ["stun:stun6.l.google.com:19302"]})
        
        # Try to detect network conditions
        try:
            # Check for restrictive networks (corporate, university, etc.)
            restrictive_network = cls._detect_restrictive_network()
            if restrictive_network:
                logger.info("Detected restrictive network, enabling additional resilience features")
                # Increase timeouts and prefer TCP on restrictive networks
                config.ice_candidate_timeout = 8000
                config.ice_gathering_timeout = 8000
                config.ice_connectivity_timeout = 15000
                config.use_ice_tcp = True
                
                # Try to get free TURN servers with ephemeral credentials
                # This will work for example purposes, but for production
                # you should use your own TURN service
                try:
                    import requests
                    turn_url = "https://metered.ca/api/v1/turn/credentials?apiKey=ccafe87gcaac89vofpfk"
                    response = requests.get(turn_url)
                    if response.status_code == 200:
                        turn_data = response.json()
                        if "username" in turn_data and "credential" in turn_data:
                            config.ice_servers.append({
                                "urls": turn_data.get("urls", ["turn:a.relay.metered.ca:80"]),
                                "username": turn_data["username"],
                                "credential": turn_data["credential"]
                            })
                except Exception:
                    # Silently continue if we can't get TURN credentials
                    pass
        except Exception as e:
            logger.warning(f"Error detecting network conditions: {e}")
        
        return config
    
    @staticmethod
    def _detect_restrictive_network():
        """
        Attempt to detect if we're on a restrictive network.
        
        Returns:
            Boolean indicating if we're on a restrictive network
        """
        # Try to connect to a few common ports to see if they're blocked
        test_endpoints = [
            ("stun.l.google.com", 19302),  # STUN
            ("1.1.1.1", 53),              # DNS
            ("meet.jit.si", 443)          # WebRTC service
        ]
        
        restrictive = False
        
        for host, port in test_endpoints:
            try:
                # Try to create a socket connection with a short timeout
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                sock.connect((host, port))
                sock.close()
            except (socket.timeout, socket.error):
                # If we can't connect to these common services, we might be on a restrictive network
                restrictive = True
                break
                
        return restrictive


@contextmanager
def webrtc_error_handling(operation_name):
    """Context manager for standardized WebRTC error handling."""
    try:
        yield
    except Exception as e:
        error_info = {
            "operation": operation_name,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": time.time(),
            "traceback": traceback.format_exc()
        }
        
        # Log the error
        logger.error(f"WebRTC error in {operation_name}: {e}")
        
        # Add to error history
        last_webrtc_errors.append(error_info)
        if len(last_webrtc_errors) > MAX_ERROR_HISTORY:
            last_webrtc_errors.pop(0)
        
        # Re-raise the exception
        raise


@dataclass
class WebRTCFrameStat:
    """Statistics for a single frame's processing and delivery."""
    
    timestamp: float = field(default_factory=time.time)
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    size_bytes: int = 0
    codec: str = ""
    encode_start_time: Optional[float] = None
    encode_end_time: Optional[float] = None
    send_start_time: Optional[float] = None
    send_end_time: Optional[float] = None
    receive_time: Optional[float] = None
    decode_start_time: Optional[float] = None
    decode_end_time: Optional[float] = None
    render_time: Optional[float] = None
    
    # Derived metrics (computed on demand)
    @property
    def encode_time_ms(self) -> Optional[float]:
        """Time taken to encode the frame in milliseconds."""
        if self.encode_start_time and self.encode_end_time:
            return (self.encode_end_time - self.encode_start_time) * 1000
        return None
    
    @property
    def transfer_time_ms(self) -> Optional[float]:
        """Time taken to transfer the frame over the network in milliseconds."""
        if self.send_start_time and self.receive_time:
            return (self.receive_time - self.send_start_time) * 1000
        return None
    
    @property
    def decode_time_ms(self) -> Optional[float]:
        """Time taken to decode the frame in milliseconds."""
        if self.decode_start_time and self.decode_end_time:
            return (self.decode_end_time - self.decode_start_time) * 1000
        return None
    
    @property
    def total_latency_ms(self) -> Optional[float]:
        """Total end-to-end latency for the frame in milliseconds."""
        if self.encode_start_time and self.render_time:
            return (self.render_time - self.encode_start_time) * 1000
        return None


class WebRTCBenchmark:
    """Comprehensive benchmarking system for WebRTC streaming performance.
    
    This class enables detailed performance benchmarking of WebRTC connections,
    providing insights into network conditions, codec efficiency, latency,
    and resource utilization.
    
    Features:
    - Connection establishment timing
    - Network throughput and stability analysis
    - Video codec performance benchmarking
    - End-to-end latency measurement
    - Resource utilization tracking (CPU, memory, bandwidth)
    - Quality of Experience metrics
    - Regression testing capabilities
    - Automatic report generation
    
    The benchmarking system operates with minimal performance impact on the 
    actual streaming process and can be enabled/disabled as needed.
    """
    
    def __init__(self, 
                 connection_id: str, 
                 cid: str,
                 enable_frame_stats: bool = True,
                 max_frame_stats: int = 1000,
                 interval_ms: int = 500,
                 report_dir: Optional[str] = None):
        """
        Initialize a new benchmark session for a WebRTC connection.
        
        Args:
            connection_id: Unique ID of the WebRTC connection
            cid: Content ID being streamed
            enable_frame_stats: Whether to collect per-frame statistics
            max_frame_stats: Maximum number of frame stats to keep in memory
            interval_ms: Interval between periodic measurements in milliseconds
            report_dir: Directory to save benchmark reports
        """
        # Connection information
        self.connection_id = connection_id
        self.cid = cid
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        
        # Configuration
        self.enable_frame_stats = enable_frame_stats
        self.max_frame_stats = max_frame_stats
        self.interval_ms = interval_ms
        self.report_dir = report_dir
        
        # Create report directory if specified
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        
        # Basic metrics
        self.connection_metrics = {
            "ice_gathering_time_ms": None,
            "ice_connection_time_ms": None,
            "dtls_setup_time_ms": None,
            "first_frame_time_ms": None,
            "reconnection_count": 0,
            "reconnection_times_ms": [],
            "ice_candidate_counts": {
                "host": 0,
                "srflx": 0,
                "prflx": 0,
                "relay": 0
            }
        }
        
        # Detailed time series metrics
        self.time_series = {
            "timestamps": [],
            "rtt_ms": [],
            "jitter_ms": [],
            "packet_loss_percent": [],
            "bitrate_kbps": [],
            "available_bitrate_kbps": [],
            "frames_per_second": [],
            "resolution_width": [],
            "resolution_height": [],
            "cpu_percent": [],
            "quality_score": []
        }
        
        # Frame statistics
        self.frame_stats: List[WebRTCFrameStat] = []
        self.frame_count = 0
        self.keyframe_count = 0
        
        # Network stats
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_lost = 0
        
        # Codec information
        self.video_codec = ""
        self.audio_codec = ""
        self.video_parameters = {}
        self.audio_parameters = {}
        
        # Internal state
        self._active = True
        self._task = None
        self._lock = asyncio.Lock()
        
        # Start the benchmark
        logger.info(f"Starting WebRTC benchmark for connection {connection_id}")
    
    async def start_monitoring(self):
        """Start the periodic monitoring task."""
        if self._task is None:
            self._task = asyncio.create_task(self._monitoring_task())
            logger.debug(f"Benchmark monitoring started for connection {self.connection_id}")
    
    async def stop(self):
        """Stop the benchmark and finalize measurements."""
        if not self._active:
            return
            
        self._active = False
        self.end_time = time.time()
        
        # Cancel the monitoring task if it exists
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        # Generate final report
        if self.report_dir:
            await self.generate_report()
            
        logger.info(f"Benchmark stopped for connection {self.connection_id} after " 
                   f"{self.end_time - self.start_time:.2f} seconds")
    
    async def _monitoring_task(self):
        """Background task for periodic metric collection."""
        try:
            while self._active:
                await self._collect_periodic_metrics()
                await asyncio.sleep(self.interval_ms / 1000)
        except asyncio.CancelledError:
            logger.debug(f"Benchmark monitoring task cancelled for {self.connection_id}")
            raise
        except Exception as e:
            logger.error(f"Error in benchmark monitoring task: {e}")
    
    async def _collect_periodic_metrics(self):
        """Collect periodic metrics at regular intervals."""
        # This will be called by the monitoring task
        # Actual implementation will depend on integration with WebRTCStreamingManager
        pass
    
    def record_connection_event(self, event_type: str, data: Dict[str, Any]):
        """
        Record a connection lifecycle event.
        
        Args:
            event_type: Type of event (e.g., 'ice_candidate', 'connected', 'first_frame')
            data: Event-specific data
        """
        now = time.time()
        
        if event_type == "ice_gathering_start":
            # Mark the start of ICE gathering
            self._ice_gathering_start = now
            
        elif event_type == "ice_gathering_complete":
            # Record ICE gathering time
            if hasattr(self, "_ice_gathering_start"):
                self.connection_metrics["ice_gathering_time_ms"] = (now - self._ice_gathering_start) * 1000
        
        elif event_type == "ice_connection_start":
            # Mark the start of ICE connection establishment
            self._ice_connection_start = now
            
        elif event_type == "ice_connected":
            # Record ICE connection time
            if hasattr(self, "_ice_connection_start"):
                self.connection_metrics["ice_connection_time_ms"] = (now - self._ice_connection_start) * 1000
        
        elif event_type == "dtls_start":
            # Mark the start of DTLS handshake
            self._dtls_start = now
            
        elif event_type == "dtls_connected":
            # Record DTLS setup time
            if hasattr(self, "_dtls_start"):
                self.connection_metrics["dtls_setup_time_ms"] = (now - self._dtls_start) * 1000
        
        elif event_type == "first_frame":
            # Record time to first frame
            self.connection_metrics["first_frame_time_ms"] = (now - self.start_time) * 1000
        
        elif event_type == "reconnection":
            # Record reconnection event
            self.connection_metrics["reconnection_count"] += 1
            if "duration_ms" in data:
                self.connection_metrics["reconnection_times_ms"].append(data["duration_ms"])
        
        elif event_type == "ice_candidate":
            # Count ICE candidate types
            if "candidate_type" in data:
                candidate_type = data["candidate_type"]
                if candidate_type in self.connection_metrics["ice_candidate_counts"]:
                    self.connection_metrics["ice_candidate_counts"][candidate_type] += 1
                    
        elif event_type == "codec_selected":
            # Record codec information
            if "kind" in data:
                if data["kind"] == "video":
                    self.video_codec = data.get("codec", "")
                    self.video_parameters = data.get("parameters", {})
                elif data["kind"] == "audio":
                    self.audio_codec = data.get("codec", "")
                    self.audio_parameters = data.get("parameters", {})
    
    def update_stats(self, stats: Dict[str, Any]):
        """
        Update benchmark with current WebRTC stats.
        
        Args:
            stats: WebRTC stats dictionary containing network and media metrics
        """
        # Record timestamp
        now = time.time()
        self.time_series["timestamps"].append(now)
        
        # Extract metrics from stats
        rtt_ms = stats.get("rtt", 0)
        jitter_ms = stats.get("jitter", 0)
        packet_loss = stats.get("packet_loss", 0)
        bitrate = stats.get("bitrate", 0) / 1000  # Convert to kbps
        available_bitrate = stats.get("bandwidth_estimate", 0) / 1000  # Convert to kbps
        fps = stats.get("frames_per_second", 0)
        width = stats.get("resolution_width", 0)
        height = stats.get("resolution_height", 0)
        cpu = stats.get("cpu_percent", 0)
        
        # Calculate quality score (simple weighted formula)
        # Lower RTT, jitter, and packet loss are better; higher bitrate is better
        quality_score = 0
        if rtt_ms > 0 and jitter_ms > 0 and bitrate > 0:
            # Normalize metrics to 0-1 scale
            normalized_rtt = min(1.0, rtt_ms / 500)  # 500ms or higher = 1.0
            normalized_jitter = min(1.0, jitter_ms / 100)  # 100ms or higher = 1.0
            normalized_loss = min(1.0, packet_loss / 10)  # 10% or higher = 1.0
            normalized_bitrate = min(1.0, bitrate / 4000)  # 4Mbps or higher = 1.0
            
            # Compute quality score (0-100)
            quality_score = 100 * (
                0.3 * (1 - normalized_rtt) +
                0.2 * (1 - normalized_jitter) +
                0.3 * (1 - normalized_loss) +
                0.2 * normalized_bitrate
            )
        
        # Update cumulative stats
        self.bytes_sent += stats.get("bytes_sent_delta", 0)
        self.bytes_received += stats.get("bytes_received_delta", 0)
        self.packets_sent += stats.get("packets_sent_delta", 0)
        self.packets_received += stats.get("packets_received_delta", 0)
        self.packets_lost += stats.get("packets_lost_delta", 0)
        
        # Update time series
        self.time_series["rtt_ms"].append(rtt_ms)
        self.time_series["jitter_ms"].append(jitter_ms)
        self.time_series["packet_loss_percent"].append(packet_loss)
        self.time_series["bitrate_kbps"].append(bitrate)
        self.time_series["available_bitrate_kbps"].append(available_bitrate)
        self.time_series["frames_per_second"].append(fps)
        self.time_series["resolution_width"].append(width)
        self.time_series["resolution_height"].append(height)
        self.time_series["cpu_percent"].append(cpu)
        self.time_series["quality_score"].append(quality_score)
    
    def add_frame_stat(self, frame_stat: WebRTCFrameStat):
        """
        Add a new frame statistic to the benchmark.
        
        Args:
            frame_stat: Statistics for a single frame
        """
        if not self.enable_frame_stats:
            return
            
        # Add to frame stats list, respecting maximum limit
        self.frame_stats.append(frame_stat)
        if len(self.frame_stats) > self.max_frame_stats:
            self.frame_stats.pop(0)  # Remove oldest stat
        
        # Update frame counters
        self.frame_count += 1
        
        # Update keyframe counter if this is a keyframe
        if frame_stat.size_bytes > 0 and hasattr(frame_stat, 'is_keyframe') and frame_stat.is_keyframe:
            self.keyframe_count += 1
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get a summary of important benchmark statistics.
        
        Returns:
            Dictionary with summary statistics
        """
        duration = (self.end_time or time.time()) - self.start_time
        
        # Calculate average values for time series metrics
        avg_rtt = statistics.mean(self.time_series["rtt_ms"]) if self.time_series["rtt_ms"] else 0
        avg_jitter = statistics.mean(self.time_series["jitter_ms"]) if self.time_series["jitter_ms"] else 0
        avg_loss = statistics.mean(self.time_series["packet_loss_percent"]) if self.time_series["packet_loss_percent"] else 0
        avg_bitrate = statistics.mean(self.time_series["bitrate_kbps"]) if self.time_series["bitrate_kbps"] else 0
        avg_fps = statistics.mean(self.time_series["frames_per_second"]) if self.time_series["frames_per_second"] else 0
        avg_quality = statistics.mean(self.time_series["quality_score"]) if self.time_series["quality_score"] else 0
        
        # Calculate latency metrics from frame stats
        frame_latencies = [fs.total_latency_ms for fs in self.frame_stats if fs.total_latency_ms is not None]
        avg_latency = statistics.mean(frame_latencies) if frame_latencies else None
        p50_latency = statistics.median(frame_latencies) if frame_latencies else None
        p95_latency = None
        if frame_latencies:
            frame_latencies.sort()
            p95_index = int(0.95 * len(frame_latencies))
            p95_latency = frame_latencies[p95_index]
        
        # Throughput calculations
        bytes_per_second = self.bytes_sent / duration if duration > 0 else 0
        
        return {
            "connection_id": self.connection_id,
            "cid": self.cid,
            "duration_sec": duration,
            "ice_gathering_time_ms": self.connection_metrics["ice_gathering_time_ms"],
            "ice_connection_time_ms": self.connection_metrics["ice_connection_time_ms"],
            "first_frame_time_ms": self.connection_metrics["first_frame_time_ms"],
            "reconnection_count": self.connection_metrics["reconnection_count"],
            "avg_rtt_ms": avg_rtt,
            "avg_jitter_ms": avg_jitter,
            "avg_packet_loss_percent": avg_loss,
            "avg_bitrate_kbps": avg_bitrate,
            "avg_frames_per_second": avg_fps,
            "total_frames": self.frame_count,
            "keyframe_ratio": self.keyframe_count / self.frame_count if self.frame_count > 0 else 0,
            "avg_end_to_end_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "throughput_bytes_per_sec": bytes_per_second,
            "throughput_mbps": bytes_per_second * 8 / 1_000_000,
            "packet_loss_rate": self.packets_lost / max(1, self.packets_sent + self.packets_received),
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "avg_quality_score": avg_quality,
            "ice_candidates": self.connection_metrics["ice_candidate_counts"]
        }
    
    async def generate_report(self) -> str:
        """
        Generate a comprehensive benchmark report.
        
        Returns:
            Path to the saved report file
        """
        if not self.report_dir:
            logger.warning("Cannot generate report: report_dir not specified")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.report_dir, f"webrtc_benchmark_{self.connection_id}_{timestamp}.json")
        
        # Prepare summary report
        summary = self.get_summary_stats()
        
        # Add time series data
        time_series = {
            key: value for key, value in self.time_series.items()
            if key != "timestamps"  # Exclude raw timestamps
        }
        
        # Add connection events timeline
        events = []
        if self.connection_metrics["ice_gathering_time_ms"]:
            events.append({
                "event": "ICE Gathering Complete",
                "time_ms": self.connection_metrics["ice_gathering_time_ms"]
            })
        if self.connection_metrics["ice_connection_time_ms"]:
            events.append({
                "event": "ICE Connected",
                "time_ms": self.connection_metrics["ice_connection_time_ms"]
            })
        if self.connection_metrics["dtls_setup_time_ms"]:
            events.append({
                "event": "DTLS Connected",
                "time_ms": self.connection_metrics["dtls_setup_time_ms"]
            })
        if self.connection_metrics["first_frame_time_ms"]:
            events.append({
                "event": "First Frame",
                "time_ms": self.connection_metrics["first_frame_time_ms"]
            })
        
        # Full report structure
        report = {
            "summary": summary,
            "time_series": time_series,
            "events": events,
            "config": {
                "enable_frame_stats": self.enable_frame_stats,
                "max_frame_stats": self.max_frame_stats,
                "interval_ms": self.interval_ms
            }
        }
        
        # Write report to file
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Benchmark report saved to {report_file}")
        return report_file
    
    @staticmethod
    async def compare_benchmarks(benchmark1: str, benchmark2: str) -> Dict[str, Any]:
        """
        Compare two benchmark reports and generate a comparison report.
        
        Args:
            benchmark1: Path to first benchmark report
            benchmark2: Path to second benchmark report
            
        Returns:
            Dictionary with comparison metrics
        """
        # Load benchmark reports
        try:
            with open(benchmark1, 'r') as f1:
                report1 = json.load(f1)
                
            with open(benchmark2, 'r') as f2:
                report2 = json.load(f2)
                
            summary1 = report1["summary"]
            summary2 = report2["summary"]
            
            # Calculate differences and percentage changes
            comparison = {}
            for key in summary1:
                if key in summary2 and isinstance(summary1[key], (int, float)) and summary1[key] != 0:
                    difference = summary2[key] - summary1[key]
                    percent_change = (difference / summary1[key]) * 100
                    
                    comparison[key] = {
                        "baseline": summary1[key],
                        "current": summary2[key],
                        "difference": difference,
                        "percent_change": percent_change,
                        "regression": WebRTCBenchmark._is_regression(key, percent_change)
                    }
            
            # Generate regression indicators
            regressions = [k for k, v in comparison.items() if v.get("regression", False)]
            improvements = [k for k, v in comparison.items() 
                          if "regression" in v and v["percent_change"] != 0 and not v["regression"]]
            
            # Overall assessment
            if len(regressions) > len(improvements):
                assessment = "Performance regression detected"
            elif len(improvements) > len(regressions):
                assessment = "Performance improvement detected"
            else:
                assessment = "Performance unchanged"
                
            return {
                "comparison": comparison,
                "regressions": regressions,
                "improvements": improvements,
                "assessment": assessment
            }
            
        except Exception as e:
            logger.error(f"Error comparing benchmarks: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _is_regression(metric: str, percent_change: float) -> bool:
        """
        Determine if a metric change represents a regression.
        
        Args:
            metric: Metric name
            percent_change: Percentage change in the metric
            
        Returns:
            Boolean indicating if this is a regression
        """
        # Define which direction is a regression for each metric
        regression_if_increases = {
            "ice_gathering_time_ms", "ice_connection_time_ms", "first_frame_time_ms",
            "reconnection_count", "avg_rtt_ms", "avg_jitter_ms", "avg_packet_loss_percent",
            "p50_latency_ms", "p95_latency_ms", "keyframe_ratio", "avg_end_to_end_latency_ms",
            "packet_loss_rate"
        }
        
        regression_if_decreases = {
            "avg_bitrate_kbps", "avg_frames_per_second", "throughput_bytes_per_sec",
            "throughput_mbps", "avg_quality_score"
        }
        
        # Threshold for significant change (5%)
        threshold = 5.0
        
        if abs(percent_change) < threshold:
            return False  # Change not significant enough
            
        if metric in regression_if_increases and percent_change > 0:
            return True
            
        if metric in regression_if_decreases and percent_change < 0:
            return True
            
        return False


class AdaptiveBitrateController:
    """Manages adaptive bitrate for WebRTC streaming based on network conditions."""
    
    def __init__(self, initial_quality="medium"):
        """
        Initialize the adaptive bitrate controller.
        
        Args:
            initial_quality: Starting quality level ("low", "medium", "high", "auto")
        """
        # Define quality presets with resolution, bitrate, and frame rate
        self.quality_levels = {
            "very_low": {"width": 320, "height": 240, "bitrate": 250_000, "frame_rate": 15},
            "low": {"width": 640, "height": 360, "bitrate": 500_000, "frame_rate": 20},
            "medium": {"width": 854, "height": 480, "bitrate": 1_000_000, "frame_rate": 30},
            "high": {"width": 1280, "height": 720, "bitrate": 2_500_000, "frame_rate": 30},
            "very_high": {"width": 1920, "height": 1080, "bitrate": 4_500_000, "frame_rate": 30}
        }
        
        # Ordered list of quality levels for stepping up/down
        self.quality_order = ["very_low", "low", "medium", "high", "very_high"]
        
        # Set initial quality level
        self.current_quality = initial_quality if initial_quality in self.quality_levels else "medium"
        self.current_settings = self.quality_levels[self.current_quality].copy()
        
        # State management
        self.auto_mode = (initial_quality == "auto")
        self.last_adaptation = time.time()
        self.adaptation_interval = 5.0  # Seconds between adaptation checks
        self.stability_threshold = 3    # Number of consistent readings before changing quality
        
        # Metrics tracking
        self.metrics_window = []        # Window of recent network metrics
        self.window_size = 30           # Number of metrics to keep
        self.up_count = 0               # Counter for potential quality increases
        self.down_count = 0             # Counter for potential quality decreases
        
        # Network thresholds for adaptation decisions
        self.thresholds = {
            "rtt": {                    # Round-trip time thresholds (ms)
                "excellent": 100,
                "good": 200,
                "fair": 300,
                "poor": 500
            },
            "packet_loss": {            # Packet loss thresholds (percentage)
                "excellent": 0.5,
                "good": 2.0,
                "fair": 5.0,
                "poor": 10.0
            },
            "bandwidth": {              # Available bandwidth thresholds (bps)
                "excellent": 5_000_000,
                "good": 2_500_000,
                "fair": 1_000_000,
                "poor": 500_000
            },
            "jitter": {                 # Jitter thresholds (ms)
                "excellent": 20,
                "good": 50,
                "fair": 100,
                "poor": 200
            }
        }
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def add_metrics(self, metrics):
        """
        Add network metrics to the controller for adaptation decisions.
        
        Args:
            metrics: Dictionary with network metrics (rtt, packet_loss, bandwidth, jitter)
        """
        # Add timestamp to metrics
        metrics["timestamp"] = time.time()
        
        # Add to metrics window
        self.metrics_window.append(metrics)
        
        # Keep window at specified size
        if len(self.metrics_window) > self.window_size:
            self.metrics_window = self.metrics_window[-self.window_size:]
        
        # Check if it's time to adapt
        if self.auto_mode and (time.time() - self.last_adaptation) > self.adaptation_interval:
            self._adapt_quality()
            self.last_adaptation = time.time()
    
    def set_quality(self, quality):
        """
        Manually set quality level.
        
        Args:
            quality: Quality level ("very_low", "low", "medium", "high", "very_high", "auto")
            
        Returns:
            Dictionary with the new quality settings
        """
        if quality == "auto":
            self.auto_mode = True
            # Immediate adaptation
            self._adapt_quality()
        elif quality in self.quality_levels:
            self.auto_mode = False
            self.current_quality = quality
            self.current_settings = self.quality_levels[quality].copy()
        else:
            self.logger.warning(f"Unknown quality level: {quality}")
            return self.current_settings
        
        self.logger.info(f"Quality set to: {self.current_quality}")
        return self.current_settings
    
    def get_current_settings(self):
        """
        Get current quality settings.
        
        Returns:
            Dictionary with current quality settings
        """
        return {
            "quality_level": self.current_quality,
            "auto_mode": self.auto_mode,
            "settings": self.current_settings,
            "metrics": self._calculate_average_metrics() if self.metrics_window else {}
        }
    
    def _adapt_quality(self):
        """Adapt quality based on current network conditions."""
        if not self.auto_mode or len(self.metrics_window) < 3:
            return
        
        # Calculate average metrics
        avg_metrics = self._calculate_average_metrics()
        
        # Score current network conditions
        network_score = self._calculate_network_score(avg_metrics)
        
        # Determine if we should change quality
        current_index = self.quality_order.index(self.current_quality)
        
        if network_score >= 80:  # Excellent conditions
            self.up_count += 1
            self.down_count = 0
            if self.up_count >= self.stability_threshold and current_index < len(self.quality_order) - 1:
                # Increase quality
                new_quality = self.quality_order[current_index + 1]
                self.logger.info(f"Increasing quality to {new_quality} (score: {network_score})")
                self.current_quality = new_quality
                self.current_settings = self.quality_levels[new_quality].copy()
                self.up_count = 0
        elif network_score <= 40:  # Poor conditions
            self.down_count += 1
            self.up_count = 0
            if self.down_count >= self.stability_threshold and current_index > 0:
                # Decrease quality
                new_quality = self.quality_order[current_index - 1]
                self.logger.info(f"Decreasing quality to {new_quality} (score: {network_score})")
                self.current_quality = new_quality
                self.current_settings = self.quality_levels[new_quality].copy()
                self.down_count = 0
        else:
            # Reset counters when in middle range
            self.up_count = 0
            self.down_count = 0
    
    def _calculate_average_metrics(self):
        """Calculate average values for each metric in the window."""
        if not self.metrics_window:
            return {}
        
        avg_metrics = {
            "rtt": 0,
            "packet_loss": 0,
            "bandwidth": 0,
            "jitter": 0
        }
        
        # Count valid readings for each metric
        counts = {metric: 0 for metric in avg_metrics}
        
        # Sum all valid metrics
        for reading in self.metrics_window:
            for metric in avg_metrics:
                if metric in reading and reading[metric] is not None:
                    avg_metrics[metric] += reading[metric]
                    counts[metric] += 1
        
        # Calculate averages
        for metric in avg_metrics:
            if counts[metric] > 0:
                avg_metrics[metric] /= counts[metric]
        
        return avg_metrics
    
    def _calculate_network_score(self, metrics):
        """
        Calculate a network score from 0-100 based on metrics.
        
        Args:
            metrics: Dictionary with averaged network metrics
            
        Returns:
            Integer score from 0-100 (higher is better)
        """
        score = 100  # Start with perfect score
        
        # Apply penalties based on each metric
        if "rtt" in metrics and metrics["rtt"] > 0:
            rtt = metrics["rtt"]
            if rtt > self.thresholds["rtt"]["poor"]:
                score -= 40
            elif rtt > self.thresholds["rtt"]["fair"]:
                score -= 20
            elif rtt > self.thresholds["rtt"]["good"]:
                score -= 10
            elif rtt > self.thresholds["rtt"]["excellent"]:
                score -= 5
        
        if "packet_loss" in metrics and metrics["packet_loss"] > 0:
            loss = metrics["packet_loss"]
            if loss > self.thresholds["packet_loss"]["poor"]:
                score -= 50  # Heavy penalty for significant packet loss
            elif loss > self.thresholds["packet_loss"]["fair"]:
                score -= 30
            elif loss > self.thresholds["packet_loss"]["good"]:
                score -= 15
            elif loss > self.thresholds["packet_loss"]["excellent"]:
                score -= 5
        
        if "bandwidth" in metrics and metrics["bandwidth"] > 0:
            bandwidth = metrics["bandwidth"]
            if bandwidth < self.thresholds["bandwidth"]["poor"]:
                score -= 30
            elif bandwidth < self.thresholds["bandwidth"]["fair"]:
                score -= 20
            elif bandwidth < self.thresholds["bandwidth"]["good"]:
                score -= 10
            elif bandwidth < self.thresholds["bandwidth"]["excellent"]:
                score -= 5
        
        if "jitter" in metrics and metrics["jitter"] > 0:
            jitter = metrics["jitter"]
            if jitter > self.thresholds["jitter"]["poor"]:
                score -= 20
            elif jitter > self.thresholds["jitter"]["fair"]:
                score -= 15
            elif jitter > self.thresholds["jitter"]["good"]:
                score -= 10
            elif jitter > self.thresholds["jitter"]["excellent"]:
                score -= 5
        
        # Ensure score stays in range 0-100
        return max(0, min(100, score))


class StreamBuffer:
    """
    Advanced buffer management for media streaming with adaptive behavior.
    
    This buffer manages frame queuing, playback timing, and provides
    adaptation capabilities for different network conditions.
    """
    
    def __init__(self, max_size=30, target_duration=2.0, min_duration=0.5, max_duration=5.0):
        """
        Initialize the stream buffer.
        
        Args:
            max_size: Maximum number of frames in the buffer
            target_duration: Target buffer size in seconds
            min_duration: Minimum buffer duration before playback
            max_duration: Maximum buffer duration before throttling
        """
        self.max_size = max_size
        self.target_duration = target_duration
        self.min_duration = min_duration
        self.max_duration = max_duration
        
        # Main buffer
        self.buffer = asyncio.Queue(maxsize=max_size)
        
        # Buffer state tracking
        self.buffer_duration = 0.0
        self.frame_count = 0
        self.total_frames_added = 0
        self.total_frames_consumed = 0
        self.dropped_frames = 0
        self.last_frame_time = None
        
        # Frame timing tracking
        self.frame_times = []
        self.max_frame_times = 30  # Number of frame times to keep for averaging
        
        # Event for signaling buffer readiness
        self.playback_ready = asyncio.Event()
        
        # Control flow with throttling
        self.throttle_input = asyncio.Event()
        self.throttle_input.set()  # Start unthrottled
        
        # Monitoring
        self.last_stats_time = time.time()
        self.stats = {
            "buffer_level": 0,
            "buffer_duration": 0,
            "frame_rate": 0,
            "latency": 0,
            "drops_per_minute": 0
        }
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    async def add_frame(self, frame, key_frame=False):
        """
        Add a frame to the buffer.
        
        Args:
            frame: The frame to add
            key_frame: Whether this is a key frame (higher priority)
            
        Returns:
            Boolean indicating whether the frame was added
        """
        # Wait if throttled, unless it's a key frame
        if not key_frame:
            await self.throttle_input.wait()
        
        # Calculate current buffer fullness
        buffer_fullness = self.buffer.qsize() / self.max_size
        
        # Handle buffer overflow
        if self.buffer.full():
            if key_frame:
                # Try to make room for key frame by dropping oldest frame
                try:
                    # This is a non-blocking get that will raise QueueEmpty if the buffer is actually empty
                    _ = self.buffer.get_nowait()
                    self.dropped_frames += 1
                except asyncio.QueueEmpty:
                    # Very rare race condition where buffer became empty
                    pass
            else:
                # Drop non-key frame if buffer is full
                self.dropped_frames += 1
                return False
        
        # Add frame to buffer
        try:
            await self.buffer.put(frame)
            self.total_frames_added += 1
            
            # Update frame timing
            now = time.time()
            if self.last_frame_time is not None:
                frame_time = now - self.last_frame_time
                self.frame_times.append(frame_time)
                # Keep frame times list bounded
                if len(self.frame_times) > self.max_frame_times:
                    self.frame_times = self.frame_times[-self.max_frame_times:]
            self.last_frame_time = now
            
            # Update buffer duration estimate
            self._update_buffer_duration()
            
            # Set playback_ready if buffer has reached minimum duration
            if self.buffer_duration >= self.min_duration and not self.playback_ready.is_set():
                self.playback_ready.set()
            
            # Throttle input if buffer exceeds maximum duration
            if self.buffer_duration > self.max_duration:
                self.throttle_input.clear()
            
            return True
            
        except asyncio.QueueFull:
            self.dropped_frames += 1
            return False
    
    async def get_frame(self):
        """
        Get a frame from the buffer when available.
        
        Returns:
            The next frame from the buffer
        """
        # Wait until playback is ready
        await self.playback_ready.wait()
        
        # Get frame from buffer
        try:
            frame = await self.buffer.get()
            self.total_frames_consumed += 1
            
            # Update buffer duration estimate
            self._update_buffer_duration()
            
            # Unthrottle input if buffer drops below target duration
            if self.buffer_duration < self.target_duration and not self.throttle_input.is_set():
                self.throttle_input.set()
            
            # Clear playback_ready if buffer is empty
            if self.buffer.empty():
                self.playback_ready.clear()
            
            return frame
            
        except Exception as e:
            self.logger.error(f"Error getting frame from buffer: {e}")
            raise
    
    def _update_buffer_duration(self):
        """Update the buffer duration estimate based on frame times."""
        # Calculate average frame time if we have data
        if self.frame_times:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            # Buffer duration = number of frames * average frame time
            self.buffer_duration = self.buffer.qsize() * avg_frame_time
        else:
            # Fallback estimate if no frame timing data available
            self.buffer_duration = self.buffer.qsize() / 30.0  # Assume 30fps
        
        # Update stats periodically
        now = time.time()
        if now - self.last_stats_time > 1.0:  # Update stats every second
            time_diff = now - self.last_stats_time
            self.stats["buffer_level"] = self.buffer.qsize() / self.max_size
            self.stats["buffer_duration"] = self.buffer_duration
            
            # Calculate frame rate
            frames_in_period = self.total_frames_added - self.frame_count
            self.stats["frame_rate"] = frames_in_period / time_diff
            
            # Calculate drops per minute
            self.stats["drops_per_minute"] = (self.dropped_frames / time_diff) * 60
            
            # Update latency estimate based on buffer fullness
            self.stats["latency"] = self.buffer_duration
            
            # Update frame count for next calculation
            self.frame_count = self.total_frames_added
            self.last_stats_time = now
    
    def get_stats(self):
        """
        Get buffer statistics.
        
        Returns:
            Dictionary with buffer statistics
        """
        return {
            "buffer_level": self.stats["buffer_level"],
            "buffer_duration": self.stats["buffer_duration"],
            "frame_rate": self.stats["frame_rate"],
            "latency": self.stats["latency"],
            "drops_per_minute": self.stats["drops_per_minute"],
            "total_frames_added": self.total_frames_added,
            "total_frames_consumed": self.total_frames_consumed,
            "dropped_frames": self.dropped_frames,
            "queue_size": self.buffer.qsize(),
            "playback_ready": self.playback_ready.is_set(),
            "throttled": not self.throttle_input.is_set()
        }
    
    def reset(self):
        """Reset the buffer state."""
        # Clear the buffer
        while not self.buffer.empty():
            try:
                self.buffer.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # Reset state
        self.buffer_duration = 0.0
        self.frame_count = 0
        self.playback_ready.clear()
        self.throttle_input.set()
        
        # Reset tracking stats but keep totals
        self.last_frame_time = None
        self.frame_times = []
        self.last_stats_time = time.time()


# Define IPFSMediaStreamTrack based on dependency availability
if HAVE_WEBRTC:
    class IPFSMediaStreamTrack(MediaStreamTrack):
        """MediaStreamTrack that sources content directly from IPFS."""
        
        kind = "video"  # Default kind, can be changed to "audio"
        
        def __init__(self, track=None, ipfs_api=None, cid=None, kind="video", frame_rate=30):
            """
            Initialize an IPFS media stream track.
            
            Args:
                track: Optional source track to relay
                ipfs_api: IPFS API instance for content retrieval
                cid: Content identifier for the media in IPFS
                kind: Track kind ("audio" or "video")
                frame_rate: Target frame rate for video tracks
            """
            super().__init__()
            self.track = track
            self.ipfs_api = ipfs_api
            self.cid = cid
            self.kind = kind
            self.frame_rate = frame_rate
            
            # Advanced buffer management
            self._buffer = StreamBuffer(
                max_size=60,  # Larger buffer for adaptivity
                target_duration=2.0,  # Target 2 seconds of buffer
                min_duration=0.5,  # Start playback after 0.5 seconds
                max_duration=5.0   # Maximum 5 seconds buffer before throttling
            )
            
            # Adaptive bitrate control
            self._bitrate_controller = AdaptiveBitrateController(initial_quality="auto")
            
            self._task = None
            self._start_time = None
            self._frame_count = 0
            self._content = None
            self._content_loaded = False
            self._stopped = False
            self._decoder = None
            
            # Statistics tracking
            self._last_timestamp = time.time()
            self._last_stats_update = time.time()
            self._stats = {
                "frames_sent": 0,
                "frames_dropped": 0,
                "bitrate": 0,
                "latency": 0,
                "buffer_level": 0,
                "quality_level": "medium",
                "network_score": 0
            }
            
            # Network metrics
            self._network_metrics = {
                "rtt": 0,
                "packet_loss": 0,
                "bandwidth": 0,
                "jitter": 0
            }
            
            # Start loading content if CID is provided
            if self.ipfs_api and self.cid:
                self._task = asyncio.create_task(self._load_content())
                
        async def _load_content(self):
            """Load content from IPFS and prepare it for streaming."""
            try:
                logger.info(f"Loading content from IPFS: {self.cid}")
                self._content = self.ipfs_api.cat(self.cid)
                
                # Create a temporary file to use with av
                temp_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "temp")
                os.makedirs(temp_dir, exist_ok=True)
                
                temp_file = os.path.join(temp_dir, f"{uuid.uuid4()}.mp4")
                with open(temp_file, "wb") as f:
                    f.write(self._content)
                
                # Initialize the decoder
                container = av.open(temp_file)
                if self.kind == "video":
                    stream = container.streams.video[0]
                else:
                    stream = container.streams.audio[0]
                
                self._decoder = container.decode(stream)
                self._content_loaded = True
                logger.info(f"Content loaded successfully: {self.cid}")
                
                # Start the frame generator
                asyncio.create_task(self._generate_frames())
                
                # Clean up temp file after loading
                os.unlink(temp_file)
                
            except Exception as e:
                logger.error(f"Error loading content from IPFS: {e}")
                self._stopped = True
else:
    # Stub implementation when dependencies are not available
    class IPFSMediaStreamTrack:
        """Stub implementation when WebRTC dependencies are not available."""
        
        kind = "video"  # Default kind
        
        def __init__(self, *args, **kwargs):
            """Stub initialization that raises an import error."""
            self.ended = Exception
            logger.error("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
            raise ImportError("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
            
        async def recv(self):
            """Stub recv method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        def stop(self):
            """Stub stop method."""
            pass
            
        async def _load_content(self):
            """Stub _load_content method."""
            raise NotImplementedError("WebRTC dependencies not available")
    
    
    async def _generate_frames(self):
        """Generate frames from the loaded content with adaptive quality and buffer management."""
        try:
            if not self._content_loaded or not self._decoder:
                logger.error("Cannot generate frames: content not loaded")
                return
            
            self._start_time = time.time()
            last_quality_check = time.time()
            
            # Get initial quality settings
            quality_settings = self._bitrate_controller.get_current_settings()
            target_frame_rate = quality_settings["settings"]["frame_rate"]
            
            # Initialize network metrics
            network_metrics = {
                "rtt": 100,           # Initial estimate (ms)
                "packet_loss": 0.0,    # Initial estimate (%)
                "bandwidth": 2_000_000, # Initial estimate (bps)
                "jitter": 30           # Initial estimate (ms)
            }
            
            # Start with medium quality
            for frame in self._decoder:
                if self._stopped:
                    break
                
                # Calculate timing for frame rate control
                self._frame_count += 1
                current_time = time.time()
                elapsed = current_time - self._start_time
                
                # Check if quality settings have changed (maybe externally set)
                if current_time - last_quality_check > 1.0:  # Check every second
                    quality_settings = self._bitrate_controller.get_current_settings()
                    target_frame_rate = quality_settings["settings"]["frame_rate"]
                    last_quality_check = current_time
                    
                    # Update network metrics (in a real implementation, these would come from WebRTC stats)
                    # Here we're using simulated metrics that improve over time for demo purposes
                    elapsed_since_start = current_time - self._start_time
                    if elapsed_since_start < 30:  # First 30 seconds, simulate varying network conditions
                        # Simulated network fluctuation
                        network_metrics["rtt"] = 100 + 100 * math.sin(elapsed_since_start / 5)
                        network_metrics["packet_loss"] = max(0, 2 + 2 * math.sin(elapsed_since_start / 7))
                        network_metrics["bandwidth"] = 2_000_000 + 1_000_000 * math.sin(elapsed_since_start / 10)
                    else:
                        # After 30 seconds, simulate network stabilization
                        network_metrics["rtt"] = max(50, network_metrics["rtt"] * 0.95)  # Improve gradually
                        network_metrics["packet_loss"] = max(0.1, network_metrics["packet_loss"] * 0.9)
                        network_metrics["bandwidth"] = min(5_000_000, network_metrics["bandwidth"] * 1.05)
                    
                    # Feed metrics to bitrate controller
                    self._bitrate_controller.add_metrics(network_metrics)
                    
                    # Update stats for monitoring
                    self._network_metrics = network_metrics.copy()
                    self._stats["quality_level"] = quality_settings["quality_level"]
                    self._stats["network_score"] = self._bitrate_controller._calculate_network_score(network_metrics)
                
                # Adaptive frame rate control
                target_time = self._frame_count / target_frame_rate
                
                # Wait if we're ahead of schedule
                if elapsed < target_time:
                    await asyncio.sleep(target_time - elapsed)
                
                # Check if this is a key frame (more important for video quality)
                is_key_frame = hasattr(frame, 'key_frame') and frame.key_frame
                
                # Try to add frame to buffer with priority for key frames
                added = await self._buffer.add_frame(frame, key_frame=is_key_frame)
                
                if added:
                    self._stats["frames_sent"] += 1
                else:
                    self._stats["frames_dropped"] += 1
                
                # Update stats periodically
                if current_time - self._last_stats_update > 1.0:
                    buffer_stats = self._buffer.get_stats()
                    self._stats["buffer_level"] = buffer_stats["buffer_level"]
                    self._stats["latency"] = buffer_stats["latency"]
                    self._last_stats_update = current_time
            
            logger.info(f"Finished generating frames for {self.cid}")
            
        except Exception as e:
            logger.error(f"Error generating frames: {e}")
            self._stopped = True
    
    async def recv(self):
        """Receive the next frame from the stream with advanced metrics collection."""
        try:
            if self.track:
                # Relay mode - just pass through frames
                frame = await self.track.recv()
            else:
                # IPFS source mode - get from our advanced buffer
                if self._stopped and self._buffer.buffer.empty():
                    # End of stream or error condition
                    raise MediaStreamTrack.ended()
                
                # Wait for next frame from the buffer
                frame = await self._buffer.get_frame()
            
            # Update performance statistics for quality adaptation
            now = time.time()
            time_diff = now - self._last_timestamp
            
            if time_diff > 1.0:  # Update comprehensive stats every second
                # Get current buffer statistics
                buffer_stats = self._buffer.get_stats() if hasattr(self._buffer, 'get_stats') else {}
                
                # Update our main stats from the buffer stats
                if buffer_stats:
                    self._stats["buffer_level"] = buffer_stats.get("buffer_level", 0)
                    self._stats["latency"] = buffer_stats.get("latency", 0)
                    
                    # Calculate effective bitrate based on frame rate and size
                    if hasattr(frame, 'width') and hasattr(frame, 'height') and buffer_stats.get("frame_rate", 0) > 0:
                        avg_frame_size = (frame.width * frame.height * 3) / (8 * 1024)  # Rough estimate in KB
                        self._stats["bitrate"] = avg_frame_size * buffer_stats.get("frame_rate", 30) * 8  # bits per second
                
                # Get quality settings from bitrate controller
                quality_settings = self._bitrate_controller.get_current_settings()
                self._stats["quality_level"] = quality_settings["quality_level"]
                
                # Emit quality changed notification if we have notification support
                if HAVE_NOTIFICATIONS and hasattr(self, 'cid'):
                    asyncio.create_task(emit_event(
                        NotificationType.WEBRTC_QUALITY_CHANGED,
                        {
                            "cid": self.cid,
                            "quality_level": self._stats["quality_level"],
                            "frame_rate": buffer_stats.get("frame_rate", self.frame_rate),
                            "buffer_level": self._stats["buffer_level"],
                            "latency": self._stats["latency"],
                            "network_score": self._stats.get("network_score", 0)
                        },
                        source="media_stream_track"
                    ))
                
                self._last_timestamp = now
            
            # Return the frame
            return frame
            
        except Exception as e:
            logger.error(f"Error in recv: {e}")
            raise
    
    def stop(self):
        """Stop the stream and clean up resources."""
        if not self._stopped:
            logger.info(f"Stopping IPFS media stream: {self.cid}")
            self._stopped = True
            if self._task:
                self._task.cancel()
            super().stop()


# Define WebRTCStreamingManager based on dependency availability
if HAVE_WEBRTC:
    class WebRTCStreamingManager:
        """Manages WebRTC connections for IPFS content streaming with performance optimization."""
        
        def __init__(self, ipfs_api, config=None):
            """
            Initialize the WebRTC streaming manager with advanced configuration.
            
            Args:
                ipfs_api: IPFS API instance for content access
                config: WebRTCConfig object or None to use optimal defaults
            """
            self.ipfs_api = ipfs_api
            self.peer_connections = {}
            self.media_relays = {}
            self.tracks = {}
            self.connection_stats = {}
            self.reconnection_tasks = {}
            self.ended_connections = set()  # Track ended connections for cleanup
            
            # Use provided config or create optimal one based on system
            self.config = config or WebRTCConfig.get_optimal_config()
            
            # Get RTC configuration from config object
            self.rtc_configuration = self.config.get_rtc_configuration()
            
            # Enhanced global metrics for monitoring
            self.global_metrics = {
                # Network metrics
                "rtt_avg": 0,
                "packet_loss_avg": 0,
                "bandwidth_avg": 0,
                "jitter_avg": 0,
                "connection_success_rate": 1.0,
                
                # Performance metrics
                "total_connections": 0,
                "active_connections": 0,
                "failed_connections": 0,
                "current_bitrate_total": 0,
                "frames_per_second_avg": 0,
                
                # Resource metrics
                "total_tracks": 0,
                "total_bytes_sent": 0,
                "total_frames_sent": 0,
                "memory_usage": 0,
                
                # Time metrics
                "uptime": 0,
                "start_time": time.time(),
                "last_update": time.time()
            }
            
            # Track connections by content ID for easy lookup
            self.connections_by_cid = {}
            
            # Security features
            if self.config.enable_security:
                self.connection_blacklist = set()  # IPs or connection IDs to reject
                self.max_connections_per_ip = 5    # Limit connections per client
                self.ip_connection_counter = {}    # Count connections per client IP
                self.token_validation = {}         # Optional token validation for sensitive content
                
            # Set up enhanced periodic monitoring if enabled
            if self.config.enable_metrics:
                self._start_metrics_collection()
    
    def _start_metrics_collection(self):
        """Start a background task for periodic metrics collection."""
        self.metrics_task = asyncio.create_task(self._collect_metrics())
        logger.info("Started WebRTC metrics collection task")
    
    async def _collect_metrics(self):
        """Periodically collect and aggregate statistics from all connections."""
        collection_interval = 5.0  # seconds between collection cycles
        
        try:
            while True:
                # Update global metrics
                await self._update_global_metrics()
                
                # Clean up ended connections
                await self._cleanup_ended_connections()
                
                # Wait until next collection cycle
                await asyncio.sleep(collection_interval)
        except asyncio.CancelledError:
            logger.info("WebRTC metrics collection task cancelled")
        except Exception as e:
            logger.error(f"Error in WebRTC metrics collection: {e}")
    
    async def _update_global_metrics(self):
        """Aggregate statistics from all connections."""
        try:
            # Update timestamp
            now = time.time()
            self.global_metrics["last_update"] = now
            self.global_metrics["uptime"] = now - self.global_metrics["start_time"]
            
            # Count connections
            active_connections = list(self.peer_connections.keys())
            self.global_metrics["active_connections"] = len(active_connections)
            self.global_metrics["total_connections"] = self.global_metrics.get("total_connections", 0) + len(self.ended_connections)
            self.ended_connections.clear()  # Reset after counting
            
            # Reset aggregate metrics for recalculation
            total_rtt = 0
            total_packet_loss = 0
            total_bandwidth = 0
            total_jitter = 0
            total_bitrate = 0
            total_fps = 0
            connection_count = max(1, len(active_connections))  # Avoid division by zero
            
            # Aggregate metrics from all active connections
            for pc_id in active_connections:
                if pc_id in self.connection_stats:
                    stats = self.connection_stats[pc_id]
                    
                    # Network metrics
                    total_rtt += stats.get("rtt", 0)
                    total_packet_loss += stats.get("packet_loss", 0)
                    total_bandwidth += stats.get("bandwidth_estimate", 0)
                    total_jitter += stats.get("jitter", 0)
                    
                    # Performance metrics
                    total_bitrate += stats.get("bitrate", 0)
                    
                    # Resource tracking
                    self.global_metrics["total_frames_sent"] += stats.get("frames_sent", 0) - stats.get("last_frames_sent", 0)
                    stats["last_frames_sent"] = stats.get("frames_sent", 0)
            
            # Calculate averages
            self.global_metrics["rtt_avg"] = total_rtt / connection_count
            self.global_metrics["packet_loss_avg"] = total_packet_loss / connection_count
            self.global_metrics["bandwidth_avg"] = total_bandwidth / connection_count
            self.global_metrics["jitter_avg"] = total_jitter / connection_count
            self.global_metrics["current_bitrate_total"] = total_bitrate
            
            # Estimate system resource usage
            if hasattr(os, 'getpid'):
                try:
                    import psutil
                    process = psutil.Process(os.getpid())
                    self.global_metrics["memory_usage"] = process.memory_info().rss  # in bytes
                    self.global_metrics["cpu_percent"] = process.cpu_percent()
                except (ImportError, Exception) as e:
                    # Fall back to rough estimate if psutil not available
                    self.global_metrics["memory_usage"] = 50 * 1024 * 1024 * len(active_connections)  # Rough estimate
                    
            # Report to notification system if available
            if HAVE_NOTIFICATIONS and self.global_metrics["active_connections"] > 0:
                # Only send periodic updates if we have active connections
                await emit_event(
                    NotificationType.SYSTEM_METRICS,
                    {
                        "webrtc": {
                            "active_connections": self.global_metrics["active_connections"],
                            "total_connections": self.global_metrics["total_connections"],
                            "rtt_avg": self.global_metrics["rtt_avg"],
                            "packet_loss_avg": self.global_metrics["packet_loss_avg"],
                            "bandwidth_avg": self.global_metrics["bandwidth_avg"],
                            "memory_usage": self.global_metrics["memory_usage"],
                            "uptime": self.global_metrics["uptime"],
                            "total_frames_sent": self.global_metrics["total_frames_sent"]
                        }
                    },
                    source="webrtc_manager"
                )
                
        except Exception as e:
            logger.error(f"Error updating global metrics: {e}")
    
    async def _cleanup_ended_connections(self):
        """Cleanup resources for connections that have ended."""
        try:
            # Identify connections that need cleanup
            to_cleanup = []
            for pc_id, pc in list(self.peer_connections.items()):
                if pc.connectionState in ["closed", "failed"]:
                    to_cleanup.append(pc_id)
                    self.ended_connections.add(pc_id)
            
            # Clean up each identified connection
            for pc_id in to_cleanup:
                await self.close_peer_connection(pc_id)
                logger.info(f"Automatically cleaned up ended connection: {pc_id}")
        except Exception as e:
            logger.error(f"Error cleaning up ended connections: {e}")
            
    def get_global_metrics(self):
        """
        Get global WebRTC performance metrics.
        
        Returns:
            Dictionary with aggregated metrics
        """
        return {
            "active_connections": self.global_metrics["active_connections"],
            "total_connections": self.global_metrics["total_connections"],
            "rtt_avg": self.global_metrics["rtt_avg"],
            "packet_loss_avg": self.global_metrics["packet_loss_avg"],
            "bandwidth_avg": self.global_metrics["bandwidth_avg"],
            "jitter_avg": self.global_metrics["jitter_avg"],
            "memory_usage": self.global_metrics["memory_usage"],
            "uptime": self.global_metrics["uptime"],
            "total_frames_sent": self.global_metrics["total_frames_sent"],
            "current_bitrate_total": self.global_metrics["current_bitrate_total"],
            "timestamp": self.global_metrics["last_update"]
        }
else:
    class WebRTCStreamingManager:
        """Stub implementation when WebRTC dependencies are not available."""
        
        def __init__(self, *args, **kwargs):
            """Stub initialization that raises an import error."""
            logger.error("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
            raise ImportError("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
            
        async def create_offer(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        async def handle_answer(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        async def handle_candidate(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        async def add_content_track(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        async def close_peer_connection(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        async def close_all_connections(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
            
        def get_connection_stats(self, *args, **kwargs):
            """Stub method that raises NotImplementedError."""
            raise NotImplementedError("WebRTC dependencies not available")
    
    async def create_offer(self, cid=None, kind="video", frame_rate=30, quality="auto"):
        """
        Create a WebRTC offer for streaming IPFS content with quality settings.
        
        Args:
            cid: Content identifier for the media in IPFS
            kind: Track kind ("audio" or "video")
            frame_rate: Target frame rate for video tracks
            quality: Initial quality level ("very_low", "low", "medium", "high", "very_high", "auto")
            
        Returns:
            Dict with SDP offer and peer connection ID
        """
        # Create a new peer connection with optimized configuration
        pc_id = str(uuid.uuid4())
        pc = RTCPeerConnection(configuration=self.rtc_configuration)
        self.peer_connections[pc_id] = pc
        
        # Initialize connection stats with enhanced metrics
        self.connection_stats[pc_id] = {
            "created_at": time.time(),
            "state": "new",
            "cid": cid,
            "kind": kind,
            "frame_rate": frame_rate,
            "quality": quality,
            "ice_candidates_added": 0,
            "streams_active": 0,
            "bytes_sent": 0,
            "frames_sent": 0,
            "frames_dropped": 0,
            "last_quality_update": time.time(),
            # Enhanced network metrics for quality adaptation
            "rtt": 0,
            "packet_loss": 0,
            "bandwidth_estimate": 0,
            "jitter": 0,
            "connection_quality_score": 100,
            "buffer_health": 1.0,
            "adaptation_changes": 0,
            "dropped_frame_rate": 0
        }
        
        # Create media track from IPFS content
        if cid:
            track = IPFSMediaStreamTrack(
                ipfs_api=self.ipfs_api,
                cid=cid,
                kind=kind,
                frame_rate=frame_rate
            )
            # Configure initial quality if track supports it
            if hasattr(track, '_bitrate_controller') and hasattr(track._bitrate_controller, 'set_quality'):
                track._bitrate_controller.set_quality(quality)
                
            self.tracks[pc_id] = track
            pc.addTrack(track)
            self.connection_stats[pc_id]["streams_active"] += 1
        
        # Set up connection monitoring
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state is {pc.connectionState}")
            old_state = self.connection_stats[pc_id]["state"]
            self.connection_stats[pc_id]["state"] = pc.connectionState
            
            # Emit notification for state change
            if HAVE_NOTIFICATIONS:
                if pc.connectionState == "connected" and old_state != "connected":
                    # Connection established
                    await emit_event(
                        NotificationType.WEBRTC_CONNECTION_ESTABLISHED, 
                        {
                            "pc_id": pc_id,
                            "cid": cid,
                            "kind": kind,
                            "connection_time": time.time() - self.connection_stats[pc_id]["created_at"]
                        },
                        source="webrtc_manager"
                    )
                elif pc.connectionState in ["failed", "closed"]:
                    # Connection closed or failed
                    notification_type = (NotificationType.WEBRTC_ERROR if pc.connectionState == "failed" 
                                        else NotificationType.WEBRTC_CONNECTION_CLOSED)
                    await emit_event(
                        notification_type,
                        {
                            "pc_id": pc_id,
                            "cid": cid,
                            "state": pc.connectionState,
                            "duration": time.time() - self.connection_stats[pc_id]["created_at"]
                        },
                        source="webrtc_manager"
                    )
                    await self.close_peer_connection(pc_id)
        
        # Monitor ICE connection state
        @pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            logger.info(f"ICE gathering state changed to {pc.iceGatheringState}")
            self.connection_stats[pc_id]["ice_gathering_state"] = pc.iceGatheringState
            
        # Setup track stats monitoring
        async def monitor_track_stats():
            """Monitor track statistics and collect performance metrics for quality adaptation."""
            connection_start_time = time.time()
            stats_interval = 2.0  # Collect stats every 2 seconds
            quality_update_interval = 5.0  # Send quality updates every 5 seconds
            performance_data = []  # Store performance data points for trend analysis
            
            while pc_id in self.peer_connections:
                try:
                    # Get RTCPeerConnection stats (in a real implementation)
                    # For now we'll simulate stats based on track statistics
                    now = time.time()
                    connection_duration = now - connection_start_time
                    
                    # Monitor track statistics if there's an active track
                    if pc_id in self.tracks:
                        track = self.tracks[pc_id]
                        
                        # Handle both single track and multiple tracks
                        tracks_to_check = [track] if not isinstance(track, list) else track
                        
                        for idx, current_track in enumerate(tracks_to_check):
                            if hasattr(current_track, "_stats"):
                                # Get the track stats
                                track_stats = current_track._stats
                                
                                # Update connection stats with track stats
                                self.connection_stats[pc_id]["frames_sent"] = track_stats.get("frames_sent", 0)
                                self.connection_stats[pc_id]["frames_dropped"] = track_stats.get("frames_dropped", 0)
                                self.connection_stats[pc_id]["buffer_level"] = track_stats.get("buffer_level", 0)
                                self.connection_stats[pc_id]["quality_level"] = track_stats.get("quality_level", "medium")
                                
                                # Collect network metrics from track (in a real implementation, these would come from getStats())
                                if hasattr(current_track, "_network_metrics"):
                                    network_metrics = current_track._network_metrics
                                    self.connection_stats[pc_id]["rtt"] = network_metrics.get("rtt", 0)
                                    self.connection_stats[pc_id]["packet_loss"] = network_metrics.get("packet_loss", 0)
                                    self.connection_stats[pc_id]["bandwidth_estimate"] = network_metrics.get("bandwidth", 0)
                                    self.connection_stats[pc_id]["jitter"] = network_metrics.get("jitter", 0)
                                
                                # Calculate additional metrics
                                total_frames = track_stats.get("frames_sent", 0) + track_stats.get("frames_dropped", 0)
                                if total_frames > 0:
                                    drop_rate = track_stats.get("frames_dropped", 0) / total_frames
                                    self.connection_stats[pc_id]["dropped_frame_rate"] = drop_rate
                                    
                                    # Calculate a connection quality score (0-100)
                                    quality_score = 100
                                    
                                    # Penalize based on drop rate
                                    if drop_rate > 0.2:  # >20% drops is very bad
                                        quality_score -= 50
                                    elif drop_rate > 0.1:  # >10% drops is bad
                                        quality_score -= 30
                                    elif drop_rate > 0.05:  # >5% drops is concerning
                                        quality_score -= 15
                                    elif drop_rate > 0.01:  # >1% drops is noticeable
                                        quality_score -= 5
                                    
                                    # Penalize based on network metrics
                                    if self.connection_stats[pc_id]["rtt"] > 500:
                                        quality_score -= 20
                                    elif self.connection_stats[pc_id]["rtt"] > 300:
                                        quality_score -= 10
                                    elif self.connection_stats[pc_id]["rtt"] > 150:
                                        quality_score -= 5
                                    
                                    if self.connection_stats[pc_id]["packet_loss"] > 10:
                                        quality_score -= 30
                                    elif self.connection_stats[pc_id]["packet_loss"] > 5:
                                        quality_score -= 20
                                    elif self.connection_stats[pc_id]["packet_loss"] > 2:
                                        quality_score -= 10
                                    
                                    # Update the quality score
                                    self.connection_stats[pc_id]["connection_quality_score"] = max(0, min(100, quality_score))
                                    
                                    # Add to performance data for trend analysis
                                    performance_data.append({
                                        "timestamp": now,
                                        "quality_score": quality_score,
                                        "drop_rate": drop_rate,
                                        "buffer_level": track_stats.get("buffer_level", 0),
                                        "quality_level": track_stats.get("quality_level", "medium")
                                    })
                                    
                                    # Keep performance data bounded
                                    if len(performance_data) > 30:
                                        performance_data = performance_data[-30:]
                                
                                # Check if it's time for a quality notification
                                if (now - self.connection_stats[pc_id]["last_quality_update"]) > quality_update_interval:
                                    self.connection_stats[pc_id]["last_quality_update"] = now
                                    
                                    # If we have at least 3 data points, analyze trend
                                    quality_trend = "stable"
                                    if len(performance_data) >= 3:
                                        recent_scores = [point["quality_score"] for point in performance_data[-3:]]
                                        if all(recent_scores[i] > recent_scores[i-1] for i in range(1, len(recent_scores))):
                                            quality_trend = "improving"
                                        elif all(recent_scores[i] < recent_scores[i-1] for i in range(1, len(recent_scores))):
                                            quality_trend = "degrading"
                                    
                                    # Create quality notification with enhanced metrics
                                    quality_notification = {
                                        "pc_id": pc_id,
                                        "cid": cid,
                                        "drop_rate": self.connection_stats[pc_id]["dropped_frame_rate"],
                                        "buffer_level": track_stats.get("buffer_level", 0),
                                        "quality_level": track_stats.get("quality_level", "medium"),
                                        "connection_quality_score": self.connection_stats[pc_id]["connection_quality_score"],
                                        "quality_trend": quality_trend,
                                        "duration": connection_duration,
                                        "network_metrics": {
                                            "rtt": self.connection_stats[pc_id]["rtt"],
                                            "packet_loss": self.connection_stats[pc_id]["packet_loss"],
                                            "bandwidth_estimate": self.connection_stats[pc_id]["bandwidth_estimate"],
                                            "jitter": self.connection_stats[pc_id]["jitter"]
                                        }
                                    }
                                    
                                    # Emit enhanced quality notification
                                    if HAVE_NOTIFICATIONS:
                                        await emit_event(
                                            NotificationType.WEBRTC_QUALITY_CHANGED,
                                            quality_notification,
                                            source="webrtc_manager"
                                        )
                                    
                                    logger.debug(f"Quality update for {pc_id}: score={quality_notification['connection_quality_score']}, "
                                                f"trend={quality_trend}, quality={quality_notification['quality_level']}")
                                
                except Exception as e:
                    logger.error(f"Error monitoring track stats: {e}")
                
                # Sleep until next stats collection cycle
                await asyncio.sleep(stats_interval)
        
        # Start stats monitoring task
        asyncio.create_task(monitor_track_stats())
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Emit connection created notification
        if HAVE_NOTIFICATIONS:
            await emit_event(
                NotificationType.WEBRTC_CONNECTION_CREATED,
                {
                    "pc_id": pc_id,
                    "cid": cid,
                    "kind": kind,
                    "frame_rate": frame_rate
                },
                source="webrtc_manager"
            )
        
        # Return the offer to be sent to the client
        return {
            "pc_id": pc_id,
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        }
    
    async def handle_answer(self, pc_id, sdp, type_):
        """
        Handle a WebRTC answer from a client.
        
        Args:
            pc_id: Peer connection ID
            sdp: Session Description Protocol string
            type_: SDP type (usually "answer")
            
        Returns:
            Boolean indicating success
        """
        if pc_id not in self.peer_connections:
            logger.error(f"Unknown peer connection ID: {pc_id}")
            return False
        
        pc = self.peer_connections[pc_id]
        
        # Set the remote description
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type=type_)
        )
        
        logger.info(f"Established WebRTC connection for PC ID: {pc_id}")
        
        # Update connection stats
        self.connection_stats[pc_id]["remote_description_set"] = time.time()
        
        return True
    
    async def handle_candidate(self, pc_id, candidate, sdp_mid, sdp_mline_index):
        """
        Handle an ICE candidate from a client.
        
        Args:
            pc_id: Peer connection ID
            candidate: ICE candidate string
            sdp_mid: Media stream identifier
            sdp_mline_index: Media line index
            
        Returns:
            Boolean indicating success
        """
        if pc_id not in self.peer_connections:
            logger.error(f"Unknown peer connection ID: {pc_id}")
            return False
        
        pc = self.peer_connections[pc_id]
        
        # Add the ICE candidate
        await pc.addIceCandidate({
            "candidate": candidate,
            "sdpMid": sdp_mid,
            "sdpMLineIndex": sdp_mline_index
        })
        
        # Update stats
        if pc_id in self.connection_stats:
            self.connection_stats[pc_id]["ice_candidates_added"] += 1
        
        return True
    
    async def add_content_track(self, pc_id, cid, kind="video", frame_rate=30):
        """
        Add a new content track to an existing peer connection.
        
        Args:
            pc_id: Peer connection ID
            cid: Content identifier for the media in IPFS
            kind: Track kind ("audio" or "video")
            frame_rate: Target frame rate for video tracks
            
        Returns:
            Boolean indicating success
        """
        if pc_id not in self.peer_connections:
            logger.error(f"Unknown peer connection ID: {pc_id}")
            return False
        
        pc = self.peer_connections[pc_id]
        
        # Create new track
        track = IPFSMediaStreamTrack(
            ipfs_api=self.ipfs_api,
            cid=cid,
            kind=kind,
            frame_rate=frame_rate
        )
        
        # Store and add the track
        if pc_id not in self.tracks:
            self.tracks[pc_id] = []
        
        if isinstance(self.tracks[pc_id], list):
            self.tracks[pc_id].append(track)
        else:
            self.tracks[pc_id] = [self.tracks[pc_id], track]
        
        # Update stats
        if pc_id in self.connection_stats:
            self.connection_stats[pc_id]["streams_active"] += 1
        
        # Add track to the peer connection
        pc.addTrack(track)
        
        # Create and set a new offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Emit stream started notification
        if HAVE_NOTIFICATIONS:
            await emit_event(
                NotificationType.WEBRTC_STREAM_STARTED,
                {
                    "pc_id": pc_id,
                    "cid": cid,
                    "kind": kind,
                    "frame_rate": frame_rate
                },
                source="webrtc_manager"
            )
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        }
    
    async def close_peer_connection(self, pc_id, attempt_reconnection=False):
        """
        Close a WebRTC peer connection and clean up resources.
        
        Args:
            pc_id: Peer connection ID
            attempt_reconnection: Whether to attempt reconnection after closing
            
        Returns:
            Boolean indicating success
        """
        if pc_id not in self.peer_connections:
            logger.warning(f"Unknown peer connection ID: {pc_id}")
            return False
        
        # Get connection stats before cleanup
        connection_duration = 0
        connection_stats = None
        if pc_id in self.connection_stats:
            connection_stats = self.connection_stats[pc_id].copy()
            connection_duration = time.time() - connection_stats.get("created_at", time.time())
        
        # Save reconnection information if needed
        reconnect_info = None
        if attempt_reconnection and self.config.enable_resilience:
            if pc_id in self.connection_stats:
                # Save the essential information needed for reconnection
                reconnect_info = {
                    "cid": connection_stats.get("cid"),
                    "kind": connection_stats.get("kind"),
                    "frame_rate": connection_stats.get("frame_rate"),
                    "quality": connection_stats.get("quality"),
                    "pc_id": pc_id,  # We'll try to reuse the same ID for consistency
                    "attempt": connection_stats.get("reconnect_attempt", 0) + 1,
                    "original_created_at": connection_stats.get("created_at"),
                    "total_duration": connection_duration,
                    "previous_state": connection_stats.get("state")
                }
        
        # Stop all tracks
        if pc_id in self.tracks:
            tracks = self.tracks[pc_id]
            if isinstance(tracks, list):
                for track in tracks:
                    if hasattr(track, 'stop'):
                        track.stop()
                        # Emit stream ended notification for each track
                        if HAVE_NOTIFICATIONS:
                            await emit_event(
                                NotificationType.WEBRTC_STREAM_ENDED,
                                {
                                    "pc_id": pc_id,
                                    "cid": track.cid if hasattr(track, 'cid') else None,
                                    "kind": track.kind if hasattr(track, 'kind') else None,
                                    "duration": connection_duration
                                },
                                source="webrtc_manager"
                            )
            elif hasattr(tracks, 'stop'):
                tracks.stop()
                # Emit stream ended notification
                if HAVE_NOTIFICATIONS:
                    await emit_event(
                        NotificationType.WEBRTC_STREAM_ENDED,
                        {
                            "pc_id": pc_id,
                            "cid": tracks.cid if hasattr(tracks, 'cid') else None,
                            "kind": tracks.kind if hasattr(tracks, 'kind') else None,
                            "duration": connection_duration
                        },
                        source="webrtc_manager"
                    )
            del self.tracks[pc_id]
        
        # Close the peer connection
        pc = self.peer_connections[pc_id]
        await pc.close()
        del self.peer_connections[pc_id]
        
        # Clean up any relay
        if pc_id in self.media_relays:
            del self.media_relays[pc_id]
        
        # Event notification depends on whether we're reconnecting
        if HAVE_NOTIFICATIONS and connection_stats:
            if attempt_reconnection:
                # If we're trying to reconnect, send a reconnection attempt notification
                await emit_event(
                    NotificationType.WEBRTC_RECONNECTION_ATTEMPT,
                    {
                        "pc_id": pc_id,
                        "duration": connection_duration,
                        "state": connection_stats.get("state", "unknown"),
                        "reconnect_attempt": reconnect_info["attempt"] if reconnect_info else 1,
                        "cid": connection_stats.get("cid")
                    },
                    source="webrtc_manager"
                )
            else:
                # Standard connection closed notification
                await emit_event(
                    NotificationType.WEBRTC_CONNECTION_CLOSED,
                    {
                        "pc_id": pc_id,
                        "duration": connection_duration,
                        "state": connection_stats.get("state", "unknown"),
                        "streams_active": connection_stats.get("streams_active", 0),
                        "frames_sent": connection_stats.get("frames_sent", 0),
                        "frames_dropped": connection_stats.get("frames_dropped", 0)
                    },
                    source="webrtc_manager"
                )
        
        # Clean up stats if not reconnecting
        if pc_id in self.connection_stats and not attempt_reconnection:
            del self.connection_stats[pc_id]
        
        # Log the closure
        if attempt_reconnection:
            logger.info(f"Closed peer connection {pc_id} for reconnection attempt {reconnect_info['attempt'] if reconnect_info else 1}")
        else:
            logger.info(f"Closed peer connection {pc_id}")
        
        # Schedule reconnection if requested
        if attempt_reconnection and reconnect_info and self.config.enable_resilience:
            # Check if we're under the max reconnection attempts
            max_attempts = self.config.reconnect_attempts
            if reconnect_info["attempt"] <= max_attempts:
                # Calculate delay using exponential backoff
                delay = self.config.calculate_reconnect_delay(reconnect_info["attempt"])
                
                # Schedule the reconnection task
                logger.info(f"Scheduling reconnection attempt {reconnect_info['attempt']} for {pc_id} in {delay:.2f} seconds")
                
                # Create and store the reconnection task
                self.reconnection_tasks[pc_id] = asyncio.create_task(
                    self._attempt_reconnection(reconnect_info, delay)
                )
            else:
                logger.warning(f"Maximum reconnection attempts ({max_attempts}) reached for {pc_id}, giving up")
                
                # Clean up the stats now that we're not reconnecting
                if pc_id in self.connection_stats:
                    del self.connection_stats[pc_id]
                
                # Notify about the failed reconnection
                if HAVE_NOTIFICATIONS:
                    await emit_event(
                        NotificationType.WEBRTC_RECONNECTION_FAILED,
                        {
                            "pc_id": pc_id,
                            "cid": reconnect_info.get("cid"),
                            "attempts": reconnect_info["attempt"],
                            "reason": "max_attempts_reached"
                        },
                        source="webrtc_manager"
                    )
        
        return True
    
    async def _attempt_reconnection(self, reconnect_info, delay):
        """
        Attempt to reconnect a failed WebRTC peer connection.
        
        Args:
            reconnect_info: Dictionary with information needed for reconnection
            delay: Delay before attempting reconnection (seconds)
            
        Returns:
            Boolean indicating success
        """
        # First wait for the specified delay
        await asyncio.sleep(delay)
        
        pc_id = reconnect_info["pc_id"]
        attempt = reconnect_info["attempt"]
        cid = reconnect_info["cid"]
        kind = reconnect_info["kind"]
        frame_rate = reconnect_info["frame_rate"]
        quality = reconnect_info["quality"]
        
        logger.info(f"Attempting reconnection for {pc_id} (attempt {attempt}/{self.config.reconnect_attempts}) "
                   f"CID: {cid}, kind: {kind}")
        
        try:
            # Create a new peer connection with the original ID
            # Using a different config that might work better for problematic networks
            retry_config = self.config.get_rtc_configuration()
            
            # For reconnection attempts, prefer TCP and add more STUN servers
            if attempt > 1:
                # Try to increase the chance of success on retry
                retry_config["iceTransportPolicy"] = "all"  # Try all transport methods
                retry_config["enableTcpCandidates"] = True  # Explicitly enable TCP
                
                # Try to get fresh TURN servers if available
                if attempt > 2:
                    # For third and subsequent attempts, really try to get through
                    try:
                        import requests
                        # Try to get ephemeral TURN credentials (for example purposes)
                        turn_url = "https://metered.ca/api/v1/turn/credentials?apiKey=ccafe87gcaac89vofpfk"
                        response = requests.get(turn_url)
                        if response.status_code == 200:
                            turn_data = response.json()
                            if "username" in turn_data and "credential" in turn_data:
                                turn_server = {
                                    "urls": turn_data.get("urls", ["turn:a.relay.metered.ca:80"]),
                                    "username": turn_data["username"],
                                    "credential": turn_data["credential"]
                                }
                                # Add the TURN server to the beginning of the list
                                retry_config["iceServers"].insert(0, turn_server)
                    except Exception as e:
                        logger.warning(f"Failed to get TURN credentials for reconnection: {e}")
            
            # Create the new peer connection
            pc = RTCPeerConnection(retry_config)
            self.peer_connections[pc_id] = pc
            
            # Update connection stats with reconnection information
            self.connection_stats[pc_id] = {
                "created_at": time.time(),
                "state": "reconnecting",
                "cid": cid,
                "kind": kind,
                "frame_rate": frame_rate,
                "quality": quality,
                "ice_candidates_added": 0,
                "streams_active": 0,
                "bytes_sent": 0,
                "frames_sent": 0,
                "frames_dropped": 0,
                "last_quality_update": time.time(),
                "reconnect_attempt": attempt,
                "original_created_at": reconnect_info["original_created_at"],
                "previous_state": reconnect_info["previous_state"],
                "total_duration": reconnect_info["total_duration"]
            }
            
            # Set up connection state change handler
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                state = pc.connectionState
                logger.info(f"Reconnection {attempt} state: {state} for {pc_id}")
                
                if state == "connected":
                    logger.info(f"Successfully reconnected {pc_id} on attempt {attempt}")
                    
                    # Update state to reflect successful reconnection
                    if pc_id in self.connection_stats:
                        self.connection_stats[pc_id]["state"] = "connected"
                        self.connection_stats[pc_id]["reconnected_at"] = time.time()
                    
                    # Emit reconnection success notification
                    if HAVE_NOTIFICATIONS:
                        await emit_event(
                            NotificationType.WEBRTC_RECONNECTION_SUCCESS,
                            {
                                "pc_id": pc_id,
                                "cid": cid,
                                "attempt": attempt,
                                "elapsed_time": time.time() - (
                                    reconnect_info["original_created_at"] + reconnect_info["total_duration"]
                                )
                            },
                            source="webrtc_manager"
                        )
                    
                elif state in ["failed", "closed"] and pc_id in self.peer_connections:
                    # Check whether to retry again
                    if attempt < self.config.reconnect_attempts:
                        logger.info(f"Reconnection attempt {attempt} failed for {pc_id}, will retry")
                        # Close and try again
                        await self.close_peer_connection(pc_id, attempt_reconnection=True)
                    else:
                        logger.warning(f"All reconnection attempts failed for {pc_id}")
                        
                        # No more retries, clean up
                        await self.close_peer_connection(pc_id, attempt_reconnection=False)
                        
                        # Emit reconnection failed notification
                        if HAVE_NOTIFICATIONS:
                            await emit_event(
                                NotificationType.WEBRTC_RECONNECTION_FAILED,
                                {
                                    "pc_id": pc_id,
                                    "cid": cid,
                                    "attempts": attempt,
                                    "reason": "connection_failed",
                                    "total_time": time.time() - reconnect_info["original_created_at"]
                                },
                                source="webrtc_manager"
                            )
            
            # Create media track from IPFS content
            track = IPFSMediaStreamTrack(
                ipfs_api=self.ipfs_api,
                cid=cid,
                kind=kind,
                frame_rate=frame_rate
            )
            # Configure quality based on previous setting
            if hasattr(track, '_bitrate_controller') and hasattr(track._bitrate_controller, 'set_quality'):
                track._bitrate_controller.set_quality(quality)
                
            self.tracks[pc_id] = track
            pc.addTrack(track)
            self.connection_stats[pc_id]["streams_active"] += 1
            
            # Create offer for the reconnection
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Notify about the reconnection attempt via WebSocket signaling
            # The client needs to handle the reconnection offer:
            if HAVE_NOTIFICATIONS:
                await emit_event(
                    NotificationType.WEBRTC_RECONNECTION_OFFER,
                    {
                        "pc_id": pc_id,
                        "sdp": pc.localDescription.sdp,
                        "type": pc.localDescription.type,
                        "cid": cid,
                        "attempt": attempt
                    },
                    source="webrtc_manager"
                )
            
            # Send the reconnection offer through the signaling protocol
            # This would normally be handled by the signaling server
            # but for direct communication we'll need to publish it
            logger.info(f"Created reconnection offer for {pc_id} (attempt {attempt})")
            
            # Return success for creating the offer
            # The actual reconnection will be handled through the signaling protocol
            return True
            
        except Exception as e:
            logger.error(f"Failed to create reconnection offer: {e}")
            
            # Clean up if we failed to create the offer
            if pc_id in self.peer_connections:
                pc = self.peer_connections[pc_id]
                await pc.close()
                del self.peer_connections[pc_id]
                
            # Remove the stats
            if pc_id in self.connection_stats:
                del self.connection_stats[pc_id]
                
            # Notify about the failure
            if HAVE_NOTIFICATIONS:
                await emit_event(
                    NotificationType.WEBRTC_RECONNECTION_FAILED,
                    {
                        "pc_id": pc_id,
                        "cid": cid,
                        "attempts": attempt,
                        "reason": str(e),
                        "total_time": time.time() - reconnect_info["original_created_at"]
                    },
                    source="webrtc_manager"
                )
                
            return False
    
    async def close_all_connections(self):
        """Close all active WebRTC connections and stop metrics collection."""
        # Cancel metrics collection task if running
        if hasattr(self, 'metrics_task') and self.metrics_task is not None:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling metrics task: {e}")
            self.metrics_task = None
        
        # Close all peer connections
        pc_ids = list(self.peer_connections.keys())
        for pc_id in pc_ids:
            await self.close_peer_connection(pc_id)
            
    def get_connection_stats(self, pc_id=None):
        """
        Get statistics for WebRTC connections.
        
        Args:
            pc_id: Optional peer connection ID to get stats for a specific connection
            
        Returns:
            Dict with connection statistics
        """
        if pc_id:
            if pc_id in self.connection_stats:
                stats = self.connection_stats[pc_id].copy()
                # Add additional calculated stats
                stats["active"] = pc_id in self.peer_connections
                stats["current_time"] = time.time()
                stats["duration"] = stats["current_time"] - stats["created_at"]
                return stats
            else:
                return {"error": f"Unknown peer connection ID: {pc_id}"}
        
        # Return stats for all connections
        all_stats = {
            "active_connections": len(self.peer_connections),
            "total_streams": sum(stats.get("streams_active", 0) for stats in self.connection_stats.values()),
            "total_frames_sent": sum(stats.get("frames_sent", 0) for stats in self.connection_stats.values()),
            "total_frames_dropped": sum(stats.get("frames_dropped", 0) for stats in self.connection_stats.values()),
            "connections": {pc_id: stats.copy() for pc_id, stats in self.connection_stats.items()}
        }
        
        # Add calculated metrics to each connection
        for pc_id, stats in all_stats["connections"].items():
            stats["active"] = pc_id in self.peer_connections
            stats["current_time"] = time.time()
            stats["duration"] = stats["current_time"] - stats["created_at"]
        
        return all_stats


# Utility functions for WebRTC signaling
async def handle_webrtc_signaling(websocket, ipfs_api):
    """
    Handle WebRTC signaling via WebSocket for streaming IPFS content.
    
    Args:
        websocket: WebSocket connection
        ipfs_api: IPFS API instance
    """
    # Check for complete WebRTC support
    if not HAVE_WEBRTC:
        error_message = "WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'"
        logger.error(error_message)
        
        # Try to send error via websocket if possible
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_message,
                "dependency_status": {
                    "av": HAVE_AV,
                    "cv2": HAVE_CV2,
                    "numpy": HAVE_NUMPY,
                    "aiortc": HAVE_AIORTC,
                    "webrtc": HAVE_WEBRTC
                }
            })
        except Exception as e:
            logger.error(f"Failed to send WebRTC dependency error: {e}")
            
        return
    
    # Generate a client ID for this signaling connection
    client_id = f"client_{uuid.uuid4()}"
    
    # Log the new connection
    logger.info(f"New WebRTC signaling connection: {client_id}")
    
    # Create WebRTC manager
    manager = WebRTCStreamingManager(ipfs_api)
    
    # Notify about new signaling connection if notifications available
    if HAVE_NOTIFICATIONS:
        await emit_event(
            NotificationType.SYSTEM_INFO,
            {
                "message": "New WebRTC signaling connection established",
                "client_id": client_id
            },
            source="webrtc_signaling"
        )
    
    try:
        # Accept the connection
        await websocket.accept()
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "message": "IPFS WebRTC signaling server connected",
            "capabilities": ["video", "audio"],
            "notification_support": HAVE_NOTIFICATIONS
        })
        
        # Handle signaling messages
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                if msg_type == "offer_request":
                    # Client wants to start a new WebRTC session
                    cid = message.get("cid")
                    kind = message.get("kind", "video")
                    frame_rate = message.get("frameRate", 30)
                    
                    logger.info(f"WebRTC offer request for CID: {cid}, kind: {kind}")
                    
                    offer = await manager.create_offer(cid, kind, frame_rate)
                    await websocket.send_json({
                        "type": "offer",
                        "pc_id": offer["pc_id"],
                        "sdp": offer["sdp"],
                        "sdpType": offer["type"]
                    })
                
                elif msg_type == "answer":
                    # Client responded with an answer to our offer
                    pc_id = message.get("pc_id")
                    sdp = message.get("sdp")
                    sdp_type = message.get("sdpType")
                    
                    logger.info(f"WebRTC answer received for connection: {pc_id}")
                    
                    success = await manager.handle_answer(pc_id, sdp, sdp_type)
                    if success:
                        await websocket.send_json({
                            "type": "connected",
                            "pc_id": pc_id
                        })
                    else:
                        error_msg = f"Failed to handle answer for {pc_id}"
                        logger.error(error_msg)
                        
                        # Emit error notification
                        if HAVE_NOTIFICATIONS:
                            await emit_event(
                                NotificationType.WEBRTC_ERROR,
                                {
                                    "pc_id": pc_id,
                                    "error": error_msg,
                                    "client_id": client_id
                                },
                                source="webrtc_signaling"
                            )
                        
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                
                elif msg_type == "candidate":
                    # Client sent an ICE candidate
                    pc_id = message.get("pc_id")
                    candidate = message.get("candidate")
                    sdp_mid = message.get("sdpMid")
                    sdp_mline_index = message.get("sdpMLineIndex")
                    
                    await manager.handle_candidate(pc_id, candidate, sdp_mid, sdp_mline_index)
                
                elif msg_type == "add_track":
                    # Client wants to add another track to an existing connection
                    pc_id = message.get("pc_id")
                    cid = message.get("cid")
                    kind = message.get("kind", "video")
                    frame_rate = message.get("frameRate", 30)
                    
                    logger.info(f"Adding new track to connection {pc_id}, CID: {cid}, kind: {kind}")
                    
                    offer = await manager.add_content_track(pc_id, cid, kind, frame_rate)
                    if offer:
                        await websocket.send_json({
                            "type": "track_offer",
                            "pc_id": pc_id,
                            "sdp": offer["sdp"],
                            "sdpType": offer["type"]
                        })
                    else:
                        error_msg = f"Failed to add track for {pc_id}"
                        logger.error(error_msg)
                        
                        # Emit error notification
                        if HAVE_NOTIFICATIONS:
                            await emit_event(
                                NotificationType.WEBRTC_ERROR,
                                {
                                    "pc_id": pc_id,
                                    "cid": cid,
                                    "error": error_msg,
                                    "client_id": client_id
                                },
                                source="webrtc_signaling"
                            )
                        
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                
                elif msg_type == "get_stats":
                    # Client wants to get connection statistics
                    pc_id = message.get("pc_id")
                    include_global = message.get("include_global", False)
                    
                    response = {"type": "stats"}
                    
                    if pc_id:
                        # Get stats for specific connection
                        response["connection_stats"] = manager.get_connection_stats(pc_id)
                    else:
                        # Get stats for all connections
                        response["connection_stats"] = manager.get_connection_stats()
                    
                    # Include global metrics if requested
                    if include_global and hasattr(manager, 'get_global_metrics'):
                        response["global_metrics"] = manager.get_global_metrics()
                    
                    await websocket.send_json(response)
                
                elif msg_type == "close":
                    # Client wants to close a connection
                    pc_id = message.get("pc_id")
                    if pc_id:
                        logger.info(f"Closing WebRTC connection: {pc_id}")
                        await manager.close_peer_connection(pc_id)
                        await websocket.send_json({
                            "type": "closed",
                            "pc_id": pc_id
                        })
                    else:
                        # Close all connections if no specific PC ID
                        logger.info(f"Closing all WebRTC connections for client: {client_id}")
                        await manager.close_all_connections()
                        await websocket.send_json({
                            "type": "closed_all"
                        })
                
                elif msg_type == "ping":
                    # Client ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })
                    
                elif msg_type == "set_quality":
                    # Client wants to change video quality
                    pc_id = message.get("pc_id")
                    quality = message.get("quality")
                    
                    if not pc_id or not quality:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing pc_id or quality parameter"
                        })
                        continue
                    
                    logger.info(f"Setting quality for {pc_id} to {quality}")
                    
                    # Find the track for this connection
                    success = False
                    if pc_id in manager.tracks:
                        track = manager.tracks[pc_id]
                        
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