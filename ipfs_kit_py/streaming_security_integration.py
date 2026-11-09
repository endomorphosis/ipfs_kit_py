"""
Streaming Security Integration for IPFS Kit.

This module integrates the streaming security features with the existing WebRTC streaming 
and WebSocket notification systems, providing a secure streaming solution.

Key integrations:
1. Secure WebRTC Streaming: Authentication and access control for WebRTC streams
2. Secure WebSocket Notifications: Protected real-time notifications
3. Security Middleware: FastAPI middleware for security headers and rate limiting
4. Token Authentication: JWT-based authentication for API endpoints
5. Authorization Framework: Content-specific access control
"""

import anyio
import logging
from typing import Dict, List, Optional, Any, Union

# Import security components
from .streaming_security import (
    StreamingSecurityManager, 
    WebRTCContentSecurity,
    secure_websocket_middleware,
    SecurityLevel,
    AuthType
)

# Import WebRTC streaming components (with conditional import for testing)
try:
    from .webrtc_streaming import (
        WebRTCStreamingManager, 
        handle_webrtc_signaling,
        IPFSMediaStreamTrack
    )
    HAVE_WEBRTC = True
except ImportError:
    HAVE_WEBRTC = False

# Import notification system (with conditional import for testing)
try:
    from .websocket_notifications import (
        notification_manager,
        emit_event,
        NotificationType,
        handle_notification_websocket
    )
    HAVE_NOTIFICATIONS = True
except ImportError:
    HAVE_NOTIFICATIONS = False
    # Create dummy emit_event function for environments without notifications
    async def emit_event(*args, **kwargs):
        pass

# Check for FastAPI availability
try:
    from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
    HAVE_FASTAPI = True
except ImportError:
    HAVE_FASTAPI = False

# Configure logging
logger = logging.getLogger(__name__)


# Initialize the security manager (singleton for the application)
security_manager = StreamingSecurityManager()

# Create WebRTC security helper
webrtc_security = WebRTCContentSecurity(security_manager)


