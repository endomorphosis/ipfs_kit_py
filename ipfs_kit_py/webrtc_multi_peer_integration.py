"""
WebRTC Multi-Peer Integration for IPFS Kit.

This module provides integration between the WebRTC multi-peer streaming functionality
and the rest of the IPFS Kit, including API endpoints, high-level interfaces,
and seamless access to IPFS content for streaming.

Key features:
1. API Integration: FastAPI endpoints for WebRTC multi-peer streaming
2. Session Discovery: API endpoints for discovering and joining streaming sessions
3. High-Level Interface: Simplified interface for common multi-peer streaming operations
4. IPFS Integration: Direct streaming of IPFS content in multi-peer sessions
5. Client Libraries: JavaScript client libraries for browser integration
6. Security Integration: Integration with streaming security features
7. Statistics Collection: Session and peer performance metrics
8. Media Processing: Optional video/audio processing capabilities

This module serves as the integration point between the multi-peer streaming system,
the IPFS Kit API, and client applications.
"""

import anyio
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Path, Depends, HTTPException

# Import Pydantic with version compatibility
try:
    import pydantic
    from pydantic import BaseModel, Field
    
    # Check for Pydantic v2
    PYDANTIC_V2 = pydantic.__version__.startswith('2.')
except ImportError:
    PYDANTIC_V2 = False
    
    # Fallback class if Pydantic isn't available
    class BaseModel:
        """Fallback BaseModel when Pydantic is not available."""
        pass
    Field = lambda *args, **kwargs: None

try:
    from . import webrtc_multi_peer
    from .webrtc_multi_peer import session_manager, handle_multi_peer_signaling, PeerRole
    from .websocket_notifications import emit_event, NotificationType
    from .high_level_api import IPFSSimpleAPI
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import security if available
try:
    from .streaming_security import StreamingSecurityManager, SecurityLevel, can_access_stream
    HAS_SECURITY = True
except ImportError:
    HAS_SECURITY = False

# Configure logging
logger = logging.getLogger(__name__)

# Define API models for request/response validation

class SessionOptions(BaseModel):
    """Options for creating a new streaming session."""
    session_id: Optional[str] = Field(None, description="Optional custom session ID")
    session_type: str = Field("broadcast", description="Session type: broadcast, mesh, or hybrid")
    max_peers: int = Field(20, description="Maximum number of peers allowed in the session")
    public: bool = Field(False, description="Whether this session is publicly discoverable")
    metadata: Dict[str, Any] = Field({}, description="Custom session metadata")
    security_level: Optional[str] = Field(None, description="Security level for the session")
    access_control: Optional[Dict[str, Any]] = Field(None, description="Access control configuration")

class PeerInfo(BaseModel):
    """Information about a peer joining a session."""
    peer_id: Optional[str] = Field(None, description="Optional custom peer ID")
    role: str = Field("viewer", description="Peer role: broadcaster, viewer, participant, relay, recorder")
    capabilities: Dict[str, Any] = Field({}, description="Peer capabilities")
    client_info: Dict[str, Any] = Field({}, description="Client information")
    metadata: Dict[str, Any] = Field({}, description="Custom peer metadata")
    auth_token: Optional[str] = Field(None, description="Authentication token if required")

class TrackInfo(BaseModel):
    """Information about a media track to add to a session."""
    track_id: Optional[str] = Field(None, description="Optional custom track ID")
    kind: str = Field("video", description="Track kind: video or audio")
    source_type: str = Field("live", description="Source type: live or ipfs")
    source: Optional[str] = Field(None, description="Source identifier (CID for IPFS)")
    options: Dict[str, Any] = Field({}, description="Track options like frame_rate, quality, etc.")

