#!/usr/bin/env python3
"""
libp2p controller for MCP integration with AnyIO support.

This controller provides HTTP endpoints for direct peer-to-peer communication
using libp2p, without requiring the full IPFS daemon. It exposes functionalities
for peer discovery, content routing, and direct content exchange, using AnyIO
for backend-agnostic async operations.
"""

import logging
import time
import warnings
import sniffio
from typing import Dict, List, Any, Optional, Set, Union

# AnyIO import
import anyio

# Try to import FastAPI dependencies
try:
    from fastapi import APIRouter, HTTPException, Body, Query, Path, status, Response
    from pydantic import BaseModel, Field
except ImportError:
    # For testing without FastAPI
    class APIRouter:
        def add_api_route(self, *args, **kwargs): pass
    class HTTPException(Exception): pass
    class Response: pass
    class BaseModel: pass
    def Body(*args, **kwargs): return None
    def Query(*args, **kwargs): return None
    def Path(*args, **kwargs): return None
    class Field:
        def __init__(self, *args, **kwargs): pass
    class status:
        HTTP_404_NOT_FOUND = 404
        HTTP_500_INTERNAL_SERVER_ERROR = 500
        HTTP_503_SERVICE_UNAVAILABLE = 503

# Try to import libp2p dependencies
try:
    from ipfs_kit_py.libp2p import HAS_LIBP2P
except ImportError:
    HAS_LIBP2P = False

# Import our controller
try:
    from ipfs_kit_py.mcp.controllers.libp2p_controller import (
        LibP2PController, HealthResponse, PeerDiscoveryRequest, PeerDiscoveryResponse,
        PeerConnectionRequest, ContentRequest, ContentDataRequest, ContentProvidersResponse
    )
except ImportError:
    class LibP2PController:
        pass
    class HealthResponse(BaseModel): pass
    class PeerDiscoveryRequest(BaseModel): pass
    class PeerDiscoveryResponse(BaseModel): pass
    class PeerConnectionRequest(BaseModel): pass
    class ContentRequest(BaseModel): pass
    class ContentDataRequest(BaseModel): pass
    class ContentProvidersResponse(BaseModel): pass

# Configure logger
logger = logging.getLogger(__name__)