# Secure version of handle_webrtc_signaling
async def secure_handle_webrtc_signaling(websocket, ipfs_api):
    """
    Handle WebRTC signaling securely with authentication and authorization.
    
    Args:
        websocket: WebSocket connection
        ipfs_api: IPFS API instance
    """
    if not HAVE_WEBRTC:
        await websocket.send_json({
            "type": "error",
            "message": "WebRTC dependencies not available"
        })
        return
    
    # Authenticate the WebRTC signaling connection
    authenticated, user_claims, security_context = await security_manager.authenticate_webrtc_signaling(websocket)
    
    # Check security issues
    if security_context.get("rate_limited"):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
        
    if security_context.get("invalid_origin"):
        await websocket.close(code=1008, reason="Invalid origin")
        return
    
    # For public WebRTC, we might allow anonymous connections
    # Accept the connection even if not authenticated
    # The actual content access will be checked per-CID
    await websocket.accept()
    
    # Generate a client ID for this signaling connection
    client_id = f"client_{security_context.get('session_id', 'anon')}"
    
    # Log the new connection
    logger.info(f"New secure WebRTC signaling connection: {client_id}")
    
    # Create WebRTC manager
    manager = WebRTCStreamingManager(ipfs_api)
    
    # Notify about new signaling connection if notifications available
    if HAVE_NOTIFICATIONS:
        await emit_event(
            NotificationType.SYSTEM_INFO,
            {
                "message": "New WebRTC signaling connection established",
                "client_id": client_id,
                "authenticated": authenticated,
                "role": security_context.get("role", "anonymous")
            },
            source="secure_webrtc_signaling"
        )
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "client_id": client_id,
            "message": "IPFS WebRTC signaling server connected",
            "authenticated": authenticated,
            "capabilities": ["video", "audio", "encrypted"],
            "notification_support": HAVE_NOTIFICATIONS,
            "security": {
                "authenticated": authenticated,
                "role": security_context.get("role", "anonymous") if authenticated else "anonymous",
                "permissions": security_context.get("permissions", {}) if authenticated else {}
            }
        })
        
        # Handle signaling messages securely
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                # Process different message types
                if msg_type == "offer_request":
                    # Client wants to start a new WebRTC session
                    cid = message.get("cid")
                    kind = message.get("kind", "video")
                    frame_rate = message.get("frameRate", 30)
                    quality = message.get("quality", "auto")
                    
                    # Securely check access to this content
                    allowed, reason, enhanced_context = await webrtc_security.secure_streaming_offer(
                        cid, user_claims, security_context
                    )
                    
                    if not allowed:
                        # Access denied
                        await websocket.send_json({
                            "type": "error",
                            "error": reason,
                            "cid": cid
                        })
                        
                        # Log access denial
                        logger.warning(f"WebRTC access denied for CID {cid}: {reason}")
                        continue
                    
                    # Access granted, create offer
                    logger.info(f"Secure WebRTC offer request for CID: {cid}, kind: {kind}, security level: {enhanced_context.get('security_level')}")
                    
                    # Create WebRTC offer
                    offer = await manager.create_offer(cid, kind, frame_rate, quality)
                    
                    # Enhance offer with security information
                    security_info = {
                        "security_level": enhanced_context.get("security_level", SecurityLevel.PROTECTED)
                    }
                    
                    # For encrypted content, add content key
                    if enhanced_context.get("security_level") == SecurityLevel.ENCRYPTED:
                        security_info["content_key"] = enhanced_context.get("content_key")
                    
                    # Send enhanced offer
                    await websocket.send_json({
                        "type": "offer",
                        "pc_id": offer["pc_id"],
                        "sdp": offer["sdp"],
                        "sdpType": offer["type"],
                        "security": security_info
                    })
                
                elif msg_type == "answer":
                    # Client responded with an answer to our offer
                    pc_id = message.get("pc_id")
                    sdp = message.get("sdp")
                    sdp_type = message.get("sdpType")
                    
                    logger.info(f"WebRTC answer received for connection: {pc_id}")
                    
                    # Process the answer
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
                                source="secure_webrtc_signaling"
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
                    
                    # Check access to this content
                    allowed, reason, enhanced_context = await webrtc_security.secure_streaming_offer(
                        cid, user_claims, security_context
                    )
                    
                    if not allowed:
                        # Access denied
                        await websocket.send_json({
                            "type": "error",
                            "error": reason,
                            "cid": cid
                        })
                        
                        # Log access denial
                        logger.warning(f"WebRTC track addition denied for CID {cid}: {reason}")
                        continue
                    
                    # Access granted, add track
                    logger.info(f"Adding new secure track to connection {pc_id}, CID: {cid}, kind: {kind}")
                    
                    # Add track to connection
                    offer = await manager.add_content_track(pc_id, cid, kind, frame_rate)
                    if offer:
                        # Add security info
                        security_info = {
                            "security_level": enhanced_context.get("security_level", SecurityLevel.PROTECTED)
                        }
                        
                        if enhanced_context.get("security_level") == SecurityLevel.ENCRYPTED:
                            security_info["content_key"] = enhanced_context.get("content_key")
                        
                        await websocket.send_json({
                            "type": "track_offer",
                            "pc_id": pc_id,
                            "sdp": offer["sdp"],
                            "sdpType": offer["type"],
                            "security": security_info
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
                                source="secure_webrtc_signaling"
                            )
                        
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg
                        })
                
                elif msg_type == "get_stats":
                    # Client wants to get connection statistics
                    pc_id = message.get("pc_id")
                    
                    # Get and send stats
                    stats = manager.get_connection_stats(pc_id)
                    await websocket.send_json({
                        "type": "stats",
                        "stats": stats
                    })
                
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
                
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })
            
            except Exception as e:
                error_msg = f"Error processing WebRTC signaling message: {str(e)}"
                logger.error(error_msg)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": error_msg
                    })
                except:
                    # Connection might be closed
                    break
    
    except WebSocketDisconnect:
        logger.info(f"WebRTC signaling connection closed: {client_id}")
    except Exception as e:
        logger.error(f"Error in WebRTC signaling: {e}")
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
                source="secure_webrtc_signaling"
            )
            

