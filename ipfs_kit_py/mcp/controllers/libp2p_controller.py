"""
libp2p controller for MCP integration.

This controller provides HTTP endpoints for direct peer-to-peer communication
using libp2p, without requiring the full IPFS daemon. It exposes functionalities
for peer discovery, content routing, and direct content exchange.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Set, Union
from fastapi import APIRouter, HTTPException, Body, Query, Path, status, Response
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Try to import libp2p dependencies
try:
    from ipfs_kit_py.libp2p import HAS_LIBP2P
except ImportError:
    HAS_LIBP2P = False

# Define request/response models
class HealthResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    libp2p_available: bool = Field(..., description="Whether libp2p is available")
    peer_initialized: bool = Field(..., description="Whether the peer is initialized")
    peer_id: Optional[str] = Field(None, description="The peer ID if initialized")
    addresses: Optional[List[str]] = Field(None, description="Listen addresses")
    connected_peers: Optional[int] = Field(None, description="Number of connected peers")
    dht_peers: Optional[int] = Field(None, description="Number of peers in DHT routing table")
    protocols: Optional[List[str]] = Field(None, description="Supported protocols")
    role: Optional[str] = Field(None, description="Node role (master, worker, leecher)")
    stats: Optional[Dict[str, Any]] = Field(None, description="Operation statistics")
    error: Optional[str] = Field(None, description="Error message if any")
    error_type: Optional[str] = Field(None, description="Type of error if any")

class PeerDiscoveryRequest(BaseModel):
    discovery_method: str = Field("all", description="Discovery method (dht, mdns, bootstrap, all)")
    limit: int = Field(10, description="Maximum number of peers to discover", ge=1, le=100)

class PeerDiscoveryResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    peers: List[str] = Field([], description="Discovered peer addresses")
    peer_count: Optional[int] = Field(None, description="Number of discovered peers")
    error: Optional[str] = Field(None, description="Error message if any")
    error_type: Optional[str] = Field(None, description="Type of error if any")

class PeerConnectionRequest(BaseModel):
    peer_addr: str = Field(..., description="Peer multiaddress to connect to")

class ContentRequest(BaseModel):
    cid: str = Field(..., description="Content ID to retrieve or announce")
    timeout: Optional[int] = Field(60, description="Timeout in seconds", ge=1, le=300)

class ContentDataRequest(BaseModel):
    cid: str = Field(..., description="Content ID to announce")
    data: bytes = Field(..., description="Content data to store and announce")

class ContentProvidersResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation was successful")
    providers: List[str] = Field([], description="Content provider addresses")
    provider_count: Optional[int] = Field(None, description="Number of providers")
    error: Optional[str] = Field(None, description="Error message if any")
    error_type: Optional[str] = Field(None, description="Type of error if any")

class LibP2PController:
    """
    Controller for libp2p peer-to-peer operations.
    
    This controller provides HTTP endpoints for direct peer-to-peer communication
    using libp2p, without requiring the full IPFS daemon. It exposes functionalities
    for peer discovery, content routing, and direct content exchange.
    """
    
    def __init__(self, libp2p_model):
        """
        Initialize the libp2p controller.
        
        Args:
            libp2p_model: The libp2p model instance to use
        """
        self.libp2p_model = libp2p_model
        self.initialized_endpoints = set()
        
    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Health check endpoint
        if "/libp2p/health" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/health",
                self.health_check,
                methods=["GET"],
                response_model=HealthResponse,
                summary="Check libp2p health",
                description="Check if libp2p is available and get peer health information",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/health")
            
        # Peer discovery endpoint
        if "/libp2p/discover" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/discover",
                self.discover_peers,
                methods=["POST"],
                response_model=PeerDiscoveryResponse,
                summary="Discover peers",
                description="Discover peers using various discovery mechanisms",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/discover")
            
        # Simple peer discovery with GET
        if "/libp2p/peers" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/peers",
                self.get_peers,
                methods=["GET"],
                response_model=PeerDiscoveryResponse,
                summary="List peers",
                description="Get list of discovered peers",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/peers")
            
        # Connect to peer endpoint
        if "/libp2p/connect" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/connect",
                self.connect_peer,
                methods=["POST"],
                summary="Connect to peer",
                description="Connect to a specific peer using multiaddr",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/connect")
            
        # Find content providers endpoint
        if "/libp2p/providers/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/providers/{cid}",
                self.find_providers,
                methods=["GET"],
                response_model=ContentProvidersResponse,
                summary="Find content providers",
                description="Find providers for a specific CID",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/providers/{cid}")
            
        # Retrieve content metadata endpoint
        if "/libp2p/content/info/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/content/info/{cid}",
                self.retrieve_content_info,
                methods=["GET"],
                summary="Get content info",
                description="Check if content is available and get metadata",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/content/info/{cid}")
            
        # Retrieve content data endpoint
        if "/libp2p/content/{cid}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/content/{cid}",
                self.retrieve_content,
                methods=["GET"],
                summary="Get content",
                description="Retrieve content data by CID",
                tags=["libp2p"],
                response_class=Response
            )
            self.initialized_endpoints.add("/libp2p/content/{cid}")
            
        # Announce content endpoint
        if "/libp2p/announce" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/announce",
                self.announce_content,
                methods=["POST"],
                summary="Announce content",
                description="Announce content availability to the network",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/announce")
            
        # Get connected peers endpoint
        if "/libp2p/connected" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/connected",
                self.get_connected_peers,
                methods=["GET"],
                summary="Get connected peers",
                description="Get information about currently connected peers",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/connected")
            
        # Get peer info endpoint
        if "/libp2p/peer/{peer_id}" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/peer/{peer_id}",
                self.get_peer_info,
                methods=["GET"],
                summary="Get peer info",
                description="Get detailed information about a specific peer",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/peer/{peer_id}")
            
        # Get stats endpoint
        if "/libp2p/stats" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/stats",
                self.get_stats,
                methods=["GET"],
                summary="Get stats",
                description="Get operation statistics",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/stats")
            
        # Reset endpoint
        if "/libp2p/reset" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/reset",
                self.reset,
                methods=["POST"],
                summary="Reset",
                description="Reset the libp2p peer, clearing caches and statistics",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/reset")
            
        logger.info(f"Registered libp2p controller routes: {len(self.initialized_endpoints)} endpoints")
    
    async def health_check(self):
        """
        Check if libp2p is available and healthy.
        
        Returns:
            dict: Health status information
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            return {
                "success": False,
                "libp2p_available": False,
                "peer_initialized": False,
                "error": "libp2p model not initialized",
                "error_type": "initialization_error"
            }
        
        # Get health from model
        result = self.libp2p_model.get_health()
        
        # If not successful, raise HTTP exception
        if not result.get("success") and not result.get("peer_initialized"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.get("error", "libp2p service unavailable")
            )
            
        return result
    
    async def discover_peers(self, request: PeerDiscoveryRequest):
        """
        Discover peers using various discovery mechanisms.
        
        Args:
            request: Peer discovery request parameters
        
        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.discover_peers(
            discovery_method=request.discovery_method,
            limit=request.limit
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to discover peers")
            )
            
        return result
    
    async def get_peers(
        self,
        method: str = Query("all", description="Discovery method (dht, mdns, bootstrap, all)"),
        limit: int = Query(10, description="Maximum number of peers to discover", ge=1, le=100)
    ):
        """
        Get list of discovered peers.
        
        Args:
            method: Discovery method to use
            limit: Maximum number of peers to return
        
        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.discover_peers(
            discovery_method=method,
            limit=limit
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to discover peers")
            )
            
        return result
    
    async def connect_peer(self, request: PeerConnectionRequest):
        """
        Connect to a specific peer.
        
        Args:
            request: Peer connection request parameters
        
        Returns:
            dict: Connection status
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.connect_peer(request.peer_addr)
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to connect to peer")
            )
            
        return result
    
    async def find_providers(
        self,
        cid: str = Path(..., description="Content ID to find providers for"),
        timeout: int = Query(30, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Find providers for a specific CID.
        
        Args:
            cid: Content ID to find providers for
            timeout: Timeout in seconds
        
        Returns:
            dict: Content providers information
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.find_content(cid, timeout=timeout)
        
        # If not successful but it's just that no providers were found,
        # return empty result instead of error
        if not result.get("success") and result.get("error_type") == "provider_lookup_error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to find content providers")
            )
            
        return result
    
    async def retrieve_content_info(
        self,
        cid: str = Path(..., description="Content ID to retrieve info for"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Check if content is available and get metadata.
        
        Args:
            cid: Content ID to retrieve info for
            timeout: Timeout in seconds
        
        Returns:
            dict: Content metadata
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.retrieve_content(cid, timeout=timeout)
        
        # If not successful and content not found, return 404
        if not result.get("success") and result.get("error_type") == "content_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Content not found: {cid}")
            )
            
        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to retrieve content info")
            )
            
        return result
    
    async def retrieve_content(
        self,
        cid: str = Path(..., description="Content ID to retrieve"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Retrieve content data by CID.
        
        Args:
            cid: Content ID to retrieve
            timeout: Timeout in seconds
        
        Returns:
            bytes: Content data or error response
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.get_content(cid, timeout=timeout)
        
        # If not successful and content not found, return 404
        if not result.get("success") and result.get("error_type") == "content_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Content not found: {cid}")
            )
            
        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to retrieve content")
            )
            
        # Return content data directly
        content_data = result.get("data")
        
        # Try to detect content type
        content_type = "application/octet-stream"
        if content_data and len(content_data) > 2:
            # Check for common magic bytes
            if content_data.startswith(b"\xff\xd8\xff"):
                content_type = "image/jpeg"
            elif content_data.startswith(b"\x89PNG\r\n\x1a\n"):
                content_type = "image/png"
            elif content_data.startswith(b"GIF87a") or content_data.startswith(b"GIF89a"):
                content_type = "image/gif"
            elif content_data.startswith(b"%PDF"):
                content_type = "application/pdf"
            elif content_data.startswith(b"PK\x03\x04"):
                content_type = "application/zip"
            # Text detection
            elif all(c < 128 and c >= 32 or c in (9, 10, 13) for c in content_data[:100]):
                try:
                    # Check if it's JSON
                    if (content_data.startswith(b"{") and content_data.rstrip().endswith(b"}")) or \
                       (content_data.startswith(b"[") and content_data.rstrip().endswith(b"]")):
                        content_type = "application/json"
                    else:
                        content_type = "text/plain"
                except:
                    content_type = "text/plain"
        
        return Response(
            content=content_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={cid}",
                "X-Content-CID": cid,
                "X-Content-Size": str(len(content_data)) if content_data else "0"
            }
        )
    
    async def announce_content(self, request: ContentDataRequest):
        """
        Announce content availability to the network.
        
        Args:
            request: Content announcement request parameters
        
        Returns:
            dict: Announcement status
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.announce_content(request.cid, data=request.data)
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to announce content")
            )
            
        return result
    
    async def get_connected_peers(self):
        """
        Get information about currently connected peers.
        
        Returns:
            dict: Connected peers information
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.get_connected_peers()
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get connected peers")
            )
            
        return result
    
    async def get_peer_info(self, peer_id: str = Path(..., description="Peer ID to get info for")):
        """
        Get detailed information about a specific peer.
        
        Args:
            peer_id: Peer ID to get info for
        
        Returns:
            dict: Peer information
        """
        # Check if libp2p is available
        if not self.libp2p_model.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method
        result = self.libp2p_model.get_peer_info(peer_id)
        
        # If not successful and peer not found, return 404
        if not result.get("success") and result.get("error_type") == "peer_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", f"Peer not found: {peer_id}")
            )
            
        # If other error, return 500
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get peer info")
            )
            
        return result
    
    async def get_stats(self):
        """
        Get operation statistics.
        
        Returns:
            dict: Operation statistics
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized"
            )
        
        # Get stats from model
        return self.libp2p_model.get_stats()
    
    async def reset(self):
        """
        Reset the libp2p peer, clearing caches and statistics.
        
        Returns:
            dict: Reset status
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized"
            )
        
        # Call model method
        result = self.libp2p_model.reset()
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to reset libp2p peer")
            )
            
        return result