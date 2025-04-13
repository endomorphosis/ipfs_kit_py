"""
WebRTC Multi-Peer Streaming for IPFS Kit.

This module extends the WebRTC streaming capabilities to support multiple peer connections,
enabling group streaming sessions, broadcasting, and mesh networking for IPFS content.

Key features:
1. Group Streaming: Stream to multiple receivers simultaneously
2. Broadcasting: Efficiently distribute media streams to many viewers
3. Mesh Networking: Peer-to-peer media distribution network
4. SFU-like Functionality: Selective forwarding for efficient multi-party streaming
5. Dynamic Peer Management: Add/remove peers during active sessions
6. Bandwidth Optimization: Intelligent stream routing and quality adaptation
7. Session Management: Create, join, and manage streaming sessions
8. Room-based Model: Group peers by room/channel for organization

This module builds on the core WebRTC streaming functionality and integrates with
the notification system for signaling and session coordination.
"""

import anyio
import json
import logging
import time
import uuid
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Tuple

try:
    from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
    from aiortc.contrib.media import MediaRelay
    
    HAVE_WEBRTC = True
except ImportError:
    HAVE_WEBRTC = False

# Import core components with fallbacks for testing
try:
    from .webrtc_streaming import IPFSMediaStreamTrack, AdaptiveBitrateController, StreamBuffer
    from .websocket_notifications import emit_event, NotificationType
    HAVE_DEPENDENCIES = True
except ImportError:
    HAVE_DEPENDENCIES = False
    # Create dummy emit_event function for environments without notifications
    async def emit_event(*args, **kwargs):
        pass

# Configure logging
logger = logging.getLogger(__name__)


class PeerRole(str, Enum):
    """Roles that peers can have in a streaming session."""
    BROADCASTER = "broadcaster"      # Originates media stream
    VIEWER = "viewer"                # Receives media stream only
    PARTICIPANT = "participant"      # Both sends and receives media
    RELAY = "relay"                  # Forwards media without displaying
    RECORDER = "recorder"            # Records media without displaying