# Secure version of handle_notification_websocket
async def secure_handle_notification_websocket(websocket, ipfs_api=None):
    """
    Handle a WebSocket connection for notifications with security.
    
    Args:
        websocket: The WebSocket connection
        ipfs_api: IPFS API instance (optional)
    """
    if not HAVE_NOTIFICATIONS:
        await websocket.close(code=1008, reason="Notification system not available")
        return
    
    # Authenticate and apply security
    authenticated, user_claims, security_context = await secure_websocket_middleware(
        websocket, security_manager
    )
    
    # Check rate limits
    if security_context.get("rate_limited"):
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    
    # For notifications, we might require authentication based on configuration
    require_auth = security_manager.notifications_require_auth if hasattr(security_manager, 'notifications_require_auth') else False
    
    if require_auth and not authenticated:
        await websocket.close(code=1008, reason="Authentication required for notifications")
        return
    
    # Generate a unique connection ID with user info if authenticated
    if authenticated and user_claims:
        user_id = user_claims.get("sub", "unknown")
        connection_id = f"user_{user_id}_{security_context.get('session_id', '')}"
    else:
        connection_id = f"anon_{security_context.get('session_id', '')}"
    
    try:
        # Register connection
        success = await notification_manager.connect(websocket, connection_id)
        if not success:
            await websocket.close(code=1008, reason="Failed to register notification connection")
            return
        
        # Send welcome message with security info
        await websocket.send_json({
            "type": "welcome",
            "message": "Connected to IPFS secure notification service",
            "connection_id": connection_id,
            "available_notifications": [t.value for t in NotificationType],
            "security": {
                "authenticated": authenticated,
                "role": user_claims.get("role", "anonymous") if authenticated else "anonymous",
                "permissions": user_claims.get("permissions", {}) if authenticated else {}
            },
            "timestamp": time.time()
        })
        
        # Process messages with security filtering
        while True:
            message = await websocket.receive_json()
            
            # Process the message
            if "action" not in message:
                await websocket.send_json({
                    "type": "error",
                    "error": "Missing 'action' field",
                    "timestamp": time.time()
                })
                continue
            
            action = message["action"]
            
            if action == "subscribe":
                # Get subscription details
                notification_types = message.get("notification_types", [])
                filters = message.get("filters")
                
                # Apply security filtering to subscription types
                if authenticated and user_claims:
                    # For authenticated users, filter based on role
                    allowed_types = filter_notification_types_by_role(
                        notification_types, 
                        user_claims.get("role", "anonymous"),
                        user_claims.get("permissions", {})
                    )
                else:
                    # For anonymous users, only allow public notification types
                    allowed_types = filter_notification_types_for_anonymous(notification_types)
                
                # Apply subscription with filtered types
                result = await notification_manager.subscribe(
                    connection_id, allowed_types, filters
                )
                
                # Add security info to result
                if result["success"]:
                    result["filtered_types"] = [t for t in notification_types if t not in allowed_types]
                    
                    # Send enhanced result
                    await websocket.send_json({
                        "type": "subscription_result",
                        "result": result,
                        "timestamp": time.time()
                    })
                    
                    logger.debug(f"Client {connection_id} subscribed to: {result['subscribed_types']}")
                    
                    # If any types were filtered, send a notice
                    if result.get("filtered_types"):
                        await websocket.send_json({
                            "type": "security_notice",
                            "message": "Some notification types were restricted due to permissions",
                            "filtered_types": result.get("filtered_types"),
                            "timestamp": time.time()
                        })
            
            elif action == "unsubscribe":
                # Unsubscribe from notification types
                notification_types = message.get("notification_types", [])
                
                result = await notification_manager.unsubscribe(
                    connection_id, notification_types
                )
                
                # Send result
                await websocket.send_json({
                    "type": "unsubscription_result",
                    "result": result,
                    "timestamp": time.time()
                })
                
                logger.debug(f"Client {connection_id} remaining subscriptions: {result.get('remaining_subscriptions', [])}")
            
            elif action == "get_history":
                # Apply security filter to history
                limit = message.get("limit", 100)
                notification_type = message.get("notification_type")
                
                # Get history with security filtering
                filtered_history = await get_filtered_notification_history(
                    limit, 
                    notification_type, 
                    authenticated, 
                    user_claims
                )
                
                # Send filtered history
                await websocket.send_json({
                    "type": "history",
                    "events": filtered_history,
                    "count": len(filtered_history),
                    "timestamp": time.time()
                })
            
            elif action == "ping":
                # Simple ping-pong for connection testing
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": time.time()
                })
            
            elif action == "get_metrics":
                # Only allow admin users to get metrics
                if authenticated and user_claims and user_claims.get("role") == "admin":
                    metrics = notification_manager.get_metrics()
                    
                    await websocket.send_json({
                        "type": "metrics",
                        "metrics": metrics,
                        "timestamp": time.time()
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Insufficient permissions to access metrics",
                        "timestamp": time.time()
                    })
            
            elif action == "get_info":
                # Get connection info
                info = await notification_manager.get_connection_info(connection_id)
                
                # Filter sensitive info for non-admin users
                if not (authenticated and user_claims and user_claims.get("role") == "admin"):
                    # Remove sensitive fields
                    if "info" in info and isinstance(info["info"], dict):
                        for sensitive_field in ["ip_address", "user_agent", "headers"]:
                            if sensitive_field in info["info"]:
                                del info["info"][sensitive_field]
                
                await websocket.send_json({
                    "type": "connection_info",
                    "info": info,
                    "timestamp": time.time()
                })
            
            else:
                # Unknown action
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown action: {action}",
                    "timestamp": time.time()
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Error in secure notification WebSocket: {e}")
    finally:
        # Unregister connection
        notification_manager.disconnect(connection_id)