class SessionResponse(BaseModel):
    """Response model for session operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    session_id: str = Field(..., description="Session ID")
    error: Optional[str] = Field(None, description="Error message if not successful")

class SessionListResponse(BaseModel):
    """Response model for listing available sessions."""
    success: bool = Field(..., description="Whether the operation was successful")
    sessions: List[Dict[str, Any]] = Field(..., description="List of available sessions")
    count: int = Field(..., description="Number of sessions")

class SessionInfoResponse(BaseModel):
    """Response model for detailed session information."""
    success: bool = Field(..., description="Whether the operation was successful")
    session_info: Optional[Dict[str, Any]] = Field(None, description="Detailed session information")
    error: Optional[str] = Field(None, description="Error message if not successful")

# Integration class for high-level operations

class MultiPeerStreamingIntegration:
    """
    Integration class for WebRTC multi-peer streaming functionality.
    
    This class provides a high-level interface to the multi-peer streaming
    capabilities and integrates with the IPFS Kit API and security features.
    """
    
    def __init__(self, ipfs_api=None, security_manager=None):
        """
        Initialize the multi-peer streaming integration.
        
        Args:
            ipfs_api: IPFS API instance for content access
            security_manager: Optional security manager for access control
        """
        if not HAS_DEPENDENCIES:
            raise ImportError("WebRTC multi-peer dependencies not available")
        
        self.ipfs_api = ipfs_api
        self.security_manager = security_manager
        
        # Set up the session manager
        if ipfs_api and webrtc_multi_peer.session_manager.ipfs_api is None:
            webrtc_multi_peer.session_manager.ipfs_api = ipfs_api
        
        # Initialize APIRouter for FastAPI integration
        self.router = self._create_api_router()
        
        # Statistics for this integration instance
        self.statistics = {
            "api_requests": 0,
            "websocket_connections": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "errors": []
        }
        
        logger.info("WebRTC multi-peer streaming integration initialized")
    
    def _create_api_router(self) -> APIRouter:
        """Create FastAPI router with streaming endpoints."""
        router = APIRouter(prefix="/api/v0/streaming", tags=["streaming"])
        
        # Register API endpoints
        router.add_api_route("/sessions", self.create_session, methods=["POST"], 
                           response_model=SessionResponse, 
                           summary="Create a new streaming session")
        
        router.add_api_route("/sessions", self.get_sessions, methods=["GET"], 
                           response_model=SessionListResponse, 
                           summary="Get available streaming sessions")
        
        router.add_api_route("/sessions/{session_id}", self.get_session_info, methods=["GET"], 
                           response_model=SessionInfoResponse, 
                           summary="Get information about a specific session")
        
        router.add_api_route("/sessions/{session_id}", self.close_session, methods=["DELETE"], 
                           response_model=SessionResponse, 
                           summary="Close a streaming session")
        
        router.add_api_route("/sessions/{session_id}/metrics", self.get_session_metrics, methods=["GET"], 
                           response_model=Dict[str, Any], 
                           summary="Get session performance metrics")
        
        # Register WebSocket route for signaling
        @router.websocket("/signaling")
        async def websocket_endpoint(websocket: WebSocket):
            self.statistics["websocket_connections"] += 1
            await handle_multi_peer_signaling(websocket, self.ipfs_api)
        
        return router
    
    async def create_session(self, options: SessionOptions) -> Dict[str, Any]:
        """
        Create a new streaming session with the provided options.
        
        Args:
            options: Session configuration options
            
        Returns:
            Dict with session creation results
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Apply security configuration if available
            if HAS_SECURITY and self.security_manager and options.security_level:
                # Add security configuration to session metadata
                if "security" not in options.metadata:
                    options.metadata["security"] = {}
                
                options.metadata["security"]["level"] = options.security_level
                if options.access_control:
                    options.metadata["security"]["access_control"] = options.access_control
            
            # Create the session
            result = await session_manager.create_session(options.dict(exclude_none=True))
            
            if result["success"]:
                self.statistics["successful_operations"] += 1
            else:
                self.statistics["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error creating session: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": options.session_id or "unknown"
            }
    
    async def get_sessions(self, public_only: bool = True) -> Dict[str, Any]:
        """
        Get a list of available sessions.
        
        Args:
            public_only: If True, only return public sessions
            
        Returns:
            Dict with available sessions information
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Get sessions from session manager
            result = await session_manager.get_sessions(public_only)
            
            if result["success"]:
                self.statistics["successful_operations"] += 1
            else:
                self.statistics["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error getting sessions: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "sessions": [],
                "count": 0,
                "error": error_msg
            }
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific session.
        
        Args:
            session_id: ID of the session to get information for
            
        Returns:
            Dict with session information
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Get session info from session manager
            result = await session_manager.get_session_info(session_id)
            
            if result["success"]:
                self.statistics["successful_operations"] += 1
            else:
                self.statistics["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error getting session info: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": session_id
            }
    
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """
        Close a streaming session and clean up all resources.
        
        Args:
            session_id: ID of the session to close
            
        Returns:
            Dict with session closure results
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Close the session
            result = await session_manager.close_session(session_id)
            
            if result["success"]:
                self.statistics["successful_operations"] += 1
            else:
                self.statistics["failed_operations"] += 1
            
            return result
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error closing session: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": session_id
            }
    
    async def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed performance metrics for a session.
        
        Args:
            session_id: ID of the session to get metrics for
            
        Returns:
            Dict with session metrics
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Check if session exists
            if session_id not in session_manager.sessions:
                self.statistics["failed_operations"] += 1
                return {
                    "success": False,
                    "error": "Session not found",
                    "session_id": session_id
                }
            
            # Get session
            session = session_manager.sessions[session_id]
            
            # Collect comprehensive metrics
            session_info = session.get_session_info()
            
            # Extract performance metrics
            metrics = {
                "success": True,
                "session_id": session_id,
                "peers": {
                    "count": len(session_info["peers"]),
                    "by_role": self._count_peers_by_role(session_info["peers"]),
                    "connection_quality": self._get_peer_connection_quality(session)
                },
                "tracks": {
                    "count": len(session_info["tracks"]),
                    "by_kind": self._count_tracks_by_kind(session_info["tracks"]),
                    "by_source": self._count_tracks_by_source(session_info["tracks"]),
                    "subscription_stats": self._get_track_subscription_stats(session_info["tracks"])
                },
                "connections": {
                    "count": len(session_info["connections"]),
                    "mesh_density": self._calculate_mesh_density(session_info["mesh_topology"]),
                    "topology_stats": self._get_topology_stats(session)
                },
                "performance": {
                    "bytes_transferred": session.statistics.get("bytes_transferred", 0),
                    "errors": session.statistics.get("errors", 0),
                    "optimization_count": len(session.topology_optimizer.get("optimization_history", [])),
                    "last_optimization": session.topology_optimizer.get("last_optimization", 0)
                },
                "timestamp": time.time()
            }
            
            self.statistics["successful_operations"] += 1
            return metrics
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error getting session metrics: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "session_id": session_id
            }
    
    def _count_peers_by_role(self, peers_info: Dict[str, Any]) -> Dict[str, int]:
        """Count peers by role for metrics."""
        role_counts = {}
        for peer_id, info in peers_info.items():
            role = info.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
        return role_counts
    
    def _count_tracks_by_kind(self, tracks_info: Dict[str, Any]) -> Dict[str, int]:
        """Count tracks by kind (video/audio) for metrics."""
        kind_counts = {}
        for track_id, info in tracks_info.items():
            kind = info.get("kind", "unknown")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        return kind_counts
    
    def _count_tracks_by_source(self, tracks_info: Dict[str, Any]) -> Dict[str, int]:
        """Count tracks by source type for metrics."""
        source_counts = {}
        for track_id, info in tracks_info.items():
            source_type = info.get("source_type", "unknown")
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
        return source_counts
    
    def _get_track_subscription_stats(self, tracks_info: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about track subscriptions."""
        stats = {
            "total_subscriptions": 0,
            "tracks_with_subscribers": 0,
            "max_subscribers": 0,
            "avg_subscribers": 0
        }
        
        if not tracks_info:
            return stats
        
        subscriber_counts = []
        for track_id, info in tracks_info.items():
            subscribers = info.get("subscribers", [])
            count = len(subscribers)
            subscriber_counts.append(count)
            stats["total_subscriptions"] += count
            
            if count > 0:
                stats["tracks_with_subscribers"] += 1
            
            stats["max_subscribers"] = max(stats["max_subscribers"], count)
        
        if tracks_info:
            stats["avg_subscribers"] = stats["total_subscriptions"] / len(tracks_info)
        
        return stats
    
    def _get_peer_connection_quality(self, session) -> Dict[str, Any]:
        """Get statistics about peer connection quality."""
        quality_stats = {
            "average": 0,
            "min": 100,
            "max": 0,
            "distribution": {
                "excellent": 0,  # 90-100
                "good": 0,       # 70-89
                "fair": 0,       # 50-69
                "poor": 0        # 0-49
            }
        }
        
        if not session.peers:
            return quality_stats
        
        total_quality = 0
        
        for peer_id, peer_info in session.peers.items():
            quality = peer_info.get("connection_quality", 0)
            total_quality += quality
            
            quality_stats["min"] = min(quality_stats["min"], quality)
            quality_stats["max"] = max(quality_stats["max"], quality)
            
            # Categorize by quality level
            if quality >= 90:
                quality_stats["distribution"]["excellent"] += 1
            elif quality >= 70:
                quality_stats["distribution"]["good"] += 1
            elif quality >= 50:
                quality_stats["distribution"]["fair"] += 1
            else:
                quality_stats["distribution"]["poor"] += 1
        
        if session.peers:
            quality_stats["average"] = total_quality / len(session.peers)
        
        return quality_stats
    
    def _calculate_mesh_density(self, mesh_topology: Dict[str, Any]) -> float:
        """Calculate the density of the mesh network (0.0-1.0)."""
        if not mesh_topology or len(mesh_topology) <= 1:
            return 0.0
        
        # Count actual connections
        total_connections = sum(len(connections) for peer_id, connections in mesh_topology.items())
        
        # Divide by 2 because each connection is counted twice (once for each peer)
        total_connections = total_connections / 2
        
        # Maximum possible connections in a complete graph: n(n-1)/2
        n = len(mesh_topology)
        max_connections = (n * (n - 1)) / 2
        
        # Density: actual connections / maximum possible connections
        return total_connections / max_connections if max_connections > 0 else 0.0
    
    def _get_topology_stats(self, session) -> Dict[str, Any]:
        """Get statistics about the session topology."""
        stats = {
            "relay_candidates": len(session.topology_optimizer.get("relay_candidates", [])),
            "edge_peers": len(session.topology_optimizer.get("edge_peers", [])),
            "optimizations": len(session.topology_optimizer.get("optimization_history", [])),
            "fan_out_stats": {
                "max": 0,
                "avg": 0
            }
        }
        
        # Calculate fan-out statistics
        if session.peer_mesh:
            fan_outs = [len(connections) for peer_id, connections in session.peer_mesh.items()]
            if fan_outs:
                stats["fan_out_stats"]["max"] = max(fan_outs)
                stats["fan_out_stats"]["avg"] = sum(fan_outs) / len(fan_outs)
        
        return stats
    
    async def check_session_access(self, session_id: str, auth_token: Optional[str] = None) -> bool:
        """
        Check if access to a session is allowed.
        
        Args:
            session_id: ID of the session to check
            auth_token: Optional authentication token
            
        Returns:
            True if access is allowed, False otherwise
        """
        # If no security manager, allow access by default
        if not HAS_SECURITY or self.security_manager is None:
            return True
        
        # Check if session exists
        if session_id not in session_manager.sessions:
            return False
        
        # Get session
        session = session_manager.sessions[session_id]
        
        # Check if session has security configuration
        security_config = session.metadata.get("security", {})
        if not security_config:
            return True  # No security configuration means public access
        
        # Get security level
        security_level = security_config.get("level")
        if not security_level:
            return True  # No security level specified means public access
        
        # Check access based on security level and token
        return await self.security_manager.can_access_content(
            content_id=session_id,
            security_level=security_level,
            token=auth_token,
            content_type="streaming_session"
        )
    
    async def create_session_from_ipfs_content(self, cid: str, options: Optional[SessionOptions] = None) -> Dict[str, Any]:
        """
        Create a streaming session for specific IPFS content.
        
        Args:
            cid: Content identifier for the media in IPFS
            options: Optional session configuration options
            
        Returns:
            Dict with session creation results including session ID
        """
        self.statistics["api_requests"] += 1
        
        try:
            # Verify that the CID exists
            if self.ipfs_api:
                cid_exists = await self._check_cid_exists(cid)
                if not cid_exists:
                    self.statistics["failed_operations"] += 1
                    return {
                        "success": False,
                        "error": f"Content with CID {cid} not found",
                        "cid": cid
                    }
            
            # Create session options if not provided
            if options is None:
                options = SessionOptions(
                    session_type="broadcast",
                    max_peers=20,
                    public=True,
                    metadata={
                        "content": {
                            "cid": cid,
                            "created_at": time.time()
                        }
                    }
                )
            else:
                # Add content metadata
                if "content" not in options.metadata:
                    options.metadata["content"] = {}
                options.metadata["content"]["cid"] = cid
                options.metadata["content"]["created_at"] = time.time()
            
            # Create the session
            session_result = await self.create_session(options)
            
            if not session_result["success"]:
                return session_result
            
            session_id = session_result["session_id"]
            
            # Add the broadcaster peer (system peer for IPFS content)
            system_peer_id = f"ipfs_{int(time.time())}"
            peer_info = PeerInfo(
                peer_id=system_peer_id,
                role=PeerRole.BROADCASTER.value,
                client_info={"type": "ipfs_system"},
                metadata={"content_source": cid}
            )
            
            join_result = await session_manager.join_session(session_id, peer_info.dict(exclude_none=True))
            
            if not join_result["success"]:
                # Clean up session if peer couldn't join
                await session_manager.close_session(session_id)
                self.statistics["failed_operations"] += 1
                return {
                    "success": False,
                    "error": f"Error adding system broadcaster: {join_result.get('error')}",
                    "session_id": session_id,
                    "cid": cid
                }
            
            # Add the track from IPFS content
            session = session_manager.sessions[session_id]
            
            track_info = TrackInfo(
                kind="video",  # Assume video for now, could be detected from mimetype
                source_type="ipfs",
                source=cid,
                options={
                    "frame_rate": 30,
                    "quality": "auto"
                }
            )
            
            track_result = await session.add_track(system_peer_id, track_info.dict(exclude_none=True))
            
            if not track_result["success"]:
                # Clean up session if track couldn't be added
                await session_manager.close_session(session_id)
                self.statistics["failed_operations"] += 1
                return {
                    "success": False,
                    "error": f"Error adding content track: {track_result.get('error')}",
                    "session_id": session_id,
                    "cid": cid
                }
            
            self.statistics["successful_operations"] += 1
            return {
                "success": True,
                "session_id": session_id,
                "cid": cid,
                "track_id": track_result["track_id"],
                "system_peer_id": system_peer_id,
                "created_at": session_result["created_at"],
                "session_type": options.session_type,
                "public": options.public
            }
            
        except Exception as e:
            self.statistics["failed_operations"] += 1
            error_msg = f"Error creating session from IPFS content: {str(e)}"
            self.statistics["errors"].append(error_msg)
            logger.error(error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "cid": cid
            }
    
    async def _check_cid_exists(self, cid: str) -> bool:
        """Check if a CID exists in IPFS."""
        if not self.ipfs_api:
            return True  # Assume it exists if we can't check
        
        try:
            # This is a simple existence check, not retrieving the full content
            result = self.ipfs_api.dag_stat(cid)
            return result.get("success", False)
        except Exception as e:
            logger.warning(f"Error checking CID existence: {e}")
            return False
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """
        Get statistics about this integration instance.
        
        Returns:
            Dict with integration statistics
        """
        stats = self.statistics.copy()
        stats["timestamp"] = time.time()
        
        # Add session manager stats
        manager_stats = session_manager.get_manager_stats()
        stats["session_manager"] = manager_stats
        
        # Add security stats if available
        if HAS_SECURITY and self.security_manager:
            stats["security"] = self.security_manager.get_security_stats()
        
        return stats

# High-level API extension for multi-peer streaming

def extend_simple_api(api_instance: IPFSSimpleAPI) -> IPFSSimpleAPI:
    """
    Extend the IPFSSimpleAPI with multi-peer streaming capabilities.
    
    Args:
        api_instance: IPFSSimpleAPI instance to extend
        
    Returns:
        The extended API instance
    """
    if not HAS_DEPENDENCIES:
        # Skip extension if dependencies not available
        return api_instance
    
    # Create integration instance
    integration = MultiPeerStreamingIntegration(api_instance.ipfs)
    
    # Add streaming methods to the API
    async def create_stream(cid: str, public: bool = True, session_type: str = "broadcast", 
                           max_peers: int = 20) -> Dict[str, Any]:
        """
        Create a streaming session for IPFS content.
        
        Args:
            cid: Content identifier for the media in IPFS
            public: Whether the session should be public
            session_type: Type of session (broadcast, mesh, hybrid)
            max_peers: Maximum number of peers allowed
            
        Returns:
            Dict with session information including session ID
        """
        options = SessionOptions(
            session_type=session_type,
            max_peers=max_peers,
            public=public
        )
        
        return await integration.create_session_from_ipfs_content(cid, options)
    
    async def get_streams(public_only: bool = True) -> Dict[str, Any]:
        """
        Get available streaming sessions.
        
        Args:
            public_only: Only return public sessions
            
        Returns:
            Dict with available sessions
        """
        return await integration.get_sessions(public_only)
    
    async def get_stream_info(session_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a streaming session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dict with session information
        """
        return await integration.get_session_info(session_id)
    
    async def close_stream(session_id: str) -> Dict[str, Any]:
        """
        Close a streaming session.
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dict with closure result
        """
        return await integration.close_session(session_id)
    
    # Add methods to the API instance
    api_instance.create_stream = create_stream
    api_instance.get_streams = get_streams
    api_instance.get_stream_info = get_stream_info
    api_instance.close_stream = close_stream
    
    # Add integration instance to API for reference
    api_instance._streaming_integration = integration
    
    return api_instance

# JavaScript client for browser integration

JAVASCRIPT_CLIENT = """
/**
 * IPFS Kit WebRTC Multi-Peer Streaming Client
 * 
 * This client provides an easy way to integrate with the IPFS Kit WebRTC
 * multi-peer streaming functionality from browser applications.
 */
class IPFSStreamingClient {
  /**
   * Initialize the streaming client
   * 
   * @param {Object} options - Client configuration options
   * @param {string} options.signaling_url - WebSocket URL for signaling server
   * @param {Object} options.peer_info - Information about this peer
   * @param {string} options.auth_token - Optional authentication token
   */
  constructor(options) {
    this.options = options || {};
    this.signaling_url = options.signaling_url || 
      ((window.location.protocol === 'https:' ? 'wss://' : 'ws://') + 
       window.location.host + '/api/v0/streaming/signaling');
    this.peer_info = options.peer_info || {
      role: 'viewer',
      capabilities: {},
      client_info: {
        type: 'browser',
        browser: navigator.userAgent
      }
    };
    this.auth_token = options.auth_token;
    
    // Client state
    this.connected = false;
    this.client_id = null;
    this.current_session = null;
    this.current_peer_id = null;
    this.peer_connections = {};
    this.local_tracks = {};
    this.remote_tracks = {};
    this.signaling = null;
    
    // Event handlers
    this.event_handlers = {
      'connected': [],
      'disconnected': [],
      'session_joined': [],
      'session_left': [],
      'track_added': [],
      'track_removed': [],
      'peer_joined': [],
      'peer_left': [],
      'error': []
    };
    
    // Bind methods
    this.connect = this.connect.bind(this);
    this.disconnect = this.disconnect.bind(this);
    this.joinSession = this.joinSession.bind(this);
    this.leaveSession = this.leaveSession.bind(this);
    this.addTrack = this.addTrack.bind(this);
    this.removeTrack = this.removeTrack.bind(this);
    this.subscribeToTrack = this.subscribeToTrack.bind(this);
    this.unsubscribeFromTrack = this.unsubscribeFromTrack.bind(this);
    this._handleSignalingMessage = this._handleSignalingMessage.bind(this);
  }
  
  /**
   * Add an event listener
   * 
   * @param {string} event - Event name
   * @param {Function} handler - Event handler function
   */
  on(event, handler) {
    if (this.event_handlers[event]) {
      this.event_handlers[event].push(handler);
    }
    return this;
  }
  
  /**
   * Remove an event listener
   * 
   * @param {string} event - Event name
   * @param {Function} handler - Event handler function
   */
  off(event, handler) {
    if (this.event_handlers[event]) {
      this.event_handlers[event] = this.event_handlers[event]
        .filter(h => h !== handler);
    }
    return this;
  }
  
  /**
   * Trigger an event
   * 
   * @param {string} event - Event name
   * @param {*} data - Event data
   */
  _triggerEvent(event, data) {
    if (this.event_handlers[event]) {
      this.event_handlers[event].forEach(handler => handler(data));
    }
  }
  
  /**
   * Connect to the signaling server
   * 
   * @returns {Promise} Resolves when connected
   */
  async connect() {
    if (this.connected) {
      return;
    }
    
    return new Promise((resolve, reject) => {
      try {
        // Create WebSocket connection
        this.signaling = new WebSocket(this.signaling_url);
        
        // Setup event handlers
        this.signaling.onopen = () => {
          console.log('Connected to signaling server');
          this.connected = true;
          this._triggerEvent('connected', {
            signaling_url: this.signaling_url
          });
          resolve();
        };
        
        this.signaling.onclose = () => {
          console.log('Disconnected from signaling server');
          this.connected = false;
          this._triggerEvent('disconnected', {});
          this._cleanupPeerConnections();
        };
        
        this.signaling.onerror = (error) => {
          console.error('Signaling error:', error);
          this._triggerEvent('error', {
            source: 'signaling',
            error: error
          });
          reject(error);
        };
        
        this.signaling.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this._handleSignalingMessage(message);
          } catch (error) {
            console.error('Error parsing signaling message:', error);
            this._triggerEvent('error', {
              source: 'signaling',
              error: error
            });
          }
        };
      } catch (error) {
        console.error('Error connecting to signaling server:', error);
        this._triggerEvent('error', {
          source: 'signaling',
          error: error
        });
        reject(error);
      }
    });
  }
  
  /**
   * Disconnect from the signaling server
   */
  disconnect() {
    if (!this.connected) {
      return;
    }
    
    // Leave current session if any
    if (this.current_session) {
      this.leaveSession();
    }
    
    // Close signaling connection
    if (this.signaling) {
      this.signaling.close();
      this.signaling = null;
    }
    
    this.connected = false;
    this._triggerEvent('disconnected', {});
  }
  
  /**
   * Join a streaming session
   * 
   * @param {string} session_id - ID of the session to join
   * @param {Object} peer_info - Optional peer information
   * @returns {Promise} Resolves with session join result
   */
  async joinSession(session_id, peer_info) {
    if (!this.connected) {
      throw new Error('Not connected to signaling server');
    }
    
    if (this.current_session) {
      await this.leaveSession();
    }
    
    return new Promise((resolve, reject) => {
      // Combine provided peer info with default peer info
      const finalPeerInfo = {
        ...this.peer_info,
        ...peer_info
      };
      
      // Add auth token if available
      if (this.auth_token) {
        finalPeerInfo.auth_token = this.auth_token;
      }
      
      // Send join message
      this._sendSignalingMessage({
        type: 'join_session',
        session_id: session_id,
        peer_info: finalPeerInfo
      });
      
      // Set up handler for session join response
      const handleJoinResponse = (message) => {
        if (message.type === 'session_joined') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleJoinResponse);
          
          if (message.result && message.result.success) {
            // Store session and peer info
            this.current_session = message.result.session_id;
            this.current_peer_id = message.result.peer_id;
            
            this._triggerEvent('session_joined', message.result);
            resolve(message.result);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'session',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleJoinResponse);
          
          this._triggerEvent('error', {
            source: 'session',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for join response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleJoinResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for join response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleJoinResponse);
        reject(new Error('Timeout waiting for session join response'));
      }, 10000);
    });
  }
  
  /**
   * Leave the current session
   * 
   * @returns {Promise} Resolves with session leave result
   */
  async leaveSession() {
    if (!this.connected || !this.current_session) {
      return;
    }
    
    return new Promise((resolve, reject) => {
      // Clean up all peer connections
      this._cleanupPeerConnections();
      
      // Send leave message
      this._sendSignalingMessage({
        type: 'leave_session',
        session_id: this.current_session,
        peer_id: this.current_peer_id
      });
      
      // Set up handler for session leave response
      const handleLeaveResponse = (message) => {
        if (message.type === 'session_left') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleLeaveResponse);
          
          // Clear session and peer info
          const oldSession = this.current_session;
          this.current_session = null;
          this.current_peer_id = null;
          
          this._triggerEvent('session_left', {
            session_id: oldSession
          });
          
          resolve(message.result);
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleLeaveResponse);
          
          this._triggerEvent('error', {
            source: 'session',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for leave response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleLeaveResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for leave response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleLeaveResponse);
        
        // Force cleanup even if response not received
        const oldSession = this.current_session;
        this.current_session = null;
        this.current_peer_id = null;
        
        this._triggerEvent('session_left', {
          session_id: oldSession
        });
        
        resolve({
          success: true,
          session_id: oldSession
        });
      }, 5000);
    });
  }
  
  /**
   * Add a media track to the session
   * 
   * @param {MediaStreamTrack} track - Media track to add
   * @param {Object} options - Track options
   * @returns {Promise} Resolves with track addition result
   */
  async addTrack(track, options = {}) {
    if (!this.connected || !this.current_session) {
      throw new Error('Not connected to a session');
    }
    
    // Create track info
    const trackInfo = {
      kind: track.kind,
      source_type: 'live',
      options: options
    };
    
    return new Promise((resolve, reject) => {
      // Send add track message
      this._sendSignalingMessage({
        type: 'add_track',
        session_id: this.current_session,
        peer_id: this.current_peer_id,
        track_info: trackInfo
      });
      
      // Set up handler for add track response
      const handleAddTrackResponse = (message) => {
        if (message.type === 'track_added') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleAddTrackResponse);
          
          if (message.result && message.result.success) {
            // Store track info
            const trackId = message.result.track_id;
            this.local_tracks[trackId] = {
              track: track,
              info: trackInfo,
              track_id: trackId
            };
            
            this._triggerEvent('track_added', {
              track_id: trackId,
              kind: track.kind,
              local: true
            });
            
            resolve(message.result);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'track',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleAddTrackResponse);
          
          this._triggerEvent('error', {
            source: 'track',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for add track response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleAddTrackResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for add track response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleAddTrackResponse);
        reject(new Error('Timeout waiting for add track response'));
      }, 10000);
    });
  }
  
  /**
   * Remove a media track from the session
   * 
   * @param {string} trackId - ID of the track to remove
   * @returns {Promise} Resolves with track removal result
   */
  async removeTrack(trackId) {
    if (!this.connected || !this.current_session) {
      throw new Error('Not connected to a session');
    }
    
    if (!this.local_tracks[trackId]) {
      throw new Error('Track not found or not owned by this peer');
    }
    
    return new Promise((resolve, reject) => {
      // Send remove track message
      this._sendSignalingMessage({
        type: 'remove_track',
        session_id: this.current_session,
        track_id: trackId
      });
      
      // Set up handler for remove track response
      const handleRemoveTrackResponse = (message) => {
        if (message.type === 'track_removed') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleRemoveTrackResponse);
          
          if (message.result && message.result.success) {
            // Remove track from tracking
            delete this.local_tracks[trackId];
            
            this._triggerEvent('track_removed', {
              track_id: trackId
            });
            
            resolve(message.result);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'track',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleRemoveTrackResponse);
          
          this._triggerEvent('error', {
            source: 'track',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for remove track response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleRemoveTrackResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for remove track response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleRemoveTrackResponse);
        reject(new Error('Timeout waiting for remove track response'));
      }, 10000);
    });
  }
  
  /**
   * Subscribe to a track in the session
   * 
   * @param {string} trackId - ID of the track to subscribe to
   * @returns {Promise} Resolves with track subscription result and MediaStreamTrack
   */
  async subscribeToTrack(trackId) {
    if (!this.connected || !this.current_session) {
      throw new Error('Not connected to a session');
    }
    
    return new Promise((resolve, reject) => {
      // Send subscribe message
      this._sendSignalingMessage({
        type: 'subscribe_to_track',
        session_id: this.current_session,
        peer_id: this.current_peer_id,
        track_id: trackId
      });
      
      // Set up handler for subscription response
      const handleSubscriptionResponse = (message) => {
        if (message.type === 'track_subscription') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleSubscriptionResponse);
          
          if (message.result && message.result.success) {
            const result = message.result;
            
            // This will trigger WebRTC connection setup
            // The track will be available when the connection is established
            // and will be added to remote_tracks
            
            this._triggerEvent('track_subscribed', {
              track_id: trackId,
              pc_id: result.pc_id,
              source_peer: result.source_peer
            });
            
            resolve(result);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'track',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleSubscriptionResponse);
          
          this._triggerEvent('error', {
            source: 'track',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for subscription response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleSubscriptionResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for subscription response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleSubscriptionResponse);
        reject(new Error('Timeout waiting for track subscription response'));
      }, 10000);
    });
  }
  
  /**
   * Unsubscribe from a track in the session
   * 
   * @param {string} trackId - ID of the track to unsubscribe from
   * @returns {Promise} Resolves with track unsubscription result
   */
  async unsubscribeFromTrack(trackId) {
    if (!this.connected || !this.current_session) {
      throw new Error('Not connected to a session');
    }
    
    return new Promise((resolve, reject) => {
      // Send unsubscribe message
      this._sendSignalingMessage({
        type: 'unsubscribe_from_track',
        session_id: this.current_session,
        peer_id: this.current_peer_id,
        track_id: trackId
      });
      
      // Set up handler for unsubscription response
      const handleUnsubscriptionResponse = (message) => {
        if (message.type === 'track_unsubscription') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleUnsubscriptionResponse);
          
          if (message.result && message.result.success) {
            // Remove track from tracking
            delete this.remote_tracks[trackId];
            
            this._triggerEvent('track_unsubscribed', {
              track_id: trackId
            });
            
            resolve(message.result);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'track',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleUnsubscriptionResponse);
          
          this._triggerEvent('error', {
            source: 'track',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for unsubscription response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleUnsubscriptionResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for unsubscription response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleUnsubscriptionResponse);
        reject(new Error('Timeout waiting for track unsubscription response'));
      }, 10000);
    });
  }
  
  /**
   * Get available tracks in the session
   * 
   * @returns {Promise} Resolves with available tracks
   */
  async getAvailableTracks() {
    if (!this.connected || !this.current_session) {
      throw new Error('Not connected to a session');
    }
    
    return new Promise((resolve, reject) => {
      // Send session info request
      this._sendSignalingMessage({
        type: 'get_session_info',
        session_id: this.current_session
      });
      
      // Set up handler for session info response
      const handleSessionInfoResponse = (message) => {
        if (message.type === 'session_info') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleSessionInfoResponse);
          
          if (message.result && message.result.success) {
            const sessionInfo = message.result.session_info;
            const tracks = sessionInfo.tracks || {};
            
            // Filter tracks not published by this peer and not already subscribed
            const availableTracks = Object.entries(tracks)
              .filter(([trackId, info]) => {
                return info.publisher !== this.current_peer_id && 
                       !info.subscribers.includes(this.current_peer_id);
              })
              .map(([trackId, info]) => {
                return {
                  track_id: trackId,
                  kind: info.kind,
                  publisher: info.publisher,
                  source_type: info.source_type,
                  source: info.source
                };
              });
            
            resolve(availableTracks);
          } else {
            const error = message.result ? message.result.error : 'Unknown error';
            this._triggerEvent('error', {
              source: 'session',
              error: error
            });
            reject(new Error(error));
          }
        } else if (message.type === 'error') {
          // Clean up handler
          this.signaling.removeEventListener('message', handleSessionInfoResponse);
          
          this._triggerEvent('error', {
            source: 'session',
            error: message.message
          });
          reject(new Error(message.message));
        }
      };
      
      // Add temporary handler for session info response
      this.signaling.addEventListener('message', (event) => {
        try {
          const message = JSON.parse(event.data);
          handleSessionInfoResponse(message);
        } catch (error) {
          // Ignore parsing errors for this handler
        }
      });
      
      // Set timeout for session info response
      setTimeout(() => {
        this.signaling.removeEventListener('message', handleSessionInfoResponse);
        reject(new Error('Timeout waiting for session info response'));
      }, 10000);
    });
  }
  
  /**
   * Handle a signaling message
   * 
   * @param {Object} message - The signaling message
   */
  _handleSignalingMessage(message) {
    const type = message.type;
    
    if (type === 'welcome') {
      this.client_id = message.client_id;
      console.log('Received welcome message, client ID:', this.client_id);
    } else if (type === 'peer_connection_created') {
      if (message.result && message.result.success) {
        this._handlePeerConnectionCreated(message.result);
      }
    } else if (type === 'answer_handled') {
      // Answer has been processed by server, nothing to do
    } else if (type === 'track_added') {
      // Remote track was added, nothing to do here since it will come through RTCPeerConnection
    } else if (type === 'notification') {
      this._handleNotification(message);
    }
  }
  
  /**
   * Handle a peer connection creation
   * 
   * @param {Object} data - Peer connection data
   */
  _handlePeerConnectionCreated(data) {
    const pcId = data.pc_id;
    const sourcePeer = data.source_peer;
    const targetPeer = data.target_peer;
    const sdp = data.sdp;
    const type = data.type;
    
    // Create RTCPeerConnection
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    });
    
    // Store connection
    this.peer_connections[pcId] = {
      pc: pc,
      source_peer: sourcePeer,
      target_peer: targetPeer
    };
    
    // Set up ICE candidate handling
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        this._sendSignalingMessage({
          type: 'candidate',
          session_id: this.current_session,
          pc_id: pcId,
          candidate: event.candidate.candidate,
          sdp_mid: event.candidate.sdpMid,
          sdp_mline_index: event.candidate.sdpMLineIndex
        });
      }
    };
    
    // Set up track handling
    pc.ontrack = (event) => {
      const track = event.track;
      const streams = event.streams;
      
      console.log('Received remote track:', track.kind);
      
      // Store track
      // Note: We don't know the track ID from the session at this point
      // We'll need to cross-reference with session info
      this._handleRemoteTrack(track, streams, pcId);
    };
    
    // Set connection state change handling
    pc.onconnectionstatechange = () => {
      console.log('Connection state change:', pc.connectionState);
      
      if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
        // Connection failed or closed, clean up
        this._cleanupPeerConnection(pcId);
      }
    };
    
    // Set remote description
    pc.setRemoteDescription({
      type: type,
      sdp: sdp
    }).then(() => {
      return pc.createAnswer();
    }).then(answer => {
      return pc.setLocalDescription(answer);
    }).then(() => {
      // Send answer to signaling server
      this._sendSignalingMessage({
        type: 'answer',
        session_id: this.current_session,
        pc_id: pcId,
        sdp: pc.localDescription.sdp,
        sdp_type: pc.localDescription.type
      });
    }).catch(error => {
      console.error('Error setting up peer connection:', error);
      this._triggerEvent('error', {
        source: 'webrtc',
        error: error.message
      });
    });
  }
  
  /**
   * Handle a remote track received from a peer connection
   * 
   * @param {MediaStreamTrack} track - The received track
   * @param {MediaStream[]} streams - Associated media streams
   * @param {string} pcId - Peer connection ID
   */
  _handleRemoteTrack(track, streams, pcId) {
    // Get session info to match track with track ID
    this._sendSignalingMessage({
      type: 'get_session_info',
      session_id: this.current_session
    });
    
    // Set up handler for session info response
    const handleSessionInfoResponse = (message) => {
      if (message.type === 'session_info') {
        // Clean up handler
        this.signaling.removeEventListener('message', handleSessionInfoResponse);
        
        if (message.result && message.result.success) {
          const sessionInfo = message.result.session_info;
          const tracks = sessionInfo.tracks || {};
          
          // Try to find the track ID by matching with source and target peer
          let foundTrackId = null;
          
          // Parse the peer connection ID to get source and target
          const [sourcePeer, targetPeer] = pcId.split(':');
          
          // Look for tracks where source is the publisher and target is us
          for (const [trackId, trackInfo] of Object.entries(tracks)) {
            if (trackInfo.publisher === sourcePeer && 
                trackInfo.subscribers.includes(this.current_peer_id)) {
              if (trackInfo.kind === track.kind) {
                foundTrackId = trackId;
                break;
              }
            }
          }
          
          if (foundTrackId) {
            // Store track with ID
            this.remote_tracks[foundTrackId] = {
              track: track,
              streams: streams,
              pc_id: pcId,
              info: tracks[foundTrackId]
            };
            
            this._triggerEvent('track_added', {
              track_id: foundTrackId,
              track: track,
              streams: streams,
              kind: track.kind,
              local: false
            });
          } else {
            console.warn('Could not identify received track, storing temporarily without ID');
            
            // Store temporarily without ID
            const tempId = 'temp_' + Date.now();
            this.remote_tracks[tempId] = {
              track: track,
              streams: streams,
              pc_id: pcId,
              temporary: true
            };
            
            this._triggerEvent('track_added', {
              track_id: tempId,
              track: track,
              streams: streams,
              kind: track.kind,
              local: false,
              temporary: true
            });
          }
        }
      }
    };
    
    // Add temporary handler for session info response
    this.signaling.addEventListener('message', (event) => {
      try {
        const message = JSON.parse(event.data);
        handleSessionInfoResponse(message);
      } catch (error) {
        // Ignore parsing errors for this handler
      }
    });
  }
  
  /**
   * Handle a notification message
   * 
   * @param {Object} message - The notification message
   */
  _handleNotification(message) {
    const notificationType = message.notification_type;
    const data = message.data || {};
    
    if (notificationType === 'peer_joined') {
      this._triggerEvent('peer_joined', data);
    } else if (notificationType === 'peer_left') {
      this._triggerEvent('peer_left', data);
    } else if (notificationType === 'track_added') {
      // This is just a notification, the actual track will come through WebRTC
      this._triggerEvent('track_available', data);
    } else if (notificationType === 'track_removed') {
      // If we have this track, trigger removed event
      if (this.remote_tracks[data.track_id]) {
        this._triggerEvent('track_removed', data);
        delete this.remote_tracks[data.track_id];
      }
    }
  }
  
  /**
   * Send a message to the signaling server
   * 
   * @param {Object} message - The message to send
   */
  _sendSignalingMessage(message) {
    if (!this.connected || !this.signaling) {
      throw new Error('Not connected to signaling server');
    }
    
    this.signaling.send(JSON.stringify(message));
  }
  
  /**
   * Clean up a specific peer connection
   * 
   * @param {string} pcId - Peer connection ID to clean up
   */
  _cleanupPeerConnection(pcId) {
    if (!this.peer_connections[pcId]) {
      return;
    }
    
    const pc = this.peer_connections[pcId].pc;
    
    // Close the connection
    pc.close();
    
    // Remove from tracking
    delete this.peer_connections[pcId];
    
    console.log(`Closed peer connection: ${pcId}`);
  }
  
  /**
   * Clean up all peer connections
   */
  _cleanupPeerConnections() {
    // Close all peer connections
    for (const pcId in this.peer_connections) {
      this._cleanupPeerConnection(pcId);
    }
    
    // Clear tracks
    this.local_tracks = {};
    this.remote_tracks = {};
  }
  
  /**
   * Get current session information
   * 
   * @returns {Object} Current session information
   */
  getSessionInfo() {
    return {
      connected: this.connected,
      client_id: this.client_id,
      current_session: this.current_session,
      current_peer_id: this.current_peer_id,
      peer_connections: Object.keys(this.peer_connections),
      local_tracks: Object.keys(this.local_tracks),
      remote_tracks: Object.keys(this.remote_tracks)
    };
  }
  
  /**
   * Get local tracks
   * 
   * @returns {Object} Local tracks with track IDs as keys
   */
  getLocalTracks() {
    return this.local_tracks;
  }
  
  /**
   * Get remote tracks
   * 
   * @returns {Object} Remote tracks with track IDs as keys
   */
  getRemoteTracks() {
    return this.remote_tracks;
  }
}

// Export for module systems
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
  module.exports = IPFSStreamingClient;
} else {
  window.IPFSStreamingClient = IPFSStreamingClient;
}
"""

def get_javascript_client():
    """Get the JavaScript client for browser integration."""
    return JAVASCRIPT_CLIENT