class LibP2PControllerAnyIO(LibP2PController):
    """
    Controller for libp2p peer-to-peer operations with AnyIO support.
    
    This controller provides HTTP endpoints for direct peer-to-peer communication
    using libp2p, without requiring the full IPFS daemon. It exposes functionalities
    for peer discovery, content routing, and direct content exchange, using AnyIO
    for backend-agnostic async operations.
    """
    
    def __init__(self, libp2p_model):
        """
        Initialize the libp2p controller with AnyIO support.
        
        Args:
            libp2p_model: The libp2p model instance to use
        """
        super().__init__(libp2p_model)
        logger.info("LibP2P controller with AnyIO initialized")
    
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _warn_if_async_context(self, method_name):
        """Warn if called from async context without using async version."""
        backend = self.get_backend()
        if backend is not None:
            warnings.warn(
                f"Synchronous method {method_name} called from async context. "
                f"Use {method_name}_async instead for better performance.",
                stacklevel=3
            )
    
    # Override synchronous methods to add warnings
    def health_check(self):
        """Check libp2p health with warning in async context."""
        self._warn_if_async_context("health_check")
        return super().health_check()
    
    def discover_peers(self, request):
        """Discover peers with warning in async context."""
        self._warn_if_async_context("discover_peers")
        return super().discover_peers(request)
    
    def get_peers(self, method="all", limit=10):
        """Get peers with warning in async context."""
        self._warn_if_async_context("get_peers")
        return super().get_peers(method, limit)
    
    def connect_peer(self, request):
        """Connect to peer with warning in async context."""
        self._warn_if_async_context("connect_peer")
        return super().connect_peer(request)
    
    def find_providers(self, cid, timeout=30):
        """Find providers with warning in async context."""
        self._warn_if_async_context("find_providers")
        return super().find_providers(cid, timeout)
    
    def retrieve_content_info(self, cid, timeout=60):
        """Retrieve content info with warning in async context."""
        self._warn_if_async_context("retrieve_content_info")
        return super().retrieve_content_info(cid, timeout)
    
    def retrieve_content(self, cid, timeout=60):
        """Retrieve content with warning in async context."""
        self._warn_if_async_context("retrieve_content")
        return super().retrieve_content(cid, timeout)
    
    def announce_content(self, request):
        """Announce content with warning in async context."""
        self._warn_if_async_context("announce_content")
        return super().announce_content(request)
    
    def get_connected_peers(self):
        """Get connected peers with warning in async context."""
        self._warn_if_async_context("get_connected_peers")
        return super().get_connected_peers()
    
    def get_peer_info(self, peer_id):
        """Get peer info with warning in async context."""
        self._warn_if_async_context("get_peer_info")
        return super().get_peer_info(peer_id)
    
    def get_stats(self):
        """Get stats with warning in async context."""
        self._warn_if_async_context("get_stats")
        return super().get_stats()
    
    def reset(self):
        """Reset with warning in async context."""
        self._warn_if_async_context("reset")
        return super().reset()
    
    # Async implementation of methods
    async def health_check_async(self):
        """
        Check if libp2p is available and healthy asynchronously.
        
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
        
        # Get health from model using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.get_health
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success") and not result.get("peer_initialized"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.get("error", "libp2p service unavailable")
            )
            
        return result
    
    async def discover_peers_async(self, request: PeerDiscoveryRequest):
        """
        Discover peers using various discovery mechanisms asynchronously.
        
        Args:
            request: Peer discovery request parameters
        
        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.discover_peers,
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
    
    async def get_peers_async(
        self,
        method: str = Query("all", description="Discovery method (dht, mdns, bootstrap, all)"),
        limit: int = Query(10, description="Maximum number of peers to discover", ge=1, le=100)
    ):
        """
        Get list of discovered peers asynchronously.
        
        Args:
            method: Discovery method to use
            limit: Maximum number of peers to return
        
        Returns:
            dict: Discovered peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.discover_peers,
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
    
    async def connect_peer_async(self, request: PeerConnectionRequest):
        """
        Connect to a specific peer asynchronously.
        
        Args:
            request: Peer connection request parameters
        
        Returns:
            dict: Connection status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.connect_peer,
            peer_addr=request.peer_addr
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to connect to peer")
            )
            
        return result
    
    async def find_providers_async(
        self,
        cid: str = Path(..., description="Content ID to find providers for"),
        timeout: int = Query(30, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Find providers for a specific CID asynchronously.
        
        Args:
            cid: Content ID to find providers for
            timeout: Timeout in seconds
        
        Returns:
            dict: Content providers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.find_content,
            cid=cid,
            timeout=timeout
        )
        
        # If not successful but it's just that no providers were found,
        # return empty result instead of error
        if not result.get("success") and result.get("error_type") == "provider_lookup_error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to find content providers")
            )
            
        return result
    
    async def retrieve_content_info_async(
        self,
        cid: str = Path(..., description="Content ID to retrieve info for"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Check if content is available and get metadata asynchronously.
        
        Args:
            cid: Content ID to retrieve info for
            timeout: Timeout in seconds
        
        Returns:
            dict: Content metadata
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.retrieve_content,
            cid=cid,
            timeout=timeout
        )
        
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
    
    async def retrieve_content_async(
        self,
        cid: str = Path(..., description="Content ID to retrieve"),
        timeout: int = Query(60, description="Timeout in seconds", ge=1, le=300)
    ):
        """
        Retrieve content data by CID asynchronously.
        
        Args:
            cid: Content ID to retrieve
            timeout: Timeout in seconds
        
        Returns:
            bytes: Content data or error response
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.get_content,
            cid=cid,
            timeout=timeout
        )
        
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
            # The content type detection is the same as in the original method
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
    
    async def announce_content_async(self, request: ContentDataRequest):
        """
        Announce content availability to the network asynchronously.
        
        Args:
            request: Content announcement request parameters
        
        Returns:
            dict: Announcement status
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.announce_content,
            cid=request.cid,
            data=request.data
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to announce content")
            )
            
        return result
    
    async def get_connected_peers_async(self):
        """
        Get information about currently connected peers asynchronously.
        
        Returns:
            dict: Connected peers information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.get_connected_peers
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get connected peers")
            )
            
        return result
    
    async def get_peer_info_async(self, peer_id: str = Path(..., description="Peer ID to get info for")):
        """
        Get detailed information about a specific peer asynchronously.
        
        Args:
            peer_id: Peer ID to get info for
        
        Returns:
            dict: Peer information
        """
        # Check if libp2p is available
        is_available = await anyio.to_thread.run_sync(
            self.libp2p_model.is_available
        )
        if not is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p is not available"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.get_peer_info,
            peer_id=peer_id
        )
        
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
    
    async def get_stats_async(self):
        """
        Get operation statistics asynchronously.
        
        Returns:
            dict: Operation statistics
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized"
            )
        
        # Get stats from model using anyio
        return await anyio.to_thread.run_sync(
            self.libp2p_model.get_stats
        )
    
    async def reset_async(self):
        """
        Reset the libp2p peer, clearing caches and statistics asynchronously.
        
        Returns:
            dict: Reset status
        """
        # Check if libp2p model is initialized
        if not self.libp2p_model:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="libp2p model not initialized"
            )
        
        # Call model method using anyio
        result = await anyio.to_thread.run_sync(
            self.libp2p_model.reset
        )
        
        # If not successful, raise HTTP exception
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to reset libp2p peer")
            )
            
        return result
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with the API router. Overrides base method to use async versions.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Health check endpoint
        if "/libp2p/health" not in self.initialized_endpoints:
            router.add_api_route(
                "/libp2p/health",
                self.health_check_async,
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
                self.discover_peers_async,
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
                self.get_peers_async,
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
                self.connect_peer_async,
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
                self.find_providers_async,
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
                self.retrieve_content_info_async,
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
                self.retrieve_content_async,
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
                self.announce_content_async,
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
                self.get_connected_peers_async,
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
                self.get_peer_info_async,
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
                self.get_stats_async,
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
                self.reset_async,
                methods=["POST"],
                summary="Reset",
                description="Reset the libp2p peer, clearing caches and statistics",
                tags=["libp2p"]
            )
            self.initialized_endpoints.add("/libp2p/reset")
            
        logger.info(f"Registered libp2p controller routes with AnyIO support: {len(self.initialized_endpoints)} endpoints")