# Helper function for secure notification filtering
def filter_notification_types_by_role(notification_types, role, permissions):
    """
    Filter notification types based on user role and permissions.
    
    Args:
        notification_types: List of notification types requested
        role: User role
        permissions: User permissions dictionary
        
    Returns:
        List of allowed notification types
    """
    allowed_types = []
    
    # Define permission rules for different notification types
    notification_permissions = {
        # System notifications require admin role or system permission
        "system_metrics": lambda r, p: r == "admin" or p.get("system", False),
        "system_warning": lambda r, p: r == "admin" or p.get("system", False),
        "system_error": lambda r, p: r == "admin" or p.get("system", False),
        
        # WebRTC notifications require streaming permission or admin role
        "webrtc_connection_created": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_connection_established": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_connection_closed": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_stream_started": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_stream_ended": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_quality_changed": lambda r, p: r == "admin" or p.get("streaming", False),
        "webrtc_error": lambda r, p: r == "admin" or p.get("streaming", False),
        
        # Cluster notifications require cluster permission or admin role
        "cluster_peer_joined": lambda r, p: r == "admin" or p.get("cluster", False),
        "cluster_peer_left": lambda r, p: r == "admin" or p.get("cluster", False),
        "cluster_state_changed": lambda r, p: r == "admin" or p.get("cluster", False),
        "cluster_pin_added": lambda r, p: r == "admin" or p.get("cluster", False),
        "cluster_pin_removed": lambda r, p: r == "admin" or p.get("cluster", False),
    }
    
    # Process each notification type
    for notification_type in notification_types:
        # Public notifications are always allowed
        if notification_type in ["content_added", "content_retrieved", "system_info", "custom_event"]:
            allowed_types.append(notification_type)
            continue
            
        # Check against permission rules
        permission_rule = notification_permissions.get(notification_type)
        if permission_rule:
            if permission_rule(role, permissions):
                allowed_types.append(notification_type)
            continue
            
        # For types without specific rules, only admin can access
        if role == "admin":
            allowed_types.append(notification_type)
    
    return allowed_types


