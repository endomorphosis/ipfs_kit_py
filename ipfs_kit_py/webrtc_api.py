"""
WebRTC API for IPFS Kit

This module provides a FastAPI router for WebRTC streaming and signaling
in IPFS Kit, enabling real-time peer-to-peer content streaming.

Features:
- WebRTC signaling (offer/answer)
- Direct peer connections
- Content streaming
- Stream recording
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union
import json

import fastapi
from fastapi import Body, HTTPException, Query, Request, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Create router
webrtc_router = fastapi.APIRouter(prefix="/api/v0/webrtc", tags=["webrtc"])

class WebRTCOffer(BaseModel):
    """WebRTC offer model"""
    sdp: str
    peer_id: Optional[str] = None
    cid: Optional[str] = None
    stream_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

class WebRTCAnswer(BaseModel):
    """WebRTC answer model"""
    sdp: str
    peer_id: str
    stream_id: Optional[str] = None
    ice_candidates: Optional[List[Dict[str, Any]]] = None

class WebRTCICECandidate(BaseModel):
    """WebRTC ICE candidate model"""
    candidate: str
    sdp_mid: str
    sdp_m_line_index: int
    peer_id: str
    stream_id: Optional[str] = None

@webrtc_router.post("/offer", response_model=Dict[str, Any])
async def create_webrtc_offer(
    offer: WebRTCOffer = Body(..., description="WebRTC offer")
):
    """
    Create a WebRTC offer for peer-to-peer streaming.
    
    This endpoint creates a WebRTC offer for establishing a direct peer-to-peer
    connection for content streaming.
    
    Parameters:
    - **offer**: WebRTC offer object containing SDP and optional peer ID, CID, and configuration
    
    Returns:
        WebRTC offer details
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Create offer
        logger.info(f"Creating WebRTC offer for peer {offer.peer_id or 'anonymous'}")
        result = api.webrtc.create_offer(
            sdp=offer.sdp,
            peer_id=offer.peer_id,
            cid=offer.cid,
            stream_id=offer.stream_id,
            config=offer.config
        )
        
        return {
            "success": True,
            "operation": "create_webrtc_offer",
            "timestamp": time.time(),
            "peer_id": result.get("peer_id"),
            "stream_id": result.get("stream_id"),
            "sdp": result.get("sdp"),
            "ice_candidates": result.get("ice_candidates", [])
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error creating WebRTC offer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating WebRTC offer: {str(e)}")
        
@webrtc_router.post("/answer", response_model=Dict[str, Any])
async def process_webrtc_answer(
    answer: WebRTCAnswer = Body(..., description="WebRTC answer")
):
    """
    Process a WebRTC answer.
    
    This endpoint processes a WebRTC answer from a remote peer.
    
    Parameters:
    - **answer**: WebRTC answer object containing SDP, peer ID, and optional ICE candidates
    
    Returns:
        WebRTC connection status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Process answer
        logger.info(f"Processing WebRTC answer from peer {answer.peer_id}")
        result = api.webrtc.process_answer(
            sdp=answer.sdp,
            peer_id=answer.peer_id,
            stream_id=answer.stream_id,
            ice_candidates=answer.ice_candidates
        )
        
        return {
            "success": True,
            "operation": "process_webrtc_answer",
            "timestamp": time.time(),
            "peer_id": answer.peer_id,
            "stream_id": answer.stream_id or result.get("stream_id"),
            "status": result.get("status", "unknown"),
            "connected": result.get("connected", False)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error processing WebRTC answer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing WebRTC answer: {str(e)}")
        
@webrtc_router.post("/ice-candidate", response_model=Dict[str, Any])
async def add_ice_candidate(
    candidate: WebRTCICECandidate = Body(..., description="WebRTC ICE candidate")
):
    """
    Add an ICE candidate for WebRTC connection.
    
    This endpoint adds an ICE candidate for establishing a WebRTC connection.
    
    Parameters:
    - **candidate**: WebRTC ICE candidate object
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Add ICE candidate
        logger.info(f"Adding ICE candidate for peer {candidate.peer_id}")
        result = api.webrtc.add_ice_candidate(
            candidate=candidate.candidate,
            sdp_mid=candidate.sdp_mid,
            sdp_m_line_index=candidate.sdp_m_line_index,
            peer_id=candidate.peer_id,
            stream_id=candidate.stream_id
        )
        
        return {
            "success": True,
            "operation": "add_ice_candidate",
            "timestamp": time.time(),
            "peer_id": candidate.peer_id,
            "stream_id": candidate.stream_id or result.get("stream_id"),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error adding ICE candidate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding ICE candidate: {str(e)}")
        
@webrtc_router.post("/stream/start", response_model=Dict[str, Any])
async def start_stream(
    cid: str = Body(..., description="Content ID to stream"),
    stream_id: Optional[str] = Body(None, description="Stream ID (generated if not provided)"),
    config: Optional[Dict[str, Any]] = Body(None, description="Stream configuration")
):
    """
    Start streaming content.
    
    This endpoint starts streaming content via WebRTC.
    
    Parameters:
    - **cid**: Content ID to stream
    - **stream_id**: Stream ID (generated if not provided)
    - **config**: Stream configuration
    
    Returns:
        Stream details
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Start stream
        logger.info(f"Starting stream for content {cid}")
        result = api.webrtc.start_stream(
            cid=cid,
            stream_id=stream_id,
            config=config
        )
        
        return {
            "success": True,
            "operation": "start_stream",
            "timestamp": time.time(),
            "cid": cid,
            "stream_id": result.get("stream_id"),
            "status": result.get("status", "unknown"),
            "url": result.get("url"),
            "offer": result.get("offer")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error starting stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting stream: {str(e)}")
        
@webrtc_router.post("/stream/stop", response_model=Dict[str, Any])
async def stop_stream(
    stream_id: str = Body(..., description="Stream ID to stop")
):
    """
    Stop streaming content.
    
    This endpoint stops streaming content via WebRTC.
    
    Parameters:
    - **stream_id**: Stream ID to stop
    
    Returns:
        Operation status
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Stop stream
        logger.info(f"Stopping stream {stream_id}")
        result = api.webrtc.stop_stream(stream_id)
        
        return {
            "success": True,
            "operation": "stop_stream",
            "timestamp": time.time(),
            "stream_id": stream_id,
            "status": result.get("status", "unknown"),
            "duration": result.get("duration", 0)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error stopping stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error stopping stream: {str(e)}")
        
@webrtc_router.get("/streams", response_model=Dict[str, Any])
async def list_streams():
    """
    List active streams.
    
    This endpoint lists all active WebRTC streams.
    
    Returns:
        List of active streams
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # List streams
        logger.info("Listing active streams")
        result = api.webrtc.list_streams()
        
        return {
            "success": True,
            "operation": "list_streams",
            "timestamp": time.time(),
            "streams": result.get("streams", []),
            "count": result.get("count", 0)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error listing streams: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing streams: {str(e)}")
        
@webrtc_router.get("/streams/{stream_id}", response_model=Dict[str, Any])
async def get_stream_info(
    stream_id: str
):
    """
    Get stream information.
    
    This endpoint gets information about a specific WebRTC stream.
    
    Parameters:
    - **stream_id**: Stream ID
    
    Returns:
        Stream information
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Get stream info
        logger.info(f"Getting info for stream {stream_id}")
        result = api.webrtc.get_stream_info(stream_id)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Stream {stream_id} not found"
            )
            
        return {
            "success": True,
            "operation": "get_stream_info",
            "timestamp": time.time(),
            "stream_id": stream_id,
            "cid": result.get("cid"),
            "status": result.get("status", "unknown"),
            "start_time": result.get("start_time"),
            "duration": result.get("duration", 0),
            "peers": result.get("peers", []),
            "stats": result.get("stats", {})
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error getting stream info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stream info: {str(e)}")
        
@webrtc_router.post("/record/start", response_model=Dict[str, Any])
async def start_recording(
    stream_id: str = Body(..., description="Stream ID to record"),
    format: str = Body("mp4", description="Recording format (mp4, webm, hls)"),
    config: Optional[Dict[str, Any]] = Body(None, description="Recording configuration")
):
    """
    Start recording a stream.
    
    This endpoint starts recording a WebRTC stream.
    
    Parameters:
    - **stream_id**: Stream ID to record
    - **format**: Recording format (mp4, webm, hls)
    - **config**: Recording configuration
    
    Returns:
        Recording details
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Start recording
        logger.info(f"Starting recording for stream {stream_id}")
        result = api.webrtc.start_recording(
            stream_id=stream_id,
            format=format,
            config=config
        )
        
        return {
            "success": True,
            "operation": "start_recording",
            "timestamp": time.time(),
            "stream_id": stream_id,
            "recording_id": result.get("recording_id"),
            "format": format,
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error starting recording: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting recording: {str(e)}")
        
@webrtc_router.post("/record/stop", response_model=Dict[str, Any])
async def stop_recording(
    recording_id: str = Body(..., description="Recording ID to stop"),
    pin: bool = Body(True, description="Pin the recording in IPFS")
):
    """
    Stop recording a stream.
    
    This endpoint stops recording a WebRTC stream.
    
    Parameters:
    - **recording_id**: Recording ID to stop
    - **pin**: Pin the recording in IPFS
    
    Returns:
        Recording details including the CID
    """
    try:
        # Get API from request state
        api = fastapi.requests.Request.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            raise HTTPException(
                status_code=404,
                detail="WebRTC API is not available."
            )
            
        # Stop recording
        logger.info(f"Stopping recording {recording_id}")
        result = api.webrtc.stop_recording(
            recording_id=recording_id,
            pin=pin
        )
        
        return {
            "success": True,
            "operation": "stop_recording",
            "timestamp": time.time(),
            "recording_id": recording_id,
            "stream_id": result.get("stream_id"),
            "cid": result.get("cid"),
            "format": result.get("format"),
            "size": result.get("size", 0),
            "duration": result.get("duration", 0),
            "status": result.get("status", "unknown")
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error stopping recording: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error stopping recording: {str(e)}")

@webrtc_router.websocket("/signaling/{peer_id}")
async def websocket_signaling(websocket: WebSocket, peer_id: str):
    """
    WebSocket endpoint for WebRTC signaling.
    
    This endpoint provides a WebSocket connection for WebRTC signaling.
    
    Parameters:
    - **peer_id**: Peer ID for signaling
    """
    try:
        # Get API from request state
        api = websocket.state.ipfs_api
        
        # Check if WebRTC module is available
        if not hasattr(api, "webrtc"):
            await websocket.close(code=1008, reason="WebRTC API is not available")
            return
            
        # Accept connection
        await websocket.accept()
        logger.info(f"WebSocket signaling connection established for peer {peer_id}")
        
        # Register peer with signaling service
        api.webrtc.register_signaling_peer(peer_id, websocket)
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                msg = json.loads(data)
                
                # Process message
                api.webrtc.process_signaling_message(peer_id, msg)
                
                # Send response if needed
                if msg.get("type") == "offer":
                    response = {
                        "type": "answer",
                        "sdp": api.webrtc.create_answer(peer_id, msg.get("sdp")),
                        "stream_id": msg.get("stream_id")
                    }
                    await websocket.send_text(json.dumps(response))
                elif msg.get("type") == "ice-candidate":
                    # Just acknowledge receipt
                    await websocket.send_text(json.dumps({"type": "ack", "id": msg.get("id")}))
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket signaling connection closed for peer {peer_id}")
        except Exception as e:
            logger.exception(f"Error in WebSocket signaling: {str(e)}")
            await websocket.close(code=1011, reason=f"Error: {str(e)}")
        finally:
            # Unregister peer
            api.webrtc.unregister_signaling_peer(peer_id)
    except Exception as e:
        logger.exception(f"Error in WebSocket signaling setup: {str(e)}")
        try:
            await websocket.close(code=1011, reason=f"Error: {str(e)}")
        except Exception:
            pass