class StreamingSession:
    """
    Manages a multi-peer streaming session with multiple participants.
    
    A session represents a group of connected peers that can share media streams
    with each other, either in broadcast mode (one-to-many) or mesh mode (many-to-many).
    """
    
    def __init__(self, session_id: str, ipfs_api=None, session_type: str = "broadcast",
                max_peers: int = 20, public: bool = False):
        """
        Initialize a new streaming session.
        
        Args:
            session_id: Unique identifier for this session
            ipfs_api: IPFS API instance for content access
            session_type: Type of session ("broadcast", "mesh", or "hybrid")
            max_peers: Maximum number of peers allowed in the session
            public: Whether this session is publicly discoverable
        """
        if not HAVE_WEBRTC:
            raise ImportError("WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'")
        
        self.session_id = session_id
        self.ipfs_api = ipfs_api
        self.session_type = session_type
        self.max_peers = max_peers
        self.public = public
        
        # Session state
        self.active = True
        self.created_at = time.time()
        self.last_activity = time.time()
        self.metadata = {}
        
        # Track peers, connections, and media streams
        self.peers: Dict[str, Dict[str, Any]] = {}
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.tracks: Dict[str, Dict[str, Any]] = {}
        self.media_relays: Dict[str, MediaRelay] = {}
        
        # Content sources (CIDs)
        self.content_sources: Dict[str, Dict[str, Any]] = {}
        
        # Mesh connectivity matrix (tracks which peers are connected to each other)
        self.peer_mesh: Dict[str, Set[str]] = {}
        
        # Session statistics
        self.statistics = {
            "total_peers_joined": 0,
            "current_peer_count": 0,
            "max_concurrent_peers": 0,
            "total_tracks_shared": 0,
            "current_track_count": 0,
            "bytes_transferred": 0,
            "session_duration": 0,
            "errors": 0
        }
        
        # Optimization components
        self.topology_optimizer = self._initialize_topology_optimizer()
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def _initialize_topology_optimizer(self):
        """Initialize the topology optimizer for efficient peer connections."""
        return {
            "last_optimization": time.time(),
            "optimization_interval": 30,  # Optimize topology every 30 seconds
            "quality_threshold": 70,      # Minimum quality score for relay candidates
            "max_fan_out": 5,             # Maximum peers to connect to a single source
            "proximity_map": {},          # Map of peer-to-peer latencies
            "bandwidth_map": {},          # Map of peer bandwidth capacities
            "relay_candidates": set(),    # Peers that can serve as relays
            "edge_peers": set(),          # Peers that should not relay content
            "optimization_history": []    # History of topology changes
        }
    
    async def join_peer(self, peer_id: str, peer_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new peer to the session with specified role and capabilities.
        
        Args:
            peer_id: Unique identifier for the peer
            peer_info: Dictionary with peer information including role, capabilities, and client info
            
        Returns:
            Dict with join results and peer connection information
        """
        if not self.active:
            return {
                "success": False,
                "error": "Session is no longer active",
                "session_id": self.session_id
            }
            
        if len(self.peers) >= self.max_peers:
            return {
                "success": False,
                "error": f"Maximum number of peers ({self.max_peers}) reached",
                "session_id": self.session_id
            }
            
        # Extract peer information
        role = peer_info.get("role", PeerRole.VIEWER.value)
        capabilities = peer_info.get("capabilities", {})
        client_info = peer_info.get("client_info", {})
        
        # Create peer entry
        self.peers[peer_id] = {
            "role": role,
            "capabilities": capabilities,
            "client_info": client_info,
            "joined_at": time.time(),
            "last_activity": time.time(),
            "tracks_published": [],
            "tracks_subscribed": [],
            "connection_quality": 100,
            "metadata": peer_info.get("metadata", {})
        }
        
        # Initialize peer's place in the mesh
        self.peer_mesh[peer_id] = set()
        
        # Update session statistics
        self.statistics["total_peers_joined"] += 1
        self.statistics["current_peer_count"] = len(self.peers)
        self.statistics["max_concurrent_peers"] = max(
            self.statistics["max_concurrent_peers"], 
            self.statistics["current_peer_count"]
        )
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Emit peer joined notification
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.WEBRTC_CONNECTION_CREATED, 
                {
                    "session_id": self.session_id,
                    "peer_id": peer_id,
                    "role": role,
                    "timestamp": time.time()
                },
                source="streaming_session"
            )
        
        # Return success with session information
        peers_info = {p_id: {"role": info["role"]} for p_id, info in self.peers.items()}
        return {
            "success": True,
            "session_id": self.session_id,
            "session_type": self.session_type,
            "peer_id": peer_id,
            "peers": peers_info,
            "content_sources": list(self.content_sources.keys()),
            "join_time": time.time(),
            "tracks_available": self._get_available_tracks_for_peer(peer_id)
        }
    
    async def leave_peer(self, peer_id: str) -> Dict[str, Any]:
        """
        Remove a peer from the session and clean up its connections.
        
        Args:
            peer_id: Identifier of the peer to remove
            
        Returns:
            Dict with leave results
        """
        if peer_id not in self.peers:
            return {
                "success": False,
                "error": "Peer not found in session",
                "session_id": self.session_id
            }
        
        # Get peer info before removal
        peer_info = self.peers[peer_id].copy()
        
        # Clean up peer's tracks
        tracks_to_remove = []
        for track_id, track_info in self.tracks.items():
            if track_info.get("publisher") == peer_id:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            await self.remove_track(track_id)
        
        # Clean up peer connections
        connections_to_remove = []
        for pc_id, pc in self.peer_connections.items():
            if pc_id.startswith(f"{peer_id}:") or pc_id.endswith(f":{peer_id}"):
                connections_to_remove.append(pc_id)
        
        for pc_id in connections_to_remove:
            await self._close_peer_connection(pc_id)
        
        # Remove peer from mesh tracking
        if peer_id in self.peer_mesh:
            # Remove connections to this peer from other peers' sets
            for other_peer in self.peer_mesh:
                if peer_id in self.peer_mesh[other_peer]:
                    self.peer_mesh[other_peer].remove(peer_id)
            
            # Remove this peer's connections
            del self.peer_mesh[peer_id]
        
        # Remove peer from relays if present
        if peer_id in self.topology_optimizer["relay_candidates"]:
            self.topology_optimizer["relay_candidates"].remove(peer_id)
        
        if peer_id in self.topology_optimizer["edge_peers"]:
            self.topology_optimizer["edge_peers"].remove(peer_id)
        
        # Remove peer from session
        del self.peers[peer_id]
        
        # Update session statistics
        self.statistics["current_peer_count"] = len(self.peers)
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Check if session should be closed (no more peers)
        if not self.peers and self.active:
            self.active = False
            self.statistics["session_duration"] = time.time() - self.created_at
            
            # Emit session closed notification
            if HAVE_DEPENDENCIES:
                await emit_event(
                    NotificationType.WEBRTC_CONNECTION_CLOSED, 
                    {
                        "session_id": self.session_id,
                        "duration": self.statistics["session_duration"],
                        "reason": "All peers left"
                    },
                    source="streaming_session"
                )
        
        # Emit peer left notification
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.WEBRTC_CONNECTION_CLOSED, 
                {
                    "session_id": self.session_id,
                    "peer_id": peer_id,
                    "role": peer_info["role"],
                    "duration": time.time() - peer_info["joined_at"],
                    "timestamp": time.time()
                },
                source="streaming_session"
            )
        
        # Optimize session topology after peer departure
        if self.active and len(self.peers) > 1:
            await self._optimize_session_topology()
        
        return {
            "success": True,
            "session_id": self.session_id,
            "peer_id": peer_id,
            "duration": time.time() - peer_info["joined_at"]
        }
    
    async def create_peer_connection(self, source_peer_id: str, target_peer_id: str) -> Dict[str, Any]:
        """
        Create a WebRTC peer connection between two peers in the session.
        
        Args:
            source_peer_id: ID of the peer initiating the connection
            target_peer_id: ID of the peer receiving the connection
            
        Returns:
            Dict with connection results and SDP offer
        """
        # Validate both peers exist in the session
        if source_peer_id not in self.peers:
            return {
                "success": False,
                "error": "Source peer not found in session",
                "session_id": self.session_id
            }
            
        if target_peer_id not in self.peers:
            return {
                "success": False,
                "error": "Target peer not found in session",
                "session_id": self.session_id
            }
        
        # Create a unique connection ID
        pc_id = f"{source_peer_id}:{target_peer_id}"
        
        # Check if connection already exists
        if pc_id in self.peer_connections:
            return {
                "success": False,
                "error": "Connection already exists between these peers",
                "pc_id": pc_id
            }
        
        # Create new RTCPeerConnection with ICE servers
        ice_servers = [
            {"urls": ["stun:stun.l.google.com:19302"]},
            {"urls": ["stun:stun1.l.google.com:19302"]}
        ]
        
        rtc_configuration = {
            "iceServers": ice_servers,
            "iceTransportPolicy": "all",
            "bundlePolicy": "max-bundle",
            "rtcpMuxPolicy": "require",
            "sdpSemantics": "unified-plan"
        }
        
        pc = RTCPeerConnection(configuration=rtc_configuration)
        self.peer_connections[pc_id] = pc
        
        # Setup connection state monitoring
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            self.logger.info(f"Connection state for {pc_id}: {pc.connectionState}")
            
            if pc.connectionState == "connected":
                # Update mesh tracking
                self.peer_mesh[source_peer_id].add(target_peer_id)
                self.peer_mesh[target_peer_id].add(source_peer_id)
                
                # Emit connection established notification
                if HAVE_DEPENDENCIES:
                    await emit_event(
                        NotificationType.WEBRTC_CONNECTION_ESTABLISHED, 
                        {
                            "session_id": self.session_id,
                            "connection_id": pc_id,
                            "source_peer": source_peer_id,
                            "target_peer": target_peer_id,
                            "timestamp": time.time()
                        },
                        source="streaming_session"
                    )
            
            elif pc.connectionState in ["failed", "closed"]:
                # Clean up mesh tracking
                if source_peer_id in self.peer_mesh and target_peer_id in self.peer_mesh[source_peer_id]:
                    self.peer_mesh[source_peer_id].remove(target_peer_id)
                
                if target_peer_id in self.peer_mesh and source_peer_id in self.peer_mesh[target_peer_id]:
                    self.peer_mesh[target_peer_id].remove(source_peer_id)
                
                # Emit connection closed notification
                if HAVE_DEPENDENCIES:
                    await emit_event(
                        NotificationType.WEBRTC_CONNECTION_CLOSED, 
                        {
                            "session_id": self.session_id,
                            "connection_id": pc_id,
                            "source_peer": source_peer_id,
                            "target_peer": target_peer_id,
                            "state": pc.connectionState,
                            "timestamp": time.time()
                        },
                        source="streaming_session"
                    )
                
                # Remove connection if it's still in our tracking
                if pc_id in self.peer_connections:
                    await self._close_peer_connection(pc_id)
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Return the offer to be sent to the target peer
        return {
            "success": True,
            "session_id": self.session_id,
            "pc_id": pc_id,
            "source_peer": source_peer_id,
            "target_peer": target_peer_id,
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        }
    
    async def handle_answer(self, pc_id: str, sdp: str, type_: str) -> Dict[str, Any]:
        """
        Handle a WebRTC answer for a peer connection.
        
        Args:
            pc_id: Peer connection ID (format: "source_peer:target_peer")
            sdp: Session Description Protocol string
            type_: SDP type (usually "answer")
            
        Returns:
            Dict indicating success or failure
        """
        if pc_id not in self.peer_connections:
            return {
                "success": False,
                "error": f"Unknown peer connection ID: {pc_id}",
                "session_id": self.session_id
            }
        
        pc = self.peer_connections[pc_id]
        
        try:
            # Set the remote description
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type=type_)
            )
            
            # Update session activity timestamp
            self.last_activity = time.time()
            
            return {
                "success": True,
                "session_id": self.session_id,
                "pc_id": pc_id
            }
        except Exception as e:
            self.logger.error(f"Error handling WebRTC answer: {e}")
            self.statistics["errors"] += 1
            
            return {
                "success": False,
                "error": f"Error setting remote description: {str(e)}",
                "session_id": self.session_id,
                "pc_id": pc_id
            }
    
    async def handle_candidate(self, pc_id: str, candidate: str, 
                             sdp_mid: str, sdp_mline_index: int) -> Dict[str, Any]:
        """
        Handle an ICE candidate for a peer connection.
        
        Args:
            pc_id: Peer connection ID
            candidate: ICE candidate string
            sdp_mid: Media stream identifier
            sdp_mline_index: Media line index
            
        Returns:
            Dict indicating success or failure
        """
        if pc_id not in self.peer_connections:
            return {
                "success": False,
                "error": f"Unknown peer connection ID: {pc_id}",
                "session_id": self.session_id
            }
        
        pc = self.peer_connections[pc_id]
        
        try:
            # Add the ICE candidate
            await pc.addIceCandidate({
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index
            })
            
            # Update session activity timestamp
            self.last_activity = time.time()
            
            return {
                "success": True,
                "session_id": self.session_id,
                "pc_id": pc_id
            }
        except Exception as e:
            self.logger.error(f"Error handling ICE candidate: {e}")
            self.statistics["errors"] += 1
            
            return {
                "success": False,
                "error": f"Error adding ICE candidate: {str(e)}",
                "session_id": self.session_id,
                "pc_id": pc_id
            }
    
    async def add_track(self, peer_id: str, track_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a media track to the session from a peer's stream or IPFS content.
        
        Args:
            peer_id: ID of the peer adding the track
            track_info: Information about the track including kind, source, and options
            
        Returns:
            Dict with track addition results
        """
        if peer_id not in self.peers:
            return {
                "success": False,
                "error": "Peer not found in session",
                "session_id": self.session_id
            }
        
        # Extract track information
        track_id = track_info.get("track_id") or f"track_{uuid.uuid4()}"
        kind = track_info.get("kind", "video")
        source_type = track_info.get("source_type", "live")  # "live" or "ipfs"
        source = track_info.get("source")  # CID if source_type is "ipfs"
        options = track_info.get("options", {})
        
        # Create the track based on source type
        if source_type == "ipfs" and source:
            # Create track from IPFS content
            if not self.ipfs_api:
                return {
                    "success": False,
                    "error": "IPFS API not available for content tracks",
                    "session_id": self.session_id
                }
            
            try:
                # Create IPFSMediaStreamTrack for the content
                frame_rate = options.get("frame_rate", 30)
                quality = options.get("quality", "auto")
                
                ipfs_track = IPFSMediaStreamTrack(
                    ipfs_api=self.ipfs_api,
                    cid=source,
                    kind=kind,
                    frame_rate=frame_rate
                )
                
                # Set quality if supported
                if hasattr(ipfs_track, '_bitrate_controller') and hasattr(ipfs_track._bitrate_controller, 'set_quality'):
                    ipfs_track._bitrate_controller.set_quality(quality)
                
                # Create a media relay for distributing this track to multiple peers
                relay = MediaRelay()
                relayed_track = relay.subscribe(ipfs_track)
                
                # Store track information
                self.tracks[track_id] = {
                    "track_id": track_id,
                    "kind": kind,
                    "publisher": peer_id,
                    "source_type": source_type,
                    "source": source,
                    "original_track": ipfs_track,
                    "relay": relay,
                    "relayed_track": relayed_track,
                    "subscribers": set(),
                    "created_at": time.time(),
                    "options": options
                }
                
                # Store the relay for cleanup
                self.media_relays[track_id] = relay
                
                # Register content source
                self.content_sources[source] = {
                    "cid": source,
                    "added_by": peer_id,
                    "added_at": time.time(),
                    "track_id": track_id,
                    "kind": kind
                }
                
            except Exception as e:
                self.logger.error(f"Error creating track from IPFS content: {e}")
                self.statistics["errors"] += 1
                
                return {
                    "success": False,
                    "error": f"Error creating track from IPFS content: {str(e)}",
                    "session_id": self.session_id
                }
                
        elif source_type == "live":
            # For live tracks, we'll set up placeholders - the actual track will be 
            # added via the peer connection when the client adds it
            
            # Create a media relay for distributing this track to multiple peers
            relay = MediaRelay()
            
            # Store track information (without the actual track yet)
            self.tracks[track_id] = {
                "track_id": track_id,
                "kind": kind,
                "publisher": peer_id,
                "source_type": source_type,
                "source": source,
                "relay": relay,
                "subscribers": set(),
                "created_at": time.time(),
                "options": options,
                "pending": True  # Mark as pending until actual track is received
            }
            
            # Store the relay for cleanup
            self.media_relays[track_id] = relay
            
        else:
            return {
                "success": False,
                "error": f"Unsupported source type: {source_type}",
                "session_id": self.session_id
            }
        
        # Update peer's published tracks
        self.peers[peer_id]["tracks_published"].append(track_id)
        
        # Update session statistics
        self.statistics["total_tracks_shared"] += 1
        self.statistics["current_track_count"] += 1
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Emit track added notification
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.WEBRTC_STREAM_STARTED, 
                {
                    "session_id": self.session_id,
                    "track_id": track_id,
                    "peer_id": peer_id,
                    "kind": kind,
                    "source_type": source_type,
                    "timestamp": time.time()
                },
                source="streaming_session"
            )
        
        # Consider reoptimizing session topology for new track
        if len(self.peers) > 2:
            await self._optimize_session_topology()
        
        return {
            "success": True,
            "session_id": self.session_id,
            "track_id": track_id,
            "kind": kind,
            "source_type": source_type,
            "source": source
        }
    
    async def remove_track(self, track_id: str) -> Dict[str, Any]:
        """
        Remove a media track from the session.
        
        Args:
            track_id: ID of the track to remove
            
        Returns:
            Dict with track removal results
        """
        if track_id not in self.tracks:
            return {
                "success": False,
                "error": "Track not found in session",
                "session_id": self.session_id
            }
        
        track_info = self.tracks[track_id]
        publisher_id = track_info["publisher"]
        
        # Stop the original track if it exists and has a stop method
        if "original_track" in track_info and hasattr(track_info["original_track"], "stop"):
            track_info["original_track"].stop()
        
        # Clean up subscribers
        for peer_id in list(track_info.get("subscribers", set())):
            if peer_id in self.peers:
                if track_id in self.peers[peer_id]["tracks_subscribed"]:
                    self.peers[peer_id]["tracks_subscribed"].remove(track_id)
        
        # Remove from publisher's tracks
        if publisher_id in self.peers and track_id in self.peers[publisher_id]["tracks_published"]:
            self.peers[publisher_id]["tracks_published"].remove(track_id)
        
        # Remove content source reference if this is an IPFS track
        if track_info.get("source_type") == "ipfs" and track_info.get("source") in self.content_sources:
            del self.content_sources[track_info["source"]]
        
        # Clean up media relay
        if track_id in self.media_relays:
            del self.media_relays[track_id]
        
        # Remove track from tracking
        del self.tracks[track_id]
        
        # Update session statistics
        self.statistics["current_track_count"] = len(self.tracks)
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Emit track removed notification
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.WEBRTC_STREAM_ENDED, 
                {
                    "session_id": self.session_id,
                    "track_id": track_id,
                    "peer_id": publisher_id,
                    "kind": track_info["kind"],
                    "source_type": track_info.get("source_type"),
                    "timestamp": time.time()
                },
                source="streaming_session"
            )
        
        return {
            "success": True,
            "session_id": self.session_id,
            "track_id": track_id
        }
    
    async def subscribe_to_track(self, peer_id: str, track_id: str) -> Dict[str, Any]:
        """
        Subscribe a peer to receive a specific track.
        
        Args:
            peer_id: ID of the peer subscribing
            track_id: ID of the track to subscribe to
            
        Returns:
            Dict with subscription results
        """
        if peer_id not in self.peers:
            return {
                "success": False,
                "error": "Peer not found in session",
                "session_id": self.session_id
            }
            
        if track_id not in self.tracks:
            return {
                "success": False,
                "error": "Track not found in session",
                "session_id": self.session_id
            }
        
        track_info = self.tracks[track_id]
        publisher_id = track_info["publisher"]
        
        # Check if this is a self-subscription (publisher subscribing to their own track)
        if publisher_id == peer_id:
            return {
                "success": False,
                "error": "Cannot subscribe to your own published track",
                "session_id": self.session_id
            }
        
        # Check if already subscribed
        if peer_id in track_info.get("subscribers", set()):
            return {
                "success": False, 
                "error": "Already subscribed to this track",
                "session_id": self.session_id,
                "track_id": track_id
            }
        
        # Determine the best source peer (direct publisher or relay)
        source_peer_id = await self._determine_best_source_for_track(peer_id, track_id)
        
        # Create/get peer connection between subscriber and source
        pc_id = f"{source_peer_id}:{peer_id}"
        
        if pc_id not in self.peer_connections:
            # Create new connection
            connection_result = await self.create_peer_connection(source_peer_id, peer_id)
            
            if not connection_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to create peer connection: {connection_result.get('error')}",
                    "session_id": self.session_id
                }
                
            pc = self.peer_connections[pc_id]
        else:
            pc = self.peer_connections[pc_id]
        
        # Get relayed track from media relay
        if "relay" not in track_info or "relayed_track" not in track_info:
            return {
                "success": False,
                "error": "Track relay not available",
                "session_id": self.session_id
            }
        
        relayed_track = track_info["relayed_track"]
        
        # Add track to peer connection
        sender = pc.addTrack(relayed_track)
        
        # Update tracking
        if "subscribers" not in track_info:
            track_info["subscribers"] = set()
            
        track_info["subscribers"].add(peer_id)
        self.peers[peer_id]["tracks_subscribed"].append(track_id)
        
        # Create new offer with the added track
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        return {
            "success": True,
            "session_id": self.session_id,
            "pc_id": pc_id,
            "track_id": track_id,
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
            "source_peer": source_peer_id
        }
    
    async def unsubscribe_from_track(self, peer_id: str, track_id: str) -> Dict[str, Any]:
        """
        Unsubscribe a peer from a specific track.
        
        Args:
            peer_id: ID of the peer unsubscribing
            track_id: ID of the track to unsubscribe from
            
        Returns:
            Dict with unsubscription results
        """
        if peer_id not in self.peers:
            return {
                "success": False,
                "error": "Peer not found in session",
                "session_id": self.session_id
            }
            
        if track_id not in self.tracks:
            return {
                "success": False,
                "error": "Track not found in session",
                "session_id": self.session_id
            }
        
        track_info = self.tracks[track_id]
        
        # Check if actually subscribed
        if peer_id not in track_info.get("subscribers", set()):
            return {
                "success": False, 
                "error": "Not subscribed to this track",
                "session_id": self.session_id,
                "track_id": track_id
            }
        
        # Remove from subscribers list
        track_info["subscribers"].remove(peer_id)
        
        # Remove from peer's subscribed tracks
        if track_id in self.peers[peer_id]["tracks_subscribed"]:
            self.peers[peer_id]["tracks_subscribed"].remove(track_id)
        
        # Update session activity timestamp
        self.last_activity = time.time()
        
        # Determine if we need to update peer connections
        # This would require renegotiation of the connection, which is complex
        # For now, we'll leave the track in the connection but note it's unsubscribed
        
        return {
            "success": True,
            "session_id": self.session_id,
            "track_id": track_id,
            "peer_id": peer_id
        }
    
    async def _determine_best_source_for_track(self, subscriber_id: str, track_id: str) -> str:
        """
        Determine the best peer to serve as the source for a track subscription.
        
        This implements the intelligent routing logic for efficient distribution.
        
        Args:
            subscriber_id: ID of the peer that wants to subscribe
            track_id: ID of the track to subscribe to
            
        Returns:
            Peer ID of the best source (publisher or relay)
        """
        track_info = self.tracks[track_id]
        publisher_id = track_info["publisher"]
        
        # Simple case: if few peers or broadcast mode, use direct connection to publisher
        if len(self.peers) <= 3 or self.session_type == "broadcast":
            return publisher_id
        
        # For mesh or hybrid modes, consider using relay peers
        if self.session_type in ["mesh", "hybrid"]:
            # Get current subscribers who could potentially relay
            potential_relays = [
                peer_id for peer_id in track_info.get("subscribers", set())
                if peer_id in self.topology_optimizer["relay_candidates"]
            ]
            
            if not potential_relays:
                return publisher_id
            
            # Find the best relay based on connection quality and load
            best_relay = None
            best_score = -1
            
            for relay_id in potential_relays:
                # Skip if already at max connections
                relay_connections = len(self.peer_mesh.get(relay_id, set()))
                if relay_connections >= self.topology_optimizer["max_fan_out"]:
                    continue
                
                # Calculate score based on quality and number of connections
                quality = self.peers[relay_id].get("connection_quality", 0)
                load_factor = 1 - (relay_connections / self.topology_optimizer["max_fan_out"])
                score = quality * load_factor
                
                if score > best_score:
                    best_score = score
                    best_relay = relay_id
            
            # Use the best relay if it meets quality threshold, otherwise use publisher
            if best_relay and best_score >= self.topology_optimizer["quality_threshold"]:
                return best_relay
        
        # Default to publisher
        return publisher_id
    
    async def _optimize_session_topology(self) -> None:
        """
        Optimize the peer connection topology for efficient media distribution.
        
        This analyzes the current session state and may restructure connections
        for better performance and reduced bandwidth usage.
        """
        now = time.time()
        optimizer = self.topology_optimizer
        
        # Only optimize periodically
        if now - optimizer["last_optimization"] < optimizer["optimization_interval"]:
            return
        
        optimizer["last_optimization"] = now
        
        # 1. Identify potential relay candidates (peers with good connectivity)
        optimizer["relay_candidates"] = set()
        optimizer["edge_peers"] = set()
        
        for peer_id, peer_info in self.peers.items():
            role = peer_info["role"]
            
            # Peers explicitly marked as relays or participants with good connectivity
            if (role == PeerRole.RELAY.value or 
                (role == PeerRole.PARTICIPANT.value and peer_info.get("connection_quality", 0) >= optimizer["quality_threshold"])):
                optimizer["relay_candidates"].add(peer_id)
            
            # Mark viewers and poor quality connections as edge peers
            elif role == PeerRole.VIEWER.value or peer_info.get("connection_quality", 0) < optimizer["quality_threshold"]:
                optimizer["edge_peers"].add(peer_id)
        
        # 2. Analyze current topology for inefficiencies
        # This is a simplified version - a real implementation would do more analysis
        for track_id, track_info in self.tracks.items():
            publisher_id = track_info["publisher"]
            subscribers = track_info.get("subscribers", set())
            
            # Skip if few subscribers
            if len(subscribers) <= 2:
                continue
            
            # Check if publisher has too many direct connections
            direct_subscribers = set()
            for pc_id in self.peer_connections:
                if pc_id.startswith(f"{publisher_id}:"):
                    target_id = pc_id.split(":")[1]
                    if target_id in subscribers:
                        direct_subscribers.add(target_id)
            
            # If publisher is overloaded, redistribute some connections
            if len(direct_subscribers) > optimizer["max_fan_out"]:
                # Find subscribers that could be served by relays instead
                subscribers_to_move = list(direct_subscribers - optimizer["relay_candidates"])
                
                # Keep within max fan-out limit
                subscribers_to_move = subscribers_to_move[:len(direct_subscribers) - optimizer["max_fan_out"]]
                
                for sub_id in subscribers_to_move:
                    # Find a suitable relay
                    best_relay = await self._determine_best_source_for_track(sub_id, track_id)
                    
                    if best_relay != publisher_id:
                        # Create new connection through relay
                        pc_id_old = f"{publisher_id}:{sub_id}"
                        pc_id_new = f"{best_relay}:{sub_id}"
                        
                        # Only proceed if we don't already have the new connection
                        if pc_id_new not in self.peer_connections:
                            # Log the topology change
                            self.logger.info(
                                f"Topology optimization: Moving subscriber {sub_id} from " +
                                f"direct connection to publisher {publisher_id} to relay {best_relay}"
                            )
                            
                            # Record change in history
                            optimizer["optimization_history"].append({
                                "timestamp": now,
                                "action": "redistribute",
                                "track_id": track_id,
                                "subscriber": sub_id,
                                "old_source": publisher_id,
                                "new_source": best_relay
                            })
                            
                            # In a real implementation, we would create the new connection
                            # and update subscription paths, but this is complex and requires
                            # renegotiating connections, which we'll simplify for this example
        
        # Keep optimization history bounded
        if len(optimizer["optimization_history"]) > 100:
            optimizer["optimization_history"] = optimizer["optimization_history"][-100:]
    
    async def _close_peer_connection(self, pc_id: str) -> None:
        """
        Close a peer connection and clean up resources.
        
        Args:
            pc_id: ID of the peer connection to close
        """
        if pc_id not in self.peer_connections:
            return
        
        pc = self.peer_connections[pc_id]
        
        # Close the peer connection
        await pc.close()
        
        # Remove from tracking
        del self.peer_connections[pc_id]
        
        # Extract peer IDs from connection ID
        try:
            source_id, target_id = pc_id.split(":")
            
            # Update mesh tracking
            if source_id in self.peer_mesh and target_id in self.peer_mesh[source_id]:
                self.peer_mesh[source_id].remove(target_id)
            
            if target_id in self.peer_mesh and source_id in self.peer_mesh[target_id]:
                self.peer_mesh[target_id].remove(source_id)
        except:
            pass
    
    def _get_available_tracks_for_peer(self, peer_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of tracks available for a peer to subscribe to.
        
        Args:
            peer_id: ID of the peer
            
        Returns:
            List of track information dictionaries
        """
        available_tracks = []
        
        for track_id, track_info in self.tracks.items():
            # Don't include peer's own tracks
            if track_info["publisher"] == peer_id:
                continue
            
            # Don't include tracks already subscribed to
            if peer_id in track_info.get("subscribers", set()):
                continue
            
            available_tracks.append({
                "track_id": track_id,
                "kind": track_info["kind"],
                "publisher": track_info["publisher"],
                "source_type": track_info.get("source_type"),
                "source": track_info.get("source")
            })
        
        return available_tracks
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the session state.
        
        Returns:
            Dict with session information
        """
        # Calculate current session duration
        current_duration = time.time() - self.created_at
        
        # Create peer information without sensitive details
        peers_info = {}
        for peer_id, peer_info in self.peers.items():
            peers_info[peer_id] = {
                "role": peer_info["role"],
                "joined_at": peer_info["joined_at"],
                "tracks_published": peer_info["tracks_published"],
                "tracks_subscribed": peer_info["tracks_subscribed"],
                "duration": time.time() - peer_info["joined_at"]
            }
        
        # Create track information
        tracks_info = {}
        for track_id, track_info in self.tracks.items():
            tracks_info[track_id] = {
                "kind": track_info["kind"],
                "publisher": track_info["publisher"],
                "source_type": track_info.get("source_type"),
                "source": track_info.get("source"),
                "subscribers": list(track_info.get("subscribers", set())),
                "created_at": track_info["created_at"]
            }
        
        # Create content sources information
        content_info = {}
        for cid, source_info in self.content_sources.items():
            content_info[cid] = {
                "added_by": source_info["added_by"],
                "added_at": source_info["added_at"],
                "track_id": source_info["track_id"],
                "kind": source_info["kind"]
            }
        
        # Create mesh topology information
        mesh_info = {}
        for peer_id, connections in self.peer_mesh.items():
            mesh_info[peer_id] = list(connections)
        
        return {
            "session_id": self.session_id,
            "session_type": self.session_type,
            "created_at": self.created_at,
            "duration": current_duration,
            "active": self.active,
            "last_activity": self.last_activity,
            "max_peers": self.max_peers,
            "public": self.public,
            "peers": peers_info,
            "tracks": tracks_info,
            "content_sources": content_info,
            "connections": list(self.peer_connections.keys()),
            "mesh_topology": mesh_info,
            "statistics": self.statistics,
            "metadata": self.metadata
        }


class SessionManager:
    """
    Manages multiple streaming sessions and provides discovery services.
    
    This class creates, maintains, and controls access to streaming sessions,
    allowing clients to discover and join existing sessions or create new ones.
    """
    
    def __init__(self, ipfs_api=None):
        """
        Initialize the session manager.
        
        Args:
            ipfs_api: IPFS API instance for content access
        """
        self.ipfs_api = ipfs_api
        self.sessions: Dict[str, StreamingSession] = {}
        self.created_at = time.time()
        self.cleanup_interval = 300  # 5 minutes
        self.session_timeout = 1800  # 30 minutes of inactivity
        self.last_cleanup = time.time()
        self.statistics = {
            "total_sessions_created": 0,
            "active_sessions": 0,
            "total_peers": 0,
            "content_sources": set(),
            "errors": 0
        }
        
        # Set up background cleanup task
        self._start_cleanup_task()
        
        # Logger
        self.logger = logging.getLogger(__name__)
    
    def _start_cleanup_task(self):
        """Start background task for session cleanup."""
        # Create task and store it for proper cancellation during shutdown
        if not hasattr(self, 'cleanup_task') or self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            # Make sure the task doesn't disappear due to garbage collection
            self.cleanup_task.add_done_callback(lambda t: self._handle_cleanup_task_done(t))
    
    def _handle_cleanup_task_done(self, task):
        """Handle cleanup task completion."""
        # Only log if the task wasn't cancelled as part of normal shutdown
        if not task.cancelled() and task.exception() is not None:
            self.logger.error(f"Cleanup task failed with error: {task.exception()}")
        # Clear the reference if this matches our current cleanup task
        if hasattr(self, 'cleanup_task') and self.cleanup_task == task:
            self.cleanup_task = None
        anyio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically check for inactive sessions and clean them up."""
        while True:
            try:
                await anyio.sleep(self.cleanup_interval)
                await self.cleanup_inactive_sessions()
            except Exception as e:
                self.logger.error(f"Error in session cleanup: {e}")
    
    async def create_session(self, session_options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new streaming session.
        
        Args:
            session_options: Dictionary with session configuration options
            
        Returns:
            Dict with session creation results
        """
        # Generate a unique session ID if not provided
        session_id = session_options.get("session_id") or f"session_{uuid.uuid4()}"
        
        # Check if session ID already exists
        if session_id in self.sessions:
            return {
                "success": False,
                "error": "Session ID already exists",
                "session_id": session_id
            }
        
        # Extract session options
        session_type = session_options.get("session_type", "broadcast")
        max_peers = session_options.get("max_peers", 20)
        public = session_options.get("public", False)
        metadata = session_options.get("metadata", {})
        
        # Validate session type
        valid_session_types = ["broadcast", "mesh", "hybrid"]
        if session_type not in valid_session_types:
            return {
                "success": False,
                "error": f"Invalid session type: {session_type}. Must be one of {valid_session_types}",
                "session_id": session_id
            }
        
        # Create the session
        try:
            session = StreamingSession(
                session_id=session_id,
                ipfs_api=self.ipfs_api,
                session_type=session_type,
                max_peers=max_peers,
                public=public
            )
            
            # Add metadata
            session.metadata = metadata
            
            # Store the session
            self.sessions[session_id] = session
            
            # Update statistics
            self.statistics["total_sessions_created"] += 1
            self.statistics["active_sessions"] = len(self.sessions)
            
            # Emit session created notification
            if HAVE_DEPENDENCIES:
                await emit_event(
                    NotificationType.SYSTEM_INFO, 
                    {
                        "message": "New streaming session created",
                        "session_id": session_id,
                        "session_type": session_type,
                        "public": public
                    },
                    source="session_manager"
                )
            
            return {
                "success": True,
                "session_id": session_id,
                "created_at": session.created_at,
                "session_type": session_type,
                "max_peers": max_peers,
                "public": public
            }
            
        except Exception as e:
            self.logger.error(f"Error creating session: {e}")
            self.statistics["errors"] += 1
            
            return {
                "success": False,
                "error": f"Error creating session: {str(e)}",
                "session_id": session_id
            }
    
    async def shutdown(self) -> Dict[str, Any]:
        """
        Shut down the multi-peer controller and clean up all resources.
        
        Returns:
            Dict with shutdown results
        """
        self.logger.info("Shutting down WebRTC multi-peer controller")
        
        result = {
            "success": True,
            "component": "webrtc_multi_peer",
            "sessions_closed": 0,
            "errors": []
        }
        
        # Cancel cleanup task first
        if hasattr(self, 'cleanup_task') and self.cleanup_task is not None:
            try:
                if not self.cleanup_task.done() and not self.cleanup_task.cancelled():
                    self.cleanup_task.cancel()
                    # Wait for cancellation to complete with timeout
                    try:
                        await asyncio.wait_for(asyncio.gather(self.cleanup_task, return_exceptions=True), timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                self.cleanup_task = None
            except Exception as e:
                error_msg = f"Error cancelling cleanup task: {str(e)}"
                self.logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # Close all active sessions
        for session_id in list(self.sessions.keys()):
            try:
                close_result = await self.close_session(session_id)
                if close_result.get("success", False):
                    result["sessions_closed"] += 1
                else:
                    result["errors"].append(f"Failed to close session {session_id}: {close_result.get('error', 'Unknown error')}")
            except Exception as e:
                error_msg = f"Error closing session {session_id}: {str(e)}"
                self.logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # Clean up resources
        self.sessions.clear()
        
        # Update overall success status
        if result["errors"]:
            result["success"] = False
            
        self.logger.info(f"WebRTC multi-peer controller shutdown complete. Closed {result['sessions_closed']} sessions with {len(result['errors'])} errors")
        return result
    
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """
        Close a streaming session and clean up all resources.
        
        Args:
            session_id: ID of the session to close
            
        Returns:
            Dict with session closure results
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
                "session_id": session_id
            }
        
        session = self.sessions[session_id]
        
        # Get session info before cleanup
        session_info = session.get_session_info()
        
        try:
            # Close all peer connections
            for pc_id in list(session.peer_connections.keys()):
                await session._close_peer_connection(pc_id)
            
            # Clean up all tracks
            for track_id in list(session.tracks.keys()):
                await session.remove_track(track_id)
            
            # Mark session as inactive
            session.active = False
            session.statistics["session_duration"] = time.time() - session.created_at
            
            # Remove session from tracking
            del self.sessions[session_id]
            
            # Update statistics
            self.statistics["active_sessions"] = len(self.sessions)
            
            # Emit session closed notification
            if HAVE_DEPENDENCIES:
                await emit_event(
                    NotificationType.SYSTEM_INFO, 
                    {
                        "message": "Streaming session closed",
                        "session_id": session_id,
                        "duration": session_info["duration"],
                        "peer_count": len(session_info["peers"]),
                        "track_count": len(session_info["tracks"])
                    },
                    source="session_manager"
                )
            
            return {
                "success": True,
                "session_id": session_id,
                "duration": session_info["duration"],
                "peer_count": len(session_info["peers"]),
                "track_count": len(session_info["tracks"])
            }
            
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")
            self.statistics["errors"] += 1
            
            return {
                "success": False,
                "error": f"Error closing session: {str(e)}",
                "session_id": session_id
            }
    
    async def join_session(self, session_id: str, peer_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Join an existing session with the provided peer information.
        
        Args:
            session_id: ID of the session to join
            peer_info: Dictionary with peer information
            
        Returns:
            Dict with session join results
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
                "session_id": session_id
            }
        
        session = self.sessions[session_id]
        
        if not session.active:
            return {
                "success": False,
                "error": "Session is no longer active",
                "session_id": session_id
            }
        
        # Extract peer information
        peer_id = peer_info.get("peer_id") or f"peer_{uuid.uuid4()}"
        
        # Try to join the session
        join_result = await session.join_peer(peer_id, peer_info)
        
        if join_result["success"]:
            # Update statistics
            self.statistics["total_peers"] = sum(
                len(s.peers) for s in self.sessions.values()
            )
        
            # Add content sources to global tracking
            for cid in session.content_sources:
                self.statistics["content_sources"].add(cid)
        
        return join_result
    
    async def leave_session(self, session_id: str, peer_id: str) -> Dict[str, Any]:
        """
        Leave a session and clean up peer resources.
        
        Args:
            session_id: ID of the session to leave
            peer_id: ID of the peer leaving
            
        Returns:
            Dict with session leave results
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
                "session_id": session_id
            }
        
        session = self.sessions[session_id]
        leave_result = await session.leave_peer(peer_id)
        
        if leave_result["success"]:
            # Update statistics
            self.statistics["total_peers"] = sum(
                len(s.peers) for s in self.sessions.values()
            )
            
            # Check if session is now empty and should be removed
            if session_id in self.sessions and not session.peers:
                await self.close_session(session_id)
        
        return leave_result
    
    async def get_sessions(self, public_only: bool = False) -> Dict[str, Any]:
        """
        Get a list of available sessions.
        
        Args:
            public_only: If True, only return public sessions
            
        Returns:
            Dict with available sessions information
        """
        sessions_list = []
        
        for session_id, session in self.sessions.items():
            if public_only and not session.public:
                continue
            
            sessions_list.append({
                "session_id": session_id,
                "session_type": session.session_type,
                "created_at": session.created_at,
                "peer_count": len(session.peers),
                "track_count": len(session.tracks),
                "content_sources": list(session.content_sources.keys()),
                "public": session.public,
                "active": session.active,
                "metadata": session.metadata
            })
        
        return {
            "success": True,
            "sessions": sessions_list,
            "count": len(sessions_list),
            "timestamp": time.time()
        }
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific session.
        
        Args:
            session_id: ID of the session to get information for
            
        Returns:
            Dict with session information
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found",
                "session_id": session_id
            }
        
        session = self.sessions[session_id]
        session_info = session.get_session_info()
        
        return {
            "success": True,
            "session_info": session_info
        }
    
    async def cleanup_inactive_sessions(self) -> Dict[str, Any]:
        """
        Clean up inactive sessions that have timed out.
        
        Returns:
            Dict with cleanup results
        """
        now = time.time()
        self.last_cleanup = now
        
        closed_sessions = []
        
        for session_id, session in list(self.sessions.items()):
            # Close sessions with no activity for longer than timeout period
            if now - session.last_activity > self.session_timeout:
                close_result = await self.close_session(session_id)
                
                if close_result["success"]:
                    closed_sessions.append({
                        "session_id": session_id,
                        "duration": close_result["duration"],
                        "reason": "inactivity"
                    })
        
        return {
            "success": True,
            "closed_sessions": closed_sessions,
            "count": len(closed_sessions),
            "timestamp": now
        }
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the session manager and all sessions.
        
        Returns:
            Dict with manager statistics
        """
        # Update active sessions count
        self.statistics["active_sessions"] = len(self.sessions)
        
        # Update total peers count
        self.statistics["total_peers"] = sum(
            len(s.peers) for s in self.sessions.values()
        )
        
        # Get content source count
        content_sources = set()
        for session in self.sessions.values():
            content_sources.update(session.content_sources.keys())
        
        self.statistics["content_sources"] = content_sources
        content_source_count = len(content_sources)
        
        # Calculate uptime
        uptime = time.time() - self.created_at
        
        return {
            "uptime": uptime,
            "active_sessions": self.statistics["active_sessions"],
            "total_sessions_created": self.statistics["total_sessions_created"],
            "active_peers": self.statistics["total_peers"],
            "content_sources": content_source_count,
            "last_cleanup": self.last_cleanup,
            "errors": self.statistics["errors"],
            "timestamp": time.time()
        }


# Global session manager instance
session_manager = SessionManager()


async def handle_multi_peer_signaling(websocket, ipfs_api=None):
    """
    Handle WebSocket signaling for multi-peer streaming sessions.
    
    This function provides the WebSocket endpoint for session management,
    peer coordination, and media stream exchange for multi-peer streaming.
    
    Args:
        websocket: WebSocket connection
        ipfs_api: IPFS API instance
    """
    if not HAVE_WEBRTC:
        await websocket.send_json({
            "type": "error",
            "message": "WebRTC dependencies not available. Install with 'pip install ipfs_kit_py[webrtc]'"
        })
        return
    
    # Initialize session manager if needed
    global session_manager
    if not session_manager.ipfs_api and ipfs_api:
        session_manager.ipfs_api = ipfs_api
    
    # Generate a client ID for this signaling connection
    client_id = f"client_{uuid.uuid4()}"
    
    # Client state tracking
    current_session_id = None
    current_peer_id = None
    
    # Log the new connection
    logger.info(f"New multi-peer signaling connection: {client_id}")
    
    try:
        # Accept the connection
        await websocket.accept()
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "message": "IPFS multi-peer streaming signaling server connected",
            "timestamp": time.time()
        })
        
        # Handle signaling messages
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                if msg_type == "create_session":
                    # Create a new streaming session
                    session_options = message.get("session_options", {})
                    
                    logger.info(f"Creating new session with options: {session_options}")
                    
                    result = await session_manager.create_session(session_options)
                    
                    if result["success"]:
                        # Update current session tracking
                        current_session_id = result["session_id"]
                    
                    await websocket.send_json({
                        "type": "session_created",
                        "result": result
                    })
                
                elif msg_type == "join_session":
                    # Join an existing session
                    session_id = message.get("session_id")
                    peer_info = message.get("peer_info", {})
                    
                    if not peer_info.get("peer_id"):
                        # Generate peer ID if not provided
                        peer_info["peer_id"] = f"peer_{uuid.uuid4()}"
                    
                    logger.info(f"Joining session {session_id} with peer info: {peer_info}")
                    
                    result = await session_manager.join_session(session_id, peer_info)
                    
                    if result["success"]:
                        # Update current session and peer tracking
                        current_session_id = session_id
                        current_peer_id = peer_info["peer_id"]
                    
                    await websocket.send_json({
                        "type": "session_joined",
                        "result": result
                    })
                
                elif msg_type == "leave_session":
                    # Leave the current session
                    session_id = message.get("session_id") or current_session_id
                    peer_id = message.get("peer_id") or current_peer_id
                    
                    if not session_id or not peer_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "No active session or peer ID not specified"
                        })
                        continue
                    
                    logger.info(f"Leaving session {session_id} as peer {peer_id}")
                    
                    result = await session_manager.leave_session(session_id, peer_id)
                    
                    if result["success"]:
                        # Clear current session and peer tracking
                        if session_id == current_session_id and peer_id == current_peer_id:
                            current_session_id = None
                            current_peer_id = None
                    
                    await websocket.send_json({
                        "type": "session_left",
                        "result": result
                    })
                
                elif msg_type == "get_sessions":
                    # Get available sessions
                    public_only = message.get("public_only", False)
                    
                    logger.debug(f"Getting available sessions (public_only={public_only})")
                    
                    result = await session_manager.get_sessions(public_only)
                    
                    await websocket.send_json({
                        "type": "sessions_list",
                        "result": result
                    })
                
                elif msg_type == "get_session_info":
                    # Get detailed information about a session
                    session_id = message.get("session_id") or current_session_id
                    
                    if not session_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "No session ID specified"
                        })
                        continue
                    
                    logger.debug(f"Getting session info for {session_id}")
                    
                    result = await session_manager.get_session_info(session_id)
                    
                    await websocket.send_json({
                        "type": "session_info",
                        "result": result
                    })
                
                elif msg_type == "create_peer_connection":
                    # Create a connection between two peers in the session
                    session_id = message.get("session_id") or current_session_id
                    source_peer_id = message.get("source_peer_id") or current_peer_id
                    target_peer_id = message.get("target_peer_id")
                    
                    if not session_id or not source_peer_id or not target_peer_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for peer connection"
                        })
                        continue
                    
                    logger.info(f"Creating peer connection from {source_peer_id} to {target_peer_id} in session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.create_peer_connection(source_peer_id, target_peer_id)
                    
                    await websocket.send_json({
                        "type": "peer_connection_created",
                        "result": result
                    })
                
                elif msg_type == "answer":
                    # Handle a WebRTC answer
                    session_id = message.get("session_id") or current_session_id
                    pc_id = message.get("pc_id")
                    sdp = message.get("sdp")
                    sdp_type = message.get("sdp_type") or "answer"
                    
                    if not session_id or not pc_id or not sdp:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for answer"
                        })
                        continue
                    
                    logger.debug(f"Handling WebRTC answer for connection {pc_id} in session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.handle_answer(pc_id, sdp, sdp_type)
                    
                    await websocket.send_json({
                        "type": "answer_handled",
                        "result": result
                    })
                
                elif msg_type == "candidate":
                    # Handle an ICE candidate
                    session_id = message.get("session_id") or current_session_id
                    pc_id = message.get("pc_id")
                    candidate = message.get("candidate")
                    sdp_mid = message.get("sdp_mid")
                    sdp_mline_index = message.get("sdp_mline_index")
                    
                    if not session_id or not pc_id or not candidate:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for ICE candidate"
                        })
                        continue
                    
                    logger.debug(f"Handling ICE candidate for connection {pc_id} in session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.handle_candidate(pc_id, candidate, sdp_mid, sdp_mline_index)
                    
                    # No response needed for candidates
                
                elif msg_type == "add_track":
                    # Add a media track to the session
                    session_id = message.get("session_id") or current_session_id
                    peer_id = message.get("peer_id") or current_peer_id
                    track_info = message.get("track_info", {})
                    
                    if not session_id or not peer_id or not track_info:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for adding track"
                        })
                        continue
                    
                    logger.info(f"Adding track from peer {peer_id} to session {session_id}: {track_info}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.add_track(peer_id, track_info)
                    
                    await websocket.send_json({
                        "type": "track_added",
                        "result": result
                    })
                
                elif msg_type == "remove_track":
                    # Remove a media track from the session
                    session_id = message.get("session_id") or current_session_id
                    track_id = message.get("track_id")
                    
                    if not session_id or not track_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for removing track"
                        })
                        continue
                    
                    logger.info(f"Removing track {track_id} from session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.remove_track(track_id)
                    
                    await websocket.send_json({
                        "type": "track_removed",
                        "result": result
                    })
                
                elif msg_type == "subscribe_to_track":
                    # Subscribe to receive a track
                    session_id = message.get("session_id") or current_session_id
                    peer_id = message.get("peer_id") or current_peer_id
                    track_id = message.get("track_id")
                    
                    if not session_id or not peer_id or not track_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for track subscription"
                        })
                        continue
                    
                    logger.info(f"Peer {peer_id} subscribing to track {track_id} in session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.subscribe_to_track(peer_id, track_id)
                    
                    await websocket.send_json({
                        "type": "track_subscription",
                        "result": result
                    })
                
                elif msg_type == "unsubscribe_from_track":
                    # Unsubscribe from a track
                    session_id = message.get("session_id") or current_session_id
                    peer_id = message.get("peer_id") or current_peer_id
                    track_id = message.get("track_id")
                    
                    if not session_id or not peer_id or not track_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Missing required parameters for track unsubscription"
                        })
                        continue
                    
                    logger.info(f"Peer {peer_id} unsubscribing from track {track_id} in session {session_id}")
                    
                    if session_id not in session_manager.sessions:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Session not found"
                        })
                        continue
                    
                    session = session_manager.sessions[session_id]
                    result = await session.unsubscribe_from_track(peer_id, track_id)
                    
                    await websocket.send_json({
                        "type": "track_unsubscription",
                        "result": result
                    })
                
                elif msg_type == "ping":
                    # Simple ping-pong for connection testing
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
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
                if HAVE_DEPENDENCIES:
                    await emit_event(
                        NotificationType.WEBRTC_ERROR,
                        {
                            "error": error_msg,
                            "client_id": client_id
                        },
                        source="multi_peer_signaling"
                    )
                
                await websocket.send_json({
                    "type": "error",
                    "message": error_msg
                })
    
    except Exception as e:
        error_msg = f"Multi-peer signaling error: {e}"
        logger.error(error_msg)
        
        # Emit error notification
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.WEBRTC_ERROR,
                {
                    "error": error_msg,
                    "client_id": client_id,
                    "stack_trace": str(e)
                },
                source="multi_peer_signaling"
            )
        
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
    
    finally:
        # Clean up any active sessions for this client
        if current_session_id and current_peer_id:
            try:
                await session_manager.leave_session(current_session_id, current_peer_id)
            except Exception as e:
                logger.error(f"Error cleaning up session: {e}")
        
        # Notify about signaling connection closing
        if HAVE_DEPENDENCIES:
            await emit_event(
                NotificationType.SYSTEM_INFO,
                {
                    "message": "Multi-peer signaling connection closed",
                    "client_id": client_id
                },
                source="multi_peer_signaling"
            )
        
        logger.info(f"Multi-peer signaling connection closed: {client_id}")