def filter_notification_types_for_anonymous(notification_types):
    """
    Filter notification types for anonymous users.
    
    Args:
        notification_types: List of notification types requested
        
    Returns:
        List of allowed notification types for anonymous users
    """
    # Only allow the minimal set of public notification types
    public_types = ["content_added", "content_retrieved", "system_info", "custom_event"]
    return [t for t in notification_types if t in public_types]


async def get_filtered_notification_history(limit, notification_type, authenticated, user_claims):
    """
    Get filtered notification history based on security permissions.
    
    Args:
        limit: Maximum number of history events to retrieve
        notification_type: Optional specific notification type to retrieve
        authenticated: Whether the user is authenticated
        user_claims: User claims from token if authenticated
        
    Returns:
        Filtered list of notification events
    """
    # Get raw history from notification manager
    history = []
    if hasattr(notification_manager, 'event_history'):
        history = notification_manager.event_history
    
    # Filter by type if specified
    if notification_type:
        history = [
            event for event in history
            if event.get("notification_type") == notification_type
        ]
    
    # Apply security filtering based on authentication status
    if authenticated and user_claims:
        role = user_claims.get("role", "user")
        permissions = user_claims.get("permissions", {})
        
        # Admins can see all notifications
        if role == "admin":
            filtered_history = history
        else:
            # Regular users can only see notifications they have permission for
            allowed_types = filter_notification_types_by_role(
                [event.get("notification_type") for event in history],
                role,
                permissions
            )
            
            filtered_history = [
                event for event in history
                if event.get("notification_type") in allowed_types
            ]
    else:
        # Anonymous users can only see public notifications
        public_types = ["content_added", "content_retrieved", "system_info", "custom_event"]
        filtered_history = [
            event for event in history
            if event.get("notification_type") in public_types
        ]
    
    # Apply limit
    return filtered_history[-limit:]


# Secure version of enhanced emit_event
async def secure_emit_event(notification_type, data, source=None, security_level=SecurityLevel.PROTECTED):
    """
    Emit a secure event with proper access control.
    
    Args:
        notification_type: Type of notification to emit
        data: Notification data
        source: Source of the notification
        security_level: Security level for this notification
        
    Returns:
        Result of emit operation
    """
    if not HAVE_NOTIFICATIONS:
        logger.warning("Notification system not available. Event not emitted.")
        return {"success": False, "error": "Notification system not available"}
    
    # Sanitize notification data based on security level
    if security_level != SecurityLevel.PUBLIC:
        # Remove sensitive information from non-public notifications
        sanitized_data = sanitize_notification_data(data)
    else:
        sanitized_data = data
    
    # Add security metadata
    enhanced_data = {
        **sanitized_data,
        "security_level": security_level,
        "security_timestamp": time.time()
    }
    
    # Emit through notification system
    result = await emit_event(notification_type, enhanced_data, source)
    return result


def sanitize_notification_data(data):
    """
    Remove sensitive information from notification data.
    
    Args:
        data: Notification data to sanitize
        
    Returns:
        Sanitized data
    """
    if not isinstance(data, dict):
        return data
    
    # Create a copy to avoid modifying the original
    sanitized = data.copy()
    
    # List of sensitive fields to remove or mask
    sensitive_fields = [
        "token", "password", "secret", "key", "credential",
        "auth", "private", "session_token", "nonce"
    ]
    
    # Check each field
    for field in list(sanitized.keys()):
        # Check if field name contains any sensitive term
        if any(sensitive_term in field.lower() for sensitive_term in sensitive_fields):
            # Mask the value
            sanitized[field] = "***REDACTED***"
        
        # Recursively sanitize nested dictionaries
        elif isinstance(sanitized[field], dict):
            sanitized[field] = sanitize_notification_data(sanitized[field])
        
        # Recursively sanitize lists of dictionaries
        elif isinstance(sanitized[field], list):
            sanitized[field] = [
                sanitize_notification_data(item) if isinstance(item, dict) else item
                for item in sanitized[field]
            ]
    
    return sanitized


# Secure version of IPFSMediaStreamTrack with content encryption
class SecureIPFSMediaStreamTrack(IPFSMediaStreamTrack):
    """MediaStreamTrack that securely sources content from IPFS with encryption support."""
    
    def __init__(self, track=None, ipfs_api=None, cid=None, kind="video", frame_rate=30, 
                security_context=None, security_manager=None):
        """
        Initialize a secure IPFS media stream track.
        
        Args:
            track: Optional source track to relay
            ipfs_api: IPFS API instance for content retrieval
            cid: Content identifier for the media in IPFS
            kind: Track kind ("audio" or "video")
            frame_rate: Target frame rate for video tracks
            security_context: Security context with access control info
            security_manager: Security manager for encryption support
        """
        # Call parent initialization
        super().__init__(track, ipfs_api, cid, kind, frame_rate)
        
        # Security components
        self.security_context = security_context or {}
        self.security_manager = security_manager
        
        # Track whether this content needs encryption
        self.requires_encryption = (
            self.security_context.get("security_level") == SecurityLevel.ENCRYPTED
            and self.security_manager and self.security_manager.have_crypto
        )
        
        # Set up frame security handler
        if self.requires_encryption and hasattr(webrtc_security, 'secure_frame_data'):
            self.secure_frame = lambda frame: webrtc_security.secure_frame_data(
                frame, self.security_context
            )
        else:
            # Passthrough if no encryption needed or available
            self.secure_frame = lambda frame: frame
    
    async def recv(self):
        """Receive the next frame with security measures applied."""
        try:
            # Get frame from parent implementation
            frame = await super().recv()
            
            # Apply security measures if needed
            if self.requires_encryption:
                # Apply frame encryption
                frame = self.secure_frame(frame)
            
            return frame
            
        except Exception as e:
            logger.error(f"Error in secure recv: {e}")
            raise


# FastAPI security integration
if HAVE_FASTAPI:
    from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
    
    # Import the security middleware
    from .streaming_security import SecurityMiddleware, TokenSecurity
    
    class SecureStreamingIntegration:
        """FastAPI integration for secure streaming."""
        
        def __init__(self, app: FastAPI, ipfs_api, secret_key=None, 
                    allowed_origins=None, notifications_require_auth=False):
            """
            Initialize secure streaming integration for FastAPI.
            
            Args:
                app: FastAPI application
                ipfs_api: IPFS API instance
                secret_key: Secret key for token generation and validation
                allowed_origins: List of allowed origins for CORS
                notifications_require_auth: Whether notifications require authentication
            """
            self.app = app
            self.ipfs_api = ipfs_api
            
            # Configure security manager
            if secret_key:
                security_manager.secret_key = secret_key
            
            if allowed_origins:
                security_manager.allowed_origins = allowed_origins
            
            # Set notification auth requirement
            security_manager.notifications_require_auth = notifications_require_auth
            
            # Add security middleware
            app.add_middleware(SecurityMiddleware, security_manager=security_manager)
            
            # Create token security dependency
            self.token_security = TokenSecurity(security_manager)
            
            # Register WebSocket endpoints
            self._register_websocket_routes()
            
            # Register token API endpoints
            self._register_token_endpoints()
        
        def _register_websocket_routes(self):
            """Register secure WebSocket endpoints."""
            
            @self.app.websocket("/ws/webrtc")
            async def websocket_webrtc(websocket: WebSocket):
                await secure_handle_webrtc_signaling(websocket, self.ipfs_api)
            
            @self.app.websocket("/ws/notifications")
            async def websocket_notifications(websocket: WebSocket):
                await secure_handle_notification_websocket(websocket, self.ipfs_api)
        
        def _register_token_endpoints(self):
            """Register token management API endpoints."""
            
            @self.app.post("/api/token")
            async def create_token(username: str, password: str):
                """Simple token creation endpoint for testing."""
                # In a real implementation, this would validate credentials against a database
                if username == "test" and password == "test":
                    token = security_manager.create_token(
                        user_id=username,
                        user_role="user",
                        permissions={"streaming": True}
                    )
                    return {"token": token}
                elif username == "admin" and password == "admin":
                    token = security_manager.create_token(
                        user_id=username,
                        user_role="admin",
                        permissions={"streaming": True, "system": True, "cluster": True}
                    )
                    return {"token": token}
                else:
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Invalid credentials"
                    )
            
            @self.app.post("/api/token/revoke")
            async def revoke_token(token: str, user_claims = Depends(self.token_security)):
                """Revoke a specific token."""
                # Only admins or the token owner can revoke tokens
                if user_claims["role"] == "admin" or user_claims["sub"] == token:
                    result = security_manager.revoke_token(token)
                    return {"revoked": result}
                else:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="Not authorized to revoke this token"
                    )
            
            @self.app.post("/api/token/validate")
            async def validate_token(token: str):
                """Validate a token and return claims if valid."""
                claims = security_manager.verify_token(token)
                if claims:
                    return {"valid": True, "claims": claims}
                else:
                    return {"valid": False}
        
        def register_secure_content_endpoints(self):
            """Register endpoints for secure content access."""
            
            @self.app.get("/api/secure-content/{cid}")
            async def get_secure_content(cid: str, user_claims = Depends(self.token_security)):
                """Get secure content with authentication and authorization."""
                # Check content access
                access_allowed = security_manager.check_content_access(cid, user_claims)
                if not access_allowed:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="Content access denied"
                    )
                
                # Access the content
                # In a real implementation, this would retrieve the content from IPFS
                # and apply any necessary security measures (e.g., encryption)
                
                return {
                    "cid": cid,
                    "access": "granted",
                    "user": user_claims["sub"],
                    "timestamp": time.time()
                }
            
            @self.app.post("/api/content-policy/{cid}")
            async def set_content_policy(
                cid: str, 
                allowed_users: List[str] = None,
                allowed_roles: List[str] = None,
                security_level: SecurityLevel = SecurityLevel.PROTECTED,
                user_claims = Depends(self.token_security)
            ):
                """Set access policy for a specific content item."""
                # Only admins can set content policies
                if user_claims["role"] != "admin":
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="Only administrators can set content policies"
                    )
                
                # Set policy
                policy = security_manager.set_content_policy(
                    cid,
                    allowed_users=allowed_users,
                    allowed_roles=allowed_roles,
                    security_level=security_level
                )
                
                return {"policy": policy}


# Example usage of the integration
"""
from fastapi import FastAPI
from ipfs_kit_py.ipfs_kit import IPFSKit
from ipfs_kit_py.streaming_security_integration import SecureStreamingIntegration

# Initialize FastAPI app
app = FastAPI(title="Secure IPFS Streaming")

# Initialize IPFS Kit
ipfs_kit = IPFSKit()

# Initialize secure streaming integration
secure_streaming = SecureStreamingIntegration(
    app=app,
    ipfs_api=ipfs_kit,
    secret_key="your-secure-secret-key",
    allowed_origins=["https://example.com"],
    notifications_require_auth=True
)

# Register additional secure content endpoints
secure_streaming.register_secure_content_endpoints()

@app.get("/")
async def root():
    return {"message": "Secure IPFS Streaming API"}
"""